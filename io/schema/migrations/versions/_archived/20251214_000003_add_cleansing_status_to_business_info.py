"""Add _cleansing_status column to business_info table.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 4.3: Add JSONB column to track cleansing results

This migration adds:
- _cleansing_status: JSONB column to store cleansing metadata

Revision ID: 20251214_000003
Revises: 20251214_000002
Create Date: 2025-12-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20251214_000003"
down_revision = "20251214_000002"
branch_labels = None
depends_on = None

SCHEMA_NAME = "enterprise"
TABLE_NAME = "business_info"


def _column_exists(conn, table_name: str, column_name: str, schema: str) -> bool:
    """Check if a column exists in the given table."""
    result = conn.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
        )
        """
        ),
        {"schema": schema, "table": table_name, "column": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Add _cleansing_status column to business_info table.

    Uses ADD COLUMN IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()

    # === Step 1: Add _cleansing_status JSONB column ===
    if not _column_exists(conn, TABLE_NAME, "_cleansing_status", SCHEMA_NAME):
        conn.execute(
            sa.text(
                f"""
            ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
            ADD COLUMN _cleansing_status JSONB DEFAULT NULL
            """
            )
        )
        conn.execute(
            sa.text(
                f"""
            COMMENT ON COLUMN {SCHEMA_NAME}.{TABLE_NAME}._cleansing_status IS
            'Cleansing metadata: domain, fields_cleansed, fields_failed, failed_fields'
            """
            )
        )


def downgrade() -> None:
    """Remove _cleansing_status column from business_info table.

    Uses DROP COLUMN IF EXISTS for safety.
    """
    conn = op.get_bind()

    conn.execute(
        sa.text(
            f"""
        ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
        DROP COLUMN IF EXISTS _cleansing_status
        """
        )
    )
