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
from typing import Any, Dict, List, Optional

import dateutil.parser as dp
import numpy as np
import pandas as pd

from work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline, TransformStep
from work_data_hub.domain.pipelines.types import Row, StepResult

logger = logging.getLogger(__name__)


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
        if re.match(r'(\d{2}|\d{4})年\d{1,2}月$', date_string):
            return datetime.strptime(date_string + '1日', '%Y年%m月%d日')

        # Match YYYY年MM月DD日 or YY年MM月DD日 format
        elif re.match(r'(\d{2}|\d{4})年\d{1,2}月\d{1,2}日$', date_string):
            return datetime.strptime(date_string, '%Y年%m月%d日')

        # Match YYYYMMDD format
        elif re.match(r'\d{8}', date_string):
            return datetime.strptime(date_string, '%Y%m%d')

        # Match YYYYMM format
        elif re.match(r'\d{6}', date_string):
            return datetime.strptime(date_string + '01', '%Y%m%d')

        # Match YYYY-MM format
        elif re.match(r'\d{4}-\d{2}', date_string):
            return datetime.strptime(date_string + '-01', '%Y-%m-%d')

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
        return ''

    # Remove extra spaces
    name = re.sub(r'\s+', '', name)

    # Remove specified characters
    name = re.sub(r'及下属子企业', '', name)
    name = re.sub(r'(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$', '', name)

    # Simple cleanup for common suffixes
    suffixes_to_remove = [
        '已转出', '待转出', '终止', '转出', '转移终止', '已作废', '已终止',
        '保留', '保留账户', '存量', '已转移终止', '本部', '未使用', '集合', '原'
    ]

    for suffix in suffixes_to_remove:
        if name.endswith(suffix):
            name = name[:-len(suffix)]

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
                '机构': '机构名称',
                '计划号': '计划代码',
                '流失（含待遇支付）': '流失(含待遇支付)'
            }

            # Apply column renaming
            renamed_count = 0
            for old_name, new_name in column_mappings.items():
                if old_name in updated_row:
                    updated_row[new_name] = updated_row.pop(old_name)
                    renamed_count += 1
                    logger.debug(f"Renamed column: {old_name} -> {new_name}")

            if renamed_count > 0:
                warnings.append(f"Renamed {renamed_count} legacy column names to standard format")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"renamed_columns": renamed_count}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Column normalization failed: {e}"]
            )


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
            if '月度' in updated_row:
                original_value = updated_row['月度']
                try:
                    parsed_date = parse_to_standard_date(original_value)
                    updated_row['月度'] = parsed_date

                    if str(parsed_date) != str(original_value):
                        warnings.append(f"Parsed date: {original_value} -> {parsed_date}")

                except Exception as date_error:
                    warnings.append(f"Date parsing failed for '{original_value}': {date_error}")
                    # Keep original value on parsing failure

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"date_fields_processed": 1 if '月度' in row else 0}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Date parsing failed: {e}"]
            )


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

            if '计划代码' in updated_row:
                original_code = updated_row['计划代码']

                # Step 1: Apply specific replacements (exact match from legacy)
                if original_code == '1P0290':
                    updated_row['计划代码'] = 'P0290'
                    warnings.append("Replaced plan code: 1P0290 -> P0290")
                elif original_code == '1P0807':
                    updated_row['计划代码'] = 'P0807'
                    warnings.append("Replaced plan code: 1P0807 -> P0807")

                # Step 2: Apply defaults based on plan type (exact match from legacy)
                current_code = updated_row['计划代码']
                plan_type = updated_row.get('计划类型')

                if (not current_code or current_code == '' or pd.isna(current_code)) and plan_type:
                    if plan_type == '集合计划':
                        updated_row['计划代码'] = 'AN001'
                        warnings.append("Set default plan code AN001 for 集合计划")
                    elif plan_type == '单一计划':
                        updated_row['计划代码'] = 'AN002'
                        warnings.append("Set default plan code AN002 for 单一计划")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"plan_code_updates": len(warnings)}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Plan code cleansing failed: {e}"]
            )


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
            if '机构名称' in updated_row:
                institution_name = updated_row.get('机构名称')
                if institution_name and institution_name in self.company_branch_mapping:
                    mapped_code = self.company_branch_mapping[institution_name]
                    updated_row['机构代码'] = mapped_code
                    warnings.append(f"Mapped institution code: {institution_name} -> {mapped_code}")

            # Step 2: Replace null/empty codes with G00 (exact match from legacy)
            if '机构代码' in updated_row:
                current_code = updated_row['机构代码']
                if current_code == 'null' or not current_code or pd.isna(current_code):
                    updated_row['机构代码'] = 'G00'
                    warnings.append("Set default institution code G00")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"institution_mappings_applied": len(warnings)}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Institution code mapping failed: {e}"]
            )


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
            "职业年金": "QTAN003"
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
            if '组合代码' not in updated_row:
                updated_row['组合代码'] = np.nan

            # Step 2: Remove 'F' prefix (exact match from legacy)
            if '组合代码' in updated_row and updated_row['组合代码']:
                current_code = str(updated_row['组合代码'])
                if current_code.startswith('F'):
                    updated_row['组合代码'] = re.sub(r'^F', '', current_code)
                    warnings.append(f"Removed F prefix from portfolio code: {current_code}")

            # Step 3: Apply defaults (exact match from legacy)
            portfolio_code = updated_row.get('组合代码')
            current_code = str(portfolio_code) if portfolio_code is not None else ''
            business_type = updated_row.get('业务类型')
            plan_type = updated_row.get('计划类型')

            if (not current_code or current_code == '' or pd.isna(current_code)):
                if business_type in ['职年受托', '职年投资']:
                    updated_row['组合代码'] = 'QTAN003'
                    warnings.append("Set portfolio code QTAN003 for 职年业务")
                elif plan_type and plan_type in self.default_portfolio_mapping:
                    default_code = self.default_portfolio_mapping[plan_type]
                    updated_row['组合代码'] = default_code
                    warnings.append(f"Set default portfolio code {default_code} for {plan_type}")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"portfolio_updates": len(warnings)}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Portfolio code defaulting failed: {e}"]
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
            business_type_mapping: Dictionary mapping business types to product line codes
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
            if '业务类型' in updated_row:
                business_type = updated_row['业务类型']
                if business_type and business_type in self.business_type_mapping:
                    product_code = self.business_type_mapping[business_type]
                    updated_row['产品线代码'] = product_code
                    warnings.append(f"Mapped business type: {business_type} -> {product_code}")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"business_type_mappings": len(warnings)}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Business type mapping failed: {e}"]
            )


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

            if '客户名称' in updated_row:
                original_name = updated_row['客户名称']

                # Step 1: Copy to account name field (exact match from legacy)
                updated_row['年金账户名'] = original_name

                # Step 2: Clean customer name (exact match from legacy)
                if isinstance(original_name, str):
                    cleaned_name = clean_company_name(original_name)
                    updated_row['客户名称'] = cleaned_name

                    if cleaned_name != original_name:
                        warnings.append(f"Cleaned customer name: {original_name} -> {cleaned_name}")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"name_cleanings": len(warnings)}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Customer name cleansing failed: {e}"]
            )


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
        company_id5_mapping: Optional[Dict[str, str]] = None
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
            plan_code = updated_row.get('计划代码')
            if plan_code and plan_code in self.company_id1_mapping:
                company_id = self.company_id1_mapping[plan_code]
                resolution_method = "plan_code"
                warnings.append(f"Resolved company_id via plan code: {plan_code} -> {company_id}")

            # Clean enterprise customer number (exact match from legacy)
            if '集团企业客户号' in updated_row and updated_row['集团企业客户号']:
                cleaned_number = str(updated_row['集团企业客户号']).lstrip('C')
                updated_row['集团企业客户号'] = cleaned_number

            # Step 2: Account number mapping (priority 2, exact match from legacy)
            if not company_id:
                account_number = updated_row.get('集团企业客户号')
                if account_number and account_number in self.company_id2_mapping:
                    company_id = self.company_id2_mapping[account_number]
                    resolution_method = "account_number"
                    warnings.append(
                        f"Resolved company_id via account number: {account_number} -> {company_id}"
                    )

            # Step 3: Special case with default '600866980' (priority 3, exact match from legacy)
            if not company_id:
                customer_name = updated_row.get('客户名称')
                if not customer_name or customer_name == '':
                    # Use hardcoded mapping or default
                    if plan_code and plan_code in self.company_id3_mapping:
                        company_id = self.company_id3_mapping[plan_code]
                        resolution_method = "hardcoded"
                        warnings.append(
                            f"Resolved company_id via hardcoded mapping: {plan_code} -> "
                            f"{company_id}"
                        )
                    else:
                        company_id = '600866980'
                        resolution_method = "default_fallback"
                        warnings.append(
                            "Applied default company_id 600866980 for empty customer name"
                        )

            # Step 4: Customer name mapping (priority 4, exact match from legacy)
            if not company_id:
                customer_name = updated_row.get('客户名称')
                if customer_name and customer_name in self.company_id4_mapping:
                    company_id = self.company_id4_mapping[customer_name]
                    resolution_method = "customer_name"
                    warnings.append(
                        f"Resolved company_id via customer name: {customer_name} -> {company_id}"
                    )

            # Step 5: Account name mapping (priority 5, exact match from legacy)
            if not company_id:
                account_name = updated_row.get('年金账户名')
                if account_name and account_name in self.company_id5_mapping:
                    company_id = self.company_id5_mapping[account_name]
                    resolution_method = "account_name"
                    warnings.append(
                        f"Resolved company_id via account name: {account_name} -> {company_id}"
                    )

            # Set the resolved company_id
            updated_row['company_id'] = company_id

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={
                    "company_id": company_id,
                    "resolution_method": resolution_method,
                    "resolution_priority": {
                        "plan_code": 1, "account_number": 2, "hardcoded": 3,
                        "customer_name": 4, "account_name": 5, "default_fallback": 3
                    }.get(resolution_method or "", 0)
                }
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Company ID resolution failed: {e}"]
            )


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
            '备注', '子企业号', '子企业名称', '集团企业客户号', '集团企业客户名称'
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
                metadata={"dropped_fields": dropped_count}
            )

        except Exception as e:
            return StepResult(
                row=row,
                errors=[f"Field cleanup failed: {e}"]
            )




