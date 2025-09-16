"""
Pure transformation service for annuity performance data.

This module provides pure functions for transforming raw Excel data from "规模明细"
sheets into validated annuity performance domain objects. All functions are side-effect
free and fully testable. Includes column projection to prevent SQL column mismatch errors.
"""

import logging
import time
from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

from pydantic import ValidationError

from work_data_hub.utils.date_parser import parse_chinese_date

from .csv_export import write_unknowns_csv
from .models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
    EnrichmentStats,
    ProcessingResultWithEnrichment,
)

logger = logging.getLogger(__name__)


class AnnuityPerformanceTransformationError(Exception):
    """Raised when annuity performance data transformation fails."""

    pass


def get_allowed_columns() -> List[str]:
    """
    Get allowed columns from actual database table schema.

    Returns all columns that exist in the "规模明细" table based on the
    actual database schema, not the DDL. This prevents SQL column-not-found
    errors by filtering data to only valid database columns.

    Returns:
        List of allowed column names matching actual database schema
    """
    return [
        "id",
        "月度",
        "业务类型",
        "计划类型",
        "计划代码",
        "计划名称",
        "组合类型",
        "组合代码",
        "组合名称",
        "客户名称",
        "期初资产规模",
        "期末资产规模",
        "供款",
        "流失_含待遇支付",  # 与实际 DDL 保持一致（标准化列名）
        "流失",
        "待遇支付",
        "投资收益",
        "当期收益率",
        "机构代码",
        "机构名称",
        "产品线代码",
        "年金账户号",
        "年金账户名",
        "company_id",
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
    projected_rows = [{k: row.get(k) for k in allowed_cols if k in row} for row in rows]

    if projected_rows:
        original_cols = set(rows[0].keys()) if rows else set()
        projected_cols = set(projected_rows[0].keys()) if projected_rows else set()
        removed_cols = original_cols - projected_cols
        if removed_cols:
            logger.debug(f"Removed columns during projection: {sorted(removed_cols)}")

    return projected_rows


def process(
    rows: List[Dict[str, Any]],
    data_source: str = "unknown",
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
) -> ProcessingResultWithEnrichment:
    """
    Process raw Excel rows into validated annuity performance output models
    with optional enrichment.

    This is the main entry point for the annuity performance domain service.
    It transforms raw dictionary data from "规模明细" Excel sheets into fully
    validated AnnuityPerformanceOut models ready for data warehouse loading.

    When enrichment_service is provided, performs company ID resolution using
    internal mappings, EQC lookups, and async queue processing according to the
    configured budget and export settings.

    Args:
        rows: List of dictionaries representing Excel rows
        data_source: Identifier for the source file or system
        enrichment_service: Optional CompanyEnrichmentService for company ID resolution
        sync_lookup_budget: Budget for synchronous EQC lookups per processing session
        export_unknown_names: Whether to export unknown company names to CSV

    Returns:
        ProcessingResultWithEnrichment with processed records, statistics, and optional CSV export

    Raises:
        AnnuityPerformanceTransformationError: If transformation fails
        ValueError: If input data is invalid or cannot be processed
    """
    if not rows:
        logger.info("No rows provided for processing")
        return ProcessingResultWithEnrichment(
            records=[],
            data_source=data_source
        )

    if not isinstance(rows, list):
        raise ValueError("Rows must be provided as a list")

    logger.info(f"Processing {len(rows)} rows from data source: {data_source}")

    start_time = time.time()
    stats = EnrichmentStats()
    unknown_names: List[str] = []
    processed_records = []
    processing_errors = []

    # NOTE: Do NOT project columns before transformation.
    # Transformation may rely on helper fields like 年/月 present in raw rows.
    # Output models already map to DB columns, and ops will serialize by alias.
    for row_index, raw_row in enumerate(rows):
        try:
            # Transform single row (existing logic)
            processed_record = _transform_single_row(raw_row, data_source, row_index)

            if processed_record:
                # Optional enrichment integration
                if enrichment_service:
                    try:
                        # Call enrichment service with proper field mapping
                        # Extract fields from raw_row since processed_record
                        # may not have all original fields
                        result = enrichment_service.resolve_company_id(
                            plan_code=raw_row.get("计划代码"),
                            customer_name=raw_row.get("客户名称"),
                            account_name=raw_row.get("年金账户名"),
                            sync_lookup_budget=sync_lookup_budget,
                        )

                        # Update record with resolved company_id
                        if result.company_id:
                            processed_record.company_id = result.company_id

                        # Record statistics
                        stats.record(result.status, result.source)

                        # Collect unknown names for CSV export
                        if not result.company_id and raw_row.get("客户名称"):
                            unknown_names.append(raw_row.get("客户名称"))

                    except Exception as e:
                        # CRITICAL: Never fail main pipeline on enrichment errors
                        logger.warning(f"Enrichment failed for row {row_index}: {e}")
                        stats.failed += 1

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

    # Generate CSV export if requested and unknowns exist
    csv_path = None
    if export_unknown_names and unknown_names:
        try:
            csv_path = write_unknowns_csv(unknown_names, data_source)
            logger.info(f"Exported {len(unknown_names)} unknown company names to: {csv_path}")
        except Exception as e:
            # Don't fail processing for CSV export errors
            logger.warning(f"Failed to export unknown names CSV: {e}")

    # Calculate processing time
    processing_time_ms = int((time.time() - start_time) * 1000)
    stats.processing_time_ms = processing_time_ms

    # Log enrichment statistics if enrichment was used
    if enrichment_service and stats.total_records > 0:
        logger.info(
            "Enrichment processing completed",
            extra={
                "total_records": stats.total_records,
                "internal_hits": stats.success_internal,
                "external_hits": stats.success_external,
                "pending_lookup": stats.pending_lookup,
                "temp_assigned": stats.temp_assigned,
                "failed": stats.failed,
                "sync_budget_used": stats.sync_budget_used,
                "processing_time_ms": processing_time_ms,
                "unknown_names_count": len(unknown_names),
                "csv_exported": bool(csv_path)
            }
        )

    return ProcessingResultWithEnrichment(
        records=processed_records,
        enrichment_stats=stats,
        unknown_names_csv=csv_path,
        data_source=data_source,
        processing_time_ms=processing_time_ms,
    )


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
        "company_id": company_code,  # For composite PK - matches database column
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
    Extract report date from input model using unified date parsing.

    For annuity performance, we can use 月度 directly or construct from 年/月.
    This function now uses the unified date parser to handle various Chinese
    date formats including integer YYYYMM format from Excel.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Extracted date or None if cannot be determined
    """
    # Try 月度 field first using unified date parser
    if input_model.月度:
        try:
            parsed_date = parse_chinese_date(input_model.月度)
            if parsed_date:
                logger.debug(f"Row {row_index}: Parsed date from 月度 field: {parsed_date}")
                return parsed_date
        except Exception as e:
            logger.debug(f"Row {row_index}: Cannot parse 月度 field {input_model.月度}: {e}")

    # Fall back to constructing from 年/月 fields
    year = None
    month = None

    # Try Chinese field names first using unified date parser
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


def _strip_f_prefix_if_pattern_matches(value: Optional[str]) -> Optional[str]:
    """
    Strip F-prefix from portfolio code only if it matches strict pattern for portfolio codes.

    This function implements surgical F-prefix removal as specified in PRP P-024.
    Only removes the leading 'F' from codes that look like prefixed portfolio codes,
    not from company names that happen to start with F.

    Args:
        value: The portfolio code string to potentially strip

    Returns:
        String with F-prefix removed if pattern matches, otherwise original string

    Examples:
        "F123ABC" -> "123ABC" (matches: code pattern)
        "F123" -> "123" (matches: code pattern)
        "FIDELITY001" -> "IDELITY001" (matches broadened code pattern)
        "Fund123" -> "Fund123" (doesn't match: contains lowercase)
        "F" -> "F" (doesn't match: no characters after F)
    """
    if not value:
        return value

    import re

    portfolio_code = str(value).strip()

    # Only strip if it matches pattern for portfolio codes:
    # F followed by one or more uppercase alphanumeric characters
    # Pattern broadened per requirement to ^F[0-9A-Z]+$
    if re.match(r"^F[0-9A-Z]+$", portfolio_code):
        return portfolio_code[1:]  # Remove leading 'F'

    return portfolio_code


def _extract_plan_code(input_model: AnnuityPerformanceIn, row_index: int) -> Optional[str]:
    """Extract plan code from input model without F-prefix modification."""
    # Try Chinese field name first
    if input_model.计划代码:
        plan_code = str(input_model.计划代码).strip()
        return plan_code

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
        simplified = (
            customer.replace("有限公司", "").replace("股份有限公司", "").replace("集团", "").strip()
        )
        if simplified:
            return simplified[:20]  # Truncate to reasonable length

    logger.debug(f"Row {row_index}: No company code found")
    return None


def _extract_financial_metrics(input_model: AnnuityPerformanceIn, row_index: int) -> Dict[str, Any]:
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
        "期初资产规模",
        "期末资产规模",
        "供款",
        "流失",
        "待遇支付",
        "投资收益",
        "当期收益率",
    ]

    for field in financial_fields:
        if hasattr(input_model, field) and getattr(input_model, field) is not None:
            metrics[field] = getattr(input_model, field)

    # Handle the standardized field name "流失_含待遇支付"
    # The column normalizer will convert "流失(含待遇支付)" to "流失_含待遇支付"
    # but we need to use the original database column name for output
    if input_model.流失_含待遇支付 is not None:
        metrics["流失(含待遇支付)"] = input_model.流失_含待遇支付

    return metrics


def _extract_metadata_fields(input_model: AnnuityPerformanceIn, row_index: int) -> Dict[str, Any]:
    """
    Extract all metadata and organizational fields from input model.

    Applies F-prefix stripping logic specifically to portfolio code (组合代码)
    when it matches the strict pattern ^F[0-9A-Z]+$.

    Args:
        input_model: Input model containing raw data
        row_index: Row number for error reporting

    Returns:
        Dictionary of metadata fields for output model
    """
    fields = {}

    # Extract all text/organizational fields
    text_fields = [
        "业务类型",
        "计划类型",
        "计划名称",
        "组合类型",
        "组合名称",
        "客户名称",
        "机构代码",
        "机构名称",
        "产品线代码",
        "年金账户号",
        "年金账户名",
    ]

    for field in text_fields:
        if hasattr(input_model, field) and getattr(input_model, field) is not None:
            fields[field] = getattr(input_model, field)

    # Handle 组合代码 separately with F-prefix stripping logic
    if hasattr(input_model, "组合代码") and input_model.组合代码 is not None:
        portfolio_code = _strip_f_prefix_if_pattern_matches(input_model.组合代码)
        fields["组合代码"] = portfolio_code

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
    valid_rows = []
    errors = []

    allowed_columns = get_allowed_columns()

    for i, row in enumerate(rows):
        try:
            # Basic structural validation
            model = AnnuityPerformanceIn(**row)
            # Require at least date info (derivable) and identifiers
            has_date = _extract_report_date(model, i) is not None
            has_plan = _extract_plan_code(model, i) is not None
            has_company = _extract_company_code(model, i) is not None

            if has_date and has_plan and has_company:
                # Project to allowed columns for downstream safety
                projected = project_columns([row], allowed_columns)
                valid_rows.append(projected[0] if projected else {})
            else:
                errors.append(f"Row {i}: missing required fields (date/plan/company)")
        except ValidationError as e:
            errors.append(f"Row {i}: {e}")
        except Exception as e:
            errors.append(f"Row {i}: Unexpected validation error: {e}")

    return valid_rows, errors
