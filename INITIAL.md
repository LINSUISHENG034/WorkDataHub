# INITIAL.md — C‑011 Validate Trustee Performance E2E Execute Mode (Fix DB Context, JSONB, Decimal)

Selected task: ROADMAP.md → Milestone 1 → C‑011

Purpose: Ensure the trustee_performance Dagster job runs end‑to‑end against PostgreSQL with `--execute`, not just plan‑only. Address defects surfaced in VALIDATION.md: psycopg2 connection context recursion, JSONB parameter adaptation, and Decimal precision validation causing row drops.

Reference: See VALIDATION.md — errors include Pydantic `decimal_max_places` on `return_rate`, and `psycopg2.ProgrammingError: the connection cannot be re-entered recursively` during load.

## FEATURE
Make `uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2` succeed end‑to‑end:
- Fix DB connection context handling to avoid recursive re‑entry.
- Properly adapt JSONB parameters for psycopg2.
- Quantize numeric inputs to the declared decimal places to avoid Pydantic precision errors.

## SCOPE
- In‑scope:
  - `src/work_data_hub/orchestration/ops.py` — adjust DB connection lifecycle in `load_op` to avoid nesting with the loader’s own context management.
  - `src/work_data_hub/io/loader/warehouse_loader.py` — adapt dict/list values to JSONB via `psycopg2.extras.Json` before `execute_values`.
  - `src/work_data_hub/domain/trustee_performance/models.py` — extend decimal field validator to convert/quantize inputs to the model’s precision (`return_rate`: 6, `net_asset_value`: 4, `fund_scale`: 2) and avoid float tail precision errors.
  - Tests covering the above, including a DB‑skipped suite and optional `@pytest.mark.postgres` for live DB.
- Non‑goals:
  - Do not change DB schema or table/column names (table SQL already applied).
  - Do not change file discovery patterns or job CLI contract beyond these fixes.
  - No new domains, connectors, or scheduling.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  orchestration/
    ops.py               # load_op opens psycopg2 connection (nested)
    jobs.py              # CLI and run_config (works)
  io/
    loader/warehouse_loader.py  # uses `with conn:` and execute_values
    readers/excel_reader.py      # ok
  domain/trustee_performance/
    models.py            # Pydantic v2; decimal_places set on Decimal fields
    service.py           # transformation; model_dump() yields list/dict for warnings
config/
  data_sources.yml       # table/pk = trustee_performance
scripts/create_table/trustee_performance.sql   # already applied
```

## EXAMPLES
- Pattern: Connection lifecycle — pick one layer to own transaction
  - Current: ops.py wraps `psycopg2.connect(dsn)` in `with ...:` and loader also does `with conn:` → recursion error.
  - Follow loader’s transaction management: in ops.py use bare `conn = psycopg2.connect(dsn)` and pass to `load(...)`; rely on loader’s `with conn:` to commit/rollback and close cursor; ensure `conn.close()` in finally.

- JSONB adaptation with psycopg2
```python
from psycopg2.extras import Json

def _adapt_param(v):
    # wrap non‑scalar JSON types so psycopg2 can send to json/jsonb
    if isinstance(v, (dict, list)):
        return Json(v)
    return v

# before execute_values, map each value in each row
row_data = [[_adapt_param(val) for val in row] for row in row_data]
```

- Decimal quantization in Pydantic v2
```python
from decimal import Decimal, ROUND_HALF_UP
from pydantic import FieldValidationInfo

PLACES = {"return_rate": 6, "net_asset_value": 4, "fund_scale": 2}

@field_validator("return_rate", "net_asset_value", "fund_scale", mode="before")
@classmethod
def clean_decimal_fields(cls, v, info: FieldValidationInfo):
    # existing parsing (%, cleaning) → obtain a numeric/str value "val"
    if v is None or v == "":
        return None
    # normalize str/float/int → Decimal using string to avoid float tail
    s = str(v).strip() if not isinstance(v, (int, float, Decimal)) else (str(v) if isinstance(v, float) else v)
    d = Decimal(str(s)) if not isinstance(v, Decimal) else v
    places = PLACES.get(info.field_name)
    if places is not None:
        quant = Decimal("1." + ("0" * places))
        d = d.quantize(quant, rounding=ROUND_HALF_UP)
    return d
