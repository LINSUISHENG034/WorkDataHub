# INITIAL.md — Transactional PostgreSQL Loader (SQL Builder + Tests)

Purpose: Implement a transactional PostgreSQL loader with a testable SQL builder that supports delete‑then‑insert and append modes, without requiring a live database for unit tests. Provide optional, skipped‑by‑default integration hooks for real Postgres.

Read these first for context and constraints:
- docs/project/01_architecture_analysis_report.md
- docs/implement/01_implementation_plan.md
- src/work_data_hub/config/settings.py (will be extended with DB settings)

Important: The provided URI string `postgresql: root:Post.169828@192.168.0.200:5432` is not a valid PostgreSQL URI. The correct pattern is `postgresql://user:password@host:port/database`. Example (do not hardcode secrets in code):
- `postgresql://root:Post.169828@192.168.0.200:5432/wdh` (replace `wdh` with the actual database name)

Prefer environment variables loaded via `pydantic-settings` (see ENV section below) instead of embedding credentials.

## FEATURE
Add a loader component `DataWarehouseLoader` that can:
- Build parameterized SQL for both modes:
  - delete_then_insert (transactional upsert pattern via delete by PK, then bulk insert)
  - append (bulk insert only)
- Execute within a single transaction when given a real psycopg2 connection, but expose pure SQL builders so unit tests assert SQL/params without a DB.

## SCOPE
- In‑scope:
  - `src/work_data_hub/io/loader/warehouse_loader.py` with:
    - `build_delete_sql(table, pk_cols, rows) -> (sql, params)`
    - `build_insert_sql(table, cols, rows) -> (sql, params)`
    - `load(table, rows, mode="delete_insert"|"append", pk=[...], chunk_size=1000, conn=None)`
  - Identifier quoting and safe parameterization for psycopg2 (`%s` placeholders).
  - Chunking for large inserts; graceful no‑op on empty input; deterministic column order.
  - Unit tests that validate generated SQL and parameters, and loader behavior for edge cases.
- Non‑goals (this PR):
  - Full ORM/UPSERT (`ON CONFLICT`) logic; we explicitly use delete‑then‑insert as specified.
  - Dagster wiring and jobs.
  - Cross‑DB portability; target is PostgreSQL (psycopg2 paramstyle).

## CONTEXT SNAPSHOT
Repository highlights:
```
src/work_data_hub/
  config/settings.py           # will add DatabaseSettings, env mapping
  io/connectors/file_connector.py
  io/readers/excel_reader.py
  domain/trustee_performance/
tests/
  io/test_file_connector.py
  domain/trustee_performance/test_service.py
pyproject.toml                 # has psycopg2-binary
```

## API & CONTRACTS
- Target table for trustee_performance (example): `public.trustee_performance`
- Suggested PK for delete‑then‑insert: `["report_date", "plan_code", "company_code"]` (override per call)
- Input rows: list[dict[str, Any]]; keys must map to table columns

Functions to implement in `warehouse_loader.py`:
- `quote_ident(name: str) -> str`
  - Minimal identifier quoting: wrap with double‑quotes and escape inner quotes
- `build_insert_sql(table: str, cols: list[str], rows: list[dict]) -> tuple[str, list]`
  - Stable `cols` order; params flattened row‑major
  - SQL: `INSERT INTO "table" ("c1","c2",...) VALUES (%s,%s,...), (...), ...`
- `build_delete_sql(table: str, pk_cols: list[str], rows: list[dict]) -> tuple[str, list]`
  - Use tuple IN over composite keys: `DELETE FROM "table" WHERE ("pk1","pk2") IN ((%s,%s),(...))`
  - Error if pk missing in rows; deduplicate PK tuples before building
- `load(table: str, rows: list[dict], mode: str = "delete_insert", pk: list[str] | None = None, chunk_size: int = 1000, conn: Any | None = None) -> dict`
  - Behavior:
    - If rows empty → return {inserted: 0, deleted: 0}
    - Determine columns from union (or provided) and enforce deterministic order
    - In delete_insert: build delete on PK, then batched inserts in one transaction if `conn` provided; else return plan for tests
    - In append: skip delete; only batched inserts
  - Return shape (always): `{mode, table, deleted, inserted, batches}` for introspection in tests

