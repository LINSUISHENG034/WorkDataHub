"""Demonstration Dagster ops kept for backward-compatible exports.

These are sample ops from Story 1.9 that illustrate thin-wrapper patterns.
They remain available via work_data_hub.orchestration.ops.* re-exports.
"""

from pathlib import Path
from typing import Any, Dict, List, cast

import pandas as pd
from dagster import OpExecutionContext, op

from work_data_hub.config.settings import get_settings
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError, load

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2


@op
def read_csv_op(context: OpExecutionContext) -> List[Dict[str, Any]]:
    """Read sample CSV data and return rows as dictionaries."""
    fixture_path = Path("tests/fixtures/sample_data.csv")
    try:
        context.log.info(f"Reading sample CSV data from {fixture_path}")
        df = pd.read_csv(fixture_path)
        rows = df.to_dict(orient="records")
        context.log.info(
            f"Sample CSV read completed - rows: {len(rows)}, columns: {len(df.columns)}"
        )
        return cast(List[Dict[str, any]], rows)
    except Exception as e:  # pragma: no cover - demo-only path
        context.log.error(f"Sample CSV read failed: {e}")
        raise


@op
def validate_op(
    context: OpExecutionContext, rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Demo validation op showing Pipeline pattern (pass-through)."""
    try:
        context.log.info(f"Starting sample validation pipeline - rows: {len(rows)}")
        df = pd.DataFrame(rows)
        validated_rows = df.to_dict(orient="records")
        context.log.info(
            f"Sample validation completed - validated: {len(validated_rows)} rows"
        )
        return validated_rows
    except Exception as e:  # pragma: no cover - demo-only path
        context.log.error(f"Sample validation failed: {e}")
        raise


@op
def load_to_db_op(
    context: OpExecutionContext, rows: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Demo load op using Story 1.8 WarehouseLoader."""
    global psycopg2
    try:
        context.log.info(f"Starting sample database load - rows: {len(rows)}")

        # Lazy import psycopg2
        if psycopg2 is _PSYCOPG2_NOT_LOADED:
            try:
                import psycopg2 as _psycopg2

                psycopg2 = _psycopg2
            except ImportError as exc:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                ) from exc

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

        conn = None
        try:
            conn = psycopg2.connect(dsn)
            result = load(
                table="sample_data",
                rows=rows,
                mode="append",
                pk=[],
                conn=conn,
            )
            context.log.info(
                "Sample database load completed - inserted: %s, batches: %s",
                result.get("inserted", 0),
                result.get("batches", 0),
            )
            return result
        finally:
            if conn is not None:
                conn.close()

    except Exception as e:  # pragma: no cover - demo-only path
        context.log.error(f"Sample database load failed: {e}")
        raise
