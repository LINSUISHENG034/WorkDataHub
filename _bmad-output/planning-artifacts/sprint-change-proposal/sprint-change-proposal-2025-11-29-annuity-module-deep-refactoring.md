# Sprint Change Proposal: Story 4.8 - Annuity Module Deep Refactoring Phase 2

**Document Version:** 1.0
**Date:** 2025-11-29
**Triggered By:** Story 4.7 Code Review - Line Count Targets Not Met
**Workflow:** Correct Course (SM Agent)
**Status:** Pending Approval

---

## Section 1: Issue Summary

### Problem Statement

Story 4.7 (Pipeline Framework Refactoring) was completed and passed code review, achieving its functional goals of extracting shared pipeline steps. However, the code reduction targets were not met:

| Module | Story 4.7 Target | Actual Result | Gap |
|--------|------------------|---------------|-----|
| `pipeline_steps.py` | ~600 lines | **1,194 lines** | +99% over target |
| `service.py` | ~800 lines | **1,408 lines** | +76% over target |
| `schemas.py` | (no target) | **635 lines** | Needs evaluation |

**Total `annuity_performance` module:** 4,847 lines - still significantly complex.

### Discovery Context

- **When:** During Story 4.7 code review (2025-11-29)
- **How:** Code review noted line count deviations as "Minor Observations"
- **Evidence:**
  - Story 4.7 review: "Line Count Metrics deviated from targets, but refactoring goals achieved"
  - `service.py` contains 31 functions/classes (excessive responsibilities)
  - `schemas.py` contains ~200 lines of documentation strings

### Impact if Not Addressed

- **Epic 9 Risk:** 6+ new domains will copy the verbose pattern, potentially adding 30,000+ lines of duplicated code
- **Maintainability:** Large modules are harder to test, review, and modify
- **Onboarding:** New developers face steeper learning curve

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact Level | Description |
|------|--------------|-------------|
| **Epic 4** | Low | Add Story 4.8 to complete refactoring; MVP functionality unaffected |
| **Epic 5** | None | Company enrichment unaffected |
| **Epic 9** | Medium | Better patterns established before domain migrations begin |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 4.7 | Done | No changes - already completed and approved |
| **4.8** | **NEW** | New story to complete Phase 2 refactoring |
| Epic 4 Retrospective | Optional | Should capture lessons learned |

### Artifact Conflicts

| Artifact | Conflict Level | Required Updates |
|----------|----------------|------------------|
| PRD | None | MVP goals unchanged |
| Architecture | Low | Extend Decision #3 with shared validation utilities |
| sprint-status.yaml | Low | Add Story 4.8 to backlog |
| UI/UX | None | N/A (backend only) |

### Technical Impact

- **Code Changes:** Refactoring only - no functional changes
- **Test Impact:** All 200+ existing tests must pass
- **Performance:** No impact expected
- **Database:** No schema changes

---

## Section 3: Recommended Approach

### Selected Path: Option 1 - Direct Adjustment

**Decision:** Add Story 4.8 to Epic 4 for Phase 2 refactoring

**Rationale:**
1. **Low Risk:** Pure refactoring with no functional changes
2. **No MVP Impact:** Story 4.7 already delivered functional requirements
3. **Future Value:** Establishes better patterns before Epic 9
4. **Incremental:** Can be prioritized based on team capacity

### Effort Estimate

| Aspect | Estimate |
|--------|----------|
| Development | Medium (2-3 days) |
| Testing | Low (existing tests cover functionality) |
| Documentation | Low (architecture update only) |
| **Total** | **Medium** |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test regression | Low | High | Run full test suite after each change |
| Scope creep | Medium | Medium | Strict focus on extraction only |
| Time pressure | Low | Low | Story is optional, can defer |

---

## Section 4: Detailed Change Proposals

### Proposal 4.1: Create Story 4.8

**Type:** New Story
**Location:** `docs/sprint-artifacts/stories/4-8-annuity-module-deep-refactoring.md`

```markdown
# Story 4.8: Annuity Module Deep Refactoring - Phase 2

**Epic:** Epic 4 - Annuity Performance Domain Migration (MVP)
**Story ID:** 4.8
**Status:** drafted
**Priority:** Medium
**Triggered By:** Correct Course Analysis - Story 4.7 code reduction targets not met

## User Story

**As a** data engineer,
**I want** further modularization of annuity_performance code,
**So that** the codebase is more maintainable and Epic 9 domains can reuse more components.

## Acceptance Criteria

### AC-4.8.1: Extract Shared Data Classes
- Extract `ErrorContext` from `service.py` to `domain/pipelines/types.py`
- Extract `PipelineResult` from `service.py` to `domain/pipelines/types.py`
- Update all imports in `annuity_performance/service.py`
- Ensure backward compatibility via re-exports

### AC-4.8.2: Extract Shared Schema Validation Utilities
- Create `domain/pipelines/validation/` module
- Extract generic validation helpers:
  - `_raise_schema_error` -> `validation/helpers.py`
  - `_ensure_required_columns` -> `validation/helpers.py`
  - `_ensure_not_empty` -> `validation/helpers.py`
- Create `ValidationSummaryBase` class for domain summaries to inherit
- Keep domain-specific schemas in `annuity_performance/schemas.py`

### AC-4.8.3: Refactor service.py Structure
- Split `service.py` into focused modules:
  - `service.py` - Main orchestration entry point (~300 lines)
  - `discovery_helpers.py` - File discovery utilities
  - `processing_helpers.py` - Row processing and transformation logic
- Target: `service.py` reduced to <500 lines

### AC-4.8.4: All Tests Pass
- All existing 200+ tests in `tests/unit/domain/annuity_performance/` pass
- All existing 92 tests in `tests/unit/domain/pipelines/steps/` pass
- No functional changes - behavior identical before and after

## Tasks

- [ ] Task 1: Extract ErrorContext and PipelineResult to shared types (AC: 4.8.1)
- [ ] Task 2: Create domain/pipelines/validation/ module structure (AC: 4.8.2)
- [ ] Task 3: Extract generic validation helpers (AC: 4.8.2)
- [ ] Task 4: Split service.py into focused modules (AC: 4.8.3)
- [ ] Task 5: Update all imports and verify backward compatibility
- [ ] Task 6: Run full test suite and verify all tests pass (AC: 4.8.4)
- [ ] Task 7: Update architecture.md Decision #3

## Success Metrics

| Metric | Before (4.7) | After (4.8) | Target |
|--------|--------------|-------------|--------|
| `service.py` lines | 1,408 | <500 | -65% |
| `schemas.py` lines | 635 | <400 | -37% |
| Shared validation utils | 0 | ~200 | New |
| Total annuity_performance | 4,847 | <3,500 | -28% |

## Definition of Done

- [ ] All acceptance criteria met (AC-4.8.1 through AC-4.8.4)
- [ ] All tasks completed
- [ ] All existing tests pass (200+ tests)
- [ ] Architecture documentation updated
- [ ] Code reviewed and approved
- [ ] No regression in pipeline performance
```

