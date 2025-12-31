"""Seed static reference data from CSV files.

Story 7.2-2: New Migration Structure
Phase 2: Create 003_seed_static_data.py with ~1,350 rows of seed data

This migration populates reference data tables from CSV files:
- Enterprise schema: company_types_classification (104 rows),
  industrial_classification (1,183 rows)
- Mapping schema: 产品线 (12 rows), 组织架构 (38 rows), 计划层规模 (7 rows),
  产品明细 (18 rows), 利润指标 (12 rows)

All INSERT statements use ON CONFLICT DO NOTHING for idempotency.

CRITICAL: All seed data comes from legacy database (config/seeds/*.csv),
version-controlled.
No embedded data - all values loaded from CSV files.

Revision ID: 20251228_000003
Revises: 20251228_000002
Create Date: 2025-12-28
"""

from __future__ import annotations

import csv
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20251228_000003"
down_revision = "20251228_000002"
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


def _get_seeds_dir() -> Path:
    """Get the path to config/seeds/ directory."""
    # Path: io/schema/migrations/versions/003_*.py -> config/seeds/
    return Path(__file__).parent.parent.parent.parent.parent / "config" / "seeds"


def _normalize_value(value: str) -> str | None:
    """Normalize CSV value by stripping whitespace and newlines.

    Returns None for empty strings to handle numeric columns correctly.
    """
    if value is None:
        return None
    cleaned = value.strip().replace("\r\n", "").replace("\n", "").replace("\r", "")
    return cleaned if cleaned else None


def _load_csv_seed_data(conn, csv_filename: str, table_name: str, schema: str) -> int:
    """Load seed data from CSV file into table.

    Returns the number of rows inserted.
    """
    csv_path = _get_seeds_dir() / csv_filename

    if not csv_path.exists():
        print(f"Warning: CSV file not found: {csv_path}")
        return 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return 0

    # Build INSERT statement with ON CONFLICT DO NOTHING
    columns = list(rows[0].keys())
    # Exclude 'id' for tables with GENERATED ALWAYS AS IDENTITY columns
    # Story 7.5: Added 年金客户 to the list (id is now IDENTITY)
    if "id" in columns and table_name in [
        "年金计划",
        "组合计划",
        "年金客户",
    ]:
        columns.remove("id")

    columns_str = ", ".join(f'"{col}"' for col in columns)
    # Use safe parameter names (param_0, param_1, etc.) to handle special chars
    # in column names
    placeholders_str = ", ".join(f":param_{i}" for i in range(len(columns)))

    insert_sql = f"""
        INSERT INTO {schema}."{table_name}" ({columns_str})
        VALUES ({placeholders_str})
        ON CONFLICT DO NOTHING
    """

    # Execute batch insert with remapped parameter names and normalized values
    inserted = 0
    for row in rows:
        # Map original column names to safe parameter names with normalization
        params = {
            f"param_{i}": _normalize_value(row[col]) for i, col in enumerate(columns)
        }
        # Skip empty rows (all values are None because _normalize_value returns None
        # for empty strings)
        if all(v is None for v in params.values()):
            continue
        conn.execute(sa.text(insert_sql), params)
        inserted += 1

    return inserted


