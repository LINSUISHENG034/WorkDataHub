"""Add tracking fields to reference tables.

Story 6.2.2: Reference Table Schema Enhancement
Adds data source tracking fields to all 4 reference tables:
- _source: VARCHAR(20), NOT NULL, DEFAULT 'authoritative'
- _needs_review: BOOLEAN, NOT NULL, DEFAULT FALSE
- _derived_from_domain: VARCHAR(50), NULLABLE
- _derived_at: TIMESTAMP WITH TIME ZONE, NULLABLE

Target Tables (business schema):
- 年金计划 (Annuity Plan) - PK: 年金计划号
- 组合计划 (Portfolio Plan) - PK: 组合代码
- 产品线 (Product Line) - PK: 产品线代码
- 组织架构 (Organization) - PK: 组织代码

Performance Indexes:
- Index on _source column for each table
- Index on _needs_review column for each table

Revision ID: 20251212_120000
Revises: 20251208_000001
Create Date: 2025-12-12
"""

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "20251212_120000"
down_revision = "20251208_000001"
branch_labels = None
depends_on = None

DEFAULT_SCHEMA_NAME = "business"
FALLBACK_SCHEMA_NAME = "mapping"

# Target reference tables
TARGET_TABLES = ["年金计划", "组合计划", "产品线", "组织架构"]
TABLE_PRIMARY_KEYS = {
    "年金计划": "年金计划号",
    "组合计划": "组合代码",
    "产品线": "产品线代码",
    "组织架构": "机构代码",
}


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


def _resolve_reference_schema(conn) -> str:
    """
    Resolve the reference-table schema for this migration.

    Priority:
    1) Explicit env override via WDH_REFERENCE_SCHEMA
    2) DEFAULT_SCHEMA_NAME if target tables exist there
    3) FALLBACK_SCHEMA_NAME if target tables exist there
    """
    env_schema = os.getenv("WDH_REFERENCE_SCHEMA")
    if env_schema:
        return env_schema

    probe_table = TARGET_TABLES[0]
    if _table_exists(conn, probe_table, DEFAULT_SCHEMA_NAME):
        return DEFAULT_SCHEMA_NAME
    if _table_exists(conn, probe_table, FALLBACK_SCHEMA_NAME):
        return FALLBACK_SCHEMA_NAME

    # Fall back to the default (error messaging will be clearer downstream)
    return DEFAULT_SCHEMA_NAME


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
    """Add tracking columns to all 4 reference tables.

    Order: verify tables exist -> add columns -> create indexes
    All operations use IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()
    schema_name = _resolve_reference_schema(conn)

    # Ensure schema exists (fresh test DBs may be empty)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema_name or ""):
        raise ValueError(f"Invalid reference schema name: {schema_name!r}")
    conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

    # Tracking columns to add
    tracking_columns = [
        sa.Column(
            "_source",
            sa.String(20),
            nullable=False,
            server_default="authoritative",
            comment="Data source: authoritative or auto_derived",
        ),
        sa.Column(
            "_needs_review",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
            comment="Flag for records needing manual review",
        ),
        sa.Column(
            "_derived_from_domain",
            sa.String(50),
            nullable=True,
            comment="Source domain for auto-derived records",
        ),
        sa.Column(
            "_derived_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when record was auto-derived",
        ),
    ]

    for table_name in TARGET_TABLES:
        # === Step 1: Ensure table exists ===
        if not _table_exists(conn, table_name, schema_name):
            pk_col = TABLE_PRIMARY_KEYS.get(table_name)
            if not pk_col:
                raise ValueError(f"Missing primary key mapping for table: {table_name}")
            op.create_table(
                table_name,
                sa.Column(pk_col, sa.String(255), primary_key=True),
                schema=schema_name,
            )

        # === Step 2: Add tracking columns (AC1, AC2, AC3, AC5) ===
        for col in tracking_columns:
            if not _column_exists(conn, table_name, col.name, schema_name):
                op.add_column(table_name, col, schema=schema_name)

        # === Step 3: Create performance indexes (AC4, AC5) ===
        # Index on _source column
        source_idx = f"ix_{table_name}_source"
        if not _index_exists(conn, source_idx, schema_name):
            op.create_index(
                source_idx,
                table_name,
                ["_source"],
                schema=schema_name,
            )

        # Index on _needs_review column
        review_idx = f"ix_{table_name}_needs_review"
        if not _index_exists(conn, review_idx, schema_name):
            op.create_index(
                review_idx,
                table_name,
                ["_needs_review"],
                schema=schema_name,
            )


def downgrade() -> None:
    """Remove tracking columns from all 4 reference tables.

    Order: drop indexes -> drop columns (reverse of upgrade)
    Uses IF EXISTS for safety (AC6).

    All operations rely on Alembic helpers to avoid string interpolation of
    identifiers (AC10: no hand-built SQL). Existence checks guard idempotency.
    """
    conn = op.get_bind()
    schema_name = _resolve_reference_schema(conn)

    tracking_column_names = [
        "_source",
        "_needs_review",
        "_derived_from_domain",
        "_derived_at",
    ]

    for table_name in TARGET_TABLES:
        # === Step 1: Drop indexes first ===
        source_idx = f"ix_{table_name}_source"
        review_idx = f"ix_{table_name}_needs_review"

        if _index_exists(conn, source_idx, schema_name):
            op.drop_index(source_idx, table_name=table_name, schema=schema_name)
        if _index_exists(conn, review_idx, schema_name):
            op.drop_index(review_idx, table_name=table_name, schema=schema_name)

        # === Step 2: Drop columns ===
        for col_name in tracking_column_names:
            if _column_exists(conn, table_name, col_name, schema_name):
                op.drop_column(table_name, col_name, schema=schema_name)
