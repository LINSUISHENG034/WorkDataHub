# Sprint Change Proposal: ETL Backfill Bug Fixes & SQL Module Architecture

**Date:** 2025-12-16
**Triggered By:** Story 6.2-P6 Validation Failure
**Change Scope:** Moderate
**Status:** Pending Approval

---

## 1. Issue Summary

### Problem Statement

During validation of Story 6.2-P6 (CLI Architecture Unification), the `generic_backfill_refs_op` step failed with multiple issues preventing successful database writes to the `mapping` schema tables.

### Discovery Context

- **When Discovered:** 2025-12-16, during manual CLI validation
- **Discovery Method:** Execution of `python -m work_data_hub.cli etl --domains annuity_performance --execute`
- **Affected Component:** `GenericBackfillService.backfill_table()` in `domain/reference_backfill/generic_service.py`

### Evidence Summary

| Issue ID | Description | Severity | Current Status |
|----------|-------------|----------|----------------|
| I001 | Windows PowerShell command format incompatibility | Medium | Documented |
| I002 | Missing schema qualification in SQL queries | High | Partially Fixed |
| I003 | Missing column quoting for Chinese column names | High | Partially Fixed |
| I004 | Column name mismatch in backfill_columns config | High | Partially Fixed |
| I005 | Tracking fields not supported by mapping schema | High | Fixed |
| I006 | Unknown error after applying fixes | **Critical** | **Unresolved** |

### Additional Architecture Concern

SQL generation logic is scattered across **17 files** with duplicated handling for:
- Schema qualification
- Column name quoting (Chinese characters)
- Parameter binding
- Database dialect differences

---

## 2. Impact Analysis

### Epic Impact

| Epic | Current Status | Impact | Action Required |
|------|----------------|--------|-----------------|
| **Epic 6.2** | `done` (incorrect) | **Direct** | Revert to `in-progress`, add Patch Story |
| Epic 7 | `backlog` | Indirect | Blocked until 6.2 fixes complete |
| Other Epics | Various | None | No impact |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 6.2-P6 (CLI Architecture) | `done` | Code complete, validation blocked |
| 6.2-1 (Generic Backfill Framework) | `done` | Underlying bug affects this story |
| **6.2-P10 (NEW)** | `drafted` | New Patch Story to address issues |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| `sprint-status.yaml` | Epic 6.2 incorrectly marked done | Update to `in-progress` |
| `data_sources.yml` | Needs validation against DB schemas | Add verification task |
| `brownfield-architecture.md` | Missing SQL module documentation | Add new section |
| `cli-etl-backfill-issues-diagnosis.md` | Needs resolution plan | Update with Story reference |

### Technical Impact

| Area | Impact |
|------|--------|
| `domain/reference_backfill/generic_service.py` | Primary fix target |
| `orchestration/ops.py` | Uses GenericBackfillService |
| `infrastructure/sql/` (NEW) | New module to be created |
| Unit Tests | New tests required for SQL generation |

---

## 3. Recommended Approach

### Selected Path: Hybrid Approach (Bug Fix + Architecture Enhancement)

| Phase | Description | Priority | Effort |
|-------|-------------|----------|--------|
| **Phase 1** | Diagnose I006 root cause | Critical | 0.5 day |
| **Phase 2** | Fix I001-I005 known issues | High | 0.5 day |
| **Phase 3** | Create `infrastructure/sql/` module | Medium | 1-2 days |
| **Phase 4** | Migrate existing SQL (optional) | Low | Deferred |

### Rationale

1. **Implementation Effort:** Total ~2-3 days for Phases 1-3
2. **Technical Risk:** I006 root cause unknown is highest risk, must diagnose first
3. **Team Impact:** Incremental fixes, does not block other work
4. **Long-term Sustainability:** SQL module provides foundation for future development

### Alternatives Considered

| Option | Description | Why Not Selected |
|--------|-------------|------------------|
| Quick Fix Only | Fix I001-I006 without SQL module | Addresses symptoms, not root cause of maintainability |
| Full Refactor | Refactor all 17 files immediately | Too much scope, high risk |
| Rollback | Revert 6.2-P6 changes | Doesn't solve underlying issue |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| I006 diagnosis takes longer than expected | Medium | Medium | Time-box to 1 day, escalate if unresolved |
| SQL module introduces new bugs | Low | Medium | Comprehensive unit tests |
| Scope creep during Phase 3 | Medium | Low | Strict scope boundary, defer Phase 4 |

