"""
Adapter classes for integrating existing cleansing rules into pipeline framework.

This module provides adapters that wrap the existing cleansing registry rules
into the TransformStep interface, enabling reuse of existing cleansing logic
within the new pipeline architecture.
"""

import logging
from typing import Any, Dict, List, Optional

from work_data_hub.infrastructure.cleansing.registry import CleansingRule, registry

from .core import TransformStep
from .exceptions import PipelineAssemblyError
from .types import Row, StepResult

logger = logging.getLogger(__name__)


class CleansingRuleStep(TransformStep):
    """
    Adapter that wraps a cleansing rule from the registry into a TransformStep.

    This adapter enables reuse of existing cleansing rules within the pipeline
    framework while providing consistent error handling and metadata collection.
    """

    def __init__(
        self,
        rule: CleansingRule,
        target_fields: Optional[List[str]] = None,
        step_name: Optional[str] = None,
        **options,
    ):
        """
        Initialize the cleansing rule step.

        Args:
            rule: CleansingRule instance from the registry
            target_fields: List of field names to apply the rule to
                (None = apply to all fields)
            step_name: Custom step name (defaults to rule name)
            **options: Additional options passed to the cleansing rule function
        """
        self.rule = rule
        self.target_fields = target_fields
        self.step_name = step_name or rule.name
        self.options = options

        logger.debug(
            f"Created CleansingRuleStep: {self.step_name}",
            extra={
                "rule_name": rule.name,
                "rule_category": rule.category.value,
                "target_fields": target_fields,
                "options": options,
            },
        )

    @property
    def name(self) -> str:
        """Return the name of this transformation step."""
        return self.step_name

    @classmethod
    def from_registry(
        cls,
        rule_name: str,
        target_fields: Optional[List[str]] = None,
        step_name: Optional[str] = None,
        **options,
    ) -> "CleansingRuleStep":
        """
        Create a CleansingRuleStep from a rule in the registry.

        Args:
            rule_name: Name of the rule in the cleansing registry
            target_fields: List of field names to apply the rule to
            step_name: Custom step name (defaults to rule name)
            **options: Additional options passed to the cleansing rule function

        Returns:
            Configured CleansingRuleStep instance

        Raises:
            PipelineAssemblyError: If rule is not found in registry

        Example:
            >>> step = CleansingRuleStep.from_registry(
            ...     "decimal_quantization",
            ...     target_fields=["amount", "price"],
            ...     precision=2
            ... )
        """
        rule = registry.get_rule(rule_name)
        if not rule:
            available_rules = [r.name for r in registry.list_all_rules()]
            raise PipelineAssemblyError(
                f"Cleansing rule '{rule_name}' not found in registry. "
                f"Available rules: {available_rules}"
            )

        return cls(
            rule=rule, target_fields=target_fields, step_name=step_name, **options
        )

    def apply(self, row: Row, context: Dict) -> StepResult:
        """
        Apply the cleansing rule to the specified fields in the row.

        Args:
            row: Input data row to transform
            context: Execution context (not used by cleansing rules)

        Returns:
            StepResult with transformed row and any errors/warnings

        Raises:
            PipelineStepError: If cleansing rule execution fails critically
        """
        # CRITICAL: Work with copy to prevent side effects
        processed_row = {**row}
        warnings = []
        errors = []
        metadata: Dict[str, Any] = {
            "rule_name": self.rule.name,
            "rule_category": self.rule.category.value,
            "processed_fields": [],
            "skipped_fields": [],
            "error_fields": [],
        }

        # Determine which fields to process
        fields_to_process = (
            self.target_fields if self.target_fields else list(row.keys())
        )

        logger.debug(
            f"Applying cleansing rule: {self.rule.name}",
            extra={
                "step_name": self.step_name,
                "rule_name": self.rule.name,
                "fields_to_process": len(fields_to_process),
                "total_fields": len(row.keys()),
            },
        )

        for field_name in fields_to_process:
            if field_name not in row:
                warnings.append(f"Field '{field_name}' not found in row")
                metadata["skipped_fields"].append(field_name)
                continue

            original_value = row[field_name]

            try:
                # Apply cleansing rule with field-specific options
                rule_options = {**self.options}

                # Some rules expect field_name as a parameter
                if "field_name" in self.rule.func.__code__.co_varnames:
                    rule_options["field_name"] = field_name

                cleaned_value = self.rule.func(original_value, **rule_options)
                processed_row[field_name] = cleaned_value
                metadata["processed_fields"].append(field_name)

                # Log significant transformations
                if cleaned_value != original_value:
                    logger.debug(
                        f"Field transformed: {field_name}",
                        extra={
                            "field": field_name,
                            "rule": self.rule.name,
                            "original_type": type(original_value).__name__,
                            "cleaned_type": type(cleaned_value).__name__,
                        },
                    )

            except Exception as e:
                error_msg = (
                    f"Rule '{self.rule.name}' failed on field '{field_name}': {e}"
                )
                errors.append(error_msg)
                metadata["error_fields"].append(field_name)

                logger.warning(
                    error_msg,
                    extra={
                        "step_name": self.step_name,
                        "rule_name": self.rule.name,
                        "field": field_name,
                        "original_value": original_value,
                        "error": str(e),
                    },
                )

                # Keep original value when cleansing fails
                # This allows pipeline to continue with best-effort processing

        # Create step result
        result = StepResult(
            row=processed_row, warnings=warnings, errors=errors, metadata=metadata
        )

        logger.debug(
            f"Cleansing rule completed: {self.rule.name}",
            extra={
                "step_name": self.step_name,
                "processed_fields": len(metadata["processed_fields"]),
                "warnings": len(warnings),
                "errors": len(errors),
            },
        )

        return result


class FieldMapperStep(TransformStep):
    """
    Simple transformation step that renames or maps fields in a row.

    This is a utility step for common field transformation needs within pipelines.
    """

    def __init__(self, field_mapping: Dict[str, str], step_name: str = "field_mapper"):
        """
        Initialize field mapper step.

        Args:
            field_mapping: Dictionary mapping old field names to new field names
            step_name: Name for this transformation step
        """
        self.field_mapping = field_mapping
        self.step_name = step_name

        logger.debug(
            f"Created FieldMapperStep: {step_name}",
            extra={"mapping_count": len(field_mapping), "mapping": field_mapping},
        )

    @property
    def name(self) -> str:
        """Return the name of this transformation step."""
        return self.step_name

    def apply(self, row: Row, context: Dict) -> StepResult:
        """
        Apply field mapping to the row.

        Args:
            row: Input data row to transform
            context: Execution context (not used)

        Returns:
            StepResult with renamed fields
        """
        # CRITICAL: Work with copy to prevent side effects
        processed_row = {}
        warnings = []
        metadata: Dict[str, Any] = {
            "mapped_fields": [],
            "missing_fields": [],
            "preserved_fields": [],
        }

        # Apply field mapping
        for old_name, new_name in self.field_mapping.items():
            if old_name in row:
                processed_row[new_name] = row[old_name]
                metadata["mapped_fields"].append(f"{old_name} -> {new_name}")
            else:
                warnings.append(
                    f"Field '{old_name}' not found for mapping to '{new_name}'"
                )
                metadata["missing_fields"].append(old_name)

        # Preserve fields not in mapping
        for field_name, value in row.items():
            if field_name not in self.field_mapping:
                processed_row[field_name] = value
                metadata["preserved_fields"].append(field_name)

        return StepResult(
            row=processed_row, warnings=warnings, errors=[], metadata=metadata
        )
