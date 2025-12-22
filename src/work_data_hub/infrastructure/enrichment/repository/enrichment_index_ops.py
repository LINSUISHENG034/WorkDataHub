"""
Enrichment index table operations mixin.

This module contains operations for the enterprise.enrichment_index table.

Story 6.1.1: Enrichment Index Schema Enhancement
Story 7.3: Infrastructure Layer Decomposition
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, NUMERIC, TEXT

from work_data_hub.utils.logging import get_logger

from ..types import EnrichmentIndexRecord, LookupType
from .models import InsertBatchResult

logger = get_logger(__name__)


class EnrichmentIndexOpsMixin:
    """Mixin providing enrichment_index table operations."""

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
        - source fields: Keep existing unless new confidence is higher

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
