import logging
import sys
import time
import uuid
from typing import TYPE_CHECKING, List, Optional

# Static imports for compilation/linting, dynamic in methods for test patching
if TYPE_CHECKING:
    from psycopg2.pool import ThreadedConnectionPool

from functools import lru_cache

import pandas as pd

from work_data_hub.config import get_settings
from work_data_hub.io.loader.models import DataWarehouseLoaderError, LoadResult
from work_data_hub.io.loader.sql_utils import quote_ident, quote_qualified
from work_data_hub.utils.logging import get_logger

logger = logging.getLogger(__name__)
structured_logger = get_logger(__name__)


class WarehouseLoader:
    """Transactional PostgreSQL loader with pooling and column projection."""

    _DEFAULT_RETRY_ATTEMPTS = 3
    _DEFAULT_BACKOFF_MS = 1000

    def __init__(
        self,
        connection_url: Optional[str] = None,
        pool_size: Optional[int] = None,
        batch_size: Optional[int] = None,
        connect_timeout: int = 5,
    ):
        settings = get_settings()
        self.connection_url = (
            connection_url or settings.get_database_connection_string()
        )
        self.pool_size = pool_size or settings.DB_POOL_SIZE
        # Allow override but default to sensible batch size if not configured
        self.batch_size = batch_size or getattr(settings, "DB_BATCH_SIZE", 5000)
        self.connect_timeout = connect_timeout
        self._pool: Optional[ThreadedConnectionPool] = None
        self._logger = structured_logger

        self._logger.info(
            "database.loader.initialized",
            pool_size=self.pool_size,
            batch_size=self.batch_size,
        )
        self._health_check()

    def close(self):
        """Close the underlying connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            self._logger.info("database.loader.closed")

    def _health_check(self):
        """Validate pool connectivity with a lightweight query."""
        try:
            conn = self._get_connection_with_retry()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            self._pool.putconn(conn)
        except Exception as e:
            raise DataWarehouseLoaderError(f"Database connection failed: {e}") from e

    def _get_dynamic_import(self, attr_name: str, fallback_import):
        """
        Get a dynamically imported attribute, checking facade modules first for test patching.

        Args:
            attr_name: The attribute name to look for (e.g., "ThreadedConnectionPool")
            fallback_import: A callable that returns the default import if not found in facade

        Returns:
            The imported attribute
        """
        for name in [
            "src.work_data_hub.io.loader.warehouse_loader",
            "work_data_hub.io.loader.warehouse_loader",
        ]:
            if name in sys.modules:
                mod = sys.modules[name]
                if hasattr(mod, attr_name):
                    return getattr(mod, attr_name)
        return fallback_import()

    def _get_connection_with_retry(self):
        """Acquire a connection from the pool with retry on transient errors."""
        # Dynamic import to allow tests to patch ThreadedConnectionPool via the facade
        ThreadedConnectionPool = self._get_dynamic_import(
            "ThreadedConnectionPool",
            lambda: __import__(
                "psycopg2.pool", fromlist=["ThreadedConnectionPool"]
            ).ThreadedConnectionPool,
        )

        if self._pool is None or self._pool.closed:
            try:
                self._pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.pool_size,
                    dsn=self.connection_url,
                    connect_timeout=self.connect_timeout,
                )
            except Exception as e:
                raise DataWarehouseLoaderError(f"Failed to create pool: {e}") from e

        last_error = None
        for attempt in range(self._DEFAULT_RETRY_ATTEMPTS):
            try:
                # getconn() can fail if pool is exhausted or connections broken
                conn = self._pool.getconn()
                return conn
            except Exception as e:
                last_error = e
                wait_ms = self._DEFAULT_BACKOFF_MS * (2**attempt)
                time.sleep(wait_ms / 1000)

        raise DataWarehouseLoaderError(
            f"Failed to acquire connection after retries: {last_error}"
        ) from last_error

    @lru_cache(maxsize=128)
    def get_allowed_columns(self, table: str, schema: str = "public") -> List[str]:
        """Fetch and cache the allowed columns for a table."""
        # Note: In a production system we might cache this.
        # For now, we query generic_schema_info (if available) or raw catalog
        conn = self._get_connection_with_retry()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table),
                )
                columns = [row[0] for row in cursor.fetchall()]
                if not columns:
                    # Don't error here, just return empty list to let caller decide
                    # (But project_columns depends on this)
                    pass
                return columns
        finally:
            self._pool.putconn(conn)

    def project_columns(
        self, df: pd.DataFrame, table: str, schema: str = "public"
    ) -> pd.DataFrame:
        """Project DataFrame columns to the allowed schema-defined set."""
        allowed_cols = set(self.get_allowed_columns(table, schema))
        if not allowed_cols:
            raise DataWarehouseLoaderError(
                f"Table {schema}.{table} not found or has no columns"
            )

        # Identify extra columns
        df_cols = set(df.columns)
        extra_cols = df_cols - allowed_cols
        if extra_cols:
            self._logger.warning(
                "database.columns.ignored",
                table=table,
                ignored_columns=list(extra_cols),
                count=len(extra_cols),
            )

        # Identify missing non-nullable columns?
        # That's harder without nullability info. We assume DF has what's needed.
        # We only keep columns that exist in DB
        valid_cols = [c for c in df.columns if c in allowed_cols]
        if not valid_cols:
            raise DataWarehouseLoaderError(
                f"No matching columns between DataFrame and table {table}"
            )

        return df[valid_cols]

    def _chunk_dataframe(self, df: pd.DataFrame):
        """Yield DataFrame chunks respecting configured batch size."""
        for start in range(0, len(df), self.batch_size):
            yield df.iloc[start : start + self.batch_size]

    def _build_insert_query(
        self,
        columns: List[str],
        table: str,
        schema: str,
        upsert_keys: Optional[List[str]],
    ) -> str:
        qualified_table = quote_qualified(schema, table)
        quoted_cols = ",".join(quote_ident(col) for col in columns)
        query = f"INSERT INTO {qualified_table} ({quoted_cols}) VALUES %s"

        if upsert_keys:
            quoted_conflict = ",".join(quote_ident(key) for key in upsert_keys)
            update_targets = [col for col in columns if col not in upsert_keys]
            if not update_targets:
                update_targets = columns
            set_clause = ", ".join(
                f"{quote_ident(col)} = EXCLUDED.{quote_ident(col)}"
                for col in update_targets
            )
            query += f" ON CONFLICT ({quoted_conflict}) DO UPDATE SET {set_clause}"
            query += " RETURNING (xmax = 0) AS inserted"
        else:
            # Pure INSERT mode - no conflict handling, just return True for all rows
            query += " RETURNING TRUE AS inserted"
        return query

    def load_dataframe(
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        upsert_keys: Optional[List[str]] = None,
    ) -> LoadResult:
        """Load a DataFrame into PostgreSQL with ACID guarantees."""
        if not isinstance(df, pd.DataFrame):
            raise DataWarehouseLoaderError(
                "load_dataframe() requires a pandas DataFrame"
            )

        execution_id = uuid.uuid4().hex
        if df.empty:
            self._logger.info(
                "database.load.skipped",
                reason="empty_dataframe",
                table=table,
                schema=schema,
                execution_id=execution_id,
            )
            return LoadResult(True, 0, 0, 0.0, execution_id)

        projected_df = self.project_columns(df, table, schema)
        columns = list(projected_df.columns)
        query = self._build_insert_query(columns, table, schema, upsert_keys)

        conn = self._get_connection_with_retry()
        start_time = time.perf_counter()
        rows_inserted = 0
        rows_updated = 0

        self._logger.info(
            "database.load.started",
            table=table,
            schema=schema,
            rows=len(projected_df.index),
            execution_id=execution_id,
        )

        try:
            # Dynamic import to allow tests to patch execute_values via the facade
            execute_values_func = self._get_dynamic_import(
                "execute_values",
                lambda: __import__(
                    "psycopg2.extras", fromlist=["execute_values"]
                ).execute_values,
            )

            with conn.cursor() as cursor:
                for batch in self._chunk_dataframe(projected_df):
                    values = list(batch.itertuples(index=False, name=None))
                    if not values:
                        continue

                    execute_values_func(
                        cursor,
                        query,
                        values,
                        page_size=min(len(values), self.batch_size),
                    )
                    result_flags = cursor.fetchall()
                    inserted = sum(1 for (flag,) in result_flags if flag)
                    rows_inserted += inserted
                    rows_updated += len(result_flags) - inserted
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:  # pragma: no cover - best-effort rollback
                pass
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._logger.error(
                "database.load.failed",
                table=table,
                schema=schema,
                execution_id=execution_id,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise DataWarehouseLoaderError(
                f"Load failed for {schema}.{table}: {exc}"
            ) from exc
        finally:
            self._pool.putconn(conn)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._logger.info(
            "database.load.completed",
            table=table,
            schema=schema,
            execution_id=execution_id,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            duration_ms=duration_ms,
        )
        return LoadResult(
            success=True,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            duration_ms=duration_ms,
            execution_id=execution_id,
        )

    def load_with_refresh(
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        refresh_keys: Optional[List[str]] = None,
    ) -> LoadResult:
        """
        Load DataFrame using DELETE + INSERT pattern (Legacy-compatible refresh mode).

        This mode deletes all existing records matching the refresh_keys combinations
        in the input data, then inserts all new records. Suitable for detail tables
        where the same key combination can have multiple records.

        Unlike UPSERT mode (load_dataframe with upsert_keys), this does NOT require
        UNIQUE constraints on the database table.

        Args:
            df: DataFrame to load
            table: Target table name
            schema: Database schema (default: "public")
            refresh_keys: Columns defining the refresh scope. All existing records
                         matching unique combinations of these columns in the input
                         data will be deleted before inserting new records.
                         (Legacy equivalent: update_based_on_field)

        Returns:
            LoadResult with rows_inserted (new records) and rows_updated (deleted count)

        Example:
            # Refresh all records for specific month/business_type/plan_type
            # combinations
            loader.load_with_refresh(
                df,
                table="annuity_performance_NEW",
                refresh_keys=["月度", "业务类型", "计划类型"],
            )
        """
        if not isinstance(df, pd.DataFrame):
            raise DataWarehouseLoaderError(
                "load_with_refresh() requires a pandas DataFrame"
            )

        execution_id = uuid.uuid4().hex
        if df.empty:
            self._logger.info(
                "database.load.skipped",
                reason="empty_dataframe",
                table=table,
                schema=schema,
                execution_id=execution_id,
            )
            return LoadResult(True, 0, 0, 0.0, execution_id)

        if not refresh_keys:
            raise DataWarehouseLoaderError(
                "refresh_keys is required for load_with_refresh()"
            )

        # Validate refresh_keys exist in DataFrame
        missing_keys = [k for k in refresh_keys if k not in df.columns]
        if missing_keys:
            raise DataWarehouseLoaderError(
                f"refresh_keys {missing_keys} not found in DataFrame columns"
            )

        projected_df = self.project_columns(df, table, schema)
        columns = list(projected_df.columns)

        # Extract unique combinations of refresh_keys from input data
        unique_combinations = (
            df[refresh_keys].drop_duplicates().to_dict(orient="records")
        )

        conn = self._get_connection_with_retry()
        start_time = time.perf_counter()
        rows_deleted = 0
        rows_inserted = 0

        self._logger.info(
            "database.refresh.started",
            table=table,
            schema=schema,
            rows=len(projected_df.index),
            refresh_keys=refresh_keys,
            unique_combinations=len(unique_combinations),
            execution_id=execution_id,
        )

        try:
            with conn.cursor() as cursor:
                # Step 1: DELETE existing records matching refresh_keys combinations
                if unique_combinations:
                    qualified_table = quote_qualified(schema, table)
                    for combo in unique_combinations:
                        conditions = []
                        values = []
                        for key in refresh_keys:
                            val = combo[key]
                            if val is None:
                                conditions.append(f"{quote_ident(key)} IS NULL")
                            else:
                                conditions.append(f"{quote_ident(key)} = %s")
                                values.append(val)

                        delete_sql = (
                            f"DELETE FROM {qualified_table} "
                            f"WHERE {' AND '.join(conditions)}"
                        )
                        cursor.execute(delete_sql, values)
                        rows_deleted += cursor.rowcount if cursor.rowcount > 0 else 0

                # Step 2: INSERT all new records
                insert_query = self._build_insert_query(
                    columns, table, schema, upsert_keys=None
                )

                # Dynamic import for test compatibility
                execute_values_func = self._get_dynamic_import(
                    "execute_values",
                    lambda: __import__(
                        "psycopg2.extras", fromlist=["execute_values"]
                    ).execute_values,
                )

                for batch in self._chunk_dataframe(projected_df):
                    values = list(batch.itertuples(index=False, name=None))
                    if not values:
                        continue

                    execute_values_func(
                        cursor,
                        insert_query,
                        values,
                        page_size=min(len(values), self.batch_size),
                    )
                    # For pure INSERT, all rows are inserted
                    result_flags = cursor.fetchall()
                    rows_inserted += len(result_flags)

            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:  # pragma: no cover - best-effort rollback
                pass
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._logger.error(
                "database.refresh.failed",
                table=table,
                schema=schema,
                execution_id=execution_id,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise DataWarehouseLoaderError(
                f"Refresh load failed for {schema}.{table}: {exc}"
            ) from exc
        finally:
            self._pool.putconn(conn)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._logger.info(
            "database.refresh.completed",
            table=table,
            schema=schema,
            execution_id=execution_id,
            rows_deleted=rows_deleted,
            rows_inserted=rows_inserted,
            duration_ms=duration_ms,
        )
        # Use rows_updated to report deleted count for consistency with LoadResult
        # structure
        return LoadResult(
            success=True,
            rows_inserted=rows_inserted,
            rows_updated=rows_deleted,  # Repurpose as "rows affected by refresh"
            duration_ms=duration_ms,
            execution_id=execution_id,
        )
