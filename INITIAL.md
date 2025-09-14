# INITIAL.md — Backfill Hardening & Configurability (Skip Facts, Config‑Driven Refs/Schema, Qualified SQL)

This INITIAL guides Claude to implement the next set of improvements for Reference Backfill to make it safer, configurable, and easier to validate in real environments. The work focuses on: a skip‑facts switch, config‑driven reference targets (with schema), qualified SQL generation, tests, and docs updates — plus enhanced Annuity Plan value derivations.

## FEATURE
Harden and parameterize Reference Backfill so that:
- A CLI flag `--skip-facts` runs ONLY the backfill steps and skips fact loading.
- Backfill targets (plans/portfolios) are read from `data_sources.yml` under a `refs:` block (table name, schema, key columns, updatable columns).
- All SQL for backfill supports a separate schema parameter and emits qualified identifiers like `"schema"."table"` safely.
- Enhanced Annuity Plan derivations implemented from fact rows.

## SCOPE
- In‑scope:
  - CLI: add `--skip-facts` and wire it so load_op is not executed when set.
  - Config: extend `src/work_data_hub/config/data_sources.yml` → `domains.annuity_performance.refs` with:
    - `plans: { schema, table, key, updatable }`
    - `portfolios: { schema, table, key, updatable }`
  - SQL: add a helper to produce qualified names (`"schema"."table"`) and update backfill SQL builders to accept an optional `schema` argument.
  - Orchestration: backfill ops read the refs config and pass schema/table/key/updatable into loader helpers.
  - Annuity Plan derivations (see IMPLEMENTATION NOTES → Annuity Plan Derivations).
  - Tests: config parsing, qualified SQL, skip‑facts run_config mapping, and derivation logic; a small end‑to‑end (opt‑in marker) for skip‑facts only.
  - Docs: README updates for configuration and skip‑facts usage; VALIDATION.md with results.
- Non‑goals:
  - No new domains or mapping services.
  - No Dagster deployment changes.
  - No strong FK enforcement.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  orchestration/
    jobs.py          # CLI + run_config; add --skip-facts & summary
    ops.py           # backfill_refs_op; read refs config & pass schema/table
  io/loader/warehouse_loader.py  # add quote_qualified(schema, table); schema-aware SQL
  config/data_sources.yml        # add refs block under annuity_performance

  domain/reference_backfill/
    service.py, models.py  # implement enhanced Annuity Plan derivations

tests/
  orchestration/test_jobs_run_config.py       # cover --skip-facts mapping
  orchestration/test_backfill_ops.py          # ops consume refs & schema; qualified names appear
  io/test_warehouse_loader_backfill.py        # qualified SQL helper & generated SQL assertions
  domain/reference_backfill/test_service.py   # derivation tests (max 期末资产规模, 备注, 资格)
