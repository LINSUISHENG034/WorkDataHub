"""
Mapping loader for WorkDataHub configuration-driven YAML seeds.

This module provides typed loading functions for static mapping data
previously stored in the database. It supports UTF-8 Chinese characters
and provides comprehensive validation and error handling.

Migrated from config/mapping_loader.py in Story 5.3.
"""

import logging
import os
from pathlib import Path
from typing import Dict

import yaml

logger = logging.getLogger(__name__)


class MappingLoaderError(Exception):
    """Raised when mapping loader encounters an error."""

    pass


def get_mappings_dir() -> Path:
    """
    Get mappings directory with environment variable override support.

    Returns:
        Path to the mappings directory

    Raises:
        MappingLoaderError: If WDH_MAPPINGS_DIR environment variable points to an
            invalid path
    """
    env_dir = os.environ.get("WDH_MAPPINGS_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.exists() or not p.is_dir():
            raise MappingLoaderError(
                f"WDH_MAPPINGS_DIR not found or not a directory: {env_dir}"
            )
        return p
    # Default: project root / config / mappings (migrated from data/)
    # Robustly find project root by looking for pyproject.toml
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "config" / "mappings"

    # Fallback if pyproject.toml not found (e.g. installed package context)
    # Assume standard structure:
    # src/work_data_hub/infrastructure/settings/loader.py -> root
    return Path(__file__).parents[4] / "config" / "mappings"


def load_yaml_mapping(path: str) -> Dict[str, str]:
    """
    Load and validate YAML mapping file.

    Args:
        path: Path to YAML mapping file

    Returns:
        Dictionary with string keys and string values

    Raises:
        MappingLoaderError: If file cannot be loaded or structure invalid
    """
    config_path = Path(path)

    if not config_path.exists():
        raise MappingLoaderError(f"Mapping file not found: {path}")

    try:
        # PATTERN: Exact same structure as file_connector._load_config
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise MappingLoaderError(f"Invalid YAML mapping: {e}")
    except Exception as e:
        raise MappingLoaderError(f"Failed to load mapping: {e}")

    # PATTERN: Validate structure like file_connector domain validation
    if not isinstance(data, dict):
        raise MappingLoaderError("Mapping must be a dictionary")

    # Convert all values to strings for consistency
    validated_mapping = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise MappingLoaderError(f"Mapping key must be string, got {type(key)}")
        if not isinstance(value, (str, int)):
            raise MappingLoaderError(
                f"Mapping value must be string or int, got {type(value)}"
            )
        validated_mapping[key] = str(value)

    logger.debug(f"Loaded {len(validated_mapping)} mappings from {path}")
    return validated_mapping


def load_company_branch() -> Dict[str, str]:
    """Load company branch name to code mapping."""
    return load_yaml_mapping(str(get_mappings_dir() / "company_branch.yml"))


def load_default_portfolio_code() -> Dict[str, str]:
    """Load default portfolio code mapping."""
    return load_yaml_mapping(str(get_mappings_dir() / "default_portfolio_code.yml"))


def load_company_id_overrides_plan() -> Dict[str, str]:
    """Load company ID override mapping for plans."""
    # Story 6.x: Reorganized to company_id/ subdirectory
    return load_yaml_mapping(
        str(get_mappings_dir() / "company_id" / "company_id_overrides_plan.yml")
    )


def load_business_type_code() -> Dict[str, str]:
    """Load business type to code mapping."""
    return load_yaml_mapping(str(get_mappings_dir() / "business_type_code.yml"))
