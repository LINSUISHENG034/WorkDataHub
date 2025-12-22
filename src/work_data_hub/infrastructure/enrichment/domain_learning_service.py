"""
Domain Learning Service for automatic company ID mapping extraction (Story 6.1.3).

This service extracts valid company ID mappings from processed Domain data
(annuity_performance, annuity_income) and writes them to the enrichment_index
cache for future lookups.

Architecture Reference:
- AD-010: Infrastructure Layer
- docs/guides/company-enrichment-service.md#2.3 Domain Self-Learning

Key Features:
- Multi-type learning: Extracts all 5 lookup types (plan_code, account_name,
  account_number, customer_name, plan_customer)
- Configurable confidence levels per lookup type
- Filters out temporary IDs (IN_*) and null values
- Idempotent operation via ON CONFLICT DO UPDATE
- Statistics tracking for observability
"""

from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
import structlog

from .mapping_repository import CompanyMappingRepository
from .normalizer import normalize_for_temp_id
from .types import (
    DomainLearningConfig,
    DomainLearningResult,
    EnrichmentIndexRecord,
    LookupType,
    ResolutionStatistics,
    SourceType,
)

logger = structlog.get_logger(__name__)


class DomainLearningService:
    """
    Service for learning company ID mappings from processed Domain data.

    Extracts valid mappings from Domain tables after pipeline processing
    and writes them to the enrichment_index cache for future lookups.

    Attributes:
        repository: CompanyMappingRepository for database operations.
        config: DomainLearningConfig with learning parameters.

    Example:
        >>> from work_data_hub.infrastructure.enrichment import (
        ...     CompanyMappingRepository,
        ...     DomainLearningService,
        ... )
        >>> repo = CompanyMappingRepository(connection)
        >>> service = DomainLearningService(repo)
        >>> result = service.learn_from_domain(
        ...     domain_name="annuity_performance",
        ...     table_name="annuity_performance_new",
        ...     df=processed_dataframe,
        ... )
        >>> print(f"Extracted: {result.extracted}, Inserted: {result.inserted}")
    """

    def __init__(
        self,
        repository: CompanyMappingRepository,
        config: Optional[DomainLearningConfig] = None,
    ) -> None:
        """
        Initialize DomainLearningService.

        Args:
            repository: CompanyMappingRepository for database operations.
            config: Optional DomainLearningConfig. Uses defaults if not provided.
        """
        self.repository = repository
        self.config = config or DomainLearningConfig()

        logger.debug(
            "domain_learning_service.initialized",
            enabled_domains=self.config.enabled_domains,
            min_records_for_learning=self.config.min_records_for_learning,
            min_confidence_for_cache=self.config.min_confidence_for_cache,
        )

    def learn_from_domain(
        self,
        domain_name: str,
        table_name: str,
        df: pd.DataFrame,
        stats: Optional[ResolutionStatistics] = None,
    ) -> DomainLearningResult:
        """
        Learn company ID mappings from a processed Domain DataFrame.

        Extracts valid mappings for all enabled lookup types and writes
        them to the enrichment_index cache.

        Args:
            domain_name: Name of the domain (e.g., 'annuity_performance').
            table_name: Name of the source table (e.g., 'annuity_performance_new').
            df: Processed DataFrame with company_id column populated.

        Returns:
            DomainLearningResult with extraction and insertion statistics.

        Raises:
            ValueError: If domain is not enabled or required columns are missing.
        """
        result = DomainLearningResult(
            domain_name=domain_name,
            table_name=table_name,
            total_records=len(df),
        )

        # AC11: Check if domain is enabled
        if domain_name not in self.config.enabled_domains:
            logger.warning(
                "domain_learning_service.domain_disabled",
                domain_name=domain_name,
                enabled_domains=self.config.enabled_domains,
            )
            result.skipped = result.total_records
            result.skipped_by_reason["domain_disabled"] = result.total_records
            return result

        # AC12: Validate required columns
        column_mapping = self.config.column_mappings.get(domain_name)
        if not column_mapping:
            logger.warning(
                "domain_learning_service.no_column_mapping",
                domain_name=domain_name,
            )
            result.skipped = result.total_records
            result.skipped_by_reason["no_column_mapping"] = result.total_records
            return result

        missing_columns = self._validate_columns(df, column_mapping)
        if missing_columns:
            logger.warning(
                "domain_learning_service.missing_columns",
                domain_name=domain_name,
                table_name=table_name,
                missing_columns=missing_columns,
            )
            result.skipped = result.total_records
            result.skipped_by_reason["missing_columns"] = result.total_records
            return result

        company_id_col = column_mapping.get("company_id", "company_id")
        company_id_text = df[company_id_col].astype(str).str.strip()
        is_temp_id = company_id_text.str.upper().str.startswith("IN")
        is_numeric_id = company_id_text.str.fullmatch(r"\d+").fillna(False)
        valid_mask = df[company_id_col].notna() & is_numeric_id & ~is_temp_id
        valid_count = int(valid_mask.sum())
        null_count = int(df[company_id_col].isna().sum())
        temp_id_count = int((df[company_id_col].notna() & is_temp_id).sum())
        result.valid_records = valid_count

        # AC5: Check minimum records threshold based on valid (non-temp) rows
        if valid_count < self.config.min_records_for_learning:
            logger.info(
                "domain_learning_service.below_threshold",
                domain_name=domain_name,
                table_name=table_name,
                total_records=len(df),
                valid_records=valid_count,
                min_records=self.config.min_records_for_learning,
            )
            result.skipped = result.total_records
            result.skipped_by_reason["below_threshold"] = result.total_records
            if null_count > 0:
                result.skipped_by_reason["null_company_id"] = null_count
            if temp_id_count > 0:
                result.skipped_by_reason["temp_id"] = temp_id_count
            return result

        # Extract mappings from DataFrame
        records, extraction_stats = self._extract_mappings_from_dataframe(
            df=df,
            domain_name=domain_name,
            table_name=table_name,
            column_mapping=column_mapping,
        )

        result.valid_records = extraction_stats.get("valid_records", 0)
        result.extracted = extraction_stats.get("extracted", {})
        result.skipped_by_reason.update(extraction_stats.get("skipped_by_reason", {}))

        if not records:
            logger.info(
                "domain_learning_service.no_records_to_insert",
                domain_name=domain_name,
                table_name=table_name,
                extraction_stats=extraction_stats,
            )
            result.skipped = sum(result.skipped_by_reason.values())
            return result

        # AC9: Insert records (idempotent via ON CONFLICT DO UPDATE)
        insert_result = self.repository.insert_enrichment_index_batch(records)

        result.inserted = insert_result.inserted_count
        result.updated = (
            insert_result.skipped_count
        )  # skipped_count = updates in UPSERT
        result.skipped = sum(result.skipped_by_reason.values())

        # AC7/AC14: Populate resolution statistics when provided
        self._update_statistics(stats, result)

        # AC14: Emit structured log
        logger.info(
            "domain_learning_service.completed",
            domain_name=domain_name,
            table_name=table_name,
            total_records=result.total_records,
            valid_records=result.valid_records,
            extracted=result.extracted,
            extracted_total=sum(result.extracted.values()),
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            skipped_by_reason=result.skipped_by_reason,
            min_records_for_learning=self.config.min_records_for_learning,
            min_confidence_for_cache=self.config.min_confidence_for_cache,
        )

        return result

    def _validate_columns(
        self,
        df: pd.DataFrame,
        column_mapping: Dict[str, str],
    ) -> List[str]:
        """
        Validate that required columns exist in DataFrame.

        Args:
            df: DataFrame to validate.
            column_mapping: Mapping of lookup types to column names.

        Returns:
            List of missing column names (empty if all present).
        """
        required_columns = [
            column_mapping.get("company_id", "company_id"),
        ]

        # Add columns for enabled lookup types
        for lookup_type, enabled in self.config.enabled_lookup_types.items():
            if enabled and lookup_type in column_mapping:
                required_columns.append(column_mapping[lookup_type])

        missing = [col for col in required_columns if col not in df.columns]
        return missing

    def _extract_mappings_from_dataframe(
        self,
        df: pd.DataFrame,
        domain_name: str,
        table_name: str,
        column_mapping: Dict[str, str],
    ) -> tuple[List[EnrichmentIndexRecord], Dict]:
        """
        Extract company ID mappings from DataFrame for all enabled lookup types.

        Args:
            df: DataFrame with company_id and lookup key columns.
            domain_name: Name of the domain.
            table_name: Name of the source table.
            column_mapping: Mapping of lookup types to column names.

        Returns:
            Tuple of (list of EnrichmentIndexRecord, extraction statistics dict).
        """
        records: List[EnrichmentIndexRecord] = []
        stats = {
            "valid_records": 0,
            "extracted": {},
            "skipped_by_reason": {},
        }

        company_id_col = column_mapping.get("company_id", "company_id")

        # Filter valid records: numeric company_id and not temp ID (IN*)
        company_id_text = df[company_id_col].astype(str).str.strip()
        is_temp_id = company_id_text.str.upper().str.startswith("IN")
        is_numeric_id = company_id_text.str.fullmatch(r"\d+").fillna(False)
        valid_mask = df[company_id_col].notna() & is_numeric_id & ~is_temp_id
        valid_df = df[valid_mask].copy()
        stats["valid_records"] = len(valid_df)

        # Track skipped records
        null_count = df[company_id_col].isna().sum()
        temp_id_count = (df[company_id_col].notna() & is_temp_id).sum()

        if null_count > 0:
            stats["skipped_by_reason"]["null_company_id"] = int(null_count)
        if temp_id_count > 0:
            stats["skipped_by_reason"]["temp_id"] = int(temp_id_count)

        if valid_df.empty:
            return records, stats

        # Extract mappings for each enabled lookup type
        lookup_type_configs = [
            ("plan_code", LookupType.PLAN_CODE, False),
            ("account_name", LookupType.ACCOUNT_NAME, False),
            ("account_number", LookupType.ACCOUNT_NUMBER, False),
            ("customer_name", LookupType.CUSTOMER_NAME, True),  # needs normalization
            ("plan_customer", LookupType.PLAN_CUSTOMER, True),  # needs normalization
        ]

        for type_key, lookup_type, needs_normalization in lookup_type_configs:
            candidate_count = self._count_candidates(
                valid_df=valid_df,
                column_mapping=column_mapping,
                type_key=type_key,
            )

            if not self.config.enabled_lookup_types.get(type_key, False):
                stats["skipped_by_reason"][f"{type_key}_disabled"] = candidate_count
                continue

            confidence = self.config.confidence_levels.get(type_key, 0.85)

            # AC11: Check min_confidence_for_cache
            if confidence < self.config.min_confidence_for_cache:
                stats["skipped_by_reason"][f"{type_key}_low_confidence"] = (
                    candidate_count
                )
                continue

            type_records = self._extract_lookup_type(
                df=valid_df,
                domain_name=domain_name,
                table_name=table_name,
                column_mapping=column_mapping,
                type_key=type_key,
                lookup_type=lookup_type,
                confidence=confidence,
                needs_normalization=needs_normalization,
            )

            records.extend(type_records)
            stats["extracted"][type_key] = len(type_records)

        return records, stats

    def _extract_lookup_type(
        self,
        df: pd.DataFrame,
        domain_name: str,
        table_name: str,
        column_mapping: Dict[str, str],
        type_key: str,
        lookup_type: LookupType,
        confidence: float,
        needs_normalization: bool,
    ) -> List[EnrichmentIndexRecord]:
        """
        Extract mappings for a specific lookup type.

        Args:
            df: Valid DataFrame (already filtered for non-null, non-temp company_id).
            domain_name: Name of the domain.
            table_name: Name of the source table.
            column_mapping: Mapping of lookup types to column names.
            type_key: Key for the lookup type (e.g., 'plan_code').
            lookup_type: LookupType enum value.
            confidence: Confidence level for this lookup type.
            needs_normalization: Whether to normalize the lookup key.

        Returns:
            List of EnrichmentIndexRecord for this lookup type.
        """
        records: List[EnrichmentIndexRecord] = []
        company_id_col = column_mapping.get("company_id", "company_id")

        # Handle plan_customer specially (composite key)
        if type_key == "plan_customer":
            plan_col = column_mapping.get("plan_code")
            customer_col = column_mapping.get("customer_name")

            if not plan_col or not customer_col:
                return records

            if plan_col not in df.columns or customer_col not in df.columns:
                return records

            # Get unique combinations
            combo_df = df[[plan_col, customer_col, company_id_col]].drop_duplicates()
            combo_df = combo_df[
                combo_df[plan_col].notna() & combo_df[customer_col].notna()
            ]

            for _, row in combo_df.iterrows():
                plan_code = str(row[plan_col]).strip()
                customer_name = str(row[customer_col]).strip()
                company_id = str(row[company_id_col]).strip()

                if not plan_code or not customer_name or not company_id:
                    continue

                # AC8: Use same normalizer as Layer 2 lookup
                normalized_name = normalize_for_temp_id(customer_name)
                lookup_key = f"{plan_code}|{normalized_name}"

                records.append(
                    EnrichmentIndexRecord(
                        lookup_key=lookup_key,
                        lookup_type=lookup_type,
                        company_id=company_id,
                        confidence=Decimal(str(confidence)),
                        source=SourceType.DOMAIN_LEARNING,
                        source_domain=domain_name,
                        source_table=table_name,
                    )
                )

            return records

        # Standard single-column lookup types
        col_name = column_mapping.get(type_key)
        if not col_name or col_name not in df.columns:
            return records

        # Get unique key-value pairs
        unique_df = df[[col_name, company_id_col]].drop_duplicates()
        unique_df = unique_df[unique_df[col_name].notna()]

        for _, row in unique_df.iterrows():
            raw_key = str(row[col_name]).strip()
            company_id = str(row[company_id_col]).strip()

            if not raw_key or not company_id:
                continue

            # AC8: Normalize customer_name for cache consistency
            if needs_normalization:
                lookup_key = normalize_for_temp_id(raw_key)
            else:
                lookup_key = raw_key

            if not lookup_key:
                continue

            records.append(
                EnrichmentIndexRecord(
                    lookup_key=lookup_key,
                    lookup_type=lookup_type,
                    company_id=company_id,
                    confidence=Decimal(str(confidence)),
                    source=SourceType.DOMAIN_LEARNING,
                    source_domain=domain_name,
                    source_table=table_name,
                )
            )

        return records

    def learn_from_table(
        self,
        domain_name: str,
        table_name: str,
    ) -> DomainLearningResult:
        """
        Learn company ID mappings directly from a database table.

        This method queries the database table directly using SQL for
        efficient batch extraction. Useful for batch learning from
        existing data.

        Args:
            domain_name: Name of the domain (e.g., 'annuity_performance').
            table_name: Name of the source table (e.g., 'annuity_performance_new').

        Returns:
            DomainLearningResult with extraction and insertion statistics.

        Note:
            This method requires the table to exist in the database.
            For DataFrame-based learning, use learn_from_domain() instead.
        """
        result = DomainLearningResult(
            domain_name=domain_name,
            table_name=table_name,
        )

        # AC11: Check if domain is enabled
        if domain_name not in self.config.enabled_domains:
            logger.warning(
                "domain_learning_service.learn_from_table.domain_disabled",
                domain_name=domain_name,
                enabled_domains=self.config.enabled_domains,
            )
            result.skipped_by_reason["domain_disabled"] = 1
            return result

        column_mapping = self.config.column_mappings.get(domain_name)
        if not column_mapping:
            logger.warning(
                "domain_learning_service.learn_from_table.no_column_mapping",
                domain_name=domain_name,
            )
            result.skipped_by_reason["no_column_mapping"] = 1
            return result

        # Query table and extract mappings
        records = self._extract_from_table_sql(
            domain_name=domain_name,
            table_name=table_name,
            column_mapping=column_mapping,
            result=result,
        )

        if not records:
            logger.info(
                "domain_learning_service.learn_from_table.no_records",
                domain_name=domain_name,
                table_name=table_name,
            )
            return result

        # Insert records
        insert_result = self.repository.insert_enrichment_index_batch(records)

        result.inserted = insert_result.inserted_count
        result.updated = insert_result.skipped_count
        result.skipped = sum(result.skipped_by_reason.values())

        logger.info(
            "domain_learning_service.learn_from_table.completed",
            domain_name=domain_name,
            table_name=table_name,
            extracted=result.extracted,
            inserted=result.inserted,
            updated=result.updated,
        )

        return result

    def _extract_from_table_sql(
        self,
        domain_name: str,
        table_name: str,
        column_mapping: Dict[str, str],
        result: DomainLearningResult,
    ) -> List[EnrichmentIndexRecord]:
        """
        Extract mappings from database table using SQL queries.

        Uses efficient DISTINCT queries to extract unique mappings
        for each enabled lookup type.

        Args:
            domain_name: Name of the domain.
            table_name: Name of the source table.
            column_mapping: Mapping of lookup types to column names.
            result: DomainLearningResult to update with statistics.

        Returns:
            List of EnrichmentIndexRecord extracted from the table.
        """
        from sqlalchemy import text

        records: List[EnrichmentIndexRecord] = []
        company_id_col = column_mapping.get("company_id", "company_id")

        # Get total and valid record counts
        count_query = text(f"""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN {company_id_col} IS NOT NULL
                           AND {company_id_col} NOT LIKE 'IN_%' THEN 1 END) as valid
            FROM {table_name}
        """)

        count_result = self.repository.connection.execute(count_query).fetchone()
        result.total_records = count_result[0] if count_result else 0
        result.valid_records = count_result[1] if count_result else 0

        # AC5: Check minimum records threshold
        if result.valid_records < self.config.min_records_for_learning:
            logger.info(
                "domain_learning_service.learn_from_table.below_threshold",
                domain_name=domain_name,
                table_name=table_name,
                valid_records=result.valid_records,
                min_records=self.config.min_records_for_learning,
            )
            result.skipped_by_reason["below_threshold"] = result.total_records
            return records

        # Extract each lookup type
        lookup_configs = [
            ("plan_code", LookupType.PLAN_CODE, False),
            ("account_name", LookupType.ACCOUNT_NAME, False),
            ("account_number", LookupType.ACCOUNT_NUMBER, False),
            ("customer_name", LookupType.CUSTOMER_NAME, True),
        ]

        for type_key, lookup_type, needs_normalization in lookup_configs:
            if not self.config.enabled_lookup_types.get(type_key, False):
                continue

            col_name = column_mapping.get(type_key)
            if not col_name:
                continue

            confidence = self.config.confidence_levels.get(type_key, 0.85)
            if confidence < self.config.min_confidence_for_cache:
                continue

            query = text(f"""
                SELECT DISTINCT
                    "{col_name}" as lookup_key,
                    {company_id_col} as company_id
                FROM {table_name}
                WHERE {company_id_col} IS NOT NULL
                  AND {company_id_col} NOT LIKE 'IN_%'
                  AND "{col_name}" IS NOT NULL
            """)

            rows = self.repository.connection.execute(query).fetchall()

            type_count = 0
            for row in rows:
                raw_key = str(row[0]).strip() if row[0] else ""
                company_id = str(row[1]).strip() if row[1] else ""

                if not raw_key or not company_id:
                    continue

                lookup_key = (
                    normalize_for_temp_id(raw_key) if needs_normalization else raw_key
                )
                if not lookup_key:
                    continue

                records.append(
                    EnrichmentIndexRecord(
                        lookup_key=lookup_key,
                        lookup_type=lookup_type,
                        company_id=company_id,
                        confidence=Decimal(str(confidence)),
                        source=SourceType.DOMAIN_LEARNING,
                        source_domain=domain_name,
                        source_table=table_name,
                    )
                )
                type_count += 1

            result.extracted[type_key] = type_count

        # Handle plan_customer composite key
        if self.config.enabled_lookup_types.get("plan_customer", False):
            plan_col = column_mapping.get("plan_code")
            customer_col = column_mapping.get("customer_name")
            confidence = self.config.confidence_levels.get("plan_customer", 0.90)

            if (
                plan_col
                and customer_col
                and confidence >= self.config.min_confidence_for_cache
            ):
                query = text(f"""
                    SELECT DISTINCT
                        "{plan_col}" as plan_code,
                        "{customer_col}" as customer_name,
                        {company_id_col} as company_id
                    FROM {table_name}
                    WHERE {company_id_col} IS NOT NULL
                      AND {company_id_col} NOT LIKE 'IN_%'
                      AND "{plan_col}" IS NOT NULL
                      AND "{customer_col}" IS NOT NULL
                """)

                rows = self.repository.connection.execute(query).fetchall()

                type_count = 0
                for row in rows:
                    plan_code = str(row[0]).strip() if row[0] else ""
                    customer_name = str(row[1]).strip() if row[1] else ""
                    company_id = str(row[2]).strip() if row[2] else ""

                    if not plan_code or not customer_name or not company_id:
                        continue

                    normalized_name = normalize_for_temp_id(customer_name)
                    lookup_key = f"{plan_code}|{normalized_name}"

                    records.append(
                        EnrichmentIndexRecord(
                            lookup_key=lookup_key,
                            lookup_type=LookupType.PLAN_CUSTOMER,
                            company_id=company_id,
                            confidence=Decimal(str(confidence)),
                            source=SourceType.DOMAIN_LEARNING,
                            source_domain=domain_name,
                            source_table=table_name,
                        )
                    )
                    type_count += 1

                result.extracted["plan_customer"] = type_count

        return records

    def _count_candidates(
        self,
        valid_df: pd.DataFrame,
        column_mapping: Dict[str, str],
        type_key: str,
    ) -> int:
        """
        Count distinct candidate mappings for a lookup type (used for skip accounting).
        """
        company_id_col = column_mapping.get("company_id", "company_id")

        if type_key == "plan_customer":
            plan_col = column_mapping.get("plan_code")
            customer_col = column_mapping.get("customer_name")
            if not plan_col or not customer_col:
                return 0
            if plan_col not in valid_df.columns or customer_col not in valid_df.columns:
                return 0
            combo_df = valid_df[[plan_col, customer_col, company_id_col]].dropna(
                subset=[plan_col, customer_col, company_id_col]
            )
            return combo_df.drop_duplicates(subset=[plan_col, customer_col]).shape[0]

        col_name = column_mapping.get(type_key)
        if not col_name or col_name not in valid_df.columns:
            return 0

        return (
            valid_df[[col_name, company_id_col]]
            .dropna(subset=[col_name, company_id_col])
            .drop_duplicates(subset=[col_name])
            .shape[0]
        )

    def _update_statistics(
        self,
        stats: Optional[ResolutionStatistics],
        result: DomainLearningResult,
    ) -> None:
        """
        Populate ResolutionStatistics.domain_learning_stats with the latest run.
        """
        if stats is None:
            return

        key = f"{result.domain_name}:{result.table_name}"
        stats.domain_learning_stats[key] = result.to_dict()

    def learn_from_domain_safely(
        self,
        domain_name: str,
        table_name: str,
        df: pd.DataFrame,
        *,
        enabled: bool = True,
        stats: Optional[ResolutionStatistics] = None,
    ) -> DomainLearningResult:
        """
        Non-blocking wrapper for pipeline hooks (AC15).

        - Respects an enable flag (default on)
        - Catches errors and logs instead of raising, so pipelines don't fail
        - Still updates domain_learning_stats when possible
        """
        if not enabled:
            logger.info(
                "domain_learning_service.disabled_by_flag",
                domain_name=domain_name,
                table_name=table_name,
            )
            result = DomainLearningResult(
                domain_name=domain_name,
                table_name=table_name,
                total_records=len(df),
                skipped=len(df),
                skipped_by_reason={"disabled_flag": len(df)},
            )
            self._update_statistics(stats, result)
            return result

        try:
            return self.learn_from_domain(
                domain_name=domain_name,
                table_name=table_name,
                df=df,
                stats=stats,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "domain_learning_service.failed",
                domain_name=domain_name,
                table_name=table_name,
                error=str(exc),
            )
            result = DomainLearningResult(
                domain_name=domain_name,
                table_name=table_name,
                total_records=len(df),
                skipped=len(df),
                skipped_by_reason={"error": len(df)},
            )
            self._update_statistics(stats, result)
            return result
