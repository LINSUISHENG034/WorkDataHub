from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    EqcLookupConfig,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.mappings import PLAN_CODE_CORRECTIONS  # Story 7.4-6
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    ReplacementStep,
    TransformStep,
    # Story 7.4-6: Import shared helpers from infrastructure
    apply_plan_code_defaults,
    apply_portfolio_code_defaults,
)
from work_data_hub.utils.date_parser import parse_chinese_date

from .constants import (
    BUSINESS_TYPE_CODE_MAPPING,
    COLUMN_ALIAS_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_INSTITUTION_CODE,
    LEGACY_COLUMNS_TO_DELETE,
    # Story 7.4-6: PLAN_CODE_CORRECTIONS now imported from infrastructure.mappings
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


# Story 7.4-6: Local _apply_plan_code_defaults and _apply_portfolio_code_defaults
# removed - now using shared helpers from infrastructure.transforms


def _fill_customer_name_from_plan_name(df: pd.DataFrame) -> pd.Series:
    """Fill customer name from plan name for single-plan records only.

    Story 7.5-2: For '单一计划' records with empty customer name,
    extract company name from plan name by removing suffix '企业年金计划'.

    Extraction rules:
    - Single plan with matching suffix: "{CompanyName}企业年金计划" → "{CompanyName}"
    - Single plan without matching suffix: Keep NULL (do NOT use plan name as-is)
    - Collective plan: Skip (belongs to multiple customers)

    Args:
        df: DataFrame with columns 客户名称, 计划名称, 计划类型

    Returns:
        pd.Series: Customer names (extracted or original)
    """
    if "客户名称" not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)

    result = df["客户名称"].copy()

    # Check required columns for extraction
    if "计划类型" not in df.columns or "计划名称" not in df.columns:
        return result  # Keep as-is if missing columns

    # Build mask: single-plan + empty customer name + valid plan name
    # Note: "0" is a known empty placeholder in source data
    empty_mask = result.isna() | (result == "") | (result == "0")
    single_plan_mask = df["计划类型"] == "单一计划"
    has_plan_name = df["计划名称"].notna() & (df["计划名称"] != "")
    target_mask = empty_mask & single_plan_mask & has_plan_name

    # Extract company name from plan name (only if suffix matches)
    suffix = "企业年金计划"

    def extract_company_name(plan_name: str) -> object:
        """Extract company name if plan name matches pattern, else return NA."""
        if not isinstance(plan_name, str):
            return pd.NA
        if plan_name.endswith(suffix):
            extracted = plan_name[: -len(suffix)].strip()
            # Guard: suffix-only plan name (e.g., "企业年金计划") returns NA
            return extracted if extracted else pd.NA
        # No suffix match: return NA (do NOT use plan name as customer name)
        return pd.NA

    extracted = df.loc[target_mask, "计划名称"].apply(extract_company_name)
    result.loc[target_mask] = extracted

    # Structured logging for operational visibility
    extracted_count = extracted.notna().sum()
    skipped_no_match = extracted.isna().sum()
    collective_count = ((df["计划类型"] == "集合计划") & empty_mask).sum()

    logger.bind(domain="annuity_income", step="fill_customer_name").info(
        "Plan name extraction complete",
        extracted=extracted_count,
        skipped_no_match=skipped_no_match,
        skipped_collective=collective_count,
    )

    return result


class CompanyIdResolutionStep(TransformStep):
    """Batch company ID resolution using CompanyIdResolver."""

    def __init__(
        self,
        eqc_config: EqcLookupConfig,  # Story 7.3-6: Make REQUIRED (not optional)
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        mapping_repository=None,  # Story 7.3-6: Add mapping_repository parameter
        generate_temp_ids: bool = True,
        sync_lookup_budget: int = 0,
    ) -> None:
        """Initialize CompanyIdResolutionStep.

        Story 7.3-6: eqc_config is REQUIRED, mapping_repository added.
        """
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
            eqc_config=eqc_config,
            enrichment_service=enrichment_service,
            yaml_overrides=yaml_overrides,
            mapping_repository=mapping_repository,  # Story 7.3-6
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
    eqc_config: EqcLookupConfig,  # Story 7.3-6: Make REQUIRED (not optional)
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,  # Story 7.3-6: Add mapping_repository parameter
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
    6. CalculationStep: Customer/income defaults (客户名称 from 计划名称,
       income nulls → 0) - Story 7.5-2
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
        # Step 2.5: Story 7.3-6 - Apply plan code corrections (typo fixes)
        ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),
        # Step 2.6: Story 7.4-6 - Apply plan code defaults (using shared helper)
        CalculationStep({"计划代码": apply_plan_code_defaults}),
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
        # Step 6: Customer/income defaults (extract names + zero missing income)
        CalculationStep(
            {
                "客户名称": _fill_customer_name_from_plan_name,
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
        # Story 7.4-6: Now using shared helper from infrastructure.transforms
        CalculationStep(
            {
                "组合代码": lambda df: apply_portfolio_code_defaults(df),
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
        # Step 11: Company ID resolution (Story 7.3-6)
        CompanyIdResolutionStep(
            eqc_config=eqc_config,
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
            mapping_repository=mapping_repository,  # Story 7.3-6
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
    """Load plan code → company ID overrides from YAML.

    Story 7.x: Refactored to use unified settings loader, eliminating hardcoded paths.
    """
    from pathlib import Path

    import yaml

    if mapping_path is None:
        # Use unified settings loader (no hardcoded path)
        from work_data_hub.infrastructure.settings import load_company_id_overrides_plan

        try:
            return load_company_id_overrides_plan()
        except Exception as e:
            logger.bind(domain="annuity_income", step="load_plan_override").warning(
                "Failed to load plan override mapping via settings loader", error=str(e)
            )
            return {}

    # Custom path provided - load directly
    path = Path(mapping_path)
    if not path.exists():
        logger.bind(domain="annuity_income", step="load_plan_override").debug(
            "Plan override mapping file not found", path=mapping_path
        )
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Support flat (key: value) or nested (plan_overrides: {...}) format
        if isinstance(data, dict) and "plan_overrides" in data:
            mapping = data.get("plan_overrides", {})
        else:
            mapping = data if isinstance(data, dict) else {}
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
