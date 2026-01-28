"""Monthly snapshot refresh service.

Story 7.6-7: Monthly Snapshot Refresh (Post-ETL Hook)
Populates customer.fct_customer_business_monthly_status table from
customer.customer_plan_contract with aggregated status flags and AUM.

Granularity: Customer + Product Line (monthly snapshot)
Source: customer.customer_plan_contract (current active contracts)
Status derivation:
  - is_strategic: Aggregated from contract attributes (BOOL_OR)
  - is_existing: Aggregated from contract attributes (BOOL_OR)
  - is_winning_this_year: Derived from customer.当年中标
  - is_churned_this_year: Derived from customer.当年流失
  - is_new: is_winning AND NOT is_existing
  - aum_balance: Aggregated from business.规模明细
  - plan_count: COUNT DISTINCT plan_code
"""

from __future__ import annotations

import calendar
import os
from datetime import date
from typing import Optional

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

logger = get_logger(__name__)

# Period format constants
PERIOD_LENGTH = 6  # YYYYMM format
MIN_MONTH = 1
MAX_MONTH = 12


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


def refresh_monthly_snapshot(
    period: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Refresh monthly snapshot for the specified period.

    Performs an idempotent UPSERT operation:
    - Aggregates contract data by (company_id, product_line_code)
    - Derives 中标/流失 status from customer.当年中标/当年流失 tables
    - Aggregates AUM from business.规模明细
    - Uses ON CONFLICT DO UPDATE for idempotent writes

    Args:
        period: Period to refresh (YYYYMM format).
            If not specified, uses current month.
        dry_run: If True, logs actions without executing database changes

    Returns:
        Dictionary with refresh statistics:
        - upserted: Number of records inserted or updated
        - total: Total source records available

    Raises:
        psycopg.Error: Database connection or query error
        ValueError: Invalid period format
    """
    # Force .wdh_env to override system environment variables (Story 7.3-5 pattern)
    load_dotenv(dotenv_path=".wdh_env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    # Resolve period to snapshot_month
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
            # Build refresh SQL with idempotent UPSERT
            # NOTE: This aggregates at Customer + Product Line granularity
            refresh_sql = """
                INSERT INTO customer.fct_customer_business_monthly_status (
                    snapshot_month,
                    company_id,
                    product_line_code,
                    product_line_name,
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

                    -- Aggregate attributes from contracts
                    -- (if any contract is strategic, customer is strategic)
                    BOOL_OR(c.is_strategic) as is_strategic,
                    BOOL_OR(c.is_existing) as is_existing,

                    -- Derived is_new: Winning this year AND NOT Existing
                    (
                        EXISTS (
                            SELECT 1 FROM customer.当年中标 w
                            WHERE w.company_id = c.company_id
                                AND w.产品线代码 = c.product_line_code
                                AND EXTRACT(YEAR FROM w.上报月份) = %(snapshot_year)s
                        )
                        AND NOT BOOL_OR(c.is_existing)
                    ) as is_new,

                    -- 当年中标判定 (Aggregated to Product Line level)
                    EXISTS (
                        SELECT 1 FROM customer.当年中标 w
                        WHERE w.company_id = c.company_id
                          AND w.产品线代码 = c.product_line_code
                          AND EXTRACT(YEAR FROM w.上报月份) = %(snapshot_year)s
                    ) as is_winning_this_year,

                    -- 当年流失判定 (Aggregated to Product Line level)
                    EXISTS (
                        SELECT 1 FROM customer.当年流失 l
                        WHERE l.company_id = c.company_id
                          AND l.产品线代码 = c.product_line_code
                          AND EXTRACT(YEAR FROM l.上报月份) = %(snapshot_year)s
                    ) as is_churned_this_year,

                    -- 月末资产规模 (Aggregated AUM for this customer+product line)
                    -- NOTE: 规模明细.月度 uses month-start dates (e.g., 2025-10-01)
                    -- so we use DATE_TRUNC to convert snapshot_month to month-start
                    COALESCE((
                        SELECT SUM(s.期末资产规模)
                        FROM business.规模明细 s
                        WHERE s.company_id = c.company_id
                          AND s.产品线代码 = c.product_line_code
                          AND s.月度 = DATE_TRUNC('month', %(snapshot_month)s::date)
                    ), 0) as aum_balance,

                    -- Plan Count
                    COUNT(DISTINCT c.plan_code) as plan_count

                FROM customer.customer_plan_contract c
                WHERE c.valid_to = '9999-12-31'  -- Only current active contracts
                GROUP BY c.company_id, c.product_line_code

                ON CONFLICT (snapshot_month, company_id, product_line_code)
                DO UPDATE SET
                    product_line_name = EXCLUDED.product_line_name,
                    is_strategic = EXCLUDED.is_strategic,
                    is_existing = EXCLUDED.is_existing,
                    is_new = EXCLUDED.is_new,
                    is_winning_this_year = EXCLUDED.is_winning_this_year,
                    is_churned_this_year = EXCLUDED.is_churned_this_year,
                    aum_balance = EXCLUDED.aum_balance,
                    plan_count = EXCLUDED.plan_count,
                    updated_at = CURRENT_TIMESTAMP;
            """

            params = {
                "snapshot_month": snapshot_month,
                "snapshot_year": snapshot_year,
            }

            if dry_run:
                logger.info("Dry run mode: skipping database refresh")
                # Run count query only for dry run
                count_sql = """
                    SELECT COUNT(DISTINCT company_id || product_line_code)
                    FROM customer.customer_plan_contract
                    WHERE valid_to = '9999-12-31'
                """
                cur.execute(count_sql)
                total_count = cur.fetchone()[0]

                return {
                    "upserted": 0,
                    "total": total_count,
                }

            # Execute the refresh
            cur.execute(refresh_sql, params)
            upserted = cur.rowcount

            # Get total source records for logging
            cur.execute(
                """
                SELECT COUNT(DISTINCT company_id || product_line_code)
                FROM customer.customer_plan_contract
                WHERE valid_to = '9999-12-31'
                """
            )
            total = cur.fetchone()[0]

            conn.commit()

            logger.info(
                "Monthly snapshot refresh completed",
                snapshot_month=snapshot_month,
                upserted=upserted,
                total=total,
            )

            return {
                "upserted": upserted,
                "total": total,
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
    print(f"  Upserted: {result['upserted']}")
    print(f"  Total source records: {result['total']}")
