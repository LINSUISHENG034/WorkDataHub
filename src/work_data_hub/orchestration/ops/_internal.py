"""Internal shared utilities for ops sub-modules (Story 7.1).

This module contains common imports and helper functions used across
the ops package modules. It is intentionally internal (prefixed with _)
to prevent external imports.
"""

import logging
from pathlib import Path
from typing import Any, List

import yaml

from work_data_hub.config.settings import get_settings

logger = logging.getLogger(__name__)


# psycopg2 lazy import holder to satisfy both patching styles in tests:
# 1) patch("src.work_data_hub.orchestration.ops.psycopg2") expects a module
#    attribute here
# 2) patch builtins.__import__ expects a dynamic import path at runtime
_PSYCOPG2_NOT_LOADED = object()
psycopg2: Any = _PSYCOPG2_NOT_LOADED


def _load_valid_domains() -> List[str]:
    """
    Load valid domain names from data_sources.yml configuration.

    Returns:
        List of valid domain names sorted alphabetically

    Notes:
        - Returns fallback ["sandbox_trustee_performance"] if config cannot be loaded
        - Logs warnings for missing config or empty domains
        - Handles exceptions gracefully to prevent complete failure
    """
    try:
        settings = get_settings()
        config_path = Path(settings.data_sources_config)

        if not config_path.exists():
            logger.warning("Data sources config not found: %s", config_path)
            return ["sandbox_trustee_performance"]  # Fallback to current default

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            data = {}

        # Optional: validate only when the file resembles Epic 3 schema.
        # (Unit tests frequently patch in minimal YAML that is not schema-valid.)
        try:
            domains = data.get("domains") or {}
            looks_like_epic3 = bool(
                data.get("schema_version")
                or any(
                    isinstance(cfg, dict) and "base_path" in cfg
                    for cfg in domains.values()
                )
            )
            if looks_like_epic3:
                from work_data_hub.infrastructure.settings.data_source_schema import (
                    validate_data_sources_config,
                )

                validate_data_sources_config(str(config_path))
        except Exception as e:
            logger.debug("Optional data_sources validation skipped: %s", e)

        domains = data.get("domains") or {}
        valid_domains = sorted(domains.keys())

        if not valid_domains:
            logger.warning("No domains found in configuration, using default")
            return ["sandbox_trustee_performance"]

        logger.debug("Loaded %s valid domains: %s", len(valid_domains), valid_domains)
        return valid_domains

    except Exception as e:
        logger.error("Failed to load domains from configuration: %s", e)
        # Fallback to prevent complete failure
        return ["sandbox_trustee_performance"]


def ensure_psycopg2() -> Any:
    """
    Lazily load psycopg2 module, updating the global reference.

    Returns:
        The psycopg2 module

    Raises:
        DataWarehouseLoaderError: If psycopg2 is not available
    """
    from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

    global psycopg2
    if psycopg2 is None:
        # Explicitly treated as unavailable (tests may patch to None)
        raise DataWarehouseLoaderError(
            "psycopg2 not available for database operations"
        )
    if psycopg2 is _PSYCOPG2_NOT_LOADED:
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2
        except ImportError:
            raise DataWarehouseLoaderError(
                "psycopg2 not available for database operations"
            )
    return psycopg2
