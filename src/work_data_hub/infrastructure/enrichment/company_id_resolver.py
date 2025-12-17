"""
Company ID Resolver for batch company identification.

This module provides the CompanyIdResolver class for batch-optimized company ID
resolution with hierarchical strategy support. It extracts and centralizes the
company ID resolution logic from domain layer for cross-domain reuse.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition

Resolution Priority (Story 6.4 - Multi-Tier Lookup):
1. YAML overrides (5 priority levels: plan → account → hardcode → name → account_name)
2. Database cache lookup (enterprise.company_mapping)
3. Existing company_id column passthrough + backflow
4. EQC sync lookup (budgeted, cached)
5. Temporary ID generation (HMAC-SHA1 based)
"""

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd

from work_data_hub.infrastructure.cleansing import normalize_company_name
from work_data_hub.utils.logging import get_logger

from .normalizer import generate_temp_company_id, normalize_for_temp_id
from .types import (
    EnrichmentIndexRecord,
    LookupType,
    ResolutionResult,
    ResolutionStatistics,
    ResolutionStrategy,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)

# Default salt for development - MUST be overridden in production
DEFAULT_SALT = "default_dev_salt_change_in_prod"
SALT_ENV_VAR = "WDH_ALIAS_SALT"

# YAML priority levels in resolution order
YAML_PRIORITY_ORDER = ["plan", "account", "hardcode", "name", "account_name"]


