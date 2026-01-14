"""Generic backfill ops (extracted from reference_backfill.py to meet <500 line limit).

This module contains ops for generic reference backfill:
- GenericBackfillConfig: Configuration for generic backfill
- generic_backfill_refs_op: Execute generic reference backfill
- gate_after_backfill: Dependency gate for backfill completion
"""

import logging
from typing import Any, Dict, List

from dagster import Config, OpExecutionContext, op

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill import (
    GenericBackfillService,
    load_foreign_keys_config,
)
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

logger = logging.getLogger(__name__)


class GenericBackfillConfig(Config):
    """Configuration for generic backfill operation."""

    domain: str = "annuity_performance"
    add_tracking_fields: bool = True
    plan_only: bool = True


@op
def generic_backfill_refs_op(
    context: OpExecutionContext,
    config: GenericBackfillConfig,
    processed_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute generic reference backfill using configuration-driven approach.

    This op replaces the legacy backfill_refs_op with the new
    GenericBackfillService that reads foreign_keys configuration from
    data_sources.yml.

    Args:
        context: Dagster execution context
        config: Generic backfill configuration
        processed_rows: Processed fact data to derive references from

    Returns:
        Dictionary with backfill execution metadata
    """
    # Convert processed rows to DataFrame for the service
    import pandas as pd

    df = pd.DataFrame(processed_rows)

    if df.empty:
        context.log.info("No processed rows provided for backfill")
        return {
            "processing_order": [],
            "tables_processed": [],
            "total_inserted": 0,
            "plan_only": config.plan_only,
        }

    # Phase 4 Enhancement: Check requires_backfill from domain config
    # This is a safeguard for domains that explicitly disable backfill
    try:
        from work_data_hub.infrastructure.settings.data_source_schema import (
            get_domain_config_v2,
        )
        domain_cfg = get_domain_config_v2(
            config.domain, config_path="config/data_sources.yml"
        )
        if not getattr(domain_cfg, "requires_backfill", True):
            context.log.info(
                f"Domain '{config.domain}' has requires_backfill=false, skipping"
            )
            return {
                "processing_order": [],
                "tables_processed": [],
                "total_inserted": 0,
                "plan_only": config.plan_only,
                "skipped_reason": "requires_backfill=false",
            }
    except Exception as e:
        # If config loading fails, continue with FK config check
        context.log.debug(f"Could not check requires_backfill: {e}")

    settings = get_settings()

    conn = None
    try:
        # Load foreign key configurations (Story 6.2-P14: uses default path config/foreign_keys.yml)
        fk_configs = load_foreign_keys_config(domain=config.domain)

        if not fk_configs:
            context.log.info(
                f"No foreign_keys configuration found for domain '{config.domain}'"
            )
            return {
                "processing_order": [],
                "tables_processed": [],
                "total_inserted": 0,
                "plan_only": config.plan_only,
            }

        # Create database connection if not in plan_only mode
        if not config.plan_only:
            # Use SQLAlchemy connection for GenericBackfillService
            import psycopg2
            from sqlalchemy import create_engine

            dsn = settings.get_database_connection_string()
            if not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info(
                f"Connecting to database for generic backfill (domain: {config.domain})"
            )

            # Create SQLAlchemy engine with explicit psycopg2 module
            engine = create_engine(dsn, module=psycopg2)
            conn = engine.connect()

        # Create and run the generic backfill service
        service = GenericBackfillService(config.domain)
        result = service.run(
            df=df,
            configs=fk_configs,
            conn=conn,
            add_tracking_fields=config.add_tracking_fields,
            plan_only=config.plan_only,
        )

        # Convert BackfillResult to dictionary for JSON serialization
        result_dict = {
            "processing_order": result.processing_order,
            "tables_processed": result.tables_processed,
            "total_inserted": result.total_inserted,
            "total_skipped": result.total_skipped,
            "processing_time_seconds": result.processing_time_seconds,
            "rows_per_second": result.rows_per_second,
            "plan_only": config.plan_only,
            "domain": config.domain,
            "tracking_fields_enabled": config.add_tracking_fields,
        }

        # Enhanced logging
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Generic backfill completed ({mode_text}) - domain: {config.domain}, "
            f"tables: {len(result.tables_processed)}, inserted: {result.total_inserted}, "
            f"skipped: {result.total_skipped}, time: {result.processing_time_seconds:.2f}s"
        )

        # Log per-table results
        for table_info in result.tables_processed:
            context.log.info(
                f"Table '{table_info['table']}': {table_info['inserted']} inserted, "
                f"{table_info.get('skipped', 0)} skipped"
            )

        # Performance logging
        if result.rows_per_second:
            context.log.info(
                f"Backfill performance: {result.rows_per_second:.0f} rows/sec"
            )

        return result_dict

    except Exception as e:
        context.log.error(f"Generic backfill operation failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


@op
def gate_after_backfill(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
    backfill_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Dependency gate to ensure backfill completes before fact loading.

    This op simply forwards processed_rows, but establishes an explicit
    dependency on backfill_refs_op so that load_op cannot start before
    reference backfill has finished (important when FK constraints exist).
    """
    ops = (
        backfill_summary.get("operations", [])
        if isinstance(backfill_summary, dict)
        else []
    )
    tables = backfill_summary.get("tables_processed", [])
    context.log.info(
        f"Backfill completed; gating fact load. operations={len(ops)}, tables={len(tables)}"
    )
    return processed_rows
