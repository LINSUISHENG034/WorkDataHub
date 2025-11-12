import uuid
from datetime import timezone
from typing import Any, Dict, List
from importlib import import_module

import pandas as pd
import pytest

from work_data_hub.config import get_settings
from src.work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig
from src.work_data_hub.domain.pipelines.core import Pipeline
from src.work_data_hub.domain.pipelines.examples import build_reference_pipeline
from src.work_data_hub.domain.pipelines.exceptions import PipelineStepError
from src.work_data_hub.domain.pipelines.types import (
    DataFrameStep,
    PipelineContext,
    PipelineResult,
    Row,
    RowTransformStep,
    StepResult,
)


class AddOneStep(DataFrameStep):
    def __init__(self):
        self._name = "add_one"

    @property
    def name(self) -> str:
        return self._name

    def execute(self, dataframe: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        updated = dataframe.copy(deep=True)
        updated["value"] = updated["value"] + 1
        return updated


class RowWarningStep(RowTransformStep):
    def __init__(self, trigger_value: int):
        self._name = "row_warning"
        self.trigger_value = trigger_value

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        warnings: List[str] = []
        if row["value"] > self.trigger_value:
            warnings.append("value_above_threshold")

        return StepResult(row=row, warnings=warnings, errors=[])


class RowErrorStep(RowTransformStep):
    def __init__(self):
        self._name = "row_error"

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        return StepResult(row=row, warnings=[], errors=["boom"])


class CaptureLogger:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def bind(self, **kwargs):
        # Return new logger sharing history but with bound context
        bound = CaptureLogger()
        bound.events = self.events
        for event in self.events:
            event.setdefault("bound", {}).update(kwargs)
        bound.events.append({"event": "bind", "bound": kwargs})
        return bound

    def info(self, event: str, **kwargs):
        self.events.append({"level": "info", "event": event, "payload": kwargs})

    def warning(self, event: str, **kwargs):
        self.events.append({"level": "warning", "event": event, "payload": kwargs})


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    """Ensure cached settings state never bleeds between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        name="unit_test_pipeline",
        steps=[
            StepConfig(
                name="add_one",
                import_path="tests.unit.domain.pipelines.test_core.AddOneStep",
            ),
            StepConfig(
                name="row_warning",
                import_path="tests.unit.domain.pipelines.test_core.RowWarningStep",
                options={"trigger_value": 1},
            ),
        ],
        stop_on_error=True,
    )


@pytest.mark.unit
def test_dataframe_and_row_steps_execute_in_order(pipeline_config):
    steps = [AddOneStep(), RowWarningStep(trigger_value=1)]
    pipeline = Pipeline(steps=steps, config=pipeline_config)

    input_df = pd.DataFrame([{"value": 1}])
    result = pipeline.run(input_df)

    assert isinstance(result, PipelineResult)
    assert result.success
    assert result.row == {"value": 2}
    assert result.metrics.executed_steps == ["add_one", "row_warning"]
    assert result.metrics.step_details[0].rows_processed == 1


@pytest.mark.unit
def test_pipeline_contracts_dataclasses(pipeline_config):
    single_config = PipelineConfig(
        name="contract_test",
        steps=[
            StepConfig(
                name="add_one",
                import_path="tests.unit.domain.pipelines.test_core.AddOneStep",
            )
        ],
        stop_on_error=True,
    )

    context = PipelineContext(
        pipeline_name="contract_test",
        execution_id=str(uuid.uuid4()),
        timestamp=pd.Timestamp.utcnow().to_pydatetime().replace(tzinfo=timezone.utc),
        config=single_config.model_dump(),
    )
    empty_df = pd.DataFrame([{"value": 1}])
    result = Pipeline(
        steps=[AddOneStep()],
        config=single_config,
    ).run(empty_df, context=context)

    assert result.context.pipeline_name == "contract_test"
    assert result.context.execution_id == context.execution_id
    assert result.metrics.duration_ms >= 0


@pytest.mark.unit
def test_pipeline_fail_fast_includes_step_index(pipeline_config):
    steps = [AddOneStep(), RowErrorStep()]
    pipeline = Pipeline(steps=steps, config=pipeline_config)

    with pytest.raises(PipelineStepError) as exc_info:
        pipeline.run(pd.DataFrame([{"value": 5}]))

    assert "step_index=1" in str(exc_info.value)
    assert "row_index=0" in str(exc_info.value)


@pytest.mark.unit
def test_pipeline_logging_events(monkeypatch, pipeline_config):
    from src.work_data_hub.domain.pipelines import core as core_module

    stub_logger = CaptureLogger()
    monkeypatch.setattr(core_module, "logger", stub_logger)

    pipeline = Pipeline(steps=[AddOneStep()], config=pipeline_config)
    pipeline.run(pd.DataFrame([{"value": 1}]))

    emitted_events = [event["event"] for event in stub_logger.events if "event" in event]
    assert "pipeline.started" in emitted_events
    assert "pipeline.step.started" in emitted_events
    assert "pipeline.step.completed" in emitted_events
    assert "pipeline.completed" in emitted_events


@pytest.mark.unit
def test_reference_pipeline_chaining():
    pipeline = build_reference_pipeline(min_total=10)
    data = pd.DataFrame(
        [
            {"region": "APAC", "revenue": 5, "expenses": 5},
            {"region": "APAC", "revenue": 2, "expenses": 1},
            {"region": "EMEA", "revenue": 20, "expenses": 0},
        ]
    )

    result = pipeline.run(data)

    assert result.success
    assert not result.output_data.empty
    assert set(result.output_data.columns) == {"region", "region_total"}
    assert result.output_data.loc[result.output_data["region"] == "APAC", "region_total"].iloc[0] == 10


@pytest.mark.unit
def test_pipeline_context_metadata_propagated(pipeline_config):
    pipeline = Pipeline(steps=[AddOneStep()], config=pipeline_config)
    context = PipelineContext(
        pipeline_name="unit_test_pipeline",
        execution_id=str(uuid.uuid4()),
        timestamp=pd.Timestamp.utcnow().to_pydatetime().replace(tzinfo=timezone.utc),
        config=pipeline_config.model_dump(),
        metadata={"source": "unit-test"},
    )

    result = pipeline.run(pd.DataFrame([{"value": 10}]), context=context)

    assert result.context is context
    assert result.row == {"value": 11}


@pytest.mark.unit
def test_pipeline_metrics_capture_row_counts(pipeline_config):
    steps = [AddOneStep(), RowWarningStep(trigger_value=5)]
    pipeline = Pipeline(steps=steps, config=pipeline_config)
    result = pipeline.run(pd.DataFrame([{"value": 10}, {"value": 1}]))

    assert len(result.metrics.step_details) == 2
    assert result.metrics.step_details[0].rows_processed == 2
    assert result.metrics.step_details[1].rows_processed == 2
    assert result.warnings == ["value_above_threshold"]


AC_TEST_MATRIX = {
    "AC1": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_contracts_dataclasses",
        "tests.unit.domain.pipelines.test_core.test_pipeline_context_metadata_propagated",
    ],
    "AC2": [
        "tests.unit.domain.pipelines.test_core.test_dataframe_and_row_steps_execute_in_order",
    ],
    "AC3": [
        "tests.unit.domain.pipelines.test_core.test_dataframe_and_row_steps_execute_in_order",
    ],
    "AC4": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_fail_fast_includes_step_index",
    ],
    "AC5": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_logging_events",
        "tests.unit.domain.pipelines.test_core.test_pipeline_metrics_capture_row_counts",
    ],
    "AC6": [
        "tests.unit.domain.pipelines.test_core.test_reference_pipeline_chaining",
    ],
    "AC7": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_contracts_dataclasses",
        "tests.unit.domain.pipelines.test_core.test_pipeline_context_metadata_propagated",
    ],
    "AC8": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_task_matrix_ac8",
    ],
}


def _resolve_callable(dotted_name: str):
    module_path, _, attr = dotted_name.rpartition(".")
    module = import_module(module_path)
    return getattr(module, attr, None)


def test_pipeline_task_matrix_ac8():
    """
    Ensure every acceptance criterion maps to at least one concrete test.
    """

    missing = {}
    for ac, tests in AC_TEST_MATRIX.items():
        if not tests:
            missing[ac] = ["<no tests listed>"]
            continue

        unresolved = []
        for dotted in tests:
            func = _resolve_callable(dotted)
            if not callable(func):
                unresolved.append(dotted)
        if unresolved:
            missing[ac] = unresolved

    assert not missing, f"Traceability gaps detected: {missing}"
