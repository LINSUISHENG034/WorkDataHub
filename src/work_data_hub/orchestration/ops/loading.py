"""Database loading ops (Story 7.1).

This module contains ops for database loading operations:
- LoadConfig: Configuration for data loading
- load_op: Load processed data to database
"""

import logging
from typing import Any, Dict, List

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator, model_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    load,
)

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2

logger = logging.getLogger(__name__)


class LoadConfig(Config):
    """Configuration for data loading operation."""

    table: str = "sandbox_trustee_performance"
    mode: str = "delete_insert"
    pk: List[str] = ["report_date", "plan_code", "company_code"]
    plan_only: bool = True
    skip: bool = False  # NEW: skip flag for early return

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate load mode is supported."""
        valid_modes = ["delete_insert", "append"]
        if v not in valid_modes:
            raise ValueError(f"Mode '{v}' not supported. Valid: {valid_modes}")
        return v

    @model_validator(mode="after")
    def validate_delete_insert_requirements(self) -> "LoadConfig":
        """Ensure delete_insert mode has primary key defined."""
        if self.mode == "delete_insert" and not self.pk:
            raise ValueError("delete_insert mode requires primary key columns")
        return self


@op
def load_op(
    context: OpExecutionContext,
    config: LoadConfig,
    processed_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Load processed data to database or return execution plan.

    Args:
        context: Dagster execution context
        config: Load configuration
        processed_rows: Processed data rows to load

    Returns:
        Dictionary with execution metadata or SQL plans
    """
    # Use module-level psycopg2 reference
    global psycopg2

    # NEW: Check skip flag and early return
    if config.skip:
        context.log.info("Fact loading skipped due to --skip-facts flag")
        return {
            "table": config.table,
            "mode": config.mode,
            "skipped": True,
            "inserted": 0,
            "deleted": 0,
            "batches": 0,
        }

    conn = None
    try:
        if not config.plan_only:
            # Lazy import psycopg2 into module-global for test compatibility
            if psycopg2 is None:
                # Explicitly treated as unavailable (tests may patch to None)
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                )
            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError(
                        "psycopg2 not available for database operations"
                    )
                psycopg2 = _psycopg2

            settings = get_settings()

            # Primary DSN retrieval with fallback for test compatibility
            dsn = None
            # Primary: consolidated accessor
            if hasattr(settings, "get_database_connection_string"):
                try:
                    dsn = settings.get_database_connection_string()
                except Exception:
                    dsn = None
            # Fallback: compatibility wrapper
            if not isinstance(dsn, str) and hasattr(settings, "database"):
                try:
                    dsn = settings.database.get_connection_string()
                except Exception:
                    pass
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            # Story 6.2-P16 AC-2: Validate required settings before attempting connect
            missing = []
            if not settings.database_host:
                missing.append("WDH_DATABASE__HOST")
            if not settings.database_port:
                missing.append("WDH_DATABASE__PORT")
            if not settings.database_db:
                missing.append("WDH_DATABASE__DB")
            if not settings.database_user:
                missing.append("WDH_DATABASE__USER")
            if not settings.database_password:
                missing.append("WDH_DATABASE__PASSWORD")
            if missing:
                context.log.error(
                    "db_connection.missing_settings",
                    extra={
                        "missing": missing,
                        "purpose": "load_op",
                        "table": config.table,
                    },
                )
                raise DataWarehouseLoaderError(
                    "Database connection settings missing: "
                    f"{', '.join(missing)}. "
                    "Set them in .wdh_env and try again."
                )

            # Story 6.2-P16 AC-2: Log DSN components for debugging (never log password)
            context.log.info(
                "db_connection.attempting",
                extra={
                    "host": settings.database_host,
                    "port": settings.database_port,
                    "database": settings.database_db,
                    "user": settings.database_user,
                    "table": config.table,
                    "purpose": "load_op",
                },
            )

            # CRITICAL: Only catch psycopg2.connect failures
            try:
                conn = psycopg2.connect(dsn)  # Bare connection, no context manager
            except Exception as e:
                # Story 6.2-P16 AC-2: Improved error message with hints
                context.log.error(
                    "db_connection.failed",
                    extra={
                        "host": settings.database_host,
                        "port": settings.database_port,
                        "database": settings.database_db,
                        "table": config.table,
                        "error": str(e),
                    },
                )
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__HOST, WDH_DATABASE__PORT, WDH_DATABASE__DB, "
                    "WDH_DATABASE__USER, WDH_DATABASE__PASSWORD in .wdh_env"
                ) from e

            # Call loader - it handles transactions with 'with conn:'
            result = load(
                table=config.table,
                rows=processed_rows,
                mode=config.mode,
                pk=config.pk,
                conn=conn,
            )
        else:
            # Plan-only: no connection created
            result = load(
                table=config.table,
                rows=processed_rows,
                mode=config.mode,
                pk=config.pk,
                conn=None,
            )

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Load operation completed (%s) - table: %s, mode: %s, "
            "deleted: %s, inserted: %s, batches: %s",
            mode_text,
            config.table,
            config.mode,
            result.get("deleted", 0),
            result.get("inserted", 0),
            result.get("batches", 0),
        )

        return result

    except Exception as e:
        context.log.error(f"Load operation failed: {e}")
        raise
    finally:
        # CRITICAL: Clean up bare connection in finally
        if conn is not None:
            conn.close()
