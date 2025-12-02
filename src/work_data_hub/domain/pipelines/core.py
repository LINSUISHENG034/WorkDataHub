"""
Core pipeline execution framework with dual DataFrame and row-level support.

Story 1.5 introduces the basic executor framework.
Story 1.10 adds advanced features: retry logic, optional steps, error collection mode,
and comprehensive metrics including memory tracking.
"""

from __future__ import annotations

import copy
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, MutableMapping, Optional, Sequence, Tuple, Union

import pandas as pd

from work_data_hub.utils.logging import get_logger

from .pipeline_config import PipelineConfig
from .exceptions import PipelineStepError, StepSkipped
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


def is_retryable_error(
    exception: Exception,
    retryable_exceptions: tuple,
    retryable_http_status_codes: tuple,
) -> Tuple[bool, Optional[str]]:
    """
    Determine if an error is retryable and return the tier name for retry limits.

    Args:
        exception: The exception that was raised
        retryable_exceptions: Tuple of exception class names eligible for retry
        retryable_http_status_codes: HTTP status codes that trigger retry

    Returns:
        Tuple of (is_retryable: bool, tier_name: Optional[str])
        tier_name will be one of: "database", "network", "http_429_503",
        "http_500_502_504", or None if not retryable

    Examples:
        >>> import psycopg2
        >>> exc = psycopg2.OperationalError("connection lost")
        >>> is_retryable_error(exc, ("psycopg2.OperationalError",), ())
        (True, "database")

        >>> from requests import HTTPError, Response
        >>> resp = Response()
        >>> resp.status_code = 500
        >>> exc = HTTPError(response=resp)
        >>> is_retryable_error(exc, (), (500, 502, 503, 504))
        (True, "http_500_502_504")
    """
    exception_class_name = (
        f"{exception.__class__.__module__}.{exception.__class__.__name__}"
    )

    # Check for HTTP errors with status code detection
    if "HTTPError" in exception.__class__.__name__:
        try:
            # Try to get status code from requests.HTTPError
            response = getattr(exception, "response", None)
            if response is not None:
                status_code = getattr(response, "status_code", None)
                if status_code is not None:
                    if status_code in retryable_http_status_codes:
                        # Determine tier based on status code
                        if status_code in (429, 503):
                            return (True, "http_429_503")
                        elif status_code in (500, 502, 504):
                            return (True, "http_500_502_504")
                    # Status code not in retryable list - permanent error
                    return (False, None)
        except Exception:  # pragma: no cover
            pass  # Fall through to general exception checking

    # Check if exception class name is in retryable list
    if exception_class_name not in retryable_exceptions:
        return (False, None)

    # Determine tier based on exception type
    if "psycopg2" in exception_class_name:
        return (True, "database")
    elif any(
        keyword in exception_class_name
        for keyword in ["requests.", "Connection", "Timeout", "Pipe"]
    ):
        return (True, "network")

    # Retryable but no specific tier (shouldn't happen with current config)
    return (True, "network")  # Default to network tier


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

        Story 1.10 enhancements:
        - Error collection mode (stop_on_error=False collects all errors)
        - error_rows tracking for failed row processing
        - Per-step retry logic with exponential backoff
        - Optional step support (StepSkipped exceptions)

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
        error_rows: List[Dict[str, Any]] = []  # Story 1.10

        start_time = datetime.now(timezone.utc)
        self.logger.info(
            "pipeline.started",
            execution_id=pipeline_context.execution_id,
            rows=len(current_df),
            stop_on_error=self.config.stop_on_error,
        )

        for index, step in enumerate(self.steps):
            step_result = self._run_step(
                index, step, current_df, pipeline_context
            )

            # Unpack enhanced step result
            step_df = step_result["df"]
            step_warnings = step_result["warnings"]
            step_errors = step_result["errors"]
            step_error_rows = step_result.get("error_rows", [])
            metrics = step_result["metrics"]

            current_df = step_df
            warnings.extend(step_warnings)
            errors.extend(step_errors)
            error_rows.extend(step_error_rows)
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
            error_rows=len(error_rows),
        )

        return PipelineResult(
            success=success,
            output_data=result_df,
            warnings=warnings,
            errors=errors,
            error_rows=error_rows,  # Story 1.10
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
    ) -> Dict[str, Any]:
        """
        Execute a single pipeline step with retry logic, optional step support,
        and comprehensive metrics tracking (Story 1.10).

        Returns dict with keys:
            df: Transformed DataFrame
            warnings: List of warning messages
            errors: List of error messages
            error_rows: List of failed rows with error details
            metrics: StepMetrics with duration, memory, timestamp
        """
        self.logger.info(
            "pipeline.step.started",
            step=step.name,
            step_index=step_index,
            rows=len(current_df),
        )

        step_start = datetime.now(timezone.utc)
        warnings: List[str] = []
        errors: List[str] = []
        error_rows: List[Dict[str, Any]] = []

        # Memory tracking (Story 1.10 - Task 5)
        try:
            import os

            import psutil
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss
        except ImportError:
            memory_before = 0

        # Execute step with retry logic (Story 1.10 - Tasks 6 & 7)
        updated_df = current_df
        rows_processed = 0

        try:
            updated_df, warnings, errors, error_rows, rows_processed = (
                self._execute_step_with_retry(
                    step, step_index, current_df, context
                )
            )

        except StepSkipped as skip_exc:
            # Optional step skipped (Story 1.10 - Task 4)
            self.logger.warning(
                "pipeline.step.skipped",
                step=step.name,
                step_index=step_index,
                reason=skip_exc.reason,
            )
            warnings.append(f"Step skipped: {skip_exc.reason}")
            updated_df = current_df.copy(deep=True)  # Pass through unchanged
            rows_processed = len(current_df)

        except PipelineStepError:
            raise

        except Exception as exc:  # pragma: no cover - defensive logging
            raise PipelineStepError(
                f"Step execution failed: {exc}",
                step_name=getattr(step, "name", "unknown"),
                step_index=step_index,
            ) from exc

        # Memory tracking completion
        try:
            import os

            import psutil
            process = psutil.Process(os.getpid())
            memory_after = process.memory_info().rss
            memory_delta = memory_after - memory_before
        except ImportError:
            memory_delta = 0

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
            error_rows=len(error_rows),
            memory_delta_mb=round(memory_delta / (1024 * 1024), 2),
        )

        metrics = StepMetrics(
            name=step.name,
            duration_ms=duration_ms,
            rows_processed=rows_processed,
            memory_delta_bytes=memory_delta,
            timestamp=datetime.now(timezone.utc),
        )

        return {
            "df": updated_df,
            "warnings": warnings,
            "errors": errors,
            "error_rows": error_rows,
            "metrics": metrics,
        }

    def _execute_step_with_retry(
        self,
        step: TransformStep,
        step_index: int,
        current_df: pd.DataFrame,
        context: PipelineContext,
    ) -> Tuple[pd.DataFrame, List[str], List[str], List[Dict[str, Any]], int]:
        """
        Execute step with retry logic for transient errors.

        Story 1.10 - Tasks 6 & 7. Implements exponential backoff with
        tier-specific retry limits based on error type.

        Returns:
            (updated_df, warnings, errors, error_rows, rows_processed)
        """
        warnings: List[str] = []
        errors: List[str] = []
        error_rows: List[Dict[str, Any]] = []

        attempt = 0
        last_exception: Optional[Exception] = None
        tier_name: Optional[str] = None

        while True:
            attempt += 1
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

                    # Log retry success if this was a retry (attempt > 1)
                    if attempt > 1:
                        max_tier_retries = self.config.retry_limits.get(
                            tier_name or "network", self.config.max_retries
                        )
                        self.logger.info(
                            "pipeline.step.retry_success",
                            step=step.name,
                            step_index=step_index,
                            message=(
                                f"Step '{step.name}' succeeded on retry "
                                f"{attempt - 1}/{max_tier_retries} after "
                                f"{last_exception.__class__.__name__}"
                            ),
                            tier=tier_name or "unknown",
                            successful_attempt=attempt,
                        )

                    return updated_df, warnings, errors, error_rows, rows_processed

                elif isinstance(step, RowTransformStep):
                    updated_df, warnings, errors, error_rows = self._execute_row_step(
                        step, current_df, context, step_index
                    )
                    rows_processed = len(current_df)

                    # Log retry success if this was a retry (attempt > 1)
                    if attempt > 1:
                        max_tier_retries = self.config.retry_limits.get(
                            tier_name or "network", self.config.max_retries
                        )
                        self.logger.info(
                            "pipeline.step.retry_success",
                            step=step.name,
                            step_index=step_index,
                            message=(
                                f"Step '{step.name}' succeeded on retry "
                                f"{attempt - 1}/{max_tier_retries} after "
                                f"{last_exception.__class__.__name__}"
                            ),
                            tier=tier_name or "unknown",
                            successful_attempt=attempt,
                        )

                    return updated_df, warnings, errors, error_rows, rows_processed

                else:
                    raise PipelineStepError(
                        "Step must implement DataFrameStep or "
                        "RowTransformStep protocols",
                        step_name=getattr(step, "name", "unknown"),
                        step_index=step_index,
                    )

            except Exception as exc:
                last_exception = exc

                # Check if error is retryable and get tier
                is_retriable, tier_name = is_retryable_error(
                    exc,
                    self.config.retryable_exceptions,
                    self.config.retryable_http_status_codes,
                )

                # Get tier-specific retry limit
                if tier_name and tier_name in self.config.retry_limits:
                    max_attempts = self.config.retry_limits[tier_name] + 1
                else:
                    # Fall back to default max_retries for unknown tiers
                    max_attempts = self.config.max_retries + 1

                if not is_retriable or attempt >= max_attempts:
                    # Log retry exhaustion before raising
                    if is_retriable and attempt >= max_attempts:
                        self.logger.error(
                            "pipeline.step.retry_failed",
                            step=step.name,
                            step_index=step_index,
                            message=(
                                f"Step '{step.name}' failed after "
                                f"{attempt}/{max_attempts} retries"
                            ),
                            tier=tier_name or "unknown",
                            last_error=str(exc),
                        )

                    # Non-retriable error or max retries exhausted
                    if isinstance(exc, (PipelineStepError, StepSkipped)):
                        raise
                    raise PipelineStepError(
                        f"Step execution failed: {exc}",
                        step_name=getattr(step, "name", "unknown"),
                        step_index=step_index,
                    ) from exc

                # Retriable error - log and retry with exponential backoff
                delay = self.config.retry_backoff_base * (2 ** (attempt - 1))
                delay = min(delay, 60.0)  # Cap at 60 seconds

                self.logger.warning(
                    "pipeline.step.retry",
                    step=step.name,
                    step_index=step_index,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    tier=tier_name or "unknown",
                    delay_seconds=round(delay, 2),
                    error=str(exc),
                    exception_type=f"{exc.__class__.__module__}.{exc.__class__.__name__}",
                )

                time.sleep(delay)  # Exponential backoff

                # Check if next attempt will be the successful one by trying it
                # If we continue to the next iteration and succeed, log success
                continue  # Continue to next attempt

        # Should never reach here (safety fallback)
        raise PipelineStepError(
            "Retry logic exhausted unexpectedly",
            step_name=getattr(step, "name", "unknown"),
            step_index=step_index,
        )

    def _execute_row_step(
        self,
        step: RowTransformStep,
        dataframe: pd.DataFrame,
        context: PipelineContext,
        step_index: int,
    ) -> Tuple[pd.DataFrame, List[str], List[str], List[Dict[str, Any]]]:
        """
        Execute row-level transformation step with error collection (Story 1.10).

        Returns:
            (updated_df, warnings, errors, error_rows)
        """
        transformed_rows: List[Row] = []
        warnings: List[str] = []
        errors: List[str] = []
        error_rows: List[Dict[str, Any]] = []

        for row_position, (_, row_series) in enumerate(dataframe.iterrows()):
            row_dict: Row = row_series.to_dict()

            # Deep copy for nested dict structures (AC #2)
            # This ensures no accidental mutation of complex row data
            row_dict_copy = copy.deepcopy(row_dict)

            try:
                result: StepResult = step.apply(row_dict_copy, context)
            except Exception as exc:
                # Error collection mode (Story 1.10 - Task 2)
                error_detail = {
                    "row_index": row_position,
                    "row_data": row_dict,
                    "error": str(exc),
                    "step_name": step.name,
                }
                error_rows.append(error_detail)

                if self.config.stop_on_error:
                    raise PipelineStepError(
                        f"Row-level transform failed: {exc}",
                        step_name=step.name,
                        step_index=step_index,
                        row_index=row_position,
                    ) from exc
                else:
                    # Collect error and continue processing
                    errors.append(f"Row {row_position}: {exc}")
                    # Keep copy of original row (not the mutated version)
                    transformed_rows.append(copy.deepcopy(row_dict))
                    continue

            transformed_rows.append(result.row)
            warnings.extend(result.warnings)

            # Row-level errors from StepResult
            if result.errors:
                error_detail = {
                    "row_index": row_position,
                    "row_data": row_dict,
                    "error": "; ".join(result.errors),
                    "step_name": step.name,
                }
                error_rows.append(error_detail)
                errors.extend(result.errors)

                if self.config.stop_on_error:
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
        return updated_df, warnings, errors, error_rows


__all__ = ["Pipeline", "TransformStep"]
