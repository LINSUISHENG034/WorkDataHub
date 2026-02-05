# Sprint Change Proposal: Customer Status Field Implementation Gap

> **Date**: 2026-02-03
> **Author**: Claude Code (Correct Course Workflow)
> **Status**: Pending Approval
> **Scope Classification**: Minor
> **Related Documents**:
> - [Gap Analysis](../../specific/customer-mdm/customer-plan-contract-status-field-gap-analysis.md)
> - [Specification](../../specific/customer-mdm/customer-plan-contract-specification.md)
> - [Story 7.6-6](../stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md)
> - [Story 7.6-9](../stories/epic-customer-mdm/7.6-9-index-trigger-optimization.md)

---

## 1. Issue Summary

### 1.1 Problem Statement

Three critical status fields in `customer.customer_plan_contract` table were not implemented with their full business logic:

| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| `is_strategic` | 5B threshold + whitelist logic | Fixed `FALSE` | **Missing** |
| `is_existing` | Prior year asset check | Fixed `FALSE` | **Missing** |
| `contract_status` | 12-month rolling contribution window | Single-month AUM only | **Incomplete** |

### 1.2 Discovery Context

- **When**: Post-implementation review of Story 7.6-6
- **How**: Code review identified placeholder values with comments referencing Story 7.6-9
- **Evidence**: `contract_sync.py:110-111` contains:
  ```python
  FALSE as is_strategic,  -- Story 7.6-9 implements full logic
  FALSE as is_existing,   -- Story 7.6-9 implements full logic
  ```

### 1.3 Root Cause

**Scope Gap (Story Handoff Failure)**:
- Story 7.6-6 declared these fields would be implemented in Story 7.6-9
- Story 7.6-9's actual acceptance criteria only covered triggers and index optimization
- Result: Business logic was never assigned to any story

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Action Needed |
|------|--------|---------------|
| Epic 7.6 (Customer MDM) | Moderate | Add Story 7.6-11 |
| Other Epics | None | No action |

### 2.2 Story Impact

| Story | Impact | Action |
|-------|--------|--------|
| 7.6-6 | Completion Notes need update | Document known limitation |
| 7.6-9 | Scope clarification | Update Dev Notes to clarify scope |
| 7.6-11 (NEW) | New story required | Create and implement |

### 2.3 Artifact Conflicts

| Artifact | Conflict | Update Needed |
|----------|----------|---------------|
| PRD | None | No |
| Architecture | None | No |
| Specification | None (already defines logic) | No |
| Power BI Reports | Functional gap | Verify after 7.6-11 |

### 2.4 Technical Impact

| Component | Impact |
|-----------|--------|
| `contract_sync.py` | Requires enhancement |
| `fct_customer_business_monthly_status` | May need sync update |
| Post-ETL Hook | May need year-init trigger |
| CLI | New `init-year` command needed |

### 2.5 Current Data State

Based on Story 7.6-6 completion:
- Total records: 19,882
- `is_strategic = FALSE`: 19,882 (100%)
- `is_existing = FALSE`: 19,882 (100%)
- `contract_status = '正常'`: 17,989 (90.5%)
- `contract_status = '停缴'`: 1,893 (9.5%)

---

## 3. Recommended Approach

### 3.1 Selected Path: Direct Adjustment (Option 1)

**Create Story 7.6-11: Customer Status Field Enhancement**

### 3.2 Rationale

| Factor | Assessment |
|--------|------------|
| Data source readiness | ✅ `business.规模明细` available |
| Configuration readiness | ✅ `config/customer_mdm.yaml` exists |
| Code structure | ✅ `contract_sync.py` established |
| Effort estimate | Medium (1-1.5 days) |
| Risk level | Low |
| Timeline impact | Minimal |

### 3.3 Why Not Other Options

- **Rollback**: Not needed - current implementation is valid placeholder
- **MVP Reduction**: Not acceptable - strategic/existing customer analysis is core requirement

---

## 4. Detailed Change Proposals

### 4.1 Code Changes

#### 4.1.1 contract_sync.py Enhancement

**File**: `src/work_data_hub/customer_mdm/contract_sync.py`

**OLD** (lines 110-111):
```python
FALSE as is_strategic,  -- Story 7.6-9 implements full logic
FALSE as is_existing,   -- Story 7.6-9 implements full logic
```

**NEW**:
```python
CASE
    WHEN aum_summary.total_aum >= %(strategic_threshold)s THEN TRUE
    WHEN whitelist.company_id IS NOT NULL THEN TRUE
    ELSE FALSE
END as is_strategic,
CASE
    WHEN prior_year.company_id IS NOT NULL THEN TRUE
    ELSE FALSE
END as is_existing,
```

**Rationale**: Implement full business logic per specification §4.4.3

#### 4.1.2 contract_sync.py - contract_status Enhancement

**OLD** (lines 113-116):
```python
CASE
    WHEN s.期末资产规模 > 0 THEN '正常'
    ELSE '停缴'
END as contract_status,
```

