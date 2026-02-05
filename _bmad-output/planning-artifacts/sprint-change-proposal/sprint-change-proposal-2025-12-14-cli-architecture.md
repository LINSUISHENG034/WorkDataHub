# Sprint Change Proposal: CLI Architecture Unification & Multi-Domain Batch Processing

**Date**: 2025-12-14
**Author**: Link (via Correct Course Workflow)
**Status**: Proposed
**Priority**: High

---

## 1. Executive Summary

### 1.1 Change Trigger
During Epic 6.2 implementation, a functional gap was identified between the current CLI tool (`src/work_data_hub/orchestration/jobs.py`) and the Legacy System (`legacy/annuity_hub/main.py`). The current CLI can only process a single domain per invocation, while production scenarios require batch processing of multiple domains for monthly data.

### 1.2 Proposed Solution
Create **Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing** to:
1. Unify all CLI tools under `src/work_data_hub/cli/` directory
2. Implement multi-domain batch processing capability
3. Maintain clean separation between CLI layer and Dagster orchestration layer

### 1.3 Impact Assessment
- **Risk Level**: Low
- **Effort**: Medium
- **Breaking Changes**: Yes (CLI command paths will change)
- **Documents Affected**: ~30 command examples across documentation

---

## 2. Problem Statement

### 2.1 Current State

| System | Multi-Domain Support | Monthly Processing |
|--------|---------------------|-------------------|
| **Legacy System** | One run processes multiple domains (via handler config) | Only processes specified directory |
| **WorkDataHub CLI** | One run processes single domain only | Supports `--period` parameter |

### 2.2 Evidence

**Evidence 1 - Data Directory Structure**:
```
tests/fixtures/real_data/
├── 202311/
├── 202411/
├── 202412/
├── 202501/
├── 202502/
└── 202510/
```

**Evidence 2 - Legacy System** (`legacy/annuity_hub/main.py:56-72`):
- Iterates through all files and matches handlers by keyword
- One run can process multiple domains

**Evidence 3 - Current CLI Limitation** (`jobs.py:758-761`):
- Only supports single `--domain` parameter
- Story 6.2-P3 explicitly excluded "single command multi-domain run" CLI

### 2.3 Additional Architecture Issue

CLI tools are scattered across 4 different locations:
- `cli/` - EQC refresh, data cleansing (Story 6.2-P5)
- `orchestration/jobs.py` - Main ETL jobs
- `io/auth/auto_eqc_auth.py` - EQC authentication
- `scripts/`, `utils/` - Development scripts (not for unification)

---

## 3. Proposed Solution

### 3.1 Target Architecture

```
src/work_data_hub/
├── cli/                              # CLI Entry Layer (NEW/ENHANCED)
│   ├── __init__.py
│   ├── __main__.py                   # Unified entry: python -m work_data_hub.cli
│   ├── etl.py                        # ETL CLI - supports single & multi-domain (extracted from jobs.py)
│   ├── auth.py                       # Auth CLI (migrated from auto_eqc_auth.py)
│   ├── eqc_refresh.py                # EQC refresh (existing)
│   └── cleanse_data.py               # Data cleansing (existing)
│
├── orchestration/                    # Dagster Orchestration Layer (PRESERVED)
│   ├── jobs.py                       # Dagster job definitions (main() REMOVED)
│   ├── ops.py                        # Dagster ops
│   ├── schedules.py                  # Dagster schedules
│   └── sensors.py                    # Dagster sensors
```

> **Design Decision (First Principles)**: Single domain is a special case of multi-domain (domains=1).
> No separate `batch` command needed - unified `etl` command handles both cases.

### 3.2 New Command Format

```bash
# Unified entry point
python -m work_data_hub.cli <command> [options]

# Single domain processing
python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

# Multi-domain batch processing (same command, multiple domains)
python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

# All domains processing
python -m work_data_hub.cli etl --all-domains --period 202411 --execute

# Authentication
python -m work_data_hub.cli auth refresh

# EQC refresh
python -m work_data_hub.cli eqc-refresh --full
```

### 3.3 Command Migration Table

| Old Command | New Command |
|-------------|-------------|
| `python -m work_data_hub.orchestration.jobs --domain X --period Y --execute` | `python -m work_data_hub.cli etl --domains X --period Y --execute` |
| `python -m work_data_hub.io.auth.auto_eqc_auth` | `python -m work_data_hub.cli auth refresh` |
| `python -m work_data_hub.cli.eqc_refresh` | `python -m work_data_hub.cli eqc-refresh` (unchanged) |
| `python -m work_data_hub.cli.cleanse_data` | `python -m work_data_hub.cli cleanse` (unchanged) |
| N/A | `python -m work_data_hub.cli etl --domains X,Y --period Y --execute` (NEW - multi-domain) |
| N/A | `python -m work_data_hub.cli etl --all-domains --period Y --execute` (NEW - all domains) |

> **Breaking Change**: Old commands are completely deprecated with no compatibility layer.
> Project is not yet in production - clean architecture takes priority.

---

## 4. Impact Analysis

### 4.1 Epic Impact

| Epic | Impact | Action Required |
|------|--------|-----------------|
| Epic 1-6 | Done | No action |
| Epic 6.2 | Done | Add Story 6.2-P6 |
| Epic 7 | Backlog | Benefits from multi-domain CLI for testing |

### 4.2 Artifact Impact