class CompanyIdResolver:
    """
    Batch-optimized company ID resolver with hierarchical strategy support.

    This class provides vectorized company ID resolution for DataFrames,
    supporting multiple resolution strategies in priority order:

    1. YAML overrides (5 priority levels)
    2. Database cache lookup
    3. Existing company_id column (passthrough) + backflow
    4. EQC sync lookup (budgeted, cached)
    5. Temporary ID generation (HMAC-SHA1 based)

    The resolver is designed for batch processing performance, using vectorized
    Pandas operations where possible to achieve 5-10x speedup over row-by-row
    processing.

    Attributes:
        enrichment_service: Optional CompanyEnrichmentService for EQC lookup.
        yaml_overrides: Dict of priority level -> {alias: company_id} mappings.
        mapping_repository: Optional CompanyMappingRepository for database cache.
        salt: Salt for temporary ID generation (from environment or default).

    Example:
        >>> from work_data_hub.config import load_company_id_overrides
        >>> resolver = CompanyIdResolver(
        ...     yaml_overrides=load_company_id_overrides()
        ... )
        >>> df = pd.DataFrame({
        ...     "计划代码": ["FP0001", "UNKNOWN"],
        ...     "客户名称": ["公司A", "公司B"]
        ... })
        >>> result = resolver.resolve_batch(df, ResolutionStrategy())
        >>> result.data["company_id"].tolist()
        ['614810477', 'IN_XXXXXXXXXXXXXXXX']
    """

    def __init__(
        self,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,
        mapping_repository: Optional["CompanyMappingRepository"] = None,
        eqc_provider: Optional["EqcProvider"] = None,
    ) -> None:
        """
        Initialize the CompanyIdResolver.

        Args:
            enrichment_service: Optional CompanyEnrichmentService for EQC lookup (legacy).
            yaml_overrides: Dict of priority level -> {alias: company_id} mappings.
                If not provided, auto-loads from load_company_id_overrides().
            mapping_repository: Optional CompanyMappingRepository for database cache.
                If not provided, database lookup is skipped.
            eqc_provider: Optional EqcProvider for EQC sync lookup (Story 6.6).
                If provided, takes precedence over enrichment_service for EQC lookups.
                If not provided, will auto-create one with mapping_repository.
        """
        self.enrichment_service = enrichment_service
        self.mapping_repository = mapping_repository

        # Auto-create EqcProvider if not provided and mapping_repository is available
        if eqc_provider is None and mapping_repository is not None:
            try:
                from work_data_hub.config.settings import get_settings
                from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
                settings = get_settings()
                if hasattr(settings, 'eqc_token') and settings.eqc_token:
                    self.eqc_provider = EqcProvider(
                        token=settings.eqc_token,
                        budget=getattr(settings, 'company_sync_lookup_limit', 5),
                        base_url=getattr(settings, 'eqc_base_url', None),
                        mapping_repository=mapping_repository,  # 关键：传入 mapping_repository
                        validate_on_init=False
                    )
                    logger.info(
                        "company_id_resolver.eqc_provider_auto_created",
                        msg="Auto-created EqcProvider with mapping_repository"
                    )
                else:
                    self.eqc_provider = None
                    logger.debug(
                        "company_id_resolver.no_eqc_token",
                        msg="No EQC token configured, EqcProvider not created"
                    )
            except Exception as e:
                logger.warning(
                    "company_id_resolver.eqc_provider_creation_failed",
                    error=str(e),
                    msg="Failed to create EqcProvider"
                )
                self.eqc_provider = None
        else:
            self.eqc_provider = eqc_provider

            # If eqc_provider is provided but no mapping_repository, try to set it
            if self.eqc_provider and self.mapping_repository and not getattr(self.eqc_provider, 'mapping_repository', None):
                self.eqc_provider.mapping_repository = self.mapping_repository
                logger.info(
                    "company_id_resolver.eqc_provider_repo_set",
                    msg="Set mapping_repository on existing EqcProvider"
                )

        # Initialize YAML overrides
        if yaml_overrides is None:
            # Auto-load YAML if not provided
            try:
                from work_data_hub.config import load_company_id_overrides

                self.yaml_overrides = load_company_id_overrides()
            except Exception:
                # Graceful fallback if loading fails
                self.yaml_overrides = {level: {} for level in YAML_PRIORITY_ORDER}
                logger.debug(
                    "company_id_resolver.yaml_load_failed",
                    msg="Failed to auto-load YAML overrides, using empty defaults",
                )
        else:
            self.yaml_overrides = yaml_overrides

        # Load salt from environment with safety check
        self.salt = os.environ.get(SALT_ENV_VAR, DEFAULT_SALT)
        self._check_salt_safety()

    def _check_salt_safety(self) -> None:
        """Log warning if using default salt in non-development environment."""
        if self.salt == DEFAULT_SALT:
            # Check if we're in a production-like environment
            env = os.environ.get("ENVIRONMENT", "").lower()
            if env in ("production", "prod", "staging", "stage"):
                logger.warning(
                    "company_id_resolver.default_salt_in_production",
                    env=env,
                    msg=f"Using default development salt in {env} environment! "
                    f"Set {SALT_ENV_VAR} environment variable for production.",
                )
            else:
                logger.debug(
                    "company_id_resolver.using_default_salt",
                    msg="Using default development salt for temporary ID generation",
                )

    def resolve_batch(
        self,
        df: pd.DataFrame,
        strategy: ResolutionStrategy,
    ) -> ResolutionResult:
        """
        Batch resolve company_id with hierarchical strategy.

        Applies resolution strategies in priority order using vectorized
        operations for performance. Returns the DataFrame with resolved
        company IDs and statistics about the resolution process.

        Resolution Priority (Story 6.4):
        1. YAML overrides (5 levels: plan → account → hardcode → name → account_name)
        2. Database cache lookup
        3. Existing company_id column passthrough + backflow
        4. EQC sync lookup (budgeted, cached)
        5. Temporary ID generation

        Args:
            df: Input DataFrame containing columns specified in strategy.
            strategy: ResolutionStrategy configuration for column names
                and resolution behavior.

        Returns:
            ResolutionResult containing the resolved DataFrame (in .data)
            and statistics (in .statistics).

        Raises:
            ValueError: If required columns are missing from input DataFrame.

        Performance:
            - 1000 rows processed in <100ms (without EQC)
            - Memory usage <100MB for 10K rows
        """
        # Validate required columns
        required_cols = {strategy.customer_name_column}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Input DataFrame missing required columns: {missing_cols}"
            )

        result_df = df.copy()
        stats = ResolutionStatistics(
            total_rows=len(df),
            budget_remaining=strategy.sync_lookup_budget,
        )

        # Initialize output column with NaN
        result_df[strategy.output_column] = pd.NA

        # Track resolution sources for statistics
        resolution_mask = pd.Series(False, index=result_df.index)

        # Step 1: YAML overrides lookup (5 priority levels)
        yaml_resolved, yaml_hits = self._resolve_via_yaml_overrides(
            result_df, strategy
        )
        result_df[strategy.output_column] = yaml_resolved
        stats.yaml_hits = yaml_hits

        yaml_mask = result_df[strategy.output_column].notna()
        resolution_mask |= yaml_mask

        # Backward compatibility: set plan_override_hits
        stats.plan_override_hits = yaml_hits.get("plan", 0)

        logger.debug(
            "company_id_resolver.yaml_lookup_complete",
            total_hits=sum(yaml_hits.values()),
            hits_by_priority=yaml_hits,
        )

        # Step 2: Database cache lookup
        mask_missing = result_df[strategy.output_column].isna()
        if mask_missing.any() and self.mapping_repository:
            db_resolved, db_hits = self._resolve_via_db_cache(
                result_df, mask_missing, strategy, stats
            )
            # Fill in DB results for unresolved rows
            result_df.loc[mask_missing, strategy.output_column] = result_df.loc[
                mask_missing, strategy.output_column
            ].fillna(db_resolved.loc[mask_missing])

            stats.db_cache_hits = db_hits
            stats.ensure_db_cache_keys()
            db_mask = result_df[strategy.output_column].notna() & ~resolution_mask
            resolution_mask |= db_mask

            logger.debug(
                "company_id_resolver.db_cache_lookup_complete",
                hits=db_hits,
            )

        # Step 3: Existing company_id column passthrough
        mask_missing = result_df[strategy.output_column].isna()
        existing_column_resolved_indices: List[int] = []

        if strategy.company_id_column in result_df.columns:
            existing_values_all = result_df[strategy.company_id_column]
            existing_values_text = existing_values_all.astype(str).str.strip()
            # Only trust numeric company IDs from source column.
            # Reject placeholders like 'N' to avoid treating them as valid IDs.
            valid_existing_all = (
                existing_values_all.notna()
                & existing_values_text.str.fullmatch(r"\d+").fillna(False)
            )
            valid_mask = mask_missing & valid_existing_all
            result_df.loc[valid_mask, strategy.output_column] = existing_values_text[
                valid_mask
            ]

            existing_hits = result_df[strategy.output_column].notna() & ~resolution_mask
            stats.existing_column_hits = existing_hits.sum()
            resolution_mask |= existing_hits

            # Track indices for backflow
            existing_column_resolved_indices = list(
                result_df[existing_hits].index
            )

            logger.debug(
                "company_id_resolver.existing_column_passthrough_complete",
                hits=stats.existing_column_hits,
            )

        # Step 3b: Backflow new mappings from existing column
        if (
            strategy.enable_backflow
            and self.mapping_repository
            and existing_column_resolved_indices
        ):
            backflow_stats = self._backflow_new_mappings(
                result_df,
                existing_column_resolved_indices,
                strategy,
            )
            stats.backflow_stats = backflow_stats

        # Step 4: EQC sync lookup (budgeted, cached)
        mask_missing = result_df[strategy.output_column].isna()
        if (
            strategy.use_enrichment_service
            and mask_missing.any()
            and strategy.sync_lookup_budget > 0
            and (self.eqc_provider is not None or self.enrichment_service is not None)
        ):
            eqc_resolved, eqc_hits, budget_remaining = self._resolve_via_eqc_sync(
                result_df, mask_missing, strategy
            )
            # Fill in EQC results for unresolved rows
            result_df.loc[mask_missing, strategy.output_column] = result_df.loc[
                mask_missing, strategy.output_column
            ].fillna(eqc_resolved.loc[mask_missing])

            stats.eqc_sync_hits = eqc_hits
            stats.budget_consumed = strategy.sync_lookup_budget - budget_remaining
            stats.budget_remaining = budget_remaining

            # Legacy field
            stats.enrichment_service_hits = eqc_hits

            eqc_mask = result_df[strategy.output_column].notna() & ~resolution_mask
            resolution_mask |= eqc_mask

            logger.debug(
                "company_id_resolver.eqc_sync_complete",
                hits=eqc_hits,
                budget_consumed=stats.budget_consumed,
                budget_remaining=budget_remaining,
            )

        # Step 4.5: Default fallback for empty customer_name (Legacy compatibility)
        # From legacy data_cleaner.py lines 215-217: when company_id is empty AND
        # customer_name is empty, use hardcoded default '600866980'
        mask_missing = result_df[strategy.output_column].isna()
        customer_name_col = strategy.customer_name_column
        mask_empty_customer = mask_missing & (
            result_df[customer_name_col].isna() |
            (result_df[customer_name_col].astype(str).str.strip() == "")
        )
        if mask_empty_customer.any():
            result_df.loc[mask_empty_customer, strategy.output_column] = "600866980"
            stats.default_fallback_hits = int(mask_empty_customer.sum())
            resolution_mask |= mask_empty_customer

            logger.debug(
                "company_id_resolver.default_fallback_applied",
                count=stats.default_fallback_hits,
            )

        # Step 5: Generate temp IDs for remaining (vectorized apply)
        mask_still_missing = result_df[strategy.output_column].isna()
        temp_id_indices: List[int] = []
        if strategy.generate_temp_ids and mask_still_missing.any():
            result_df.loc[mask_still_missing, strategy.output_column] = result_df.loc[
                mask_still_missing, strategy.customer_name_column
            ].apply(lambda x: self._generate_temp_id(x))

            stats.temp_ids_generated = mask_still_missing.sum()
            temp_id_indices = list(result_df[mask_still_missing].index)

            logger.debug(
                "company_id_resolver.temp_ids_generated",
                count=stats.temp_ids_generated,
            )

        # Step 5b: Enqueue for async enrichment (Story 6.5)
        if (
            strategy.enable_async_queue
            and self.mapping_repository
            and temp_id_indices
        ):
            async_queued = self._enqueue_for_async_enrichment(
                result_df,
                temp_id_indices,
                strategy,
            )
            stats.async_queued = async_queued

        # Count unresolved
        stats.unresolved = result_df[strategy.output_column].isna().sum()

        logger.info(
            "company_id_resolver.batch_resolution_complete",
            total_rows=stats.total_rows,
            yaml_hits_total=sum(stats.yaml_hits.values()),
            db_cache_hits=stats.db_cache_hits,
            existing_column_hits=stats.existing_column_hits,
            eqc_sync_hits=stats.eqc_sync_hits,
            temp_ids_generated=stats.temp_ids_generated,
            unresolved=stats.unresolved,
        )

        return ResolutionResult(data=result_df, statistics=stats)

    def _resolve_via_yaml_overrides(
        self,
        df: pd.DataFrame,
        strategy: ResolutionStrategy,
    ) -> Tuple[pd.Series, Dict[str, int]]:
        """
        Resolve company_id via YAML overrides (5 priority levels).

        Priority order: plan (1) → account (2) → hardcode (3) →
        name (4) → account_name (5)

        Args:
            df: Input DataFrame.
            strategy: Resolution strategy configuration.

        Returns:
            Tuple of (resolved_series, hits_by_priority)
        """
        resolved = pd.Series(pd.NA, index=df.index, dtype=object)
        hits_by_priority: Dict[str, int] = {}

        # Map priority levels to columns
        priority_columns = {
            "plan": strategy.plan_code_column,
            "account": strategy.account_number_column,
            "hardcode": strategy.plan_code_column,  # Same as plan for hardcode
            "name": strategy.customer_name_column,
            "account_name": strategy.account_name_column,
        }

        for priority in YAML_PRIORITY_ORDER:
            column = priority_columns.get(priority)
            if not column or column not in df.columns:
                hits_by_priority[priority] = 0
                continue

            mappings = self.yaml_overrides.get(priority, {})
            if not mappings:
                hits_by_priority[priority] = 0
                continue

            # Vectorized lookup for unresolved rows
            mask_unresolved = resolved.isna()
            if not mask_unresolved.any():
                hits_by_priority[priority] = 0
                break

            # Map values to company IDs
            lookup_values = df.loc[mask_unresolved, column].map(mappings)
            new_hits = lookup_values.notna()

            # Update resolved series
            resolved.loc[mask_unresolved] = resolved.loc[mask_unresolved].fillna(
                lookup_values
            )
            hits_by_priority[priority] = int(new_hits.sum())

        return resolved, hits_by_priority

    def _resolve_via_db_cache(
        self,
        df: pd.DataFrame,
        mask_unresolved: pd.Series,
        strategy: ResolutionStrategy,
        stats: Optional[ResolutionStatistics] = None,
    ) -> Tuple[pd.Series, Dict[str, int]]:
        """
        Resolve company_id via database cache.

        Uses CompanyMappingRepository.lookup_batch() for batch-optimized
        single SQL round-trip.

        Story 6.4.1: P4 (customer_name) uses normalized values for lookup,
        while P1 (plan_code), P2 (account_number), P5 (account_name) use RAW values.

        Args:
            df: Input DataFrame.
            mask_unresolved: Boolean mask of unresolved rows.
            strategy: Resolution strategy configuration.

        Returns:
            Tuple of (resolved_series, hits_by_priority)
        """
        if not self.mapping_repository:
            return pd.Series(pd.NA, index=df.index, dtype=object), {}
        # Prefer new enrichment_index path (Story 6.1.1)
        repo = self.mapping_repository
        use_enrichment_index = callable(
            getattr(repo, "lookup_enrichment_index_batch", None)
        )
        if use_enrichment_index:
            try:
                resolved, hits = self._resolve_via_enrichment_index(
                    df, mask_unresolved, strategy, stats
                )
                # Use legacy fallback only if nothing was resolved and legacy API exists
                if sum(hits.values()) > 0 or not callable(
                    getattr(repo, "lookup_batch", None)
                ):
                    return resolved, hits
            except Exception as e:  # Graceful fallback to legacy path
                logger.warning(
                    "company_id_resolver.enrichment_index_lookup_failed",
                    error=str(e),
                )

        # Fallback: legacy company_mapping lookup
        return self._resolve_via_company_mapping(df, mask_unresolved, strategy)

    def _resolve_via_enrichment_index(
        self,
        df: pd.DataFrame,
        mask_unresolved: pd.Series,
        strategy: ResolutionStrategy,
        stats: Optional[ResolutionStatistics] = None,
    ) -> Tuple[pd.Series, Dict[str, int]]:
        """
        Resolve company_id via enrichment_index (DB-P1..P5).

        Priority order: plan_code → account_name → account_number →
        customer_name (normalized) → plan_customer (plan|normalized_customer).
        """
        keys_by_type: Dict[LookupType, set[str]] = {
            LookupType.PLAN_CODE: set(),
            LookupType.ACCOUNT_NAME: set(),
            LookupType.ACCOUNT_NUMBER: set(),
            LookupType.CUSTOMER_NAME: set(),
            LookupType.PLAN_CUSTOMER: set(),
        }

        for idx in df[mask_unresolved].index:
            row = df.loc[idx]
            plan_code = row.get(strategy.plan_code_column)
            account_name = row.get(strategy.account_name_column)
            account_number = row.get(strategy.account_number_column)
            customer_name = row.get(strategy.customer_name_column)

            if pd.notna(plan_code):
                keys_by_type[LookupType.PLAN_CODE].add(str(plan_code))
            if pd.notna(account_name):
                keys_by_type[LookupType.ACCOUNT_NAME].add(str(account_name))
            if pd.notna(account_number):
                keys_by_type[LookupType.ACCOUNT_NUMBER].add(str(account_number))
            if pd.notna(customer_name):
                normalized_customer = normalize_for_temp_id(str(customer_name))
                if normalized_customer:
                    keys_by_type[LookupType.CUSTOMER_NAME].add(normalized_customer)
                    if pd.notna(plan_code):
                        plan_customer_key = f"{plan_code}|{normalized_customer}"
                        keys_by_type[LookupType.PLAN_CUSTOMER].add(plan_customer_key)

        # Remove empty entry types to avoid unnecessary UNNEST arrays
        keys_by_type = {
            key_type: list(keys)
            for key_type, keys in keys_by_type.items()
            if keys
        }

        if not keys_by_type:
            return (
                pd.Series(pd.NA, index=df.index, dtype=object),
                {
                    "plan_code": 0,
                    "account_name": 0,
                    "account_number": 0,
                    "customer_name": 0,
                    "plan_customer": 0,
                },
            )

        resolved = pd.Series(pd.NA, index=df.index, dtype=object)
        used_keys: list[tuple[LookupType, str]] = []
        hits_by_priority: Dict[str, int] = {
            "plan_code": 0,
            "account_name": 0,
            "account_number": 0,
            "customer_name": 0,
            "plan_customer": 0,
        }
        decision_paths: Dict[int, str] = {}

        try:
            results = self.mapping_repository.lookup_enrichment_index_batch(
                keys_by_type
            )
        except Exception as e:
            logger.warning(
                "company_id_resolver.enrichment_index_query_failed",
                error=str(e),
            )
            return (
                pd.Series(pd.NA, index=df.index, dtype=object),
                hits_by_priority,
            )

        # Apply priority order per row
        priority_order = [
            LookupType.PLAN_CODE,
            LookupType.ACCOUNT_NAME,
            LookupType.ACCOUNT_NUMBER,
            LookupType.CUSTOMER_NAME,
            LookupType.PLAN_CUSTOMER,
        ]
        label_by_type = {
            LookupType.PLAN_CODE: "plan_code",
            LookupType.ACCOUNT_NAME: "account_name",
            LookupType.ACCOUNT_NUMBER: "account_number",
            LookupType.CUSTOMER_NAME: "customer_name",
            LookupType.PLAN_CUSTOMER: "plan_customer",
        }
        path_label_by_type = {
            LookupType.PLAN_CODE: "DB-P1",
            LookupType.ACCOUNT_NAME: "DB-P2",
            LookupType.ACCOUNT_NUMBER: "DB-P3",
            LookupType.CUSTOMER_NAME: "DB-P4",
            LookupType.PLAN_CUSTOMER: "DB-P5",
        }

        for idx in df[mask_unresolved].index:
            row = df.loc[idx]
            plan_code = row.get(strategy.plan_code_column)
            account_name = row.get(strategy.account_name_column)
            account_number = row.get(strategy.account_number_column)
            customer_name = row.get(strategy.customer_name_column)
            normalized_customer = (
                normalize_for_temp_id(str(customer_name))
                if pd.notna(customer_name)
                else ""
            )

            candidate_keys = {
                LookupType.PLAN_CODE: str(plan_code) if pd.notna(plan_code) else None,
                LookupType.ACCOUNT_NAME: str(account_name)
                if pd.notna(account_name)
                else None,
                LookupType.ACCOUNT_NUMBER: str(account_number)
                if pd.notna(account_number)
                else None,
                LookupType.CUSTOMER_NAME: normalized_customer or None,
                LookupType.PLAN_CUSTOMER: f"{plan_code}|{normalized_customer}"
                if pd.notna(plan_code) and normalized_customer
                else None,
            }

            path_segments: List[str] = []

            for lookup_type in priority_order:
                key = candidate_keys.get(lookup_type)
                label = path_label_by_type[lookup_type]
                priority_key = label_by_type[lookup_type]
                if not key:
                    path_segments.append(f"{label}:MISS")
                    continue

                record = results.get((lookup_type, key))
                if isinstance(record, EnrichmentIndexRecord):
                    company_id = str(record.company_id).strip()
                    # Validate cache entries: reject obvious placeholders like 'N' or empty values,
                    # but accept alphanumeric IDs like '602671512X' (special customer IDs).
                    # Valid format: at least 5 chars starting with digit (e.g., '602671512X')
                    if not company_id or len(company_id) < 5 or not company_id[0].isdigit():
                        path_segments.append(f"{label}:INVALID")
                        continue
                    resolved.loc[idx] = company_id
                    used_keys.append((lookup_type, key))
                    hits_by_priority[priority_key] += 1
                    path_segments.append(f"{label}:HIT")
                    break
                else:
                    path_segments.append(f"{label}:MISS")

            decision_paths[idx] = "→".join(path_segments)

        for row_idx, path in decision_paths.items():
            logger.debug(
                "company_id_resolver.db_cache_decision_path",
                index=int(row_idx),
                path=path,
                decision_path=path,
            )

        decision_path_counts: Dict[str, int] = {}
        for path in decision_paths.values():
            decision_path_counts[path] = decision_path_counts.get(path, 0) + 1

        if stats is not None:
            stats.db_decision_path_counts = decision_path_counts

        # Emit summary metrics/logs for per-priority hits (observable counters)
        logger.info(
            "company_id_resolver.db_cache_priority_summary",
            hits_by_priority=hits_by_priority,
            total_hits=sum(hits_by_priority.values()),
            resolved_rows=int(resolved.notna().sum()),
        )
        logger.info(
            "company_id_resolver.db_cache_metrics",
            hits_by_priority=hits_by_priority,
            decision_path_counts=decision_path_counts,
            total_hits=sum(hits_by_priority.values()),
            resolved_rows=int(resolved.notna().sum()),
        )

        # Increment hit_count on matched records (best-effort)
        if used_keys and callable(getattr(self.mapping_repository, "update_hit_count", None)):
            for lookup_type, key in used_keys:
                try:
                    self.mapping_repository.update_hit_count(key, lookup_type)
                except Exception:
                    # Non-blocking
                    continue

        return resolved, hits_by_priority

    def _resolve_via_company_mapping(
        self,
        df: pd.DataFrame,
        mask_unresolved: pd.Series,
        strategy: ResolutionStrategy,
    ) -> Tuple[pd.Series, Dict[str, int]]:
        """
        Legacy fallback: resolve via company_mapping table.
        """
        # Collect all potential lookup values from unresolved rows
        lookup_columns = [
            (strategy.plan_code_column, False),       # P1: RAW
            (strategy.account_number_column, False),  # P2: RAW
            (strategy.customer_name_column, True),    # P4: NORMALIZED
            (strategy.account_name_column, False),    # P5: RAW
        ]

        alias_names: set[str] = set()
        for col, needs_normalization in lookup_columns:
            if col not in df.columns:
                continue
            values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
            for v in values:
                if needs_normalization:
                    normalized = normalize_company_name(v)
                    if normalized:
                        alias_names.add(normalized)
                else:
                    alias_names.add(v)

        if not alias_names:
            return pd.Series(pd.NA, index=df.index, dtype=object), {"legacy": 0}

        # Batch lookup from database
        try:
            results = self.mapping_repository.lookup_batch(list(alias_names))
        except Exception as e:
            logger.warning(
                "company_id_resolver.db_cache_lookup_failed",
                error=str(e),
            )
            return pd.Series(pd.NA, index=df.index, dtype=object), {"legacy": 0}

        resolved = pd.Series(pd.NA, index=df.index, dtype=object)
        hits_by_priority: Dict[str, int] = {"legacy": 0}

        for idx in df[mask_unresolved].index:
            row = df.loc[idx]
            for col, needs_normalization in lookup_columns:
                if col not in df.columns:
                    continue
                value = row[col]
                if pd.isna(value):
                    continue
                str_value = str(value)

                if needs_normalization:
                    lookup_key = normalize_company_name(str_value)
                    if not lookup_key:
                        continue
                else:
                    lookup_key = str_value

                if lookup_key in results:
                    resolved.loc[idx] = results[lookup_key].company_id
                    hits_by_priority["legacy"] += 1
                    break

        return resolved, hits_by_priority

    def _resolve_via_eqc_sync(
        self,
        df: pd.DataFrame,
        mask_unresolved: pd.Series,
        strategy: ResolutionStrategy,
    ) -> Tuple[pd.Series, int, int]:
        """
        Resolve via EQC within budget; cache results to enterprise.company_mapping.

        Story 6.6: Supports both EqcProvider (preferred) and legacy enrichment_service.

        Args:
            df: Input DataFrame.
            mask_unresolved: Boolean mask of unresolved rows.
            strategy: Resolution strategy configuration.

        Returns:
            Tuple of (resolved_series, eqc_hits, budget_remaining)
        """
        # Story 6.6: Use EqcProvider if available, otherwise fall back to enrichment_service
        use_eqc_provider = self.eqc_provider is not None and self.eqc_provider.is_available
        use_enrichment_service = self.enrichment_service is not None and not use_eqc_provider

        if not (use_eqc_provider or use_enrichment_service) or strategy.sync_lookup_budget <= 0:
            return (
                pd.Series(pd.NA, index=df.index, dtype=object),
                0,
                strategy.sync_lookup_budget,
            )

        # Story 6.6: Use EqcProvider path if available
        if use_eqc_provider:
            return self._resolve_via_eqc_provider(df, mask_unresolved, strategy)

        budget_remaining = strategy.sync_lookup_budget
        resolved = pd.Series(pd.NA, index=df.index, dtype=object)
        eqc_hits = 0

        cache_payloads: List[Dict[str, Any]] = []

        # Deduplicate by normalized customer name so budget is consumed per-unique name
        # (not per-row), and apply a successful hit to all matching rows.
        unresolved_name_series = df.loc[mask_unresolved, strategy.customer_name_column]
        indices_by_name: Dict[str, List[int]] = {}
        exemplar_row_by_name: Dict[str, pd.Series] = {}
        for idx, raw_name in unresolved_name_series.items():
            if pd.isna(raw_name):
                continue
            raw_text = str(raw_name).strip()
            if not raw_text:
                continue
            normalized_name = normalize_for_temp_id(raw_text) or raw_text
            indices_by_name.setdefault(normalized_name, []).append(idx)
            exemplar_row_by_name.setdefault(normalized_name, df.loc[idx])

        for normalized_name, indices in indices_by_name.items():
            if budget_remaining <= 0:
                break

            row = exemplar_row_by_name[normalized_name]
            customer_name = row.get(strategy.customer_name_column)
            if pd.isna(customer_name):
                continue

            try:
                result = self.enrichment_service.resolve_company_id(
                    plan_code=row.get(strategy.plan_code_column)
                    if pd.notna(row.get(strategy.plan_code_column))
                    else None,
                    customer_name=str(customer_name),
                    account_name=row.get(strategy.account_name_column)
                    if pd.notna(row.get(strategy.account_name_column))
                    else None,
                    sync_lookup_budget=1,
                )
                budget_remaining -= 1

                if result and result.company_id:
                    for idx in indices:
                        resolved.loc[idx] = result.company_id
                    eqc_hits += len(indices)

                    cache_payloads.append(
                        {
                            # Align EQC cache entries with P4 normalization so lookups hit
                            "alias_name": normalize_company_name(str(customer_name))
                            or str(customer_name).strip(),
                            "canonical_id": result.company_id,
                            "match_type": "eqc",
                            "priority": 6,
                            "source": "eqc_sync",
                        }
                    )

            except Exception as e:
                budget_remaining -= 1
                logger.warning(
                    "company_id_resolver.eqc_lookup_failed",
                    error=str(e),
                )
                # Continue to next name - don't block pipeline

        if cache_payloads and self.mapping_repository:
            # Deduplicate by alias_name/match_type to avoid redundant inserts
            deduped: Dict[Tuple[str, str], Dict[str, Any]] = {}
            for payload in cache_payloads:
                key = (payload["alias_name"], payload["match_type"])
                deduped.setdefault(key, payload)

            try:
                self.mapping_repository.insert_batch_with_conflict_check(
                    list(deduped.values())
                )
            except Exception as cache_err:
                logger.warning(
                    "company_id_resolver.eqc_cache_failed",
                    error=str(cache_err),
                )

        return resolved, eqc_hits, budget_remaining

    def _resolve_via_eqc_provider(
        self,
        df: pd.DataFrame,
        mask_unresolved: pd.Series,
        strategy: ResolutionStrategy,
    ) -> Tuple[pd.Series, int, int]:
        """
        Resolve via EqcProvider (Story 6.6).

        Uses the new EqcProvider adapter for EQC API lookups with built-in
        budget management, caching, and error handling.

        Args:
            df: Input DataFrame.
            mask_unresolved: Boolean mask of unresolved rows.
            strategy: Resolution strategy configuration.

        Returns:
            Tuple of (resolved_series, eqc_hits, budget_remaining)
        """
        resolved = pd.Series(pd.NA, index=df.index, dtype=object)
        eqc_hits = 0

        # EqcProvider manages its own budget internally
        # Set provider budget to match strategy budget
        if self.eqc_provider.budget != strategy.sync_lookup_budget:
            self.eqc_provider.budget = strategy.sync_lookup_budget
            self.eqc_provider.remaining_budget = strategy.sync_lookup_budget

        # Deduplicate by normalized customer name so budget is consumed per-unique name
        # (not per-row), and apply a successful hit to all matching rows.
        unresolved_name_series = df.loc[mask_unresolved, strategy.customer_name_column]
        indices_by_name: Dict[str, List[int]] = {}
        exemplar_raw_by_name: Dict[str, str] = {}
        for idx, raw_name in unresolved_name_series.items():
            if pd.isna(raw_name):
                continue
            raw_text = str(raw_name).strip()
            if not raw_text:
                continue
            normalized_name = normalize_for_temp_id(raw_text) or raw_text
            indices_by_name.setdefault(normalized_name, []).append(idx)
            exemplar_raw_by_name.setdefault(normalized_name, raw_text)

        for normalized_name, indices in indices_by_name.items():
            # Check if provider still has budget
            if not self.eqc_provider.is_available:
                break

            try:
                # EqcProvider.lookup() handles budget, caching, and errors internally
                result = self.eqc_provider.lookup(exemplar_raw_by_name[normalized_name])

                if result:
                    for idx in indices:
                        resolved.loc[idx] = result.company_id
                    eqc_hits += len(indices)

            except Exception as e:
                logger.warning(
                    "company_id_resolver.eqc_provider_lookup_failed",
                    error_type=type(e).__name__,
                )
                # Continue to next name - don't block pipeline

        budget_remaining = self.eqc_provider.remaining_budget

        logger.info(
            "company_id_resolver.eqc_provider_completed",
            eqc_hits=eqc_hits,
            budget_remaining=budget_remaining,
        )

        return resolved, eqc_hits, budget_remaining

    def _backflow_new_mappings(
        self,
        df: pd.DataFrame,
        resolved_indices: List[int],
        strategy: ResolutionStrategy,
    ) -> Dict[str, int]:
        """
        Backflow new mappings to database cache.

        Collects mappings from rows resolved via existing column and inserts
        them into the database for future cache hits.

        Story 6.4.1: P4 (customer_name) uses normalized values for backflow,
        while P2 (account_number), P5 (account_name) use RAW values.

        Args:
            df: DataFrame with resolved company IDs.
            resolved_indices: Indices of rows resolved via existing column.
            strategy: Resolution strategy configuration.

        Returns:
            Dict with keys: inserted, skipped, conflicts
        """
        if not self.mapping_repository:
            return {"inserted": 0, "skipped": 0, "conflicts": 0}

        new_mappings: List[Dict[str, Any]] = []
        # Story 6.4.1: P4 (customer_name) needs normalization, others use RAW values
        backflow_fields = [
            (strategy.account_number_column, "account", 2, False),     # P2: RAW
            (strategy.customer_name_column, "name", 4, True),          # P4: NORMALIZED
            (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
        ]

        for idx in resolved_indices:
            row = df.loc[idx]
            company_id = str(row[strategy.output_column])

            # Skip temporary IDs
            if company_id.startswith("IN"):
                continue

            for column, match_type, priority, needs_normalization in backflow_fields:
                if column not in df.columns:
                    continue
                alias_value = row.get(column)
                if pd.isna(alias_value) or not str(alias_value).strip():
                    continue

                # Story 6.4.1: Apply normalization for P4 only
                if needs_normalization:
                    alias_name = normalize_company_name(str(alias_value))
                    if not alias_name:
                        continue  # Skip if normalization returns empty
                else:
                    alias_name = str(alias_value).strip()

                new_mappings.append(
                    {
                        "alias_name": alias_name,
                        "canonical_id": company_id,
                        "match_type": match_type,
                        "priority": priority,
                        "source": "pipeline_backflow",
                    }
                )

        if not new_mappings:
            return {"inserted": 0, "skipped": 0, "conflicts": 0}

        try:
            result = self.mapping_repository.insert_batch_with_conflict_check(
                new_mappings
            )

            if result.conflicts:
                logger.warning(
                    "company_id_resolver.backflow.conflicts_detected",
                    conflict_count=len(result.conflicts),
                )

            logger.info(
                "company_id_resolver.backflow.completed",
                inserted=result.inserted_count,
                skipped=result.skipped_count,
                conflicts=len(result.conflicts),
            )

            return {
                "inserted": result.inserted_count,
                "skipped": result.skipped_count,
                "conflicts": len(result.conflicts),
            }

        except Exception as e:
            logger.warning(
                "company_id_resolver.backflow.failed",
                error=str(e),
            )
            return {"inserted": 0, "skipped": 0, "conflicts": 0}

    def _enqueue_for_async_enrichment(
        self,
        df: pd.DataFrame,
        temp_id_indices: List[int],
        strategy: ResolutionStrategy,
    ) -> int:
        """
        Enqueue unresolved company names for async enrichment (Story 6.5).

        Called after temp ID generation to queue names for background
        resolution via the enterprise.enrichment_requests table.

        Args:
            df: DataFrame with resolved company IDs (including temp IDs).
            temp_id_indices: Indices of rows that received temp IDs.
            strategy: Resolution strategy configuration.

        Returns:
            Number of requests actually enqueued (excludes duplicates).
        """
        if not self.mapping_repository or not temp_id_indices:
            return 0

        # Build enqueue requests using normalize_for_temp_id for dedup parity
        enqueue_requests: List[Dict[str, str]] = []
        seen_normalized: set[str] = set()

        for idx in temp_id_indices:
            row = df.loc[idx]
            raw_name = row.get(strategy.customer_name_column)
            temp_id = row.get(strategy.output_column)

            if pd.isna(raw_name) or not str(raw_name).strip():
                continue

            raw_name_str = str(raw_name)
            normalized = normalize_for_temp_id(raw_name_str)

            # Deduplicate within batch by normalized name
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)

            enqueue_requests.append(
                {
                    "raw_name": raw_name_str,
                    "normalized_name": normalized,
                    "temp_id": str(temp_id) if pd.notna(temp_id) else "",
                }
            )

        if not enqueue_requests:
            return 0

        # Graceful degradation: enqueue failures don't block pipeline
        try:
            result = self.mapping_repository.enqueue_for_enrichment(enqueue_requests)

            logger.info(
                "company_id_resolver.async_enqueue.completed",
                queued_count=result.queued_count,
                skipped_count=result.skipped_count,
            )

            return result.queued_count

        except Exception as e:
            logger.warning(
                "company_id_resolver.async_enqueue.failed",
                error=str(e),
            )
            return 0

    def _generate_temp_id(self, customer_name: Optional[str]) -> str:
        """
        Generate temporary company ID using HMAC-SHA1.

        Delegates to the normalizer module which handles legacy-compatible
        name normalization before hashing.

        Args:
            customer_name: Customer name to generate ID for.

        Returns:
            Temporary ID in format "IN_<16-char-Base32>".
        """
        if not customer_name or not str(customer_name).strip():
            # For empty names, use a placeholder
            customer_name = "__EMPTY__"

        return generate_temp_company_id(str(customer_name), self.salt)

    def _resolve_via_enrichment(
        self,
        plan_code: Optional[str],
        customer_name: Optional[str],
        account_name: Optional[str],
        budget: int,
    ) -> Optional[str]:
        """
        Delegate resolution to enrichment service if available.

        DEPRECATED: Use _resolve_via_eqc_sync for batch operations.

        Args:
            plan_code: Plan code for lookup.
            customer_name: Customer name for lookup.
            account_name: Account name for lookup.
            budget: Sync lookup budget.

        Returns:
            Resolved company ID or None if not found.
        """
        if not self.enrichment_service:
            return None

        try:
            result = self.enrichment_service.resolve_company_id(
                plan_code=plan_code,
                customer_name=customer_name,
                account_name=account_name,
                sync_lookup_budget=budget,
            )
            return result.company_id if result.company_id else None
        except Exception as e:
            logger.warning(
                "company_id_resolver.enrichment_failed",
                error=str(e),
            )
            return None

    def _resolve_via_enrichment_batch(
        self,
        df: pd.DataFrame,
        mask: pd.Series,
        strategy: ResolutionStrategy,
    ) -> int:
        """
        Batch resolve via enrichment service for rows matching mask.

        DEPRECATED: Use _resolve_via_eqc_sync instead.

        Note: This uses row-by-row processing as enrichment service
        doesn't support true batch operations. Budget is shared across
        all rows.

        Args:
            df: DataFrame to update in place.
            mask: Boolean mask of rows to process.
            strategy: Resolution strategy configuration.

        Returns:
            Number of successful resolutions.
        """
        hits = 0
        remaining_budget = strategy.sync_lookup_budget

        for idx in df[mask].index:
            if remaining_budget <= 0:
                break

            row = df.loc[idx]
            plan_code = row.get(strategy.plan_code_column)
            customer_name = row.get(strategy.customer_name_column)
            account_name = row.get(strategy.account_name_column)

            result = self._resolve_via_enrichment(
                plan_code=plan_code if pd.notna(plan_code) else None,
                customer_name=customer_name if pd.notna(customer_name) else None,
                account_name=account_name if pd.notna(account_name) else None,
                budget=1,  # Use 1 per row
            )

            if result:
                df.loc[idx, strategy.output_column] = result
                hits += 1

            remaining_budget -= 1

        return hits
