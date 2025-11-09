"""
Exception hierarchy for pipeline transformation framework.

This module defines specialized exceptions that provide clear error context
for pipeline assembly, step execution, and configuration issues.
"""

from typing import Optional


class PipelineError(Exception):
    """Base exception for all pipeline-related errors."""

    pass


class PipelineStepError(PipelineError):
    """
    Raised when a pipeline step execution fails.

    This exception is used for errors that occur during the execution
    of individual transformation steps, including both configuration
    and runtime failures.

    Args:
        message: Error description
        step_name: Name of the step that failed
        row_index: Index of the row being processed when error occurred (optional)
    """

    def __init__(
        self,
        message: str,
        step_name: Optional[str] = None,
        row_index: Optional[int] = None,
    ):
        self.step_name = step_name
        self.row_index = row_index

        # Build contextual error message
        context_parts = []
        if step_name:
            context_parts.append(f"step='{step_name}'")
        if row_index is not None:
            context_parts.append(f"row_index={row_index}")

        if context_parts:
            full_message = f"{message} ({', '.join(context_parts)})"
        else:
            full_message = message

        super().__init__(full_message)


class PipelineAssemblyError(PipelineError):
    """
    Raised when pipeline assembly or configuration fails.

    This exception is used for errors that occur during pipeline
    construction, such as invalid configuration, missing steps,
    or dependency resolution failures.

    Args:
        message: Error description
        config_path: Path or name of the configuration that failed (optional)
        step_name: Name of the step that caused assembly failure (optional)
    """

    def __init__(
        self,
        message: str,
        config_path: Optional[str] = None,
        step_name: Optional[str] = None,
    ):
        self.config_path = config_path
        self.step_name = step_name

        # Build contextual error message
        context_parts = []
        if config_path:
            context_parts.append(f"config='{config_path}'")
        if step_name:
            context_parts.append(f"step='{step_name}'")

        if context_parts:
            full_message = f"{message} ({', '.join(context_parts)})"
        else:
            full_message = message

        super().__init__(full_message)
