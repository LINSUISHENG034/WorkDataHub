"""Create system.sync_state table for incremental sync state persistence.

Story 6.2-p4: Reference Sync Incremental State Persistence
Creates a table to store the last_synced_at timestamp for each sync job/table
combination, enabling incremental synchronization.

Table: system.sync_state
- job_name: VARCHAR(255), NOT NULL, part of composite PK
- table_name: VARCHAR(255), NOT NULL, part of composite PK
- last_synced_at: TIMESTAMP WITH TIME ZONE, NOT NULL
- updated_at: TIMESTAMP WITH TIME ZONE, auto-updated

Revision ID: 20251214_000001
Revises: 20251212_120000
Create Date: 2025-12-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20251214_000001"
down_revision = "20251212_120000"
branch_labels = None
depends_on = None

SCHEMA_NAME = "system"
TABLE_NAME = "sync_state"


def _schema_exists(conn, schema: str) -> bool:
    """Check if a schema exists."""
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.schemata
                WHERE schema_name = :schema
            )
            """
        ),
        {"schema": schema},
    )
    return result.scalar()


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
    """Create system.sync_state table for incremental sync state tracking.

    Operations:
    1. Create 'system' schema if not exists
    2. Create sync_state table with composite primary key
    3. Add index on updated_at for maintenance queries
    """
    conn = op.get_bind()

    # Step 1: Create schema if not exists
    if not _schema_exists(conn, SCHEMA_NAME):
        op.execute(sa.text(f"CREATE SCHEMA {SCHEMA_NAME}"))

    # Step 2: Create table if not exists
    if not _table_exists(conn, TABLE_NAME, SCHEMA_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("job_name", sa.String(255), nullable=False),
            sa.Column("table_name", sa.String(255), nullable=False),
            sa.Column(
                "last_synced_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="High-water mark timestamp for incremental sync",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
                comment="Record update timestamp",
            ),
            sa.PrimaryKeyConstraint("job_name", "table_name"),
            schema=SCHEMA_NAME,
            comment="Stores sync state for incremental reference data synchronization",
        )

        # Step 3: Create index on updated_at for maintenance queries
        op.create_index(
            f"ix_{TABLE_NAME}_updated_at",
            TABLE_NAME,
            ["updated_at"],
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    """Drop system.sync_state table.

    Note: Does not drop the 'system' schema as it may contain other tables.
    """
    conn = op.get_bind()

    if _table_exists(conn, TABLE_NAME, SCHEMA_NAME):
        op.drop_index(
            f"ix_{TABLE_NAME}_updated_at",
            table_name=TABLE_NAME,
            schema=SCHEMA_NAME,
        )
        op.drop_table(TABLE_NAME, schema=SCHEMA_NAME)
