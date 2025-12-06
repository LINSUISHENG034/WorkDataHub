"""
Company ID Resolver for batch company identification.

This module provides the CompanyIdResolver class for batch-optimized company ID
resolution with hierarchical strategy support. It extracts and centralizes the
company ID resolution logic from domain layer for cross-domain reuse.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition

Resolution Priority:
1. Plan override lookup (vectorized)
2. Existing company_id column passthrough
3. Enrichment service delegation (optional)
4. Temporary ID generation (HMAC-SHA1 based)
"""

import logging
import os
from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd

from .normalizer import generate_temp_company_id
from .types import ResolutionResult, ResolutionStatistics, ResolutionStrategy

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = logging.getLogger(__name__)

# Default salt for development - MUST be overridden in production
DEFAULT_SALT = "default_dev_salt_change_in_prod"
SALT_ENV_VAR = "WDH_ALIAS_SALT"


class CompanyIdResolver:
    """
    Batch-optimized company ID resolver with hierarchical strategy support.

    This class provides vectorized company ID resolution for DataFrames,
    supporting multiple resolution strategies in priority order:

    1. Plan override mapping (direct lookup)
    2. Existing company_id column (passthrough)
    3. Enrichment service (optional, for complex resolution)
    4. Temporary ID generation (HMAC-SHA1 based)

    The resolver is designed for batch processing performance, using vectorized
    Pandas operations where possible to achieve 5-10x speedup over row-by-row
    processing.

    Attributes:
        enrichment_service: Optional CompanyEnrichmentService for complex resolution.
        plan_override_mapping: Dict mapping plan codes to company IDs.
        salt: Salt for temporary ID generation (from environment or default).

    Example:
        >>> resolver = CompanyIdResolver(
        ...     plan_override_mapping={"FP0001": "614810477"}
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
        plan_override_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize the CompanyIdResolver.

        Args:
            enrichment_service: Optional CompanyEnrichmentService for delegating
                complex resolution. If not provided, resolver works standalone.
            plan_override_mapping: Dict mapping plan codes to company IDs for
                direct override lookup. Typically loaded from
                data/mappings/company_id_overrides_plan.yml.
        """
        self.enrichment_service = enrichment_service
        self.plan_override_mapping = plan_override_mapping or {}

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
                    f"Using default development salt in {env} environment! "
                    f"Set {SALT_ENV_VAR} environment variable for production."
                )
            else:
                logger.debug(
                    "Using default development salt for temporary ID generation"
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
            - 1000 rows processed in <100ms (without external API)
            - Memory usage <100MB for 10K rows
        """
        # Validate required columns
        required_cols = {strategy.plan_code_column, strategy.customer_name_column}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Input DataFrame missing required columns: {missing_cols}"
            )

        result_df = df.copy()
        stats = ResolutionStatistics(total_rows=len(df))

        # Initialize output column with NaN
        result_df[strategy.output_column] = pd.NA

        # Track resolution sources for statistics
        resolution_mask = pd.Series(False, index=result_df.index)

        # Step 1: Vectorized plan override lookup
        if self.plan_override_mapping:
            result_df[strategy.output_column] = result_df[
                strategy.plan_code_column
            ].map(self.plan_override_mapping)

            plan_hits = result_df[strategy.output_column].notna()
            stats.plan_override_hits = plan_hits.sum()
            resolution_mask |= plan_hits

            logger.debug(f"Plan override lookup: {stats.plan_override_hits} hits")

        # Step 2: Fill remaining with existing company_id column
        mask_missing = result_df[strategy.output_column].isna()
        if strategy.company_id_column in result_df.columns:
            existing_values = result_df.loc[mask_missing, strategy.company_id_column]
            # Only use non-empty existing values
            valid_existing = existing_values.notna() & (existing_values != "")
            valid_mask = mask_missing & valid_existing.reindex(
                mask_missing.index, fill_value=False
            )
            result_df.loc[valid_mask, strategy.output_column] = result_df.loc[
                valid_mask, strategy.company_id_column
            ]

            existing_hits = result_df[strategy.output_column].notna() & ~resolution_mask
            stats.existing_column_hits = existing_hits.sum()
            resolution_mask |= existing_hits

            logger.debug(
                f"Existing column passthrough: {stats.existing_column_hits} hits"
            )

        # Step 3: Enrichment service delegation (if enabled and available)
        if strategy.use_enrichment_service and self.enrichment_service:
            mask_still_missing = result_df[strategy.output_column].isna()
            if mask_still_missing.any() and strategy.sync_lookup_budget > 0:
                enrichment_hits = self._resolve_via_enrichment_batch(
                    result_df, mask_still_missing, strategy
                )
                stats.enrichment_service_hits = enrichment_hits
                resolution_mask |= (
                    result_df[strategy.output_column].notna() & ~resolution_mask
                )

                logger.debug(
                    f"Enrichment service: {stats.enrichment_service_hits} hits"
                )

        # Step 4: Generate temp IDs for remaining (vectorized apply)
        mask_still_missing = result_df[strategy.output_column].isna()
        if strategy.generate_temp_ids and mask_still_missing.any():
            result_df.loc[mask_still_missing, strategy.output_column] = result_df.loc[
                mask_still_missing, strategy.customer_name_column
            ].apply(lambda x: self._generate_temp_id(x))

            stats.temp_ids_generated = mask_still_missing.sum()

            logger.debug(f"Temp IDs generated: {stats.temp_ids_generated}")

        # Count unresolved
        stats.unresolved = result_df[strategy.output_column].isna().sum()

        logger.info(
            "Batch resolution complete",
            extra={"statistics": stats.to_dict()},
        )

        return ResolutionResult(data=result_df, statistics=stats)

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
                f"Enrichment service resolution failed: {e}",
                extra={
                    "plan_code": plan_code,
                    "customer_name": customer_name,
                },
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
