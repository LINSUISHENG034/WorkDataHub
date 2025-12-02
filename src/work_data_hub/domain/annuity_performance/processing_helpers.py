"""
Row processing and transformation helper functions for annuity performance domain.

Story 4.8: Extracted from service.py to reduce module size and improve
separation of concerns. Contains row-level processing and transformation logic.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import ValidationError

from work_data_hub.utils.date_parser import parse_chinese_date

from .models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
    EnrichmentStats,
)

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = logging.getLogger(__name__)


class AnnuityPerformanceTransformationError(Exception):
    """Raised when annuity performance data transformation fails."""

    pass


def process_rows_via_pipeline(
    rows: List[Dict[str, Any]],
    data_source: str,
    enrichment_service: Optional["CompanyEnrichmentService"],
    sync_lookup_budget: int,
    stats: EnrichmentStats,
    unknown_names: List[str],
) -> tuple[List[AnnuityPerformanceOut], List[str]]:
    """
    Process rows using Pipeline.run() for DataFrame-level transformation.

    Story 4.7 refactoring: Uses Pipeline.run() instead of row-by-row execute()
    for improved performance and cleaner orchestration.

    Args:
        rows: Raw Excel rows to process
        data_source: Source identifier
        enrichment_service: Optional enrichment service
        sync_lookup_budget: Budget for sync lookups
        stats: Enrichment statistics tracker
        unknown_names: List to collect unknown company names

    Returns:
        Tuple of (processed_records, processing_errors)
    """
    from .pipeline_steps import build_annuity_pipeline, load_mappings_from_json_fixture

    # Build pipeline with mappings
    pipeline = build_pipeline_with_mappings(
        build_annuity_pipeline, load_mappings_from_json_fixture
    )

    # Convert rows to DataFrame for Pipeline.run()
    input_df = pd.DataFrame(rows)
    logger.debug(f"Running pipeline on DataFrame with {len(input_df)} rows")

    # Execute pipeline on entire DataFrame (Story 4.7: AC-4.7.4)
    pipeline_result = pipeline.run(input_df)

    # Collect pipeline-level errors
    processing_errors = list(pipeline_result.errors)
    if pipeline_result.error_rows:
        for error_row in pipeline_result.error_rows:
            row_idx = error_row.get("row_index", "unknown")
            error_msg = error_row.get("error", "Unknown error")
            processing_errors.append(f"Row {row_idx}: {error_msg}")

    # Convert output DataFrame to domain models
    processed_records = convert_pipeline_output_to_models(
        pipeline_result.output_data,
        rows,
        data_source,
        enrichment_service,
        sync_lookup_budget,
        stats,
        unknown_names,
        processing_errors,
    )

    return processed_records, processing_errors


def build_pipeline_with_mappings(
    build_fn: Any,
    load_mappings_fn: Any,
) -> Any:
    """
    Build pipeline with mappings, falling back to empty mappings on error.

    Args:
        build_fn: Pipeline builder function
        load_mappings_fn: Mappings loader function

    Returns:
        Configured Pipeline instance
    """
    try:
        fixture_path = "tests/fixtures/sample_legacy_mappings.json"
        mappings = load_mappings_fn(fixture_path)
        pipeline = build_fn(mappings)
        logger.debug("Built pipeline with mapping fixture")
        return pipeline
    except Exception as mapping_error:
        logger.warning(
            f"Could not load mapping fixture: {mapping_error}, using empty mappings"
        )
        return build_fn()


def convert_pipeline_output_to_models(
    output_df: pd.DataFrame,
    original_rows: List[Dict[str, Any]],
    data_source: str,
    enrichment_service: Optional["CompanyEnrichmentService"],
    sync_lookup_budget: int,
    stats: EnrichmentStats,
    unknown_names: List[str],
    processing_errors: List[str],
) -> List[AnnuityPerformanceOut]:
    """
    Convert Pipeline.run() output DataFrame to validated domain models.

    Args:
        output_df: Transformed DataFrame from Pipeline.run()
        original_rows: Original input rows for enrichment context
        data_source: Source identifier
        enrichment_service: Optional enrichment service
        sync_lookup_budget: Budget for sync lookups
        stats: Enrichment statistics tracker
        unknown_names: List to collect unknown company names
        processing_errors: List to append conversion errors

    Returns:
        List of validated AnnuityPerformanceOut models
    """
    processed_records: List[AnnuityPerformanceOut] = []

    for row_index, row in output_df.iterrows():
        try:
            row_dict = row.to_dict()
            processed_record = pipeline_row_to_model(
                row_dict, data_source, int(row_index)
            )

            if processed_record:
                # Apply enrichment if service is available
                if enrichment_service and row_index < len(original_rows):
                    processed_record = apply_enrichment_integration(
                        processed_record,
                        original_rows[int(row_index)],
                        enrichment_service,
                        sync_lookup_budget,
                        stats,
                        unknown_names,
                        int(row_index),
                    )
                processed_records.append(processed_record)
            else:
                logger.debug(f"Row {row_index} filtered out during model conversion")
                processing_errors.append(
                    f"Row {row_index}: filtered out due to missing required fields"
                )

        except ValidationError as e:
            error_msg = f"Pipeline validation failed for row {row_index}: {e}"
            logger.error(error_msg)
            processing_errors.append(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error converting row {row_index}: {e}"
            logger.error(error_msg)
            processing_errors.append(error_msg)

    return processed_records


def validate_processing_results(
    processed_records: List[AnnuityPerformanceOut],
    processing_errors: List[str],
    total_rows: int,
) -> None:
    """
    Validate processing results and raise error if too many failures.

    Args:
        processed_records: Successfully processed records
        processing_errors: List of error messages
        total_rows: Total number of input rows

    Raises:
        AnnuityPerformanceTransformationError: If >50% of rows failed
    """
    logger.info(f"Successfully processed {len(processed_records)} of {total_rows} rows")

    if processing_errors:
        logger.warning(f"Encountered {len(processing_errors)} processing errors")

        if len(processing_errors) > total_rows * 0.5:
            raise AnnuityPerformanceTransformationError(
                f"Too many processing errors ({len(processing_errors)}/{total_rows}). "
                f"First error: {processing_errors[0]}"
            )


def export_unknown_names_csv(
    unknown_names: List[str],
    data_source: str,
    export_enabled: bool,
) -> Optional[str]:
    """
    Export unknown company names to CSV if requested.

    Args:
        unknown_names: List of unknown company names
        data_source: Source identifier for CSV filename
        export_enabled: Whether export is enabled

    Returns:
        Path to exported CSV file, or None if not exported
    """
    from pathlib import Path

    from work_data_hub.infrastructure.validation import export_error_csv

    if not export_enabled or not unknown_names:
        return None

    try:
        # Convert unknown names to DataFrame for export
        df = pd.DataFrame({"unknown_company_name": unknown_names})
        csv_path = export_error_csv(
            df,
            filename_prefix=f"unknown_companies_{data_source}",
            output_dir=Path("logs"),
        )
        logger.info(
            f"Exported {len(unknown_names)} unknown company names to: {csv_path}"
        )
        return str(csv_path)
    except Exception as e:
        logger.warning(f"Failed to export unknown names CSV: {e}")
        return None


def log_enrichment_stats(
    enrichment_service: Optional["CompanyEnrichmentService"],
    stats: EnrichmentStats,
    processing_time_ms: int,
    unknown_names_count: int,
    csv_exported: bool,
) -> None:
    """
    Log enrichment statistics if enrichment was used.

    Args:
        enrichment_service: Enrichment service (None if not used)
        stats: Enrichment statistics
        processing_time_ms: Total processing time
        unknown_names_count: Number of unknown company names
        csv_exported: Whether CSV was exported
    """
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
                "unknown_names_count": unknown_names_count,
                "csv_exported": csv_exported,
            },
        )


def transform_single_row(
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
    report_date = extract_report_date(input_model, row_index)

    if report_date is None:
        logger.debug(f"Row {row_index}: Cannot determine report date, skipping")
        return None

    # Step 3: Extract and validate required identifiers
    plan_code = extract_plan_code(input_model, row_index)
    company_code = extract_company_code(input_model, row_index)

    if not plan_code or not company_code:
        logger.debug(f"Row {row_index}: Missing required identifiers, skipping")
        return None

    # Step 4: Extract all financial and metadata fields
    financial_data = extract_financial_metrics(input_model, row_index)
    metadata_fields = extract_metadata_fields(input_model, row_index)

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


def extract_report_date(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Optional[date]:
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
                logger.debug(
                    f"Row {row_index}: Parsed date from 月度 field: {parsed_date}"
                )
                return parsed_date
        except Exception as e:
            logger.debug(
                f"Row {row_index}: Cannot parse 月度 field {input_model.月度}: {e}"
            )

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
            logger.debug(
                f"Row {row_index}: Cannot parse year from '年' field: {input_model.年}"
            )

    if input_model.月:
        try:
            month = int(str(input_model.月).strip())
        except (ValueError, AttributeError):
            logger.debug(
                f"Row {row_index}: Cannot parse month from '月' field: {input_model.月}"
            )

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
                "Row %s: Cannot create date from year=%s, month=%s: %s",
                row_index,
                year,
                month,
                e,
            )
            return None

    logger.debug(f"Row {row_index}: No valid date could be extracted")
    return None


def parse_report_period(report_period: str) -> Optional[Tuple[int, int]]:
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


def strip_f_prefix_if_pattern_matches(value: Optional[str]) -> Optional[str]:
    """
    Strip F-prefix from portfolio code only if it matches the strict
    pattern for portfolio codes.

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

    portfolio_code = str(value).strip()

    # Only strip if it matches pattern for portfolio codes:
    # F followed by one or more uppercase alphanumeric characters
    # Pattern broadened per requirement to ^F[0-9A-Z]+$
    if re.match(r"^F[0-9A-Z]+$", portfolio_code):
        return portfolio_code[1:]  # Remove leading 'F'

    return portfolio_code


