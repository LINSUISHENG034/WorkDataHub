# Validation Report

**Document:** `docs/sprint-artifacts/stories/7.1-4-remove-company-mapping-legacy.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2025-12-25

## Summary

- **Overall:** 17/24 items passed (71%)
- **Critical Issues:** 6
- **Enhancement Opportunities:** 3
- **LLM Optimizations:** 2

---

## Section Results

### 1. Story Structure & Metadata
Pass Rate: 4/4 (100%)

✓ **Story header with status**
*Evidence:* Line 1-3: `# Story 7.1-4: Remove company_mapping Legacy`, `Status: ready-for-dev`

✓ **User story format (As/I want/So that)**
*Evidence:* Lines 7-9: Proper user story format with Data Engineer persona

✓ **Context section with Priority/Effort/Epic**
*Evidence:* Lines 13-15: `Priority: P0 (BLOCKING)`, `Effort: 3 hours`, `Epic: 7.1`

✓ **Problem Statement and Root Cause**
*Evidence:* Lines 17-37: Clear problem statement about Zero Legacy violation and root cause explanation

---

### 2. Acceptance Criteria Quality
Pass Rate: 7/9 (78%)

✓ **AC-1: Remove Alembic Migration Table Creation**
*Evidence:* Lines 48-58: GIVEN/WHEN/THEN format with verification command

⚠ **AC-1 PARTIAL: Migration already cleaned**
*Evidence:* Grep of `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` (line 537-538) shows: `# NOTE: Step 5 (company_mapping) REMOVED - see enrichment_index` and `# See Story 7.1-4: Remove company_mapping Legacy`
*Impact:* Task 1 claims to remove Step 5, but it's already removed. Story should acknowledge this partial completion state.

✓ **AC-2: Remove company_mapping_loader.py Module**
*Evidence:* Lines 60-73: Verification commands provided

✓ **AC-3: Remove orchestration/jobs.py References**
*Evidence:* Lines 75-90: Specific line numbers to modify

✓ **AC-4: Remove DDL File**
*Evidence:* Lines 92-104: Delete and verify commands

✓ **AC-5: Update manifest.yml**
*Evidence:* Lines 106-125: YAML snippet showing what to remove

⚠ **AC-6 PARTIAL: Remove company_mapping Tests**
*Evidence:* Lines 127-148 lists files to delete, but file structure verification shows:
- `tests/io/test_company_mapping_loader.py` - EXISTS ✓
- `tests/io/loader/test_company_mapping_loader.py` - EXISTS ✓
- `tests/e2e/test_company_mapping_migration.py` - EXISTS ✓
*Impact:* File paths are accurate, but missing `tests/integration/test_cli_multi_domain.py` which has 10+ `company_mapping` references

✓ **AC-7: Remove company_mapping_ops.py Module**
*Evidence:* Lines 150-165: Verification commands with usage check

✗ **AC-8 FAIL: Documentation Not Comprehensive**
*Evidence:* Lines 167-182 mention only 3 documentation files, but grep shows additional files:
- `docs/project-context.md` - Line 142 references `config/company_mapping.yml` (YAML config, NOT the deprecated table - DISTINCTION UNCLEAR)
- `scripts/create_table/README.md` - Lines 9, 72 reference `company_mapping`
*Impact:* Developer may miss documentation updates

✓ **AC-9: Full Test Suite Passes**
*Evidence:* Lines 184-193: Clear verification command

---

### 3. Task/Subtask Completeness
Pass Rate: 3/6 (50%)

✓ **Tasks map to ACs**
*Evidence:* Lines 197-247: 8 tasks clearly mapped to 9 ACs

✗ **Task 1 FAIL: Inaccurate Description**
*Evidence:* Task 1.1-1.4 (lines 198-201) describe removing "Step 5" from migration, but the migration file (line 537) already has `# NOTE: Step 5 (company_mapping) REMOVED`. Either:
1. Story was created after partial work was done (should update task description)
2. Task should be "Verify Step 5 removal" not "Remove Step 5"

✗ **Task 6 FAIL: Missing Dependency Analysis**
*Evidence:* Task 6 (lines 230-234) deletes `company_mapping_ops.py`, but:
1. `core.py` line 16 imports `CompanyMappingOpsMixin`
2. `core.py` line 24 composes `CompanyMappingOpsMixin` into `CompanyMappingRepository`
*Impact:* Deleting `company_mapping_ops.py` will cause ImportError. Task must include updating `core.py`.

⚠ **Task 5.6 PARTIAL: Incomplete Verification**
*Evidence:* Line 228 suggests `grep -r "company_mapping" tests/` but this will find 50+ false positives including variable names like `valid_company_mappings` in `generate_golden_dataset_gemini.py`

✓ **Task 7: Documentation Update**
*Evidence:* Lines 236-241: Comprehensive search and update approach

✓ **Task 8: Full Test Suite Validation**
*Evidence:* Lines 243-247: Complete verification steps

---

### 4. Dev Notes Quality
Pass Rate: 3/4 (75%)

✓ **Critical Implementation Details**
*Evidence:* Lines 251-268: Clear WARNING about not preserving deprecated code

✓ **File Deletion/Modification Checklists**
*Evidence:* Lines 270-288: Tables with file, action, and rationale

✓ **Risk Mitigation**
*Evidence:* Lines 364-376: Three risks identified with mitigations

✗ **Missing: Active Code Dependencies FAIL**
*Evidence:* Dev Notes don't mention that `company_enrichment_loader.py` (active, NOT deprecated) has 15+ references to `enterprise.company_mapping` table in SQL queries (lines 125, 181, 251, 359, 421, 480, 505). This file is NOT in the deletion list because it's not deprecated - it's active code that USES the deprecated table.
*Impact:* After removing `company_mapping` table, the active `company_enrichment_loader.py` will have broken SQL queries. Story needs to address what happens to this file.

