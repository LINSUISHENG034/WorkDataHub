"""Add tags JSONB column to customer.客户明细 table.

This migration adds a JSONB column for multi-dimensional customer tagging,
migrates existing data from the VARCHAR 年金客户标签 column, and creates
a GIN index for efficient tag queries.

Purpose: Enable multi-tag support for customer segmentation without schema
changes. Supports queries like: WHERE tags @> '["VIP"]'

Source table: customer.客户明细 (migrated from mapping schema in Story 7.6)

Revision ID: 20260115_000007
Revises: 20260115_000006
Create Date: 2026-01-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260115_000007"
down_revision = "20260115_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tags JSONB column with data migration and GIN index."""
    conn = op.get_bind()

    # 1. Add JSONB column with default empty array (idempotent)
    conn.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'customer'
                    AND table_name = '客户明细'
                    AND column_name = 'tags'
                ) THEN
                    ALTER TABLE customer."客户明细"
                    ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
                END IF;
            END $$;
            """
        )
    )

    # 2. Migrate existing data from 年金客户标签 to tags
    conn.execute(
        sa.text(
            """
            UPDATE customer."客户明细"
            SET tags = CASE
                WHEN "年金客户标签" IS NULL OR "年金客户标签" = '' THEN '[]'::jsonb
                ELSE jsonb_build_array("年金客户标签")
            END
            """
        )
    )

    # 3. Create GIN index for efficient tag queries (after data populated)
    conn.execute(
        sa.text(
            """
            CREATE INDEX idx_customer_detail_tags_gin
            ON customer."客户明细" USING GIN (tags)
            """
        )
    )

    # 4. Add deprecation comment to old column
    conn.execute(
        sa.text(
            """
            COMMENT ON COLUMN customer."客户明细"."年金客户标签"
            IS 'DEPRECATED: Use tags JSONB column instead'
            """
        )
    )


def downgrade() -> None:
    """Remove tags column and GIN index.

    WARNING: This will result in data loss if tags column contains
    multi-value arrays that cannot be represented in the original
    VARCHAR column.
    """
    conn = op.get_bind()

    # Remove deprecation comment
    conn.execute(
        sa.text(
            """
            COMMENT ON COLUMN customer."客户明细"."年金客户标签" IS NULL
            """
        )
    )

    # Drop GIN index
    conn.execute(
        sa.text(
            """
            DROP INDEX IF EXISTS customer.idx_customer_detail_tags_gin
            """
        )
    )

    # Drop tags column
    conn.execute(
        sa.text(
            """
            ALTER TABLE customer."客户明细" DROP COLUMN IF EXISTS tags
            """
        )
    )
