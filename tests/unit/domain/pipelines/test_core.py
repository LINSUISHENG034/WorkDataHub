import time
import uuid
from datetime import timezone
from importlib import import_module
from typing import Any, Dict, List

import pandas as pd
import pytest

from work_data_hub.config import get_settings
from src.work_data_hub.domain.pipelines.pipeline_config import (
    PipelineConfig,
    StepConfig,
)
from src.work_data_hub.domain.pipelines.core import Pipeline
from src.work_data_hub.domain.pipelines.examples import build_reference_pipeline
from src.work_data_hub.domain.pipelines.exceptions import PipelineStepError, StepSkipped
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

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
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


class OptionalStep(DataFrameStep):
    def __init__(self, reason: str):
        self._name = "optional_enrichment"
        self.reason = reason

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        raise StepSkipped(self.reason)


class IntermittentFailureRowStep(RowTransformStep):
    def __init__(self, failing_values: List[int]):
        self._name = "intermittent_row_failure"
        self.failing_values = set(failing_values)

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        if row["value"] in self.failing_values:
            raise ValueError(f"value {row['value']} failed validation")
        return StepResult(row=row, warnings=[], errors=[])


class RowPassThroughStep(RowTransformStep):
    def __init__(self):
        self._name = "row_passthrough"

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        return StepResult(row=row, warnings=[], errors=[])


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

    emitted_events = [
        event["event"] for event in stub_logger.events if "event" in event
    ]
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
    assert (
        result.output_data.loc[
            result.output_data["region"] == "APAC", "region_total"
        ].iloc[0]
        == 10
    )


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


@pytest.mark.unit
def test_pipeline_continues_when_stop_on_error_disabled():
    config = PipelineConfig(
        name="soft_fail_pipeline",
        steps=[
            StepConfig(
                name="intermittent_row_failure",
                import_path="tests.unit.domain.pipelines.test_core.IntermittentFailureRowStep",
            )
        ],
        stop_on_error=False,
    )
    pipeline = Pipeline(
        steps=[IntermittentFailureRowStep(failing_values=[2])],
        config=config,
    )
    data = pd.DataFrame([{"value": 1}, {"value": 2}, {"value": 3}])

    result = pipeline.run(data)

    assert not result.success
    assert any("Row 1" in error for error in result.errors)
    # Pipeline kept processing even though an error occurred.
    pd.testing.assert_frame_equal(result.output_data.reset_index(drop=True), data)


@pytest.mark.unit
def test_error_rows_capture_row_context():
    config = PipelineConfig(
        name="error_row_pipeline",
        steps=[
            StepConfig(
                name="intermittent_row_failure",
                import_path="tests.unit.domain.pipelines.test_core.IntermittentFailureRowStep",
            )
        ],
        stop_on_error=False,
    )
    pipeline = Pipeline(
        steps=[IntermittentFailureRowStep(failing_values=[5])],
        config=config,
    )
    data = pd.DataFrame([{"value": 4}, {"value": 5}])

    result = pipeline.run(data)

    assert result.error_rows, "Expected error_rows to capture failing rows"
    captured = result.error_rows[0]
    assert captured["row_index"] == 1
    assert captured["row_data"]["value"] == 5
    assert captured["step_name"] == "intermittent_row_failure"
    assert "value 5 failed validation" in captured["error"]


@pytest.mark.unit
def test_optional_step_skip_emits_warning_and_continues():
    config = PipelineConfig(
        name="optional_pipeline",
        steps=[
            StepConfig(
                name="add_one_pre",
                import_path="tests.unit.domain.pipelines.test_core.AddOneStep",
            ),
            StepConfig(
                name="optional_enrichment",
                import_path="tests.unit.domain.pipelines.test_core.OptionalStep",
            ),
            StepConfig(
                name="add_one_post",
                import_path="tests.unit.domain.pipelines.test_core.AddOneStep",
            ),
        ],
    )
    pipeline = Pipeline(
        steps=[AddOneStep(), OptionalStep("Service unavailable"), AddOneStep()],
        config=config,
    )
    data = pd.DataFrame([{"value": 1}])

    result = pipeline.run(data)

    assert result.success
    assert result.warnings == ["Step skipped: Service unavailable"]
    assert result.row == {"value": 3}


def _measure_runtime(callable_obj, repetitions: int = 3) -> float:
    """Return the best runtime across repetitions to reduce noise."""
    durations: List[float] = []
    for _ in range(repetitions):
        start = time.perf_counter()
        callable_obj()
        durations.append(time.perf_counter() - start)
    return min(durations)


