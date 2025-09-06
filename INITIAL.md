# INITIAL.md — Skeleton + Connector + Domain Service

Purpose: Build the project skeleton and deliver two core components: a config‑driven file connector and one domain service with Pydantic v2 data contracts. Defer the warehouse loader and Dagster to a later PR.

Read these first for context and constraints:
- docs/project/01_architecture_analysis_report.md
- docs/project/02_production_data_sample_analysis.md
- docs/project/03_specified_data_source_problems_analysis.md
- docs/project/04_dependency_and_priority_analysis.md
- docs/implement/01_implementation_plan.md

## FEATURE
Create `src/work_data_hub` structure, implement a robust file discovery connector (regex + latest version selection), and one domain service (pure transform with Pydantic models). Provide tests for both.

## SCOPE
- In‑scope:
  - Project skeleton under `src/work_data_hub/` with clear layering: `config/`, `io/`, `domain/`, `utils/` and tests.
  - Config‑driven file discovery with regex patterns and “latest version per domain” selection.
  - One domain service (pick a representative domain, e.g., `trustee_performance`) with Pydantic v2 I/O models and a pure transformation.
  - Unit tests for the connector and the domain service.
- Non‑goals (explicitly defer):
  - Data warehouse loader, database writes, transactions.
  - Dagster ops/jobs, orchestration, schedules.
  - Performance optimizations (vectorization/parallelism), and additional domains.

## CONTEXT SNAPSHOT
Repository highlights:
```
docs/project/… (analysis inputs)
docs/implement/01_implementation_plan.md
src/work_data_hub/           # empty; create structure
pyproject.toml               # has pandas, pydantic, dagster (unused now)
```

## IMPLEMENTATION NOTES
Create these modules with small, focused functions and tests:
```
src/work_data_hub/
  config/
    settings.py             # minimal settings (base data dir, patterns path)
    data_sources.yml        # regex patterns → domain mapping, version strategy
  io/
    connectors/file_connector.py      # DataSourceConnector
    readers/excel_reader.py           # thin Excel→rows utility (pandas)
  domain/
    trustee_performance/
      models.py            # *In/*Out Pydantic models
      service.py           # pure process(rows)->list[Out]
  utils/
    types.py               # DiscoveredFile (TypedDict/dataclass) and helpers
tests/
  io/test_file_connector.py
  domain/trustee_performance/test_service.py
```

Recommended responsibilities & signatures:
- config/settings.py
  - Provide `DATA_BASE_DIR` and `DATA_SOURCES_YML` via env with sensible defaults.
  - Avoid adding new deps; simple `os.getenv` or a small Pydantic `BaseModel` loader is OK.
- config/data_sources.yml (example):
```yaml
domains:
  trustee_performance:
    pattern: "(?P<year>20\\d{2})[-_/]?(?P<month>0?[1-9]|1[0-2]).*受托业绩.*\\.xlsx$"
    select: latest_by_year_month
    sheet: 0
```
- utils/types.py
  - `DiscoveredFile` with fields: `domain: str`, `path: str`, `year: int|None`, `month: int|None`, `metadata: dict`.
- io/readers/excel_reader.py
  - `read_rows(path: str, sheet: int|str=0) -> list[dict]` using `pandas.read_excel`.
  - Note: pandas needs `openpyxl` for `.xlsx`. For tests, do not require real files.
- io/connectors/file_connector.py
  - `discover(domain: str|None=None) -> list[DiscoveredFile]`.
  - Load YAML, compile regex per domain, scan `DATA_BASE_DIR` recursively.
  - Ignore non‑xlsx files like `.eml`/temp; extract `year`/`month` from regex groups.
  - Implement `latest_by_year_month`: compute `(year, month)` if present; pick the max per domain; if absent, fallback to newest mtime.
- domain/trustee_performance/models.py
  - Pydantic v2 models for input/output; include `report_date` if available, else derive from `(year, month)` as first‑of‑month.
- domain/trustee_performance/service.py
  - `process(rows: list[dict]) -> list[TrusteePerformanceOut]`.
  - Keep pure; map/validate fields; raise `ValueError` on invariant violations.

## DATA CONTRACTS (example models)
```python
from datetime import date
from pydantic import BaseModel, Field

class TrusteePerformanceIn(BaseModel):
    report_date: date | None = None
    # TODO: add concrete input columns after inspecting a representative file

class TrusteePerformanceOut(BaseModel):
    report_date: date
    # TODO: add normalized fields for warehouse contract (even if loader is out of scope)
```

## TESTS TO IMPLEMENT NOW
- io/test_file_connector.py
  - Discovers `.xlsx` and ignores `.eml`/other files.
  - Extracts `year`/`month` from filenames via regex.
  - Selects latest by `(year, month)`; when missing, selects by newest mtime.
- domain/trustee_performance/test_service.py
  - Valid input rows → list[TrusteePerformanceOut] with derived `report_date` when needed.
  - Invalid rows raise validation errors.

## VALIDATION GATES
```bash
uv venv && uv sync
uv run ruff check src/ --fix
uv run pytest -q
```
Notes:
- If you add typing coverage, include `uv run mypy src/` and add `mypy` to `project.optional-dependencies.dev`.

## ACCEPTANCE CRITERIA
- [ ] `src/work_data_hub/` skeleton exists with modules listed above.
- [ ] `settings.py` and `data_sources.yml` present; regex pattern configured for one domain.
- [ ] File connector discovers files, extracts version info, and selects the latest version deterministically.
- [ ] One domain service implemented as a pure transform with Pydantic v2 models and unit tests.
- [ ] Ruff and pytest pass locally.

## GOTCHAS
- Regex must be Unicode‑aware; filenames may contain Chinese characters.
- Keep connector side‑effects minimal; do not move/delete files.
- Do not import DB/Dagster modules in this PR; keep slice self‑contained and fast.
