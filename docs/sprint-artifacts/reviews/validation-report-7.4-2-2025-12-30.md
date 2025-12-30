# Validation Report: Story 7.4-2

**Document:** [7.4-2-config-driven-backfill-list.md](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/7.4-2-config-driven-backfill-list.md)
**Checklist:** [create-story/checklist.md](file:///e:/Projects/WorkDataHub/_bmad/bmm/workflows/4-implementation/create-story/checklist.md)
**Date:** 2025-12-30T14:46

## Summary

- **Overall:** 18/23 passed (78%)
- **Critical Issues:** 3
- **Partial Issues:** 2

---

## Section Results

### Section 1: Epics and Stories Analysis

**Pass Rate: 4/4 (100%)**

✓ **PASS** - Epic context extracted

- Evidence: Story references "MD-002 (Medium Severity)" issue from sprint change proposal (L210-212)

✓ **PASS** - Story requirements clearly stated

- Evidence: 5 Acceptance Criteria defined (L14-42)

✓ **PASS** - Technical constraints identified

- Evidence: "JOB_REGISTRY.supports_backfill Relationship" and scope boundaries (L124-137)

✓ **PASS** - Cross-story dependencies identified

- Evidence: References Story 7.4-1, Story 6.2-P14 predecessors (L142-144)

---

### Section 2: Architecture Deep-Dive

**Pass Rate: 5/6 (83%)**

✓ **PASS** - Code structure patterns followed

- Evidence: Uses existing `get_domain_config_v2()` API from infrastructure layer (L217)

✓ **PASS** - Database schema awareness

- Evidence: Story references `data_sources.yml` schema version increment to 1.2 (L49, L157-160)

⚠ **PARTIAL** - Technical stack with versions

- Evidence: Story references Pydantic model but doesn't specify the exact file path or field type constraints
- **Gap:** Task 2 mentions "output config (or appropriate location)" - location ambiguity

✓ **PASS** - Testing standards documented

- Evidence: Testing Strategy section with specific pytest commands (L186-207)

✓ **PASS** - Integration patterns clear

- Evidence: Shows both config.py and jobs.py integration patterns (L64-107)

✓ **PASS** - File locations specified

- Evidence: Target Code Locations table (L146-154)

---

### Section 3: Previous Story Intelligence

**Pass Rate: 3/3 (100%)**

✓ **PASS** - Previous story analyzed

- Evidence: "Previous Story Intelligence (Story 7.4-1)" section (L220-234)

✓ **PASS** - Key learnings extracted

- Evidence: 4 learnings listed including "Config loader already imported in config.py" (L229-234)

✓ **PASS** - Patterns established

- Evidence: Notes JOB_REGISTRY pattern and import strategies from 7.4-1 (L222-227)

---

### Section 4: Disaster Prevention Gap Analysis

**Pass Rate: 3/5 (60%)**

✗ **FAIL** - Pydantic field location precision

- **Impact:** Task 2.1 says "Add `requires_backfill: bool = False` to output config (or appropriate location)" - this is **too vague** for a developer agent
- **Evidence:** L54: "2.1 Add `requires_backfill: bool = False` to output config (or appropriate location)"
- **Recommendation:** Specify exact Pydantic model (`DomainConfigV2` in `data_source_schema.py`) and field definition

✗ **FAIL** - Schema version validator not updated

- **Impact:** Story says "Update schema_version to 1.2" but doesn't mention updating the `validate_schema_version` validator in `data_source_schema.py:314` which only supports ["1.0", "1.1"]
- **Evidence:** Current code: `supported_versions = ["1.0", "1.1"]` (L314)
- **Recommendation:** Add subtask to update supported_versions list

⚠ **PARTIAL** - Line number accuracy (config.py)

- Evidence: Story says "lines 157-161" but actual hardcoded list is at L157-161 - **CORRECT**
- Note: Line numbers verified against actual `config.py`

✗ **FAIL** - Line number accuracy (jobs.py)

- **Impact:** Story says "lines 434-438" but actual hardcoded list is at L434-438 - **CORRECT**, however there's a **second hardcoded list** in `jobs.py` that isn't addressed
- **Evidence:** Both `build_run_config()` at L323-468 AND the hardcoded check at L434-438 need to be checked - story only addresses one location
- **Recommendation:** Verify if `build_run_config()` in jobs.py is legacy code that should also be refactored

✓ **PASS** - Fallback strategy defined

- Evidence: "Fallback to `False` if config not found or field missing" (L122-123)

---

### Section 5: Implementation Specification Quality

**Pass Rate: 3/5 (60%)**

✓ **PASS** - Clear code examples

- Evidence: OLD vs NEW code patterns for both files (L64-107)

✓ **PASS** - Task breakdown complete

- Evidence: 5 tasks with 13 subtasks (L46-113)

✗ **FAIL** - Missing `_merge_with_defaults` handling

- **Impact:** `get_domain_config_v2()` uses `_merge_with_defaults()` for inheritance. Story doesn't specify that `requires_backfill` should be added to `defaults` section AND that the merge logic will automatically inherit it
- **Evidence:** Story says "Add to defaults section" but doesn't explain inheritance mechanism for new field
- **Recommendation:** Add explicit note about how inheritance will work via `_merge_with_defaults()`

✗ **FAIL** - Task 2.3 is unnecessary/confusing

- **Impact:** "Update `get_domain_config_v2()` to expose field if needed" - this is misleading because Pydantic automatically exposes all model fields
- **Evidence:** L56: "2.3 Update `get_domain_config_v2()` to expose field if needed"
- **Recommendation:** Remove or clarify - Pydantic model fields are auto-exposed

✓ **PASS** - Backward compatibility addressed

- Evidence: AC4 specifies defaults behavior (L33-37)

---

### Section 6: LLM Optimization Analysis

**Pass Rate: 3/3 (100%)**

✓ **PASS** - Actionable instructions

- Evidence: Tasks use checkbox format with specific subtasks

✓ **PASS** - Scannable structure

- Evidence: Uses tables, code blocks, and clear sections

✓ **PASS** - Token efficiency

- Evidence: Story is concise (246 lines) with no excessive verbosity

---

## Failed Items

| ID  | Description                             | Severity     | Recommendation                                                                                                                                 |
| --- | --------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | Pydantic field location ambiguity       | **Critical** | Change Task 2.1 to: "Add `requires_backfill: bool = False` field to `DomainConfigV2` class in `infrastructure/settings/data_source_schema.py`" |
| F2  | Missing schema version validator update | **High**     | Add Task 2.4: "Update `validate_schema_version()` in `data_source_schema.py` to add '1.2' to supported_versions list"                          |
| F3  | Duplicate hardcoded list in jobs.py     | **Medium**   | Verify if `build_run_config()` in jobs.py (L434-438) is the same location referenced OR if there's duplicate logic                             |
| F4  | Unnecessary Task 2.3                    | **Low**      | Remove or clarify Task 2.3 - Pydantic handles field exposure automatically                                                                     |
| F5  | Missing inheritance explanation         | **Low**      | Add note that `_merge_with_defaults()` will automatically propagate `requires_backfill` to domains                                             |

---

## Partial Items

| ID  | Description               | Gap                                                                                          |
| --- | ------------------------- | -------------------------------------------------------------------------------------------- |
| P1  | Technical stack precision | Field location says "(or appropriate location)" - should be explicit                         |
| P2  | Line number verification  | Verified correct, but story should note `jobs.py` has TWO `build_run_config` implementations |

---

## Recommendations

### Must Fix (Critical)

1. **F1**: Specify exact Pydantic model location - current wording will cause LLM developer to search/guess
2. **F2**: Add schema version validator update subtask - without this, v1.2 configs will fail validation

### Should Improve (Important)

3. **F3**: Investigate `build_run_config()` in `jobs.py` vs `cli/etl/config.py` - are these duplicates?
4. **F5**: Add one sentence explaining defaults inheritance via `_merge_with_defaults()`

### Consider (Minor)

5. **F4**: Clean up Task 2.3 wording

---

## Verification Notes

**Files Analyzed:**

- [data_sources.yml](file:///e:/Projects/WorkDataHub/config/data_sources.yml) - v1.1, no `requires_backfill` field
- [data_source_schema.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/infrastructure/settings/data_source_schema.py) - `DomainConfigV2` class, no `requires_backfill`
- [config.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl/config.py) - L157-161 hardcoded list confirmed
- [jobs.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/orchestration/jobs.py) - L434-438 hardcoded list confirmed, legacy `build_run_config()` also present

**Sprint Change Proposal Alignment:** ✅ Story aligns with SCP for MD-002 fix