@pytest.mark.performance
def test_dataframe_step_performance_benchmark():
    config = PipelineConfig(
        name="dataframe_perf",
        steps=[
            StepConfig(
                name="add_one",
                import_path="tests.unit.domain.pipelines.test_core.AddOneStep",
            )
        ],
    )
    pipeline = Pipeline(steps=[AddOneStep()], config=config)
    dataset = pd.DataFrame([{"value": value} for value in range(2000)])

    # Warmup to account for psutil import/memory introspection.
    pipeline.run(dataset)

    best_duration = _measure_runtime(lambda: pipeline.run(dataset))
    assert best_duration < 0.1, (
        f"DataFrame step exceeded 100ms budget ({best_duration:.4f}s)"
    )


@pytest.mark.performance
def test_row_step_performance_benchmark():
    config = PipelineConfig(
        name="row_perf",
        steps=[
            StepConfig(
                name="row_passthrough",
                import_path="tests.unit.domain.pipelines.test_core.RowPassThroughStep",
            )
        ],
    )
    pipeline = Pipeline(steps=[RowPassThroughStep()], config=config)
    dataset = pd.DataFrame([{"value": value} for value in range(400)])

    pipeline.run(dataset)

    best_duration = _measure_runtime(lambda: pipeline.run(dataset))
    per_row = best_duration / len(dataset)
    assert per_row < 0.001, f"Row step overhead {per_row:.6f}s exceeded 1ms target"


