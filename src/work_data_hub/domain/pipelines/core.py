"""
Core pipeline execution framework.

This module defines the abstract base classes and execution engine for
the data transformation pipeline system, providing step orchestration,
error handling, and metrics collection.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .config import PipelineConfig
from .exceptions import PipelineStepError
from .types import PipelineMetrics, PipelineResult, Row, StepResult

logger = logging.getLogger(__name__)


class TransformStep(ABC):
    """
    Abstract base class for pipeline transformation steps.

    All pipeline steps must inherit from this class and implement the apply method
    to perform data transformations on individual rows.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this transformation step."""
        pass

    @abstractmethod
    def apply(self, row: Row, context: Dict) -> StepResult:
        """
        Apply this transformation step to a data row.

        Args:
            row: Input data row to transform
            context: Execution context and shared state

        Returns:
            StepResult containing transformed row and metadata

        Raises:
            Exception: May raise any exception for step-specific errors
        """
        pass


class Pipeline:
    """
    Data transformation pipeline executor.

    Orchestrates the execution of transformation steps in sequence,
    collecting metrics and handling errors according to configuration.
    """

    def __init__(self, steps: List[TransformStep], config: PipelineConfig):
        """
        Initialize pipeline with steps and configuration.

        Args:
            steps: List of transformation steps to execute in order
            config: Pipeline configuration including error handling behavior
        """
        self.steps = steps
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Validate steps match configuration
        if len(steps) != len(config.steps):
            logger.warning(
                f"Step count mismatch: pipeline has {len(steps)} steps, "
                f"config defines {len(config.steps)} steps"
            )

    def execute(self, row: Row, context: Optional[Dict] = None) -> PipelineResult:
        """
        Execute the complete pipeline on a single data row.

        Args:
            row: Input data row to transform
            context: Optional execution context for sharing state between steps

        Returns:
            PipelineResult with transformed row, errors, warnings, and metrics

        Raises:
            PipelineStepError: If stop_on_error=True and a step fails
        """
        if context is None:
            context = {}

        start_time = time.perf_counter()
        executed_steps = []
        all_warnings = []
        all_errors = []

        # CRITICAL: Work with copy to avoid side effects
        current_row = {**row}

        self.logger.debug(
            "Starting pipeline execution",
            extra={"pipeline": self.config.name, "steps": len(self.steps)}
        )

        for step in self.steps:
            step_start_time = time.perf_counter()

            try:
                self.logger.debug(f"Executing step: {step.name}")

                # Apply transformation step
                result = step.apply(current_row, context)

                # CRITICAL: Always copy to prevent side effects
                current_row = {**result.row}
                all_warnings.extend(result.warnings)
                all_errors.extend(result.errors)
                executed_steps.append(step.name)

                step_duration = int((time.perf_counter() - step_start_time) * 1000)
                self.logger.debug(
                    f"Step completed: {step.name}",
                    extra={
                        "step": step.name,
                        "duration_ms": step_duration,
                        "warnings": len(result.warnings),
                        "errors": len(result.errors)
                    }
                )

                # Handle stop_on_error configuration
                if result.errors and self.config.stop_on_error:
                    error_msg = f"Step '{step.name}' failed: {result.errors[0]}"
                    self.logger.error(error_msg)
                    raise PipelineStepError(error_msg, step_name=step.name)

            except Exception as e:
                step_duration = int((time.perf_counter() - step_start_time) * 1000)
                error_msg = f"Step '{step.name}' execution failed: {e}"

                self.logger.error(
                    error_msg,
                    extra={
                        "step": step.name,
                        "duration_ms": step_duration,
                        "error": str(e)
                    }
                )

                # Handle error according to configuration
                if self.config.stop_on_error:
                    raise PipelineStepError(error_msg, step_name=step.name)
                else:
                    # In non-stop mode, record error and continue
                    all_errors.append(error_msg)

        # Calculate total execution time
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        metrics = PipelineMetrics(executed_steps=executed_steps, duration_ms=duration_ms)

        self.logger.info(
            "Pipeline execution completed",
            extra={
                "pipeline": self.config.name,
                "duration_ms": duration_ms,
                "executed_steps": len(executed_steps),
                "total_warnings": len(all_warnings),
                "total_errors": len(all_errors)
            }
        )

        return PipelineResult(
            row=current_row,
            warnings=all_warnings,
            errors=all_errors,
            metrics=metrics
        )
