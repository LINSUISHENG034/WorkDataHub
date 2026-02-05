# Validation Report

**Document:** `docs/sprint-artifacts/stories/7.4-1-job-registry-pattern.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2025-12-30

## Summary
- Overall: 17/22 passed (77%)
- Critical Issues: 3
- Enhancement Opportunities: 4
- Optimization Suggestions: 2

---

## Section Results

### Story Structure & Metadata
Pass Rate: 3/3 (100%)

✓ **Story Format (As a... I want... So that...)**
Evidence: Lines 7-11 - Clear user story format with developer persona, registry pattern goal, and business value.

✓ **Status Field Present**
Evidence: Line 3 - `Status: ready-for-dev`

✓ **References to Source Documents**
Evidence: Lines 156-159 - References sprint-change-proposal, new-domain-checklist.md, and actual code location.

---

### Acceptance Criteria Quality
Pass Rate: 4/5 (80%)

✓ **AC1: JOB_REGISTRY Dictionary Created**
Evidence: Lines 15-19 - Clear, testable criteria with specific structure requirements.

✓ **AC2: CLI Executor Refactored**
Evidence: Lines 21-25 - Specific line numbers (200-232) and replacement pattern.

✓ **AC3: Error Message Auto-Generated**
Evidence: Lines 27-30 - Addresses MD-004 issue explicitly.

✓ **AC4: Multi-File Job Support Preserved**
Evidence: Lines 32-35 - Maintains backward compatibility for sandbox_trustee_performance.

⚠ **AC5: Testing Strategy Incomplete**
Evidence: Lines 37-39 - Says "All Existing Tests Pass" but doesn't identify WHICH tests validate this functionality.
Impact: Developer may miss critical test coverage. Need to identify existing executor dispatch tests.

---

### Task Breakdown Quality
Pass Rate: 4/5 (80%)

✓ **Task 1: JobEntry Dataclass**
Evidence: Lines 43-46 - Clear subtasks with type hints and docstring requirements.

✓ **Task 2: JOB_REGISTRY Dictionary**
Evidence: Lines 48-53 - Lists all 3 domains with correct backfill flags.

✓ **Task 3: Refactor _execute_single_domain()**
Evidence: Lines 55-60 - Specific steps for registry lookup and error generation.

✓ **Task 4: Multi-file Job Selection**
Evidence: Lines 62-65 - Preserves existing behavior.

⚠ **Task 5: Test Verification Incomplete**
Evidence: Lines 67-70 - Lists test directories but no specific test file names.
Impact: `tests/cli/` and `tests/orchestration/` are broad; specific test files should be listed.

---

### Technical Specification Quality
Pass Rate: 3/5 (60%)

✓ **Target Code Pattern (Before/After)**
Evidence: Lines 81-112 - Excellent before/after code comparison with line numbers.

✓ **JobEntry DataClass Design**
Evidence: Lines 114-126 - Proper frozen dataclass with type hints.

✗ **FAIL: annuity_income supports_backfill Flag Incorrect**
Evidence: Lines 51 says `annuity_income_job` with `supports_backfill=True` but Task 2.2 doesn't show the flag value.
Actual Code: `jobs.py:143-144` shows `generic_backfill_refs_op` IS used for annuity_income (Story 7.3-7).
Impact: **CRITICAL** - If developer doesn't set `supports_backfill=True`, config.py won't generate backfill config for annuity_income.

✗ **FAIL: Missing Multi-File Warning Logic**
Evidence: "After" code (Lines 95-112) doesn't show how to generate the warning message for domains without multi_file_job.
Current Code: `executors.py:204-205, 210-211` prints warning for annuity_performance and annuity_income.
Impact: **CRITICAL** - Warning messages will be lost if not explicitly preserved in the refactored code.

⚠ **PARTIAL: config.py Backfill List Not Addressed**
Evidence: Story addresses MD-001 and MD-004 but NOT MD-002 (backfill domain list in config.py:157-161).
Impact: Developer might think JOB_REGISTRY `supports_backfill` should be used in config.py, but that's Story 7.4-2's scope. Needs clarification.

---

### Files to Modify Accuracy
Pass Rate: 2/2 (100%)

✓ **orchestration/jobs.py**
Evidence: Line 132 - Correct file path for adding JobEntry and JOB_REGISTRY.

✓ **cli/etl/executors.py**
Evidence: Line 133 - Correct file path and line range (200-232) verified against actual code.

---

### Anti-Pattern Prevention
Pass Rate: 1/2 (50%)

✓ **Special Domain Handling**
Evidence: Lines 77-78 - Explicitly states company_lookup_queue and reference_sync remain special cases.

✗ **FAIL: Missing Import Order Consideration**
Evidence: No mention of where JOB_REGISTRY import should be placed in executors.py.
Current Code: Domain imports are lazy (inside if/elif blocks).
Impact: Moving to registry pattern requires top-level import. Story should note that lazy imports may be needed if circular dependency issues arise.

---

## Failed Items

### F1: annuity_income supports_backfill Flag (Critical)
**Location:** Task 2.2 (Line 51)
**Issue:** Task says "Register `annuity_income_job` with `supports_backfill=True` (Story 7.3-7)" but doesn't show this in the JOB_REGISTRY example.
**Evidence:** `jobs.py:143-144` confirms annuity_income uses `generic_backfill_refs_op`.
**Recommendation:** Add explicit code example:
```python
JOB_REGISTRY = {
    "annuity_performance": JobEntry(annuity_performance_job, supports_backfill=True),
    "annuity_income": JobEntry(annuity_income_job, supports_backfill=True),  # Story 7.3-7
    "sandbox_trustee_performance": JobEntry(
        sandbox_trustee_performance_job,
        multi_file_job=sandbox_trustee_performance_multi_file_job,
        supports_backfill=True,
    ),
}
```

### F2: Missing Multi-File Warning Logic (Critical)
**Location:** Dev Notes → Target Code Pattern (Lines 95-112)
**Issue:** Current executors.py prints warnings when `max_files > 1` for domains without multi_file_job support. The "After" code doesn't preserve this.
**Evidence:** `executors.py:204-205` - `print(f"Warning: max_files > 1 not yet supported for {domain}, using 1")`
**Recommendation:** Add to "After" code:
```python
selected_job = job_entry.job
if max_files > 1:
    if job_entry.multi_file_job:
        selected_job = job_entry.multi_file_job
    else:
        print(f"Warning: max_files > 1 not yet supported for {domain}, using single file")
