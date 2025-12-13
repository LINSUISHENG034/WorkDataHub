"""
Reference sync service for pre-loading authoritative data.

This module provides a service for syncing reference data from authoritative
sources (Legacy MySQL, config files) to implement the Pre-load layer of the
hybrid reference data strategy (AD-011).
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Set

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .sync_models import ReferenceSyncTableConfig

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a reference sync operation."""

    table: str
    source_type: str
    rows_synced: int
    rows_deleted: int
    sync_mode: str
    duration_seconds: float
    error: Optional[str] = None


class DataSourceAdapter(Protocol):
    """Protocol for reference data source adapters."""

    def fetch_data(
        self,
        table_config: ReferenceSyncTableConfig,
        state: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Fetch reference data from source.

        Args:
            table_config: Table sync configuration
            state: Optional state for incremental sync (e.g., last_synced_at)

        Returns:
            DataFrame with reference data

        Raises:
            Exception: If data fetch fails
        """
        ...


class ReferenceSyncService:
    """
    Service for syncing reference data from authoritative sources.

    Implements the Pre-load layer of the hybrid reference data strategy (AD-011).
    Syncs data from multiple source types (Legacy MySQL, config files) and marks
    all records as authoritative data.
    """

    def __init__(self, domain: str = "reference_sync", enable_audit_logging: bool = True):
        """
        Initialize the sync service.

        Args:
            domain: Domain name for logging and tracking
            enable_audit_logging: Whether to enable audit logging for data changes
        """
        self.domain = domain
        self.logger = logging.getLogger(f"{__name__}.{domain}")
        self.enable_audit_logging = enable_audit_logging

    def sync_all(
        self,
        configs: List[ReferenceSyncTableConfig],
        adapters: Dict[str, DataSourceAdapter],
        conn: Connection,
        plan_only: bool = False,
        state: Optional[Dict[str, Any]] = None,
        default_batch_size: Optional[int] = None,
    ) -> List[SyncResult]:
        """
        Sync all configured reference tables.

        Args:
            configs: List of table sync configurations
            adapters: Dictionary mapping source_type to adapter instances
            conn: Database connection
            plan_only: If True, only plan without executing
            state: Optional per-table state, keyed by config.name
            default_batch_size: Optional global batch size override

        Returns:
            List of sync results for each table

        Raises:
            ValueError: If adapter not found for source type
        """
        self.logger.info(
            f"Starting reference sync for domain '{self.domain}' "
            f"with {len(configs)} table configs"
        )

        results = []
        for config in configs:
            # Get adapter for this source type
            adapter = adapters.get(config.source_type)
            if adapter is None:
                error_msg = (
                    f"No adapter found for source type '{config.source_type}'. "
                    f"Available adapters: {list(adapters.keys())}"
                )
                self.logger.error(error_msg)
                results.append(
                    SyncResult(
                        table=config.target_table,
                        source_type=config.source_type,
                        rows_synced=0,
                        rows_deleted=0,
                        sync_mode=config.sync_mode,
                        duration_seconds=0.0,
                        error=error_msg,
                    )
                )
                continue

            # Sync this table
            try:
                result = self.sync_table(
                    config=config,
                    adapter=adapter,
                    conn=conn,
                    plan_only=plan_only,
                    state_for_table=(state or {}).get(config.name),
                    default_batch_size=default_batch_size,
                )
                results.append(result)
            except Exception as e:
                self.logger.error(
                    f"Error syncing table '{config.target_table}': {e}",
                    exc_info=True,
                )
                results.append(
                    SyncResult(
                        table=config.target_table,
                        source_type=config.source_type,
                        rows_synced=0,
                        rows_deleted=0,
                        sync_mode=config.sync_mode,
                        duration_seconds=0.0,
                        error=str(e),
                    )
                )

        # Log summary
        total_synced = sum(r.rows_synced for r in results)
        total_deleted = sum(r.rows_deleted for r in results)
        failed_count = sum(1 for r in results if r.error is not None)

        self.logger.info(
            f"Reference sync completed: {total_synced} rows synced, "
            f"{total_deleted} rows deleted, {failed_count} failures"
        )

        return results

    def sync_table(
        self,
        config: ReferenceSyncTableConfig,
        adapter: DataSourceAdapter,
        conn: Connection,
        plan_only: bool = False,
        state_for_table: Optional[Dict[str, Any]] = None,
        default_batch_size: Optional[int] = None,
    ) -> SyncResult:
        """
        Sync a single reference table.

        Args:
            config: Table sync configuration
            adapter: Data source adapter
            conn: Database connection
            plan_only: If True, only plan without executing
            state_for_table: Optional state data for incremental sync
            default_batch_size: Optional global batch size override

        Returns:
            Sync result with operation statistics

        Raises:
            Exception: If sync operation fails
        """
        start_time = time.time()
        self.logger.info(
            f"Syncing table '{config.target_table}' from {config.source_type} "
            f"(mode: {config.sync_mode})"
        )

        batch_size = (
            config.batch_size
            if config.batch_size is not None
            else default_batch_size
            if default_batch_size is not None
            else 5000
        )

        try:
            # Fetch data from source
            df = adapter.fetch_data(config, state=state_for_table)

            if df.empty:
                self.logger.warning(
                    f"No data fetched for table '{config.target_table}' "
                    f"from {config.source_type}"
                )
                return SyncResult(
                    table=config.target_table,
                    source_type=config.source_type,
                    rows_synced=0,
                    rows_deleted=0,
                    sync_mode=config.sync_mode,
                    duration_seconds=time.time() - start_time,
                )

            # Add authoritative tracking fields
            df = self._add_authoritative_tracking_fields(df)
            self._warn_if_string_columns_exceed_limit(df)

            if plan_only:
                self.logger.info(
                    f"Plan-only mode: Would sync {len(df)} rows to '{config.target_table}'"
                )
                return SyncResult(
                    table=config.target_table,
                    source_type=config.source_type,
                    rows_synced=0,
                    rows_deleted=0,
                    sync_mode=config.sync_mode,
                    duration_seconds=time.time() - start_time,
                )

            # Execute sync based on mode
            if config.sync_mode == "delete_insert":
                rows_deleted, rows_synced = self._sync_delete_insert(
                    df, config, conn, batch_size=batch_size
                )
            else:  # upsert
                rows_deleted = 0
                rows_synced = self._sync_upsert(
                    df, config, conn, batch_size=batch_size
                )

            duration = time.time() - start_time
            self.logger.info(
                f"Table '{config.target_table}' synced: {rows_synced} rows, "
                f"{rows_deleted} deleted, {duration:.2f}s"
            )

            return SyncResult(
                table=config.target_table,
                source_type=config.source_type,
                rows_synced=rows_synced,
                rows_deleted=rows_deleted,
                sync_mode=config.sync_mode,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to sync table '{config.target_table}': {e}",
                exc_info=True,
            )
            raise

    def _add_authoritative_tracking_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add tracking fields for authoritative data.

        All pre-loaded data is marked as authoritative and does not need review.

        Args:
            df: DataFrame with reference data

        Returns:
            DataFrame with tracking fields added
        """
        df = df.copy()

        # Authoritative data tracking fields
        df['_source'] = 'authoritative'
        df['_needs_review'] = False
        df['_derived_from_domain'] = None
        df['_derived_at'] = None

        return df

    def _warn_if_string_columns_exceed_limit(
        self,
        df: pd.DataFrame,
        limit: int = 255,
    ) -> None:
        """
        Emit warnings when object columns contain strings that exceed a sane limit.

        This is a lightweight guard to catch obvious length mismatches between
        source data and typical VARCHAR targets without requiring schema introspection.
        """
        if df.empty:
            return

        object_cols = df.select_dtypes(include=["object"]).columns
        for col in object_cols:
            max_len = (
                df[col].astype(str).str.len().max()  # type: ignore[assignment]
                if not df[col].isna().all()
                else 0
            )
            if max_len and max_len > limit:
                self.logger.warning(
                    "reference_sync.length_warning",
                    column=col,
                    max_len=int(max_len),
                    limit=limit,
                )

    def _sync_delete_insert(
        self,
        df: pd.DataFrame,
        config: ReferenceSyncTableConfig,
        conn: Connection,
        batch_size: int,
    ) -> tuple[int, int]:
        """
        Sync using delete-insert strategy.

        Deletes all existing records and inserts new ones in a transaction.

        Args:
            df: DataFrame with reference data
            config: Table sync configuration
            conn: Database connection

        Returns:
            Tuple of (rows_deleted, rows_inserted)
        """
        full_table_name = f'"{config.target_schema}"."{config.target_table}"'

        audit_logger = None
        if self.enable_audit_logging:
            from .observability import ReferenceDataAuditLogger
            audit_logger = ReferenceDataAuditLogger()

        # Capture keys before delete for audit logging
        existing_keys: List[str] = []
        if audit_logger:
            select_keys = text(f'SELECT "{config.primary_key}" FROM {full_table_name}')
            existing_keys = [str(row[0]) for row in conn.execute(select_keys).fetchall()]

        # Start transaction
        trans = conn.begin()
        try:
            # Delete all existing records
            delete_query = f"DELETE FROM {full_table_name}"
            delete_result = conn.execute(text(delete_query))
            rows_deleted = delete_result.rowcount if hasattr(delete_result, 'rowcount') else 0

            self.logger.debug(
                f"Deleted {rows_deleted} existing rows from '{config.target_table}'"
            )

            if audit_logger and existing_keys:
                for key in existing_keys:
                    audit_logger.log_delete(
                        table=config.target_table,
                        record_key=key,
                        old_source="authoritative",
                        actor=f"sync_service.{self.domain}",
                    )

            # Insert new records in batches
            rows_inserted = self._batch_insert(df, config, conn, batch_size=batch_size)

            # Log audit events for inserted records
            if audit_logger and rows_inserted > 0:
                # Re-fetch inserted records for audit logging
                inserted_query = f'SELECT "{config.primary_key}" FROM {full_table_name}'
                inserted_keys = [str(row[0]) for row in conn.execute(text(inserted_query)).fetchall()]

                for record_key in inserted_keys:
                    audit_logger.log_insert(
                        table=config.target_table,
                        record_key=record_key,
                        source='authoritative',
                        actor=f"sync_service.{self.domain}"
                    )

            # Commit transaction
            trans.commit()

            return rows_deleted, rows_inserted

        except Exception as e:
            trans.rollback()
            self.logger.error(
                f"Transaction rolled back for table '{config.target_table}': {e}"
            )
            raise

    def _sync_upsert(
        self,
        df: pd.DataFrame,
        config: ReferenceSyncTableConfig,
        conn: Connection,
        batch_size: int,
    ) -> int:
        """
        Sync using upsert strategy.

        Inserts new records or updates existing ones based on primary key.

        Args:
            df: DataFrame with reference data
            config: Table sync configuration
            conn: Database connection

        Returns:
            Number of rows synced (inserted or updated)
        """
        full_table_name = f'"{config.target_schema}"."{config.target_table}"'
        columns = list(df.columns)
        placeholders = [f":{col}" for col in columns]

        audit_logger = None
        if self.enable_audit_logging:
            from .observability import ReferenceDataAuditLogger
            audit_logger = ReferenceDataAuditLogger()

        pk_values = df[config.primary_key].tolist()
        existing_keys: Set[Any] = set()
        if audit_logger and pk_values:
            pk_placeholders = ", ".join([f":pk_{i}" for i in range(len(pk_values))])
            existing_query = text(f"""
                SELECT "{config.primary_key}" FROM {full_table_name}
                WHERE "{config.primary_key}" IN ({pk_placeholders})
            """)
            existing_params = {f"pk_{i}": v for i, v in enumerate(pk_values)}
            existing_keys = {
                row[0] for row in conn.execute(existing_query, existing_params).fetchall()
            }

        # Build upsert query based on database dialect
        if conn.dialect.name == 'postgresql':
            # PostgreSQL: INSERT ... ON CONFLICT DO UPDATE
            update_set = ", ".join(
                [f'"{col}" = EXCLUDED."{col}"' for col in columns if col != config.primary_key]
            )
            query = f"""
                INSERT INTO {full_table_name} ({', '.join([f'"{col}"' for col in columns])})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT ("{config.primary_key}") DO UPDATE
                SET {update_set}
            """
        elif conn.dialect.name == 'mysql':
            # MySQL: INSERT ... ON DUPLICATE KEY UPDATE
            update_set = ", ".join(
                [f"{col}=VALUES({col})" for col in columns if col != config.primary_key]
            )
            query = f"""
                INSERT INTO {full_table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON DUPLICATE KEY UPDATE {update_set}
            """
        else:
            # Generic approach: check existence and insert/update separately
            return self._generic_upsert(df, config, conn, batch_size=batch_size)

        # Execute batch upsert
        records = df.to_dict('records')
        result = conn.execute(text(query), records)
        conn.commit()

        rows_synced = result.rowcount if hasattr(result, 'rowcount') else len(records)

        # Log audit events for upserted records
        if audit_logger and rows_synced > 0:
            for record in records:
                record_key = str(record[config.primary_key])
                if record[config.primary_key] in existing_keys:
                    audit_logger.log_update(
                        table=config.target_table,
                        record_key=record_key,
                        old_source="authoritative",
                        new_source="authoritative",
                        actor=f"sync_service.{self.domain}"
                    )
                else:
                    audit_logger.log_insert(
                        table=config.target_table,
                        record_key=record_key,
                        source='authoritative',
                        actor=f"sync_service.{self.domain}"
                    )

        self.logger.debug(
            f"Upserted {rows_synced} rows into '{config.target_table}'"
        )

        return rows_synced

    def _generic_upsert(
        self,
        df: pd.DataFrame,
        config: ReferenceSyncTableConfig,
        conn: Connection,
        batch_size: int,
    ) -> int:
        """
        Generic upsert implementation for databases without native upsert.

        Args:
            df: DataFrame with reference data
            config: Table sync configuration
            conn: Database connection

        Returns:
            Number of rows synced
        """
        full_table_name = f'"{config.target_schema}"."{config.target_table}"'
        columns = list(df.columns)

        # Check which records exist
        if df.empty:
            return 0

        pk_values = df[config.primary_key].tolist()
        placeholder_list = ", ".join(
            [f":pk_{i}" for i in range(len(pk_values))]
        ) or ":pk_0"
        existing_query = f"""
            SELECT "{config.primary_key}" FROM {full_table_name}
            WHERE "{config.primary_key}" IN ({placeholder_list})
        """
        existing_params = {f"pk_{i}": v for i, v in enumerate(pk_values)}

        existing_keys = {
            row[0]
            for row in conn.execute(
                text(existing_query),
                existing_params,
            ).fetchall()
        }

        # Split into insert and update
        insert_mask = ~df[config.primary_key].isin(existing_keys)
        insert_df = df[insert_mask]
        update_df = df[~insert_mask]

        rows_synced = 0

        audit_logger = None
        if self.enable_audit_logging:
            from .observability import ReferenceDataAuditLogger
            audit_logger = ReferenceDataAuditLogger()

        # Insert new records
        if not insert_df.empty:
            rows_synced += self._batch_insert(
                insert_df, config, conn, batch_size=batch_size
            )
            if audit_logger:
                for record in insert_df.to_dict('records'):
                    audit_logger.log_insert(
                        table=config.target_table,
                        record_key=str(record[config.primary_key]),
                        source='authoritative',
                        actor=f"sync_service.{self.domain}"
                    )

        # Update existing records
        if not update_df.empty:
            for record in update_df.to_dict('records'):
                pk_value = record[config.primary_key]
                update_fragments = []
                params: Dict[str, Any] = {"pk": pk_value}

                for col in columns:
                    if col == config.primary_key:
                        continue
                    params[col] = record[col]
                    update_fragments.append(f'"{col}" = :{col}')

                    if update_fragments:
                        update_query = f"""
                            UPDATE {full_table_name}
                            SET {', '.join(update_fragments)}
                            WHERE "{config.primary_key}" = :pk
                        """
                        conn.execute(text(update_query), params)
                        rows_synced += 1

                    if audit_logger:
                        audit_logger.log_update(
                            table=config.target_table,
                            record_key=str(pk_value),
                            old_source="authoritative",
                            new_source="authoritative",
                            actor=f"sync_service.{self.domain}"
                        )

            conn.commit()

        return rows_synced

    def _batch_insert(
        self,
        df: pd.DataFrame,
        config: ReferenceSyncTableConfig,
        conn: Connection,
        batch_size: int = 5000,
    ) -> int:
        """
        Insert records in batches.

        Args:
            df: DataFrame with records to insert
            config: Table sync configuration
            conn: Database connection
            batch_size: Number of records per batch

        Returns:
            Total number of rows inserted
        """
        if df.empty:
            return 0

        full_table_name = f'"{config.target_schema}"."{config.target_table}"'
        columns = list(df.columns)
        placeholders = [f":{col}" for col in columns]

        insert_query = f"""
            INSERT INTO {full_table_name} ({', '.join([f'"{col}"' for col in columns])})
            VALUES ({', '.join(placeholders)})
        """

        total_inserted = 0
        records = df.to_dict('records')

        # Insert in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            result = conn.execute(text(insert_query), batch)
            batch_inserted = result.rowcount if hasattr(result, 'rowcount') else len(batch)
            total_inserted += batch_inserted

            self.logger.debug(
                f"Inserted batch {i // batch_size + 1}: {batch_inserted} rows"
            )

        conn.commit()

        return total_inserted
