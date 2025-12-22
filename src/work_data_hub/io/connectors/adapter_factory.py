"""
Data source adapter factory for reference data sync.

This module provides a factory for creating data source adapters based on
configuration, supporting the generic data source adapter architecture.
"""

import logging
from typing import Any, Dict, Optional, Protocol

import pandas as pd

from work_data_hub.domain.reference_backfill.sync_models import ReferenceSyncTableConfig

logger = logging.getLogger(__name__)


class DataSourceAdapter(Protocol):
    """
    Protocol for data source adapters.

    All adapters must implement this interface to be compatible with
    the ReferenceSyncService.
    """

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Fetch reference data from the source.

        Args:
            table_config: Table sync configuration
            state: Optional state for incremental sync

        Returns:
            DataFrame with reference data
        """
        ...


class AdapterFactory:
    """
    Factory for creating data source adapters.

    Creates appropriate adapter instances based on source_type configuration.
    Supports PostgreSQL, MySQL, and config file sources.
    """

    # Cache for adapter instances (singleton per source_type + config)
    _adapter_cache: Dict[str, DataSourceAdapter] = {}

    @classmethod
    def create(
        cls,
        source_type: str,
        connection_env_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> DataSourceAdapter:
        """
        Create a data source adapter based on source type.

        Args:
            source_type: Type of data source ("postgres", "legacy_mysql", "mysql", "config_file")
            connection_env_prefix: Optional environment variable prefix for connection settings
            **kwargs: Additional adapter-specific configuration

        Returns:
            DataSourceAdapter instance

        Raises:
            ValueError: If source_type is unknown
        """
        # Generate cache key
        cache_key = f"{source_type}:{connection_env_prefix or 'default'}"

        # Return cached adapter if available
        if cache_key in cls._adapter_cache:
            logger.debug(f"Returning cached adapter for {cache_key}")
            return cls._adapter_cache[cache_key]

        # Create new adapter based on source_type
        adapter: DataSourceAdapter

        if source_type == "postgres":
            from work_data_hub.io.connectors.postgres_source_adapter import (
                PostgresSourceAdapter,
            )

            adapter = PostgresSourceAdapter(
                connection_env_prefix=connection_env_prefix or "WDH_LEGACY_PG",
                **kwargs,
            )
            logger.info(
                f"Created PostgresSourceAdapter with prefix {connection_env_prefix or 'WDH_LEGACY_PG'}"
            )

        elif source_type in ("legacy_mysql", "mysql"):
            from work_data_hub.io.connectors.mysql_source_adapter import (
                MySQLSourceAdapter,
            )

            adapter = MySQLSourceAdapter(**kwargs)
            logger.info("Created MySQLSourceAdapter (LegacyMySQLConnector wrapper)")

        elif source_type == "config_file":
            from work_data_hub.io.connectors.config_file_connector import (
                ConfigFileConnector,
            )

            adapter = ConfigFileConnector(**kwargs)
            logger.info("Created ConfigFileConnector")

        else:
            raise ValueError(
                f"Unknown source_type: '{source_type}'. "
                f"Supported types: 'postgres', 'legacy_mysql', 'mysql', 'config_file'"
            )

        # Cache the adapter
        cls._adapter_cache[cache_key] = adapter

        return adapter

    @classmethod
    def create_adapters_for_configs(
        cls,
        table_configs: list[ReferenceSyncTableConfig],
    ) -> Dict[str, DataSourceAdapter]:
        """
        Create adapters for a list of table configurations.

        Returns a dictionary mapping source_type to adapter instance,
        suitable for use with ReferenceSyncService.sync_all().

        Args:
            table_configs: List of table sync configurations

        Returns:
            Dictionary mapping source_type to adapter instance
        """
        adapters: Dict[str, DataSourceAdapter] = {}

        # Collect unique source types
        source_types = set(config.source_type for config in table_configs)

        for source_type in source_types:
            # Find first config with this source_type to get connection settings
            config = next(c for c in table_configs if c.source_type == source_type)

            # Extract connection_env_prefix if available
            connection_env_prefix = None
            if (
                source_type == "postgres"
                and "connection_env_prefix" in config.source_config
            ):
                connection_env_prefix = config.source_config["connection_env_prefix"]

            # Create adapter
            adapters[source_type] = cls.create(
                source_type=source_type,
                connection_env_prefix=connection_env_prefix,
            )

        logger.info(
            f"Created {len(adapters)} adapters for source types: {list(adapters.keys())}"
        )

        return adapters

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the adapter cache."""
        cls._adapter_cache.clear()
        logger.debug("Adapter cache cleared")
