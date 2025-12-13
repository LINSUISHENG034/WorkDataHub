"""
Dagster ops for reference sync operations.

Story 6.2.4: Pre-load reference data from authoritative sources.
"""

import structlog
from typing import Optional
from dagster import Config, OpExecutionContext, op
from pydantic import Field
from sqlalchemy import create_engine

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.sync_service import ReferenceSyncService
from work_data_hub.domain.reference_backfill.sync_config_loader import load_reference_sync_config
from work_data_hub.io.connectors.adapter_factory import AdapterFactory

logger = structlog.get_logger(__name__)


class ReferenceSyncOpConfig(Config):
    """Configuration for reference_sync_op."""

    plan_only: bool = Field(
        default=False,
        description="If True, only plan sync without executing"
    )
    state: Optional[dict] = Field(
        default=None,
        description="Optional per-table state for incremental sync (keyed by table config name)",
    )


@op
def reference_sync_op(context: OpExecutionContext, config: ReferenceSyncOpConfig) -> dict:
    """
    Sync reference data from authoritative sources.

    Story 6.2.4: Implements pre-load layer of hybrid reference data strategy.

    Args:
        context: Dagster execution context
        config: Operation configuration

    Returns:
        Dictionary with sync results summary
    """
    settings = get_settings()

    logger.info(
        "reference_sync_op.start",
        plan_only=config.plan_only,
    )

    # Load sync configuration
    try:
        sync_config = load_reference_sync_config()
    except Exception as e:
        logger.error(
            "reference_sync_op.config_load_failed",
            error=str(e),
        )
        raise

    if sync_config is None:
        logger.info("reference_sync_op.no_config", message="No reference_sync configuration found")
        return {"status": "skipped", "reason": "no_config"}

    if not sync_config.enabled:
        logger.info("reference_sync_op.disabled", message="Reference sync is disabled")
        return {"status": "skipped", "reason": "disabled"}

    # Initialize adapters (postgres/mysql/config_file) using factory
    adapters = AdapterFactory.create_adapters_for_configs(sync_config.tables)

    # Initialize sync service
    sync_service = ReferenceSyncService(domain="reference_sync")

    # Get database connection
    db_url = settings.get_database_connection_string()
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            # Sync all tables
            results = sync_service.sync_all(
                configs=sync_config.tables,
                adapters=adapters,
                conn=conn,
                plan_only=config.plan_only,
                state=config.state,
                default_batch_size=sync_config.batch_size,
            )

            # Summarize results
            total_synced = sum(r.rows_synced for r in results)
            total_deleted = sum(r.rows_deleted for r in results)
            failed_count = sum(1 for r in results if r.error is not None)

            logger.info(
                "reference_sync_op.complete",
                total_synced=total_synced,
                total_deleted=total_deleted,
                failed_count=failed_count,
                table_count=len(results),
            )

            return {
                "status": "success",
                "total_synced": total_synced,
                "total_deleted": total_deleted,
                "failed_count": failed_count,
                "table_count": len(results),
                "results": [
                    {
                        "table": r.table,
                        "source_type": r.source_type,
                        "rows_synced": r.rows_synced,
                        "rows_deleted": r.rows_deleted,
                        "sync_mode": r.sync_mode,
                        "duration_seconds": r.duration_seconds,
                        "error": r.error,
                    }
                    for r in results
                ],
            }

    except Exception as e:
        logger.error(
            "reference_sync_op.failed",
            error=str(e),
        )
        raise
    finally:
        engine.dispose()
