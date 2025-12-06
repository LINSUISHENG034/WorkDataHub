"""Create enterprise schema and enrichment tables for Epic 6.

Story 6.1: Enterprise Schema Creation
Creates the persistence layer for company enrichment:
- enterprise schema (isolated from business tables)
- company_master: Company master data
- company_mapping: Unified mapping cache (Legacy 5-tier + EQC)
- enrichment_requests: Async backfill queue

Table Schema per Tech Spec:
- company_master: company_id PK, official_name, unified_credit_code UNIQUE,
  aliases TEXT[], source, timestamps
- company_mapping: alias_name + match_type UNIQUE, priority CHECK 1-5
- enrichment_requests: async queue with status tracking, partial unique index

Revision ID: 20251206_000001
Revises: 20251129_000001
Create Date: 2025-12-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

revision = "20251206_000001"
down_revision = "20251129_000001"
branch_labels = None
depends_on = None

SCHEMA_NAME = "enterprise"


def _table_exists(conn, table_name: str, schema: str) -> bool:
    """Check if a table exists in the given schema."""
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
        )
        """
    ), {"schema": schema, "table": table_name})
    return result.scalar()


def _index_exists(conn, index_name: str, schema: str) -> bool:
    """Check if an index exists in the given schema."""
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT FROM pg_indexes
            WHERE schemaname = :schema AND indexname = :index
        )
        """
    ), {"schema": schema, "index": index_name})
    return result.scalar()


def upgrade() -> None:
    """Create enterprise schema and enrichment tables.

    Order: schema -> tables -> indexes
    All operations use IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()

    # === Step 1: Create schema if not exists ===
    conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))

    # === Step 2: Create company_master table (AC2) ===
    if not _table_exists(conn, "company_master", SCHEMA_NAME):
        op.create_table(
            "company_master",
            sa.Column(
                "company_id",
                sa.String(100),
                primary_key=True,
                comment="Company identifier (公司标识)"
            ),
            sa.Column(
                "official_name",
                sa.String(255),
                nullable=False,
                comment="Official company name (官方名称)"
            ),
            sa.Column(
                "unified_credit_code",
                sa.String(50),
                unique=True,
                nullable=True,
                comment="Unified social credit code (统一社会信用代码)"
            ),
            sa.Column(
                "aliases",
                postgresql.ARRAY(sa.Text),
                nullable=True,
                comment="Known aliases for this company (别名列表)"
            ),
            sa.Column(
                "source",
                sa.String(50),
                nullable=False,
                server_default="internal",
                comment="Data source: internal/eqc"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
                comment="Record creation timestamp"
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
                comment="Record last update timestamp"
            ),
            schema=SCHEMA_NAME,
        )

    # === Step 3: Create company_mapping table (AC3) ===
    if not _table_exists(conn, "company_mapping", SCHEMA_NAME):
        op.create_table(
            "company_mapping",
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key"
            ),
            sa.Column(
                "alias_name",
                sa.String(255),
                nullable=False,
                comment="Alias or lookup key (别名/查询键)"
            ),
            sa.Column(
                "canonical_id",
                sa.String(100),
                nullable=False,
                comment="Resolved company_id (规范化公司ID)"
            ),
            sa.Column(
                "match_type",
                sa.String(20),
                nullable=False,
                comment="Mapping type: plan/account/hardcode/name/account_name"
            ),
            sa.Column(
                "priority",
                sa.Integer,
                nullable=False,
                comment="Resolution priority 1-5 (lower = higher priority)"
            ),
            sa.Column(
                "source",
                sa.String(50),
                nullable=False,
                server_default="internal",
                comment="Data source: internal/eqc/pipeline_backflow"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
                comment="Record creation timestamp"
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
                comment="Record last update timestamp"
            ),
            # Constraints
            sa.UniqueConstraint(
                "alias_name", "match_type", name="uq_company_mapping_alias_type"
            ),
            sa.CheckConstraint(
                "priority >= 1 AND priority <= 5",
                name="chk_company_mapping_priority"
            ),
            sa.CheckConstraint(
                "match_type IN ('plan','account','hardcode','name','account_name')",
                name="chk_company_mapping_match_type"
            ),
            schema=SCHEMA_NAME,
        )

    # Index for efficient lookup by alias_name and priority
    if not _index_exists(conn, "idx_company_mapping_lookup", SCHEMA_NAME):
        op.create_index(
            "idx_company_mapping_lookup",
            "company_mapping",
            ["alias_name", "priority"],
            schema=SCHEMA_NAME,
        )

    # === Step 4: Create enrichment_requests table (AC4) ===
    if not _table_exists(conn, "enrichment_requests", SCHEMA_NAME):
        op.create_table(
            "enrichment_requests",
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key"
            ),
            sa.Column(
                "raw_name",
                sa.String(255),
                nullable=False,
                comment="Original company name as received (原始名称)"
            ),
            sa.Column(
                "normalized_name",
                sa.String(255),
                nullable=False,
                comment="Normalized name for deduplication (规范化名称)"
            ),
            sa.Column(
                "temp_id",
                sa.String(50),
                nullable=True,
                comment="Assigned temporary ID (IN_xxx format)"
            ),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pending",
                comment="Queue status: pending/processing/done/failed"
            ),
            sa.Column(
                "attempts",
                sa.Integer,
                nullable=False,
                server_default="0",
                comment="Number of processing attempts"
            ),
            sa.Column(
                "last_error",
                sa.Text,
                nullable=True,
                comment="Last error message if failed"
            ),
            sa.Column(
                "resolved_company_id",
                sa.String(100),
                nullable=True,
                comment="Resolved company_id after successful enrichment"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
                comment="Record creation timestamp"
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
                comment="Record last update timestamp"
            ),
            schema=SCHEMA_NAME,
        )

    # Index for queue processing (status + created_at for FIFO)
    if not _index_exists(conn, "idx_enrichment_requests_status", SCHEMA_NAME):
        op.create_index(
            "idx_enrichment_requests_status",
            "enrichment_requests",
            ["status", "created_at"],
            schema=SCHEMA_NAME,
        )

    # Partial unique index: prevent duplicate pending/processing requests
    # This uses raw SQL because Alembic doesn't directly support partial indexes
    # IF NOT EXISTS is used for idempotency
    conn.execute(sa.text(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_enrichment_requests_normalized
        ON {SCHEMA_NAME}.enrichment_requests (normalized_name)
        WHERE status IN ('pending', 'processing')
        """
    ))


def downgrade() -> None:
    """Drop enrichment tables and schema.

    Order: indexes -> tables -> schema (reverse of upgrade)
    Only drops objects created by this migration.
    Uses IF EXISTS for safety.
    """
    conn = op.get_bind()

    # === Step 1: Drop indexes (with IF EXISTS for safety) ===
    conn.execute(sa.text(
        f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_enrichment_requests_normalized"
    ))
    conn.execute(sa.text(
        f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_enrichment_requests_status"
    ))
    conn.execute(sa.text(
        f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_company_mapping_lookup"
    ))

    # === Step 2: Drop tables (with IF EXISTS for safety) ===
    conn.execute(sa.text(
        f"DROP TABLE IF EXISTS {SCHEMA_NAME}.enrichment_requests"
    ))
    conn.execute(sa.text(
        f"DROP TABLE IF EXISTS {SCHEMA_NAME}.company_mapping"
    ))
    conn.execute(sa.text(
        f"DROP TABLE IF EXISTS {SCHEMA_NAME}.company_master"
    ))

    # === Step 3: Drop schema (only if empty) ===
    remaining_tables = conn.execute(sa.text(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = :schema
        """
    ), {"schema": SCHEMA_NAME}).scalar()

    if remaining_tables == 0:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME}"))
