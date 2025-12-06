"""Tests for CleansingStep (AC 5.6.3)."""

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.transforms import CleansingStep
from work_data_hub.infrastructure.cleansing.registry import (
    CleansingRule,
    RuleCategory,
    registry as cleansing_registry,
)


def _register_test_rule() -> None:
    """Register a simple test rule with kwargs support (idempotent)."""
    if cleansing_registry.get_rule("test_append_suffix"):
        return
    cleansing_registry.register(
        CleansingRule(
            name="test_append_suffix",
            category=RuleCategory.STRING,
            description="Append suffix for testing kwargs passthrough",
            func=lambda value, suffix="!": f"{value}{suffix}",
        )
    )


class TestCleansingStep:
    """Tests for CleansingStep (cleansing integration)."""

    def test_cleansing_step_initialization(self) -> None:
        """CleansingStep can be initialized with domain name."""
        step = CleansingStep(domain="test_domain")
        assert step.name == "CleansingStep"

    def test_cleansing_step_with_columns(self) -> None:
        """CleansingStep can be initialized with specific columns."""
        step = CleansingStep(domain="test_domain", columns=["col1", "col2"])
        assert step.name == "CleansingStep"

    def test_cleansing_step_with_rules_override(self) -> None:
        """CleansingStep can be initialized with rules override."""
        step = CleansingStep(
            domain="test_domain",
            rules_override={"col1": ["trim_whitespace"]},
        )
        assert step.name == "CleansingStep"

    def test_cleansing_step_returns_dataframe(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CleansingStep returns a DataFrame."""
        step = CleansingStep(domain="nonexistent_domain")
        result = step.apply(sample_dataframe, pipeline_context)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_dataframe)

    def test_cleansing_step_does_not_mutate_input(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CleansingStep does not mutate input DataFrame."""
        original_data = sample_dataframe.copy()
        step = CleansingStep(domain="test_domain")
        _ = step.apply(sample_dataframe, pipeline_context)

        pd.testing.assert_frame_equal(sample_dataframe, original_data)

    def test_cleansing_step_handles_missing_columns(
        self, sample_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CleansingStep handles missing columns gracefully."""
        step = CleansingStep(
            domain="test_domain",
            columns=["nonexistent_column"],
        )
        result = step.apply(sample_dataframe, pipeline_context)

        # Should return copy without error
        assert len(result) == len(sample_dataframe)

    def test_cleansing_step_with_empty_dataframe(
        self, empty_dataframe: pd.DataFrame, pipeline_context: PipelineContext
    ) -> None:
        """CleansingStep handles empty DataFrame."""
        step = CleansingStep(domain="test_domain")
        result = step.apply(empty_dataframe, pipeline_context)

        assert len(result) == 0

    def test_rules_override_applies_kwargs(
        self, pipeline_context: PipelineContext
    ) -> None:
        """CleansingStep should honor rule kwargs via registry.apply_rules."""
        _register_test_rule()
        df_in = pd.DataFrame({"col1": ["a", "b"]})
        step = CleansingStep(
            domain="test_domain",
            rules_override={
                "col1": [{"name": "test_append_suffix", "kwargs": {"suffix": "?"}}]
            },
        )

        result = step.apply(df_in, pipeline_context)

        assert result["col1"].tolist() == ["a?", "b?"]
