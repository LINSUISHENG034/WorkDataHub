# INITIAL.md — Vertical Slice 1 (Connector → Domain Service → Loader → Dagster)

Purpose: Convert the modernization plan into a concrete, one‑pass, testable implementation for the first vertical slice. Claude should produce a minimal, working pipeline from file discovery to Postgres load, with strong typing, tests, and Dagster wiring.

Read these first for context and constraints:
- docs/project/01_architecture_analysis_report.md
- docs/project/02_production_data_sample_analysis.md
- docs/project/03_specified_data_source_problems_analysis.md
- docs/project/04_dependency_and_priority_analysis.md
- docs/implement/01_implementation_plan.md

## FEATURE
Bootstrap WorkDataHub v1 with a complete vertical slice: file discovery (regex‑based), a sample domain service (pure transform), a transactional Postgres loader, and a small Dagster job that ties them together.

## SCOPE
- In‑scope:
  - Project skeleton under `src/work_data_hub/` with clear layering: `config/`, `io/`, `domain/`, `orchestration/`, `utils/`.
  - Config‑driven file discovery with regex patterns and “latest version per domain” selection.
  - One domain service (choose a representative domain from the analysis, e.g., trustee_performance) with Pydantic I/O models and a pure transformation.
  - Transactional Postgres loader supporting delete‑then‑insert (by PK) and append modes.
  - Dagster job with ops linking connector → domain service → loader for the chosen domain; CLI entry to run locally.
  - Unit tests for connector and domain service; smoke test for loader logic (DB‑less by default; mark integration tests for Postgres).
  - Tooling gates: ruff, mypy, pytest wired via `uv`.
- Non‑goals:
  - Full migration of all legacy flows/domains.
  - Full performance tuning (batching, vectorized Excel read, parallelism).
  - Production deployment and schedules (covered in the plan’s later milestones).
  - Implementing every domain’s exact column mapping (start with one; leave placeholders + tests for the pattern).

## CONTEXT SNAPSHOT
Repository highlights:
```
docs/
  project/
    01_architecture_analysis_report.md
    02_production_data_sample_analysis.md
    03_specified_data_source_problems_analysis.md
    04_dependency_and_priority_analysis.md
  implement/01_implementation_plan.md
src/
  work_data_hub/           # empty; create structure below
pyproject.toml             # has dagster, pydantic, psycopg2-binary, pandas
```

## EXAMPLES
Mirror patterns and intent from internal docs:
- Dagster wiring: docs/project/04_dependency_and_priority_analysis.md (pseudo‑code for ops/job composition).
- Config‑driven orchestration: docs/project/03_specified_data_source_problems_analysis.md (regex/file patterns and version discovery).
- Domain separation and contracts: docs/project/02_production_data_sample_analysis.md (per‑domain thinking and validation).

## DOCUMENTATION
- Internal:
  - docs/implement/01_implementation_plan.md (milestones, acceptance criteria)
  - All docs under docs/project/ (analysis inputs)
- External (for library specifics):
  - Dagster: https://docs.dagster.io/
  - Pydantic v2: https://docs.pydantic.dev/latest/
  - Psycopg2: https://www.psycopg.org/docs/

## INTEGRATION POINTS
- Data models: Pydantic v2 I/O models live under `src/work_data_hub/domain/<domain>/models.py`.
- Database: Postgres via `psycopg2-binary`; transactional loader in `src/work_data_hub/io/loader/warehouse_loader.py`.
- Config/ENV: Pydantic Settings in `src/work_data_hub/config/settings.py`; data source rules in `src/work_data_hub/config/data_sources.yml`.
- Orchestrator: Dagster ops/job in `src/work_data_hub/orchestration/`.

## DATA CONTRACTS (schemas & payloads)
Start with one concrete domain (e.g., `trustee_performance`). Create a minimal yet typed contract; use Pydantic v2 models, keeping the transform pure.

Example (adapt names/fields to the chosen domain after checking docs):
```python
from datetime import date
from pydantic import BaseModel, Field

class TrusteePerformanceIn(BaseModel):
    report_date: date
    # Add domain‑specific input fields extracted from Excel rows

class TrusteePerformanceOut(BaseModel):
    report_date: date
    # Add normalized output fields destined for the warehouse table
```

## GOTCHAS & LIBRARY QUIRKS
- Pydantic v2 only; prefer typed transforms over DataFrame‑wide implicit casts.
- Keep connector robust to non‑xlsx files; ignore `.eml`, temp files, and stray formats.
- Use regex groups to extract version info (e.g., year/month); select latest per domain within a run.
- Loader: wrap delete‑then‑insert in a single transaction; never leave the table partially updated.
- Dagster: keep ops small/pure; pass artifacts via I/O types or file paths, not global state.

