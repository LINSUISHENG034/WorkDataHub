# Validation Report

**Document:** docs/sprint-artifacts/stories/7.3-6-annuity-income-pipeline-alignment.md
**Checklist:** _bmad/bmm/workflows/4-implementation/create-story/checklist.md
**Date:** 2025-12-29

## Summary
- Overall: 28/33 passed (85%)
- Critical Issues: 3
- Enhancement Opportunities: 5
- LLM Optimizations: 4

---

## Section Results

### 1. Story Metadata & Structure
Pass Rate: 7/7 (100%)

✓ PASS - Epic/Story numbering consistency
Evidence: Line 3 - "Epic: 7.3 - Multi-Domain Consistency Fixes", Line 4 - "Status: ready-for-dev"

✓ PASS - Sprint change proposal link present
Evidence: Line 8 - links to `sprint-change-proposal-2025-12-29-annuity-income-pipeline-gap.md`

✓ PASS - User story format (As a... I want... So that...)
Evidence: Lines 13-16 - "As a data engineer, I want... so that..."

✓ PASS - Problem statement with clear evidence
Evidence: Lines 18-41 - SQL verification evidence with row counts and data comparison

✓ PASS - Acceptance criteria with checkboxes
Evidence: Lines 45-65 - 10 acceptance criteria with `- [ ]` checkboxes

✓ PASS - Tasks/Subtasks with checkbox structure
Evidence: Lines 67-109 - 6 tasks with 20 subtasks, all have checkboxes

✓ PASS - Dev Notes section with reference pattern
Evidence: Lines 113-173 - Includes code snippets, file list, architecture notes

---

### 2. Technical Accuracy vs Reference Implementation
Pass Rate: 6/8 (75%)

✓ PASS - `mapping_repository` parameter pattern matches annuity_performance
Evidence: Story lines 119-133 match `annuity_performance/pipeline_builder.py` lines 142-173

✓ PASS - `_fill_customer_name` fix logic is correct
Evidence: Story accurately identifies the bug at `annuity_income/pipeline_builder.py` lines 41-51

✓ PASS - PLAN_CODE_CORRECTIONS/DEFAULTS constants correctly defined
Evidence: Story references `annuity_performance/constants.py` lines 39-40

⚠ PARTIAL - `build_bronze_to_silver_pipeline` signature differs between domains
Evidence: Story Task 1.3 mentions adding parameter but:
- `annuity_performance` has `eqc_config` as REQUIRED (Line 215)
- `annuity_income` has `eqc_config` as OPTIONAL with default None (Line 162)
- Story doesn't mention this inconsistency
Impact: Dev may not realize `eqc_config` handling differs between domains

✗ FAIL - **Missing `eqc_config` parameter requirement in service.py**
Evidence: Story Task 2.1-2.4 focuses on `mapping_repository` but ignores that:
- `annuity_performance/service.py` (lines 211-228) has `eqc_config` handling
- `annuity_income/service.py` (line 254-258) doesn't pass `eqc_config` at all
- Current call: `build_bronze_to_silver_pipeline(enrichment_service=enrichment_service, plan_override_mapping=plan_overrides, sync_lookup_budget=sync_lookup_budget)`
- Missing: `eqc_config` parameter
Impact: **Critical** - Without `eqc_config`, EQC lookups are silently disabled regardless of `mapping_repository`

✗ FAIL - **Missing connection cleanup in service.py**
Evidence: `annuity_performance/service.py` lines 251-257 have try/finally with commit/rollback/close:
```python
finally:
    if repo_connection is not None:
        try:
            repo_connection.commit()
        except Exception:
            repo_connection.rollback()
        repo_connection.close()
```
- Story doesn't mention this cleanup pattern
- Story's proposed code at lines 152-166 lacks finally block
Impact: **Critical** - Connection leak if exception occurs during pipeline execution

---

### 3. Reinvention Prevention Gaps Analysis
Pass Rate: 4/5 (80%)

✓ PASS - Uses existing `CompanyMappingRepository` from infrastructure
Evidence: Line 158 - "Uses existing CompanyMappingRepository from infrastructure.enrichment"

✓ PASS - Uses existing `ReplacementStep` from infrastructure
Evidence: Task 5.1 - "Import ReplacementStep from infrastructure"

