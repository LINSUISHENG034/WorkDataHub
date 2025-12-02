# Sprint Change Proposal: Annuity Module Decomposition

**Date:** 2025-11-30
**Author:** Claude (via correct-course workflow)
**Approved by:** Link
**Status:** Pending Implementation

---

## 1. Issue Summary

### Problem Statement

After completing Story 4.7 (Pipeline Framework Refactoring) and Story 4.8 (Annuity Module Deep Refactoring), the `src/work_data_hub/domain/annuity_performance/` module has become excessively large (~5,000 lines across 11 files), creating potential risks for future domain development.

### Discovery Context

- **Triggering Stories:** Story 4.7, Story 4.8
- **Discovery Date:** 2025-11-30
- **Issue Type:** Technical limitation - architecture concern discovered during implementation

### Evidence

| File | Lines | Concern |
|------|-------|---------|
| `pipeline_steps.py` | 1,194 | Contains 11 classes, many could be shared |
| `processing_helpers.py` | 887 | 19 functions, many are generic transformations |
| `schemas.py` | 637 | 28 symbols, validation logic can be abstracted |
| `models.py` | 627 | Domain-specific, acceptable size |
| `service.py` | 523 | Contains duplicate aliases to processing_helpers |
| `transformations.py` | 362 | Acceptable |
| `validation_with_errors.py` | 356 | Patterns should be reusable |
| `csv_export.py` | 190 | Acceptable |
| `discovery_helpers.py` | 91 | Acceptable |
| `__init__.py` | 41 | Module exports |
| `constants.py` | 34 | Acceptable |
| **Total** | **4,942** | **Target: <2,000 lines** |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact Level | Description |
|------|--------|--------------|-------------|
| Epic 4 | Completed | Low | Add Story 4.9 for cleanup |
| Epic 5 | Backlog | **High** | Needs reusable validation/schema patterns |
| Epic 6 | Backlog | Medium | Testing framework may need adaptation |
| Epic 7-10 | Not Started | **High** | All future domains affected |

### Artifact Conflicts

| Artifact | Conflict | Required Update |
|----------|----------|-----------------|
| PRD | Partial | No change needed - aligns with "new domain in <4 hours" goal |
| Architecture | Yes | Add shared component references to `architecture-boundaries.md` |
| Epics | Yes | Add Story 4.9 to `epics.md` |
| Sprint Status | Yes | Add Story 4.9 to tracking |

### Technical Impact

- **Code Reusability:** Currently 0% - each domain would duplicate ~3,000 lines
- **After Refactoring:** ~60% reduction in per-domain boilerplate
- **Backward Compatibility:** 100% maintained via re-exports

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment (Option 1)

**Create Story 4.9: Annuity Module Decomposition for Reusability**

### Rationale

1. **Low Risk:** Complete test coverage exists for annuity module
2. **High Value:** Prevents code duplication across 5+ future domains
3. **Aligns with PRD:** Supports "new domain in <4 hours" goal
4. **No Rollback Needed:** Story 4.7/4.8 delivered value, just needs optimization

### Alternatives Considered

| Option | Evaluation | Decision |
|--------|------------|----------|
| Option 1: Direct Adjustment | Low effort, low risk | **Selected** |
| Option 2: Rollback 4.7/4.8 | High effort, loses value | Rejected |
| Option 3: MVP Scope Change | Not applicable (MVP complete) | Rejected |

### Effort & Risk Assessment

- **Effort Estimate:** Medium (1 Story cycle)
- **Risk Level:** Low
- **Timeline Impact:** Delays Epic 5 start by 1 Story

---

## 4. Detailed Change Proposals

### 4.1 New Story Definition

**Story 4.9: Annuity Module Decomposition for Reusability**

As a **data engineer**,
I want **the annuity_performance module decomposed into reusable shared components**,
So that **future domain migrations (Epic 5+) can leverage proven patterns without code duplication**.

**Acceptance Criteria:**

1. **Shared Validation Framework** (`domain/validation/`)
   - Extract `validation_with_errors.py` patterns to reusable module
   - Generic `validate_with_error_reporting()` function
   - Configurable error thresholds and export paths

2. **Shared Schema Utilities** (`domain/schemas/`)
   - Extract common schema helpers from `schemas.py`
   - Reusable functions: `_coerce_numeric_columns()`, `_parse_dates()`, `_ensure_required_columns()`
   - Base schema validation patterns

3. **Shared Pipeline Steps** (`domain/pipelines/steps/`)
   - Extract generic steps from `pipeline_steps.py`:
     - `BronzeSchemaValidationStep` → generic base class
     - `GoldProjectionStep` → generic base class
     - `ValidateInputRowsStep` / `ValidateOutputRowsStep` → generic

4. **Slim Annuity Module** (target: <2,000 lines total)
   - Keep only domain-specific logic
   - Import shared components
   - Maintain 100% backward compatibility

**Success Metrics:**
- All existing tests pass without modification
- Module size reduced from ~5,000 to <2,000 lines (60% reduction)
- New domain can import shared components and reduce boilerplate by >50%

### 4.2 Sprint Status Update

Add to `docs/sprint-artifacts/sprint-status.yaml`:
```yaml
4-9-annuity-module-decomposition-for-reusability: drafted
```

### 4.3 Architecture Documentation Update

Add to `docs/architecture-boundaries.md` Cross-story references:
```markdown
- **Story 4.9 – Shared domain components** (planned)
  - `src/work_data_hub/domain/validation/` – Reusable validation with error reporting
  - `src/work_data_hub/domain/schemas/` – Common schema utilities and base patterns
  - `src/work_data_hub/domain/pipelines/steps/` – Generic pipeline step base classes
```

### 4.4 Epics Document Update

Add complete Story 4.9 definition to `docs/epics.md` after Story 4.8.

---

## 5. Implementation Handoff

### Change Scope Classification: **Minor**

This change can be implemented directly by the development team without requiring backlog reorganization or strategic replanning.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Developer (Dev Agent)** | Implement Story 4.9 extraction and refactoring |
| **Scrum Master (SM Agent)** | Draft Story 4.9 file, create story context |
| **Tech Lead** | Review architecture decisions for shared components |

### Implementation Sequence

1. **SM Agent:** Create Story 4.9 file via `create-story` workflow
2. **SM Agent:** Generate story context via `story-context` workflow
3. **Dev Agent:** Implement via `dev-story` workflow
4. **SM Agent:** Code review via `code-review` workflow
5. **Update:** Mark Story 4.9 as done, proceed to Epic 5

### Success Criteria

- [ ] All existing annuity tests pass (100% backward compatibility)
- [ ] Module size reduced to <2,000 lines
- [ ] Shared components documented in architecture-boundaries.md
- [ ] New domain template demonstrates >50% boilerplate reduction

---

## 6. Approval

**Proposal Status:** All 4 change proposals approved by Link

| Proposal | Description | Status |
|----------|-------------|--------|
| Proposal 1 | Story 4.9 Definition | ✓ Approved |
| Proposal 2 | Sprint Status Update | ✓ Approved |
| Proposal 3 | Architecture Doc Update | ✓ Approved |
| Proposal 4 | Epics Doc Update | ✓ Approved |

---

**Next Steps:**
1. Execute approved document updates
2. Run `create-story` workflow for Story 4.9
3. Begin implementation before Epic 5

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
