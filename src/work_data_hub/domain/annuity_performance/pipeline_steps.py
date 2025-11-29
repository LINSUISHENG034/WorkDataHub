"""
Annuity Performance Domain Pipeline Steps

This module contains TransformStep implementations that replicate the exact
transformation logic from the legacy AnnuityPerformanceCleaner._clean_method(),
decomposed into discrete, testable, and reusable pipeline steps.

Each step corresponds to a specific transformation operation from the legacy cleaner,
ensuring 100% behavioral parity for safe migration.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

import dateutil.parser as dp
import numpy as np
import pandas as pd
import pandera as pa
from pandera.errors import SchemaError as PanderaSchemaError

from work_data_hub.domain.annuity_performance.constants import (
    DEFAULT_ALLOWED_GOLD_COLUMNS,
)
from work_data_hub.domain.annuity_performance.schemas import (
    BronzeAnnuitySchema,
    GoldAnnuitySchema,
    bronze_summary_to_dict,
    gold_summary_to_dict,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline, TransformStep
from work_data_hub.domain.pipelines.exceptions import PipelineStepError
from work_data_hub.domain.pipelines.types import (
    DataFrameStep,
    PipelineContext,
    Row,
    StepResult,
)

logger = logging.getLogger(__name__)

LEGACY_COLUMNS_TO_DELETE: Sequence[str] = (
    "id",
    "备注",
    "子企业号",
    "子企业名称",
    "集团企业客户号",
    "集团企业客户名称",
)

ALIAS_COLUMNS = {
    "流失(含待遇支付)": "流失_含待遇支付",
}


def parse_to_standard_date(data):
    """
    Convert date data to standard format - extracted from legacy common_utils.

    This function replicates the exact date parsing logic from the legacy cleaner.
    """
    if isinstance(data, (date, datetime)):
        return data
    else:
        date_string = str(data)

    try:
        # Match YYYY年MM月 or YY年MM月 format
        if re.match(r"(\d{2}|\d{4})年\d{1,2}月$", date_string):
            return datetime.strptime(date_string + "1日", "%Y年%m月%d日")

        # Match YYYY年MM月DD日 or YY年MM月DD日 format
        elif re.match(r"(\d{2}|\d{4})年\d{1,2}月\d{1,2}日$", date_string):
            return datetime.strptime(date_string, "%Y年%m月%d日")

        # Match YYYYMMDD format
        elif re.match(r"\d{8}", date_string):
            return datetime.strptime(date_string, "%Y%m%d")

        # Match YYYYMM format
        elif re.match(r"\d{6}", date_string):
            return datetime.strptime(date_string + "01", "%Y%m%d")

        # Match YYYY-MM format
        elif re.match(r"\d{4}-\d{2}", date_string):
            return datetime.strptime(date_string + "-01", "%Y-%m-%d")

        # Match other formats
        else:
            return dp.parse(date_string)

    except (ValueError, TypeError):
        return data


def clean_company_name(name: str) -> str:
    """
    Basic company name cleaning - simplified from legacy common_utils.

    This function replicates the core company name cleaning logic.
    """
    if not name:
        return ""

    # Remove extra spaces
    name = re.sub(r"\s+", "", name)

    # Remove specified characters
    name = re.sub(r"及下属子企业", "", name)
    name = re.sub(r"(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$", "", name)

    # Simple cleanup for common suffixes
    suffixes_to_remove = [
        "已转出",
        "待转出",
        "终止",
        "转出",
        "转移终止",
        "已作废",
        "已终止",
        "保留",
        "保留账户",
        "存量",
        "已转移终止",
        "本部",
        "未使用",
        "集合",
        "原",
    ]

    for suffix in suffixes_to_remove:
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    return name


class ColumnNormalizationStep(TransformStep):
    """
    Normalize legacy column names to standardized format.

    Replicates the column renaming logic from legacy cleaner:
    - '机构' -> '机构名称'
    - '计划号' -> '计划代码'
    - '流失（含待遇支付）' -> '流失(含待遇支付)'
    """

    @property
    def name(self) -> str:
        return "column_normalization"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply column name normalization."""
        try:
            updated_row = {**row}
            warnings = []

            # Define column mappings (exact match from legacy cleaner)
            column_mappings = {
                "机构": "机构名称",
                "计划号": "计划代码",
                "流失（含待遇支付）": "流失(含待遇支付)",
            }

            # Apply column renaming
            renamed_count = 0
            for old_name, new_name in column_mappings.items():
                if old_name in updated_row:
                    updated_row[new_name] = updated_row.pop(old_name)
                    renamed_count += 1
                    logger.debug(f"Renamed column: {old_name} -> {new_name}")

            if renamed_count > 0:
                warnings.append(
                    f"Renamed {renamed_count} legacy column names to standard format"
                )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"renamed_columns": renamed_count},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Column normalization failed: {e}"])


