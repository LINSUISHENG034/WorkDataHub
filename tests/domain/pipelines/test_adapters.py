"""
Tests for adapter classes that integrate existing cleansing rules.

This module tests the adapters that wrap cleansing registry rules and other
transformation logic into the TransformStep interface.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from src.work_data_hub.domain.pipelines.adapters import (
    CleansingRuleStep,
    FieldMapperStep,
)
from src.work_data_hub.domain.pipelines.exceptions import PipelineAssemblyError
from src.work_data_hub.domain.pipelines.types import StepResult
from work_data_hub.infrastructure.cleansing.registry import CleansingRule, RuleCategory


class TestCleansingRuleStepInitialization:
    """Test CleansingRuleStep initialization."""

    def test_cleansing_rule_step_initialization(self):
        """Test basic CleansingRuleStep initialization."""
        mock_rule = CleansingRule(
            name="test_rule",
            category=RuleCategory.NUMERIC,
            func=lambda x: x,
            description="Test rule",
        )

        step = CleansingRuleStep(
            rule=mock_rule,
            target_fields=["field1", "field2"],
            step_name="custom_step",
            precision=2,
        )

        assert step.rule == mock_rule
        assert step.target_fields == ["field1", "field2"]
        assert step.name == "custom_step"
        assert step.options["precision"] == 2

    def test_cleansing_rule_step_default_name(self):
        """Test CleansingRuleStep uses rule name as default."""
        mock_rule = CleansingRule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            func=lambda x: x,
            description="Test rule",
        )

        step = CleansingRuleStep(rule=mock_rule)

        assert step.name == "decimal_quantization"
        assert step.target_fields is None


class TestCleansingRuleStepFromRegistry:
    """Test CleansingRuleStep.from_registry class method."""

    @patch("src.work_data_hub.domain.pipelines.adapters.registry")
    def test_from_registry_success(self, mock_registry):
        """Test successful creation from registry."""
        mock_rule = CleansingRule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            func=lambda x, precision=4: x,
            description="Decimal quantization rule",
        )
        mock_registry.get_rule.return_value = mock_rule

        step = CleansingRuleStep.from_registry(
            "decimal_quantization", target_fields=["amount"], precision=2
        )

        assert step.rule == mock_rule
        assert step.target_fields == ["amount"]
        assert step.options["precision"] == 2
        mock_registry.get_rule.assert_called_once_with("decimal_quantization")

    @patch("src.work_data_hub.domain.pipelines.adapters.registry")
    def test_from_registry_rule_not_found(self, mock_registry):
        """Test from_registry with non-existent rule."""
        mock_registry.get_rule.return_value = None
        mock_registry.list_all_rules.return_value = [
            Mock(name="rule1"),
            Mock(name="rule2"),
        ]

        with pytest.raises(PipelineAssemblyError, match="not found in registry"):
            CleansingRuleStep.from_registry("nonexistent_rule")

        mock_registry.get_rule.assert_called_once_with("nonexistent_rule")

    @patch("src.work_data_hub.domain.pipelines.adapters.registry")
    def test_from_registry_with_custom_step_name(self, mock_registry):
        """Test from_registry with custom step name."""
        mock_rule = CleansingRule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            func=lambda x: x,
            description="Test rule",
        )
        mock_registry.get_rule.return_value = mock_rule

        step = CleansingRuleStep.from_registry(
            "decimal_quantization", step_name="custom_decimal_step"
        )

        assert step.name == "custom_decimal_step"


class TestCleansingRuleStepExecution:
    """Test CleansingRuleStep execution behavior."""

    def test_apply_to_all_fields_when_no_target_specified(self):
        """Test applying rule to all fields when target_fields is None."""

        # Create a simple rule that adds "_processed" suffix
        def test_rule(value):
            if isinstance(value, str):
                return value + "_processed"
            return value

        mock_rule = CleansingRule(
            name="test_rule",
            category=RuleCategory.STRING,
            func=test_rule,
            description="Test rule",
        )

        step = CleansingRuleStep(rule=mock_rule)
        result = step.apply({"field1": "value1", "field2": "value2", "field3": 123}, {})

        assert result.row["field1"] == "value1_processed"
        assert result.row["field2"] == "value2_processed"
        assert result.row["field3"] == 123  # Non-string, unchanged
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_apply_to_specific_fields_only(self):
        """Test applying rule only to specified target fields."""

        def test_rule(value):
            return value.upper() if isinstance(value, str) else value

        mock_rule = CleansingRule(
            name="uppercase_rule",
            category=RuleCategory.STRING,
            func=test_rule,
            description="Uppercase rule",
        )

        step = CleansingRuleStep(rule=mock_rule, target_fields=["field1", "field3"])

        result = step.apply(
            {"field1": "test", "field2": "unchanged", "field3": "another"}, {}
        )

        assert result.row["field1"] == "TEST"
        assert result.row["field2"] == "unchanged"  # Not in target_fields
        assert result.row["field3"] == "ANOTHER"
        assert "field1" in result.metadata["processed_fields"]
        assert "field3" in result.metadata["processed_fields"]
        assert "field2" not in result.metadata["processed_fields"]

    def test_apply_with_field_name_parameter(self):
        """Test rule that expects field_name parameter."""

        def field_aware_rule(value, field_name=""):
            if "amount" in field_name:
                return float(value) * 2
            return value

        mock_rule = CleansingRule(
            name="field_aware_rule",
            category=RuleCategory.NUMERIC,
            func=field_aware_rule,
            description="Field-aware rule",
        )

        step = CleansingRuleStep(rule=mock_rule)
        result = step.apply({"amount_field": "10", "other_field": "5"}, {})

        assert (
            result.row["amount_field"] == 20.0
        )  # Doubled because "amount" in field name
        assert result.row["other_field"] == "5"  # Unchanged

    def test_apply_handles_rule_exceptions(self):
        """Test handling of exceptions raised by cleansing rules."""

        def failing_rule(value):
            if value == "fail":
                raise ValueError("Rule failed")
            return value + "_processed"

        mock_rule = CleansingRule(
            name="failing_rule",
            category=RuleCategory.STRING,
            func=failing_rule,
            description="Failing rule",
        )

        step = CleansingRuleStep(rule=mock_rule)
        result = step.apply({"good_field": "success", "bad_field": "fail"}, {})

        assert result.row["good_field"] == "success_processed"
        assert result.row["bad_field"] == "fail"  # Original value preserved
        assert len(result.errors) == 1
        assert "Rule failed" in result.errors[0]
        assert "bad_field" in result.metadata["error_fields"]
        assert "good_field" in result.metadata["processed_fields"]

    def test_apply_handles_missing_target_fields(self):
        """Test handling when target fields are not in the row."""
        mock_rule = CleansingRule(
            name="test_rule",
            category=RuleCategory.STRING,
            func=lambda x: x,
            description="Test rule",
        )

        step = CleansingRuleStep(
            rule=mock_rule, target_fields=["existing_field", "missing_field"]
        )

        result = step.apply({"existing_field": "value"}, {})

        assert result.row["existing_field"] == "value"
        assert len(result.warnings) == 1
        assert "missing_field" in result.warnings[0]
        assert "missing_field" in result.metadata["skipped_fields"]

    def test_apply_preserves_row_immutability(self):
        """Test that apply doesn't mutate the original row."""

        def modifying_rule(value):
            return value + "_modified"

        mock_rule = CleansingRule(
            name="modifying_rule",
            category=RuleCategory.STRING,
            func=modifying_rule,
            description="Modifying rule",
        )

        step = CleansingRuleStep(rule=mock_rule)
        original_row = {"field": "original"}
        original_copy = original_row.copy()

        result = step.apply(original_row, {})

        # Original row should be unchanged
        assert original_row == original_copy
        # Result should contain modifications
        assert result.row["field"] == "original_modified"

    def test_apply_with_rule_options(self):
        """Test passing options to the cleansing rule."""

        def configurable_rule(value, multiplier=1, suffix=""):
            if isinstance(value, (int, float)):
                return value * multiplier
            return str(value) + suffix

        mock_rule = CleansingRule(
            name="configurable_rule",
            category=RuleCategory.NUMERIC,
            func=configurable_rule,
            description="Configurable rule",
        )

        step = CleansingRuleStep(rule=mock_rule, multiplier=3, suffix="_custom")

        result = step.apply({"number": 5, "text": "hello"}, {})

        assert result.row["number"] == 15  # 5 * 3
        assert result.row["text"] == "hello_custom"