```

## DOCUMENTATION
- Pydantic v2 field validators & validation info:
  - https://docs.pydantic.dev/2.11/usage/validators/#field-validators
- Decimal pitfalls and quantize:
  - Python `decimal` — https://docs.python.org/3/library/decimal.html#decimal.Decimal.quantize
- psycopg2 JSON adaptation:
  - https://www.psycopg.org/docs/extras.html#json-adaptation
- psycopg2 connections and context managers:
  - https://www.psycopg.org/docs/connection.html#connection

## INTEGRATION POINTS
- Data models: `TrusteePerformanceOut` decimal fields — keep `decimal_places` as is; validator enforces quantization.
- Database: no DDL changes; table `trustee_performance` exists per `scripts/create_table/trustee_performance.sql` (JSONB column `validation_warnings`).
- Config/ENV: keep using `.env` → `Settings.get_database_connection_string()`; no new vars.
- Jobs: no CLI changes; continue using `--execute` and `--plan-only` semantics.

## DATA CONTRACTS
Trustee performance output schema (aligned with table):
- `report_date: date`
- `plan_code: str`
- `company_code: str`
- `return_rate: Decimal(8,6) | null`
- `net_asset_value: Decimal(18,4) | null`
- `fund_scale: Decimal(18,2) | null`
- `data_source: text`
- `processed_at: timestamp`
- `has_performance_data: boolean`
- `validation_warnings: jsonb` (list of strings)

Sample record:
```json
{
  "report_date": "2024-01-01",
  "plan_code": "PLAN001",
  "company_code": "COMP001",
  "return_rate": 0.048800,
  "net_asset_value": 1.0512,
  "fund_scale": 12000000.00,
  "data_source": "tests/fixtures/sample_data/2024-01_受托业绩_sample.xlsx",
  "processed_at": "2025-09-08T14:00:00",
  "has_performance_data": true,
  "validation_warnings": []
}
```

## GOTCHAS & LIBRARY QUIRKS
- Do not nest psycopg2 connection context managers; only one layer should manage `with conn:`.
- psycopg2 will not adapt Python list/dict to JSONB automatically; wrap with `extras.Json`.
- Avoid constructing `Decimal` from binary floats directly; always use `Decimal(str(x))` prior to `quantize`.
- Keep Dagster job execution in‑process; `jobs.py` is fine. No need for DAGSTER_HOME unless `--debug`.
- Windows paths may appear in logs; avoid hard‑coded separators.

## IMPLEMENTATION NOTES
- ops.py
  - Replace `with psycopg2.connect(dsn) as conn:` with `conn = psycopg2.connect(dsn)` and ensure `finally: conn.close()` when not plan‑only.
  - Keep plan‑only path unchanged.
- warehouse_loader.py
  - Before `execute_values`, adapt per‑value using helper `_adapt_param` (wrap dict/list with `Json`).
  - Leave plan‑only `sql_plans` intact; do not mutate returned params for readability.
- models.py
  - Extend existing `clean_decimal_fields` to perform quantization keyed by `info.field_name` without loosening constraints.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```

E2E checks:
```bash
# Plan‑only sanity
uv run python -m src.work_data_hub.orchestration.jobs --plan-only --max-files 2

# Execute against DB (requires .env pointing to a reachable Postgres)
uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2
```

Expected outcomes:
- Plan‑only: job succeeds; `load_op` returns `sql_plans` with DELETE + INSERT batches.
- Execute: job succeeds; no `ProgrammingError: connection cannot be re-entered`; inserted rows match processed count; JSONB column accepted.

## ACCEPTANCE CRITERIA
- [ ] psycopg2 recursion error eliminated in execute mode.
- [ ] JSONB parameters are correctly adapted; no `can't adapt type list/dict` errors.
- [ ] Decimal inputs quantized to their declared precision; no `decimal_max_places` errors on valid inputs.
- [ ] All validation gates green (ruff, mypy, pytest), and E2E execute succeeds on sample data with a reachable DB.

## ROLLOUT & RISK
- Requires a reachable Postgres for execute validation; otherwise, rely on plan‑only tests and mark DB tests with `@pytest.mark.postgres`.
- Minimal risk to plan‑only path; primary changes are guarded under execute branch and model validators.
- Rollback: revert ops.py connection lifecycle and loader JSON adaptation; Decimal validator change is additive and can be gated.

## APPENDICES
Useful ripgrep searches:
```bash
rg -n "load_op\(|execute_values|jsonb|decimal_places|FieldValidationInfo" src/
```

Minimal test skeleton (DB‑less):
```python
def test_build_insert_plan_includes_jsonb_without_error():
    rows = [{"a": 1, "validation_warnings": ["ok"]}]
    plan = load("t", rows, mode="append", conn=None)
    assert plan["sql_plans"]
```

Optional DB test (requires Postgres, mark with `postgres`):
```python
import pytest, psycopg2

@pytest.mark.postgres
def test_execute_values_accepts_jsonb(settings):
    conn = psycopg2.connect(settings.get_database_connection_string())
    try:
        rows = [{"report_date": "2024-01-01", "plan_code": "P", "company_code": "C", "validation_warnings": []}]
        out = load("trustee_performance", rows, mode="append", pk=None, conn=conn)
        assert out["inserted"] == 1
    finally:
        conn.close()
```

Next steps for Claude:
1) Generate PRP from this INITIAL (C‑011) and implement fixes in ops.py, warehouse_loader.py, and models.py with tests.
2) Run validation gates; verify plan‑only and execute modes as applicable.
3) Update ROADMAP.md: mark C‑011 → COMPLETED with PRP link; if new subtask(s) were introduced (e.g., JSONB adaptation), add them and mark COMPLETED.
