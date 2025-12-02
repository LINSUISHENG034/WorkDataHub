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

from typing import TYPE_CHECKING, Iterable

import pandas as pd
from pandera.errors import SchemaError

if TYPE_CHECKING:
    import pandera as pa


def raise_schema_error(
    schema: "pa.DataFrameSchema",
    data: pd.DataFrame,
    message: str,
    failure_cases: pd.DataFrame | None = None,
) -> SchemaError:
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
    raise SchemaError(
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
        raise SchemaError(
            schema=schema,
            data=dataframe,
            message=f"{schema_name} validation failed: DataFrame cannot be empty",
        )


__all__ = [
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
]
