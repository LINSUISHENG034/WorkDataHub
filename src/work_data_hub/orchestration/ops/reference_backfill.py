"""Reference backfill ops (Story 7.1).

This module contains ops for legacy reference data backfill:
- BackfillRefsConfig: Configuration for legacy backfill
- derive_plan_refs_op: Derive plan reference candidates
- derive_portfolio_refs_op: Derive portfolio reference candidates
- backfill_refs_op: Execute legacy reference backfill

Note: GenericBackfillConfig, generic_backfill_refs_op, and gate_after_backfill
are now in generic_backfill.py to keep this module under 500 lines.
"""

import logging
from typing import Any, Dict, List

import yaml
from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
)
from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    fill_null_only,
    insert_missing,
)

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2

logger = logging.getLogger(__name__)


class BackfillRefsConfig(Config):
    """Configuration for reference backfill operation."""

    # Legacy configuration for backward compatibility
    targets: List[str] = []  # Empty list means no backfill
    mode: str = "insert_missing"  # or "fill_null_only"
    plan_only: bool = True
    chunk_size: int = 1000
    domain: str = "annuity_performance"  # Domain to backfill references for

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: List[str]) -> List[str]:
        """Validate backfill targets are supported."""
        if not v:  # Allow empty list to disable backfill
            return v
        valid = ["plans", "portfolios", "all", "generic"]
        for target in v:
            if target not in valid:
                raise ValueError(f"Invalid target: {target}. Valid: {valid}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate backfill mode is supported."""
        valid_modes = ["insert_missing", "fill_null_only"]
        if v not in valid_modes:
            raise ValueError(f"Mode '{v}' not supported. Valid: {valid_modes}")
        return v


@op
def derive_plan_refs_op(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive plan reference candidates from processed fact data.

    Args:
        context: Dagster execution context
        processed_rows: Processed annuity performance fact data

    Returns:
        List of plan candidate dictionaries ready for backfill
    """
    try:
        candidates = derive_plan_candidates(processed_rows)

        context.log.info(
            "Plan candidate derivation completed",
            extra={
                "input_rows": len(processed_rows),
                "unique_plans": len(candidates),
                "domain": "annuity_performance",
            },
        )

        return candidates

    except Exception as e:
        context.log.error(f"Plan candidate derivation failed: {e}")
        raise


@op
def derive_portfolio_refs_op(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive portfolio reference candidates from processed fact data.

    Args:
        context: Dagster execution context
        processed_rows: Processed annuity performance fact data

    Returns:
        List of portfolio candidate dictionaries ready for backfill
    """
    try:
        candidates = derive_portfolio_candidates(processed_rows)

        context.log.info(
            "Portfolio candidate derivation completed",
            extra={
                "input_rows": len(processed_rows),
                "unique_portfolios": len(candidates),
                "domain": "annuity_performance",
            },
        )

        return candidates

    except Exception as e:
        context.log.error(f"Portfolio candidate derivation failed: {e}")
        raise


@op
def backfill_refs_op(
    context: OpExecutionContext,
    config: BackfillRefsConfig,
    plan_candidates: List[Dict[str, Any]],
    portfolio_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute reference backfill operations for plans and/or portfolios.

    Args:
        context: Dagster execution context
        config: Backfill configuration
        plan_candidates: Plan candidate dictionaries
        portfolio_candidates: Portfolio candidate dictionaries

    Returns:
        Dictionary with backfill execution metadata
    """
    # Use module-level psycopg2 reference
    global psycopg2

    conn = None
    try:
        # Mirror load_op connection handling pattern
        if not config.plan_only:
            if psycopg2 is None:
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

            context.log.info("Connecting to database for reference backfill execution")

            try:
                conn = psycopg2.connect(dsn)
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__* environment variables."
                ) from e

        result: Dict[str, Any] = {"operations": [], "plan_only": config.plan_only}

        # Early return if no backfill targets specified
        if not config.targets:
            context.log.info("Reference backfill skipped - no targets specified")
            return result

        # Read refs configuration from data_sources.yml
        settings = get_settings()
        refs_config = {}
        try:
            with open(settings.data_sources_config, "r", encoding="utf-8") as f:
                data_sources: Dict[str, Any] = yaml.safe_load(f) or {}

            # Extract refs for current domain (annuity_performance)
            domain = "annuity_performance"  # TODO: pass from discover_files_op
            refs_config = (
                data_sources.get("domains", {}).get(domain, {}).get("refs", {})
            )
        except Exception as e:
            context.log.warning("Could not load refs config: %s, using defaults", e)

        # Get plans configuration with fallbacks
        plans_config = refs_config.get("plans", {})
        plans_schema = plans_config.get("schema")  # None if not specified
        plans_table = plans_config.get("table", "年金计划")  # fallback to hardcoded
        plans_key = plans_config.get("key", ["年金计划号"])  # fallback
        plans_updatable = plans_config.get(
            "updatable", ["计划全称", "计划类型", "客户名称", "company_id"]
        )

        # Get portfolios configuration with fallbacks
        portfolios_config = refs_config.get("portfolios", {})
        portfolios_schema = portfolios_config.get("schema")  # None if not specified
        portfolios_table = portfolios_config.get(
            "table", "组合计划"
        )  # fallback to hardcoded
        portfolios_key = portfolios_config.get("key", ["组合代码"])  # fallback
        portfolios_updatable = portfolios_config.get(
            "updatable", ["组合名称", "组合类型", "运作开始日"]
        )

        # Execute backfill for plans
        if ("plans" in config.targets or "all" in config.targets) and plan_candidates:
            try:
                # Begin a savepoint for plans operation
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SAVEPOINT plans_backfill")

                if config.mode == "insert_missing":
                    plan_result = insert_missing(
                        table=plans_table,
                        key_cols=plans_key,
                        rows=plan_candidates,
                        conn=conn,
                        chunk_size=config.chunk_size,
                        schema=plans_schema,
                    )
                elif config.mode == "fill_null_only":
                    plan_result = fill_null_only(
                        table=plans_table,
                        key_cols=plans_key,
                        rows=plan_candidates,
                        updatable_cols=plans_updatable,
                        conn=conn,
                        schema=plans_schema,
                    )
                else:
                    raise DataWarehouseLoaderError(
                        f"Unsupported backfill mode: {config.mode}"
                    )

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT plans_backfill")

                result["operations"].append({"table": plans_table, **plan_result})
                context.log.info(
                    f"Plans backfill completed successfully: {plans_table}"
                )

            except Exception as plans_error:
                context.log.warning(f"Plans backfill failed: {plans_error}")
                # Rollback to savepoint on failure
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("ROLLBACK TO SAVEPOINT plans_backfill")
                            cursor.execute("RELEASE SAVEPOINT plans_backfill")
                    except Exception:
                        pass

                # Add error result but continue with portfolios
                result["operations"].append(
                    {
                        "table": plans_table,
                        "error": str(plans_error),
                        "inserted": 0,
                        "batches": 0,
                    }
                )

        # Execute backfill for portfolios
        if (
            "portfolios" in config.targets or "all" in config.targets
        ) and portfolio_candidates:
            try:
                # Begin a savepoint for portfolios operation
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SAVEPOINT portfolios_backfill")

                if config.mode == "insert_missing":
                    portfolio_result = insert_missing(
                        table=portfolios_table,
                        key_cols=portfolios_key,
                        rows=portfolio_candidates,
                        conn=conn,
                        chunk_size=config.chunk_size,
                        schema=portfolios_schema,
                    )
                elif config.mode == "fill_null_only":
                    portfolio_result = fill_null_only(
                        table=portfolios_table,
                        key_cols=portfolios_key,
                        rows=portfolio_candidates,
                        updatable_cols=portfolios_updatable,
                        conn=conn,
                        schema=portfolios_schema,
                    )
                else:
                    raise DataWarehouseLoaderError(
                        f"Unsupported backfill mode: {config.mode}"
                    )

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT portfolios_backfill")

                result["operations"].append(
                    {"table": portfolios_table, **portfolio_result}
                )
                context.log.info(
                    f"Portfolios backfill completed successfully: {portfolios_table}"
                )

            except Exception as portfolios_error:
                context.log.warning(f"Portfolios backfill failed: {portfolios_error}")
                # Rollback to savepoint on failure
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("ROLLBACK TO SAVEPOINT portfolios_backfill")
                            cursor.execute("RELEASE SAVEPOINT portfolios_backfill")
                    except Exception:
                        pass

                # Add error result
                result["operations"].append(
                    {
                        "table": portfolios_table,
                        "error": str(portfolios_error),
                        "inserted": 0,
                        "batches": 0,
                    }
                )

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Reference backfill completed ({mode_text})",
            extra={
                "targets": config.targets,
                "mode": config.mode,
                "operations": len(result["operations"]),
                "plan_candidates": len(plan_candidates),
                "portfolio_candidates": len(portfolio_candidates),
            },
        )

        # Final commit for successful operations
        if conn and not config.plan_only:
            try:
                conn.commit()
                context.log.info("Reference backfill transaction committed")
            except Exception as final_commit_error:
                context.log.warning(f"Final commit warning: {final_commit_error}")

        return result

    except Exception as e:
        context.log.error(f"Reference backfill failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()
