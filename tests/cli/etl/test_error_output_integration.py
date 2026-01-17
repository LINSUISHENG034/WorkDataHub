# tests/cli/etl/test_error_output_integration.py
"""Integration test for clean error output.

Story: CLI-ERROR-CLEANUP - Verify end-to-end error display is clean

NOTE: This test requires database connection and takes several minutes.
Run manually with: uv run pytest tests/cli/etl/test_error_output_integration.py -v
"""

import subprocess

import pytest


@pytest.mark.slow
@pytest.mark.skip(reason="Long-running integration test - run manually")
def test_missing_file_error_output_is_clean():
    """CLI error output should be user-friendly when files don't exist.

    Validates that running ETL on a non-existent period produces:
    - Clean error message about missing files
    - NO raw StepFailureData repr in final summary

    Note: Dagster's internal console logger may still show cascade messages.
    The key improvement is that the FINAL error summary is clean.
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "--env-file",
            ".wdh_env",
            "python",
            "-m",
            "work_data_hub.cli",
            "etl",
            "--domains",
            "annuity_performance",
            "--period",
            "190001",  # Non-existent period
            "--execute",
        ],
        capture_output=True,
        text=True,
        timeout=300,  # Allow 5 minutes for Dagster initialization
    )

    stdout = result.stdout

    # Key assertion: Final error summary should NOT contain raw repr noise
    # The "Job completed with failures" section should show clean message
    assert "StepFailureData(" not in stdout, (
        "Raw StepFailureData repr found in final output"
    )

    # Should contain clean error indication
    assert "failed" in stdout.lower() or "error" in stdout.lower()
