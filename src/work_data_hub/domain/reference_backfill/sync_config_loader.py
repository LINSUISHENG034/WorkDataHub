"""
Configuration loader for reference sync operations.

This module provides utilities for loading and validating reference sync
configuration from config/reference_sync.yml.

Story 6.2-P14: Config File Modularization
- Changed default from config/data_sources.yml to config/reference_sync.yml
- Follows Single Responsibility Principle
"""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

from .sync_models import ReferenceSyncConfig

logger = logging.getLogger(__name__)

# Default path for reference sync configuration (Story 6.2-P14)
DEFAULT_SYNC_CONFIG_PATH = "config/reference_sync.yml"


class ReferenceSyncConfigLoader:
    """
    Loader for reference sync configuration.

    Loads and validates reference sync configuration from config/reference_sync.yml.

    Story 6.2-P14: Config File Modularization
    - Changed default from data_sources.yml to reference_sync.yml
    """

    def __init__(self, config_path: str = DEFAULT_SYNC_CONFIG_PATH):
        """
        Initialize the config loader.

        Args:
            config_path: Path to reference_sync.yml configuration file
                        (default: config/reference_sync.yml)
        """
        resolved = Path(config_path)
        if not resolved.is_absolute():
            project_root = os.environ.get("WDH_PROJECT_ROOT")
            if project_root:
                resolved = Path(project_root) / resolved
        self.config_path = resolved
        self.logger = logging.getLogger(f"{__name__}")

    def load_config(self) -> Optional[ReferenceSyncConfig]:
        """
        Load reference sync configuration from config/reference_sync.yml.

        Story 6.2-P14: New config file structure has sync config at root level.

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
                config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in configuration file: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to load configuration file: {e}"
            self.logger.error(error_msg)
            raise

        if not isinstance(config_data, dict):
            raise ValueError("Invalid reference sync configuration: expected a YAML mapping at root")

        # Story 6.2-P14 (Zero Legacy): reference_sync.yml MUST be root-level config.
        # If it's missing the expected structure, treat as no config.
        if "tables" not in config_data:
            self.logger.info("No reference sync configuration found")
            return None

        sync_config_data = dict(config_data)
        # schema_version is metadata only (not part of ReferenceSyncConfig model)
        sync_config_data.pop("schema_version", None)

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
    config_path: str = DEFAULT_SYNC_CONFIG_PATH
) -> Optional[ReferenceSyncConfig]:
    """
    Convenience function to load reference sync configuration.

    Story 6.2-P14: Config File Modularization
    - Changed default from config/data_sources.yml to config/reference_sync.yml

    Args:
        config_path: Path to reference_sync.yml configuration file
                    (default: config/reference_sync.yml)

    Returns:
        ReferenceSyncConfig if configuration exists and is valid, None otherwise

    Raises:
        FileNotFoundError: If config file does not exist
        ValueError: If configuration is invalid
    """
    loader = ReferenceSyncConfigLoader(config_path)
    return loader.load_config()

