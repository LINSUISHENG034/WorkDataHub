# Implementation Plan: Customer Schema Table Rename

> **Source**: `customer-schema-table-rename-mapping.md`
> **Date**: 2026-02-26
> **Scope**: Rename 6 tables, 11 triggers, 1 seed file across ~50 files
> **Strategy**: Direct modification of existing Alembic scripts (fresh-build scenario, no ALTER TABLE RENAME)

---

## Rename Reference (Quick Lookup)

| ID | Old Name | New Name | Type |
|----|----------|----------|------|
| T1 | `customer_plan_contract` | `客户年金计划` | Table |
| T2 | `fct_customer_product_line_monthly` | `客户业务月度快照` | Table |
| T3 | `fct_customer_plan_monthly` | `客户计划月度快照` | Table |
| T4 | `当年中标` | `中标客户明细` | Table |
| T5 | `当年流失` | `流失客户明细` | Table |
| T6 | `年金客户` (in migrations) / `年金关联公司` (in src/config/tests) | `客户明细` | Table |

> **Critical Discovery**: Alembic migrations use `年金客户` (post-rename from commit `5495b53`), while `src/`, `config/`, and `tests/` still use `年金关联公司`. Both map to `客户明细`.

---

## Pre-Implementation Checklist

- [ ] Ensure clean git state (`git stash` or commit WIP)
- [ ] Verify current `alembic upgrade head` works on empty DB (baseline)
- [ ] Run `uv run ruff check src/` to confirm clean baseline
- [ ] Run `PYTHONPATH=src uv run pytest tests/unit -x` to confirm passing baseline

---

## Step 1: Alembic Migration Scripts (12 files)

> **Path**: `io/schema/migrations/versions/`
> **Principle**: Direct in-place edit for fresh-build. No ALTER TABLE RENAME.
> **Verification**: `alembic upgrade head` on empty DB succeeds.

### 1.1 `001_initial_infrastructure.py` — T6 (`年金客户` → `客户明细`)

| What | Change |
|------|--------|
| Table name | `年金客户` → `客户明细` (in `_table_exists`, `op.create_table`, downgrade) |
| PK constraint | `年金客户_pkey` → `客户明细_pkey` |
| `mapping."年金客户"` view | Keep view name, change source: `customer."年金客户"` → `customer."客户明细"` |
| `customer."年金客户"` compat view | **Delete entirely** (per §1.1: project not in production) |
| Comments | Update all `年金客户` references in docstrings/comments |

### 1.2 `003_seed_static_data.py` — T6 (seed refs)

| What | Change |
|------|--------|
| Identity column list | `年金客户` → `客户明细` |
| Conditional check | `table_name == "年金客户"` → `"客户明细"` |
| CSV load call | Table `年金客户` → `客户明细`, filename `年金客户.csv` → `客户明细.csv` |
| Downgrade truncate | `年金客户` → `客户明细` |

### 1.3 `004_create_annual_award.py` — T4 (`当年中标` → `中标客户明细`) + TR4

| What | Change |
|------|--------|
| Table name | All `当年中标` → `中标客户明细` (CREATE TABLE, indexes, triggers, downgrade) |
| Trigger function | `update_annual_award_updated_at()` → `update_中标客户明细_updated_at()` |
| Trigger name | `trg_annual_award_updated_at` → `trg_中标客户明细_updated_at` |

### 1.4 `005_create_annual_loss.py` — T5 (`当年流失` → `流失客户明细`) + TR5

| What | Change |
|------|--------|
| Table name | All `当年流失` → `流失客户明细` (CREATE TABLE, indexes, triggers, downgrade) |
| Trigger function | `update_annual_loss_updated_at()` → `update_流失客户明细_updated_at()` |
| Trigger name | `trg_annual_loss_updated_at` → `trg_流失客户明细_updated_at` |

### 1.5 `006_create_business_type_view.py` — T4, T5 (view refs)

