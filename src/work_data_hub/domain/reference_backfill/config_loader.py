"""
Configuration loader for foreign key backfill operations.

This module provides functions to load and validate foreign key configurations
from data_sources.yml files.
"""

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import ValidationError

from .models import DomainForeignKeysConfig, ForeignKeyConfig

logger = logging.getLogger(__name__)


def load_foreign_keys_config(config_path: Path, domain: str) -> List[ForeignKeyConfig]:
    """
    Load foreign key configurations from data_sources.yml for a specific domain.

    Args:
        config_path: Path to data_sources.yml configuration file
        domain: Domain name to load configurations for

    Returns:
        List of foreign key configurations for the domain

    Raises:
        ValueError: If configuration is invalid
    """
    if not config_path.exists():
        logger.warning(f"Configuration file not found: {config_path}")
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Extract foreign_keys section for the domain
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
