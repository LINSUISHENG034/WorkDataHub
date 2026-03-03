"""Seed static reference data from CSV files.

Story 7.2-2: New Migration Structure
Phase 2: Create 003_seed_static_data.py with ~1,350 rows of seed data

This migration populates reference data tables from CSV files:
- Enterprise schema: company_types_classification (104 rows),
  industrial_classification (1,183 rows), base_info (~27K rows),
  enrichment_index (~45K rows)
- Mapping schema: 产品线 (12 rows), 组织架构 (38 rows), 计划层规模 (7 rows),
  产品明细 (18 rows), 利润指标 (12 rows)

All INSERT statements use ON CONFLICT DO NOTHING for idempotency.

CRITICAL: All seed data comes from CSV files in config/seeds/.
No embedded data - all values loaded from CSV files.

Revision ID: 20251228_000003
Revises: 20251228_000002
Create Date: 2025-12-28
"""

from __future__ import annotations

import csv
from itertools import chain
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# base_info has JSONB fields up to ~100KB per row; raise CSV field limit
csv.field_size_limit(2**31 - 1)
_BATCH_SIZE = 1000

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


def _get_seeds_base_dir() -> Path:
    """Get the base path to config/seeds/ directory."""
    return Path(__file__).parent.parent.parent.parent.parent / "config" / "seeds"


def _get_seed_file_path(filename: str) -> Path:
    """Get path to seed file using highest version containing that file.

    NOTE: This logic is intentionally duplicated from seed_resolver.py.
    Migrations must be self-contained and not import from project code,
    as project code may change while migrations must remain stable.

    Scans all numeric version directories (001, 002, ...) and selects
    the highest one that actually contains the specified file.
    Empty directories are ignored - they don't affect version selection.

    Args:
        filename: Name of the seed CSV file (e.g., "产品线.csv")

    Returns:
        Full path to the seed file from the highest version containing it,
        or fallback to base directory if no versioned file exists.
    """
    base_dir = _get_seeds_base_dir()

    if not base_dir.exists():
        return base_dir / filename

    # Find all version directories containing this file
    versions_with_file = []
    for d in base_dir.iterdir():
        if d.is_dir() and d.name.isdigit():
            if (d / filename).exists():
                versions_with_file.append(d.name)

    if versions_with_file:
        highest = max(versions_with_file, key=int)
        return base_dir / highest / filename

    return base_dir / filename  # Fallback for backward compatibility


def _normalize_value(value: str) -> str | None:
    """Normalize CSV value while preserving content fidelity."""
    if value is None:
        return None
    return None if value == "" else value


def _load_csv_seed_data(conn, csv_filename: str, table_name: str, schema: str) -> int:
    """Load seed data from CSV file into table.

    Returns the number of rows inserted.
    """
    csv_path = _get_seed_file_path(csv_filename)

    if not csv_path.exists():
        print(f"Warning: CSV file not found: {csv_path}")
        return 0

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)

        if first_row is None:
            return 0

        # Build INSERT statement with ON CONFLICT DO NOTHING
        columns = list(first_row.keys())
        # Exclude 'id' for tables with GENERATED ALWAYS AS IDENTITY columns
        # Story 7.5: Added 客户明细 to the list (id is now IDENTITY)
        if "id" in columns and table_name in [
            "年金计划",
            "组合计划",
            "客户明细",
        ]:
            columns.remove("id")

        # Exclude created_at/updated_at for tables with server_default=now().
        # These columns should use database defaults, not CSV values.
        if table_name == "客户明细":
            if "created_at" in columns:
                columns.remove("created_at")
            if "updated_at" in columns:
                columns.remove("updated_at")

        columns_str = ", ".join(f'"{col}"' for col in columns)
        # Use safe parameter names (param_0, param_1, etc.) to handle special chars
        # in column names
        placeholders_str = ", ".join(f":param_{i}" for i in range(len(columns)))

        insert_sql = f"""
            INSERT INTO {schema}."{table_name}" ({columns_str})
            VALUES ({placeholders_str})
            ON CONFLICT DO NOTHING
        """

        statement = sa.text(insert_sql)
        inserted = 0
        batch: list[dict[str, str | None]] = []

        for row in chain([first_row], reader):
            # Map original column names to safe parameter names with normalization
            params = {
                f"param_{i}": _normalize_value(row[col])
                for i, col in enumerate(columns)
            }
            # Skip empty rows (all values are None because _normalize_value returns None
            # for empty strings)
            if all(v is None for v in params.values()):
                continue
            batch.append(params)
            if len(batch) >= _BATCH_SIZE:
                conn.execute(statement, batch)
                inserted += len(batch)
                batch.clear()

        if batch:
            conn.execute(statement, batch)
            inserted += len(batch)

        return inserted


def upgrade() -> None:
    """Populate all reference data tables from CSV files."""
    conn = op.get_bind()
    seeds_dir = _get_seeds_base_dir()

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

    # === 8. 客户明细 (985 rows - cascade filtered from 年金计划.company_id) ===
    # Story 7.6: Migrated from mapping to customer schema
    if _table_exists(conn, "客户明细", "customer"):
        count = _load_csv_seed_data(conn, "客户明细.csv", "客户明细", "customer")
        print(f"Seeded {count} rows into customer.客户明细")

        # Merge deprecated 年金客户标签 into tags JSONB (idempotent)
        conn.execute(
            sa.text("""
            WITH normalized AS (
                SELECT
                    company_id,
                    NULLIF(BTRIM("年金客户标签"), '') AS normalized_tag
                FROM customer."客户明细"
            )
            UPDATE customer."客户明细" AS c
            SET tags = CASE
                WHEN n.normalized_tag IS NULL THEN COALESCE(c.tags, '[]'::jsonb)
                WHEN COALESCE(c.tags, '[]'::jsonb) @> to_jsonb(ARRAY[n.normalized_tag])
                    THEN COALESCE(c.tags, '[]'::jsonb)
                ELSE COALESCE(c.tags, '[]'::jsonb)
                     || jsonb_build_array(n.normalized_tag)
            END
            FROM normalized AS n
            WHERE c.company_id = n.company_id
              AND (
                  n.normalized_tag IS NOT NULL
                  OR c.tags IS NULL
              )
        """)
        )
        # Clear deprecated source column after merge to avoid dual-write ambiguity.
        conn.execute(
            sa.text("""
            UPDATE customer."客户明细"
            SET "年金客户标签" = NULL
            WHERE "年金客户标签" IS NOT NULL
        """)
        )
        conn.execute(
            sa.text("""
            COMMENT ON COLUMN customer."客户明细"."年金客户标签"
            IS 'DEPRECATED: Use tags JSONB column instead'
        """)
        )
        print("  Merged 年金客户标签 into tags JSONB and cleared deprecated column")

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

    # === 11. base_info (27,535 rows - CSV, JSONB fields auto-cast) ===
    if _table_exists(conn, "base_info", "enterprise"):
        count = _load_csv_seed_data(conn, "base_info.csv", "base_info", "enterprise")
        print(f"Seeded {count} rows into enterprise.base_info")

    # === 12. enrichment_index (44,891 rows - CSV) ===
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
        ("base_info", "enterprise"),
        ("组合计划", "mapping"),
        ("年金计划", "mapping"),
        ("客户明细", "customer"),  # Story 7.6: Migrated to customer schema
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