class TestCleansingRuleStepWithRealRules:
    """Test CleansingRuleStep with actual cleansing rules."""

    @patch("src.work_data_hub.domain.pipelines.adapters.registry")
    def test_with_decimal_quantization_rule(self, mock_registry, decimal_test_data):
        """Test CleansingRuleStep with decimal quantization rule."""
        # Import the real rule function
        from work_data_hub.infrastructure.cleansing.rules.numeric_rules import (
            decimal_quantization,
        )

        mock_rule = CleansingRule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            func=decimal_quantization,
            description="Decimal quantization",
        )
        mock_registry.get_rule.return_value = mock_rule

        step = CleansingRuleStep.from_registry(
            "decimal_quantization", target_fields=["规模", "净值"], precision=2
        )

        result = step.apply(decimal_test_data, {})

        # Check that decimal values were quantized
        assert result.row["规模"] == Decimal("123.46")  # Quantized to 2 decimal places
        assert result.row["净值"] == Decimal("1.23")  # Already a Decimal, quantized

        # Other fields should be unchanged
        assert result.row["收益率"] == "5.67%"
        assert result.row["金额"] == "¥1,234.56"

        # Check that processing was recorded
        assert "规模" in result.metadata["processed_fields"]
        assert "净值" in result.metadata["processed_fields"]