def upgrade() -> None:
    """Populate all reference data tables from CSV files."""
    conn = op.get_bind()
    seeds_dir = _get_seeds_dir()

    print(f"Loading seed data from: {seeds_dir}")

    # ========================================================================
    # ENTERPRISE SCHEMA (Large Datasets)
    # ========================================================================

    # === 1. company_types_classification (104 rows) ===
    if _table_exists(conn, "company_types_classification", "enterprise"):
        count = _load_csv_seed_data(
            conn,
            "company_types_classification.csv",
            "company_types_classification",
            "enterprise",
        )
        print(f"Seeded {count} rows into enterprise.company_types_classification")

    # === 2. industrial_classification (1,183 rows) ===
    if _table_exists(conn, "industrial_classification", "enterprise"):
        count = _load_csv_seed_data(
            conn,
            "industrial_classification.csv",
            "industrial_classification",
            "enterprise",
        )
        print(f"Seeded {count} rows into enterprise.industrial_classification")

    # ========================================================================
    # MAPPING SCHEMA (From Legacy Database)
    # ========================================================================

    # === 3. 产品线 (12 rows) ===
    if _table_exists(conn, "产品线", "mapping"):
        count = _load_csv_seed_data(conn, "产品线.csv", "产品线", "mapping")
        print(f"Seeded {count} rows into mapping.产品线")

    # === 4. 组织架构 (38 rows) ===
    if _table_exists(conn, "组织架构", "mapping"):
        count = _load_csv_seed_data(conn, "组织架构.csv", "组织架构", "mapping")
        print(f"Seeded {count} rows into mapping.组织架构")

    # === 5. 计划层规模 (7 rows) ===
    if _table_exists(conn, "计划层规模", "mapping"):
        count = _load_csv_seed_data(conn, "计划层规模.csv", "计划层规模", "mapping")
        print(f"Seeded {count} rows into mapping.计划层规模")

    # === 6. 产品明细 (18 rows) ===
    if _table_exists(conn, "产品明细", "mapping"):
        count = _load_csv_seed_data(conn, "产品明细.csv", "产品明细", "mapping")
        print(f"Seeded {count} rows into mapping.产品明细")

    # === 7. 利润指标 (12 rows) ===
    if _table_exists(conn, "利润指标", "mapping"):
        count = _load_csv_seed_data(conn, "利润指标.csv", "利润指标", "mapping")
        print(f"Seeded {count} rows into mapping.利润指标")

    # === 8. 年金客户 (985 rows - cascade filtered from 年金计划.company_id) ===
    if _table_exists(conn, "年金客户", "mapping"):
        count = _load_csv_seed_data(conn, "年金客户.csv", "年金客户", "mapping")
        print(f"Seeded {count} rows into mapping.年金客户")

    # === 9. 年金计划 (1,128 rows - base table, company_id NOT LIKE 'IN%') ===
    if _table_exists(conn, "年金计划", "mapping"):
        count = _load_csv_seed_data(conn, "年金计划.csv", "年金计划", "mapping")
        print(f"Seeded {count} rows into mapping.年金计划")

    # === 10. 组合计划 (1,315 rows - cascade filtered from 年金计划.年金计划号) ===
    if _table_exists(conn, "组合计划", "mapping"):
        count = _load_csv_seed_data(conn, "组合计划.csv", "组合计划", "mapping")
        print(f"Seeded {count} rows into mapping.组合计划")

    # ========================================================================
    # ENTERPRISE SCHEMA (Enrichment Cache)
    # ========================================================================

    # === 11. enrichment_index (32,052 rows - aggregated from legacy migration) ===
    if _table_exists(conn, "enrichment_index", "enterprise"):
        count = _load_csv_seed_data(
            conn, "enrichment_index.csv", "enrichment_index", "enterprise"
        )
        print(f"Seeded {count} rows into enterprise.enrichment_index")


def downgrade() -> None:
    """Remove all seed data.

    This simply truncates the seed data tables without dropping them.
    """
    conn = op.get_bind()

    # Truncate tables in reverse order
    for table, schema in [
        ("enrichment_index", "enterprise"),
        ("组合计划", "mapping"),
        ("年金计划", "mapping"),
        ("年金客户", "mapping"),
        ("利润指标", "mapping"),
        ("产品明细", "mapping"),
        ("计划层规模", "mapping"),
        ("组织架构", "mapping"),
        ("产品线", "mapping"),
        ("industrial_classification", "enterprise"),
        ("company_types_classification", "enterprise"),
    ]:
        if _table_exists(conn, table, schema):
            conn.execute(sa.text(f'TRUNCATE TABLE {schema}."{table}" CASCADE;'))
