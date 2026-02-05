# Sprint Change Proposal: P4 Customer Name Normalization Fix

**Date:** 2025-12-07
**Status:** Pending Approval
**Triggered By:** Epic 6 Mid-Sprint Review (Story 6.4/6.5)
**Scope Classification:** Minor (Direct implementation by dev team)

## 1. Issue Summary

### Problem Statement
During Epic 6 implementation review, a consistency gap was identified between the **Resolver lookup mechanism** and the **Backflow write mechanism** for P4 (Customer Name) priority level.

### Discovery Context
- **Trigger:** Review of `docs/specific/backflow/` documentation against actual code implementation
- **Evidence:** Code analysis of `CompanyIdResolver._resolve_via_db_cache()` and `_backflow_new_mappings()`
- **Verification:** Comparison with legacy system (`legacy/annuity_hub/data_handler/`)

### Root Cause
The original backflow documentation (`critical-issue-resolver-inconsistency.md`) suggested using normalized names for ALL priority levels. However, legacy system analysis revealed that **only P4 (Customer Name)** should use normalized values; other priorities (P1, P2, P3, P5) should use RAW values.

Current implementation uses RAW values for all priorities, causing P4 cache misses.

## 2. Impact Analysis

### Epic Impact
| Epic | Impact Level | Details |
|------|--------------|---------|
| Epic 6 (Company Enrichment) | **Direct** | Story 6.4 requires patch |
| Epic 7+ | None | No downstream impact after fix |

### Artifact Impact
| Artifact | Impact | Action Required |
|----------|--------|-----------------|
| PRD | None | No conflict with goals |
| Architecture | Documentation | Update backflow docs |
| Code | 2 methods | Modify `_resolve_via_db_cache`, `_backflow_new_mappings` |
| Tests | Addition | Add normalization consistency tests |

### Story Impact
| Story | Status | Action |
|-------|--------|--------|
| 6.4 (Multi-tier Lookup) | Done | **Patch Required** |
| 6.5 (Async Queue) | Review | No change needed |
| 6.6+ | Backlog | No impact |

## 3. Recommended Approach

### Selected Path: Direct Adjustment
- **Effort:** Low
- **Risk:** Low
- **Timeline Impact:** None (can be completed within current sprint)

### Rationale
1. Fix is localized to 2 methods in `CompanyIdResolver`
2. Uses existing `normalize_company_name` function from cleansing infrastructure
3. Maintains backward compatibility with legacy data
4. No schema changes required

## 4. Detailed Change Proposals

### Change #1: `_resolve_via_db_cache` Method

**File:** `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
**Lines:** ~437-448

**Current Behavior:** All lookup columns use RAW values
**Required Behavior:** P4 (customer_name) uses `normalize_company_name`, others use RAW

```python
# BEFORE
lookup_columns = [
    strategy.plan_code_column,
    strategy.account_number_column,
    strategy.customer_name_column,
    strategy.account_name_column,
]

alias_names: set[str] = set()
for col in lookup_columns:
    if col in df.columns:
        values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
        alias_names.update(values)

# AFTER
from work_data_hub.infrastructure.cleansing import normalize_company_name

# P4 (customer_name) needs normalization, others use RAW values
lookup_columns = [
    (strategy.plan_code_column, False),      # P1: RAW
    (strategy.account_number_column, False), # P2: RAW
    (strategy.customer_name_column, True),   # P4: NORMALIZED
    (strategy.account_name_column, False),   # P5: RAW
]

alias_names: set[str] = set()
normalized_to_original: Dict[str, List[str]] = {}

for col, needs_normalization in lookup_columns:
    if col not in df.columns:
        continue
    values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
    for v in values:
        if needs_normalization:
            normalized = normalize_company_name(v)
            if normalized:
                alias_names.add(normalized)
                if normalized not in normalized_to_original:
                    normalized_to_original[normalized] = []
                normalized_to_original[normalized].append(v)
        else:
            alias_names.add(v)
```

### Change #2: `_backflow_new_mappings` Method

**File:** `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
**Lines:** ~617-625

