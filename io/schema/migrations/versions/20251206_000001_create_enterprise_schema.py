"""Create enterprise schema and enrichment tables for Epic 6.

Story 6.2-P7: Enterprise Schema Consolidation
Refactors the enterprise schema to align with Legacy archive tables:
- Removes company_master table (deprecated)
- Creates base_info table aligned with archive_base_info (37+ columns)
- Creates business_info table aligned with archive_business_info (43 columns)
- Creates biz_label table aligned with archive_biz_label (9 columns)
- Preserves existing company_mapping and enrichment_requests tables

Revision ID: 20251206_000001 (same revision - rewrites migration)
Revises: 20251129_000001
Create Date: 2025-12-06
Rewritten: 2025-12-15 (Story 6.2-P7)
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


def upgrade() -> None:  # noqa: PLR0912
    """Create enterprise schema with consolidated tables.

    Creates the complete enterprise schema aligned with Legacy archive tables:
    1. base_info: Primary company table (37+ legacy columns + new columns)
    2. business_info: Business details (43 columns, normalized types)
    3. biz_label: Company labels (9 columns)
    4. company_mapping: Existing mapping cache (preserved)
    5. enrichment_requests: Existing async queue (preserved)

    All operations use IF NOT EXISTS for idempotency.
    """
    conn = op.get_bind()

    # === Step 1: Create schema if not exists ===
    conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))

    # === Step 2: Create base_info table (aligned with archive_base_info) ===
    if not _table_exists(conn, "base_info", SCHEMA_NAME):
        op.create_table(
            "base_info",
            # Primary Key
            sa.Column(
                "company_id",
                sa.String(255),
                primary_key=True,
                comment="Primary key: Company identifier",
            ),
            sa.Column(
                "search_key_word",
                sa.String(255),
                nullable=True,
                comment="Original search keyword",
            ),
            # Legacy archive_base_info alignment (37 columns)
            sa.Column("name", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column(
                "name_display", sa.String(255), nullable=True, comment="Legacy field"
            ),
            sa.Column("symbol", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column(
                "rank_score",
                sa.Float(precision=53),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column("country", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column(
                "company_en_name", sa.String(255), nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "smdb_code", sa.String(255), nullable=True, comment="Legacy field"
            ),
            sa.Column("is_hk", sa.Integer, nullable=True, comment="Legacy field"),
            sa.Column("coname", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column("is_list", sa.Integer, nullable=True, comment="Legacy field"),
            sa.Column(
                "company_nature", sa.String(255), nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "_score", sa.Float(precision=53), nullable=True, comment="Legacy field"
            ),
            sa.Column("type", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column(
                "registeredStatus",
                sa.String(255),
                nullable=True,
                comment="Legacy field (compatibility-only)",
            ),
            sa.Column(
                "organization_code",
                sa.String(255),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column("le_rep", sa.Text, nullable=True, comment="Legacy field"),
            sa.Column(
                "reg_cap", sa.Float(precision=53), nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "is_pa_relatedparty", sa.Integer, nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "province", sa.String(255), nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "companyFullName",
                sa.String(255),
                nullable=True,
                comment="Canonical full name (quoted identifier)",
            ),
            sa.Column(
                "est_date",
                sa.String(255),
                nullable=True,
                comment="Legacy field (raw string)",
            ),
            sa.Column(
                "company_short_name",
                sa.String(255),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column("id", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column("is_debt", sa.Integer, nullable=True, comment="Legacy field"),
            sa.Column(
                "unite_code",
                sa.String(255),
                nullable=True,
                comment="Canonical credit code",
            ),
            sa.Column(
                "registered_status",
                sa.String(255),
                nullable=True,
                comment="Canonical status",
            ),
            sa.Column("cocode", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column(
                "default_score",
                sa.Float(precision=53),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column(
                "company_former_name",
                sa.String(255),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column(
                "is_rank_list", sa.Integer, nullable=True, comment="Legacy field"
            ),
            sa.Column(
                "trade_register_code",
                sa.String(255),
                nullable=True,
                comment="Legacy field",
            ),
            sa.Column(
                "companyId",
                sa.String(255),
                nullable=True,
                comment="Legacy field (compatibility-only)",
            ),
            sa.Column("is_normal", sa.Integer, nullable=True, comment="Legacy field"),
            sa.Column(
                "company_full_name",
                sa.String(255),
                nullable=True,
                comment="Legacy field (compatibility-only)",
            ),
            # Raw API response storage
            sa.Column(
                "raw_data",
                postgresql.JSONB,
                nullable=True,
                comment="Original search API response payload",
            ),
            sa.Column(
                "raw_business_info",
                postgresql.JSONB,
                nullable=True,
                comment="findDepart API response payload",
            ),
            sa.Column(
                "raw_biz_label",
                postgresql.JSONB,
                nullable=True,
                comment="findLabels API response payload",
            ),
            # Timestamps
            sa.Column(
                "api_fetched_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="When API data was fetched",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
                comment="Record last update timestamp",
            ),
            schema=SCHEMA_NAME,
        )

    # Create indexes on commonly queried fields (create even if table pre-existed)
    if _table_exists(conn, "base_info", SCHEMA_NAME):
        if not _index_exists(conn, "idx_base_info_unite_code", SCHEMA_NAME):
            op.create_index(
                "idx_base_info_unite_code",
                "base_info",
                ["unite_code"],
                schema=SCHEMA_NAME,
            )

        if not _index_exists(conn, "idx_base_info_search_key", SCHEMA_NAME):
            op.create_index(
                "idx_base_info_search_key",
                "base_info",
                ["search_key_word"],
                schema=SCHEMA_NAME,
            )

        if not _index_exists(conn, "idx_base_info_api_fetched", SCHEMA_NAME):
            op.create_index(
                "idx_base_info_api_fetched",
                "base_info",
                ["api_fetched_at"],
                schema=SCHEMA_NAME,
            )

    # === Step 3: Create business_info table (aligned with archive_business_info) ===
    if not _table_exists(conn, "business_info", SCHEMA_NAME):
        op.create_table(
            "business_info",
            # Primary Key (adjusted from MongoDB _id)
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key",
            ),
            # Foreign Key to base_info
            sa.Column(
                "company_id",
                sa.String(255),
                nullable=False,
                comment="Foreign key to base_info",
            ),
            # Normalized fields (require cleansing from raw strings)
            sa.Column(
                "registered_date",
                sa.Date,
                nullable=True,
                comment="Registration date (normalized from string)",
            ),
            sa.Column(
                "registered_capital",
                sa.Numeric(20, 2),
                nullable=True,
                comment="Registered capital (normalized from '万元')",
            ),
            sa.Column(
                "start_date",
                sa.Date,
                nullable=True,
                comment="Business period start date",
            ),
            sa.Column(
                "end_date",
                sa.Date,
                nullable=True,
                comment="Business period end date",
            ),
            sa.Column(
                "colleagues_num",
                sa.Integer,
                nullable=True,
                comment="Number of employees (fixed typo from collegues_num)",
            ),
            sa.Column(
                "actual_capital",
                sa.Numeric(20, 2),
                nullable=True,
                comment="Actual paid-in capital",
            ),
            # Retained fields (VARCHAR/TEXT, no type change)
            sa.Column("registered_status", sa.String(100), nullable=True),
            sa.Column("legal_person_name", sa.String(255), nullable=True),
            sa.Column("address", sa.Text, nullable=True),
            sa.Column("codename", sa.String(100), nullable=True),
            sa.Column("company_name", sa.String(255), nullable=True),
            sa.Column("company_en_name", sa.Text, nullable=True),
            sa.Column("currency", sa.String(50), nullable=True),
            sa.Column(
                "credit_code",
                sa.String(50),
                nullable=True,
                comment="Unified social credit code",
            ),
            sa.Column(
                "register_code",
                sa.String(50),
                nullable=True,
                comment="Registration number",
            ),
            sa.Column(
                "organization_code",
                sa.String(50),
                nullable=True,
                comment="Organization code",
            ),
            sa.Column("company_type", sa.String(100), nullable=True),
            sa.Column("industry_name", sa.String(255), nullable=True),
            sa.Column(
                "registration_organ_name",
                sa.String(255),
                nullable=True,
                comment="Registration authority",
            ),
            sa.Column(
                "start_end",
                sa.String(100),
                nullable=True,
                comment="Business period (combined)",
            ),
            sa.Column(
                "business_scope", sa.Text, nullable=True, comment="Business scope"
            ),
            sa.Column("telephone", sa.String(100), nullable=True),
            sa.Column("email_address", sa.String(255), nullable=True),
            sa.Column("website", sa.String(500), nullable=True),
            sa.Column(
                "company_former_name", sa.Text, nullable=True, comment="Former name"
            ),
            sa.Column(
                "control_id",
                sa.String(100),
                nullable=True,
                comment="Actual controller ID",
            ),
            sa.Column(
                "control_name",
                sa.String(255),
                nullable=True,
                comment="Actual controller name",
            ),
            sa.Column(
                "bene_id", sa.String(100), nullable=True, comment="Beneficiary ID"
            ),
            sa.Column(
                "bene_name", sa.String(255), nullable=True, comment="Beneficiary name"
            ),
            sa.Column("province", sa.String(100), nullable=True),
            sa.Column("department", sa.String(255), nullable=True),
            # snake_case converted from camelCase
            sa.Column(
                "legal_person_id",
                sa.String(100),
                nullable=True,
                comment="Legal person ID",
            ),
            sa.Column("logo_url", sa.Text, nullable=True),
            sa.Column("type_code", sa.String(50), nullable=True),
            sa.Column(
                "update_time", sa.Date, nullable=True, comment="EQC data update time"
            ),
            sa.Column(
                "registered_capital_currency",
                sa.String(50),
                nullable=True,
            ),
            sa.Column("full_register_type_desc", sa.String(255), nullable=True),
            sa.Column("industry_code", sa.String(50), nullable=True),
            # New fields
            sa.Column(
                "_cleansing_status",
                postgresql.JSONB,
                nullable=True,
                comment="Cleansing status tracking",
            ),
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
                onupdate=func.now(),
                nullable=False,
            ),
            # Foreign Key constraint
            sa.ForeignKeyConstraint(
                ["company_id"],
                [f"{SCHEMA_NAME}.base_info.company_id"],
                name="fk_business_info_company_id",
            ),
            schema=SCHEMA_NAME,
        )

    # Index for FK lookups (create even if table pre-existed)
    if _table_exists(conn, "business_info", SCHEMA_NAME):
        if not _index_exists(conn, "idx_business_info_company_id", SCHEMA_NAME):
            op.create_index(
                "idx_business_info_company_id",
                "business_info",
                ["company_id"],
                schema=SCHEMA_NAME,
            )

    # === Step 4: Create biz_label table (aligned with archive_biz_label) ===
    if not _table_exists(conn, "biz_label", SCHEMA_NAME):
        op.create_table(
            "biz_label",
            # Primary Key (adjusted from MongoDB _id)
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key",
            ),
            # Foreign Key to base_info (snake_case from companyId)
            sa.Column(
                "company_id",
                sa.String(255),
                nullable=False,
                comment="Foreign key to base_info",
            ),
            # Retained field
            sa.Column("type", sa.String(100), nullable=True, comment="Label type"),
            # snake_case converted from camelCase
            sa.Column(
                "lv1_name", sa.String(255), nullable=True, comment="Level 1 label"
            ),
            sa.Column(
                "lv2_name", sa.String(255), nullable=True, comment="Level 2 label"
            ),
            sa.Column(
                "lv3_name", sa.String(255), nullable=True, comment="Level 3 label"
            ),
            sa.Column(
                "lv4_name", sa.String(255), nullable=True, comment="Level 4 label"
            ),
            # New fields
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
                onupdate=func.now(),
                nullable=False,
            ),
            # Foreign Key constraint
            sa.ForeignKeyConstraint(
                ["company_id"],
                [f"{SCHEMA_NAME}.base_info.company_id"],
                name="fk_biz_label_company_id",
            ),
            schema=SCHEMA_NAME,
        )

    # Indexes for FK lookups and label queries (create even if table pre-existed)
    if _table_exists(conn, "biz_label", SCHEMA_NAME):
        if not _index_exists(conn, "idx_biz_label_company_id", SCHEMA_NAME):
            op.create_index(
                "idx_biz_label_company_id",
                "biz_label",
                ["company_id"],
                schema=SCHEMA_NAME,
            )

        if not _index_exists(conn, "idx_biz_label_hierarchy", SCHEMA_NAME):
            op.create_index(
                "idx_biz_label_hierarchy",
                "biz_label",
                ["company_id", "type", "lv1_name", "lv2_name"],
                schema=SCHEMA_NAME,
            )

    # NOTE: Step 5 (company_mapping) REMOVED - see enrichment_index
    # See Story 7.1-4: Remove company_mapping Legacy

    # === Step 6: Create enrichment_requests table (preserved from original) ===
    if not _table_exists(conn, "enrichment_requests", SCHEMA_NAME):
        op.create_table(
            "enrichment_requests",
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                comment="Auto-increment primary key",
            ),
            sa.Column(
                "raw_name",
                sa.String(255),
                nullable=False,
                comment="Original company name as received (原始名称)",
            ),
            sa.Column(
                "normalized_name",
                sa.String(255),
                nullable=False,
                comment="Normalized name for deduplication (规范化名称)",
            ),
            sa.Column(
                "temp_id",
                sa.String(50),
                nullable=True,
                comment="Assigned temporary ID (IN_xxx format)",
            ),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pending",
                comment="Queue status: pending/processing/done/failed",
            ),
            sa.Column(
                "attempts",
                sa.Integer,
                nullable=False,
                server_default="0",
                comment="Number of processing attempts",
            ),
            sa.Column(
                "last_error",
                sa.Text,
                nullable=True,
                comment="Last error message if failed",
            ),
            sa.Column(
                "resolved_company_id",
                sa.String(100),
                nullable=True,
                comment="Resolved company_id after successful enrichment",
            ),
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
                onupdate=func.now(),
                nullable=False,
                comment="Record last update timestamp",
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
    conn.execute(
        sa.text(
            f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_enrichment_requests_normalized
        ON {SCHEMA_NAME}.enrichment_requests (normalized_name)
        WHERE status IN ('pending', 'processing')
        """
        )
    )


