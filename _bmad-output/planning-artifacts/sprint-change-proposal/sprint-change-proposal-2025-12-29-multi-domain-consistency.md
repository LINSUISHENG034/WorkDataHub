# Sprint Change Proposal: Multi-Domain Field Validation Consistency

> **Date:** 2025-12-29
> **Author:** Link (via Correct-Course Workflow)
> **Status:** Pending Approval
> **Scope:** Minor-to-Moderate
> **Blocking:** Epic 8 (Testing & Validation Infrastructure)

---

## 1. Issue Summary

### Problem Statement

During multi-domain ETL testing (Epic 8 preparation), a critical inconsistency was discovered between `annuity_performance` and `annuity_income` domains regarding shared field validation:

- **`annuity_income`** defines `客户名称` and `company_id` as **required fields** (`str`)
- **`annuity_performance`** defines them as **optional fields** (`Optional[str]`)

This causes `annuity_income` validation to fail when these fields contain null values, while `annuity_performance` processes the same data successfully.

### Discovery Context

- **Trigger:** Multi-domain ETL testing during Epic 8 preparation
- **Discovery Date:** 2025-12-28
- **Evidence Document:** `docs/specific/multi-domain/shared-field-validators-analysis.md`

### Critical Issues Identified

| Issue ID | Severity | Field | Description |
|----------|----------|-------|-------------|
| CN-001 | **Critical** | `客户名称` | `annuity_income` rejects null values, should allow null |
| CI-001 | **Critical** | `company_id` | `annuity_income` requires field, should be `Optional` |
| DR-001 | **Critical** | `客户名称` | Domain Registry has `nullable=False`, should be `True` |

### Additional Issues (Lower Priority)

| Issue ID | Severity | Description |
|----------|----------|-------------|
| DR-002 | Medium | `gold_required` includes `客户名称`, should be removed |
| PC-002 | Medium | Null handling differs in gold validators |
| CN-002 | Medium | Duplicate `apply_domain_rules()` function (~9 LOC × 2) |
| CN-003 | Medium | Duplicate `DEFAULT_COMPANY_RULES` constant |
| CI-002 | Medium | Duplicate validator logic |
| PC-001 | Low | Different validator names for same logic |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| Epic 7.2 | ✅ None | Already completed |
| **Epic 8** | ⚠️ **Blocked** | Multi-domain testing cannot proceed until fixed |
| Epic 9+ | ✅ Indirect benefit | Shared validators pattern simplifies future domain development |

### Story Impact

| Affected Story | Impact Type | Description |
|----------------|-------------|-------------|
| 8-1 Golden Dataset Extraction | ⚠️ Blocked | Cannot extract complete dataset if `annuity_income` validation fails |
| 8-2 Automated Reconciliation | ⚠️ Blocked | Requires both domains to run successfully |

### Artifact Conflicts

| Artifact | Change Type | Description |
|----------|-------------|-------------|
| `infrastructure/cleansing/validators.py` | **CREATE** | New shared validators module |
| `infrastructure/cleansing/__init__.py` | MODIFY | Export new validators |
| `infrastructure/schema/definitions/annuity_income.py` | MODIFY | `客户名称` → `nullable=True` |
| `domain/annuity_income/models.py` | MODIFY | `客户名称`/`company_id` → `Optional[str]` |
| `docs/architecture/infrastructure-layer.md` | MODIFY | Document shared validators |
| `docs/sprint-artifacts/sprint-status.yaml` | MODIFY | Add Epic 7.3 |

### Technical Impact

- **Code Changes:** ~6 files modified, ~120 LOC refactored
- **Database:** No schema changes required (Pydantic-only change)
- **Deployment:** No deployment changes
- **Backward Compatibility:** ✅ Yes - relaxing constraints, not tightening

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

Create **Epic 7.3: Multi-Domain Consistency Fixes** with targeted stories.

### Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | 🟢 Low (2-4h P0, 4-6h total) |
| Timeline Impact | 🟢 Minimal (completable before Epic 8) |
| Technical Risk | 🟢 Low (backward-compatible changes) |
| Team Impact | 🟢 None (code quality improvement) |
| Long-term Sustainability | 🟢 Improved (reduces duplication, establishes shared pattern) |

