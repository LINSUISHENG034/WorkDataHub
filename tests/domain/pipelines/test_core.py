"""
Integration-style tests that ensure the pipeline executor remains backwards
compatible with dict-based `execute` calls while honoring Story 1.5 features.
"""

import pandas as pd
import pytest
from unittest.mock import Mock

from src.work_data_hub.domain.pipelines.pipeline_config import (
    PipelineConfig,
    StepConfig,
)
from src.work_data_hub.domain.pipelines.core import Pipeline
from src.work_data_hub.domain.pipelines.exceptions import PipelineStepError
from src.work_data_hub.domain.pipelines.types import Row, StepResult


class LegacyRowStep:
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context) -> StepResult:
        return StepResult(row={**row, f"{self._name}_value": "processed"})


def build_row_pipeline(stop_on_error: bool = True) -> Pipeline:
    config = PipelineConfig(
        name="legacy_row_pipeline",
        steps=[
            StepConfig(
                name="step1",
                import_path="tests.domain.pipelines.test_core.LegacyRowStep",
            ),
            StepConfig(
                name="step2",
                import_path="tests.domain.pipelines.test_core.LegacyRowStep",
            ),
        ],
        stop_on_error=stop_on_error,
    )
    steps = [LegacyRowStep("step1"), LegacyRowStep("step2")]
    return Pipeline(steps=steps, config=config)


def test_execute_single_row_backwards_compatibility():
    pipeline = build_row_pipeline()
    result = pipeline.execute({"value": 1})

    assert result.row["step1_value"] == "processed"
    assert result.row["step2_value"] == "processed"
    assert result.metrics.executed_steps == ["step1", "step2"]


def test_execute_preserves_input_row():
    pipeline = build_row_pipeline()
    row = {"value": 1}
    pipeline.execute(row)

    assert row == {"value": 1}


def test_execute_aggregates_warnings_and_errors():
    class WarningStep(LegacyRowStep):
        def apply(self, row: Row, context) -> StepResult:
            return StepResult(row=row, warnings=["warn"], errors=[])

    class ErrorStep(LegacyRowStep):
        def apply(self, row: Row, context) -> StepResult:
            return StepResult(row=row, warnings=[], errors=["err"])

    config = PipelineConfig(
        name="warnings",
        steps=[
            StepConfig(
                name="warn", import_path="tests.domain.pipelines.test_core.WarningStep"
            ),
            StepConfig(
                name="err", import_path="tests.domain.pipelines.test_core.ErrorStep"
            ),
        ],
        stop_on_error=False,
    )

    pipeline = Pipeline(steps=[WarningStep("warn"), ErrorStep("err")], config=config)
    result = pipeline.execute({"value": 1})

    assert result.warnings == ["warn"]
    assert result.errors == ["err"]


def test_execute_stop_on_error_true():
    class BoomStep(LegacyRowStep):
        def apply(self, row: Row, context) -> StepResult:
            raise ValueError("explode")

    config = PipelineConfig(
        name="boom",
        steps=[
            StepConfig(
                name="boom", import_path="tests.domain.pipelines.test_core.BoomStep"
            )
        ],
        stop_on_error=True,
    )

    pipeline = Pipeline(steps=[BoomStep("boom")], config=config)

    with pytest.raises(PipelineStepError):
        pipeline.execute({"value": 1})