## IMPLEMENTATION TASKS
1) SQL utilities
   - Implement `quote_ident`, `ensure_list_of_dicts`, and column ordering helper
2) SQL builders
   - Implement `build_insert_sql` and `build_delete_sql` with psycopg2 `%s` placeholders
   - Validate inputs (non‑empty cols, PK present in all rows for delete)
3) Loader orchestration
   - Implement `load` with chunking
   - If `conn` provided: use `conn.cursor()`; execute delete then inserts inside `with conn: ...` (transactional); rollback exceptions
   - If `conn` is None: return only SQL/param plans (no I/O) to keep unit tests DB‑less
4) Settings
   - Extend `src/work_data_hub/config/settings.py` with `DatabaseSettings` and `Settings.database: DatabaseSettings`
   - Support env vars like `WDH_DATABASE__HOST`, `WDH_DATABASE__PORT`, `WDH_DATABASE__USER`, `WDH_DATABASE__PASSWORD`, `WDH_DATABASE__DB`
5) Tests
   - Add `tests/io/test_warehouse_loader.py`:
     - Insert SQL: deterministic column order; correct placeholders/param flattening
     - Delete SQL: composite PK IN tuples; error on missing PK
     - delete_then_insert mode: correct sequencing; chunking math correct; no‑op on empty
     - Append mode: skips delete
     - Identifier quoting handles mixed‑case and reserved words
   - Optional integration (skipped by default): `@pytest.mark.postgres` uses env DSN if provided

## EXAMPLES
Delete‑then‑insert for three rows on composite PK (report_date, plan_code, company_code):
```
DELETE FROM "trustee_performance"
WHERE ("report_date","plan_code","company_code") IN ((%s,%s,%s),(%s,%s,%s),(%s,%s,%s));

INSERT INTO "trustee_performance" ("report_date","plan_code","company_code","return_rate")
VALUES (%s,%s,%s,%s),(%s,%s,%s,%s),(%s,%s,%s,%s);
```
Params are flattened row‑major; date/decimal types are passed as Python objects for psycopg2 adaptation.

## GOTCHAS & LIBRARY QUIRKS
- Do not interpolate values into SQL; always use `%s` parameterization
- Identifier quoting uses double‑quotes; do not quote `schema.table` together—quote each part if you support schemas
- Composite IN lists can exceed parameter limits for very large batches; chunk conservatively (e.g., 1000 rows)
- Keep functions small (<50 lines) per CLAUDE.md; prefer helpers over long functions
- Never hardcode credentials; use env variables via `pydantic-settings`
- Decimal handling: let psycopg2 adapt `decimal.Decimal`; avoid pre‑casting to strings

## ENV & CONFIG
Use Pydantic Settings (already present) and extend with database settings. Example env variables (do not commit secrets):
```
export WDH_DATABASE__HOST=192.168.0.200
export WDH_DATABASE__PORT=5432
export WDH_DATABASE__USER=root
export WDH_DATABASE__PASSWORD='Post.169828'
export WDH_DATABASE__DB=wdh   # replace with actual database name
```
Optional DSN (if you prefer a single var):
```
export WDH_DATABASE__URI='postgresql://root:Post.169828@192.168.0.200:5432/wdh'
```

## VALIDATION GATES
```bash
uv venv && uv sync
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "warehouse_loader"
```
Optional integration (requires a reachable DB and env set):
```bash
uv run pytest -v -k "warehouse_loader and postgres" -m postgres
```

## ACCEPTANCE CRITERIA
- [ ] `warehouse_loader.py` implements `build_insert_sql`, `build_delete_sql`, and `load`
- [ ] Identifier quoting and parameterization are correct; no string interpolation of values
- [ ] Delete‑then‑insert runs within a single transaction when `conn` is provided
- [ ] Append mode inserts only
- [ ] Chunking works and is covered by tests
- [ ] Unit tests for SQL builders and loader behavior pass without a database
- [ ] Optional integration tests are skipped by default (marker present)
- [ ] Ruff, mypy, and pytest are green

## NEXT INTEGRATION (OUT OF SCOPE HERE)
- Wire the loader into a Dagster op and end‑to‑end job once this component is accepted.