```

## EXAMPLES (most important)
- data_sources.yml (refs example)
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
        updatable: ["计划全称", "计划类型", "客户名称", "company_id", "主拓代码", "主拓机构", "备注", "资格"]
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

## DATA CONTRACTS (schemas & payloads)
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
- Backfill op config:
  - targets: ["plans"|"portfolios"|"all"] (from CLI or default)
  - mode: ["insert_missing"|"fill_null_only"]
  - plan_only: bool (derived from execute/plan-only)
  - refs: injected from data_sources.yml for actual table/schema/key/updatable

## GOTCHAS & LIBRARY QUIRKS
- Do NOT pass `schema.table` to `quote_ident` directly; build qualified name as `quote_ident(schema) + '.' + quote_ident(table)`.
- Ensure `--skip-facts` truly bypasses fact load: either remove `load_op` from dag graph via config, or early‑return in `load_op` when `skip=True`.
- Backward compatibility: if refs not present, default to previous hardcoded tables (年金计划/组合计划, public schema).
- Preserve fallback path for ON CONFLICT missing constraints (SQLSTATE 42P10, multi‑language messages).
- FK constraints: orchestration already gates fact load after backfill; keep that ordering.

## IMPLEMENTATION NOTES
- Loader (`warehouse_loader.py`):
  - Add:
    - `def quote_qualified(schema: Optional[str], table: str) -> str` → returns `"schema"."table"` or `"table"` if schema is None/empty.
  - Update:
    - `insert_missing(..., schema: Optional[str] = None, ...)` → use `quote_qualified`.
    - `fill_null_only(..., schema: Optional[str] = None, ...)` → use `quote_qualified`.
  - Keep existing ON CONFLICT + fallback behavior.

- Ops (`ops.py`):
  - Read `refs` from data_sources.yml (under current domain): plans/portfolios → schema/table/key/updatable (with defaults if absent).
  - In `backfill_refs_op`, pass these values into `insert_missing` / `fill_null_only`.
  - Log a one‑line summary that includes qualified table names.

- Jobs (`jobs.py`):
  - Add CLI flag `--skip-facts` (bool).
  - In `build_run_config`, propagate skip_facts (e.g., as a flag in `load_op` config).
  - In CLI output, print `Skip facts: True/False` and show Reference Backfill Summary before any fact summary.

- Reference backfill service (`domain/reference_backfill/service.py`):
  - Implement Annuity Plan Derivations (below) with deterministic tie‑breaking and unit tests.

### Annuity Plan Derivations
Group by plan code (计划代码) over processed fact rows; build each plan candidate fields:
1) 客户名称:
   - From any row’s "客户名称". If multiple distinct values:
     - choose the most frequent; if tied, choose value from the row with maximum 期末资产规模; if still tied, choose the first by stable ordering.
2) 主拓代码, 主拓机构:
   - Pick the row (within the plan) with the maximum 期末资产规模 (numeric compare; clean commas/currency/full‑width → Decimal).
   - 主拓代码 <- that row’s 计划代码; 主拓机构 <- that row’s 机构名称.
3) 备注:
   - From 月度 to `YYMM_新建` (月度 may be date/int/string like 202411; parse to YYYY‑MM‑01; YY=year%100; MM 2 digits).
4) 资格:
   - From distinct 业务类型 (set), keep those appearing in this fixed order only: ["企年受托", "企年投资", "职年受托", "职年投资"], and join with '+'.
   - If none present, leave NULL/empty (consistent with table definition).

- Ensure these fields are included in `refs.plans.updatable` so `fill_null_only` can set them.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "backfill or run_config or qualified or derivation"
```

Manual checks (record in VALIDATION.md):
- CLI shows `Skip facts: True` → no fact load summary printed.
- With refs (schema=public), Reference Backfill Summary indicates inserts into `"public"."年金计划"` / `"public"."组合计划"`.
- ON CONFLICT fast path (with unique indexes) and fallback path (without) both succeed.
- Show an example plan row with derived fields (客户名称/主拓代码/主拓机构/备注/资格) from the subset.

## ACCEPTANCE CRITERIA
- `--skip-facts` available and effective; Reference Backfill Summary printed.
- Refs configuration consumed; qualified SQL generated with provided schema.
- Annuity Plan derivations implemented as specified; unit tests cover edge cases.
- README updated; VALIDATION.md contains skip‑facts and qualified SQL evidence.
- All targeted tests pass; no regressions.

## ROLLOUT & RISK
- Misconfigured refs: add validation and clear errors.
- Schema quoting errors: covered by qualified SQL unit tests.
- Accidental fact skipping: default `--skip-facts=False`; print summary flags.
- FK constraints: already gated; verify order = backfill → gate → load.

## APPENDICES (optional snippets)
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
  plans:      { schema: public, table: "年金计划",  key: ["年金计划号"], updatable: ["计划全称","计划类型","客户名称","company_id","主拓代码","主拓机构","备注","资格"] }
  portfolios: { schema: public, table: "组合计划",  key: ["组合代码"],  updatable: ["组合名称","组合类型","运作开始日"] }
```