✓ PASS - Uses existing constants pattern from annuity_performance
Evidence: Lines 168-170 - References to source constants file

✓ PASS - Follows domain layer organization pattern
Evidence: Lines 146-153 - Correct file modification summary

⚠ PARTIAL - Story doesn't mention `eqc_config` derivation pattern
Evidence: `annuity_performance/service.py` lines 211-228 have sophisticated fallback:
```python
if eqc_config is None:
    eqc_config = EqcLookupConfig(
        enabled=sync_lookup_budget > 0,
        sync_budget=max(sync_lookup_budget, 0),
        ...
    )
```
Impact: Dev might not implement this fallback, causing different behavior

---

### 4. File Structure & Organization
Pass Rate: 4/4 (100%)

✓ PASS - Correct file paths specified
Evidence: Lines 148-153 - All 4 files exist and paths are correct

✓ PASS - Changes align with Epic 5 domain pattern
Evidence: Line 157 - "All changes align with Epic 5 standard domain pattern"

✓ PASS - Architecture compliance noted
Evidence: Lines 162-165 - Single Responsibility, Dependency Inversion, Open/Closed

✓ PASS - Test file location specified
Evidence: Line 153 - `tests/domain/annuity_income/test_pipeline_builder.py`

---

### 5. Regression Prevention
Pass Rate: 3/4 (75%)

✓ PASS - Backward compatibility claimed
Evidence: Line 165 - "Open/Closed: Adding parameters, not modifying existing interfaces"

✓ PASS - Existing test verification required
Evidence: AC9 - "All existing unit tests pass"

✓ PASS - New test requirements specified
Evidence: AC10 - "New unit tests verify consistent behavior between domains"

⚠ PARTIAL - Missing test for connection cleanup error handling
Evidence: No test case for verifying proper cleanup when pipeline throws exception
Impact: Silent connection leaks could occur in production

---

### 6. Implementation Completeness
Pass Rate: 4/5 (80%)

✓ PASS - All 4 identified gaps have tasks
Evidence: Tasks 1-6 cover all gaps from sprint change proposal

✓ PASS - Plan code processing steps specified
Evidence: Tasks 4-5 with subtasks 4.1-5.4

✓ PASS - Clear task sequencing
Evidence: Tasks ordered logically: parameters → service → logic fix → constants → steps → tests

⚠ PARTIAL - Task 2 (`service.py` changes) incomplete
Evidence: Task 2 has 4 subtasks but doesn't include:
- 2.5: Add `eqc_config` handling (deriving from sync_lookup_budget if not provided)
- 2.6: Add try/finally cleanup for `repo_connection`
Impact: Developer will implement incomplete service.py changes

---

### 7. LLM Dev Agent Optimization
Pass Rate: 3/6 (50%)

✓ PASS - Code snippets provided with line numbers
Evidence: Lines 119-144 - Reference pattern with file and line references

✓ PASS - File modification summary table
Evidence: Lines 148-153 - Clear table format

✓ PASS - References section with clickable links
Evidence: Lines 167-172

⚠ PARTIAL - Excessive prose in Dev Notes could be more concise
Evidence: Lines 115-173 could be condensed
Impact: Token waste, slower LLM processing

⚠ PARTIAL - Missing critical anti-pattern warning
Evidence: No warning about:
- Not forgetting try/finally cleanup
- Not forgetting eqc_config parameter
Impact: Dev might miss these critical patterns

⚠ PARTIAL - Story doesn't specify parameter ordering convention
Evidence: In `annuity_performance`, `mapping_repository` comes after `plan_override_mapping` (line 147)
Story Task 1.1 doesn't specify exact parameter position
Impact: Minor inconsistency risk

---

## Failed Items

### FAIL-1: Missing `eqc_config` Parameter Requirement (Critical)

**Problem:** The story focuses on `mapping_repository` but ignores that `eqc_config` is also missing from `annuity_income/service.py`.

**Evidence:**
- `annuity_performance/service.py` line 232: `eqc_config=eqc_config`
- `annuity_income/service.py` line 254-258: No `eqc_config` passed

**Recommendation:** Add Task 2.5:
```
- [ ] 2.5 Add `eqc_config` parameter derivation from `sync_lookup_budget` if not provided
```

