"""Tests for standard transformation steps (AC 5.6.2, 5.6.4)."""

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    DropStep,
    FilterStep,
    MappingStep,
    RenameStep,
    ReplacementStep,
)


class TestMappingStep:
    """Tests for MappingStep (column renaming)."""

    def test_renames_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """MappingStep renames columns correctly."""
        step = MappingStep({"old_col": "new_col", "a": "amount"})
        result = step.apply(sample_dataframe, pipeline_context)

        assert "new_col" in result.columns
        assert "amount" in result.columns
        assert "old_col" not in result.columns
        assert "a" not in result.columns

    def test_handles_missing_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """MappingStep handles missing columns gracefully."""
        step = MappingStep({"nonexistent": "new_name", "old_col": "renamed"})
        result = step.apply(sample_dataframe, pipeline_context)

        assert "renamed" in result.columns
        assert "new_name" not in result.columns

    def test_empty_mapping_raises(self) -> None:
        """MappingStep raises ValueError for empty mapping."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MappingStep({})

    def test_invalid_type_raises(self) -> None:
        """MappingStep raises TypeError for non-dict input."""
        with pytest.raises(TypeError, match="must be a dict"):
            MappingStep(["not", "a", "dict"])  # type: ignore

    def test_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """MappingStep does not mutate input DataFrame."""
        original_columns = list(sample_dataframe.columns)
        step = MappingStep({"old_col": "new_col"})
        _ = step.apply(sample_dataframe, pipeline_context)

        assert list(sample_dataframe.columns) == original_columns

    def test_name_property(self) -> None:
        """MappingStep has correct name."""
        step = MappingStep({"a": "b"})
        assert step.name == "MappingStep"


class TestReplacementStep:
    """Tests for ReplacementStep (value replacement)."""

    def test_replaces_values(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """ReplacementStep replaces values correctly."""
        step = ReplacementStep({"status": {"draft": "pending"}})
        result = step.apply(sample_dataframe, pipeline_context)

        assert "draft" not in result["status"].values
        assert "pending" in result["status"].values
        assert "active" in result["status"].values

    def test_handles_missing_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """ReplacementStep handles missing columns gracefully."""
        step = ReplacementStep({"nonexistent": {"old": "new"}})
        result = step.apply(sample_dataframe, pipeline_context)

        # Should return copy without error
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True),
            sample_dataframe.reset_index(drop=True),
        )

    def test_empty_mapping_raises(self) -> None:
        """ReplacementStep raises ValueError for empty mapping."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ReplacementStep({})

    def test_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """ReplacementStep does not mutate input DataFrame."""
        original_values = sample_dataframe["status"].tolist()
        step = ReplacementStep({"status": {"draft": "changed"}})
        _ = step.apply(sample_dataframe, pipeline_context)

        assert sample_dataframe["status"].tolist() == original_values

    def test_name_property(self) -> None:
        """ReplacementStep has correct name."""
        step = ReplacementStep({"col": {"a": "b"}})
        assert step.name == "ReplacementStep"


