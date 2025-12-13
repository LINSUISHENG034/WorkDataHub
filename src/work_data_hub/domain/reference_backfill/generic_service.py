"""
Generic backfill service for reference data management.

This module provides a configuration-driven service for backfilling reference
tables from fact data, supporting dependency ordering, tracking fields, and
idempotent operations.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from graphlib import TopologicalSorter, CycleError
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .models import ForeignKeyConfig, BackfillColumnMapping

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """Result of a backfill operation."""

    processing_order: List[str]
    tables_processed: List[Dict[str, int]]
    total_inserted: int
    total_skipped: int
    processing_time_seconds: float
    rows_per_second: Optional[float] = None


class GenericBackfillService:
    """
    Service for generic reference data backfill operations.

    Provides configuration-driven backfill of reference tables from fact data,
    with support for dependency ordering, tracking fields, and performance
    monitoring.
    """

    def __init__(self, domain: str, enable_audit_logging: bool = True):
        """
        Initialize the backfill service.

        Args:
            domain: Domain name for logging and tracking
            enable_audit_logging: Whether to enable audit logging for data changes
        """
        self.domain = domain
        self.logger = logging.getLogger(f"{__name__}.{domain}")
        self.enable_audit_logging = enable_audit_logging

    def run(
        self,
        df: pd.DataFrame,
        configs: List[ForeignKeyConfig],
        conn: Optional[Connection],
        add_tracking_fields: bool = True,
        plan_only: bool = False,
    ) -> BackfillResult:
        """
        Run backfill operations for all configured foreign keys.

        Args:
            df: DataFrame containing fact data
            configs: List of foreign key configurations
            conn: Database connection
            add_tracking_fields: Whether to add tracking fields to inserted records

        Returns:
            BackfillResult with operation statistics

        Raises:
            ValueError: If circular dependencies or unknown dependencies are detected
            ValueError: If plan_only is False but no database connection provided
        """
        if not plan_only and conn is None:
            raise ValueError("Database connection is required when plan_only is False")

        start_time = time.time()
        self.logger.info(f"Starting backfill for domain '{self.domain}' with {len(configs)} FK configs")

        # Sort configurations by dependency
        sorted_configs = self._topological_sort(configs)
        processing_order = [config.name for config in sorted_configs]

        self.logger.info(f"Processing order: {' -> '.join(processing_order)}")

        tables_processed = []
        total_inserted = 0
        total_skipped = 0

        for config in sorted_configs:
            try:
                # Derive candidates for this foreign key
                candidates_df = self.derive_candidates(df, config)

                if candidates_df.empty:
                    self.logger.warning(
                        f"No candidates derived for FK '{config.name}' "
                        f"(source_column: {config.source_column})"
                    )
                    tables_processed.append({
                        "table": config.target_table,
                        "inserted": 0,
                        "skipped": 0
                    })
                    continue

                if plan_only:
                    inserted_count = 0
                    skipped_count = len(candidates_df)
                else:
                    # Backfill the reference table
                    inserted_count = self.backfill_table(
                        candidates_df,
                        config,
                        conn,
                        add_tracking_fields=add_tracking_fields
                    )

                    # Calculate skipped records (duplicate primary keys)
                    total_candidates = len(candidates_df)
                    skipped_count = total_candidates - inserted_count

                tables_processed.append({
                    "table": config.target_table,
                    "inserted": inserted_count,
                    "skipped": skipped_count
                })

                total_inserted += inserted_count
                total_skipped += skipped_count

                self.logger.info(
                    f"Table '{config.target_table}': {inserted_count} inserted, "
                    f"{skipped_count} skipped (duplicates)"
                )

            except Exception as e:
                self.logger.error(f"Error processing FK '{config.name}': {e}")
                raise

        processing_time = time.time() - start_time
        rows_per_second = total_inserted / processing_time if processing_time > 0 and total_inserted > 0 else None

        result = BackfillResult(
            processing_order=processing_order,
            tables_processed=tables_processed,
            total_inserted=total_inserted,
            total_skipped=total_skipped,
            processing_time_seconds=processing_time,
            rows_per_second=rows_per_second
        )

        self.logger.info(
            f"Backfill completed: {total_inserted} total inserted, "
            f"{total_skipped} total skipped, {processing_time:.2f}s"
        )

        if rows_per_second:
            self.logger.info(f"Performance: {rows_per_second:.0f} rows/sec")

        return result

    def _topological_sort(self, configs: List[ForeignKeyConfig]) -> List[ForeignKeyConfig]:
        """
        Sort configurations by dependency using topological sorting.

        Args:
            configs: List of foreign key configurations

        Returns:
            Configurations sorted in dependency order

        Raises:
            ValueError: If circular dependencies or unknown dependencies are detected
        """
        # Create name to config mapping
        name_map = {config.name: config for config in configs}

        # Build dependency graph
        graph = {config.name: set(config.depends_on) for config in configs}

        # Validate all dependencies exist
        for name, deps in graph.items():
            for dep in deps:
                if dep not in name_map:
                    raise ValueError(
                        f"FK '{name}' depends on unknown key '{dep}'. "
                        f"Available keys: {list(name_map.keys())}"
                    )

        # Perform topological sort
        sorter = TopologicalSorter(graph)
        try:
            sorted_names = list(sorter.static_order())
        except CycleError as e:
            raise ValueError(f"Circular dependency detected in foreign keys: {e}")

        # Return configs in sorted order
        return [name_map[name] for name in sorted_names]

    def derive_candidates(self, df: pd.DataFrame, config: ForeignKeyConfig) -> pd.DataFrame:
        """
        Derive candidate records for a reference table from fact data.

        Args:
            df: DataFrame containing fact data
            config: Foreign key configuration

        Returns:
            DataFrame with candidate records for the reference table
        """
        # Check if source column exists
        if config.source_column not in df.columns:
            self.logger.warning(
                f"Source column '{config.source_column}' not found in data. "
                f"Available columns: {list(df.columns)}"
            )
            return pd.DataFrame()

        # Filter rows where source column is not null/blank
        source_series = df[config.source_column]
        source_mask = self._non_blank_mask(source_series)
        source_df = df[source_mask].copy()

        if source_df.empty:
            self.logger.warning(
                f"No non-null values found in source column '{config.source_column}'"
            )
            return pd.DataFrame()

        # Group by source column to get unique records
        grouped = source_df.groupby(config.source_column)

        candidates = []
        for source_value, group in grouped:
            candidate = {config.target_key: source_value}

            # Map additional columns
            for col_mapping in config.backfill_columns:
                # Find first non-null value in the group
                values = group[col_mapping.source]
                values = values[self._non_blank_mask(values)]

                if values.empty:
                    if col_mapping.optional:
                        # Optional column - skip if no values
                        candidate[col_mapping.target] = None
                    else:
                        # Required column - log warning but continue with None
                        self.logger.warning(
                            f"No values found for required column mapping "
                            f"'{col_mapping.source}' -> '{col_mapping.target}' "
                            f"for {config.source_column}='{source_value}'"
                        )
                        candidate[col_mapping.target] = None
                else:
                    # Use first value (could enhance with aggregation logic)
                    candidate[col_mapping.target] = values.iloc[0]

            candidates.append(candidate)

        candidates_df = pd.DataFrame(candidates)

        # Note: We do NOT filter out records where optional columns are null.
        # A record with only the primary key is still valid for backfill.
        # The primary key (target_key) is always present since we grouped by source_column.

        self.logger.info(
            f"Derived {len(candidates_df)} candidates for table '{config.target_table}' "
            f"from {len(source_df)} fact rows"
        )

        return candidates_df

    def backfill_table(
        self,
        candidates_df: pd.DataFrame,
        config: ForeignKeyConfig,
        conn: Connection,
        add_tracking_fields: bool = True,
    ) -> int:
        """
        Insert candidate records into the reference table.

        Args:
            candidates_df: DataFrame with candidate records
            config: Foreign key configuration
            conn: Database connection
            add_tracking_fields: Whether to add tracking fields

        Returns:
            Number of records inserted
        """
        if candidates_df.empty:
            return 0

        # Add tracking fields if requested
        if add_tracking_fields:
            candidates_df = self._add_tracking_fields(candidates_df)

        # Build INSERT ... ON CONFLICT DO NOTHING query
        # This ensures idempotency by ignoring existing records
        columns = list(candidates_df.columns)
        placeholders = [f":{col}" for col in columns]

        # Construct column list for conflict detection (primary key)
        conflict_columns = [config.target_key]

        # Pre-fetch existing keys for accurate audit logging
        records = candidates_df.to_dict('records')
        pk_values = [record[config.target_key] for record in records]
        existing_keys: Set[Any] = set()
        if pk_values:
            pk_placeholders = ", ".join([f":pk_{i}" for i in range(len(pk_values))])
            existing_query = text(f"""
                SELECT {config.target_key} FROM {config.target_table}
                WHERE {config.target_key} IN ({pk_placeholders})
            """)
            existing_params = {f"pk_{i}": v for i, v in enumerate(pk_values)}
            existing_keys = {
                row[0] for row in conn.execute(existing_query, existing_params).fetchall()
            }
        new_keys = {str(v) for v in pk_values} - {str(v) for v in existing_keys}

        # Different syntax for different databases
        if conn.dialect.name == 'postgresql':
            if config.mode == "fill_null_only":
                update_set = ", ".join(
                    [
                        f"{col} = CASE WHEN {config.target_table}.{col} IS NULL THEN EXCLUDED.{col} ELSE {config.target_table}.{col} END"
                        for col in columns
                        if col != config.target_key
                    ]
                )
                query = f"""
                    INSERT INTO {config.target_table} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE
                    SET {update_set}
                """
            else:
                query = f"""
                    INSERT INTO {config.target_table} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT ({', '.join(conflict_columns)}) DO NOTHING
                """
        elif conn.dialect.name == 'mysql':
            if config.mode == "fill_null_only":
                update_set = ", ".join(
                    [
                        f"{col}=IF({col} IS NULL, VALUES({col}), {col})"
                        for col in columns
                        if col != config.target_key
                    ]
                )
                query = f"""
                    INSERT INTO {config.target_table} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON DUPLICATE KEY UPDATE {update_set}
                """
            else:
                query = f"""
                    INSERT INTO {config.target_table} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
                """
        else:
            # Generic approach - check existence first
            # This is slower but works across databases
            existing_query = f"""
                SELECT {config.target_key} FROM {config.target_table}
                WHERE {config.target_key} IN :primary_keys
            """
            existing_keys = {
                row[0] for row in conn.execute(
                    text(existing_query),
                    {"primary_keys": tuple(candidates_df[config.target_key].tolist())}
                ).fetchall()
            }

            # Filter out existing records
            mask = ~candidates_df[config.target_key].isin(existing_keys)
            new_records_df = candidates_df[mask]

            if config.mode == "insert_missing":
                candidates_df = new_records_df
                if candidates_df.empty:
                    return 0

                query = f"""
                    INSERT INTO {config.target_table} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
            else:
                # fill_null_only: insert missing, then update null columns on existing keys
                inserted = 0
                if not new_records_df.empty:
                    insert_query = f"""
                        INSERT INTO {config.target_table} ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    records = new_records_df.to_dict('records')
                    insert_result = conn.execute(text(insert_query), records)
                    conn.commit()
                    inserted += insert_result.rowcount if hasattr(insert_result, 'rowcount') else len(records)

                # Update existing rows where columns are NULL and candidate has value
                existing_df = candidates_df[~mask]
                for record in existing_df.to_dict('records'):
                    pk_value = record[config.target_key]
                    update_fragments = []
                    params: Dict[str, Any] = {"pk": pk_value}
                    for col in columns:
                        if col == config.target_key:
                            continue
                        value = record[col]
                        if value is None:
                            continue
                        update_fragments.append(f"{col} = :{col}")
                        params[col] = value
                    if update_fragments:
                        update_query = f"""
                            UPDATE {config.target_table}
                            SET {', '.join(update_fragments)}
                            WHERE {config.target_key} = :pk AND (
                                {" OR ".join([f"{col} IS NULL" for col in params if col != 'pk'])}
                            )
                        """
                        conn.execute(text(update_query), params)
                conn.commit()

                # Return combined count (inserted records only; updates are idempotent fills)
                return inserted

        # Execute batch insert
        result = conn.execute(text(query), records)
        conn.commit()

        inserted_count = result.rowcount if hasattr(result, 'rowcount') else len(records)

        # Log audit events for inserted records
        if self.enable_audit_logging and add_tracking_fields and inserted_count > 0:
            # Import here to avoid circular import
            from .observability import ReferenceDataAuditLogger

            audit_logger = ReferenceDataAuditLogger()
            # Log inserts for new keys
            for record in records:
                pk = str(record[config.target_key])
                if pk in new_keys:
                    audit_logger.log_insert(
                        table=config.target_table,
                        record_key=pk,
                        source=record.get('_source', 'auto_derived'),
                        domain=record.get('_derived_from_domain'),
                        actor=f"backfill_service.{self.domain}"
                    )
                elif config.mode == "fill_null_only":
                    # Existing records updated with new values (fill nulls)
                    audit_logger.log_update(
                        table=config.target_table,
                        record_key=pk,
                        old_source="unknown",
                        new_source=record.get('_source', 'auto_derived'),
                        domain=record.get('_derived_from_domain'),
                        actor=f"backfill_service.{self.domain}"
                    )

        self.logger.debug(
            f"Inserted {inserted_count} records into '{config.target_table}' "
            f"from {len(candidates_df)} candidates"
        )

        return inserted_count

    @staticmethod
    def _non_blank_mask(series: pd.Series) -> pd.Series:
        """
        Determine non-blank (non-null, non-empty-string) mask for a Series.
        """
        mask = series.notna()
        if series.dtype == object or str(series.dtype).startswith("string"):
            mask &= series.astype(str).str.strip() != ""
        return mask

    def _add_tracking_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add tracking fields to candidate records.

        Args:
            df: DataFrame with candidate records

        Returns:
            DataFrame with tracking fields added
        """
        df = df.copy()

        # Standard tracking fields
        df['_source'] = 'auto_derived'
        df['_needs_review'] = True
        df['_derived_from_domain'] = self.domain
        df['_derived_at'] = datetime.now(timezone.utc).isoformat()

        return df
