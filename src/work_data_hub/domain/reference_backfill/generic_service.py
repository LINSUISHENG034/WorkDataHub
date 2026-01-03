"""
Generic backfill service for reference data management.

This module provides a configuration-driven service for backfilling reference
tables from fact data, supporting dependency ordering, tracking fields, and
idempotent operations.
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from graphlib import CycleError, TopologicalSorter
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

# SQL Module (Story 6.2-P10)
from work_data_hub.infrastructure.sql import (
    InsertBuilder,
    PostgreSQLDialect,
    build_indexed_params,
    qualify_table,
    remap_records,
)

from .models import (
    AggregationType,
    BackfillColumnMapping,
    ForeignKeyConfig,
)

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


def _qualified_table_name(config: ForeignKeyConfig) -> str:
    """Get fully qualified table name with schema."""
    return qualify_table(config.target_table, schema=config.target_schema)


class GenericBackfillService:
    """
    Service for generic reference data backfill operations.

    Provides configuration-driven backfill of reference tables from fact data,
    with support for dependency ordering, tracking fields, and performance
    monitoring.
    """

    def __init__(
        self,
        domain: str,
        enable_audit_logging: bool = True,
        audit_record_limit: int = 0,
    ):
        """
        Initialize the backfill service.

        Args:
            domain: Domain name for logging and tracking
            enable_audit_logging: Whether to enable audit logging for data changes
            audit_record_limit: Max per-record audit events per run (0 = always log a summary)
        """
        self.domain = domain
        self.logger = logging.getLogger(f"{__name__}.{domain}")
        self.enable_audit_logging = enable_audit_logging
        self.audit_record_limit = audit_record_limit

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
        self.logger.info(
            f"Starting backfill for domain '{self.domain}' with {len(configs)} FK configs"
        )

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
                    tables_processed.append(
                        {"table": config.target_table, "inserted": 0, "skipped": 0}
                    )
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
                        add_tracking_fields=add_tracking_fields,
                    )

                    # Calculate skipped records (duplicate primary keys)
                    total_candidates = len(candidates_df)
                    skipped_count = total_candidates - inserted_count

                tables_processed.append(
                    {
                        "table": config.target_table,
                        "inserted": inserted_count,
                        "skipped": skipped_count,
                    }
                )

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
        rows_per_second = (
            total_inserted / processing_time
            if processing_time > 0 and total_inserted > 0
            else None
        )

        result = BackfillResult(
            processing_order=processing_order,
            tables_processed=tables_processed,
            total_inserted=total_inserted,
            total_skipped=total_skipped,
            processing_time_seconds=processing_time,
            rows_per_second=rows_per_second,
        )

        self.logger.info(
            f"Backfill completed: {total_inserted} total inserted, "
            f"{total_skipped} total skipped, {processing_time:.2f}s"
        )

        if rows_per_second:
            self.logger.info(f"Performance: {rows_per_second:.0f} rows/sec")

        return result

    def _topological_sort(
        self, configs: List[ForeignKeyConfig]
    ) -> List[ForeignKeyConfig]:
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

    def derive_candidates(
        self, df: pd.DataFrame, config: ForeignKeyConfig
    ) -> pd.DataFrame:
        """
        Derive candidate records for a reference table from fact data.

        Story 6.2-P15: Supports aggregation strategies per column:
        - first: Default, takes first non-null value per group
        - max_by: Select value from row with maximum order_column value
        - concat_distinct: Concatenate distinct values with separator

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

        # Vectorized aggregation: "first non-blank per group per column"
        mapping_sources = [
            m.source
            for m in config.backfill_columns
            if m.source != config.source_column
        ]
        present_sources = [c for c in mapping_sources if c in source_df.columns]

        # Normalize blanks to NA for string-like columns so groupby.first skips them
        for col in present_sources:
            s = source_df[col]
            if s.dtype == object or str(s.dtype).startswith("string"):
                s = s.astype("string").str.strip()
                source_df[col] = s.mask(s == "", pd.NA)

        grouped_first = source_df.groupby(config.source_column, sort=False).first()

        # Build candidates DataFrame with aggregation strategies (Story 6.2-P15)
        candidates_df = pd.DataFrame({config.target_key: grouped_first.index})
        for col_mapping in config.backfill_columns:
            if col_mapping.source == config.source_column:
                candidates_df[col_mapping.target] = candidates_df[
                    config.target_key
                ].to_numpy()
                continue

            # Apply aggregation strategy
            if col_mapping.aggregation is None:
                # Default: first non-null value
                if col_mapping.source in grouped_first.columns:
                    candidates_df[col_mapping.target] = grouped_first[
                        col_mapping.source
                    ].to_numpy()
                else:
                    candidates_df[col_mapping.target] = None
            elif col_mapping.aggregation.type == AggregationType.MAX_BY:
                # max_by: value from row with maximum order_column
                candidates_df[col_mapping.target] = (
                    self._aggregate_max_by(source_df, config.source_column, col_mapping)
                    .reindex(grouped_first.index)
                    .to_numpy()
                )
            elif col_mapping.aggregation.type == AggregationType.CONCAT_DISTINCT:
                # concat_distinct: concatenate unique values
                candidates_df[col_mapping.target] = (
                    self._aggregate_concat_distinct(
                        source_df, config.source_column, col_mapping
                    )
                    .reindex(grouped_first.index)
                    .to_numpy()
                )
            elif col_mapping.aggregation.type == AggregationType.FIRST:
                # Explicit first: same as default
                if col_mapping.source in grouped_first.columns:
                    candidates_df[col_mapping.target] = grouped_first[
                        col_mapping.source
                    ].to_numpy()
                else:
                    candidates_df[col_mapping.target] = None
            elif col_mapping.aggregation.type == AggregationType.TEMPLATE:
                # Story 6.2-P18: template aggregation
                candidates_df[col_mapping.target] = (
                    self._aggregate_template(
                        source_df, config.source_column, col_mapping
                    )
                    .reindex(grouped_first.index)
                    .to_numpy()
                )
            elif col_mapping.aggregation.type == AggregationType.COUNT_DISTINCT:
                # Story 6.2-P18: count_distinct aggregation
                result = self._aggregate_count_distinct(
                    source_df, config.source_column, col_mapping
                )
                if result.empty:
                    candidates_df[col_mapping.target] = None
                else:
                    # Preserve Int64 type through reindex (avoid float conversion)
                    reindexed = result.reindex(grouped_first.index)
                    candidates_df[col_mapping.target] = pd.array(
                        reindexed, dtype="Int64"
                    )
            elif col_mapping.aggregation.type == AggregationType.LAMBDA:
                # Story 6.2-P18: lambda aggregation
                candidates_df[col_mapping.target] = (
                    self._aggregate_lambda(source_df, config.source_column, col_mapping)
                    .reindex(grouped_first.index)
                    .to_numpy()
                )

        # Match legacy behavior: optional missing values are represented as Python None
        for col_mapping in config.backfill_columns:
            if col_mapping.optional and col_mapping.target in candidates_df.columns:
                col = candidates_df[col_mapping.target]
                candidates_df[col_mapping.target] = col.where(col.notna(), None)

        # Note: We do NOT filter out records where optional columns are null.
        # A record with only the primary key is still valid for backfill.
        # The primary key (target_key) is always present since we grouped by source_column.

        self.logger.info(
            f"Derived {len(candidates_df)} candidates for table '{config.target_table}' "
            f"from {len(source_df)} fact rows"
        )

        return candidates_df

    def _aggregate_max_by(
        self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
    ) -> pd.Series:
        """
        Get value from row with maximum order_column value.

        Story 6.2-P15: Complex Mapping Backfill Enhancement
        Story 6.2-P16: Fixed TypeError when order_column has mixed types

        Falls back to 'first' aggregation when:
        - order_column doesn't exist in DataFrame (defensive)
        - All values in order_column are NULL for a group
        - order_column has mixed types that can't be compared

        Args:
            df: Source DataFrame
            group_col: Column to group by
            mapping: Column mapping with aggregation config

        Returns:
            Series with aggregated values indexed by group
        """
        order_col = mapping.aggregation.order_column

        # Defensive check: column existence
        if order_col not in df.columns:
            self.logger.warning(
                f"order_column '{order_col}' not found in DataFrame, "
                f"falling back to 'first' for column '{mapping.source}'"
            )
            return df.groupby(group_col)[mapping.source].first()

        # Story 6.2-P16: Convert order_column to numeric for safe comparison
        # This handles cases where the column has mixed float/str types
        order_series = pd.to_numeric(df[order_col], errors="coerce")

        # Per-group max_by with fallback for all-NULL order_column
        def max_by_with_fallback(group: pd.DataFrame) -> Any:
            # Use the converted numeric series for comparison
            group_indices = group.index
            numeric_vals = order_series.loc[group_indices]
            valid = numeric_vals.dropna()

            if valid.empty:
                # All order_column values are NULL or non-numeric, fallback to first
                self.logger.debug(
                    f"All '{order_col}' values NULL/non-numeric for group, using 'first' "
                    f"for column '{mapping.source}'"
                )
                first_val = group[mapping.source].iloc[0] if len(group) > 0 else None
                return first_val

            # Use idxmax on the valid numeric values
            try:
                max_idx = numeric_vals.idxmax(skipna=True)
                return group.loc[max_idx, mapping.source]
            except (TypeError, ValueError) as e:
                # Fallback on comparison errors
                self.logger.warning(
                    f"max_by comparison error for column '{mapping.source}': {e}, "
                    "falling back to 'first'"
                )
                return group[mapping.source].iloc[0] if len(group) > 0 else None

        return df.groupby(group_col, sort=False).apply(
            max_by_with_fallback, include_groups=False
        )

    def _aggregate_concat_distinct(
        self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
    ) -> pd.Series:
        """
        Concatenate distinct values with separator.

        Story 6.2-P15: Complex Mapping Backfill Enhancement

        Args:
            df: Source DataFrame
            group_col: Column to group by
            mapping: Column mapping with aggregation config

        Returns:
            Series with concatenated values indexed by group
        """
        sep = mapping.aggregation.separator
        sort_values = mapping.aggregation.sort

        def concat_func(x: pd.Series) -> str:
            # Drop NA and get unique values
            unique = x.dropna().unique()
            if len(unique) == 0:
                return pd.NA  # Handle empty case gracefully, returns NA for optional field handling

            # Convert to strings for sorting and joining
            str_values = [str(v) for v in unique]
            if sort_values:
                str_values = sorted(str_values)

            return sep.join(str_values)

        return df.groupby(group_col, sort=False)[mapping.source].agg(concat_func)

    def _aggregate_template(
        self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
    ) -> pd.Series:
        """
        Apply template string with field placeholders.

        Story 6.2-P18: Advanced Aggregation Capabilities

        Template format: "prefix_{field1}_suffix_{field2}"
        Placeholders are replaced with first non-null value from each group.

        Args:
            df: Source DataFrame
            group_col: Column to group by
            mapping: Column mapping with template config

        Returns:
            Series with formatted template strings per group

        Raises:
            ValueError: If template references non-existent field
        """
        template = mapping.aggregation.template
        template_fields = mapping.aggregation.template_fields or []

        # Auto-extract fields from template if not explicitly provided
        if not template_fields:
            template_fields = re.findall(r"\{(\w+)\}", template)

        # Validate all template fields exist in DataFrame
        missing_fields = [f for f in template_fields if f not in df.columns]
        if missing_fields:
            raise ValueError(f"Template references missing fields: {missing_fields}")

        def apply_template(group: pd.DataFrame) -> str:
            values = {}
            for field in template_fields:
                # Get first non-null value
                non_null = group[field].dropna()
                values[field] = str(non_null.iloc[0]) if len(non_null) > 0 else ""
            return template.format(**values)

        return df.groupby(group_col, sort=False).apply(
            apply_template, include_groups=False
        )

    def _aggregate_count_distinct(
        self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
    ) -> pd.Series:
        """
        Count distinct non-null values per group.

        Story 6.2-P18: Advanced Aggregation Capabilities

        Args:
            df: Source DataFrame
            group_col: Column to group by
            mapping: Column mapping configuration

        Returns:
            Series with count of distinct values per group
        """
        source_col = mapping.source
        if source_col not in df.columns:
            self.logger.warning(
                f"Source column '{source_col}' not found for count_distinct"
            )
            return pd.Series(dtype="Int64")

        # Filter out null/blank values before counting (per Sprint Change Proposal)
        valid_mask = self._non_blank_mask(df[source_col])
        filtered_df = df[valid_mask]

        if filtered_df.empty:
            return pd.Series(dtype="Int64")

        # Returns Int64 to ensure PostgreSQL integer compatibility
        result = filtered_df.groupby(group_col, sort=False)[source_col].nunique()
        return result.astype("Int64")

    def _aggregate_lambda(
        self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
    ) -> pd.Series:
        """
        Execute user-defined lambda expression on each group.

        Story 6.2-P18: Advanced Aggregation Capabilities

        Args:
            df: Source DataFrame
            group_col: Column to group by
            mapping: Column mapping with lambda code

        Returns:
            Series with lambda results per group
        """
        code = mapping.aggregation.code
        # Compile and evaluate the lambda expression
        lambda_func = eval(code)  # noqa: S307

        return df.groupby(group_col, sort=False).apply(
            lambda_func, include_groups=False
        )

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
        # Use indexed parameter names to avoid issues with Chinese column names (Story 6.2-P10)
        col_param_map, placeholders = build_indexed_params(columns)

        # Construct column list for conflict detection (primary key)
        conflict_columns = [config.target_key]

        # Pre-fetch existing keys for accurate audit logging
        records = candidates_df.to_dict("records")
        pk_values = [record[config.target_key] for record in records]
        existing_keys: Set[Any] = set()
        qualified_table = _qualified_table_name(config)
        if pk_values:
            pk_placeholders = ", ".join([f":pk_{i}" for i in range(len(pk_values))])
            existing_query = text(f"""
                SELECT "{config.target_key}" FROM {qualified_table}
                WHERE "{config.target_key}" IN ({pk_placeholders})
            """)
            existing_params = {f"pk_{i}": v for i, v in enumerate(pk_values)}
            existing_keys = {
                row[0]
                for row in conn.execute(existing_query, existing_params).fetchall()
            }
        new_keys = {str(v) for v in pk_values} - {str(v) for v in existing_keys}

        # Different syntax for different databases
        # Use InsertBuilder for PostgreSQL (Story 6.2-P10 SQL Module)
        if conn.dialect.name == "postgresql":
            dialect = PostgreSQLDialect()
            builder = InsertBuilder(dialect)
            update_columns = [col for col in columns if col != config.target_key]

            if config.mode == "fill_null_only":
                query = builder.upsert(
                    schema=config.target_schema,
                    table=config.target_table,
                    columns=columns,
                    placeholders=placeholders,
                    conflict_columns=conflict_columns,
                    mode="do_update",
                    update_columns=update_columns,
                    null_guard=True,
                )
            else:
                query = builder.upsert(
                    schema=config.target_schema,
                    table=config.target_table,
                    columns=columns,
                    placeholders=placeholders,
                    conflict_columns=conflict_columns,
                    mode="do_nothing",
                )
        elif conn.dialect.name == "mysql":
            if config.mode == "fill_null_only":
                update_set = ", ".join(
                    [
                        f"`{col}`=IF(`{col}` IS NULL, VALUES(`{col}`), `{col}`)"
                        for col in columns
                        if col != config.target_key
                    ]
                )
                query = f"""
                    INSERT INTO {qualified_table} ({", ".join(f'"{c}"' for c in columns)})
                    VALUES ({", ".join(placeholders)})
                    ON DUPLICATE KEY UPDATE {update_set}
                """
            else:
                query = f"""
                    INSERT INTO {qualified_table} ({", ".join(f'"{c}"' for c in columns)})
                    VALUES ({", ".join(placeholders)})
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
                """
        else:
            # Generic approach - check existence first
            # This is slower but works across databases
            existing_query = f"""
                SELECT "{config.target_key}" FROM {qualified_table}
                WHERE "{config.target_key}" IN :primary_keys
            """
            existing_keys = {
                row[0]
                for row in conn.execute(
                    text(existing_query),
                    {"primary_keys": tuple(candidates_df[config.target_key].tolist())},
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
                    INSERT INTO {qualified_table} ({", ".join(f'"{c}"' for c in columns)})
                    VALUES ({", ".join(placeholders)})
                """
            else:
                # fill_null_only: insert missing, then update null columns on existing keys
                inserted = 0
                if not new_records_df.empty:
                    insert_query = f"""
                        INSERT INTO {qualified_table} ({", ".join(f'"{c}"' for c in columns)})
                        VALUES ({", ".join(placeholders)})
                    """
                    records = new_records_df.to_dict("records")
                    insert_result = conn.execute(text(insert_query), records)
                    conn.commit()
                    rowcount = getattr(insert_result, "rowcount", None)
                    inserted += rowcount if isinstance(rowcount, int) else len(records)

                # Update existing rows where columns are NULL and candidate has value
                existing_df = candidates_df[~mask]
                for record in existing_df.to_dict("records"):
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
                            UPDATE {qualified_table}
                            SET {", ".join(update_fragments)}
                            WHERE {config.target_key} = :pk AND (
                                {" OR ".join([f"{col} IS NULL" for col in params if col != "pk"])}
                            )
                        """
                        conn.execute(text(update_query), params)
                conn.commit()

                # Return combined count (inserted records only; updates are idempotent fills)
                return inserted

        # Remap record keys to indexed parameter names (Story 6.2-P10)
        remapped_records = remap_records(records, col_param_map)

        # Execute batch insert
        result = conn.execute(text(query), remapped_records)
        conn.commit()

        rowcount = getattr(result, "rowcount", None)
        inserted_count = rowcount if isinstance(rowcount, int) else len(records)

        # Log audit events for inserted records
        if self.enable_audit_logging and add_tracking_fields and inserted_count > 0:
            # Import here to avoid circular import
            from .observability import ReferenceDataAuditLogger

            if self.audit_record_limit <= 0 or len(new_keys) > self.audit_record_limit:
                self.logger.info(
                    "Skipping per-record audit logging for large batch",
                    table=config.target_table,
                    new_keys=len(new_keys),
                    limit=self.audit_record_limit,
                    actor=f"backfill_service.{self.domain}",
                )
            else:
                audit_logger = ReferenceDataAuditLogger()
                # Log inserts for new keys
                for record in records:
                    pk = str(record[config.target_key])
                    if pk in new_keys:
                        audit_logger.log_insert(
                            table=config.target_table,
                            record_key=pk,
                            source=record.get("_source", "auto_derived"),
                            domain=record.get("_derived_from_domain"),
                            actor=f"backfill_service.{self.domain}",
                        )
                    elif config.mode == "fill_null_only":
                        # Existing records updated with new values (fill nulls)
                        audit_logger.log_update(
                            table=config.target_table,
                            record_key=pk,
                            old_source="unknown",
                            new_source=record.get("_source", "auto_derived"),
                            domain=record.get("_derived_from_domain"),
                            actor=f"backfill_service.{self.domain}",
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
        df["_source"] = "auto_derived"
        df["_needs_review"] = True
        df["_derived_from_domain"] = self.domain
        df["_derived_at"] = datetime.now(timezone.utc).isoformat()

        return df
