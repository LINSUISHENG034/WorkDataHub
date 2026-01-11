"""Annual Award (当年中标) domain - Pipeline Builder.

Composes the Bronze → Silver transformation pipeline for annual award data.
Implements fixes for:
1. Multi-sheet support (企年受托中标 + 企年投资中标) - handled by op
2. Business type mapping (受托→企年受托, 投资/投管→企年投资)
3. Plan type mapping (集合→集合计划, 单一→单一计划)
4. Preserve 机构名称 field
5. Correct 机构代码 and company_id mapping (uses CompanyIdResolutionStep)
"""

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
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    TransformStep,  # Story 7.4-6: Shared helper for plan code defaults
)
from work_data_hub.utils.date_parser import parse_chinese_date

from .constants import (
    BUSINESS_TYPE_CODE_MAPPING,
    BUSINESS_TYPE_NORMALIZATION,
    COLUMN_MAPPING,
    COLUMNS_TO_DROP,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_INSTITUTION_CODE,
    PLAN_TYPE_MAPPING,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


def _clean_customer_name_column(df: pd.DataFrame) -> pd.Series:
    """Clean customer name using customer_name_normalize module.

    Implements requirement #3: Generate cleaned 客户名称 from 上报客户名称.
    """
    from work_data_hub.infrastructure.cleansing import normalize_customer_name

    if "上报客户名称" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    return df["上报客户名称"].apply(
        lambda x: normalize_customer_name(x) if isinstance(x, str) and x else None
    )


def _apply_business_type_normalization(df: pd.DataFrame) -> pd.Series:
    """Normalize 业务类型 to canonical product line names.

    Mapping: 受托→企年受托, 投资→企年投资, 投管→企年投资
    """
    if "业务类型" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    return df["业务类型"].map(BUSINESS_TYPE_NORMALIZATION).fillna(df["业务类型"])


def _apply_product_line_code_mapping(df: pd.DataFrame) -> pd.Series:
    """Derive 产品线代码 from normalized 业务类型.

    Uses shared BUSINESS_TYPE_CODE_MAPPING (企年受托→PL202, 企年投资→PL201)
    """
    if "业务类型" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    return df["业务类型"].map(BUSINESS_TYPE_CODE_MAPPING)


def _apply_plan_type_mapping(df: pd.DataFrame) -> pd.Series:
    """Map 计划类型 to canonical names.

    Mapping: 集合→集合计划, 单一→单一计划
    """
    if "计划类型" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    return df["计划类型"].map(PLAN_TYPE_MAPPING).fillna(df["计划类型"])


def _apply_branch_code_mapping(df: pd.DataFrame) -> pd.Series:
    """Map 机构名称 to 机构代码.

    Uses COMPANY_BRANCH_MAPPING from infrastructure.
    """
    if "机构名称" not in df.columns:
        if "机构代码" in df.columns:
            return df["机构代码"]
        return pd.Series([DEFAULT_INSTITUTION_CODE] * len(df), index=df.index)

    return df["机构名称"].map(COMPANY_BRANCH_MAPPING).fillna(DEFAULT_INSTITUTION_CODE)


def _apply_plan_code_defaults_for_annual_award(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes for annual_award domain.

    Adapts the shared apply_plan_code_defaults logic for annual_award's '年金计划号' column.
    Uses PLAN_CODE_DEFAULTS: 集合计划→AN001, 单一计划→AN002

    Only fills empty values - preserves existing 年金计划号 from source data or enrichment.
    """
    from work_data_hub.infrastructure.mappings import PLAN_CODE_DEFAULTS

    if "年金计划号" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["年金计划号"].copy()

    if "计划类型" in df.columns:
        # Only fill empty values (preserves existing data)
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, PLAN_CODE_DEFAULTS["集合计划"])
        result = result.mask(single_mask, PLAN_CODE_DEFAULTS["单一计划"])

    return result


class CompanyIdResolutionStep(TransformStep):
    """Batch company ID resolution using CompanyIdResolver.

    This step resolves company_id from 客户名称 using:
    1. Database cache lookup
    2. YAML overrides
    3. Temp ID generation (if no match found)
    """

    def __init__(
        self,
        eqc_config: EqcLookupConfig,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,
        mapping_repository=None,
    ) -> None:
        """Initialize CompanyIdResolutionStep."""
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
            mapping_repository=mapping_repository,
        )

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        if "客户名称" not in df.columns:
            df = df.copy()
            df["客户名称"] = pd.NA

        # Resolution strategy follows annuity_performance pattern:
        # Priority: YAML overrides → DB cache (enrichment_index) → existing company_id → temp ID
        strategy = ResolutionStrategy(
            plan_code_column="年金计划号",  # Uses 年金计划号 for YAML plan override lookup
            customer_name_column="客户名称",
            account_name_column=None,  # No account name in annual award
            account_number_column=None,  # No account number in annual award
            company_id_column="company_id",  # Use existing company_id from source data
            output_column="company_id",
            use_enrichment_service=True,
            sync_lookup_budget=0,
            generate_temp_ids=True,
        )

        result = self._resolver.resolve_batch(df, strategy)

        # Log resolution statistics
        stats = result.statistics
        cfg = context.config or {}
        domain = getattr(context, "domain", None) or cfg.get("domain", "annual_award")
        logger.bind(domain=domain, step=self.name).info(
            "Company ID resolution complete",
            **stats.to_dict(),
        )

        return result.data


class PlanCodeEnrichmentStep(TransformStep):
    """Enrich 年金计划号 from customer_plan_contract table.

    This step fills empty 年金计划号 values by looking up the customer_plan_contract
    table using company_id + 产品线代码 as join keys.

    Plan Code Selection Priority (based on 计划类型):
    -----------------------------------------------
    - 集合计划: Prefer plan codes starting with "P" (e.g., P0001, P0002)
      Rationale: "P" prefix typically indicates pooled/collective plans (集合计划)
    - 单一计划: Prefer plan codes starting with "S" (e.g., S0001, S0002)
      Rationale: "S" prefix typically indicates single/individual plans (单一计划)
    - If no matching prefix found, use any available plan code for the company

    Only updates rows where 年金计划号 is empty (preserves existing values per requirement #2).
    """

    def __init__(self, db_connection=None) -> None:
        """Initialize PlanCodeEnrichmentStep.

        Args:
            db_connection: SQLAlchemy connection for database queries.
                If None, this step will be skipped.
        """
        self._connection = db_connection

    @property
    def name(self) -> str:
        return "plan_code_enrichment"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Apply plan code enrichment from customer_plan_contract table."""
        if self._connection is None:
            logger.bind(domain="annual_award", step=self.name).warning(
                "No database connection provided, skipping plan code enrichment"
            )
            return df

        df = df.copy()

        # Only process rows where 年金计划号 is empty
        mask_empty_plan = df["年金计划号"].isna() | (df["年金计划号"] == "")
        if not mask_empty_plan.any():
            logger.bind(domain="annual_award", step=self.name).info(
                "No empty 年金计划号 values to enrich"
            )
            return df

        # Get unique company_id + 产品线代码 combinations that need enrichment
        rows_to_enrich = df[mask_empty_plan][
            ["company_id", "产品线代码", "计划类型"]
        ].drop_duplicates()

        if rows_to_enrich.empty:
            return df

        # Query customer_plan_contract table
        try:
            # Build lookup mapping: (company_id, product_line_code) -> list of plan_codes
            plan_code_mapping = self._build_plan_code_mapping(rows_to_enrich)

            # Apply enrichment
            enriched_count = 0
            for idx in df[mask_empty_plan].index:
                company_id = df.at[idx, "company_id"]
                product_line = df.at[idx, "产品线代码"]
                plan_type = df.at[idx, "计划类型"]

                key = (company_id, product_line)
                if key in plan_code_mapping:
                    plan_codes = plan_code_mapping[key]
                    selected_code = self._select_plan_code(plan_codes, plan_type)
                    if selected_code:
                        df.at[idx, "年金计划号"] = selected_code
                        enriched_count += 1

            logger.bind(domain="annual_award", step=self.name).info(
                "Plan code enrichment complete",
                total_empty=mask_empty_plan.sum(),
                enriched=enriched_count,
            )

        except Exception as e:
            logger.bind(domain="annual_award", step=self.name).warning(
                "Plan code enrichment failed", error=str(e)
            )

        return df

    def _build_plan_code_mapping(
        self, rows_to_enrich: pd.DataFrame
    ) -> Dict[tuple, list]:
        """Build mapping from (company_id, product_line_code) to list of plan_codes."""
        from sqlalchemy import text

        # Get unique company_ids for query
        company_ids = rows_to_enrich["company_id"].dropna().unique().tolist()
        if not company_ids:
            return {}

        # Query customer_plan_contract table
        query = text("""
            SELECT company_id, product_line_code, plan_code
            FROM customer.customer_plan_contract
            WHERE company_id = ANY(:company_ids)
            ORDER BY company_id, product_line_code, plan_code
        """)

        result = self._connection.execute(query, {"company_ids": company_ids})

        # Build mapping
        mapping: Dict[tuple, list] = {}
        for row in result:
            key = (row.company_id, row.product_line_code)
            if key not in mapping:
                mapping[key] = []
            mapping[key].append(row.plan_code)

        return mapping

    def _select_plan_code(
        self, plan_codes: list, plan_type: Optional[str]
    ) -> Optional[str]:
        """Select the best plan code based on 计划类型.

        Selection Priority:
        - 集合计划: Prefer "P" prefix (pooled plans)
        - 单一计划: Prefer "S" prefix (single plans)
        - Fallback: Use first available plan code

        Args:
            plan_codes: List of available plan codes
            plan_type: 计划类型 value (集合计划/单一计划)

        Returns:
            Selected plan code or None if no codes available
        """
        if not plan_codes:
            return None

        # Determine preferred prefix based on plan type
        # 集合计划 (collective/pooled plan) -> prefer "P" prefix
        # 单一计划 (single/individual plan) -> prefer "S" prefix
        preferred_prefix = None
        if plan_type == "集合计划":
            preferred_prefix = "P"
        elif plan_type == "单一计划":
            preferred_prefix = "S"

        # Try to find a plan code with preferred prefix
        if preferred_prefix:
            for code in plan_codes:
                if code and code.upper().startswith(preferred_prefix):
                    return code

        # Fallback: return first available plan code
        return plan_codes[0] if plan_codes else None


def build_bronze_to_silver_pipeline(
    eqc_config: Optional[EqcLookupConfig] = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,
    db_connection=None,
) -> Pipeline:
    """Build the Bronze → Silver transformation pipeline for AnnualAward.

    Pipeline steps:
    1. MappingStep: Column renaming
    2. CalculationStep: Apply business type normalization
    3. CalculationStep: Derive product line code
    4. CalculationStep: Apply plan type mapping
    5. CalculationStep: Parse 上报月份 date
    6. CalculationStep: Parse 中标日期 date
    7. CalculationStep: Apply branch code mapping
    8. CalculationStep: Generate cleaned 客户名称
    9. CleansingStep: Apply domain cleansing rules
    10. CompanyIdResolutionStep: Resolve company_id (if eqc_config provided)
    11. PlanCodeEnrichmentStep: Enrich 年金计划号 from customer_plan_contract
    12. DropStep: Remove excluded columns

    Args:
        eqc_config: EqcLookupConfig for company_id resolution
        enrichment_service: Optional CompanyEnrichmentService
        plan_override_mapping: Optional plan code overrides
        mapping_repository: CompanyMappingRepository for DB cache lookup
        db_connection: SQLAlchemy connection for plan code enrichment
    """
    steps: list[TransformStep] = [
        # Step 1: Column renaming
        MappingStep(COLUMN_MAPPING),
        # Step 2: Business type normalization (受托→企年受托)
        CalculationStep(
            {
                "业务类型": _apply_business_type_normalization,
            }
        ),
        # Step 3: Product line code derivation (业务类型→产品线代码)
        CalculationStep(
            {
                "产品线代码": _apply_product_line_code_mapping,
            }
        ),
        # Step 4: Plan type mapping (集合→集合计划)
        CalculationStep(
            {
                "计划类型": _apply_plan_type_mapping,
            }
        ),
        # Step 5: Date parsing for 上报月份
        CalculationStep(
            {
                "上报月份": lambda df: df["上报月份"].apply(parse_chinese_date)
                if "上报月份" in df.columns
                else df.get("上报月份"),
            }
        ),
        # Step 6: Date parsing for 中标日期
        CalculationStep(
            {
                "中标日期": lambda df: df["中标日期"].apply(
                    lambda x: parse_chinese_date(x) if x and str(x).strip() else None
                )
                if "中标日期" in df.columns
                else pd.Series([None] * len(df), index=df.index),
            }
        ),
        # Step 7: Institution code mapping
        CalculationStep(
            {
                "机构代码": _apply_branch_code_mapping,
            }
        ),
        # Step 8: Generate cleaned customer name
        CalculationStep(
            {
                "客户名称": _clean_customer_name_column,
            }
        ),
        # Step 9: Apply domain cleansing rules
        CleansingStep(domain="annual_award"),
    ]

    # Step 10: Company ID resolution (optional, requires eqc_config)
    if eqc_config:
        steps.append(
            CompanyIdResolutionStep(
                eqc_config=eqc_config,
                enrichment_service=enrichment_service,
                plan_override_mapping=plan_override_mapping,
                mapping_repository=mapping_repository,
            )
        )

    # Step 11: Plan code enrichment from customer_plan_contract
    # Must run AFTER company_id resolution (needs resolved company_id for lookup)
    if db_connection:
        steps.append(PlanCodeEnrichmentStep(db_connection=db_connection))

    # Step 12: Apply plan code defaults for remaining empty values
    # Uses PLAN_CODE_DEFAULTS: 集合计划→AN001, 单一计划→AN002
    # Must run AFTER PlanCodeEnrichmentStep (fallback for unmatched records)
    # Note: apply_plan_code_defaults expects '计划代码' column, so we adapt for '年金计划号'
    steps.append(
        CalculationStep(
            {
                "年金计划号": _apply_plan_code_defaults_for_annual_award,
            }
        )
    )

    # Step 13: Drop excluded columns
    steps.append(DropStep(list(COLUMNS_TO_DROP)))

    pipeline = Pipeline(steps)

    logger.bind(domain="annual_award", step="build_pipeline").info(
        "Built bronze_to_silver pipeline",
        step_count=len(steps),
        steps=[s.name for s in steps],
        has_company_id_resolution=eqc_config is not None,
    )

    return pipeline


__all__ = [
    "build_bronze_to_silver_pipeline",
    "CompanyIdResolutionStep",
    "PlanCodeEnrichmentStep",
]
