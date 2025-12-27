"""Add next_retry_at column to enrichment_requests table.

Story 6.7: Async Enrichment Queue (Deferred Resolution)
Adds exponential backoff support for retry logic:
- next_retry_at column for scheduling retries
- Composite index on (status, next_retry_at) for efficient dequeue queries

Revision ID: 20251207_000001
Revises: 20251206_000001
Create Date: 2025-12-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20251207_000001"
down_revision = "20251206_000001"
branch_labels = None
depends_on = None

SCHEMA_NAME = "enterprise"


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


def _index_exists(conn, index_name: str, schema: str) -> bool:
    """Check if an index exists in the given schema."""
    result = conn.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM pg_indexes
            WHERE schemaname = :schema AND indexname = :index
        )
        """
        ),
        {"schema": schema, "index": index_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Add next_retry_at column and index for exponential backoff support.

    AC2: Failed requests use exponential backoff delays before retry.
    """
    conn = op.get_bind()

    # Add next_retry_at column if not exists
    if not _column_exists(conn, "enrichment_requests", "next_retry_at", SCHEMA_NAME):
        op.add_column(
            "enrichment_requests",
            sa.Column(
                "next_retry_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
                comment="Next retry timestamp for exponential backoff",
            ),
            schema=SCHEMA_NAME,
        )

    # Create composite index for efficient dequeue queries
    # This index supports: WHERE status = 'pending' AND next_retry_at <= NOW()
    if not _index_exists(conn, "ix_enrichment_requests_status_next_retry", SCHEMA_NAME):
        op.create_index(
            "ix_enrichment_requests_status_next_retry",
            "enrichment_requests",
            ["status", "next_retry_at"],
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    """Remove next_retry_at column and index."""
    conn = op.get_bind()

    # Drop index first
    if _index_exists(conn, "ix_enrichment_requests_status_next_retry", SCHEMA_NAME):
        op.drop_index(
            "ix_enrichment_requests_status_next_retry",
            table_name="enrichment_requests",
            schema=SCHEMA_NAME,
        )

    # Drop column
    if _column_exists(conn, "enrichment_requests", "next_retry_at", SCHEMA_NAME):
        op.drop_column("enrichment_requests", "next_retry_at", schema=SCHEMA_NAME)
