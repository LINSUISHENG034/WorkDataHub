"""Create missing domain tables from domain_registry (Story 6.2-P13).

This migration creates domain tables that don't yet exist. All operations
are IDEMPOTENT - if tables already exist, they are skipped.

Current database state (2025-12-19):
- business.规模明细 - EXISTS (skip)
- business.收入明细 - MISSING (create)
- mapping.年金计划 - EXISTS (skip)
- mapping.组合计划 - EXISTS (skip)

Story 6.2-P13: Unified Domain Schema Management Architecture
AC-3.1: Add new idempotent migrations for physical domain tables

Revision ID: 20251219_000001
Revises: Merges 20251207_000001, 20251214_000003
Create Date: 2025-12-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision = "20251219_000001"
# Merge both heads - this migration depends on both branches
down_revision = ("20251207_000001", "20251214_000003")
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str, schema: str | None = None) -> bool:
    """Check if a table exists in the database."""
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = :table
            )
            """
        ),
        {"schema": schema or "public", "table": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Create missing domain tables (idempotent - skips existing tables).

    Story 6.2-P13: Uses domain_registry as Single Source of Truth.
    Only creates tables that don't exist yet.
    """
    conn = op.get_bind()

    # === business.收入明细 (annuity_income) - MISSING ===
    if not _table_exists(conn, "收入明细", "business"):
        op.create_table(
            "收入明细",
            # Primary Key
            sa.Column(
                "annuity_income_id",
                sa.Integer(),
                sa.Identity(always=True),
                primary_key=True,
            ),
            # Business columns - from domain_registry annuity_income
            sa.Column("月度", sa.Date(), nullable=False, comment="Report date"),
            sa.Column("计划号", sa.String(255), nullable=False, comment="Plan code"),
            sa.Column(
                "company_id", sa.String(50), nullable=False, comment="Company ID"
            ),
            sa.Column("客户名称", sa.String(255), nullable=False),
            sa.Column("年金账户名", sa.String(255), nullable=True),
            sa.Column("业务类型", sa.String(255), nullable=True),
            sa.Column("计划类型", sa.String(255), nullable=True),
            sa.Column("组合代码", sa.String(255), nullable=True),
            sa.Column("产品线代码", sa.String(255), nullable=True),
            sa.Column("机构代码", sa.String(255), nullable=True),
            sa.Column("固费", sa.Numeric(18, 4), nullable=False),
            sa.Column("浮费", sa.Numeric(18, 4), nullable=False),
            sa.Column("回补", sa.Numeric(18, 4), nullable=False),
            sa.Column("税", sa.Numeric(18, 4), nullable=False),
            # Audit columns
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
            ),
            schema="business",
        )

        # Indexes for 收入明细
        op.create_index("idx_收入明细_月度", "收入明细", ["月度"], schema="business")
        op.create_index(
            "idx_收入明细_计划号", "收入明细", ["计划号"], schema="business"
        )
        op.create_index(
            "idx_收入明细_company_id", "收入明细", ["company_id"], schema="business"
        )
        op.create_index(
            "idx_收入明细_月度_计划号_company_id",
            "收入明细",
            ["月度", "计划号", "company_id"],
            schema="business",
        )

        # updated_at trigger (match existing DDL convention)
        op.execute(
            sa.text(
                """
                CREATE OR REPLACE FUNCTION business.update_annuity_income_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_trigger
                        WHERE tgname = 'trigger_update_annuity_income_updated_at'
                    ) THEN
                        CREATE TRIGGER trigger_update_annuity_income_updated_at
                            BEFORE UPDATE ON business."收入明细"
                            FOR EACH ROW
                            EXECUTE FUNCTION business.update_annuity_income_updated_at();
                    END IF;
                END $$;
                """
            )
        )

    # === Other tables already exist ===
    # business.规模明细 - EXISTS
    # mapping.年金计划 - EXISTS
    # mapping.组合计划 - EXISTS
    # No action needed for these tables


def downgrade() -> None:
    """Drop only the tables created by this migration.

    WARNING: This will DELETE ALL DATA in 收入明细!
    Only run in development/testing environments.
    """
    conn = op.get_bind()

    # Only drop 收入明细 if it exists
    if _table_exists(conn, "收入明细", "business"):
        op.drop_table("收入明细", schema="business")

    # Note: Other domain tables (规模明细, 年金计划, 组合计划) were not created
    # by this migration, so they should NOT be dropped here.
