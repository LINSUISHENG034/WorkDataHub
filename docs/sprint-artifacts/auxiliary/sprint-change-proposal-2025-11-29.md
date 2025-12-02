# Sprint Change Proposal: Pipeline Framework Refactoring

**Date:** 2025-11-29
**Triggered By:** Epic 4 Retrospective
**Author:** Bob (Scrum Master Agent)
**Approved By:** Link
**Status:** Approved for Implementation

---

## 1. Issue Summary

### Problem Statement

During the Epic 4 `annuity_performance` domain implementation, development did not fully utilize the shared Pipeline framework established in Epic 1 (`domain/pipelines/`). This resulted in:

1. **Code Duplication:** Generic transformation steps were implemented within the domain instead of shared modules
2. **Architecture Deviation:** `service.py` uses manual orchestration instead of `Pipeline.run()`
3. **Code Bloat:** Domain code expanded to ~5,000 lines, with ~36% (~1,800 lines) that should be shared
4. **Future Risk:** Without remediation, Epic 9's 6+ domain migrations will produce 10,800+ lines of duplicate code

### Discovery Context

- **When:** Epic 4 completion retrospective (2025-11-29)
- **How:** Code structure analysis comparing architecture design vs actual implementation
- **Evidence:**
  - `annuity_performance/pipeline_steps.py`: 1,376 lines (58% shareable)
  - `annuity_performance/service.py`: 1,338 lines (45% shareable)
  - `architecture.md` Decision #3 defines Pipeline framework, but not fully utilized

### Root Cause Analysis

| Factor | Responsibility | Explanation |
|--------|----------------|-------------|
| **Implementation Deviation** | ~70% | Did not fully utilize existing shared Pipeline framework |
| **Architecture Guidance Gap** | ~30% | Lacked specific guidance on which steps should be shared |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact Level | Details |
|------|--------------|---------|
| **Epic 4** | Completed | Requires refactoring but functionality unchanged |
| **Epic 5** | Medium | Should use refactored shared framework |
| **Epic 6-8** | Low | Not directly affected |
| **Epic 9** | **High** | Direct beneficiary - saves ~1,800 lines per domain |

### Artifact Conflicts

| Artifact | Required Changes |
|----------|------------------|
| `architecture.md` | Add shared steps list and directory structure to Decision #3 |
| `domain/pipelines/steps/` | Create new directory, extract generic steps |
| `annuity_performance/` | Refactor to use shared steps and Pipeline.run() |
| Tests | Add unit tests for shared steps |

### Technical Impact

- **Code Reduction:** ~1,800 lines extracted to shared module
- **Reusability:** 4 generic steps available for all future domains
- **Maintainability:** Single source of truth for common transformations
- **Performance:** No impact (same code, different organization)

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment - Add New Story

**Story 4.7: Pipeline Framework Refactoring for Domain Reusability**

### Rationale

| Criterion | Assessment |
|-----------|------------|
| Implementation Effort | **Medium** - 3 days estimated |
| Technical Risk | **Low** - No functional changes, only code organization |
| Timeline Impact | **Minimal** - Completes before Epic 5 starts |
| Long-term Benefit | **High** - Saves 10,800+ lines in Epic 9 |
| Team Morale | **Positive** - Addresses technical debt proactively |

### Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| Rollback | ❌ Not viable | Functionality is correct, would lose validated work |
| MVP Adjustment | ❌ Not needed | This is code quality, not functionality issue |
| Defer to Epic 9 | ❌ Risky | Technical debt accumulates, harder to fix later |

---

## 4. Detailed Change Proposals

### 4.1 New Story: 4-7-pipeline-framework-refactoring.md

**Location:** `docs/sprint-artifacts/stories/4-7-pipeline-framework-refactoring.md`

**Summary:**
- Extract 4 generic steps to `domain/pipelines/steps/`
- Refactor `annuity_performance` to use shared steps
- Refactor `service.py` to use `Pipeline.run()`
- Update architecture documentation
- Add unit tests for shared steps
- Verify all existing tests pass

**Acceptance Criteria:** 7 ACs covering structure, extraction, refactoring, documentation, testing

**Tasks:** 11 tasks estimated at 3 days total

### 4.2 Update: sprint-status.yaml

**Changes:**
- Epic 4 status: `done` → `in-progress`
- Add Story 4-7 with status `drafted`, priority `high`
- Story 4-7 blocks Epic 5

### 4.3 Update: architecture.md Decision #3

**Changes:**
- Add "Shared Steps Directory Structure" section
- List available shared steps with purposes
- Provide usage pattern for new domains
- Set target: <500 lines domain-specific code per domain

---

## 5. Implementation Handoff

### Change Scope Classification: **Minor**

This change can be implemented directly by the development team without requiring backlog reorganization or strategic replanning.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Dev Agent** | Execute code refactoring, extract shared steps, update tests |
| **Scrum Master (Bob)** | Create Story document, update sprint-status.yaml |
| **Architect (Winston)** | Review architecture documentation updates |

### Implementation Sequence

| Order | Action | Owner | Duration |
|-------|--------|-------|----------|
| 1 | Create Story 4.7 document | Scrum Master | 0.5 day |
| 2 | Update sprint-status.yaml | Scrum Master | 0.1 day |
| 3 | Create shared steps directory | Dev Agent | 0.5 day |
| 4 | Extract generic steps | Dev Agent | 1 day |
| 5 | Refactor annuity_performance | Dev Agent | 0.5 day |
| 6 | Update architecture.md | Dev Agent | 0.25 day |
| 7 | Add shared step tests | Dev Agent | 0.5 day |
| 8 | Verify existing tests pass | Dev Agent | 0.25 day |
| 9 | Code review | Architect | 0.5 day |

### Success Criteria

- [ ] `domain/pipelines/steps/` directory created with 4 shared steps
- [ ] `annuity_performance/pipeline_steps.py` reduced from ~1,376 to ~600 lines
- [ ] `annuity_performance/service.py` uses `Pipeline.run()`
- [ ] `architecture.md` Decision #3 updated with shared steps guidance
- [ ] All 54+ existing annuity tests pass
- [ ] Shared steps have >90% test coverage
- [ ] Real data validation (33,615 rows) still completes in <20 seconds

---

## 6. Approval Record

| Item | Status | Date |
|------|--------|------|
| Change Proposal #1: New Story 4.7 | ✅ Approved | 2025-11-29 |
| Change Proposal #2: Update sprint-status.yaml | ✅ Approved | 2025-11-29 |
| Change Proposal #3: Update architecture.md | ✅ Approved | 2025-11-29 |
| Change Proposal #4: Create Story file | ✅ Approved | 2025-11-29 |
| **Overall Sprint Change Proposal** | ✅ Approved | 2025-11-29 |

---

## 7. Next Steps

1. **Immediate:** Create Story 4.7 document and update sprint-status.yaml
2. **This Sprint:** Execute Story 4.7 (3 days)
3. **Before Epic 5:** Verify refactoring complete and all tests pass
4. **Epic 5+:** Use shared framework for all new domain development

---

**Document Generated:** 2025-11-29
**Workflow:** Correct Course (BMad Method)
**Approved By:** Link
