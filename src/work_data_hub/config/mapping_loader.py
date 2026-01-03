"""
Multi-file YAML loader for company ID mapping configurations.

This module provides centralized loading of company ID override mappings
from multiple YAML files organized by priority level. It supports the
hierarchical resolution strategy used by CompanyIdResolver.

Story 6.3: Internal Mapping Tables and Database Schema
Architecture Reference: AD-010 Infrastructure Layer

Priority Levels (New Pipeline Order):
1. plan - Plan code mappings (highest priority)
2. account_name - Account name mappings (年金账户名)
3. account - Account number mappings (年金账户号)
4. name - Customer name mappings (客户名称)
5. hardcode - Hardcoded special cases (lowest priority)
"""

import os
from pathlib import Path
from typing import Dict, Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Default mappings directory relative to project root
# Story 7.x: Migrated from data/mappings to config/mappings
DEFAULT_MAPPINGS_DIR = Path("config/mappings/company_id")

# Priority level file suffixes (in priority order)
# New Pipeline Priority Order (per company-enrichment-service.md):
#   P1: plan_code → company_id
#   P2: account_name → company_id (年金账户名)
#   P3: account_number → company_id (年金账户号)
#   P4: customer_name → company_id (客户名称)
#   P5: plan_code + customer_name → company_id (hardcode组合映射)
PRIORITY_LEVELS = ["plan", "account_name", "account", "name", "hardcode"]

# Environment variable for custom mappings directory
MAPPINGS_DIR_ENV_VAR = "WDH_MAPPINGS_DIR"


def _get_mappings_dir() -> Path:
    """
    Get the mappings directory path.

    Checks WDH_MAPPINGS_DIR environment variable first, then falls back
    to the default data/mappings directory.

    Returns:
        Path to the mappings directory.
    """
    env_path = os.environ.get(MAPPINGS_DIR_ENV_VAR)
    if env_path:
        return Path(env_path)
    return DEFAULT_MAPPINGS_DIR


def _load_single_yaml_file(file_path: Path, priority_name: str) -> Dict[str, str]:
    """
    Load a single YAML mapping file.

    Behavior:
    - Missing file: Returns empty dict, logs debug message (no exception)
    - Empty file: Returns empty dict
    - Invalid YAML: Raises ValueError with filename
    - Valid file: Returns dict with whitespace-stripped keys/values

    Args:
        file_path: Path to the YAML file.
        priority_name: Name of the priority level (for logging).

    Returns:
        Dict mapping alias names to company IDs.

    Raises:
        ValueError: If YAML syntax is invalid.
    """
    if not file_path.exists():
        logger.debug(
            "mapping_loader.file_not_found",
            priority=priority_name,
            file_path=str(file_path),
        )
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
    except yaml.YAMLError as e:
        error_msg = f"Invalid YAML in {file_path}: {e}"
        logger.error(
            "mapping_loader.yaml_parse_error",
            priority=priority_name,
            file_path=str(file_path),
            error=str(e),
        )
        raise ValueError(error_msg) from e

    # Handle empty file (yaml.safe_load returns None)
    if content is None:
        logger.debug(
            "mapping_loader.empty_file",
            priority=priority_name,
            file_path=str(file_path),
        )
        return {}

    # Validate shape: must be a dict of string -> string
    if not isinstance(content, dict):
        error_msg = (
            f"Invalid mapping format in {file_path}: "
            f"expected dict, got {type(content).__name__}"
        )
        logger.error(
            "mapping_loader.invalid_format",
            priority=priority_name,
            file_path=str(file_path),
            actual_type=type(content).__name__,
        )
        raise ValueError(error_msg)

    # Strip whitespace from keys and values, enforce string types
    result: Dict[str, str] = {}
    for key, value in content.items():
        if not isinstance(key, str) or not isinstance(value, str):
            error_msg = (
                f"Invalid mapping entry in {file_path}: "
                f"expected string key/value, got "
                f"{type(key).__name__}/{type(value).__name__}"
            )
            logger.error(
                "mapping_loader.invalid_entry_type",
                priority=priority_name,
                file_path=str(file_path),
                key_type=type(key).__name__,
                value_type=type(value).__name__,
            )
            raise ValueError(error_msg)

        stripped_key = key.strip()
        stripped_value = value.strip()
        result[stripped_key] = stripped_value

    logger.debug(
        "mapping_loader.file_loaded",
        priority=priority_name,
        file_path=str(file_path),
        entry_count=len(result),
    )

    return result


def load_company_id_overrides(
    mappings_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Load all company_id mapping configurations (5 priority levels).

    Loads YAML files from the mappings directory following the naming
    convention: company_id_overrides_{priority}.yml

    Args:
        mappings_dir: Optional custom mappings directory. If not provided,
            uses WDH_MAPPINGS_DIR environment variable or defaults to
            data/mappings.

    Returns:
        Dict with priority level keys mapping to their respective mappings:
        {
            "plan": {"FP0001": "614810477", ...},         # Priority 1
            "account_name": {"平安年金账户": "600866980", ...},  # Priority 2
            "account": {"12345678": "601234567", ...},    # Priority 3
            "name": {"中国平安": "600866980", ...},        # Priority 4
            "hardcode": {"FP0001": "614810477", ...},     # Priority 5
        }

    Raises:
        ValueError: If any YAML file has invalid syntax.

    Example:
        >>> overrides = load_company_id_overrides()
        >>> plan_mappings = overrides["plan"]
        >>> plan_mappings.get("FP0001")
        '614810477'
    """
    if mappings_dir is None:
        mappings_dir = _get_mappings_dir()

    result: Dict[str, Dict[str, str]] = {}
    total_entries = 0

    for priority in PRIORITY_LEVELS:
        file_name = f"company_id_overrides_{priority}.yml"
        file_path = mappings_dir / file_name

        mappings = _load_single_yaml_file(file_path, priority)
        result[priority] = mappings
        total_entries += len(mappings)

    logger.info(
        "mapping_loader.all_files_loaded",
        mappings_dir=str(mappings_dir),
        priority_count=len(PRIORITY_LEVELS),
        total_entries=total_entries,
    )

    return result


def get_flat_overrides(
    mappings_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Load all mappings and flatten into a single dict (plan priority only).

    This is a convenience function for backward compatibility with
    CompanyIdResolver which expects a flat dict of plan code mappings.

    Args:
        mappings_dir: Optional custom mappings directory.

    Returns:
        Dict mapping plan codes to company IDs (plan priority only).

    Example:
        >>> flat = get_flat_overrides()
        >>> flat.get("FP0001")
        '614810477'
    """
    overrides = load_company_id_overrides(mappings_dir)
    return overrides.get("plan", {})
