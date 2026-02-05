# Sprint Change Proposal: Epic 5 Migration Cleanup

**Date:** 2025-12-04
**Author:** SM Agent (Correct-Course Workflow)
**Status:** Ready for Review
**Epic:** Epic 5 (Infrastructure Layer Architecture)
**Topic:** Post-Implementation Cleanup and Domain Structure Standardization
**Workflow:** Correct-Course

---

## 1. Issue Summary

### Trigger
Epic 5 gap analysis report (`docs/sprint-artifacts/auxiliary/epic-5-migration-gap-analysis.md`) revealed significant discrepancies between the original proposal targets and actual implementation state after Stories 5.1-5.8 were marked as complete.

### Problem Statement
While Epic 5 infrastructure layer has been successfully established and is functional, the domain layer cleanup was not fully executed:

| Metric | Proposal Target | Actual (2025-12-04) | Gap |
|--------|-----------------|---------------------|-----|
| **Domain Total Lines** | <500 | 2,683 | 436% over |
| **Domain File Count** | 4 files | 9 files | 5 extra files |
| **service.py** | <150 | 171 | ✅ ~14% over (acceptable) |
| **models.py** | <200 | 648 | 224% over |
| **schemas.py** | <100 | 611 | 511% over |
| **pipeline_steps.py** | DELETE | 468 | Not deleted |

### Evidence
**Current Domain Structure (9 files):**
```
domain/annuity_performance/
├── __init__.py              40 lines
├── constants.py            192 lines  ✅ OK
├── discovery_helpers.py     97 lines  ⚠️ Unplanned
├── models.py               648 lines  ❌ Target <200
├── pipeline_builder.py     284 lines  ⚠️ Unplanned
├── pipeline_steps.py       468 lines  ❌ Should be deleted/migrated
├── processing_helpers.py   172 lines  ⚠️ Unplanned
├── schemas.py              611 lines  ❌ Target <100
└── service.py              171 lines  ✅ ~OK

Total: 2,683 lines (Target: <500)
```

### Root Cause
1. **Incomplete cleanup**: New infrastructure components created, but old implementations not removed
2. **Duplicate code**: `CompanyIdResolutionStep` exists in both `pipeline_steps.py` (old) and `pipeline_builder.py` (new)
3. **Validation/projection steps not migrated**: `BronzeSchemaValidationStep`, `GoldProjectionStep`, `GoldSchemaValidationStep` remain in domain
4. **Helper functions not extracted**: Cleansing/date/numeric helpers still embedded in `schemas.py` and `models.py`
5. **File proliferation**: Helper files created during refactoring but not consolidated
6. **Aggressive targets not re-evaluated**: Original line count targets may have been too aggressive given business field complexity

---

## 2. Impact Analysis

| Area | Impact | Severity |
|------|--------|----------|
| **Epic 5 Completion** | Stories marked done but targets not met | Medium |
| **Epic 9 (Growth Domains)** | Pattern not fully replicable - still partially blocked | High |
| **Technical Debt** | Duplicate code increases maintenance burden | Medium |
| **Architecture Compliance** | Partial - infrastructure established but domain not lightweight | Medium |
| **Functionality** | None - system works correctly | None |

### Affected Components

**Direct Impact:**
- `domain/annuity_performance/pipeline_steps.py` - Needs cleanup/deletion
- `domain/annuity_performance/models.py` - Needs simplification
- `domain/annuity_performance/schemas.py` - Needs helper extraction
- `infrastructure/validation/` - Needs schema steps migration
- `infrastructure/transforms/` - Needs projection step migration

**No Impact:**
- `infrastructure/` layer - Already correctly established
- `service.py` - Already lightweight orchestrator
- Dagster jobs - Continue working
- Test suite - All passing

---

## 3. Recommended Approach

### Strategy: Direct Adjustment - Add Cleanup Story (方案 B: 务实 6 文件)

**Selected Structure:** Pragmatic 6-file standard for each domain

**Target Domain Structure:**
```
domain/annuity_performance/
├── __init__.py          # Module exports
├── service.py           # <200 lines - Lightweight orchestration
├── models.py            # <400 lines - Pydantic models
├── schemas.py           # <250 lines - Pandera schemas only
├── constants.py         # ~200 lines - Business constants
├── pipeline_builder.py  # <150 lines - Pipeline assembly
└── helpers.py           # <150 lines - Domain-specific helpers
```

