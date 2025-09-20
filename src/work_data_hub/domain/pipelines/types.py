"""
Core data types for the pipeline transformation framework.

This module defines the fundamental data structures used throughout the pipeline
system for representing transformation results, metrics, and execution state.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Type alias for data rows flowing through pipeline steps
Row = Dict[str, Any]


@dataclass
class StepResult:
    """
    Result of applying a single transformation step to a data row.

    Contains the transformed row, any warnings or errors encountered,
    and metadata about the transformation process.

    Args:
        row: The transformed data row
        warnings: List of non-fatal issues encountered during transformation
        errors: List of errors that occurred during transformation
        metadata: Additional information about the transformation step
    """

    row: Row
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """
    Metrics collected during pipeline execution.

    Tracks performance and execution information for monitoring
    and debugging pipeline operations.

    Args:
        executed_steps: List of step names that were executed in order
        duration_ms: Total execution time in milliseconds
    """

    executed_steps: List[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class PipelineResult:
    """
    Complete result of pipeline execution on a single data row.

    Contains the final transformed row, aggregated warnings and errors
    from all steps, and execution metrics for monitoring.

    Args:
        row: The final transformed data row
        warnings: Aggregated warnings from all pipeline steps
        errors: Aggregated errors from all pipeline steps
        metrics: Execution metrics and timing information
    """

    row: Row
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
