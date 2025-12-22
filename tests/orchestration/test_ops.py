"""
Unit tests for Dagster ops.

This module tests each op individually with mock data and validates that they
handle inputs correctly, produce JSON-serializable outputs, and implement
proper error handling and logging.
"""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import ANY, Mock, patch

import pandas as pd
import pytest
import yaml
from dagster import build_op_context

from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError
from work_data_hub.orchestration.ops import (
    BackfillRefsConfig,
    DiscoverFilesConfig,
    LoadConfig,
    ProcessingConfig,
    ReadExcelConfig,
    ReadProcessConfig,
    _load_valid_domains,
    backfill_refs_op,
    derive_plan_refs_op,
    derive_portfolio_refs_op,
    discover_files_op,
    load_op,
    process_annuity_income_op,
    process_annuity_performance_op,
    process_sandbox_trustee_performance_op,
    read_and_process_sandbox_trustee_files_op,
    read_excel_op,
)


class TestDiscoverFilesOp:
    """Test discover_files_op functionality."""

    def test_discover_files_op_epic3_schema_routes_to_file_discovery_service(self, tmp_path):
        """Test Epic 3 schema discovery routes to FileDiscoveryService (AC2).

        Validates that domains with Epic 3 schema (base_path, file_patterns) use
        FileDiscoveryService.discover_file() instead of legacy DataSourceConnector.
        """
        from pathlib import Path
        from unittest.mock import MagicMock

        # Mock the DiscoveryMatch result
        mock_match = MagicMock()
        mock_match.file_path = Path("/mock/path/test_file.xlsx")
        mock_match.version = "V2"
        mock_match.sheet_name = "规模明细"

        # Mock FileDiscoveryService - patch where it's used, not where it's defined
        with patch("work_data_hub.orchestration.ops.file_processing.FileDiscoveryService") as mock_fds_class:
            mock_fds = MagicMock()
            mock_fds.discover_file.return_value = mock_match
            mock_fds_class.return_value = mock_fds

            # Mock get_settings and yaml loading
            with patch("work_data_hub.orchestration.ops.file_processing.get_settings") as mock_settings:
                mock_settings.return_value.data_sources_config = str(tmp_path / "config.yml")

                # Create mock Epic 3 schema config
                config_data = {
                    "domains": {
                        "annuity_performance": {
                            "base_path": "tests/fixtures/{YYYYMM}",
                            "file_patterns": ["*.xlsx"],
                            "version_strategy": "latest_version_dir",
                            "sheet_name": "规模明细",
                        }
                    }
                }
                config_file = tmp_path / "config.yml"
                with open(config_file, "w", encoding="utf-8") as f:
                    yaml.dump(config_data, f)

                context = build_op_context()
                config = DiscoverFilesConfig(domain="annuity_performance", period="202510")

                result = discover_files_op(context, config)

                # Verify FileDiscoveryService was used (not DataSourceConnector)
                mock_fds_class.assert_called_once()
                mock_fds.discover_file.assert_called_once_with(
                    domain="annuity_performance",
                    selection_strategy=ANY,
                    YYYYMM="202510"
                )

                # Verify result is list of string paths
                assert result == [str(mock_match.file_path)]
                assert isinstance(result[0], str)

    def test_discover_files_op_legacy_schema_raises_error(self, tmp_path):
        """Test legacy schema discovery raises ValueError (Zero Legacy Policy).

        After DataSourceConnector removal, domains with legacy schema (pattern, select)
        should raise an error directing users to migrate to Epic 3 schema.
        """
        # Mock get_settings and yaml loading
        with patch("work_data_hub.orchestration.ops.file_processing.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(tmp_path / "config.yml")

            # Create mock legacy schema config (pattern/select instead of base_path/file_patterns)
            config_data = {
                "domains": {
                    "sandbox_trustee_performance": {
                        "pattern": ".*trustee.*\\.xlsx",
                        "select": "latest_by_mtime",
                        "table": "sandbox_trustee_performance",
                    }
                }
            }
            config_file = tmp_path / "config.yml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            context = build_op_context()
            config = DiscoverFilesConfig(domain="sandbox_trustee_performance")

            # Legacy schema should raise error after DataSourceConnector removal
            with pytest.raises(ValueError, match="Legacy.*removed"):
                discover_files_op(context, config)

    def test_discover_files_op_invalid_domain(self):
        """Test that invalid domain raises ValidationError."""
        with pytest.raises(ValueError, match="Domain 'invalid' not supported"):
            DiscoverFilesConfig(domain="invalid")

    def test_discover_files_op_missing_period(self):
        """Test that missing period parameter raises error for Epic 3 domains."""
        # annuity_performance requires period parameter (has {YYYYMM} in base_path)
        context = build_op_context()
        config = DiscoverFilesConfig(domain="annuity_performance")  # No period provided

        with pytest.raises(ValueError, match="requires --period parameter"):
            discover_files_op(context, config)

    def test_discover_files_op_invalid_period_format(self, tmp_path):
        """Test that invalid period format raises error (AC3 validation)."""
        # Mock get_settings and yaml loading for Epic 3 schema domain
        with patch("work_data_hub.orchestration.ops.file_processing.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(tmp_path / "config.yml")

            # Create mock Epic 3 schema config
            config_data = {
                "domains": {
                    "annuity_performance": {
                        "base_path": "tests/fixtures/{YYYYMM}",
                        "file_patterns": ["*.xlsx"],
                        "version_strategy": "latest_version_dir",
                        "sheet_name": "规模明细",
                    }
                }
            }
            config_file = tmp_path / "config.yml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            # Mock FileDiscoveryService to raise ValueError for invalid period
            with patch("work_data_hub.orchestration.ops.file_processing.FileDiscoveryService") as mock_fds_class:
                mock_fds = Mock()
                mock_fds.discover_file.side_effect = ValueError(
                    "Template variable {YYYYMM} must be 6 digits (YYYYMM)"
                )
                mock_fds_class.return_value = mock_fds

                context = build_op_context()

                # Test with invalid period format (too short)
                config = DiscoverFilesConfig(domain="annuity_performance", period="2025")

                with pytest.raises(ValueError, match="6 digits"):
                    discover_files_op(context, config)


class TestReadExcelOp:
    """Test read_excel_op functionality."""

    def test_read_excel_op_success(self, tmp_path):
        """Test successful Excel reading with metadata logging."""
        # Create test Excel file
        test_data = pd.DataFrame(
            {
                "年": ["2024", "2024"],
                "月": ["11", "11"],
                "计划代码": ["PLAN001", "PLAN002"],
            }
        )

        test_file = tmp_path / "test.xlsx"
        test_data.to_excel(test_file, index=False, engine="openpyxl")

        # Mock read_excel_rows
        expected_rows = [
            {"年": "2024", "月": "11", "计划代码": "PLAN001"},
            {"年": "2024", "月": "11", "计划代码": "PLAN002"},
        ]

        with patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read:
            mock_read.return_value = expected_rows

            context = build_op_context()
            config = ReadExcelConfig(sheet=0)
            result = read_excel_op(context, config, [str(test_file)])

            assert result == expected_rows
            # Verify result is JSON-serializable
            json.dumps(result)

            # Verify read_excel_rows was called with correct parameters
            mock_read.assert_called_once_with(str(test_file), sheet=0)

    def test_read_excel_config_validation(self):
        """Test ReadExcelConfig validation."""
        # Valid config
        config = ReadExcelConfig(sheet=0)
        assert config.sheet == 0

        # Invalid negative sheet
        with pytest.raises(ValueError, match="Sheet index must be non-negative"):
            ReadExcelConfig(sheet=-1)

    def test_read_excel_op_empty_file(self, tmp_path):
        """Test reading empty Excel file."""
        test_file = tmp_path / "empty.xlsx"
        pd.DataFrame().to_excel(test_file, index=False, engine="openpyxl")

        with patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read:
            mock_read.return_value = []

            context = build_op_context()
            config = ReadExcelConfig()
            result = read_excel_op(context, config, [str(test_file)])

            assert result == []

    def test_read_excel_op_empty_file_list(self):
        """Test reading with empty file list."""
        context = build_op_context()
        config = ReadExcelConfig()
        result = read_excel_op(context, config, [])

        assert result == []


class TestProcessTrusteePerformanceOp:
    """Test process_sandbox_trustee_performance_op functionality."""

    def test_process_sandbox_trustee_performance_op_success(self):
        """Test successful domain processing."""
        # Mock input data
        excel_rows = [
            {"年": "2024", "月": "11", "计划代码": "PLAN001", "收益率": "5.5%"}
        ]

        # Mock processed result
        mock_model = Mock()
        mock_model.model_dump.return_value = {
            "report_date": "2024-11-01",
            "plan_code": "PLAN001",
            "return_rate": "0.055",
        }

        with patch("work_data_hub.orchestration.ops.pipeline_ops.process") as mock_process:
            mock_process.return_value = [mock_model]

            context = build_op_context()
            result = process_sandbox_trustee_performance_op(
                context, excel_rows, ["/path/to/file.xlsx"]
            )

            assert len(result) == 1
            assert result[0]["plan_code"] == "PLAN001"

            # Verify result is JSON-serializable
            json.dumps(result)

            # Verify process was called correctly
            mock_process.assert_called_once_with(
                excel_rows, data_source="/path/to/file.xlsx"
            )

    def test_process_sandbox_trustee_performance_op_empty_data(self):
        """Test processing empty data."""
        with patch("work_data_hub.orchestration.ops.pipeline_ops.process") as mock_process:
            mock_process.return_value = []

            context = build_op_context()
            result = process_sandbox_trustee_performance_op(
                context, [], ["/path/to/file.xlsx"]
            )

            assert result == []

    def test_process_sandbox_trustee_performance_op_empty_file_paths(self):
        """Test processing with empty file paths."""
        excel_rows = [{"年": "2024", "月": "11", "计划代码": "PLAN001"}]

        with patch("work_data_hub.orchestration.ops.pipeline_ops.process") as mock_process:
            mock_process.return_value = []

            context = build_op_context()
            result = process_sandbox_trustee_performance_op(context, excel_rows, [])

            assert result == []
            # Should use "unknown" as data_source when no file paths provided
            mock_process.assert_called_once_with(excel_rows, data_source="unknown")


class TestLoadOp:
    """Test load_op functionality."""

    def test_load_op_plan_only_mode(self):
        """Test load_op generates SQL plans without database."""
        processed_rows = [
            {
                "report_date": date(2024, 11, 1),
                "plan_code": "PLAN001",
                "company_code": "COMP01",
                "return_rate": Decimal("0.055"),
            }
        ]

        # Mock the load function result
        mock_result = {
            "mode": "delete_insert",
            "table": "sandbox_trustee_performance",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
            "sql_plans": [
                ("DELETE", "DELETE FROM ...", []),
                ("INSERT", "INSERT INTO ...", []),
            ],
        }

        with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
            mock_load.return_value = mock_result

            context = build_op_context()
            config = LoadConfig(plan_only=True)
            result = load_op(context, config, processed_rows)

            assert result["mode"] == "delete_insert"
            assert "sql_plans" in result

            # Verify result is JSON-serializable
            json.dumps(result, default=str)  # Use str for datetime objects

    def test_load_config_validation(self):
        """Test LoadConfig validation."""
        # Valid config
        config = LoadConfig(
            table="test_table", mode="delete_insert", pk=["id"], plan_only=True
        )
        assert config.table == "test_table"

        # Invalid mode
        with pytest.raises(ValueError, match="Mode 'invalid' not supported"):
            LoadConfig(mode="invalid")

        # delete_insert without pk
        with pytest.raises(ValueError, match="delete_insert mode requires primary key"):
            LoadConfig(mode="delete_insert", pk=[])

    def test_load_op_append_mode(self):
        """Test load_op in append mode."""
        processed_rows = [{"col1": "value1"}]

        mock_result = {
            "mode": "append",
            "table": "test_table",
            "deleted": 0,
            "inserted": 1,
            "batches": 1,
        }

        with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
            mock_load.return_value = mock_result

            context = build_op_context()
            config = LoadConfig(mode="append", pk=[], plan_only=True)
            result = load_op(context, config, processed_rows)

            assert result["mode"] == "append"
            assert result["deleted"] == 0

    def test_load_valid_domains_from_yaml(self, tmp_path):
        """Test _load_valid_domains loads from YAML correctly."""
        config_data = {
            "domains": {
                "sandbox_trustee_performance": {
                    "table": "sandbox_trustee_performance"
                },
                "annuity_performance": {"table": "annuity_performance"},
            }
        }
        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with patch("work_data_hub.orchestration.ops._internal.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            domains = _load_valid_domains()

            assert domains == ["annuity_performance", "sandbox_trustee_performance"]

    @pytest.mark.skip(
        reason="Test depends on deprecated domain config - pending Epic 5"
    )
    def test_load_valid_domains_missing_file(self, tmp_path):
        """Test _load_valid_domains handles missing config file gracefully."""
        missing_file = tmp_path / "nonexistent.yml"

        with patch("work_data_hub.orchestration.ops._internal.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(missing_file)

            domains = _load_valid_domains()

            # Should fallback to default
            assert domains == ["sandbox_trustee_performance"]

    def test_load_valid_domains_empty_config(self, tmp_path):
        """Test _load_valid_domains handles empty domains gracefully."""
        config_data = {"domains": {}}
        config_file = tmp_path / "empty_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with patch("work_data_hub.orchestration.ops._internal.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            domains = _load_valid_domains()

            # Should fallback to default when no domains found
            assert domains == ["sandbox_trustee_performance"]

    def test_load_valid_domains_invalid_yaml(self, tmp_path):
        """Test _load_valid_domains handles invalid YAML gracefully."""
        config_file = tmp_path / "invalid.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [")

        with patch("work_data_hub.orchestration.ops._internal.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            domains = _load_valid_domains()

            # Should fallback to default on YAML parse error
            assert domains == ["sandbox_trustee_performance"]

    def test_load_op_execute_mode_mocked(self):
        """Test load_op with execute=True using mocked psycopg2."""
        processed_rows = [{"col": "value", "id": 1}]  # Add missing id field

        mock_conn = Mock()
        mock_result = {
            "mode": "delete_insert",
            "table": "test_table",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_db = Mock()
                    mock_db.get_connection_string.return_value = "postgresql://test"
                    mock_settings.return_value.database = mock_db

                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test_table", pk=["id"])
                    result = load_op(context, config, processed_rows)

                    # Verify bare connection was used
                    mock_psycopg2.connect.assert_called_once_with("postgresql://test")

                    # Verify load was called with bare connection
                    mock_load.assert_called_once_with(
                        table="test_table",
                        rows=processed_rows,
                        mode="delete_insert",
                        pk=["id"],
                        conn=mock_conn,
                    )

                    # Verify connection cleanup
                    mock_conn.close.assert_called_once()
                    assert result == mock_result

    def test_load_op_execute_mode_psycopg2_not_available(self):
        """Test load_op with execute=True when psycopg2 is not available."""
        processed_rows = [{"col": "value", "id": 1}]  # Add missing id field

        # Mock psycopg2 module to be None (simulating ImportError at module level)
        with patch("work_data_hub.orchestration.ops.loading.psycopg2", None):
            context = build_op_context()
            config = LoadConfig(plan_only=False, table="test_table", pk=["id"])

            with pytest.raises(DataWarehouseLoaderError) as exc_info:
                load_op(context, config, processed_rows)

            assert "psycopg2 not available for database operations" in str(
                exc_info.value
            )

    def test_load_op_execute_mode_connection_failed(self):
        """Test load_op with execute=True when database connection fails."""
        processed_rows = [{"col": "value"}]

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Connection refused")

            with patch(
                "work_data_hub.orchestration.ops.loading.get_settings"
            ) as mock_settings:
                mock_db = Mock()
                mock_db.get_connection_string.return_value = "postgresql://test"
                mock_settings.return_value.database = mock_db

                context = build_op_context()
                config = LoadConfig(plan_only=False, table="test_table", pk=["id"])

                with pytest.raises(Exception) as exc_info:
                    load_op(context, config, processed_rows)

                assert "Database connection failed" in str(exc_info.value)
                assert "WDH_DATABASE__" in str(exc_info.value)


class TestReadProcessConfig:
    """Test ReadProcessConfig validation."""

    def test_read_process_config_valid(self):
        """Test valid ReadProcessConfig creation."""
        config = ReadProcessConfig(sheet=1, max_files=5)
        assert config.sheet == 1
        assert config.max_files == 5

    def test_read_process_config_defaults(self):
        """Test ReadProcessConfig default values."""
        config = ReadProcessConfig()
        assert config.sheet == 0
        assert config.max_files == 1

    def test_read_process_config_sheet_validation(self):
        """Test sheet validation in ReadProcessConfig."""
        # Valid sheet
        config = ReadProcessConfig(sheet=0)
        assert config.sheet == 0

        # Invalid negative sheet
        with pytest.raises(ValueError, match="Sheet index must be non-negative"):
            ReadProcessConfig(sheet=-1)

    def test_read_process_config_max_files_validation(self):
        """Test max_files validation in ReadProcessConfig."""
        # Valid max_files
        config = ReadProcessConfig(max_files=10)
        assert config.max_files == 10

        # Invalid - too small
        with pytest.raises(ValueError, match="max_files must be at least 1"):
            ReadProcessConfig(max_files=0)

        # Invalid - too large
        with pytest.raises(ValueError, match="max_files cannot exceed 20"):
            ReadProcessConfig(max_files=25)


@pytest.mark.skip(
    reason="Tests depend on deprecated trustee_performance ops - pending Epic 5"
)
class TestReadAndProcessTrusteeFilesOp:
    """Test read_and_process_trustee_files_op functionality."""

    def test_read_and_process_trustee_files_op_multi_file(self):
        """Test combined op processes multiple files and accumulates correctly."""
        file_paths = ["/path/file1.xlsx", "/path/file2.xlsx"]
        config = ReadProcessConfig(sheet=0, max_files=2)

        # Mock read_excel_rows and process functions
        with (
            patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read,
            patch("work_data_hub.orchestration.ops.file_processing.process") as mock_process,
        ):
            # Configure mock returns for each file
            mock_read.side_effect = [
                [{"col": "data1"}],  # File 1 rows
                [{"col": "data2"}],  # File 2 rows
            ]

            # Mock model objects with model_dump method
            mock_model1 = Mock()
            mock_model1.model_dump.return_value = {"processed": "data1"}
            mock_model2 = Mock()
            mock_model2.model_dump.return_value = {"processed": "data2"}

            mock_process.side_effect = [
                [mock_model1],  # File 1 models
                [mock_model2],  # File 2 models
            ]

            context = build_op_context()
            result = read_and_process_trustee_files_op(context, config, file_paths)

            # Verify accumulation worked correctly
            assert len(result) == 2
            assert result[0]["processed"] == "data1"
            assert result[1]["processed"] == "data2"

            # Verify both read_excel_rows calls made
            assert mock_read.call_count == 2
            mock_read.assert_any_call("/path/file1.xlsx", sheet=0)
            mock_read.assert_any_call("/path/file2.xlsx", sheet=0)

            # Verify both process calls made with correct data_source
            assert mock_process.call_count == 2
            mock_process.assert_any_call(
                [{"col": "data1"}], data_source="/path/file1.xlsx"
            )
            mock_process.assert_any_call(
                [{"col": "data2"}], data_source="/path/file2.xlsx"
            )

            # Verify result is JSON-serializable
            json.dumps(result)

    def test_read_and_process_trustee_files_op_max_files_limit(self):
        """Test that max_files parameter correctly limits file processing."""
        file_paths = ["/path/file1.xlsx", "/path/file2.xlsx", "/path/file3.xlsx"]
        config = ReadProcessConfig(sheet=0, max_files=2)  # Limit to 2 files

        with (
            patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read,
            patch("work_data_hub.orchestration.ops.file_processing.process") as mock_process,
        ):
            mock_read.side_effect = [[{"col": "data1"}], [{"col": "data2"}]]

            mock_model = Mock()
            mock_model.model_dump.return_value = {"processed": "data"}
            mock_process.side_effect = [[mock_model], [mock_model]]

            context = build_op_context()
            result = read_and_process_trustee_files_op(context, config, file_paths)

            # Should only process 2 files due to max_files limit
            assert len(result) == 2
            assert mock_read.call_count == 2
            assert mock_process.call_count == 2

    def test_read_and_process_trustee_files_op_empty_files(self):
        """Test combined op with empty file list."""
        config = ReadProcessConfig(sheet=0, max_files=2)

        context = build_op_context()
        result = read_and_process_trustee_files_op(context, config, [])

        assert result == []

    def test_read_and_process_trustee_files_op_single_file(self):
        """Test combined op with single file (backward compatibility)."""
        file_paths = ["/path/file1.xlsx"]
        config = ReadProcessConfig(sheet=1, max_files=1)

        with (
            patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read,
            patch("work_data_hub.orchestration.ops.file_processing.process") as mock_process,
        ):
            mock_read.return_value = [{"col": "data"}]

            mock_model = Mock()
            mock_model.model_dump.return_value = {"processed": "data"}
            mock_process.return_value = [mock_model]

            context = build_op_context()
            result = read_and_process_trustee_files_op(context, config, file_paths)

            assert len(result) == 1
            assert result[0]["processed"] == "data"

            # Verify correct sheet parameter passed
            mock_read.assert_called_once_with("/path/file1.xlsx", sheet=1)

    def test_read_and_process_trustee_files_op_error_handling(self):
        """Test error handling in combined op."""
        file_paths = ["/path/file1.xlsx"]
        config = ReadProcessConfig(sheet=0, max_files=1)

        with patch("work_data_hub.orchestration.ops.file_processing.read_excel_rows") as mock_read:
            mock_read.side_effect = Exception("File read error")

            context = build_op_context()

            with pytest.raises(Exception, match="File read error"):
                read_and_process_trustee_files_op(context, config, file_paths)


class TestLoadOpConnectionLifecycle:
    """Enhanced DB connection lifecycle testing according to PRP P-013."""

    def test_load_op_uses_bare_connection_not_context_manager(self):
        """Verify load_op uses bare connection and lets warehouse_loader handle transactions."""
        processed_rows = [{"col": "value"}]

        mock_conn = Mock()
        mock_result = {
            "mode": "delete_insert",
            "table": "test",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            # CRITICAL: load_op should create bare connection, not use context manager
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"

                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test", pk=["id"])
                    result = load_op(context, config, processed_rows)

                    # Verify bare connection creation (not context manager)
                    mock_psycopg2.connect.assert_called_once_with("postgresql://test")

                    # Verify load was called with bare connection
                    mock_load.assert_called_once_with(
                        table="test",
                        rows=processed_rows,
                        mode="delete_insert",
                        pk=["id"],
                        conn=mock_conn,
                    )

                    # Verify connection cleanup in finally block
                    mock_conn.close.assert_called_once()
                    assert result == mock_result

    def test_load_op_connection_cleanup_on_success(self):
        """Test connection is properly closed on successful execution."""
        processed_rows = [{"col": "value"}]

        mock_conn = Mock()
        mock_result = {
            "mode": "append",
            "table": "test",
            "deleted": 0,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"

                    context = build_op_context()
                    config = LoadConfig(
                        plan_only=False, table="test", mode="append", pk=[]
                    )

                    result = load_op(context, config, processed_rows)

                    # Verify successful execution and cleanup
                    assert result == mock_result
                    mock_conn.close.assert_called_once()

    def test_load_op_connection_cleanup_on_load_failure(self):
        """Test connection is cleaned up even when load operation fails."""
        processed_rows = [{"col": "value"}]

        mock_conn = Mock()

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                # Simulate load operation failure
                mock_load.side_effect = Exception("Load operation failed")

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"

                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test", pk=["id"])

                    with pytest.raises(Exception, match="Load operation failed"):
                        load_op(context, config, processed_rows)

                    # CRITICAL: Connection must be closed even on failure
                    mock_conn.close.assert_called_once()

    def test_load_op_connection_cleanup_on_connection_failure(self):
        """Test no connection cleanup when connection creation fails."""
        processed_rows = [{"col": "value"}]

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            # Simulate connection failure
            mock_psycopg2.connect.side_effect = Exception("Connection refused")

            with patch(
                "work_data_hub.orchestration.ops.loading.get_settings"
            ) as mock_settings:
                mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"

                context = build_op_context()
                config = LoadConfig(plan_only=False, table="test", pk=["id"])

                with pytest.raises(Exception, match="Database connection failed"):
                    load_op(context, config, processed_rows)

                # No connection object created, so no cleanup should be attempted
                # This is validated by the fact that no mock_conn.close was called

    def test_load_op_no_context_manager_nesting_detected(self):
        """Test that load_op avoids context manager nesting by using bare connection."""
        processed_rows = [{"col": "value"}]

        mock_conn = Mock()
        mock_result = {
            "mode": "delete_insert",
            "table": "test",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"

                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test", pk=["id"])

                    load_op(context, config, processed_rows)

                    # Verify that psycopg2.connect was called directly (not as context manager)
                    mock_psycopg2.connect.assert_called_once_with("postgresql://test")

                    # Verify that the connection object has NO __enter__ or __exit__ calls
                    # This confirms no context manager nesting
                    assert (
                        not hasattr(mock_conn, "__enter__")
                        or not mock_conn.__enter__.called
                    )
                    assert (
                        not hasattr(mock_conn, "__exit__")
                        or not mock_conn.__exit__.called
                    )

                    # Verify load was called with bare connection object
                    mock_load.assert_called_once_with(
                        table="test",
                        rows=processed_rows,
                        mode="delete_insert",
                        pk=["id"],
                        conn=mock_conn,
                    )

    def test_load_op_plan_only_mode_no_connection_created(self):
        """Test that plan_only=True doesn't create database connections."""
        processed_rows = [{"col": "value"}]

        mock_result = {
            "mode": "delete_insert",
            "table": "test",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                context = build_op_context()
                config = LoadConfig(
                    plan_only=True, table="test", pk=["id"]
                )  # plan_only=True

                result = load_op(context, config, processed_rows)

                # Verify no database connection was created
                mock_psycopg2.connect.assert_not_called()

                # Verify load was called with conn=None
                mock_load.assert_called_once_with(
                    table="test",
                    rows=processed_rows,
                    mode="delete_insert",
                    pk=["id"],
                    conn=None,
                )
                assert result == mock_result

    def test_load_op_connection_dsn_building(self):
        """Test that connection string is properly built from settings."""
        processed_rows = [{"col": "value"}]

        mock_conn = Mock()
        mock_result = {
            "mode": "append",
            "table": "test",
            "deleted": 0,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    # Test specific DSN format
                    mock_settings.return_value.get_database_connection_string.return_value = "postgresql://user:pass@localhost:5432/testdb"

                    context = build_op_context()
                    config = LoadConfig(
                        plan_only=False, table="test", mode="append", pk=[]
                    )

                    load_op(context, config, processed_rows)

                    # Verify get_database_connection_string was called
                    mock_settings.return_value.get_database_connection_string.assert_called_once()

                    # Verify psycopg2.connect was called with the correct DSN
                    mock_psycopg2.connect.assert_called_once_with(
                        "postgresql://user:pass@localhost:5432/testdb"
                    )

    # Preserve existing tests with legacy names for backward compatibility
    def test_load_op_db_context_manager_mocked(self):
        """Test load_op uses bare connection with fallback DSN resolution."""
        processed_rows = [{"col": "value", "id": 1}]  # Add missing id field

        mock_conn = Mock()
        mock_result = {
            "mode": "delete_insert",
            "table": "test",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
        }

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            with patch("work_data_hub.orchestration.ops.loading.load") as mock_load:
                mock_load.return_value = mock_result

                with patch(
                    "work_data_hub.orchestration.ops.loading.get_settings"
                ) as mock_settings:
                    mock_db = Mock()
                    mock_db.get_connection_string.return_value = "postgresql://test"
                    mock_settings.return_value.database = mock_db
                    # Primary method not available to test fallback
                    del mock_settings.return_value.get_database_connection_string

                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test", pk=["id"])
                    result = load_op(context, config, processed_rows)

                    # Verify bare connection was used (not context manager)
                    mock_psycopg2.connect.assert_called_once_with("postgresql://test")

                    # Verify load was called with bare connection
                    mock_load.assert_called_once_with(
                        table="test",
                        rows=processed_rows,
                        mode="delete_insert",
                        pk=["id"],
                        conn=mock_conn,
                    )

                    # Verify connection cleanup
                    mock_conn.close.assert_called_once()
                    assert result == mock_result

    def test_load_op_context_manager_exception_handling(self):
        """Test load_op connection handling with exceptions."""
        processed_rows = [{"col": "value", "id": 1}]  # Add missing id field

        with patch(
            "work_data_hub.orchestration.ops.loading.psycopg2", create=True
        ) as mock_psycopg2:
            # Simulate connection failure
            mock_psycopg2.connect.side_effect = Exception("Connection error")

            with patch(
                "work_data_hub.orchestration.ops.loading.get_settings"
            ) as mock_settings:
                mock_db = Mock()
                mock_db.get_connection_string.return_value = "postgresql://test"
                mock_settings.return_value.database = mock_db

                context = build_op_context()
                config = LoadConfig(plan_only=False, table="test", pk=["id"])

                with pytest.raises(Exception, match="Database connection failed"):
                    load_op(context, config, processed_rows)


class TestProcessAnnuityPerformanceOp:
    """Test process_annuity_performance_op functionality with plan-only mode."""

    def test_process_annuity_performance_op_plan_only_no_connections(self):
        """Test plan-only mode doesn't create database connections."""
        context = build_op_context()
        config = ProcessingConfig(
            enrichment_enabled=True,
            plan_only=True,
            enrichment_sync_budget=5,
            export_unknown_names=True,
        )
        excel_rows = []
        file_paths = ["test_file.xlsx"]

        # Mock the process_with_enrichment function to avoid import issues
        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_with_enrichment"
        ) as mock_process:
            # Setup mock result
            mock_result = Mock()
            mock_result.records = []
            mock_result.enrichment_stats.total_records = 0
            mock_process.return_value = mock_result

            # Mock psycopg2 to verify it's not called in plan-only mode
            with patch("work_data_hub.orchestration.ops.loading.psycopg2") as mock_psycopg2:
                result = process_annuity_performance_op(
                    context, config, excel_rows, file_paths
                )

                # Should not attempt database connection in plan-only mode
                mock_psycopg2.connect.assert_not_called()

                # Should still call processing without enrichment service
                mock_process.assert_called_once_with(
                    excel_rows,
                    data_source="test_file.xlsx",
                    eqc_config=ANY,  # EqcLookupConfig object
                    enrichment_service=None,  # No enrichment service in plan-only mode
                    export_unknown_names=ANY,  # Derived from config
                )

                assert result == []

    def test_process_annuity_performance_op_enrichment_disabled_plan_only(self):
        """Test plan-only mode with enrichment disabled works correctly."""
        context = build_op_context()
        config = ProcessingConfig(
            enrichment_enabled=False,  # Disabled
            plan_only=True,
            enrichment_sync_budget=0,
            export_unknown_names=True,
        )
        excel_rows = [{"计划代码": "TEST001", "客户名称": "Test Client"}]
        file_paths = ["test_file.xlsx"]

        # Mock the process_with_enrichment function
        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_with_enrichment"
        ) as mock_process:
            # Setup mock result with some processed records
            mock_result = Mock()
            mock_record = Mock()
            mock_record.model_dump.return_value = {
                "plan_code": "TEST001",
                "client": "Test Client",
            }
            mock_result.records = [mock_record]
            mock_result.enrichment_stats.total_records = 0
            mock_process.return_value = mock_result

            result = process_annuity_performance_op(
                context, config, excel_rows, file_paths
            )

            # Should call processing without enrichment service
            mock_process.assert_called_once_with(
                excel_rows,
                data_source="test_file.xlsx",
                eqc_config=ANY,  # EqcLookupConfig object
                enrichment_service=None,  # No enrichment service when disabled
                export_unknown_names=ANY,  # Derived from config
            )

            # Should return serialized records
            assert result == [{"plan_code": "TEST001", "client": "Test Client"}]


class TestProcessAnnuityIncomeOp:
    """Test process_annuity_income_op functionality (Story 6.2-P3 AC5)."""

    def test_process_annuity_income_op_plan_only_success(self):
        """Test plan-only mode processes data without database connections."""
        context = build_op_context()
        config = ProcessingConfig(
            enrichment_enabled=False,
            plan_only=True,
            enrichment_sync_budget=0,
            export_unknown_names=True,
        )
        excel_rows = [{"计划号": "PLAN001", "机构": "北京", "固费": "100.00"}]
        file_paths = ["test_income_file.xlsx"]

        # Mock the process_annuity_income_with_enrichment function
        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_annuity_income_with_enrichment"
        ) as mock_process:
            # Setup mock result with processed records
            mock_result = Mock()
            mock_record = Mock()
            mock_record.model_dump.return_value = {
                "plan_code": "PLAN001",
                "branch": "北京",
                "fixed_fee": "100.00",
            }
            mock_result.records = [mock_record]
            mock_process.return_value = mock_result

            result = process_annuity_income_op(
                context, config, excel_rows, file_paths
            )

            # Verify process was called with correct parameters
            mock_process.assert_called_once_with(
                excel_rows,
                data_source="test_income_file.xlsx"
            )

            # Verify result is JSON-serializable
            json.dumps(result)

            # Should return serialized records
            assert result == [{"plan_code": "PLAN001", "branch": "北京", "fixed_fee": "100.00"}]

    def test_process_annuity_income_op_empty_data(self):
        """Test processing empty data returns empty list."""
        context = build_op_context()
        config = ProcessingConfig(plan_only=True)
        excel_rows = []
        file_paths = ["test_file.xlsx"]

        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_annuity_income_with_enrichment"
        ) as mock_process:
            mock_result = Mock()
            mock_result.records = []
            mock_process.return_value = mock_result

            result = process_annuity_income_op(context, config, excel_rows, file_paths)

            assert result == []

    def test_process_annuity_income_op_empty_file_paths(self):
        """Test processing with empty file paths uses 'unknown' as data_source."""
        context = build_op_context()
        config = ProcessingConfig(plan_only=True)
        excel_rows = [{"计划号": "PLAN001"}]
        file_paths = []

        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_annuity_income_with_enrichment"
        ) as mock_process:
            mock_result = Mock()
            mock_result.records = []
            mock_process.return_value = mock_result

            result = process_annuity_income_op(context, config, excel_rows, file_paths)

            # Should use "unknown" as data_source when no file paths provided
            mock_process.assert_called_once_with(excel_rows, data_source="unknown")
            assert result == []

    def test_process_annuity_income_op_multiple_records(self):
        """Test processing multiple records returns all serialized."""
        context = build_op_context()
        config = ProcessingConfig(plan_only=True)
        excel_rows = [
            {"计划号": "PLAN001", "固费": "100.00"},
            {"计划号": "PLAN002", "固费": "200.00"},
        ]
        file_paths = ["test_file.xlsx"]

        with patch(
            "work_data_hub.orchestration.ops.pipeline_ops.process_annuity_income_with_enrichment"
        ) as mock_process:
            mock_result = Mock()
            mock_record1 = Mock()
            mock_record1.model_dump.return_value = {"plan_code": "PLAN001", "fixed_fee": "100.00"}
            mock_record2 = Mock()
            mock_record2.model_dump.return_value = {"plan_code": "PLAN002", "fixed_fee": "200.00"}
            mock_result.records = [mock_record1, mock_record2]
            mock_process.return_value = mock_result

            result = process_annuity_income_op(context, config, excel_rows, file_paths)

            assert len(result) == 2
            assert result[0]["plan_code"] == "PLAN001"
            assert result[1]["plan_code"] == "PLAN002"

            # Verify result is JSON-serializable
            json.dumps(result)