class TestCalculationStep:
    """Tests for CalculationStep (calculated fields)."""

    def test_adds_calculated_fields(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CalculationStep adds calculated fields correctly."""
        step = CalculationStep(
            {
                "sum": lambda df: df["a"] + df["b"],
                "product": lambda df: df["a"] * df["b"],
            }
        )
        result = step.apply(sample_dataframe, pipeline_context)

        assert "sum" in result.columns
        assert "product" in result.columns
        assert result["sum"].tolist() == [15, 30, 45]
        assert result["product"].tolist() == [50, 200, 450]

    def test_calculation_error_raises(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CalculationStep raises on calculation error."""
        step = CalculationStep(
            {
                "bad": lambda df: df["nonexistent_column"] + 1,
            }
        )
        with pytest.raises(KeyError):
            step.apply(sample_dataframe, pipeline_context)

    def test_empty_calculations_raises(self) -> None:
        """CalculationStep raises ValueError for empty calculations."""
        with pytest.raises(ValueError, match="cannot be empty"):
            CalculationStep({})

    def test_non_callable_raises(self) -> None:
        """CalculationStep raises TypeError for non-callable."""
        with pytest.raises(TypeError, match="must be callable"):
            CalculationStep({"field": "not_a_function"})  # type: ignore

    def test_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CalculationStep does not mutate input DataFrame."""
        original_columns = list(sample_dataframe.columns)
        step = CalculationStep({"new_field": lambda df: df["a"] * 2})
        _ = step.apply(sample_dataframe, pipeline_context)

        assert list(sample_dataframe.columns) == original_columns

    def test_name_property(self) -> None:
        """CalculationStep has correct name."""
        step = CalculationStep({"x": lambda df: df["a"]})
        assert step.name == "CalculationStep"


class TestFilterStep:
    """Tests for FilterStep (row filtering)."""

    def test_filters_rows(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """FilterStep filters rows correctly."""
        step = FilterStep(lambda df: df["a"] > 15)
        result = step.apply(sample_dataframe, pipeline_context)

        assert len(result) == 2
        assert all(result["a"] > 15)

    def test_filter_all_rows(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """FilterStep can filter out all rows."""
        step = FilterStep(lambda df: df["a"] > 100)
        result = step.apply(sample_dataframe, pipeline_context)

        assert len(result) == 0

    def test_filter_no_rows(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """FilterStep can keep all rows."""
        step = FilterStep(lambda df: df["a"] > 0)
        result = step.apply(sample_dataframe, pipeline_context)

        assert len(result) == len(sample_dataframe)

    def test_none_predicate_raises(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """FilterStep raises when predicate returns None."""
        step = FilterStep(lambda df: None)  # type: ignore
        with pytest.raises(ValueError, match="returned None"):
            step.apply(sample_dataframe, pipeline_context)

    def test_non_callable_raises(self) -> None:
        """FilterStep raises TypeError for non-callable."""
        with pytest.raises(TypeError, match="must be callable"):
            FilterStep("not_a_function")  # type: ignore

    def test_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """FilterStep does not mutate input DataFrame."""
        original_length = len(sample_dataframe)
        step = FilterStep(lambda df: df["a"] > 15)
        _ = step.apply(sample_dataframe, pipeline_context)

        assert len(sample_dataframe) == original_length

    def test_name_property(self) -> None:
        """FilterStep has correct name."""
        step = FilterStep(lambda df: df["a"] > 0)
        assert step.name == "FilterStep"


class TestDropStep:
    """Tests for DropStep (column removal)."""

    def test_drops_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """DropStep removes specified columns."""
        step = DropStep(["old_col", "status"])
        result = step.apply(sample_dataframe, pipeline_context)

        assert "old_col" not in result.columns
        assert "status" not in result.columns
        assert "a" in result.columns
        assert "b" in result.columns

    def test_handles_missing_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """DropStep handles missing columns gracefully."""
        step = DropStep(["nonexistent", "old_col"])
        result = step.apply(sample_dataframe, pipeline_context)

        assert "old_col" not in result.columns
        assert "a" in result.columns

    def test_empty_columns_raises(self) -> None:
        """DropStep raises ValueError for empty columns list."""
        with pytest.raises(ValueError, match="cannot be empty"):
            DropStep([])

    def test_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """DropStep does not mutate input DataFrame."""
        original_columns = list(sample_dataframe.columns)
        step = DropStep(["old_col"])
        _ = step.apply(sample_dataframe, pipeline_context)

        assert list(sample_dataframe.columns) == original_columns

    def test_name_property(self) -> None:
        """DropStep has correct name."""
        step = DropStep(["col"])
        assert step.name == "DropStep"


class TestRenameStep:
    """Tests for RenameStep (alias for MappingStep)."""

    def test_renames_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """RenameStep renames columns correctly."""
        step = RenameStep({"old_col": "new_col"})
        result = step.apply(sample_dataframe, pipeline_context)

        assert "new_col" in result.columns
        assert "old_col" not in result.columns

    def test_name_property(self) -> None:
        """RenameStep has correct name."""
        step = RenameStep({"a": "b"})
        assert step.name == "RenameStep"

    def test_empty_mapping_raises(self) -> None:
        """RenameStep raises ValueError for empty mapping."""
        with pytest.raises(ValueError, match="cannot be empty"):
            RenameStep({})
