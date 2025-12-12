"""
Unit tests for ConfigFileConnector.

Tests config file loading, schema validation, and error handling.
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml

from work_data_hub.io.connectors.config_file_connector import ConfigFileConnector
from work_data_hub.domain.reference_backfill.sync_models import (
    ReferenceSyncTableConfig,
)


@pytest.fixture
def sample_table_config():
    """Create sample table configuration."""
    return ReferenceSyncTableConfig(
        name="test_sync",
        target_table="产品线",
        target_schema="business",
        source_type="config_file",
        source_config={
            "file_path": "config/reference_data/product_lines.yml",
            "schema_version": "1.0",
        },
        sync_mode="delete_insert",
        primary_key="产品线代码",
    )


@pytest.fixture
def sample_yaml_content():
    """Create sample YAML content."""
    return {
        "schema_version": "1.0",
        "description": "Product lines reference data",
        "data": [
            {"产品线代码": "PL001", "产品线名称": "企业年金"},
            {"产品线代码": "PL002", "产品线名称": "职业年金"},
            {"产品线代码": "PL003", "产品线名称": "养老保障"},
        ]
    }


class TestConfigFileConnector:
    """Test suite for ConfigFileConnector."""

    def test_init(self):
        """Test connector initialization."""
        connector = ConfigFileConnector()
        assert connector.logger is not None

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_success(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
        sample_yaml_content,
    ):
        """Test successful data fetch from config file."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = sample_yaml_content

        connector = ConfigFileConnector()
        df = connector.fetch_data(sample_table_config)

        # Verify DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

        # Verify columns
        assert "产品线代码" in df.columns
        assert "产品线名称" in df.columns

        # Verify data values
        assert df["产品线代码"].tolist() == ["PL001", "PL002", "PL003"]
        assert df["产品线名称"].tolist() == ["企业年金", "职业年金", "养老保障"]

        # Verify file was opened
        mock_file_open.assert_called_once()

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    def test_fetch_data_file_not_found(
        self,
        mock_exists,
        sample_table_config,
    ):
        """Test fetch with missing config file."""
        mock_exists.return_value = False

        connector = ConfigFileConnector()

        with pytest.raises(FileNotFoundError, match="Config file not found"):
            connector.fetch_data(sample_table_config)

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_schema_version_mismatch(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
        sample_yaml_content,
    ):
        """Test fetch with schema version mismatch."""
        mock_exists.return_value = True

        # Modify schema version to mismatch
        mismatched_content = sample_yaml_content.copy()
        mismatched_content["schema_version"] = "2.0"
        mock_yaml_load.return_value = mismatched_content

        connector = ConfigFileConnector()
        df = connector.fetch_data(sample_table_config)

        # Should return empty DataFrame instead of raising error
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_empty_data(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
    ):
        """Test fetch with empty data section."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "description": "Empty data",
            "data": []
        }

        connector = ConfigFileConnector()
        df = connector.fetch_data(sample_table_config)

        # Should return empty DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_missing_data_key(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
    ):
        """Test fetch with missing data key."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "description": "No data key"
        }

        connector = ConfigFileConnector()
        df = connector.fetch_data(sample_table_config)

        # Should return empty DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_yaml_parse_error(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
    ):
        """Test fetch with YAML parse error."""
        mock_exists.return_value = True
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")

        connector = ConfigFileConnector()

        with pytest.raises(ValueError, match="Invalid YAML"):
            connector.fetch_data(sample_table_config)

    def test_fetch_data_invalid_config(self):
        """Test fetch with invalid source configuration."""
        # Invalid config - missing required fields
        invalid_config = ReferenceSyncTableConfig(
            name="test_sync",
            target_table="产品线",
            target_schema="business",
            source_type="config_file",
            source_config={
                "invalid_field": "value"
            },
            sync_mode="delete_insert",
            primary_key="产品线代码",
        )

        connector = ConfigFileConnector()

        with pytest.raises(ValueError, match="Invalid config file source config"):
            connector.fetch_data(invalid_config)

    @patch('work_data_hub.io.connectors.config_file_connector.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.io.connectors.config_file_connector.yaml.safe_load')
    def test_fetch_data_with_description(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_table_config,
        sample_yaml_content,
    ):
        """Test fetch preserves all data fields."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = sample_yaml_content

        connector = ConfigFileConnector()
        df = connector.fetch_data(sample_table_config)

        # Verify all columns from data are preserved
        assert len(df.columns) == 2
        assert "产品线代码" in df.columns
        assert "产品线名称" in df.columns
