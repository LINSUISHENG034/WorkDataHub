"""
Generic validation helper functions for DataFrame schema validation.

Story 4.8: Extracted from annuity_performance/schemas.py for reuse across
multiple domains (annuity_performance, Epic 9 domains, etc.).

These helpers provide consistent validation behavior and error formatting
for Pandera schema validation across all domain modules.
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
    """
    Raise SchemaError with consistent formatting.

    This helper ensures all schema validation errors across domains have
    consistent structure and formatting for logging and error handling.

    Args:
        schema: The Pandera schema that failed validation
        data: The DataFrame that failed validation
        message: Human-readable error message
        failure_cases: Optional DataFrame with failure details

    Raises:
        SchemaError: Always raises with the provided details
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
    """
    Ensure all required columns are present in the DataFrame.

    Args:
        schema: The Pandera schema for error context
        dataframe: The DataFrame to validate
        required: Iterable of required column names
        schema_name: Human-readable schema name for error messages

    Raises:
        SchemaError: If any required columns are missing
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
    """
    Ensure the DataFrame is not empty.

    Args:
        schema: The Pandera schema for error context
        dataframe: The DataFrame to validate
        schema_name: Human-readable schema name for error messages

    Raises:
        SchemaError: If the DataFrame is empty
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
