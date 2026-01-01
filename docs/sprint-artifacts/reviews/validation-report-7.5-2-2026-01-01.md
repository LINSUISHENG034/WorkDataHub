# Validation Report

**Document:** docs/sprint-artifacts/stories/7.5-2-plan-name-fallback-single-plan.md
**Checklist:** _bmad/bmm/workflows/4-implementation/create-story/checklist.md
**Date:** 2026-01-01

## Summary

- Overall: 21/24 passed (88%)
- Critical Issues: 3
- Enhancement Opportunities: 4
- LLM Optimization Suggestions: 2

---

## Section Results

### Step 1: Load and Understand the Target

Pass Rate: 4/4 (100%)

✓ **Story file loaded and parsed**
Evidence: Story file at line 1-309 contains complete story structure with Status: ready-for-dev

✓ **Metadata extracted correctly**
Evidence: epic_num=7.5, story_num=7.5-2, story_key=7.5-2-plan-name-fallback-single-plan, story_title="Plan Name Fallback for Single-Plan Records" (line 1)

✓ **Workflow variables resolved**
Evidence: story_dir, output_folder correctly mapped; Sprint Change Proposal reference at line 251

✓ **Current status understood**
Evidence: Story provides comprehensive implementation guidance with exact code snippets (lines 106-147, 171-241)

---

### Step 2: Exhaustive Source Document Analysis

Pass Rate: 6/6 (100%)

✓ **Epic context extracted**
Evidence: Sprint Change Proposal section 4 (lines 120-152) provides complete Story 7.5-2 specification with Problem ID PN-001

✓ **Architecture deep-dive completed**
Evidence: Dev Notes section (lines 68-169) includes complete plan name format analysis, data statistics, and pipeline integration points

✓ **Previous story intelligence extracted**
Evidence: Story 7.5-1 (completed) referenced at line 81, 253 as prerequisite; learnings incorporated (test patterns, backflow mechanism)

✓ **Technical stack verified**
Evidence: Target file `pipeline_builder.py` correctly identified at line 104, 245; pandas, structured logging patterns documented

✓ **Cross-story dependencies documented**
Evidence: Story 7.5-1 dependency explicitly stated in SCP (lines 251-252 dependency chain)

✓ **Problem context documented**
Evidence: Lines 70-84 provide detailed statistics: 10,565 single-plan records with empty customer names, 297 temp IDs

---

### Step 3: Disaster Prevention Gap Analysis

Pass Rate: 5/8 (63%)

✓ **Reinvention prevention addressed**
Evidence: Code reuses existing `_fill_customer_name` pattern, only modifies/replaces it (line 107: "replace _fill_customer_name")

✓ **API contract consistency**
Evidence: Function signature `_fill_customer_name_from_plan_name(df: pd.DataFrame) -> pd.Series` matches existing pattern (line 108)

✓ **Pipeline integration documented**
Evidence: Lines 149-169 document exact line numbers and replacement strategy

✗ **FAIL: Empty value detection inconsistency**
Impact: Story specifies `(result == "0") | (result == "空白")` at line 134, but current codebase `_fill_customer_name` does NOT check for "空白" (verified via grep at lines 43-51 of actual file). This creates inconsistency between story expectation and actual empty value detection patterns.

**Current codebase pattern:**
```python
# Line 43-51 of pipeline_builder.py - only checks None
if "客户名称" in df.columns:
    return df["客户名称"]  # Keep as-is, including nulls
```

**Story specifies (line 134):**
```python
empty_mask = result.isna() | (result == "") | (result == "0") | (result == "空白")
```

**Risk:** Developer may implement without realizing the empty value detection logic is new, not from existing patterns.

⚠ **PARTIAL: Test file import update missing**
Evidence: Line 247 mentions "Add `_fill_customer_name_from_plan_name` to test file imports" but doesn't show the complete import statement update. Test file (test_pipeline.py) currently imports `_fill_customer_name` at line 25 - story should show the exact import change.

✗ **FAIL: Edge case handling for plan name without suffix**
Impact: Test at lines 230-240 (`test_handles_plan_name_without_suffix`) expects plan name "其他类型计划" to return as-is when no suffix match. However, the function implementation (lines 141-143) returns the plan name unchanged if it doesn't end with "企业年金计划" - this may not be the desired business behavior.

**Question:** If a single-plan record has plan name "山东重工集团" (no suffix), should the result be:
- The plan name as-is → customer name becomes "山东重工集团"? (current implementation)
- Or should it remain empty/null since extraction failed?

**The implementation silently assumes non-matching plan names are valid company names, which may pollute customer name data.**

✓ **Regression check planned**
Evidence: Lines 272-274 document regression verification steps including ETL dry-run and collective-plan behavior check

---

### Step 4: LLM-Dev-Agent Optimization Analysis

Pass Rate: 6/6 (100%)

✓ **Verbosity appropriate**
Evidence: Story provides exact code snippets with line numbers, reducing ambiguity

✓ **Actionable instructions**
Evidence: Tasks broken into specific subtasks (lines 44-66) with checkboxes

✓ **Scannable structure**
Evidence: Clear headings, bullet points, code blocks with comments

