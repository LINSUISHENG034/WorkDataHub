# Validation Report: Story 7.6-6 Contract Status Sync (Post-ETL Hook)

**Document:** `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2026-01-17

---

## Summary

- **Overall:** 26/30 passed **(87%)**
- **Critical Issues:** 3
- **Partial Items:** 4

---

## Section Results

### § Epic & Story Requirements Analysis
Pass Rate: 7/7 (100%)

✓ **Epic 7.6 context** — Story correctly references dependencies (7.6-0 to 7.6-5)
✓ **Acceptance criteria** — 5 well-defined ACs with measurable outcomes
✓ **Business value** — Clear BI Analyst user story with automation benefit
✓ **Technical constraints** — CLI integration, hook pattern, idempotency covered
✓ **Cross-story dependencies** — Correctly lists prerequisite stories
✓ **Effort estimate** — 1.5 days aligns with scope
✓ **Rollback strategy** — DDL reversible with `DROP TABLE CASCADE`

---

### § Architecture Deep-Dive
Pass Rate: 6/8 (75%)

✓ **Technical stack** — Alembic migration, Python CLI, PostgreSQL DDL specified
✓ **Code structure** — File tree clearly shows new packages and modifications
✓ **Post-ETL Hook pattern** — Design matches Sprint Change Proposal §4.2
✓ **CLI conventions** — Follows Epic 7 modularization pattern
✓ **Migration pattern** — References existing migrations correctly

⚠ **PARTIAL: FK Constraint Naming Inconsistency**
- **DDL Line 146-147** references `mapping.産品線(産品線代码)` — **Japanese 産 character** used instead of Chinese 产品线
- **Evidence:** Story DDL uses `産` (\u7523, Japanese) vs. specification v0.6 line 114 uses `产` (\u4ea7, Chinese)
- **Impact:** Migration will fail with FK reference error if table name doesn't match exactly

✗ **FAIL: Missing company_id FK Constraint**
- Story DDL Line 117 mentions `UNIQUE` constraint but specification v0.6 lines 111-112 explicitly includes:
  ```sql
  CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
      REFERENCES mapping."年金客户"(company_id)
  ```
- **Story DDL does NOT include this FK constraint**
- **Impact:** Data integrity violation — orphan company_ids possible

✗ **FAIL: Column Naming Mismatch in Validation SQL**
- Story Line 304-306 validation SQL references `mapping.産品線.産品線代码` — inconsistent with DDL
- Line 265 SQL references `mapping.産品線 p ON s.産品線代码 = p.産品線代码` — uses Japanese characters

---

### § Previous Story Intelligence
Pass Rate: 6/6 (100%)

✓ **Story 7.6-5 learnings** — Sheet names, 100% fill rate, pattern noted (Line 231-242)
✓ **Git commit patterns** — `feat(schema):`, `feat(customer):`, `feat(cli):` documented
✓ **Alembic naming** — `00X_xxx.py` pattern acknowledged
✓ **ETL execution pattern** — Uses existing CLI patterns
✓ **EQC enrichment** — Not required for this story (data from规模明细 already enriched)
✓ **Aggregation view** — Correctly notes this story builds on 7.6-3 view

---

### § Technical Specification Quality
Pass Rate: 5/7 (71%)

✓ **Table DDL** — Comprehensive with columns, constraints, indexes
✓ **Contract status logic** — Python pseudocode provided (Line 167-172)
✓ **Post-ETL Hook pattern** — Dataclass and registry pattern well-defined
✓ **CLI commands** — Three commands documented with correct syntax
✓ **Validation queries** — 5 SQL queries provided

⚠ **PARTIAL: Simplified contract_status Logic**
- Story uses simplified logic: `期末资产规模 > 0 → 正常, else → 停缴`
- Specification v0.6 §4.3.1-4.3.2 defines **12-month rolling window** for 停缴 detection:
  ```
  停缴: 期末资产规模 > 0 且 过去12个月无供款
  ```
- **Impact:** Story correctly notes this is "simplified" for v1, but developer may not know to implement the complex logic later

✗ **FAIL: is_strategic/is_existing Implementation Missing**
- DDL includes `is_strategic BOOLEAN`, `is_existing BOOLEAN` columns
- Story Line 330 explicitly defers: "Full strategic customer logic will be implemented in Story 7.6-9"
- **But:** No placeholder logic provided — columns will be NULL or FALSE for all records
- **Impact:** Story claims to "populate initial contract data" (AC-2) but doesn't specify how these columns are initialized

---

### § File Structure & Organization
Pass Rate: 5/5 (100%)

✓ **New files** — `hooks.py`, `contract_sync.py`, customer_mdm CLI package clearly listed
✓ **Modified files** — `main.py`, `executors.py` modifications specified
✓ **Migration path** — `008_create_customer_plan_contract.py` follows naming convention
✓ **Package structure** — CLI separation (cli/customer_mdm/) from service layer (customer_mdm/)
✓ **Config file** — Optional `config/customer_mdm.yaml` documented

---

### § LLM Developer Agent Optimization
Pass Rate: 4/4 (100%)

✓ **Clarity** — Instructions are precise and actionable
✓ **Scannable structure** — Tasks, Dev Notes, CLI Commands all well-organized
✓ **Token efficiency** — Story at 357 lines is reasonable for scope
✓ **Unambiguous language** — Most requirements have explicit values

---

## Failed Items

### 1. Missing company_id FK Constraint [CRITICAL]

**Location:** Dev Notes → Table DDL, Line 116-151
**Issue:** The FK constraint `fk_contract_company FOREIGN KEY (company_id) REFERENCES mapping."年金客户"(company_id)` is present in specification v0.6 but **missing from story DDL**.
**Recommendation:** Add the constraint after line 150:
```sql
CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
    REFERENCES mapping."年金客户"(company_id),
