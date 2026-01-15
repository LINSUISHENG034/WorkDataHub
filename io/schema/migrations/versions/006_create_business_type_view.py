"""Create customer.v_customer_business_monthly_status_by_type view.

This migration creates a pre-aggregated view that groups customer award/loss
data by business type (受托/投资) with monthly aggregation.

Purpose: Enable BI Analysts to quickly analyze award/loss patterns across
different product lines without writing complex SQL joins.

Source tables:
- customer.当年中标 (awards)
- customer.当年流失 (losses)

Revision ID: 20260115_000006
Revises: 20260115_000005
Create Date: 2026-01-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260115_000006"
down_revision = "20260115_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create customer.v_customer_business_monthly_status_by_type view."""
    conn = op.get_bind()

    # Ensure customer schema exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS customer"))

    # Drop view if exists for idempotency
    conn.execute(
        sa.text(
            "DROP VIEW IF EXISTS customer.v_customer_business_monthly_status_by_type"
        )
    )

    # Create the aggregation view
    conn.execute(
        sa.text(
            """
        CREATE VIEW customer.v_customer_business_monthly_status_by_type AS
        WITH combined AS (
            SELECT "上报月份", "业务类型", company_id, 'award' AS record_type
            FROM customer."当年中标"
            UNION ALL
            SELECT "上报月份", "业务类型", company_id, 'loss' AS record_type
            FROM customer."当年流失"
        )
        SELECT
            "上报月份",
            "业务类型",
            COUNT(*) FILTER (WHERE record_type = 'award') AS award_count,
            COUNT(DISTINCT company_id) FILTER (
                WHERE record_type = 'award' AND company_id IS NOT NULL
            ) AS award_distinct_companies,
            COUNT(*) FILTER (WHERE record_type = 'loss') AS loss_count,
            COUNT(DISTINCT company_id) FILTER (
                WHERE record_type = 'loss' AND company_id IS NOT NULL
            ) AS loss_distinct_companies,
            COUNT(*) FILTER (WHERE record_type = 'award')
                - COUNT(*) FILTER (WHERE record_type = 'loss') AS net_change
        FROM combined
        GROUP BY "上报月份", "业务类型"
        ORDER BY "上报月份" DESC, "业务类型"
        """
        )
    )


def downgrade() -> None:
    """Drop customer.v_customer_business_monthly_status_by_type view."""
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DROP VIEW IF EXISTS "
            "customer.v_customer_business_monthly_status_by_type CASCADE"
        )
    )
