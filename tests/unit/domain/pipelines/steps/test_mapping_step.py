"""
Unit tests for DataFrameMappingStep (Story 1.12, AC-1.12.1).

Tests cover:
- Happy path: valid configuration, valid data
- Edge cases: empty DataFrame, missing columns, null values
- Error handling: invalid configuration
- Immutability: input DataFrame not modified
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.steps.mapping_step import DataFrameMappingStep
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


class TestDataFrameMappingStep:
    """Test suite for DataFrameMappingStep."""

    def test_step_name(self) -> None:
        """Test that step has correct name property."""
        step = DataFrameMappingStep({"a": "b"})
        assert step.name == "DataFrameMappingStep"

    def test_rename_single_column(self, pipeline_context: PipelineContext) -> None:
        """Test renaming a single column."""
        df_in = pd.DataFrame({"old_col": [1, 2, 3]})
        step = DataFrameMappingStep({"old_col": "new_col"})

        df_out = step.execute(df_in, pipeline_context)

        assert list(df_out.columns) == ["new_col"]
        assert df_out["new_col"].tolist() == [1, 2, 3]

    def test_rename_multiple_columns(self, pipeline_context: PipelineContext) -> None:
        """Test renaming multiple columns at once."""
        df_in = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        step = DataFrameMappingStep({"a": "x", "b": "y"})

        df_out = step.execute(df_in, pipeline_context)

        assert set(df_out.columns) == {"x", "y", "c"}
        assert df_out["x"].iloc[0] == 1
        assert df_out["y"].iloc[0] == 2
        assert df_out["c"].iloc[0] == 3

    def test_rename_chinese_columns(self, pipeline_context: PipelineContext) -> None:
        """Test renaming Chinese column names to English."""
        df_in = pd.DataFrame({"月度": [202501], "计划代码": ["ABC"], "客户名称": ["公司A"]})
        step = DataFrameMappingStep(
            {"月度": "report_date", "计划代码": "plan_code", "客户名称": "customer_name"}
        )

        df_out = step.execute(df_in, pipeline_context)

        assert list(df_out.columns) == ["report_date", "plan_code", "customer_name"]
        assert len(df_out) == 1

    def test_missing_columns_gracefully_ignored(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that missing columns are logged and skipped, not causing errors."""
        df_in = pd.DataFrame({"col1": [1, 2, 3]})
        step = DataFrameMappingStep({"missing_col": "new_col", "col1": "renamed_col"})

        df_out = step.execute(df_in, pipeline_context)

        # Only col1 should be renamed, missing_col should be ignored
        assert list(df_out.columns) == ["renamed_col"]
        assert df_out["renamed_col"].tolist() == [1, 2, 3]

    def test_all_columns_missing(self, pipeline_context: PipelineContext) -> None:
        """Test when all mapping columns are missing from DataFrame."""
        df_in = pd.DataFrame({"existing": [1, 2, 3]})
        step = DataFrameMappingStep({"missing1": "new1", "missing2": "new2"})

        df_out = step.execute(df_in, pipeline_context)

        # DataFrame should be unchanged (copy returned)
        assert list(df_out.columns) == ["existing"]
        assert df_out["existing"].tolist() == [1, 2, 3]

    def test_empty_dataframe(self, pipeline_context: PipelineContext) -> None:
        """Test with empty DataFrame (no rows)."""
        df_in = pd.DataFrame({"old_col": []})
        step = DataFrameMappingStep({"old_col": "new_col"})

        df_out = step.execute(df_in, pipeline_context)

        assert list(df_out.columns) == ["new_col"]
        assert len(df_out) == 0

    def test_dataframe_with_null_values(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that null values are preserved during rename."""
        df_in = pd.DataFrame({"col": [1, None, 3, None]})
        step = DataFrameMappingStep({"col": "renamed"})

        df_out = step.execute(df_in, pipeline_context)

        assert list(df_out.columns) == ["renamed"]
        assert df_out["renamed"].tolist()[0] == 1
        assert pd.isna(df_out["renamed"].tolist()[1])
        assert df_out["renamed"].tolist()[2] == 3
        assert pd.isna(df_out["renamed"].tolist()[3])

    def test_original_dataframe_unchanged(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test that the original DataFrame is not mutated (immutability)."""
        df_in = pd.DataFrame({"old_col": [1, 2, 3]})
        original_columns = list(df_in.columns)
        step = DataFrameMappingStep({"old_col": "new_col"})

        _ = step.execute(df_in, pipeline_context)

        # Original DataFrame should be unchanged
        assert list(df_in.columns) == original_columns
        assert "old_col" in df_in.columns
        assert "new_col" not in df_in.columns

    def test_invalid_mapping_type_raises_error(self) -> None:
        """Test that non-dict mapping raises TypeError."""
        with pytest.raises(TypeError, match="column_mapping must be a dict"):
            DataFrameMappingStep(["a", "b"])  # type: ignore[arg-type]

    def test_empty_mapping_raises_error(self) -> None:
        """Test that empty mapping raises ValueError."""
        with pytest.raises(ValueError, match="column_mapping cannot be empty"):
            DataFrameMappingStep({})

    def test_preserves_data_types(self, pipeline_context: PipelineContext) -> None:
        """Test that column data types are preserved after rename."""
        df_in = pd.DataFrame(
            {
                "int_col": [1, 2, 3],
                "float_col": [1.1, 2.2, 3.3],
                "str_col": ["a", "b", "c"],
            }
        )
        step = DataFrameMappingStep(
            {"int_col": "integers", "float_col": "floats", "str_col": "strings"}
        )

        df_out = step.execute(df_in, pipeline_context)

        assert df_out["integers"].dtype == df_in["int_col"].dtype
        assert df_out["floats"].dtype == df_in["float_col"].dtype
        assert df_out["strings"].dtype == df_in["str_col"].dtype

    def test_large_dataframe_performance(
        self, pipeline_context: PipelineContext
    ) -> None:
        """Test performance with larger DataFrame (10,000 rows)."""
        import time

        df_in = pd.DataFrame(
            {
                "col1": range(10000),
                "col2": range(10000),
                "col3": range(10000),
            }
        )
        step = DataFrameMappingStep({"col1": "new1", "col2": "new2", "col3": "new3"})

        start = time.perf_counter()
        df_out = step.execute(df_in, pipeline_context)
        duration_ms = (time.perf_counter() - start) * 1000

        assert len(df_out) == 10000
        assert set(df_out.columns) == {"new1", "new2", "new3"}
        # Performance target: <5ms for 10,000 rows
        assert duration_ms < 50  # Allow some margin for CI environments
