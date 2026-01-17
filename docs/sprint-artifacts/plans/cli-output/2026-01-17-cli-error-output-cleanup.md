# CLI Error Output Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up CLI error output when file discovery fails, replacing messy JSON logs, stack traces, and raw Dagster data with concise, user-friendly error messages.

**Architecture:** Fix three layers of output pollution: (1) extract clean error messages from `StepFailureData` instead of printing raw repr, (2) suppress Dagster's internal "Dependencies failed" cascade noise, (3) prevent structlog JSON from mixing with Rich spinner output.

**Tech Stack:** Python, structlog, Dagster, Rich console

---

## Problem Analysis

When running `etl --all-domains --period 202511 --execute` and files don't exist, the output shows:

1. **Raw JSON logs mixed with spinner** (line 29 of temp.md):
   ```
   ⠼ Processing annuity_performance...{"error_type": "DiscoveryError", ...}
   ```

2. **Duplicate Dagster ERROR logs** (lines 31-37):
   ```
   dagster - ERROR - discover_files_op - Epic 3 discovery failed...
   dagster - ERROR - discover_files_op - File discovery failed...
   ```

3. **Full stack traces** (lines 47-69) - Entire Python traceback dumped

4. **Cascading "Dependencies failed" noise** (lines 71-85):
   ```
   dagster - ERROR - read_data_op - Dependencies for step read_data_op failed
   dagster - ERROR - process_domain_op_v2 - Dependencies for step process_domain_op_v2 failed
   ... (6 more lines of this)
   ```

5. **Raw `StepFailureData` repr** (lines 89-133) - Worst offender:
   ```python
   StepFailureData(error=SerializableErrorInfo(message='dagster._core.errors...
   ```

**Desired Output:**
```
⠼ Processing annuity_performance...
❌ Domain annuity_performance failed:
   📁 No files found matching patterns ['*规模收入数据*.xlsx']
      Path: data\real_data\202511\收集数据\数据采集
⚠️  Domain annuity_performance failed with exit code 1
```

---

## Task 1: Create Error Message Formatter Utility

**Files:**
- Create: `src/work_data_hub/cli/etl/error_formatter.py`
- Test: `tests/cli/etl/test_error_formatter.py`

**Step 1: Write the failing test**

```python
# tests/cli/etl/test_error_formatter.py
"""Tests for CLI error message formatting.

Story: CLI-ERROR-CLEANUP - User-friendly error messages
"""

import pytest

from work_data_hub.cli.etl.error_formatter import format_step_failure


class TestFormatStepFailure:
    """Test error message extraction from Dagster StepFailureData."""

    def test_extracts_discovery_error_message(self):
        """Should extract clean message from DiscoveryError cause."""
        # Simulated StepFailureData structure (matches Dagster's actual format)
        class MockSerializableErrorInfo:
            def __init__(self, message: str, cause=None):
                self.message = message
                self.cause = cause
                self.cls_name = "DagsterExecutionStepExecutionError"

        class MockStepFailureData:
            def __init__(self, error):
                self.error = error

        # Build nested error structure matching temp.md lines 89-132
        inner_cause = MockSerializableErrorInfo(
            message=(
                "work_data_hub.io.connectors.exceptions.DiscoveryError: "
                "Discovery failed for domain 'unknown' at stage 'file_matching': "
                "No files found matching patterns ['*规模收入数据*.xlsx'] "
                "in path data\\real_data\\202511\\收集数据\\数据采集. "
                "Candidates found: 0, Files excluded: 0\n"
            ),
            cause=None,
        )
        inner_cause.cls_name = "DiscoveryError"

        outer_error = MockSerializableErrorInfo(
            message=(
                "dagster._core.errors.DagsterExecutionStepExecutionError: "
                "Error occurred while executing op \"discover_files_op\":\n"
            ),
            cause=inner_cause,
        )

        mock_data = MockStepFailureData(error=outer_error)

        result = format_step_failure("discover_files_op", mock_data)

        assert "No files found matching patterns" in result
        assert "规模收入数据" in result
        assert "StepFailureData" not in result
        assert "SerializableErrorInfo" not in result

    def test_handles_none_event_data(self):
        """Should return generic message for None event data."""
        result = format_step_failure("some_op", None)
        assert "some_op failed" in result.lower()

    def test_handles_unknown_error_structure(self):
        """Should fallback gracefully for unexpected structures."""

        class UnknownData:
            pass

        result = format_step_failure("some_op", UnknownData())
        assert "some_op" in result
        # Should not raise, should return something sensible
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/etl/test_error_formatter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'work_data_hub.cli.etl.error_formatter'"

**Step 3: Write minimal implementation**

```python
# src/work_data_hub/cli/etl/error_formatter.py
"""Error message formatting utilities for CLI output.

Story: CLI-ERROR-CLEANUP - Extract user-friendly messages from Dagster errors.
"""

