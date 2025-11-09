"""
Company enrichment loader for EQC result caching.

This module provides specialized loading functionality for caching EQC company
lookup results to the enterprise.company_mapping table. Supports atomic UPSERT
operations and integrates with the CompanyEnrichmentService architecture.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from work_data_hub.domain.company_enrichment.models import CompanyMappingRecord

logger = logging.getLogger(__name__)


class CompanyEnrichmentLoaderError(Exception):
    """Raised when company enrichment loader encounters an error."""

    pass


class CompanyEnrichmentLoader:
    """
    Specialized loader for caching EQC company lookup results.

    Provides atomic UPSERT operations to cache EQC company mapping results
    in the enterprise.company_mapping table, supporting both individual
    caching operations and batch processing scenarios.

    Examples:
        >>> loader = CompanyEnrichmentLoader(connection, plan_only=False)
        >>> loader.cache_company_mapping("中国平安", "614810477", source="EQC")
        >>> mappings = loader.load_mappings()
    """

    def __init__(self, connection, *, plan_only: bool = False):
        """
        Initialize company enrichment loader.

        Args:
            connection: psycopg2 database connection
            plan_only: If True, only generate SQL plans without executing
        """
        self.connection = connection
        self.plan_only = plan_only

        logger.debug(
            "CompanyEnrichmentLoader initialized",
            extra={"plan_only": plan_only, "has_connection": bool(connection)},
        )

    def cache_company_mapping(
        self,
        alias_name: str,
        canonical_id: str,
        *,
        source: str = "EQC",
        match_type: str = "name",
    ) -> None:
        """
        Cache a company mapping result from EQC lookup.

        Uses atomic UPSERT operation to store EQC lookup results in the
        enterprise.company_mapping table for future internal lookups.

        Args:
            alias_name: Company name that was looked up
            canonical_id: Resolved company ID from EQC
            source: Source identifier (default: "EQC")
            match_type: Mapping type (default: "name" for customer names)

        Raises:
            CompanyEnrichmentLoaderError: If caching operation fails
            ValueError: If required parameters are invalid
        """
        if not alias_name or not alias_name.strip():
            raise ValueError("Alias name cannot be empty")

        if not canonical_id or not canonical_id.strip():
            raise ValueError("Canonical ID cannot be empty")

        # Clean inputs
        clean_alias = alias_name.strip()
        clean_canonical_id = canonical_id.strip()

        # Validate match_type for EQC results (typically "name" for customer names)
        allowed_match_types = {"name", "account_name", "external"}
        if match_type not in allowed_match_types:
            logger.warning(
                f"Unusual match_type for EQC caching: {match_type}. "
                f"Expected one of {allowed_match_types}"
            )

        # Determine priority based on match_type (following existing patterns)
        priority_map = {
            "plan": 1,
            "account": 2,
            "hardcode": 3,
            "name": 4,
            "account_name": 5,
            "external": 6,  # New priority for EQC results
        }
        priority = priority_map.get(match_type, 4)  # Default to priority 4 for names

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would cache company mapping",
                extra={
                    "alias_name": clean_alias,
                    "canonical_id": clean_canonical_id,
                    "source": source,
                    "match_type": match_type,
                    "priority": priority,
                },
            )
            return

        # UPSERT SQL - insert or update on conflict
        sql = """
            INSERT INTO enterprise.company_mapping
            (alias_name, canonical_id, source, match_type, priority, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (alias_name, match_type)
            DO UPDATE SET
                canonical_id = EXCLUDED.canonical_id,
                source = EXCLUDED.source,
                priority = EXCLUDED.priority,
                updated_at = EXCLUDED.updated_at
        """

        try:
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Caching company mapping result",
                    extra={
                        "alias_name": clean_alias,
                        "canonical_id": clean_canonical_id,
                        "source": source,
                        "match_type": match_type,
                    },
                )

                cursor.execute(
                    sql,
                    (
                        clean_alias,
                        clean_canonical_id,
                        source,
                        match_type,
                        priority,
                        datetime.now(timezone.utc),
                    ),
                )

                logger.info(
                    "Company mapping cached successfully",
                    extra={
                        "alias_name": clean_alias,
                        "canonical_id": clean_canonical_id,
                        "source": source,
                        "match_type": match_type,
                    },
                )

        except psycopg2.Error as e:
            logger.error(
                "Database error during company mapping cache operation",
                extra={
                    "alias_name": clean_alias,
                    "canonical_id": clean_canonical_id,
                    "error": str(e),
                },
            )
            raise CompanyEnrichmentLoaderError(f"Failed to cache company mapping: {e}")

    def cache_company_mappings_batch(
        self,
        mappings: List[Dict[str, str]],
        *,
        source: str = "EQC",
        match_type: str = "name",
    ) -> Dict[str, int]:
        """
        Cache multiple company mappings in a single transaction.

        Args:
            mappings: List of dictionaries with 'alias_name' and 'canonical_id' keys
            source: Source identifier for all mappings
            match_type: Match type for all mappings

        Returns:
            Dictionary with operation statistics

        Raises:
            CompanyEnrichmentLoaderError: If batch caching operation fails
        """
        if not mappings:
            logger.warning("No mappings provided for batch caching")
            return {"cached": 0}

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would cache batch of company mappings",
                extra={
                    "batch_size": len(mappings),
                    "source": source,
                    "match_type": match_type,
                },
            )
            return {"cached": len(mappings)}

        priority_map = {
            "plan": 1,
            "account": 2,
            "hardcode": 3,
            "name": 4,
            "account_name": 5,
            "external": 6,
        }
        priority = priority_map.get(match_type, 4)
        now = datetime.now(timezone.utc)

        # Prepare batch data
        batch_data = []
        for mapping in mappings:
            if "alias_name" not in mapping or "canonical_id" not in mapping:
                logger.warning(f"Skipping invalid mapping: {mapping}")
                continue

            alias_name = str(mapping["alias_name"]).strip()
            canonical_id = str(mapping["canonical_id"]).strip()

            if not alias_name or not canonical_id:
                logger.warning(f"Skipping empty mapping: {mapping}")
                continue

            batch_data.append(
                (alias_name, canonical_id, source, match_type, priority, now)
            )

        if not batch_data:
            logger.warning("No valid mappings to cache after filtering")
            return {"cached": 0}

        sql = """
            INSERT INTO enterprise.company_mapping
            (alias_name, canonical_id, source, match_type, priority, updated_at)
            VALUES %s
            ON CONFLICT (alias_name, match_type)
            DO UPDATE SET
                canonical_id = EXCLUDED.canonical_id,
                source = EXCLUDED.source,
                priority = EXCLUDED.priority,
                updated_at = EXCLUDED.updated_at
        """

        try:
            with self.connection:  # Transaction
                with self.connection.cursor() as cursor:
                    logger.debug(
                        "Caching batch of company mappings",
                        extra={"batch_size": len(batch_data), "source": source},
                    )

                    # Use execute_values for efficient batch insert
                    from psycopg2.extras import execute_values

                    execute_values(
                        cursor, sql, batch_data, template=None, page_size=1000
                    )

                    logger.info(
                        "Company mappings batch cached successfully",
                        extra={"cached_count": len(batch_data), "source": source},
                    )

                    return {"cached": len(batch_data)}

        except psycopg2.Error as e:
            logger.error(
                "Database error during batch company mapping cache operation",
                extra={"batch_size": len(batch_data), "error": str(e)},
            )
            raise CompanyEnrichmentLoaderError(
                f"Failed to cache company mappings batch: {e}"
            )

    def load_mappings(
        self,
        *,
        source: Optional[str] = None,
        match_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[CompanyMappingRecord]:
        """
        Load company mappings from the database.

        Args:
            source: Filter by source (e.g., "internal", "EQC")
            match_type: Filter by match_type
            limit: Limit number of results

        Returns:
            List of CompanyMappingRecord objects

        Raises:
            CompanyEnrichmentLoaderError: If loading operation fails
        """
        if self.plan_only:
            # Return mock data for plan-only mode
            mock_mappings = [
                CompanyMappingRecord(
                    alias_name="Test Company",
                    canonical_id="614810477",
                    source="internal",
                    match_type="name",
                    priority=4,
                )
            ]
            logger.info(
                "PLAN ONLY: Would load company mappings",
                extra={
                    "source": source,
                    "match_type": match_type,
                    "limit": limit,
                    "mock_count": len(mock_mappings),
                },
            )
            return mock_mappings

        # Build dynamic SQL with filters
        where_clauses = []
        params = []

        if source:
            where_clauses.append("source = %s")
            params.append(source)

        if match_type:
            where_clauses.append("match_type = %s")
            params.append(match_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        limit_sql = ""
        if limit and limit > 0:
            limit_sql = "LIMIT %s"
            params.append(str(limit))

        sql = f"""
            SELECT alias_name, canonical_id, source, match_type, priority, updated_at
            FROM enterprise.company_mapping
            {where_sql}
            ORDER BY priority ASC, match_type, alias_name
            {limit_sql}
        """

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                logger.debug(
                    "Loading company mappings",
                    extra={"source": source, "match_type": match_type, "limit": limit},
                )

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                mappings = [CompanyMappingRecord(**dict(row)) for row in rows]

                logger.debug(
                    "Company mappings loaded successfully",
                    extra={"loaded_count": len(mappings)},
                )

                return mappings

        except psycopg2.Error as e:
            logger.error(
                "Database error during company mappings loading",
                extra={"source": source, "match_type": match_type, "error": str(e)},
            )
            raise CompanyEnrichmentLoaderError(f"Failed to load company mappings: {e}")

    def get_cached_mapping(
        self, alias_name: str, match_type: str = "name"
    ) -> Optional[str]:
        """
        Get a cached company mapping for a specific alias.

        Args:
            alias_name: Company name to look up
            match_type: Type of mapping to search for

        Returns:
            Canonical company ID if found, None otherwise

        Raises:
            CompanyEnrichmentLoaderError: If lookup operation fails
        """
        if not alias_name or not alias_name.strip():
            raise ValueError("Alias name cannot be empty")

        clean_alias = alias_name.strip()

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would get cached mapping",
                extra={"alias_name": clean_alias, "match_type": match_type},
            )
            return "614810477"  # Mock result

        sql = """
            SELECT canonical_id
            FROM enterprise.company_mapping
            WHERE alias_name = %s AND match_type = %s
            ORDER BY priority ASC
            LIMIT 1
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (clean_alias, match_type))
                row = cursor.fetchone()

                if row:
                    canonical_id = row[0]
                    logger.debug(
                        "Found cached mapping",
                        extra={
                            "alias_name": clean_alias,
                            "match_type": match_type,
                            "canonical_id": canonical_id,
                        },
                    )
                    return canonical_id
                else:
                    logger.debug(
                        "No cached mapping found",
                        extra={"alias_name": clean_alias, "match_type": match_type},
                    )
                    return None

        except psycopg2.Error as e:
            logger.error(
                "Database error during cached mapping lookup",
                extra={
                    "alias_name": clean_alias,
                    "match_type": match_type,
                    "error": str(e),
                },
            )
            raise CompanyEnrichmentLoaderError(f"Failed to get cached mapping: {e}")

    def clear_cache(
        self, *, source: str = "EQC", dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Clear cached mappings by source.

        Args:
            source: Source identifier to clear (default: "EQC")
            dry_run: If True, only count what would be deleted without executing

        Returns:
            Dictionary with operation statistics

        Raises:
            CompanyEnrichmentLoaderError: If clear operation fails
        """
        if self.plan_only or dry_run:
            # Count what would be deleted
            count_sql = (
                "SELECT COUNT(*) FROM enterprise.company_mapping WHERE source = %s"
            )

            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(count_sql, (source,))
                    count = cursor.fetchone()[0]

                    logger.info(
                        "PLAN ONLY/DRY RUN: Would clear cached mappings",
                        extra={"source": source, "would_delete_count": count},
                    )

                    return {"deleted": count}

            except psycopg2.Error as e:
                logger.error(
                    "Database error during cache clear count",
                    extra={"source": source, "error": str(e)},
                )
                raise CompanyEnrichmentLoaderError(
                    f"Failed to count cached mappings: {e}"
                )

        # Execute actual deletion
        delete_sql = "DELETE FROM enterprise.company_mapping WHERE source = %s"

        try:
            with self.connection:  # Transaction
                with self.connection.cursor() as cursor:
                    logger.warning("Clearing cached mappings", extra={"source": source})

                    cursor.execute(delete_sql, (source,))
                    deleted_count = cursor.rowcount

                    logger.warning(
                        "Cached mappings cleared",
                        extra={"source": source, "deleted_count": deleted_count},
                    )

                    return {"deleted": deleted_count}

        except psycopg2.Error as e:
            logger.error(
                "Database error during cache clear operation",
                extra={"source": source, "error": str(e)},
            )
            raise CompanyEnrichmentLoaderError(f"Failed to clear cached mappings: {e}")
