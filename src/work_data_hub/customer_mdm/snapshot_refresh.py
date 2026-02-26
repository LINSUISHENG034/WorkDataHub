"""Monthly snapshot refresh service.

Story 7.6-7: Monthly Snapshot Refresh (Post-ETL Hook)
Story 7.6-16: Fact Table Refactoring (双表粒度分离)
Story 7.6-18: Config-Driven Status Evaluation Framework

Populates two fact tables from customer."客户年金计划" (客户年金计划):
1. "客户业务月度快照" - ProductLine granularity
2. "客户计划月度快照" - Plan granularity

ProductLine Table ("客户业务月度快照"):
  Granularity: Customer + Product Line
  Status derivation:
    - is_strategic: Aggregated from contract attributes (BOOL_OR)
    - is_existing: Aggregated from contract attributes (BOOL_OR)
    - is_winning_this_year: Derived from customer.中标客户明细 (config-driven)
    - is_churned_this_year: Derived from customer.流失客户明细 (config-driven)
    - is_new: is_winning AND NOT is_existing (config-driven)
    - aum_balance: Aggregated from business.规模明细
    - plan_count: COUNT DISTINCT plan_code

Plan Table ("客户计划月度快照"):
  Granularity: Customer + Plan + Product Line
  Status derivation:
    - is_churned_this_year: Plan-level churn from customer.流失客户明细 (config-driven)
    - contract_status: Current contract status
    - aum_balance: Plan-level AUM from business.规模明细
"""

from __future__ import annotations

import calendar
import os
from datetime import date
from typing import Optional

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

from work_data_hub.customer_mdm.status_evaluator import StatusEvaluator

logger = get_logger(__name__)

# Singleton evaluator instance (lazy loaded)
_evaluator: Optional[StatusEvaluator] = None


