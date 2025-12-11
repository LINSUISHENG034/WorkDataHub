"""
Output configuration helper for domain data loading.

This module provides utilities to retrieve output table configuration
from data_sources.yml with fallback logic for missing configuration.
"""

from datetime import datetime
from typing import Tuple

import structlog

from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourcesValidationError,
    get_domain_config_v2,
)

logger = structlog.get_logger(__name__)


def get_domain_output_config(
    domain_name: str,
    is_validation_mode: bool = True,
    config_path: str = "config/data_sources.yml",
) -> Tuple[str, str]:
    """
    Get output table configuration for a domain.

    This function reads the output configuration from data_sources.yml
    and applies the Strangler Fig pattern (_NEW suffix) when in validation mode.
    If configuration is missing, it falls back to a timestamped temporary table.

    Args:
        domain_name: Domain identifier (e.g., "annuity_performance")
        is_validation_mode: Apply Strangler Fig _NEW suffix (default: True)
        config_path: Path to data_sources.yml file (default: "config/data_sources.yml")

    Returns:
        Tuple of (table_name, schema_name)

    Raises:
        ValueError: If domain_name is invalid or empty

    Examples:
        >>> get_domain_output_config("annuity_performance")
        ("annuity_performance_NEW", "public")

        >>> get_domain_output_config("annuity_performance", is_validation_mode=False)
        ("annuity_performance", "public")

        >>> # When output config is missing, falls back to temp table
        >>> get_domain_output_config("unknown_domain")
        ("temp_unknown_domain_20251212_143022", "public")
    """
    # Validate input
    if not domain_name or not isinstance(domain_name, str):
        raise ValueError(f"Invalid domain_name: {domain_name}")

    try:
        # Load domain configuration from data_sources.yml
        domain_config = get_domain_config_v2(domain_name, config_path)

        # Check if output configuration exists
        if domain_config.output is None:
            # Fallback: Use timestamped temporary table
            timestamp = datetime.now().strftime("%Y%m%d")
            fallback_table = f"temp_{domain_name}_{timestamp}"
            fallback_schema = "public"

            logger.warning(
                "output.config.missing",
                domain=domain_name,
                fallback_table=fallback_table,
                fallback_schema=fallback_schema,
                message=f"Output configuration missing for domain '{domain_name}'. "
                f"Using fallback temporary table: {fallback_schema}.{fallback_table}",
            )

            return (fallback_table, fallback_schema)

        # Extract table and schema from configuration
        base_table = domain_config.output.table
        schema_name = domain_config.output.schema_name

        # Apply Strangler Fig pattern (_NEW suffix) if in validation mode
        if is_validation_mode:
            table_name = f"{base_table}_NEW"
        else:
            table_name = base_table

        logger.debug(
            "output.config.loaded",
            domain=domain_name,
            table=table_name,
            schema=schema_name,
            validation_mode=is_validation_mode,
        )

        return (table_name, schema_name)

    except DataSourcesValidationError as e:
        # Domain not found or configuration invalid
        logger.error(
            "output.config.error",
            domain=domain_name,
            error=str(e),
        )
        raise ValueError(f"Failed to load configuration for domain '{domain_name}': {e}")
