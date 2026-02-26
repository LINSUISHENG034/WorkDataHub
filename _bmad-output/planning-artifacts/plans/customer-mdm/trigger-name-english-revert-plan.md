# Implementation Plan: Revert Trigger/Function Names to English

> **Date**: 2026-02-26
> **Scope**: Revert 19 mixed Chinese-English trigger/function/index names back to English across 10 files
> **Rationale**: Mapping doc §4 established that indexes/constraints stay English. Triggers/functions are "code-level" identifiers and should follow the same convention. Table names remain Chinese per dual naming strategy.

---

## Naming Revert Mapping

### updated_at Triggers (TR1-TR5)

| ID | Mixed Name (Current) | English Name (Target) |
|----|---------------------|----------------------|
| TR1-fn | `update_客户年金计划_timestamp()` | `update_customer_plan_contract_timestamp()` |
| TR1-trg | `update_客户年金计划_timestamp` | `update_customer_plan_contract_timestamp` |
| TR2-fn | `update_客户业务月度快照_timestamp()` | `update_fct_pl_monthly_timestamp()` |
| TR2-trg | `update_客户业务月度快照_timestamp` | `update_fct_pl_monthly_timestamp` |
| TR3-fn | `update_客户计划月度快照_timestamp()` | `update_fct_plan_monthly_timestamp()` |
| TR3-trg | `update_客户计划月度快照_timestamp` | `update_fct_plan_monthly_timestamp` |
| TR4-fn | `update_中标客户明细_updated_at()` | `update_annual_award_updated_at()` |
| TR4-trg | `trg_中标客户明细_updated_at` | `trg_annual_award_updated_at` |
| TR5-fn | `update_流失客户明细_updated_at()` | `update_annual_loss_updated_at()` |
| TR5-trg | `trg_流失客户明细_updated_at` | `trg_annual_loss_updated_at` |

### Sync Triggers (TR6-TR11)

| ID | Mixed Name (Current) | English Name (Target) |
|----|---------------------|----------------------|
| TR6-fn | `sync_客户年金计划_customer_name()` | `sync_contract_customer_name()` |
| TR6-trg | `trg_sync_客户年金计划_customer_name` | `trg_sync_contract_customer_name` |
| TR7-fn | `sync_客户年金计划_plan_name()` | `sync_contract_plan_name()` |
| TR7-trg | `trg_sync_客户年金计划_plan_name` | `trg_sync_contract_plan_name` |
| TR8-fn | `sync_客户业务月度快照_customer_name()` | `sync_fct_pl_customer_name()` |
| TR8-trg | `trg_sync_客户业务月度快照_customer_name` | `trg_sync_fct_pl_customer_name` |
| TR9-fn | `sync_产品线名称()` | `sync_product_line_name()` |
| TR10-fn | `sync_客户计划月度快照_customer_name()` | `sync_fct_plan_customer_name()` |
| TR10-trg | `trg_sync_客户计划月度快照_customer_name` | `trg_sync_fct_plan_customer_name` |
| TR11-fn | `sync_客户计划月度快照_plan_name()` | `sync_fct_plan_plan_name()` |
| TR11-trg | `trg_sync_客户计划月度快照_plan_name` | `trg_sync_fct_plan_plan_name` |

### Index

| Mixed Name (Current) | English Name (Target) |
|---------------------|----------------------|
| `idx_客户明细_tags_gin` | `idx_customer_detail_tags_gin` |

---

## Files to Modify (10 files)

### Alembic Migrations (6 files)

| # | File | Triggers Affected |
|---|------|-------------------|
| 1 | `io/schema/migrations/versions/004_create_annual_award.py` | TR4 (4 occurrences) |
| 2 | `io/schema/migrations/versions/005_create_annual_loss.py` | TR5 (4 occurrences) |
| 3 | `io/schema/migrations/versions/007_add_customer_tags_jsonb.py` | idx (2 occurrences) |
| 4 | `io/schema/migrations/versions/008_create_customer_plan_contract.py` | TR1, TR6, TR7 (17 occurrences) |
| 5 | `io/schema/migrations/versions/009_create_fct_customer_monthly_status.py` | TR2, TR8 (11 occurrences) |
| 6 | `io/schema/migrations/versions/011_create_sync_product_line_trigger.py` | TR9 (7 occurrences) |
| 7 | `io/schema/migrations/versions/013_create_fct_customer_plan_monthly.py` | TR3, TR10, TR11 (17 occurrences) |

### Scripts/Migrations (3 files)

