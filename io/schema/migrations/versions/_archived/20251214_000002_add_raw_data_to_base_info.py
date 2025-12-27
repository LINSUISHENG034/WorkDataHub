"""Add raw_data and updated_at columns to base_info table.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 1.1: Create migration to add raw_data JSONB and updated_at columns

This migration adds:
- raw_data: JSONB column to store complete EQC API response
- updated_at: TIMESTAMP WITH TIME ZONE for freshness tracking

Revision ID: 20251214_000002
Revises: 20251214_000001
Create Date: 2025-12-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20251214_000002"
down_revision = "20251214_000001"
branch_labels = None
depends_on = None

SCHEMA_NAME = "enterprise"
TABLE_NAME = "base_info"


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
    """Add raw_data and updated_at columns to base_info table.

    Uses ADD COLUMN IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()

    # === Step 1: Add raw_data JSONB column ===
    if not _column_exists(conn, TABLE_NAME, "raw_data", SCHEMA_NAME):
        conn.execute(
            sa.text(
                f"""
            ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
            ADD COLUMN raw_data JSONB DEFAULT NULL
            """
            )
        )
        conn.execute(
            sa.text(
                f"""
            COMMENT ON COLUMN {SCHEMA_NAME}.{TABLE_NAME}.raw_data IS
            'Complete EQC API response JSON for audit and analysis'
            """
            )
        )

    # === Step 2: Add updated_at column ===
    if not _column_exists(conn, TABLE_NAME, "updated_at", SCHEMA_NAME):
        conn.execute(
            sa.text(
                f"""
            ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
            ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            """
            )
        )
        conn.execute(
            sa.text(
                f"""
            COMMENT ON COLUMN {SCHEMA_NAME}.{TABLE_NAME}.updated_at IS
            'Last update timestamp for data freshness tracking'
            """
            )
        )


def downgrade() -> None:
    """Remove raw_data and updated_at columns from base_info table.

    Uses DROP COLUMN IF EXISTS for safety.
    """
    conn = op.get_bind()

    # Drop columns in reverse order
    conn.execute(
        sa.text(
            f"""
        ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
        DROP COLUMN IF EXISTS updated_at
        """
        )
    )

    conn.execute(
        sa.text(
            f"""
        ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME}
        DROP COLUMN IF EXISTS raw_data
        """
        )
    )
