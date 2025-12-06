"""Performance regression tracking for sample pipeline execution."""

from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.pipeline_config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline
from work_data_hub.domain.pipelines.types import DataFrameStep

BASELINE_FILE = Path(
    os.environ.get("PERF_BASELINE_FILE", "tests/.performance_baseline.json")
)
BASELINE_KEY = "sample_pipeline_ms"


class NoOpDataFrameStep(DataFrameStep):
    """Minimal DataFrame step for performance sampling."""

    name = "noop"

    def execute(self, df: pd.DataFrame, context):
        return df


@pytest.mark.integration
@pytest.mark.performance
def test_sample_pipeline_performance_regression() -> None:
    """Warn (not fail) if pipeline execution regresses by >20% vs baseline."""
    df = pd.DataFrame({"value": range(10_000)})
    pipeline = Pipeline(
        steps=[NoOpDataFrameStep()],
        config=PipelineConfig(
            name="performance_probe",
            steps=[
                StepConfig(
                    name="noop",
                    import_path="tests.integration.test_performance_baseline.NoOpDataFrameStep",
                )
            ],
            stop_on_error=True,
        ),
    )

    start = time.perf_counter()
    result = pipeline.run(df)
    duration_ms = (time.perf_counter() - start) * 1000
    assert result.success is True

    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())
        baseline_ms = float(baseline.get(BASELINE_KEY, duration_ms))
        regression_pct = (
            ((duration_ms - baseline_ms) / baseline_ms) * 100 if baseline_ms else 0.0
        )
        if regression_pct > 20:
            warnings.warn(
                f"Performance regression detected: {regression_pct:.1f}% slower "
                f"(current={duration_ms:.1f}ms, baseline={baseline_ms:.1f}ms)",
                UserWarning,
            )
        if duration_ms < baseline_ms:
            BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
            BASELINE_FILE.write_text(json.dumps({BASELINE_KEY: duration_ms}, indent=2))
    else:
        baseline = {BASELINE_KEY: duration_ms}
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(baseline, indent=2))
