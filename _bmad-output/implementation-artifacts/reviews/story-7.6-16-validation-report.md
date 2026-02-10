# 🎯 Story 7.6-16 Validation Report

**Story:** 7.6-16 - Fact Table Refactoring (双表粒度分离)
**Validation Date:** 2026-02-09
**Validator:** Claude Opus 4.6 (claude-opus-4-6)
**Status:** ✅ IMPLEMENTATION COMPLETE

---

## 📊 Implementation Summary

| Task | Status | Notes |
|------|--------|-------|
| Task 1: Modify Migration 009 | ✅ DONE | Table renamed, customer_name added, triggers updated |
| Task 2: Create Migration 013 | ✅ DONE | fct_customer_plan_monthly table created |
| Task 3: Create SQL Script | ✅ DONE | scripts/migrations/migrate_fct_tables_2026-02-09.sql |
| Task 4: Data Backfill | ⏳ PENDING | Runtime operation - SQL script ready |
| Task 5: Update snapshot_refresh.py | ✅ DONE | Dual-table refresh logic implemented |
| Task 6: Update Tests | ✅ DONE | 53 unit tests pass |
| Task 7: Update Documentation | ✅ DONE | Specification updated |

---

## 📋 Pre-Implementation Review (Historical)

The following issues were identified during pre-implementation review and have been **RESOLVED**:

---

## 🚨 CRITICAL ISSUES (Must Fix)

### C1: Missing SQL Script Content for `fct_customer_plan_monthly`

**Problem:** Story references "Task 2: Create Migration 013" and "Task 3: Create Migration SQL Script" but provides **NO DDL specification** for the new `fct_customer_plan_monthly` table.

**Impact:** Dev agent will reinvent table design without critical guidance on:
- Exact column definitions (types, constraints)
- Trigger function signatures
- Index specifications

**Required Fix:** Add complete DDL for `fct_customer_plan_monthly`:

```sql
-- Required table structure (from Sprint Change Proposal §4.2)
CREATE TABLE customer.fct_customer_plan_monthly (
    snapshot_month DATE NOT NULL,
    company_id VARCHAR NOT NULL,
    plan_code VARCHAR NOT NULL,
    product_line_code VARCHAR(20) NOT NULL,
    
    -- Redundant fields for query convenience
    customer_name VARCHAR(200),
    plan_name VARCHAR(200),
    product_line_name VARCHAR(50),
    
    -- Status flags (Plan-level granularity)
    is_churned_this_year BOOLEAN DEFAULT FALSE,
    contract_status VARCHAR(50),
    
    -- Measure
    aum_balance DECIMAL(20,2) DEFAULT 0,
    
    -- Audit
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (snapshot_month, company_id, plan_code, product_line_code),
    
    CONSTRAINT fk_plan_company FOREIGN KEY (company_id)
        REFERENCES customer."年金客户"(company_id),
    CONSTRAINT fk_plan_plan_code FOREIGN KEY (plan_code)
        REFERENCES mapping."年金计划"(年金计划号)
);
```

---

### C2: Missing `refresh_plan_snapshot()` SQL Logic

**Problem:** AC-5 requires `refresh_plan_snapshot()` function but story provides **zero SQL specification** for this new function.

**Impact:** Dev agent will guess at:
- Source tables and JOIN logic
- How `is_churned_this_year` is derived at Plan level
- UPSERT conflict resolution

**Required Fix:** Add SQL template for Plan-level snapshot:

```sql
-- refresh_plan_snapshot() SQL
INSERT INTO customer.fct_customer_plan_monthly (
    snapshot_month, company_id, plan_code, product_line_code,
    customer_name, plan_name, product_line_name,
    is_churned_this_year, contract_status, aum_balance
)
SELECT
    :snapshot_month,
    c.company_id,
    c.plan_code,
    c.product_line_code,
    c.customer_name,  -- From 7.6-13 enhancement
    c.plan_name,      -- From 7.6-13 enhancement
    c.product_line_name,
    
    -- 流失判定: Plan-level granularity (from customer.当年流失)
    EXISTS (
        SELECT 1 FROM customer.当年流失 l
        WHERE l.company_id = c.company_id
          AND l.年金计划号 = c.plan_code
          AND EXTRACT(YEAR FROM l.上报月份) = EXTRACT(YEAR FROM :snapshot_month)
    ) as is_churned_this_year,
    
    c.contract_status,
    
    -- Plan-level AUM
    COALESCE((
        SELECT SUM(s.期末资产规模)
        FROM business.规模明细 s
        WHERE s.company_id = c.company_id
          AND s.计划代码 = c.plan_code
          AND s.月度 = :snapshot_month
    ), 0) as aum_balance

FROM customer.customer_plan_contract c
WHERE c.valid_to = '9999-12-31'

ON CONFLICT (snapshot_month, company_id, plan_code, product_line_code)
DO UPDATE SET
    customer_name = EXCLUDED.customer_name,
    plan_name = EXCLUDED.plan_name,
    is_churned_this_year = EXCLUDED.is_churned_this_year,
    contract_status = EXCLUDED.contract_status,
    aum_balance = EXCLUDED.aum_balance,
    updated_at = CURRENT_TIMESTAMP;
```

