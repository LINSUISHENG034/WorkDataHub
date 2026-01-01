# Sprint Change Proposal: Empty Customer Name Handling Enhancement

**Date:** 2026-01-01
**Author:** Link (via Correct-Course Workflow)
**Status:** Approved
**Epic:** 7.5 (New)
**Priority:** P0-P2

---

## 1. Issue Summary

### Problem Statement

During ETL execution for the 202510 period, data quality issues were discovered related to empty customer name handling:

1. **Backflow Gap (BF-001)**: The backflow mechanism doesn't support `plan_code` mapping, causing 18 plan codes to miss enrichment_index caching
2. **Plan Name Underutilization (PN-001)**: Single-plan records with empty customer names don't extract company names from plan names for EQC lookup
3. **Semantic Inconsistency (CP-001)**: All empty customer name records receive the same temp ID `IN7KZNPWPCVQXJ6AY7`, which is semantically incorrect

### Discovery Context

- **Trigger:** Analysis of 202510 period ETL results
- **Affected Domains:** annuity_income, annuity_performance
- **Evidence Documents:**
  - `docs/specific/customer/empty-customer-name-plan-type-handling.md`
  - `docs/specific/customer/plan-code-backflow-missing.md`
  - `docs/specific/customer/empty-customer-name-handling.md`

### Data Impact

| Metric | Value | Notes |
|--------|-------|-------|
| Single-plan records with empty customer name | 10,565 | 87.2% of single-plan total |
| Single-plan records with temp ID | 297 | 2.8% - should be reducible |
| Collective-plan records with temp ID | 1,530 | 100% - semantic issue |
| Missing plan_code enrichment_index entries | 18 | Due to BF-001 |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Action Required |
|------|--------|-----------------|
| Epic 7.4 (Done) | None | No changes needed |
| Epic 8 (Backlog) | Blocked | Should complete Epic 7.5 first |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| PRD | None | No scope change |
| Architecture | Minor | Update company_id nullable documentation |
| Domain Registry | Modify | annuity_performance.company_id → nullable=True |
| Alembic Migration | Modify | Add ALTER COLUMN in 002_initial_domains.py |

### Technical Impact

| Component | File | Change Type |
|-----------|------|-------------|
| Backflow Module | `infrastructure/enrichment/resolver/backflow.py` | Add plan_code support |
| Pipeline Builder | `domain/annuity_income/pipeline_builder.py` | Add plan name extraction |
| Domain Registry | `infrastructure/schema/definitions/annuity_performance.py` | company_id nullable |
| Temp ID Generator | `infrastructure/enrichment/resolver/backflow.py` | Return None for empty names |
| Migration | `io/schema/migrations/versions/002_initial_domains.py` | ALTER COLUMN |

---

## 3. Recommended Approach

**Selected Path:** Option 1 - Direct Adjustment

**Rationale:**
1. Changes are well-scoped (5 files, 3 logical changes)
2. No rollback required
3. Low risk with clear testing criteria
4. Can be completed before Epic 8

**Effort Estimate:** Medium (8-12 hours)
**Risk Level:** Low

---

## 4. Detailed Change Proposals

### Story 7.5-1: Fix Backflow Logic - Add plan_code Mapping Support (P0)

**Problem ID:** BF-001

**File:** `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py`
**Lines:** 56-60

**Change:**
```python
# OLD
backflow_fields = [
    (strategy.account_number_column, "account", 2, False),  # P2: RAW
    (strategy.customer_name_column, "name", 4, True),  # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
]

# NEW
backflow_fields = [
    (strategy.plan_code_column, "plan", 1, False),  # P1: RAW (plan_code)
    (strategy.account_number_column, "account", 2, False),  # P2: RAW
    (strategy.customer_name_column, "name", 4, True),  # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
]
```

**Acceptance Criteria:**
- [ ] plan_code → company_id mappings are written to enrichment_index with source='pipeline_backflow'
- [ ] Existing P2, P4, P5 backflow behavior unchanged
- [ ] Unit tests updated

---

### Story 7.5-2: Implement Plan Name Fallback for Single-Plan Records (P1)

**Problem ID:** PN-001

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`

**Changes:**
1. Add new function `_fill_customer_name_from_plan_name()`
2. Replace `_fill_customer_name` with new function in pipeline Step 6
3. Update comments

**New Function:**
```python
def _fill_customer_name_from_plan_name(df: pd.DataFrame) -> pd.Series:
    """Fill customer name from plan name for single-plan records only.

    Story 7.5: For '单一计划' records with empty customer name,
    extract company name from plan name by removing suffix '企业年金计划'.

    Extraction rules:
    - Single plan: "{CompanyName}企业年金计划" → "{CompanyName}"
    - Collective plan: Skip (belongs to multiple customers)
    """
    # Implementation as specified in change proposal
