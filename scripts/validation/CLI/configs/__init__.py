"""
Domain Configuration Registry for Cleaner Comparison.

This module provides a centralized registry of domain-specific configurations
for the cleaner comparison framework. Each domain defines its validation rules,
field mappings, and pipeline builders through a config class.

Usage:
    from configs import DOMAIN_CONFIGS, get_domain_config

    # Get available domains
    print(list(DOMAIN_CONFIGS.keys()))

    # Get specific config
    config = get_domain_config("annuity_performance")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from .base import DomainComparisonConfig

# Domain configuration registry
# Maps domain names to their configuration classes
DOMAIN_CONFIGS: Dict[str, Type["DomainComparisonConfig"]] = {}


def register_config(
    config_class: Type["DomainComparisonConfig"],
) -> Type["DomainComparisonConfig"]:
    """
    Decorator to register a domain configuration class.

    Usage:
        @register_config
        class AnnuityPerformanceConfig(DomainComparisonConfig):
            domain_name = "annuity_performance"
            ...
    """
    DOMAIN_CONFIGS[config_class.domain_name] = config_class
    return config_class


def get_domain_config(domain: str) -> "DomainComparisonConfig":
    """
    Get an instantiated domain configuration by name.

    Args:
        domain: Domain name (e.g., "annuity_performance")

    Returns:
        Instantiated DomainComparisonConfig subclass

    Raises:
        ValueError: If domain is not registered
    """
    if domain not in DOMAIN_CONFIGS:
        available = ", ".join(sorted(DOMAIN_CONFIGS.keys()))
        raise ValueError(f"Unknown domain: {domain}. Available domains: {available}")
    return DOMAIN_CONFIGS[domain]()


# Import domain configs to trigger registration
# NOTE: Imports are at the bottom to avoid circular imports
def _load_domain_configs() -> None:
    """Load all domain configuration modules to trigger registration."""
    # Import annuity_performance config
    try:
        from . import annuity_performance  # noqa: F401
    except ImportError:
        pass  # Config not yet created or dependencies missing

    # Import annuity_income config
    try:
        from . import annuity_income  # noqa: F401
    except ImportError:
        pass  # Config not yet created or dependencies missing


# Auto-load configs on module import
_load_domain_configs()
