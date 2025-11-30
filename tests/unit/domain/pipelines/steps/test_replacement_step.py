"""
Unit tests for DataFrameValueReplacementStep (Story 1.12, AC-1.12.2).

Tests cover:
- Happy path: valid configuration, valid data
- Edge cases: empty DataFrame, missing columns, unmapped values
- Error handling: invalid configuration
- Immutability: input DataFrame not modified
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.steps.replacement_step import (
    DataFrameValueReplacementStep,
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


class TestDataFrameValueReplacementStep:
    """Test suite for DataFrameValueReplacementStep."""

    def test_step_name(self) -> None:
        """Test that step has correct name property."""
        step = DataFrameValueReplacementStep({"col": {"a": "b"}})
        assert step.name == "DataFrameValueReplacementStep"

    def test_replace_values_single_column(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test replacing values in a single column."""
        df_in = pd.DataFrame({"status": ["draft", "active", "draft"]})
        step = DataFrameValueReplacementStep({"status": {"draft": "pending"}})

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["status"].tolist() == ["pending", "active", "pending"]

    def test_replace_values_multiple_columns(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test replacing values in multiple columns."""
        df_in = pd.DataFrame({"status": ["draft"], "type": ["A"]})
        step = DataFrameValueReplacementStep(
            {"status": {"draft": "pending"}, "type": {"A": "Alpha"}}
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["status"].tolist() == ["pending"]
        assert df_out["type"].tolist() == ["Alpha"]

    def test_unmapped_values_unchanged(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that values not in mapping remain unchanged."""
        df_in = pd.DataFrame({"status": ["draft", "unknown", "active"]})
        step = DataFrameValueReplacementStep({"status": {"draft": "pending"}})

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["status"].tolist() == ["pending", "unknown", "active"]

    def test_replace_chinese_values(self, pipeline_context: PipelineContext) -> None:
        """Test replacing Chinese values."""
        df_in = pd.DataFrame({"business_type": ["旧值1", "旧值2", "未变"]})
        step = DataFrameValueReplacementStep(
            {"business_type": {"旧值1": "新值1", "旧值2": "新值2"}}
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["business_type"].tolist() == ["新值1", "新值2", "未变"]

    def test_missing_columns_gracefully_ignored(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that missing columns are logged and skipped."""
        df_in = pd.DataFrame({"existing": ["a", "b"]})
        step = DataFrameValueReplacementStep(
            {"missing": {"x": "y"}, "existing": {"a": "A"}}
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["existing"].tolist() == ["A", "b"]

    def test_empty_dataframe(self, pipeline_context: PipelineContext) -> None:
        """Test with empty DataFrame (no rows)."""
        df_in = pd.DataFrame({"status": []})
        step = DataFrameValueReplacementStep({"status": {"draft": "pending"}})

        df_out = step.execute(df_in, pipeline_context)

        assert len(df_out) == 0
        assert "status" in df_out.columns

    def test_dataframe_with_null_values(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that null values are preserved during replacement."""
        df_in = pd.DataFrame({"status": ["draft", None, "draft"]})
        step = DataFrameValueReplacementStep({"status": {"draft": "pending"}})

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["status"].tolist()[0] == "pending"
        assert pd.isna(df_out["status"].tolist()[1])
        assert df_out["status"].tolist()[2] == "pending"

    def test_original_dataframe_unchanged(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that the original DataFrame is not mutated (immutability)."""
        df_in = pd.DataFrame({"status": ["draft", "active"]})
        original_values = df_in["status"].tolist()
        step = DataFrameValueReplacementStep({"status": {"draft": "pending"}})

        _ = step.execute(df_in, pipeline_context)

        assert df_in["status"].tolist() == original_values

    def test_invalid_replacements_type_raises_error(self) -> None:
        """Test that non-dict replacements raises TypeError."""
        with pytest.raises(TypeError, match="value_replacements must be a dict"):
            DataFrameValueReplacementStep(["a", "b"])  # type: ignore[arg-type]

    def test_empty_replacements_raises_error(self) -> None:
        """Test that empty replacements raises ValueError."""
        with pytest.raises(ValueError, match="value_replacements cannot be empty"):
            DataFrameValueReplacementStep({})

    def test_replace_numeric_values(self, pipeline_context: PipelineContext) -> None:
        """Test replacing numeric values."""
        df_in = pd.DataFrame({"code": [1, 2, 3, 1]})
        step = DataFrameValueReplacementStep({"code": {1: 100, 2: 200}})

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["code"].tolist() == [100, 200, 3, 100]

    def test_large_dataframe_performance(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test performance with larger DataFrame (10,000 rows)."""
        import time

        df_in = pd.DataFrame(
            {"status": ["draft", "active", "pending"] * 3334}  # ~10,000 rows
        )
        step = DataFrameValueReplacementStep(
            {"status": {"draft": "new_draft", "active": "new_active"}}
        )

        start = time.perf_counter()
        df_out = step.execute(df_in, pipeline_context)
        duration_ms = (time.perf_counter() - start) * 1000

        assert len(df_out) == 10002  # 3334 * 3
        # Performance target: <10ms for 10,000 rows
        assert duration_ms < 100  # Allow margin for CI environments
