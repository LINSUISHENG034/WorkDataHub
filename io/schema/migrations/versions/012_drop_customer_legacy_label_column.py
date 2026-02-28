"""Drop deprecated 年金客户标签 column from customer.客户明细.

Story 7.6-20: Consolidate customer labels into tags JSONB only.

This migration:
1. Merges any residual 年金客户标签 values into tags JSONB (idempotent)
2. Drops deprecated 年金客户标签 column

Revision ID: 20260228_000012
Revises: 20260209_000011
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260228_000012"
down_revision = "20260209_000011"
branch_labels = None
depends_on = None


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    """Check whether a column exists."""
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                  AND column_name = :column
            )
            """
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return bool(result.scalar())


def upgrade() -> None:
    """Merge legacy labels into tags and drop deprecated column."""
    conn = op.get_bind()

    if not _column_exists(conn, "customer", "客户明细", "年金客户标签"):
        return

    # Merge deprecated label into tags if needed before dropping the column.
    conn.execute(
        sa.text(
            """
            WITH normalized AS (
                SELECT
                    company_id,
                    NULLIF(BTRIM("年金客户标签"), '') AS normalized_tag
                FROM customer."客户明细"
            )
            UPDATE customer."客户明细" AS c
            SET tags = CASE
                WHEN n.normalized_tag IS NULL THEN COALESCE(c.tags, '[]'::jsonb)
                WHEN COALESCE(c.tags, '[]'::jsonb) @> to_jsonb(ARRAY[n.normalized_tag])
                    THEN COALESCE(c.tags, '[]'::jsonb)
                ELSE COALESCE(c.tags, '[]'::jsonb)
                     || jsonb_build_array(n.normalized_tag)
            END
            FROM normalized AS n
            WHERE c.company_id = n.company_id
              AND (
                  n.normalized_tag IS NOT NULL
                  OR c.tags IS NULL
              )
            """
        )
    )

    # mapping."客户明细" is a SELECT * compatibility view and depends on this column.
    conn.execute(sa.text('DROP VIEW IF EXISTS mapping."客户明细"'))
    conn.execute(
        sa.text('ALTER TABLE customer."客户明细" DROP COLUMN IF EXISTS "年金客户标签"')
    )
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW mapping."客户明细" AS
            SELECT * FROM customer."客户明细"
            """
        )
    )


def downgrade() -> None:
    """Recreate deprecated 年金客户标签 column from tags best effort."""
    conn = op.get_bind()

    # Drop compatibility view before changing column layout.
    conn.execute(sa.text('DROP VIEW IF EXISTS mapping."客户明细"'))

    if not _column_exists(conn, "customer", "客户明细", "年金客户标签"):
        conn.execute(
            sa.text('ALTER TABLE customer."客户明细" ADD COLUMN "年金客户标签" VARCHAR')
        )

    # Restore a best-effort legacy value from tags (first *新建 tag).
    conn.execute(
        sa.text(
            """
            WITH extracted AS (
                SELECT
                    c.company_id,
                    (
                        SELECT e.tag
                        FROM jsonb_array_elements_text(COALESCE(c.tags, '[]'::jsonb))
                             WITH ORDINALITY AS e(tag, ord)
                        WHERE e.tag ~ '^[0-9]{4}新建$'
                        ORDER BY e.ord
                        LIMIT 1
                    ) AS legacy_tag
                FROM customer."客户明细" c
            )
            UPDATE customer."客户明细" c
            SET "年金客户标签" = extracted.legacy_tag
            FROM extracted
            WHERE c.company_id = extracted.company_id
              AND extracted.legacy_tag IS NOT NULL
            """
        )
    )

    conn.execute(
        sa.text(
            """
            COMMENT ON COLUMN customer."客户明细"."年金客户标签"
            IS 'DEPRECATED: Use tags JSONB column instead'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW mapping."客户明细" AS
            SELECT * FROM customer."客户明细"
            """
        )
    )