**Rationale:**
1. **Clean Architecture compliance**: `helpers.py` contains `FileDiscoveryProtocol` for TID251 boundary
2. **Lightweight service**: Keeps `service.py` under 200 lines (not bloated by merging)
3. **Separation of concerns**: Pipeline assembly separate from orchestration
4. **Replicable pattern**: Clear template for Epic 9 domain migrations
5. **Infrastructure foundation is solid**: No architectural changes needed

### Expected Outcomes

**Quantitative (Revised Targets):**
- Domain file count: 9 → 7 files (including `__init__.py`)
- Domain layer: 2,683 → ~1,100 lines (-59%)
- `service.py`: 171 → <200 lines (keep lightweight)
- `models.py`: 648 → <400 lines
- `schemas.py`: 611 → <250 lines
- `pipeline_builder.py`: 284 → <150 lines
- `helpers.py`: NEW ~150 lines (merged from discovery + processing)
- `pipeline_steps.py`: 468 → 0 lines (DELETED)

**Qualitative:**
- ✅ Duplicate code eliminated
- ✅ Validation/projection steps in infrastructure
- ✅ Helper functions properly located
- ✅ Epic 9 fully unblocked

---

## 4. Detailed Change Proposals

### 4.1 Consolidate Helper Files → `helpers.py`

**Action:** Merge `discovery_helpers.py` + `processing_helpers.py` → `helpers.py`

**Current State:**
- `discovery_helpers.py` (97 lines): `FileDiscoveryProtocol`, `run_discovery`, `normalize_month`
- `processing_helpers.py` (172 lines): `convert_dataframe_to_models`, `export_unknown_names_csv`, `summarize_enrichment`, `parse_report_period`, `parse_report_date`

**Target:** `helpers.py` (<150 lines)

```python
# domain/annuity_performance/helpers.py
"""Domain-specific helpers for annuity performance processing."""

# From discovery_helpers.py
class FileDiscoveryProtocol(Protocol):
    """Protocol for file discovery service (Clean Architecture boundary)."""
    ...

def run_discovery(...) -> Any: ...
def normalize_month(month: str) -> str: ...

# From processing_helpers.py
def convert_dataframe_to_models(df: pd.DataFrame) -> Tuple[List, List]: ...
def export_unknown_names_csv(...) -> Optional[str]: ...
def summarize_enrichment(...) -> EnrichmentStats: ...
```

**Note:** `parse_report_period` and `parse_report_date` move to `utils/date_parser.py`

**Files to Delete:**
- `discovery_helpers.py`
- `processing_helpers.py`

---

### 4.2 Delete Duplicate/Obsolete Code from `pipeline_steps.py`

**File:** `domain/annuity_performance/pipeline_steps.py` (468 lines)

**Action:** Delete or migrate:

| Symbol | Lines | Action | Rationale |
|--------|-------|--------|-----------|
| `CompanyIdResolutionStep` (old) | 126 | DELETE | Replaced by `pipeline_builder.py` version |
| `build_annuity_pipeline` | ~50 | DELETE | No longer called |
| `load_mappings_from_json_fixture` | ~20 | DELETE | No longer called |
| `BronzeSchemaValidationStep` | 27 | MIGRATE → `infrastructure/validation/schema_steps.py` |
| `GoldProjectionStep` | 99 | MIGRATE → `infrastructure/transforms/projection_step.py` |
| `GoldSchemaValidationStep` | ~30 | MIGRATE → `infrastructure/validation/schema_steps.py` |

**Expected Result:** File DELETED (0 lines)

---

### 4.3 Migrate Validation/Projection Steps to Infrastructure

**NEW FILE:** `infrastructure/validation/schema_steps.py`

```python
"""Pandera schema validation pipeline steps."""
from work_data_hub.infrastructure.transforms.base import TransformStep

class BronzeSchemaValidationStep(TransformStep):
    """Bronze layer Pandera schema validation step."""
    ...

class GoldSchemaValidationStep(TransformStep):
    """Gold layer Pandera schema validation step."""
    ...
```

**NEW FILE:** `infrastructure/transforms/projection_step.py`

```python
"""DataFrame projection pipeline steps."""
from work_data_hub.infrastructure.transforms.base import TransformStep

class ProjectionStep(TransformStep):
    """Project DataFrame to specified columns."""
    ...
```

