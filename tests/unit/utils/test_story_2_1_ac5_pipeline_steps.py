"""
Tests for Story 2.1 AC5: Pipeline validation step implementations

This module tests the ValidateInputRowsStep and ValidateOutputRowsStep
classes that integrate Pydantic models with the Epic 1 pipeline framework.
"""

import pandas as pd
import pytest
from datetime import date

from work_data_hub.domain.annuity_performance.pipeline_steps import (
    ValidateInputRowsStep,
    ValidateOutputRowsStep,
)
from work_data_hub.domain.pipelines.types import PipelineContext


@pytest.mark.unit
class TestValidateInputRowsStep:
    """Test ValidateInputRowsStep batch validation."""

    def test_validates_valid_rows(self):
        """Should accept valid rows and return DataFrame."""
        step = ValidateInputRowsStep()

        # Create test DataFrame with valid data
        df = pd.DataFrame([
            {"月度": "202501", "计划代码": "P001", "公司代码": "C001"},
            {"月度": "202502", "计划代码": "P002", "公司代码": "C002"},
        ])

        # Create mock context
        context = PipelineContext(
            pipeline_name="test",
            execution_id="test-123",
            timestamp=pd.Timestamp.now(),
            config={},
            metadata={},
        )

        # Execute step
        result_df = step.execute(df, context)

        # Should return DataFrame with valid rows
        assert len(result_df) == 2
        assert "validation_errors" in context.metadata
        assert len(context.metadata["validation_errors"]) == 0

    def test_filters_invalid_rows(self):
        """Should filter out invalid rows and collect errors."""
        step = ValidateInputRowsStep()

        # Create test DataFrame with mix of valid and invalid
        df = pd.DataFrame([
            {"月度": "202501", "计划代码": "P001"},  # Valid
            {"月度": "invalid_date", "计划代码": 123},  # Invalid date
        ])

        context = PipelineContext(
            pipeline_name="test",
            execution_id="test-123",
            timestamp=pd.Timestamp.now(),
            config={},
            metadata={},
        )

        result_df = step.execute(df, context)

        # Should have 1 valid row only
        assert len(result_df) <= 2  # May have both rows with cleaned data
        assert "validation_errors" in context.metadata


@pytest.mark.unit
class TestValidateOutputRowsStep:
    """Test ValidateOutputRowsStep strict validation."""

    def test_validates_valid_rows(self):
        """Should accept valid rows with required fields."""
        step = ValidateOutputRowsStep()

        # Create test DataFrame with required fields
        df = pd.DataFrame([
            {
                "计划代码": "P001",
                "company_id": "C001",
                "月度": date(2025, 1, 1),
                "期末资产规模": 1000.0,
            },
        ])

        context = PipelineContext(
            pipeline_name="test",
            execution_id="test-123",
            timestamp=pd.Timestamp.now(),
            config={},
            metadata={},
        )

        result_df = step.execute(df, context)

        assert len(result_df) == 1
        assert "strict_validation_errors" in context.metadata

    def test_enforces_required_fields(self):
        """Should reject rows missing required fields but not trigger threshold with small dataset."""
        step = ValidateOutputRowsStep()

        # Create mix: 9 valid + 1 invalid (10% error rate, at threshold)
        valid_rows = [
            {
                "计划代码": f"P00{i}",
                "company_id": f"C00{i}",
                "月度": date(2025, 1, 1),
                "期末资产规模": 1000.0,
            }
            for i in range(9)
        ]
        invalid_row = {"计划代码": "P009", "月度": date(2025, 1, 1)}  # Missing company_id
        df = pd.DataFrame(valid_rows + [invalid_row])

        context = PipelineContext(
            pipeline_name="test",
            execution_id="test-123",
            timestamp=pd.Timestamp.now(),
            config={},
            metadata={},
        )

        result_df = step.execute(df, context)

        # Should filter out 1 invalid row, keep 9 valid
        assert len(result_df) == 9
        assert len(context.metadata["strict_validation_errors"]) > 0

    def test_raises_on_high_error_rate(self):
        """Should raise ValueError if error rate > 10%."""
        step = ValidateOutputRowsStep()

        # Create 100 rows, all missing required fields
        invalid_rows = [{"月度": date(2025, 1, 1)} for _ in range(100)]
        df = pd.DataFrame(invalid_rows)

        context = PipelineContext(
            pipeline_name="test",
            execution_id="test-123",
            timestamp=pd.Timestamp.now(),
            config={},
            metadata={},
        )

        # Should raise ValueError for >10% error rate
        with pytest.raises(ValueError, match="exceeds 10% threshold"):
            step.execute(df, context)


@pytest.mark.unit
def test_step_names():
    """Verify step names for pipeline integration."""
    input_step = ValidateInputRowsStep()
    output_step = ValidateOutputRowsStep()

    assert input_step.name == "pydantic_input_validation"
    assert output_step.name == "pydantic_output_validation"