from typing import Any, Optional


def format_step_failure(op_name: str, event_data: Any) -> str:
    """Extract user-friendly error message from Dagster StepFailureData.

    Dagster wraps exceptions in nested SerializableErrorInfo objects.
    This function drills down to find the actual error message.

    Args:
        op_name: Name of the failed op (e.g., "discover_files_op")
        event_data: StepFailureData from dagster event.event_specific_data

    Returns:
        Clean, user-friendly error message without stack traces or repr noise
    """
    if event_data is None:
        return f"Step '{op_name}' failed (no details available)"

    # Try to extract the nested error chain
    error_info = getattr(event_data, "error", None)
    if error_info is None:
        return f"Step '{op_name}' failed: {_safe_str(event_data)}"

    # Drill down through cause chain to find the root cause
    root_message = _extract_root_cause_message(error_info)
    if root_message:
        return root_message

    # Fallback to outer message if no cause found
    outer_message = getattr(error_info, "message", None)
    if outer_message:
        return _clean_message(outer_message)

    return f"Step '{op_name}' failed: {_safe_str(event_data)}"


def _extract_root_cause_message(error_info: Any) -> Optional[str]:
    """Recursively extract the deepest cause message.

    The actual user-relevant error is usually at the deepest level
    of the cause chain (e.g., DiscoveryError inside DagsterExecutionStepExecutionError).
    """
    cause = getattr(error_info, "cause", None)
    if cause is not None:
        # Recurse to get deepest cause
        deeper = _extract_root_cause_message(cause)
        if deeper:
            return deeper
        # This is the deepest cause
        message = getattr(cause, "message", None)
        if message:
            return _clean_message(message)

    return None


def _clean_message(message: str) -> str:
    """Clean up error message for display.

    Removes:
    - Exception class prefixes (e.g., "work_data_hub.io.connectors.exceptions.DiscoveryError: ")
    - Trailing newlines
    """
    if not message:
        return ""

    # Remove common exception prefixes
    prefixes_to_strip = [
        "work_data_hub.io.connectors.exceptions.DiscoveryError: ",
        "dagster._core.errors.DagsterExecutionStepExecutionError: ",
    ]

    cleaned = message.strip()
    for prefix in prefixes_to_strip:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]

    return cleaned.strip()


def _safe_str(obj: Any) -> str:
    """Safely convert object to string, truncating if too long."""
    try:
        s = str(obj)
        # Truncate very long strings
        if len(s) > 200:
            return s[:200] + "..."
        return s
    except Exception:
        return "<unable to convert to string>"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/etl/test_error_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/cli/etl/error_formatter.py tests/cli/etl/test_error_formatter.py
git commit -m "feat(cli): add error message formatter for clean failure output"
```

---

## Task 2: Update Executor to Use Error Formatter

**Files:**
- Modify: `src/work_data_hub/cli/etl/executors.py:369-377`
- Test: `tests/cli/etl/test_executors.py` (existing, add new test)

**Step 1: Write the failing test**

```python
# Add to tests/cli/etl/test_executors.py or create new test file

