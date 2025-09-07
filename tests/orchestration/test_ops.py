"""
Unit tests for Dagster ops.

This module tests each op individually with mock data and validates that they
handle inputs correctly, produce JSON-serializable outputs, and implement
proper error handling and logging.
"""

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import yaml
from dagster import build_op_context

from src.work_data_hub.orchestration.ops import (
    DiscoverFilesConfig,
    LoadConfig,
    ReadExcelConfig,
    _load_valid_domains,
    discover_files_op,
    load_op,
    process_trustee_performance_op,
    read_excel_op,
)


class TestDiscoverFilesOp:
    """Test discover_files_op functionality."""

    def test_discover_files_op_success(self, tmp_path):
        """Test successful file discovery with metadata logging."""
        # Create test configuration
        config_data = {
            "domains": {
                "trustee_performance": {
                    "pattern": r"(?P<year>20\d{2})[-_](?P<month>0?[1-9]|1[0-2]).*受托业绩.*\.xlsx$",
                    "select": "latest_by_year_month",
                    "sheet": 0,
                }
            }
        }
        
        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Create test Excel file
        test_file = tmp_path / "2024_11_受托业绩报告.xlsx"
        df = pd.DataFrame({"col1": ["data"]})
        df.to_excel(test_file, index=False, engine="openpyxl")

        # Mock settings
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            # Mock DataSourceConnector
            mock_discovered = Mock()
            mock_discovered.path = str(test_file)
            mock_discovered.year = 2024
            mock_discovered.month = 11

            with patch(
                "src.work_data_hub.orchestration.ops.DataSourceConnector"
            ) as mock_connector_class:
                mock_connector = Mock()
                mock_connector.discover.return_value = [mock_discovered]
                mock_connector_class.return_value = mock_connector

                # Execute op
                context = build_op_context()
                config = DiscoverFilesConfig(domain="trustee_performance")
                result = discover_files_op(context, config)

                # Verify result is JSON-serializable
                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == str(test_file)
                
                # Verify result can be JSON serialized
                json.dumps(result)

    def test_discover_files_op_invalid_domain(self):
        """Test that invalid domain raises ValidationError."""
        with pytest.raises(ValueError, match="Domain 'invalid' not supported"):
            DiscoverFilesConfig(domain="invalid")

    def test_discover_files_op_empty_result(self, tmp_path):
        """Test discovery with no matching files."""
        config_data = {
            "domains": {
                "trustee_performance": {
                    "pattern": r"(?P<year>20\d{2}).*受托业绩.*\.xlsx$",
                    "select": "latest_by_year_month",
                }
            }
        }
        
        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)

            with patch(
                "src.work_data_hub.orchestration.ops.DataSourceConnector"
            ) as mock_connector_class:
                mock_connector = Mock()
                mock_connector.discover.return_value = []  # No files found
                mock_connector_class.return_value = mock_connector

                context = build_op_context()
                config = DiscoverFilesConfig(domain="trustee_performance")
                result = discover_files_op(context, config)

                assert result == []


