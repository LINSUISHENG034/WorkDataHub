"""
Other table operations mixin.

This module contains operations for other enterprise tables:
- company_name_index (Story 6.6 cache)
- enrichment_requests (Story 6.5 async queue)
- base_info (Story 6.2-P5 EQC data persistence)

Story 7.3: Infrastructure Layer Decomposition
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

from work_data_hub.utils.logging import get_logger

from .models import EnqueueResult, InsertBatchResult

logger = get_logger(__name__)


class OtherOpsMixin:
    """Mixin providing operations for other enterprise tables."""

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
            ...      "temp_id": "INABC123DEF456GH"},
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

    def upsert_base_info(
        self,
        company_id: str,
        search_key_word: str,
        company_full_name: str,
        unite_code: Optional[str],
        raw_data: Optional[Dict[str, Any]] = None,
        raw_business_info: Optional[Dict[str, Any]] = None,
        raw_biz_label: Optional[Dict[str, Any]] = None,
        # New parsed fields for enhanced persistence
        data_source: Optional[str] = None,
        match_type: Optional[str] = None,
        le_rep: Optional[str] = None,
        est_date: Optional[str] = None,
        province: Optional[str] = None,
        registered_status: Optional[str] = None,
        organization_code: Optional[str] = None,
        company_en_name: Optional[str] = None,
        company_former_name: Optional[str] = None,
        reg_cap: Optional[float] = None,
        # Search scores
        score: Optional[float] = None,
        rank_score: Optional[float] = None,
        # Legacy/Compatibility
        name: Optional[str] = None,
    ) -> bool:
        """
        Upsert company data to enterprise.base_info table with raw API responses.

        Story 6.2-P5: Store search API response in raw_data
        Story 6.2-P8: Store findDepart response in raw_business_info,
        findLabels in raw_biz_label
        Base Info Enhancement: Write parsed fields from raw_data/raw_business_info

        Conflict Resolution:
        - Use COALESCE to preserve existing data if new value is NULL
          (partial update support)
        - Always update api_fetched_at and updated_at on successful API call

        Args:
            company_id: EQC company ID (primary key).
            search_key_word: Original search query that found this company.
            company_full_name: Official company name from EQC.
            unite_code: Unified social credit code (统一社会信用代码).
            raw_data: Complete search API response JSON (response body only).
            raw_business_info: Complete findDepart API response JSON
                               (response body only).
            raw_biz_label: Complete findLabels API response JSON (response body only).
            data_source: Origin of data ("search", "direct_id", "refresh").
            match_type: EQC match quality (全称精确匹配/模糊匹配/拼音).
            le_rep: Legal representative name.
            est_date: Establishment date.
            province: Province.
            registered_status: Registration status.
            organization_code: Organization code.
            company_en_name: English company name.
            company_former_name: Former company name.
            reg_cap: Registered capital (parsed float).
            score: Search relevance score (_score).
            rank_score: Ranking score.
            name: Legacy name field (populated from company_full_name for direct_id).

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
            ...     data_source="search",
            ...     match_type="全称精确匹配",
            ... )
            >>> print(f"New record: {inserted}")
        """
        query = text("""
            INSERT INTO enterprise.base_info
                (company_id, search_key_word, company_full_name, unite_code,
                 raw_data, raw_business_info, raw_biz_label,
                 data_source, type, le_rep, est_date, province,
                 registered_status, organization_code, company_en_name,
                 company_former_name, reg_cap, _score, rank_score, name,
                 api_fetched_at, updated_at)
            VALUES
                (:company_id, :search_key_word, :company_full_name, :unite_code,
                 CAST(:raw_data AS JSONB), CAST(:raw_business_info AS JSONB),
                 CAST(:raw_biz_label AS JSONB),
                 :data_source, :match_type, :le_rep, :est_date, :province,
                 :registered_status, :organization_code, :company_en_name,
                 :company_former_name, :reg_cap, :score, :rank_score, :name,
                 NOW(), NOW())
            ON CONFLICT (company_id) DO UPDATE SET
                search_key_word = COALESCE(
                    EXCLUDED.search_key_word, base_info.search_key_word
                ),
                company_full_name = COALESCE(
                    EXCLUDED.company_full_name, base_info.company_full_name
                ),
                unite_code = COALESCE(EXCLUDED.unite_code, base_info.unite_code),
                raw_data = COALESCE(EXCLUDED.raw_data, base_info.raw_data),
                raw_business_info = COALESCE(
                    EXCLUDED.raw_business_info, base_info.raw_business_info
                ),
                raw_biz_label = COALESCE(
                    EXCLUDED.raw_biz_label, base_info.raw_biz_label
                ),
                data_source = COALESCE(EXCLUDED.data_source, base_info.data_source),
                type = COALESCE(EXCLUDED.type, base_info.type),
                le_rep = COALESCE(EXCLUDED.le_rep, base_info.le_rep),
                est_date = COALESCE(EXCLUDED.est_date, base_info.est_date),
                province = COALESCE(EXCLUDED.province, base_info.province),
                registered_status = COALESCE(
                    EXCLUDED.registered_status, base_info.registered_status
                ),
                organization_code = COALESCE(
                    EXCLUDED.organization_code, base_info.organization_code
                ),
                company_en_name = COALESCE(
                    EXCLUDED.company_en_name, base_info.company_en_name
                ),
                company_former_name = COALESCE(
                    EXCLUDED.company_former_name, base_info.company_former_name
                ),
                reg_cap = COALESCE(EXCLUDED.reg_cap, base_info.reg_cap),
                _score = COALESCE(EXCLUDED._score, base_info._score),
                rank_score = COALESCE(EXCLUDED.rank_score, base_info.rank_score),
                name = COALESCE(EXCLUDED.name, base_info.name),
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
                "raw_data": json.dumps(raw_data, ensure_ascii=False)
                if raw_data is not None
                else None,
                "raw_business_info": json.dumps(raw_business_info, ensure_ascii=False)
                if raw_business_info is not None
                else None,
                "raw_biz_label": json.dumps(raw_biz_label, ensure_ascii=False)
                if raw_biz_label is not None
                else None,
                "data_source": data_source,
                "match_type": match_type,
                "le_rep": le_rep,
                "est_date": est_date,
                "province": province,
                "registered_status": registered_status,
                "organization_code": organization_code,
                "company_en_name": company_en_name,
                "company_former_name": company_former_name,
                "reg_cap": reg_cap,
                "score": score,
                "rank_score": rank_score,
                "name": name,
            },
        )

        row = result.fetchone()
        inserted = row.inserted if row else False

        logger.info(
            "mapping_repository.upsert_base_info.completed",
            inserted=inserted,
            data_source=data_source,
            has_raw_data=raw_data is not None,
            has_raw_business_info=raw_business_info is not None,
            has_raw_biz_label=raw_biz_label is not None,
        )

        return inserted