| Artifact Type | Impact | Priority |
|---------------|--------|----------|
| PRD | No change required | - |
| Architecture Docs | Update required (2-3 files) | High |
| UX Design | No change required | - |
| Tech Spec | Optional update (command examples) | Medium |
| Story Files | Optional update (historical) | Low |

### 4.3 Code Impact

| Category | Files | Complexity |
|----------|-------|------------|
| Test files (import updates) | 6 | Low |
| Demo scripts | 1 | Low |
| Documentation (command examples) | ~30 locations | Medium |

---

## 5. Risk Assessment

### 5.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import path changes cause test failures | High | Low | Batch update all imports, run full test suite |
| Dagster job call chain breaks | Medium | Medium | Keep job definitions in orchestration/jobs.py unchanged |
| Multi-domain batch performance issues | Low | Medium | Sequential execution, reuse existing single-domain logic |
| Documentation update omissions | Medium | Low | Use grep to find all references |

### 5.2 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users accustomed to old commands | Medium | Low | Provide clear migration docs and command mapping table |
| CI/CD scripts fail | Low | Medium | Check for automation scripts depending on old commands |

### 5.3 Overall Risk Level: **LOW**

---

## 6. Implementation Plan

### 6.1 Proposed Story: 6.2-P6

**Title**: CLI Architecture Unification & Multi-Domain Batch Processing

**Description**: Unify all CLI tools under `src/work_data_hub/cli/` directory and implement multi-domain batch processing capability to close the functional gap with Legacy System.

### 6.2 Implementation Phases

```
Phase 1: CLI Architecture Setup
├── Task 1.1: Create cli/__main__.py unified entry framework
├── Task 1.2: Extract jobs.py main() to cli/etl.py
└── Task 1.3: Verify single-domain processing unchanged

Phase 2: Multi-Domain Support in ETL CLI
├── Task 2.1: Extend cli/etl.py to support --domains parameter (comma-separated)
├── Task 2.2: Implement sequential multi-domain processing logic
└── Task 2.3: Add --all-domains flag to process all configured domains

Phase 3: Auth CLI Migration
├── Task 3.1: Migrate auto_eqc_auth.py to cli/auth.py
└── Task 3.2: Integrate into unified entry

Phase 4: Testing and Documentation
├── Task 4.1: Update all test file imports
├── Task 4.2: Update architecture documentation
├── Task 4.3: Update command example documentation
└── Task 4.4: Create command migration reference
```

> **Simplified by First Principles**: No separate `batch.py` needed.
> Multi-domain logic integrated directly into `etl.py`.

### 6.3 Acceptance Criteria

| AC | Description | Verification |
|----|-------------|--------------|
| AC1 | `python -m work_data_hub.cli etl --domains X --period Y --execute` works identically to old command | Run existing tests |
| AC2 | `python -m work_data_hub.cli etl --domains A,B --period Y --execute` processes multiple specified domains | New integration test |
| AC3 | `python -m work_data_hub.cli etl --all-domains --period Y --execute` processes all configured domains | New integration test |
| AC4 | All existing tests pass | `pytest` |
| AC5 | Architecture documentation updated | Documentation review |
| AC6 | Old command paths completely removed (no compatibility layer) | Code review |

---

## 7. Recommendation

### 7.1 Decision

**Recommended Action**: Create Story 6.2-P6 and implement before starting Epic 7

### 7.2 Rationale

1. **Closes functional gap** with Legacy System
2. **Clean architecture** - separates CLI layer from Dagster orchestration
3. **No technical debt** - direct refactoring without compatibility layers
4. **Benefits Epic 7** - multi-domain CLI simplifies testing workflows

### 7.3 Next Steps

| Step | Action | Owner |
|------|--------|-------|
| 1 | Approve this change proposal | Link |
| 2 | Create Story 6.2-P6 via `create-story` workflow | Agent |
| 3 | Update sprint-status.yaml | Agent |
| 4 | Begin implementation | Dev |

---

## 8. Appendix

### 8.1 Related Documents

- PRD Summary: `docs/prd/prd-summary.md`
- Architecture: `docs/brownfield-architecture.md`
- Story 6.2-P3: `docs/sprint-artifacts/stories/6.2-p3-orchestration-architecture-unification.md`
- Legacy System: `legacy/annuity_hub/main.py`
- Current CLI: `src/work_data_hub/orchestration/jobs.py`

### 8.2 Files to be Modified

**New Files**:
- `src/work_data_hub/cli/__main__.py` - Unified CLI entry point
- `src/work_data_hub/cli/etl.py` - ETL CLI with single & multi-domain support
- `src/work_data_hub/cli/auth.py` - Authentication CLI

**Modified Files**:
- `src/work_data_hub/orchestration/jobs.py` (remove main(), keep Dagster job definitions)
- `src/work_data_hub/io/auth/auto_eqc_auth.py` (remove - functionality moved to cli/auth.py)
- `docs/brownfield-architecture.md`
- `docs/architecture-boundaries.md`
- 6 test files (import updates)

> **First Principles Simplification**: No `batch.py` needed - multi-domain logic in `etl.py`

### 8.3 Checklist Completion Status

| Section | Status |
|---------|--------|
| 1. Understand Trigger and Context | Completed |
| 2. Epic Impact Assessment | Completed |
| 3. Artifact Conflict Analysis | Completed |
| 4. Solution Design | Completed |
| 5. Risk Assessment | Completed |
| 6. Implementation Path | Completed |

---

*Generated by Correct Course Workflow on 2025-12-14*