---

## Failed Items

### ✗ F1: Alembic Migration Task Already Completed (Critical)
**Problem:** Task 1 describes removing Step 5 from Alembic migration, but this is already done.
**Recommendation:** Update Task 1 to "Verify Step 5 removal is complete" or mark as pre-completed with a note.

### ✗ F2: Missing core.py Update for CompanyMappingOpsMixin Import (Critical)
**Problem:** Deleting `company_mapping_ops.py` (AC-7) without updating `core.py` will cause `ImportError`.
**Recommendation:** Add subtask to Task 6:
```
- [ ] 6.5 Update `src/work_data_hub/infrastructure/enrichment/repository/core.py`:
  - Remove `from .company_mapping_ops import CompanyMappingOpsMixin` (line 16)
  - Remove `CompanyMappingOpsMixin` from `CompanyMappingRepository` class composition (line 24)
```

### ✗ F3: company_enrichment_loader.py Uses Deprecated Table (Critical)
**Problem:** `src/work_data_hub/io/loader/company_enrichment_loader.py` is an ACTIVE file (not deprecated) that has 15+ SQL references to `enterprise.company_mapping`. The story treats this table as deprecated but doesn't address what happens to code that writes to it.
**Recommendation:** Add new AC or clarify in Dev Notes:
- Option A: Update `company_enrichment_loader.py` to use `enrichment_index` instead
- Option B: Mark `company_enrichment_loader.py` for deprecation
- Option C: Clarify that `company_mapping` table continues to exist for write operations but loader is deprecated

### ✗ F4: db_strategy.py Has Fallback to company_mapping (Critical)
**Problem:** `src/work_data_hub/infrastructure/enrichment/resolver/db_strategy.py` lines 81-82, 298-305 contain `_resolve_via_company_mapping()` function as a fallback.
**Recommendation:** Add to AC-7 or create new AC:
- Remove `_resolve_via_company_mapping()` function from `db_strategy.py`
- Remove fallback call at line 82

### ✗ F5: test_cli_multi_domain.py References Not Listed (Medium)
**Problem:** AC-6 lists test files to delete but `tests/integration/test_cli_multi_domain.py` has 10+ `company_mapping` references (lines 54, 57, 66, 67, 107, 113, 122, 139, 153).
**Recommendation:** Add to Task 5:
```
- [ ] 5.7 Review and update `tests/integration/test_cli_multi_domain.py`
```

### ✗ F6: AC-8 Documentation List Incomplete (Minor)
**Problem:** AC-8 lists only 3 documentation files but `scripts/create_table/README.md` also has `company_mapping` references.
**Recommendation:** Add to AC-8:
```
Files to update:
- scripts/create_table/README.md - Remove company_mapping references
```

---

## Partial Items

### ⚠ P1: config/company_mapping.yml Distinction Unclear
**Problem:** Story mentions `config/company_mapping.yml` (YAML config for Layer 1) but this is NOT the deprecated `enterprise.company_mapping` table. The naming overlap may cause developer confusion.
**Recommendation:** Add clarifying note in Dev Notes:
```markdown
> [!NOTE]
> The `config/company_mapping.yml` file is NOT deprecated. It is the Layer 1 YAML config
> for hardcoded mappings and remains in use. Only the `enterprise.company_mapping` DATABASE
> TABLE and its loader code are deprecated.
```

### ⚠ P2: False Positive Grep Matches
**Problem:** Verification commands like `grep -r "company_mapping" tests/` will find false positives like `valid_company_mappings` variable in `scripts/temp/generate_golden_dataset_gemini.py`.
**Recommendation:** Update verification commands to use word boundaries or exclude known false positives.

---

## LLM Optimization Improvements

### O1: Reduce Dev Notes Verbosity
**Problem:** Dev Notes (Lines 249-377) are 128 lines - very verbose with repeated information.
**Recommendation:** 
- Consolidate "File Deletion Checklist" and "File Modification Checklist" into single table
- Move database migration notes to separate section only if needed
- Remove redundant "Zero Legacy Policy Compliance" section (repeats project-context.md principles)

### O2: Make Tasks More Atomic
**Problem:** Task 6 (lines 230-234) has implicit dependency on updating `core.py` which is not stated.
**Recommendation:** Each task should be self-contained with explicit dependencies listed.

---

## Recommendations

### 1. Must Fix (Critical Failures)
1. **F2:** Add core.py update subtask to prevent ImportError
2. **F3:** Clarify company_enrichment_loader.py fate - uses deprecated table
3. **F4:** Add db_strategy.py cleanup to remove company_mapping fallback

### 2. Should Improve (Important Gaps)
1. **F1:** Update Task 1 description to reflect already-completed state
2. **F5:** Add test_cli_multi_domain.py to test cleanup list
3. **P1:** Add clarifying note about config/company_mapping.yml vs deprecated table

### 3. Consider (Minor Improvements)
1. **F6:** Add README.md to documentation update list
2. **O1:** Reduce Dev Notes verbosity by ~30%
3. **P2:** Improve grep commands to reduce false positives

---

## Conclusion

The story is well-structured with clear acceptance criteria and comprehensive tasks. However, **6 critical issues** were identified that could cause implementation failures:

1. **ImportError risk** from deleting `company_mapping_ops.py` without updating `core.py`
2. **Active code breakage** in `company_enrichment_loader.py` and `db_strategy.py` that use the deprecated table
3. **Outdated task** describing work that's already been done

These issues must be addressed before the story can be implemented successfully.
