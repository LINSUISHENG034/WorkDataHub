"""
Tests for Dagster schedules in WorkDataHub orchestration.

This module tests the schedule configuration and ensures that the generated
run_config matches the expected op schemas defined in ops.py.

NOTE: Tests skipped pending Epic 5 infrastructure refactoring.
Tests depend on deprecated trustee_performance schedules.
"""

from unittest.mock import patch

import pytest
import yaml

from src.work_data_hub.orchestration.schedules import (
    _build_schedule_run_config,
    trustee_daily_schedule,
)

pytestmark = pytest.mark.skip(reason="Tests depend on deprecated trustee_performance schedules - pending Epic 5")


class TestScheduleRunConfig:
    """Test schedule run_config building functionality."""

    def test_build_schedule_run_config_success(self, tmp_path):
        """Test successful schedule run config building with valid configuration."""
        # Create test configuration matching data_sources.yml structure
        config_data = {
            "domains": {
                "sample_trustee_performance": {
                    "table": "sample_trustee_performance",
                    "pk": ["report_date", "plan_code", "company_code"],
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Mock get_settings to use test config file
        with patch("src.work_data_hub.orchestration.schedules.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            result = _build_schedule_run_config()

            # Verify structure matches expected op config schemas
            expected = {
                "ops": {
            "discover_files_op": {"config": {"domain": "sample_trustee_performance"}},
                    "read_and_process_trustee_files_op": {"config": {"sheet": 0, "max_files": 5}},
                    "load_op": {
                        "config": {
                            "table": "sample_trustee_performance",
                            "mode": "delete_insert",
                            "pk": ["report_date", "plan_code", "company_code"],
                            "plan_only": False,  # Execute mode for scheduled runs
                        }
                    },
                }
            }

            assert result == expected

    def test_build_schedule_run_config_fallback(self, tmp_path):
        """Test schedule run config building with fallback values."""
        # Create config without table/pk info to test fallbacks
        config_data = {"domains": {"trustee_performance": {}}}

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with patch("src.work_data_hub.orchestration.schedules.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            result = _build_schedule_run_config()

            # Verify fallback values are used
            load_config = result["ops"]["load_op"]["config"]
            assert load_config["table"] == "sample_trustee_performance"
            assert load_config["pk"] == ["report_date", "plan_code", "company_code"]
            assert load_config["mode"] == "delete_insert"
            assert load_config["plan_only"] is False

            # Verify other ops have correct config
            discover_config = result["ops"]["discover_files_op"]["config"]
            assert discover_config["domain"] == "sample_trustee_performance"

            read_config = result["ops"]["read_and_process_trustee_files_op"]["config"]
            assert read_config["sheet"] == 0
            assert read_config["max_files"] == 5

    def test_build_schedule_run_config_error_handling(self):
        """Test schedule run config building with config file errors."""
        with patch("src.work_data_hub.orchestration.schedules.get_settings") as mock_settings:
            # Simulate config file not found
            mock_settings.return_value.data_sources_config = "nonexistent.yml"

            # Should handle error gracefully and use fallback values
            result = _build_schedule_run_config()

            load_config = result["ops"]["load_op"]["config"]
            assert load_config["table"] == "sample_trustee_performance"
            assert load_config["pk"] == ["report_date", "plan_code", "company_code"]

    def test_build_schedule_run_config_execution_mode(self, tmp_path):
        """Test that schedule always configures execution mode (plan_only=False)."""
        config_data = {"domains": {"sample_trustee_performance": {"table": "test_table", "pk": ["id"]}}}

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with patch("src.work_data_hub.orchestration.schedules.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            result = _build_schedule_run_config()

            # Verify schedule always uses execute mode
            load_config = result["ops"]["load_op"]["config"]
            assert load_config["plan_only"] is False
            assert load_config["mode"] == "delete_insert"


class TestTrusteeSchedule:
    """Test trustee daily schedule configuration."""

    def test_trustee_daily_schedule_configuration(self):
        """Test that the trustee daily schedule has correct configuration."""
        # Access the schedule's configuration
        schedule = trustee_daily_schedule

        # Verify schedule properties
        assert schedule.cron_schedule == "0 2 * * *"  # 02:00 daily
        assert schedule.execution_timezone == "Asia/Shanghai"

        # Verify the job is correctly configured
        from src.work_data_hub.orchestration.jobs import sample_trustee_performance_multi_file_job

        assert schedule.job == sample_trustee_performance_multi_file_job

    def test_trustee_daily_schedule_run_config_generation(self, tmp_path):
        """Test that the schedule generates valid run_config when executed."""
        # Create test configuration
        config_data = {
            "domains": {
                "trustee_performance": {
                    "table": "trustee_performance",
                    "pk": ["report_date", "plan_code", "company_code"],
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Mock context (schedule functions receive context as first parameter)
        mock_context = None  # Schedule function doesn't use context currently

        with patch("src.work_data_hub.orchestration.schedules.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            # Call the schedule function
            result = trustee_daily_schedule(mock_context)

            # Verify the result is a valid run_config
            assert "ops" in result
            assert "discover_files_op" in result["ops"]
            assert "read_and_process_trustee_files_op" in result["ops"]
            assert "load_op" in result["ops"]

            # Verify specific configuration values for scheduled execution
            load_config = result["ops"]["load_op"]["config"]
            assert load_config["plan_only"] is False  # Execute mode
            assert load_config["mode"] == "delete_insert"  # Data consistency