def extract_plan_code(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Optional[str]:
    """Extract plan code from input model without F-prefix modification."""
    # Try Chinese field name first
    if input_model.计划代码:
        plan_code = str(input_model.计划代码).strip()
        return plan_code

    logger.debug(f"Row {row_index}: No plan code found")
    return None


def generate_temp_company_id(customer_name: str) -> str:
    """
    Generate a temporary company ID in IN_<16-char-base32> format.

    Uses HMAC-SHA1 with a salt to generate a stable, deterministic ID
    for unresolved company names. The same customer name will always
    produce the same IN_* ID.

    Args:
        customer_name: The customer name to generate ID for

    Returns:
        Temporary ID in format IN_<16-char-base32> (e.g., IN_ABCDEFGHIJKLMNOP)
    """
    import base64
    import hashlib
    import hmac
    import os

    # Get salt from environment or use default for development
    salt = os.environ.get("WDH_ALIAS_SALT", "default_dev_salt_change_in_prod")

    # Generate HMAC-SHA1 hash
    key = salt.encode("utf-8")
    message = customer_name.encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha1).digest()

    # Take first 10 bytes (80 bits) and encode as base32 (16 chars)
    # Base32 produces 8 chars per 5 bytes, so 10 bytes = 16 chars
    encoded = base64.b32encode(digest[:10]).decode("ascii")

    return f"IN_{encoded}"