| What | Change |
|------|--------|
| View SQL | `customer."当年中标"` → `customer."中标客户明细"` |
| View SQL | `customer."当年流失"` → `customer."流失客户明细"` |

### 1.6 `007_add_customer_tags_jsonb.py` — T6 (`年金客户` → `客户明细`)

| What | Change |
|------|--------|
| Table name | All `年金客户` → `客户明细` (ALTER TABLE, UPDATE, COMMENT ON) |
| GIN index | `idx_年金客户_tags_gin` → `idx_客户明细_tags_gin` |
| Downgrade | Update DROP INDEX and ALTER TABLE DROP COLUMN refs |

### 1.7 `008_create_customer_plan_contract.py` — T1 + TR1/TR6/TR7 + FK

| What | Change |
|------|--------|
| Table name | All `customer_plan_contract` → `"客户年金计划"` (CREATE TABLE, indexes, triggers, downgrade) |
| FK reference | `customer."年金客户"(company_id)` → `customer."客户明细"(company_id)` |
| TR1 function | `update_customer_plan_contract_timestamp()` → `update_客户年金计划_timestamp()` |
| TR1 trigger | `update_customer_plan_contract_timestamp` → `update_客户年金计划_timestamp` |
| TR6 function | `sync_contract_customer_name()` → `sync_客户年金计划_customer_name()` |
| TR6 trigger | `trg_sync_contract_customer_name` → `trg_sync_客户年金计划_customer_name` |
| TR6 source table | `ON customer."年金客户"` → `ON customer."客户明细"` |
| TR7 function | `sync_contract_plan_name()` → `sync_客户年金计划_plan_name()` |
| TR7 trigger | `trg_sync_contract_plan_name` → `trg_sync_客户年金计划_plan_name` |

### 1.8 `009_create_fct_customer_monthly_status.py` — T2 + TR2/TR8 + FK

| What | Change |
|------|--------|
| Table name | All `fct_customer_product_line_monthly` → `"客户业务月度快照"` |
| FK reference | `customer."年金客户"(company_id)` → `customer."客户明细"(company_id)` |
| TR2 function | `update_fct_pl_monthly_timestamp()` → `update_客户业务月度快照_timestamp()` |
| TR2 trigger | `update_fct_pl_monthly_timestamp` → `update_客户业务月度快照_timestamp` |
| TR8 function | `sync_fct_pl_customer_name()` → `sync_客户业务月度快照_customer_name()` |
| TR8 trigger | `trg_sync_fct_pl_customer_name` → `trg_sync_客户业务月度快照_customer_name` |
| TR8 source table | `ON customer."年金客户"` → `ON customer."客户明细"` |

### 1.9 `010_create_bi_star_schema.py` — T6 + BUG FIX

| What | Change |
|------|--------|
| dim_customer view | `customer."年金客户"` → `customer."客户明细"` |
| fct view refs | `fct_customer_business_monthly_status` → `"客户业务月度快照"` |

> **BUG FIX**: This file references `fct_customer_business_monthly_status` (old name pre-009 rename). The actual table created by 009 is `fct_customer_product_line_monthly`. This rename fixes the pre-existing bug by using the correct new name `客户业务月度快照`.

### 1.10 `011_create_sync_product_line_trigger.py` — TR9 + BUG FIX

| What | Change |
|------|--------|
| TR9 function | `sync_product_line_name()` → `sync_产品线名称()` |
| TR9 trigger name | `trg_sync_product_line_name` — **NO CHANGE** (per mapping doc) |
| Function body ref | `customer_plan_contract` → `"客户年金计划"` |
| Function body ref | `fct_customer_business_monthly_status` → `"客户业务月度快照"` |

> **BUG FIX (TR9)**: Function body references `fct_customer_business_monthly_status` which never existed in the active migration chain. Should have been `fct_customer_product_line_monthly`. Fixed to `客户业务月度快照`.

### 1.11 `012_fix_contract_unique_constraint.py` — T1

| What | Change |
|------|--------|
| Table name | All `customer_plan_contract` → `"客户年金计划"` (8 occurrences in ALTER TABLE, SELECT) |

