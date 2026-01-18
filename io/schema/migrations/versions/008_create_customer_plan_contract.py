"""Create customer_plan_contract table with SCD Type 2 support.

Story 7.6-6: Contract Status Sync (Post-ETL Hook)
Task 1: Create table with business key, annual/monthly status fields, and time dimension

Purpose: Track customer-plan contract relationships with SCD Type 2 history for
status changes. Supports BI queries for current and historical contract status.

Source specification: docs/specific/customer-mdm/customer-plan-contract-specification.md

Revision ID: 20260118_000008
Revises: 20260115_000007
Create Date: 2026-01-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260118_000008"
down_revision = "20260115_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create customer_plan_contract table with all constraints, indexes,
    and triggers."""
    conn = op.get_bind()

    # 1. Create main table
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS customer.customer_plan_contract (
                -- Primary key
                contract_id SERIAL PRIMARY KEY,

                -- Business dimension (compound business key)
                company_id VARCHAR NOT NULL,
                plan_code VARCHAR NOT NULL,
                product_line_code VARCHAR(20) NOT NULL,

                -- Redundant fields (for query convenience)
                product_line_name VARCHAR(50) NOT NULL,

                -- Annual initialization status (updated every January)
                is_strategic BOOLEAN DEFAULT FALSE,
                is_existing BOOLEAN DEFAULT FALSE,
                status_year INTEGER NOT NULL,

                -- Monthly update status
                contract_status VARCHAR(20) NOT NULL,

                -- SCD Type 2 time dimension (end of month)
                valid_from DATE NOT NULL,
                valid_to DATE DEFAULT '9999-12-31',

                -- Audit fields
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                -- Foreign key constraints
                CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
                    REFERENCES customer."年金客户"(company_id),
                CONSTRAINT fk_contract_product_line FOREIGN KEY (product_line_code)
                    REFERENCES mapping."产品线"(产品线代码),

                -- Compound unique constraint (business key + time)
                CONSTRAINT uq_active_contract UNIQUE (
                    company_id, plan_code, product_line_code, valid_to
                )
            );
            """
        )
    )

    # 2. Create indexes for query performance
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_contract_company
                ON customer.customer_plan_contract(company_id);

            CREATE INDEX IF NOT EXISTS idx_contract_plan
                ON customer.customer_plan_contract(plan_code);

            CREATE INDEX IF NOT EXISTS idx_contract_product_line
                ON customer.customer_plan_contract(product_line_code);

            CREATE INDEX IF NOT EXISTS idx_contract_strategic
                ON customer.customer_plan_contract(is_strategic)
                WHERE is_strategic = TRUE;

            CREATE INDEX IF NOT EXISTS idx_contract_status_year
                ON customer.customer_plan_contract(status_year);

            CREATE INDEX IF NOT EXISTS idx_active_contracts
                ON customer.customer_plan_contract(
                    company_id, plan_code, product_line_code
                ) WHERE valid_to = '9999-12-31';

            CREATE INDEX IF NOT EXISTS idx_contract_valid_from_brin
                ON customer.customer_plan_contract USING BRIN (valid_from);
            """
        )
    )

    # 3. Create updated_at trigger function
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION
            customer.update_customer_plan_contract_timestamp()
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
            DROP TRIGGER IF EXISTS update_customer_plan_contract_timestamp
                ON customer.customer_plan_contract;

            CREATE TRIGGER update_customer_plan_contract_timestamp
                BEFORE UPDATE ON customer.customer_plan_contract
                FOR EACH ROW
                EXECUTE FUNCTION customer.update_customer_plan_contract_timestamp();
            """
        )
    )


def downgrade() -> None:
    """Remove customer_plan_contract table and all associated objects."""
    conn = op.get_bind()

    # Drop table (cascades to indexes and triggers)
    conn.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS customer.customer_plan_contract CASCADE;
            """
        )
    )

    # Drop trigger function
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS customer.update_customer_plan_contract_timestamp();
            """
        )
    )