```

### F3: Missing Import Consideration (Medium)
**Location:** Task 3.1 (Line 57)
**Issue:** Says "Import JOB_REGISTRY from orchestration.jobs" but current pattern uses lazy imports inside if/elif blocks to avoid circular dependencies.
**Recommendation:** Add note: "JOB_REGISTRY can be imported at module level. If circular import issues arise, use lazy initialization pattern."

---

## Partial Items

### P1: AC5 - Testing Strategy Lacks Specificity
**Location:** Lines 37-39
**Gap:** Says "All existing tests pass" but doesn't identify specific test files.
**Recommendation:** Add specific test files:
- `tests/cli/test_executors.py` - if exists
- `tests/orchestration/test_jobs.py` - if exists
- Manual validation commands are good (Lines 139-141)

### P2: config.py MD-002 Boundary Clarification
**Location:** Dev Notes section
**Gap:** Story addresses MD-001/MD-004 but MD-002 (config.py backfill list) is Story 7.4-2's scope. Developer might be confused.
**Recommendation:** Add explicit note: "Note: config.py backfill domain list (MD-002) is OUT OF SCOPE for this story - addressed in Story 7.4-2."

---

## Recommendations

### 1. Must Fix: Critical Misses

| # | Issue | Action |
|---|-------|--------|
| 1 | annuity_income supports_backfill | Add explicit JOB_REGISTRY code example showing all 3 domains with correct flags |
| 2 | Multi-file warning missing | Update "After" code to show warning logic preservation |
| 3 | Import consideration | Add note about lazy import pattern if circular dependency issues arise |

### 2. Should Improve: Enhancements

| # | Issue | Action |
|---|-------|--------|
| 1 | Test file specificity | List actual test files in tests/cli/ that test executor dispatch |
| 2 | MD-002 scope boundary | Add explicit "OUT OF SCOPE" note for config.py changes |
| 3 | Task 5.1-5.3 paths | Add specific pytest command with actual test file paths |
| 4 | Error handling | Add note about what happens if JobEntry.job is accidentally None |

### 3. Consider: LLM Optimization

| # | Issue | Action |
|---|-------|--------|
| 1 | Task 2 verbosity | Combine Task 2.1, 2.2, 2.3 into single task with code example |
| 2 | References section | Move References from bottom to Dev Notes for better visibility |

---

## Validation Metadata

**Validator:** validate-create-story workflow
**Source Documents Analyzed:**
- Story file: 7.4-1-job-registry-pattern.md (172 lines)
- Sprint Change Proposal: sprint-change-proposal-2025-12-30-domain-registry-architecture.md
- Actual code: executors.py (lines 190-250), jobs.py (full), config.py (lines 140-190)
- Technical debt doc: new-domain-checklist.md
- Sprint status: sprint-status.yaml
