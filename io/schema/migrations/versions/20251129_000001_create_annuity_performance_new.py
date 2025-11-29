"""Create annuity_performance_NEW table for Epic 4 MVP.

This migration creates the shadow table for annuity performance data,
supporting Epic 6 parallel execution for parity validation.

Story 4.6: Annuity Domain Configuration and Documentation
AC-4.6.2: Database Migration for annuity_performance_NEW Table

Table Schema:
- Composite PK: (reporting_month, plan_code, company_id)
- All columns from Story 4.4 Gold schema (AnnuityPerformanceOut model)
- Audit columns: pipeline_run_id, created_at, updated_at
- Indexes: idx_reporting_month, idx_company_id
- CHECK constraints: starting_assets >= 0, ending_assets >= 0

Revision ID: 20251129_000001
Revises: 20251113_000001
Create Date: 2025-11-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

revision = "20251129_000001"
down_revision = "20251113_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create annuity_performance_NEW table with all Gold schema columns.

    This table is a shadow table for Epic 6 parallel execution:
    - New pipeline writes to annuity_performance_NEW
    - Legacy system writes to annuity_performance (existing)
    - Epic 6 compares outputs for 100% parity validation
    - After parity proven, cutover: rename _NEW to production table
    """
    # Check if table already exists (idempotent migration)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "annuity_performance_new" in [t.lower() for t in inspector.get_table_names()]:
        return  # Table already exists, skip creation

    op.create_table(
        "annuity_performance_new",
        # === Primary Key Columns (Composite PK) ===
        # reporting_month: Report date (月度 in Chinese)
        sa.Column("reporting_month", sa.Date(), nullable=False, comment="Report date (月度)"),
        # plan_code: Plan code identifier (计划代码)
        sa.Column("plan_code", sa.String(255), nullable=False, comment="Plan code (计划代码)"),
        # company_id: Company identifier - generated during enrichment
        sa.Column("company_id", sa.String(50), nullable=False, comment="Company ID (公司标识)"),

        # === Business Type and Plan Information ===
        sa.Column("business_type", sa.String(255), nullable=True, comment="Business type (业务类型)"),
        sa.Column("plan_type", sa.String(255), nullable=True, comment="Plan type (计划类型)"),
        sa.Column("plan_name", sa.String(255), nullable=True, comment="Plan name (计划名称)"),

        # === Portfolio Information ===
        sa.Column("portfolio_type", sa.String(255), nullable=True, comment="Portfolio type (组合类型)"),
        sa.Column("portfolio_code", sa.String(255), nullable=True, comment="Portfolio code (组合代码)"),
        sa.Column("portfolio_name", sa.String(255), nullable=True, comment="Portfolio name (组合名称)"),

        # === Customer Information ===
        sa.Column("customer_name", sa.String(255), nullable=True, comment="Customer name (客户名称)"),

        # === Financial Metrics (with CHECK constraints for non-negative values) ===
        # starting_assets: Initial asset scale (期初资产规模)
        sa.Column(
            "starting_assets",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Initial asset scale (期初资产规模)"
        ),
        # ending_assets: Final asset scale (期末资产规模)
        sa.Column(
            "ending_assets",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Final asset scale (期末资产规模)"
        ),
        # contribution: Contribution amount (供款)
        sa.Column(
            "contribution",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Contribution (供款)"
        ),
        # loss_with_benefit: Loss including benefit payment (流失_含待遇支付)
        sa.Column(
            "loss_with_benefit",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Loss including benefit payment (流失_含待遇支付)"
        ),
        # loss: Loss amount (流失)
        sa.Column(
            "loss",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Loss (流失)"
        ),
        # benefit_payment: Benefit payment (待遇支付)
        sa.Column(
            "benefit_payment",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Benefit payment (待遇支付)"
        ),
        # investment_return: Investment return (投资收益) - can be negative
        sa.Column(
            "investment_return",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="Investment return (投资收益)"
        ),
        # annualized_return_rate: Current period return rate (当期收益率/年化收益率)
        sa.Column(
            "annualized_return_rate",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Annualized return rate (当期收益率)"
        ),

        # === Organizational Information ===
        sa.Column("institution_code", sa.String(255), nullable=True, comment="Institution code (机构代码)"),
        sa.Column("institution_name", sa.String(255), nullable=True, comment="Institution name (机构名称)"),
        sa.Column("product_line_code", sa.String(255), nullable=True, comment="Product line code (产品线代码)"),

        # === Pension Account Information ===
        sa.Column("pension_account_number", sa.String(50), nullable=True, comment="Pension account number (年金账户号)"),
        sa.Column("pension_account_name", sa.String(255), nullable=True, comment="Pension account name (年金账户名)"),

        # === Enterprise Group Information ===
        sa.Column("sub_enterprise_number", sa.String(50), nullable=True, comment="Sub-enterprise number (子企业号)"),
        sa.Column("sub_enterprise_name", sa.String(255), nullable=True, comment="Sub-enterprise name (子企业名称)"),
        sa.Column("group_customer_number", sa.String(50), nullable=True, comment="Group enterprise customer number (集团企业客户号)"),
        sa.Column("group_customer_name", sa.String(255), nullable=True, comment="Group enterprise customer name (集团企业客户名称)"),

        # === Audit Columns ===
        sa.Column("pipeline_run_id", sa.String(50), nullable=True, comment="Pipeline execution ID for traceability"),
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

        # === Constraints ===
        # Composite Primary Key
        sa.PrimaryKeyConstraint("reporting_month", "plan_code", "company_id", name="pk_annuity_performance_new"),
        # CHECK constraints for non-negative asset values (AC-4.6.2)
        sa.CheckConstraint("starting_assets >= 0", name="chk_starting_assets_non_negative"),
        sa.CheckConstraint("ending_assets >= 0", name="chk_ending_assets_non_negative"),
    )

    # Create indexes for common query patterns (AC-4.6.2)
    op.create_index(
        "idx_annuity_perf_new_reporting_month",
        "annuity_performance_new",
        ["reporting_month"],
        unique=False
    )
    op.create_index(
        "idx_annuity_perf_new_company_id",
        "annuity_performance_new",
        ["company_id"],
        unique=False
    )
    # Additional index for pipeline traceability
    op.create_index(
        "idx_annuity_perf_new_pipeline_run",
        "annuity_performance_new",
        ["pipeline_run_id"],
        unique=False
    )


def downgrade() -> None:
    """Drop annuity_performance_NEW table and all associated indexes."""
    # Drop indexes first
    op.drop_index("idx_annuity_perf_new_pipeline_run", table_name="annuity_performance_new")
    op.drop_index("idx_annuity_perf_new_company_id", table_name="annuity_performance_new")
    op.drop_index("idx_annuity_perf_new_reporting_month", table_name="annuity_performance_new")

    # Drop table (constraints are dropped automatically with table)
    op.drop_table("annuity_performance_new")
