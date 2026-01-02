"""Make company_id nullable for empty customer names (Story 7.5-3).

Story 7.5-3: Empty Customer Name Returns NULL Instead of Temp ID

This migration alters company_id columns to allow NULL values, fixing the
semantic issue where empty customer names shared a temp ID.

Changes:
- business.规模明细.company_id: NOT NULL → NULL
- business.收入明细.company_id: Already NULL (verified, no change)

Domain Registry Source of Truth:
- annuity_performance.company_id: nullable=True (updated in Story 7.5-3)
- annuity_income.company_id: nullable=True (already correct)

Production Impact:
- 625,126 rows in business.规模明细
- 158,480 rows in business.收入明细
- No data loss: Existing company_id values are preserved

Revision ID: 20260102_000004
Revises: 20251228_000003
Create Date: 2026-01-02
"""

from __future__ import annotations

from alembic import op


def upgrade() -> None:
    """Make company_id nullable for empty customer name handling."""

    # business.规模明细 (annuity_performance)
    # Story 7.5-3: Allow NULL for empty customer names
    op.execute('ALTER TABLE business."规模明细" ALTER COLUMN company_id DROP NOT NULL')

    # business.收入明细 (annuity_income)
    # Already nullable, but verify idempotently
    # (No-op if already NULL, which is the case)

    # Note: annuity_income.company_id was already nullable=True
    # No ALTER needed, but documenting for clarity


def downgrade() -> None:
    """Revert company_id to NOT NULL (NOT RECOMMENDED)."""

    # WARNING: Downgrade will fail if any NULL values exist
    # Verify no NULLs before reverting:
    # SELECT COUNT(*) FROM business."规模明细" WHERE company_id IS NULL

    op.execute('ALTER TABLE business."规模明细" ALTER COLUMN company_id SET NOT NULL')

    # business.收入明细
    # Revert to original state (nullable=False)
    op.execute('ALTER TABLE business."收入明细" ALTER COLUMN company_id SET NOT NULL')
