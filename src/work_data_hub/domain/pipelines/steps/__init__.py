"""
Row-level pipeline transformation steps for WorkDataHub.

NOTE: DataFrame steps have been migrated to infrastructure/transforms/ (Story 5.6).
Import DataFrame steps from:
    from work_data_hub.infrastructure.transforms import MappingStep, FilterStep, ...

This module only contains row-level transformation steps that are domain-specific.

Available Steps:
    Row-Level Steps (RowTransformStep protocol):
    - ColumnNormalizationStep: Normalize legacy column names to standard format
    - DateParsingStep: Parse and standardize date fields
    - CustomerNameCleansingStep: Clean customer names and create account name field
    - FieldCleanupStep: Remove invalid columns and finalize record structure

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import (
    ...     ColumnNormalizationStep,
    ...     DateParsingStep,
    ...     CustomerNameCleansingStep,
    ...     FieldCleanupStep,
    ... )
    >>>
    >>> # For DataFrame steps, use infrastructure.transforms (Story 5.6)
    >>> from work_data_hub.infrastructure.transforms import (
    ...     MappingStep,
    ...     ReplacementStep,
    ...     CalculationStep,
    ...     FilterStep,
    ... )
"""

# Row-level transformation steps (remain in domain - these are domain-specific)
from .column_normalization import ColumnNormalizationStep
from .customer_name_cleansing import CustomerNameCleansingStep, clean_company_name
from .date_parsing import DateParsingStep, parse_to_standard_date
from .field_cleanup import FieldCleanupStep

__all__ = [
    # Row-level transformation steps only
    "ColumnNormalizationStep",
    "DateParsingStep",
    "CustomerNameCleansingStep",
    "FieldCleanupStep",
    # Utility functions
    "parse_to_standard_date",
    "clean_company_name",
]
