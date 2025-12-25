"""
Domain validation utilities for ETL CLI.

Story 7.4: CLI Layer Modularization - Domain loading and validation.
"""

from typing import List, Tuple

import yaml


def _load_configured_domains() -> List[str]:
    """
    Load list of configured data domains from data_sources.yml.

    Returns:
        List of domain names from config/data_sources.yml
    """
    from work_data_hub.config.settings import get_settings

    settings = get_settings()
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        domains_config = data_sources.get("domains", {})
        if isinstance(domains_config, dict):
            return list(domains_config.keys())
        return []
    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        return []


def _validate_domains(
    domains: List[str], allow_special: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Validate domain names against configured domains and special orchestration domains.

    Args:
        domains: List of domain names to validate
        allow_special: If True, allow special orchestration domains for single-domain runs

    Returns:
        Tuple of (valid_domains, invalid_domains)
    """
    # Special orchestration domains (not in data_sources.yml)
    # Note: company_mapping removed in Story 7.1-4 (Zero Legacy)
    SPECIAL_DOMAINS = {"company_lookup_queue", "reference_sync"}

    # Load configured data domains
    configured_domains = set(_load_configured_domains())

    valid = []
    invalid = []

    for domain in domains:
        if domain in configured_domains:
            valid.append(domain)
        elif allow_special and domain in SPECIAL_DOMAINS:
            valid.append(domain)
        else:
            invalid.append(domain)

    return valid, invalid
