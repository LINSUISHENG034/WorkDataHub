# Sprint Change Proposal: Annuity Income Pipeline Processing Gap

> **Date:** 2025-12-29
> **Author:** Link (via Correct-Course Workflow)
> **Status:** ✅ Approved (2025-12-29)
> **Scope:** Minor
> **Blocking:** Epic 8 (Testing & Validation Infrastructure)

---

## 1. Issue Summary

### Problem Statement

During post-ETL data verification for period `202510`, **four processing inconsistencies** were discovered between `annuity_performance` and `annuity_income` domains at the **pipeline processing layer** (not model layer):

| Issue | Severity | Impact |
|-------|----------|--------|
| `company_id` lacks multi-priority matching | **Critical** | All `annuity_income` records have temporary IDs only |
| `客户名称` incorrectly filled from `计划名称` | **High** | Produces redundant/incorrect customer name data |
| `计划代码` missing corrections and defaults | **Medium** | Inconsistent plan code processing |
| `组合代码` processing logic differs | **Low** | Minor inconsistencies (document only) |

### Discovery Context

- **Trigger:** ETL execution with `--all-domains --period 202510 --execute --no-enrichment`
- **Discovery Date:** 2025-12-29
- **Evidence Document:** `docs/specific/multi-domain/annuity-income-processing-gap-analysis.md`

### Relationship to Epic 7.3

| Layer | Epic 7.3 (Stories 7.3-1 to 7.3-5) | New Discovery (Story 7.3-6) |
|-------|-----------------------------------|----------------------------|
| **Pydantic Model** | ✅ Fixed nullability of `客户名称`/`company_id` | N/A |
| **Domain Registry** | ✅ Fixed `nullable=True` for `客户名称` | N/A |
| **Pipeline Processing** | Not addressed | ❌ **Gap discovered** |

**Key Distinction:** Epic 7.3 fixed the **type declarations**, but the **runtime processing logic** in `pipeline_builder.py` still differs between domains.

### Critical Evidence

**SQL Verification Results (Period 202510):**

```sql
-- annuity_performance: Mixed company_ids (cached + temporary)
SELECT COUNT(*) FROM "business"."规模明细" WHERE "月度" = '2025-10-01';
-- Result: 37,121 rows, 7 null customer names, 0 null company_ids

-- annuity_income: ALL temporary IDs (no cached lookups)
SELECT COUNT(*) FROM "business"."收入明细" WHERE "月度" = '2025-10-01';
-- Result: 13,639 rows, 0 null customer names (all filled with plan names!)
```

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| Epic 7.3 | ⚠️ **Reopen** | Add Story 7.3-6 to address pipeline layer gaps |
| **Epic 8** | ⚠️ **Blocked** | Cannot proceed with multi-domain testing until fixed |
| Epic 9+ | ✅ Indirect benefit | Establishes consistent pattern for future domains |

### Story Impact

| Story | Impact | Description |
|-------|--------|-------------|
| 8-1 Golden Dataset Extraction | ⚠️ Blocked | Inconsistent data cannot be used as golden baseline |
| 8-2 Automated Reconciliation | ⚠️ Blocked | Requires consistent processing across domains |

### Artifact Conflicts

| Artifact | Change Type | Lines Changed |
|----------|-------------|---------------|
| `domain/annuity_income/service.py` | MODIFY | +15 |
| `domain/annuity_income/pipeline_builder.py` | MODIFY | +30 (fix + additions) |
| `domain/annuity_income/constants.py` | MODIFY | +2 |
| `tests/domain/annuity_income/` | MODIFY | ~30 |

### Technical Impact

- **Code Changes:** 4 files modified, ~77 LOC changes
- **Database:** No schema changes required
- **Backward Compatibility:** ✅ Yes - all changes are additive/relaxing

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

Add **Story 7.3-6: Annuity Income Pipeline Processing Alignment** to Epic 7.3.

### Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | 🟢 Low (3-4 hours) |
| Timeline Impact | 🟢 Minimal (completable before Epic 8) |
| Technical Risk | 🟢 Low (additive changes, no breaking changes) |
| Team Impact | 🟢 None |
| Long-term Value | 🟢 High (establishes consistent multi-domain pattern) |

### Alternatives Considered