def test_failure_output_is_clean_not_raw_repr(capsys, monkeypatch):
    """Error output should be user-friendly, not raw StepFailureData repr.

    Story: CLI-ERROR-CLEANUP - Lines 89-133 of temp.md show ugly output
    """
    # This test verifies that when a job fails, we don't see:
    # - "StepFailureData(error=SerializableErrorInfo..."
    # - Full stack traces
    # We should see:
    # - "No files found matching patterns ['*规模收入数据*.xlsx']"

    # Integration test would be ideal but unit test can verify formatter is called
    from work_data_hub.cli.etl.error_formatter import format_step_failure

    # Verify the formatter produces clean output (covered in Task 1)
    # This test documents the integration requirement
    pass
```

**Step 2: Modify executors.py to use formatter**

Change lines 369-378 in `src/work_data_hub/cli/etl/executors.py`:

FROM:
```python
        else:
            console.print("❌ Job completed with failures")
            if not args.raise_on_error:
                for event in result.all_node_events:
                    if event.is_failure:
                        console.print(
                            f"   Error in {event.node_name}: "
                            f"{event.event_specific_data}"
                        )
```

TO:
```python
        else:
            console.print("❌ Job completed with failures")
            if not args.raise_on_error:
                from .error_formatter import format_step_failure

                for event in result.all_node_events:
                    if event.is_failure:
                        clean_message = format_step_failure(
                            event.node_name, event.event_specific_data
                        )
                        console.print(f"   {clean_message}")
```

**Step 3: Run existing tests to verify no regressions**

Run: `uv run pytest tests/cli/etl/ -v -k executor`
Expected: PASS

**Step 4: Commit**

```bash
git add src/work_data_hub/cli/etl/executors.py
git commit -m "fix(cli): use error formatter for clean failure output"
```

---

## Task 3: Suppress Dagster Cascading "Dependencies Failed" Logs

**Files:**
- Modify: `src/work_data_hub/cli/etl/dagster_logging.py`
- Modify: `src/work_data_hub/utils/logging.py`

**Step 1: Analyze the noise source**

The "Dependencies failed" messages come from Dagster's execution engine logging:
```
dagster - ERROR - read_data_op - Dependencies for step read_data_op failed: ['discover_files_op']. Not executing.
```

These are ERROR-level logs from Dagster that fire for every downstream op when an upstream fails.

**Step 2: Add filter to suppress cascading dependency messages**

Modify `src/work_data_hub/utils/logging.py` - add a custom logging filter:

```python
# Add after line 42 (after SENSITIVE_PATTERNS)

