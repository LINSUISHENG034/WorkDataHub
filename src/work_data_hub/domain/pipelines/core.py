"""
Core pipeline execution framework with dual DataFrame and row-level support.

Story 1.5 upgrades the executor to provide:
- Structured execution context (`PipelineContext`)
- Sequential `run()` processing for DataFrame and row steps
- Fail-fast error wrapping with step index/name
- Structlog instrumentation (`pipeline.*` events)
- Comprehensive `PipelineResult` metrics and immutability guarantees
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, MutableMapping, Optional, Sequence, Tuple, Union

import pandas as pd

from work_data_hub.utils.logging import get_logger

from .config import PipelineConfig
from .exceptions import PipelineStepError
from .types import (
    DataFrameStep,
    PipelineContext,
    PipelineMetrics,
    PipelineResult,
    Row,
    RowTransformStep,
    StepMetrics,
    StepResult,
    TransformStep,
)

ContextInput = Optional[Union[PipelineContext, MutableMapping[str, Any]]]

logger = get_logger(__name__)


class Pipeline:
    """
    Data transformation pipeline executor.

    Supports both DataFrame-based steps (`DataFrameStep`) and row-level steps
    (`RowTransformStep`) while emitting structured logs and metrics.
    """

    def __init__(self, steps: List[TransformStep], config: PipelineConfig):
        self.steps = steps
        self.config = config
        self.logger = logger.bind(pipeline=config.name)

        if len(steps) != len(config.steps):
            self.logger.warning(
                "pipeline.step_mismatch",
                configured=len(config.steps),
                provided=len(steps),
            )

    def add_step(self, step: TransformStep) -> None:
        """Append a transformation step at runtime (builder-style API)."""
        self.steps.append(step)

    def run(
        self,
        initial_data: pd.DataFrame,
        context: Optional[PipelineContext] = None,
    ) -> PipelineResult:
        """
        Execute the pipeline over a DataFrame and return the aggregated result.

        Args:
            initial_data: Input DataFrame (copied internally to stay immutable)
            context: Optional PipelineContext (auto-generated when omitted)

        Raises:
            PipelineStepError: When a step fails and stop_on_error is True
        """
        pipeline_context = context or self._build_context()
        current_df = initial_data.copy(deep=True)

        step_metrics: List[StepMetrics] = []
        warnings: List[str] = []
        errors: List[str] = []

        start_time = datetime.now(timezone.utc)
        self.logger.info(
            "pipeline.started",
            execution_id=pipeline_context.execution_id,
            rows=len(current_df),
        )

        for index, step in enumerate(self.steps):
            step_df, step_warnings, step_errors, metrics = self._run_step(
                index, step, current_df, pipeline_context
            )
            current_df = step_df
            warnings.extend(step_warnings)
            errors.extend(step_errors)
            step_metrics.append(metrics)

            if step_errors and self.config.stop_on_error:
                # Fail-fast after recording the error in metrics/logs
                raise PipelineStepError(
                    step_errors[0],
                    step_name=step.name,
                    step_index=index,
                )

        total_duration_ms = int(
        (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()
            * 1000
        )

        metrics = PipelineMetrics(
            executed_steps=[metric.name for metric in step_metrics],
            duration_ms=total_duration_ms,
            step_details=step_metrics,
        )

        success = len(errors) == 0
        result_df = current_df.copy(deep=True)
        first_row: Optional[Row] = None
        if not result_df.empty and len(result_df.index) == 1:
            first_row = result_df.iloc[0].to_dict()

        self.logger.info(
            "pipeline.completed",
            execution_id=pipeline_context.execution_id,
            success=success,
            duration_ms=total_duration_ms,
            warnings=len(warnings),
            errors=len(errors),
        )

        return PipelineResult(
            success=success,
            output_data=result_df,
            warnings=warnings,
            errors=errors,
            metrics=metrics,
            context=pipeline_context,
            row=first_row,
        )

    def execute(
        self,
        row: Row,
        context: ContextInput = None,
    ) -> PipelineResult:
        """
        Backwards-compatible single-row execution helper.

        Converts the row into a single-row DataFrame, runs the pipeline,
        and returns the resulting PipelineResult with `.row` populated.
        """
        dataframe = pd.DataFrame([row])
        pipeline_context = self._ensure_context(context)
        result = self.run(dataframe, pipeline_context)

        if result.row is None and not result.output_data.empty:
            result.row = result.output_data.iloc[0].to_dict()

        return result

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _ensure_context(self, context: ContextInput) -> PipelineContext:
        if isinstance(context, PipelineContext):
            return context
        return self._build_context(context)

    def _build_context(
        self, seed: Optional[MutableMapping[str, Any]] = None
    ) -> PipelineContext:
        seed = seed or {}
        execution_id = seed.get("execution_id") or str(uuid.uuid4())
        timestamp = seed.get("timestamp")
        if not isinstance(timestamp, datetime):
            timestamp = datetime.now(timezone.utc)

        metadata = dict(seed.get("metadata", {}))
        for k, v in seed.items():
            if k not in {"execution_id", "timestamp", "metadata"}:
                metadata.setdefault(k, v)

        return PipelineContext(
            pipeline_name=self.config.name,
            execution_id=execution_id,
            timestamp=timestamp,
            config=self.config.model_dump(),
            metadata=metadata,
        )

    def _run_step(
        self,
        step_index: int,
        step: TransformStep,
        current_df: pd.DataFrame,
        context: PipelineContext,
    ) -> Tuple[pd.DataFrame, List[str], List[str], StepMetrics]:
        self.logger.info(
            "pipeline.step.started",
            step=step.name,
            step_index=step_index,
            rows=len(current_df),
        )

        step_start = datetime.now(timezone.utc)
        warnings: List[str] = []
        errors: List[str] = []

        try:
            if isinstance(step, DataFrameStep):
                result_df = step.execute(current_df.copy(deep=True), context)
                if not isinstance(result_df, pd.DataFrame):
                    raise PipelineStepError(
                        "DataFrameStep.execute must return a pandas DataFrame",
                        step_name=step.name,
                        step_index=step_index,
                    )

                updated_df = result_df.copy(deep=True)
                rows_processed = len(updated_df)

            elif isinstance(step, RowTransformStep):
                updated_df, warnings, errors = self._execute_row_step(
                    step, current_df, context, step_index
                )
                rows_processed = len(current_df)

            else:
                raise PipelineStepError(
                    "Step must implement DataFrameStep or RowTransformStep protocols",
                    step_name=getattr(step, "name", "unknown"),
                    step_index=step_index,
                )

        except PipelineStepError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            raise PipelineStepError(
                f"Step execution failed: {exc}",
                step_name=getattr(step, "name", "unknown"),
                step_index=step_index,
            ) from exc

        duration_ms = int(
            (datetime.now(timezone.utc) - step_start).total_seconds() * 1000
        )

        self.logger.info(
            "pipeline.step.completed",
            step=step.name,
            step_index=step_index,
            duration_ms=duration_ms,
            warnings=len(warnings),
            errors=len(errors),
        )

        metrics = StepMetrics(
            name=step.name,
            duration_ms=duration_ms,
            rows_processed=rows_processed,
        )
        return updated_df, warnings, errors, metrics

    def _execute_row_step(
        self,
        step: RowTransformStep,
        dataframe: pd.DataFrame,
        context: PipelineContext,
        step_index: int,
    ) -> Tuple[pd.DataFrame, List[str], List[str]]:
        transformed_rows: List[Row] = []
        warnings: List[str] = []
        errors: List[str] = []

        for row_position, (_, row_series) in enumerate(dataframe.iterrows()):
            row_dict: Row = row_series.to_dict()
            try:
                result: StepResult = step.apply(row_dict, context)
            except Exception as exc:
                raise PipelineStepError(
                    f"Row-level transform failed: {exc}",
                    step_name=step.name,
                    step_index=step_index,
                    row_index=row_position,
                ) from exc

            transformed_rows.append(result.row)
            warnings.extend(result.warnings)
            errors.extend(result.errors)

            if result.errors and self.config.stop_on_error:
                error_message = (
                    result.errors[0]
                    if isinstance(result.errors, Sequence) and result.errors
                    else "Row-level step reported errors"
                )
                raise PipelineStepError(
                    error_message,
                    step_name=step.name,
                    step_index=step_index,
                    row_index=row_position,
                )

        updated_df = pd.DataFrame(transformed_rows)
        return updated_df, warnings, errors


__all__ = ["Pipeline", "TransformStep"]