## IMPLEMENTATION NOTES
Create these modules with small, focused functions and tests:

```
src/work_data_hub/
  config/
    settings.py             # Pydantic Settings (DB creds, base paths)
    data_sources.yml        # regex patterns → domain mapping, version strategy
  io/
    connectors/file_connector.py      # DataSourceConnector
    loader/warehouse_loader.py        # DataWarehouseLoader
    readers/excel_reader.py           # thin Excel→rows/records util
  domain/
    trustee_performance/
      models.py            # *In/*Out Pydantic models
      service.py           # pure process(DataFrame/rows)->list[Out]
  orchestration/
    ops.py                 # discover → process → load
    jobs.py                # dagster job + CLI entry
  utils/
    logging.py, exceptions.py (as needed)
```

Minimal responsibilities:
- DataSourceConnector
  - Scan base folder(s) from settings.
  - Match files by domain via regex (from YAML); ignore unsupported files.
  - Extract `report_date` (or equivalent) via regex groups; if multiple versions, pick latest.
  - Return a list of `DiscoveredFile(domain, path, metadata)`.
- Domain service (e.g., trustee_performance.service)
  - Read Excel via `excel_reader` into rows/records.
  - Validate/transform to `TrusteePerformanceOut`.
  - Return list[TrusteePerformanceOut] or a small DataFrame‑like structure ready for load.
- DataWarehouseLoader
  - `load(table, rows, mode="delete_insert" | "append", pk=[...])`.
  - In `delete_insert`: within one transaction, stage rows, delete target PKs, insert rows.
  - Provide a simple SQL‑builder so unit tests can assert generated SQL without a DB.
- Dagster ops
  - `discover_files_op` → `process_trustee_performance_op` → `load_op`.
  - Small job in `jobs.py` to run the vertical slice end‑to‑end locally.

## VALIDATION GATES
Commands must pass locally:
```bash
uv venv && uv sync
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -q
```
Notes:
− Add `mypy` to `[project.optional-dependencies].dev` and configure if missing.
− For DB integration tests, mark with `@pytest.mark.postgres` and skip by default (no CI DB yet).

## ACCEPTANCE CRITERIA
- [ ] `src/work_data_hub/` structure created as above with typed modules.
- [ ] `settings.py` and `data_sources.yml` support regex mapping and version selection.
- [ ] File connector discovers only supported files, extracts metadata, and selects latest per domain.
- [ ] One domain service (trustee_performance or similar) processes rows with Pydantic v2 models and unit tests (>90% for that service).
- [ ] Loader exposes transactional delete‑then‑insert and append, with unit‑testable SQL building.
- [ ] Dagster job wires the three steps; local run path documented.
- [ ] Lint (ruff), types (mypy), tests (pytest) all green.

## ROLLOUT & RISK
- Start with pandas (already in pyproject) to reduce churn; switch to Polars later if needed for performance.
- Guard loader with transactions to avoid partial writes.
- Keep domain services pure to simplify testing/mocking.
- Postgres creds come from env via `settings.py`; never hardcode.

## APPENDICES

Example `settings.py` (sketch):
```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class DatabaseSettings(BaseModel):
    host: str
    port: int
    user: str
    password: str
    db: str

class Settings(BaseSettings):
    data_base_dir: str
    database: DatabaseSettings

    model_config = {
        "env_nested_delimiter": "__",
        "env_prefix": "WDH_",
    }

settings = Settings()  # reads env vars like WDH_DATABASE__HOST
```

Example `data_sources.yml`:
```yaml
domains:
  trustee_performance:
    pattern: "(?P<year>20\\d{2})[-_/]?(?P<month>0?[1-9]|1[0-2]).*受托业绩.*\\.xlsx$"
    select: latest_by_year_month
    table: trustee_performance
    pk: [report_date, record_id]
    sheet: 0
```

Example Dagster skeleton:
```python
from dagster import job, op

@op
def discover_files():
    ...  # call DataSourceConnector and filter to trustee_performance

@op
def process_trustee_performance(discovered):
    ...  # call domain service

@op
def load(rows):
    ...  # call DataWarehouseLoader

@job
def trustee_performance_job():
    load(process_trustee_performance(discover_files()))
```

Test ideas (must implement now):
- Connector: creates `DiscoveredFile` for matching `.xlsx`, ignores `.eml`, selects latest by `(year, month)`.
- Domain service: validates input rows, raises on bad types, returns normalized output.
- Loader: builds correct SQL for both modes; integration test is optional/skipped.

