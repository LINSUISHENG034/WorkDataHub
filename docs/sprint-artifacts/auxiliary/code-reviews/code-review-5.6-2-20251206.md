**🔥 CODE REVIEW FINDINGS, Link!**

**Story:** `docs/sprint-artifacts/stories/5.6-2-normalize-company-name-bracket-fix.md`
**Git vs Story Discrepancies:** 2 found (Untracked test files)
**Issues Found:** 0 High, 2 Medium, 1 Low

## 🟡 MEDIUM ISSUES
1.  **Untracked Test Files:** The directory `tests/unit/infrastructure/cleansing/` contains new tests (`test_string_rules.py`, `__init__.py`) that are present on disk but **not tracked by git** (`??` status). They must be added.
2.  **Performance - Inefficient Sorting:** In `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py`, the line `sorted_core = sorted(_CORE_REPLACE_STRING, key=lambda s: -len(s))` is executed **inside the function call**. This means for a dataset of 1M rows, it sorts this list 1M times. It should be moved to a module-level constant `_SORTED_CORE_SUFFIXES`.

## 🟢 LOW ISSUES
1.  **Weak Test Assertion:** In `tests/unit/infrastructure/cleansing/test_string_rules.py`, the test `test_nested_brackets_not_matched` uses `assert "中国公司" in result`. It should assert exact equality (`assert result == "中国公司"`) to ensure no trailing artifacts remain.

**Verification Results:**
*   **AC Coverage:** 100% (Verified via code analysis and running new tests).
*   **New Tests:** 18 Passed.
*   **Regression:** One pre-existing failure (`test_normalize_company_name_collapses_spaces`) confirmed unrelated to this story.

**Recommendation:**
I can fix the performance issue, improve the test assertion, and add the files to git.

