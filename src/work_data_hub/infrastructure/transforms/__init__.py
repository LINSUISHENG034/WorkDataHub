"""
Pipeline Transformation Steps

Provides standard, reusable pipeline transformation steps that can be composed
to build domain-specific data processing pipelines.

Story 5.6: Implement Standard Pipeline Steps
Architecture Decision AD-010: Infrastructure Layer & Pipeline Composition

Components:
- TransformStep: Abstract base class for all steps
- Pipeline: Compose multiple steps into a pipeline
- MappingStep: Column renaming
- ReplacementStep: Value replacement
- CalculationStep: Calculated fields
- FilterStep: Row filtering
- CleansingStep: Data cleansing integration
- DropStep: Column removal
- RenameStep: Column renaming (alias for MappingStep)

Example:
    >>> from work_data_hub.infrastructure.transforms import (
    ...     Pipeline, MappingStep, FilterStep, CalculationStep
    ... )
    >>> pipeline = Pipeline([
    ...     MappingStep({'old_col': 'new_col'}),
    ...     FilterStep(lambda df: df['value'] > 0),
    ...     CalculationStep({'total': lambda df: df['a'] + df['b']}),
    ... ])
    >>> result = pipeline.execute(df, context)
"""

from .base import Pipeline, TransformStep
from .cleansing_step import CleansingStep
from .standard_steps import (
    CalculationStep,
    DropStep,
    FilterStep,
    MappingStep,
    RenameStep,
    ReplacementStep,
)

__all__ = [
    # Base classes
    "TransformStep",
    "Pipeline",
    # Standard steps
    "MappingStep",
    "ReplacementStep",
    "CalculationStep",
    "FilterStep",
    "CleansingStep",
    "DropStep",
    "RenameStep",
]