```

**Acceptance Criteria:**
- [ ] Single-plan records with empty customer name get company name from plan name
- [ ] Collective-plan records are not affected (customer name remains empty)
- [ ] Extracted names go through CleansingStep for normalization
- [ ] Unit tests for extraction logic

---

### Story 7.5-3: Empty Customer Name Returns NULL Instead of Temp ID (P2)

**Problem ID:** CP-001

**Files:**
1. `src/work_data_hub/infrastructure/schema/definitions/annuity_performance.py`
2. `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py`
3. `io/schema/migrations/versions/002_initial_domains.py`

**Changes:**

#### 3a. Domain Registry (annuity_performance.py:82)
```python
# OLD
ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),

# NEW
ColumnDef("company_id", ColumnType.STRING, nullable=True, max_length=50),
```

#### 3b. Temp ID Generator (backflow.py:203-225)
```python
# OLD: Returns temp ID for empty names
def generate_temp_id(customer_name: Optional[str], salt: str) -> str:
    if customer_name is None or pd.isna(customer_name) or not str(customer_name).strip():
        customer_name = "__EMPTY__"
    return generate_temp_company_id(str(customer_name), salt)

# NEW: Returns None for empty names
def generate_temp_id(customer_name: Optional[str], salt: str) -> Optional[str]:
    if (
        customer_name is None
        or pd.isna(customer_name)
        or not str(customer_name).strip()
        or str(customer_name).strip() in ("0", "空白")
    ):
        return None
    return generate_temp_company_id(str(customer_name), salt)
```

#### 3c. Migration Script (002_initial_domains.py)
Add at end of `upgrade()`:
```python
# Story 7.5: Ensure company_id is nullable for both domain tables
for table_info in [("business", "规模明细"), ("business", "收入明细")]:
    schema, table = table_info
    if _table_exists(conn, table, schema):
        conn.execute(sa.text(
            f'ALTER TABLE {schema}."{table}" ALTER COLUMN company_id DROP NOT NULL'
        ))
```

#### 3d. PostgreSQL Data Fix Commands
```sql
-- Modify column constraints
ALTER TABLE business."规模明细" ALTER COLUMN company_id DROP NOT NULL;
ALTER TABLE business."收入明细" ALTER COLUMN company_id DROP NOT NULL;

-- Update existing temp IDs for empty customer names to NULL
UPDATE business."规模明细"
SET company_id = NULL
WHERE company_id LIKE 'IN%'
  AND ("客户名称" IS NULL OR "客户名称" = '' OR "客户名称" = '0' OR "客户名称" = '空白');

UPDATE business."收入明细"
SET company_id = NULL
WHERE company_id LIKE 'IN%'
  AND ("客户名称" IS NULL OR "客户名称" = '' OR "客户名称" = '0' OR "客户名称" = '空白');
```

**Acceptance Criteria:**
- [ ] annuity_performance and annuity_income have consistent company_id definition (nullable=True)
- [ ] Empty customer name records get company_id=NULL instead of temp ID
- [ ] Non-empty customer name records still get temp ID if unresolved
- [ ] Multi-priority matching mechanism unaffected
- [ ] Existing data migrated correctly
- [ ] Unit tests updated

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

This change can be implemented directly by the development team.

### Story Breakdown

| Story | Priority | Estimated Hours | Dependencies |
|-------|----------|-----------------|--------------|
| 7.5-1: Backflow plan_code support | P0 | 2-3h | None |
| 7.5-2: Plan name fallback | P1 | 3-4h | Story 7.5-1 |
| 7.5-3: Empty name → NULL | P2 | 3-4h | None |

### Implementation Order

```
Story 7.5-1 (P0) ──┬──→ Story 7.5-2 (P1)
                   │
Story 7.5-3 (P2) ──┘
```

### Success Criteria

1. **Backflow Coverage:** enrichment_index contains plan_code records with source='pipeline_backflow'
2. **Single-Plan Resolution:** 297 temp ID records reduced to near-zero (depends on EQC hit rate)
3. **Empty Name Handling:** All empty customer name records have company_id=NULL
4. **Data Consistency:** annuity_income and annuity_performance use same company_id definition
5. **Regression:** All existing tests pass

### Test Plan

1. **Unit Tests:**
   - `test_backflow_plan_code_mapping()` - verify P1 backflow
   - `test_extract_company_name_from_plan_name()` - verify extraction logic
   - `test_generate_temp_id_empty_returns_none()` - verify NULL behavior

2. **Integration Tests:**
   - ETL run with sample data containing empty customer names
   - Verify enrichment_index contains plan_code mappings
   - Verify company_id is NULL for empty customer name records

3. **Data Validation:**
   - SQL queries to verify data distribution after fix

---

## 6. Related Documents

- [Empty Customer Name Plan Type Handling](../../specific/customer/empty-customer-name-plan-type-handling.md)
- [Plan Code Backflow Missing](../../specific/customer/plan-code-backflow-missing.md)
- [Empty Customer Name Handling](../../specific/customer/empty-customer-name-handling.md)

---

## 7. Approval

- [x] **User Approved:** 2026-01-01
- [ ] **Implementation Started**
- [ ] **Code Review Passed**
- [ ] **Deployed to Production**

---

## Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-01 | Link | Initial proposal via Correct-Course workflow |
