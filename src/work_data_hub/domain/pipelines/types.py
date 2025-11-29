"""
Core data types and protocols for the pipeline execution framework.

Story 1.5 introduces richer execution contracts that provide consistent metadata
to every transformation step. This module defines those contracts so that
pipeline code, sample steps, and tests can all share common structures.

Story 4.8 adds shared domain types (ErrorContext, DomainPipelineResult) that can
be reused across multiple domains (annuity_performance, Epic 9 domains, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, MutableMapping, Optional

import pandas as pd
from typing_extensions import Protocol, runtime_checkable

if TYPE_CHECKING:
    from work_data_hub.utils.error_reporter import ValidationErrorReporter

# Type alias for data rows flowing through pipeline steps
Row = Dict[str, Any]


# =============================================================================
# Shared Domain Types (Story 4.8)
# =============================================================================


@dataclass
class ErrorContext:
    """
    Structured error context for pipeline failures.

    Provides consistent error information across all pipeline stages,
    following Architecture Decision #4 (Hybrid Error Context Standards).

    This class is shared across all domains (annuity_performance, Epic 9, etc.)
    to ensure consistent error reporting and logging.

    Attributes:
        error_type: Classification of error (e.g., 'discovery', 'validation', 'transformation')
        operation: Specific operation that failed (e.g., 'file_discovery', 'bronze_validation')
        domain: Domain being processed (e.g., 'annuity_performance')
        stage: Pipeline stage where error occurred (e.g., 'discovery', 'transformation', 'loading')
        error_message: Human-readable error message (renamed from 'message' to avoid logging conflict)
        details: Additional context-specific details
        row_number: Optional row number for row-level errors
        field: Optional field name for field-level errors
    """

    error_type: str
    operation: str
    domain: str
    stage: str
    error_message: str
    details: Dict[str, Any] = field(default_factory=dict)
    row_number: Optional[int] = None
    field: Optional[str] = None

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for structured logging."""
        log_dict = {
            "error_type": self.error_type,
            "operation": self.operation,
            "domain": self.domain,
            "stage": self.stage,
            "error_message": self.error_message,
        }
        if self.row_number is not None:
            log_dict["row_number"] = self.row_number
        if self.field:
            log_dict["field"] = self.field
        if self.details:
            log_dict["details"] = self.details
        return log_dict


@dataclass
class DomainPipelineResult:
    """
    Structured return value for domain-level pipeline execution.

    This is distinct from PipelineResult (used by the pipeline framework) and
    represents the result of a complete domain processing operation like
    process_annuity_performance().

    Attributes:
        success: Whether the full pipeline completed without fatal errors
        rows_loaded: Total rows inserted/updated in the warehouse
        rows_failed: Rows dropped during validation
        duration_ms: End-to-end duration in milliseconds
        file_path: Source Excel path that seeded the run
        version: Version folder (V1/V2/...) selected by discovery
        errors: Non-fatal warnings collected during execution
        metrics: Rich per-stage metadata for observability
    """

    success: bool
    rows_loaded: int
    rows_failed: int
    duration_ms: float
    file_path: Path
    version: str
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Return JSON-serialisable representation (useful for logging/tests)."""
        return {
            "success": self.success,
            "rows_loaded": self.rows_loaded,
            "rows_failed": self.rows_failed,
            "duration_ms": self.duration_ms,
            "file_path": str(self.file_path),
            "version": self.version,
            "errors": list(self.errors),
            "metrics": self.metrics,
        }

    def summary(self) -> str:
        """Concise human-readable summary."""
        return (
            f"success={self.success} rows_loaded={self.rows_loaded} "
            f"rows_failed={self.rows_failed} duration_ms={self.duration_ms:.2f} "
            f"file={self.file_path} version={self.version}"
        )


# =============================================================================
# Pipeline Framework Types (Story 1.5)
# =============================================================================


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
        reporter: Optional ValidationErrorReporter for collecting validation errors
                  (Story 2.5 integration)
    """

    pipeline_name: str
    execution_id: str
    timestamp: datetime
    config: Mapping[str, Any]
    metadata: MutableMapping[str, Any] = field(default_factory=dict)
    reporter: Optional[ValidationErrorReporter] = None


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
        memory_delta_bytes: Memory usage change during step execution (Story 1.10)
        timestamp: UTC timestamp when step completed (Story 1.10)
    """

    name: str
    duration_ms: int
    rows_processed: int = 0
    memory_delta_bytes: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
        error_rows: Rows that failed processing with error details (Story 1.10)
        metrics: Aggregate PipelineMetrics for observability
        context: PipelineContext describing the execution
        row: Single row result for backward compatibility
    """

    success: bool
    output_data: pd.DataFrame
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    error_rows: List[Dict[str, Any]] = field(default_factory=list)  # Story 1.10
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
