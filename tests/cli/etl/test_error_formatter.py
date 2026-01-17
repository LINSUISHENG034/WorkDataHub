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
                'Error occurred while executing op "discover_files_op":\n'
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
        assert "some_op" in result.lower()
        assert "failed" in result.lower()

    def test_handles_unknown_error_structure(self):
        """Should fallback gracefully for unexpected structures."""

        class UnknownData:
            pass

        result = format_step_failure("some_op", UnknownData())
        assert "some_op" in result
        # Should not raise, should return something sensible
