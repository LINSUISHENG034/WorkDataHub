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
    COLUMN_MAPPING,
    COMPANY_BRANCH_MAPPING,
    LEGACY_COLUMNS_TO_DELETE,
    # Story 7.4-6: PLAN_CODE_CORRECTIONS now imported from infrastructure.mappings
    # via infrastructure.transforms for consistency
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


# Story 7.4-6: Local functions _apply_plan_code_defaults, _apply_portfolio_code_defaults,
# and _clean_portfolio_code removed - now using shared helpers from infrastructure.transforms


class CompanyIdResolutionStep(TransformStep):
    """Batch company ID resolution using CompanyIdResolver."""

    def __init__(
        self,
        eqc_config: EqcLookupConfig,  # Story 6.2-P17: Required parameter
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        mapping_repository=None,
    ) -> None:
        """Initialize CompanyIdResolutionStep.

        Story 6.2-P17: Breaking Change - eqc_config is now REQUIRED parameter.

        Args:
            eqc_config: EqcLookupConfig controlling EQC lookup behavior
            enrichment_service: Optional legacy enrichment service
            plan_override_mapping: Optional plan code overrides
            mapping_repository: Optional database cache repository
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
            eqc_config=eqc_config,  # Story 6.2-P17: Pass explicit config
            enrichment_service=enrichment_service,
            yaml_overrides=yaml_overrides,
            mapping_repository=mapping_repository,
        )

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        if "客户名称" not in df.columns:
            df = df.copy()
            df["客户名称"] = pd.NA

        # Story 6.2-P17: ResolutionStrategy no longer needs enrichment flags
        # (CompanyIdResolver uses eqc_config directly)
        strategy = ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            account_name_column="年金账户名",
            account_number_column="集团企业客户号",  # Use 集团企业客户号 for account_number lookup
            company_id_column="公司代码",
            output_column="company_id",
            use_enrichment_service=True,  # Legacy flag (ignored by resolver)
            sync_lookup_budget=0,  # Legacy flag (ignored by resolver)
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
    eqc_config: EqcLookupConfig,  # Story 6.2-P17: Required parameter
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,
) -> Pipeline:
    """Compose the Bronze → Silver pipeline using shared infrastructure steps.

    Story 6.2-P17: Breaking Change - eqc_config is now REQUIRED parameter.
    """
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
        # Story 7.4-6: Now using shared helper from infrastructure.transforms
        CalculationStep(
            {
                "计划代码": lambda df: apply_plan_code_defaults(df),
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
        # Story 7.4-6: Now using shared helper from infrastructure.transforms
        CalculationStep(
            {
                "组合代码": lambda df: apply_portfolio_code_defaults(df),
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
                "年金账户号": lambda df: df.get(
                    "集团企业客户号", pd.Series([None] * len(df))
                ).copy(),
            }
        ),
        # Step 11: Data cleansing via CleansingRegistry
        CleansingStep(domain="annuity_performance"),
        # Step 12: Company ID resolution (Story 6.2-P17: Pass eqc_config)
        CompanyIdResolutionStep(
            eqc_config=eqc_config,
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping,
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

        # Support both flat format (key: value) and nested format (plan_overrides: {key: value})
        # Flat format is used by company_id_overrides_plan.yml (actual production YAML file)
        if isinstance(data, dict) and "plan_overrides" in data:
            mapping = data.get("plan_overrides", {})
        else:
            # Flat format: data is already the mapping dict
            mapping = data if isinstance(data, dict) else {}
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
