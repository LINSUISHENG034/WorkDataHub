"""
Hybrid reference service for combining pre-load and backfill strategies.

This module provides a unified service that coordinates ReferenceSyncService
(pre-load) and GenericBackfillService (backfill) to implement the integration
layer of the hybrid reference data strategy (AD-011).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .generic_service import BackfillResult, GenericBackfillService
from .models import ForeignKeyConfig
from .sync_models import ReferenceSyncTableConfig
from .sync_service import ReferenceSyncService

logger = logging.getLogger(__name__)


@dataclass
class CoverageMetrics:
    """Coverage metrics for a single reference table."""

    table: str
    total_fk_values: int
    covered_values: int
    missing_values: int
    coverage_rate: float  # 0.0 - 1.0


@dataclass
class HybridResult:
    """Result of hybrid reference service operation."""

    domain: str
    pre_load_available: bool
    coverage_metrics: List[CoverageMetrics]
    backfill_result: Optional[BackfillResult]
    total_auto_derived: int
    total_authoritative: int
    auto_derived_ratio: float  # 0.0 - 1.0
    degraded_mode: bool
    degradation_reason: Optional[str] = None


class HybridReferenceService:
    """
    Unified service combining pre-load and backfill for reference data.

    Implements the integration layer of the hybrid reference data strategy (AD-011).
    Coordinates ReferenceSyncService (pre-load) and GenericBackfillService (backfill)
    to ensure FK references exist before fact data insertion.
    """

    def __init__(
        self,
        backfill_service: GenericBackfillService,
        sync_service: Optional[ReferenceSyncService] = None,
        auto_derived_threshold: float = 0.10,  # 10% warning threshold
        sync_configs: Optional[List[ReferenceSyncTableConfig]] = None,
        sync_adapters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the hybrid service.

        Args:
            backfill_service: Service for on-demand backfill
            sync_service: Optional service for pre-load (None = backfill-only mode)
            auto_derived_threshold: Threshold for auto_derived ratio warning
            sync_configs: Optional list of ReferenceSyncTableConfig for pre-load
            sync_adapters: Optional adapter map for ReferenceSyncService.sync_all
        """
        self.backfill = backfill_service
        self.sync = sync_service
        self.threshold = auto_derived_threshold
        self.sync_configs = sync_configs
        self.sync_adapters = sync_adapters
        self.logger = logging.getLogger(f"{__name__}")
        # Ensure warnings/metrics can be captured via root handlers (e.g. pytest caplog).
        if self.logger.propagate is False:
            self.logger.propagate = True
        if self.logger.level == logging.NOTSET:
            self.logger.setLevel(logging.DEBUG)

    def ensure_references(
        self,
        domain: str,
        df: pd.DataFrame,
        fk_configs: List[ForeignKeyConfig],
        conn: Connection,
    ) -> HybridResult:
        """
        Ensure all FK references exist before fact data insertion.

        Strategy:
        1. Check coverage of existing reference data
        2. Identify missing FK values
        3. Backfill only missing values
        4. Return comprehensive metrics

        Args:
            domain: Domain name for tracking
            df: Fact data DataFrame
            fk_configs: FK configurations for this domain
            conn: Database connection

        Returns:
            HybridResult with coverage metrics and backfill results
        """
        self.logger.info(
            f"Starting hybrid reference service for domain '{domain}' "
            f"with {len(fk_configs)} FK configs"
        )

        # Check if pre-load service is available
        pre_load_available = self.sync is not None
        degraded_mode = False
        degradation_reasons: List[str] = []

        # Optional pre-load step when configs + adapters are provided
        if self.sync and self.sync_configs and self.sync_adapters:
            try:
                self.logger.info(
                    "Running pre-load reference sync before coverage check "
                    f"(tables: {len(self.sync_configs)})"
                )
                self.sync.sync_all(
                    configs=self.sync_configs,
                    adapters=self.sync_adapters,
                    conn=conn,
                )
            except Exception as e:
                degraded_mode = True
                degradation_reasons.append(f"Pre-load failed: {e}")
                self.logger.error(
                    "Pre-load reference sync failed, continuing in degraded mode: %s",
                    e,
                )

        # Step 1: Check coverage of existing reference data with error handling
        coverage_metrics: List[CoverageMetrics] = []
        missing_by_table: Dict[str, Set[Any]] = {}
        failed_tables: List[str] = []

        for config in fk_configs:
            try:
                metrics, missing_values = self._check_coverage_for_config(
                    df, config, conn
                )
                if metrics:
                    coverage_metrics.append(metrics)
                    missing_by_table[config.target_table] = missing_values
                    self.logger.info(
                        f"Coverage for '{metrics.table}': "
                        f"{metrics.covered_values}/{metrics.total_fk_values} "
                        f"({metrics.coverage_rate:.1%})"
                    )
            except Exception as e:
                # AC #5: Graceful degradation - isolate per-table failures
                failed_tables.append(config.target_table)
                self.logger.warning(
                    f"Coverage check failed for table '{config.target_table}': {e}. "
                    f"Will use full backfill for this table."
                )
                # Add zero-coverage metric to trigger full backfill
                fk_values = (
                    set(df[config.source_column].dropna().unique())
                    if config.source_column in df.columns
                    else set()
                )
                coverage_metrics.append(
                    CoverageMetrics(
                        table=config.target_table,
                        total_fk_values=len(fk_values),
                        covered_values=0,
                        missing_values=len(fk_values),
                        coverage_rate=0.0,
                    )
                )
                missing_by_table[config.target_table] = fk_values

        # Set degradation status if any tables failed
        if failed_tables:
            degraded_mode = True
            degradation_reasons.append(
                f"Coverage check failed for tables: {', '.join(failed_tables)}"
            )

        # Step 2: Identify if backfill is needed
        total_missing = sum(m.missing_values for m in coverage_metrics)

        backfill_result = None
        if total_missing == 0:
            self.logger.info("All FK values covered, no backfill needed")
        else:
            # Step 3: Selective backfill for missing values
            self.logger.info(
                f"Backfilling {total_missing} missing FK values across "
                f"{len(fk_configs)} tables"
            )
            try:
                backfill_result = self._selective_backfill(
                    df, fk_configs, coverage_metrics, missing_by_table, conn
                )
            except Exception as e:
                # AC #5: Backfill errors don't block the pipeline
                degraded_mode = True
                degradation_reasons.append(f"Backfill failed: {e}")
                self.logger.error(
                    f"Backfill operation failed: {e}. Continuing with partial results."
                )

        # Step 4: Calculate auto_derived ratio with error handling
        try:
            total_auto_derived, total_authoritative, auto_derived_ratio = (
                self._calculate_auto_derived_ratio(fk_configs, conn)
            )
        except Exception as e:
            self.logger.warning(f"Failed to calculate auto_derived ratio: {e}")
            total_auto_derived = 0
            total_authoritative = 0
            auto_derived_ratio = 0.0

        # Check threshold and warn if exceeded (global)
        if auto_derived_ratio > self.threshold:
            self.logger.warning(
                f"Auto-derived ratio {auto_derived_ratio:.1%} exceeds "
                f"threshold {self.threshold:.1%}. Consider running reference_sync."
            )

        # AC #4: Per-table threshold warnings
        self._check_per_table_thresholds(fk_configs, conn)

        # Combine degradation reasons
        degradation_reason = (
            "; ".join(degradation_reasons) if degradation_reasons else None
        )

        result = HybridResult(
            domain=domain,
            pre_load_available=pre_load_available,
            coverage_metrics=coverage_metrics,
            backfill_result=backfill_result,
            total_auto_derived=total_auto_derived,
            total_authoritative=total_authoritative,
            auto_derived_ratio=auto_derived_ratio,
            degraded_mode=degraded_mode,
            degradation_reason=degradation_reason,
        )

        self.logger.info(
            f"Hybrid reference service completed: "
            f"coverage={[m.coverage_rate for m in coverage_metrics]}, "
            f"auto_derived_ratio={auto_derived_ratio:.1%}, "
            f"degraded_mode={degraded_mode}"
        )

        return result

    def _check_coverage_for_config(
        self,
        df: pd.DataFrame,
        config: ForeignKeyConfig,
        conn: Connection,
    ) -> Tuple[Optional[CoverageMetrics], Set[Any]]:
        """
        Check FK coverage for a single reference table.

        Args:
            df: Fact data DataFrame
            config: FK configuration
            conn: Database connection

        Returns:
            Tuple of (CoverageMetrics for the table or None, missing FK values set)
        """
        # Get unique FK values from fact data
        if config.source_column not in df.columns:
            self.logger.warning(
                f"Source column '{config.source_column}' not in DataFrame"
            )
            return (None, set())

        fk_values = set(df[config.source_column].dropna().unique())
        total_values = len(fk_values)

        if total_values == 0:
            return CoverageMetrics(
                table=config.target_table,
                total_fk_values=0,
                covered_values=0,
                missing_values=0,
                coverage_rate=1.0,
            ), set()

        # Batch check existence in reference table
        existing_values = self._get_existing_fk_values(fk_values, config, conn)

        covered = len(existing_values)
        missing_values = fk_values - existing_values
        missing = len(missing_values)
        coverage_rate = covered / total_values if total_values > 0 else 1.0

        return CoverageMetrics(
            table=config.target_table,
            total_fk_values=total_values,
            covered_values=covered,
            missing_values=missing,
            coverage_rate=coverage_rate,
        ), missing_values

    def _check_coverage(
        self,
        df: pd.DataFrame,
        fk_configs: List[ForeignKeyConfig],
        conn: Connection,
    ) -> List[CoverageMetrics]:
        """
        Check FK coverage for each reference table.

        Uses batch query to check existence of FK values.

        Args:
            df: Fact data DataFrame
            fk_configs: FK configurations
            conn: Database connection

        Returns:
            List of coverage metrics for each table
        """
        metrics = []

        for config in fk_configs:
            result, _missing_values = self._check_coverage_for_config(df, config, conn)
            if result:
                metrics.append(result)
                self.logger.info(
                    f"Coverage for '{config.target_table}': "
                    f"{result.covered_values}/{result.total_fk_values} ({result.coverage_rate:.1%})"
                )

        return metrics

    def _check_per_table_thresholds(
        self,
        fk_configs: List[ForeignKeyConfig],
        conn: Connection,
    ) -> None:
        """
        Check auto_derived ratio per table and warn if threshold exceeded.

        Implements AC #4: Per-table threshold warnings.

        Args:
            fk_configs: FK configurations
            conn: Database connection
        """
        for config in fk_configs:
            try:
                # Count auto_derived records for this table
                auto_derived_query = f"""
                    SELECT COUNT(*) FROM "{config.target_table}"
                    WHERE "_source" = 'auto_derived'
                """
                result = conn.execute(text(auto_derived_query))
                auto_derived_count = result.scalar() or 0

                # Count authoritative records for this table
                authoritative_query = f"""
                    SELECT COUNT(*) FROM "{config.target_table}"
                    WHERE "_source" = 'authoritative'
                """
                result = conn.execute(text(authoritative_query))
                authoritative_count = result.scalar() or 0

                total = auto_derived_count + authoritative_count
                if total > 0:
                    table_ratio = auto_derived_count / total
                    if table_ratio > self.threshold:
                        self.logger.warning(
                            f"Table '{config.target_table}' auto_derived ratio "
                            f"{table_ratio:.1%} exceeds threshold {self.threshold:.1%}"
                        )

            except Exception as e:
                # Don't fail on per-table threshold check errors
                self.logger.debug(
                    f"Could not check per-table threshold for '{config.target_table}': {e}"
                )

    def _get_existing_fk_values(
        self,
        fk_values: Set,
        config: ForeignKeyConfig,
        conn: Connection,
    ) -> Set:
        """
        Get FK values that exist in reference table.

        Args:
            fk_values: Set of FK values to check
            config: FK configuration
            conn: Database connection

        Returns:
            Set of existing FK values

        Raises:
            Exception: If database query fails (propagated for degradation handling)
        """
        if not fk_values:
            return set()

        # Build query with proper quoting
        if conn.dialect.name == "postgresql":
            existing_query = f"""
                SELECT "{config.target_key}"
                FROM "{config.target_table}"
                WHERE "{config.target_key}" = ANY(:fk_values)
            """
            params = {"fk_values": list(fk_values)}
        else:
            placeholders = (
                ", ".join([f":v{i}" for i, _ in enumerate(fk_values)]) or ":v0"
            )
            existing_query = f"""
                SELECT "{config.target_key}"
                FROM "{config.target_table}"
                WHERE "{config.target_key}" IN ({placeholders})
            """
            params = {f"v{i}": v for i, v in enumerate(fk_values)}

        # Let exceptions propagate for degradation handling in ensure_references
        result = conn.execute(text(existing_query), params)
        existing_values = {row[0] for row in result.fetchall()}
        return existing_values

    def _selective_backfill(
        self,
        df: pd.DataFrame,
        fk_configs: List[ForeignKeyConfig],
        coverage_metrics: List[CoverageMetrics],
        missing_by_table: Dict[str, Set[Any]],
        conn: Connection,
    ) -> Optional[BackfillResult]:
        """
        Backfill only missing FK values.

        Filters fact data to only include rows with missing FK values,
        then delegates to GenericBackfillService.

        Args:
            df: Fact data DataFrame
            fk_configs: FK configurations
            coverage_metrics: Coverage metrics from check
            conn: Database connection

        Returns:
            BackfillResult or None if no backfill needed
        """
        # Check if any backfill needed
        total_missing = sum(m.missing_values for m in coverage_metrics)
        if total_missing == 0:
            self.logger.info("All FK values covered, no backfill needed")
            return None

        # Build mask of rows that contain missing FK values only
        rows_to_backfill = pd.Series(False, index=df.index)

        for config in fk_configs:
            if config.source_column not in df.columns:
                continue
            missing_values = missing_by_table.get(config.target_table)
            if not missing_values:
                continue
            rows_to_backfill |= df[config.source_column].isin(missing_values)

        if not rows_to_backfill.any():
            self.logger.info(
                "Missing values were counted but no rows require backfill after filtering"
            )
            return None

        filtered_df = df.loc[rows_to_backfill].copy()

        # Delegate to GenericBackfillService
        # The service will handle idempotency and only insert missing records
        result = self.backfill.run(
            df=filtered_df,
            configs=fk_configs,
            conn=conn,
            add_tracking_fields=True,
        )

        return result

    def _calculate_auto_derived_ratio(
        self,
        fk_configs: List[ForeignKeyConfig],
        conn: Connection,
    ) -> tuple[int, int, float]:
        """
        Calculate auto_derived ratio across all reference tables.

        Args:
            fk_configs: FK configurations
            conn: Database connection

        Returns:
            Tuple of (auto_derived_count, authoritative_count, ratio)
        """
        total_auto_derived = 0
        total_authoritative = 0

        for config in fk_configs:
            try:
                # Count auto_derived records
                auto_derived_query = f"""
                    SELECT COUNT(*) FROM "{config.target_table}"
                    WHERE "_source" = 'auto_derived'
                """
                result = conn.execute(text(auto_derived_query))
                auto_derived_count = result.scalar() or 0
                total_auto_derived += auto_derived_count

                # Count authoritative records
                authoritative_query = f"""
                    SELECT COUNT(*) FROM "{config.target_table}"
                    WHERE "_source" = 'authoritative'
                """
                result = conn.execute(text(authoritative_query))
                authoritative_count = result.scalar() or 0
                total_authoritative += authoritative_count

            except Exception as e:
                self.logger.warning(
                    f"Error calculating auto_derived ratio for '{config.target_table}': {e}"
                )
                continue

        # Calculate ratio
        total_records = total_auto_derived + total_authoritative
        ratio = total_auto_derived / total_records if total_records > 0 else 0.0

        return total_auto_derived, total_authoritative, ratio
