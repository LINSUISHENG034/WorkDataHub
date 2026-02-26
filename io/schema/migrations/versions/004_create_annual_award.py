"""Create customer.中标客户明细 table for Annual Award domain.

This migration creates the unified annual award table that consolidates:
- Legacy: 企年受托中标 (TrusteeAwardCleaner)
- Legacy: 企年投资中标 (InvesteeAwardCleaner)

Key changes from legacy:
- Dropped columns: 区域, 年金中心, 上报人 (per requirement #1)
- Dropped investment redundant fields: 战区前五大, 中心前十大, 机构前十大, 五亿以上
- Renamed: 客户全称 → 上报客户名称, cleaned to 客户名称
- 业务类型 uses product line names: 企年受托, 企年投资

Revision ID: 20260111_000004
Revises: 003_seed_static_data
Create Date: 2026-01-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260111_000004"
down_revision = "20251228_000003"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str, schema: str) -> bool:
    """Check if a table exists in the given schema."""
    result = conn.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
        )
        """
        ),
        {"schema": schema, "table": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Create customer.中标客户明细 table."""
    conn = op.get_bind()

    # Create customer schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS customer"))

    if not _table_exists(conn, "中标客户明细", "customer"):
        conn.execute(
            sa.text(
                """
            CREATE TABLE customer."中标客户明细" (
                -- Primary key
                id SERIAL PRIMARY KEY,
                
                -- Required identification fields
                "上报月份" DATE NOT NULL,
                "业务类型" VARCHAR(20) NOT NULL,  -- 企年受托/企年投资 (references mapping.产品线)
                "产品线代码" VARCHAR(10),          -- QN01/QN02 derived from 业务类型
                
                -- Customer name fields (transformed per requirement #3)
                "上报客户名称" VARCHAR(255) NOT NULL,  -- Original 客户全称
                "客户名称" VARCHAR(255),               -- Cleaned via customer_name_normalize
                
                -- Plan and company identification (conditional update per requirement #2)
                "年金计划号" VARCHAR(50),
                company_id VARCHAR(50),
                
                -- Institution (mapped from 机构)
                "机构名称" VARCHAR(100),           -- Original institution name
                "机构代码" VARCHAR(10) NOT NULL DEFAULT 'G00',
                
                -- Award information
                "中标日期" DATE,
                "计划规模" NUMERIC(18, 4),  -- 亿元
                "年缴规模" NUMERIC(18, 4),  -- 亿元
                
                -- Classification
                "客户类型" VARCHAR(50),
                "原受托人" VARCHAR(255),
                "计划类型" VARCHAR(50),      -- 集合计划/单一计划
                "证明材料" VARCHAR(255),
                "考核有效" INTEGER DEFAULT 0,  -- 0 or 1
                "备注" TEXT,
                
                -- Audit fields
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
        )

        # Create indexes for common query patterns
        conn.execute(
            sa.text(
                """
            CREATE INDEX idx_annual_award_report_month 
            ON customer."中标客户明细"("上报月份")
            """
            )
        )
        conn.execute(
            sa.text(
                """
            CREATE INDEX idx_annual_award_business_type 
            ON customer."中标客户明细"("业务类型")
            """
            )
        )
        conn.execute(
            sa.text(
                """
            CREATE INDEX idx_annual_award_company_id 
            ON customer."中标客户明细"(company_id)
            """
            )
        )
        conn.execute(
            sa.text(
                """
            CREATE INDEX idx_annual_award_plan_code 
            ON customer."中标客户明细"("年金计划号")
            """
            )
        )

        # Create trigger function for updated_at
        conn.execute(
            sa.text(
                """
            CREATE OR REPLACE FUNCTION update_annual_award_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
            )
        )

        # Create trigger
        conn.execute(
            sa.text(
                """
            CREATE TRIGGER trg_annual_award_updated_at
            BEFORE UPDATE ON customer."中标客户明细"
            FOR EACH ROW EXECUTE FUNCTION update_annual_award_updated_at()
            """
            )
        )


def downgrade() -> None:
    """Drop customer.中标客户明细 table."""
    conn = op.get_bind()

    if _table_exists(conn, "中标客户明细", "customer"):
        conn.execute(sa.text('DROP TABLE IF EXISTS customer."中标客户明细" CASCADE'))

    # Drop trigger function
    conn.execute(
        sa.text("DROP FUNCTION IF EXISTS update_annual_award_updated_at() CASCADE")
    )
