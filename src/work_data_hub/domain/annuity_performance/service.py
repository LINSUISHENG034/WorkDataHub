"""
Pure transformation service for annuity performance data.

This module provides pure functions for transforming raw Excel data from "规模明细"
sheets into validated annuity performance domain objects. All functions are side-effect
free and fully testable. Includes column projection to prevent SQL column mismatch errors.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from .models import AnnuityPerformanceIn, AnnuityPerformanceOut

logger = logging.getLogger(__name__)


class AnnuityPerformanceTransformationError(Exception):
    """Raised when annuity performance data transformation fails."""

    pass


def get_allowed_columns() -> List[str]:
    """
    Get allowed columns from DDL - hardcoded for MVP.

    Returns all 24 columns from scripts/dev/annuity_performance_real.sql
    This prevents SQL column-not-found errors by filtering Excel data
    to only valid database columns.

    Returns:
        List of allowed column names matching DDL schema
    """
    return [
        "id", "月度", "业务类型", "计划类型", "计划代码", "计划名称",
        "组合类型", "组合代码", "组合名称", "客户名称", "期初资产规模",
        "期末资产规模", "供款", "流失(含待遇支付)", "流失", "待遇支付",
        "投资收益", "当期收益率", "机构代码", "机构名称", "产品线代码",
        "年金账户号", "年金账户名", "company_id",
        # Additional fields that may appear in Excel for processing
        "年", "月", "公司代码", "报告日期"
    ]


def project_columns(rows: List[Dict[str, Any]], allowed_cols: List[str]) -> List[Dict[str, Any]]:
    """
    Filter dictionary keys to only allowed columns for safe SQL loading.

    This prevents column-not-found errors when Excel files contain more
    columns than the database schema expects.

    Args:
        rows: List of row dictionaries from Excel
        allowed_cols: List of column names allowed in database

    Returns:
        List of dictionaries with only allowed columns
    """
    if not rows:
        return []

    logger.debug(f"Projecting {len(rows)} rows to allowed columns: {len(allowed_cols)} columns")

    # Use dictionary comprehension for memory efficiency
    projected_rows = [
        {k: row.get(k) for k in allowed_cols if k in row}
        for row in rows
    ]

    if projected_rows:
        original_cols = set(rows[0].keys()) if rows else set()
        projected_cols = set(projected_rows[0].keys()) if projected_rows else set()
        removed_cols = original_cols - projected_cols
        if removed_cols:
            logger.debug(f"Removed columns during projection: {sorted(removed_cols)}")

    return projected_rows


def process(
    rows: List[Dict[str, Any]], data_source: str = "unknown"
) -> List[AnnuityPerformanceOut]:
    """
    Process raw Excel rows into validated annuity performance output models.

    This is the main entry point for the annuity performance domain service.
    It transforms raw dictionary data from "规模明细" Excel sheets into fully
    validated AnnuityPerformanceOut models ready for data warehouse loading.

    Args:
        rows: List of dictionaries representing Excel rows
        data_source: Identifier for the source file or system

    Returns:
        List of validated AnnuityPerformanceOut models

    Raises:
        AnnuityPerformanceTransformationError: If transformation fails
        ValueError: If input data is invalid or cannot be processed
    """
    if not rows:
        logger.info("No rows provided for processing")
        return []

    if not isinstance(rows, list):
        raise ValueError("Rows must be provided as a list")

    logger.info(f"Processing {len(rows)} rows from data source: {data_source}")

    # CRITICAL: Column projection to prevent SQL errors
    allowed_columns = get_allowed_columns()
    projected_rows = project_columns(rows, allowed_columns)

    if not projected_rows:
        logger.warning("No rows remained after column projection")
        return []

    processed_records = []
    processing_errors = []

    for row_index, raw_row in enumerate(projected_rows):
        try:
            # Transform single row
            processed_record = _transform_single_row(raw_row, data_source, row_index)

            if processed_record:
                processed_records.append(processed_record)
            else:
                logger.debug(f"Row {row_index} was filtered out during transformation")
                processing_errors.append(
                    f"Row {row_index}: filtered out due to missing required fields"
                )

        except ValidationError as e:
            error_msg = f"Validation failed for row {row_index}: {e}"
            logger.error(error_msg)
            processing_errors.append(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error processing row {row_index}: {e}"
            logger.error(error_msg)
            processing_errors.append(error_msg)

    # Report processing results
    logger.info(f"Successfully processed {len(processed_records)} of {len(rows)} rows")

    if processing_errors:
        logger.warning(f"Encountered {len(processing_errors)} processing errors")

        # If more than 50% of rows failed, consider this a critical failure
        if len(processing_errors) > len(rows) * 0.5:
            raise AnnuityPerformanceTransformationError(
                f"Too many processing errors ({len(processing_errors)}/{len(rows)}). "
                f"First error: {processing_errors[0]}"
            )

    return processed_records


def _transform_single_row(
    raw_row: Dict[str, Any], data_source: str, row_index: int
) -> Optional[AnnuityPerformanceOut]:
    """
    Transform a single raw Excel row into a validated output model.

    Args:
        raw_row: Dictionary representing a single Excel row (after column projection)
        data_source: Source identifier for tracking
        row_index: Row number for error reporting

    Returns:
        Validated AnnuityPerformanceOut model, or None if row should be filtered out

    Raises:
        ValidationError: If validation fails
        ValueError: If required data is missing or invalid
    """
    # Step 1: Parse raw row into input model for initial validation
    try:
        input_model = AnnuityPerformanceIn(**raw_row)
    except ValidationError:
        raise

    # Step 2: Extract and validate core date information
    report_date = _extract_report_date(input_model, row_index)

    if report_date is None:
        logger.debug(f"Row {row_index}: Cannot determine report date, skipping")
        return None

    # Step 3: Extract and validate required identifiers
    plan_code = _extract_plan_code(input_model, row_index)
    company_code = _extract_company_code(input_model, row_index)

    if not plan_code or not company_code:
        logger.debug(f"Row {row_index}: Missing required identifiers, skipping")
        return None

    # Step 4: Extract all financial and metadata fields
    financial_data = _extract_financial_metrics(input_model, row_index)
    metadata_fields = _extract_metadata_fields(input_model, row_index)

    # Step 5: Build output model with all extracted data
    output_data = {
        "月度": report_date,
        "计划代码": plan_code,
        "公司代码": company_code,  # For composite PK
        "data_source": data_source,
        **financial_data,
        **metadata_fields,
    }

    # Step 6: Create and validate final output model
    try:
        output_model = AnnuityPerformanceOut(**output_data)
        return output_model
    except ValidationError:
        raise


def _extract_report_date(input_model: AnnuityPerformanceIn, row_index: int) -> Optional[date]:
    """
    Extract report date from input model, trying various field combinations.

    For annuity performance, we can use 月度 directly or construct from 年/月.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Extracted date or None if cannot be determined
    """
    # Try 月度 field first (may already be a date)
    if input_model.月度:
        if isinstance(input_model.月度, date):
            return input_model.月度
        # Try to parse string date
        try:
            from datetime import datetime
            if isinstance(input_model.月度, str):
                # Try common date formats
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月"]:
                    try:
                        parsed_date = datetime.strptime(input_model.月度.strip(), fmt).date()
                        return parsed_date
                    except ValueError:
                        continue
        except Exception as e:
            logger.debug(f"Row {row_index}: Cannot parse 月度 field {input_model.月度}: {e}")

    # Fall back to constructing from 年/月 fields
    year = None
    month = None

    # Try Chinese field names first
    if input_model.年:
        try:
            year = int(str(input_model.年).strip())
            # Handle 2-digit years (24 -> 2024)
            if year < 50:  # Assume years < 50 are 20xx
                year += 2000
            elif year < 100:  # Years 50-99 are 19xx
                year += 1900
        except (ValueError, AttributeError):
            logger.debug(f"Row {row_index}: Cannot parse year from '年' field: {input_model.年}")

    if input_model.月:
        try:
            month = int(str(input_model.月).strip())
        except (ValueError, AttributeError):
            logger.debug(f"Row {row_index}: Cannot parse month from '月' field: {input_model.月}")

    # Try to parse from report_period string if direct fields are not available
    if (year is None or month is None) and input_model.report_period:
        parsed_date_tuple = _parse_report_period(input_model.report_period)
        if parsed_date_tuple:
            if year is None:
                year = parsed_date_tuple[0]
            if month is None:
                month = parsed_date_tuple[1]

    # Validate extracted values
    if year is not None and month is not None:
        # Treat explicitly provided but invalid values as validation errors
        if not (2000 <= year <= 2030):
            logger.debug(f"Row {row_index}: Invalid year {year}; returning None")
            return None
        if not (1 <= month <= 12):
            logger.debug(f"Row {row_index}: Invalid month {month}; returning None")
            return None

        try:
            return date(year, month, 1)
        except ValueError as e:
            logger.debug(
                f"Row {row_index}: Cannot construct date from year={year}, "
                f"month={month}: {e}; returning None"
            )
            return None

    logger.debug(f"Row {row_index}: Could not extract valid year/month")
    return None


def _parse_report_period(report_period: str) -> Optional[Tuple[int, int]]:
    """
    Parse year and month from various report period string formats.

    Same logic as trustee_performance but may encounter different Chinese formats.

    Args:
        report_period: String containing period information

    Returns:
        Tuple of (year, month) or None if cannot be parsed
    """
    if not report_period:
        return None

    import re

    # Try common patterns for annuity files
    patterns = [
        r"(\d{4})[年\-/](\d{1,2})",  # 2024年11月 or 2024-11 or 2024/11
        r"(\d{4})[年\-/](\d{1,2})[月]",  # 2024年11月
        r"(\d{1,2})[月/](\d{4})",  # 11月2024
        r"(\d{4})(\d{2})",  # 202411
        r"(\d{2})年(\d{1,2})",  # 24年11月 (2-digit year)
    ]

    for pattern in patterns:
        match = re.search(pattern, report_period)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 2:
                    # Determine which group is year vs month based on value
                    val1, val2 = int(groups[0]), int(groups[1])

                    if val1 > 12:  # First value is likely year
                        year, month = val1, val2
                    elif val2 > 12:  # Second value is likely year
                        year, month = val2, val1
                    elif val1 > 2000:  # First value looks like year
                        year, month = val1, val2
                    elif val2 > 2000:  # Second value looks like year
                        year, month = val2, val1
                    else:
                        # Default: assume first is year for YYYY/MM pattern
                        year, month = val1, val2

                    # Handle 2-digit years
                    if year < 50:
                        year += 2000
                    elif year < 100:
                        year += 1900

                    return (year, month)

            except (ValueError, IndexError):
                continue

    return None


def _extract_plan_code(input_model: AnnuityPerformanceIn, row_index: int) -> Optional[str]:
    """Extract plan code from input model."""
    # Try Chinese field name first
    if input_model.计划代码:
        return str(input_model.计划代码).strip()

    logger.debug(f"Row {row_index}: No plan code found")
    return None


def _extract_company_code(input_model: AnnuityPerformanceIn, row_index: int) -> Optional[str]:
    """Extract company code from input model."""
    # Try explicit company_id field first
    if input_model.company_id:
        return str(input_model.company_id).strip()

    # Try Chinese field name
    if input_model.公司代码:
        return str(input_model.公司代码).strip()

    # For annuity data, we might derive company code from customer name or other fields
    # This is domain-specific logic
    if input_model.客户名称:
        # Simple heuristic: use first part of customer name as company code
        customer = str(input_model.客户名称).strip()
        # Remove common company suffixes and take first meaningful part
        simplified = (customer.replace("有限公司", "")
                     .replace("股份有限公司", "")
                     .replace("集团", "")
                     .strip())
        if simplified:
            return simplified[:20]  # Truncate to reasonable length

    logger.debug(f"Row {row_index}: No company code found")
    return None


def _extract_financial_metrics(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Dict[str, Any]:
    """
    Extract all financial metrics from input model.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Dictionary of financial metrics for output model
    """
    metrics = {}

    # Extract all financial fields that have direct mappings
    financial_fields = [
        "期初资产规模", "期末资产规模", "供款", "流失", "待遇支付",
        "投资收益", "当期收益率"
    ]

    for field in financial_fields:
        if hasattr(input_model, field) and getattr(input_model, field) is not None:
            metrics[field] = getattr(input_model, field)

    # Handle the special case of "流失(含待遇支付)" -> "流失_含待遇支付"
    if input_model.流失_含待遇支付 is not None:
        metrics["流失_含待遇支付"] = input_model.流失_含待遇支付

    return metrics


def _extract_metadata_fields(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Dict[str, Any]:
    """
    Extract all metadata and organizational fields from input model.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Dictionary of metadata fields for output model
    """
    fields = {}

    # Extract all text/organizational fields
    text_fields = [
        "业务类型", "计划类型", "计划名称", "组合类型", "组合代码", "组合名称",
        "客户名称", "机构代码", "机构名称", "产品线代码", "年金账户号", "年金账户名"
    ]

    for field in text_fields:
        if hasattr(input_model, field) and getattr(input_model, field) is not None:
            fields[field] = getattr(input_model, field)

    # Handle company_id separately
    if input_model.company_id:
        fields["company_id"] = input_model.company_id

    return fields


def validate_input_batch(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate a batch of input rows and return valid rows plus error messages.

    This is a utility function for pre-validating input data before processing.
    Includes column projection step.

    Args:
        rows: List of raw Excel row dictionaries

    Returns:
        Tuple of (valid_rows, error_messages)
    """
    # Apply column projection first
    allowed_columns = get_allowed_columns()
    projected_rows = project_columns(rows, allowed_columns)

    valid_rows = []
    errors = []

    for i, row in enumerate(projected_rows):
        try:
            # Basic structural validation
            model = AnnuityPerformanceIn(**row)
            # Require at least date info (derivable) and identifiers
            has_date = _extract_report_date(model, i) is not None
            has_plan = _extract_plan_code(model, i) is not None
            has_company = _extract_company_code(model, i) is not None

            if has_date and has_plan and has_company:
                valid_rows.append(row)
            else:
                errors.append(
                    f"Row {i}: missing required fields (date/plan/company)"
                )
        except ValidationError as e:
            errors.append(f"Row {i}: {e}")
        except Exception as e:
            errors.append(f"Row {i}: Unexpected validation error: {e}")

    return valid_rows, errors