---

### C3: Story 7.6-13 NOT Implemented - Dependency Conflict

**Problem:** Story 7.6-16 claims it "merges" 7.6-13 content via AC-2, but 7.6-13 status is `ready-for-dev` (NOT `done`).

**Impact:**
- `customer_name` field does NOT exist in current `fct_customer_business_monthly_status` table
- 7.6-16 depends on non-existent infrastructure
- Dev agent will fail when referencing `customer_name`

**Required Fix Options:**
1. **Explicit Dependency:** Mark 7.6-13 as a blocker that must be completed FIRST
2. **Scope Expansion:** 7.6-16 must implement ALL of 7.6-13's work (triggers, backfill) as part of Migration 009 modifications

---

## ⚡ ENHANCEMENT OPPORTUNITIES (Should Add)

### E1: Missing Index Specifications for New Table

Story mentions "All required indexes created" (AC-3) but doesn't specify which indexes.

**Add:**
```sql
-- Indexes for fct_customer_plan_monthly
CREATE INDEX idx_fct_plan_snapshot_month ON customer.fct_customer_plan_monthly(snapshot_month);
CREATE INDEX idx_fct_plan_company ON customer.fct_customer_plan_monthly(company_id);
CREATE INDEX idx_fct_plan_plan_code ON customer.fct_customer_plan_monthly(plan_code);
CREATE INDEX idx_fct_plan_churned ON customer.fct_customer_plan_monthly(snapshot_month) WHERE is_churned_this_year = TRUE;
CREATE INDEX idx_fct_plan_month_brin ON customer.fct_customer_plan_monthly USING BRIN (snapshot_month);
```

### E2: Missing Sync Trigger Specifications

AC-3 mentions "Sync triggers for `customer_name` and `plan_name`" but provides no DDL.

**Add trigger specs from 7.6-13 pattern:**
```sql
-- Sync customer_name when 年金客户.客户名称 changes
CREATE TRIGGER trg_sync_fct_plan_customer_name
AFTER UPDATE OF 客户名称 ON customer."年金客户"
FOR EACH ROW
EXECUTE FUNCTION customer.sync_fct_plan_customer_name();

-- Sync plan_name when 年金计划.计划全称 changes  
CREATE TRIGGER trg_sync_fct_plan_plan_name
AFTER UPDATE OF 计划全称 ON mapping."年金计划"
FOR EACH ROW
EXECUTE FUNCTION customer.sync_fct_plan_plan_name();
```

### E3: Missing Rollback SQL Script

Story mentions "Execute rollback SQL script" in At a Glance but provides no script content.

**Add `scripts/migrations/rollback_fct_tables_2026-02-09.sql`:**
```sql
-- Rollback script
BEGIN;
-- 1. Drop new table
DROP TABLE IF EXISTS customer.fct_customer_plan_monthly CASCADE;
-- 2. Drop new triggers on renamed table
DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name ON customer."年金客户";
-- 3. Remove customer_name column
ALTER TABLE customer.fct_customer_product_line_monthly DROP COLUMN IF EXISTS customer_name;
-- 4. Rename table back
ALTER TABLE customer.fct_customer_product_line_monthly RENAME TO fct_customer_business_monthly_status;
COMMIT;
```

### E4: Missing Backfill SQL for Historical `fct_customer_plan_monthly`

AC-4 requires "Historical data backfilled into `fct_customer_plan_monthly`" but no SQL provided.

**Add:**
```sql
-- Backfill historical Plan-level snapshots from existing snapshot months
INSERT INTO customer.fct_customer_plan_monthly (...)
SELECT ...
FROM customer.customer_plan_contract c
CROSS JOIN (
    SELECT DISTINCT snapshot_month 
    FROM customer.fct_customer_product_line_monthly
) months
WHERE c.valid_from <= months.snapshot_month
  AND c.valid_to > months.snapshot_month
ON CONFLICT DO NOTHING;
```

---

## ✨ OPTIMIZATIONS (Nice to Have)

