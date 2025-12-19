"""
Unit tests for ReferenceSyncConfigLoader.

Tests configuration loading, validation, and error handling.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml

from work_data_hub.domain.reference_backfill.sync_config_loader import (
    ReferenceSyncConfigLoader,
    load_reference_sync_config,
)
from work_data_hub.domain.reference_backfill.sync_models import ReferenceSyncConfig


@pytest.fixture
def sample_config_data():
    """Create sample configuration data."""
    return {
        "schema_version": "1.0",
        "enabled": True,
        "schedule": "0 1 * * *",
        "concurrency": 1,
        "batch_size": 5000,
        "tables": [
            {
                "name": "年金计划",
                "target_table": "年金计划",
                "target_schema": "business",
                "source_type": "legacy_mysql",
                "source_config": {
                    "table": "annuity_plan",
                    "columns": [
                        {"source": "plan_code", "target": "年金计划号"},
                        {"source": "plan_name", "target": "计划名称"},
                    ]
                },
                "sync_mode": "upsert",
                "primary_key": "年金计划号",
            },
            {
                "name": "产品线",
                "target_table": "产品线",
                "target_schema": "business",
                "source_type": "config_file",
                "source_config": {
                    "file_path": "config/reference_data/product_lines.yml",
                    "schema_version": "1.0",
                },
                "sync_mode": "delete_insert",
                "primary_key": "产品线代码",
            },
        ],
    }


class TestReferenceSyncConfigLoader:
    """Test suite for ReferenceSyncConfigLoader."""

    def test_init(self):
        """Test loader initialization."""
        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")
        assert loader.config_path == Path("config/reference_sync.yml")
        assert loader.logger is not None

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_success(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_config_data,
    ):
        """Test successful config loading."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = sample_config_data

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")
        config = loader.load_config()

        # Verify config was loaded
        assert isinstance(config, ReferenceSyncConfig)
        assert config.enabled is True
        assert config.schedule == "0 1 * * *"
        assert config.concurrency == 1
        assert config.batch_size == 5000
        assert len(config.tables) == 2

        # Verify table configurations
        assert config.tables[0].name == "年金计划"
        assert config.tables[0].source_type == "legacy_mysql"
        assert config.tables[1].name == "产品线"
        assert config.tables[1].source_type == "config_file"

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        """Test loading with missing config file."""
        mock_exists.return_value = False

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")

        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            loader.load_config()

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_no_tables_key(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
    ):
        """Test loading with missing tables key."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "enabled": True,
            "schedule": "0 1 * * *",
        }

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")
        config = loader.load_config()

        # Should return None when tables key is missing
        assert config is None

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_yaml_parse_error(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
    ):
        """Test loading with YAML parse error."""
        mock_exists.return_value = True
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")

        with pytest.raises(ValueError, match="Invalid YAML"):
            loader.load_config()

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_invalid_schema(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
    ):
        """Test loading with invalid configuration schema."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "tables": [{}],  # Missing required fields for ReferenceSyncTableConfig
        }

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")

        with pytest.raises(ValueError, match="Invalid reference sync configuration"):
            loader.load_config()

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_disabled(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_config_data,
    ):
        """Test loading with disabled reference sync."""
        mock_exists.return_value = True

        # Modify config to disable sync
        disabled_config = sample_config_data.copy()
        disabled_config["enabled"] = False
        mock_yaml_load.return_value = disabled_config

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")
        config = loader.load_config()

        # Config should still load but be disabled
        assert isinstance(config, ReferenceSyncConfig)
        assert config.enabled is False

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_reference_sync_config_convenience_function(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
        sample_config_data,
    ):
        """Test convenience function for loading config."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = sample_config_data

        config = load_reference_sync_config("config/reference_sync.yml")

        # Verify config was loaded
        assert isinstance(config, ReferenceSyncConfig)
        assert config.enabled is True
        assert len(config.tables) == 2

    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load')
    def test_load_config_empty_tables(
        self,
        mock_yaml_load,
        mock_file_open,
        mock_exists,
    ):
        """Test loading with empty tables list."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "enabled": True,
            "schedule": "0 1 * * *",
            "tables": [],
        }

        loader = ReferenceSyncConfigLoader("config/reference_sync.yml")
        config = loader.load_config()

        # Should load successfully with empty tables
        assert isinstance(config, ReferenceSyncConfig)
        assert len(config.tables) == 0
