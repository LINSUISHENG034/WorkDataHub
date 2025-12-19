"""
Configuration loader for foreign key backfill operations.

This module provides functions to load and validate foreign key configurations
from config/foreign_keys.yml (Story 6.2-P14: Config File Modularization).

Previously loaded from data_sources.yml, now uses dedicated foreign_keys.yml
following Single Responsibility Principle.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

import yaml
from yaml import YAMLError
from pydantic import ValidationError

from .models import DomainForeignKeysConfig, ForeignKeyConfig

logger = logging.getLogger(__name__)

# Default path for foreign keys configuration (Story 6.2-P14)
DEFAULT_FK_CONFIG_RELATIVE_PATH = Path("config") / "foreign_keys.yml"


def _default_fk_config_path() -> Path:
    project_root = os.environ.get("WDH_PROJECT_ROOT")
    return Path(project_root) / DEFAULT_FK_CONFIG_RELATIVE_PATH if project_root else DEFAULT_FK_CONFIG_RELATIVE_PATH


def load_foreign_keys_config(
    config_path: Optional[Path] = None,
    domain: str = "annuity_performance"
) -> List[ForeignKeyConfig]:
    """
    Load foreign key configurations from config/foreign_keys.yml for a specific domain.

    Story 6.2-P14: Config File Modularization
    - Changed default from data_sources.yml to foreign_keys.yml
    - File structure: domains.<domain_name>.foreign_keys

    Args:
        config_path: Path to foreign_keys.yml configuration file (default: config/foreign_keys.yml)
        domain: Domain name to load configurations for

    Returns:
        List of foreign key configurations for the domain

    Raises:
        ValueError: If configuration is invalid
    """
    if config_path is None:
        config_path = _default_fk_config_path()

    if not config_path.exists():
        logger.warning(f"Configuration file not found: {config_path}")
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Extract foreign_keys section for the domain
        # Story 6.2-P14: New structure is domains.<name>.foreign_keys
        domain_config = data.get("domains", {}).get(domain, {})
        foreign_keys_data = domain_config.get("foreign_keys", [])

        # If no foreign_keys configured, return empty list
        if not foreign_keys_data:
            logger.info(f"No foreign_keys configuration found for domain '{domain}'")
            return []

        # Validate configuration using Pydantic model
        domain_config = DomainForeignKeysConfig(foreign_keys=foreign_keys_data)

        logger.info(
            f"Loaded {len(domain_config.foreign_keys)} foreign key configurations "
            f"for domain '{domain}'"
        )

        return domain_config.foreign_keys

    except ValidationError as e:
        logger.error(f"Invalid foreign_keys configuration for domain '{domain}': {e}")
        raise ValueError(f"Invalid foreign_keys configuration: {e}") from e
    except YAMLError as e:
        logger.error(f"Failed to load foreign_keys configuration (YAML error): {e}")
        raise ValueError(f"Failed to load foreign_keys configuration: {e}") from e
    except Exception as e:
        logger.error(f"Failed to load foreign_keys configuration: {e}")
        raise ValueError(f"Failed to load foreign_keys configuration: {e}") from e


def get_domain_from_context(context: Optional[str] = None) -> str:
    """
    Get domain name from context or use default.

    Args:
        context: Optional context string to extract domain from

    Returns:
        Domain name as string
    """
    if context:
        # Try to extract domain from context
        if "." in context:
            return context.split(".")[-1]
        return context

    # Default domain for backfill operations
    return "annuity_performance"
