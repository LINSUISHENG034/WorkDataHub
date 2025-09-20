# INITIAL.md — Shared Cleansing Pipeline Foundation (Task 1)

## FEATURE
Introduce a reusable domain-cleansing pipeline foundation (TransformStep API + pipeline builder + config loader + diagnostics) that domain services can orchestrate before enrichment.

## SCOPE
- In-scope:
  - Define the core pipeline abstractions (step contract, context, pipeline runner, step ordering, error capture) under a new `src/work_data_hub/domain/pipelines/` package.
  - Provide helpers for composing steps from config (YAML/JSON/dict) with validation.
  - Integrate existing cleansing rules (`src/work_data_hub/cleansing/`) via adapters usable inside steps.
  - Deliver unit tests covering step execution order, short-circuit/error propagation, metrics collection, and config-driven assembly.
  - Add developer documentation (docstring + module-level README-style comment) explaining how domain services invoke the pipeline.
- Non-goals:
  - Do NOT refactor existing domain services yet (handled in Task 3).
  - Do NOT modify Company Enrichment internals (adapter support comes later).
  - Do NOT introduce new CLI/ops wiring; focus on library surface.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  cleansing/
    registry.py
    rules/
  domain/
    annuity_performance/
      service.py  # current monolithic flow we will refactor later
  utils/
    logging.py
    types.py
```

## EXAMPLES
- Path: `src/work_data_hub/cleansing/registry.py` — registry pattern & logging style to reuse when exposing cleansing rule adapters.
- Path: `src/work_data_hub/domain/sample_trustee_performance/service.py` — current domain orchestration (logging + error handling) the pipeline will ultimately plug into.
- Path: `tests/domain/company_enrichment/test_lookup_queue.py` — test structuring with mocks/context managers to mirror for pipeline tests.
- Snippet:
```python
# Desired usage inside future domain service
pipeline = build_pipeline(config, steps=[mapping_step, numeric_cleanup_step])
result = pipeline.execute(raw_row, data_source="规模明细")
assert result.row["计划代码"] == "AN001"
```

## DOCUMENTATION
- File: `docs/company_id/simplified/PROBLEM.CI-001_问题定义.md` — context for enrichment inputs (ensure pipeline prepares plan/customer/account fields cleanly later).
- File: `README.md` (Architecture at a Glance) — maintain conventions for domain services.
- File: `ROADMAP.md` (Milestone 2 entries C-014, F-018, C-065) — keep scope aligned.

## INTEGRATION POINTS
- Data models: introduce lightweight dataclasses / TypedDicts for pipeline rows (e.g., `PipelineRow` alias) in new package.
- Config: allow pipeline definition via dict/YAML (keys: `name`, `steps`, `requires`, `on_error`); define schema using Pydantic model under `pipelines/config.py`.
- Logging/metrics: integrate with `logging.getLogger(__name__)`; expose step timings & counts via simple struct.
- Tests: add `tests/domain/pipelines/test_core.py` (unit) and `tests/domain/pipelines/test_config_builder.py`.

## DATA CONTRACTS
```python
# src/work_data_hub/domain/pipelines/types.py
from dataclasses import dataclass
from typing import Dict, Any, Optional

Row = Dict[str, Any]

@dataclass
class StepResult:
    row: Row
    warnings: list[str]
    errors: list[str]
    metadata: dict[str, Any]

@dataclass
class PipelineMetrics:
    executed_steps: list[str]
    duration_ms: int
```

```python
# src/work_data_hub/domain/pipelines/config.py
from pydantic import BaseModel, Field

class StepConfig(BaseModel):
    name: str
    import_path: str  # e.g. "work_data_hub.domain.pipelines.steps.numeric.clean_decimal"
    options: dict[str, Any] = Field(default_factory=dict)
    requires: list[str] = Field(default_factory=list)

class PipelineConfig(BaseModel):
    name: str
    steps: list[StepConfig]
    stop_on_error: bool = True
```

## GOTCHAS & LIBRARY QUIRKS
- Keep pipeline execution synchronous for now; domain services run in sync context.
- Pydantic v2: use `.model_validate` for config ingestion; avoid `.parse_obj`.
- Ensure steps mutate row copies (not original dict) to avoid side-effects between retries.
- Use `time.perf_counter()` for metrics; convert to ms (int).
- Provide clear exception hierarchy (`PipelineStepError`, `PipelineAssemblyError`) to aid future ops integration.

## IMPLEMENTATION NOTES
- Create `src/work_data_hub/domain/pipelines/__init__.py` exporting public API (`build_pipeline`, `TransformStep`, `Pipeline`).
- Steps should be callables/classes implementing `apply(row, context) -> StepResult`.
- Supply adapters to wrap existing cleansing rules: e.g., `CleansingRuleStep.from_registry("decimal_quantization")`.
- Add docstring in module root describing sample usage.
- Keep functions <40 lines; prefer dataclasses & helpers for clarity.

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "pipelines"
uv run pytest -v tests/domain/pipelines/test_core.py
```

## ACCEPTANCE CRITERIA
- [ ] `build_pipeline` assembles steps from config and executes them in declared order with logging & metrics.
- [ ] Errors propagate according to config (`stop_on_error` vs warning) and include step metadata.
- [ ] At least one adapter demonstrates wrapping `cleansing.registry` rules into TransformSteps.
- [ ] Tests cover happy path, error handling, config validation, and registry-backed step assembly.

## ROLLOUT & RISK
- No migrations. Pure library addition — low risk.
- Future domain refactors (Task 3) will incrementally adopt the pipeline; ensure backwards compatibility by keeping old services untouched until refactor.
- Document rollback: remove new package if blocking issues arise (no persistent state).

## APPENDICES
```python
# tests/domain/pipelines/test_core.py skeleton
from src.work_data_hub.domain.pipelines import build_pipeline, TransformStep

class UpperCaseStep(TransformStep):
    name = "uppercase"
    def apply(self, row, context):
        value = row.get("customer_name")
        if value:
            row = {**row, "customer_name": value.upper()}
        return StepResult(row=row, warnings=[], errors=[], metadata={"changed": bool(value)})

def test_pipeline_executes_steps_in_order(sample_row):
    pipeline = build_pipeline(config=PIPELINE_CFG, steps=[UpperCaseStep()])
    result = pipeline.execute(sample_row)
    assert result.row["customer_name"] == "TEST CO"
    assert result.metrics.executed_steps == ["uppercase"]
```

```bash
# Useful search
rg "TransformStep" src/work_data_hub
rg "annuity_performance" src/work_data_hub/domain -n
```
