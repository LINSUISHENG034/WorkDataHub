"""
Base classes for pipeline transformation steps.

Story 5.6: Implement Standard Pipeline Steps
Architecture Decision AD-010: Infrastructure Layer & Pipeline Composition

This module provides the abstract base class for all transformation steps
and a Pipeline class for composing multiple steps into a processing pipeline.

Design Principles:
- Python code composition over JSON configuration
- Immutability: steps return new DataFrames, never mutate input
- Vectorized operations for performance
- Structured logging with context
"""

from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from work_data_hub.domain.pipelines.types import PipelineContext


class TransformStep(ABC):
    """
    Abstract base class for all pipeline transformation steps.

    All transformation steps must inherit from this class and implement
    the `name` property and `apply` method.

    This class also implements `execute` for compatibility with the
    domain/pipelines/core.Pipeline which uses the DataFrameStep protocol.

    Example:
        >>> class MyStep(TransformStep):
        ...     @property
        ...     def name(self) -> str:
        ...         return "MyStep"
        ...
        ...     def apply(self, df, context):
        ...         return df.copy()
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        pass

    @abstractmethod
    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """
        Apply transformation to DataFrame.

        Args:
            df: Input DataFrame (should not be mutated)
            context: Pipeline execution context

        Returns:
            Transformed DataFrame (new copy)
        """
        pass

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        """
        Execute transformation (DataFrameStep protocol compatibility).

        This method delegates to `apply` for compatibility with
        domain/pipelines/core.Pipeline which expects `execute` method.
        """
        return self.apply(dataframe, context)


class Pipeline:
    """
    Compose multiple TransformSteps into a sequential pipeline.

    The pipeline executes steps in order, passing the output of each step
    as input to the next. The input DataFrame is copied before processing
    to ensure immutability.

    Example:
        >>> from work_data_hub.infrastructure.transforms import (
        ...     Pipeline, MappingStep, FilterStep
        ... )
        >>> pipeline = Pipeline([
        ...     MappingStep({'old_col': 'new_col'}),
        ...     FilterStep(lambda df: df['value'] > 0),
        ... ])
        >>> result = pipeline.execute(df, context)
    """

    def __init__(self, steps: List[TransformStep]) -> None:
        """
        Initialize pipeline with a list of steps.

        Args:
            steps: Ordered list of TransformStep instances to execute
        """
        self.steps = steps

    def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """
        Execute all steps in sequence.

        Args:
            df: Input DataFrame
            context: Pipeline execution context

        Returns:
            Transformed DataFrame after all steps have been applied
        """
        result = df.copy()
        for step in self.steps:
            result = step.apply(result, context)
        return result
