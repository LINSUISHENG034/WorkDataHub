"""
Company enrichment loader for EQC result caching.

This module provides specialized loading functionality for caching EQC company
lookup results to the enterprise.enrichment_index table. Supports atomic UPSERT
operations and integrates with the CompanyEnrichmentService architecture.

Note: enterprise.company_mapping table was removed in Story 7.1-4 (Zero Legacy).
      All caching now uses enterprise.enrichment_index table.
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
    in the enterprise.enrichment_index table, supporting both individual
    caching operations and batch processing scenarios.

    Note: Migrated from company_mapping to enrichment_index in Story 7.1-4.

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
        enterprise.enrichment_index table for future lookups.

        Note: Migrated from company_mapping to enrichment_index in Story 7.1-4.

        Args:
            alias_name: Company name that was looked up (stored as lookup_key)
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

        # Map match_type to enrichment_index lookup_type format
        lookup_type_map = {
            "plan": "plan_code",
            "account": "account_number",
            "hardcode": "plan_customer",
            "name": "customer_name",
            "account_name": "account_name",
            "external": "customer_name",  # EQC results map to customer_name
        }
        lookup_type = lookup_type_map.get(match_type, "customer_name")

        # Determine confidence based on source/match_type
        confidence_map = {
            "EQC": 0.85,  # EQC API lookups
            "internal": 0.95,  # Internal mapping data
            "yaml": 1.00,  # YAML configuration
        }
        confidence = confidence_map.get(source.lower(), 0.80)

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would cache company mapping to enrichment_index",
                extra={
                    "lookup_key": clean_alias,
                    "company_id": clean_canonical_id,
                    "source": source,
                    "lookup_type": lookup_type,
                    "confidence": confidence,
                },
            )
            return

        # UPSERT SQL for enrichment_index table
        sql = """
            INSERT INTO enterprise.enrichment_index
            (lookup_key, lookup_type, company_id, confidence, source,
             source_domain, source_table, hit_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
            ON CONFLICT (lookup_key, lookup_type)
            DO UPDATE SET
                company_id = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.company_id
                    ELSE enterprise.enrichment_index.company_id
                END,
                confidence = GREATEST(
                    enterprise.enrichment_index.confidence,
                    EXCLUDED.confidence
                ),
                source = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.source
                    ELSE enterprise.enrichment_index.source
                END,
                hit_count = enterprise.enrichment_index.hit_count + 1,
                last_hit_at = NOW(),
                updated_at = EXCLUDED.updated_at
        """

        now = datetime.now(timezone.utc)

        try:
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Caching company mapping to enrichment_index",
                    extra={
                        "lookup_key": clean_alias,
                        "company_id": clean_canonical_id,
                        "source": source,
                        "lookup_type": lookup_type,
                    },
                )

                cursor.execute(
                    sql,
                    (
                        clean_alias,
                        lookup_type,
                        clean_canonical_id,
                        confidence,
                        source,
                        "company_enrichment",  # source_domain
                        "eqc_lookup",  # source_table
                        now,
                        now,
                    ),
                )

                logger.info(
                    "Company mapping cached to enrichment_index successfully",
                    extra={
                        "lookup_key": clean_alias,
                        "company_id": clean_canonical_id,
                        "source": source,
                        "lookup_type": lookup_type,
                    },
                )

        except psycopg2.Error as e:
            logger.error(
                "Database error during company mapping cache operation",
                extra={
                    "lookup_key": clean_alias,
                    "company_id": clean_canonical_id,
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

        # Map match_type to enrichment_index lookup_type format
        lookup_type_map = {
            "plan": "plan_code",
            "account": "account_number",
            "hardcode": "plan_customer",
            "name": "customer_name",
            "account_name": "account_name",
            "external": "customer_name",
        }
        lookup_type = lookup_type_map.get(match_type, "customer_name")

        # Determine confidence based on source
        confidence_map = {
            "EQC": 0.85,
            "internal": 0.95,
            "yaml": 1.00,
        }
        confidence = confidence_map.get(source.lower(), 0.80)

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would cache batch of company mappings to enrichment_index",
                extra={
                    "batch_size": len(mappings),
                    "source": source,
                    "lookup_type": lookup_type,
                },
            )
            return {"cached": len(mappings)}

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
                (
                    alias_name,
                    lookup_type,
                    canonical_id,
                    confidence,
                    source,
                    "company_enrichment",
                    "eqc_lookup",
                    now,
                    now,
                )
            )

        if not batch_data:
            logger.warning("No valid mappings to cache after filtering")
            return {"cached": 0}

        sql = """
            INSERT INTO enterprise.enrichment_index
            (lookup_key, lookup_type, company_id, confidence, source,
             source_domain, source_table, created_at, updated_at)
            VALUES %s
            ON CONFLICT (lookup_key, lookup_type)
            DO UPDATE SET
                company_id = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.company_id
                    ELSE enterprise.enrichment_index.company_id
                END,
                confidence = GREATEST(
                    enterprise.enrichment_index.confidence,
                    EXCLUDED.confidence
                ),
                source = CASE
                    WHEN EXCLUDED.confidence > enterprise.enrichment_index.confidence
                    THEN EXCLUDED.source
                    ELSE enterprise.enrichment_index.source
                END,
                hit_count = enterprise.enrichment_index.hit_count + 1,
                last_hit_at = NOW(),
                updated_at = EXCLUDED.updated_at
        """

        try:
            with self.connection:  # Transaction
                with self.connection.cursor() as cursor:
                    logger.debug(
                        "Caching batch of company mappings to enrichment_index",
                        extra={"batch_size": len(batch_data), "source": source},
                    )

                    # Use execute_values for efficient batch insert
                    from psycopg2.extras import execute_values

                    execute_values(
                        cursor, sql, batch_data, template=None, page_size=1000
                    )

                    logger.info(
                        "Company mappings batch cached to enrichment_index successfully",
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
        Load company mappings from the enrichment_index table.

        Note: Migrated from company_mapping to enrichment_index in Story 7.1-4.

        Args:
            source: Filter by source (e.g., "internal", "EQC")
            match_type: Filter by match_type (maps to lookup_type)
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
                "PLAN ONLY: Would load company mappings from enrichment_index",
                extra={
                    "source": source,
                    "match_type": match_type,
                    "limit": limit,
                    "mock_count": len(mock_mappings),
                },
            )
            return mock_mappings

        # Map match_type to enrichment_index lookup_type if provided
        lookup_type = None
        if match_type:
            lookup_type_map = {
                "plan": "plan_code",
                "account": "account_number",
                "hardcode": "plan_customer",
                "name": "customer_name",
                "account_name": "account_name",
            }
            lookup_type = lookup_type_map.get(match_type)

        # Build dynamic SQL with filters
        where_clauses = []
        params = []

        if source:
            where_clauses.append("source = %s")
            params.append(source)

        if lookup_type:
            where_clauses.append("lookup_type = %s")
            params.append(lookup_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        limit_sql = ""
        if limit and limit > 0:
            limit_sql = "LIMIT %s"
            params.append(str(limit))

        # Map enrichment_index columns to CompanyMappingRecord fields
        # lookup_type -> match_type (reverse mapping)
        sql = f"""
            SELECT
                lookup_key AS alias_name,
                company_id AS canonical_id,
                source,
                CASE lookup_type
                    WHEN 'plan_code' THEN 'plan'
                    WHEN 'account_number' THEN 'account'
                    WHEN 'plan_customer' THEN 'hardcode'
                    WHEN 'customer_name' THEN 'name'
                    WHEN 'account_name' THEN 'account_name'
                    ELSE 'name'
                END AS match_type,
                CASE lookup_type
                    WHEN 'plan_code' THEN 1
                    WHEN 'account_number' THEN 2
                    WHEN 'plan_customer' THEN 3
                    WHEN 'customer_name' THEN 4
                    WHEN 'account_name' THEN 5
                    ELSE 4
                END AS priority,
                updated_at
            FROM enterprise.enrichment_index
            {where_sql}
            ORDER BY priority ASC, match_type, alias_name
            {limit_sql}
        """

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                logger.debug(
                    "Loading company mappings from enrichment_index",
                    extra={"source": source, "match_type": match_type, "limit": limit},
                )

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                mappings = [CompanyMappingRecord(**dict(row)) for row in rows]

                logger.debug(
                    "Company mappings loaded from enrichment_index successfully",
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

        Note: Migrated from company_mapping to enrichment_index in Story 7.1-4.

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
                "PLAN ONLY: Would get cached mapping from enrichment_index",
                extra={"lookup_key": clean_alias, "match_type": match_type},
            )
            return "614810477"  # Mock result

        # Map match_type to enrichment_index lookup_type
        lookup_type_map = {
            "plan": "plan_code",
            "account": "account_number",
            "hardcode": "plan_customer",
            "name": "customer_name",
            "account_name": "account_name",
        }
        lookup_type = lookup_type_map.get(match_type, "customer_name")

        sql = """
            SELECT company_id
            FROM enterprise.enrichment_index
            WHERE lookup_key = %s AND lookup_type = %s
            ORDER BY confidence DESC
            LIMIT 1
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (clean_alias, lookup_type))
                row = cursor.fetchone()

                if row:
                    canonical_id = row[0]
                    logger.debug(
                        "Found cached mapping in enrichment_index",
                        extra={
                            "lookup_key": clean_alias,
                            "lookup_type": lookup_type,
                            "company_id": canonical_id,
                        },
                    )
                    return canonical_id
                else:
                    logger.debug(
                        "No cached mapping found in enrichment_index",
                        extra={"lookup_key": clean_alias, "lookup_type": lookup_type},
                    )
                    return None

        except psycopg2.Error as e:
            logger.error(
                "Database error during cached mapping lookup",
                extra={
                    "lookup_key": clean_alias,
                    "lookup_type": lookup_type,
                    "error": str(e),
                },
            )
            raise CompanyEnrichmentLoaderError(f"Failed to get cached mapping: {e}")

    def clear_cache(
        self, *, source: str = "EQC", dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Clear cached mappings by source from enrichment_index.

        Note: Migrated from company_mapping to enrichment_index in Story 7.1-4.

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
                "SELECT COUNT(*) FROM enterprise.enrichment_index WHERE source = %s"
            )

            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(count_sql, (source,))
                    count = cursor.fetchone()[0]

                    logger.info(
                        "PLAN ONLY/DRY RUN: Would clear cached mappings from enrichment_index",
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
        delete_sql = "DELETE FROM enterprise.enrichment_index WHERE source = %s"

        try:
            with self.connection:  # Transaction
                with self.connection.cursor() as cursor:
                    logger.warning(
                        "Clearing cached mappings from enrichment_index",
                        extra={"source": source},
                    )

                    cursor.execute(delete_sql, (source,))
                    deleted_count = cursor.rowcount

                    logger.warning(
                        "Cached mappings cleared from enrichment_index",
                        extra={"source": source, "deleted_count": deleted_count},
                    )

                    return {"deleted": deleted_count}

        except psycopg2.Error as e:
            logger.error(
                "Database error during cache clear operation",
                extra={"source": source, "error": str(e)},
            )
            raise CompanyEnrichmentLoaderError(f"Failed to clear cached mappings: {e}")
