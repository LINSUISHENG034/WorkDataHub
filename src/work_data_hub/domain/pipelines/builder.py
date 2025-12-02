"""
Pipeline builder and assembly utilities.

This module provides functionality for constructing pipelines from configuration,
including dynamic step loading, dependency resolution, and validation.
"""

import importlib
import logging
from typing import Any, Dict, List, Optional, Union

from .pipeline_config import PipelineConfig, StepConfig
from .core import Pipeline, TransformStep
from .exceptions import PipelineAssemblyError
from .types import DataFrameStep, RowTransformStep

logger = logging.getLogger(__name__)


class PipelineBuilder:
    """
    Fluent API builder for constructing transformation pipelines.

    Provides programmatic construction of pipelines with method chaining
    and validation of step dependencies and configuration.
    """

    def __init__(self):
        """Initialize empty pipeline builder."""
        self._steps: List[TransformStep] = []
        self._config: Optional[PipelineConfig] = None

    def add_step(self, step: TransformStep) -> "PipelineBuilder":
        """
        Add a transformation step to the pipeline.

        Args:
            step: Configured transformation step instance

        Returns:
            Self for method chaining
        """
        self._steps.append(step)
        return self

    def with_config(self, config: PipelineConfig) -> "PipelineBuilder":
        """
        Set the pipeline configuration.

        Args:
            config: Pipeline configuration object

        Returns:
            Self for method chaining
        """
        self._config = config
        return self

    def build(self) -> Pipeline:
        """
        Build the configured pipeline.

        Returns:
            Assembled Pipeline instance ready for execution

        Raises:
            PipelineAssemblyError: If configuration is invalid or missing
        """
        if not self._config:
            raise PipelineAssemblyError("Pipeline configuration is required")

        if not self._steps:
            raise PipelineAssemblyError("Pipeline must have at least one step")

        logger.debug(
            f"Building pipeline '{self._config.name}' with {len(self._steps)} steps"
        )

        return Pipeline(steps=self._steps, config=self._config)


def _import_step_class_or_factory(import_path: str) -> Any:
    """
    Dynamically import a step class or factory method from its import path.

    Supports both direct class imports and factory method calls:
    - "work_data_hub.domain.pipelines.adapters.CleansingRuleStep"
      -> imports class
    - "work_data_hub.domain.pipelines.adapters.CleansingRuleStep.from_registry"
      -> imports factory

    Args:
        import_path: Full import path to the step class or factory method

    Returns:
        Step class or factory callable

    Raises:
        PipelineAssemblyError: If import fails or target is not valid
    """
    try:
        if "." not in import_path:
            raise PipelineAssemblyError(f"Invalid import path format: {import_path}")

        # Check if this is a factory method call (has method after class name)
        parts = import_path.split(".")

        # Try to import as a direct class first
        try:
            class_name = parts[-1]
            module_path = ".".join(parts[:-1])
            module = importlib.import_module(module_path)

            if hasattr(module, class_name):
                target = getattr(module, class_name)

                # If it's a class, validate it
                if isinstance(target, type):
                    _validate_transform_step_class(target, import_path)
                    return target
                else:
                    # It's not a class, might be a callable - return it
                    return target
        except ImportError:
            pass

        # Try as factory method (Class.method)
        if len(parts) >= 2:
            method_name = parts[-1]
            class_name = parts[-2]
            module_path = ".".join(parts[:-2])

            try:
                module = importlib.import_module(module_path)
                if hasattr(module, class_name):
                    step_class = getattr(module, class_name)
                    if isinstance(step_class, type) and hasattr(
                        step_class, method_name
                    ):
                        factory_method = getattr(step_class, method_name)
                        if callable(factory_method):
                            # Validate that the class inherits from TransformStep
                            _validate_transform_step_class(
                                step_class, f"{module_path}.{class_name}"
                            )
                            return factory_method
            except ImportError:
                pass

        # If we get here, nothing worked
        raise PipelineAssemblyError(
            f"Could not import class or factory from '{import_path}'"
        )

    except ImportError as e:
        raise PipelineAssemblyError(f"Failed to import '{import_path}': {e}")
    except Exception as e:
        raise PipelineAssemblyError(f"Error loading '{import_path}': {e}")


def _validate_transform_step_class(step_class: type, import_path: str) -> None:
    """
    Validate that a class implements the TransformStep interface.

    Uses duck-typing approach to avoid import path mismatches between
    src.work_data_hub and work_data_hub module roots.
    """
    if not isinstance(step_class, type):
        raise PipelineAssemblyError(f"'{import_path}' is not a class")

    # Duck-typing validation: check for required methods and properties
    if not hasattr(step_class, "name"):
        raise PipelineAssemblyError(
            f"Class '{import_path}' must have a 'name' property "
            "(TransformStep interface)"
        )

    if not (hasattr(step_class, "apply") or hasattr(step_class, "execute")):
        raise PipelineAssemblyError(
            f"Class '{import_path}' must implement either 'apply' "
            "or 'execute' to satisfy the TransformStep protocols"
        )

    # Additional validation: try direct issubclass check, but don't fail if it
    # doesn't work due to import path mismatches (duck typing is sufficient)
    try:
        if issubclass(step_class, TransformStep):
            logger.debug(f"Direct issubclass check passed for {import_path}")
        else:
            logger.debug(
                "Direct issubclass check failed for %s, but duck typing passed",
                import_path,
            )
    except TypeError:
        # This can happen with import path mismatches - duck typing above should
        # catch issues
        logger.debug(
            "Direct issubclass check not possible for %s, relying on duck typing",
            import_path,
        )


