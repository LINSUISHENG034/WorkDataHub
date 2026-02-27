"""
Shared test fixtures and utilities for pipeline framework tests.

This module provides common test fixtures, mock objects, and utility functions
used across the pipeline framework test suite.
"""

import pytest
from decimal import Decimal
from typing import Dict, List

from src.work_data_hub.domain.pipelines.core import TransformStep
from src.work_data_hub.domain.pipelines.types import Row, StepResult
from src.work_data_hub.domain.pipelines.pipeline_config import (
    PipelineConfig,
    StepConfig,
)


class MockTransformStep(TransformStep):
    """Mock transformation step for testing."""

    def __init__(self, step_name: str, transform_func=None, should_fail: bool = False):
        """
        Initialize mock step.

        Args:
            step_name: Name of the step
            transform_func: Optional custom transformation function
            should_fail: If True, step will raise an exception
        """
        self.step_name = step_name
        self.transform_func = transform_func
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        """Return step name."""
        return self.step_name

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Apply mock transformation."""
        self.call_count += 1

        if self.should_fail:
            raise ValueError(f"Mock step {self.step_name} failed")

        if self.transform_func:
            transformed_row = self.transform_func(row)
        else:
            # Default behavior: add a field indicating this step was applied
            transformed_row = {**row, f"{self.step_name}_applied": True}

        return StepResult(
            row=transformed_row,
            warnings=[],
            errors=[],
            metadata={"step_name": self.step_name, "call_count": self.call_count},
        )


class UpperCaseStep(TransformStep):
    """Test step that converts specified fields to uppercase."""

    def __init__(self, fields: List[str] = None):
        """Initialize with fields to convert."""
        self.fields = fields or ["name"]

    @property
    def name(self) -> str:
        """Return step name."""
        return "uppercase"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Convert specified fields to uppercase."""
        transformed_row = {**row}

        for field in self.fields:
            if field in row and isinstance(row[field], str):
                transformed_row[field] = row[field].upper()

        return StepResult(
            row=transformed_row,
            warnings=[],
            errors=[],
            metadata={"processed_fields": self.fields},
        )


class TrimStep(TransformStep):
    """Test step that trims whitespace from string fields."""

    def __init__(self, fields: List[str] = None):
        """Initialize with fields to trim."""
        self.fields = fields or ["name"]

    @property
    def name(self) -> str:
        """Return step name."""
        return "trim"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Trim whitespace from specified fields."""
        transformed_row = {**row}

        for field in self.fields:
            if field in row and isinstance(row[field], str):
                transformed_row[field] = row[field].strip()

        return StepResult(
            row=transformed_row,
            warnings=[],
            errors=[],
            metadata={"processed_fields": self.fields},
        )


class FailingStep(TransformStep):
    """Test step that always fails."""

    def __init__(self, error_message: str = "Intentional test failure"):
        """Initialize with error message."""
        self.error_message = error_message

    @property
    def name(self) -> str:
        """Return step name."""
        return "failing_step"

    def apply(self, row: Row, context: Dict) -> StepResult:
        """Always fail with configured error."""
        raise ValueError(self.error_message)


@pytest.fixture
def sample_row():
    """Provide a sample data row for testing."""
    return {
        "name": "  Test Company  ",
        "amount": "123.456",
        "price": 67.89,
        "description": "Sample Description",
        "active": True,
    }


@pytest.fixture
def sample_config():
    """Provide a sample pipeline configuration."""
    return PipelineConfig(
        name="test_pipeline",
        steps=[
            StepConfig(
                name="uppercase",
                import_path="tests.unit.domain.pipelines.conftest.UpperCaseStep",
                options={"fields": ["name"]},
            ),
            StepConfig(
                name="trim",
                import_path="tests.unit.domain.pipelines.conftest.TrimStep",
                options={"fields": ["name"]},
            ),
        ],
        stop_on_error=True,
    )


@pytest.fixture
def sample_config_dict():
    """Provide a sample pipeline configuration as dictionary."""
    return {
        "name": "test_pipeline",
        "steps": [
            {
                "name": "uppercase",
                "import_path": "tests.unit.domain.pipelines.conftest.UpperCaseStep",
                "options": {"fields": ["name"]},
            },
            {
                "name": "trim",
                "import_path": "tests.unit.domain.pipelines.conftest.TrimStep",
                "options": {"fields": ["name"]},
            },
        ],
        "stop_on_error": True,
    }


@pytest.fixture
def mock_steps():
    """Provide a list of mock transformation steps."""
    return [
        MockTransformStep("step1", lambda row: {**row, "step1_value": "processed"}),
        MockTransformStep("step2", lambda row: {**row, "step2_value": "processed"}),
        MockTransformStep("step3", lambda row: {**row, "step3_value": "processed"}),
    ]


@pytest.fixture
def failing_step():
    """Provide a step that always fails."""
    return FailingStep("Test failure")


@pytest.fixture
def decimal_test_data():
    """Provide test data with decimal values for cleansing tests."""
    return {
        "规模": "123.456",
        "收益率": "5.67%",
        "净值": Decimal("1.2345"),
        "金额": "¥1,234.56",
        "invalid_decimal": "not a number",
        "empty_field": "",
        "null_field": None,
    }
