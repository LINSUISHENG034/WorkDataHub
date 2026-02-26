"""Create BI star schema views for Power BI DirectQuery integration.

Story 7.6-8: Power BI Star Schema Integration
Task 1: Create Alembic migration for BI schema and views (AC: 1, 2, 3)

Purpose: Create optimized database views following the star schema pattern for
Power BI consumption. This enables BI analysts to perform self-service analysis
with clear dimensional relationships.

Views Created:
- bi.dim_customer: Customer dimension from customer."客户明细"
- bi.dim_product_line: Product line dimension from mapping."产品线"
- bi.dim_time: Time dimension generated from distinct snapshot_month
- bi.fct_customer_monthly_summary: Fact view from customer."客户业务月度快照"

Dependencies:
- Story 7.6-7: customer."客户业务月度快照" (Migration 009)
- Story 7.6-4: customer."客户明细".tags JSONB column (Migration 007)

Revision ID: 20260129_000010
Revises: 20260121_000009
Create Date: 2026-01-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260129_000010"
down_revision = "20260121_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create BI schema and star schema views."""
    conn = op.get_bind()

    # 1. Create BI schema
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS bi"))

    # 2. Create dim_customer view
    # Source: customer."客户明细" filtered to customers with contract data
    # Using EXISTS for better performance with large datasets
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW bi.dim_customer AS
            SELECT
                c.company_id,
                c."客户名称" AS customer_name,
                c."年金客户类型" AS customer_type,
                c.tags AS customer_tags,
                c."客户简称" AS customer_short_name,
                c."最新受托规模" AS latest_trustee_aum,
                c."最新投管规模" AS latest_investment_aum,
                c."规模区间" AS aum_tier,
                c."关联计划数" AS plan_count
            FROM customer."客户明细" c
            WHERE EXISTS (
                SELECT 1 FROM customer."客户业务月度快照" f
                WHERE f.company_id = c.company_id
            );

            COMMENT ON VIEW bi.dim_customer IS 'Customer dimension for BI star schema';
            """
        )
    )

    # 3. Create dim_product_line view
    # Source: mapping."产品线" (full dimension - small table)
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW bi.dim_product_line AS
            SELECT
                "产品线代码" AS product_line_code,
                "产品线" AS product_line_name,
                "业务大类" AS business_category
            FROM mapping."产品线";

            COMMENT ON VIEW bi.dim_product_line IS 'Product line dimension for BI';
            """
        )
    )

    # 4. Create dim_time view
    # Source: Generated from distinct snapshot_month in fact table
    # Note: ORDER BY removed - views don't guarantee order; use ORDER BY in queries
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW bi.dim_time AS
            SELECT DISTINCT
                snapshot_month,
                EXTRACT(YEAR FROM snapshot_month)::INTEGER AS year,
                EXTRACT(QUARTER FROM snapshot_month)::INTEGER AS quarter,
                EXTRACT(MONTH FROM snapshot_month)::INTEGER AS month_number,
                TO_CHAR(snapshot_month, 'FMMonth') AS month_name,
                TO_CHAR(snapshot_month, 'YYYY-MM') AS year_month_label
            FROM customer."客户业务月度快照";

            COMMENT ON VIEW bi.dim_time IS 'Time dimension derived from snapshot_month';
            """
        )
    )

    # 5. Create fct_customer_monthly_summary fact view
    # Source: customer."客户业务月度快照"
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW bi.fct_customer_monthly_summary AS
            SELECT
                -- Keys (using natural keys for dimension joins)
                snapshot_month,
                company_id,
                product_line_code,
                product_line_name,

                -- Status Flags
                is_strategic,
                is_existing,
                is_new,
                is_winning_this_year AS is_winning,
                is_churned_this_year AS is_churned,

                -- Measures
                aum_balance,
                plan_count,

                -- Audit
                updated_at
            FROM customer."客户业务月度快照";

            COMMENT ON VIEW bi.fct_customer_monthly_summary IS 'Monthly status fact';
            """
        )
    )


def downgrade() -> None:
    """Drop BI star schema views and schema."""
    conn = op.get_bind()

    # Drop views in reverse order
    conn.execute(sa.text("DROP VIEW IF EXISTS bi.fct_customer_monthly_summary"))
    conn.execute(sa.text("DROP VIEW IF EXISTS bi.dim_time"))
    conn.execute(sa.text("DROP VIEW IF EXISTS bi.dim_product_line"))
    conn.execute(sa.text("DROP VIEW IF EXISTS bi.dim_customer"))

    # Drop schema (only if empty)
    conn.execute(sa.text("DROP SCHEMA IF EXISTS bi"))