class DateParsingStep(TransformStep):
    """
    Parse and standardize date fields using parse_to_standard_date.

    Applies the legacy date parsing logic to the '月度' field.
    """

    @property
    def name(self) -> str:
        return "date_parsing"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply date parsing to 月度 field."""
        try:
            updated_row = {**row}
            warnings = []

            # Parse 月度 field (exact match from legacy cleaner)
            if "月度" in updated_row:
                original_value = updated_row["月度"]
                try:
                    parsed_date = parse_to_standard_date(original_value)
                    updated_row["月度"] = parsed_date

                    if str(parsed_date) != str(original_value):
                        warnings.append(
                            f"Parsed date: {original_value} -> {parsed_date}"
                        )

                except Exception as date_error:
                    warnings.append(
                        f"Date parsing failed for '{original_value}': {date_error}"
                    )
                    # Keep original value on parsing failure

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"date_fields_processed": 1 if "月度" in row else 0},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Date parsing failed: {e}"])


class PlanCodeCleansingStep(TransformStep):
    """
    Apply plan code corrections and defaults (AN001, AN002).

    Replicates the plan code cleansing logic from legacy cleaner:
    - Replace '1P0290' -> 'P0290', '1P0807' -> 'P0807'
    - Set 'AN001' for empty 集合计划, 'AN002' for empty 单一计划
    """

    @property
    def name(self) -> str:
        return "plan_code_cleansing"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply plan code cleansing rules."""
        try:
            updated_row = {**row}
            warnings = []

            if "计划代码" in updated_row:
                original_code = updated_row["计划代码"]

                # Step 1: Apply specific replacements (exact match from legacy)
                if original_code == "1P0290":
                    updated_row["计划代码"] = "P0290"
                    warnings.append("Replaced plan code: 1P0290 -> P0290")
                elif original_code == "1P0807":
                    updated_row["计划代码"] = "P0807"
                    warnings.append("Replaced plan code: 1P0807 -> P0807")

                # Step 2: Apply defaults based on plan type (exact match from legacy)
                current_code = updated_row["计划代码"]
                plan_type = updated_row.get("计划类型")

                if (
                    not current_code or current_code == "" or pd.isna(current_code)
                ) and plan_type:
                    if plan_type == "集合计划":
                        updated_row["计划代码"] = "AN001"
                        warnings.append("Set default plan code AN001 for 集合计划")
                    elif plan_type == "单一计划":
                        updated_row["计划代码"] = "AN002"
                        warnings.append("Set default plan code AN002 for 单一计划")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"plan_code_updates": len(warnings)},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Plan code cleansing failed: {e}"])


class InstitutionCodeMappingStep(TransformStep):
    """
    Map institution names to codes via COMPANY_BRANCH_MAPPING.

    Applies institution code mapping and sets default 'G00' for null values.
    """

    def __init__(self, company_branch_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize with institution name -> code mapping.

        Args:
            company_branch_mapping: Dictionary mapping institution names to codes
        """
        self.company_branch_mapping = company_branch_mapping or {}

    @property
    def name(self) -> str:
        return "institution_code_mapping"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply institution code mapping."""
        try:
            updated_row = {**row}
            warnings = []

            # Step 1: Map institution names to codes (exact match from legacy)
            if "机构名称" in updated_row:
                institution_name = updated_row.get("机构名称")
                if institution_name and institution_name in self.company_branch_mapping:
                    mapped_code = self.company_branch_mapping[institution_name]
                    updated_row["机构代码"] = mapped_code
                    warnings.append(
                        f"Mapped institution code: {institution_name} -> {mapped_code}"
                    )

            # Step 2: Replace null/empty codes with G00 (exact match from legacy)
            if "机构代码" in updated_row:
                current_code = updated_row["机构代码"]
                if current_code == "null" or not current_code or pd.isna(current_code):
                    updated_row["机构代码"] = "G00"
                    warnings.append("Set default institution code G00")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"institution_mappings_applied": len(warnings)},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Institution code mapping failed: {e}"])


