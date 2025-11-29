"""
Shared validation utilities for DataFrame schema validation.

Story 4.8: This module provides generic validation helpers and base classes
that can be reused across multiple domains (annuity_performance, Epic 9, etc.).

Usage Example:
    from work_data_hub.domain.pipelines.validation import (
        ensure_required_columns,
        ensure_not_empty,
        raise_schema_error,
        ValidationSummaryBase,
    )

    # In domain-specific schema validation
    ensure_not_empty(schema, dataframe, "Bronze")
    ensure_required_columns(schema, dataframe, REQUIRED_COLUMNS, "Bronze")
"""

from .helpers import (
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)
from .summaries import ValidationSummaryBase

__all__ = [
    # Validation helpers
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
    # Base classes
    "ValidationSummaryBase",
]
