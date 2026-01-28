"""Create fct_customer_business_monthly_status table for monthly snapshots.

Story 7.6-7: Monthly Snapshot Refresh (Post-ETL Hook)
Task 1: Create table with composite PK, status flags, and measures

Purpose: Track monthly snapshots of customer business status with AUM,
中标/流失 tracking for BI trend analysis.

Granularity: Customer + Product Line
Source: docs/specific/customer-mdm/customer-monthly-snapshot-specification.md

Revision ID: 20260121_000009
Revises: 20260118_000008
Create Date: 2026-01-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260121_000009"
down_revision = "20260118_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create fct_customer_business_monthly_status table with all constraints,
    indexes, and triggers."""
    conn = op.get_bind()

    # 1. Create main table
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS customer.fct_customer_business_monthly_status (
                -- Composite primary key (Granularity: Customer + Product Line)
                snapshot_month DATE NOT NULL,
                company_id VARCHAR NOT NULL,
                product_line_code VARCHAR(20) NOT NULL,

                -- Redundant field (for query convenience)
                product_line_name VARCHAR(50) NOT NULL,

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
                CONSTRAINT fk_snapshot_company FOREIGN KEY (company_id)
                    REFERENCES customer."年金客户"(company_id),
                CONSTRAINT fk_snapshot_product_line FOREIGN KEY (product_line_code)
                    REFERENCES mapping."产品线"(产品线代码)
            );
            """
        )
    )

    # 2. Create indexes for query performance
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshot_month
                ON customer.fct_customer_business_monthly_status(snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_snapshot_company
                ON customer.fct_customer_business_monthly_status(company_id);

            CREATE INDEX IF NOT EXISTS idx_snapshot_product_line
                ON customer.fct_customer_business_monthly_status(product_line_code);

            CREATE INDEX IF NOT EXISTS idx_snapshot_month_product
                ON customer.fct_customer_business_monthly_status(
                    snapshot_month, product_line_code
                );

            CREATE INDEX IF NOT EXISTS idx_snapshot_month_brin
                ON customer.fct_customer_business_monthly_status
                USING BRIN (snapshot_month);

            CREATE INDEX IF NOT EXISTS idx_snapshot_strategic
                ON customer.fct_customer_business_monthly_status(snapshot_month)
                WHERE is_strategic = TRUE;
            """
        )
    )

    # 3. Create updated_at trigger function
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION
            customer.update_fct_customer_monthly_status_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 4. Attach trigger to table
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS update_fct_customer_monthly_status_timestamp
                ON customer.fct_customer_business_monthly_status;

            CREATE TRIGGER update_fct_customer_monthly_status_timestamp
                BEFORE UPDATE ON customer.fct_customer_business_monthly_status
                FOR EACH ROW
                EXECUTE FUNCTION
                    customer.update_fct_customer_monthly_status_timestamp();
            """
        )
    )


def downgrade() -> None:
    """Remove fct_customer_business_monthly_status table and associated objects."""
    conn = op.get_bind()

    # Drop table (cascades to indexes and triggers)
    conn.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS customer.fct_customer_business_monthly_status CASCADE;
            """
        )
    )

    # Drop trigger function
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS
                customer.update_fct_customer_monthly_status_timestamp();
            """
        )
    )
