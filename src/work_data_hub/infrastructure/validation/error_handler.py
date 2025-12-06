"""Validation error handling and threshold checking utilities.

This module provides functions for handling validation errors from multiple
sources (Pandera, Pydantic) with consistent formatting and threshold checking.

Key Functions:
- handle_validation_errors: Check thresholds and log validation errors
- collect_error_details: Convert errors from various sources to structured format

Usage:
    >>> from work_data_hub.infrastructure.validation import (
    ...     handle_validation_errors,
    ...     collect_error_details,
    ...     ValidationThresholdExceeded,
    ... )
    >>>
    >>> try:
    ...     validated_df = schema.validate(df, lazy=True)
    ... except SchemaErrors as exc:
    ...     error_details = collect_error_details(exc)
    ...     handle_validation_errors(error_details, threshold=0.1, total_rows=len(df))
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List, Sequence, Union, cast

import structlog

from work_data_hub.infrastructure.validation.types import (
    ValidationErrorDetail,
    ValidationSummary,
    ValidationThresholdExceeded,
)

if TYPE_CHECKING:
    from pandera.errors import SchemaError, SchemaErrors
    from pydantic import ValidationError as PydanticValidationError

logger = structlog.get_logger(__name__)


def handle_validation_errors(
    errors: Union[
        "SchemaErrors",
        "SchemaError",
        List["PydanticValidationError"],
        Sequence[ValidationErrorDetail],
    ],
    threshold: float = 0.1,
    total_rows: int | None = None,
    domain: str = "unknown",
) -> ValidationSummary:
    """Check error thresholds and log validation errors.

    This function:
    1. Converts errors to structured ValidationErrorDetail format
    2. Calculates error statistics (failed rows, error rate)
    3. Logs validation summary with structured logging
    4. Raises ValidationThresholdExceeded if failure rate exceeds threshold

    Args:
        errors: Validation errors from Pandera, Pydantic, or pre-converted list
        threshold: Maximum acceptable error rate (default 10%)
        total_rows: Total number of rows processed (required for threshold check)
        domain: Domain name for logging context (e.g., 'annuity_performance')

    Returns:
        ValidationSummary with error statistics

    Raises:
        ValidationThresholdExceeded: If failure rate exceeds threshold
        ValueError: If total_rows is None or <= 0

    Example:
        >>> errors = [ValidationErrorDetail(0, 'field', 'type', 'msg', 'val')]
        >>> summary = handle_validation_errors(errors, threshold=0.1, total_rows=100)
        >>> summary.error_rate
        0.01
    """
    if total_rows is None or total_rows <= 0:
        raise ValueError("total_rows must be a positive integer")

    # Convert to structured format if needed
    error_details = collect_error_details(errors)

    # Calculate unique failed rows
    failed_row_indices = {e.row_index for e in error_details if e.row_index is not None}
    failed_rows = len(failed_row_indices)
    valid_rows = total_rows - failed_rows
    error_rate = failed_rows / total_rows

    summary = ValidationSummary(
        total_rows=total_rows,
        valid_rows=valid_rows,
        failed_rows=failed_rows,
        error_count=len(error_details),
        error_rate=error_rate,
    )

    # Log validation summary
    log = logger.bind(domain=domain, operation="validation")
    log.info(
        "validation_summary",
        total_rows=total_rows,
        failed_rows=failed_rows,
        error_count=len(error_details),
        error_rate=f"{error_rate:.1%}",
        threshold=f"{threshold:.1%}",
    )

    # Check threshold
    if error_rate >= threshold:
        log.error(
            "validation_threshold_exceeded",
            error_rate=f"{error_rate:.1%}",
            threshold=f"{threshold:.1%}",
            failed_rows=failed_rows,
        )
        raise ValidationThresholdExceeded(
            f"Validation failure rate {error_rate:.1%} exceeds "
            f"threshold {threshold:.1%}, likely systemic issue. "
            f"Failed {failed_rows}/{total_rows} rows.",
            error_rate=error_rate,
            threshold=threshold,
            failed_rows=failed_rows,
            total_rows=total_rows,
        )

    return summary


def collect_error_details(
    errors: Union[
        "SchemaErrors",
        "SchemaError",
        "PydanticValidationError",
        List["PydanticValidationError"],
        Sequence[ValidationErrorDetail],
    ],
    row_index: int | None = None,
) -> Sequence[ValidationErrorDetail]:
    """Convert validation errors from various sources to structured format.

    Supports:
    - Pandera SchemaErrors (lazy validation with multiple errors)
    - Pandera SchemaError (fail-fast single error)
    - Pydantic ValidationError (exception containing list of errors)
    - List of Pydantic ValidationErrors
    - Raw ValidationErrorDetail sequence (passthrough)

    Args:
        errors: Validation errors from any supported source
        row_index: Optional row index to associate with errors (useful for Pydantic)

    Returns:
        Sequence of ValidationErrorDetail with consistent structure

    Example:
        >>> # From Pandera SchemaErrors
        >>> try:
        ...     schema.validate(df, lazy=True)
        ... except SchemaErrors as exc:
        ...     details = collect_error_details(exc)
        >>>
        >>> # From Pydantic ValidationError
        >>> try:
        ...     Model(**data)
        ... except ValidationError as exc:
        ...     details = collect_error_details(exc, row_index=5)
    """
    # Passthrough for already-converted errors
    if isinstance(errors, (list, tuple)) and all(
        isinstance(e, ValidationErrorDetail) for e in errors
    ):
        return cast(Sequence[ValidationErrorDetail], errors)

    # Handle Pandera SchemaErrors (lazy validation)
    if _is_pandera_schema_errors(errors):
        return _collect_from_pandera_schema_errors(cast("SchemaErrors", errors))

    # Handle Pandera SchemaError (fail-fast)
    if _is_pandera_schema_error(errors):
        return _collect_from_pandera_schema_error(cast("SchemaError", errors))

    # Handle Pydantic ValidationError
    if _is_pydantic_validation_error(errors):
        return _collect_from_pydantic_error(
            cast("PydanticValidationError", errors), row_index=row_index
        )

    # Handle list of Pydantic ValidationErrors
    if isinstance(errors, list) and errors and _is_pydantic_validation_error(errors[0]):
        result: List[ValidationErrorDetail] = []
        for err in errors:
            result.extend(
                _collect_from_pydantic_error(
                    cast("PydanticValidationError", err), row_index=row_index
                )
            )
        return result

    # Unknown type - return empty
    logger.warning(
        "unknown_error_type",
        error_type=type(errors).__name__,
        message="Cannot collect error details from unknown error type",
    )
    return []


def _is_pandera_schema_errors(obj: Any) -> bool:
    """Check if object is Pandera SchemaErrors."""
    return type(obj).__name__ == "SchemaErrors"


def _is_pandera_schema_error(obj: Any) -> bool:
    """Check if object is Pandera SchemaError."""
    return type(obj).__name__ == "SchemaError"


def _is_pydantic_validation_error(obj: Any) -> bool:
    """Check if object is Pydantic ValidationError."""
    return type(obj).__name__ == "ValidationError" and hasattr(obj, "errors")


def _collect_from_pandera_schema_errors(
    exc: "SchemaErrors",
) -> List[ValidationErrorDetail]:
    """Extract error details from Pandera SchemaErrors.

    SchemaErrors contains a failure_cases DataFrame with columns:
    - index: row index (can be None for schema-level errors)
    - column: field name
    - check: check name that failed
    - failure_case: the value that failed

    Args:
        exc: Pandera SchemaErrors exception

    Returns:
        List of ValidationErrorDetail
    """
    result: List[ValidationErrorDetail] = []

    # Access failure_cases DataFrame
    failure_cases = getattr(exc, "failure_cases", None)
    if failure_cases is None or failure_cases.empty:
        return result

    for _, row in failure_cases.iterrows():
        # Extract row index - handle various column names
        row_index = None
        for idx_col in ["index", "row_index", "row"]:
            if idx_col in row.index:
                idx_val = row[idx_col]
                if idx_val is not None and not _is_nan(idx_val):
                    row_index = int(idx_val)
                break

        # Extract field name
        field_name = str(row.get("column", row.get("field", "unknown")))

        # Extract check name as error type
        error_type = str(row.get("check", "SchemaError"))

        # Build error message
        error_message = f"Check '{error_type}' failed"
        if "failure_case" in row.index:
            error_message = f"{error_message} for value: {row['failure_case']}"

        # Extract original value
        original_value = row.get("failure_case", None)

        result.append(
            ValidationErrorDetail(
                row_index=row_index,
                field_name=field_name,
                error_type=error_type,
                error_message=error_message,
                original_value=original_value,
            )
        )

    return result


def _collect_from_pandera_schema_error(
    exc: "SchemaError",
) -> List[ValidationErrorDetail]:
    """Extract error details from Pandera SchemaError (fail-fast).

    Args:
        exc: Pandera SchemaError exception

    Returns:
        List of ValidationErrorDetail (usually single item)
    """
    result: List[ValidationErrorDetail] = []

    # Get failure cases if available
    failure_cases = getattr(exc, "failure_cases", None)
    # Check if failure_cases is a DataFrame (not None, not string, has empty attr)
    has_empty = hasattr(failure_cases, "empty")
    if failure_cases is not None and has_empty and not failure_cases.empty:
        for _, row in failure_cases.iterrows():
            row_index = None
            if "index" in row.index:
                idx_val = row["index"]
                if idx_val is not None and not _is_nan(idx_val):
                    row_index = int(idx_val)

            result.append(
                ValidationErrorDetail(
                    row_index=row_index,
                    field_name=str(row.get("column", "unknown")),
                    error_type="SchemaError",
                    error_message=str(exc),
                    original_value=row.get("failure_case", None),
                )
            )
    else:
        # No failure cases - create single error from exception message
        result.append(
            ValidationErrorDetail(
                row_index=None,
                field_name="unknown",
                error_type="SchemaError",
                error_message=str(exc),
                original_value=None,
            )
        )

    return result


def _collect_from_pydantic_error(
    exc: "PydanticValidationError",
    row_index: int | None = None,
) -> List[ValidationErrorDetail]:
    """Extract error details from Pydantic ValidationError.

    Pydantic ValidationError.errors() returns list of dicts with:
    - loc: tuple of field path (e.g., ('field_name',) or ('nested', 'field'))
    - msg: error message
    - type: error type (e.g., 'value_error', 'type_error')
    - input: the input value that failed (Pydantic v2)
    - ctx: additional context (optional)

    Args:
        exc: Pydantic ValidationError exception
        row_index: Optional row index to associate with errors

    Returns:
        List of ValidationErrorDetail
    """
    result: List[ValidationErrorDetail] = []

    for error in exc.errors():
        # Extract field name from location tuple
        loc = error.get("loc", ())
        field_name = ".".join(str(part) for part in loc) if loc else "unknown"

        # Extract error type and message
        error_type = str(error.get("type", "validation_error"))
        error_message = str(error.get("msg", "Validation failed"))

        # Extract original value (Pydantic v2 uses 'input')
        original_value = error.get("input", error.get("ctx", {}).get("given", None))

        result.append(
            ValidationErrorDetail(
                row_index=row_index,
                field_name=field_name,
                error_type=error_type,
                error_message=error_message,
                original_value=original_value,
            )
        )

    return result


def _is_nan(value: Any) -> bool:
    """Check if value is NaN (handles pandas NA and numpy nan)."""
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):
        pass

    # Check for pandas NA
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (ImportError, TypeError, ValueError):
        pass

    return False


__all__ = [
    "handle_validation_errors",
    "collect_error_details",
]
