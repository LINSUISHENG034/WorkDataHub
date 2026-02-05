# Validation Report

**Document:** `docs/sprint-artifacts/stories/7.4-6-plan-portfolio-code-consolidation.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2026-01-02

## Summary

- **Overall:** 18/22 passed (82%)
- **Critical Issues:** 3
- **Enhancement Opportunities:** 4
- **LLM Optimization Suggestions:** 2

---

## Section Results

### Step 1: Load and Understand the Target

Pass Rate: 4/4 (100%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Story file loaded and metadata extracted | Story 7.4-6, Status: drafted, Epic 7.4 |
| ✓ PASS | Workflow variables resolved | story_key=7.4-6, story_title="Plan/Portfolio Code Handling Consolidation" |
| ✓ PASS | Current implementation guidance assessed | Story has User Story, 5 AC, 5 Task groups with subtasks, Dev Notes, Command Reference |
| ✓ PASS | Sprint Change Proposal linkage | References `sprint-change-proposal-2026-01-02-plan-code-consistency.md` correctly (line 105-106) |

---

### Step 2: Exhaustive Source Document Analysis

Pass Rate: 5/6 (83%)

#### 2.1 Epics and Stories Analysis

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Epic objectives understood | Story addresses code duplication from Epic 7.4 validation (line 87) |
| ✓ PASS | Cross-story dependencies identified | References Story 5.5.4 precedent (line 98-100), Story 7.3-6 as source of duplication |
| ⚠ PARTIAL | Story requirements complete | Story has 5 AC but Sprint Change Proposal mentions `_clean_portfolio_code()` helper function that may also need consolidation - story doesn't address this |

**Impact:** The `_clean_portfolio_code()` helper in `annuity_performance/pipeline_builder.py:98-136` is called by `_apply_portfolio_code_defaults()` but is not mentioned in the story tasks. If not extracted, the shared function will need to duplicate this helper.

#### 2.2 Architecture Deep-Dive

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Technical stack verified | Pandas, Python typing, infrastructure layer patterns followed |
| ✓ PASS | Code structure patterns verified | Matches existing `infrastructure/mappings/shared.py` pattern (lines 98-100 reference Story 5.5.4) |

#### 2.3 Previous Story Intelligence

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Previous work patterns analyzed | Story references Story 5.5.4 portfolio code extraction as precedent (line 98-100) |

---

### Step 3: Disaster Prevention Gap Analysis

Pass Rate: 5/8 (63%)

#### 3.1 Reinvention Prevention

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Code reuse opportunities identified | Story correctly identifies existing `infrastructure/mappings/shared.py` to extend |
| ✓ PASS | Existing solutions referenced | References existing `DEFAULT_PORTFOLIO_CODE_MAPPING` and `PORTFOLIO_QTAN003_BUSINESS_TYPES` constants |

#### 3.2 Technical Specification

| Mark | Item | Evidence |
|------|------|----------|
| ✗ FAIL | Implementation differences documented | Story assumes functions are identical but actual code shows significant differences between domains |
| ⚠ PARTIAL | Function signature consistency | Sprint Change Proposal shows function with different parameter signature than what exists in code |

**Critical Finding - Function Implementation Differences:**

**`_apply_portfolio_code_defaults()`** implementations differ significantly:

| Aspect | annuity_performance | annuity_income |
|--------|---------------------|----------------|
| Value cleaning | Uses `_clean_portfolio_code()` helper | Uses inline `str.replace()` + `str.upper()` |
| Empty mask | `result.isna() \| (result == "")` | `result.isna()` only |
| Data type | Preserves numeric types | Converts to `"string"` dtype |
| 职业年金 handling | Skips in loop: `if plan_type != "职业年金"` | Processes all plan_types |

**Impact:** The Sprint Change Proposal provides implementation code that doesn't match either domain exactly. Developer will need to decide which behavior to preserve or unify.

#### 3.3 File Structure

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | File locations correct | `infrastructure/transforms/plan_portfolio_helpers.py` follows existing pattern |
| ⚠ PARTIAL | Export configuration specified | AC-2 mentions exports but doesn't specify which functions should be re-exported in domain constants.py for backward compatibility |

#### 3.4 Regression Prevention

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Regression tests specified | AC-5 covers existing pipeline tests, multi-domain integration test, ETL dry-run |
| ✗ FAIL | Behavioral parity validation | No specific test for behavioral differences between domains being unified |

**Impact:** If implementation differences are silently merged to one behavior, existing domain-specific tests may pass but production behavior may change unexpectedly.

---

### Step 4: LLM-Dev-Agent Optimization Analysis

Pass Rate: 4/4 (100%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Token efficiency | Story is well-structured with tables and bullet points |
| ✓ PASS | Actionable instructions | Each task has specific subtasks with file locations |
| ✓ PASS | Command reference provided | Lines 109-123 provide concrete test commands |
| ✓ PASS | File list provided | Lines 137-150 list all new and modified files |

---

## Failed Items

### ✗ FAIL: Implementation differences not documented (3.2)

**Issue:** The story assumes `_apply_plan_code_defaults()` functions are identical and `_apply_portfolio_code_defaults()` functions are "similar" (line 94), but actual code review reveals significant implementation differences:

1. `annuity_performance` uses helper function `_clean_portfolio_code()` for robust type handling
2. `annuity_income` uses inline pandas string operations
3. Empty value detection logic differs
4. `职业年金` handling differs in the plan type loop

**Recommendation:** Add Dev Notes section documenting:
```markdown
### Implementation Decisions Required