class DagsterCascadeFilter(logging.Filter):
    """Filter out Dagster's cascading 'Dependencies failed' messages.

    When one op fails, Dagster logs ERROR for every downstream op saying
    "Dependencies for step X failed". This is noise - user already knows
    the root cause from the first failure.

    Story: CLI-ERROR-CLEANUP
    """

    NOISE_PATTERNS = [
        "Dependencies for step",
        "were not executed:",
        "Not executing.",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress, True to allow."""
        if record.name.startswith("dagster"):
            message = record.getMessage()
            if any(pattern in message for pattern in self.NOISE_PATTERNS):
                return False  # Suppress this message
        return True  # Allow all other messages
```

**Step 3: Apply filter in reconfigure_for_console**

In `reconfigure_for_console()`, add the filter to the dagster logger:

```python
# After line 282 (after dagster_logger.setLevel(...))
    # Story CLI-ERROR-CLEANUP: Suppress cascading dependency failure noise
    if not debug:
        dagster_logger.addFilter(DagsterCascadeFilter())
```

**Step 4: Run tests**

Run: `uv run pytest tests/utils/test_logging.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/utils/logging.py
git commit -m "fix(logging): suppress Dagster cascading dependency failure noise"
```

---

## Task 4: Prevent JSON Logs from Mixing with Spinner

**Files:**
- Modify: `src/work_data_hub/utils/logging.py`

**Step 1: Analyze the issue**

The problem is that structlog JSON logs write to stdout while Rich spinner is also using stdout:
```
⠼ Processing annuity_performance...{"error_type": "DiscoveryError"...
```

The JSON appears inline with the spinner because both write to the same stream.

**Step 2: Solution - Suppress structlog during job execution OR redirect to stderr**

Option A (Recommended): In default (non-debug) mode, set structlog to only emit ERROR+
Option B: Redirect structlog to stderr so it doesn't interfere with Rich

Current code in `reconfigure_for_console()` already sets root_level to ERROR in default mode.
The issue is that Dagster's logger is set to WARNING which allows ERROR logs through.

The real fix: The JSON log at line 29 comes from `discovery/service.py` logging the DiscoveryError.
In default mode, ERROR logs should be allowed but formatted differently.

**Step 3: Modify to use stderr for structlog in non-debug mode**

In `reconfigure_for_console()`, change the handler to use stderr when not in debug mode:

```python
# Replace lines 308-312 with:
    import sys

    # Use stderr for structlog output to avoid mixing with Rich console on stdout
    stream = sys.stderr if not debug else sys.stdout
    new_handler = logging.StreamHandler(stream)
    new_handler.setLevel(root_level)
    new_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.root.addHandler(new_handler)
```

This ensures JSON logs go to stderr while Rich output stays on stdout, preventing the mixed output.

**Step 4: Test manually**

Run: `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202511 --execute`
Expected: Spinner and error message should not be on same line

**Step 5: Commit**

```bash
git add src/work_data_hub/utils/logging.py
git commit -m "fix(logging): redirect structlog to stderr to avoid Rich spinner collision"
```

---

## Task 5: Final Integration Test

**Step 1: Create integration test scenario**

```python
# tests/cli/etl/test_error_output_integration.py
"""Integration test for clean error output.

Story: CLI-ERROR-CLEANUP - Verify end-to-end error display is clean
"""

import subprocess


def test_missing_file_error_output_is_clean():
    """CLI error output should be user-friendly when files don't exist.

    Validates that running ETL on a non-existent period produces:
    - Clean error message about missing files
    - NO raw StepFailureData repr
    - NO cascading "Dependencies failed" noise
    - NO JSON mixed with spinner
    """
    result = subprocess.run(
        [
            "uv", "run", "--env-file", ".wdh_env",
            "python", "-m", "work_data_hub.cli", "etl",
            "--domains", "annuity_performance",
            "--period", "190001",  # Non-existent period
            "--execute",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    stdout = result.stdout
    stderr = result.stderr

    # Should NOT contain raw repr noise
    assert "StepFailureData(" not in stdout, "Raw StepFailureData repr found in output"
    assert "SerializableErrorInfo(" not in stdout, "Raw SerializableErrorInfo found in output"

    # Should NOT contain cascading dependency failures
    assert stdout.count("Dependencies for step") == 0, "Cascading dependency noise found"

    # Should contain clean error indication
    assert "failed" in stdout.lower() or "error" in stdout.lower()
```

**Step 2: Run integration test**

Run: `uv run pytest tests/cli/etl/test_error_output_integration.py -v`
Expected: PASS

**Step 3: Manual verification**

Run the original command from temp.md and verify clean output:
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --all-domains --period 202511 --file-selection newest --execute
```

**Step 4: Final commit**

```bash
git add tests/cli/etl/test_error_output_integration.py
git commit -m "test(cli): add integration test for clean error output"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Error message formatter | `error_formatter.py` + tests |
| 2 | Integrate formatter into executor | `executors.py` |
| 3 | Suppress cascading dependency logs | `logging.py` |
| 4 | Redirect structlog to stderr | `logging.py` |
| 5 | Integration test | `test_error_output_integration.py` |

**Expected Result After Implementation:**

```
==================================================
Processing domain 1/4: annuity_performance
==================================================
🚀 Starting annuity_performance job...
   Domain: annuity_performance
   Mode: delete_insert
   Execute: True
==================================================
⠼ Processing annuity_performance...
✅ Job completed successfully: False
❌ Job completed with failures
   Discovery failed for domain 'unknown' at stage 'file_matching': No files found matching patterns ['*规模收入数据*.xlsx'] in path data\real_data\202511\收集数据\数据采集. Candidates found: 0, Files excluded: 0
⚠️  Domain annuity_performance failed with exit code 1
```

No JSON logs, no stack traces, no cascading dependency noise, no raw repr.
