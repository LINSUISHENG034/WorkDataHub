"""
Core CompanyIdResolver class.

This module contains the main CompanyIdResolver class with initialization
and the primary resolve_batch entry point. Strategy implementations are
split across sibling modules for maintainability.

Story 7.3: Infrastructure Layer Decomposition
"""

import logging
import os
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

from work_data_hub.utils.logging import get_logger

from ..eqc_lookup_config import EqcLookupConfig
from ..types import (
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
_stdlib_logger = logging.getLogger(__name__)
if _stdlib_logger.propagate is False:
    _stdlib_logger.propagate = True
if _stdlib_logger.level == logging.NOTSET:
    _stdlib_logger.setLevel(logging.DEBUG)

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
        >>> from work_data_hub.infrastructure.enrichment.eqc_lookup_config import EqcLookupConfig
        >>> resolver = CompanyIdResolver(
        ...     eqc_config=EqcLookupConfig.disabled(),  # Required param (Story 6.2-P17)
        ...     yaml_overrides=load_company_id_overrides()
        ... )
        >>> df = pd.DataFrame({
        ...     "计划代码": ["FP0001", "UNKNOWN"],
        ...     "客户名称": ["公司A", "公司B"]
        ... })
        >>> result = resolver.resolve_batch(df, ResolutionStrategy())
        >>> result.data["company_id"].tolist()
        ['614810477', 'INXXXXXXXXXXXXXXXX']
    """

    def __init__(
        self,
        eqc_config: EqcLookupConfig,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,
        mapping_repository: Optional["CompanyMappingRepository"] = None,
        eqc_provider: Optional["EqcProvider"] = None,
    ) -> None:
        """
        Initialize the CompanyIdResolver.

        Story 6.2-P17: Breaking Change - eqc_config is now REQUIRED parameter.
        This enforces explicit configuration and prevents hidden auto-creation
        of EqcProvider that ignores upper-layer intent.

        Args:
            eqc_config: EqcLookupConfig controlling EQC lookup behavior.
                REQUIRED parameter (no default). Use EqcLookupConfig.disabled()
                for tests or domains that don't need enrichment.
            enrichment_service: Optional CompanyEnrichmentService for EQC lookup (legacy).
                Deprecated in favor of eqc_provider + eqc_config.
            yaml_overrides: Dict of priority level -> {alias: company_id} mappings.
                If not provided, auto-loads from load_company_id_overrides().
            mapping_repository: Optional CompanyMappingRepository for database cache.
                If not provided, database lookup is skipped.
            eqc_provider: Optional EqcProvider for EQC sync lookup.
                If not provided AND eqc_config.should_auto_create_provider is True,
                will create one using settings + mapping_repository.

        Example:
            >>> # For tests - disable EQC
            >>> resolver = CompanyIdResolver(
            ...     eqc_config=EqcLookupConfig.disabled(),
            ...     mapping_repository=repo
            ... )

            >>> # For production - explicit config
            >>> config = EqcLookupConfig(enabled=True, sync_budget=10)
            >>> resolver = CompanyIdResolver(
            ...     eqc_config=config,
            ...     mapping_repository=repo
            ... )
        """
        self.eqc_config = eqc_config
        self.enrichment_service = enrichment_service
        self.mapping_repository = mapping_repository

        # Only auto-create EqcProvider when EXPLICITLY allowed by config
        # Story 6.2-P17: Remove "magic" auto-creation that ignores upper-layer intent
        if eqc_provider is None and eqc_config.should_auto_create_provider:
            # Config explicitly allows auto-creation
            if mapping_repository is None:
                logger.warning(
                    "company_id_resolver.cannot_auto_create_eqc_provider",
                    msg="eqc_config allows auto-creation but mapping_repository is None",
                )
                self.eqc_provider = None
            else:
                try:
                    from work_data_hub.config.settings import get_settings
                    from work_data_hub.infrastructure.enrichment.eqc_provider import (
                        EqcProvider,
                    )

                    settings = get_settings()
                    if hasattr(settings, "eqc_token") and settings.eqc_token:
                        self.eqc_provider = EqcProvider(
                            token=settings.eqc_token,
                            budget=eqc_config.sync_budget,  # Use config budget
                            base_url=getattr(settings, "eqc_base_url", None),
                            mapping_repository=mapping_repository,
                            validate_on_init=False,
                        )
                        logger.info(
                            "company_id_resolver.eqc_provider_created",
                            msg="Created EqcProvider per eqc_config.should_auto_create_provider",
                        )
                    else:
                        self.eqc_provider = None
                        logger.debug(
                            "company_id_resolver.no_eqc_token",
                            msg="No EQC token configured, EqcProvider not created",
                        )
                except Exception as e:
                    logger.warning(
                        "company_id_resolver.eqc_provider_creation_failed",
                        error=str(e),
                        msg="Failed to create EqcProvider",
                    )
                    self.eqc_provider = None
        else:
            # Use injected provider or None (no auto-creation)
            self.eqc_provider = eqc_provider

            # If eqc_provider is provided but no mapping_repository, try to set it
            if (
                self.eqc_provider
                and self.mapping_repository
                and not getattr(self.eqc_provider, "mapping_repository", None)
            ):
                self.eqc_provider.mapping_repository = self.mapping_repository
                logger.info(
                    "company_id_resolver.eqc_provider_repo_set",
                    msg="Set mapping_repository on existing EqcProvider",
                )

        # Validate consistency: warn if enrichment_service contradicts eqc_config
        if enrichment_service is not None and not eqc_config.enabled:
            logger.warning(
                "company_id_resolver.config_contradiction",
                msg="enrichment_service provided but eqc_config.enabled=False. "
                "enrichment_service will be IGNORED per eqc_config.",
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
        verbose: bool = False,
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
            verbose: Whether to show progress bar for EQC API calls (Story 7.1-14 AC-4).

        Returns:
            ResolutionResult containing the resolved DataFrame (in .data)
            and statistics (in .statistics).

        Raises:
            ValueError: If required columns are missing from input DataFrame.

        Performance:
            - 1000 rows processed in <100ms (without EQC)
            - Memory usage <100MB for 10K rows
        """
        # Import strategy modules here to avoid circular imports
        from .backflow import (
            backflow_new_mappings,
            enqueue_for_async_enrichment,
            generate_temp_id,
        )
        from .db_strategy import resolve_via_db_cache
        from .eqc_strategy import resolve_via_eqc_sync
        from .yaml_strategy import resolve_via_yaml_overrides

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
            # Story 6.2-P17: Budget is controlled by EqcLookupConfig (SSOT), not strategy.
            budget_remaining=self.eqc_config.sync_budget,
        )

        # Initialize output column with NaN
        result_df[strategy.output_column] = pd.NA

        # Track resolution sources for statistics
        resolution_mask = pd.Series(False, index=result_df.index)

        # Story 7.1-14: Cache Warming (Task 2 - Highest ROI)
        # Pre-batch cache warming: extract unique customer names and query enrichment_index once
        # This reduces EQC API calls by proactively populating an in-memory cache
        cache_stats: dict[str, int] = {}
        if self.mapping_repository:
            from .cache_warming import CacheWarmer

            warmer = CacheWarmer(self.mapping_repository)
            warmed_cache = warmer.warm_cache(result_df, strategy.customer_name_column)

            if warmed_cache:
                cache_stats = {
                    "cache_warming_hits": len(warmed_cache),
                    "cache_warming_total": len(
                        result_df[strategy.customer_name_column].dropna().unique()
                    ),
                }
                logger.info(
                    "company_id_resolver.cache_warming_stats",
                    **cache_stats,
                )

        # Step 1: YAML overrides lookup (5 priority levels)
        yaml_resolved, yaml_hits = resolve_via_yaml_overrides(
            result_df, strategy, self.yaml_overrides
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
            db_resolved, db_hits = resolve_via_db_cache(
                result_df, mask_missing, strategy, stats, self.mapping_repository
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
            # Preserve non-empty company IDs from the source column.
            # Reject common placeholders like 'N' to avoid treating them as valid IDs.
            invalid_sentinels = {"N", "NA", "N/A", "NONE", "NULL", "NAN"}
            valid_existing_all = (
                existing_values_all.notna()
                & (existing_values_text != "")
                & ~existing_values_text.str.upper().isin(invalid_sentinels)
            )
            valid_mask = mask_missing & valid_existing_all
            result_df.loc[valid_mask, strategy.output_column] = existing_values_text[
                valid_mask
            ]

            existing_hits = result_df[strategy.output_column].notna() & ~resolution_mask
            stats.existing_column_hits = existing_hits.sum()
            resolution_mask |= existing_hits

            # Track indices for backflow
            existing_column_resolved_indices = list(result_df[existing_hits].index)

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
            backflow_stats = backflow_new_mappings(
                result_df,
                existing_column_resolved_indices,
                strategy,
                self.mapping_repository,
            )
            stats.backflow_stats = backflow_stats

        # Step 4: EQC sync lookup (budgeted, cached)
        # Story 6.2-P17: Use eqc_config.enabled instead of strategy flag
        mask_missing = result_df[strategy.output_column].isna()
        if (
            self.eqc_config.enabled  # Config-driven enablement (Story 6.2-P17)
            and mask_missing.any()
            and self.eqc_config.sync_budget > 0  # Use config budget
            and (self.eqc_provider is not None or self.enrichment_service is not None)
        ):
            eqc_resolved, eqc_hits, budget_remaining = resolve_via_eqc_sync(
                result_df,
                mask_missing,
                strategy,
                self.eqc_config,
                self.eqc_provider,
                self.enrichment_service,
                self.mapping_repository,
                verbose=verbose,  # Story 7.1-14 AC-4: Pass verbose for progress bar
            )
            # Fill in EQC results for unresolved rows
            result_df.loc[mask_missing, strategy.output_column] = result_df.loc[
                mask_missing, strategy.output_column
            ].fillna(eqc_resolved.loc[mask_missing])

            stats.eqc_sync_hits = eqc_hits
            stats.budget_consumed = self.eqc_config.sync_budget - budget_remaining
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

        # Step 5: Generate temp IDs for remaining (vectorized apply)
        mask_still_missing = result_df[strategy.output_column].isna()
        temp_id_indices: List[int] = []
        if strategy.generate_temp_ids and mask_still_missing.any():
            result_df.loc[mask_still_missing, strategy.output_column] = result_df.loc[
                mask_still_missing, strategy.customer_name_column
            ].apply(lambda x: generate_temp_id(x, self.salt))

            # Story 7.5-3 CRITICAL FIX: Only include rows that actually received a temp ID
            # generate_temp_id() now returns None for empty customer names, so we must
            # re-check the mask after generation to exclude those rows from async queue.
            # Before this fix, all rows in mask_still_missing were added to temp_id_indices,
            # even if generate_temp_id() returned None (empty names).
            mask_received_temp_id = result_df[mask_still_missing][
                strategy.output_column
            ].notna()
            temp_id_indices = list(
                result_df[mask_still_missing][mask_received_temp_id].index
            )

            stats.temp_ids_generated = mask_received_temp_id.sum()

            logger.debug(
                "company_id_resolver.temp_ids_generated",
                count=stats.temp_ids_generated,
            )

        # Step 5b: Enqueue for async enrichment (Story 6.5)
        if strategy.enable_async_queue and self.mapping_repository and temp_id_indices:
            async_queued = enqueue_for_async_enrichment(
                result_df,
                temp_id_indices,
                strategy,
                self.mapping_repository,
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
