"""
PostgreSQL source adapter for reference data sync.

This module provides an adapter for fetching reference data from PostgreSQL
databases, supporting the generic data source adapter architecture.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from work_data_hub.domain.reference_backfill.sync_models import (
    ReferenceSyncTableConfig,
    PostgresSourceConfig,
)

logger = logging.getLogger(__name__)


class PostgresSourceAdapter:
    """
    Adapter for PostgreSQL data sources.

    Provides connection management, retry logic, and data fetching capabilities
    for syncing reference data from PostgreSQL databases.

    Supports configurable connection via environment variable prefix.
    """

    def __init__(
        self,
        connection_env_prefix: str = "WDH_LEGACY",
        connect_timeout: int = 30,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        """
        Initialize the PostgreSQL source adapter.

        Args:
            connection_env_prefix: Prefix for environment variables
                (e.g., "WDH_LEGACY_PG" -> WDH_LEGACY_PG_HOST, WDH_LEGACY_PG_PORT, etc.)
            connect_timeout: Connection timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff (seconds)
        """
        self.connection_env_prefix = connection_env_prefix
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.logger = logging.getLogger(f"{__name__}")

        # Load connection settings from environment
        def _get_env(key: str, default: str = "") -> str:
            primary = os.getenv(f"{connection_env_prefix}_{key}")
            if primary:
                return primary
            # Backward compatibility with earlier prefix WDH_LEGACY_PG
            legacy = os.getenv(f"WDH_LEGACY_PG_{key}")
            return legacy if legacy else default

        self.host = _get_env("HOST", "localhost")
        self.port = int(_get_env("PORT", "5432"))
        self.user = _get_env("USER", "postgres")
        self.password = _get_env("PASSWORD", "")
        self.database = _get_env("DATABASE", "legacy")

        # Log connection parameters (sanitized)
        self.logger.info(
            f"PostgreSQL source adapter initialized: host={self.host}, "
            f"port={self.port}, database={self.database}, "
            f"user={self.user}, connect_timeout={connect_timeout}, "
            f"max_retries={max_retries}"
        )

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        Get a connection to PostgreSQL with proper cleanup.

        Yields:
            psycopg2 connection object

        Raises:
            psycopg2.Error: If connection fails after all retries
        """
        conn = None
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(
                    f"PostgreSQL connection attempt {attempt}/{self.max_retries}"
                )

                conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    dbname=self.database,
                    connect_timeout=self.connect_timeout,
                    cursor_factory=RealDictCursor,
                )

                self.logger.info(
                    f"PostgreSQL connection established on attempt {attempt}"
                )

                try:
                    yield conn
                finally:
                    try:
                        conn.close()
                    except Exception as close_error:
                        self.logger.warning(
                            f"Error closing PostgreSQL connection: {str(close_error)}"
                        )
                return

            except psycopg2.Error as e:
                last_error = e
                self.logger.warning(
                    f"PostgreSQL connection failed on attempt {attempt}/{self.max_retries}: "
                    f"{type(e).__name__}: {str(e)}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    backoff_time = self.retry_backoff_base ** attempt
                    self.logger.info(
                        f"Retrying PostgreSQL connection after {backoff_time}s backoff"
                    )
                    time.sleep(backoff_time)
                else:
                    self.logger.error(
                        f"PostgreSQL connection exhausted after {self.max_retries} attempts: {str(e)}"
                    )

        # All retries exhausted
        error_msg = (
            f"Failed to connect to PostgreSQL after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
        self.logger.error(
            f"PostgreSQL connection failed final: {str(last_error)}"
        )
        raise psycopg2.Error(error_msg)

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Fetch reference data from PostgreSQL.

        Implements the DataSourceAdapter protocol for use with ReferenceSyncService.

        Args:
            table_config: Table sync configuration
            state: Optional state for incremental sync (e.g., last_synced_at)

        Returns:
            DataFrame with reference data

        Raises:
            ValueError: If source_config is invalid
            psycopg2.Error: If query execution fails
        """
        # Parse source configuration
        try:
            source_config = PostgresSourceConfig(**table_config.source_config)
        except Exception as e:
            error_msg = f"Invalid PostgreSQL source config: {e}"
            self.logger.error(
                f"Invalid PostgreSQL config for table {table_config.target_table}: {str(e)}"
            )
            raise ValueError(error_msg)

        # Build fully qualified table name (schema.table)
        full_table_name = f'"{source_config.source_schema}"."{source_config.table}"'

        # Build column list with proper quoting
        column_list = [f'"{mapping.source}"' for mapping in source_config.columns]
        query = f"SELECT {', '.join(column_list)} FROM {full_table_name}"

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
                )
            else:
                # PostgreSQL uses %(name)s for named parameters
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
            f"Fetching data from {source_config.source_schema}.{source_config.table} -> "
            f"{table_config.target_table} ({len(source_config.columns)} columns)"
        )

        # Execute query with retry logic
        try:
            df = self._execute_query_with_retry(
                query,
                params,
                source_config,
                table_config,
            )
        except psycopg2.Error as e:
            if incremental_used and self._is_missing_incremental_column_error(e):
                self.logger.warning(
                    "Incremental column missing, falling back to full refresh",
                )
                base_query = f"SELECT {', '.join(column_list)} FROM {full_table_name}"
                df = self._execute_query_with_retry(
                    base_query,
                    {},
                    source_config,
                    table_config,
                )
            else:
                raise

        # Apply column mappings
        df = self._apply_column_mappings(df, source_config)

        self.logger.info(
            f"Fetch complete: {source_config.source_schema}.{source_config.table} -> "
            f"{table_config.target_table} ({len(df)} rows)"
        )

        return df

    def _execute_query_with_retry(
        self,
        query: str,
        params: Dict[str, Any],
        source_config: PostgresSourceConfig,
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
            psycopg2.Error: If query fails after all retries
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
                        df = pd.DataFrame(columns=[m.source for m in source_config.columns])

                    self.logger.info(
                        f"Query success on attempt {attempt} for table {source_config.table}: {len(df)} rows"
                    )

                    return df

            except psycopg2.Error as e:
                last_error = e
                self.logger.warning(
                    f"Query failed on attempt {attempt}/{self.max_retries} for table {source_config.table}: "
                    f"{type(e).__name__}: {str(e)}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff
                    backoff_time = self.retry_backoff_base ** attempt
                    self.logger.info(
                        f"Retrying query after {backoff_time}s backoff"
                    )
                    time.sleep(backoff_time)

        # All retries exhausted
        error_msg = (
            f"Failed to execute query on table '{source_config.table}' "
            f"after {self.max_retries} attempts. Last error: {last_error}"
        )
        self.logger.error(
            f"Query failed final for table {source_config.table}: {str(last_error)}"
        )
        raise psycopg2.Error(error_msg)

    @staticmethod
    def _is_missing_incremental_column_error(err: psycopg2.Error) -> bool:
        """Detect missing column errors to allow graceful full-refresh fallback."""
        message = str(err).lower()
        # PostgreSQL error code 42703 = undefined_column
        pgcode = getattr(err, 'pgcode', None)
        return (pgcode == '42703') or ("column" in message and "does not exist" in message)

    def _apply_column_mappings(
        self,
        df: pd.DataFrame,
        source_config: PostgresSourceConfig,
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
            mapping.source: mapping.target
            for mapping in source_config.columns
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

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
