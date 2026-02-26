"""Create 客户计划月度快照 table for plan-level monthly snapshots.

Story 7.6-16: Fact Table Refactoring (双表粒度分离)
Task 2: Create Plan-level fact table

Purpose: Track monthly snapshots of customer-plan status with churn tracking
at plan granularity. Complements 客户业务月度快照 which
tracks at ProductLine granularity.

Granularity: Customer + Plan + Product Line
Source: Sprint Change Proposal 2026-02-09-fact-table-refactoring

Revision ID: 20260209_000013
Revises: 20260205_000012
Create Date: 2026-02-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260209_000013"
down_revision = "20260205_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create 客户计划月度快照 table with constraints and triggers."""
    conn = op.get_bind()

    # 1. Create main table
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS customer."客户计划月度快照" (
                -- Composite primary key (Granularity: Customer + Plan + ProductLine)
                snapshot_month DATE NOT NULL,
                company_id VARCHAR NOT NULL,
                plan_code VARCHAR NOT NULL,
                product_line_code VARCHAR(20) NOT NULL,

                -- Redundant fields (for query convenience)
                customer_name VARCHAR(200),
                plan_name VARCHAR(200),
                product_line_name VARCHAR(50) NOT NULL,

                -- Status flags (Plan-level)
                is_churned_this_year BOOLEAN DEFAULT FALSE,
                contract_status VARCHAR(50),

                -- Measure (Plan-level)
                aum_balance DECIMAL(20,2) DEFAULT 0,

                -- Audit fields
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                -- Primary key constraint
                PRIMARY KEY (snapshot_month, company_id, plan_code, product_line_code),

                -- Foreign key constraints
                CONSTRAINT fk_fct_plan_company FOREIGN KEY (company_id)
                    REFERENCES customer."客户明细"(company_id),
                CONSTRAINT fk_fct_plan_product_line FOREIGN KEY (product_line_code)
                    REFERENCES mapping."产品线"(产品线代码)
            );
            """
        )
    )

    # 2. Create indexes for query performance
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_fct_plan_snapshot_month
                ON customer."客户计划月度快照"(snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_company
                ON customer."客户计划月度快照"(company_id);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_plan_code
                ON customer."客户计划月度快照"(plan_code);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_product_line
                ON customer."客户计划月度快照"(product_line_code);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_month_brin
                ON customer."客户计划月度快照"
                USING BRIN (snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_churned
                ON customer."客户计划月度快照"(snapshot_month)
                WHERE is_churned_this_year = TRUE;

            CREATE INDEX IF NOT EXISTS idx_fct_plan_customer_name
                ON customer."客户计划月度快照"(customer_name);

            CREATE INDEX IF NOT EXISTS idx_fct_plan_plan_name
                ON customer."客户计划月度快照"(plan_name);
            """
        )
    )

    # 3. Create updated_at trigger function
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION
            customer.update_fct_plan_monthly_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 4. Attach updated_at trigger to table
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS update_fct_plan_monthly_timestamp
                ON customer."客户计划月度快照";

            CREATE TRIGGER update_fct_plan_monthly_timestamp
                BEFORE UPDATE ON customer."客户计划月度快照"
                FOR EACH ROW
                EXECUTE FUNCTION
                    customer.update_fct_plan_monthly_timestamp();
            """
        )
    )

    # 5. Create sync trigger for customer name changes
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_fct_plan_customer_name()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
                    UPDATE customer."客户计划月度快照"
                    SET customer_name = NEW.客户名称,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = NEW.company_id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
                ON customer."客户明细";

            CREATE TRIGGER trg_sync_fct_plan_customer_name
                AFTER UPDATE OF 客户名称 ON customer."客户明细"
                FOR EACH ROW
                EXECUTE FUNCTION customer.sync_fct_plan_customer_name();
            """
        )
    )

    # 6. Create sync trigger for plan name changes
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_fct_plan_plan_name()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.计划全称 IS DISTINCT FROM NEW.计划全称 THEN
                    UPDATE customer."客户计划月度快照"
                    SET plan_name = NEW.计划全称,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE plan_code = NEW.年金计划号;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_sync_fct_plan_plan_name
                ON mapping."年金计划";

            CREATE TRIGGER trg_sync_fct_plan_plan_name
                AFTER UPDATE OF 计划全称 ON mapping."年金计划"
                FOR EACH ROW
                EXECUTE FUNCTION customer.sync_fct_plan_plan_name();
            """
        )
    )


def downgrade() -> None:
    """Remove 客户计划月度快照 table and associated objects."""
    conn = op.get_bind()

    # Drop sync triggers first
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
                ON customer."客户明细";
            DROP TRIGGER IF EXISTS trg_sync_fct_plan_plan_name
                ON mapping."年金计划";
            """
        )
    )

    # Drop table (cascades to indexes and triggers)
    conn.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS customer."客户计划月度快照" CASCADE;
            """
        )
    )

    # Drop trigger functions
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS customer.update_fct_plan_monthly_timestamp();
            DROP FUNCTION IF EXISTS customer.sync_fct_plan_customer_name();
            DROP FUNCTION IF EXISTS customer.sync_fct_plan_plan_name();
            """
        )
    )