def extract_company_code(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Optional[str]:
    """Extract company code from input model.

    Priority:
    1. Explicit company_id field (already resolved)
    2. Chinese 公司代码 field
    3. Generate IN_* temporary ID from customer name

    For unresolved company names, generates a stable IN_<hash> format ID
    that can be resolved later via company enrichment service.
    """
    # Try explicit company_id field first (already resolved)
    if input_model.company_id:
        return str(input_model.company_id).strip()

    # Try Chinese field name
    if input_model.公司代码:
        return str(input_model.公司代码).strip()

    # Generate IN_* temporary ID from customer name
    # This provides a stable, deterministic ID for unresolved names
    if input_model.客户名称:
        customer = str(input_model.客户名称).strip()
        if customer:
            temp_id = generate_temp_company_id(customer)
            logger.debug(
                f"Row {row_index}: Generated temp company_id {temp_id} "
                f"for customer: {customer[:30]}..."
            )
            return temp_id

    logger.debug(f"Row {row_index}: No company code found")
    return None


def extract_financial_metrics(
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


def extract_metadata_fields(
    input_model: AnnuityPerformanceIn, row_index: int
) -> Dict[str, Any]:
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
        portfolio_code = strip_f_prefix_if_pattern_matches(input_model.组合代码)
        fields["组合代码"] = portfolio_code

    # Handle company_id separately
    if input_model.company_id:
        fields["company_id"] = input_model.company_id

    return fields


def pipeline_row_to_model(
    pipeline_row: Dict[str, Any], data_source: str, row_index: int
) -> Optional[AnnuityPerformanceOut]:
    """
    Convert pipeline-transformed row to validated domain model.

    This function takes the output from the pipeline transformation and converts
    it to the final AnnuityPerformanceOut model, applying the same validation
    and field extraction logic as the legacy path.

    Args:
        pipeline_row: Row dict after pipeline transformation
        data_source: Source file identifier
        row_index: Row number for error reporting

    Returns:
        Validated AnnuityPerformanceOut model or None if validation fails
    """
    try:
        # Create input model for extraction functions
        input_model = AnnuityPerformanceIn(**pipeline_row)

        # Extract required fields using existing logic
        report_date = extract_report_date(input_model, row_index)
        plan_code = extract_plan_code(input_model, row_index)
        company_code = extract_company_code(input_model, row_index)

        if not all([report_date, plan_code, company_code]):
            logger.debug(
                "Row %s: Missing required fields after pipeline transformation",
                row_index,
            )
            return None

        # Extract financial and metadata fields
        financial_metrics = extract_financial_metrics(input_model, row_index)
        metadata_fields = extract_metadata_fields(input_model, row_index)

        # Combine all fields for output model (use Chinese field names to match model)
        output_data = {
            "月度": report_date,
            "计划代码": plan_code,
            "company_id": company_code,  # For composite PK - matches database column
            **financial_metrics,
            **metadata_fields,
        }

        # Create and validate output model
        return AnnuityPerformanceOut(**output_data)

    except ValidationError as e:
        logger.debug(f"Row {row_index}: Pipeline output validation failed: {e}")
        return None
    except Exception as e:
        logger.warning(
            f"Row {row_index}: Unexpected error in pipeline model conversion: {e}"
        )
        return None


def apply_enrichment_integration(
    processed_record: AnnuityPerformanceOut,
    raw_row: Dict[str, Any],
    enrichment_service: "CompanyEnrichmentService",
    sync_lookup_budget: int,
    stats: EnrichmentStats,
    unknown_names: List[str],
    row_index: int,
) -> AnnuityPerformanceOut:
    """
    Apply enrichment service integration to a processed record.

    This function encapsulates the enrichment logic that is identical between
    legacy and pipeline paths, maintaining the exact same behavior.

    Args:
        processed_record: Already transformed domain model
        raw_row: Original raw Excel row dict
        enrichment_service: Company enrichment service instance
        sync_lookup_budget: Budget for synchronous EQC lookups
        stats: Enrichment statistics tracker
        unknown_names: List to collect unknown company names
        row_index: Row number for error reporting

    Returns:
        Updated domain model with enrichment results
    """
    try:
        # Call enrichment service with proper field mapping
        # Extract fields from raw_row since processed_record may not have all
        # original fields
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
            customer_name = raw_row.get("客户名称")
            if customer_name is not None:
                unknown_names.append(str(customer_name))

    except Exception as e:
        # CRITICAL: Never fail main pipeline on enrichment errors
        logger.warning(f"Enrichment failed for row {row_index}: {e}")
        stats.failed += 1

    return processed_record


__all__ = [
    # Processing functions
    "process_rows_via_pipeline",
    "validate_processing_results",
    "export_unknown_names_csv",
    "log_enrichment_stats",
    # Transformation functions
    "transform_single_row",
    "extract_report_date",
    "parse_report_period",
    "extract_plan_code",
    "extract_company_code",
    "extract_financial_metrics",
    "extract_metadata_fields",
    # Pipeline helpers
    "build_pipeline_with_mappings",
    "convert_pipeline_output_to_models",
    "pipeline_row_to_model",
    "apply_enrichment_integration",
    # Utilities
    "strip_f_prefix_if_pattern_matches",
    # Exceptions
    "AnnuityPerformanceTransformationError",
]
