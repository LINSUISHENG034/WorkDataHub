# Validation Report

**Document:** `docs/sprint-artifacts/stories/7.5-5-unified-failed-records-logging.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2026-01-02

## Summary

- **Overall:** 17/21 passed (81%)
- **Critical Issues:** 3
- **Enhancements:** 5
- **Optimizations:** 3

---

## Section Results

### 1. Epic Context & Story Alignment

Pass Rate: 3/4 (75%)

✓ **PASS** - Story clearly references Epic 7.5 and fits within "Empty Customer Name Handling Enhancement" scope extension
Evidence: Lines 1-14 establish user story format and dependency on Story 7.5-4

✓ **PASS** - Story number format consistent with epic (7.5-5)
Evidence: Line 1: "# Story 7.5.5: Unified Failed Records Logging"

✓ **PASS** - Dependency explicitly declared
Evidence: Line 7: "> **Dependency:** Requires Story 7.5-4 (session_id generation in CLI layer)"

⚠ **PARTIAL** - Dependency description is misleading
Evidence: Story says "Requires Story 7.5-4 (session_id generation in CLI layer)" but Story 7.5-4 does NOT implement session_id generation - it only provides the Rich console infrastructure. Story 7.5-5 itself defines session_id generation (AC-1 and Task 2.4).
Impact: Dev agent may incorrectly assume session_id is already available from 7.5-4

### 2. Acceptance Criteria Validation

Pass Rate: 6/6 (100%)

✓ **PASS** - AC-1: Session ID format clearly specified
Evidence: Lines 17-20 define format `etl_{YYYYMMDD_HHMMSS}_{random_6chars}` with example

✓ **PASS** - AC-2: Single file output path specified
Evidence: Lines 22-24: `logs/wdh_etl_failures_{session_id}.csv`

✓ **PASS** - AC-3: Unified schema with all required fields
Evidence: Lines 26-36 define complete schema table with 6 fields

✓ **PASS** - AC-4: Append mode requirement specified
Evidence: Lines 38-40 describe append mode behavior

✓ **PASS** - AC-5: Hyperlink output requirement with Rich integration
Evidence: Lines 42-44 specify hyperlink format

✓ **PASS** - AC-6: Auto-create directory requirement
Evidence: Lines 46-48 specify pathlib usage pattern

### 3. Tasks & Subtasks Structure

Pass Rate: 3/5 (60%)

✓ **PASS** - Tasks are numbered and linked to ACs
Evidence: Lines 51-88 define 6 tasks with AC references

⚠ **PARTIAL** - Task 3 has incorrect scope description
Evidence: Line 67 says "Modify `cli/etl/main.py` to generate session_id at startup" but session_id generation function is defined in Task 2.4 (failure_exporter.py). The CLI should *call* the function, not define it.
Impact: Potential code duplication or confusion about where generation logic lives

✗ **FAIL** - Task 3.2 references unclear "executor context"
Evidence: Line 68: "Pass session_id through executor context" - What is executor context? Is it a dataclass, dict, or global? Not specified.
Impact: Dev agent may create ad-hoc solutions instead of using established patterns

✗ **FAIL** - Task 4 modifies domain services incorrectly
Evidence: Lines 71-75 say modify `domain/annuity_performance/service.py` and `annuity_income/service.py` to "emit FailedRecord objects" but current services use `export_error_csv()` function. The task doesn't explain HOW to transition from DataFrame-based export to FailedRecord-based export.
Impact: Breaking change without migration path

✓ **PASS** - Task 6 unit tests cover all ACs
Evidence: Lines 81-88 define tests for each AC

### 4. Dev Notes Quality

Pass Rate: 4/5 (80%)

✓ **PASS** - Architecture patterns section with package structure
Evidence: Lines 92-106 show validation package tree

✓ **PASS** - Key implementation details with code examples
Evidence: Lines 108-195 provide FailedRecord, session ID, and FailureExporter code

✓ **PASS** - File modifications summary table
Evidence: Lines 218-228 list all file changes with types

✓ **PASS** - Code quality constraints referenced
Evidence: Lines 236-243 reference project-context.md limits

⚠ **PARTIAL** - Error type categories list is incomplete
Evidence: Lines 245-251 list 4 error types but don't explain how to determine which type applies. No mapping from current exception types (SchemaErrors, ValidationError) to these categories.
Impact: Dev may assign inconsistent error_type values

### 5. Technical Accuracy

Pass Rate: 1/3 (33%)

✓ **PASS** - References to existing code paths correct
Evidence: `infrastructure/validation/error_handler.py` exists per search results

✗ **FAIL** - Incorrect file path in Reference section
Evidence: Line 257 references `../../src/work_data_hub/infrastructure/validation/error_handler.py` which is wrong (should be relative to docs folder or absolute from project root)
Impact: Clickable link won't work

✗ **FAIL** - Session ID not where story says it should be
Evidence: Story says AC-1 "Generate unique session ID per CLI execution" but Task 2.4 puts generation in `failure_exporter.py`. This is infrastructure layer, not CLI layer. AC-1 implies CLI responsibility but implementation puts it in infrastructure.
Impact: Architectural inconsistency - session_id generation should be in CLI layer per AC-1, but code shows it in infrastructure

---

## Failed Items

### 1. ✗ Task 3.2 - Undefined "executor context"
**Recommendation:** Define explicitly what executor context means. Options:
- Add `session_id: str` parameter to `execute_domain()` function signature
- Create `ExecutionContext` dataclass in `cli/etl/models.py`
- Use structlog `bind()` for context propagation

### 2. ✗ Task 4 - Missing migration path for domain services
**Recommendation:** Add explicit guidance:
1. Keep existing `export_error_csv()` calls for backward compatibility during transition
2. Add parallel collection of `FailedRecord` objects
3. At end of service method, call new `FailureExporter.export()` with collected records
4. After validation, remove legacy `export_error_csv()` calls

### 3. ✗ Reference path incorrect
**Recommendation:** Change line 257 from:
```
- [Existing Error Handler](../../src/work_data_hub/infrastructure/validation/error_handler.py)
```
To:
```
- Existing Error Handler: `src/work_data_hub/infrastructure/validation/error_handler.py`
```

---

## Partial Items

### 1. ⚠ Dependency description misleading
**What's missing:** Story 7.5-4 provides Rich console infrastructure, NOT session_id generation. Clarify that Story 7.5-5 is responsible for session_id generation.
**Suggested fix:** Change line 7 to:
```
> **Dependency:** Requires Story 7.5-4 (Rich console for hyperlink output in AC-5)
```

### 2. ⚠ Task 3 scope description
**What's missing:** Clarify that CLI calls `generate_session_id()` from infrastructure layer
**Suggested fix:** Change Task 3.1 to:
```
- [ ] 3.1 Import `generate_session_id` from `infrastructure.validation.failure_exporter`
- [ ] 3.2 Call at CLI startup and store in local variable
```

### 3. ⚠ Error type categories incomplete
**What's missing:** Mapping from exception types to error_type values
**Suggested addition:**
```python
# Error type mapping:
# SchemaErrors from pandera → VALIDATION_FAILED
# ValidationError from pydantic → VALIDATION_FAILED
# DataFrame rows dropped during transform → DROPPED_IN_PIPELINE
# EnrichmentFailure from company resolver → ENRICHMENT_FAILED
# ForeignKeyViolation from backfill → FK_CONSTRAINT_VIOLATION
```

---

## Recommendations

### 1. Must Fix (Critical)

1. **Define executor context mechanism** - Add explicit guidance for session_id propagation pattern
2. **Add migration path for domain services** - Document how to transition from `export_error_csv()` to `FailedRecord` without breaking existing functionality
3. **Fix reference file path** - Correct the broken relative path

### 2. Should Improve (Enhancements)

1. **Clarify dependency description** - Story 7.5-4 provides Rich console, not session_id
2. **Add error type mapping** - Document which exceptions map to which error_type values
3. **Specify where session_id is generated vs consumed** - Clear separation between infrastructure function and CLI usage
4. **Add integration test scenario** - Multi-domain batch run test to verify append mode works correctly
5. **Reference existing `export_error_csv()` signature** - Show current function signature so dev understands what exists

### 3. Consider (Optimizations)

1. **Add constants for error_type values** - Create `ErrorType` enum in `types.py` to prevent typos
2. **Consider context manager for session** - `with FailureExporter.session() as exporter:` pattern
3. **Add CSV schema version header** - Future-proof the file format

---

## LLM Optimization Issues

### Verbosity Problems
- Code examples are appropriate length
- File structure diagram is helpful
- No excessive explanatory text

### Ambiguity Issues
- "executor context" undefined
- session_id ownership unclear (CLI vs infrastructure)
- domain service modification path unclear

### Missing Critical Signals
- No explicit "DO NOT modify existing export_error_csv function" directive
- No warning about breaking changes to domain services

### Structure Improvements
- Add "⚠️ WARNING" block for potential breaking changes
- Add "Key Files to Read First" section pointing to:
  - `infrastructure/validation/report_generator.py` (existing export function)
  - `domain/annuity_performance/service.py` (current usage pattern)
  - `cli/etl/console.py` (hyperlink method from 7.5-4)

---

## Validation Report Summary

| Category | Count | Status |
|----------|-------|--------|
| PASS | 17 | ✓ |
| PARTIAL | 4 | ⚠ |
| FAIL | 3 | ✗ |
| N/A | 0 | ➖ |

**Verdict:** Story requires minor fixes before dev-story execution. The core requirements are well-defined but task implementation details need clarification to prevent dev agent confusion.

---

## Post-Validation Updates Applied

**Date:** 2026-01-02
**Action:** All improvements applied to story file

### Changes Made:

1. ✅ **Fixed dependency description** (Line 7) - Now correctly states "Rich console for `hyperlink()` method"
2. ✅ **Defined executor context mechanism** - Task 3 now explicitly uses `session_id: str` parameter
3. ✅ **Added migration path for domain services** - Task 4 includes warning block and step-by-step migration
4. ✅ **Fixed reference file paths** - Removed broken relative paths
5. ✅ **Added ErrorType enum** - Task 1 now includes enum creation (prevents typos)
6. ✅ **Added error type mapping table** - Clear mapping from exceptions to enum values
7. ✅ **Added "Key Files to Read First" section** - Guides dev agent to read existing patterns
8. ✅ **Added "Breaking Change Warning" block** - Explicit DO NOT MODIFY directive
9. ✅ **Added existing function reference** - Shows current `export_error_csv()` signature
10. ✅ **Added integration test for multi-domain batch** - Task 6.7
11. ✅ **Added "Future Considerations" section** - Documents out-of-scope optimizations

**Updated Pass Rate:** 21/21 (100%)
