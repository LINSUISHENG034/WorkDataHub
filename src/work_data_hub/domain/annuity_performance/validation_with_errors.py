"""Validation integration with error reporting and structured logging.

This module demonstrates how to integrate ValidationErrorReporter (Story 2.5)
with existing validation layers (Stories 2.1-2.2) to collect errors, export
failed rows to CSV, and log validation metrics.

Usage Example:
    >>> from work_data_hub.utils.error_reporter import ValidationErrorReporter
    >>> from work_data_hub.utils.logging import get_logger
    >>>
    >>> reporter = ValidationErrorReporter()
    >>> logger = get_logger(__name__)
    >>>
    >>> # Run validation pipeline with error collection
    >>> result_df = validate_with_error_reporting(
    ...     input_df,
    ...     domain='annuity_performance',
    ...     reporter=reporter,
    ...     logger=logger
    ... )
    >>>
    >>> # Export failed rows if any
    >>> if reporter.errors:
    ...     reporter.export_to_csv(
    ...         Path('logs/failed_rows_annuity_20251127.csv'),
    ...         len(input_df),
    ...         'annuity_performance',
    ...         duration_seconds
    ...     )
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
import pandera as pa
from pydantic import ValidationError as PydanticValidationError

if TYPE_CHECKING:
    from work_data_hub.utils.error_reporter import (
        ValidationErrorReporter,
        ValidationSummary,
    )

from work_data_hub.domain.annuity_performance.models import AnnuityPerformanceOut
from work_data_hub.domain.annuity_performance.schemas import (
    BronzeAnnuitySchema,
    GoldAnnuitySchema,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def validate_bronze_with_errors(
    df: pd.DataFrame,
    reporter: Optional[ValidationErrorReporter] = None,
    failure_threshold: float = 0.50,
) -> pd.DataFrame:
    """Validate Bronze schema with error collection.

    This wraps the existing validate_bronze_dataframe() function (Story 2.2)
    and collects validation errors into the reporter for CSV export.

    Args:
        df: Raw DataFrame from Excel
        reporter: Optional ValidationErrorReporter to collect errors
        failure_threshold: Maximum ratio of invalid rows before raising (default 0.50 = 50%)

    Returns:
        Validated DataFrame (may have fewer rows if errors filtered)

    Example:
        >>> reporter = ValidationErrorReporter()
        >>> validated_df = validate_bronze_with_errors(raw_df, reporter)
        >>> print(f"Failed rows: {len(reporter.errors)}")
    """
    try:
        # Use existing Bronze validation from Story 2.2
        # Pass higher threshold to allow error collection before failing
        validated_df, summary = validate_bronze_dataframe(df, failure_threshold=failure_threshold)

        # If reporter provided, collect errors from summary
        if reporter:
            # Collect date parsing errors
            for row_idx in summary.invalid_date_rows:
                reporter.collect_error(
                    row_index=row_idx,
                    field_name="月度",
                    error_type="SchemaError",
                    error_message="Cannot parse date field",
                    original_value=df.iloc[row_idx]["月度"],
                )

            # Collect numeric coercion errors
            for column, invalid_rows in summary.numeric_error_rows.items():
                for row_idx in invalid_rows:
                    reporter.collect_error(
                        row_index=row_idx,
                        field_name=column,
                        error_type="SchemaError",
                        error_message=f"Cannot coerce to numeric",
                        original_value=df.iloc[row_idx][column],
                    )

        return validated_df

    except pa.errors.SchemaError as e:
        # Pandera SchemaError - collect all failure cases
        if reporter and hasattr(e, "failure_cases"):
            for _, failure in e.failure_cases.iterrows():
                reporter.collect_error(
                    row_index=failure.get("index", -1),
                    field_name=str(failure.get("column", "unknown")),
                    error_type="SchemaError",
                    error_message=str(failure.get("check", "Schema validation failed")),
                    original_value=failure.get("failure_case", ""),
                )

        raise


def validate_pydantic_with_errors(
    df: pd.DataFrame,
    reporter: Optional[ValidationErrorReporter] = None,
) -> List[AnnuityPerformanceOut]:
    """Validate each row with Pydantic models and collect errors.

    This demonstrates row-level validation (Story 2.1) with error collection.
    Continues processing valid rows even when some fail (partial success).

    Args:
        df: DataFrame to validate
        reporter: Optional ValidationErrorReporter to collect errors

    Returns:
        List of validated Pydantic model instances (only valid rows)

    Example:
        >>> reporter = ValidationErrorReporter()
        >>> valid_models = validate_pydantic_with_errors(df, reporter)
        >>> print(f"Valid: {len(valid_models)}, Failed: {len(reporter.errors)}")
    """
    validated_rows: List[AnnuityPerformanceOut] = []

    for idx, row_dict in df.iterrows():
        try:
            # Validate single row with Pydantic model (Story 2.1)
            validated_model = AnnuityPerformanceOut(**row_dict)
            validated_rows.append(validated_model)

        except PydanticValidationError as e:
            # Collect all field-level errors from this row
            if reporter:
                for error in e.errors():
                    field_name = error["loc"][0] if error["loc"] else "unknown"
                    reporter.collect_error(
                        row_index=int(idx),  # type: ignore
                        field_name=str(field_name),
                        error_type="ValidationError",
                        error_message=error["msg"],
                        original_value=error.get("input", ""),
                    )

    # Check threshold after all rows processed
    if reporter:
        reporter.check_threshold(total_rows=len(df))

    return validated_rows


def validate_gold_with_errors(
    df: pd.DataFrame,
    reporter: Optional[ValidationErrorReporter] = None,
) -> pd.DataFrame:
    """Validate Gold schema with error collection.

    This wraps the existing validate_gold_dataframe() function (Story 2.2)
    and collects validation errors for composite PK uniqueness checks.

    Args:
        df: DataFrame of validated Pydantic models
        reporter: Optional ValidationErrorReporter to collect errors

    Returns:
        Validated DataFrame ready for database loading

    Example:
        >>> reporter = ValidationErrorReporter()
        >>> gold_df = validate_gold_with_errors(silver_df, reporter)
    """
    try:
        # Use existing Gold validation from Story 2.2
        validated_df, summary = validate_gold_dataframe(df)
        return validated_df

    except pa.errors.SchemaError as e:
        # Collect Gold schema errors (PK uniqueness violations, etc.)
        if reporter and hasattr(e, "failure_cases"):
            for _, failure in e.failure_cases.iterrows():
                reporter.collect_error(
                    row_index=failure.get("index", -1),
                    field_name=str(failure.get("column", "unknown")),
                    error_type="SchemaError",
                    error_message=str(failure.get("check", "Gold schema validation failed")),
                    original_value=failure.get("failure_case", ""),
                )

        raise


def validate_with_error_reporting(
    df: pd.DataFrame,
    domain: str,
    reporter: Optional[ValidationErrorReporter] = None,
    export_errors: bool = True,
) -> pd.DataFrame:
    """Run full validation pipeline with error reporting and structured logging.

    This demonstrates the complete integration of:
    - Bronze validation (Story 2.2)
    - Silver validation (Story 2.1)
    - Gold validation (Story 2.2)
    - Error collection and CSV export (Story 2.5)
    - Structured logging for validation metrics (Story 1.3 + 2.5)

    Args:
        df: Raw DataFrame from Excel
        domain: Domain name (e.g., 'annuity_performance')
        reporter: Optional ValidationErrorReporter (creates one if not provided)
        export_errors: Whether to export errors to CSV (default True)

    Returns:
        Validated DataFrame ready for database loading

    Raises:
        ValidationThresholdExceeded: If error rate >= 10%

    Example:
        >>> result_df = validate_with_error_reporting(
        ...     raw_df,
        ...     domain='annuity_performance',
        ...     export_errors=True
        ... )
    """
    # Create reporter if not provided
    if reporter is None:
        from work_data_hub.utils.error_reporter import ValidationErrorReporter

        reporter = ValidationErrorReporter()

    start_time = time.time()

    # Log validation start (Story 1.3 structured logging)
    logger.info(
        "validation.started",
        domain=domain,
        total_rows=len(df),
    )

    try:
        # Bronze Layer - Structural validation
        logger.info("validation.bronze.started", domain=domain, rows=len(df))
        bronze_df = validate_bronze_with_errors(df, reporter)
        logger.info(
            "validation.bronze.completed",
            domain=domain,
            input_rows=len(df),
            output_rows=len(bronze_df),
        )

        # Silver Layer - Business rules validation (row-by-row)
        logger.info("validation.silver.started", domain=domain, rows=len(bronze_df))
        validated_models = validate_pydantic_with_errors(bronze_df, reporter)
        logger.info(
            "validation.silver.completed",
            domain=domain,
            input_rows=len(bronze_df),
            valid_rows=len(validated_models),
        )

        # Convert back to DataFrame
        silver_df = pd.DataFrame([model.model_dump() for model in validated_models])

        # Gold Layer - Database integrity validation
        logger.info("validation.gold.started", domain=domain, rows=len(silver_df))
        gold_df = validate_gold_with_errors(silver_df, reporter)
        logger.info(
            "validation.gold.completed",
            domain=domain,
            input_rows=len(silver_df),
            output_rows=len(gold_df),
        )

        # Calculate duration
        duration = time.time() - start_time

        # Get validation summary
        summary = reporter.get_summary(len(df))

        # Log validation success with metrics
        logger.info(
            "validation.completed",
            domain=domain,
            total_rows=summary.total_rows,
            valid_rows=summary.valid_rows,
            failed_rows=summary.failed_rows,
            error_count=summary.error_count,
            error_rate=summary.error_rate,
            duration_seconds=round(duration, 2),
        )

        # Export failed rows if any errors and export enabled
        if export_errors and summary.failed_rows > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = Path(f"logs/failed_rows_{domain}_{timestamp}.csv")
            reporter.export_to_csv(csv_path, len(df), domain, duration)

            logger.info(
                "validation.errors_exported",
                domain=domain,
                csv_path=str(csv_path),
                failed_rows=summary.failed_rows,
                error_count=summary.error_count,
            )

        return gold_df

    except Exception as e:
        # Log validation failure
        duration = time.time() - start_time
        summary = reporter.get_summary(len(df))

        logger.error(
            "validation.failed",
            domain=domain,
            error_type=type(e).__name__,
            error_message=str(e),
            failed_rows=summary.failed_rows,
            error_rate=summary.error_rate,
            duration_seconds=round(duration, 2),
        )

        # Still export errors for debugging
        if export_errors and summary.failed_rows > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = Path(f"logs/failed_rows_{domain}_{timestamp}.csv")
            reporter.export_to_csv(csv_path, len(df), domain, duration)

        raise