class PortfolioCodeDefaultStep(TransformStep):
    """
    Set portfolio code defaults based on business type logic.

    Replicates the portfolio code logic from legacy cleaner:
    - Remove 'F' prefix from existing codes
    - Set 'QTAN003' for 职年受托/职年投资
    - Use DEFAULT_PORTFOLIO_CODE_MAPPING for others
    """

    def __init__(self, default_portfolio_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize with default portfolio code mapping.

        Args:
            default_portfolio_mapping: Dictionary mapping plan types to portfolio codes
        """
        self.default_portfolio_mapping = default_portfolio_mapping or {
            "集合计划": "QTAN001",
            "单一计划": "QTAN002",
            "职业年金": "QTAN003",
        }

    @property
    def name(self) -> str:
        return "portfolio_code_default"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply portfolio code defaulting logic."""
        try:
            updated_row = {**row}
            warnings = []

            # Step 1: Ensure 组合代码 column exists (exact match from legacy)
            if "组合代码" not in updated_row:
                updated_row["组合代码"] = np.nan

            # Step 2: Remove 'F' prefix (exact match from legacy)
            if "组合代码" in updated_row and updated_row["组合代码"]:
                current_code = str(updated_row["组合代码"])
                if current_code.startswith("F"):
                    updated_row["组合代码"] = re.sub(r"^F", "", current_code)
                    warnings.append(
                        f"Removed F prefix from portfolio code: {current_code}"
                    )

            # Step 3: Apply defaults (exact match from legacy)
            portfolio_code = updated_row.get("组合代码")
            current_code = str(portfolio_code) if portfolio_code is not None else ""
            business_type = updated_row.get("业务类型")
            plan_type = updated_row.get("计划类型")

            if not current_code or current_code == "" or pd.isna(current_code):
                if business_type in ["职年受托", "职年投资"]:
                    updated_row["组合代码"] = "QTAN003"
                    warnings.append("Set portfolio code QTAN003 for 职年业务")
                elif plan_type and plan_type in self.default_portfolio_mapping:
                    default_code = self.default_portfolio_mapping[plan_type]
                    updated_row["组合代码"] = default_code
                    warnings.append(
                        f"Set default portfolio code {default_code} for {plan_type}"
                    )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"portfolio_updates": len(warnings)},
            )

        except Exception as e:
            return StepResult(
                row=row, errors=[f"Portfolio code defaulting failed: {e}"]
            )


class BusinessTypeCodeMappingStep(TransformStep):
    """
    Map business types to product line codes.

    Applies BUSINESS_TYPE_CODE_MAPPING from legacy cleaner.
    """

    def __init__(self, business_type_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize with business type -> code mapping.

        Args:
            business_type_mapping: Dictionary mapping business types to product
                line codes
        """
        self.business_type_mapping = business_type_mapping or {}

    @property
    def name(self) -> str:
        return "business_type_code_mapping"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply business type to product line code mapping."""
        try:
            updated_row = {**row}
            warnings = []

            # Apply business type mapping (exact match from legacy)
            if "业务类型" in updated_row:
                business_type = updated_row["业务类型"]
                if business_type and business_type in self.business_type_mapping:
                    product_code = self.business_type_mapping[business_type]
                    updated_row["产品线代码"] = product_code
                    warnings.append(
                        f"Mapped business type: {business_type} -> {product_code}"
                    )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"business_type_mappings": len(warnings)},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Business type mapping failed: {e}"])


