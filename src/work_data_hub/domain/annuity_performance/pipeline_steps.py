"""
Annuity Performance Domain Pipeline Steps.

Story 4.10: Refactored to use Standard Domain Pattern with generic steps.

This module contains only domain-specific TransformStep implementations that
cannot be replaced by generic steps. Simple mapping/replacement operations
now use configuration-driven generic steps from Story 1.12.

Remaining Custom Steps (domain-specific business logic):
- CompanyIdResolutionStep: 5-priority company ID resolution algorithm

Deleted Steps (replaced by generic steps + config):
- PlanCodeCleansingStep → DataFrameValueReplacementStep + PLAN_CODE_CORRECTIONS
- InstitutionCodeMappingStep → DataFrameValueReplacementStep + COMPANY_BRANCH_MAPPING
- PortfolioCodeDefaultStep → Inline logic in pipeline construction
- BusinessTypeCodeMappingStep → DataFrameValueReplacementStep + BUSINESS_TYPE_CODE_MAPPING
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd
import pandera as pa
from pandera.errors import SchemaError as PanderaSchemaError

from work_data_hub.domain.annuity_performance.constants import (
    COLUMN_ALIAS_MAPPING,
    DEFAULT_ALLOWED_GOLD_COLUMNS,
    DEFAULT_COMPANY_ID,
    LEGACY_COLUMNS_TO_DELETE,
)
from work_data_hub.domain.annuity_performance.schemas import (
    BronzeAnnuitySchema,
    GoldAnnuitySchema,
    bronze_summary_to_dict,
    gold_summary_to_dict,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.pipeline_config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline, TransformStep
from work_data_hub.domain.pipelines.exceptions import PipelineStepError

# Import shared steps from domain/pipelines/steps/ (Story 4.7 + Story 1.12)
from work_data_hub.domain.pipelines.steps import (
    ColumnNormalizationStep,
    CustomerNameCleansingStep,
    DataFrameValueReplacementStep,
    DateParsingStep,
    FieldCleanupStep,
    clean_company_name,
    parse_to_standard_date,
)
from work_data_hub.domain.pipelines.types import (
    DataFrameStep,
    PipelineContext,
    Row,
    StepResult,
)

logger = logging.getLogger(__name__)

# Re-export shared functions for backward compatibility
__all__ = [
    # Shared steps (from domain/pipelines/steps/)
    "ColumnNormalizationStep",
    "DateParsingStep",
    "CustomerNameCleansingStep",
    "FieldCleanupStep",
    "parse_to_standard_date",
    "clean_company_name",
    # Domain-specific steps (Story 4.10: only CompanyIdResolutionStep remains)
    "CompanyIdResolutionStep",
    # Pipeline factory
    "build_annuity_pipeline",
    "load_mappings_from_json_fixture",
    # Validation steps
    "BronzeSchemaValidationStep",
    "GoldProjectionStep",
    "GoldSchemaValidationStep",
]


# =============================================================================
# Domain-Specific Pipeline Step (Complex Business Logic)
# =============================================================================


class CompanyIdResolutionStep(TransformStep):
    """
    5-priority company_id resolution matching legacy algorithm.

    This step CANNOT be replaced by generic steps because it implements
    complex multi-step business logic with priority-based fallback.

    Resolution Priority:
    1. Plan code mapping (COMPANY_ID1_MAPPING)
    2. Account number mapping (COMPANY_ID2_MAPPING)
    3. Hardcoded mapping (COMPANY_ID3_MAPPING) with default fallback
    4. Customer name mapping (COMPANY_ID4_MAPPING)
    5. Account name mapping (COMPANY_ID5_MAPPING)
    """

    def __init__(
        self,
        company_id1_mapping: Optional[Dict[str, str]] = None,
        company_id2_mapping: Optional[Dict[str, str]] = None,
        company_id3_mapping: Optional[Dict[str, str]] = None,
        company_id4_mapping: Optional[Dict[str, str]] = None,
        company_id5_mapping: Optional[Dict[str, str]] = None,
    ):
        """Initialize with all 5 company ID mapping dictionaries."""
        self._company_id1_mapping = company_id1_mapping or {}
        self._company_id2_mapping = company_id2_mapping or {}
        self._company_id3_mapping = company_id3_mapping or {}
        self._company_id4_mapping = company_id4_mapping or {}
        self._company_id5_mapping = company_id5_mapping or {}

    @property
    def name(self) -> str:
        return "company_id_resolution"

    @property
    def company_id1_mapping(self) -> Dict[str, str]:
        return self._company_id1_mapping

    @property
    def company_id2_mapping(self) -> Dict[str, str]:
        return self._company_id2_mapping

    @property
    def company_id3_mapping(self) -> Dict[str, str]:
        return self._company_id3_mapping

    @property
    def company_id4_mapping(self) -> Dict[str, str]:
        return self._company_id4_mapping

    @property
    def company_id5_mapping(self) -> Dict[str, str]:
        return self._company_id5_mapping

    def apply(self, row: Row, context: Dict[str, Any]) -> StepResult:
        """Apply 5-step company ID resolution algorithm."""
        try:
            updated_row = {**row}
            warnings: List[str] = []
            company_id = None
            resolution_method = None

            # Step 1: Plan code mapping (priority 1)
            plan_code = updated_row.get("计划代码")
            if plan_code and plan_code in self._company_id1_mapping:
                company_id = self._company_id1_mapping[plan_code]
                resolution_method = "plan_code"
                warnings.append(f"Resolved company_id via plan code: {plan_code} -> {company_id}")

            # Clean enterprise customer number
            if "集团企业客户号" in updated_row and updated_row["集团企业客户号"]:
                cleaned_number = str(updated_row["集团企业客户号"]).lstrip("C")
                updated_row["集团企业客户号"] = cleaned_number

            # Step 2: Account number mapping (priority 2)
            if not company_id:
                account_number = updated_row.get("集团企业客户号")
                if account_number and account_number in self._company_id2_mapping:
                    company_id = self._company_id2_mapping[account_number]
                    resolution_method = "account_number"
                    warnings.append(f"Resolved company_id via account number: {account_number} -> {company_id}")

            # Step 3: Special case with default fallback (priority 3)
            if not company_id:
                customer_name = updated_row.get("客户名称")
                if not customer_name or customer_name == "":
                    if plan_code and plan_code in self._company_id3_mapping:
                        company_id = self._company_id3_mapping[plan_code]
                        resolution_method = "hardcoded"
                        warnings.append(f"Resolved company_id via hardcoded mapping: {plan_code} -> {company_id}")
                    else:
                        company_id = DEFAULT_COMPANY_ID
                        resolution_method = "default_fallback"
                        warnings.append(f"Applied default company_id {DEFAULT_COMPANY_ID} for empty customer name")

            # Step 4: Customer name mapping (priority 4)
            if not company_id:
                customer_name = updated_row.get("客户名称")
                if customer_name and customer_name in self._company_id4_mapping:
                    company_id = self._company_id4_mapping[customer_name]
                    resolution_method = "customer_name"
                    warnings.append(f"Resolved company_id via customer name: {customer_name} -> {company_id}")

            # Step 5: Account name mapping (priority 5)
            if not company_id:
                account_name = updated_row.get("年金账户名")
                if account_name and account_name in self._company_id5_mapping:
                    company_id = self._company_id5_mapping[account_name]
                    resolution_method = "account_name"
                    warnings.append(f"Resolved company_id via account name: {account_name} -> {company_id}")

            updated_row["company_id"] = company_id

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={
                    "company_id": company_id,
                    "resolution_method": resolution_method,
                    "resolution_priority": {
                        "plan_code": 1, "account_number": 2, "hardcoded": 3,
                        "customer_name": 4, "account_name": 5, "default_fallback": 3,
                    }.get(resolution_method or "", 0),
                },
            )
        except Exception as e:
            return StepResult(row=row, errors=[f"Company ID resolution failed: {e}"])


# =============================================================================
# Pipeline Factory (Story 4.10: Simplified with Generic Steps)
# =============================================================================


def build_annuity_pipeline(mappings: Optional[Dict[str, Any]] = None) -> Pipeline:
    """
    Build the annuity performance pipeline using generic steps + config.

    Story 4.10: Refactored to use DataFrameValueReplacementStep for simple
    value mappings, keeping only CompanyIdResolutionStep as custom step.
    """
    if mappings is None:
        mappings = {}

    def extract_mapping(key: str, fallback: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        if fallback is None:
            fallback = {}
        mapping_entry = mappings.get(key, {})
        if isinstance(mapping_entry, dict) and "data" in mapping_entry:
            return mapping_entry["data"]
        return fallback

    # Extract mappings for CompanyIdResolutionStep
    company_id1_mapping = extract_mapping("company_id1_mapping")
    company_id2_mapping = extract_mapping("company_id2_mapping")
    company_id3_mapping = extract_mapping("company_id3_mapping")
    company_id4_mapping = extract_mapping("company_id4_mapping")
    company_id5_mapping = extract_mapping("company_id5_mapping")

    # Build pipeline with shared + domain-specific steps
    steps = [
        ColumnNormalizationStep(),
        DateParsingStep(),
        CustomerNameCleansingStep(),
        CompanyIdResolutionStep(
            company_id1_mapping=company_id1_mapping,
            company_id2_mapping=company_id2_mapping,
            company_id3_mapping=company_id3_mapping,
            company_id4_mapping=company_id4_mapping,
            company_id5_mapping=company_id5_mapping,
        ),
        FieldCleanupStep(),
    ]

    step_configs = [
        StepConfig(
            name=step.name,
            import_path=f"{step.__class__.__module__}.{step.__class__.__name__}",
        )
        for step in steps
    ]

    config = PipelineConfig(
        name="annuity_performance_standard_pattern",
        steps=step_configs,
        stop_on_error=False,
    )

    pipeline = Pipeline(steps=steps, config=config)
    logger.info(f"Built annuity pipeline with {len(steps)} steps: {[s.name for s in steps]}")
    return pipeline


def load_mappings_from_json_fixture(fixture_path: str) -> Dict[str, Any]:
    """Load mapping dictionaries from JSON fixture file."""
    import json
    from pathlib import Path

    fixture_file = Path(fixture_path)
    if not fixture_file.exists():
        raise FileNotFoundError(f"Mapping fixture not found: {fixture_path}")

    with fixture_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    mappings = data.get("mappings", {})
    logger.info(f"Loaded {len(mappings)} mapping categories from {fixture_path}")
    return mappings


# =============================================================================
# Validation Steps (Unchanged - Required for Schema Validation)
# =============================================================================


class BronzeSchemaValidationStep:
    """Story 2.2: DataFrame-level validation for Bronze schema."""

    def __init__(self, failure_threshold: float = 0.10):
        self.failure_threshold = failure_threshold

    @property
    def name(self) -> str:
        return "bronze_schema_validation"

    @pa.check_io(df1=BronzeAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        return df1

    def execute(self, dataframe: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        try:
            validated_df, summary = validate_bronze_dataframe(dataframe, failure_threshold=self.failure_threshold)
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            context.metadata.setdefault("bronze_schema_validation", bronze_summary_to_dict(summary))
        return validated_df


class GoldProjectionStep(DataFrameStep):
    """Story 4.4: Project Silver output to database columns and run Gold validation."""

    def __init__(
        self,
        allowed_columns_provider: Optional[Callable[[], List[str]]] = None,
        table: str = "annuity_performance_new",
        schema: str = "public",
        legacy_columns_to_remove: Optional[Sequence[str]] = None,
    ) -> None:
        self.table = table
        self.schema = schema
        self._allowed_columns_provider = allowed_columns_provider
        self._allowed_columns: Optional[List[str]] = None
        self.legacy_columns_to_remove = (
            list(legacy_columns_to_remove) if legacy_columns_to_remove is not None
            else list(LEGACY_COLUMNS_TO_DELETE)
        )

    @property
    def name(self) -> str:
        return "gold_projection"

    def execute(self, dataframe: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        working_df = dataframe.copy(deep=True)
        working_df.rename(columns=COLUMN_ALIAS_MAPPING, inplace=True)
        self._ensure_annualized_column(working_df)
        legacy_removed = self._remove_legacy_columns(working_df)

        allowed_columns = self._get_allowed_columns()
        preserved = [col for col in allowed_columns if col in working_df.columns]
        removed = [col for col in working_df.columns if col not in allowed_columns]

        if removed:
            logger.info("gold_projection.removed_columns", extra={"columns": removed, "count": len(removed)})

        if not preserved:
            raise PipelineStepError("Gold projection failed: no columns remain", step_name=self.name)

        projected_df = working_df.loc[:, preserved].copy()
        validated_df, summary = validate_gold_dataframe(projected_df, project_columns=False)

        if hasattr(context, "metadata"):
            context.metadata["gold_projection"] = {
                "removed_columns": removed,
                "legacy_removed_columns": legacy_removed,
                "allowed_columns_count": len(allowed_columns),
            }
            context.metadata["gold_schema_validation"] = gold_summary_to_dict(summary)

        return validated_df

    def _ensure_annualized_column(self, dataframe: pd.DataFrame) -> None:
        if "年化收益率" in dataframe.columns:
            return
        if "当期收益率" in dataframe.columns:
            dataframe["年化收益率"] = dataframe["当期收益率"]
            dataframe.drop(columns=["当期收益率"], inplace=True)

    def _remove_legacy_columns(self, dataframe: pd.DataFrame) -> List[str]:
        existing = [col for col in self.legacy_columns_to_remove if col in dataframe.columns]
        if existing:
            dataframe.drop(columns=existing, inplace=True)
        return existing

    def _get_allowed_columns(self) -> List[str]:
        if self._allowed_columns is not None:
            return self._allowed_columns

        provider = self._allowed_columns_provider or self._default_allowed_columns_provider
        columns = list(provider())

        if not columns:
            raise PipelineStepError("Allowed columns provider returned empty list", step_name=self.name)

        seen = set()
        deduped: List[str] = []
        for column in columns:
            if column not in seen:
                seen.add(column)
                deduped.append(column)

        self._allowed_columns = deduped
        return self._allowed_columns

    @staticmethod
    def _default_allowed_columns_provider() -> List[str]:
        return list(DEFAULT_ALLOWED_GOLD_COLUMNS)


class GoldSchemaValidationStep:
    """Story 2.2: Gold-layer schema validation before database projection."""

    def __init__(self, project_columns: bool = True):
        self.project_columns = project_columns

    @property
    def name(self) -> str:
        return "gold_schema_validation"

    @pa.check_io(df1=GoldAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        return df1

    def execute(self, dataframe: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        try:
            validated_df, summary = validate_gold_dataframe(dataframe, project_columns=self.project_columns)
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            context.metadata.setdefault("gold_schema_validation", gold_summary_to_dict(summary))
        return validated_df
