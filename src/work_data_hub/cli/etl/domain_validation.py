"""
Domain validation utilities for ETL CLI.

Story 7.4: CLI Layer Modularization - Domain loading and validation.
"""

from typing import List, Tuple

import yaml

# Special orchestration domains (not in data_sources.yml)
# Note: company_mapping removed in Story 7.1-4 (Zero Legacy)
# Story 7.4-4: Exposed as module-level constant for validate_domain_registry()
SPECIAL_DOMAINS = {"company_lookup_queue", "reference_sync"}


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


# Story 7.4-4: Domain Registry Validation
# SPECIAL_DOMAINS defined at module level (line 14)


def validate_domain_registry() -> None:
    """Validate that configured domains have corresponding job definitions.

    Emits UserWarning for domains in data_sources.yml that lack JOB_REGISTRY entries.
    Excludes SPECIAL_DOMAINS which intentionally have no jobs.

    This validation runs at CLI startup to catch configuration/implementation
    mismatches early, preventing silent runtime failures.
    """
    import warnings

    from work_data_hub.orchestration.jobs import JOB_REGISTRY

    try:
        configured_domains: set[str] = set(_load_configured_domains())
    except Exception:
        # Config loading failed - already warned by _load_configured_domains()
        return

    registry_domains: set[str] = set(JOB_REGISTRY.keys())

    # Exclude special domains that intentionally lack job definitions
    domains_to_check = configured_domains - SPECIAL_DOMAINS

    missing = domains_to_check - registry_domains
    if missing:
        warnings.warn(
            f"Domains in data_sources.yml without jobs: {sorted(missing)}",
            category=UserWarning,
            stacklevel=2,
        )
