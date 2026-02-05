"""Contract status synchronization service.

Story 7.6-6: Contract Status Sync (Post-ETL Hook)
Story 7.6-11: Customer Status Field Enhancement

Populates customer.customer_plan_contract table from business.规模明细
with SCD Type 2 history support.

Contract Status Logic (v2 - Story 7.6-11):
  - 正常: 期末资产规模 > 0 AND 12个月滚动供款 > 0
  - 停缴: 期末资产规模 > 0 AND 12个月滚动供款 = 0

Strategic Customer Logic (Story 7.6-11):
  - is_strategic = TRUE if: AUM >= threshold OR top N per branch per product line
  - is_existing = TRUE if: prior year December has asset records
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

from work_data_hub.customer_mdm.sql import load_sql
from work_data_hub.customer_mdm.strategic import (
    get_strategic_threshold,
    get_whitelist_top_n,
)

logger = get_logger(__name__)


def has_status_changed(old: dict | object, new: dict | object) -> bool:
    """Detect if tracked status fields have changed between old and new records.

    Story 7.6-12: SCD Type 2 status change detection.

    Tracked fields that trigger version creation:
    - contract_status (正常 ↔ 停缴)
    - is_strategic (战客状态变化)
    - is_existing (已客状态变化)

    Args:
        old: Previous record (dict or object with attributes)
        new: New record (dict or object with attributes)

    Returns:
        True if any tracked field has changed, False otherwise
    """

    # Support both dict and object attribute access
    def get_value(record: dict | object, field: str):
        if isinstance(record, dict):
            return record.get(field)
        return getattr(record, field, None)

    return (
        get_value(old, "contract_status") != get_value(new, "contract_status")
        or get_value(old, "is_strategic") != get_value(new, "is_strategic")
        or get_value(old, "is_existing") != get_value(new, "is_existing")
    )


def determine_contract_status(
    期末资产规模: float, has_contribution_12m: bool = True
) -> str:
    """Determine contract status based on AUM and 12-month rolling contribution.

    Story 7.6-11 v2 logic:
    - 正常: AUM > 0 AND 12-month rolling contribution > 0
    - 停缴: AUM > 0 AND 12-month rolling contribution = 0
    - For AUM = 0, returns 停缴 (inactive)

    Args:
        期末资产规模: End-of-period assets under management
        has_contribution_12m: Whether there's contribution in past 12 months

    Returns:
        "正常" if active with contributions, else "停缴"
    """
    if 期末资产规模 > 0 and has_contribution_12m:
        return "正常"
    return "停缴"


def _build_close_old_records_sql() -> str:
    """Build SQL to close old records when status changes (SCD Type 2 Step 1).

    Story 7.6-12: Implements proper SCD Type 2 versioning.
    Loads SQL from sql/close_old_records.sql with common CTEs injected.

    Parameters order: whitelist_top_n, strategic_threshold

    Returns:
        SQL string for closing old records
    """
    common_ctes = load_sql("common_ctes.sql")
    close_sql = load_sql("close_old_records.sql")
    return close_sql.replace("{common_ctes}", common_ctes)


def _build_sync_sql() -> str:
    """Build the SQL for contract status sync with full business logic.

    Story 7.6-11: Implements is_strategic, is_existing, and contract_status v2.
    Story 7.6-12: Modified to only insert new/changed records (SCD Type 2 Step 2).
    Loads SQL from sql/sync_insert.sql with common CTEs injected.

    Note: Uses %s placeholders for parameterized queries. Parameters order:
    1. whitelist_top_n
    2. strategic_threshold

    Returns:
        SQL string for the sync operation (requires 2 parameters)
    """
    common_ctes = load_sql("common_ctes.sql")
    insert_sql = load_sql("sync_insert.sql")
    return insert_sql.replace("{common_ctes}", common_ctes)


def sync_contract_status(
    period: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Synchronize contract status from business.规模明细 to
    customer.customer_plan_contract.

    Story 7.6-12: Implements proper SCD Type 2 versioning:
    - Step 1: Close old records when status changes (UPDATE valid_to)
    - Step 2: Insert new/changed records with current status

    This ensures status changes are properly versioned and historical
    queries return correct point-in-time status.

    Args:
        period: Reserved for future use. Currently ignored - syncs all data.
        dry_run: If True, logs actions without executing database changes

    Returns:
        Dictionary with sync statistics:
        - inserted: Number of new records inserted
        - closed: Number of old records closed (status changed)
        - total: Total number of source records

    Raises:
        psycopg.Error: Database connection or query error
    """
    # Force .wdh_env to override system environment variables (Story 7.3-5 pattern)
    load_dotenv(dotenv_path=".wdh_env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    logger.info(
        "Starting contract status sync (SCD Type 2)",
        period=period,
        dry_run=dry_run,
    )

    # Load config values for SQL parameters
    strategic_threshold = get_strategic_threshold()
    whitelist_top_n = get_whitelist_top_n()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            if dry_run:
                logger.info("Dry run mode: skipping database sync")
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
                    "closed": 0,
                    "total": total_count,
                }

            # SCD Type 2 Step 1: Close old records with changed status
            close_sql = _build_close_old_records_sql()
            cur.execute(close_sql, (whitelist_top_n, strategic_threshold))
            closed = cur.rowcount

            logger.info(
                "SCD Type 2 Step 1: Closed old records",
                closed=closed,
            )

            # SCD Type 2 Step 2: Insert new/changed records
            insert_sql = _build_sync_sql()
            cur.execute(insert_sql, (whitelist_top_n, strategic_threshold))
            inserted = cur.rowcount

            logger.info(
                "SCD Type 2 Step 2: Inserted new records",
                inserted=inserted,
            )

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
                "Contract status sync completed (SCD Type 2)",
                inserted=inserted,
                closed=closed,
                total=total,
            )

            return {
                "inserted": inserted,
                "closed": closed,
                "total": total,
            }


if __name__ == "__main__":
    # Allow direct execution for testing
    import sys

    dry_run = "--dry-run" in sys.argv

    result = sync_contract_status(dry_run=dry_run)

    print("Sync completed (SCD Type 2):")
    print(f"  Inserted: {result['inserted']}")
    print(f"  Closed: {result['closed']}")
    print(f"  Total processed: {result['total']}")
