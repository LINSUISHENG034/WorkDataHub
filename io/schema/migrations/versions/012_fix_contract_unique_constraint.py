"""Fix customer_plan_contract unique constraint for SCD Type 2.

Story 7.6-15: Ratchet Rule Implementation
Fix: Change unique constraint from valid_to to valid_from

Problem: The original constraint (company_id, plan_code, product_line_code, valid_to)
causes UniqueViolation when multiple status changes occur on the same day.

Solution: Change to (company_id, plan_code, product_line_code, valid_from) which
better represents SCD Type 2 semantics - each version has a unique start date.

Revision ID: 20260205_000012
Revises: 20260129_000011
Create Date: 2026-02-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260205_000012"
down_revision = "20260129_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change unique constraint from valid_to to valid_from."""
    conn = op.get_bind()

    # 1. Drop the old constraint
    conn.execute(
        sa.text(
            """
            ALTER TABLE customer.customer_plan_contract
            DROP CONSTRAINT IF EXISTS uq_active_contract;
            """
        )
    )

    # 2. Remove duplicate valid_from records (keep the one with latest valid_to)
    conn.execute(
        sa.text(
            """
            DELETE FROM customer.customer_plan_contract
            WHERE contract_id IN (
                SELECT contract_id FROM (
                    SELECT contract_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY company_id, plan_code,
                                   product_line_code, valid_from
                               ORDER BY valid_to DESC, contract_id DESC
                           ) as rn
                    FROM customer.customer_plan_contract
                ) ranked
                WHERE rn > 1
            );
            """
        )
    )

    # 2. Create new constraint with valid_from
    conn.execute(
        sa.text(
            """
            ALTER TABLE customer.customer_plan_contract
            ADD CONSTRAINT uq_contract_version
            UNIQUE (company_id, plan_code, product_line_code, valid_from);
            """
        )
    )

    # 3. Add comment explaining the constraint
    conn.execute(
        sa.text(
            """
            COMMENT ON CONSTRAINT uq_contract_version
            ON customer.customer_plan_contract IS
            'SCD Type 2: Each contract version has unique start date';
            """
        )
    )


def downgrade() -> None:
    """Revert to original valid_to constraint."""
    conn = op.get_bind()

    # Drop new constraint
    conn.execute(
        sa.text(
            """
            ALTER TABLE customer.customer_plan_contract
            DROP CONSTRAINT IF EXISTS uq_contract_version;
            """
        )
    )

    # Restore old constraint
    conn.execute(
        sa.text(
            """
            ALTER TABLE customer.customer_plan_contract
            ADD CONSTRAINT uq_active_contract
            UNIQUE (company_id, plan_code, product_line_code, valid_to);
            """
        )
    )
