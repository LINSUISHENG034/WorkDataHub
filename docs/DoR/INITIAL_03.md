# INITIAL.md — Dagster Wiring + CLI for Vertical Slice (Connector → Domain → Loader)

Purpose: Implement Dagster ops and a small in‑process job to wire the existing vertical slice end‑to‑end (file discovery → Excel read → trustee_performance transform → loader). Provide a thin CLI to run locally. Favor a DB‑optional path (plan‑only load) so tests don’t require PostgreSQL.

Read these first for context and constraints:
- docs/DoR/INITIAL_00.md (end‑to‑end slice intent and examples)
- docs/project/04_dependency_and_priority_analysis.md (pseudo‑code for ops/job composition)
- src/work_data_hub/config/settings.py (env config)
- src/work_data_hub/io/connectors/file_connector.py, io/readers/excel_reader.py
- src/work_data_hub/domain/trustee_performance/service.py
- src/work_data_hub/io/loader/warehouse_loader.py

## FEATURE
Create Dagster ops and a job that composes: discover → read → process → load for the `trustee_performance` domain, plus a CLI that executes the job in‑process with DB‑optional execution (plan‑only when no DB).

## SCOPE
- In‑scope:
  - New package `src/work_data_hub/orchestration/` with:
    - `ops.py`: `discover_files_op`, `read_excel_op`, `process_trustee_performance_op`, `load_op` (thin wrappers calling existing modules)
    - `jobs.py`: `trustee_performance_job()` and a `main()` to run via CLI (in‑process)
  - Extend `config/data_sources.yml` for `trustee_performance` with `table` and `pk` used by `load_op`.
  - Ensure ops exchange simple, JSON‑serializable payloads (paths, lists of dicts) to avoid Dagster type friction.
- Non‑goals:
  - Additional domains, schedules/sensors, resources, or deployment.
  - Airflow/other orchestrators or asset‑based refactors.
  - Real DB requirement in unit tests (keep plan‑only default).

## CONTEXT SNAPSHOT
```
src/work_data_hub/
  config/{settings.py, data_sources.yml}
  io/connectors/file_connector.py
  io/readers/excel_reader.py
  io/loader/warehouse_loader.py
  domain/trustee_performance/{models.py, service.py}
tests/
  io/{test_file_connector.py, test_excel_reader.py, test_warehouse_loader.py}
  test_integration.py  # E2E without Dagster

# Missing now: src/work_data_hub/orchestration/{ops.py, jobs.py}
```

## EXAMPLES (mirror these patterns)
- Path: `docs/project/04_dependency_and_priority_analysis.md` — sample ops/job composition to adapt
- Path: `tests/test_integration.py` — end‑to‑end flow without Dagster; replicate the same steps within Dagster ops
- Snippet (skeleton ops):
```python
from dagster import op, job
from ..config.settings import get_settings
from ..io.connectors.file_connector import DataSourceConnector
from ..io.readers.excel_reader import read_excel_rows
from ..domain.trustee_performance.service import process
from ..io.loader.warehouse_loader import load

@op
def discover_files_op(domain: str) -> list[str]:
    settings = get_settings()
    connector = DataSourceConnector(settings.data_sources_config)
    files = connector.discover(domain)
    return [f.path for f in files]

@op
def read_excel_op(path: str, sheet: int | str = 0) -> list[dict]:
    return read_excel_rows(path, sheet=sheet)

@op
def process_trustee_performance_op(rows: list[dict]) -> list[dict]:
    models = process(rows, data_source="dagster")
    return [m.model_dump() for m in models]

@op
def load_op(table: str, rows: list[dict], mode: str = "delete_insert", pk: list[str] | None = None, plan_only: bool = True) -> dict:
    conn = None if plan_only else ...  # look up real connection when enabled
    return load(table=table, rows=rows, mode=mode, pk=pk, conn=conn)

@job
def trustee_performance_job():
    # Wire a single file for simplicity; expand as needed
    discovered = discover_files_op.alias("discover_trustee_files")("trustee_performance")
    # In a full job, map over discovered; for now assume one file
    rows = read_excel_op(discovered[0])
    processed = process_trustee_performance_op(rows)
    load_op("trustee_performance", processed, pk=["report_date", "plan_code", "company_code"], plan_only=True)
```

