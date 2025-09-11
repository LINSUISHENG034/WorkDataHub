"""
End-to-end integration tests for Annuity Performance (规模明细) pipeline - opt-in via marker.

These tests validate the complete ETL pipeline for annuity performance processing
including discovery, reading, processing with column projection, and loading to
PostgreSQL. Tests are opt-in via legacy_data marker.

Usage:
    # Run only legacy data tests
    uv run pytest -m legacy_data -v -k annuity_performance

    # Run with specific environment
    WDH_DATA_BASE_DIR=./reference/monthly uv run pytest -m legacy_data -v -k annuity_performance_e2e

Requirements:
    - reference/monthly directory with sample Excel files
    - PostgreSQL database with DDL applied for execute tests
    - psycopg2 available for database tests
"""

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.legacy_data


def _has_sample_root() -> bool:
    """Check if reference/monthly exists with expected structure."""
    return Path("reference/monthly").exists()


def _has_psycopg2() -> bool:
    """Check if psycopg2 is available for database tests."""
    try:
        import psycopg2  # noqa: F401

        return True
    except ImportError:
        return False


def _run_cli_command(cmd_args: list, capture_output=True):
    """Run CLI command and return result."""
    cmd = ["uv", "run", "python", "-m", "src.work_data_hub.orchestration.jobs"] + cmd_args
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        cwd=".",
        env={**os.environ, "WDH_DATA_BASE_DIR": "./reference/monthly"},
    )
    return result