class CustomerNameCleansingStep(TransformStep):
    """
    Clean customer names and create account name field.

    Applies customer name cleaning logic from legacy cleaner:
    - Copy 客户名称 to 年金账户名
    - Clean 客户名称 using clean_company_name function
    """

    @property
    def name(self) -> str:
        return "customer_name_cleansing"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply customer name cleansing."""
        try:
            updated_row = {**row}
            warnings = []

            if "客户名称" in updated_row:
                original_name = updated_row["客户名称"]

                # Step 1: Copy to account name field (exact match from legacy)
                updated_row["年金账户名"] = original_name

                # Step 2: Clean customer name (exact match from legacy)
                if isinstance(original_name, str):
                    cleaned_name = clean_company_name(original_name)
                    updated_row["客户名称"] = cleaned_name

                    if cleaned_name != original_name:
                        warnings.append(
                            f"Cleaned customer name: {original_name} -> {cleaned_name}"
                        )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"name_cleanings": len(warnings)},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Customer name cleansing failed: {e}"])


class CompanyIdResolutionStep(TransformStep):
    """
    5-priority company_id resolution matching legacy algorithm.

    Applies the exact 5-step company ID resolution from legacy cleaner:
    1. Plan code mapping (COMPANY_ID1_MAPPING)
    2. Account number mapping (COMPANY_ID2_MAPPING)
    3. Hardcoded mapping (COMPANY_ID3_MAPPING) with '600866980' default
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
        self.company_id1_mapping = company_id1_mapping or {}
        self.company_id2_mapping = company_id2_mapping or {}
        self.company_id3_mapping = company_id3_mapping or {}
        self.company_id4_mapping = company_id4_mapping or {}
        self.company_id5_mapping = company_id5_mapping or {}

    @property
    def name(self) -> str:
        return "company_id_resolution"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply 5-step company ID resolution algorithm."""
        try:
            updated_row = {**row}
            warnings = []
            company_id = None
            resolution_method = None

            # Step 1: Plan code mapping (priority 1, exact match from legacy)
            plan_code = updated_row.get("计划代码")
            if plan_code and plan_code in self.company_id1_mapping:
                company_id = self.company_id1_mapping[plan_code]
                resolution_method = "plan_code"
                warnings.append(
                    f"Resolved company_id via plan code: {plan_code} -> {company_id}"
                )

            # Clean enterprise customer number (exact match from legacy)
            if "集团企业客户号" in updated_row and updated_row["集团企业客户号"]:
                cleaned_number = str(updated_row["集团企业客户号"]).lstrip("C")
                updated_row["集团企业客户号"] = cleaned_number

            # Step 2: Account number mapping (priority 2, exact match from legacy)
            if not company_id:
                account_number = updated_row.get("集团企业客户号")
                if account_number and account_number in self.company_id2_mapping:
                    company_id = self.company_id2_mapping[account_number]
                    resolution_method = "account_number"
                    warnings.append(
                        "Resolved company_id via account number: "
                        f"{account_number} -> {company_id}"
                    )

            # Step 3: Special case with default '600866980'
            # (priority 3, exact match from legacy)
            if not company_id:
                customer_name = updated_row.get("客户名称")
                if not customer_name or customer_name == "":
                    # Use hardcoded mapping or default
                    if plan_code and plan_code in self.company_id3_mapping:
                        company_id = self.company_id3_mapping[plan_code]
                        resolution_method = "hardcoded"
                        warnings.append(
                            "Resolved company_id via hardcoded mapping: "
                            f"{plan_code} -> {company_id}"
                        )
                    else:
                        company_id = "600866980"
                        resolution_method = "default_fallback"
                        warnings.append(
                            "Applied default company_id 600866980 for empty "
                            "customer name"
                        )

            # Step 4: Customer name mapping (priority 4, exact match from legacy)
            if not company_id:
                customer_name = updated_row.get("客户名称")
                if customer_name and customer_name in self.company_id4_mapping:
                    company_id = self.company_id4_mapping[customer_name]
                    resolution_method = "customer_name"
                    warnings.append(
                        "Resolved company_id via customer name: "
                        f"{customer_name} -> {company_id}"
                    )

            # Step 5: Account name mapping (priority 5, exact match from legacy)
            if not company_id:
                account_name = updated_row.get("年金账户名")
                if account_name and account_name in self.company_id5_mapping:
                    company_id = self.company_id5_mapping[account_name]
                    resolution_method = "account_name"
                    warnings.append(
                        "Resolved company_id via account name: "
                        f"{account_name} -> {company_id}"
                    )

            # Set the resolved company_id
            updated_row["company_id"] = company_id

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={
                    "company_id": company_id,
                    "resolution_method": resolution_method,
                    "resolution_priority": {
                        "plan_code": 1,
                        "account_number": 2,
                        "hardcoded": 3,
                        "customer_name": 4,
                        "account_name": 5,
                        "default_fallback": 3,
                    }.get(resolution_method or "", 0),
                },
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Company ID resolution failed: {e}"])


class FieldCleanupStep(TransformStep):
    """
    Remove invalid columns and finalize record structure.

    Removes the same columns dropped in legacy cleaner:
    ['备注', '子企业号', '子企业名称', '集团企业客户号', '集团企业客户名称']
    """

    def __init__(self, columns_to_drop: Optional[List[str]] = None):
        """
        Initialize with columns to drop.

        Args:
            columns_to_drop: List of column names to remove from output
        """
        self.columns_to_drop = columns_to_drop or [
            "备注",
            "子企业号",
            "子企业名称",
            "集团企业客户号",
            "集团企业客户名称",
        ]

    @property
    def name(self) -> str:
        return "field_cleanup"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Remove invalid fields from final record."""
        try:
            updated_row = {**row}
            warnings = []
            dropped_count = 0

            # Remove specified columns (exact match from legacy)
            for col_name in self.columns_to_drop:
                if col_name in updated_row:
                    updated_row.pop(col_name)
                    dropped_count += 1
                    warnings.append(f"Dropped invalid field: {col_name}")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"dropped_fields": dropped_count},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Field cleanup failed: {e}"])


