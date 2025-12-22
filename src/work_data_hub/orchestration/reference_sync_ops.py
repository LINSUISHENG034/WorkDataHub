"""
Dagster ops for reference sync operations.

Story 6.2.4: Pre-load reference data from authoritative sources.
Story 6.2-p4: Incremental state persistence for reference sync.
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from dagster import Config, OpExecutionContext, op
from pydantic import Field
from sqlalchemy import create_engine

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.sync_config_loader import (
    load_reference_sync_config,
)
from work_data_hub.domain.reference_backfill.sync_service import ReferenceSyncService
from work_data_hub.io.connectors.adapter_factory import AdapterFactory
from work_data_hub.io.repositories.sync_state_repository import SyncStateRepository

logger = structlog.get_logger(__name__)

JOB_NAME = "reference_sync"


class ReferenceSyncOpConfig(Config):
    """Configuration for reference_sync_op."""

    plan_only: bool = Field(
        default=False, description="If True, only plan sync without executing"
    )
    state: Optional[dict] = Field(
        default=None,
        description="Optional per-table state for incremental sync (keyed by table config name). "
        "If None, state will be loaded from the database automatically.",
    )
    persist_state: bool = Field(
        default=True,
        description="If True, persist sync state to database after successful sync",
    )
    force_full_sync: bool = Field(
        default=False,
        description="If True, ignore persisted state and perform full sync",
    )


@op
def reference_sync_op(
    context: OpExecutionContext, config: ReferenceSyncOpConfig
) -> dict:
    """
    Sync reference data from authoritative sources.

    Story 6.2.4: Implements pre-load layer of hybrid reference data strategy.
    Story 6.2-p4: Adds incremental state persistence for efficient syncs.

    Args:
        context: Dagster execution context
        config: Operation configuration

    Returns:
        Dictionary with sync results summary
    """
    settings = get_settings()
    sync_start_time = datetime.now(timezone.utc)

    logger.info(
        "reference_sync_op.start",
        plan_only=config.plan_only,
        persist_state=config.persist_state,
        force_full_sync=config.force_full_sync,
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
        logger.info(
            "reference_sync_op.no_config",
            message="No reference_sync configuration found",
        )
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
    import psycopg2

    engine = create_engine(db_url, module=psycopg2)

    try:
        with engine.connect() as conn:
            # Initialize state repository for incremental sync
            state_repo = SyncStateRepository(conn)

            # Determine sync state to use
            sync_state = _resolve_sync_state(
                config=config,
                state_repo=state_repo,
                table_configs=sync_config.tables,
            )

            logger.info(
                "reference_sync_op.state_resolved",
                tables_with_state=len(sync_state) if sync_state else 0,
                force_full_sync=config.force_full_sync,
            )

            # Sync all tables
            results = sync_service.sync_all(
                configs=sync_config.tables,
                adapters=adapters,
                conn=conn,
                plan_only=config.plan_only,
                state=sync_state,
                default_batch_size=sync_config.batch_size,
            )

            # Persist state for successful syncs (Story 6.2-p4)
            states_persisted = 0
            if config.persist_state and not config.plan_only:
                states_persisted = _persist_sync_states(
                    results=results,
                    state_repo=state_repo,
                    sync_time=sync_start_time,
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
                states_persisted=states_persisted,
            )

            return {
                "status": "success",
                "total_synced": total_synced,
                "total_deleted": total_deleted,
                "failed_count": failed_count,
                "table_count": len(results),
                "states_persisted": states_persisted,
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


def _resolve_sync_state(
    config: ReferenceSyncOpConfig,
    state_repo: SyncStateRepository,
    table_configs: list,
) -> Optional[dict]:
    """
    Resolve the sync state to use for incremental sync.

    Priority:
    1. If force_full_sync is True, return None (full sync)
    2. If explicit state is provided in config, use it
    3. Otherwise, load state from database

    Args:
        config: Op configuration
        state_repo: State repository instance
        table_configs: List of table configurations

    Returns:
        Dictionary mapping table names to their state, or None for full sync
    """
    # Force full sync - ignore all state
    if config.force_full_sync:
        logger.info(
            "reference_sync_op.force_full_sync", message="Ignoring persisted state"
        )
        return None

    # Explicit state provided - use it directly
    if config.state is not None:
        logger.info(
            "reference_sync_op.using_explicit_state",
            tables=list(config.state.keys()),
        )
        return config.state

    # Load state from database
    persisted_states = state_repo.get_all_states(JOB_NAME)

    if not persisted_states:
        logger.info(
            "reference_sync_op.no_persisted_state",
            message="No persisted state found, will perform full sync",
        )
        return None

    # Convert to format expected by sync_service
    # Map table config names to their state
    sync_state = {}
    for table_config in table_configs:
        table_name = table_config.name
        if table_name in persisted_states:
            state_data = persisted_states[table_name]
            sync_state[table_name] = {
                "last_synced_at": state_data["last_synced_at"],
            }

    logger.info(
        "reference_sync_op.loaded_persisted_state",
        tables_with_state=list(sync_state.keys()),
    )

    return sync_state if sync_state else None


def _persist_sync_states(
    results: list,
    state_repo: SyncStateRepository,
    sync_time: datetime,
) -> int:
    """
    Persist sync state for successfully synced tables.

    Args:
        results: List of SyncResult objects
        state_repo: State repository instance
        sync_time: Timestamp of the sync operation

    Returns:
        Number of states successfully persisted
    """
    persisted_count = 0

    for result in results:
        # Only persist state for successful syncs
        if result.error is not None:
            logger.debug(
                "reference_sync_op.skip_state_persist",
                table=result.table,
                reason="sync_failed",
            )
            continue

        # Persist the state
        success = state_repo.update_state(
            job_name=JOB_NAME,
            table_name=result.table,
            last_synced_at=sync_time,
        )

        if success:
            persisted_count += 1
            logger.debug(
                "reference_sync_op.state_persisted",
                table=result.table,
                last_synced_at=sync_time.isoformat(),
            )
        else:
            logger.warning(
                "reference_sync_op.state_persist_failed",
                table=result.table,
            )

    return persisted_count