### 1.12 `013_create_fct_customer_plan_monthly.py` — T3 + TR3/TR10/TR11 + FK

| What | Change |
|------|--------|
| Table name | All `fct_customer_plan_monthly` → `"客户计划月度快照"` |
| FK reference | `customer."年金客户"(company_id)` → `customer."客户明细"(company_id)` |
| TR3 function | `update_fct_plan_monthly_timestamp()` → `update_客户计划月度快照_timestamp()` |
| TR3 trigger | `update_fct_plan_monthly_timestamp` → `update_客户计划月度快照_timestamp` |
| TR10 function | `sync_fct_plan_customer_name()` → `sync_客户计划月度快照_customer_name()` |
| TR10 trigger | `trg_sync_fct_plan_customer_name` → `trg_sync_客户计划月度快照_customer_name` |
| TR10 source | `ON customer."年金客户"` → `ON customer."客户明细"` |
| TR11 function | `sync_fct_plan_plan_name()` → `sync_客户计划月度快照_plan_name()` |
| TR11 trigger | `trg_sync_fct_plan_plan_name` → `trg_sync_客户计划月度快照_plan_name` |

### Step 1 Verification

```bash
# Drop and recreate DB, then run migrations
alembic upgrade head
# Verify all 6 tables exist with new names
psql -c "SELECT tablename FROM pg_tables WHERE schemaname='customer' ORDER BY tablename;"
```

---

## Step 2: Seed Data File + Resolver (2 files)

### 2.1 Rename CSV file

```bash
cd config/seeds/001/
mv "年金关联公司.csv" "客户明细.csv"
```

### 2.2 `src/work_data_hub/io/schema/seed_resolver.py` — docstring only

| What | Change |
|------|--------|
| Lines 10, 13, 114-116 | Docstring examples: `年金关联公司.csv` → `客户明细.csv` |

> **Note**: This file was **not listed** in the mapping doc §5 but contains references in docstrings.

### Step 2 Verification

```bash
test -f "config/seeds/001/客户明细.csv" && echo "OK" || echo "FAIL"
test ! -f "config/seeds/001/年金关联公司.csv" && echo "OK" || echo "FAIL"
```

---

## Step 3: Config Files (4 files)

> **Path**: `config/`
> **Verification**: `uv run ruff check src/` passes (config loaded by Python code)

### 3.1 `config/customer_status_rules.yml` — T4, T5

| Line | Change |
|------|--------|
| 21 | `table: "当年中标"` → `table: "中标客户明细"` |
| 26 | `table: "当年流失"` → `table: "流失客户明细"` |
| 54, 67, 80, 93 | Comments: `当年中标` / `当年流失` → new names |

### 3.2 `config/data_sources.yml` — T4, T5

| Line | Change |
|------|--------|
| 144 | `table: "当年中标"` → `table: "中标客户明细"` |
| 173 | `table: "当年流失"` → `table: "流失客户明细"` |
| 150, 179 | Comments: `年金关联公司` → `客户明细` |

> **Note**: File patterns like `"*当年中标*.xlsx"` (line 133) and `"*当年流失*.xlsx"` (line 163) are **Excel file globs**, NOT table names. Do NOT change these.

### 3.3 `config/domain_sources.yaml`

No table name references to change. The `path_pattern` values are file globs, not table names.

### 3.4 `config/foreign_keys.yml` — T6

| Line(s) | Change |
|---------|--------|
| 162, 324, 400, 488 | `target_table: "年金关联公司"` → `target_table: "客户明细"` |
| 156-157, 319, 393, 397, 481, 485 | Comments: `年金关联公司` → `客户明细` |

---

## Step 4: Source Code — Python + SQL (15 files)

> **Path**: `src/work_data_hub/`
> **Verification**: `uv run ruff check src/` + `uv run mypy src/` pass

### 4.1 `customer_mdm/sql/` — SQL Templates (4 files)