def downgrade() -> None:
    """Drop enterprise schema tables.

    Order: indexes -> tables -> schema (reverse of upgrade)
    Only drops objects created by this migration.
    Uses IF EXISTS for safety.
    """
    conn = op.get_bind()

    schema_exists = conn.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.schemata
            WHERE schema_name = :schema
        )
        """
        ),
        {"schema": SCHEMA_NAME},
    ).scalar()
    if not schema_exists:
        return

    # === Step 1: Drop indexes (with IF EXISTS for safety) ===
    conn.execute(
        sa.text(
            f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_enrichment_requests_normalized"
        )
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_enrichment_requests_status")
    )
    # NOTE: idx_company_mapping_lookup removal skipped - table deprecated
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_biz_label_hierarchy"))
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_biz_label_company_id")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_business_info_company_id")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_base_info_api_fetched")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_base_info_search_key")
    )
    conn.execute(
        sa.text(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.idx_base_info_unite_code")
    )

    # === Step 2: Drop tables (with IF EXISTS for safety) ===
    # Note: Drop order matters due to FK constraints
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.enrichment_requests"))
    # NOTE: company_mapping drop skipped - table deprecated and no longer created
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.biz_label"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.business_info"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.base_info"))

    # === Step 3: Drop schema (only if empty) ===
    remaining_tables = conn.execute(
        sa.text(
            """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = :schema
        """
        ),
        {"schema": SCHEMA_NAME},
    ).scalar()

    if remaining_tables == 0:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME}"))