**Update References:**
- `schemas.py` imports from `infrastructure/validation/schema_steps`
- `pipeline_builder.py` imports from `infrastructure/transforms/projection_step`

---

### 4.4 Slim Down `pipeline_builder.py`

**Current:** 284 lines
**Target:** <150 lines

**Actions:**
1. Remove any duplicate logic already in infrastructure
2. Keep only pipeline assembly code
3. Use infrastructure steps directly

---

### 4.5 Extract Helper Functions from `schemas.py`

**Current:** 611 lines
**Target:** <250 lines

**Helpers to Extract:**

| Function | Target Location |
|----------|-----------------|
| `_clean_numeric_for_schema` | `infrastructure/cleansing/rules/numeric_rules.py` |
| `_coerce_numeric_columns` | `infrastructure/transforms/standard_steps.py` |
| `_parse_bronze_dates` | `utils/date_parser.py` |

**Keep in `schemas.py`:**
- `BronzeAnnuitySchema` (Pandera schema)
- `GoldAnnuitySchema` (Pandera schema)
- `BronzeValidationSummary`, `GoldValidationSummary` (dataclasses)
- `validate_bronze_dataframe`, `validate_gold_dataframe` (thin wrappers)

---

### 4.6 Simplify `models.py`

**Current:** 648 lines
**Target:** <400 lines

**Actions:**
1. Move `@field_validator` cleansing logic to Pandera + infra cleansing
2. Keep Pydantic models for type definitions and serialization only
3. Remove inline business/cleansing logic

---

### 4.7 Consolidate Date Parsing to `utils/date_parser.py`

**Current Locations:**
- `processing_helpers.py`: `parse_report_period`, `parse_report_date`
- `schemas.py`: `_parse_bronze_dates`

**Action:** Move all to `utils/date_parser.py` (already exists, extend it)

---

### 4.8 Update Documentation

**Files to Update:**

1. **`docs/architecture/infrastructure-layer.md`**
   - Update line counts and structure
   - Document 6-file domain standard

2. **`docs/domains/annuity_performance.md`**
   - Reflect final 6-file structure

3. **`docs/epics/epic-5-infrastructure-layer.md`**
   - Add Story 5.9
   - Update success metrics

4. **`docs/migration-guide.md`**
   - Document 6-file domain template for Epic 9

---

## 5. Story Proposal: Story 5.9 - Epic 5 Migration Cleanup (6-File Standard)

### User Story

As a **developer**,
I want to **complete the Epic 5 migration cleanup by consolidating to the 6-file domain standard**,
So that **the domain layer is lightweight, well-organized, and provides a replicable template for Epic 9**.

### Acceptance Criteria

**Given** Epic 5 Stories 5.1-5.8 are complete but cleanup is incomplete
**When** cleanup is performed
**Then**:

1. **Domain Structure Matches 6-File Standard:**
   ```
   domain/annuity_performance/
   ├── __init__.py          # Module exports
   ├── service.py           # <200 lines
   ├── models.py            # <400 lines
   ├── schemas.py           # <250 lines
   ├── constants.py         # ~200 lines
   ├── pipeline_builder.py  # <150 lines
   └── helpers.py           # <150 lines (NEW - merged)
   ```

2. **Helper Files Consolidated:**
   - `helpers.py` created by merging `discovery_helpers.py` + `processing_helpers.py`
   - `discovery_helpers.py` DELETED
   - `processing_helpers.py` DELETED
   - `FileDiscoveryProtocol` preserved in `helpers.py` (Clean Architecture boundary)

3. **Obsolete Code Removed:**
   - `pipeline_steps.py` DELETED (468 lines removed)
   - Old `CompanyIdResolutionStep` removed
   - `build_annuity_pipeline` and `load_mappings_from_json_fixture` removed

4. **Validation/Projection Steps Migrated to Infrastructure:**
   - `BronzeSchemaValidationStep` → `infrastructure/validation/schema_steps.py`
   - `GoldSchemaValidationStep` → `infrastructure/validation/schema_steps.py`
   - `GoldProjectionStep` → `infrastructure/transforms/projection_step.py`
   - All references updated to new locations

