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
- plan_portfolio_helpers: Plan/portfolio code normalization helpers (Story 7.4-6)

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
from .plan_portfolio_helpers import (
    _clean_portfolio_code,
    apply_plan_code_defaults,
    apply_portfolio_code_defaults,
)
from .standard_steps import (
    CalculationStep,
    DropStep,
    FilterStep,
    MappingStep,
    RenameStep,
    ReplacementStep,
    coerce_numeric_columns,
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
    "coerce_numeric_columns",
    # Plan/Portfolio helpers (Story 7.4-6)
    "apply_plan_code_defaults",
    "apply_portfolio_code_defaults",
    "_clean_portfolio_code",
]
