"""Create enrichment_index table for multi-type lookups.

Story 6.1.1: Enrichment Index Schema Enhancement
Creates the enrichment_index table for Layer 2 (Database Cache) multi-priority lookups:
- DB-P1: plan_code
- DB-P2: account_name
- DB-P3: account_number
- DB-P4: customer_name (normalized)
- DB-P5: plan_customer (plan_code|normalized_name)

Table Schema:
- lookup_key + lookup_type UNIQUE constraint
- CHECK constraints for lookup_type and source enums
- CHECK constraint for confidence range (0.00-1.00)
- Performance indexes for efficient lookups

Revision ID: 20251208_000001
Revises: 20251206_000001
Create Date: 2025-12-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision = "20251208_000001"
down_revision = "20251206_000001"
branch_labels = None
depends_on = None

SCHEMA_NAME = "enterprise"


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
    """Create enrichment_index table with indexes and constraints.

    Order: table -> indexes
    All operations use IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()

    # === Step 1: Create enrichment_index table (AC1, AC2) ===
    if not _table_exists(conn, "enrichment_index", SCHEMA_NAME):
        op.create_table(
            "enrichment_index",
            # Primary key
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key",
            ),
            # Lookup keys
            sa.Column(
                "lookup_key",
                sa.String(255),
                nullable=False,
                comment="Lookup key value (normalized for customer_name/plan_customer)",
            ),
            sa.Column(
                "lookup_type",
                sa.String(20),
                nullable=False,
                comment="Lookup type: plan_code, account_name, account_number, customer_name, plan_customer",
            ),
            # Mapping result
            sa.Column(
                "company_id",
                sa.String(100),
                nullable=False,
                comment="Resolved company_id (aligned with enterprise.base_info/company_id)",
            ),
            # Metadata
            sa.Column(
                "confidence",
                sa.Numeric(3, 2),
                nullable=False,
                server_default="1.00",
                comment="Confidence score (0.00-1.00)",
            ),
            sa.Column(
                "source",
                sa.String(50),
                nullable=False,
                comment="Data source: yaml, eqc_api, manual, backflow, domain_learning, legacy_migration",
            ),
            sa.Column(
                "source_domain",
                sa.String(50),
                nullable=True,
                comment="Learning source domain (e.g., annuity_performance)",
            ),
            sa.Column(
                "source_table",
                sa.String(100),
                nullable=True,
                comment="Learning source table (e.g., gold_annuity_performance)",
            ),
            # Statistics
            sa.Column(
                "hit_count",
                sa.Integer,
                nullable=False,
                server_default="0",
                comment="Number of cache hits",
            ),
            sa.Column(
                "last_hit_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="Timestamp of last cache hit",
            ),
            # Audit timestamps
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
                comment="Record creation timestamp",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
                comment="Record last update timestamp",
            ),
            # Constraints (AC2)
            sa.UniqueConstraint(
                "lookup_key", "lookup_type", name="uq_enrichment_index_key_type"
            ),
            sa.CheckConstraint(
                "lookup_type IN ('plan_code', 'account_name', 'account_number', 'customer_name', 'plan_customer')",
                name="chk_enrichment_index_lookup_type",
            ),
            sa.CheckConstraint(
                "source IN ('yaml', 'eqc_api', 'manual', 'backflow', 'domain_learning', 'legacy_migration')",
                name="chk_enrichment_index_source",
            ),
            sa.CheckConstraint(
                "confidence >= 0.00 AND confidence <= 1.00",
                name="chk_enrichment_index_confidence",
            ),
            schema=SCHEMA_NAME,
        )

    # === Step 2: Create indexes (AC3) ===
    # Index for efficient lookup by type and key (primary query pattern)
    if not _index_exists(conn, "ix_enrichment_index_type_key", SCHEMA_NAME):
        op.create_index(
            "ix_enrichment_index_type_key",
            "enrichment_index",
            ["lookup_type", "lookup_key"],
            schema=SCHEMA_NAME,
        )

    # Index for filtering by source
    if not _index_exists(conn, "ix_enrichment_index_source", SCHEMA_NAME):
        op.create_index(
            "ix_enrichment_index_source",
            "enrichment_index",
            ["source"],
            schema=SCHEMA_NAME,
        )

    # Index for domain-based queries (learning/migration tracking)
    if not _index_exists(conn, "ix_enrichment_index_source_domain", SCHEMA_NAME):
        op.create_index(
            "ix_enrichment_index_source_domain",
            "enrichment_index",
            ["source_domain"],
            schema=SCHEMA_NAME,
        )


def downgrade() -> None:
    """Drop enrichment_index table and indexes.

    Order: indexes -> table (reverse of upgrade)
    Uses IF EXISTS for safety.
    """
    conn = op.get_bind()

    # === Step 1: Drop indexes (with IF EXISTS for safety) ===
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.ix_enrichment_index_source_domain")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.ix_enrichment_index_source")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.ix_enrichment_index_type_key")
    )

    # === Step 2: Drop table (with IF EXISTS for safety) ===
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.enrichment_index"))
