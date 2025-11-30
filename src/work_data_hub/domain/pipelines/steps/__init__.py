"""
Shared pipeline transformation steps for WorkDataHub.

This module provides domain-agnostic transformation steps that can be
reused across different data domains (annuity_performance, future domains).

Available Steps:
    Row-Level Steps (RowTransformStep protocol):
    - ColumnNormalizationStep: Normalize legacy column names to standard format
    - DateParsingStep: Parse and standardize date fields
    - CustomerNameCleansingStep: Clean customer names and create account name field
    - FieldCleanupStep: Remove invalid columns and finalize record structure

    DataFrame Steps (DataFrameStep protocol) - Story 1.12:
    - DataFrameMappingStep: Configuration-driven column renaming
    - DataFrameValueReplacementStep: Configuration-driven value replacement
    - DataFrameCalculatedFieldStep: Configuration-driven calculated fields
    - DataFrameFilterStep: Configuration-driven row filtering

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import (
    ...     # Row-level steps
    ...     ColumnNormalizationStep,
    ...     DateParsingStep,
    ...     CustomerNameCleansingStep,
    ...     FieldCleanupStep,
    ...     # DataFrame steps (Story 1.12)
    ...     DataFrameMappingStep,
    ...     DataFrameValueReplacementStep,
    ...     DataFrameCalculatedFieldStep,
    ...     DataFrameFilterStep,
    ... )
    >>>
    >>> # Configuration-driven DataFrame pipeline (Story 1.12 pattern)
    >>> pipeline.add_step(DataFrameMappingStep({'月度': 'report_date'}))
    >>> pipeline.add_step(DataFrameValueReplacementStep({'status': {'draft': 'pending'}}))
    >>> pipeline.add_step(DataFrameCalculatedFieldStep({'total': lambda df: df['a'] + df['b']}))
    >>> pipeline.add_step(DataFrameFilterStep(lambda df: df['total'] > 0))
"""

# Row-level transformation steps
from .column_normalization import ColumnNormalizationStep
from .customer_name_cleansing import CustomerNameCleansingStep, clean_company_name
from .date_parsing import DateParsingStep, parse_to_standard_date
from .field_cleanup import FieldCleanupStep

# DataFrame transformation steps (Story 1.12: Standard Domain Generic Steps)
from .calculated_field_step import DataFrameCalculatedFieldStep
from .filter_step import DataFrameFilterStep
from .mapping_step import DataFrameMappingStep
from .replacement_step import DataFrameValueReplacementStep

__all__ = [
    # Row-level transformation steps
    "ColumnNormalizationStep",
    "DateParsingStep",
    "CustomerNameCleansingStep",
    "FieldCleanupStep",
    # DataFrame transformation steps (Story 1.12)
    "DataFrameMappingStep",
    "DataFrameValueReplacementStep",
    "DataFrameCalculatedFieldStep",
    "DataFrameFilterStep",
    # Utility functions (for backward compatibility and direct use)
    "parse_to_standard_date",
    "clean_company_name",
]
