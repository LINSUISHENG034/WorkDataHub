"""
Pure transformation service for trustee performance data.

This module provides pure functions for transforming raw Excel data into
validated trustee performance domain objects. All functions are side-effect
free and fully testable.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from work_data_hub.utils.date_parser import parse_chinese_date

from .models import TrusteePerformanceIn, TrusteePerformanceOut

logger = logging.getLogger(__name__)


class TrusteePerformanceTransformationError(Exception):
    """Raised when trustee performance data transformation fails."""

    pass


def process(
    rows: List[Dict[str, Any]], data_source: str = "unknown"
) -> List[TrusteePerformanceOut]:
    """
    Process raw Excel rows into validated trustee performance output models.

    This is the main entry point for the trustee performance domain service.
    It transforms raw dictionary data from Excel files into fully validated
    TrusteePerformanceOut models ready for data warehouse loading.

    Args:
        rows: List of dictionaries representing Excel rows
        data_source: Identifier for the source file or system

    Returns:
        List of validated TrusteePerformanceOut models

    Raises:
        TrusteePerformanceTransformationError: If transformation fails
        ValueError: If input data is invalid or cannot be processed
    """
    if not rows:
        logger.info("No rows provided for processing")
        return []

    if not isinstance(rows, list):
        raise ValueError("Rows must be provided as a list")

    logger.info(f"Processing {len(rows)} rows from data source: {data_source}")

    processed_records = []
    processing_errors = []

    for row_index, raw_row in enumerate(rows):
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
            raise TrusteePerformanceTransformationError(
                f"Too many processing errors ({len(processing_errors)}/{len(rows)}). "
                f"First error: {processing_errors[0]}"
            )

    return processed_records


def _transform_single_row(
    raw_row: Dict[str, Any], data_source: str, row_index: int
) -> Optional[TrusteePerformanceOut]:
    """
    Transform a single raw Excel row into a validated output model.

    Args:
        raw_row: Dictionary representing a single Excel row
        data_source: Source identifier for tracking
        row_index: Row number for error reporting

    Returns:
        Validated TrusteePerformanceOut model, or None if row should be filtered out

    Raises:
        ValidationError: If validation fails
        ValueError: If required data is missing or invalid
    """
    # Step 1: Parse raw row into input model for initial validation
    try:
        input_model = TrusteePerformanceIn(**raw_row)
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

    # Step 4: Extract optional performance metrics
    performance_data = _extract_performance_metrics(input_model, row_index)

    # Step 5: Build output model with all extracted data
    output_data = {
        "report_date": report_date,
        "plan_code": plan_code,
        "company_code": company_code,
        "data_source": data_source,
        **performance_data,
    }

    # Step 6: Create and validate final output model
    try:
        output_model = TrusteePerformanceOut(**output_data)
        return output_model
    except ValidationError:
        raise


def _extract_report_date(input_model: TrusteePerformanceIn, row_index: int) -> Optional[date]:
    """
    Extract report date from input model using unified date parsing.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Extracted date or None if cannot be determined
    """
    year = None
    month = None

    # Try Chinese field names first using unified date parser
    if input_model.年:
        try:
            year = int(str(input_model.年).strip())
        except (ValueError, AttributeError):
            logger.debug(f"Row {row_index}: Cannot parse year from '年' field: {input_model.年}")

    if input_model.月:
        try:
            month = int(str(input_model.月).strip())
        except (ValueError, AttributeError):
            logger.debug(f"Row {row_index}: Cannot parse month from '月' field: {input_model.月}")

    # Fallback to English field names
    if year is None and input_model.year is not None:
        year = input_model.year

    if month is None and input_model.month is not None:
        month = input_model.month

    # Try to parse from report_period string if direct fields are not available
    if (year is None or month is None) and input_model.report_period:
        try:
            parsed_date = parse_chinese_date(input_model.report_period)
            if parsed_date:
                if year is None:
                    year = parsed_date.year
                if month is None:
                    month = parsed_date.month
        except Exception as e:
            logger.debug(f"Row {row_index}: Cannot parse report_period field: {e}")

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
                f"Row {row_index}: Cannot create date from year={year}, month={month}: {e}"
            )
            return None

    logger.debug(f"Row {row_index}: No valid date could be extracted")
    return None


def _parse_report_period(report_period: str) -> Optional[Tuple[int, int]]:
    """
    Parse year and month from various report period string formats.

    Args:
        report_period: String containing period information

    Returns:
        Tuple of (year, month) or None if cannot be parsed
    """
    if not report_period:
        return None

    import re

    # Try common patterns
    patterns = [
        r"(\d{4})[年\-/](\d{1,2})",  # 2024年11月 or 2024-11 or 2024/11
        r"(\d{4})[年\-/](\d{1,2})[月]",  # 2024年11月
        r"(\d{1,2})[月/](\d{4})",  # 11月2024
        r"(\d{4})(\d{2})",  # 202411
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
                        return (val1, val2)
                    elif val2 > 12:  # Second value is likely year
                        return (val2, val1)
                    elif val1 > 2000:  # First value looks like year
                        return (val1, val2)
                    elif val2 > 2000:  # Second value looks like year
                        return (val2, val1)

            except (ValueError, IndexError):
                continue

    return None


def _extract_plan_code(input_model: TrusteePerformanceIn, row_index: int) -> Optional[str]:
    """Extract plan code from input model."""
    # Try Chinese field name first
    if input_model.计划代码:
        return str(input_model.计划代码).strip()

    # Fallback to English field name
    if input_model.plan_code:
        return str(input_model.plan_code).strip()

    logger.debug(f"Row {row_index}: No plan code found")
    return None


def _extract_company_code(input_model: TrusteePerformanceIn, row_index: int) -> Optional[str]:
    """Extract company code from input model."""
    # Try Chinese field name first
    if input_model.公司代码:
        return str(input_model.公司代码).strip()

    # Fallback to English field name
    if input_model.company_code:
        return str(input_model.company_code).strip()

    logger.debug(f"Row {row_index}: No company code found")
    return None


def _extract_performance_metrics(
    input_model: TrusteePerformanceIn, row_index: int
) -> Dict[str, Any]:
    """
    Extract performance metrics from input model.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Dictionary of performance metrics for output model
    """
    metrics = {}

    # Extract return rate
    if input_model.收益率:
        metrics["return_rate"] = input_model.收益率

    # Extract net asset value
    if input_model.净值:
        metrics["net_asset_value"] = input_model.净值

    # Extract fund scale
    if input_model.规模:
        metrics["fund_scale"] = input_model.规模

    return metrics


def validate_input_batch(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate a batch of input rows and return valid rows plus error messages.

    This is a utility function for pre-validating input data before processing.

    Args:
        rows: List of raw Excel row dictionaries

    Returns:
        Tuple of (valid_rows, error_messages)
    """
    valid_rows = []
    errors = []

    for i, row in enumerate(rows):
        try:
            # Basic structural validation
            model = TrusteePerformanceIn(**row)
            # Require at least date info (derivable) and identifiers
            has_date = _extract_report_date(model, i) is not None
            has_plan = _extract_plan_code(model, i) is not None
            has_company = _extract_company_code(model, i) is not None

            if has_date and has_plan and has_company:
                valid_rows.append(row)
            else:
                errors.append(f"Row {i}: missing required fields (date/plan/company)")
        except ValidationError as e:
            errors.append(f"Row {i}: {e}")
        except Exception as e:
            errors.append(f"Row {i}: Unexpected validation error: {e}")

    return valid_rows, errors
