"""
Pipeline transformation framework for WorkDataHub.

This module provides a reusable foundation for building data cleansing
pipelines that can be configured from YAML/JSON and executed consistently
across different domain services.

The framework enables domain services to:
- Build transformation pipelines from configuration
- Reuse existing cleansing rules through adapters
- Collect metrics and handle errors consistently
- Compose complex data transformations from simple steps

Example Usage:
    >>> from work_data_hub.domain.pipelines import build_pipeline
    >>>
    >>> # Configuration-driven pipeline construction
    >>> config = {
    ...     "name": "data_cleaning",
    ...     "steps": [
    ...         {
    ...             "name": "decimal_clean",
    ...             "import_path": (
    ...                 "work_data_hub.domain.pipelines.adapters."
    ...                 "CleansingRuleStep.from_registry"
    ...             ),
    ...             "options": {
    ...                 "rule_name": "decimal_quantization",
    ...                 "target_fields": ["amount", "price"],
    ...                 "precision": 2
    ...             }
    ...         }
    ...     ],
    ...     "stop_on_error": True
    ... }
    >>>
    >>> pipeline = build_pipeline(config)
    >>> result = pipeline.execute({"amount": "123.456", "price": "67.89"})
    >>> print(result.row)  # {"amount": Decimal("123.46"), "price": Decimal("67.89")}

Integration with Domain Services:
    Domain services can integrate pipelines for standardized data cleansing:

    >>> def process_trustee_data(rows):
    ...     # Build pipeline from configuration
    ...     pipeline = build_pipeline(trustee_cleaning_config)
    ...
    ...     processed_records = []
    ...     for row in rows:
    ...         result = pipeline.execute(row)
    ...         if not result.errors:  # Only keep successful transformations
    ...             processed_records.append(result.row)
    ...
    ...     return processed_records

Available Components:
    - build_pipeline: Main entry point for pipeline construction
    - TransformStep: Abstract base class for custom transformation steps
    - Pipeline: Core execution engine with metrics and error handling
    - CleansingRuleStep: Adapter for existing cleansing registry rules
    - PipelineConfig/StepConfig: Pydantic models for configuration
    - Pipeline exceptions: Specialized error types for debugging
"""

# Core pipeline components
# Adapter classes for integration
from .adapters import CleansingRuleStep, FieldMapperStep
from .builder import PipelineBuilder, build_pipeline
from .pipeline_config import PipelineConfig, StepConfig
from .core import Pipeline, TransformStep

# Exception hierarchy for error handling
from .exceptions import (
    PipelineAssemblyError,
    PipelineError,
    PipelineStepError,
)

# Type definitions for external use
from .types import (
    DomainPipelineResult,
    ErrorContext,
    PipelineMetrics,
    PipelineResult,
    Row,
    StepResult,
)

# Validation utilities (Story 4.8)
from .validation import (
    ValidationSummaryBase,
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)

# Public API - main entry points for domain services
__all__ = [
    # Main entry point
    "build_pipeline",
    # Core framework classes
    "Pipeline",
    "TransformStep",
    "PipelineBuilder",
    # Configuration models
    "PipelineConfig",
    "StepConfig",
    # Adapter implementations
    "CleansingRuleStep",
    "FieldMapperStep",
    # Type definitions
    "Row",
    "StepResult",
    "PipelineResult",
    "PipelineMetrics",
    # Shared domain types (Story 4.8)
    "ErrorContext",
    "DomainPipelineResult",
    # Validation utilities (Story 4.8)
    "raise_schema_error",
    "ensure_required_columns",
    "ensure_not_empty",
    "ValidationSummaryBase",
    # Exception hierarchy
    "PipelineError",
    "PipelineStepError",
    "PipelineAssemblyError",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "WorkDataHub Team"
__description__ = "Reusable data transformation pipeline framework"