## DOCUMENTATION
- Dagster ops & jobs: https://docs.dagster.io/concepts/ops-jobs-graphs/ops
- Dagster execution (in‑process): https://docs.dagster.io/guides/dagster/run-a-job
- Pydantic v2: https://docs.pydantic.dev/latest/
- Internal constraints: `CLAUDE.md`, `AGENTS.md`, and `docs/DoR/INITIAL_00.md`

## INTEGRATION POINTS
- Config/ENV:
  - Use `get_settings()` for `data_base_dir` and `data_sources_config`.
  - Add to `data_sources.yml` under `trustee_performance`:
    ```yaml
    table: trustee_performance
    pk: [report_date, plan_code, company_code]
    ```
- File discovery: `DataSourceConnector.discover(domain)` → pick one latest file (already implemented).
- Excel read: `read_excel_rows(path, sheet)`.
- Domain process: `process(rows) -> list[TrusteePerformanceOut]` → convert to `list[dict]` for loader.
- Loader: `load(table, rows, mode, pk, conn=None)` → plan‑only by default (no DB during tests).
- CLI: A `main()` in `jobs.py` that parses `--domain`, `--plan-only`, `--mode`, and runs `execute_in_process()`.

## DATA CONTRACTS (op I/O)
- `discover_files_op(domain: str) -> list[str]` (paths)
- `read_excel_op(path: str, sheet: int|str=0) -> list[dict]` (rows)
- `process_trustee_performance_op(rows: list[dict]) -> list[dict]` (validated rows suitable for loader)
- `load_op(table: str, rows: list[dict], mode: str, pk: list[str], plan_only: bool) -> dict` (loader result/plan)

## GOTCHAS & LIBRARY QUIRKS
- Keep op inputs/outputs JSON‑serializable; don’t pass Pydantic models directly between ops.
- Avoid importing psycopg2 in default code paths used by tests; keep `plan_only=True` by default.
- Use small, single‑purpose ops; no global state.
- If multiple files are discovered, either select latest (existing logic) or iterate later; for MVP, a single file is fine.

## IMPLEMENTATION NOTES
```
src/work_data_hub/orchestration/
  __init__.py
  ops.py      # four ops above
  jobs.py     # job + CLI (main)
```
- CLI patterns (choose one):
  - Simple module entry: `uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --plan-only`
  - Or add a `console_scripts` entry later (out of scope here).
- `jobs.py::main()`:
  - Parse args: `--domain`, `--mode {delete_insert,append}`, `--plan-only`, `--sheet`.
  - Build run config if needed; call `trustee_performance_job.execute_in_process()` and print result/plan.
- Add minimal smoke test invoking `execute_in_process()` with a tmp data directory + config.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```
Optional local run examples (no DB):
```bash
uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --plan-only
```

## ACCEPTANCE CRITERIA
- [ ] `src/work_data_hub/orchestration/{ops.py,jobs.py}` created with four ops and a job wiring the slice
- [ ] Ops exchange JSON‑serializable payloads; no Pydantic models across op boundaries
- [ ] `data_sources.yml` extended with `table` and `pk` for trustee_performance
- [ ] CLI runs the job in‑process and prints loader plan (DELETE then INSERT) without DB
- [ ] Add smoke test covering in‑process execution path (plan‑only)
- [ ] Ruff, mypy, and pytest all green

## ROLLOUT & RISK
- Start with `plan_only=True` default to avoid DB coupling; enable DB execution via a flag later.
- Keep CLI and ops small; future work can add resources/schedules.
- If config is missing `table`/`pk`, `load_op` should raise a clear error.

## APPENDICES
Minimal `jobs.py` main skeleton:
```python
import argparse
from dagster import execute_job
from .ops import discover_files_op, read_excel_op, process_trustee_performance_op, load_op
from .jobs import trustee_performance_job

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="trustee_performance")
    parser.add_argument("--mode", default="delete_insert", choices=["delete_insert", "append"])
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    # For MVP, rely on default job config and plan-only behavior.
    result = trustee_performance_job.execute_in_process()
    print({"success": result.success})

if __name__ == "__main__":
    main()
```
