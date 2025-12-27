from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    EqcLookupConfig,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    TransformStep,
)
from work_data_hub.utils.date_parser import parse_chinese_date

from .constants import (
    BUSINESS_TYPE_CODE_MAPPING,
    COLUMN_ALIAS_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_INSTITUTION_CODE,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    LEGACY_COLUMNS_TO_DELETE,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Fallback customer name to 计划名称, then UNKNOWN."""
    if "客户名称" in df.columns:
        base = df["客户名称"]
    else:
        base = pd.Series([pd.NA] * len(df), index=df.index)

    plan_names = df.get("计划名称", pd.Series([pd.NA] * len(df), index=df.index))
    base = base.combine_first(plan_names)

    return base.fillna("UNKNOWN")


def _apply_portfolio_code_defaults(df: pd.DataFrame) -> pd.Series:
    """
    Apply default portfolio codes based on business type and plan type.

    AnnuityIncome-specific logic:
    1. Remove '^F' prefix from existing codes
    2. If empty: 职年受托/职年投资 → 'QTAN003'
    3. Else: DEFAULT_PORTFOLIO_CODE_MAPPING.get(计划类型)
    """
    if "组合代码" not in df.columns:
        result = pd.Series([None] * len(df), index=df.index)
    else:
        result = df["组合代码"].astype("string")
        # Step 1: Remove 'F' prefix (case-insensitive regex '^F')
        result = result.str.replace("^f", "", regex=True, flags=re.IGNORECASE)
        # Normalize empty placeholders to None
        result = result.replace({"nan": None, "None": None, "": None, pd.NA: None})
        # Standardize to uppercase strings for downstream comparisons
        result = result.str.upper()

    if "业务类型" in df.columns and "计划类型" in df.columns:
        empty_mask = result.isna()

        # QTAN003 for 职年受托/职年投资
        qtan003_mask = empty_mask & df["业务类型"].isin(
            PORTFOLIO_QTAN003_BUSINESS_TYPES
        )
        result = result.mask(qtan003_mask, "QTAN003")

        # Default based on plan type for remaining empty values (including 职业年金)
        still_empty = result.isna()
        for plan_type, default_code in DEFAULT_PORTFOLIO_CODE_MAPPING.items():
            type_mask = still_empty & (df["计划类型"] == plan_type)
            result = result.mask(type_mask, default_code)

    return result


class CompanyIdResolutionStep(TransformStep):
    """Batch company ID resolution using CompanyIdResolver."""

    def __init__(
        self,
        eqc_config: EqcLookupConfig = None,  # Story 6.2-P17: Accept EqcLookupConfig
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        generate_temp_ids: bool = True,
        sync_lookup_budget: int = 0,
    ) -> None:
        """Initialize CompanyIdResolutionStep.

        Story 6.2-P17: eqc_config parameter (defaults to disabled for backward compat).
        """
        # Default to disabled if not provided
        if eqc_config is None:
            eqc_config = EqcLookupConfig.disabled()

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
            eqc_config=eqc_config,  # Story 6.2-P17
            enrichment_service=enrichment_service,
            yaml_overrides=yaml_overrides,
        )
        self._generate_temp_ids = generate_temp_ids
        self._sync_lookup_budget = max(sync_lookup_budget, 0)

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        # AnnuityIncome uses 计划代码 (same as AnnuityPerformance)
        strategy = ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            account_name_column="年金账户名",
            company_id_column=None,  # AnnuityIncome doesn't have 公司代码
            output_column="company_id",
            # Story 6.2-P17: Resolver behavior is driven by EqcLookupConfig (SSOT);
            # these legacy flags are ignored by CompanyIdResolver.
            use_enrichment_service=True,
            sync_lookup_budget=self._sync_lookup_budget,
            generate_temp_ids=self._generate_temp_ids,
        )

        result = self._resolver.resolve_batch(df, strategy)

        # Log resolution statistics
        stats = result.statistics
        cfg = context.config or {}
        domain = getattr(context, "domain", None) or cfg.get("domain", "annuity_income")
        logger.bind(domain=domain, step=self.name).info(
            "Company ID resolution complete",
            **stats.to_dict(),
        )

        return result.data


def build_bronze_to_silver_pipeline(
    eqc_config: EqcLookupConfig = None,  # Story 6.2-P17: Accept EqcLookupConfig
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
) -> Pipeline:
    """
    Compose the Bronze → Silver pipeline for AnnuityIncome domain.

    Pipeline steps (per Story 5.5.2 Task 6):
    1. MappingStep: Column rename (机构 → 机构代码, 计划号 → 计划代码)
    2. CalculationStep: Plan code normalization (计划代码 → uppercase)
    3. CalculationStep: 机构代码 from 机构名称 via COMPANY_BRANCH_MAPPING
    4. CalculationStep: Date parsing for 月度 (parse_chinese_date)
    5. CalculationStep: 机构代码 default to 'G00' (replace 'null' string + fillna)
    6. CalculationStep: Customer/income defaults (客户名称 fallback to 计划名称,
       income nulls → 0)
    7. CalculationStep: 组合代码 regex replace '^F' → '' + conditional default
    8. CalculationStep: 产品线代码 from 业务类型 via BUSINESS_TYPE_CODE_MAPPING
    9. CalculationStep: Preserve 年金账户名 = 客户名称 (BEFORE normalization)
    10. CleansingStep: Normalizes 客户名称
    11. CompanyIdResolutionStep: Standard ID resolution (NO ID5 fallback)
    12. DropStep: Remove legacy columns
    """
    steps: list[TransformStep] = [
        # Step 1: Column name standardization (机构 → 机构代码)
        MappingStep(COLUMN_ALIAS_MAPPING),
        # Step 2: Plan code normalization (ensure 计划代码 is upper-cased)
        CalculationStep(
            {
                "计划代码": lambda df: (
                    df.get("计划代码", pd.Series([pd.NA] * len(df), index=df.index))
                )
                .astype("string")
                .str.upper(),
            }
        ),
        # Step 3: Institution code mapping (机构名称 → 机构代码)
        CalculationStep(
            {
                "机构代码": lambda df: df["机构名称"].map(COMPANY_BRANCH_MAPPING)
                if "机构名称" in df.columns
                else df.get("机构代码"),
            }
        ),
        # Step 4: Date parsing (月度: Chinese format → datetime)
        CalculationStep(
            {
                "月度": lambda df: df["月度"].apply(parse_chinese_date)
                if "月度" in df.columns
                else df["月度"],
            }
        ),
        # Step 5: Institution code default (replace 'null' string + fillna with 'G00')
        CalculationStep(
            {
                "机构代码": lambda df: df["机构代码"]
                .replace("null", None)
                .fillna(DEFAULT_INSTITUTION_CODE)
                if "机构代码" in df.columns
                else pd.Series([DEFAULT_INSTITUTION_CODE] * len(df)),
            }
        ),
        # Step 6: Customer/income defaults (fallback names + zero missing income)
        CalculationStep(
            {
                "客户名称": _fill_customer_name,
                "固费": lambda df: df["固费"].fillna(0)
                if "固费" in df.columns
                else pd.Series([0] * len(df)),
                "浮费": lambda df: df["浮费"].fillna(0)
                if "浮费" in df.columns
                else pd.Series([0] * len(df)),
                "回补": lambda df: df["回补"].fillna(0)
                if "回补" in df.columns
                else pd.Series([0] * len(df)),
                "税": lambda df: df["税"].fillna(0)
                if "税" in df.columns
                else pd.Series([0] * len(df)),
            }
        ),
        # Step 7: Portfolio code processing (regex '^F' removal + conditional defaults)
        CalculationStep(
            {
                "组合代码": lambda df: _apply_portfolio_code_defaults(df),
            }
        ),
        # Step 8: Product line code derivation (业务类型 → 产品线代码)
        CalculationStep(
            {
                "产品线代码": lambda df: df["业务类型"].map(BUSINESS_TYPE_CODE_MAPPING)
                if "业务类型" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 9: Preserve original customer name BEFORE cleansing
        # (年金账户名 = 客户名称)
        CalculationStep(
            {
                "年金账户名": lambda df: df["客户名称"].copy()
                if "客户名称" in df.columns
                else pd.Series([None] * len(df)),
            }
        ),
        # Step 10: Data cleansing via CleansingRegistry (normalizes 客户名称)
        CleansingStep(domain="annuity_income"),
        # Step 11: Company ID resolution (Story 6.2-P17: Pass eqc_config)
        CompanyIdResolutionStep(
            eqc_config=eqc_config,
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
            generate_temp_ids=generate_temp_ids,
            sync_lookup_budget=sync_lookup_budget,
        ),
        # Step 12: Drop legacy columns
        DropStep(list(LEGACY_COLUMNS_TO_DELETE)),
    ]

    pipeline = Pipeline(steps)

    logger.bind(domain="annuity_income", step="build_pipeline").info(
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
        logger.bind(domain="annuity_income", step="load_plan_override").debug(
            "Plan override mapping file not found", path=mapping_path
        )
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        mapping = data.get("plan_overrides", {})
        if not isinstance(mapping, dict):
            logger.bind(domain="annuity_income", step="load_plan_override").warning(
                "Plan override mapping is not a dict", path=mapping_path
            )
            return {}

        logger.bind(domain="annuity_income", step="load_plan_override").info(
            "Loaded plan override mappings", count=len(mapping), path=mapping_path
        )
        return {str(k): str(v) for k, v in mapping.items()}

    except Exception as e:
        logger.bind(domain="annuity_income", step="load_plan_override").warning(
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
