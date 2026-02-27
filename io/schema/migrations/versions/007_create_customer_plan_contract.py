"""Create 客户年金计划 table with SCD Type 2 support.

Story 7.6-6: Contract Status Sync (Post-ETL Hook)
Task 1: Create table with business key, annual/monthly status fields, and time dimension

Purpose: Track customer-plan contract relationships with SCD Type 2 history for
status changes. Supports BI queries for current and historical contract status.

Source specification: docs/specific/customer-mdm/customer-plan-contract-specification.md

Revision ID: 20260118_000007
Revises: 20260115_000006
Create Date: 2026-01-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260118_000007"
down_revision = "20260115_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create 客户年金计划 table with all constraints, indexes,
    and triggers."""
    conn = op.get_bind()

    # 1. Create main table
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS customer."客户年金计划" (
                -- Primary key
                contract_id SERIAL PRIMARY KEY,

                -- Business dimension (compound business key)
                company_id VARCHAR NOT NULL,
                plan_code VARCHAR NOT NULL,
                product_line_code VARCHAR(20) NOT NULL,

                -- Redundant fields (for query convenience)
                product_line_name VARCHAR(50) NOT NULL,
                customer_name VARCHAR(200),
                plan_name VARCHAR(200),

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
                    REFERENCES customer."客户明细"(company_id),
                CONSTRAINT fk_contract_product_line FOREIGN KEY (product_line_code)
                    REFERENCES mapping."产品线"(产品线代码),

                -- Compound unique constraint (business key + time)
                CONSTRAINT uq_contract_version UNIQUE (
                    company_id, plan_code, product_line_code, valid_from
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
                ON customer."客户年金计划"(company_id);

            CREATE INDEX IF NOT EXISTS idx_contract_plan
                ON customer."客户年金计划"(plan_code);

            CREATE INDEX IF NOT EXISTS idx_contract_product_line
                ON customer."客户年金计划"(product_line_code);

            CREATE INDEX IF NOT EXISTS idx_contract_strategic
                ON customer."客户年金计划"(is_strategic)
                WHERE is_strategic = TRUE;

            CREATE INDEX IF NOT EXISTS idx_contract_status_year
                ON customer."客户年金计划"(status_year);

            CREATE INDEX IF NOT EXISTS idx_active_contracts
                ON customer."客户年金计划"(
                    company_id, plan_code, product_line_code
                ) WHERE valid_to = '9999-12-31';

            CREATE INDEX IF NOT EXISTS idx_contract_valid_from_brin
                ON customer."客户年金计划" USING BRIN (valid_from);

            CREATE INDEX IF NOT EXISTS idx_contract_customer_name
                ON customer."客户年金计划"(customer_name);

            CREATE INDEX IF NOT EXISTS idx_contract_plan_name
                ON customer."客户年金计划"(plan_name);
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
                ON customer."客户年金计划";

            CREATE TRIGGER update_customer_plan_contract_timestamp
                BEFORE UPDATE ON customer."客户年金计划"
                FOR EACH ROW
                EXECUTE FUNCTION customer.update_customer_plan_contract_timestamp();
            """
        )
    )

    # 5. Create sync trigger for customer name changes
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_contract_customer_name()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
                    UPDATE customer."客户年金计划"
                    SET customer_name = NEW.客户名称,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = NEW.company_id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_sync_contract_customer_name
                ON customer."客户明细";

            CREATE TRIGGER trg_sync_contract_customer_name
                AFTER UPDATE OF 客户名称 ON customer."客户明细"
                FOR EACH ROW
                EXECUTE FUNCTION customer.sync_contract_customer_name();
            """
        )
    )

    # 6. Create sync trigger for plan name changes
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_contract_plan_name()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.计划全称 IS DISTINCT FROM NEW.计划全称 THEN
                    UPDATE customer."客户年金计划"
                    SET plan_name = NEW.计划全称,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE plan_code = NEW.年金计划号;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_sync_contract_plan_name
                ON mapping."年金计划";

            CREATE TRIGGER trg_sync_contract_plan_name
                AFTER UPDATE OF 计划全称 ON mapping."年金计划"
                FOR EACH ROW
                EXECUTE FUNCTION customer.sync_contract_plan_name();
            """
        )
    )


def downgrade() -> None:
    """Remove 客户年金计划 table and all associated objects."""
    conn = op.get_bind()

    # Drop sync triggers first
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_sync_contract_customer_name
                ON customer."客户明细";
            DROP TRIGGER IF EXISTS trg_sync_contract_plan_name
                ON mapping."年金计划";
            """
        )
    )

    # Drop table (cascades to indexes and triggers)
    conn.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS customer."客户年金计划" CASCADE;
            """
        )
    )

    # Drop trigger functions
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS customer.update_customer_plan_contract_timestamp();
            DROP FUNCTION IF EXISTS customer.sync_contract_customer_name();
            DROP FUNCTION IF EXISTS customer.sync_contract_plan_name();
            """
        )
    )
