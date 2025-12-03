"""Tests for base TransformStep and Pipeline classes (AC 5.6.1)."""

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.transforms import Pipeline, TransformStep


class ConcreteStep(TransformStep):
    """Concrete implementation for testing."""

    def __init__(self, suffix: str = "_transformed"):
        self._suffix = suffix

    @property
    def name(self) -> str:
        return "ConcreteStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        result = df.copy()
        result.columns = [f"{col}{self._suffix}" for col in result.columns]
        return result


class TestTransformStep:
    """Tests for TransformStep abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """TransformStep cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TransformStep()  # type: ignore

    def test_concrete_implementation_works(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Concrete implementation can be instantiated and used."""
        step = ConcreteStep()
        result = step.apply(sample_dataframe, pipeline_context)

        assert step.name == "ConcreteStep"
        assert all(col.endswith("_transformed") for col in result.columns)

    def test_step_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Step should not mutate the input DataFrame."""
        original_columns = list(sample_dataframe.columns)
        step = ConcreteStep()
        _ = step.apply(sample_dataframe, pipeline_context)

        assert list(sample_dataframe.columns) == original_columns


class TestPipeline:
    """Tests for Pipeline composition class."""

    def test_pipeline_executes_steps_in_order(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Pipeline executes steps in sequence."""
        step1 = ConcreteStep("_first")
        step2 = ConcreteStep("_second")
        pipeline = Pipeline([step1, step2])

        result = pipeline.execute(sample_dataframe, pipeline_context)

        # Columns should have both suffixes applied in order
        assert all(col.endswith("_first_second") for col in result.columns)

    def test_empty_pipeline_returns_copy(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Empty pipeline returns a copy of input."""
        pipeline = Pipeline([])
        result = pipeline.execute(sample_dataframe, pipeline_context)

        pd.testing.assert_frame_equal(result, sample_dataframe)
        assert result is not sample_dataframe

    def test_pipeline_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Pipeline should not mutate the input DataFrame."""
        original_data = sample_dataframe.copy()
        pipeline = Pipeline([ConcreteStep()])
        _ = pipeline.execute(sample_dataframe, pipeline_context)

        pd.testing.assert_frame_equal(sample_dataframe, original_data)

    def test_single_step_pipeline(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """Pipeline with single step works correctly."""
        pipeline = Pipeline([ConcreteStep("_only")])
        result = pipeline.execute(sample_dataframe, pipeline_context)

        assert all(col.endswith("_only") for col in result.columns)