**NEW**:
```python
CASE
    WHEN s.期末资产规模 > 0 AND contribution_12m.has_contribution THEN '正常'
    WHEN s.期末资产规模 > 0 AND NOT contribution_12m.has_contribution THEN '停缴'
    ELSE NULL  -- Invalid, exclude from results
END as contract_status,
```

**Rationale**: Full v2 logic per specification §4.3.1-4.3.2. Data source `供款` verified available (99.8% coverage).

### 4.2 New CLI Command

**File**: `src/work_data_hub/cli/customer_mdm/init_year.py` (NEW)

**Purpose**: Annual initialization of `is_strategic` and `is_existing` flags

**Command**: `customer-mdm init-year --year 2026`

**Behavior**:
1. Calculate strategic customers (5B threshold + top 10 per branch)
2. Calculate existing customers (prior year asset > 0)
3. Update all contracts for specified year

### 4.3 Documentation Updates

#### 4.3.1 Story 7.6-6 Completion Notes

**File**: `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md`
**Section**: Completion Notes > Known Limitations

**ADD**:
```markdown
**Scope Clarification (2026-02-03)**:
- is_strategic and is_existing placeholder values are intentional for v1
- Full business logic deferred to Story 7.6-11 (not 7.6-9 as originally noted)
- Story 7.6-9 scope was limited to triggers and index optimization only
```

#### 4.3.2 Story 7.6-9 Dev Notes

**File**: `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-9-index-trigger-optimization.md`
**Section**: Dev Notes

**ADD**:
```markdown
### Scope Clarification

> [!NOTE]
> This story's scope is limited to trigger and index optimization.
> The `is_strategic` and `is_existing` business logic mentioned in
> Story 7.6-6 Dev Notes is NOT part of this story's scope.
> See Story 7.6-11 for status field enhancement.
```

---

## 5. Implementation Handoff

### 5.1 Scope Classification: Minor

This change can be implemented directly by the development team without requiring backlog reorganization or architectural review.

### 5.2 Handoff Recipients

| Role | Responsibility |
|------|----------------|
| Dev Team | Implement Story 7.6-11 |
| QA | Validate status field logic |
| BI Analyst | Verify Power BI report functionality |

### 5.3 Implementation Phases

**Single Phase (Immediate)**: All three status fields
- Data source ready: `business.规模明细` (including `供款` field with 99.8% data coverage)
- Configuration exists: `config/customer_mdm.yaml`
- Estimated effort: 1.5 days

> **Note**: Original gap analysis incorrectly assumed `供款` data was unavailable.
> Data verification confirms 624,131 of 625,124 records (99.8%) have valid `供款` values.

### 5.4 Success Criteria

| Criterion | Validation |
|-----------|------------|
| AC-1 | `is_strategic = TRUE` for customers with AUM >= 5B |
| AC-2 | `is_strategic = TRUE` for top 10 customers per branch |
| AC-3 | `is_existing = TRUE` for customers with prior year assets |
| AC-4 | CLI command `customer-mdm init-year` works correctly |
| AC-5 | Power BI strategic/existing filters functional |

---

## 6. Proposed Story 7.6-11

### Story Definition

```yaml
Story: 7.6-11
Title: Customer Status Field Enhancement
Status: pending
Goal: Implement full business logic for is_strategic, is_existing, and contract_status fields
Impact: Enables strategic customer analysis and new/existing customer segmentation
Risk: Low
Dependencies: Story 7.6-6 (completed)
Effort: 1-1.5 days
```

### Acceptance Criteria

**AC-1**: is_strategic Strategic Customer Flag
- Prior year AUM >= 5B threshold → `is_strategic = TRUE`
- Top 10 customers per branch per product line → `is_strategic = TRUE`
- Others → `is_strategic = FALSE`

**AC-2**: is_existing Existing Customer Flag
- Prior year has asset records → `is_existing = TRUE`
- Prior year no asset records → `is_existing = FALSE`

**AC-3**: Annual Initialization CLI Command
- Command: `customer-mdm init-year --year 2026`
- Updates all contracts for specified year
- Idempotent (safe to re-run)

**AC-4**: contract_status Full Logic
- AUM > 0 AND 12-month contribution > 0 → `正常`
- AUM > 0 AND 12-month contribution = 0 → `停缴`
- Data source: `business.规模明细.供款` (99.8% coverage verified)

### Tasks

- [ ] Task 1: Implement `is_strategic` logic with threshold + whitelist
- [ ] Task 2: Implement `is_existing` logic with prior year check
- [ ] Task 3: Create `init-year` CLI command
- [ ] Task 4: Update Post-ETL hook to call enhanced logic
- [ ] Task 5: Implement `contract_status` v2 logic with 12-month rolling window
- [ ] Task 6: Update documentation and tests

---

## 7. Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-03 | Initial proposal |
