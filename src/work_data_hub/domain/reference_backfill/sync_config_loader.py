"""
Configuration loader for reference sync operations.

This module provides utilities for loading and validating reference sync
configuration from data_sources.yml.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .sync_models import ReferenceSyncConfig

logger = logging.getLogger(__name__)


class ReferenceSyncConfigLoader:
    """
    Loader for reference sync configuration.

    Loads and validates reference sync configuration from data_sources.yml.
    """

    def __init__(self, config_path: str = "config/data_sources.yml"):
        """
        Initialize the config loader.

        Args:
            config_path: Path to data_sources.yml configuration file
        """
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(f"{__name__}")

    def load_config(self) -> Optional[ReferenceSyncConfig]:
        """
        Load reference sync configuration from data_sources.yml.

        Returns:
            ReferenceSyncConfig if configuration exists and is valid, None otherwise

        Raises:
            FileNotFoundError: If config file does not exist
            ValueError: If configuration is invalid
        """
        # Check if config file exists
        if not self.config_path.exists():
            error_msg = f"Configuration file not found: {self.config_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        self.logger.info(f"Loading reference sync config from {self.config_path}")

        # Load YAML file
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in configuration file: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to load configuration file: {e}"
            self.logger.error(error_msg)
            raise

        # Check if reference_sync section exists
        if 'reference_sync' not in config_data:
            self.logger.info("No reference_sync section found in configuration")
            return None

        sync_config_data = config_data['reference_sync']

        # Validate and parse configuration
        try:
            sync_config = ReferenceSyncConfig(**sync_config_data)
            self.logger.info(
                f"Reference sync config loaded: {len(sync_config.tables)} tables, "
                f"enabled={sync_config.enabled}"
            )
            return sync_config
        except Exception as e:
            error_msg = f"Invalid reference sync configuration: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)


def load_reference_sync_config(
    config_path: str = "config/data_sources.yml"
) -> Optional[ReferenceSyncConfig]:
    """
    Convenience function to load reference sync configuration.

    Args:
        config_path: Path to data_sources.yml configuration file

    Returns:
        ReferenceSyncConfig if configuration exists and is valid, None otherwise

    Raises:
        FileNotFoundError: If config file does not exist
        ValueError: If configuration is invalid
    """
    loader = ReferenceSyncConfigLoader(config_path)
    return loader.load_config()
