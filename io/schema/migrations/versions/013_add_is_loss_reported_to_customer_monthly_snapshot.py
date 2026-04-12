"""Add is_loss_reported to 客户业务月度快照 and BI fact view.

This migration makes the reported-loss status a first-class surfaced field in
the product-line monthly snapshot.

Revision ID: 20260411_000013
Revises: 20260228_000012
Create Date: 2026-04-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260411_000013"
down_revision = "20260228_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            ALTER TABLE customer."客户业务月度快照"
            ADD COLUMN IF NOT EXISTS is_loss_reported BOOLEAN DEFAULT FALSE
            """
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_fct_pl_loss_reported
                ON customer."客户业务月度快照"(snapshot_month)
                WHERE is_loss_reported = TRUE
            """
        )
    )

    conn.execute(
        sa.text(
            """
            DROP VIEW IF EXISTS bi.fct_customer_monthly_summary;

            CREATE OR REPLACE VIEW bi.fct_customer_monthly_summary AS
            SELECT
                snapshot_month,
                company_id,
                product_line_code,
                product_line_name,
                is_strategic,
                is_existing,
                is_new,
                is_winning_this_year AS is_winning,
                is_loss_reported,
                is_churned_this_year AS is_churned,
                aum_balance,
                plan_count,
                updated_at
            FROM customer."客户业务月度快照"
            """
        )
    )
    conn.execute(
        sa.text(
            """
            COMMENT ON VIEW bi.fct_customer_monthly_summary
            IS 'Monthly status fact'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DROP INDEX IF EXISTS customer.idx_fct_pl_loss_reported"))

    conn.execute(
        sa.text(
            """
            DROP VIEW IF EXISTS bi.fct_customer_monthly_summary;

            CREATE OR REPLACE VIEW bi.fct_customer_monthly_summary AS
            SELECT
                snapshot_month,
                company_id,
                product_line_code,
                product_line_name,
                is_strategic,
                is_existing,
                is_new,
                is_winning_this_year AS is_winning,
                is_churned_this_year AS is_churned,
                aum_balance,
                plan_count,
                updated_at
            FROM customer."客户业务月度快照"
            """
        )
    )
    conn.execute(
        sa.text(
            """
            COMMENT ON VIEW bi.fct_customer_monthly_summary
            IS 'Monthly status fact'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            ALTER TABLE customer."客户业务月度快照"
            DROP COLUMN IF EXISTS is_loss_reported
            """
        )
    )
