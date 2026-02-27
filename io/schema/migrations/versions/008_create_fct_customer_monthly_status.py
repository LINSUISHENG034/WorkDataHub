"""Create 客户业务月度快照 table for monthly snapshots.

Story 7.6-7: Monthly Snapshot Refresh (Post-ETL Hook)
Story 7.6-16: Fact Table Refactoring (双表粒度分离)

Task 1: Create table with composite PK, status flags, and measures
- Renamed from fct_customer_business_monthly_status to 客户业务月度快照
- Added customer_name field with sync trigger (merged from 7.6-13)

Purpose: Track monthly snapshots of customer business status with AUM,
中标/流失 tracking for BI trend analysis.

Granularity: Customer + Product Line
Source: docs/specific/customer-mdm/customer-monthly-snapshot-specification.md

Revision ID: 20260121_000008
Revises: 20260118_000007
Create Date: 2026-01-21
Updated: 2026-02-09 (Story 7.6-16)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260121_000008"
down_revision = "20260118_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create 客户业务月度快照 table with all constraints,
    indexes, and triggers."""
    conn = op.get_bind()

    # 1. Create main table (renamed from fct_customer_business_monthly_status)
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS customer."客户业务月度快照" (
                -- Composite primary key (Granularity: Customer + Product Line)
                snapshot_month DATE NOT NULL,
                company_id VARCHAR NOT NULL,
                product_line_code VARCHAR(20) NOT NULL,

                -- Redundant fields (for query convenience)
                product_line_name VARCHAR(50) NOT NULL,
                customer_name VARCHAR(200),

                -- Status flags (Historical snapshots)
                is_strategic BOOLEAN DEFAULT FALSE,
                is_existing BOOLEAN DEFAULT FALSE,
                is_new BOOLEAN DEFAULT FALSE,
                is_winning_this_year BOOLEAN DEFAULT FALSE,
                is_churned_this_year BOOLEAN DEFAULT FALSE,

                -- Measure
                aum_balance DECIMAL(20,2) DEFAULT 0,
                plan_count INTEGER DEFAULT 0,

                -- Audit fields
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                -- Primary key constraint
                PRIMARY KEY (snapshot_month, company_id, product_line_code),

                -- Foreign key constraints
                CONSTRAINT fk_fct_pl_company FOREIGN KEY (company_id)
                    REFERENCES customer."客户明细"(company_id),
                CONSTRAINT fk_fct_pl_product_line FOREIGN KEY (product_line_code)
                    REFERENCES mapping."产品线"(产品线代码)
            );
            """
        )
    )

    # 2. Create indexes for query performance (renamed with idx_fct_pl_ prefix)
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_fct_pl_snapshot_month
                ON customer."客户业务月度快照"(snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_fct_pl_company
                ON customer."客户业务月度快照"(company_id);

            CREATE INDEX IF NOT EXISTS idx_fct_pl_product_line
                ON customer."客户业务月度快照"(product_line_code);

            CREATE INDEX IF NOT EXISTS idx_fct_pl_month_product
                ON customer."客户业务月度快照"(
                    snapshot_month, product_line_code
                );

            CREATE INDEX IF NOT EXISTS idx_fct_pl_month_brin
                ON customer."客户业务月度快照"
                USING BRIN (snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_fct_pl_strategic
                ON customer."客户业务月度快照"(snapshot_month)
                WHERE is_strategic = TRUE;

            CREATE INDEX IF NOT EXISTS idx_fct_pl_customer_name
                ON customer."客户业务月度快照"(customer_name);
            """
        )
    )

    # 3. Create updated_at trigger function (renamed)
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION
            customer.update_fct_pl_monthly_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 4. Attach updated_at trigger to table (renamed)
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS update_fct_pl_monthly_timestamp
                ON customer."客户业务月度快照";

            CREATE TRIGGER update_fct_pl_monthly_timestamp
                BEFORE UPDATE ON customer."客户业务月度快照"
                FOR EACH ROW
                EXECUTE FUNCTION
                    customer.update_fct_pl_monthly_timestamp();
            """
        )
    )

    # 5. Create sync trigger for customer name changes (Story 7.6-13 merged)
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_fct_pl_customer_name()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
                    UPDATE customer."客户业务月度快照"
                    SET customer_name = NEW.客户名称,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = NEW.company_id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
                ON customer."客户明细";

            CREATE TRIGGER trg_sync_fct_pl_customer_name
                AFTER UPDATE OF 客户名称 ON customer."客户明细"
                FOR EACH ROW
                EXECUTE FUNCTION customer.sync_fct_pl_customer_name();
            """
        )
    )


def downgrade() -> None:
    """Remove 客户业务月度快照 table and associated objects."""
    conn = op.get_bind()

    # Drop sync trigger first
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
                ON customer."客户明细";
            """
        )
    )

    # Drop table (cascades to indexes and triggers)
    conn.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS customer."客户业务月度快照" CASCADE;
            """
        )
    )

    # Drop trigger functions
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS
                customer.update_fct_pl_monthly_timestamp();
            DROP FUNCTION IF EXISTS
                customer.sync_fct_pl_customer_name();
            """
        )
    )