```

### 2. Japanese Character in FK Reference [CRITICAL]

**Location:** Dev Notes → Table DDL, Line 146-147
**Issue:** Uses `mapping.産品線` (Japanese 産) instead of `mapping.产品线` (Chinese 产)
**Recommendation:** Replace all occurrences:
- Line 147: `REFERENCES mapping."产品线"(产品线代码)`
- Line 265, 304-305: Update validation SQL accordingly

### 3. is_strategic/is_existing Initialization Missing [HIGH]

**Location:** Tasks → Task 2, Line 76-81
**Issue:** Story claims to "Populate initial contract data" (AC-2) but doesn't specify how `is_strategic`, `is_existing`, `status_year` are determined. These columns have `DEFAULT FALSE` but no explicit initialization logic.
**Recommendation:** Add explicit initialization guidance:
```
- Set is_strategic = FALSE (placeholder, Story 7.6-9 will implement)
- Set is_existing = FALSE (placeholder, Story 7.6-9 will implement)
- Set status_year = EXTRACT(YEAR FROM CURRENT_DATE)
```

---

## Partial Items

### 1. FK Constraint Naming

**What's there:** Story DDL includes `fk_contract_product_line` constraint
**What's missing:** Character encoding mismatch (産 vs 产), constraint `fk_contract_company`

### 2. contract_status Rolling Window

**What's there:** Simplified logic documented
**What's missing:** Story should explicitly state this is v1 simplified logic and link to specification for full implementation

### 3. Validation SQL Character Consistency

**What's there:** 5 validation queries provided
**What's missing:** Queries use Japanese characters inconsistently

### 4. Configuration Discovery

**What's there:** Optional `config/customer_mdm.yaml` documented
**What's missing:** Story doesn't specify if developer should CREATE this file or if it already exists

---

## Recommendations

### Must Fix (Before Implementation)

1. **Add FK constraint for company_id** — Critical for data integrity
2. **Fix character encoding** — Replace 産 → 产 in ALL SQL/DDL references
3. **Clarify is_strategic/is_existing initialization** — Add explicit placeholder values

### Should Improve

4. **Add explicit note about contract_status v1 vs v2** — Prevent future confusion
5. **Specify config file creation** — Is `config/customer_mdm.yaml` new or existing?
6. **Add executors.py hook integration point** — Specify WHERE in `_execute_single_domain` to add hook call (after line 379 success check)

### Consider

7. **Add sample data validation** — Include expected record count estimates
8. **Add error handling guidance** — What happens if hooks fail? Rollback? Continue?
