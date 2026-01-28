"""Contract status synchronization service.

Story 7.6-6: Contract Status Sync (Post-ETL Hook)
Populates customer.customer_plan_contract table from business.规模明细
with SCD Type 2 history support.

Contract Status Logic (v1 simplified):
  - 正常: 期末资产规模 > 0
  - 停缴: 期末资产规模 = 0

Future enhancements (Story 7.6-9):
  - is_strategic: Strategic customer flag based on AUM threshold
  - is_existing: Existing customer flag from historical data
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

logger = get_logger(__name__)


def determine_contract_status(期末资产规模: float) -> str:
    """Determine contract status based on end-of-period AUM.

    NOTE: This is v1 simplified logic. Full v2 logic (12-month rolling window)
    is defined in specification v0.6 §4.3.1-4.3.2 and will be implemented
    when 供款 data is available.

    Args:
        期末资产规模: End-of-period assets under management

    Returns:
        "正常" if AUM > 0, else "停缴"
    """
    if 期末资产规模 > 0:
        return "正常"
    return "停缴"


def sync_contract_status(
    period: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Synchronize contract status from business.规模明细 to
    customer.customer_plan_contract.

    This function performs an idempotent upsert operation:
    - Inserts new contract records for ALL available periods
    - Uses ON CONFLICT DO NOTHING for idempotent writes
    - Does NOT implement true SCD Type 2 versioning (v1 simplified)

    Note:
        v1 Implementation: The `period` parameter is currently UNUSED.
        All available data from business.规模明细 is synced regardless of
        the period argument. Period filtering may be added in Story 7.6-9.

    Args:
        period: Reserved for future use. Currently ignored - syncs all data.
        dry_run: If True, logs actions without executing database changes

    Returns:
        Dictionary with sync statistics:
        - inserted: Number of new records inserted
        - updated: Number of existing records updated
        - total: Total number of records processed

    Raises:
        psycopg.Error: Database connection or query error
    """
    # Force .wdh_env to override system environment variables (Story 7.3-5 pattern)
    load_dotenv(dotenv_path=".wdh_env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    logger.info(
        "Starting contract status sync",
        period=period,
        dry_run=dry_run,
    )

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # Build sync SQL with idempotent UPSERT
            sync_sql = """
                INSERT INTO customer.customer_plan_contract (
                    company_id,
                    plan_code,
                    product_line_code,
                    product_line_name,
                    is_strategic,
                    is_existing,
                    status_year,
                    contract_status,
                    valid_from,
                    valid_to
                )
                SELECT DISTINCT
                    s.company_id,
                    s.计划代码 as plan_code,
                    s.产品线代码 as product_line_code,
                    COALESCE(p.产品线, s.业务类型) as product_line_name,
                    FALSE as is_strategic,  -- Story 7.6-9 implements full logic
                    FALSE as is_existing,  -- Story 7.6-9 implements full logic
                    EXTRACT(YEAR FROM s.月度) as status_year,
                    CASE
                        WHEN s.期末资产规模 > 0 THEN '正常'
                        ELSE '停缴'
                    END as contract_status,
                    (date_trunc('month', s.月度) +
                        interval '1 month - 1 day')::date as valid_from,
                    '9999-12-31'::date as valid_to
                FROM business.规模明细 s
                LEFT JOIN mapping."产品线" p ON s.产品线代码 = p.产品线代码
                WHERE s.company_id IS NOT NULL
                  AND s.产品线代码 IS NOT NULL
                  AND s.计划代码 IS NOT NULL
                ON CONFLICT (company_id, plan_code, product_line_code, valid_to)
                DO NOTHING
                RETURNING xmin;
            """

            if dry_run:
                logger.info("Dry run mode: skipping database sync")
                # Run count query only for dry run
                count_sql = """
                    SELECT COUNT(DISTINCT s.company_id || s.计划代码 || s.产品线代码)
                    FROM business.规模明细 s
                    WHERE s.company_id IS NOT NULL
                      AND s.产品线代码 IS NOT NULL
                      AND s.计划代码 IS NOT NULL
                """
                cur.execute(count_sql)
                total_count = cur.fetchone()[0]

                return {
                    "inserted": 0,
                    "updated": 0,
                    "total": total_count,
                }

            # Execute the sync
            cur.execute(sync_sql)
            inserted = cur.rowcount

            # Get total source records for logging
            cur.execute(
                """
                SELECT COUNT(DISTINCT company_id || 计划代码 || 产品线代码)
                FROM business.规模明细
                WHERE company_id IS NOT NULL
                  AND 产品线代码 IS NOT NULL
                  AND 计划代码 IS NOT NULL
                """
            )
            total = cur.fetchone()[0]

            conn.commit()

            logger.info(
                "Contract status sync completed",
                inserted=inserted,
                total=total,
            )

            return {
                "inserted": inserted,
                "updated": 0,
                "total": total,
            }


if __name__ == "__main__":
    # Allow direct execution for testing
    import sys

    dry_run = "--dry-run" in sys.argv

    result = sync_contract_status(dry_run=dry_run)

    print("Sync completed:")
    print(f"  Inserted: {result['inserted']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Total processed: {result['total']}")
