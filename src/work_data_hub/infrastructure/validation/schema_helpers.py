"""Schema validation helper functions for DataFrame validation.

This module provides utility functions for Pandera schema validation
with consistent error formatting and common validation checks.

Migrated from: domain/pipelines/validation/helpers.py (Story 5.5)

Key Functions:
- raise_schema_error: Raise SchemaError with consistent formatting
- ensure_required_columns: Validate required columns are present
- ensure_not_empty: Validate DataFrame is not empty

Usage:
    >>> from work_data_hub.infrastructure.validation import (
    ...     raise_schema_error,
    ...     ensure_required_columns,
    ...     ensure_not_empty,
    ... )
    >>>
    >>> # Check required columns before validation
    >>> ensure_required_columns(schema, df, ['col1', 'col2'], 'BronzeSchema')
    >>>
    >>> # Check DataFrame is not empty
    >>> ensure_not_empty(schema, df, 'BronzeSchema')
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, List, NoReturn

import pandas as pd
from pandera.errors import SchemaError, SchemaErrors

if TYPE_CHECKING:
    import pandera.pandas as pa


def raise_schema_error(
    schema: "pa.DataFrameSchema",
    data: pd.DataFrame,
    message: str,
    failure_cases: pd.DataFrame | None = None,
) -> NoReturn:
    """Raise SchemaError with consistent formatting.

    This helper ensures all schema validation errors across domains have
    consistent structure and formatting for logging and error handling.

    Args:
        schema: The Pandera schema that failed validation
        data: The DataFrame that failed validation
        message: Human-readable error message
        failure_cases: Optional DataFrame with failure details

    Raises:
        SchemaError: Always raises with the provided details

    Example:
        >>> import pandera as pa
        >>> schema = pa.DataFrameSchema({'col': pa.Column(int)})
        >>> df = pd.DataFrame({'col': ['not_int']})
        >>> raise_schema_error(schema, df, "Type mismatch")
        Traceback (most recent call last):
            ...
        pandera.errors.SchemaError: Type mismatch
    """
    raise SchemaError(  # type: ignore[no-untyped-call]
        schema=schema,
        data=data,
        failure_cases=failure_cases,
        message=message,
    )


def ensure_required_columns(
    schema: "pa.DataFrameSchema",
    dataframe: pd.DataFrame,
    required: Iterable[str],
    schema_name: str = "Schema",
) -> None:
    """Ensure all required columns are present in the DataFrame.

    This check should be performed before schema validation to provide
    clear error messages about missing columns.

    Args:
        schema: The Pandera schema for error context
        dataframe: The DataFrame to validate
        required: Iterable of required column names
        schema_name: Human-readable schema name for error messages

    Raises:
        SchemaError: If any required columns are missing

    Example:
        >>> import pandera as pa
        >>> schema = pa.DataFrameSchema({'a': pa.Column(), 'b': pa.Column()})
        >>> df = pd.DataFrame({'a': [1]})
        >>> ensure_required_columns(schema, df, ['a', 'b'], 'TestSchema')
        Traceback (most recent call last):
            ...
        pandera.errors.SchemaError: TestSchema validation failed: ...
    """
    missing = [col for col in required if col not in dataframe.columns]
    if missing:
        failure_cases = pd.DataFrame({"column": missing, "failure": "missing"})
        raise_schema_error(
            schema,
            dataframe,
            message=(
                f"{schema_name} validation failed: missing required columns "
                f"{missing}, found columns: {list(dataframe.columns)}"
            ),
            failure_cases=failure_cases,
        )


def ensure_not_empty(
    schema: "pa.DataFrameSchema",
    dataframe: pd.DataFrame,
    schema_name: str = "Schema",
) -> None:
    """Ensure the DataFrame is not empty.

    This check should be performed before schema validation to provide
    clear error messages about empty DataFrames.

    Args:
        schema: The Pandera schema for error context
        dataframe: The DataFrame to validate
        schema_name: Human-readable schema name for error messages

    Raises:
        SchemaError: If the DataFrame is empty

    Example:
        >>> import pandera as pa
        >>> schema = pa.DataFrameSchema({'col': pa.Column()})
        >>> df = pd.DataFrame()
        >>> ensure_not_empty(schema, df, 'TestSchema')
        Traceback (most recent call last):
            ...
        pandera.errors.SchemaError: TestSchema validation failed: ...
    """
    if dataframe.empty:
        raise SchemaError(  # type: ignore[no-untyped-call]
            schema=schema,
            data=dataframe,
            message=f"{schema_name} validation failed: DataFrame cannot be empty",
        )


def get_schema_name(schema: "pa.DataFrameSchema") -> str:
    """Return a short schema name for error messages."""
    return (
        getattr(schema, "name", None)
        or getattr(schema, "__class__", type("", (), {})).__name__
    )


def format_schema_error_message(
    schema: "pa.DataFrameSchema", failure_cases: pd.DataFrame | None
) -> str:
    base = f"{get_schema_name(schema)} validation failed"
    if failure_cases is None or getattr(failure_cases, "empty", True):
        return base

    message_parts: List[str] = []
    if "column" in failure_cases.columns:
        columns = failure_cases["column"].dropna().astype(str).unique().tolist()
        if columns:
            message_parts.append(f"columns {columns[:5]}")

    if "failure_case" in failure_cases.columns:
        failure_values = (
            failure_cases["failure_case"].dropna().astype(str).head(5).tolist()
        )
        if failure_values:
            message_parts.append(f"failure cases {failure_values}")

    return f"{base}: " + "; ".join(message_parts) if message_parts else base


def track_invalid_ratio(
    column: str,
    invalid_rows: List[Any],
    dataframe: pd.DataFrame,
    schema: "pa.DataFrameSchema",
    threshold: float,
    reason: str,
) -> None:
    if not invalid_rows:
        return
    ratio = len(invalid_rows) / max(len(dataframe), 1)
    if ratio > threshold:
        failure_cases = pd.DataFrame({"column": column, "row_index": invalid_rows})
        raise_schema_error(
            schema,
            dataframe,
            message=(
                f"{reason}: column '{column}' has {ratio:.1%} invalid values "
                f"(rows {invalid_rows[:10]})"
            ),
            failure_cases=failure_cases,
        )


def ensure_non_null_columns(
    schema: "pa.DataFrameSchema",
    dataframe: pd.DataFrame,
    columns: Iterable[str],
) -> List[str]:
    empty_columns: List[str] = []
    for column in columns:
        if column in dataframe.columns and dataframe[column].notna().sum() == 0:
            empty_columns.append(column)
    if empty_columns:
        failure_cases = pd.DataFrame(
            {"column": empty_columns, "failure": "all values null"}
        )
        raise_schema_error(
            schema,
            dataframe,
            message=(
                f"{get_schema_name(schema)} validation failed: columns have no "
                f"non-null values {empty_columns}"
            ),
            failure_cases=failure_cases,
        )
    return empty_columns


def apply_schema_with_lazy_mode(
    schema: "pa.DataFrameSchema", dataframe: pd.DataFrame
) -> pd.DataFrame:
    try:
        return schema.validate(dataframe, lazy=True)
    except SchemaErrors as exc:
        message = format_schema_error_message(schema, exc.failure_cases)
        raise_schema_error(
            schema,
            dataframe,
            message=message,
            failure_cases=exc.failure_cases,
        )


__all__ = [
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
    "get_schema_name",
    "format_schema_error_message",
    "track_invalid_ratio",
    "ensure_non_null_columns",
    "apply_schema_with_lazy_mode",
]