**Portfolio Code Function Differences:**
The two domains implement `_apply_portfolio_code_defaults()` differently:

1. **Cleaning approach**: AP uses `_clean_portfolio_code()` helper (robust type handling),
   AI uses inline `str.replace()` (simpler but less robust)
2. **Recommended**: Extract `_clean_portfolio_code()` to shared module and use
   `annuity_performance` implementation as reference

**Decision:** Use annuity_performance implementation as canonical (more robust)
```

### ✗ FAIL: Behavioral parity validation missing (3.4)

**Issue:** No test specified to verify that the consolidated implementation produces identical output for both domains' existing data patterns.

**Recommendation:** Add to Task 4:
```markdown
- [ ] 4.4 Add behavioral parity test: verify shared function output matches
      original domain-specific function output for sample data
```

---

## Partial Items

### ⚠ PARTIAL: Story requirements complete (2.1)

**Gap:** `_clean_portfolio_code()` helper function (lines 98-136 in annuity_performance) is not addressed in tasks.

**Recommendation:** Add subtask:
```markdown
- [ ] 2.5 Extract `_clean_portfolio_code()` helper to shared module (if consolidating on AP approach)
```

### ⚠ PARTIAL: Function signature consistency (3.2)

**Gap:** Sprint Change Proposal implementation has different empty value handling than codebase.

**Recommendation:** Update Sprint Change Proposal code to match chosen implementation approach, or add explicit decision point to Dev Notes.

### ⚠ PARTIAL: Export configuration specified (3.3)

**Gap:** Story doesn't specify backward compatibility for domain-level imports.

**Recommendation:** Add to Dev Notes:
```markdown
### Backward Compatibility

Domain `constants.py` files should re-export infrastructure constants for
backward compatibility:
```python
# annuity_performance/constants.py
from work_data_hub.infrastructure.mappings import (
    PLAN_CODE_CORRECTIONS,
    PLAN_CODE_DEFAULTS,
)
# Re-export for backward compatibility
__all__ = [..., "PLAN_CODE_CORRECTIONS", "PLAN_CODE_DEFAULTS"]
```
```

---

## Recommendations

### 1. Must Fix (Critical)

1. **Document implementation decision:** Add explicit guidance on which domain's implementation to use as canonical for `_apply_portfolio_code_defaults()`

2. **Add helper function extraction:** Include `_clean_portfolio_code()` in Task 2 if using annuity_performance approach

3. **Add behavioral parity test:** Ensure consolidated function produces same output as domain-specific functions for test data

### 2. Should Improve (Enhancement)

1. **Clarify empty mask behavior:** Document whether empty string check `(result == "")` should be preserved (AP) or removed (AI)

2. **Add 职业年金 handling decision:** Document whether to skip 职业年金 in loop (AP approach) or not (AI approach)

3. **Specify backward compatibility exports:** Ensure domain constants continue to export plan code constants

4. **Add line number references:** Sprint Change Proposal references lines that may shift - use relative descriptions

### 3. Consider (Optimization)

1. **Consolidate test files:** Consider if `test_plan_portfolio_helpers.py` tests can be parameterized to test both plan and portfolio functions efficiently

2. **Add performance note:** Mention that pandas vectorized operations (AI approach) may be faster than `.apply()` with helper function (AP approach)

---

## LLM Optimization Improvements

### Already Strong

- Clear table format for duplication analysis (lines 89-95)
- Concrete command examples with full paths (lines 109-123)
- Task/subtask structure with AC traceability

### Suggested Improvements

1. **Add decision tree to Dev Notes:**
```markdown
### Decision Points
1. Which portfolio code implementation to use? → AP (more robust) ✓
2. Extract _clean_portfolio_code()? → Yes, include in Task 2.5
3. Preserve backward compatibility exports? → Yes, re-export from domain constants
```

2. **Add explicit anti-patterns section:**
```markdown
### Anti-Patterns to Avoid
- ❌ Don't copy constants to both domains (current problem)
- ❌ Don't skip _clean_portfolio_code() extraction
- ❌ Don't remove domain-level exports without checking imports
```

---

## Validation Conclusion

**Story Status:** ⚠️ **NEEDS REVISION**

The story is well-structured with good AC coverage and task breakdown, but contains critical gaps around:

1. **Implementation differences** between the two domains are significant and not documented
2. **Helper function extraction** (`_clean_portfolio_code()`) is missing from scope
3. **Behavioral parity validation** is not specified in tests

These gaps could lead to:
- Developer confusion about which implementation to follow
- Incomplete consolidation (helper function still duplicated)
- Silent behavioral changes in production

**Recommended Action:** Apply the 3 "Must Fix" recommendations before marking story as `ready-for-dev`.