| Alternative | Why Not Selected |
|-------------|------------------|
| Merge into Epic 8 | Would blur Epic 8's focus on testing infrastructure |
| Create new Epic 7.4 | Overkill for 1 story, Epic 7.3 scope already covers this |
| Defer to post-Epic 8 | Would propagate data inconsistencies into test baseline |

### Effort Estimate

| Priority | Item | Effort | Risk |
|----------|------|--------|------|
| **Critical** | Add `CompanyMappingRepository` to service.py | 0.5h | Low |
| **Critical** | Add `mapping_repository` param to pipeline_builder.py | 0.5h | Low |
| **High** | Fix `_fill_customer_name` to preserve nulls | 0.5h | Low |
| **Medium** | Add `PLAN_CODE_CORRECTIONS/DEFAULTS` | 0.5h | Low |
| **Medium** | Add plan code processing steps | 1h | Low |
| **Required** | Update tests | 1h | Low |
| **Total** | | **4 hours** | **Low** |

---

## 4. Detailed Change Proposals

### Story 7.3-6: Annuity Income Pipeline Processing Alignment

**Objective:** Align `annuity_income` pipeline processing with `annuity_performance` to ensure consistent data output.

---

#### Change 1: Add `CompanyMappingRepository` to `service.py` (Critical)

**File:** `src/work_data_hub/domain/annuity_income/service.py`

```
OLD (Lines ~253-258):
plan_overrides = load_plan_override_mapping()
pipeline = build_bronze_to_silver_pipeline(
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
    # ❌ Missing: mapping_repository parameter!
)

NEW:
# Initialize CompanyMappingRepository for database cache lookup
mapping_repository: Optional[CompanyMappingRepository] = None
repo_connection = None
try:
    from sqlalchemy import create_engine
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())
    repo_connection = engine.connect()
    mapping_repository = CompanyMappingRepository(repo_connection)
except Exception as e:
    logger.bind(domain="annuity_income", step="mapping_repository").warning(
        "Failed to initialize CompanyMappingRepository; proceeding without DB cache",
        error=str(e),
    )
    mapping_repository = None
    repo_connection = None

plan_overrides = load_plan_override_mapping()
pipeline = build_bronze_to_silver_pipeline(
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
    mapping_repository=mapping_repository,  # ✅ NEW!
)
```

**Rationale:** Enable database cache lookup for company_id resolution, matching `annuity_performance` behavior.

---

#### Change 2: Add `mapping_repository` Parameter to `pipeline_builder.py` (Critical)

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`

```
OLD (CompanyIdResolutionStep.__init__, Lines ~95-126):
def __init__(
    self,
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
    # ❌ Missing: mapping_repository parameter!
) -> None:

NEW:
def __init__(
    self,
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,  # ✅ NEW!
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
) -> None:
    self._resolver = CompanyIdResolver(
        eqc_config=eqc_config,
        enrichment_service=enrichment_service,
        yaml_overrides=yaml_overrides,
        mapping_repository=mapping_repository,  # ✅ NEW!
    )
```

```
OLD (build_bronze_to_silver_pipeline, Lines ~161-167):
def build_bronze_to_silver_pipeline(
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
    # ❌ Missing: mapping_repository parameter!
) -> Pipeline:

NEW:
def build_bronze_to_silver_pipeline(
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,  # ✅ NEW!
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
) -> Pipeline:
```

**Rationale:** Pass `mapping_repository` through the pipeline builder to `CompanyIdResolver`.

---

#### Change 3: Fix `_fill_customer_name` to Preserve Nulls (High)

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`

```
OLD (Lines 41-51):
def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Fallback customer name to 计划名称, then UNKNOWN."""
    if "客户名称" in df.columns:
        base = df["客户名称"]
    else:
        base = pd.Series([pd.NA] * len(df), index=df.index)

    plan_names = df.get("计划名称", pd.Series([pd.NA] * len(df), index=df.index))
    base = base.combine_first(plan_names)  # ❌ WRONG: Uses plan name as fallback!

    return base.fillna("UNKNOWN")  # ❌ WRONG: Then fills with "UNKNOWN"!

NEW:
def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Keep customer name as-is, allow null (consistent with annuity_performance).

    Story 7.3-6: Removed plan name fallback to match annuity_performance behavior.
    """
    if "客户名称" in df.columns:
        return df["客户名称"]  # ✅ Keep as-is, including nulls
    else:
        return pd.Series([pd.NA] * len(df), index=df.index)
```

