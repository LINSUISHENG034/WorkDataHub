# INITIAL.md — Orchestration Follow‑Up (Multi‑File, Flag Normalization, DB Conn Context, Display Consistency)

Purpose: Implement the suggested next steps for the Dagster orchestration layer. Add practical multi‑file processing, normalize execution flags, ensure DB connection cleanup via context managers, and make CLI output consistent with the effective execution mode. Keep plan‑only as the default; don’t introduce advanced Dagster features (e.g., DynamicOutput) yet.

Note for Claude: Activate PowerShell venv with `.\.venv\Scripts\Activate.ps1` (not `.venv_linux/bin/activate`). Use uv: `uv venv && uv sync`, run via `uv run ...`.

## FEATURE
- Multi‑file: Process up to N discovered files in one run and load once.
- Flag normalization: Unify execution mode under one source of truth; avoid conflicting `--plan-only` vs `--execute` signals.
- DB connection context: Open psycopg2 connections with a context manager to ensure proper closure.
- Display consistency: CLI output (plan/execution and SQL plans) matches the effective execution mode.

## SCOPE
- In‑scope:
  - Add a combined op or adjust existing ops to support multi‑file processing without Dagster dynamic mapping. Recommended: a new `read_and_process_trustee_files_op(file_paths: list[str], sheet: int, max_files: int) -> list[dict]` that iterates paths, calls `read_excel_rows(path, sheet)` and `process(rows, data_source=path)` per file, and accumulates results.
  - In `load_op`, when executing (not plan‑only), use `with psycopg2.connect(dsn) as conn:` before calling `load(...)`.
  - Normalize flags in `jobs.py`: derive a single `effective_plan_only` boolean (e.g., from `--execute`) and use it for both run_config and display. Either:
    - Deprecate `--plan-only` (keep for compatibility but ignore if `--execute` present), or
    - Remove `--plan-only` and rely solely on `--execute` as the user‑facing flag.
  - Update help text to document precedence/behavior.
  - Tests: multi‑file accumulation; CLI display consistency; DB context path smoke (mocked connect); keep existing tests green.
- Non‑goals:
  - Dagster dynamic mapping or assets; new domains; scheduler/resources.

## CONTEXT SNAPSHOT
```
src/work_data_hub/orchestration/
  ops.py                      # existing ops (add new op or enhance)
  jobs.py                     # CLI + job wiring (normalize flags; multi‑file path)
src/work_data_hub/io/readers/excel_reader.py
src/work_data_hub/domain/trustee_performance/service.py
src/work_data_hub/io/loader/warehouse_loader.py
tests/orchestration/{test_ops.py,test_jobs.py}
```

## EXAMPLES
- New op (preferred) to avoid dynamic mapping:
```python
from typing import List, Dict
from dagster import op, Config, OpExecutionContext
from ..io.readers.excel_reader import read_excel_rows
from ..domain.trustee_performance.service import process

class ReadProcessConfig(Config):
    sheet: int = 0
    max_files: int = 1

@op
def read_and_process_trustee_files_op(
    context: OpExecutionContext, config: ReadProcessConfig, file_paths: List[str]
) -> List[Dict]:
    paths = (file_paths or [])[: max(1, config.max_files)]
    all_processed: List[Dict] = []
    for p in paths:
        rows = read_excel_rows(p, sheet=config.sheet)
        models = process(rows, data_source=p)
        all_processed.extend([m.model_dump() for m in models])
    context.log.info(f"Processed {len(paths)} files, produced {len(all_processed)} records")
    return all_processed
```

- DB connection context in load_op:
```python
if not config.plan_only:
    import psycopg2
    dsn = get_settings().database.get_connection_string()
    with psycopg2.connect(dsn) as conn:
        return load(table=config.table, rows=processed_rows, mode=config.mode, pk=config.pk, conn=conn)
return load(table=config.table, rows=processed_rows, mode=config.mode, pk=config.pk, conn=None)
```

- Flag normalization in jobs.py:
```python
effective_plan_only = not args.execute if hasattr(args, "execute") else getattr(args, "plan_only", True)
# Use effective_plan_only for run_config and for display/printing logic
run_config["ops"]["load_op"]["config"]["plan_only"] = effective_plan_only
if effective_plan_only:
    # show SQL plans if available
```

## DOCUMENTATION
- Dagster ops: https://docs.dagster.io/concepts/ops-jobs-graphs/ops
- Dagster in‑process execution: https://docs.dagster.io/guides/dagster/run-a-job
- Pydantic v2 validators: https://docs.pydantic.dev/latest/concepts/validators/
- Psycopg2 connection: https://www.psycopg.org/docs/module.html#psycopg2.connect

## INTEGRATION POINTS
- `jobs.py`: parse `--execute`, `--max-files`; compute `effective_plan_only`; wire new combined op or adjust sequence to produce a single accumulated list for `load_op`.
- `ops.py`: implement `read_and_process_trustee_files_op` (or enhance existing ops accordingly); keep existing ops for backward‑compatibility.
- `load_op`: adopt connection context manager; maintain plan‑only default.

## GOTCHAS & QUIRKS
- Without dynamic mapping, iteration must occur inside an op or via a fixed slice. Prefer the new combined op to keep the graph static.
- Preserve JSON‑serializable data contracts between ops.
- Maintain safe default (plan‑only) and guard execution behind `--execute`.
- Ensure tests do not require a live DB; mock psycopg2 in execute path tests.

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```
Optional (local):
```powershell
.\.venv\Scripts\Activate.ps1
uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 1  # requires DB env
uv run python -m src.work_data_hub.orchestration.jobs --max-files 2            # plan‑only
```

## ACCEPTANCE CRITERIA
- [ ] Multi‑file: job processes up to N files and loads once; records are accumulated correctly.
- [ ] Flags: one source of truth for execution mode; help text documents behavior; display reflects effective mode.
- [ ] DB connection uses a context manager; no persistent open connection on errors.
- [ ] Tests: multi‑file accumulation (mocked), CLI display consistency, execute path (psycopg2 mocked).
- [ ] Ruff, mypy, pytest all pass.

## ROLLOUT & RISK
- Keeps safe defaults; explicit `--execute` prevents accidental DB writes.
- No DAG structure changes beyond a new combined op; minimal risk.
- Future: can replace combined op with DynamicOutput mapping when scaling.

## APPENDICES
Sample env (do not commit secrets):
```powershell
$env:WDH_DATABASE__HOST = "localhost"
$env:WDH_DATABASE__PORT = "5432"
$env:WDH_DATABASE__USER = "wdh_user"
$env:WDH_DATABASE__PASSWORD = "secret"
$env:WDH_DATABASE__DB = "wdh"
# Or URI:
$env:WDH_DATABASE__URI = "postgresql://wdh_user:secret@localhost:5432/wdh"
```