These are the most critical changes — live SQL executed at runtime.

#### `sync_insert.sql` — T1, T6

| Line | Old | New |
|------|-----|-----|
| 21 | `customer.customer_plan_contract` | `customer."客户年金计划"` |
| 61 | `customer."年金关联公司"` | `customer."客户明细"` |
| 80 | `customer.customer_plan_contract` | `customer."客户年金计划"` |

#### `close_old_records.sql` — T1

| Line | Old | New |
|------|-----|-----|
| 60 | `customer.customer_plan_contract` | `customer."客户年金计划"` |

#### `annual_cutover_insert.sql` — T1, T6

| Line | Old | New |
|------|-----|-----|
| 65 | `customer.customer_plan_contract` | `customer."客户年金计划"` |
| 69 | `customer.customer_plan_contract` | `customer."客户年金计划"` |
| 102 | `customer."年金关联公司"` | `customer."客户明细"` |

#### `annual_cutover_close.sql` — T1

| Line | Old | New |
|------|-----|-----|
| 11 | `customer.customer_plan_contract` | `customer."客户年金计划"` |

### 4.2 `customer_mdm/` — Python Modules (4 files)

#### `contract_sync.py` — T1 (docstrings only)

| Line | Change |
|------|--------|
| 6, 174 | Docstring: `customer.customer_plan_contract` → `customer."客户年金计划"` |

#### `snapshot_refresh.py` — T1, T4, T5

| Line | Old | New |
|------|-----|-----|
| 196, 288, 359, 368 | `customer.customer_plan_contract` | `customer."客户年金计划"` |
| 7, 16, 17, 25 | Docstrings: update table name references |

#### `year_init.py` — T1

| Line | Old | New |
|------|-----|-----|
| 95, 122, 163, 186 | `customer.customer_plan_contract` | `customer."客户年金计划"` |
| 199 | Docstring update |

#### `validation.py` — T1

| Line | Old | New |
|------|-----|-----|
| 78, 91 | `customer.customer_plan_contract` | `customer."客户年金计划"` |

### 4.3 `domain/annual_award/` — T4, T1 (7 files)

#### `service.py` — T4 (runtime table name)

| Line | Old | New |
|------|-----|-----|
| 90 | `table_name = config_table or "当年中标"` | `table_name = config_table or "中标客户明细"` |
| 1, 62 | Docstrings: `当年中标` → `中标客户明细` |

#### `pipeline_builder.py` — T1, T4

| Line | Old | New |
|------|-----|-----|
| 318 | `FROM customer.customer_plan_contract` | `FROM customer."客户年金计划"` |
| 1, 213, 215, 245, 270, 315, 394, 470 | Docstrings/comments: `customer_plan_contract` → `客户年金计划` |

#### `__init__.py`, `models.py`, `constants.py`, `schemas.py`, `helpers.py` — docstrings only

All contain `Annual Award (当年中标)` in line 1 docstring → change to `Annual Award (中标客户明细)`.
`helpers.py` line 95 comment: `customer_plan_contract` → `客户年金计划`.

### 4.4 `domain/annual_loss/` — T5, T1 (7 files)

#### `service.py` — T5 (runtime table name)

| Line | Old | New |
|------|-----|-----|
| 91 | `table_name = config_table or "当年流失"` | `table_name = config_table or "流失客户明细"` |
| 1, 63 | Docstrings: `当年流失` → `流失客户明细` |

#### `pipeline_builder.py` — T1, T5

| Line | Old | New |
|------|-----|-----|
| 251 | `FROM customer.customer_plan_contract` | `FROM customer."客户年金计划"` |
| 1, 177, 180 | Docstrings: `customer_plan_contract` → `客户年金计划` |

#### `__init__.py`, `models.py`, `constants.py`, `schemas.py`, `helpers.py` — docstrings only

All contain `Annual Loss (当年流失)` in line 1 docstring → change to `Annual Loss (流失客户明细)`.
`__init__.py` line 13: `customer_plan_contract` → `客户年金计划`.

