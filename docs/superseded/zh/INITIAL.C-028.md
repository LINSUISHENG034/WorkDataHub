# INITIAL.md — Backfill Hardening & Configurability (Skip Facts, Config‑Driven Refs/Schema, Qualified SQL)

This INITIAL guides Claude to implement the next set of improvements for Reference Backfill to make it safer, configurable, and easier to validate in real environments. The work focuses on: a skip‑facts switch, config‑driven reference targets (with schema), qualified SQL generation, tests, and docs updates.

## FEATURE
Harden and parameterize Reference Backfill so that:
- A CLI flag `--skip-facts` runs ONLY the backfill steps and skips fact loading.
- Backfill targets (plans/portfolios) are read from `data_sources.yml` under a `refs:` block (table name, schema, key columns, updatable columns).
- All SQL for backfill supports a separate schema parameter and emits qualified identifiers like `"schema"."table"` safely.
- README shows how to configure refs and run skip‑facts, with examples for ON CONFLICT vs fallback.

## SCOPE
- In‑scope:
  - CLI: add `--skip-facts` and wire it so load_op is not executed when set.
  - Config: extend `src/work_data_hub/config/data_sources.yml` → `domains.annuity_performance.refs` with:
    - `plans: { schema, table, key, updatable }`
    - `portfolios: { schema, table, key, updatable }`
  - SQL: add a helper to produce qualified names (`"schema"."table"`) and update backfill SQL builders to accept an optional `schema` argument.
  - Orchestration: backfill ops read the refs config and pass schema/table/keys/updatable into loader helpers.
  - Tests: unit tests for config parsing and qualified SQL; orchestration mapping tests; a tiny integration‑style test that exercises skip‑facts path.
  - Docs: README updates for configuration and skip‑facts usage.
- Non‑goals:
  - No new domains or mapping services.
  - No Dagster deployment changes.
  - No strong FK enforcement.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  orchestration/
    jobs.py          # CLI + run_config; will add --skip-facts & summary
    ops.py           # backfill_refs_op; will read refs config & pass schema/table
  io/loader/warehouse_loader.py  # add quote_qualified(schema, table); schema-aware SQL
  config/data_sources.yml        # add refs block under annuity_performance

tests/
  orchestration/test_jobs_run_config.py       # extend to cover --skip-facts
  orchestration/test_backfill_ops.py          # ensure ops consume refs config
  io/test_warehouse_loader_backfill.py        # test qualified SQL + schema arg
```

## EXAMPLES (most important)
- data_sources.yml (example)
```yaml
domains:
  annuity_performance:
    table: "规模明细"
    pk: ["月度", "计划代码", "company_id"]
    sheet: "规模明细"
    refs:
      plans:
        schema: public
        table: "年金计划"
        key: ["年金计划号"]
        updatable: ["计划全称", "计划类型", "客户名称", "company_id"]
      portfolios:
        schema: public
        table: "组合计划"
        key: ["组合代码"]
        updatable: ["组合名称", "组合类型", "运作开始日"]
```

- CLI skip‑facts (backfill only):
```bash
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --backfill-refs all \
  --backfill-mode insert_missing \
  --skip-facts \
  --sheet "规模明细" \
  --debug --raise-on-error
```

- With qualified SQL (schema configured as above), expect statements like:
```sql
INSERT INTO "public"."年金计划" ("年金计划号", ...) VALUES ...
```

## DOCUMENTATION
- README.md → add:
  - Configuring `refs` (schema/table/key/updatable) under `annuity_performance`.
  - Using `--skip-facts` for backfill‑only runs.
  - Reminder on ON CONFLICT vs fallback and recommended unique indexes.

## INTEGRATION POINTS
- Orchestration: jobs.py → run_config carries skip_facts and refs settings to ops.
- Ops: ops.py → read refs from data_sources.yml; pass schema/table/key/updatable to loader helpers.
- Loader: warehouse_loader.py → qualified SQL via `quote_qualified(schema, table)`; insert_missing/fill_null_only accept `schema`.

## DATA CONTRACTS
- data_sources.yml → `domains.<domain>.refs`:
```yaml
refs:
  plans:
    schema: <str|optional>
    table: <str>
    key:   <list[str]>
    updatable: <list[str]>
  portfolios:
    schema: <str|optional>
    table: <str>
    key:   <list[str]>
    updatable: <list[str]>