def _create_step_instance(step_config: StepConfig) -> TransformStep:
    """
    Create a step instance from configuration.

    Supports both direct class instantiation and factory method calls.

    Args:
        step_config: Step configuration including import path and options

    Returns:
        Configured step instance

    Raises:
        PipelineAssemblyError: If step creation fails
    """
    try:
        target = _import_step_class_or_factory(step_config.import_path)

        # Determine if this is a class constructor or factory method
        if isinstance(target, type):
            # Direct class instantiation
            step_instance = target(**step_config.options)
        else:
            # Factory method call
            step_instance = target(**step_config.options)

        # Validate the result implements TransformStep interface
        if not isinstance(step_instance, (RowTransformStep, DataFrameStep)):
            raise PipelineAssemblyError(
                f"Step created from '{step_config.import_path}' does not implement "
                f"TransformStep interface"
            )

        logger.debug(
            f"Created step instance: {step_config.name}",
            extra={
                "step_name": step_config.name,
                "import_path": step_config.import_path,
                "options": step_config.options,
                "actual_name": getattr(step_instance, "name", "unknown"),
            },
        )

        return step_instance

    except Exception as e:
        raise PipelineAssemblyError(
            f"Failed to create step '{step_config.name}': {e}",
            step_name=step_config.name,
        )


def _validate_step_dependencies(steps: List[StepConfig]) -> None:
    """
    Validate that step dependencies can be satisfied.

    Args:
        steps: List of step configurations to validate

    Raises:
        PipelineAssemblyError: If dependencies cannot be satisfied
    """
    step_names = [step.name for step in steps]
    step_index = {step.name: i for i, step in enumerate(steps)}

    for step in steps:
        for required_step in step.requires:
            if required_step not in step_names:
                raise PipelineAssemblyError(
                    f"Step '{step.name}' requires '{required_step}', "
                    "but it's not defined",
                    step_name=step.name,
                )

            # Check that required step comes before this step
            required_index = step_index[required_step]
            current_index = step_index[step.name]

            if required_index >= current_index:
                raise PipelineAssemblyError(
                    f"Step '{step.name}' requires '{required_step}', "
                    f"but '{required_step}' is defined after '{step.name}' "
                    "in the pipeline",
                    step_name=step.name,
                )


def build_pipeline(
    config: Union[Dict[str, Any], PipelineConfig],
    steps: Optional[List[TransformStep]] = None,
) -> Pipeline:
    """
    Build a pipeline from configuration with optional pre-built steps.

    This is the main entry point for pipeline construction, supporting
    both configuration-driven and programmatic pipeline assembly.

    Args:
        config: Pipeline configuration as dict or PipelineConfig object
        steps: Pre-built steps to use instead of loading from config

    Returns:
        Assembled Pipeline ready for execution

    Raises:
        PipelineAssemblyError: If configuration is invalid or assembly fails

    Example:
        >>> config = {
        ...     "name": "data_cleaning",
        ...     "steps": [
        ...         {
        ...             "name": "trim_whitespace",
        ...             "import_path": "work_data_hub.domain.pipelines.steps.TrimStep",
        ...             "options": {"fields": ["name", "description"]}
        ...         }
        ...     ],
        ...     "stop_on_error": True
        ... }
        >>> pipeline = build_pipeline(config)
    """
    # Convert dict to PipelineConfig if needed
    if isinstance(config, dict):
        try:
            pipeline_config = PipelineConfig.model_validate(config)  # Pydantic v2
        except Exception as e:
            raise PipelineAssemblyError(f"Invalid pipeline configuration: {e}")
    else:
        pipeline_config = config

    logger.info(
        f"Building pipeline '{pipeline_config.name}'",
        extra={
            "pipeline": pipeline_config.name,
            "step_count": len(pipeline_config.steps),
            "stop_on_error": pipeline_config.stop_on_error,
        },
    )

    # Use provided steps or build from configuration
    if steps is not None:
        # Validate provided steps match configuration
        if len(steps) != len(pipeline_config.steps):
            raise PipelineAssemblyError(
                f"Step count mismatch: provided {len(steps)} steps, "
                f"config defines {len(pipeline_config.steps)} steps"
            )
        pipeline_steps = steps
    else:
        # Validate step dependencies first
        _validate_step_dependencies(pipeline_config.steps)

        # Build steps from configuration
        pipeline_steps = []
        for step_config in pipeline_config.steps:
            step_instance = _create_step_instance(step_config)
            pipeline_steps.append(step_instance)

    # Create and return pipeline
    pipeline = Pipeline(steps=pipeline_steps, config=pipeline_config)

    logger.info(
        f"Pipeline '{pipeline_config.name}' built successfully",
        extra={
            "pipeline": pipeline_config.name,
            "steps": [step.name for step in pipeline_steps],
        },
    )

    return pipeline