### 4.5 `io/schema/seed_resolver.py` — T6 (docstrings only)

| Line(s) | Change |
|---------|--------|
| 10, 13, 114-116 | Docstring examples: `年金关联公司.csv` → `客户明细.csv` |

> **Discovery**: Not listed in mapping doc §5.2 but contains references.

### Step 4 Verification

```bash
uv run ruff check src/
uv run mypy src/
```

---

## Step 5: Test Files (11 files)

> **Path**: `tests/`
> **Verification**: `PYTHONPATH=src uv run pytest tests/unit -x` passes

### 5.1 Integration Tests — `tests/integration/customer_mdm/`

#### `conftest.py` — T4, T5, T6

| What | Old | New |
|------|-----|-----|
| SQL INSERT | `customer."年金关联公司"` | `customer."客户明细"` |
| SQL INSERT | `customer."当年中标"` | `customer."中标客户明细"` |
| SQL INSERT | `customer."当年流失"` | `customer."流失客户明细"` |
| Comments | Update all table name references |

#### `test_e2e_pipeline.py` — T1

| What | Change |
|------|--------|
| All SQL queries | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| Docstrings | Update table name references |

#### `test_trigger_sync.py` — T1, T6

| What | Change |
|------|--------|
| All SQL queries | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| UPDATE statements | `customer."年金关联公司"` → `customer."客户明细"` |
| Docstrings | `年金关联公司.客户名称` → `客户明细.客户名称` |

#### `test_status_fields.py` — T1

| What | Change |
|------|--------|
| All SQL queries (~10 occurrences) | `customer.customer_plan_contract` → `customer."客户年金计划"` |

#### `test_annual_cutover.py` (integration) — T1

| What | Change |
|------|--------|
| SQL query | `customer.customer_plan_contract` → `customer."客户年金计划"` |

#### `test_hook_chain.py` — T1

| What | Change |
|------|--------|
| SQL queries (2 occurrences) | `customer.customer_plan_contract` → `customer."客户年金计划"` |

#### `test_status_evaluation.py` — T4, T5

| What | Change |
|------|--------|
| Assertions/comments | `当年中标` → `中标客户明细` |
| Assertions/comments | `当年流失` → `流失客户明细` |

### 5.2 Unit Tests — `tests/unit/customer_mdm/`

#### `test_annual_cutover.py` (unit) — T1

| What | Change |
|------|--------|
| Line 230 | `assert "customer.customer_plan_contract" in sql` → `assert 'customer."客户年金计划"' in sql` |

#### `test_status_evaluator.py` — T4, T5

| What | Change |
|------|--------|
| Line 46 | `assert "当年中标" in sql` → `assert "中标客户明细" in sql` |
| Line 61, 72 | `assert "当年流失" in sql` → `assert "流失客户明细" in sql` |

#### `test_customer_status_schema.py` — T4

| What | Change |
|------|--------|
| Line 34 | `assert annual_award.table == "当年中标"` → `== "中标客户明细"` |

### 5.3 Additional Test Files (discovered during exploration, not in mapping doc)

#### `tests/integration/migrations/test_enterprise_schema_migration.py` — T6

| What | Change |
|------|--------|
| Lines 344-378 | Method name `test_年金关联公司_table_exists` → `test_客户明细_table_exists` |
| All assertions | `年金关联公司` → `客户明细` (table existence checks, column inspection) |

#### `tests/unit/domain/reference_backfill/test_generic_backfill_service.py` — T6

| What | Change |
|------|--------|
| ~14 occurrences | `target_table="年金关联公司"` → `target_table="客户明细"` |

#### `tests/unit/infrastructure/sql/test_postgresql.py` — T6

| What | Change |
|------|--------|
| Line 150 | `table="年金关联公司"` → `table="客户明细"` |

### Step 5 Verification

```bash
PYTHONPATH=src uv run pytest tests/unit -x
```

---

## Step 6: Scripts (6 files)

