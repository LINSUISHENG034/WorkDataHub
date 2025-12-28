"""Initial domain tables using Domain Registry definitions.

Story 7.2-2: New Migration Structure
Phase 2: Create 002_initial_domains.py with 4 registered domain tables

This migration creates the P0 domain tables using the DDL Generator:
- annuity_performance: business.规模明细 (625,126 rows in production)
- annuity_income: business.收入明细 (158,480 rows in production)
- annuity_plans: mapping.年金计划 (1,159 rows)
- portfolio_plans: mapping.组合计划 (1,338 rows)

CRITICAL: Uses ddl_generator.generate_create_table_sql() to ensure Single Source of Truth.
All tables use idempotent IF NOT EXISTS pattern.

Revision ID: 20251228_000002
Revises: 20251228_000001
Create Date: 2025-12-28
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "20251228_000002"
down_revision = "20251228_000001"
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


def _execute_domain_ddl(conn, domain_name: str) -> None:
    """Execute DDL for a domain using the Domain Registry.

    This function calls ddl_generator.generate_create_table_sql() and
    extracts the CREATE TABLE and index creation statements, excluding
    the DROP TABLE statement (since this is an upgrade migration).
    """
    # Import here to avoid circular imports
    from work_data_hub.infrastructure.schema import ddl_generator
    from work_data_hub.infrastructure.schema.registry import get_domain

    schema = get_domain(domain_name)
    full_sql = ddl_generator.generate_create_table_sql(domain_name)

    # Extract CREATE TABLE statement (skip DROP TABLE)
    # Match from CREATE TABLE to the semicolon after audit columns
    create_table_pattern = r"CREATE TABLE.*?\);"
    create_table_match = re.search(create_table_pattern, full_sql, re.DOTALL)

    if create_table_match:
        create_table_sql = create_table_match.group(0)

        # Replace TABLE with IF NOT EXISTS for idempotency
        create_table_sql = create_table_sql.replace(
            f"CREATE TABLE {schema.pg_schema}.{schema.pg_table}",
            f"CREATE TABLE IF NOT EXISTS {schema.pg_schema}.{schema.pg_table}",
        )

        conn.execute(sa.text(create_table_sql))

    # Extract and execute INDEX statements
    index_pattern = r"CREATE(?: UNIQUE)? INDEX IF NOT EXISTS.*?;"
    index_matches = re.findall(index_pattern, full_sql, re.DOTALL)

    for index_sql in index_matches:
        conn.execute(sa.text(index_sql))

    # Extract and execute TRIGGER statements
    # Match both CREATE FUNCTION and CREATE TRIGGER
    function_pattern = r"CREATE OR REPLACE FUNCTION.*?\$\$ LANGUAGE plpgsql;"
    trigger_pattern = r"CREATE TRIGGER.*?EXECUTE FUNCTION.*?\);"

    function_match = re.search(function_pattern, full_sql, re.DOTALL)
    trigger_match = re.search(trigger_pattern, full_sql, re.DOTALL)

    if function_match:
        conn.execute(sa.text(function_match.group(0)))
    if trigger_match:
        conn.execute(sa.text(trigger_match.group(0)))


def upgrade() -> None:
    """Create 4 P0 domain tables using DDL Generator."""
    conn = op.get_bind()

    # === 1. annuity_performance (business.规模明细) ===
    if not _table_exists(conn, "规模明细", "business"):
        _execute_domain_ddl(conn, "annuity_performance")

    # === 2. annuity_income (business.收入明细) ===
    if not _table_exists(conn, "收入明细", "business"):
        _execute_domain_ddl(conn, "annuity_income")

    # === 3. annuity_plans (mapping.年金计划) ===
    if not _table_exists(conn, "年金计划", "mapping"):
        _execute_domain_ddl(conn, "annuity_plans")

    # === 4. portfolio_plans (mapping.组合计划) ===
    if not _table_exists(conn, "组合计划", "mapping"):
        _execute_domain_ddl(conn, "portfolio_plans")


def downgrade() -> None:
    """Drop all domain tables created by this migration.

    This is a destructive operation. Data loss will occur.
    """
    conn = op.get_bind()

    # Drop tables in reverse order (mappings first, then business)
    # Mapping schema
    for table in ["组合计划", "年金计划"]:
        if _table_exists(conn, table, "mapping"):
            conn.execute(sa.text(f"DROP TABLE IF EXISTS mapping.{table} CASCADE;"))

    # Business schema
    for table in ["收入明细", "规模明细"]:
        if _table_exists(conn, table, "business"):
            conn.execute(sa.text(f"DROP TABLE IF EXISTS business.{table} CASCADE;"))

    # Drop update functions
    for domain in [
        "portfolio_plans",
        "annuity_plans",
        "annuity_income",
        "annuity_performance",
    ]:
        func_name = f"update_{domain}_updated_at"
        conn.execute(sa.text(f"DROP FUNCTION IF EXISTS {func_name}() CASCADE;"))
