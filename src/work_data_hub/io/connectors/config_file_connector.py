"""
Config file connector for reference data sync.

This module provides a connector for loading reference data from YAML
configuration files, with schema version validation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import yaml

from work_data_hub.domain.reference_backfill.sync_models import (
    ConfigFileSourceConfig,
    ReferenceSyncTableConfig,
)

logger = logging.getLogger(__name__)


class ConfigFileConnector:
    """
    Connector for loading reference data from YAML config files.

    Provides schema version validation and data loading capabilities
    for syncing reference data from configuration files.
    """

    def __init__(self):
        """Initialize the config file connector."""
        self.logger = logging.getLogger(f"{__name__}")
        self.logger.info("Config file connector initialized")

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,  # state unused for config files
    ) -> pd.DataFrame:
        """
        Fetch reference data from YAML config file.

        Implements the DataSourceAdapter protocol for use with ReferenceSyncService.

        Args:
            table_config: Table sync configuration

        Returns:
            DataFrame with reference data

        Raises:
            ValueError: If source_config is invalid or file is missing
            FileNotFoundError: If config file does not exist
        """
        # Parse source configuration
        try:
            source_config = ConfigFileSourceConfig(**table_config.source_config)
        except Exception as e:
            error_msg = f"Invalid config file source config: {e}"
            self.logger.error(
                f"Invalid config file config for table {table_config.target_table}: {str(e)}"
            )
            raise ValueError(error_msg)

        # Resolve file path
        file_path = Path(source_config.file_path)
        if not file_path.is_absolute():
            # Resolve relative to project root
            file_path = Path.cwd() / file_path

        # Check if file exists
        if not file_path.exists():
            error_msg = f"Config file not found: {file_path}"
            self.logger.error(
                f"Config file not found for table {table_config.target_table}: {file_path}"
            )
            raise FileNotFoundError(error_msg)

        self.logger.info(
            f"Loading config file: {file_path} -> {table_config.target_table}"
        )

        # Load YAML file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in config file: {e}"
            self.logger.error(f"YAML parse error in {file_path}: {str(e)}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to load config file: {e}"
            self.logger.error(f"Failed to load config file {file_path}: {str(e)}")
            raise

        # Validate schema version
        file_schema_version = config_data.get("schema_version")
        if file_schema_version != source_config.schema_version:
            error_msg = (
                f"Schema version mismatch: expected {source_config.schema_version}, "
                f"got {file_schema_version}"
            )
            self.logger.warning(
                f"Schema version mismatch for {file_path}: "
                f"expected {source_config.schema_version}, got {file_schema_version}. "
                f"Skipping this file."
            )
            # Return empty DataFrame instead of raising error
            return pd.DataFrame()

        # Extract data
        data = config_data.get("data", [])
        if not data:
            self.logger.warning(f"No data found in config file {file_path}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        self.logger.info(
            f"Config file loaded: {file_path} -> {table_config.target_table} ({len(df)} rows)"
        )

        return df
