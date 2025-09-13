# INITIAL.md — Reference Backfill (Annuity Plans & Portfolios) — Insert Missing and Optional Fill-Null-Only

This INITIAL guides Claude to implement a safe, observable “reference backfill” step driven by facts from the Annuity Scale Details domain. The goal is to insert missing reference rows for Annuity Plans and Portfolios (and optionally fill only null fields) based on the current fact batch, without overwriting human‑maintained fields.

## FEATURE
Introduce Reference Backfill for Annuity:
- Derive candidate reference rows (Annuity Plan, Portfolio) from the processed fact batch (规模明细).
- Backfill references before loading facts: insert missing keys; optionally fill null‑only for selected columns.
- Provide plan‑only preview (no DB changes) and execute modes, with clear summaries and candidate listings.

## SCOPE
- In‑scope:
  - Add derivation of plan candidates (key: 年金计划号) and portfolio candidates (key: 组合代码, + 年金计划号) from processed annuity fact rows.
  - Add loader support for reference backfill:
    - Mode: insert_missing (default) — insert only non‑existing keys.
    - Mode: fill_null_only (optional) — update existing rows only where target fields are NULL.
  - CLI flags to enable backfill and choose mode; plan‑only preview that prints candidate summary and SQL plan.
  - Wire the backfill step before fact load within the existing Dagster job/CLI flow.
- Non‑goals:
  - Do not implement full upsert (arbitrary column overwrite) or business mapping logic.
  - Do not enforce DB foreign keys; this is about enabling downstream apps while keeping facts independent.
  - No Dagster deployment; keep CLI‑first.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  orchestration/
    ops.py          # add: derive_*_refs ops, backfill_refs op
    jobs.py         # CLI flags, run_config plumbing, call backfill ops before fact load
  io/
    loader/warehouse_loader.py  # add insert_missing + optional fill_null_only helpers
  domain/annuity_performance/
    service.py      # provides processed fact rows to derive references from
  utils/
    date_parser.py  # reused by domain service

reference/db_migration/db_structure.json  # reference schemas (Chinese columns)
tests/fixtures/sample_data/annuity_subsets/
  2024年11月年金终稿数据_subset_distinct_5.xlsx
  2024年11月年金终稿数据_subset_overlap_pk_6.xlsx
  2024年11月年金终稿数据_subset_append_3.xlsx
```

## EXAMPLES (most important)
- Plan‑only backfill (candidates + SQL plan only):
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1 \
  --backfill-refs all --backfill-mode insert_missing
```
- Execute backfill (insert missing only), then load facts:
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --execute --max-files 1 \
  --backfill-refs all --backfill-mode insert_missing --mode delete_insert
```
- Execute with fill‑null‑only (optional, if implemented):
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --execute --max-files 1 \
  --backfill-refs plans --backfill-mode fill_null_only
```

## DOCUMENTATION
- Internal:
  - `reference/db_migration/db_structure.json` (Chinese schemas; keys and columns)
  - `src/work_data_hub/io/loader/warehouse_loader.py` (new helpers)
  - `src/work_data_hub/orchestration/ops.py` (new ops)
  - `src/work_data_hub/orchestration/jobs.py` (CLI flags + wiring)
- Conventions: `CLAUDE.md` (quoting Chinese identifiers, naming)

## INTEGRATION POINTS
- From facts (processed rows) → derive plan/portfolio candidates
- Loader executes reference backfill before fact `load_op`
- CLI flags control behavior; plan‑only path prints SQL and candidate summary

## DATA CONTRACTS (schemas & payloads)
- Derived candidates from fact rows (example fields):
  - Annuity Plan (table: "年金计划", key: 年金计划号)
    - Keys: 年金计划号 (from 计划代码)
    - Optional fields (fill if available from facts): 计划全称 (from 计划名称), 计划类型, 客户名称, company_id
  - Portfolio (table: "组合计划", key: 组合代码)
    - Keys: 组合代码 (processed/f‑prefix corrected), 年金计划号 (from 计划代码)
    - Optional fields: 组合名称, 组合类型, 运作开始日
