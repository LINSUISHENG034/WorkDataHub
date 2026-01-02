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
- domain_validators: Registry-driven validation for bronze/gold layers (Story 6.2-P13)

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
    ...     # Domain validators (Story 6.2-P13)
    ...     validate_bronze_layer,
    ...     validate_gold_layer,
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
    export_failed_records,
    handle_validation_errors,
)

# Unified failure logging (Story 7.5-5)
from work_data_hub.infrastructure.validation.failed_record import (
    ErrorType,
    FailedRecord,
)
from work_data_hub.infrastructure.validation.failure_exporter import (
    FailureExporter,
    generate_session_id,
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

# Domain validators (Story 6.2-P13) - Lazy import to avoid circular dependency
# These are imported via __getattr__ to break the import cycle


def __getattr__(name: str):
    """Lazy import domain_validators to avoid circular import.

    The domain_validators module imports transforms, which imports domain.pipelines,
    which imports domain.pipelines.validation, creating a circular dependency.
    By importing lazily, we break this cycle.

    Story 7.5-5: Fixed circular import exposed by new validation infrastructure.
    """
    if name in {
        "validate_bronze_dataframe",
        "validate_bronze_layer",
        "validate_gold_dataframe",
        "validate_gold_layer",
    }:
        from work_data_hub.infrastructure.validation import domain_validators

        return getattr(domain_validators, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Types
    "ValidationErrorDetail",
    "ValidationSummary",
    "ValidationThresholdExceeded",
    # Error handling
    "handle_validation_errors",
    "collect_error_details",
    "export_failed_records",
    # Unified failure logging (Story 7.5-5)
    "ErrorType",
    "FailedRecord",
    "FailureExporter",
    "generate_session_id",
    # Report generation
    "export_error_csv",
    "export_error_details_csv",
    "export_validation_summary",
    # Schema helpers
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
    # Domain validators (Story 6.2-P13)
    "validate_bronze_dataframe",
    "validate_bronze_layer",
    "validate_gold_dataframe",
    "validate_gold_layer",
]
