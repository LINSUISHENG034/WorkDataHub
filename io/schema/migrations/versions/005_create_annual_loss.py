"""Create customer.流失客户明细 table for Annual Loss domain.

This migration creates the unified annual loss table that consolidates:
- Legacy: 企年受托流失 (TrusteeLossCleaner)
- Legacy: 企年投资流失 (InvesteeLossCleaner)

Key changes from legacy:
- Dropped columns: 区域, 年金中心, 上报人, 考核标签 (per requirement #1)
- Dropped investment redundant fields: 战区前五大, 中心前十大, 机构前十大, 五亿以上
- Renamed: 受托人 → 原受托人, 客户全称 → 上报客户名称
- 业务类型 uses product line names: 企年受托, 企年投资

Revision ID: 20260115_000005
Revises: 20260111_000004
Create Date: 2026-01-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260115_000005"
down_revision = "20260111_000004"
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
    """Create customer.流失客户明细 table."""
    conn = op.get_bind()

    # Create customer schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS customer"))

    if not _table_exists(conn, "流失客户明细", "customer"):
        conn.execute(
            sa.text(
                """
            CREATE TABLE customer."流失客户明细" (
                -- Primary key
                id SERIAL PRIMARY KEY,

                -- Required identification fields
                "上报月份" DATE NOT NULL,
                "业务类型" VARCHAR(20) NOT NULL,  -- 企年受托/企年投资
                "产品线代码" VARCHAR(10),          -- PL201/PL202 derived from 业务类型

                -- Customer name fields (requirement #5)
                "上报客户名称" VARCHAR(255) NOT NULL,  -- Original 客户全称
                "客户名称" VARCHAR(255),               -- Cleaned name

                -- Plan and company identification (requirement #4)
                "年金计划号" VARCHAR(50),
                company_id VARCHAR(50),

                -- Institution (mapped from 机构)
                "机构名称" VARCHAR(100),           -- Original institution name
                "机构代码" VARCHAR(10) NOT NULL DEFAULT 'G00',

                -- Loss information
                "流失日期" DATE,
                "计划规模" NUMERIC(18, 4),  -- 亿元
                "年缴规模" NUMERIC(18, 4),  -- 亿元

                -- Classification
                "客户类型" VARCHAR(50),
                "原受托人" VARCHAR(255),    -- Renamed from 受托人
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

        _create_indexes(conn)
        _create_trigger(conn)


def _create_indexes(conn) -> None:
    """Create indexes for common query patterns."""
    conn.execute(
        sa.text(
            """
        CREATE INDEX idx_annual_loss_report_month
        ON customer."流失客户明细"("上报月份")
        """
        )
    )
    conn.execute(
        sa.text(
            """
        CREATE INDEX idx_annual_loss_business_type
        ON customer."流失客户明细"("业务类型")
        """
        )
    )
    conn.execute(
        sa.text(
            """
        CREATE INDEX idx_annual_loss_company_id
        ON customer."流失客户明细"(company_id)
        """
        )
    )
    conn.execute(
        sa.text(
            """
        CREATE INDEX idx_annual_loss_plan_code
        ON customer."流失客户明细"("年金计划号")
        """
        )
    )


def _create_trigger(conn) -> None:
    """Create trigger for updated_at."""
    conn.execute(
        sa.text(
            """
        CREATE OR REPLACE FUNCTION update_annual_loss_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
        )
    )

    conn.execute(
        sa.text(
            """
        CREATE TRIGGER trg_annual_loss_updated_at
        BEFORE UPDATE ON customer."流失客户明细"
        FOR EACH ROW EXECUTE FUNCTION update_annual_loss_updated_at()
        """
        )
    )


def downgrade() -> None:
    """Drop customer.流失客户明细 table."""
    conn = op.get_bind()

    if _table_exists(conn, "流失客户明细", "customer"):
        conn.execute(sa.text('DROP TABLE IF EXISTS customer."流失客户明细" CASCADE'))

    # Drop trigger function
    conn.execute(
        sa.text("DROP FUNCTION IF EXISTS update_annual_loss_updated_at() CASCADE")
    )
