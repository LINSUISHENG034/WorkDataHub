"""
MySQL source adapter implementing the generic DataSourceAdapter protocol.

This adapter wraps the existing LegacyMySQLConnector to provide a protocol-
compatible interface for reference sync.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

from work_data_hub.domain.reference_backfill.sync_models import (
    LegacyMySQLSourceConfig,
    ReferenceSyncTableConfig,
)
from work_data_hub.io.connectors.legacy_mysql_connector import LegacyMySQLConnector

logger = logging.getLogger(__name__)


class MySQLSourceAdapter:
    """Adapter for MySQL/legacy_mysql sources."""

    def __init__(self, **kwargs: Any) -> None:
        # Preserve compatibility with existing connector; kwargs kept for future parity
        self._delegate = LegacyMySQLConnector(**kwargs)
        self.logger = logging.getLogger(f"{__name__}.mysql_adapter")

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Fetch data via LegacyMySQLConnector to satisfy DataSourceAdapter."""
        try:
            source_config = LegacyMySQLSourceConfig(**table_config.source_config)
        except Exception as e:
            error_msg = f"Invalid MySQL source config: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # LegacyMySQLConnector already supports table + optional incremental where clause
        # Build a minimal request payload
        request = {
            "table": source_config.table,
            "columns": [m.source for m in source_config.columns],
            "incremental": source_config.incremental.model_dump()
            if source_config.incremental
            else None,
        }

        df = self._delegate.fetch_data(request, state=state)

        # Apply column mappings to target names
        rename_map = {m.source: m.target for m in source_config.columns}
        df = df.rename(columns=rename_map)
        return df
