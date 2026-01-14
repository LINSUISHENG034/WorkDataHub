"""Multi-Table Data Loader.

从数据库多表加载数据并按配置策略合并。

Story: Orchestration Layer Refactor - Phase 0
"""

import logging
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine, text

from work_data_hub.config.domain_sources import (
    DomainSourceConfig,
    JoinStrategy,
    TableConfig,
)
from work_data_hub.config.settings import get_settings

logger = logging.getLogger(__name__)


class MultiTableLoader:
    """多表数据加载器.

    从数据库多表加载数据并按配置策略合并，输出与单文件加载一致的 List[Dict] 格式。
    """

    @classmethod
    def load(cls, config: DomainSourceConfig) -> List[Dict[str, Any]]:
        """
        从多张数据库表加载数据并按配置策略合并.

        Args:
            config: Domain 源配置

        Returns:
            统一格式的 List[Dict]，与单文件加载输出格式一致

        Raises:
            ValueError: 如果配置缺少必要的 tables 定义
        """
        if not config.tables:
            raise ValueError("multi_table config requires 'tables' definition")

        settings = get_settings()
        engine = create_engine(settings.get_database_connection_string())

        # Load each table by role
        tables_data: Dict[str, pd.DataFrame] = {}
        for table_cfg in config.tables:
            logger.info(
                f"Loading table: {table_cfg.schema}.{table_cfg.table} (role={table_cfg.role})"
            )
            df = cls._load_table(engine, table_cfg)
            tables_data[table_cfg.role] = df
            logger.info(f"Loaded {len(df)} rows from {table_cfg.table}")

        # Apply merge strategy
        merged = cls._apply_join_strategy(tables_data, config.join_strategy)
        logger.info(f"Merged result: {len(merged)} rows")

        return merged.to_dict(orient="records")

    @classmethod
    def _load_table(cls, engine, table_config: TableConfig) -> pd.DataFrame:
        """Load single table from database.

        Args:
            engine: SQLAlchemy engine
            table_config: Table configuration with schema, table, role

        Returns:
            DataFrame with table data
        """
        # Use quoted identifiers for schema and table names (support Chinese names)
        query = f'SELECT * FROM "{table_config.schema}"."{table_config.table}"'
        return pd.read_sql(text(query), engine)

    @classmethod
    def _apply_join_strategy(
        cls,
        tables_data: Dict[str, pd.DataFrame],
        strategy: JoinStrategy,
    ) -> pd.DataFrame:
        """Apply configured join strategy to merge tables.

        Args:
            tables_data: Dict mapping role names to DataFrames
            strategy: Join strategy configuration

        Returns:
            Merged DataFrame

        Raises:
            ValueError: If required tables are missing or strategy is unknown
        """
        # Default to merge_on_key if no strategy specified
        strategy_type = strategy.type if strategy else "merge_on_key"

        if strategy_type == "merge_on_key":
            return cls._merge_on_key(tables_data, strategy)
        elif strategy_type == "left_join":
            return cls._left_join(tables_data, strategy)
        elif strategy_type == "union":
            return cls._union(tables_data)
        else:
            raise ValueError(f"Unknown join strategy: {strategy_type}")

    @classmethod
    def _merge_on_key(
        cls,
        tables_data: Dict[str, pd.DataFrame],
        strategy: JoinStrategy,
    ) -> pd.DataFrame:
        """Merge primary and detail tables on key columns.

        Args:
            tables_data: Dict with 'primary' and optionally 'detail' DataFrames
            strategy: Join strategy with key_columns

        Returns:
            Merged DataFrame
        """
        primary = tables_data.get("primary")
        detail = tables_data.get("detail")

        if primary is None:
            raise ValueError("merge_on_key requires 'primary' role table")

        if detail is None:
            logger.warning("No 'detail' table found, returning primary only")
            return primary

        key_columns = strategy.key_columns if strategy else []
        if not key_columns:
            raise ValueError("merge_on_key requires key_columns to be specified")

        return primary.merge(detail, on=key_columns, how="left")

    @classmethod
    def _left_join(
        cls,
        tables_data: Dict[str, pd.DataFrame],
        strategy: JoinStrategy,
    ) -> pd.DataFrame:
        """Left join primary to detail tables.

        Args:
            tables_data: Dict with 'primary' and 'detail' DataFrames
            strategy: Join strategy with key_columns

        Returns:
            Left-joined DataFrame
        """
        primary = tables_data.get("primary")
        detail = tables_data.get("detail")

        if primary is None:
            raise ValueError("left_join requires 'primary' role table")

        if detail is None:
            return primary

        key_columns = strategy.key_columns if strategy else []
        return primary.merge(detail, on=key_columns, how="left")

    @classmethod
    def _union(cls, tables_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Concatenate all tables vertically.

        Args:
            tables_data: Dict of DataFrames to concatenate

        Returns:
            Concatenated DataFrame
        """
        if not tables_data:
            return pd.DataFrame()

        return pd.concat(list(tables_data.values()), ignore_index=True)