> **Path**: `scripts/`
> **Verification**: Scripts can be parsed without syntax errors

### 6.1 `scripts/seed_data/seed_customer_plan_contract.py` — T1, T6

| What | Change |
|------|--------|
| All SQL refs | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| Line 197 | `customer."年金客户"` → `customer."客户明细"` |
| Line 80 | Comment: `customer.年金客户` → `customer.客户明细` |
| Docstrings | Update all `customer_plan_contract` references |

### 6.2 `scripts/seed_data/export_seed_data.py` — T6

| What | Change |
|------|--------|
| Lines 71, 85, 90 | CSV filename refs: `年金客户` → `客户明细` |

### 6.3 `scripts/verify_contract_sync.py` — T1

| What | Change |
|------|--------|
| All SQL/comments | `customer_plan_contract` → `客户年金计划` |

### 6.4 `scripts/check_customer_coverage.py` — T1, T6

| What | Change |
|------|--------|
| All SQL refs | `customer_plan_contract` → `客户年金计划` |
| Lines 77, 106 | `customer."年金客户"` → `customer."客户明细"` (stale refs) |

### 6.5 `scripts/analyze_sync_issues.py` — T1, T6

| What | Change |
|------|--------|
| All SQL refs | `customer_plan_contract` → `客户年金计划` |
| Lines 54, 96 | `customer."年金客户"` → `customer."客户明细"` (stale refs) |

### 6.6 `scripts/analyze_missing_records.py` — T1

| What | Change |
|------|--------|
| All SQL refs | `customer_plan_contract` → `客户年金计划` |

---

## Step 7: Historical Migration SQL Scripts (4 files)

> **Path**: `scripts/migrations/`
> **Note**: Ad-hoc SQL scripts, not part of Alembic chain. One will be deleted.

### 7.1 `scripts/migrations/rename_annuity_customer_table.sql` — **DELETE**

Per mapping doc §5.6: This script performed the `年金客户` → `年金关联公司` rename. Now that the Alembic scripts directly use `客户明细`, this file has no purpose.

```bash
rm scripts/migrations/rename_annuity_customer_table.sql
```

### 7.2 `scripts/migrations/add_contract_name_fields.sql` — T1, T6

| What | Change |
|------|--------|
| All refs | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| Lines 25, 50, 53 | `customer."年金客户"` → `customer."客户明细"` |

### 7.3 `scripts/migrations/rollback_annuity_customer_migration.sql` — T1, T6

| What | Change |
|------|--------|
| All refs | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| All refs | `年金关联公司` / `年金客户` → `客户明细` |

### 7.4 `scripts/migrations/migrate_fct_tables_2026-02-09.sql` — T1, T5, T6

| What | Change |
|------|--------|
| Line 283 | `customer.customer_plan_contract` → `customer."客户年金计划"` |
| Lines 105, 108, 143, 215, 218, 317 | `customer."年金客户"` → `customer."客户明细"` |
| Line 271 | `customer.当年流失` → `customer."流失客户明细"` |

---

## Step 8: Full Verification (End-to-End)

### 8.1 Static Analysis

```bash
uv run ruff check src/
uv run mypy src/
```

### 8.2 Unit Tests

```bash
PYTHONPATH=src uv run pytest tests/unit -x -v
```

### 8.3 Grep Audit — Confirm No Stale References

```bash
# Should return ZERO matches in src/, config/, tests/, scripts/
# (excluding _bmad-output/, docs/, _archived/)
grep -rn "customer_plan_contract" src/ config/ tests/ scripts/ io/schema/
grep -rn "fct_customer_product_line_monthly" src/ config/ tests/ scripts/ io/schema/
grep -rn "fct_customer_plan_monthly" src/ config/ tests/ scripts/ io/schema/
grep -rn "年金关联公司" src/ config/ tests/ scripts/ io/schema/
grep -rn "年金客户" src/ config/ tests/ scripts/ io/schema/
grep -rn "fct_customer_business_monthly_status" src/ config/ tests/ scripts/ io/schema/
```

