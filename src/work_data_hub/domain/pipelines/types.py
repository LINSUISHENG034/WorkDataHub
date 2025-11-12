"""
Core data types and protocols for the pipeline execution framework.

Story 1.5 introduces richer execution contracts that provide consistent metadata
to every transformation step. This module defines those contracts so that
pipeline code, sample steps, and tests can all share common structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

import pandas as pd
from typing_extensions import Protocol, runtime_checkable

# Type alias for data rows flowing through pipeline steps
Row = Dict[str, Any]


@dataclass
class PipelineContext:
    """
    Context shared with every pipeline step invocation.

    Attributes:
        pipeline_name: Logical name of the pipeline being executed
        execution_id: Unique identifier (uuid/slug) for this execution
        timestamp: UTC timestamp when the run started
        config: Serialized pipeline configuration for reference in steps
        metadata: Mutable map for steps to stash scratchpad data
    """

    pipeline_name: str
    execution_id: str
    timestamp: datetime
    config: Mapping[str, Any]
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """
    Result of applying a single row-level transformation.

    Attributes:
        row: The transformed row payload (copy to preserve immutability)
        warnings: Non-fatal issues encountered by the step
        errors: Fatal or blocking errors detected during processing
        metadata: Arbitrary diagnostic data captured by the step
    """

    row: Row
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepMetrics:
    """
    Fine-grained metrics for an individual step execution.

    Attributes:
        name: Step identifier
        duration_ms: Execution time for the step in milliseconds
        rows_processed: Number of rows the step touched (row-level only)
    """

    name: str
    duration_ms: int
    rows_processed: int = 0


@dataclass
class PipelineMetrics:
    """
    Aggregate metrics collected for a complete pipeline run.

    Attributes:
        executed_steps: Ordered list of step names that ran
        duration_ms: Total run duration in milliseconds
        step_details: Optional per-step metrics (duration, row counts, etc.)
    """

    executed_steps: List[str] = field(default_factory=list)
    duration_ms: int = 0
    step_details: List[StepMetrics] = field(default_factory=list)


@dataclass
class PipelineResult:
    """
    Result of executing a pipeline over a dataset.

    Attributes:
        success: Whether the run completed without fatal errors
        output_data: Final DataFrame (immutably copied) from the pipeline
        warnings: Aggregated warnings emitted by steps
        errors: Aggregated errors emitted by steps
        metrics: Aggregate PipelineMetrics for observability
        context: PipelineContext describing the execution
    """

    success: bool
    output_data: pd.DataFrame
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    context: Optional[PipelineContext] = None
    row: Optional[Row] = None


@runtime_checkable
class TransformStep(Protocol):
    """Base protocol for all pipeline transformation steps."""

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""


@runtime_checkable
class DataFrameStep(TransformStep, Protocol):
    """Protocol for steps that operate on the entire DataFrame at once."""

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """Return a transformed DataFrame."""


@runtime_checkable
class RowTransformStep(TransformStep, Protocol):
    """Protocol for steps that transform individual rows."""

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        """Return StepResult describing a row-level transformation."""
