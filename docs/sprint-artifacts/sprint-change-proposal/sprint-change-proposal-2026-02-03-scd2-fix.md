# Sprint Change Proposal: SCD Type 2 Implementation Fix

> **Date**: 2026-02-03
> **Status**: Pending Approval
> **Triggered By**: Story 7.6-6 Code Review
> **Scope Classification**: Minor
> **Related Document**: [customer-plan-contract-scd2-implementation-gap.md](../../specific/customer-mdm/customer-plan-contract-scd2-implementation-gap.md)

---

## 1. Issue Summary

### 1.1 Problem Statement

The `customer.customer_plan_contract` table's SCD Type 2 implementation has a significant gap between design intent and actual implementation. The specification document (v0.6 §5.3) explicitly requires "close old record + insert new record" when status changes, but the actual implementation uses `ON CONFLICT DO NOTHING`, causing status changes to never be captured.

### 1.2 Discovery Context

- **When**: During code review of Story 7.6-6 (Contract Status Sync)
- **How**: Comparison of specification document vs. actual code implementation
- **Evidence**: `contract_sync.py:176-178` uses `DO NOTHING` instead of SCD Type 2 versioning logic

### 1.3 Evidence

**Code Implementation (Actual)**:
```python
# contract_sync.py:176-178
ON CONFLICT (company_id, plan_code, product_line_code, valid_to)
DO NOTHING  -- Existing records are skipped
```

**Specification Requirement (Expected)**:
```sql
-- Step 1: Close old record
UPDATE customer.customer_plan_contract
SET valid_to = :snapshot_date - INTERVAL '1 day'
WHERE ... AND valid_to = '9999-12-31';

-- Step 2: Insert new record
INSERT INTO customer.customer_plan_contract (...)
VALUES (..., :new_status, :snapshot_date, '9999-12-31');
```

**Scenario Reproduction**:

| Month | company_id | Expected Status | Actual Status |
|-------|------------|-----------------|---------------|
| 2025-06 | C001 | 正常 | 正常 ✅ |
| 2025-12 | C001 | **停缴** | **正常** ❌ |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| Customer MDM | ⚠️ Moderate | Requires new story to fix SCD Type 2 implementation |
| Future Epics | ❌ None | No downstream epic dependencies affected |

### 2.2 Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 7.6-6 | Done | Implementation incomplete - SCD Type 2 not fully realized |
| 7.6-7 | Done | May inherit incorrect status data |
| 7.6-8 | Done | BI reports may show stale status |
| **7.6-12** | **NEW** | **Fix SCD Type 2 implementation** |

### 2.3 Artifact Conflicts

| Artifact | Conflict | Action Needed |
|----------|----------|---------------|
| PRD | ❌ None | Requirements are correct |
| Architecture | ⚠️ Minor | Document SCD Type 2 pattern |
| Specification | ⚠️ Minor | Add implementation details |
| Test Strategy | ⚠️ Minor | Add status change test cases |

### 2.4 Technical Impact

| Area | Impact | Description |
|------|--------|-------------|
| `contract_sync.py` | 🔴 Major | Core sync logic needs refactoring |
| Database Schema | ❌ None | Table structure is correct |
| Post-ETL Hook | ❌ None | Hook pattern unchanged |
| CLI Commands | ❌ None | No changes needed |

### 2.5 Downstream Dependencies

```
customer.customer_plan_contract (Problem Table)
         │
         ▼
customer.fct_customer_business_monthly_status (Monthly Snapshot)
         │
         ▼
Power BI Reports (End Users)
```

> If `customer_plan_contract` status is inaccurate, downstream `fct_customer_business_monthly_status` snapshots will inherit incorrect data.

---

## 3. Recommended Approach

### 3.1 Selected Path: Direct Adjustment

**Approach**: Add new Story 7.6-12 to fix SCD Type 2 implementation within current Epic.

**Rationale**:
1. **Controlled Scope**: Core changes limited to `contract_sync.py`
2. **Low Technical Risk**: SCD Type 2 is a mature pattern with clear implementation path
3. **Minimal Team Impact**: No replanning or rollback required
4. **High Business Value**: Fixes BI report accuracy and historical traceability
5. **Code Reuse**: 90% of existing code can be reused

### 3.2 Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| Rollback Story 7.6-6 | ❌ Not Viable | Problem is logic implementation, not architecture |
| Reduce MVP Scope | ❌ Not Viable | Original MVP is achievable with fix |
| Defer to Post-MVP | ❌ Not Recommended | Core functionality gap affects data quality |

### 3.3 Effort and Risk Assessment

| Metric | Value |
|--------|-------|
| **Effort Estimate** | 1-2 days |
| **Risk Level** | Low |
| **Timeline Impact** | Minimal |
| **Rollback Complexity** | Low (can revert to DO NOTHING if needed) |

---

## 4. Detailed Change Proposals

### 4.1 Story Changes

#### NEW Story: 7.6-12 SCD Type 2 Implementation Fix