### Alternatives Considered

| Alternative | Why Not Selected |
|-------------|------------------|
| Rollback | Problem is design inconsistency, not implementation error |
| MVP Review | MVP already complete, this is post-MVP improvement |
| Merge into Epic 8 | Would blur Epic 8's focus on testing infrastructure |
| Epic 7.1 Patch | Epic 7.1 already marked complete |

### Effort Estimate

| Priority | Effort | Risk |
|----------|--------|------|
| P0 (Critical fixes) | 2 hours | Low |
| P1 (Shared validators) | 4 hours | Low |
| P2 (Naming consistency) | 1 hour | Low |
| **Total** | **7 hours** | **Low** |

---

## 4. Detailed Change Proposals

### Story 7.3-1: Fix `annuity_income` Null Handling (P0 - Critical)

**Objective:** Align `annuity_income` field nullability with `annuity_performance`

#### Change 1: Domain Registry

**File:** `infrastructure/schema/definitions/annuity_income.py`

```
OLD:
ColumnDef("客户名称", ColumnType.STRING, nullable=False, max_length=255),

NEW:
ColumnDef("客户名称", ColumnType.STRING, nullable=True, max_length=255),
```

**Rationale:** Align with `annuity_performance` which allows null customer names

#### Change 2: Pydantic Gold Model - 客户名称

**File:** `domain/annuity_income/models.py`

```
OLD:
客户名称: str = Field(..., max_length=255, description="Customer name (normalized)")

NEW:
客户名称: Optional[str] = Field(None, max_length=255, description="Customer name (normalized)")
```

#### Change 3: Pydantic Gold Model - company_id

**File:** `domain/annuity_income/models.py`

```
OLD:
company_id: str = Field(
    ...,  # Required
    min_length=1,
    max_length=50,
    description="Company identifier - generated during data cleansing",
)

NEW:
company_id: Optional[str] = Field(
    None,
    min_length=1,
    max_length=50,
    description="Company identifier - generated during data cleansing",
)
```

#### Change 4: Validator Null Check

**File:** `domain/annuity_income/models.py`

```
OLD:
@field_validator("客户名称", mode="before")
@classmethod
def clean_customer_name(cls, v: Any, info: ValidationInfo) -> str:
    # No null check
    ...

NEW:
@field_validator("客户名称", mode="before")
@classmethod
def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
    if v is None:
        return v  # Allow null
    ...
```

**Acceptance Criteria:**
- [ ] AC1: `annuity_income` Gold model accepts null `客户名称`
- [ ] AC2: `annuity_income` Gold model accepts null `company_id`
- [ ] AC3: Domain Registry `annuity_income.客户名称` is `nullable=True`
- [ ] AC4: Multi-domain ETL test passes with mixed null/non-null data
- [ ] AC5: All existing tests pass

---

### Story 7.3-2: Extract Shared Validators to Infrastructure (P1)

**Objective:** Eliminate code duplication by creating shared validators

#### New File: `infrastructure/cleansing/validators.py`

```python
"""
Shared Pydantic validators for domain models.

Extracts common validation patterns to eliminate duplication
across annuity_performance, annuity_income, and future domains.
"""
from typing import Any, Optional
from pydantic import ValidationInfo

from work_data_hub.infrastructure.cleansing import get_cleansing_registry

# Shared Constants
DEFAULT_COMPANY_RULES = ["trim_whitespace", "normalize_company_name"]
DEFAULT_NUMERIC_RULES = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
]
MIN_YYYYMM_VALUE = 200000
MAX_YYYYMM_VALUE = 999999
MAX_DATE_RANGE_DAYS = 3650


def clean_code_field(v: Any) -> Optional[str]:
    """Bronze layer code field cleaner."""
    if v is None:
        return None
    s_val = str(v).strip()
    return s_val if s_val else None


def normalize_plan_code(v: Optional[str], allow_null: bool = True) -> Optional[str]:
    """Gold layer plan code normalizer."""
    if v is None:
        return v if allow_null else None
    normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
        raise ValueError(f"Plan code cannot be empty after normalization: {v}")
    return normalized


def normalize_company_id(v: Optional[str], allow_null: bool = True) -> Optional[str]:
    """Gold layer company_id normalizer."""
    if v is None:
        return v if allow_null else None
    normalized = v.upper()
    if not normalized.strip():
        raise ValueError(f"company_id cannot be empty: {v}")
    return normalized


def clean_customer_name(
    v: Any,
    info: ValidationInfo,
    domain: str,
    allow_null: bool = True,
) -> Optional[str]:
    """Gold layer customer name cleaner with domain rules."""
    if v is None:
        return v if allow_null else None
    field_name = info.field_name or "客户名称"
    registry = get_cleansing_registry()
    rules = registry.get_domain_rules(domain, field_name)
    if not rules:
        rules = DEFAULT_COMPANY_RULES
    return registry.apply_rules(v, rules, field_name=field_name)
```