---

## 4. Detailed Change Proposals

### 4.1 Sprint Status Update

**File:** `docs/sprint-artifacts/sprint-status.yaml`

```yaml
# BEFORE
epic-6.2: done
6.2-p6-cli-architecture-unification: done

# AFTER
epic-6.2: in-progress
6.2-p6-cli-architecture-unification: done  # Code complete, validation blocked
6.2-p10-etl-backfill-sql-module: drafted   # NEW
```

### 4.2 New Story: 6.2-P10

**File:** `docs/sprint-artifacts/stories/6.2-p10-etl-backfill-sql-module.md`

**Summary:**
- Type: Patch Story (Bug Fix + Architecture Enhancement)
- Priority: Critical
- Phases: 4 (Diagnose → Fix → SQL Module → Migration)
- Acceptance Criteria: 7 items

**Key Tasks:**
1. Diagnose I006 root cause with verbose logging
2. Fix SQL generation issues (quoting, schema qualification)
3. Create `infrastructure/sql/` module
4. Refactor `generic_service.py` to use new module
5. Add comprehensive unit tests

### 4.3 Configuration Validation

**File:** `config/data_sources.yml`

**Action:** Validation task (no direct edit)
- Verify all FK configs match actual table schemas
- Create verification script: `scripts/validation/verify_fk_config_schema.py`

### 4.4 Architecture Documentation

**File:** `docs/brownfield-architecture.md`

**Action:** Add new section documenting SQL module:
- Module structure (`core/`, `dialects/`, `operations/`)
- Design principles
- Usage examples

### 4.5 Diagnosis Document Update

**File:** `docs/specific/cli-etl-backfill-issues-diagnosis.md`

**Action:** Replace "Recommended Next Steps" with "Resolution Plan" linking to Story 6.2-P10

---

## 5. Implementation Handoff

### Change Scope Classification: **Moderate**

This change requires:
- New Patch Story creation
- Architecture enhancement (SQL module)
- Multiple file updates
- Testing and validation

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement Story 6.2-P10 |
| **SM/PM** | Update sprint tracking, prioritize story |
| **Code Reviewer** | Review SQL module architecture |

### Deliverables

| Deliverable | Owner | Status |
|-------------|-------|--------|
| Sprint Change Proposal (this document) | Correct-Course Workflow | ✅ Complete |
| Story 6.2-P10 file | Dev Team | 📝 To Create |
| Sprint Status update | SM | 📝 To Update |
| SQL Module implementation | Dev Team | ⏳ Pending |
| Architecture doc update | Dev Team | ⏳ Pending |

### Success Criteria

1. **I006 Root Cause Identified:** Clear documentation of what caused the unknown error
2. **ETL Backfill Works:** `generic_backfill_refs_op` successfully writes to `mapping.年金计划`
3. **SQL Module Created:** `infrastructure/sql/` with core, dialects, operations subdirectories
4. **Tests Pass:** All existing tests pass, new SQL module tests added
5. **Documentation Updated:** Architecture doc includes SQL module section

### Next Steps

1. **Immediate:** Get this proposal approved
2. **Day 1:** Create Story 6.2-P10 file, update sprint-status.yaml
3. **Day 1-2:** Execute Phase 1-2 (diagnose and fix)
4. **Day 2-3:** Execute Phase 3 (SQL module)
5. **Ongoing:** Phase 4 can be deferred to future stories

---

## Appendix: File Change Summary

| File | Change Type | Priority |
|------|-------------|----------|
| `docs/sprint-artifacts/sprint-status.yaml` | Update | High |
| `docs/sprint-artifacts/stories/6.2-p10-etl-backfill-sql-module.md` | Create | High |
| `src/work_data_hub/infrastructure/sql/` | Create (new module) | Medium |
| `src/work_data_hub/domain/reference_backfill/generic_service.py` | Refactor | Medium |
| `docs/brownfield-architecture.md` | Update | Low |
| `docs/specific/cli-etl-backfill-issues-diagnosis.md` | Update | Low |
| `config/data_sources.yml` | Validate | Low |
| `scripts/validation/verify_fk_config_schema.py` | Create | Low |

---

## Approval

| Role | Name | Date | Decision |
|------|------|------|----------|
| User | Link | 2025-12-16 | Pending |
| Workflow | Correct-Course | 2025-12-16 | Generated |

---

*Generated by Correct-Course Workflow on 2025-12-16*