5. **Helper Functions Extracted:**
   - `_clean_numeric_for_schema` → `infrastructure/cleansing/rules/numeric_rules.py`
   - `_coerce_numeric_columns` → `infrastructure/transforms/standard_steps.py`
   - `_parse_bronze_dates`, `parse_report_period`, `parse_report_date` → `utils/date_parser.py`

6. **Line Count Targets Met:**
   | File | Current | Target |
   |------|---------|--------|
   | `service.py` | 171 | <200 ✅ |
   | `models.py` | 648 | <400 |
   | `schemas.py` | 611 | <250 |
   | `pipeline_builder.py` | 284 | <150 |
   | `helpers.py` | NEW | <150 |
   | `constants.py` | 192 | ~200 ✅ |
   | `pipeline_steps.py` | 468 | 0 (DELETED) |
   | **Domain Total** | 2,683 | <1,100 |

7. **All Tests Pass:**
   - Unit tests updated for new file locations
   - Integration tests pass
   - Parity tests pass (output identical to pre-cleanup)

8. **Documentation Updated:**
   - `docs/architecture/infrastructure-layer.md` - 6-file standard documented
   - `docs/domains/annuity_performance.md` - Final structure
   - `docs/migration-guide.md` - Epic 9 domain template

### Technical Tasks

1. Create `helpers.py` by merging `discovery_helpers.py` + `processing_helpers.py`
2. Delete `discovery_helpers.py` and `processing_helpers.py`
3. Update `service.py` imports to use `helpers.py`
4. Delete obsolete code from `pipeline_steps.py`
5. Create `infrastructure/validation/schema_steps.py` with migrated steps
6. Create `infrastructure/transforms/projection_step.py` with migrated step
7. Delete `pipeline_steps.py`
8. Extract helpers from `schemas.py` to infrastructure/utils
9. Slim down `pipeline_builder.py` to <150 lines
10. Simplify `models.py` validators to <400 lines
11. Update all import references across codebase
12. Update tests for new file structure
13. Update documentation

### Estimated Effort
2 - 2.5 days

### Priority
P1 (Important - blocks Epic 9 full enablement)

### Dependencies
- Stories 5.1-5.8 complete (✅)

---

## 6. Implementation Handoff

### Scope Classification
**Minor to Moderate** - Cleanup and refactoring within existing architecture. No new architectural decisions required.

### Route To
- **Primary:** Development Team (Implementation)
- **Support:** SM (Story tracking)

### Success Criteria

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Domain file count | 9 | 7 | File count |
| Domain total lines | 2,683 | <1,100 | `wc -l` |
| `service.py` | 171 | <200 | `wc -l` |
| `models.py` | 648 | <400 | `wc -l` |
| `schemas.py` | 611 | <250 | `wc -l` |
| `pipeline_builder.py` | 284 | <150 | `wc -l` |
| `helpers.py` | NEW | <150 | `wc -l` |
| `pipeline_steps.py` | 468 | 0 | File deleted |
| `discovery_helpers.py` | 97 | 0 | File deleted |
| `processing_helpers.py` | 172 | 0 | File deleted |
| Duplicate code | Yes | No | Code review |
| All tests pass | Yes | Yes | CI/CD |

### 6-File Domain Standard (Epic 9 Template)

```
domain/{domain_name}/
├── __init__.py          # Module exports
├── service.py           # <200 lines - Lightweight orchestration
├── models.py            # Pydantic models for validation/serialization
├── schemas.py           # Pandera schemas for DataFrame validation
├── constants.py         # Business constants and mappings
├── pipeline_builder.py  # Pipeline assembly using infrastructure steps
└── helpers.py           # Domain-specific helpers + Protocol definitions
```

### Next Steps

1. **Approve this proposal** - User confirmation
2. **Create Story 5.9** - Add to sprint-status.yaml
3. **Draft Story file** - `docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md`
4. **Execute cleanup** - Development team
5. **Update documentation** - Final metrics and structure
6. **Mark Epic 5 truly complete** - After Story 5.9 done

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing functionality | Low | High | Comprehensive test coverage |
| Missing references during migration | Medium | Medium | Grep for all imports before deletion |
| Underestimated effort | Low | Low | 0.5 day buffer included |

### Rollback Plan
- Git branching: Story 5.9 on separate branch
- No destructive changes until tests pass
- Incremental commits for easy revert

---

**End of Proposal**

**Status:** Ready for user approval
**Next Action:** Confirm approval to proceed with Story 5.9 creation
