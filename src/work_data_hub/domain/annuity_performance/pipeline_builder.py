from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    ReplacementStep,
    TransformStep,
)
from work_data_hub.utils.date_parser import parse_chinese_date

from .constants import (
    BUSINESS_TYPE_CODE_MAPPING,
    COLUMN_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    LEGACY_COLUMNS_TO_DELETE,
    PLAN_CODE_CORRECTIONS,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


def _apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (legacy parity)."""
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        # Empty/null plan codes get defaults based on plan type
        # Note: Legacy only checks for isna() and empty string, NOT string "None"
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, "AN001")
        result = result.mask(single_mask, "AN002")

    return result


def _apply_portfolio_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default portfolio codes based on business type and plan type.

    Improvements over Legacy:
    1. Preserves numeric portfolio codes (e.g., 12345 stays 12345, not NaN)
    2. Handles mixed data types robustly
    3. Strips whitespace and handles edge cases
    4. Better data type consistency
    """
    if "组合代码" not in df.columns:
        result = pd.Series([None] * len(df), index=df.index)
    else:
        result = df["组合代码"].copy()

        # Improved processing: handle each value type appropriately
        result = result.apply(lambda x: _clean_portfolio_code(x))

    if "业务类型" in df.columns and "计划类型" in df.columns:
        # Check for empty/invalid codes
        empty_mask = result.isna() | (result == "")

        # QTAN003 for 职年受托/职年投资 (highest priority)
        qtan003_mask = empty_mask & df["业务类型"].isin(
            PORTFOLIO_QTAN003_BUSINESS_TYPES
        )
        result = result.mask(qtan003_mask, "QTAN003")

        # Default based on plan type for remaining empty values
        still_empty = result.isna() | (result == "")
        for plan_type, default_code in DEFAULT_PORTFOLIO_CODE_MAPPING.items():
            if plan_type != "职业年金":  # Already handled by QTAN003
                type_mask = still_empty & (df["计划类型"] == plan_type)
                result = result.mask(type_mask, default_code)

    return result


def _clean_portfolio_code(value) -> Optional[str]:
    """Clean and normalize portfolio code value.

    Args:
        value: Raw portfolio code value

    Returns:
        Cleaned portfolio code or None if invalid
    """
    # Handle None values
    if pd.isna(value):
        return None

    # Handle numeric values - preserve them as strings
    if isinstance(value, (int, float)):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)

    # Handle string values
    if isinstance(value, str):
        # Strip whitespace
        cleaned = value.strip()

        # Handle empty string after strip
        if not cleaned:
            return None

        # Remove 'F' or 'f' prefix if present (Legacy behavior, case-insensitive)
        if cleaned.upper().startswith('F'):
            cleaned = cleaned[1:]

        # Return cleaned value
        return cleaned if cleaned else None

    # Return None for any other type
    return None


class CompanyIdResolutionStep(TransformStep):
    """Batch company ID resolution using CompanyIdResolver."""

    def __init__(
        self,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        sync_lookup_budget: int = 0,
        mapping_repository=None,
    ) -> None:
        yaml_overrides = None
        if plan_override_mapping is not None:
            yaml_overrides = {
                "plan": plan_override_mapping,
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            }
        self._resolver = CompanyIdResolver(
            enrichment_service=enrichment_service,
            yaml_overrides=yaml_overrides,
            mapping_repository=mapping_repository,
        )
        self._sync_lookup_budget = sync_lookup_budget
        # Enable EQC lookup if:
        # 1. enrichment_service is provided (legacy), OR
        # 2. sync_lookup_budget > 0 and mapping_repository is available
        #    (CompanyIdResolver auto-creates eqc_provider in this case)
        self._use_enrichment = (
            enrichment_service is not None
            or (sync_lookup_budget > 0 and mapping_repository is not None)
        )

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        if "客户名称" not in df.columns:
            df = df.copy()
            df["客户名称"] = pd.NA

        strategy = ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            account_name_column="年金账户名",
            account_number_column="集团企业客户号",  # Use 集团企业客户号 for account_number lookup
            company_id_column="公司代码",
            output_column="company_id",
            use_enrichment_service=self._use_enrichment,
            sync_lookup_budget=self._sync_lookup_budget,
            generate_temp_ids=True,
        )

        result = self._resolver.resolve_batch(df, strategy)

        # Log resolution statistics
        stats = result.statistics
        cfg = context.config or {}
        domain = getattr(context, "domain", None) or cfg.get(
            "domain", "annuity_performance"
        )
        logger.bind(domain=domain, step=self.name).info(
            "Company ID resolution complete",
            **stats.to_dict(),
        )

        return result.data