**Rationale:** Match `annuity_performance` behavior which preserves null customer names.

---

#### Change 4: Add Plan Code Configurations to `constants.py` (Medium)

**File:** `src/work_data_hub/domain/annuity_income/constants.py`

```
NEW (Add to constants.py):
# Plan code corrections (typo fixes)
PLAN_CODE_CORRECTIONS: Dict[str, str] = {"1P0290": "P0290", "1P0807": "P0807"}

# Plan code defaults (for empty values based on plan type)
PLAN_CODE_DEFAULTS: Dict[str, str] = {"集合计划": "AN001", "单一计划": "AN002"}
```

**Rationale:** Align with `annuity_performance/constants.py` definitions.

---

#### Change 5: Add Plan Code Processing Steps (Medium)

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`

```
NEW (Add after MappingStep):
from work_data_hub.infrastructure.transforms import ReplacementStep
from .constants import PLAN_CODE_CORRECTIONS, PLAN_CODE_DEFAULTS

# Step: Apply plan code corrections
ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),

# Step: Apply plan code defaults
def _apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (consistent with annuity_performance)."""
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, "AN001")
        result = result.mask(single_mask, "AN002")

    return result

# Add to pipeline:
CalculationStep({"计划代码": _apply_plan_code_defaults}),
```

**Rationale:** Align plan code processing with `annuity_performance` domain.

---

### Acceptance Criteria

**Critical (Must Fix):**
- [ ] AC1: `annuity_income` `company_id` resolution uses database cache lookup
- [ ] AC2: `annuity_income` `客户名称` preserves null values (no plan name fallback)
- [ ] AC3: After re-running ETL, `annuity_income` has mix of cached IDs and temp IDs

**High (Should Fix):**
- [ ] AC4: `annuity_income` applies `PLAN_CODE_CORRECTIONS` mapping
- [ ] AC5: `annuity_income` applies `PLAN_CODE_DEFAULTS` for empty plan codes

**General:**
- [ ] AC6: All existing tests pass
- [ ] AC7: New unit tests verify consistent behavior between domains

---

## 5. Implementation Handoff

### Scope Classification: 🟢 Minor

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement Story 7.3-6 |
| **SM (Scrum Master)** | Update sprint-status.yaml |
| **Code Reviewer** | Review PR, ensure architecture compliance |

### Implementation Sequence

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Add CompanyMappingRepository (Critical)            │
│  ├── Modify service.py                                      │
│  ├── Modify pipeline_builder.py                             │
│  └── Verify: company_id has mixed cached/temp IDs           │
├─────────────────────────────────────────────────────────────┤
│  Step 2: Fix _fill_customer_name (High)                     │
│  ├── Remove plan name fallback logic                        │
│  └── Verify: null 客户名称 preserved                         │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Add Plan Code Processing (Medium)                  │
│  ├── Add constants to constants.py                          │
│  ├── Add ReplacementStep and CalculationStep                │
│  └── Verify: Plan codes corrected and defaulted             │
├─────────────────────────────────────────────────────────────┤
│  Step 4: Update Tests                                       │
│  └── Add/update tests for new behavior                      │
└─────────────────────────────────────────────────────────────┘
```

### Success Criteria

1. ✅ `annuity_income` `company_id` shows mixed cached/temp IDs (not all temp)
2. ✅ `annuity_income` `客户名称` allows null (no plan name fallback)
3. ✅ Multi-domain ETL test completes successfully
4. ✅ All existing tests pass
5. ✅ No regression in `annuity_performance` domain

---

## 6. Approval

- [x] **Link (Product Owner):** Approve scope and priority ✅ 2025-12-29
- [ ] **Dev Team:** Confirm effort estimates
- [ ] **Code Reviewer:** Acknowledge review responsibility

---

## References

- [Annuity Income Processing Gap Analysis](../../specific/multi-domain/annuity-income-processing-gap-analysis.md)
- [Multi-Domain Field Validation Consistency (Epic 7.3 Original)](sprint-change-proposal-2025-12-29-multi-domain-consistency.md)
- [Infrastructure Layer Documentation](../../architecture/infrastructure-layer.md)
- [Shared Validators Source](../../../src/work_data_hub/infrastructure/cleansing/validators.py)

---

_Generated by Correct-Course Workflow on 2025-12-29_