**Acceptance Criteria:**
- [ ] AC1: `validators.py` created with shared functions
- [ ] AC2: `annuity_performance/models.py` imports from shared module
- [ ] AC3: `annuity_income/models.py` imports from shared module
- [ ] AC4: ~120 LOC duplication eliminated
- [ ] AC5: All existing tests pass
- [ ] AC6: Unit tests added for shared validators

---

### Story 7.3-3: Unify Validator Naming Conventions (P2 - Optional)

**Objective:** Standardize validator function names across domains

| Current (Inconsistent) | Proposed (Unified) |
|------------------------|-------------------|
| `normalize_codes` (annuity_performance) | `normalize_plan_code` |
| `normalize_plan_code` (annuity_income) | `normalize_plan_code` |
| `clean_code_fields` (both) | `clean_code_field` |

**Acceptance Criteria:**
- [ ] AC1: Validator names consistent across domains
- [ ] AC2: Documentation updated

---

## 5. Implementation Handoff

### Scope Classification: 🟡 Minor-to-Moderate

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement Stories 7.3-1 and 7.3-2 |
| **SM (Scrum Master)** | Update sprint-status.yaml, create Story files |
| **Code Reviewer** | Review PRs, ensure architecture compliance |

### Implementation Sequence

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: P0 Critical Fixes (Story 7.3-1) - BLOCKS Epic 8   │
│  ├── Modify Domain Registry                                  │
│  ├── Modify Pydantic Models                                  │
│  ├── Add null checks to validators                           │
│  └── Verify: Multi-domain test passes                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: P1 Shared Validators (Story 7.3-2) - Parallel OK   │
│  ├── Create validators.py                                    │
│  ├── Refactor domain models to use shared validators         │
│  └── Verify: All tests pass                                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: P2 Consistency (Story 7.3-3) - Can Defer           │
│  ├── Rename validators for consistency                       │
│  └── Update documentation                                    │
└─────────────────────────────────────────────────────────────┘
```

### Success Criteria

1. ✅ `annuity_income` domain processes data with null `客户名称`/`company_id`
2. ✅ Multi-domain ETL test completes successfully
3. ✅ All 2000+ existing tests pass
4. ✅ Code duplication reduced by ~120 LOC (after P1)
5. ✅ No regression in `annuity_performance` domain

### Timeline

| Milestone | Target |
|-----------|--------|
| Story 7.3-1 Complete | Before Epic 8 starts |
| Story 7.3-2 Complete | Can parallel with Epic 8 |
| Story 7.3-3 Complete | Optional, low priority |

---

## 6. Approval

- [ ] **Link (Product Owner):** Approve scope and priority
- [ ] **Dev Team:** Confirm effort estimates
- [ ] **Code Reviewer:** Acknowledge review responsibility

---

## References

- [Shared Field Validators Analysis](../../specific/multi-domain/shared-field-validators-analysis.md)
- [Infrastructure Layer Documentation](../../architecture/infrastructure-layer.md)
- [Epic 7.1 Pre-Epic 8 Fixes](sprint-change-proposal-2025-12-23-epic-7.1-pre-epic8-fixes.md)

---

_Generated by Correct-Course Workflow on 2025-12-29_
