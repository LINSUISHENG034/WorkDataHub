"""
Pipeline composition for annuity performance domain.

Story 5.7: Refactor AnnuityPerformanceService to Lightweight Orchestrator

This module composes infrastructure/transforms/ steps into domain-specific pipelines.
It serves as the bridge between the domain layer (business orchestration) and the
infrastructure layer (reusable transformation components).

Architecture Reference:
- AD-010: Infrastructure Layer & Pipeline Composition
- Story 5.6: Pipeline Steps in infrastructure/transforms/

Usage:
    >>> from work_data_hub.domain.annuity_performance.pipeline_builder import (
    ...     build_bronze_to_silver_pipeline,
    ...     CompanyIdResolutionStep,
    ... )
    >>> pipeline = build_bronze_to_silver_pipeline(enrichment_service)
    >>> result_df = pipeline.execute(input_df, context)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import structlog

import pandas as pd

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.transforms import (
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    ReplacementStep,
    TransformStep,
)

from .constants import (
    BUSINESS_TYPE_CODE_MAPPING,
    COLUMN_ALIAS_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_INSTITUTION_CODE,
    LEGACY_COLUMNS_TO_DELETE,
    PLAN_CODE_CORRECTIONS,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


# =============================================================================
# Custom Pipeline Step: Company ID Resolution
# =============================================================================


class CompanyIdResolutionStep(TransformStep):
    """
    Pipeline step that wraps CompanyIdResolver for batch company ID resolution.

    This step integrates the infrastructure CompanyIdResolver into the pipeline
    composition pattern, providing vectorized company ID resolution with
    hierarchical strategy support.

    Resolution Priority:
    1. Plan override mapping (from plan_override_mapping)
    2. Existing company_id column passthrough
    3. Enrichment service delegation (optional)
    4. Temporary ID generation (HMAC-SHA1 based)

    Example:
        >>> step = CompanyIdResolutionStep(
        ...     plan_override_mapping={"FP0001": "614810477"}
        ... )
        >>> result_df = step.apply(df, context)
    """

    def __init__(
        self,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        sync_lookup_budget: int = 0,
    ) -> None:
        """
        Initialize the CompanyIdResolutionStep.

        Args:
            enrichment_service: Optional CompanyEnrichmentService for complex resolution.
            plan_override_mapping: Dict mapping plan codes to company IDs.
            sync_lookup_budget: Maximum synchronous API lookups allowed.
        """
        self._resolver = CompanyIdResolver(
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
        )
        self._sync_lookup_budget = sync_lookup_budget
        self._use_enrichment = enrichment_service is not None

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """
        Apply batch company ID resolution to DataFrame.

        Args:
            df: Input DataFrame with plan codes and customer names.
            context: Pipeline execution context.

        Returns:
            DataFrame with resolved company_id column.
        """
        strategy = ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            account_name_column="年金账户名",
            company_id_column="公司代码",
            output_column="company_id",
            use_enrichment_service=self._use_enrichment,
            sync_lookup_budget=self._sync_lookup_budget,
            generate_temp_ids=True,
        )

        result = self._resolver.resolve_batch(df, strategy)

        # Log resolution statistics
        stats = result.statistics
        domain = context.config.get("domain", "annuity_performance") if context.config else "annuity_performance"
        logger.bind(domain=domain, step=self.name).info(
            "Company ID resolution complete",
            **stats.to_dict(),
        )

        return result.data


# =============================================================================
# Pipeline Builder Functions
# =============================================================================


def build_bronze_to_silver_pipeline(
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    sync_lookup_budget: int = 0,
) -> Pipeline:
    """
    Build the Bronze → Silver transformation pipeline for annuity performance.

    This pipeline transforms raw Excel data (Bronze layer) into validated,
    standardized data (Silver layer) ready for further processing or loading.

    Pipeline Steps:
    1. Column renaming (standardization via COLUMN_ALIAS_MAPPING)
    2. Plan code corrections (PLAN_CODE_CORRECTIONS)
    3. Institution code mapping (COMPANY_BRANCH_MAPPING)
    4. Business type to product line mapping (BUSINESS_TYPE_CODE_MAPPING)
    5. Data cleansing (via CleansingRegistry)
    6. Company ID resolution (via CompanyIdResolver)
    7. Drop legacy columns (LEGACY_COLUMNS_TO_DELETE)

    Args:
        enrichment_service: Optional CompanyEnrichmentService for company ID resolution.
        plan_override_mapping: Dict mapping plan codes to company IDs for override.
        sync_lookup_budget: Maximum synchronous API lookups for enrichment.

    Returns:
        Configured Pipeline instance ready for execution.

    Example:
        >>> from datetime import datetime, timezone
        >>> pipeline = build_bronze_to_silver_pipeline(
        ...     enrichment_service=enrichment_svc,
        ...     plan_override_mapping={"FP0001": "614810477"},
        ... )
        >>> context = PipelineContext(
        ...     pipeline_name="bronze_to_silver",
        ...     execution_id="run-123",
        ...     timestamp=datetime.now(timezone.utc),
        ...     config={"domain": "annuity_performance"},
        ... )
        >>> result_df = pipeline.execute(input_df, context)
    """
    steps: list[TransformStep] = [
        # Step 1: Column name standardization
        MappingStep(COLUMN_ALIAS_MAPPING),
        # Step 2: Plan code corrections
        # ReplacementStep expects: {column_name: {old_value: new_value}}
        ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),
        # Step 3: Institution code mapping (机构名称 → 机构代码)
        # Note: ReplacementStep replaces values in-place, not cross-column
        # For cross-column mapping, we use a custom approach
        ReplacementStep({"机构名称": COMPANY_BRANCH_MAPPING}),
        # Step 4: Business type to product line code mapping
        ReplacementStep({"业务类型": BUSINESS_TYPE_CODE_MAPPING}),
        # Step 5: Data cleansing via CleansingRegistry
        CleansingStep(domain="annuity_performance"),
        # Step 6: Company ID resolution
        CompanyIdResolutionStep(
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
            sync_lookup_budget=sync_lookup_budget,
        ),
        # Step 7: Drop legacy columns
        DropStep(list(LEGACY_COLUMNS_TO_DELETE)),
    ]

    pipeline = Pipeline(steps)

    logger.bind(domain="annuity_performance", step="build_pipeline").info(
        "Built bronze_to_silver pipeline",
        step_count=len(steps),
        steps=[s.name for s in steps],
    )

    return pipeline


def load_plan_override_mapping(mapping_path: Optional[str] = None) -> Dict[str, str]:
    """
    Load plan code to company ID override mapping from YAML file.

    Args:
        mapping_path: Path to YAML mapping file. If None, uses default path.

    Returns:
        Dict mapping plan codes to company IDs.

    Example:
        >>> mapping = load_plan_override_mapping()
        >>> mapping.get("FP0001")
        '614810477'
    """
    import yaml
    from pathlib import Path

    if mapping_path is None:
        # Default path for plan override mappings
        mapping_path = "data/mappings/company_id_overrides_plan.yml"

    path = Path(mapping_path)
    if not path.exists():
        logger.bind(domain="annuity_performance", step="load_plan_override").debug(
            "Plan override mapping file not found", path=mapping_path
        )
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        mapping = data.get("plan_overrides", {})
        logger.bind(domain="annuity_performance", step="load_plan_override").info(
            "Loaded plan override mappings", count=len(mapping), path=mapping_path
        )
        return mapping

    except Exception as e:
        logger.bind(domain="annuity_performance", step="load_plan_override").warning(
            "Failed to load plan override mapping", error=str(e)
        )
        return {}


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Pipeline builders
    "build_bronze_to_silver_pipeline",
    "load_plan_override_mapping",
    # Custom steps
    "CompanyIdResolutionStep",
]