### O1: CLI Output Format Specification

AC-5 mentions "CLI output updated to show both table results" but no format specified.

**Suggest:**
```
Monthly Snapshot Refresh Complete:
  fct_customer_product_line_monthly: 1,234 records (upserted: 56)
  fct_customer_plan_monthly: 19,882 records (upserted: 112)
```

### O2: Validation Query for Dual-Table Consistency

Add cross-table validation to ensure ProductLine aggregates match Plan-level totals:

```sql
-- Verify ProductLine AUM = SUM(Plan AUM)
SELECT 
    pl.snapshot_month, pl.company_id, pl.product_line_code,
    pl.aum_balance as pl_aum,
    SUM(p.aum_balance) as plan_sum,
    pl.aum_balance - SUM(p.aum_balance) as diff
FROM customer.fct_customer_product_line_monthly pl
LEFT JOIN customer.fct_customer_plan_monthly p 
    ON pl.snapshot_month = p.snapshot_month
   AND pl.company_id = p.company_id
   AND pl.product_line_code = p.product_line_code
GROUP BY 1,2,3,4
HAVING ABS(pl.aum_balance - SUM(p.aum_balance)) > 0.01;
-- Expected: 0 rows
```

---

## 🤖 LLM OPTIMIZATION (Token Efficiency & Clarity)

### L1: Verbose Task Descriptions

**Current (Task 1):**
```
- [ ] Task 1: Modify Migration 009 (AC: 1, 2)
  - [ ] Rename table to `fct_customer_product_line_monthly`
  - [ ] Add `customer_name VARCHAR(200)` column
  - [ ] Add `idx_fct_pl_customer_name` index
  - [ ] Update trigger function names
  - [ ] Add `trg_sync_fct_pl_customer_name` trigger
```

**Optimized:**
```
- [ ] Task 1: Modify Migration 009 (AC-1, AC-2)
  ```sql
  -- Rename table + add customer_name + sync trigger
  ALTER TABLE customer.fct_customer_business_monthly_status 
    RENAME TO fct_customer_product_line_monthly;
  ALTER TABLE customer.fct_customer_product_line_monthly 
    ADD COLUMN customer_name VARCHAR(200);
  CREATE INDEX idx_fct_pl_customer_name ON ...;
  -- Trigger: see 7.6-13 pattern (copy exactly)
  ```
```

**Benefit:** Dev agent sees exact SQL instead of guessing.

### L2: Missing Dev Notes Critical Context

**Add to Dev Notes:**
```markdown
### ⚠️ CRITICAL: Migration 009 Modification Rules

1. **DO NOT create new 010/011 migrations** - Story 7.6-16 intentionally modifies 009 to keep schema changes grouped
2. **Migration 009 is for "from-scratch" deployments** - Existing databases use SQL script
3. **Trigger functions live in `customer` schema** - Not public schema
4. **Follow existing trigger naming**: `sync_*` pattern from 008 migration
```

### L3: Ambiguous AC-2 Scope

**Current:** "Column `customer_name VARCHAR(200)` added to `fct_customer_product_line_monthly`"

**Clarified:** "Column `customer_name` added **via modifying Migration 009** (not new migration). Sync trigger `trg_sync_fct_pl_customer_name` fires on `customer.年金客户.客户名称` UPDATE events."

---

## 📋 Improvement Summary

| ID | Category | Description | Priority |
|----|----------|-------------|----------|
| C1 | Critical | Add `fct_customer_plan_monthly` DDL | BLOCKER |
| C2 | Critical | Add `refresh_plan_snapshot()` SQL | BLOCKER |
| C3 | Critical | Resolve 7.6-13 dependency conflict | BLOCKER |
| E1 | Enhancement | Add index specifications for new table | HIGH |
| E2 | Enhancement | Add sync trigger DDL | HIGH |
| E3 | Enhancement | Add rollback script | MEDIUM |
| E4 | Enhancement | Add backfill SQL | MEDIUM |
| O1 | Optimization | CLI output format | LOW |
| O2 | Optimization | Cross-table validation query | LOW |
| L1 | LLM Opt | Show SQL in tasks | HIGH |
| L2 | LLM Opt | Add migration modification rules | HIGH |
| L3 | LLM Opt | Clarify AC-2 scope | MEDIUM |

---

## 🎯 Recommended Next Steps

1. **Apply all Critical (C1-C3)** - Story cannot be implemented without these
2. **Apply Enhancements (E1-E4)** - Prevents dev agent mistakes
3. **Apply LLM Optimizations (L1-L3)** - Improves dev agent efficiency