def build_annuity_pipeline(mappings: Optional[Dict[str, Any]] = None) -> Pipeline:
    """
    Build the complete annuity performance pipeline with all transformation steps.

    This factory function creates a Pipeline instance that exactly replicates
    the transformation sequence from the legacy AnnuityPerformanceCleaner._clean_method().

    Args:
        mappings: Dictionary containing all required mapping dictionaries.
                 Expected keys: company_id1_mapping, company_id2_mapping, etc.

    Returns:
        Pipeline: Configured pipeline ready for execution

    Example:
        >>> mappings = load_mappings_from_json("tests/fixtures/sample_legacy_mappings.json")
        >>> pipeline = build_annuity_pipeline(mappings)
        >>> result = pipeline.execute(excel_row_dict)
    """
    if mappings is None:
        mappings = {}

    # Extract mapping dictionaries from fixture format
    def extract_mapping(key: str, fallback: Optional[Dict[str, str]] = None) -> Dict[str, str]:
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
        fallback={"集合计划": "QTAN001", "单一计划": "QTAN002", "职业年金": "QTAN003"}
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
            company_id5_mapping=company_id5_mapping
        ),

        # Step 9: Clean up invalid fields
        FieldCleanupStep()
    ]

    # Create pipeline configuration with matching step configs
    step_configs = [
        StepConfig(name=step.name, import_path=f"{step.__class__.__module__}.{step.__class__.__name__}")
        for step in steps
    ]

    config = PipelineConfig(
        name="annuity_performance_legacy_parity",
        steps=step_configs,
        stop_on_error=False  # Continue processing on errors (log and continue)
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
        >>> mappings = load_mappings_from_json_fixture("tests/fixtures/sample_legacy_mappings.json")
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