> **Allowed exceptions**: `当年中标` / `当年流失` may appear in Excel file glob patterns (e.g., `*当年中标*.xlsx`) — these are source file names, NOT table names.

### 8.4 Database Rebuild (if DB available)

```bash
# Drop customer schema and rebuild from scratch
psql -c "DROP SCHEMA IF EXISTS customer CASCADE;"
uv run --env-file .wdh_env alembic upgrade head
```

### 8.5 Integration Tests (if DB available)

```bash
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/integration/customer_mdm -x -v
```

---

## Explicitly Excluded (No Changes)

| Scope | Reason |
|-------|--------|
| `_bmad-output/` | Historical planning artifacts, no runtime impact |
| `docs/` | Reference documentation, update later if needed |
| `_archived/` migrations | Not in active Alembic chain |
| `migration 002` | No target table references found |
| Excel file glob patterns (`*当年中标*.xlsx`, `*当年流失*.xlsx`) | Source file names, not table names |
| Column names (`年金客户标签`, `年金客户类型`) | These are column names within tables, not table names |

---

## Discoveries (Files Not in Mapping Doc)

The following files were found during codebase exploration but were **not listed** in the mapping document §5:

| File | Table Ref | Section |
|------|-----------|---------|
| `src/work_data_hub/io/schema/seed_resolver.py` | `年金关联公司` (docstrings) | Step 4.5 |
| `tests/integration/migrations/test_enterprise_schema_migration.py` | `年金关联公司` | Step 5.3 |
| `tests/unit/domain/reference_backfill/test_generic_backfill_service.py` | `年金关联公司` | Step 5.3 |
| `tests/unit/infrastructure/sql/test_postgresql.py` | `年金关联公司` | Step 5.3 |

---

## Bug Fixes Included

| Bug | Location | Description |
|-----|----------|-------------|
| BUG-1 | Migration 010 | Views reference `fct_customer_business_monthly_status` (never existed). Should be `fct_customer_product_line_monthly`. Fixed to `客户业务月度快照`. |
| BUG-2 | Migration 011 (TR9) | `sync_product_line_name()` body references `fct_customer_business_monthly_status`. Fixed to `客户业务月度快照`. |
| BUG-3 | Scripts (stale refs) | `check_customer_coverage.py`, `analyze_sync_issues.py`, `seed_customer_plan_contract.py` still reference `customer."年金客户"` instead of `年金关联公司`. All fixed to `客户明细`. |

---

## Risk Notes

1. **Chinese table names in SQL require double-quoting**: All new table names must be wrapped in `"..."` in SQL (e.g., `customer."客户年金计划"`). Missing quotes will cause runtime SQL errors.
2. **Trigger source table changes**: TR6/TR8/TR10 triggers fire on `客户明细` (was `年金客户`). Ensure the `ON customer."客户明细"` clause is correct in all trigger definitions.
3. **TR9 trigger name unchanged**: Per mapping doc, `trg_sync_product_line_name` keeps its name. Only the function name changes to `sync_产品线名称()`.

---

## Implementation Order Summary

| Step | Files | Commit Message |
|------|-------|----------------|
| 1 | 12 Alembic migrations | `refactor(customer-mdm): rename customer schema tables in Alembic migrations` |
| 2 | 1 CSV + 1 seed_resolver.py | `refactor(customer-mdm): rename seed CSV 年金关联公司 → 客户明细` |
| 3 | 4 config YAML files | `refactor(customer-mdm): update config files for table renames` |
| 4 | 15 src Python/SQL files | `refactor(customer-mdm): update source code for table renames` |
| 5 | 11 test files | `refactor(customer-mdm): update tests for table renames` |
| 6 | 6 script files | `refactor(customer-mdm): update scripts for table renames` |
| 7 | 4 migration SQL files (1 deleted) | `refactor(customer-mdm): update historical migration scripts` |

> **Total**: ~53 files modified, 1 file renamed, 1 file deleted.