def get_status_evaluator() -> StatusEvaluator:
    """Get or create StatusEvaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = StatusEvaluator()
        logger.debug("status_evaluator.singleton_created")
    return _evaluator


def reset_status_evaluator() -> None:
    """Reset StatusEvaluator singleton for testing purposes.

    This allows tests to start with a fresh evaluator instance,
    preventing test pollution from cached state.
    """
    global _evaluator
    _evaluator = None
    logger.debug("status_evaluator.singleton_reset")


# Period format constants
PERIOD_LENGTH = 6  # YYYYMM format
MIN_MONTH = 1
MAX_MONTH = 12
LOG_SQL_TRUNCATE_LENGTH = 100  # Max chars for SQL in debug logs


def period_to_snapshot_month(period: str) -> str:
    """Convert YYYYMM period string to end-of-month date string.

    Args:
        period: Period in YYYYMM format (e.g., "202601")

    Returns:
        End-of-month date string (e.g., "2026-01-31")

    Raises:
        ValueError: If period format is invalid
    """
    if not period or len(period) != PERIOD_LENGTH:
        raise ValueError(f"Invalid period format: {period}. Expected YYYYMM.")

    year = int(period[:4])
    month = int(period[4:6])

    if month < MIN_MONTH or month > MAX_MONTH:
        raise ValueError(f"Invalid month in period: {period}")

    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-{last_day:02d}"


def get_current_period() -> str:
    """Get current period in YYYYMM format.

    Returns:
        Current month as YYYYMM string
    """
    today = date.today()
    return f"{today.year}{today.month:02d}"


def _refresh_product_line_snapshot(
    cur: psycopg.Cursor,
    snapshot_month: str,
    snapshot_year: int,
) -> int:
    """Refresh ProductLine-level snapshot table.

    Story 7.6-18: Uses StatusEvaluator for config-driven status derivation.

    Args:
        cur: Database cursor
        snapshot_month: End-of-month date string
        snapshot_year: Year for status derivation

    Returns:
        Number of records upserted
    """
    evaluator = get_status_evaluator()
    params = {"snapshot_year": snapshot_year}

    # Generate config-driven SQL fragments
    is_winning_sql = evaluator.generate_sql_fragment(
        "is_winning_this_year", "c", params
    )
    is_churned_sql = evaluator.generate_sql_fragment(
        "is_churned_this_year", "c", params
    )
    is_new_sql = evaluator.generate_sql_fragment("is_new", "c", params)

    logger.debug(
        "status_evaluator.sql_generated",
        is_winning_sql=is_winning_sql[:LOG_SQL_TRUNCATE_LENGTH] + "..."
        if len(is_winning_sql) > LOG_SQL_TRUNCATE_LENGTH
        else is_winning_sql,
        is_churned_sql=is_churned_sql[:LOG_SQL_TRUNCATE_LENGTH] + "..."
        if len(is_churned_sql) > LOG_SQL_TRUNCATE_LENGTH
        else is_churned_sql,
    )

    refresh_sql = f"""
        INSERT INTO customer."客户业务月度快照" (
            snapshot_month,
            company_id,
            product_line_code,
            product_line_name,
            customer_name,
            is_strategic,
            is_existing,
            is_new,
            is_winning_this_year,
            is_churned_this_year,
            aum_balance,
            plan_count
        )
        SELECT
            %(snapshot_month)s::date as snapshot_month,
            c.company_id,
            c.product_line_code,
            MAX(c.product_line_name) as product_line_name,
            MAX(c.customer_name) as customer_name,

            -- Aggregate attributes from contracts
            BOOL_OR(c.is_strategic) as is_strategic,
            BOOL_OR(c.is_existing) as is_existing,

            -- Config-driven is_new (Story 7.6-18)
            {is_new_sql} as is_new,

            -- Config-driven is_winning_this_year (Story 7.6-18)
            {is_winning_sql} as is_winning_this_year,

            -- Config-driven is_churned_this_year (Story 7.6-18)
            {is_churned_sql} as is_churned_this_year,

            -- 月末资产规模 (Aggregated AUM)
            COALESCE((
                SELECT SUM(s.期末资产规模)
                FROM business.规模明细 s
                WHERE s.company_id = c.company_id
                  AND s.产品线代码 = c.product_line_code
                  AND s.月度 = DATE_TRUNC('month', %(snapshot_month)s::date)
            ), 0) as aum_balance,

            COUNT(DISTINCT c.plan_code) as plan_count

        FROM customer."客户年金计划" c
        WHERE c.valid_to = '9999-12-31'
        GROUP BY c.company_id, c.product_line_code

        ON CONFLICT (snapshot_month, company_id, product_line_code)
        DO UPDATE SET
            product_line_name = EXCLUDED.product_line_name,
            customer_name = EXCLUDED.customer_name,
            is_strategic = EXCLUDED.is_strategic,
            is_existing = EXCLUDED.is_existing,
            is_new = EXCLUDED.is_new,
            is_winning_this_year = EXCLUDED.is_winning_this_year,
            is_churned_this_year = EXCLUDED.is_churned_this_year,
            aum_balance = EXCLUDED.aum_balance,
            plan_count = EXCLUDED.plan_count,
            updated_at = CURRENT_TIMESTAMP;
    """

    query_params = {"snapshot_month": snapshot_month, "snapshot_year": snapshot_year}
    cur.execute(refresh_sql, query_params)
    return cur.rowcount


def _refresh_plan_snapshot(
    cur: psycopg.Cursor,
    snapshot_month: str,
    snapshot_year: int,
) -> int:
    """Refresh Plan-level snapshot table.

    Story 7.6-18: Uses StatusEvaluator for config-driven status derivation.

    Args:
        cur: Database cursor
        snapshot_month: End-of-month date string
        snapshot_year: Year for status derivation

    Returns:
        Number of records upserted
    """
    evaluator = get_status_evaluator()
    params = {"snapshot_year": snapshot_year}

    # Generate config-driven SQL fragment for plan-level churn
    is_churned_plan_sql = evaluator.generate_sql_fragment(
        "is_churned_this_year_plan", "c", params
    )

    logger.debug(
        "status_evaluator.plan_sql_generated",
        is_churned_plan_sql=is_churned_plan_sql[:LOG_SQL_TRUNCATE_LENGTH] + "..."
        if len(is_churned_plan_sql) > LOG_SQL_TRUNCATE_LENGTH
        else is_churned_plan_sql,
    )

    refresh_sql = f"""
        INSERT INTO customer."客户计划月度快照" (
            snapshot_month,
            company_id,
            plan_code,
            product_line_code,
            customer_name,
            plan_name,
            product_line_name,
            is_churned_this_year,
            contract_status,
            aum_balance
        )
        SELECT
            %(snapshot_month)s::date as snapshot_month,
            c.company_id,
            c.plan_code,
            c.product_line_code,
            c.customer_name,
            c.plan_name,
            c.product_line_name,

            -- Config-driven plan-level churn (Story 7.6-18)
            {is_churned_plan_sql} as is_churned_this_year,

            c.contract_status,

            -- Plan-level AUM (aggregated by plan + product line)
            COALESCE((
                SELECT SUM(s.期末资产规模)
                FROM business.规模明细 s
                WHERE s.company_id = c.company_id
                  AND s.计划代码 = c.plan_code
                  AND s.产品线代码 = c.product_line_code
                  AND s.月度 = DATE_TRUNC('month', %(snapshot_month)s::date)
            ), 0) as aum_balance

        FROM customer."客户年金计划" c
        WHERE c.valid_to = '9999-12-31'

        ON CONFLICT (snapshot_month, company_id, plan_code, product_line_code)
        DO UPDATE SET
            customer_name = EXCLUDED.customer_name,
            plan_name = EXCLUDED.plan_name,
            product_line_name = EXCLUDED.product_line_name,
            is_churned_this_year = EXCLUDED.is_churned_this_year,
            contract_status = EXCLUDED.contract_status,
            aum_balance = EXCLUDED.aum_balance,
            updated_at = CURRENT_TIMESTAMP;
    """

    query_params = {"snapshot_month": snapshot_month, "snapshot_year": snapshot_year}
    cur.execute(refresh_sql, query_params)
    return cur.rowcount


def refresh_monthly_snapshot(
    period: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Refresh monthly snapshots for both ProductLine and Plan tables.

    Performs idempotent UPSERT operations on both fact tables:
    1. "客户业务月度快照" (ProductLine granularity)
    2. "客户计划月度快照" (Plan granularity)

    Args:
        period: Period to refresh (YYYYMM format).
            If not specified, uses current month.
        dry_run: If True, logs actions without executing database changes

    Returns:
        Dictionary with refresh statistics:
        - product_line_upserted: Records upserted to ProductLine table
        - plan_upserted: Records upserted to Plan table
        - total_product_lines: Total ProductLine combinations
        - total_plans: Total Plan combinations

    Raises:
        psycopg.Error: Database connection or query error
        ValueError: Invalid period format
    """
    load_dotenv(dotenv_path=".wdh_env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    if period is None:
        period = get_current_period()

    snapshot_month = period_to_snapshot_month(period)
    snapshot_year = int(period[:4])

    logger.info(
        "Starting monthly snapshot refresh",
        period=period,
        snapshot_month=snapshot_month,
        dry_run=dry_run,
    )

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            if dry_run:
                logger.info("Dry run mode: skipping database refresh")
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT (company_id, product_line_code))
                    FROM customer."客户年金计划"
                    WHERE valid_to = '9999-12-31'
                    """
                )
                total_pl = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM customer."客户年金计划"
                    WHERE valid_to = '9999-12-31'
                    """
                )
                total_plans = cur.fetchone()[0]

                return {
                    "product_line_upserted": 0,
                    "plan_upserted": 0,
                    "total_product_lines": total_pl,
                    "total_plans": total_plans,
                }

            # Refresh ProductLine table
            pl_upserted = _refresh_product_line_snapshot(
                cur, snapshot_month, snapshot_year
            )
            logger.info(
                "ProductLine snapshot refreshed",
                upserted=pl_upserted,
            )

            # Refresh Plan table
            plan_upserted = _refresh_plan_snapshot(cur, snapshot_month, snapshot_year)
            logger.info(
                "Plan snapshot refreshed",
                upserted=plan_upserted,
            )

            conn.commit()

            logger.info(
                "Monthly snapshot refresh completed",
                snapshot_month=snapshot_month,
                product_line_upserted=pl_upserted,
                plan_upserted=plan_upserted,
            )

            return {
                "product_line_upserted": pl_upserted,
                "plan_upserted": plan_upserted,
            }


if __name__ == "__main__":
    # Allow direct execution for testing
    import sys

    dry_run = "--dry-run" in sys.argv
    period_arg = None

    for i, arg in enumerate(sys.argv):
        if arg == "--period" and i + 1 < len(sys.argv):
            period_arg = sys.argv[i + 1]
            break

    result = refresh_monthly_snapshot(period=period_arg, dry_run=dry_run)

    print("Refresh completed:")
    print(f"  ProductLine upserted: {result['product_line_upserted']}")
    print(f"  Plan upserted: {result['plan_upserted']}")
