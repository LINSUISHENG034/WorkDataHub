"""Initial infrastructure tables for clean migration chain.

Story 7.2-2: New Migration Structure
Phase 2: Create 001_initial_infrastructure.py with 17 infrastructure tables

This migration establishes the foundation tables for the WorkDataHub:
- Public schema: Pipeline execution tracking and data quality metrics
- Enterprise schema: Company information and enrichment infrastructure
- Mapping schema: Reference data tables (产品线, 组织架构, 计划层规模, 年金客户,
  产品明细, 利润指标)
- System schema: Incremental sync state tracking

All tables use idempotent IF NOT EXISTS pattern for safe re-execution.

Revision ID: 20251228_000001
Revises: None
Create Date: 2025-12-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

revision = "20251228_000001"
down_revision = None
branch_labels = None
depends_on = None


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


def upgrade() -> None:  # noqa: PLR0912, PLR0915
    """Create infrastructure tables across all schemas."""
    conn = op.get_bind()

    # ========================================================================
    # PUBLIC SCHEMA (2 tables)
    # ========================================================================

    # Create public schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS public"))

    # === 1. pipeline_executions ===
    if not _table_exists(conn, "pipeline_executions", "public"):
        op.create_table(
            "pipeline_executions",
            sa.Column("execution_id", sa.UUID(), nullable=False),
            sa.Column("pipeline_name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("input_file", sa.Text(), nullable=True),
            sa.Column("row_counts", sa.JSON(), nullable=True),
            sa.Column("error_details", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("execution_id", name="pipeline_executions_pkey"),
            comment="ETL pipeline execution tracking",
        )
        # Indexes
        op.create_index(
            "ix_pipeline_executions_pipeline_name",
            "pipeline_executions",
            ["pipeline_name"],
            schema="public",
        )
        op.create_index(
            "ix_pipeline_executions_started_at",
            "pipeline_executions",
            ["started_at"],
            schema="public",
        )

    # === 2. data_quality_metrics ===
    if not _table_exists(conn, "data_quality_metrics", "public"):
        op.create_table(
            "data_quality_metrics",
            sa.Column("metric_id", sa.UUID(), nullable=False),
            sa.Column("execution_id", sa.UUID(), nullable=False),
            sa.Column("pipeline_name", sa.String(255), nullable=False),
            sa.Column("metric_type", sa.String(100), nullable=False),
            sa.Column("metric_value", sa.Numeric(), nullable=True),
            sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("metric_id", name="data_quality_metrics_pkey"),
            sa.ForeignKeyConstraint(
                ["execution_id"],
                ["public.pipeline_executions.execution_id"],
                name="data_quality_metrics_execution_id_fkey",
                ondelete="CASCADE",
            ),
            comment="Data quality metrics for pipeline executions",
        )
        # Indexes
        op.create_index(
            "ix_data_quality_metrics_pipeline_name",
            "data_quality_metrics",
            ["pipeline_name"],
            schema="public",
        )
        op.create_index(
            "ix_data_quality_metrics_metric_type",
            "data_quality_metrics",
            ["metric_type"],
            schema="public",
        )

    # ========================================================================
    # ENTERPRISE SCHEMA (9 tables)
    # ========================================================================

    # Create enterprise schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS enterprise"))

    # === 3. base_info ===
    if not _table_exists(conn, "base_info", "enterprise"):
        op.create_table(
            "base_info",
            # Primary Key
            sa.Column(
                "company_id",
                sa.String(255),
                nullable=False,
                comment="Primary key: Company identifier",
            ),
            sa.Column(
                "search_key_word",
                sa.String(255),
                nullable=True,
                comment="Original search keyword",
            ),
            # Legacy archive_base_info alignment (41 columns total)
            sa.Column("name", sa.String(255), nullable=True, comment="Legacy field"),
            sa.Column("name_display", sa.String(255), nullable=True),
            sa.Column("symbol", sa.String(255), nullable=True),
            sa.Column("rank_score", sa.Float(), nullable=True),
            sa.Column("country", sa.String(255), nullable=True),
            sa.Column("company_en_name", sa.String(255), nullable=True),
            sa.Column("smdb_code", sa.String(255), nullable=True),
            sa.Column("is_hk", sa.Integer(), nullable=True),
            sa.Column("coname", sa.String(255), nullable=True),
            sa.Column("is_list", sa.Integer(), nullable=True),
            sa.Column("company_nature", sa.String(255), nullable=True),
            sa.Column("_score", sa.Float(), nullable=True),
            sa.Column("type", sa.String(255), nullable=True),
            sa.Column(
                "registeredStatus",
                sa.String(255),
                nullable=True,
                comment="Legacy (camelCase)",
            ),
            sa.Column("organization_code", sa.String(255), nullable=True),
            sa.Column("le_rep", sa.Text(), nullable=True),
            sa.Column("reg_cap", sa.Float(), nullable=True),
            sa.Column("is_pa_relatedparty", sa.Integer(), nullable=True),
            sa.Column("province", sa.String(255), nullable=True),
            sa.Column(
                "companyFullName",
                sa.String(255),
                nullable=True,
                comment="Canonical (quoted)",
            ),
            sa.Column(
                "est_date", sa.String(255), nullable=True, comment="Legacy (raw string)"
            ),
            sa.Column("company_short_name", sa.String(255), nullable=True),
            sa.Column("id", sa.String(255), nullable=True, comment="Legacy"),
            sa.Column("is_debt", sa.Integer(), nullable=True),
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
            sa.Column("cocode", sa.String(255), nullable=True),
            sa.Column("default_score", sa.Float(), nullable=True),
            sa.Column("company_former_name", sa.String(255), nullable=True),
            sa.Column("is_rank_list", sa.Integer(), nullable=True),
            sa.Column("trade_register_code", sa.String(255), nullable=True),
            sa.Column(
                "companyId", sa.String(255), nullable=True, comment="Legacy (camelCase)"
            ),
            sa.Column("is_normal", sa.Integer(), nullable=True),
            sa.Column(
                "company_full_name",
                sa.String(255),
                nullable=True,
                comment="Legacy (compatibility)",
            ),
            # JSONB fields for raw API responses
            sa.Column(
                "raw_data",
                sa.JSON(),
                nullable=True,
                comment="EQC getBasicInfo response",
            ),
            sa.Column(
                "raw_business_info",
                sa.JSON(),
                nullable=True,
                comment="EQC findDepart response",
            ),
            sa.Column(
                "raw_biz_label",
                sa.JSON(),
                nullable=True,
                comment="EQC findLabels response",
            ),
            sa.Column("api_fetched_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("company_id", name="base_info_pkey1"),
            schema="enterprise",
            comment="Primary company information table (41 columns)",
        )
        # Indexes
        op.create_index(
            "idx_base_info_unite_code", "base_info", ["unite_code"], schema="enterprise"
        )
        op.create_index(
            "idx_base_info_search_key",
            "base_info",
            ["search_key_word"],
            schema="enterprise",
        )
        op.create_index(
            "idx_base_info_api_fetched",
            "base_info",
            ["api_fetched_at"],
            schema="enterprise",
        )

    # === 4. business_info ===
    if not _table_exists(conn, "business_info", "enterprise"):
        op.create_table(
            "business_info",
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=False),
            sa.Column("company_id", sa.String(255), nullable=False),
            sa.Column(
                "registered_date", sa.Date(), nullable=True, comment="Normalized"
            ),
            sa.Column(
                "registered_capital",
                sa.Numeric(20, 2),
                nullable=True,
                comment="Normalized",
            ),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("colleagues_num", sa.Integer(), nullable=True, comment="员工数"),
            sa.Column("actual_capital", sa.Numeric(20, 2), nullable=True),
            sa.Column("registered_status", sa.String(100), nullable=True),
            sa.Column("legal_person_name", sa.String(255), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("codename", sa.String(100), nullable=True),
            sa.Column("company_name", sa.String(255), nullable=True),
            sa.Column("company_en_name", sa.Text(), nullable=True),
            sa.Column("currency", sa.String(50), nullable=True),
            sa.Column(
                "credit_code", sa.String(50), nullable=True, comment="统一社会信用代码"
            ),
            sa.Column("register_code", sa.String(50), nullable=True),
            sa.Column("organization_code", sa.String(50), nullable=True),
            sa.Column("company_type", sa.String(100), nullable=True),
            sa.Column("industry_name", sa.String(255), nullable=True),
            sa.Column("registration_organ_name", sa.String(255), nullable=True),
            sa.Column("start_end", sa.String(100), nullable=True),
            sa.Column("business_scope", sa.Text(), nullable=True),
            sa.Column("telephone", sa.String(100), nullable=True),
            sa.Column("email_address", sa.String(255), nullable=True),
            sa.Column("website", sa.String(500), nullable=True),
            sa.Column("company_former_name", sa.Text(), nullable=True),
            sa.Column("control_id", sa.String(100), nullable=True),
            sa.Column("control_name", sa.String(255), nullable=True),
            sa.Column("bene_id", sa.String(100), nullable=True),
            sa.Column("bene_name", sa.String(255), nullable=True),
            sa.Column("province", sa.String(100), nullable=True),
            sa.Column("department", sa.String(255), nullable=True),
            sa.Column("legal_person_id", sa.String(100), nullable=True),
            sa.Column("logo_url", sa.Text(), nullable=True),
            sa.Column("type_code", sa.String(50), nullable=True),
            sa.Column(
                "update_time", sa.Date(), nullable=True, comment="EQC update time"
            ),
            sa.Column("registered_capital_currency", sa.String(50), nullable=True),
            sa.Column("full_register_type_desc", sa.String(255), nullable=True),
            sa.Column("industry_code", sa.String(50), nullable=True),
            sa.Column(
                "_cleansing_status",
                sa.JSON(),
                nullable=True,
                comment="Cleansing tracking",
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="business_info_pkey1"),
            sa.ForeignKeyConstraint(
                ["company_id"],
                ["enterprise.base_info.company_id"],
                name="fk_business_info_company_id",
            ),
            schema="enterprise",
            comment="Company business details (43 columns)",
        )
        # Indexes
        op.create_index(
            "idx_business_info_company_id",
            "business_info",
            ["company_id"],
            schema="enterprise",
        )

    # === 5. biz_label ===
    if not _table_exists(conn, "biz_label", "enterprise"):
        op.create_table(
            "biz_label",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.String(255), nullable=False),
            sa.Column("type", sa.String(100), nullable=True, comment="Label type"),
            sa.Column("lv1_name", sa.String(255), nullable=True, comment="Level 1"),
            sa.Column("lv2_name", sa.String(255), nullable=True, comment="Level 2"),
            sa.Column("lv3_name", sa.String(255), nullable=True, comment="Level 3"),
            sa.Column("lv4_name", sa.String(255), nullable=True, comment="Level 4"),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="biz_label_pkey1"),
            sa.ForeignKeyConstraint(
                ["company_id"],
                ["enterprise.base_info.company_id"],
                name="fk_biz_label_company_id",
            ),
            schema="enterprise",
            comment="Company classification labels (9 columns)",
        )
        # Indexes
        op.create_index(
            "idx_biz_label_company_id", "biz_label", ["company_id"], schema="enterprise"
        )
        op.create_index(
            "idx_biz_label_hierarchy",
            "biz_label",
            ["company_id", "type", "lv1_name", "lv2_name"],
            schema="enterprise",
        )

    # === 6. enrichment_requests ===
    if not _table_exists(conn, "enrichment_requests", "enterprise"):
        op.create_table(
            "enrichment_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("raw_name", sa.String(255), nullable=False, comment="原始名称"),
            sa.Column(
                "normalized_name", sa.String(255), nullable=False, comment="规范化名称"
            ),
            sa.Column("temp_id", sa.String(50), nullable=True, comment="IN_xxx format"),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pending",
                comment="pending/processing/done/failed",
            ),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("resolved_company_id", sa.String(100), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="enrichment_requests_pkey"),
            schema="enterprise",
            comment="Async enrichment queue for company ID resolution",
        )
        # Indexes
        op.create_index(
            "idx_enrichment_requests_status",
            "enrichment_requests",
            ["status", "created_at"],
            schema="enterprise",
        )

    # === 7. enrichment_index ===
    if not _table_exists(conn, "enrichment_index", "enterprise"):
        op.create_table(
            "enrichment_index",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lookup_key", sa.String(255), nullable=False),
            sa.Column(
                "lookup_type",
                sa.String(20),
                nullable=False,
                comment="plan_code/account_name/account_number/customer_name/plan_customer",
            ),
            sa.Column("company_id", sa.String(100), nullable=False),
            sa.Column(
                "confidence",
                sa.Numeric(3, 2),
                nullable=False,
                server_default="1.00",
                comment="0.00-1.00",
            ),
            sa.Column(
                "source",
                sa.String(50),
                nullable=False,
                comment="yaml/eqc_api/manual/backflow/domain_learning/legacy_migration",
            ),
            sa.Column("source_domain", sa.String(50), nullable=True),
            sa.Column("source_table", sa.String(100), nullable=True),
            sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_hit_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="enrichment_index_pkey"),
            sa.UniqueConstraint(
                "lookup_key", "lookup_type", name="uq_enrichment_index_key_type"
            ),
            schema="enterprise",
            comment="Multi-priority company ID resolution cache (Layer 2)",
        )
        # Indexes
        op.create_index(
            "ix_enrichment_index_type_key",
            "enrichment_index",
            ["lookup_type", "lookup_key"],
            schema="enterprise",
        )
        op.create_index(
            "ix_enrichment_index_source",
            "enrichment_index",
            ["source"],
            schema="enterprise",
        )
        op.create_index(
            "ix_enrichment_index_source_domain",
            "enrichment_index",
            ["source_domain"],
            schema="enterprise",
        )

    # === 8. company_types_classification ===
    if not _table_exists(conn, "company_types_classification", "enterprise"):
        op.create_table(
            "company_types_classification",
            sa.Column("company_type", sa.String(), nullable=True),
            sa.Column("typeCode", sa.String(), nullable=False),
            sa.Column("公司类型/组织类型", sa.String(), nullable=True),
            sa.Column("分类", sa.String(), nullable=True),
            sa.Column("子分类", sa.String(), nullable=True),
            sa.Column("是否上市", sa.String(), nullable=True),
            sa.Column("法人类型", sa.String(), nullable=True),
            sa.Column("说明", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint(
                "typeCode", name="company_types_classification_pkey"
            ),
            comment="Static reference data: Company types classification "
            "(104 rows, structure only)",
        )

    # === 9. industrial_classification ===
    if not _table_exists(conn, "industrial_classification", "enterprise"):
        op.create_table(
            "industrial_classification",
            sa.Column("门类名称", sa.String(), nullable=True),
            sa.Column("大类名称", sa.String(), nullable=True),
            sa.Column("中类名称", sa.String(), nullable=True),
            sa.Column("类别名称", sa.String(), nullable=True),
            sa.Column("类别代码", sa.String(), nullable=False),
            sa.Column("门类代码", sa.String(), nullable=True),
            sa.Column("大类代码", sa.String(), nullable=True),
            sa.Column("中类顺序码", sa.String(), nullable=True),
            sa.Column("小类顺序码", sa.String(), nullable=True),
            sa.Column("说明", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("类别代码", name="industrial_classification_pkey"),
            schema="enterprise",
            comment="Static reference data: GB/T 4754 industry classification "
            "(1,183 rows, structure only)",
        )

    # === 10. validation_results ===
    if not _table_exists(conn, "validation_results", "enterprise"):
        op.create_table(
            "validation_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "validated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                server_default=func.now(),
            ),
            sa.Column("archive_company_id", sa.String(), nullable=False),
            sa.Column("search_key_word", sa.String(), nullable=True),
            sa.Column("archive_company_name", sa.String(), nullable=True),
            sa.Column("archive_unite_code", sa.String(), nullable=True),
            sa.Column("api_success", sa.Boolean(), nullable=True),
            sa.Column("api_company_id", sa.String(), nullable=True),
            sa.Column("api_company_name", sa.String(), nullable=True),
            sa.Column("api_unite_code", sa.String(), nullable=True),
            sa.Column("api_results_count", sa.Integer(), nullable=True),
            sa.Column("company_id_match", sa.Boolean(), nullable=True),
            sa.Column("company_name_match", sa.Boolean(), nullable=True),
            sa.Column("unite_code_match", sa.Boolean(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id", name="validation_results_pkey"),
            schema="enterprise",
            comment="Validation tracking for EQC API vs Archive data comparison",
        )

    # ========================================================================
    # MAPPING SCHEMA (6 tables: 3 seed tables + 3 reference tables)
    # ========================================================================

    # Create mapping schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS mapping"))

    # === 11. 产品线 (Product Lines - seed data) ===
    if not _table_exists(conn, "产品线", "mapping"):
        op.create_table(
            "产品线",
            sa.Column("产品线", sa.String(), nullable=True),
            sa.Column("产品类别", sa.String(), nullable=True),
            sa.Column("业务大类", sa.String(), nullable=True),
            sa.Column("产品线代码", sa.String(), nullable=False),
            sa.Column("NO_产品线", sa.Integer(), nullable=True),
            sa.Column("NO_产品类别", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("产品线代码", name="产品线_pkey"),
            schema="mapping",
            comment="Reference data: Product lines (12 rows, to be seeded)",
        )

    # === 12. 组织架构 (Organization Structure - seed data) ===
    if not _table_exists(conn, "组织架构", "mapping"):
        op.create_table(
            "组织架构",
            sa.Column("机构", sa.String(), nullable=True),
            sa.Column("年金中心", sa.String(), nullable=True),
            sa.Column("战区", sa.String(), nullable=True),
            sa.Column("机构代码", sa.String(), nullable=False),
            sa.Column("NO_机构", sa.Integer(), nullable=True),
            sa.Column("NO_年金中心", sa.Integer(), nullable=True),
            sa.Column("NO_区域", sa.Integer(), nullable=True),
            sa.Column("新架构", sa.String(), nullable=True),
            sa.Column("行政域", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("机构代码", name="组织架构_pkey"),
            schema="mapping",
            comment="Reference data: Organization structure (38 rows, to be seeded)",
        )

    # === 13. 计划层规模 (Plan Scale Levels - seed data) ===
    if not _table_exists(conn, "计划层规模", "mapping"):
        op.create_table(
            "计划层规模",
            sa.Column("规模分类代码", sa.String(), nullable=False),
            sa.Column("规模分类", sa.String(), nullable=True),
            sa.Column("NO_规模分类", sa.Integer(), nullable=True),
            sa.Column("规模大类", sa.String(), nullable=True),
            sa.Column("NO_规模大类", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("规模分类代码", name="计划层规模_pkey"),
            schema="mapping",
            comment="Reference data: Plan scale levels (7 rows, to be seeded)",
        )

    # === 14. 年金客户 (Annuity Customers - reference table, not a domain) ===
    if not _table_exists(conn, "年金客户", "mapping"):
        op.create_table(
            "年金客户",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.String(), nullable=False),
            sa.Column("客户名称", sa.String(), nullable=True),
            sa.Column("年金客户标签", sa.String(), nullable=True),
            sa.Column("年金客户类型", sa.String(), nullable=True),
            sa.Column("年金计划类型", sa.String(), nullable=True),
            sa.Column("关键年金计划", sa.String(), nullable=True),
            sa.Column("主拓机构代码", sa.String(), nullable=True),
            sa.Column("主拓机构", sa.String(), nullable=True),
            sa.Column("其他年金计划", sa.String(), nullable=True),
            sa.Column("客户简称", sa.String(), nullable=True),
            sa.Column("更新时间", sa.Date(), nullable=True),
            sa.Column("最新受托规模", sa.Float(), nullable=True),
            sa.Column("最新投管规模", sa.Float(), nullable=True),
            sa.Column("管理资格", sa.String(), nullable=True),
            sa.Column("规模区间", sa.String(), nullable=True),
            sa.Column("计划层规模", sa.Float(), nullable=True),
            sa.Column("年缴费规模", sa.Float(), nullable=True),
            sa.Column("外部受托规模", sa.Float(), nullable=True),
            sa.Column("上报受托规模", sa.Float(), nullable=True),
            sa.Column("上报投管规模", sa.Float(), nullable=True),
            sa.Column("关联机构数", sa.Integer(), nullable=True),
            sa.Column("其他开拓机构", sa.String(), nullable=True),
            sa.Column("计划状态", sa.String(), nullable=True),
            sa.Column("关联计划数", sa.Integer(), nullable=True),
            sa.Column("备注", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("company_id", name="年金客户_pkey"),
            schema="mapping",
            comment="Reference table: Annuity customers (10,997 rows, manual DDL)",
        )

    # === 15. 产品明细 (Product Details - seed data, not a domain) ===
    if not _table_exists(conn, "产品明细", "mapping"):
        op.create_table(
            "产品明细",
            sa.Column("产品ID", sa.String(), nullable=False),
            sa.Column("产品明细", sa.String(), nullable=True),
            sa.Column("父产品ID", sa.String(), nullable=True),
            sa.Column("NO_产品明细", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("产品ID", name="产品明细_pkey"),
            schema="mapping",
            comment="Reference data: Product details (18 rows, to be seeded, "
            "manual DDL)",
        )

    # === 16. 利润指标 (Profit Indicators - seed data, not a domain) ===
    if not _table_exists(conn, "利润指标", "mapping"):
        op.create_table(
            "利润指标",
            sa.Column("指标编码", sa.String(), nullable=False),
            sa.Column("指标分类", sa.String(), nullable=True),
            sa.Column("核算项", sa.String(), nullable=True),
            sa.Column("指标名称", sa.String(), nullable=True),
            sa.Column("指标大类", sa.String(), nullable=True),
            sa.Column("NO_指标名称", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("指标编码", name="利润指标_pkey"),
            schema="mapping",
            comment="Reference data: Profit indicators (12 rows, to be seeded, "
            "manual DDL)",
        )

    # ========================================================================
    # SYSTEM SCHEMA (1 table)
    # ========================================================================

    # Create system schema if not exists
    conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS system"))

    # === 17. sync_state ===
    if not _table_exists(conn, "sync_state", "system"):
        op.create_table(
            "sync_state",
            sa.Column(
                "job_name", sa.String(255), nullable=False, comment="ETL job identifier"
            ),
            sa.Column(
                "table_name",
                sa.String(255),
                nullable=False,
                comment="Target table name",
            ),
            sa.Column(
                "last_synced_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                comment="High-water mark",
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=func.now(),
            ),
            sa.PrimaryKeyConstraint("job_name", "table_name", name="sync_state_pkey"),
            schema="system",
            comment="Incremental sync state tracking for ETL jobs",
        )
        # Indexes
        op.create_index(
            "ix_sync_state_updated_at", "sync_state", ["updated_at"], schema="system"
        )


def downgrade() -> None:
    """Drop all infrastructure tables.

    This is a destructive operation. Data loss will occur.
    """
    conn = op.get_bind()

    # Drop tables in reverse order of creation
    # System schema
    if _table_exists(conn, "sync_state", "system"):
        op.drop_table("sync_state", schema="system")

    # Mapping schema
    for table in [
        "利润指标",
        "产品明细",
        "年金客户",
        "计划层规模",
        "组织架构",
        "产品线",
    ]:
        if _table_exists(conn, table, "mapping"):
            op.drop_table(table, schema="mapping")

    # Enterprise schema
    for table in [
        "validation_results",
        "industrial_classification",
        "company_types_classification",
        "enrichment_index",
        "enrichment_requests",
        "biz_label",
        "business_info",
        "base_info",
    ]:
        if _table_exists(conn, table, "enterprise"):
            op.drop_table(table, schema="enterprise")

    # Public schema
    for table in ["data_quality_metrics", "pipeline_executions"]:
        if _table_exists(conn, table, "public"):
            op.drop_table(table, schema="public")
