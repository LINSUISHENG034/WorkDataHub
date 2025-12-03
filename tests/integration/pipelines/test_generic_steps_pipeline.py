"""
Integration test for generic DataFrame steps in end-to-end pipeline (Story 1.12, AC-1.12.7).

This test demonstrates all 4 generic steps working together in a pipeline,
verifying that:
- Pipeline executes all steps in sequence
- Output DataFrame reflects all transformations
- No row-by-row iteration (vectorized operations only)
"""

from datetime import datetime, timezone
from typing import List

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.pipeline_config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline
from work_data_hub.domain.pipelines.types import PipelineContext, TransformStep

# Import DataFrame steps from infrastructure/transforms/ (Story 5.6)
from work_data_hub.infrastructure.transforms import (
    CalculationStep as DataFrameCalculatedFieldStep,
    FilterStep as DataFrameFilterStep,
    MappingStep as DataFrameMappingStep,
    ReplacementStep as DataFrameValueReplacementStep,
)


def create_pipeline(name: str, steps: List[TransformStep]) -> Pipeline:
    """Helper to create a Pipeline with proper config."""
    step_configs = [
        StepConfig(
            name=step.name,
            import_path=f"work_data_hub.infrastructure.transforms.{step.__class__.__name__}",
        )
        for step in steps
    ]
    config = PipelineConfig(name=name, steps=step_configs, stop_on_error=True)
    return Pipeline(steps=steps, config=config)


