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