AC_TEST_MATRIX = {
    "AC1": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_contracts_dataclasses",
        "tests.unit.domain.pipelines.test_core.test_pipeline_context_metadata_propagated",
        "tests.unit.domain.pipelines.test_core.test_pipeline_continues_when_stop_on_error_disabled",
        "tests.unit.domain.pipelines.test_core.test_error_rows_capture_row_context",
    ],
    "AC2": [
        "tests.unit.domain.pipelines.test_core.test_dataframe_and_row_steps_execute_in_order",
    ],
    "AC3": [
        "tests.unit.domain.pipelines.test_core.test_dataframe_and_row_steps_execute_in_order",
        "tests.unit.domain.pipelines.test_core.test_optional_step_skip_emits_warning_and_continues",
    ],
    "AC4": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_fail_fast_includes_step_index",
        "tests.unit.domain.pipelines.test_core.test_dataframe_step_performance_benchmark",
    ],
    "AC5": [
        "tests.unit.domain.pipelines.test_core.test_pipeline_logging_events",
        "tests.unit.domain.pipelines.test_core.test_pipeline_metrics_capture_row_counts",
        "tests.unit.domain.pipelines.test_core.test_row_step_performance_benchmark",
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


# ============================================================================
# Story 1.10 Advanced Retry Logic Tests (AC #5, AC #6)
# ============================================================================


class RetryableErrorStep(DataFrameStep):
    """Step that raises retryable errors a specified number of times before succeeding."""

    def __init__(self, error_type: str, fail_count: int = 2):
        self._name = "retryable_error_step"
        self.error_type = error_type
        self.fail_count = fail_count
        self.attempt_count = 0

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        self.attempt_count += 1
        if self.attempt_count <= self.fail_count:
            if self.error_type == "database":
                import psycopg2

                raise psycopg2.OperationalError("connection lost")
            elif self.error_type == "network":
                raise ConnectionResetError("network connection reset")
            elif self.error_type == "http_500":
                from requests import HTTPError, Response

                resp = Response()
                resp.status_code = 500
                raise HTTPError(response=resp)
            elif self.error_type == "http_429":
                from requests import HTTPError, Response

                resp = Response()
                resp.status_code = 429
                raise HTTPError(response=resp)
            elif self.error_type == "http_404":
                from requests import HTTPError, Response

                resp = Response()
                resp.status_code = 404
                raise HTTPError(response=resp)
        return dataframe


@pytest.mark.unit
def test_retry_with_database_error():
    """Test database errors retry up to 5 times (database tier)."""
    config = PipelineConfig(
        name="database_retry_test",
        steps=[
            StepConfig(
                name="retryable_error_step",
                import_path="tests.unit.domain.pipelines.test_core.RetryableErrorStep",
            )
        ],
    )
    step = RetryableErrorStep(error_type="database", fail_count=4)
    pipeline = Pipeline(steps=[step], config=config)
    data = pd.DataFrame([{"value": 1}])

    result = pipeline.run(data)

    assert result.success
    assert step.attempt_count == 5  # 4 failures + 1 success


@pytest.mark.unit
def test_retry_with_network_error():
    """Test network errors retry up to 3 times (network tier)."""
    config = PipelineConfig(
        name="network_retry_test",
        steps=[
            StepConfig(
                name="retryable_error_step",
                import_path="tests.unit.domain.pipelines.test_core.RetryableErrorStep",
            )
        ],
    )
    step = RetryableErrorStep(error_type="network", fail_count=2)
    pipeline = Pipeline(steps=[step], config=config)
    data = pd.DataFrame([{"value": 1}])

    result = pipeline.run(data)

    assert result.success
    assert step.attempt_count == 3  # 2 failures + 1 success


@pytest.mark.unit
def test_retry_with_http_500():
    """Test HTTP 500 errors retry up to 2 times (http_500_502_504 tier)."""
    config = PipelineConfig(
        name="http_500_retry_test",
        steps=[
            StepConfig(
                name="retryable_error_step",
                import_path="tests.unit.domain.pipelines.test_core.RetryableErrorStep",
            )
        ],
    )
    step = RetryableErrorStep(error_type="http_500", fail_count=1)
    pipeline = Pipeline(steps=[step], config=config)
    data = pd.DataFrame([{"value": 1}])

    result = pipeline.run(data)

    assert result.success
    assert step.attempt_count == 2  # 1 failure + 1 success


@pytest.mark.unit
def test_retry_with_http_429():
    """Test HTTP 429 errors retry up to 3 times (http_429_503 tier)."""
    config = PipelineConfig(
        name="http_429_retry_test",
        steps=[
            StepConfig(
                name="retryable_error_step",
                import_path="tests.unit.domain.pipelines.test_core.RetryableErrorStep",
            )
        ],
    )
    step = RetryableErrorStep(error_type="http_429", fail_count=2)
    pipeline = Pipeline(steps=[step], config=config)
    data = pd.DataFrame([{"value": 1}])

    result = pipeline.run(data)

    assert result.success
    assert step.attempt_count == 3  # 2 failures + 1 success


@pytest.mark.unit
def test_no_retry_with_http_404():
    """Test HTTP 404 (permanent error) does NOT retry."""
    config = PipelineConfig(
        name="http_404_no_retry_test",
        steps=[
            StepConfig(
                name="retryable_error_step",
                import_path="tests.unit.domain.pipelines.test_core.RetryableErrorStep",
            )
        ],
    )
    step = RetryableErrorStep(error_type="http_404", fail_count=1)
    pipeline = Pipeline(steps=[step], config=config)
    data = pd.DataFrame([{"value": 1}])

    with pytest.raises(PipelineStepError) as exc_info:
        pipeline.run(data)

    assert step.attempt_count == 1  # No retries for permanent error
    assert "Step execution failed" in str(exc_info.value)


# ============================================================================
# Legacy Row-Based Pipeline.execute() Backward Compatibility Tests
# (Merged from tests/domain/pipelines/test_core.py)
# ============================================================================


class LegacyRowStep:
    """Row-based step for backward compatibility testing."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context) -> StepResult:
        return StepResult(row={**row, f"{self._name}_value": "processed"})


def _build_legacy_row_pipeline(stop_on_error: bool = True) -> Pipeline:
    config = PipelineConfig(
        name="legacy_row_pipeline",
        steps=[
            StepConfig(
                name="step1",
                import_path="tests.unit.domain.pipelines.test_core.LegacyRowStep",
            ),
            StepConfig(
                name="step2",
                import_path="tests.unit.domain.pipelines.test_core.LegacyRowStep",
            ),
        ],
        stop_on_error=stop_on_error,
    )
    steps = [LegacyRowStep("step1"), LegacyRowStep("step2")]
    return Pipeline(steps=steps, config=config)


@pytest.mark.unit
def test_execute_single_row_backwards_compatibility():
    """Dict-based execute() still works for single-row processing."""
    pipeline = _build_legacy_row_pipeline()
    result = pipeline.execute({"value": 1})

    assert result.row["step1_value"] == "processed"
    assert result.row["step2_value"] == "processed"
    assert result.metrics.executed_steps == ["step1", "step2"]


@pytest.mark.unit
def test_execute_preserves_input_row():
    """execute() does not mutate the original input dict."""
    pipeline = _build_legacy_row_pipeline()
    row = {"value": 1}
    pipeline.execute(row)

    assert row == {"value": 1}


@pytest.mark.unit
def test_execute_aggregates_warnings_and_errors():
    """execute() collects warnings and errors from all steps."""

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
                name="warn",
                import_path="tests.unit.domain.pipelines.test_core.LegacyRowStep",
            ),
            StepConfig(
                name="err",
                import_path="tests.unit.domain.pipelines.test_core.LegacyRowStep",
            ),
        ],
        stop_on_error=False,
    )

    pipeline = Pipeline(steps=[WarningStep("warn"), ErrorStep("err")], config=config)
    result = pipeline.execute({"value": 1})

    assert result.warnings == ["warn"]
    assert result.errors == ["err"]


@pytest.mark.unit
def test_execute_stop_on_error_true():
    """execute() raises PipelineStepError when stop_on_error=True."""

    class BoomStep(LegacyRowStep):
        def apply(self, row: Row, context) -> StepResult:
            raise ValueError("explode")

    config = PipelineConfig(
        name="boom",
        steps=[
            StepConfig(
                name="boom",
                import_path="tests.unit.domain.pipelines.test_core.LegacyRowStep",
            )
        ],
        stop_on_error=True,
    )

    pipeline = Pipeline(steps=[BoomStep("boom")], config=config)

    with pytest.raises(PipelineStepError):
        pipeline.execute({"value": 1})