**Current Behavior:** All backflow fields use `str(alias_value).strip()`
**Required Behavior:** P4 (customer_name) uses `normalize_company_name`, others use RAW

```python
# BEFORE
backflow_fields = [
    (strategy.account_number_column, "account", 2),
    (strategy.customer_name_column, "name", 4),
    (strategy.account_name_column, "account_name", 5),
]

for column, match_type, priority in backflow_fields:
    # ...
    new_mappings.append({
        "alias_name": str(alias_value).strip(),
        # ...
    })

# AFTER
from work_data_hub.infrastructure.cleansing import normalize_company_name

backflow_fields = [
    (strategy.account_number_column, "account", 2, False),    # P2: RAW
    (strategy.customer_name_column, "name", 4, True),         # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False), # P5: RAW
]

for column, match_type, priority, needs_normalization in backflow_fields:
    # ...
    if needs_normalization:
        alias_name = normalize_company_name(str(alias_value))
        if not alias_name:
            continue
    else:
        alias_name = str(alias_value).strip()

    new_mappings.append({
        "alias_name": alias_name,
        # ...
    })
```

### Change #3: Update Backflow Documentation

**File:** `docs/specific/backflow/critical-issue-resolver-inconsistency.md`

Add correction section explaining that only P4 needs normalization, not all priorities.

### Change #4: No Change to Async Enqueue

**File:** `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
**Method:** `_enqueue_for_async_enrichment`

Current implementation using `normalize_for_temp_id` is **correct** for async queue deduplication.

## 5. Implementation Handoff

### Scope Classification: Minor

This change can be implemented directly by the development team without backlog reorganization.

### Responsibilities

| Role | Responsibility |
|------|----------------|
| **Dev Team** | Implement code changes, add tests |
| **Code Review** | Verify legacy parity, test coverage |

### Success Criteria

1. P4 lookup uses `normalize_company_name` before querying database
2. P4 backflow writes `normalize_company_name` result to database
3. P1, P2, P3, P5 continue using RAW values
4. All existing tests pass
5. New tests verify normalization consistency
6. Legacy parity maintained (same results as legacy system)

### Suggested Story

**Story 6.4.1: P4 Customer Name Normalization Alignment**

```markdown
## Story
As a **data engineer**,
I want **CompanyIdResolver to use normalize_company_name for P4 (Customer Name) lookup and backflow**,
So that **the self-learning cache mechanism works correctly with legacy data format**.

## Acceptance Criteria
1. `_resolve_via_db_cache` applies `normalize_company_name` to customer_name column before lookup
2. `_backflow_new_mappings` applies `normalize_company_name` to customer_name before writing
3. P1, P2, P3, P5 continue using RAW values (no normalization)
4. Unit tests verify normalization is applied correctly for P4 only
5. Integration test confirms cache hit rate improvement with normalized P4 keys

## Tasks
- [ ] Import `normalize_company_name` from cleansing infrastructure
- [ ] Modify `_resolve_via_db_cache` to normalize P4 lookup keys
- [ ] Modify `_backflow_new_mappings` to normalize P4 backflow keys
- [ ] Add unit tests for P4 normalization
- [ ] Update backflow documentation with correction
- [ ] Run validation script to confirm fix
```

## 6. References

- **Legacy Analysis:** `docs/specific/company-id/legacy-company-id-matching-logic.md`
- **Original Issue Report:** `docs/specific/backflow/critical-issue-resolver-inconsistency.md`
- **Mid-Sprint Review:** `docs/specific/backflow/epic-6-mid-sprint-review.md`
- **Backflow Intent:** `docs/specific/backflow/backflow-mechanism-intent.md`
- **Normalization Function:** `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py`

## 7. Approval

- [x] Technical Review Approved
- [x] User Approved (2025-12-07, Link)
- [x] Ready for Implementation

**Approval Date:** 2025-12-07
**Approved By:** Link

---

**Generated:** 2025-12-07
**Author:** Claude Opus 4.5 (Correct Course Workflow)