class TestFieldMapperStep:
    """Test FieldMapperStep utility step."""

    def test_field_mapper_initialization(self):
        """Test FieldMapperStep initialization."""
        mapping = {"old_name": "new_name", "old_id": "new_id"}
        step = FieldMapperStep(mapping, "custom_mapper")

        assert step.field_mapping == mapping
        assert step.name == "custom_mapper"

    def test_field_mapper_default_name(self):
        """Test FieldMapperStep default name."""
        mapping = {"old_name": "new_name"}
        step = FieldMapperStep(mapping)

        assert step.name == "field_mapper"

    def test_field_mapper_apply_basic_mapping(self):
        """Test basic field mapping functionality."""
        mapping = {"old_name": "new_name", "old_amount": "new_amount"}
        step = FieldMapperStep(mapping)

        result = step.apply(
            {"old_name": "test", "old_amount": 123, "unchanged": "value"}, {}
        )

        assert result.row["new_name"] == "test"
        assert result.row["new_amount"] == 123
        assert result.row["unchanged"] == "value"  # Preserved
        assert "old_name" not in result.row
        assert "old_amount" not in result.row

    def test_field_mapper_handles_missing_fields(self):
        """Test field mapper with missing source fields."""
        mapping = {"existing": "mapped_existing", "missing": "mapped_missing"}
        step = FieldMapperStep(mapping)

        result = step.apply({"existing": "value", "other": "data"}, {})

        assert result.row["mapped_existing"] == "value"
        assert result.row["other"] == "data"  # Preserved
        assert "mapped_missing" not in result.row
        assert len(result.warnings) == 1
        assert "missing" in result.warnings[0]

    def test_field_mapper_preserves_unmapped_fields(self):
        """Test that unmapped fields are preserved."""
        mapping = {"map_this": "mapped"}
        step = FieldMapperStep(mapping)

        result = step.apply(
            {"map_this": "value", "keep_this": "data", "and_this": 123}, {}
        )

        assert result.row["mapped"] == "value"
        assert result.row["keep_this"] == "data"
        assert result.row["and_this"] == 123
        assert "map_this" not in result.row

    def test_field_mapper_metadata_tracking(self):
        """Test that field mapper tracks mapping operations in metadata."""
        mapping = {"old1": "new1", "old2": "new2", "missing": "new_missing"}
        step = FieldMapperStep(mapping)

        result = step.apply({"old1": "val1", "old2": "val2", "other": "val3"}, {})

        metadata = result.metadata
        assert "old1 -> new1" in metadata["mapped_fields"]
        assert "old2 -> new2" in metadata["mapped_fields"]
        assert "missing" in metadata["missing_fields"]
        assert "other" in metadata["preserved_fields"]

    def test_field_mapper_empty_mapping(self):
        """Test field mapper with empty mapping."""
        step = FieldMapperStep({})
        result = step.apply({"field1": "value1", "field2": "value2"}, {})

        # All fields should be preserved
        assert result.row == {"field1": "value1", "field2": "value2"}
        assert len(result.metadata["preserved_fields"]) == 2
