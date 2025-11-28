# Engineering Backlog

This backlog collects cross-cutting or future action items that emerge from reviews and planning.

Routing guidance:

- Use this file for non-urgent optimizations, refactors, or follow-ups that span multiple stories/epics.
- Must-fix items to ship a story belong in that story’s `Tasks / Subtasks`.
- Same-epic improvements may also be captured under the epic Tech Spec `Post-Review Follow-ups` section.

| Date | Story | Epic | Type | Severity | Owner | Status | Notes |
| ---- | ----- | ---- | ---- | -------- | ----- | ------ | ----- |
| 2025-11-10 | 1.3 | 1 | Doc | High | TBD | Open | Add the required Dev Notes `.bind(domain="annuity", execution_id="exec_123")` example + JSON payload so AC-5 is satisfied (docs/stories/1-3-structured-logging-framework.md). |
| 2025-11-10 | 1.3 | 1 | Doc | Medium | TBD | Open | Document LOG_LEVEL/LOG_TO_FILE/LOG_FILE_DIR in `.env.example` to match `work_data_hub.utils.logging` expectations. |
| 2025-11-16 | 1.10 | 1 | Blocker | Critical | Dev | Completed | ✅ Add `requests>=2.32.0` to pyproject.toml dependencies (used in config.py:113-114 but missing - will cause ImportError). |
| 2025-11-16 | 1.10 | 1 | Feature | High | Dev | Completed | ✅ Implement tiered retry limits: create `_get_retry_limit()` helper, modify `_execute_step_with_retry()` to use tier-specific limits (database=5, network=3, HTTP status-dependent) instead of single max_retries=3 for all errors. |
| 2025-11-16 | 1.10 | 1 | Feature | High | Dev | Completed | ✅ Implement `is_retryable_error(exception, retryable_exceptions, retryable_http_status_codes) -> Tuple[bool, Optional[str]]` helper with HTTP status code detection returning tier name (database/network/http_429_503/http_500_502_504). |
| 2025-11-16 | 1.10 | 1 | Feature | Medium | Dev | Completed | ✅ Add retry outcome logs: `pipeline.step.retry_success` after successful retry, `pipeline.step.retry_failed` after exhausting retries (AC #6 completion). |
| 2025-11-16 | 1.10 | 1 | Code Quality | Low | Dev | Completed | ✅ Fix 9 ruff linting errors (7 E501 line-too-long, 2 I001 import-sorting) via `uv run ruff check --fix`. |
| 2025-11-16 | 1.10 | 1 | Test | High | Dev | Completed | ✅ Add missing unit tests: test_retry_with_database_error (5 retries), test_retry_with_network_error (3 retries), test_retry_with_http_500 (2 retries), test_retry_with_http_429 (3 retries), test_no_retry_with_http_404 (permanent error). |
| 2025-11-16 | 1.10 | 1 | Feature | Medium | Dev | Completed | ✅ RECOMMENDED: Implement deep copy for nested dicts (Task 3.1) - add `_prepare_input_data()` helper using `copy.deepcopy()` for dict rows (AC #2 completion). |
| 2025-11-17 | 2.4 | 2 | Test | Medium | Dev | Completed | ✅ Create performance test for Story 2.4 at tests/performance/test_story_2_4_performance.py - achieved 153,673 rows/s throughput (AC-PERF-1), verified all date formats and edge cases. |
| 2025-11-17 | 2.4 | 2 | Doc | Medium | Dev | Completed | ✅ Update Task 5 completion status in story file (docs/sprint-artifacts/2-4-chinese-date-parsing-utilities.md) - marked Task 5, Subtask 5.1, Subtask 5.3 as [x] complete to reflect actual code state. |
| 2025-11-17 | 2.4 | 2 | Doc | Low | Dev | Completed | ✅ Create standalone date parser usage documentation (docs/utils/date-parser-usage.md) - comprehensive guide with Pydantic integration examples, performance guidance, troubleshooting, and common use cases. |
| 2025-11-28 | 3.1 | 3 | Bug | High | Dev | Open | Add missing import `from datetime import datetime` in tests/unit/io/connectors/test_version_scanner.py:1 - causes NameError in test_versionedpath_contains_all_required_fields |
| 2025-11-28 | 3.1 | 3 | Bug | High | Dev | Open | Fix invalid directory touch() operations in tests/unit/io/connectors/test_version_scanner.py lines 110, 273-292 - cannot call touch() on directory paths, causes TypeError |
| 2025-11-28 | 3.1 | 3 | Bug | High | Dev | Open | Fix timestamp race conditions in test_latest_modified_selects_newest_folder and test_multi_version_scenario - touch files BEFORE creating version directories OR increase sleep >1s (tests/unit:56-76, tests/integration:41-74) |
| 2025-11-28 | 3.1 | 3 | Feature | High | Dev | Open | Implement complete rejected_versions metadata in src/work_data_hub/io/connectors/version_scanner.py:149-152 - include ALL scanned versions with filter reasons per AC #1 requirement |
| 2025-11-28 | 3.1 | 3 | Test | Medium | Dev | Open | Add platform detection for Windows-incompatible tests (test_folder_access_error_handling, test_cross_platform_unicode_paths) - skip on Windows or use platform-specific permission handling (tests/unit:320-346, tests/integration:184-207) |
| 2025-11-28 | 3.1 | 3 | Test | Medium | Dev | Open | Remove or adjust test_invalid_strategy_raises_error in tests/unit/io/connectors/test_version_scanner.py:212-228 - type system already prevents invalid strategies at compile time |
| 2025-11-28 | 3.1 | 3 | Doc | High | Dev | Open | Correct Change Log false statement at docs/sprint-artifacts/stories/3-1-version-aware-folder-scanner.md:702 - states "All tests passing" but 9/26 tests failing (34.6% failure rate) |
| 2025-11-28 | 3.1 | 3 | Blocker | Critical | Dev | Open | Fix ALL 9 failing tests before story can be approved - 6 unit tests, 3 integration tests (see Senior Developer Review section for complete breakdown) |