| # | File | Triggers Affected |
|---|------|-------------------|
| 8 | `scripts/migrations/add_contract_name_fields.sql` | TR6, TR7 (8 occurrences) |
| 9 | `scripts/migrations/migrate_fct_tables_2026-02-09.sql` | TR2, TR3, TR8, TR10, TR11 (25 occurrences) |
| 10 | `scripts/migrations/rollback_annuity_customer_migration.sql` | TR8, TR10 (6 occurrences) |

---

## Implementation Steps

### Step 1: Migration 004 — TR4 (annual_award)
- [ ] Replace `"update_中标客户明细_updated_at"` → `update_annual_award_updated_at` (remove quotes — English names don't need quoting)
- [ ] Replace `"trg_中标客户明细_updated_at"` → `trg_annual_award_updated_at`

### Step 2: Migration 005 — TR5 (annual_loss)
- [ ] Replace `"update_流失客户明细_updated_at"` → `update_annual_loss_updated_at`
- [ ] Replace `"trg_流失客户明细_updated_at"` → `trg_annual_loss_updated_at`

### Step 3: Migration 007 — Index
- [ ] Replace `idx_客户明细_tags_gin` → `idx_customer_detail_tags_gin`

### Step 4: Migration 008 — TR1, TR6, TR7 (customer_plan_contract)
- [ ] Replace `"update_客户年金计划_timestamp"` → `update_customer_plan_contract_timestamp`
- [ ] Replace `"sync_客户年金计划_customer_name"` → `sync_contract_customer_name`
- [ ] Replace `"trg_sync_客户年金计划_customer_name"` → `trg_sync_contract_customer_name`
- [ ] Replace `"sync_客户年金计划_plan_name"` → `sync_contract_plan_name`
- [ ] Replace `"trg_sync_客户年金计划_plan_name"` → `trg_sync_contract_plan_name`

### Step 5: Migration 009 — TR2, TR8 (fct_pl_monthly)
- [ ] Replace `"update_客户业务月度快照_timestamp"` → `update_fct_pl_monthly_timestamp`
- [ ] Replace `"sync_客户业务月度快照_customer_name"` → `sync_fct_pl_customer_name`
- [ ] Replace `"trg_sync_客户业务月度快照_customer_name"` → `trg_sync_fct_pl_customer_name`

### Step 6: Migration 011 — TR9 (product_line)
- [ ] Replace `"sync_产品线名称"` → `sync_product_line_name`

### Step 7: Migration 013 — TR3, TR10, TR11 (fct_plan_monthly)
- [ ] Replace `"update_客户计划月度快照_timestamp"` → `update_fct_plan_monthly_timestamp`
- [ ] Replace `"sync_客户计划月度快照_customer_name"` → `sync_fct_plan_customer_name`
- [ ] Replace `"trg_sync_客户计划月度快照_customer_name"` → `trg_sync_fct_plan_customer_name`
- [ ] Replace `"sync_客户计划月度快照_plan_name"` → `sync_fct_plan_plan_name`
- [ ] Replace `"trg_sync_客户计划月度快照_plan_name"` → `trg_sync_fct_plan_plan_name`

### Step 8: scripts/migrations/add_contract_name_fields.sql — TR6, TR7
- [ ] Same replacements as Step 4 (TR6, TR7 names)

### Step 9: scripts/migrations/migrate_fct_tables_2026-02-09.sql — TR2, TR3, TR8, TR10, TR11
- [ ] Same replacements as Steps 5, 7

### Step 10: scripts/migrations/rollback_annuity_customer_migration.sql — TR8, TR10
- [ ] Same replacements as Steps 5, 7 (subset)

### Step 11: Verification
- [ ] `grep -rn "update_中标\|update_流失\|update_客户\|sync_客户\|sync_产品\|trg_中标\|trg_流失\|trg_sync_客户\|idx_客户明细" io/ scripts/` returns ZERO matches
- [ ] `uv run ruff check src/`
- [ ] `PYTHONPATH=src uv run pytest tests/unit -x`

### Step 12: Update mapping doc
- [ ] Update `customer-schema-table-rename-mapping.md` §3 to reflect English trigger names

---

## Key Notes

1. **Quoting**: English-only identifiers (no special chars) do NOT need double-quoting in PostgreSQL. Remove quotes when reverting. Chinese table names in ON clauses still need quotes.
2. **No src/tests/config changes**: All mixed names are confined to migration files and SQL scripts.
3. **TR9 trigger name**: `trg_sync_product_line_name` was already English and unchanged.
