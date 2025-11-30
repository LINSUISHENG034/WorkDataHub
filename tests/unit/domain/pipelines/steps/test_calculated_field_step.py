"""
Unit tests for DataFrameCalculatedFieldStep (Story 1.12, AC-1.12.3).

Tests cover:
- Happy path: valid configuration, valid data
- Edge cases: empty DataFrame, missing columns, division by zero
- Error handling: invalid configuration, calculation errors
- Immutability: input DataFrame not modified
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.steps.calculated_field_step import (
    DataFrameCalculatedFieldStep,
)
from work_data_hub.domain.pipelines.types import PipelineContext


@pytest.fixture
def pipeline_context() -> PipelineContext:
    """Create a standard pipeline context for testing."""
    return PipelineContext(
        pipeline_name="test_pipeline",
        execution_id="test-exec-001",
        timestamp=datetime.now(timezone.utc),
        config={},
    )


class TestDataFrameCalculatedFieldStep:
    """Test suite for DataFrameCalculatedFieldStep."""

    def test_step_name(self) -> None:
        """Test that step has correct name property."""
        step = DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]})
        assert step.name == "DataFrameCalculatedFieldStep"

    def test_simple_calculation_lambda(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test simple addition calculation."""
        df_in = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        step = DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]})

        df_out = step.execute(df_in, pipeline_context)

        assert "total" in df_out.columns
        assert df_out["total"].tolist() == [4, 6]

    def test_multiple_calculated_fields(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test adding multiple calculated fields."""
        df_in = pd.DataFrame({"a": [10], "b": [5]})
        step = DataFrameCalculatedFieldStep(
            {
                "sum": lambda df: df["a"] + df["b"],
                "diff": lambda df: df["a"] - df["b"],
                "product": lambda df: df["a"] * df["b"],
            }
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["sum"].iloc[0] == 15
        assert df_out["diff"].iloc[0] == 5
        assert df_out["product"].iloc[0] == 50

    def test_annualized_return_calculation(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test realistic financial calculation."""
        df_in = pd.DataFrame(
            {
                "investment_income": [1000, 2000],
                "ending_assets": [10000, 20000],
                "beginning_assets": [9000, 18000],
            }
        )
        step = DataFrameCalculatedFieldStep(
            {
                "annualized_return": lambda df: df["investment_income"]
                / df["ending_assets"],
                "asset_change": lambda df: df["ending_assets"] - df["beginning_assets"],
            }
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["annualized_return"].tolist() == [0.1, 0.1]
        assert df_out["asset_change"].tolist() == [1000, 2000]

    def test_error_handling_missing_column(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that missing column errors are handled gracefully."""
        df_in = pd.DataFrame({"a": [1, 2]})
        step = DataFrameCalculatedFieldStep(
            {"total": lambda df: df["a"] + df["missing"]}
        )

        df_out = step.execute(df_in, pipeline_context)

        # Field should not be added due to error
        assert "total" not in df_out.columns
        # Original columns preserved
        assert "a" in df_out.columns

    def test_partial_success_on_errors(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that successful calculations are kept even if some fail."""
        df_in = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        step = DataFrameCalculatedFieldStep(
            {
                "good_calc": lambda df: df["a"] + df["b"],
                "bad_calc": lambda df: df["a"] + df["missing"],
            }
        )

        df_out = step.execute(df_in, pipeline_context)

        # Good calculation should succeed
        assert "good_calc" in df_out.columns
        assert df_out["good_calc"].tolist() == [4, 6]
        # Bad calculation should be skipped
        assert "bad_calc" not in df_out.columns

    def test_empty_dataframe(self, pipeline_context: PipelineContext) -> None:
        """Test with empty DataFrame (no rows)."""
        df_in = pd.DataFrame({"a": [], "b": []})
        step = DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]})

        df_out = step.execute(df_in, pipeline_context)

        assert len(df_out) == 0
        assert "total" in df_out.columns

    def test_original_dataframe_unchanged(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that the original DataFrame is not mutated (immutability)."""
        df_in = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        original_columns = list(df_in.columns)
        step = DataFrameCalculatedFieldStep({"total": lambda df: df["a"] + df["b"]})

        _ = step.execute(df_in, pipeline_context)

        assert list(df_in.columns) == original_columns
        assert "total" not in df_in.columns

    def test_invalid_calculated_fields_type_raises_error(self) -> None:
        """Test that non-dict calculated_fields raises TypeError."""
        with pytest.raises(TypeError, match="calculated_fields must be a dict"):
            DataFrameCalculatedFieldStep(["a", "b"])  # type: ignore[arg-type]

    def test_empty_calculated_fields_raises_error(self) -> None:
        """Test that empty calculated_fields raises ValueError."""
        with pytest.raises(ValueError, match="calculated_fields cannot be empty"):
            DataFrameCalculatedFieldStep({})

    def test_non_callable_calculation_raises_error(self) -> None:
        """Test that non-callable calculation raises TypeError."""
        with pytest.raises(TypeError, match="must be callable"):
            DataFrameCalculatedFieldStep({"field": "not_a_function"})  # type: ignore[dict-item]

    def test_callable_object_as_calculation(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test using a callable class instead of lambda."""

        class Doubler:
            def __call__(self, df: pd.DataFrame) -> pd.Series:
                return df["value"] * 2

        df_in = pd.DataFrame({"value": [1, 2, 3]})
        step = DataFrameCalculatedFieldStep({"doubled": Doubler()})

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["doubled"].tolist() == [2, 4, 6]

    def test_large_dataframe_performance(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test performance with larger DataFrame (10,000 rows)."""
        import time

        df_in = pd.DataFrame(
            {
                "a": range(10000),
                "b": range(10000),
            }
        )
        step = DataFrameCalculatedFieldStep(
            {
                "sum": lambda df: df["a"] + df["b"],
                "product": lambda df: df["a"] * df["b"],
            }
        )

        start = time.perf_counter()
        df_out = step.execute(df_in, pipeline_context)
        duration_ms = (time.perf_counter() - start) * 1000

        assert len(df_out) == 10000
        assert "sum" in df_out.columns
        assert "product" in df_out.columns
        # Performance target: <20ms for 10,000 rows
        assert duration_ms < 200  # Allow margin for CI environments