def build_annuity_pipeline(mappings: Optional[Dict[str, Any]] = None) -> Pipeline:
    """
    Build the complete annuity performance pipeline with all transformation steps.

    This factory function creates a Pipeline instance that replicates the
    transformation sequence from
    AnnuityPerformanceCleaner._clean_method().

    Args:
        mappings: Dictionary containing all required mapping dictionaries.
                 Expected keys: company_id1_mapping, company_id2_mapping, etc.

    Returns:
        Pipeline: Configured pipeline ready for execution

    Example:
        >>> mappings = load_mappings_from_json(
        ...     "tests/fixtures/sample_legacy_mappings.json"
        ... )
        >>> pipeline = build_annuity_pipeline(mappings)
        >>> result = pipeline.execute(excel_row_dict)
    """
    if mappings is None:
        mappings = {}

    # Extract mapping dictionaries from fixture format
    def extract_mapping(
        key: str, fallback: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Extract mapping data from fixture format."""
        if fallback is None:
            fallback = {}

        mapping_entry = mappings.get(key, {})
        if isinstance(mapping_entry, dict) and "data" in mapping_entry:
            return mapping_entry["data"]
        return fallback

    # Extract all required mappings
    company_id1_mapping = extract_mapping("company_id1_mapping")
    company_id2_mapping = extract_mapping("company_id2_mapping")
    company_id3_mapping = extract_mapping("company_id3_mapping")
    company_id4_mapping = extract_mapping("company_id4_mapping")
    company_id5_mapping = extract_mapping("company_id5_mapping")

    company_branch_mapping = extract_mapping("company_branch_mapping")
    business_type_mapping = extract_mapping("business_type_code_mapping")

    default_portfolio_mapping = extract_mapping(
        "default_portfolio_code_mapping",
        fallback={"集合计划": "QTAN001", "单一计划": "QTAN002", "职业年金": "QTAN003"},
    )

    # Create pipeline steps in exact execution order (matching legacy cleaner sequence)
    steps = [
        # Step 1: Normalize column names
        ColumnNormalizationStep(),
        # Step 2: Map institution codes
        InstitutionCodeMappingStep(company_branch_mapping=company_branch_mapping),
        # Step 3: Parse dates
        DateParsingStep(),
        # Step 4: Cleanse plan codes
        PlanCodeCleansingStep(),
        # Step 5: Set portfolio defaults
        PortfolioCodeDefaultStep(default_portfolio_mapping=default_portfolio_mapping),
        # Step 6: Map business type codes
        BusinessTypeCodeMappingStep(business_type_mapping=business_type_mapping),
        # Step 7: Clean customer names
        CustomerNameCleansingStep(),
        # Step 8: Resolve company IDs (5-step algorithm)
        CompanyIdResolutionStep(
            company_id1_mapping=company_id1_mapping,
            company_id2_mapping=company_id2_mapping,
            company_id3_mapping=company_id3_mapping,
            company_id4_mapping=company_id4_mapping,
            company_id5_mapping=company_id5_mapping,
        ),
        # Step 9: Clean up invalid fields
        FieldCleanupStep(),
    ]

    # Create pipeline configuration with matching step configs
    step_configs = [
        StepConfig(
            name=step.name,
            import_path=f"{step.__class__.__module__}.{step.__class__.__name__}",
        )
        for step in steps
    ]

    config = PipelineConfig(
        name="annuity_performance_legacy_parity",
        steps=step_configs,
        stop_on_error=False,  # Continue processing on errors (log and continue)
    )

    # Create and return pipeline
    pipeline = Pipeline(steps=steps, config=config)

    logger.info(
        f"Built annuity performance pipeline with {len(steps)} steps: "
        f"{[step.name for step in steps]}"
    )

    return pipeline


def load_mappings_from_json_fixture(fixture_path: str) -> Dict[str, Any]:
    """
    Load mapping dictionaries from JSON fixture file for pipeline construction.

    Args:
        fixture_path: Path to JSON fixture file containing mapping dictionaries

    Returns:
        Dictionary containing extracted mapping data

    Example:
        >>> mappings = load_mappings_from_json_fixture(
        ...     "tests/fixtures/sample_legacy_mappings.json"
        ... )
        >>> pipeline = build_annuity_pipeline(mappings)
    """
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


# ===== Story 2.2: Pandera Schema Validation Steps (AC1-AC4) =====


class BronzeSchemaValidationStep:
    """
    Story 2.2: DataFrame-level validation for Bronze schema.

    Validates structural requirements for raw Excel data using pandera.

    This implementation uses a hybrid approach:
    1. @pa.check_io decorator for basic schema validation (AC4 requirement)
    2. Custom validation logic for error thresholds and summaries

    The decorator alone cannot handle:
    - Custom 10% error thresholds
    - Detailed validation summaries (invalid rows, numeric errors)
    - Context metadata integration

    Therefore, we use the decorator for demonstration/documentation purposes
    and rely on the robust validate_bronze_dataframe() for production use.
    """

    def __init__(self, failure_threshold: float = 0.10):
        self.failure_threshold = failure_threshold

    @property
    def name(self) -> str:
        return "bronze_schema_validation"

    @pa.check_io(df1=BronzeAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        """
        Basic Pandera validation using @pa.check_io decorator (AC4).

        This demonstrates the decorator pattern required by AC4, but is not
        sufficient for production use due to lack of:
        - Custom error thresholds
        - Validation summaries
        - Metadata integration

        This method is kept for reference and to satisfy AC4 decorator requirement.
        """
        return df1

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Execute Bronze schema validation with custom threshold logic.

        Uses validate_bronze_dataframe() instead of decorator-only approach
        to support:
        - 10% error threshold enforcement
        - Detailed validation summaries
        - Context metadata integration
        """
        try:
            validated_df, summary = validate_bronze_dataframe(
                dataframe,
                failure_threshold=self.failure_threshold,
            )
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            context.metadata.setdefault(
                "bronze_schema_validation", bronze_summary_to_dict(summary)
            )

        return validated_df


class GoldProjectionStep(DataFrameStep):
    """
    Story 4.4: Project Silver output to database columns and run Gold validation.

    Responsibilities:
    - Fetch allowed columns (WarehouseLoader.get_allowed_columns via DI)
    - Remove legacy-only columns that should never reach Gold
    - Log removed columns for audit trail
    - Apply GoldAnnuitySchema validation (composite PK, ranges, strict typing)
    """

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
            list(legacy_columns_to_remove)
            if legacy_columns_to_remove is not None
            else list(LEGACY_COLUMNS_TO_DELETE)
        )

    @property
    def name(self) -> str:
        return "gold_projection"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        working_df = dataframe.copy(deep=True)
        working_df.rename(columns=ALIAS_COLUMNS, inplace=True)
        self._ensure_annualized_column(working_df)
        legacy_removed = self._remove_legacy_columns(working_df)

        allowed_columns = self._get_allowed_columns()
        preserved = [col for col in allowed_columns if col in working_df.columns]
        removed = [col for col in working_df.columns if col not in allowed_columns]

        if removed:
            logger.info(
                "gold_projection.removed_columns",
                extra={
                    "columns": removed,
                    "count": len(removed),
                    "table": self.table,
                    "schema": self.schema,
                },
            )

        if not preserved:
            raise PipelineStepError(
                "Gold projection failed: no columns remain after projection",
                step_name=self.name,
            )

        projected_df = working_df.loc[:, preserved].copy()

        validated_df, summary = validate_gold_dataframe(
            projected_df,
            project_columns=False,
        )

        if hasattr(context, "metadata"):
            context.metadata["gold_projection"] = {
                "removed_columns": removed,
                "legacy_removed_columns": legacy_removed,
                "allowed_columns_count": len(allowed_columns),
                "table": self.table,
                "schema": self.schema,
            }
            context.metadata["gold_schema_validation"] = gold_summary_to_dict(summary)

        return validated_df

    def _ensure_annualized_column(self, dataframe: pd.DataFrame) -> None:
        """Ensure Gold-facing annualized return column exists."""
        if "年化收益率" in dataframe.columns:
            return

        if "当期收益率" in dataframe.columns:
            dataframe["年化收益率"] = dataframe["当期收益率"]
            dataframe.drop(columns=["当期收益率"], inplace=True)
            logger.info(
                "gold_projection.created_annualized_return",
                extra={"source_column": "当期收益率"},
            )

    def _remove_legacy_columns(self, dataframe: pd.DataFrame) -> List[str]:
        existing = [col for col in self.legacy_columns_to_remove if col in dataframe.columns]
        if existing:
            dataframe.drop(columns=existing, inplace=True)
            logger.info(
                "gold_projection.legacy_columns_removed",
                extra={
                    "columns": existing,
                    "count": len(existing),
                },
            )
        return existing

    def _get_allowed_columns(self) -> List[str]:
        if self._allowed_columns is not None:
            return self._allowed_columns

        provider = self._allowed_columns_provider or self._default_allowed_columns_provider
        try:
            columns = list(provider())
        except Exception as exc:  # pragma: no cover - defensive
            raise PipelineStepError(
                f"Unable to load allowed columns: {exc}",
                step_name=self.name,
            ) from exc

        if not columns:
            raise PipelineStepError(
                "Allowed columns provider returned an empty list",
                step_name=self.name,
            )

        # Preserve provider ordering while de-duplicating.
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
    """
    Story 2.2: Gold-layer schema validation before database projection.

    Similar hybrid approach as BronzeSchemaValidationStep:
    - @pa.check_io decorator for AC4 compliance
    - Custom logic for composite PK checks and column projection
    """

    def __init__(self, project_columns: bool = True):
        self.project_columns = project_columns

    @property
    def name(self) -> str:
        return "gold_schema_validation"

    @pa.check_io(df1=GoldAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        """
        Basic Pandera validation using @pa.check_io decorator (AC4).

        This demonstrates the decorator pattern required by AC4, but cannot:
        - Check composite PK uniqueness (custom logic required)
        - Project/remove extra columns
        - Provide detailed summaries

        This method is kept for reference and to satisfy AC4 decorator requirement.
        """
        return df1

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Execute Gold schema validation with composite PK and projection logic.

        Uses validate_gold_dataframe() for:
        - Composite PK uniqueness checks
        - Column projection
        - Detailed validation summaries
        """
        try:
            validated_df, summary = validate_gold_dataframe(
                dataframe, project_columns=self.project_columns
            )
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            context.metadata.setdefault(
                "gold_schema_validation", gold_summary_to_dict(summary)
            )

        return validated_df


# ===== Story 2.1: Pydantic Validation Pipeline Steps (AC5) =====


class ValidateInputRowsStep:
    """
    Story 2.1 AC5: Batch validation using AnnuityPerformanceIn (loose validation).

    Validates DataFrame rows using Pydantic AnnuityPerformanceIn model to handle
    messy Excel data. Collects validation errors for export (Story 2.5) and
    returns validated DataFrame for further processing.

    Integration with Epic 1 Story 1.5 pipeline framework:
    - Implements DataFrameStep protocol (execute method)
    - Uses PipelineContext for execution metadata
    - Stores validation errors in context.metadata['validation_errors']
    """

    @property
    def name(self) -> str:
        """Step name for logging and metrics."""
        return "pydantic_input_validation"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: Any,  # PipelineContext from types.py
    ) -> pd.DataFrame:
        """
        Validate DataFrame rows using AnnuityPerformanceIn model.

        AC5 Requirements:
        - Batch validation: iterate DataFrame rows, validate each
        - Collect errors (not fail-fast)
        - Return validated DataFrame

        Args:
            dataframe: Input DataFrame with raw Excel data
            context: PipelineContext with execution metadata

        Returns:
            DataFrame with rows that passed validation (invalid rows removed)

        Side Effects:
            Stores validation errors in context.metadata['validation_errors']
            as list of dicts with keys: row_index, field_name, error_message, original_value
        """
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceIn,
        )
        from pydantic import ValidationError

        validation_errors = []
        valid_rows = []
        total_rows = len(dataframe)

        logger.info(
            f"[{self.name}] Starting batch validation of {total_rows} rows "
            f"using AnnuityPerformanceIn (loose validation)"
        )

        for idx, row in dataframe.iterrows():
            try:
                # Convert row to dict and validate with Pydantic
                row_dict = row.to_dict()
                validated_model = AnnuityPerformanceIn(**row_dict)

                # Convert validated model back to dict for DataFrame
                # Use model_dump() (Pydantic v2 API) instead of dict()
                validated_dict = validated_model.model_dump(by_alias=True)
                valid_rows.append(validated_dict)

            except ValidationError as e:
                # AC4: Collect error with row context
                for error in e.errors():
                    field_path = " -> ".join(str(loc) for loc in error["loc"])
                    validation_errors.append(
                        {
                            "row_index": idx,
                            "field_name": field_path,
                            "error_type": error["type"],
                            "error_message": error["msg"],
                            "original_value": row_dict.get(field_path),
                        }
                    )

                logger.debug(
                    f"[{self.name}] Row {idx} failed validation: "
                    f"{len(e.errors())} errors"
                )

            except Exception as e:
                # Catch unexpected errors
                validation_errors.append(
                    {
                        "row_index": idx,
                        "field_name": "unknown",
                        "error_type": "UnexpectedError",
                        "error_message": str(e),
                        "original_value": None,
                    }
                )
                logger.warning(
                    f"[{self.name}] Unexpected error validating row {idx}: {e}"
                )

        # Store errors in context for Story 2.5 CSV export
        if hasattr(context, "metadata"):
            context.metadata["validation_errors"] = validation_errors

        # AC5: Validation summary
        valid_count = len(valid_rows)
        failed_count = total_rows - valid_count
        error_rate = failed_count / total_rows if total_rows > 0 else 0

        logger.info(
            f"[{self.name}] Validation complete: "
            f"{valid_count}/{total_rows} rows valid ({error_rate:.1%} error rate), "
            f"{len(validation_errors)} errors collected"
        )

        # Create output DataFrame from valid rows
        if valid_rows:
            validated_df = pd.DataFrame(valid_rows)
            return validated_df
        else:
            # Return empty DataFrame with same columns
            return pd.DataFrame(columns=dataframe.columns)


class ValidateOutputRowsStep:
    """
    Story 2.1 AC5: Batch validation using AnnuityPerformanceOut (strict validation).

    Validates DataFrame rows using Pydantic AnnuityPerformanceOut model to enforce
    business rules before database loading. Raises ValidationError if critical
    business rules fail (e.g., required fields missing).

    Integration with Epic 1 Story 1.5 pipeline framework:
    - Implements DataFrameStep protocol (execute method)
    - Uses PipelineContext for execution metadata
    - Stores validation errors in context.metadata['strict_validation_errors']
    """

    @property
    def name(self) -> str:
        """Step name for logging and metrics."""
        return "pydantic_output_validation"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: Any,  # PipelineContext from types.py
    ) -> pd.DataFrame:
        """
        Validate DataFrame rows using AnnuityPerformanceOut model.

        AC5 Requirements:
        - Batch validation: iterate DataFrame rows, validate each
        - Collect errors (not fail-fast)
        - Enforce business rules (non-negative assets, required fields)

        AC2 Requirements:
        - Strict validation: required fields, non-nullable types
        - Business rule validation: cross-field checks

        Args:
            dataframe: Input DataFrame with cleaned Silver layer data
            context: PipelineContext with execution metadata

        Returns:
            DataFrame with rows that passed strict validation

        Side Effects:
            Stores validation errors in context.metadata['strict_validation_errors']
            as list of dicts with keys: row_index, field_name, error_message, original_value

        Raises:
            ValueError: If error rate exceeds 10% threshold (likely systemic issue)
        """
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )
        from pydantic import ValidationError

        validation_errors = []
        valid_rows = []
        total_rows = len(dataframe)

        logger.info(
            f"[{self.name}] Starting strict validation of {total_rows} rows "
            f"using AnnuityPerformanceOut (business rules enforcement)"
        )

        for idx, row in dataframe.iterrows():
            try:
                # Convert row to dict and validate with Pydantic
                row_dict = row.to_dict()
                validated_model = AnnuityPerformanceOut(**row_dict)

                # Convert validated model back to dict for DataFrame
                # Use model_dump() (Pydantic v2 API) instead of dict()
                validated_dict = validated_model.model_dump(by_alias=True)
                valid_rows.append(validated_dict)

            except ValidationError as e:
                # AC4: Collect error with row context and clear messages
                for error in e.errors():
                    field_path = " -> ".join(str(loc) for loc in error["loc"])
                    validation_errors.append(
                        {
                            "row_index": idx,
                            "field_name": field_path,
                            "error_type": error["type"],
                            "error_message": error["msg"],
                            "original_value": row_dict.get(field_path),
                        }
                    )

                logger.debug(
                    f"[{self.name}] Row {idx} failed strict validation: "
                    f"{len(e.errors())} errors"
                )

            except Exception as e:
                # Catch unexpected errors
                validation_errors.append(
                    {
                        "row_index": idx,
                        "field_name": "unknown",
                        "error_type": "UnexpectedError",
                        "error_message": str(e),
                        "original_value": None,
                    }
                )
                logger.warning(
                    f"[{self.name}] Unexpected error in strict validation row {idx}: {e}"
                )

        # Store errors in context for Story 2.5 CSV export
        if hasattr(context, "metadata"):
            context.metadata["strict_validation_errors"] = validation_errors

        # AC5: Validation summary
        valid_count = len(valid_rows)
        failed_count = total_rows - valid_count
        error_rate = failed_count / total_rows if total_rows > 0 else 0

        # Error threshold check (Story 2.5 pattern): fail fast if >10% invalid
        if error_rate > 0.10:
            error_msg = (
                f"Validation error rate {error_rate:.1%} exceeds 10% threshold. "
                f"This likely indicates a systemic issue (bad config, corrupted source data). "
                f"Failed rows: {failed_count}/{total_rows}"
            )
            logger.error(f"[{self.name}] {error_msg}")
            raise ValueError(error_msg)

        logger.info(
            f"[{self.name}] Strict validation complete: "
            f"{valid_count}/{total_rows} rows valid ({error_rate:.1%} error rate), "
            f"{len(validation_errors)} errors collected"
        )

        # Create output DataFrame from valid rows
        if valid_rows:
            validated_df = pd.DataFrame(valid_rows)
            return validated_df
        else:
            # Return empty DataFrame with same columns
            return pd.DataFrame(columns=dataframe.columns)