- Output to loader:
  - insert_missing: row dicts with key + optional fields; ignore if key exists
  - fill_null_only (optional): update existing rows only where target field IS NULL

## GOTCHAS & LIBRARY QUIRKS
- Do not rely on DB unique constraints; pre‑check existing keys via SELECT and filter before INSERT (works even without ON CONFLICT).
- Chinese identifiers must be quoted via existing `quote_ident` helper in loader.
- Keep backfill idempotent and side‑effect minimal: no deletes, no overwrites of non‑null fields.
- F‑prefix on portfolios is already handled in domain service; reuse the processed value.

## IMPLEMENTATION NOTES
- Files to touch:
  - `src/work_data_hub/orchestration/ops.py`:
    - `derive_plan_refs_op(processed_rows) -> List[Dict]`
    - `derive_portfolio_refs_op(processed_rows) -> List[Dict]`
    - `backfill_refs_op(candidates, config)` with config: {table, key_cols, mode: [insert_missing|fill_null_only], plan_only: bool}
  - `src/work_data_hub/io/loader/warehouse_loader.py`:
    - Add helpers: `insert_missing(table, key_cols, rows, conn)` and optional `fill_null_only(table, key_cols, rows, updatable_cols, conn)`
      - Approach: SELECT existing keys IN (...), compute missing; batch INSERT missing via `execute_values`.
      - For fill‑null‑only: per updatable col, UPDATE ... SET col = %s WHERE key match AND col IS NULL.
  - `src/work_data_hub/orchestration/jobs.py`:
    - CLI flags: `--backfill-refs` (choices: plans|portfolios|all), `--backfill-mode` (choices: insert_missing|fill_null_only|both)
    - Wire: discover → read → process → derive candidates (per flag) → backfill (per mode) → load facts
- Candidate mapping:
  - Plan: {年金计划号=计划代码, 计划全称=计划名称, 计划类型, 客户名称, company_id}
  - Portfolio: {组合代码=组合代码, 年金计划号=计划代码, 组合名称, 组合类型, 运作开始日}
- Config surface:
  - Put target table names and key columns in a small config dict (inline or extend data_sources.yml under annuity with `refs:` block) for discoverability.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k reference_backfill

# Plan-only preview on subsets
WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets \
  uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1 \
  --backfill-refs all --backfill-mode insert_missing
```

## ACCEPTANCE CRITERIA
- Derivation:
  - Correctly extracts candidate keys and optional fields from processed fact rows.
  - Deduplicates candidates; logs counts per reference type.
- insert_missing:
  - Plan‑only shows SQL plan and candidate summaries; no DB changes.
  - Execute inserts only non‑existing keys; does not modify existing rows.
  - Summary includes inserted counts per table (plans, portfolios).
- fill_null_only (optional if implemented):
  - Updates only NULL fields; does not overwrite non‑null values; summary shows updated counts per column.
- Pipeline:
  - When enabled, backfill runs before fact load and succeeds on subsets; fact load remains unchanged.
- CI gates green: ruff, mypy, pytest.

## ROLLOUT & RISK
- No FK enforcement: reference backfill reduces missing references but does not require FK; later we can enable FK progressively.
- Data quality variability: some optional fields may be absent in facts; treat them as nullable and do not block insert_missing.
- Concurrency: insert_missing should SELECT‑filter keys to avoid duplicate inserts; ON CONFLICT DO NOTHING can be used only if a unique index exists.

## APPENDICES (optional snippets)
```python
# Example key filtering (insert_missing)
existing = select_existing_keys(conn, table, key_cols, candidates)
to_insert = [r for r in candidates if tuple(r[k] for k in key_cols) not in existing]
bulk_insert(conn, table, to_insert)
```

