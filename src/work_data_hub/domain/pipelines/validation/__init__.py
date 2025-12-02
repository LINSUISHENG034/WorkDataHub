"""
Shared validation utilities for DataFrame schema validation.

Story 4.8: This module provides generic validation helpers and base classes
that can be reused across multiple domains (annuity_performance, Epic 9, etc.).

Story 5.5: Schema helpers migrated to infrastructure/validation/. This module
re-exports them for backward compatibility and provides domain-specific base classes.

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

# Re-export from infrastructure (Story 5.5 migration)
from work_data_hub.infrastructure.validation import (
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)

# Domain-specific base classes (remain in domain layer)
from .summaries import ValidationSummaryBase

__all__ = [
    # Validation helpers (from infrastructure)
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
    # Base classes (domain layer)
    "ValidationSummaryBase",
]
