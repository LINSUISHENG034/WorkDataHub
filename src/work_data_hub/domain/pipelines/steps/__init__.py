"""
Shared pipeline transformation steps for WorkDataHub.

This module provides domain-agnostic transformation steps that can be
reused across different data domains (annuity_performance, future domains).

Available Steps:
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
    >>> # Build a pipeline with shared steps
    >>> pipeline = Pipeline(steps=[
    ...     ColumnNormalizationStep(),
    ...     DateParsingStep(),
    ...     CustomerNameCleansingStep(),
    ...     FieldCleanupStep(),
    ... ])
"""

from .column_normalization import ColumnNormalizationStep
from .customer_name_cleansing import CustomerNameCleansingStep, clean_company_name
from .date_parsing import DateParsingStep, parse_to_standard_date
from .field_cleanup import FieldCleanupStep

__all__ = [
    # Transformation steps
    "ColumnNormalizationStep",
    "DateParsingStep",
    "CustomerNameCleansingStep",
    "FieldCleanupStep",
    # Utility functions (for backward compatibility and direct use)
    "parse_to_standard_date",
    "clean_company_name",
]