@pytest.fixture
def pipeline_context() -> PipelineContext:
    """Create a standard pipeline context for testing."""
    return PipelineContext(
        pipeline_name="generic_steps_integration_test",
        execution_id="integration-test-001",
        timestamp=datetime.now(timezone.utc),
        config={},
    )


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for integration testing."""
    return pd.DataFrame(
        {
            "旧列名": ["value1", "value2", "value3", "value4", "value5"],
            "status": ["draft", "active", "draft", "pending", "active"],
            "a": [10, 20, 30, 40, 50],
            "b": [5, 10, 15, 20, 25],
            "category": ["A", "B", "A", "C", "B"],
        }
    )


@pytest.mark.integration
class TestGenericStepsPipeline:
    """Integration tests for generic steps in pipeline."""

    def test_all_generic_steps_in_sequence(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Test all 4 generic steps executing in sequence."""
        # Build pipeline with all generic steps
        steps = [
            DataFrameMappingStep({"旧列名": "new_column"}),
            DataFrameValueReplacementStep({"status": {"draft": "pending"}}),
            DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]}),
            DataFrameFilterStep(lambda df: df["total"] > 30),
        ]
        pipeline = create_pipeline("generic_steps_demo", steps)

        # Execute pipeline
        result = pipeline.run(sample_dataframe)

        # Verify pipeline success
        assert result.success is True

        # Verify column rename (Step 1)
        assert "new_column" in result.output_data.columns
        assert "旧列名" not in result.output_data.columns

        # Verify value replacement (Step 2) - draft -> pending
        assert "draft" not in result.output_data["status"].values

        # Verify calculated field (Step 3)
        assert "total" in result.output_data.columns

        # Verify filter (Step 4) - only rows with total > 30
        assert all(result.output_data["total"] > 30)

    def test_pipeline_preserves_data_integrity(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Test that data integrity is preserved through pipeline."""
        steps = [
            DataFrameMappingStep({"a": "amount"}),
            DataFrameCalculatedFieldStep({"doubled": lambda df: df["amount"] * 2}),
        ]
        pipeline = create_pipeline("data_integrity_test", steps)

        result = pipeline.run(sample_dataframe)

        assert result.success is True
        # Verify calculation is correct
        expected_doubled = [20, 40, 60, 80, 100]
        assert result.output_data["doubled"].tolist() == expected_doubled

    def test_pipeline_with_realistic_financial_data(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test pipeline with realistic financial data scenario."""
        # Create realistic financial DataFrame
        df_in = pd.DataFrame(
            {
                "月度": [202501, 202501, 202502, 202502],
                "计划代码": ["PLAN_A", "PLAN_B", "PLAN_A", "PLAN_C"],
                "investment_income": [1000, 2000, 1500, 3000],
                "ending_assets": [10000, 20000, 15000, 30000],
                "beginning_assets": [9000, 18000, 14000, 28000],
                "status": ["draft", "active", "draft", "active"],
            }
        )

        # Build pipeline mimicking real domain processing
        steps = [
            DataFrameMappingStep({"月度": "report_date", "计划代码": "plan_code"}),
            DataFrameValueReplacementStep({"status": {"draft": "pending"}}),
            DataFrameCalculatedFieldStep(
                {
                    "return_rate": lambda df: df["investment_income"]
                    / df["ending_assets"],
                    "asset_change": lambda df: df["ending_assets"]
                    - df["beginning_assets"],
                }
            ),
            DataFrameFilterStep(
                lambda df: df["ending_assets"] > 10000,
                description="filter small accounts",
            ),
        ]
        pipeline = create_pipeline("financial_processing", steps)

        result = pipeline.run(df_in)

        assert result.success is True
        # Should have 3 rows (ending_assets > 10000)
        assert len(result.output_data) == 3
        # Verify column renames
        assert "report_date" in result.output_data.columns
        assert "plan_code" in result.output_data.columns
        # Verify calculated fields
        assert "return_rate" in result.output_data.columns
        assert "asset_change" in result.output_data.columns
        # Verify value replacement
        assert "draft" not in result.output_data["status"].values

    def test_original_dataframe_unchanged_after_pipeline(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Test that original DataFrame is not mutated by pipeline."""
        original_columns = list(sample_dataframe.columns)
        original_length = len(sample_dataframe)
        original_values = sample_dataframe["status"].tolist()

        steps = [
            DataFrameMappingStep({"旧列名": "new_column"}),
            DataFrameValueReplacementStep({"status": {"draft": "changed"}}),
            DataFrameFilterStep(lambda df: df["a"] > 20),
        ]
        pipeline = create_pipeline("immutability_test", steps)

        _ = pipeline.run(sample_dataframe)

        # Original DataFrame should be unchanged
        assert list(sample_dataframe.columns) == original_columns
        assert len(sample_dataframe) == original_length
        assert sample_dataframe["status"].tolist() == original_values

    def test_pipeline_performance_10k_rows(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test pipeline performance with 10,000 rows."""
        import time

        # Create large DataFrame with exactly 10000 rows
        n_rows = 10000
        df_in = pd.DataFrame(
            {
                "old_col": [f"value_{i}" for i in range(n_rows)],
                "status": ["draft", "active", "pending"] * (n_rows // 3)
                + ["draft"] * (n_rows % 3),
                "a": list(range(n_rows)),
                "b": list(range(n_rows)),
            }
        )
        df_in = df_in.head(n_rows)

        steps = [
            DataFrameMappingStep({"old_col": "new_col"}),
            DataFrameValueReplacementStep({"status": {"draft": "pending"}}),
            DataFrameCalculatedFieldStep(
                {
                    "sum": lambda df: df["a"] + df["b"],
                    "product": lambda df: df["a"] * df["b"],
                }
            ),
            DataFrameFilterStep(lambda df: df["sum"] > 5000),
        ]
        pipeline = create_pipeline("performance_test", steps)

        start = time.perf_counter()
        result = pipeline.run(df_in)
        duration_ms = (time.perf_counter() - start) * 1000

        assert result.success is True
        # Performance target: <100ms for full pipeline with 10k rows
        # Allow generous margin for CI environments
        assert duration_ms < 1000, f"Pipeline took {duration_ms:.2f}ms, expected <1000ms"

    def test_empty_dataframe_through_pipeline(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that empty DataFrame flows through pipeline correctly."""
        df_in = pd.DataFrame({"old_col": [], "status": [], "a": [], "b": []})

        steps = [
            DataFrameMappingStep({"old_col": "new_col"}),
            DataFrameValueReplacementStep({"status": {"draft": "pending"}}),
            DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]}),
            DataFrameFilterStep(lambda df: df["total"] > 0),
        ]
        pipeline = create_pipeline("empty_df_test", steps)

        result = pipeline.run(df_in)

        assert result.success is True
        assert len(result.output_data) == 0
        # Columns should still be present
        assert "new_col" in result.output_data.columns
        assert "total" in result.output_data.columns

    def test_single_step_pipeline(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Test pipeline with single generic step."""
        steps = [DataFrameMappingStep({"旧列名": "renamed"})]
        pipeline = create_pipeline("single_step_test", steps)

        result = pipeline.run(sample_dataframe)

        assert result.success is True
        assert "renamed" in result.output_data.columns
        assert "旧列名" not in result.output_data.columns