```
- ops config surface (backfill_refs_op):
  - targets: ["plans"|"portfolios"|"all"] (from CLI or default)
  - mode: ["insert_missing"|"fill_null_only"]
  - plan_only: bool (derived from execute/plan-only)
  - refs: injected from data_sources.yml for actual table/schema/key/updatable

## GOTCHAS & QUIRKS
- Do NOT pass `schema.table` to `quote_ident` directly; build qualified name as `quote_ident(schema) + '.' + quote_ident(table)`.
- Ensure skip‑facts truly bypasses fact load: either remove `load_op` from dag graph via config, or short‑circuit its execution (recommended: add a trivial `skip` flag to `load_op` config and early‑return with a log line).
- Backward compatibility: if refs not present in data_sources.yml, default to previous hardcoded tables (年金计划/组合计划, public schema).
- Preserve fallback path for ON CONFLICT missing constraints (SQLSTATE 42P10, multi‑language messages).

## IMPLEMENTATION NOTES
- Loader (`warehouse_loader.py`):
  - Add:
    - `def quote_qualified(schema: Optional[str], table: str) -> str` → returns `"schema"."table"` or `"table"` if schema is None/empty.
  - Update:
    - `insert_missing(..., schema: Optional[str] = None, ...)` → use `quote_qualified(schema, table)` instead of `quote_ident(table)`.
    - `fill_null_only(..., schema: Optional[str] = None, ...)` → same.
  - Keep existing ON CONFLICT + fallback behavior.

- Ops (`ops.py`):
  - Read refs from data_sources.yml (under current domain): plans/portfolios → schema/table/key/updatable (with defaults if absent).
  - In `backfill_refs_op`, pass these values into `insert_missing` / `fill_null_only`.
  - Log a one‑line summary that includes qualified table names.

- Jobs (`jobs.py`):
  - Add CLI flag `--skip-facts` (bool).
  - In `build_run_config`, propagate skip_facts (e.g., as a flag in `load_op` config).
  - In CLI output, print `Skip facts: True/False` and show Reference Backfill Summary before any fact summary.

- Config (`data_sources.yml`):
  - Add refs block for annuity_performance (see EXAMPLES), keep compatibility if refs absent.

- Tests:
  - `tests/io/test_warehouse_loader_backfill.py` → add cases for `quote_qualified(None, t)` vs `quote_qualified('public', t)`, and assert generated SQL contains `"public"."表名"` when schema is provided.
  - `tests/orchestration/test_backfill_ops.py` → verify ops read refs from config and pass schema/table/key/updatable; assert log/returned plan includes qualified names.
  - `tests/orchestration/test_jobs_run_config.py` → assert `--skip-facts` maps to run_config and load_op receives a `skip` flag.
  - Minimal end‑to‑end (optional, behind marker): run backfill with `--skip-facts` on subsets; assert Reference Backfill Summary exists and no load_op executed.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "backfill or run_config or qualified"  # focus tests
```

Manual checks (document in VALIDATION.md):
- CLI shows `Skip facts: True` when flag enabled, no fact load summary printed.
- With refs configured (schema=public), Reference Backfill Summary indicates inserts against `"public"."年金计划"` and `"public"."组合计划"` (visible in logs or SQL plans).
- ON CONFLICT fast path (with unique indexes) and fallback path (without) both succeed.

## ACCEPTANCE CRITERIA
- New CLI `--skip-facts` available and effective; Reference Backfill Summary still printed.
- Refs configuration in `data_sources.yml` is consumed; qualified SQL is generated when schema is present.
- All targeted tests pass; no regressions in existing tests.
- README updated with:
  - refs configuration examples
  - skip‑facts usage and recommended validation steps
- VALIDATION.md updated with one skip‑facts run and one qualified SQL evidence.

## ROLLOUT & RISK
- Risk: mis‑configured refs cause runtime key/updatable mismatches → add validation and clear error messages.
- Risk: schema quoting mistakes → covered by qualified SQL unit tests.
- Risk: accidental fact skipping in production → default `--skip-facts` to False; visually print flag in CLI summary.

## APPENDICES (quick snippets)
```python
# loader: qualified quoting
def quote_qualified(schema: Optional[str], table: str) -> str:
    if schema and str(schema).strip():
        return f"{quote_ident(str(schema))}.{quote_ident(table)}"
    return quote_ident(table)
```

```yaml
# data_sources.yml (annuity_performance)
refs:
  plans:      { schema: public, table: "年金计划",  key: ["年金计划号"], updatable: ["计划全称","计划类型","客户名称","company_id"] }
  portfolios: { schema: public, table: "组合计划",  key: ["组合代码"],  updatable: ["组合名称","组合类型","运作开始日"] }
```
