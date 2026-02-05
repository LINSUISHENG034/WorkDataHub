"""Year initialization service for customer status fields.

Story 7.6-11: Customer Status Field Enhancement
AC-3: Create CLI command for annual status initialization

Updates is_strategic and is_existing fields for all contracts in a given year.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

from work_data_hub.customer_mdm.strategic import (
    get_strategic_threshold,
    get_whitelist_top_n,
)

logger = get_logger(__name__)


def initialize_year_status(
    year: int,
    dry_run: bool = False,
) -> dict[str, int]:
    """Initialize is_strategic and is_existing for ALL contracts.

    Uses prior year data to determine status fields.

    This function updates ALL contracts in the table (regardless of status_year)
    because the contract table uses a single-record-per-contract design.

    The year parameter determines which prior year data to use for whitelist:
    - is_strategic: Based on (year-1) December AUM threshold and top N per branch
    - is_existing: Based on (year-1) December asset records

    This function is idempotent - safe to re-run multiple times.

    Args:
        year: Reference year (e.g., 2026). Prior year data used for whitelist.
        dry_run: If True, logs actions without executing database changes

    Returns:
        Dictionary with initialization statistics:
        - strategic_updated: Number of records marked as strategic
        - existing_updated: Number of records marked as existing
        - total: Total number of contracts in table

    Raises:
        psycopg.Error: Database connection or query error
    """
    load_dotenv(dotenv_path=".wdh_env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    strategic_threshold = get_strategic_threshold()
    whitelist_top_n = get_whitelist_top_n()
    prior_year = year - 1

    logger.info(
        "Starting year initialization",
        year=year,
        prior_year=prior_year,
        strategic_threshold=strategic_threshold,
        whitelist_top_n=whitelist_top_n,
        dry_run=dry_run,
    )

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            if dry_run:
                return _dry_run_counts(cur, year)

            strategic_updated = _update_strategic(
                cur, year, prior_year, strategic_threshold, whitelist_top_n
            )
            existing_updated = _update_existing(cur, year, prior_year)

            cur.execute(
                """
                SELECT COUNT(*)
                FROM customer.customer_plan_contract
                """
            )
            total = cur.fetchone()[0]

            conn.commit()

            logger.info(
                "Year initialization completed",
                year=year,
                strategic_updated=strategic_updated,
                existing_updated=existing_updated,
                total=total,
            )

            return {
                "strategic_updated": strategic_updated,
                "existing_updated": existing_updated,
                "total": total,
            }


def _dry_run_counts(cur, year: int) -> dict[str, int]:
    """Get counts for dry run mode without making changes."""
    cur.execute(
        """
        SELECT COUNT(*)
        FROM customer.customer_plan_contract
        """
    )
    total = cur.fetchone()[0]

    logger.info("Dry run mode: skipping database updates", total_contracts=total)

    return {
        "strategic_updated": 0,
        "existing_updated": 0,
        "total": total,
    }


def _update_strategic(
    cur, year: int, prior_year: int, threshold: int, top_n: int
) -> int:
    """Update is_strategic field based on threshold and whitelist."""
    sql = """
        WITH strategic_whitelist AS (
            SELECT company_id, 计划代码, 产品线代码
            FROM (
                SELECT
                    company_id,
                    计划代码,
                    产品线代码,
                    机构代码,
                    SUM(期末资产规模) as total_aum,
                    ROW_NUMBER() OVER (
                        PARTITION BY 机构代码, 产品线代码
                        ORDER BY SUM(期末资产规模) DESC
                    ) as rank_in_branch
                FROM business.规模明细
                WHERE EXTRACT(MONTH FROM 月度) = 12
                  AND EXTRACT(YEAR FROM 月度) = %s
                  AND company_id IS NOT NULL
                GROUP BY company_id, 计划代码, 产品线代码, 机构代码
            ) ranked
            WHERE rank_in_branch <= %s
               OR total_aum >= %s
        )
        UPDATE customer.customer_plan_contract c
        SET is_strategic = TRUE
        FROM strategic_whitelist sw
        WHERE c.company_id = sw.company_id
          AND c.plan_code = sw.计划代码
          AND c.product_line_code = sw.产品线代码
          AND c.is_strategic = FALSE
    """
    cur.execute(sql, (prior_year, top_n, threshold))
    return cur.rowcount


def _update_existing(cur, year: int, prior_year: int) -> int:
    """Update is_existing field based on prior year December assets."""
    sql = """
        WITH prior_year_dec AS (
            SELECT DISTINCT company_id, 计划代码, 产品线代码
            FROM business.规模明细
            WHERE EXTRACT(MONTH FROM 月度) = 12
              AND EXTRACT(YEAR FROM 月度) = %s
              AND 期末资产规模 > 0
              AND company_id IS NOT NULL
        )
        UPDATE customer.customer_plan_contract c
        SET is_existing = TRUE
        FROM prior_year_dec pyd
        WHERE c.company_id = pyd.company_id
          AND c.plan_code = pyd.计划代码
          AND c.product_line_code = pyd.产品线代码
          AND c.is_existing = FALSE
    """
    cur.execute(sql, (prior_year,))
    return cur.rowcount