```
Story: [7.6-12] SCD Type 2 Implementation Fix
Section: NEW STORY

Goal: Implement complete SCD Type 2 versioning for customer_plan_contract table

Acceptance Criteria:
- AC-1: Status changes trigger version creation (close old + insert new)
- AC-2: Historical queries return correct point-in-time status
- AC-3: Idempotency maintained (safe to re-run)
- AC-4: Existing data migrated/corrected

Tasks:
- Task 1: Refactor contract_sync.py with SCD Type 2 logic
- Task 2: Add status change detection function
- Task 3: Create historical data repair script
- Task 4: Add unit tests for status change scenarios
- Task 5: Update specification document

Effort: 1-2 days
Priority: P0 (High)
```

#### Story 7.6-6 Update

```
Story: [7.6-6] Contract Status Sync (Post-ETL Hook)
Section: Review Follow-ups

OLD:
- [ ] [AI-Review][MEDIUM] Document SCD Type 2 v1 simplified implementation...

NEW:
- [x] [AI-Review][MEDIUM] Document SCD Type 2 v1 simplified implementation...
  → Addressed in Story 7.6-12

Rationale: SCD Type 2 gap identified and tracked in dedicated story
```

### 4.2 Code Changes

#### contract_sync.py Refactoring

```
File: src/work_data_hub/customer_mdm/contract_sync.py
Section: sync_contract_status() function

OLD (Lines 170-180):
INSERT INTO customer.customer_plan_contract (...)
SELECT ...
ON CONFLICT (company_id, plan_code, product_line_code, valid_to)
DO NOTHING;

NEW:
-- Step 1: Close records with changed status
UPDATE customer.customer_plan_contract AS old
SET valid_to = :snapshot_date - INTERVAL '1 day',
    updated_at = CURRENT_TIMESTAMP
FROM (...new status subquery...) AS new
WHERE old.company_id = new.company_id
  AND old.plan_code = new.plan_code
  AND old.product_line_code = new.product_line_code
  AND old.valid_to = '9999-12-31'
  AND (old.contract_status != new.contract_status
       OR old.is_strategic != new.is_strategic
       OR old.is_existing != new.is_existing);

-- Step 2: Insert new/changed records
INSERT INTO customer.customer_plan_contract (...)
SELECT ...
WHERE NOT EXISTS (
    SELECT 1 FROM customer.customer_plan_contract existing
    WHERE existing.company_id = ...
      AND existing.valid_to = '9999-12-31'
      AND existing.contract_status = new.contract_status
      AND existing.is_strategic = new.is_strategic
      AND existing.is_existing = new.is_existing
);

Rationale: Implements complete SCD Type 2 versioning per specification §5.3
```

### 4.3 Documentation Changes

#### Specification Document Update

```
File: docs/specific/customer-mdm/customer-plan-contract-specification.md
Section: 5.3 SCD Type 2 Implementation Logic

ADD after existing content:

### 5.3.1 Status Change Detection Fields

The following fields trigger version creation when changed:
- `contract_status` (正常 ↔ 停缴)
- `is_strategic` (战客状态变化)
- `is_existing` (已客状态变化)

### 5.3.2 Implementation Reference

See `contract_sync.py` for production implementation.

Rationale: Document which fields trigger SCD versioning
```

### 4.4 Test Changes

#### New Test Cases

```
File: tests/unit/customer_mdm/test_contract_sync.py
Section: NEW TEST CASES

ADD:
- test_status_change_creates_new_version()
- test_status_unchanged_no_new_version()
- test_historical_query_returns_correct_status()
- test_idempotency_with_status_changes()

Rationale: Cover status change scenarios per AC-5 from Story 7.6-6
```

---

## 5. Implementation Handoff

### 5.1 Scope Classification

**Classification**: Minor

**Rationale**:
- Changes limited to single module (`contract_sync.py`)
- No architectural changes required
- Can be implemented directly by development team
- No backlog reorganization needed

### 5.2 Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Dev Team** | Implement Story 7.6-12 |
| **Dev Team** | Create and run data repair script |
| **Dev Team** | Update tests and documentation |

### 5.3 Success Criteria

- [ ] Status changes create new version records
- [ ] Old versions have `valid_to` correctly updated
- [ ] Historical queries return correct point-in-time status
- [ ] Idempotency maintained (multiple runs safe)
- [ ] All existing tests pass
- [ ] New status change tests pass

### 5.4 Recommended Implementation Order

1. Create Story 7.6-12 document
2. Refactor `contract_sync.py` with SCD Type 2 logic
3. Add unit tests for status change scenarios
4. Run historical data repair (if needed)
5. Update specification document
6. Verify BI report accuracy

---

## 6. Appendix

### 6.1 Related Files

| File | Path | Purpose |
|------|------|---------|
| Gap Analysis | `docs/specific/customer-mdm/customer-plan-contract-scd2-implementation-gap.md` | Detailed problem analysis |
| Specification | `docs/specific/customer-mdm/customer-plan-contract-specification.md` | Design intent |
| Implementation | `src/work_data_hub/customer_mdm/contract_sync.py` | Current code |
| Story 7.6-6 | `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md` | Original story |

### 6.2 Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-03 | Initial proposal |
