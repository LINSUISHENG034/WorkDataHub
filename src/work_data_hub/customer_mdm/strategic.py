"""Strategic customer identification logic.

Story 7.6-11: Customer Status Field Enhancement
AC-1: Implement strategic customer identification logic

Strategic customer criteria:
1. Prior year total AUM >= threshold (default 500M)
2. Top N customers per branch per product line (default top 10)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from structlog import get_logger

logger = get_logger(__name__)

# Default config path
CONFIG_PATH = Path("config/customer_mdm.yaml")

# Cache for config values
_config_cache: Optional[dict] = None


def _load_config() -> dict:
    """Load customer MDM configuration from YAML file.

    Returns:
        dict: Configuration dictionary with customer_mdm settings
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_PATH.exists():
        logger.warning("Config file not found, using defaults", path=str(CONFIG_PATH))
        _config_cache = {
            "customer_mdm": {
                "strategic_threshold": 500_000_000,
                "whitelist_top_n": 10,
                "status_year": 2026,
            }
        }
        return _config_cache

    with open(CONFIG_PATH) as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def get_strategic_threshold() -> int:
    """Get the AUM threshold for strategic customer identification.

    Returns:
        int: Threshold in yuan (default 500,000,000 = 500M)
    """
    config = _load_config()
    return config.get("customer_mdm", {}).get("strategic_threshold", 500_000_000)


def get_whitelist_top_n() -> int:
    """Get the top N value for whitelist generation.

    Returns:
        int: Number of top customers per branch per product line (default 10)
    """
    config = _load_config()
    return config.get("customer_mdm", {}).get("whitelist_top_n", 10)


def is_strategic_by_threshold(total_aum: float) -> bool:
    """Determine if a customer is strategic based on AUM threshold.

    Args:
        total_aum: Total assets under management in yuan

    Returns:
        True if AUM >= threshold, False otherwise
    """
    threshold = get_strategic_threshold()
    return total_aum >= threshold


def clear_config_cache() -> None:
    """Clear the configuration cache. Useful for testing."""
    global _config_cache
    _config_cache = None