class TestReadExcelOp:
    """Test read_excel_op functionality."""

    def test_read_excel_op_success(self, tmp_path):
        """Test successful Excel reading with metadata logging."""
        # Create test Excel file
        test_data = pd.DataFrame({
            "年": ["2024", "2024"],
            "月": ["11", "11"],
            "计划代码": ["PLAN001", "PLAN002"]
        })
        
        test_file = tmp_path / "test.xlsx"
        test_data.to_excel(test_file, index=False, engine="openpyxl")

        # Mock read_excel_rows
        expected_rows = [
            {"年": "2024", "月": "11", "计划代码": "PLAN001"},
            {"年": "2024", "月": "11", "计划代码": "PLAN002"},
        ]

        with patch(
            "src.work_data_hub.orchestration.ops.read_excel_rows"
        ) as mock_read:
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

        with patch(
            "src.work_data_hub.orchestration.ops.read_excel_rows"
        ) as mock_read:
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
    """Test process_trustee_performance_op functionality."""

    def test_process_trustee_performance_op_success(self):
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

        with patch("src.work_data_hub.orchestration.ops.process") as mock_process:
            mock_process.return_value = [mock_model]

            context = build_op_context()
            result = process_trustee_performance_op(
                context, excel_rows, ["/path/to/file.xlsx"]
            )

            assert len(result) == 1
            assert result[0]["plan_code"] == "PLAN001"
            
            # Verify result is JSON-serializable
            json.dumps(result)
            
            # Verify process was called correctly
            mock_process.assert_called_once_with(excel_rows, data_source="/path/to/file.xlsx")

    def test_process_trustee_performance_op_empty_data(self):
        """Test processing empty data."""
        with patch("src.work_data_hub.orchestration.ops.process") as mock_process:
            mock_process.return_value = []

            context = build_op_context()
            result = process_trustee_performance_op(context, [], ["/path/to/file.xlsx"])

            assert result == []

    def test_process_trustee_performance_op_empty_file_paths(self):
        """Test processing with empty file paths."""
        excel_rows = [{"年": "2024", "月": "11", "计划代码": "PLAN001"}]
        
        with patch("src.work_data_hub.orchestration.ops.process") as mock_process:
            mock_process.return_value = []

            context = build_op_context()
            result = process_trustee_performance_op(context, excel_rows, [])

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
            "table": "trustee_performance",
            "deleted": 1,
            "inserted": 1,
            "batches": 1,
            "sql_plans": [
                ("DELETE", "DELETE FROM ...", []),
                ("INSERT", "INSERT INTO ...", []),
            ],
        }

        with patch("src.work_data_hub.orchestration.ops.load") as mock_load:
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
            table="test_table",
            mode="delete_insert",
            pk=["id"],
            plan_only=True
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

        with patch("src.work_data_hub.orchestration.ops.load") as mock_load:
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
                "trustee_performance": {"table": "trustee_performance"},
                "annuity_performance": {"table": "annuity_performance"}
            }
        }
        config_file = tmp_path / "test_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
            
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)
            
            domains = _load_valid_domains()
            
            assert domains == ["annuity_performance", "trustee_performance"]

    def test_load_valid_domains_missing_file(self, tmp_path):
        """Test _load_valid_domains handles missing config file gracefully."""
        missing_file = tmp_path / "nonexistent.yml"
        
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(missing_file)
            
            domains = _load_valid_domains()
            
            # Should fallback to default
            assert domains == ["trustee_performance"]

    def test_load_valid_domains_empty_config(self, tmp_path):
        """Test _load_valid_domains handles empty domains gracefully."""
        config_data = {"domains": {}}
        config_file = tmp_path / "empty_config.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
            
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)
            
            domains = _load_valid_domains()
            
            # Should fallback to default when no domains found
            assert domains == ["trustee_performance"]

    def test_load_valid_domains_invalid_yaml(self, tmp_path):
        """Test _load_valid_domains handles invalid YAML gracefully."""
        config_file = tmp_path / "invalid.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [")
            
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = str(config_file)
            
            domains = _load_valid_domains()
            
            # Should fallback to default on YAML parse error
            assert domains == ["trustee_performance"]

    def test_load_op_execute_mode_mocked(self):
        """Test load_op with execute=True using mocked psycopg2."""
        processed_rows = [{"col": "value"}]
        
        mock_conn = Mock()
        mock_result = {
            "mode": "delete_insert", 
            "table": "test_table",
            "deleted": 1,
            "inserted": 1,
            "batches": 1
        }
        
        # Mock the dynamic import and psycopg2.connect
        mock_psycopg2 = Mock()
        mock_psycopg2.connect.return_value = mock_conn
        
        def mock_import(name, *args, **kwargs):
            if name == "psycopg2":
                return mock_psycopg2
            return __import__(name, *args, **kwargs)
        
        with patch("builtins.__import__", side_effect=mock_import):
            with patch("src.work_data_hub.orchestration.ops.load") as mock_load:
                mock_load.return_value = mock_result
                
                with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
                    mock_db = Mock()
                    mock_db.get_connection_string.return_value = "postgresql://test"
                    mock_settings.return_value.database = mock_db
                    
                    context = build_op_context()
                    config = LoadConfig(plan_only=False, table="test_table", pk=["id"])
                    result = load_op(context, config, processed_rows)
                    
                    # Verify connection was created and passed to load()
                    mock_psycopg2.connect.assert_called_once_with("postgresql://test")
                    mock_load.assert_called_once_with(
                        table="test_table",
                        rows=processed_rows,
                        mode="delete_insert",
                        pk=["id"],
                        conn=mock_conn
                    )
                    assert result == mock_result

    def test_load_op_execute_mode_psycopg2_not_available(self):
        """Test load_op with execute=True when psycopg2 is not available."""
        processed_rows = [{"col": "value"}]
        
        # Mock import to raise ImportError for psycopg2
        def mock_import(name, *args, **kwargs):
            if name == "psycopg2":
                raise ImportError("No module named 'psycopg2'")
            return __import__(name, *args, **kwargs)
        
        with patch("builtins.__import__", side_effect=mock_import):
            context = build_op_context()
            config = LoadConfig(plan_only=False, table="test_table", pk=["id"])
            
            with pytest.raises(Exception) as exc_info:
                load_op(context, config, processed_rows)
                
            assert "psycopg2 not available for database execution" in str(exc_info.value)

    def test_load_op_execute_mode_connection_failed(self):
        """Test load_op with execute=True when database connection fails."""
        processed_rows = [{"col": "value"}]
        
        with patch("src.work_data_hub.orchestration.ops.psycopg2", create=True) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Connection refused")
            
            with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
                mock_db = Mock()
                mock_db.get_connection_string.return_value = "postgresql://test"
                mock_settings.return_value.database = mock_db
                
                context = build_op_context()
                config = LoadConfig(plan_only=False, table="test_table", pk=["id"])
                
                with pytest.raises(Exception) as exc_info:
                    load_op(context, config, processed_rows)
                    
                assert "Database connection failed" in str(exc_info.value)
                assert "Check WDH_DATABASE__* environment variables" in str(exc_info.value)