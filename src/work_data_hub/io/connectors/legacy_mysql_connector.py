"""
Legacy MySQL connector for reference data sync.

This module provides a connector for fetching reference data from the Legacy
MySQL database, with support for connection pooling, retry logic, and
incremental sync.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.sync_models import (
    LegacyMySQLSourceConfig,
    ReferenceSyncTableConfig,
)

logger = logging.getLogger(__name__)

# MySQL error code for unknown column (Story 7.1-16)
MYSQL_UNKNOWN_COLUMN_ERROR = 1054


class LegacyMySQLConnector:
    """
    Connector for Legacy MySQL database.

    Provides connection management, retry logic, and data fetching capabilities
    for syncing reference data from the Legacy MySQL database.

    Uses WDH_LEGACY_MYSQL_* environment variables for connection configuration.
    """

    def __init__(
        self,
        pool_size: int = 5,
        max_overflow: int = 2,
        connect_timeout: int = 30,
        read_timeout: int = 30,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        """
        Initialize the Legacy MySQL connector.

        Args:
            pool_size: Connection pool size (not used with PyMySQL, for documentation)
            max_overflow: Maximum overflow connections (not used with PyMySQL)
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff (seconds)
        """
        self.settings = get_settings()
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.logger = logging.getLogger(f"{__name__}")

        # Log connection parameters (sanitized)
        self.logger.info(
            f"Legacy MySQL connector initialized: host={self.settings.legacy_mysql_host}, "
            f"port={self.settings.legacy_mysql_port}, database={self.settings.legacy_mysql_database}, "
            f"user={self.settings.legacy_mysql_user}, connect_timeout={connect_timeout}, "
            f"read_timeout={read_timeout}, max_retries={max_retries}"
        )

    @contextmanager
    def get_connection(self) -> Generator[pymysql.Connection, None, None]:
        """
        Get a connection to Legacy MySQL with proper cleanup.

        Yields:
            PyMySQL connection object

        Raises:
            pymysql.Error: If connection fails after all retries
        """
        conn = None
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(
                    f"Legacy MySQL connection attempt {attempt}/{self.max_retries}"
                )

                conn = pymysql.connect(
                    host=self.settings.legacy_mysql_host,
                    port=self.settings.legacy_mysql_port,
                    user=self.settings.legacy_mysql_user,
                    password=self.settings.legacy_mysql_password,
                    database=self.settings.legacy_mysql_database,
                    charset="utf8mb4",
                    cursorclass=DictCursor,
                    connect_timeout=self.connect_timeout,
                    read_timeout=self.read_timeout,
                )

                self.logger.info(
                    f"Legacy MySQL connection established on attempt {attempt}"
                )

                yield conn
                return

            except pymysql.Error as e:
                last_error = e
                self.logger.warning(
                    f"Legacy MySQL connection failed on attempt {attempt}/{self.max_retries}: "
                    f"{type(e).__name__}: {str(e)}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    backoff_time = self.retry_backoff_base**attempt
                    self.logger.info(
                        f"Retrying Legacy MySQL connection after {backoff_time}s backoff"
                    )
                    time.sleep(backoff_time)
                else:
                    self.logger.error(
                        f"Legacy MySQL connection exhausted after {self.max_retries} attempts: {str(e)}"
                    )

            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as close_error:
                        self.logger.warning(
                            f"Error closing Legacy MySQL connection: {str(close_error)}"
                        )

        # All retries exhausted
        error_msg = (
            f"Failed to connect to Legacy MySQL after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
        self.logger.error(f"Legacy MySQL connection failed final: {str(last_error)}")
        raise pymysql.Error(error_msg)

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Fetch reference data from Legacy MySQL.

        Implements the DataSourceAdapter protocol for use with ReferenceSyncService.

        Args:
            table_config: Table sync configuration

        Returns:
            DataFrame with reference data

        Raises:
            ValueError: If source_config is invalid
            pymysql.Error: If query execution fails
        """
        # Parse source configuration
        try:
            source_config = LegacyMySQLSourceConfig(**table_config.source_config)
        except Exception as e:
            error_msg = f"Invalid Legacy MySQL source config: {e}"
            self.logger.error(
                f"Invalid Legacy MySQL config for table {table_config.target_table}: {str(e)}"
            )
            raise ValueError(error_msg)

        # Build query
        column_list = [mapping.source for mapping in source_config.columns]
        query = f"SELECT {', '.join(column_list)} FROM {source_config.table}"

        # Add incremental WHERE clause if configured
        params: Dict[str, Any] = {}
        incremental_used = False
        if source_config.incremental:
            last_synced_at = None
            if state:
                last_synced_at = state.get("last_synced_at") or state.get(
                    "last_sync_at"
                )

            if last_synced_at is None:
                self.logger.warning(
                    "Incremental sync configured but no last_synced_at provided; falling back to full load",
                    table=source_config.table,
                )
            else:
                where_clause = source_config.incremental.where.replace(
                    ":last_synced_at", "%(last_synced_at)s"
                )
                query += f" WHERE {where_clause}"
                params["last_synced_at"] = last_synced_at
                incremental_used = True
                self.logger.info(
                    f"Incremental sync configured for table {source_config.table}: {source_config.incremental.where}"
                )

        self.logger.info(
            f"Fetching data from {source_config.table} -> {table_config.target_table} ({len(column_list)} columns)"
        )

        # Execute query with retry logic
        try:
            df = self._execute_query_with_retry(
                query,
                params,
                source_config,
                table_config,
            )
        except pymysql.Error as e:
            if incremental_used and self._is_missing_incremental_column_error(e):
                self.logger.warning(
                    "Incremental column missing, falling back to full refresh",
                    table=source_config.table,
                    error=str(e),
                )
                df = self._execute_query_with_retry(
                    f"SELECT {', '.join(column_list)} FROM {source_config.table}",
                    {},
                    source_config,
                    table_config,
                )
            else:
                raise

        # Apply column mappings
        df = self._apply_column_mappings(df, source_config)

        self.logger.info(
            f"Fetch complete: {source_config.table} -> {table_config.target_table} ({len(df)} rows)"
        )

        return df

    def _execute_query_with_retry(
        self,
        query: str,
        params: Dict[str, Any],
        source_config: LegacyMySQLSourceConfig,
        table_config: ReferenceSyncTableConfig,
    ) -> pd.DataFrame:
        """
        Execute query with retry logic.

        Args:
            query: SQL query to execute
            params: Query parameters
            source_config: Source configuration
            table_config: Table configuration

        Returns:
            DataFrame with query results

        Raises:
            pymysql.Error: If query fails after all retries
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with self.get_connection() as conn:
                    self.logger.debug(
                        f"Query attempt {attempt} for table {source_config.table}"
                    )

                    # Execute query
                    with conn.cursor() as cursor:
                        cursor.execute(query, params)
                        rows = cursor.fetchall()

                    # Convert to DataFrame
                    if rows:
                        df = pd.DataFrame(rows)
                    else:
                        # Empty result - create DataFrame with expected columns
                        df = pd.DataFrame(
                            columns=[m.source for m in source_config.columns]
                        )

                    self.logger.info(
                        f"Query success on attempt {attempt} for table {source_config.table}: {len(df)} rows"
                    )

                    return df

            except pymysql.Error as e:
                last_error = e
                self.logger.warning(
                    f"Query failed on attempt {attempt}/{self.max_retries} for table {source_config.table}: "
                    f"{type(e).__name__}: {str(e)}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff
                    backoff_time = self.retry_backoff_base**attempt
                    self.logger.info(f"Retrying query after {backoff_time}s backoff")
                    time.sleep(backoff_time)

        # All retries exhausted
        error_msg = (
            f"Failed to execute query on table '{source_config.table}' "
            f"after {self.max_retries} attempts. Last error: {last_error}"
        )
        self.logger.error(
            f"Query failed final for table {source_config.table}: {str(last_error)}"
        )
        raise pymysql.Error(error_msg)

    @staticmethod
    def _is_missing_incremental_column_error(err: pymysql.Error) -> bool:
        """Detect missing column errors to allow graceful full-refresh fallback."""
        message = str(err).lower()
        code = None
        if hasattr(err, "args") and err.args:
            try:
                code = int(err.args[0])
            except Exception:
                code = None
        return (code == MYSQL_UNKNOWN_COLUMN_ERROR) or ("unknown column" in message)

    def _apply_column_mappings(
        self,
        df: pd.DataFrame,
        source_config: LegacyMySQLSourceConfig,
    ) -> pd.DataFrame:
        """
        Apply column mappings from source to target names.

        Args:
            df: DataFrame with source column names
            source_config: Source configuration with column mappings

        Returns:
            DataFrame with target column names
        """
        if df.empty:
            # Create empty DataFrame with target column names
            target_columns = [mapping.target for mapping in source_config.columns]
            return pd.DataFrame(columns=target_columns)

        # Build rename mapping
        rename_map = {
            mapping.source: mapping.target for mapping in source_config.columns
        }

        # Rename columns
        df = df.rename(columns=rename_map)

        # Verify all expected columns are present
        expected_columns = set(rename_map.values())
        actual_columns = set(df.columns)
        missing_columns = expected_columns - actual_columns

        if missing_columns:
            self.logger.warning(
                f"Missing columns after mapping: expected {list(expected_columns)}, "
                f"got {list(actual_columns)}, missing {list(missing_columns)}"
            )

        return df
