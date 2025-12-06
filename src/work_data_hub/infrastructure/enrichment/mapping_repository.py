"""
Company Mapping Repository for database access layer.

This module provides the CompanyMappingRepository class for batch-optimized
database operations on the enterprise.company_mapping table.

Story 6.3: Internal Mapping Tables and Database Schema
Architecture Reference: AD-010 Infrastructure Layer

Repository Pattern:
- Accepts upstream Connection/Session; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via text(); no f-strings
- Log counts only; never log alias/company_id values
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import Connection, text

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MatchResult:
    """
    Result of a company mapping lookup.

    Attributes:
        company_id: The resolved canonical company ID.
        match_type: Type of match (plan/account/hardcode/name/account_name).
        priority: Priority level (1-5, lower is higher priority).
        source: Source of the mapping (internal/eqc/pipeline_backflow).
    """

    company_id: str
    match_type: str
    priority: int
    source: str


@dataclass
class InsertBatchResult:
    """
    Result of a batch insert operation with conflict detection.

    Attributes:
        inserted_count: Number of rows successfully inserted.
        skipped_count: Number of rows skipped due to existing entries.
        conflicts: List of conflicts where alias_name exists but company_id differs.
    """

    inserted_count: int
    skipped_count: int
    conflicts: List[Dict[str, Any]] = field(default_factory=list)


class CompanyMappingRepository:
    """
    Database access layer for enterprise.company_mapping table.

    This repository provides batch-optimized operations for company mapping
    lookups and inserts, following the repository pattern with explicit
    transaction management by the caller.

    Attributes:
        connection: SQLAlchemy Connection for database operations.

    Example:
        >>> from sqlalchemy import create_engine
        >>> engine = create_engine(database_url)
        >>> with engine.connect() as conn:
        ...     repo = CompanyMappingRepository(conn)
        ...     results = repo.lookup_batch(["FP0001", "FP0002"])
        ...     conn.commit()
    """

    def __init__(self, connection: Connection) -> None:
        """
        Initialize the repository with a database connection.

        Args:
            connection: SQLAlchemy Connection. Caller owns transaction lifecycle.
        """
        self.connection = connection

    def lookup_batch(
        self,
        alias_names: List[str],
        match_types: Optional[List[str]] = None,
    ) -> Dict[str, MatchResult]:
        """
        Batch lookup mappings from enterprise.company_mapping table.

        Returns the highest priority match per alias_name using DISTINCT ON
        with ORDER BY priority ASC.

        Args:
            alias_names: List of alias names to look up.
            match_types: Optional list of match types to filter by.
                If None, all match types are included.

        Returns:
            Dict mapping alias_name to MatchResult for found entries.
            Missing aliases are not included in the result.

        Performance:
            Single SQL round-trip using DISTINCT ON + ORDER BY priority ASC.
            Target: <100ms for 1,000 alias_names.
        """
        if not alias_names:
            logger.debug("mapping_repository.lookup_batch.empty_input")
            return {}

        # Build query with optional match_type filter
        if match_types:
            query = text("""
                SELECT DISTINCT ON (alias_name)
                    alias_name, canonical_id, match_type, priority, source
                FROM enterprise.company_mapping
                WHERE alias_name = ANY(:alias_names)
                  AND match_type = ANY(:match_types)
                ORDER BY alias_name, priority ASC
            """)
            params = {"alias_names": alias_names, "match_types": match_types}
        else:
            query = text("""
                SELECT DISTINCT ON (alias_name)
                    alias_name, canonical_id, match_type, priority, source
                FROM enterprise.company_mapping
                WHERE alias_name = ANY(:alias_names)
                ORDER BY alias_name, priority ASC
            """)
            params = {"alias_names": alias_names}

        result = self.connection.execute(query, params)
        rows = result.fetchall()

        # Build result dict
        results: Dict[str, MatchResult] = {}
        for row in rows:
            results[row.alias_name] = MatchResult(
                company_id=row.canonical_id,
                match_type=row.match_type,
                priority=row.priority,
                source=row.source,
            )

        logger.info(
            "mapping_repository.lookup_batch.completed",
            input_count=len(alias_names),
            found_count=len(results),
            match_types_filter=match_types,
        )

        return results

    def insert_batch(
        self,
        mappings: List[Dict[str, Any]],
    ) -> int:
        """
        Batch insert mappings with ON CONFLICT DO NOTHING.

        Inserts mappings idempotently - existing entries are silently skipped.
        Caller owns transaction; commit after this call if desired.

        Args:
            mappings: List of mapping dicts with keys:
                - alias_name: str (required)
                - canonical_id: str (required)
                - match_type: str (required)
                - priority: int (required, 1-5)
                - source: str (optional, defaults to 'internal')

        Returns:
            Number of rows actually inserted (excludes skipped duplicates).

        Example:
            >>> mappings = [
            ...     {"alias_name": "FP0001", "canonical_id": "614810477",
            ...      "match_type": "plan", "priority": 1},
            ... ]
            >>> inserted = repo.insert_batch(mappings)
        """
        if not mappings:
            logger.debug("mapping_repository.insert_batch.empty_input")
            return 0

        # Prepare values for bulk insert
        values_list = []
        for m in mappings:
            values_list.append(
                {
                    "alias_name": m["alias_name"],
                    "canonical_id": m["canonical_id"],
                    "match_type": m["match_type"],
                    "priority": m["priority"],
                    "source": m.get("source", "internal"),
                }
            )

        # Use executemany with ON CONFLICT DO NOTHING
        query = text("""
            INSERT INTO enterprise.company_mapping
                (alias_name, canonical_id, match_type, priority, source)
            VALUES
                (:alias_name, :canonical_id, :match_type, :priority, :source)
            ON CONFLICT (alias_name, match_type) DO NOTHING
        """)

        # Execute batch insert
        result = self.connection.execute(query, values_list)
        inserted_count = result.rowcount

        logger.info(
            "mapping_repository.insert_batch.completed",
            input_count=len(mappings),
            inserted_count=inserted_count,
            skipped_count=len(mappings) - inserted_count,
        )

        return inserted_count

    def insert_batch_with_conflict_check(
        self,
        mappings: List[Dict[str, Any]],
    ) -> InsertBatchResult:
        """
        Batch insert with conflict detection for pipeline backflow.

        Detects conflicts where alias_name+match_type exists but canonical_id
        differs from the new value. This is useful for identifying data
        inconsistencies during backflow operations.

        Args:
            mappings: List of mapping dicts (same format as insert_batch).

        Returns:
            InsertBatchResult with inserted_count, skipped_count, and conflicts.
            Conflicts list contains dicts with:
                - alias_name: The conflicting alias
                - match_type: The match type
                - existing_id: The existing canonical_id in database
                - new_id: The new canonical_id that was attempted

        Example:
            >>> result = repo.insert_batch_with_conflict_check(mappings)
            >>> if result.conflicts:
            ...     logger.warning(f"Found {len(result.conflicts)} conflicts")
        """
        if not mappings:
            logger.debug(
                "mapping_repository.insert_batch_with_conflict_check.empty_input"
            )
            return InsertBatchResult(inserted_count=0, skipped_count=0, conflicts=[])

        # Step 1: Prefetch existing rows for conflict detection
        alias_match_pairs = [(m["alias_name"], m["match_type"]) for m in mappings]

        alias_names = [p[0] for p in alias_match_pairs]
        match_types = [p[1] for p in alias_match_pairs]

        # Ensure pairs are aligned; use ordinality to keep positional pairing
        existing_query = text("""
            WITH input_pairs AS (
                SELECT a.alias_name, m.match_type
                FROM unnest(:alias_names) WITH ORDINALITY AS a(alias_name, idx)
                JOIN unnest(:match_types) WITH ORDINALITY AS m(match_type, idx)
                  ON a.idx = m.idx
            )
            SELECT cm.alias_name, cm.match_type, cm.canonical_id
            FROM enterprise.company_mapping AS cm
            JOIN input_pairs AS ip
              ON cm.alias_name = ip.alias_name
             AND cm.match_type = ip.match_type
        """)

        existing_result = self.connection.execute(
            existing_query,
            {"alias_names": alias_names, "match_types": match_types},
        )
        existing_rows = existing_result.fetchall()

        # Build lookup dict: (alias_name, match_type) -> canonical_id
        existing_map: Dict[tuple[str, str], str] = {}
        for row in existing_rows:
            existing_map[(row.alias_name, row.match_type)] = row.canonical_id

        # Step 2: Identify conflicts and new entries
        conflicts: List[Dict[str, Any]] = []
        new_mappings: List[Dict[str, Any]] = []

        for m in mappings:
            key = (m["alias_name"], m["match_type"])
            if key in existing_map:
                existing_id = existing_map[key]
                new_id = m["canonical_id"]
                if existing_id != new_id:
                    conflicts.append(
                        {
                            "alias_name": m["alias_name"],
                            "match_type": m["match_type"],
                            "existing_id": existing_id,
                            "new_id": new_id,
                        }
                    )
                # Skip this entry (already exists)
            else:
                new_mappings.append(m)

        # Step 3: Insert new entries
        inserted_count = 0
        if new_mappings:
            inserted_count = self.insert_batch(new_mappings)

        skipped_count = len(mappings) - inserted_count

        logger.info(
            "mapping_repository.insert_batch_with_conflict_check.completed",
            input_count=len(mappings),
            inserted_count=inserted_count,
            skipped_count=skipped_count,
            conflict_count=len(conflicts),
        )

        return InsertBatchResult(
            inserted_count=inserted_count,
            skipped_count=skipped_count,
            conflicts=conflicts,
        )

    def get_all_mappings(
        self,
        match_types: Optional[List[str]] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all mappings from the database.

        Utility method for debugging and data export. Use with caution
        on large datasets.

        Args:
            match_types: Optional filter by match types.
            limit: Maximum number of rows to return (default 10000).

        Returns:
            List of mapping dicts with all columns.
        """
        if match_types:
            query = text("""
                SELECT alias_name, canonical_id, match_type, priority, source,
                       created_at, updated_at
                FROM enterprise.company_mapping
                WHERE match_type = ANY(:match_types)
                ORDER BY priority ASC, alias_name ASC
                LIMIT :limit
            """)
            params = {"match_types": match_types, "limit": limit}
        else:
            query = text("""
                SELECT alias_name, canonical_id, match_type, priority, source,
                       created_at, updated_at
                FROM enterprise.company_mapping
                ORDER BY priority ASC, alias_name ASC
                LIMIT :limit
            """)
            params = {"limit": limit}

        result = self.connection.execute(query, params)
        rows = result.fetchall()

        mappings = []
        for row in rows:
            mappings.append(
                {
                    "alias_name": row.alias_name,
                    "canonical_id": row.canonical_id,
                    "match_type": row.match_type,
                    "priority": row.priority,
                    "source": row.source,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )

        logger.debug(
            "mapping_repository.get_all_mappings.completed",
            count=len(mappings),
            match_types_filter=match_types,
        )

        return mappings

    def delete_by_source(self, source: str) -> int:
        """
        Delete all mappings from a specific source.

        Useful for clearing pipeline_backflow entries before re-import.

        Args:
            source: Source value to delete (e.g., 'pipeline_backflow').

        Returns:
            Number of rows deleted.
        """
        query = text("""
            DELETE FROM enterprise.company_mapping
            WHERE source = :source
        """)

        result = self.connection.execute(query, {"source": source})
        deleted_count = result.rowcount

        logger.info(
            "mapping_repository.delete_by_source.completed",
            source=source,
            deleted_count=deleted_count,
        )

        return deleted_count
