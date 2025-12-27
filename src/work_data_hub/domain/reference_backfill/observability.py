"""
Observability service for reference data quality monitoring.

This module provides comprehensive observability for reference data quality,
including dashboard metrics, threshold-based alerts, CSV export for review,
and audit logging for reference data changes.

Implements the observability layer of the hybrid reference data strategy (AD-011).
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import structlog
import yaml
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .hybrid_service import HybridResult

logger = structlog.get_logger(__name__)

# Export limits (Story 7.1-16)
MAX_EXPORT_ROWS = 50000  # Maximum rows per export file to avoid disk churn


@dataclass
class ReferenceDataMetrics:
    """Metrics for a single reference table."""

    table: str
    total_records: int
    authoritative_count: int
    auto_derived_count: int
    needs_review_count: int
    auto_derived_ratio: float  # 0.0 - 1.0
    oldest_auto_derived: Optional[datetime] = None
    newest_auto_derived: Optional[datetime] = None
    domains_contributing: List[str] = field(default_factory=list)


@dataclass
class AlertConfig:
    """Configuration for observability alerts."""

    auto_derived_ratio_threshold: float = 0.10  # 10%
    needs_review_count_threshold: int = 100
    per_table_thresholds: Dict[str, float] = field(default_factory=dict)


@dataclass
class AlertResult:
    """Result of threshold check."""

    table: str
    alert_type: str  # "auto_derived_ratio" or "needs_review_count"
    current_value: float
    threshold: float
    message: str


class ObservabilityService:
    """
    Observability service for reference data quality monitoring.

    Provides: Dashboard metrics, Alerts, CSV export, Audit logging
    """

    DEFAULT_SCHEMA = "business"

    def __init__(
        self,
        schema: Optional[str] = None,
        alert_config: Optional[AlertConfig] = None,
        reference_tables: Optional[List[str]] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize the observability service.

        Args:
            schema: Database schema name (default: from env or "business")
            alert_config: Alert configuration (default: AlertConfig())
            reference_tables: List of reference tables to monitor (default: from config)
            config_path: Path to data_sources.yml config file
        """
        self.schema = schema or os.environ.get(
            "WDH_REFERENCE_SCHEMA", self.DEFAULT_SCHEMA
        )
        self.alert_config = alert_config or AlertConfig()
        self.logger = structlog.get_logger(__name__)

        # Load reference tables from config if not provided
        if reference_tables is None:
            self.reference_tables = self._load_reference_tables_from_config(config_path)
        else:
            self.reference_tables = reference_tables

    def _load_reference_tables_from_config(
        self, config_path: Optional[str]
    ) -> List[str]:
        """
        Load reference tables from config files.

        Story 6.2-P14: Config File Modularization
        - Loads from config/foreign_keys.yml for FK target tables
        - Loads from config/reference_sync.yml for sync target tables

        Args:
            config_path: Optional config path (currently unused)

        Returns:
            List of reference table names from the configs
        """
        project_root = os.environ.get("WDH_PROJECT_ROOT", ".")

        tables = set()

        # Load from foreign_keys.yml
        fk_config_path = Path(project_root) / "config" / "foreign_keys.yml"
        if fk_config_path.exists():
            try:
                with open(fk_config_path, "r", encoding="utf-8") as f:
                    fk_config = yaml.safe_load(f) or {}

                # Story 6.2-P14: New structure is domains.<name>.foreign_keys
                if "domains" in fk_config:
                    for domain_config in fk_config["domains"].values():
                        if "foreign_keys" in domain_config:
                            for fk in domain_config["foreign_keys"]:
                                target = fk.get("target_table")
                                if target:
                                    tables.add(target)
            except Exception as e:
                self.logger.warning(
                    "observability.fk_config_load_failed",
                    config_path=str(fk_config_path),
                    error=str(e),
                )

        # Load from reference_sync.yml
        sync_config_path = Path(project_root) / "config" / "reference_sync.yml"
        if sync_config_path.exists():
            try:
                with open(sync_config_path, "r", encoding="utf-8") as f:
                    sync_config = yaml.safe_load(f) or {}

                # Story 6.2-P14: New structure has tables at root level
                if "tables" in sync_config:
                    for table_config in sync_config["tables"]:
                        target = table_config.get("target_table")
                        if target:
                            tables.add(target)
            except Exception as e:
                self.logger.warning(
                    "observability.sync_config_load_failed",
                    config_path=str(sync_config_path),
                    error=str(e),
                )

        if not tables:
            raise ValueError(
                "no reference tables found in config/foreign_keys.yml or config/reference_sync.yml"
            )

        resolved = sorted(tables)
        self.logger.info(
            "observability.loaded_tables_from_config",
            fk_config=str(fk_config_path),
            sync_config=str(sync_config_path),
            tables=resolved,
        )
        return resolved

    def get_table_metrics(
        self,
        table: str,
        conn: Connection,
        *,
        domain_filter: Optional[str] = None,
        source_filter: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ReferenceDataMetrics:
        """
        Get data quality metrics for a single reference table.

        Args:
            table: Reference table name
            conn: Database connection

        Returns:
            ReferenceDataMetrics with counts and ratios

        Raises:
            Exception: If table doesn't exist or query fails
        """
        filters = []
        params: Dict[str, Any] = {}
        if domain_filter:
            filters.append('"_derived_from_domain" = :domain')
            params["domain"] = domain_filter
        if source_filter:
            filters.append(
                '"__source_filter__" IN (placeholder)'
            )  # placeholder to be replaced
        if start_date:
            filters.append('"_derived_at" >= :start_date')
            params["start_date"] = start_date
        if end_date:
            filters.append('"_derived_at" <= :end_date')
            params["end_date"] = end_date

        where_clause = ""
        if filters:
            # Handle source_filter separately to keep param ordering predictable
            if source_filter:
                filters = [
                    f for f in filters if not f.startswith('"__source_filter__"')
                ] + [
                    f'"_source" IN ({", ".join([f":source_{i}" for i in range(len(source_filter))])})'
                ]
                for i, src in enumerate(source_filter):
                    params[f"source_{i}"] = src
            where_clause = "WHERE " + " AND ".join(filters)

        query = text(f"""
            SELECT
                COUNT(*) as total_records,
                SUM(CASE WHEN "_source" = 'authoritative' THEN 1 ELSE 0 END) as authoritative_count,
                SUM(CASE WHEN "_source" = 'auto_derived' THEN 1 ELSE 0 END) as auto_derived_count,
                SUM(CASE WHEN "_needs_review" = true THEN 1 ELSE 0 END) as needs_review_count,
                MIN(CASE WHEN "_source" = 'auto_derived' THEN "_derived_at" END) as oldest_auto_derived,
                MAX(CASE WHEN "_source" = 'auto_derived' THEN "_derived_at" END) as newest_auto_derived
            FROM "{self.schema}"."{table}"
            {where_clause}
        """)

        result = conn.execute(query, params).fetchone()

        total = result.total_records or 0
        auto_derived = result.auto_derived_count or 0
        ratio = auto_derived / total if total > 0 else 0.0

        # Get contributing domains
        domains_query = text(f"""
            SELECT DISTINCT "_derived_from_domain"
            FROM "{self.schema}"."{table}"
            WHERE "_derived_from_domain" IS NOT NULL
        """)
        domains_result = conn.execute(
            domains_query, params if domain_filter else {}
        ).fetchall()
        domains = [row[0] for row in domains_result]

        return ReferenceDataMetrics(
            table=table,
            total_records=total,
            authoritative_count=result.authoritative_count or 0,
            auto_derived_count=auto_derived,
            needs_review_count=result.needs_review_count or 0,
            auto_derived_ratio=ratio,
            oldest_auto_derived=result.oldest_auto_derived,
            newest_auto_derived=result.newest_auto_derived,
            domains_contributing=domains,
        )

    def get_all_metrics(
        self,
        conn: Connection,
        *,
        domain_filter: Optional[str] = None,
        source_filter: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ReferenceDataMetrics]:
        """
        Get metrics for all reference tables dynamically.

        Args:
            conn: Database connection

        Returns:
            List of ReferenceDataMetrics for all configured tables
        """
        metrics = []
        for table in self.reference_tables:
            try:
                metrics.append(
                    self.get_table_metrics(
                        table,
                        conn,
                        domain_filter=domain_filter,
                        source_filter=source_filter,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
            except Exception as e:
                self.logger.warning(
                    "observability.table_metrics_failed",
                    table=table,
                    error=str(e),
                )
        return metrics

    def check_thresholds(
        self,
        metrics: List[ReferenceDataMetrics],
    ) -> List[AlertResult]:
        """
        Check metrics against configured thresholds.

        Args:
            metrics: List of table metrics to check

        Returns:
            List of AlertResult for threshold violations
        """
        alerts = []
        for m in metrics:
            # Check auto_derived ratio
            threshold = self.alert_config.per_table_thresholds.get(
                m.table, self.alert_config.auto_derived_ratio_threshold
            )
            if m.auto_derived_ratio > threshold:
                alert = AlertResult(
                    table=m.table,
                    alert_type="auto_derived_ratio",
                    current_value=m.auto_derived_ratio,
                    threshold=threshold,
                    message=f"Auto-derived ratio {m.auto_derived_ratio:.1%} exceeds threshold {threshold:.1%}",
                )
                alerts.append(alert)
                self.logger.warning(
                    "observability.threshold_exceeded",
                    table=alert.table,
                    alert_type=alert.alert_type,
                    current_value=alert.current_value,
                    threshold=alert.threshold,
                    message=alert.message,
                )

            # Check needs_review count
            if m.needs_review_count > self.alert_config.needs_review_count_threshold:
                alert = AlertResult(
                    table=m.table,
                    alert_type="needs_review_count",
                    current_value=float(m.needs_review_count),
                    threshold=float(self.alert_config.needs_review_count_threshold),
                    message=f"Needs review count {m.needs_review_count} exceeds threshold {self.alert_config.needs_review_count_threshold}",
                )
                alerts.append(alert)
                self.logger.warning(
                    "observability.threshold_exceeded",
                    table=alert.table,
                    alert_type=alert.alert_type,
                    current_value=alert.current_value,
                    threshold=alert.threshold,
                    message=alert.message,
                )

        return alerts

    def check_thresholds_from_hybrid_result(
        self,
        hybrid_result: HybridResult,
    ) -> List[AlertResult]:
        """
        Check thresholds using HybridResult metrics.

        Aligns with HybridReferenceService thresholds for consistency.

        Args:
            hybrid_result: Result from HybridReferenceService

        Returns:
            List of AlertResult for threshold violations
        """
        alerts = []

        # Check global auto_derived ratio
        if (
            hybrid_result.auto_derived_ratio
            > self.alert_config.auto_derived_ratio_threshold
        ):
            alert = AlertResult(
                table="<global>",
                alert_type="auto_derived_ratio",
                current_value=hybrid_result.auto_derived_ratio,
                threshold=self.alert_config.auto_derived_ratio_threshold,
                message=f"Global auto-derived ratio {hybrid_result.auto_derived_ratio:.1%} exceeds threshold {self.alert_config.auto_derived_ratio_threshold:.1%}",
            )
            alerts.append(alert)
            self.logger.warning(
                "observability.threshold_exceeded",
                table=alert.table,
                alert_type=alert.alert_type,
                current_value=alert.current_value,
                threshold=alert.threshold,
                message=alert.message,
            )

        # Check degraded mode
        if hybrid_result.degraded_mode:
            self.logger.warning(
                "observability.degraded_mode_detected",
                domain=hybrid_result.domain,
                reason=hybrid_result.degradation_reason,
            )

        return alerts

    def export_pending_review(
        self,
        table: str,
        conn: Connection,
        output_path: Optional[str] = None,
        domain_filter: Optional[str] = None,
        exclude_columns: Optional[List[str]] = None,
        config_path: Optional[str] = None,
        export_policy_path: Optional[str] = None,
    ) -> str:
        """
        Export records needing review to CSV using memory-safe streaming.

        Args:
            table: Reference table name
            conn: Database connection
            output_path: Optional output file path (default: exports/pending_review_{table}_{date}.csv)
            domain_filter: Optional domain filter
            exclude_columns: Optional list of sensitive columns to exclude (will be merged with config)
            config_path: Path to config file for sensitive field loading

        Returns:
            Path to exported CSV file

        Raises:
            Exception: If export fails or export policy is not defined
        """
        from datetime import date

        # Load sensitive fields from config and merge with manual exclude_columns
        sensitive_columns = self._load_sensitive_columns_from_config(table, config_path)
        if exclude_columns:
            self.logger.warning(
                "observability.manual_exclude_columns_supplied",
                table=table,
                manual_excludes=exclude_columns,
            )
            sensitive_columns.update(exclude_columns)

        # Check export policy (fail closed if missing)
        self._validate_export_policy(export_policy_path)

        # Build query
        where_clauses = ['"_needs_review" = true']
        params = {}
        if domain_filter:
            where_clauses.append('"_derived_from_domain" = :domain')
            params["domain"] = domain_filter

        query = text(f"""
            SELECT *
            FROM "{self.schema}"."{table}"
            WHERE {" AND ".join(where_clauses)}
            ORDER BY "_derived_at" DESC
        """)

        # Determine output path
        if output_path is None:
            output_dir = Path("exports")
            output_dir.mkdir(exist_ok=True)
            output_path = str(
                output_dir / f"pending_review_{table}_{date.today().isoformat()}.csv"
            )

        # Use chunksize for memory efficiency (10K rows per chunk)
        chunks = pd.read_sql(query, conn, params=params, chunksize=10000)

        first_chunk = True
        total_rows = 0
        for chunk in chunks:
            # Exclude sensitive columns
            if sensitive_columns:
                chunk = chunk.drop(
                    columns=[c for c in sensitive_columns if c in chunk.columns],
                    errors="ignore",
                )

            # Enforce backpressure: limit rows per file to avoid disk churn
            if total_rows + len(chunk) > MAX_EXPORT_ROWS:
                self.logger.warning(
                    "observability.export_row_limit_reached",
                    table=table,
                    current_rows=total_rows,
                    remaining_rows=len(chunk),
                )
                break

            mode = "w" if first_chunk else "a"
            header = first_chunk
            chunk.to_csv(
                output_path, mode=mode, header=header, index=False, encoding="utf-8-sig"
            )
            first_chunk = False
            total_rows += len(chunk)

        self.logger.info(
            "observability.csv_exported",
            table=table,
            output_path=str(output_path),
            total_rows=total_rows,
            sensitive_excluded=list(sensitive_columns) if sensitive_columns else None,
        )

        return str(output_path)

    def _load_sensitive_columns_from_config(
        self, table: str, config_path: Optional[str]
    ) -> set:
        """
        Load sensitive columns for a table from config.

        Story 6.2-P14: Config File Modularization
        - Default: load from config/reference_sync.yml
        - If config_path is provided, load from that path (tests/overrides)

        Args:
            table: Table name
            config_path: Optional path to reference_sync.yml (tests/overrides)

        Returns:
            Set of sensitive column names
        """
        if config_path is not None:
            # Explicit override (tests)
            sync_config_path = Path(config_path)
        else:
            # New default: use config/reference_sync.yml
            project_root = os.environ.get("WDH_PROJECT_ROOT", ".")
            sync_config_path = Path(project_root) / "config" / "reference_sync.yml"

        sensitive_columns = set()
        if not sync_config_path.exists():
            raise FileNotFoundError(
                f"reference_sync config not found: {sync_config_path}"
            )

        try:
            with open(sync_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # Story 6.2-P14 (Zero Legacy): tables are at root level in reference_sync.yml
            for table_config in config.get("tables", []) or []:
                if table_config.get("target_table") == table:
                    sensitive_fields = table_config.get("sensitive_fields", [])
                    sensitive_columns.update(sensitive_fields)

            if not sensitive_columns:
                raise ValueError(
                    f"sensitive_fields not defined for table '{table}' in {sync_config_path}"
                )

        except Exception as e:
            raise ValueError(
                f"failed to load sensitive fields for {table} from {sync_config_path}: {e}"
            ) from e

        return sensitive_columns

    def _validate_export_policy(self, export_policy_path: Optional[str] = None) -> None:
        """
        Validate that export policy is defined.

        Raises:
            Exception: If export policy is not defined
        """
        policy_path = (
            export_policy_path
            or os.environ.get("WDH_EXPORT_POLICY_PATH")
            or os.path.join("exports", "export_policy.yml")
        )
        policy_file = Path(policy_path)
        if not policy_file.exists():
            raise ValueError(
                f"export policy missing; expected at {policy_path}. "
                "Define retention/ACL/encryption policy before exporting."
            )


class ReferenceDataAuditLogger:
    """
    Audit logger for reference data changes.

    Logs all modifications to reference tables with structured events.
    """

    def __init__(self):
        """Initialize the audit logger."""
        self.logger = structlog.get_logger(__name__)

    def log_insert(
        self,
        table: str,
        record_key: str,
        source: str,
        domain: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> None:
        """
        Log an insert operation.

        Args:
            table: Reference table name
            record_key: Primary key value of inserted record
            source: Data source ('authoritative' or 'auto_derived')
            domain: Optional domain name
            actor: Optional actor/job identifier
        """
        self.logger.info(
            "reference_data.changed",
            table=table,
            operation="insert",
            record_key=record_key,
            old_source=None,
            new_source=source,
            domain=domain,
            actor=actor or "system",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def log_update(
        self,
        table: str,
        record_key: str,
        old_source: str,
        new_source: str,
        domain: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> None:
        """
        Log an update operation.

        Args:
            table: Reference table name
            record_key: Primary key value of updated record
            old_source: Previous data source
            new_source: New data source
            domain: Optional domain name
            actor: Optional actor/job identifier
        """
        self.logger.info(
            "reference_data.changed",
            table=table,
            operation="update",
            record_key=record_key,
            old_source=old_source,
            new_source=new_source,
            domain=domain,
            actor=actor or "system",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def log_delete(
        self,
        table: str,
        record_key: str,
        old_source: str,
        domain: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> None:
        """
        Log a delete operation.

        Args:
            table: Reference table name
            record_key: Primary key value of deleted record
            old_source: Previous data source
            domain: Optional domain name
            actor: Optional actor/job identifier
        """
        self.logger.info(
            "reference_data.changed",
            table=table,
            operation="delete",
            record_key=record_key,
            old_source=old_source,
            new_source=None,
            domain=domain,
            actor=actor or "system",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