And update Task 2.3 code to include `eqc_config`:
```python
pipeline = build_bronze_to_silver_pipeline(
    eqc_config=eqc_config,  # ✅ ADD THIS
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
    mapping_repository=mapping_repository,
)
```

### FAIL-2: Missing Connection Cleanup Pattern (Critical)

**Problem:** Story doesn't include try/finally block for `repo_connection` cleanup.

**Evidence:**
- `annuity_performance/service.py` lines 230-257: Has try/finally with commit/rollback/close
- Story's proposed code (sprint change proposal lines 152-175): No finally block

**Recommendation:** Add Task 2.6:
```
- [ ] 2.6 Wrap pipeline execution in try/finally for connection cleanup
```

And add to Dev Notes:
```python
# CRITICAL: Connection cleanup pattern
try:
    pipeline = build_bronze_to_silver_pipeline(...)
    # ... pipeline execution ...
finally:
    if repo_connection is not None:
        try:
            repo_connection.commit()
        except Exception:
            repo_connection.rollback()
        repo_connection.close()
```

### FAIL-3: `eqc_config` Optional vs Required Inconsistency

**Problem:** Story doesn't address that `eqc_config` parameter handling differs between domains.

**Evidence:**
- `annuity_performance/pipeline_builder.py` line 214-215: `eqc_config: EqcLookupConfig` (required)
- `annuity_income/pipeline_builder.py` line 162: `eqc_config: EqcLookupConfig = None` (optional with None default)

**Recommendation:** Update Task 1 to specify making `eqc_config` required (match annuity_performance) OR document why it should remain optional.

---

## Partial Items

### PARTIAL-1: `build_bronze_to_silver_pipeline` Signature Alignment

**Gap:** Story doesn't mention aligning the `eqc_config` parameter requirement between domains.

**What's Missing:** Decision on whether to make `eqc_config` required in annuity_income like annuity_performance, or document why the difference is intentional.

**Recommendation:** Add to Dev Notes:
```markdown
### eqc_config Parameter Consistency
Decision: [Keep optional with None default / Make required]
Rationale: [Backward compatibility / API consistency]
```

### PARTIAL-2: Missing Test Case for Connection Error Handling

**Gap:** No test verifying proper connection cleanup on exception.

**What's Missing:** Test case that simulates pipeline failure and verifies connection is properly closed.

**Recommendation:** Add to Task 6:
```
- [ ] 6.5 Add test for connection cleanup when pipeline throws exception
```

### PARTIAL-3: eqc_config Derivation Pattern Not Mentioned

**Gap:** `annuity_performance/service.py` has fallback logic to derive `eqc_config` from `sync_lookup_budget` if not provided.

**What's Missing:** This pattern should be replicated in annuity_income.

**Recommendation:** Add to Dev Notes section:
```python
# eqc_config derivation fallback (Story 6.2-P17 pattern)
if eqc_config is None:
    from work_data_hub.infrastructure.enrichment import EqcLookupConfig
    eqc_config = EqcLookupConfig(
        enabled=sync_lookup_budget > 0,
        sync_budget=max(sync_lookup_budget, 0),
        auto_create_provider=True,
        export_unknown_names=export_unknown_names,
        auto_refresh_token=True,
    )
```

---

## Recommendations

### 1. Must Fix (Critical Failures)

1. **Add `eqc_config` handling to service.py**
   - Add Task 2.5 for eqc_config parameter derivation
   - Update pipeline builder call to pass eqc_config
   - Add to imports: `from work_data_hub.infrastructure.enrichment import EqcLookupConfig`

2. **Add connection cleanup try/finally**
   - Add Task 2.6 for connection cleanup
   - Copy pattern from annuity_performance/service.py lines 230-257
   - This prevents connection leaks on pipeline exceptions

3. **Address eqc_config signature inconsistency**
   - Either make annuity_income's eqc_config required (recommended)
   - Or document why optional is intentional

### 2. Should Improve (Important Gaps)

1. **Add eqc_config derivation fallback**
   - Copy pattern from annuity_performance/service.py lines 211-228
   - Ensures consistent behavior when eqc_config not explicitly provided

2. **Add connection cleanup test case**
   - Verify resources are freed even on exception
   - Add subtask 6.5 to Task 6