def build_bronze_to_silver_pipeline(
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    sync_lookup_budget: int = 0,
    mapping_repository=None,
) -> Pipeline:
    """Compose the Bronze → Silver pipeline using shared infrastructure steps."""
    steps: list[TransformStep] = [
        # Step 1: Column name standardization (using comprehensive COLUMN_MAPPING)
        MappingStep(COLUMN_MAPPING),
        # Step 2: Preserve original customer name before cleansing (年金账户名 = 客户名称)
        CalculationStep(
            {
                "年金账户名": lambda df: df["客户名称"].copy()
                if "客户名称" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 3: Plan code corrections
        ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),
        # Step 4: Plan code defaults (empty → AN001 for 集合计划, AN002 for 单一计划)
        CalculationStep(
            {
                "计划代码": lambda df: _apply_plan_code_defaults(df),
            }
        ),
        # Step 5: Institution code mapping (机构名称 → 机构代码)
        CalculationStep(
            {
                "机构代码": lambda df: df["机构名称"]
                .map(COMPANY_BRANCH_MAPPING)
                .fillna("G00")
                .replace("null", "G00")
                if "机构名称" in df.columns
                else pd.Series(["G00"] * len(df)),
            }
        ),
        # Step 6: Product line code derivation (业务类型 → 产品线代码)
        CalculationStep(
            {
                "产品线代码": lambda df: df["业务类型"].map(BUSINESS_TYPE_CODE_MAPPING)
                if "业务类型" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 7: Date parsing (月度: 202412 → datetime)
        CalculationStep(
            {
                "月度": lambda df: df["月度"].apply(parse_chinese_date)
                if "月度" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 8: Portfolio code defaults (QTAN001/QTAN002/QTAN003)
        CalculationStep(
            {
                "组合代码": lambda df: _apply_portfolio_code_defaults(df),
            }
        ),
        # Step 9: Clean Group Enterprise Customer Number (lstrip "C")
        CalculationStep(
            {
                "集团企业客户号": lambda df: df["集团企业客户号"].str.lstrip("C")
                if "集团企业客户号" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 10: Derive 年金账户号 from cleaned 集团企业客户号 (Story 6.2-P11)
        # CRITICAL: Must copy BEFORE Step 13 (DropStep) deletes 集团企业客户号
        CalculationStep(
            {
                "年金账户号": lambda df: df.get("集团企业客户号", pd.Series([None] * len(df))).copy(),
            }
        ),
        # Step 11: Data cleansing via CleansingRegistry
        CleansingStep(domain="annuity_performance"),
        # Step 12: Company ID resolution
        CompanyIdResolutionStep(
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
            sync_lookup_budget=sync_lookup_budget,
            mapping_repository=mapping_repository,
        ),
        # Step 13: Drop legacy columns
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
    """Load plan code → company ID overrides from YAML."""
    from pathlib import Path

    import yaml

    if mapping_path is None:
        # Default path for plan override mappings
        # Story 6.x: Reorganized to company_id/ subdirectory
        mapping_path = "data/mappings/company_id/company_id_overrides_plan.yml"

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
        if not isinstance(mapping, dict):
            logger.bind(
                domain="annuity_performance", step="load_plan_override"
            ).warning("Plan override mapping is not a dict", path=mapping_path)
            return {}

        logger.bind(domain="annuity_performance", step="load_plan_override").info(
            "Loaded plan override mappings", count=len(mapping), path=mapping_path
        )
        return {str(k): str(v) for k, v in mapping.items()}

    except Exception as e:
        logger.bind(domain="annuity_performance", step="load_plan_override").warning(
            "Failed to load plan override mapping", error=str(e)
        )
        return {}


__all__ = [
    # Pipeline builders
    "build_bronze_to_silver_pipeline",
    "load_plan_override_mapping",
    # Custom steps
    "CompanyIdResolutionStep",
]
