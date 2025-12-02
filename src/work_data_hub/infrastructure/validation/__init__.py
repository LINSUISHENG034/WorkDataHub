"""Validation Error Handling and Reporting Infrastructure.

Provides utilities for validation error handling, aggregation, and reporting
across all data quality validation layers (Pydantic, Pandera, custom rules).

This module consolidates validation utilities from scattered domain implementations
into a centralized infrastructure layer with a clean, reusable API.

Components:
- types: Shared types (ValidationErrorDetail, ValidationSummary, etc.)
- error_handler: Error handling and threshold checking utilities
- report_generator: CSV export and summary report generation
- schema_helpers: Pandera schema validation helpers

Usage:
    >>> from work_data_hub.infrastructure.validation import (
    ...     # Error handling
    ...     handle_validation_errors,
    ...     collect_error_details,
    ...     # Report generation
    ...     export_error_csv,
    ...     export_error_details_csv,
    ...     export_validation_summary,
    ...     # Schema helpers
    ...     raise_schema_error,
    ...     ensure_required_columns,
    ...     ensure_not_empty,
    ...     # Types
    ...     ValidationErrorDetail,
    ...     ValidationSummary,
    ...     ValidationThresholdExceeded,
    ... )
    >>>
    >>> # Example: Handle Pandera validation errors
    >>> try:
    ...     validated_df = schema.validate(df, lazy=True)
    ... except SchemaErrors as exc:
    ...     error_details = collect_error_details(exc)
    ...     export_error_csv(df.iloc[...], "bronze_validation")
    ...     handle_validation_errors(error_details, total_rows=len(df))
"""

# Types
# Error handling
from work_data_hub.infrastructure.validation.error_handler import (
    collect_error_details,
    handle_validation_errors,
)

# Report generation
from work_data_hub.infrastructure.validation.report_generator import (
    export_error_csv,
    export_error_details_csv,
    export_validation_summary,
)

# Schema helpers
from work_data_hub.infrastructure.validation.schema_helpers import (
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)
from work_data_hub.infrastructure.validation.types import (
    ValidationErrorDetail,
    ValidationSummary,
    ValidationThresholdExceeded,
)

__all__ = [
    # Types
    "ValidationErrorDetail",
    "ValidationSummary",
    "ValidationThresholdExceeded",
    # Error handling
    "handle_validation_errors",
    "collect_error_details",
    # Report generation
    "export_error_csv",
    "export_error_details_csv",
    "export_validation_summary",
    # Schema helpers
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
]