---

### Proposal 4.2: Update sprint-status.yaml

**Type:** Status File Update
**Location:** `docs/sprint-artifacts/sprint-status.yaml`

**OLD:**
```yaml
  4-7-pipeline-framework-refactoring: done  # Code review approved 2025-11-29
  epic-4-retrospective: optional
```

**NEW:**
```yaml
  4-7-pipeline-framework-refactoring: done  # Code review approved 2025-11-29
  4-8-annuity-module-deep-refactoring: backlog  # Added via Correct Course 2025-11-29
  epic-4-retrospective: optional
```

**Rationale:** Track new story in sprint status for visibility and workflow management.

---

### Proposal 4.3: Update Architecture Decision #3

**Type:** Documentation Update
**Location:** `docs/architecture.md` (after line 446)

**Addition:**
```markdown
**Shared Validation Utilities (Story 4.8):**

Generic validation helpers are extracted to `domain/pipelines/validation/`:

```
src/work_data_hub/domain/pipelines/
├── validation/                     # Shared validation utilities
│   ├── __init__.py                 # Public exports
│   ├── helpers.py                  # Generic validation helpers
│   └── summaries.py                # ValidationSummary base classes
├── types.py                        # ErrorContext, PipelineResult (shared)
├── steps/                          # Shared transformation steps
└── core.py                         # Pipeline class
```

**Available Shared Validation Helpers:**

| Helper | Purpose | Source |
|--------|---------|--------|
| `ensure_required_columns()` | Validate DataFrame has required columns | schemas.py |
| `ensure_not_empty()` | Validate DataFrame is not empty | schemas.py |
| `raise_schema_error()` | Create consistent SchemaError | schemas.py |
| `ValidationSummaryBase` | Base class for validation summaries | schemas.py |

**Usage in Domain Schemas:**
```python
from work_data_hub.domain.pipelines.validation import (
    ensure_required_columns,
    ensure_not_empty,
    ValidationSummaryBase,
)
from work_data_hub.domain.pipelines.types import ErrorContext, PipelineResult

# Domain-specific schema inherits shared utilities
@dataclass
class BronzeValidationSummary(ValidationSummaryBase):
    invalid_date_rows: List[int] = field(default_factory=list)
```
```

**Rationale:** Extend shared infrastructure documentation to include validation utilities, providing clear guidance for Epic 9 domain implementations.

---

## Section 5: Implementation Handoff

### Change Scope Classification

**Scope:** Minor

**Rationale:**
- Pure refactoring with no functional changes
- No PRD or MVP scope changes
- No architectural pattern changes (extends existing patterns)
- Can be implemented directly by development team

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Dev Agent** | Implement Story 4.8 tasks |
| **SM Agent** | Create story file, update sprint-status.yaml |
| **Architect** | Review architecture.md updates |

### Implementation Sequence

1. **SM Agent:** Create `4-8-annuity-module-deep-refactoring.md` story file
2. **SM Agent:** Update `sprint-status.yaml` with new story
3. **Dev Agent:** Implement Story 4.8 when prioritized
4. **Dev Agent:** Update `architecture.md` Decision #3
5. **SM Agent:** Code review and mark story done

### Success Criteria

- [ ] Story 4.8 file created in `docs/sprint-artifacts/stories/`
- [ ] sprint-status.yaml updated with new story
- [ ] All 200+ existing tests pass after implementation
- [ ] `service.py` reduced to <500 lines
- [ ] `schemas.py` reduced to <400 lines
- [ ] Architecture documentation updated

---

## Approval

**Proposal Status:** Awaiting User Approval

**Approval Options:**
- [ ] **APPROVED** - Proceed with implementation
- [ ] **APPROVED WITH CONDITIONS** - Proceed with noted modifications
- [ ] **REJECTED** - Do not proceed, document reasons

**Approver:** _______________
**Date:** _______________
**Conditions (if any):** _______________

---

## Change Log

- 2025-11-29: Sprint Change Proposal created via Correct Course workflow
- 2025-11-29: Analysis completed, 3 change proposals drafted
- 2025-11-29: Awaiting user approval

---

**End of Sprint Change Proposal**

*Generated by SM Agent (Bob) via Correct Course Workflow*
