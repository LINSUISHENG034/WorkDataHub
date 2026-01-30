"""Create trigger for syncing product line name across denormalized tables.

Story 7.6-9: Index & Trigger Optimization
Task 1: Create trigger function and attach to mapping."产品线" table

Purpose: Automatically propagate 产品线 name changes from the source dimension
table to denormalized columns in customer tables, ensuring data consistency.

Target Tables:
- customer.customer_plan_contract.product_line_name
- customer.fct_customer_business_monthly_status.product_line_name

Revision ID: 20260129_000011
Revises: 20260129_000010
Create Date: 2026-01-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260129_000011"
down_revision = "20260129_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sync_product_line_name trigger function and attach to mapping.产品线."""
    conn = op.get_bind()

    # 1. Create trigger function in customer schema
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION customer.sync_product_line_name()
            RETURNS TRIGGER AS $$
            DECLARE
                v_contract_count INTEGER;
                v_snapshot_count INTEGER;
            BEGIN
                -- Sync to customer_plan_contract (use IS DISTINCT FROM for NULL safety)
                UPDATE customer.customer_plan_contract
                SET product_line_name = NEW."产品线",
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_line_code = NEW."产品线代码"
                  AND product_line_name IS DISTINCT FROM NEW."产品线";

                GET DIAGNOSTICS v_contract_count = ROW_COUNT;

                -- Sync to fct_customer_business_monthly_status
                UPDATE customer.fct_customer_business_monthly_status
                SET product_line_name = NEW."产品线",
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_line_code = NEW."产品线代码"
                  AND product_line_name IS DISTINCT FROM NEW."产品线";

                GET DIAGNOSTICS v_snapshot_count = ROW_COUNT;

                -- Performance monitoring
                RAISE NOTICE 'sync_product_line_name: % contract, % snapshot rows',
                    v_contract_count, v_snapshot_count;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            COMMENT ON FUNCTION customer.sync_product_line_name()
                IS 'Syncs product_line_name when mapping.产品线 changes';
            """
        )
    )

    # 2. Drop existing trigger if exists (idempotent deployment)
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_sync_product_line_name
                ON mapping."产品线";
            """
        )
    )

    # 3. Attach trigger to mapping."产品线" table
    conn.execute(
        sa.text(
            """
            CREATE TRIGGER trg_sync_product_line_name
                AFTER UPDATE ON mapping."产品线"
                FOR EACH ROW
                WHEN (OLD."产品线" IS DISTINCT FROM NEW."产品线")
                EXECUTE FUNCTION customer.sync_product_line_name();

            COMMENT ON TRIGGER trg_sync_product_line_name ON mapping."产品线" IS
                'Syncs product_line_name to customer.customer_plan_contract and '
                'customer.fct_customer_business_monthly_status when 产品线 changes';
            """
        )
    )


def downgrade() -> None:
    """Remove sync_product_line_name trigger and function."""
    conn = op.get_bind()

    # Drop trigger first
    conn.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_sync_product_line_name
                ON mapping."产品线";
            """
        )
    )

    # Drop function
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS customer.sync_product_line_name();
            """
        )
    )