3. **Specify parameter ordering convention**
   - Document that `mapping_repository` comes after `plan_override_mapping`
   - Maintains consistency with annuity_performance

### 3. Consider (Minor Improvements)

1. **Condense Dev Notes section**
   - Remove redundant explanations
   - Focus on actionable code snippets
   - Improve token efficiency for LLM developer

2. **Add anti-pattern warning box**
   - Explicitly warn about connection leak risk
   - Warn about missing eqc_config if copy-pasting

3. **Add parameter type hints**
   - Story code snippets show `mapping_repository=None` without type hint
   - Reference shows `Optional[CompanyMappingRepository]` pattern

---

## LLM Optimization Improvements

### 1. Token-Efficient Dev Notes Restructure

**Current Problem:** Dev Notes section at 60+ lines with prose explanations.

**Recommendation:** Replace with condensed format:

```markdown
### Dev Notes

#### Required Pattern: service.py
```python
# Imports (add)
from work_data_hub.infrastructure.enrichment import EqcLookupConfig
from work_data_hub.infrastructure.enrichment.mapping_repository import CompanyMappingRepository

# In process_with_enrichment():
mapping_repository, repo_connection = None, None
try:
    engine = create_engine(settings.get_database_connection_string())
    repo_connection = engine.connect()
    mapping_repository = CompanyMappingRepository(repo_connection)
except Exception as e:
    logger.warning("CompanyMappingRepository init failed", error=str(e))

if eqc_config is None:
    eqc_config = EqcLookupConfig(enabled=sync_lookup_budget > 0, ...)

try:
    pipeline = build_bronze_to_silver_pipeline(
        eqc_config=eqc_config,
        mapping_repository=mapping_repository,
        ...
    )
    # execute pipeline
finally:
    if repo_connection:
        repo_connection.commit() if success else repo_connection.rollback()
        repo_connection.close()
```

### 2. Anti-Pattern Warning Box

**Add:**
```markdown
> ⚠️ **CRITICAL ANTI-PATTERNS TO AVOID:**
> 1. DO NOT forget try/finally for repo_connection cleanup
> 2. DO NOT forget to pass eqc_config to pipeline builder
> 3. DO NOT make mapping_repository init failure a hard error (log & continue)
```

### 3. Explicit Success Criteria

**Add testable assertions:**
```markdown
### Verification Commands
```bash
# After implementation, run:
PYTHONPATH=src uv run pytest tests/domain/annuity_income/ -v
# Verify company_id has mixed temp/cached IDs:
SELECT company_id, COUNT(*) FROM business.收入明细 WHERE 月度='2025-10-01' GROUP BY LEFT(company_id,2);
# Expected: Some 'IN' (temp) and some non-'IN' (cached) prefixes
```

### 4. Remove Redundant References

**Current:** Lines 167-172 have 4 references, some redundant.

**Recommendation:** Keep only 2 essential references:
- Reference implementation file
- Gap analysis document

---

**Report Generated:** 2025-12-29
**Validator:** Claude Opus 4.5 (Independent Context)
**Story Status:** ~~Requires revision before dev-ready~~ → ✅ **IMPROVEMENTS APPLIED**

---

## Improvements Applied (2025-12-29)

All 12 suggested improvements have been applied to the story:

### Critical Issues Fixed:
1. ✅ Added `eqc_config` parameter requirement (new AC5, Task 2.3-2.4)
2. ✅ Added connection cleanup try/finally pattern (new AC6, Task 2.5)
3. ✅ Made `eqc_config` required in pipeline_builder (Dev Notes updated)

### Enhancements Added:
1. ✅ Added eqc_config derivation fallback pattern to Dev Notes
2. ✅ Added connection cleanup test case (new Task 6.5, AC13)
3. ✅ Specified parameter ordering convention in Dev Notes
4. ✅ Added anti-pattern warning box at top of Dev Notes
5. ✅ Added testable verification commands section

### LLM Optimizations Applied:
1. ✅ Condensed Dev Notes with essential code patterns only
2. ✅ Added critical anti-pattern warning box
3. ✅ Removed redundant references (kept 2 essential ones)
4. ✅ Added explicit verification SQL commands

**Story effort updated:** 4 → 5 Story Points (to account for new requirements)