✓ **Token efficiency**
Evidence: Dev Notes focused on relevant information; references to external docs for background

✓ **Unambiguous language**
Evidence: Acceptance Criteria are testable and specific (AC-1 through AC-4)

✓ **Command reference included**
Evidence: Lines 278-288 provide exact pytest and CLI commands

---

## Failed Items

### ✗ F-001: Empty Value Detection Inconsistency (CRITICAL)

**Requirement:** Story implementation should align with existing codebase patterns

**Issue:** Story specifies checking for `"空白"` as an empty value variant, but this pattern doesn't exist in the current codebase. This creates potential inconsistency.

**Recommendation:**
1. Verify with stakeholder if `"空白"` (literal Chinese word for "blank") appears in actual data
2. If yes, add comment explaining data source for this value
3. If no, remove from empty_mask to avoid unnecessary complexity
4. Consider extracting empty value detection to a shared utility (already exists in infrastructure/constants.py?)

### ✗ F-002: Edge Case - Plan Name Without Suffix (HIGH)

**Requirement:** Clearly define behavior when plan name doesn't match expected pattern

**Issue:** Test `test_handles_plan_name_without_suffix` expects plan name "其他类型计划" to be returned as-is, effectively setting customer name = plan name. This may introduce incorrect data.

**Recommendation:**
1. Change implementation: If plan name doesn't match `{CompanyName}企业年金计划` pattern, return original customer name (null) instead of plan name
2. Update test expectation: `assert pd.isna(result[0])` instead of `assert result[0] == "其他类型计划"`
3. Add explicit handling comment in code

---

## Partial Items

### ⚠ P-001: Test Import Statement Not Shown

**What's Missing:** Story mentions updating test imports at line 247 but doesn't show the complete change.

**Recommendation:** Add explicit before/after for test file imports:
```python
# BEFORE (line 25):
from work_data_hub.domain.annuity_income.pipeline_builder import (
    ...
    _fill_customer_name,  # Story 7.3-6: Test null preservation
    ...
)

# AFTER:
from work_data_hub.domain.annuity_income.pipeline_builder import (
    ...
    _fill_customer_name_from_plan_name,  # Story 7.5-2: Plan name extraction
    ...
)
```

### ⚠ P-002: Missing __all__ Export Update

**What's Missing:** If adding new function to `pipeline_builder.py`, should it be added to `__all__` list (line 358)?

**Recommendation:** Document whether function should be exported or remain internal.

---

## Enhancement Opportunities

### E-001: Add Negative Test Cases

**Suggestion:** Add test cases for:
- Plan name is None
- Plan name is empty string
- Plan name contains only whitespace
- Plan name is "企业年金计划" (suffix only, no company name)

### E-002: Document Collective Plan Pattern Explicitly

**Suggestion:** Dev Notes mention collective plan pattern `{BrandName}企业年金集合计划` at line 95-100, but test only checks that collective plans are skipped. Consider adding test that verifies collective plan names are NOT extracted even if they end with "企业年金计划".

### E-003: Logging for Traceability

**Suggestion:** Add structured logging to track:
- Number of records with customer name extracted from plan name
- Number of records skipped due to collective plan type
- Number of records skipped due to non-matching suffix

### E-004: Alignment with annuity_performance Domain

**Suggestion:** If this pattern is valuable, consider whether it should also be applied to `annuity_performance` domain's pipeline_builder.py for consistency. Document decision explicitly.

---

## LLM Optimization Improvements

### O-001: Consolidate Code Snippets

**Current:** Code is shown in multiple places (Dev Notes lines 106-147, Pipeline Integration lines 149-169)

**Suggestion:** Single consolidated "Implementation" section with complete before/after would reduce token waste and improve clarity.

### O-002: Remove Redundant References

**Current:** Multiple references to Sprint Change Proposal throughout

**Suggestion:** Single reference at top of Dev Notes is sufficient; remove redundant links to reduce tokens while maintaining traceability.

---

## Recommendations

### 1. Must Fix (Critical)

1. **F-002:** Clarify edge case behavior for plan names without suffix - prevent data pollution
2. **F-001:** Verify "空白" pattern exists in data or remove from implementation

### 2. Should Improve (Important)

1. **P-001:** Add complete test import change
2. **E-001:** Add negative test cases for robustness
3. **E-003:** Add logging for operational visibility

### 3. Consider (Minor)

1. **P-002:** Document __all__ export decision
2. **E-002:** Add collective plan pattern test
3. **E-004:** Document annuity_performance alignment decision

---

## Appendix: Verification Queries

### Verify "空白" exists in data:
```sql
SELECT COUNT(*), "客户名称"
FROM business."收入明细"
WHERE "客户名称" IN ('0', '空白', '')
GROUP BY "客户名称";
```

### Verify plan name patterns:
```sql
SELECT "计划类型", "计划名称",
       CASE WHEN "计划名称" LIKE '%企业年金计划' THEN 'MATCHES'
            ELSE 'NO_MATCH' END as pattern_match
FROM business."收入明细"
WHERE "客户名称" IS NULL OR "客户名称" = ''
GROUP BY "计划类型", "计划名称"
LIMIT 50;
```
