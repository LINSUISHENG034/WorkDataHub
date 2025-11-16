"""
Configuration models for pipeline transformation framework.

This module defines Pydantic models for pipeline configuration, supporting
both programmatic construction and YAML/JSON-based configuration files.
"""

import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


class StepConfig(BaseModel):
    """
    Configuration for a single pipeline transformation step.

    Defines how to instantiate and configure a transformation step,
    including its import path, initialization options, and dependencies.

    Args:
        name: Unique identifier for this step within the pipeline
        import_path: Full import path to the step class (e.g.,
            "work_data_hub.domain.pipelines.adapters.CleansingRuleStep")
        options: Dictionary of options passed to step constructor
        requires: List of step names that must execute before this step
    """

    name: str = Field(..., description="Unique step name")
    import_path: str = Field(..., description="Full import path to step class")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Step initialization options"
    )
    requires: List[str] = Field(
        default_factory=list, description="Dependencies on other steps"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate step name is suitable for identification."""
        if not v or not v.strip():
            raise ValueError("Step name cannot be empty")

        # Allow alphanumeric, underscore, and hyphen for step names
        if not re.match(r"^[a-zA-Z0-9_-]+$", v.strip()):
            raise ValueError(
                "Step name must contain only alphanumeric characters, "
                "underscores, and hyphens"
            )

        return v.strip()

    @field_validator("import_path")
    @classmethod
    def validate_import_path(cls, v: str) -> str:
        """Validate import path format."""
        if not v or not v.strip():
            raise ValueError("Import path cannot be empty")

        # Basic validation for Python import path format
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*[a-zA-Z0-9_]$", v.strip()):
            raise ValueError("Import path must be a valid Python module/class path")

        return v.strip()


class PipelineConfig(BaseModel):
    """
    Configuration for an entire data transformation pipeline.

    Defines the complete pipeline structure including all steps,
    error handling behavior, retry logic, and execution metadata.

    Args:
        name: Human-readable pipeline identifier
        steps: List of step configurations in execution order
        stop_on_error: Whether to halt pipeline execution on first error
            (backward compatible)
        max_retries: Maximum retry attempts for retriable errors
            (Story 1.10)
        retry_backoff_base: Base delay in seconds for exponential backoff
            (Story 1.10)
        retryable_exceptions: Tuple of exception class names eligible
            for retry (Story 1.10)
        retryable_http_status_codes: HTTP status codes that trigger retry
            (Story 1.10)
        retry_limits: Tier-specific retry limits by error category
            (Story 1.10)
    """

    name: str = Field(..., description="Pipeline name")
    steps: List[StepConfig] = Field(
        ..., description="Pipeline steps in execution order"
    )
    stop_on_error: bool = Field(
        default=True, description="Stop execution on first error"
    )

    # Advanced retry configuration (Story 1.10)
    # All optional with backward-compatible defaults
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for transient errors"
    )
    retry_backoff_base: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Base delay in seconds for exponential backoff"
    )
    retryable_exceptions: tuple = Field(
        default=(
            # Database errors (5 retries)
            "psycopg2.OperationalError",
            "psycopg2.InterfaceError",
            # Network errors (3 retries)
            "requests.Timeout",
            "requests.ConnectionError",
            "builtins.ConnectionResetError",
            "builtins.BrokenPipeError",
            "builtins.TimeoutError",
        ),
        description="Exception class names eligible for retry"
    )
    retryable_http_status_codes: tuple = Field(
        default=(429, 500, 502, 503, 504),
        description="HTTP status codes that trigger retry"
    )
    retry_limits: Dict[str, int] = Field(
        default={
            "database": 5,
            "network": 3,
            "http_429_503": 3,
            "http_500_502_504": 2,
        },
        description="Tier-specific retry limits by error category"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate pipeline name is provided."""
        if not v or not v.strip():
            raise ValueError("Pipeline name cannot be empty")
        return v.strip()

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: List[StepConfig]) -> List[StepConfig]:
        """Validate step configuration list."""
        if not v:
            raise ValueError("Pipeline must have at least one step")

        # Check for duplicate step names
        step_names = [step.name for step in v]
        if len(step_names) != len(set(step_names)):
            duplicates = [name for name in step_names if step_names.count(name) > 1]
            raise ValueError(f"Duplicate step names found: {duplicates}")

        # Validate step dependencies
        for step in v:
            for required_step in step.requires:
                if required_step not in step_names:
                    raise ValueError(
                        f"Step '{step.name}' requires '{required_step}', "
                        f"but it's not defined in the pipeline"
                    )

        return v
