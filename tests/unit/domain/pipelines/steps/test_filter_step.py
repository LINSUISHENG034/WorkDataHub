"""
Unit tests for DataFrameFilterStep (Story 1.12, AC-1.12.4).

Tests cover:
- Happy path: valid configuration, valid data
- Edge cases: empty DataFrame, all rows filtered, no rows filtered
- Error handling: invalid configuration, filter errors
- Immutability: input DataFrame not modified
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.steps.filter_step import DataFrameFilterStep
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


class TestDataFrameFilterStep:
    """Test suite for DataFrameFilterStep."""

    def test_step_name(self) -> None:
        """Test that step has correct name property."""
        step = DataFrameFilterStep(lambda df: df["value"] > 0)
        assert step.name == "DataFrameFilterStep"

    def test_filter_positive_values(self, pipeline_context: PipelineContext) -> None:
        """Test filtering to keep only positive values."""
        df_in = pd.DataFrame({"value": [1, -2, 3, -4, 5]})
        step = DataFrameFilterStep(lambda df: df["value"] > 0)

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["value"].tolist() == [1, 3, 5]
        assert len(df_out) == 3

    def test_filter_all_rows_removed(self, pipeline_context: PipelineContext) -> None:
        """Test when filter removes all rows."""
        df_in = pd.DataFrame({"value": [1, 2, 3]})
        step = DataFrameFilterStep(lambda df: df["value"] < 0)

        df_out = step.execute(df_in, pipeline_context)

        assert len(df_out) == 0
        assert "value" in df_out.columns  # Columns preserved

    def test_filter_none_removed(self, pipeline_context: PipelineContext) -> None:
        """Test when filter keeps all rows."""
        df_in = pd.DataFrame({"value": [1, 2, 3]})
        step = DataFrameFilterStep(lambda df: df["value"] > 0)

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["value"].tolist() == [1, 2, 3]
        assert len(df_out) == 3

    def test_compound_filter_condition(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test filter with multiple conditions."""
        df_in = pd.DataFrame(
            {
                "ending_assets": [1000, 0, -500, 2000],
                "report_date": pd.to_datetime(
                    ["2024-12-01", "2025-01-01", "2025-02-01", "2025-03-01"]
                ),
            }
        )
        step = DataFrameFilterStep(
            lambda df: (df["ending_assets"] > 0)
            & (df["report_date"] >= "2025-01-01"),
            description="positive assets after 2025",
        )

        df_out = step.execute(df_in, pipeline_context)

        assert len(df_out) == 1
        assert df_out["ending_assets"].iloc[0] == 2000

    def test_empty_dataframe(self, pipeline_context: PipelineContext) -> None:
        """Test with empty DataFrame (no rows)."""
        df_in = pd.DataFrame({"value": []})
        step = DataFrameFilterStep(lambda df: df["value"] > 0)

        df_out = step.execute(df_in, pipeline_context)

        assert len(df_out) == 0
        assert "value" in df_out.columns

    def test_original_dataframe_unchanged(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that the original DataFrame is not mutated (immutability)."""
        df_in = pd.DataFrame({"value": [1, -2, 3, -4, 5]})
        original_length = len(df_in)
        step = DataFrameFilterStep(lambda df: df["value"] > 0)

        _ = step.execute(df_in, pipeline_context)

        assert len(df_in) == original_length
        assert df_in["value"].tolist() == [1, -2, 3, -4, 5]

    def test_invalid_filter_type_raises_error(self) -> None:
        """Test that non-callable filter raises TypeError."""
        with pytest.raises(TypeError, match="filter_condition must be callable"):
            DataFrameFilterStep("not_a_function")  # type: ignore[arg-type]

    def test_filter_error_missing_column(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that missing column in filter returns original DataFrame."""
        df_in = pd.DataFrame({"existing": [1, 2, 3]})
        step = DataFrameFilterStep(lambda df: df["missing"] > 0)

        df_out = step.execute(df_in, pipeline_context)

        # Should return copy of original on error
        assert df_out["existing"].tolist() == [1, 2, 3]

    def test_filter_with_null_values(self, pipeline_context: PipelineContext) -> None:
        """Test filtering with null values in data."""
        df_in = pd.DataFrame({"value": [1, None, 3, None, 5]})
        step = DataFrameFilterStep(lambda df: df["value"] > 2)

        df_out = step.execute(df_in, pipeline_context)

        # NaN comparisons return False, so nulls are filtered out
        assert df_out["value"].tolist() == [3.0, 5.0]

    def test_filter_string_values(self, pipeline_context: PipelineContext) -> None:
        """Test filtering string values."""
        df_in = pd.DataFrame({"status": ["active", "inactive", "active", "pending"]})
        step = DataFrameFilterStep(lambda df: df["status"] == "active")

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["status"].tolist() == ["active", "active"]

    def test_filter_with_description(self, pipeline_context: PipelineContext) -> None:
        """Test that description is used for logging."""
        step = DataFrameFilterStep(
            lambda df: df["value"] > 0, description="keep positive values"
        )
        assert step._description == "keep positive values"

    def test_large_dataframe_performance(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test performance with larger DataFrame (10,000 rows)."""
        import time

        df_in = pd.DataFrame({"value": range(-5000, 5000)})
        step = DataFrameFilterStep(lambda df: df["value"] > 0)

        start = time.perf_counter()
        df_out = step.execute(df_in, pipeline_context)
        duration_ms = (time.perf_counter() - start) * 1000

        assert len(df_out) == 4999  # Values 1 to 4999
        # Performance target: <5ms for 10,000 rows
        assert duration_ms < 50  # Allow margin for CI environments
