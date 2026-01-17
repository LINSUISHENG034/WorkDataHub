# src/work_data_hub/cli/etl/error_formatter.py
"""Error message formatting utilities for CLI output.

Story: CLI-ERROR-CLEANUP - Extract user-friendly messages from Dagster errors.
"""

from typing import Any, Optional

# Max length for truncated error strings
_MAX_ERROR_LENGTH = 200


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
    - Exception class prefixes (e.g., DiscoveryError: ...)
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
        if len(s) > _MAX_ERROR_LENGTH:
            return s[:_MAX_ERROR_LENGTH] + "..."
        return s
    except Exception:
        return "<unable to convert to string>"
