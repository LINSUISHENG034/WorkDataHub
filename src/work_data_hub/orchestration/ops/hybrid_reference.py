"""Hybrid reference service ops (extracted to keep module size under limits)."""

from typing import Any, Dict

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill import (
    GenericBackfillService,
    HybridReferenceService,
    load_foreign_keys_config,
    ReferenceSyncService,
)
from work_data_hub.domain.reference_backfill.sync_config_loader import (
    load_reference_sync_config,
)
from work_data_hub.io.connectors.config_file_connector import ConfigFileConnector
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError


class HybridReferenceConfig(Config):
    """Configuration for hybrid reference service operation."""

    domain: str
    auto_derived_threshold: float = 0.10
    run_preload: bool = False

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Domain must be a non-empty string")
        return v.strip()

    @field_validator("auto_derived_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("auto_derived_threshold must be between 0 and 1")
        return v


@op
def hybrid_reference_op(
    context: OpExecutionContext,
    config: HybridReferenceConfig,
    df: Any,  # pandas DataFrame
) -> Dict[str, Any]:
    """
    Ensure FK references exist using hybrid strategy (Story 6.2.5).
    """
    try:
        context.log.info(
            f"Starting hybrid reference service for domain '{config.domain}' "
            f"with threshold {config.auto_derived_threshold:.1%}"
        )

        fk_configs = load_foreign_keys_config(domain=config.domain)
        if not fk_configs:
            context.log.warning(
                "No FK configurations found for domain '%s', skipping",
                config.domain,
            )
            return {
                "domain": config.domain,
                "pre_load_available": False,
                "coverage_metrics": [],
                "backfill_result": None,
                "total_auto_derived": 0,
                "total_authoritative": 0,
                "auto_derived_ratio": 0.0,
                "degraded_mode": False,
                "degradation_reason": None,
            }

        # Get database connection string
        settings = get_settings()
        dsn = None
        if hasattr(settings, "get_database_connection_string"):
            try:
                dsn = settings.get_database_connection_string()
            except Exception:
                dsn = None
        if not isinstance(dsn, str) and hasattr(settings, "database"):
            try:
                dsn = settings.database.get_connection_string()
            except Exception:
                pass
        if not isinstance(dsn, str) or not dsn:
            raise DataWarehouseLoaderError(
                "Database connection failed: invalid DSN resolved from settings"
            )

        # Optional pre-load
        sync_service = None
        sync_configs = None
        sync_adapters = None
        if config.run_preload:
            try:
                sync_config = load_reference_sync_config()
                if sync_config and sync_config.enabled and sync_config.tables:
                    sync_service = ReferenceSyncService(domain=config.domain)
                    sync_configs = sync_config.tables
                    sync_adapters = {"config_file": ConfigFileConnector()}
                    context.log.info(
                        "Pre-load enabled with %s table configs", len(sync_configs)
                    )
            except Exception as preload_error:  # pragma: no cover - defensive
                context.log.warning(
                    "Pre-load setup failed; continuing without pre-load: %s",
                    preload_error,
                )

        from sqlalchemy import create_engine

        engine = None
        conn = None
        try:
            engine = create_engine(dsn)
            conn = engine.connect()

            backfill_service = GenericBackfillService(domain=config.domain)
            hybrid_service = HybridReferenceService(
                backfill_service=backfill_service,
                sync_service=sync_service,
                auto_derived_threshold=config.auto_derived_threshold,
                sync_configs=sync_configs,
                sync_adapters=sync_adapters,
            )

            result = hybrid_service.ensure_references(
                domain=config.domain,
                df=df,
                fk_configs=fk_configs,
                conn=conn,
            )

            if result.auto_derived_ratio > config.auto_derived_threshold:
                context.log.warning(
                    "Auto-derived ratio %.1f%% exceeds threshold %.1f%%; consider running reference_sync job.",
                    result.auto_derived_ratio * 100,
                    config.auto_derived_threshold * 100,
                )

            return {
                "domain": result.domain,
                "pre_load_available": result.pre_load_available,
                "coverage_metrics": [
                    {
                        "table": m.table,
                        "total_fk_values": m.total_fk_values,
                        "covered_values": m.covered_values,
                        "missing_values": m.missing_values,
                        "coverage_rate": m.coverage_rate,
                    }
                    for m in result.coverage_metrics
                ],
                "backfill_result": (
                    {
                        "processing_order": result.backfill_result.processing_order,
                        "tables_processed": result.backfill_result.tables_processed,
                        "total_inserted": result.backfill_result.total_inserted,
                        "total_skipped": result.backfill_result.total_skipped,
                        "processing_time_seconds": result.backfill_result.processing_time_seconds,
                        "rows_per_second": result.backfill_result.rows_per_second,
                    }
                    if result.backfill_result
                    else None
                ),
                "total_auto_derived": result.total_auto_derived,
                "total_authoritative": result.total_authoritative,
                "auto_derived_ratio": result.auto_derived_ratio,
                "degraded_mode": result.degraded_mode,
                "degradation_reason": result.degradation_reason,
            }
        finally:
            if conn is not None:
                conn.close()
            if engine is not None:
                engine.dispose()

    except Exception as e:
        context.log.error(f"Hybrid reference operation failed: {e}")
        raise

