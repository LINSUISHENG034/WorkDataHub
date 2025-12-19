"""
Tests for Dagster sensors in WorkDataHub orchestration.

This module tests sensor logic, cursor management, and health check functionality
for the trustee performance file discovery and data quality sensors.

NOTE: Tests skipped pending Epic 5 infrastructure refactoring.
Tests depend on deprecated trustee_performance sensors.
"""

from unittest.mock import patch

import pytest
import yaml
from dagster import RunRequest, SkipReason, build_sensor_context

from src.work_data_hub.orchestration.sensors import (
    _build_sensor_run_config,
    trustee_data_quality_sensor,
    trustee_new_files_sensor,
)
from src.work_data_hub.utils.types import DiscoveredFile

pytestmark = pytest.mark.skip(
    reason="Tests depend on deprecated sensors - pending Epic 5"
)


class TestSensorRunConfig:
    """Test sensor run_config building functionality."""

    def test_build_sensor_run_config_success(self, tmp_path):
        """Test successful sensor run config building with valid configuration."""
        # Create test configuration matching data_sources.yml structure
        config_data = {
            "domains": {
                "sandbox_trustee_performance": {
                    "table": "sandbox_trustee_performance",
                    "pk": ["report_date", "plan_code", "company_code"],
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Mock get_settings to use test config file
        with patch(
            "src.work_data_hub.orchestration.sensors.get_settings"
        ) as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            result = _build_sensor_run_config()

            # Verify structure matches expected op config schemas
            expected = {
                "ops": {
                    "discover_files_op": {
                        "config": {"domain": "sandbox_trustee_performance"}
                    },
                    "read_and_process_sandbox_trustee_files_op": {
                        "config": {"sheet": 0, "max_files": 5}
                    },
                    "load_op": {
                        "config": {
                            "table": "sandbox_trustee_performance",
                            "mode": "delete_insert",
                            "pk": ["report_date", "plan_code", "company_code"],
                            "plan_only": False,  # Execute mode for sensor runs
                        }
                    },
                }
            }

            assert result == expected


class TestFileDiscoverySensor:
    """Test file discovery sensor functionality."""

    def create_mock_discovered_file(self, path, modified_time):
        """Helper to create mock DiscoveredFile objects."""
        return DiscoveredFile(
            domain="sandbox_trustee_performance",
            path=path,
            year=2024,
            month=1,
            metadata={"modified_time": modified_time},
        )

    def test_new_files_sensor_no_files_found(self):
        """Test sensor behavior when no files are discovered."""
        # Use Dagster's build_sensor_context for proper context
        context = build_sensor_context()

        # Mock DataSourceConnector to return empty list
        with patch(
            "src.work_data_hub.orchestration.sensors.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = []

            result = trustee_new_files_sensor(context)

            assert isinstance(result, SkipReason)
            assert "No sandbox_trustee_performance files found" in str(result)

    def test_new_files_sensor_no_new_files(self):
        """Test sensor behavior when no new files since last cursor."""
        # Create context with existing cursor
        context = build_sensor_context(cursor="1000.0")

        # Create mock files that are older than cursor
        old_files = [
            self.create_mock_discovered_file("old_file1.xlsx", 500.0),
            self.create_mock_discovered_file("old_file2.xlsx", 800.0),
        ]

        with patch(
            "src.work_data_hub.orchestration.sensors.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = old_files

            result = trustee_new_files_sensor(context)

            assert isinstance(result, SkipReason)
            assert "No new files detected" in str(result)
            assert "last_mtime: 1000.0" in str(result)
            assert "total_files: 2" in str(result)

    def test_new_files_sensor_with_new_files(self, tmp_path):
        """Test sensor behavior when new files are detected."""
        # Create context with existing cursor
        context = build_sensor_context(cursor="500.0")

        # Create mock files with newer modification times
        new_files = [
            self.create_mock_discovered_file("new_file1.xlsx", 1000.0),
            self.create_mock_discovered_file("new_file2.xlsx", 1200.0),
        ]

        # Create test configuration for run_config building
        config_data = {
            "domains": {
                "sandbox_trustee_performance": {
                    "table": "sandbox_trustee_performance",
                    "pk": ["report_date", "plan_code", "company_code"],
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with (
            patch(
                "src.work_data_hub.orchestration.sensors.DataSourceConnector"
            ) as mock_connector_class,
            patch(
                "src.work_data_hub.orchestration.sensors.get_settings"
            ) as mock_settings,
        ):
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = new_files
            mock_settings.return_value.data_sources_config = str(config_file)

            result = trustee_new_files_sensor(context)

            # Verify RunRequest is returned
            assert isinstance(result, RunRequest)
            assert result.run_key == "new_files_1200.0"  # Max modification time

            # Verify run_config is properly structured
            assert "ops" in result.run_config
            assert (
                result.run_config["ops"]["discover_files_op"]["config"]["domain"]
                == "sandbox_trustee_performance"
            )

    def test_new_files_sensor_first_run_no_cursor(self, tmp_path):
        """Test sensor behavior on first run with no existing cursor."""
        # Create context with no cursor (first run)
        context = build_sensor_context()

        # Create mock files
        files = [
            self.create_mock_discovered_file("file1.xlsx", 1000.0),
        ]

        # Create test configuration
        config_data = {
            "domains": {
                "sandbox_trustee_performance": {
                    "table": "sandbox_trustee_performance",
                    "pk": ["id"],
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with (
            patch(
                "src.work_data_hub.orchestration.sensors.DataSourceConnector"
            ) as mock_connector_class,
            patch(
                "src.work_data_hub.orchestration.sensors.get_settings"
            ) as mock_settings,
        ):
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = files
            mock_settings.return_value.data_sources_config = str(config_file)

            result = trustee_new_files_sensor(context)

            # Verify RunRequest is returned (all files are "new" on first run)
            assert isinstance(result, RunRequest)

    def test_new_files_sensor_error_handling(self):
        """Test sensor error handling with DataSourceConnector failures."""
        context = build_sensor_context()

        with patch(
            "src.work_data_hub.orchestration.sensors.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.side_effect = Exception("Connection failed")

            result = trustee_new_files_sensor(context)

            # Verify error is handled gracefully
            assert isinstance(result, SkipReason)
            assert "Sensor error: Connection failed" in str(result)


class TestDataQualitySensor:
    """Test data quality sensor functionality."""

    def test_data_quality_sensor_no_files_found(self):
        """Test data quality sensor when no files are discovered."""
        context = build_sensor_context()

        with patch(
            "src.work_data_hub.orchestration.sensors.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = []

            result = trustee_data_quality_sensor(context)

            assert isinstance(result, SkipReason)
            assert "No files found for health check" in str(result)

    def test_data_quality_sensor_file_not_accessible(self):
        """Test data quality sensor when files are not accessible."""
        context = build_sensor_context()

        # Create mock file with non-existent path
        mock_file = DiscoveredFile(
            domain="sandbox_trustee_performance",
            path="/nonexistent/file.xlsx",
            year=2024,
            month=1,
            metadata={"modified_time": 1000.0},
        )

        with (
            patch(
                "src.work_data_hub.orchestration.sensors.DataSourceConnector"
            ) as mock_connector_class,
            patch("pathlib.Path.exists", return_value=False),
        ):
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = [mock_file]

            result = trustee_data_quality_sensor(context)

            assert isinstance(result, SkipReason)
            assert "No accessible files for health check" in str(result)

    def test_data_quality_sensor_successful_health_check(self):
        """Test data quality sensor with successful health check."""
        context = build_sensor_context()

        # Create mock accessible file
        mock_file = DiscoveredFile(
            domain="sandbox_trustee_performance",
            path="/test/file.xlsx",
            year=2024,
            month=1,
            metadata={"modified_time": 1000.0},
        )

        with (
            patch(
                "src.work_data_hub.orchestration.sensors.DataSourceConnector"
            ) as mock_connector_class,
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "src.work_data_hub.orchestration.sensors.build_insert_sql"
            ) as mock_build_sql,
        ):
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = [mock_file]

            # Mock successful SQL building
            mock_build_sql.return_value = ("INSERT INTO table...", ["param1", "param2"])

            result = trustee_data_quality_sensor(context)

            assert isinstance(result, SkipReason)
            assert "Data quality health check completed successfully" in str(result)
            assert "1 files, 1 accessible" in str(result)

            # Verify health check components were called
            mock_build_sql.assert_called_once()

    def test_data_quality_sensor_sql_probe_failure(self):
        """Test data quality sensor when SQL probe fails."""
        context = build_sensor_context()

        # Create mock accessible file
        mock_file = DiscoveredFile(
            domain="sandbox_trustee_performance",
            path="/test/file.xlsx",
            year=2024,
            month=1,
            metadata={"modified_time": 1000.0},
        )

        with (
            patch(
                "src.work_data_hub.orchestration.sensors.DataSourceConnector"
            ) as mock_connector_class,
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "src.work_data_hub.orchestration.sensors.build_insert_sql"
            ) as mock_build_sql,
        ):
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.return_value = [mock_file]

            # Mock SQL building returning None (failure case)
            mock_build_sql.return_value = (None, [])

            result = trustee_data_quality_sensor(context)

            assert isinstance(result, SkipReason)
            assert "DATA QUALITY ALERT: Plan-only probe failed" in str(result)

    def test_data_quality_sensor_exception_handling(self):
        """Test data quality sensor exception handling."""
        context = build_sensor_context()

        with patch(
            "src.work_data_hub.orchestration.sensors.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector = mock_connector_class.return_value
            mock_connector.discover.side_effect = Exception("Critical error")

            result = trustee_data_quality_sensor(context)

            assert isinstance(result, SkipReason)
            assert "Sensor error: Critical error" in str(result)
