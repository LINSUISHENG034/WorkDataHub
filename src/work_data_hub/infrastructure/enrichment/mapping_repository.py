"""
Company Mapping Repository for database access layer.

This module provides the CompanyMappingRepository class for batch-optimized
database operations on the enterprise.company_mapping table.

Story 6.3: Internal Mapping Tables and Database Schema
Story 6.1.1: Extended with enrichment_index table operations
Architecture Reference: AD-010 Infrastructure Layer

Repository Pattern:
- Accepts upstream Connection/Session; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via text(); no f-strings
- Log counts only; never log alias/company_id values
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import Connection, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, NUMERIC, TEXT

from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)
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


@dataclass
class EnqueueResult:
    """
    Result of an async enrichment queue operation (Story 6.5).

    Attributes:
        queued_count: Number of requests actually enqueued.
        skipped_count: Number of requests skipped (duplicates via partial unique index).
    """

    queued_count: int
    skipped_count: int


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

    @staticmethod
    def _normalize_lookup_key(lookup_key: str, lookup_type: LookupType) -> str:
        """
        Normalize lookup keys for enrichment_index operations.

        AC7: Reuse shared normalizer for customer_name/plan_customer keys.
        """
        if lookup_key is None:
            return ""

        if lookup_type == LookupType.CUSTOMER_NAME:
            return normalize_for_temp_id(str(lookup_key))

        if lookup_type == LookupType.PLAN_CUSTOMER:
            # Expect format {plan_code}|{customer_name}; normalize customer_name
            raw = str(lookup_key)
            if "|" in raw:
                plan_code, customer = raw.split("|", 1)
                normalized_customer = normalize_for_temp_id(customer)
                return f"{plan_code}|{normalized_customer}"
            # Fallback: normalize whole key to avoid missing hits
            return normalize_for_temp_id(raw)

        return str(lookup_key)

    def insert_company_name_index_batch(
        self,
        rows: List[Dict[str, Any]],
    ) -> InsertBatchResult:
        """
        Batch insert into enterprise.company_name_index (Story 6.6 cache).

        Writes normalized name → company_id mappings for EQC results. Uses
        ON CONFLICT DO NOTHING to remain idempotent and avoid blocking
        failures. Minimal column set to avoid schema drift issues.

        Args:
            rows: List of dicts with keys:
                - normalized_name: str
                - company_id: str
                - match_type: str
                - confidence: float

        Returns:
            InsertBatchResult indicating inserted/skipped counts.
        """
        if not rows:
            logger.debug(
                "mapping_repository.insert_company_name_index_batch.empty_input"
            )
            return InsertBatchResult(inserted_count=0, skipped_count=0)

        # Prepare payload; keep only expected columns to avoid schema errors
        values = [
            {
                "normalized_name": row["normalized_name"],
                "company_id": row["company_id"],
                "match_type": row.get("match_type", "eqc"),
                "confidence": row.get("confidence", 0.0),
            }
            for row in rows
        ]

        query = text(
            """
            INSERT INTO enterprise.company_name_index
                (normalized_name, company_id, match_type, confidence)
            VALUES
                (:normalized_name, :company_id, :match_type, :confidence)
            ON CONFLICT (normalized_name) DO NOTHING
            """
        )

        result = self.connection.execute(query, values)
        inserted = result.rowcount
        skipped = len(values) - inserted

        logger.info(
            "mapping_repository.insert_company_name_index_batch.completed",
            input_count=len(values),
            inserted_count=inserted,
            skipped_count=skipped,
        )

        return InsertBatchResult(
            inserted_count=inserted, skipped_count=skipped, conflicts=[]
        )

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

    def enqueue_for_enrichment(
        self,
        requests: List[Dict[str, str]],
    ) -> EnqueueResult:
        """
        Batch enqueue company names for async enrichment (Story 6.5).

        Inserts requests into enterprise.enrichment_requests table with
        ON CONFLICT DO NOTHING to handle the partial unique index on
        normalized_name for pending/processing status.

        Args:
            requests: List of dicts with keys:
                - raw_name: str (original company name)
                - normalized_name: str (normalized for deduplication)
                - temp_id: str (generated temporary ID)

        Returns:
            EnqueueResult with queued_count and skipped_count.

        Performance:
            Single batch INSERT statement; target <50ms for 100 requests.

        Example:
            >>> requests = [
            ...     {"raw_name": "公司A", "normalized_name": "公司a",
            ...      "temp_id": "IN_ABC123"},
            ... ]
            >>> result = repo.enqueue_for_enrichment(requests)
            >>> print(f"Queued: {result.queued_count}")
        """
        if not requests:
            logger.debug("mapping_repository.enqueue_for_enrichment.empty_input")
            return EnqueueResult(queued_count=0, skipped_count=0)

        raw_names = [req["raw_name"] for req in requests]
        normalized_names = [req["normalized_name"] for req in requests]
        temp_ids = [req["temp_id"] for req in requests]

        # Single-statement INSERT ... SELECT with UNNEST to avoid executemany
        # and honor the partial unique index on normalized_name for pending/processing.
        #
        # NOTE: Avoid Postgres casts like ":param::text[]" because SQLAlchemy/psycopg2
        # will treat ":" as a literal in the final SQL. Use typed bindparams instead.
        query = text(
            """
            INSERT INTO enterprise.enrichment_requests
                (raw_name, normalized_name, temp_id, status, created_at)
            SELECT
                raw_name,
                normalized_name,
                temp_id,
                'pending' AS status,
                NOW() AS created_at
            FROM unnest(
                :raw_names,
                :normalized_names,
                :temp_ids
            ) AS t(raw_name, normalized_name, temp_id)
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            bindparam("raw_names", type_=ARRAY(TEXT)),
            bindparam("normalized_names", type_=ARRAY(TEXT)),
            bindparam("temp_ids", type_=ARRAY(TEXT)),
        )

        result = self.connection.execute(
            query,
            {
                "raw_names": raw_names,
                "normalized_names": normalized_names,
                "temp_ids": temp_ids,
            },
        )
        queued_count = result.rowcount
        skipped_count = len(requests) - queued_count

        logger.info(
            "mapping_repository.enqueue_for_enrichment.completed",
            input_count=len(requests),
            queued_count=queued_count,
            skipped_count=skipped_count,
        )

        return EnqueueResult(queued_count=queued_count, skipped_count=skipped_count)

    # =========================================================================
    # Story 6.1.1: Enrichment Index Operations
    # =========================================================================

    def lookup_enrichment_index(
        self,
        lookup_key: str,
        lookup_type: LookupType,
    ) -> Optional[EnrichmentIndexRecord]:
        """
        Single lookup in enterprise.enrichment_index table (Story 6.1.1).

        Args:
            lookup_key: The lookup key value (normalized for customer_name/plan_customer).
            lookup_type: Type of lookup (plan_code, account_name, etc.).

        Returns:
            EnrichmentIndexRecord if found, None otherwise.

        Example:
            >>> record = repo.lookup_enrichment_index("FP0001", LookupType.PLAN_CODE)
            >>> if record:
            ...     print(f"Found: {record.company_id}")
        """
        normalized_key = self._normalize_lookup_key(lookup_key, lookup_type)

        query = text("""
            SELECT lookup_key, lookup_type, company_id, confidence, source,
                   source_domain, source_table, hit_count, last_hit_at,
                   created_at, updated_at
            FROM enterprise.enrichment_index
            WHERE lookup_key = :lookup_key AND lookup_type = :lookup_type
        """)

        result = self.connection.execute(
            query,
            {"lookup_key": normalized_key, "lookup_type": lookup_type.value},
        )
        row = result.fetchone()

        if row is None:
            logger.debug(
                "mapping_repository.lookup_enrichment_index.not_found",
                lookup_type=lookup_type.value,
            )
            return None

        record = EnrichmentIndexRecord.from_dict(
            {
                "lookup_key": row.lookup_key,
                "lookup_type": row.lookup_type,
                "company_id": row.company_id,
                "confidence": row.confidence,
                "source": row.source,
                "source_domain": row.source_domain,
                "source_table": row.source_table,
                "hit_count": row.hit_count,
                "last_hit_at": row.last_hit_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

        logger.debug(
            "mapping_repository.lookup_enrichment_index.found",
            lookup_type=lookup_type.value,
        )
        return record

    def lookup_enrichment_index_batch(
        self,
        keys_by_type: Dict[LookupType, List[str]],
    ) -> Dict[tuple[LookupType, str], EnrichmentIndexRecord]:
        """
        Batch lookup in enterprise.enrichment_index table (Story 6.1.1).

        Efficiently queries multiple lookup keys across different types in a
        single database round-trip.

        Args:
            keys_by_type: Dictionary mapping LookupType to list of lookup keys.
                Example: {LookupType.PLAN_CODE: ["FP0001", "FP0002"],
                         LookupType.CUSTOMER_NAME: ["中国平安"]}

        Returns:
            Dictionary mapping (LookupType, lookup_key) tuples to EnrichmentIndexRecord.
            Missing keys are not included in the result.

        Performance:
            Single SQL round-trip using UNNEST for batch query.
            Target: <100ms for 1,000 keys.

        Example:
            >>> keys = {
            ...     LookupType.PLAN_CODE: ["FP0001", "FP0002"],
            ...     LookupType.CUSTOMER_NAME: ["中国平安"],
            ... }
            >>> results = repo.lookup_enrichment_index_batch(keys)
            >>> for (lookup_type, key), record in results.items():
            ...     print(f"{lookup_type.value}:{key} -> {record.company_id}")
        """
        if not keys_by_type:
            logger.debug("mapping_repository.lookup_enrichment_index_batch.empty_input")
            return {}

        # Flatten keys_by_type into parallel arrays for UNNEST
        lookup_keys: List[str] = []
        lookup_types: List[str] = []
        for lookup_type, keys in keys_by_type.items():
            for key in keys:
                normalized_key = self._normalize_lookup_key(key, lookup_type)
                lookup_keys.append(normalized_key)
                lookup_types.append(lookup_type.value)

        if not lookup_keys:
            return {}

        # Use UNNEST with ordinality to maintain pairing
        query = text("""
            WITH input_pairs AS (
                SELECT k.key AS lookup_key, t.type AS lookup_type
                FROM unnest(:lookup_keys) WITH ORDINALITY AS k(key, idx)
                JOIN unnest(:lookup_types) WITH ORDINALITY AS t(type, idx)
                  ON k.idx = t.idx
            )
            SELECT ei.lookup_key, ei.lookup_type, ei.company_id, ei.confidence,
                   ei.source, ei.source_domain, ei.source_table, ei.hit_count,
                   ei.last_hit_at, ei.created_at, ei.updated_at
            FROM enterprise.enrichment_index AS ei
            JOIN input_pairs AS ip
              ON ei.lookup_key = ip.lookup_key
             AND ei.lookup_type = ip.lookup_type
        """)

        result = self.connection.execute(
            query,
            {"lookup_keys": lookup_keys, "lookup_types": lookup_types},
        )
        rows = result.fetchall()

        # Build result dict
        results: Dict[tuple[LookupType, str], EnrichmentIndexRecord] = {}
        for row in rows:
            record = EnrichmentIndexRecord.from_dict(
                {
                    "lookup_key": row.lookup_key,
                    "lookup_type": row.lookup_type,
                    "company_id": row.company_id,
                    "confidence": row.confidence,
                    "source": row.source,
                    "source_domain": row.source_domain,
                    "source_table": row.source_table,
                    "hit_count": row.hit_count,
                    "last_hit_at": row.last_hit_at,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
            results[(record.lookup_type, record.lookup_key)] = record

        logger.info(
            "mapping_repository.lookup_enrichment_index_batch.completed",
            input_count=len(lookup_keys),
            found_count=len(results),
        )

        return results

    def insert_enrichment_index_batch(
        self,
        records: List[EnrichmentIndexRecord],
    ) -> InsertBatchResult:
        """
        Batch insert into enterprise.enrichment_index with conflict handling (Story 6.1.1).

        Uses ON CONFLICT DO UPDATE with the following semantics:
        - confidence: GREATEST(existing, new) - keep higher confidence
        - hit_count: existing + 1 - increment on conflict
        - last_hit_at: NOW() - update timestamp
        - updated_at: NOW() - update timestamp
        - source/source_domain/source_table: Keep existing unless new confidence is higher

        Args:
            records: List of EnrichmentIndexRecord to insert.

        Returns:
            InsertBatchResult with inserted_count and skipped_count.
            Note: Due to UPSERT semantics, skipped_count represents updates.

        Example:
            >>> records = [
            ...     EnrichmentIndexRecord(
            ...         lookup_key="FP0001",
            ...         lookup_type=LookupType.PLAN_CODE,
            ...         company_id="614810477",
            ...         source=SourceType.YAML,
            ...     ),
            ... ]
            >>> result = repo.insert_enrichment_index_batch(records)
            >>> print(f"Inserted: {result.inserted_count}")
        """
        if not records:
            logger.debug("mapping_repository.insert_enrichment_index_batch.empty_input")
            return InsertBatchResult(inserted_count=0, skipped_count=0)

        # Prepare values for batch insert
        lookup_keys = [
            self._normalize_lookup_key(r.lookup_key, r.lookup_type) for r in records
        ]
        lookup_types = [r.lookup_type.value for r in records]
        company_ids = [r.company_id for r in records]
        confidences = [float(r.confidence) for r in records]
        sources = [r.source.value for r in records]
        source_domains = [r.source_domain for r in records]
        source_tables = [r.source_table for r in records]

        # Use UNNEST for efficient batch insert with ON CONFLICT DO UPDATE
        # Conflict handling:
        # - confidence: GREATEST keeps higher value
        # - hit_count: increment on conflict (cache hit)
        # - timestamps: update on conflict
        # - source fields: keep existing unless new confidence is strictly higher
        query = text("""
            INSERT INTO enterprise.enrichment_index
                (lookup_key, lookup_type, company_id, confidence, source,
                 source_domain, source_table, hit_count, created_at, updated_at)
            SELECT
                lookup_key, lookup_type, company_id, confidence, source,
                source_domain, source_table, 0 AS hit_count,
                NOW() AS created_at, NOW() AS updated_at
            FROM unnest(
                CAST(:lookup_keys AS text[]),
                CAST(:lookup_types AS text[]),
                CAST(:company_ids AS text[]),
                CAST(:confidences AS numeric[]),
                CAST(:sources AS text[]),
                CAST(:source_domains AS text[]),
                CAST(:source_tables AS text[])
            ) AS t(lookup_key, lookup_type, company_id, confidence, source,
                   source_domain, source_table)
            ON CONFLICT (lookup_key, lookup_type) DO UPDATE SET
                confidence = GREATEST(
                    enterprise.enrichment_index.confidence,
                    EXCLUDED.confidence
                ),
                company_id = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.company_id
                    ELSE enterprise.enrichment_index.company_id
                END,
                source = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.source
                    ELSE enterprise.enrichment_index.source
                END,
                source_domain = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.source_domain
                    ELSE enterprise.enrichment_index.source_domain
                END,
                source_table = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.source_table
                    ELSE enterprise.enrichment_index.source_table
                END,
                hit_count = enterprise.enrichment_index.hit_count + 1,
                last_hit_at = NOW(),
                updated_at = NOW()
        """).bindparams(
            bindparam("lookup_keys", type_=ARRAY(TEXT())),
            bindparam("lookup_types", type_=ARRAY(TEXT())),
            bindparam("company_ids", type_=ARRAY(TEXT())),
            bindparam("confidences", type_=ARRAY(NUMERIC())),
            bindparam("sources", type_=ARRAY(TEXT())),
            bindparam("source_domains", type_=ARRAY(TEXT())),
            bindparam("source_tables", type_=ARRAY(TEXT())),
        )

        result = self.connection.execute(
            query,
            {
                "lookup_keys": lookup_keys,
                "lookup_types": lookup_types,
                "company_ids": company_ids,
                "confidences": confidences,
                "sources": sources,
                "source_domains": source_domains,
                "source_tables": source_tables,
            },
        )

        # rowcount includes both inserts and updates in PostgreSQL
        affected_count = result.rowcount

        logger.info(
            "mapping_repository.insert_enrichment_index_batch.completed",
            input_count=len(records),
            affected_count=affected_count,
        )

        # Note: We can't distinguish inserts from updates without additional query
        # For simplicity, report all as "inserted" (affected)
        return InsertBatchResult(
            inserted_count=affected_count,
            skipped_count=len(records) - affected_count,
        )

    def update_hit_count(
        self,
        lookup_key: str,
        lookup_type: LookupType,
    ) -> bool:
        """
        Increment hit_count and update timestamps for a cache hit (Story 6.1.1).

        Args:
            lookup_key: The lookup key value.
            lookup_type: Type of lookup.

        Returns:
            True if record was updated, False if not found.

        Example:
            >>> if repo.update_hit_count("FP0001", LookupType.PLAN_CODE):
            ...     print("Hit count incremented")
        """
        normalized_key = self._normalize_lookup_key(lookup_key, lookup_type)

        query = text("""
            UPDATE enterprise.enrichment_index
            SET hit_count = hit_count + 1,
                last_hit_at = NOW(),
                updated_at = NOW()
            WHERE lookup_key = :lookup_key AND lookup_type = :lookup_type
        """)

        result = self.connection.execute(
            query,
            {"lookup_key": normalized_key, "lookup_type": lookup_type.value},
        )

        updated = result.rowcount > 0

        logger.debug(
            "mapping_repository.update_hit_count.completed",
            lookup_type=lookup_type.value,
            updated=updated,
        )

        return updated

    # =========================================================================
    # Story 6.2-P5: EQC Data Persistence Operations
    # =========================================================================

    def upsert_base_info(
        self,
        company_id: str,
        search_key_word: str,
        company_full_name: str,
        unite_code: Optional[str],
        raw_data: Optional[Dict[str, Any]] = None,
        raw_business_info: Optional[Dict[str, Any]] = None,
        raw_biz_label: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Upsert company data to enterprise.base_info table with raw API responses.

        Story 6.2-P5: Store search API response in raw_data
        Story 6.2-P8: Store findDepart response in raw_business_info, findLabels in raw_biz_label

        Conflict Resolution:
        - Use COALESCE to preserve existing data if new value is NULL (partial update support)
        - Always update api_fetched_at and updated_at on successful API call

        Args:
            company_id: EQC company ID (primary key).
            search_key_word: Original search query that found this company.
            company_full_name: Official company name from EQC.
            unite_code: Unified social credit code (统一社会信用代码).
            raw_data: Complete search API response JSON (response body only).
            raw_business_info: Complete findDepart API response JSON (response body only).
            raw_biz_label: Complete findLabels API response JSON (response body only).

        Returns:
            True if new record was inserted, False if existing record was updated.

        Security:
            Only persists response body JSON - no headers, no token, no URL params.

        Example:
            >>> inserted = repo.upsert_base_info(
            ...     company_id="1000065057",
            ...     search_key_word="中国平安",
            ...     company_full_name="中国平安保险（集团）股份有限公司",
            ...     unite_code="91440300618698064P",
            ...     raw_data=search_response,
            ...     raw_business_info=business_response,
            ...     raw_biz_label=label_response,
            ... )
            >>> print(f"New record: {inserted}")
        """
        query = text("""
            INSERT INTO enterprise.base_info
                (company_id, search_key_word, "companyFullName", unite_code,
                 raw_data, raw_business_info, raw_biz_label, api_fetched_at, updated_at)
            VALUES
                (:company_id, :search_key_word, :company_full_name, :unite_code,
                 CAST(:raw_data AS JSONB), CAST(:raw_business_info AS JSONB),
                 CAST(:raw_biz_label AS JSONB), NOW(), NOW())
            ON CONFLICT (company_id) DO UPDATE SET
                search_key_word = COALESCE(EXCLUDED.search_key_word, enterprise.base_info.search_key_word),
                "companyFullName" = COALESCE(EXCLUDED."companyFullName", enterprise.base_info."companyFullName"),
                unite_code = COALESCE(EXCLUDED.unite_code, enterprise.base_info.unite_code),
                raw_data = COALESCE(EXCLUDED.raw_data, enterprise.base_info.raw_data),
                raw_business_info = COALESCE(EXCLUDED.raw_business_info, enterprise.base_info.raw_business_info),
                raw_biz_label = COALESCE(EXCLUDED.raw_biz_label, enterprise.base_info.raw_biz_label),
                api_fetched_at = NOW(),
                updated_at = NOW()
            RETURNING (xmax = 0) AS inserted
        """)

        result = self.connection.execute(
            query,
            {
                "company_id": company_id,
                "search_key_word": search_key_word,
                "company_full_name": company_full_name,
                "unite_code": unite_code,
                "raw_data": json.dumps(raw_data, ensure_ascii=False) if raw_data is not None else None,
                "raw_business_info": json.dumps(raw_business_info, ensure_ascii=False) if raw_business_info is not None else None,
                "raw_biz_label": json.dumps(raw_biz_label, ensure_ascii=False) if raw_biz_label is not None else None,
            },
        )

        row = result.fetchone()
        inserted = row.inserted if row else False

        logger.info(
            "mapping_repository.upsert_base_info.completed",
            inserted=inserted,
            has_raw_data=raw_data is not None,
            has_raw_business_info=raw_business_info is not None,
            has_raw_biz_label=raw_biz_label is not None,
        )

        return inserted