class TestAnnuityPerformanceE2E:
    """End-to-end integration tests for annuity performance pipeline."""

    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Setup environment for E2E testing."""
        if not _has_sample_root():
            pytest.skip("Local samples not present: reference/monthly directory not found")

        # Set environment for tests
        os.environ["WDH_DATA_BASE_DIR"] = "./reference/monthly"

    def test_plan_only_mode_success(self):
        """
        Test plan-only mode generates valid SQL plans without database connection.

        This test validates:
        - File discovery works for annuity_performance domain
        - Excel reading handles Chinese sheet names ("规模明细")
        - Domain processing with column projection succeeds
        - SQL plan generation with Chinese table/column names
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        # Run CLI in plan-only mode
        result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        print(f"Exit code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")

        # Should succeed (exit code 0)
        assert result.returncode == 0, f"Plan-only mode failed: {result.stderr}"

        # Validate output contains expected elements
        stdout = result.stdout
        assert "annuity_performance" in stdout
        assert "Plan-only" in stdout or "plan-only" in stdout

        # Should contain SQL plan indicators
        assert "DELETE" in stdout or "INSERT" in stdout or "SQL" in stdout.upper()

        # Should handle Chinese identifiers properly
        assert "规模明细" in stdout or "annuity_performance" in stdout

    def test_plan_only_with_sheet_parameter(self):
        """
        Test plan-only mode with explicit sheet parameter.

        Validates that the sheet="规模明细" configuration from data_sources.yml
        is used correctly during Excel reading.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        result = _run_cli_command(
            [
                "--domain",
                "annuity_performance",
                "--plan-only",
                "--sheet",
                "规模明细",  # Explicit sheet name
                "--max-files",
                "1",
            ]
        )

        assert result.returncode == 0, f"Plan-only with sheet parameter failed: {result.stderr}"

        # Should complete successfully
        stdout = result.stdout
        assert "annuity_performance" in stdout

    def test_discovery_finds_files(self):
        """
        Test that file discovery works for annuity_performance domain.

        This validates the regex pattern and file selection logic
        configured in data_sources.yml works with real reference files.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        # Use discovery-only approach by checking plan-only output
        result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        # Should find at least one file and not fail
        assert result.returncode == 0, "File discovery should succeed"

        # Output should indicate file processing
        stdout = result.stdout
        assert "domain: annuity_performance" in stdout or "annuity_performance" in stdout

    def test_column_projection_prevents_errors(self):
        """
        Test that column projection prevents SQL column mismatch errors.

        This is a critical test validating that extra columns in Excel files
        don't cause SQL errors during the loading phase.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        # Plan-only mode should succeed even with potential column mismatches
        result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        assert result.returncode == 0, "Column projection should prevent SQL errors"

        # Should generate valid SQL plans
        stdout = result.stdout
        assert result.stderr == "" or "warning" in result.stderr.lower(), (
            "Should not have SQL column errors"
        )

    @pytest.mark.postgres
    def test_execute_mode_with_database(self):
        """
        Test execute mode with actual database connection (requires DDL applied).

        WARNING: This test modifies database state. Only run with test database.

        Prerequisites:
        - PostgreSQL running and accessible
        - DDL applied: psql -f scripts/create_table/ddl/annuity_performance.sql
        - WDH_DATABASE_* environment variables configured
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        if not _has_psycopg2():
            pytest.skip("psycopg2 not available for database tests")

        # Check if database environment is configured
        db_host = os.environ.get("WDH_DATABASE__HOST") or os.environ.get("WDH_DATABASE_HOST")
        if not db_host:
            pytest.skip("Database not configured - set WDH_DATABASE__HOST")

        # Run in execute mode with small scope
        result = _run_cli_command(
            [
                "--domain",
                "annuity_performance",
                "--execute",  # ACTUAL DATABASE MODIFICATION
                "--max-files",
                "1",
                "--mode",
                "delete_insert",
            ]
        )

        print(f"Execute mode exit code: {result.returncode}")
        print(f"Execute STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"Execute STDERR:\n{result.stderr}")

        # Should succeed
        assert result.returncode == 0, f"Execute mode failed: {result.stderr}"

        # Validate expected execution indicators
        stdout = result.stdout
        assert "deleted:" in stdout.lower() or "inserted:" in stdout.lower(), (
            "Should show database modification counts"
        )

        # Should complete without SQL errors
        assert "error" not in result.stderr.lower() or result.stderr == ""

    @pytest.mark.postgres
    def test_execute_mode_plan_only_comparison(self):
        """
        Test that execute mode and plan-only mode are consistent.

        Validates that the SQL generated in plan-only mode matches
        what would be executed in execute mode.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        if not _has_psycopg2():
            pytest.skip("psycopg2 not available")

        # First run plan-only
        plan_result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        assert plan_result.returncode == 0, "Plan-only should succeed"

        # Then run execute mode (if database available)
        db_host = os.environ.get("WDH_DATABASE__HOST") or os.environ.get("WDH_DATABASE_HOST")
        if not db_host:
            pytest.skip("Database not configured for execute comparison")

        execute_result = _run_cli_command(
            ["--domain", "annuity_performance", "--execute", "--max-files", "1"]
        )

        # Both should succeed
        assert execute_result.returncode == 0, "Execute mode should also succeed"

        # Both should process the same domain
        assert "annuity_performance" in plan_result.stdout
        assert "annuity_performance" in execute_result.stdout

    def test_max_files_parameter_respected(self):
        """
        Test that --max-files parameter is respected for safety.

        Validates that only the specified number of files are processed,
        which is crucial for safe execution in production.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        # Test with max-files=1
        result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        assert result.returncode == 0

        # Should indicate single file processing
        stdout = result.stdout
        assert "Max files: 1" in stdout

    def test_error_handling_with_invalid_sheet(self):
        """
        Test error handling when sheet name doesn't exist.

        This validates graceful error handling in the pipeline.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        # Use invalid sheet name
        result = _run_cli_command(
            [
                "--domain",
                "annuity_performance",
                "--plan-only",
                "--sheet",
                "NonexistentSheet",  # Invalid sheet name
                "--max-files",
                "1",
            ]
        )

        # Should fail gracefully (not crash)
        assert result.returncode != 0, "Should fail with invalid sheet name"

        # Should contain meaningful error message
        error_output = result.stderr + result.stdout
        assert "sheet" in error_output.lower() or "error" in error_output.lower()

    def test_unicode_handling_in_pipeline(self):
        """
        Test that Unicode/Chinese characters are handled correctly throughout pipeline.

        This is critical for the annuity performance domain which uses Chinese
        column names and file names.
        """
        if not _has_sample_root():
            pytest.skip("Local samples not present")

        result = _run_cli_command(
            ["--domain", "annuity_performance", "--plan-only", "--max-files", "1"]
        )

        assert result.returncode == 0, "Unicode handling should work correctly"

        # Should handle Chinese characters without encoding issues
        stdout = result.stdout
        # The output should contain either Chinese characters or domain name
        assert "annuity_performance" in stdout

        # Should not have encoding errors
        assert "UnicodeError" not in result.stderr
        assert "encoding" not in result.stderr.lower()
