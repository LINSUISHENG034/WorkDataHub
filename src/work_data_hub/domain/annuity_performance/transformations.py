"""Bronze → Silver transformation pipeline for annuity performance domain.

This module implements the transformation pipeline that validates raw annuity data
through Bronze and Silver layers with comprehensive error handling. It integrates:
- Bronze validation (Story 4.2): DataFrame-level structural checks
- Silver validation (Story 4.1): Row-level business rule validation
- Error collection and export (Epic 2 Story 2.5): Failed rows CSV export
- Partial success handling (Architecture Decision #6): <10% failure threshold

The pipeline follows the Hybrid Pipeline Step Protocol (Architecture Decision #3):
1. Bronze validation: Fast DataFrame-level checks (pandera)
2. Silver validation: Detailed row-level checks (Pydantic)
3. Error export: Actionable error details for debugging

Usage Example:
    >>> from work_data_hub.domain.annuity_performance.transformations import (
    ...     transform_bronze_to_silver,
    ...     TransformationResult
    ... )
    >>>
    >>> # Transform raw DataFrame from Epic 3 FileDiscoveryService
    >>> result = transform_bronze_to_silver(raw_df, output_dir="output/errors")
    >>>
    >>> # Access results
    >>> print(f"Valid rows: {result.valid_count}/{result.row_count}")
    >>> print(f"Failed rows: {result.failed_count} ({result.failed_count/result.row_count:.1%})")
    >>> if result.error_file_path:
    ...     print(f"Error details: {result.error_file_path}")
    >>>
    >>> # Use valid DataFrame for Gold layer (Story 4.4)
    >>> gold_df = project_to_gold_layer(result.valid_df)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import AliasChoices, ValidationError as PydanticValidationError

from work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
)
from work_data_hub.domain.annuity_performance.schemas import validate_bronze_dataframe
from work_data_hub.utils.error_reporter import ValidationErrorReporter
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TransformationResult:
    """Result of Bronze → Silver transformation pipeline.

    This dataclass encapsulates the outcome of the transformation pipeline,
    providing both the valid DataFrame and comprehensive error statistics.

    Attributes:
        valid_df: DataFrame containing only rows that passed validation
        row_count: Total number of rows in input DataFrame
        valid_count: Number of rows that passed validation
        failed_count: Number of rows that failed validation
        error_file_path: Path to CSV file with error details (None if no errors)

    Example:
        >>> result = TransformationResult(
        ...     valid_df=pd.DataFrame([...]),
        ...     row_count=100,
        ...     valid_count=95,
        ...     failed_count=5,
        ...     error_file_path="output/errors/annuity_errors_20251129_103000.csv"
        ... )
        >>> print(f"Success rate: {result.valid_count/result.row_count:.1%}")
        Success rate: 95.0%
    """

    valid_df: pd.DataFrame
    row_count: int
    valid_count: int
    failed_count: int
    error_file_path: Optional[str] = None


def transform_bronze_to_silver(
    raw_df: pd.DataFrame,
    output_dir: str = "output/errors"
) -> TransformationResult:
    """Transform raw annuity DataFrame from Bronze to Silver layer.

    This function implements the complete Bronze → Silver transformation pipeline
    with comprehensive error handling and partial success support. It follows the
    Hybrid Pipeline Step Protocol (Architecture Decision #3):

    Pipeline Steps:
        1. Bronze Validation: Fast DataFrame-level structural checks
           - Validates required columns present
           - Validates numeric column types
           - Detects systemic data issues (>10% invalid)
           - Raises SchemaError immediately on failure

        2. Silver Validation: Detailed row-level business rules
           - Parses each row with AnnuityPerformanceIn (loose validation)
           - Applies date parsing (parse_yyyymm_or_chinese)
           - Applies numeric cleaning (CleansingRegistry)
           - Validates with AnnuityPerformanceOut (strict business rules)
           - Collects errors with row numbers and field details
           - Continues processing valid rows (partial success)

        3. Error Handling: Threshold checking and export
           - Calculates failure rate: failed_count / total_count
           - Raises ValueError if >10% rows fail (systemic issue)
           - Exports failed rows to CSV with error details
           - Returns valid DataFrame and error summary

    Args:
        raw_df: Raw DataFrame from Epic 3 FileDiscoveryService
        output_dir: Directory for error CSV export (default: "output/errors")

    Returns:
        TransformationResult with valid DataFrame and error summary

    Raises:
        SchemaError: If Bronze validation fails (systemic structural issue)
        ValueError: If >10% rows fail Silver validation (systemic data issue)

    Example:
        >>> # Successful transformation with partial failures
        >>> result = transform_bronze_to_silver(raw_df)
        >>> print(f"Processed {result.row_count} rows: "
        ...       f"{result.valid_count} valid ({result.valid_count/result.row_count:.1%}), "
        ...       f"{result.failed_count} failed ({result.failed_count/result.row_count:.1%})")
        Processed 33615 rows: 33500 valid (99.7%), 115 failed (0.3%)

        >>> # Access error details
        >>> if result.error_file_path:
        ...     print(f"Error details exported to: {result.error_file_path}")
        Error details exported to: output/errors/annuity_errors_20251129_103000.csv

    Notes:
        - Bronze validation uses pandera schema (Story 4.2)
        - Silver validation uses Pydantic models (Story 4.1)
        - Error export uses ValidationErrorReporter (Epic 2 Story 2.5)
        - Partial success threshold: <10% failure (Architecture Decision #6)
        - Performance target: <1ms per row for Silver validation
    """
    start_time = time.time()
    total_count = len(raw_df)

    # Log transformation start
    logger.info(
        "transformation.bronze_to_silver.started",
        domain="annuity_performance",
        total_rows=total_count,
    )

    # 空 DataFrame 无需继续处理，直接返回空结果，避免 Pandera 抛错
    if total_count == 0:
        logger.info(
            "transformation.bronze_to_silver.skipped_empty_input",
            domain="annuity_performance",
        )
        return TransformationResult(
            valid_df=pd.DataFrame(),
            row_count=0,
            valid_count=0,
            failed_count=0,
            error_file_path=None,
        )

    # Initialize error reporter
    reporter = ValidationErrorReporter()

    try:
        # Step 1: Bronze validation (fast fail for systemic issues)
        logger.info(
            "transformation.bronze.started",
            domain="annuity_performance",
            rows=total_count,
        )

        # Use existing Bronze validation from Story 4.2
        # This validates DataFrame structure and raises SchemaError on failure
        validated_df, bronze_summary = validate_bronze_dataframe(raw_df)

        logger.info(
            "transformation.bronze.completed",
            domain="annuity_performance",
            input_rows=total_count,
            output_rows=len(validated_df),
            invalid_date_rows=len(bronze_summary.invalid_date_rows),
            numeric_error_count=sum(len(rows) for rows in bronze_summary.numeric_error_rows.values()),
        )

        # Step 2: Silver row-by-row transformation
        logger.info(
            "transformation.silver.started",
            domain="annuity_performance",
            rows=len(validated_df),
        )

        valid_rows = []
        failed_count = 0

        for idx, row in validated_df.iterrows():
            try:
                # Parse with loose validation (AnnuityPerformanceIn)
                # This handles date parsing and numeric cleaning automatically
                row_dict = {
                    key: (None if pd.isna(value) else value)
                    for key, value in row.to_dict().items()
                }
                in_model = AnnuityPerformanceIn.model_validate(row_dict)

                # Get the dumped data from In model with aliases
                # Use by_alias=True to get the correct field names for Out model
                in_data = in_model.model_dump(by_alias=True, exclude_none=False)

                # Filter to only fields that exist in AnnuityPerformanceOut
                # This is necessary because Out model has extra="forbid"
                # and In model has extra="allow" with additional fields
                # Get all field names including aliases
                out_field_names = set()
                for field_name, field_info in AnnuityPerformanceOut.model_fields.items():
                    out_field_names.add(field_name)
                    validation_alias = getattr(field_info, "validation_alias", None)
                    if validation_alias:
                        if isinstance(validation_alias, AliasChoices):
                            out_field_names.update(validation_alias.choices)
                        else:
                            out_field_names.add(validation_alias)
                    alias_name = getattr(field_info, "alias", None)
                    if alias_name:
                        out_field_names.add(alias_name)

                filtered_data = {k: v for k, v in in_data.items() if k in out_field_names}

                # Validate with strict business rules (AnnuityPerformanceOut)
                # This enforces ge=0 constraints, non-empty company_id, etc.
                out_model = AnnuityPerformanceOut.model_validate(filtered_data)

                # Collect valid row (use by_alias to match database column names)
                valid_rows.append(out_model.model_dump(by_alias=True))

            except PydanticValidationError as e:
                # Collect error details for CSV export
                failed_count += 1

                # Extract all field-level errors from this row
                for error in e.errors():
                    field_name = str(error["loc"][0]) if error["loc"] else "unknown"
                    error_message = error["msg"]
                    original_value = error.get("input", row_dict.get(field_name, ""))

                    reporter.collect_error(
                        row_index=int(idx),  # type: ignore
                        field_name=field_name,
                        error_type="ValidationError",
                        error_message=error_message,
                        original_value=original_value,
                    )

        valid_count = len(valid_rows)

        logger.info(
            "transformation.silver.completed",
            domain="annuity_performance",
            input_rows=len(validated_df),
            valid_rows=valid_count,
            failed_rows=failed_count,
        )

        # Step 3: Check failure threshold (Architecture Decision #6)
        failure_rate = failed_count / total_count if total_count > 0 else 0.0

        if failure_rate > 0.10:
            # Systemic issue detected - fail pipeline
            error_msg = (
                f"Transformation failed: {failure_rate:.1%} of rows invalid "
                f"(likely systemic issue). Failed {failed_count}/{total_count} rows."
            )
            logger.error(
                "transformation.threshold_exceeded",
                domain="annuity_performance",
                failure_rate=failure_rate,
                failed_count=failed_count,
                total_count=total_count,
                threshold=0.10,
            )
            raise ValueError(error_msg)

        # Step 4: Export errors if any (partial success allowed)
        error_file_path = None
        if failed_count > 0:
            # Generate timestamped error file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            error_file = output_path / f"annuity_errors_{timestamp}.csv"

            # Export errors using ValidationErrorReporter
            duration = time.time() - start_time
            reporter.export_to_csv(
                filepath=error_file,
                total_rows=total_count,
                domain="annuity_performance",
                duration_seconds=duration,
            )

            error_file_path = str(error_file)

            logger.warning(
                "transformation.partial_success",
                domain="annuity_performance",
                valid_count=valid_count,
                failed_count=failed_count,
                failure_rate=failure_rate,
                error_file=error_file_path,
            )

        # Step 5: Assemble result
        valid_df = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()

        duration = time.time() - start_time

        # Log success summary
        logger.info(
            "transformation.bronze_to_silver.completed",
            domain="annuity_performance",
            total_rows=total_count,
            valid_rows=valid_count,
            failed_rows=failed_count,
            success_rate=valid_count / total_count if total_count > 0 else 0.0,
            duration_seconds=round(duration, 2),
            rows_per_second=int(total_count / duration) if duration > 0 else 0,
        )

        return TransformationResult(
            valid_df=valid_df,
            row_count=total_count,
            valid_count=valid_count,
            failed_count=failed_count,
            error_file_path=error_file_path,
        )

    except Exception as e:
        # Log transformation failure
        duration = time.time() - start_time

        logger.error(
            "transformation.bronze_to_silver.failed",
            domain="annuity_performance",
            error_type=type(e).__name__,
            error_message=str(e),
            duration_seconds=round(duration, 2),
        )

        raise
