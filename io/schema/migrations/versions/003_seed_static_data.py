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
import enum
import os
import subprocess
from pathlib import Path

import sqlalchemy as sa
from alembic import op


class _SeedFormat(enum.Enum):
    """Supported seed data formats (self-contained for migration stability)."""

    CSV = "csv"
    DUMP = "dump"  # pg_dump custom format

    @property
    def extension(self) -> str:
        return f".{self.value}"


# Format priority: higher index = higher priority
_SEED_FORMAT_PRIORITY = [_SeedFormat.CSV, _SeedFormat.DUMP]

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


def _resolve_seed_file(table_name: str) -> tuple[Path, _SeedFormat] | None:
    """Resolve seed file for a table with format awareness.

    Searches for seed files across all supported formats and returns
    the best match based on version and format priority.

    Args:
        table_name: Name of the table (without extension)

    Returns:
        Tuple of (path, format) if found, None otherwise.
    """
    base_dir = _get_seeds_base_dir()

    if not base_dir.exists():
        return None

    version_dirs = [
        d.name for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()
    ]

    if not version_dirs:
        return None

    # Search all versions, find highest version with any format
    versions_with_table: dict[str, list[tuple[Path, _SeedFormat]]] = {}
    for ver in version_dirs:
        version_dir = base_dir / ver
        found = []
        for fmt in _SEED_FORMAT_PRIORITY:
            file_path = version_dir / f"{table_name}{fmt.extension}"
            if file_path.exists():
                found.append((file_path, fmt))
        if found:
            versions_with_table[ver] = found

    if not versions_with_table:
        return None

    # Get highest version, highest priority format
    highest_version = max(versions_with_table.keys(), key=int)
    files = versions_with_table[highest_version]
    return files[-1]  # Last item has highest priority


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
    csv_path = _get_seed_file_path(csv_filename)

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

    # Exclude created_at/updated_at for tables with server_default=now()
    # These columns should use database defaults, not CSV values (which may be empty)
    if table_name == "年金客户":
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


def _load_dump_seed_data(conn, dump_path: Path, table_name: str, schema: str) -> int:
    """Load seed data from pg_dump custom format file.

    Args:
        conn: SQLAlchemy connection
        dump_path: Path to .dump file
        table_name: Target table name
        schema: Target schema name

    Returns:
        Number of rows loaded
    """
    url = conn.engine.url

    cmd = [
        "pg_restore",
        "-h",
        str(url.host or "localhost"),
        "-p",
        str(url.port or 5432),
        "-U",
        str(url.username or "postgres"),
        "-d",
        str(url.database or "postgres"),
        "--data-only",
        "--no-owner",
        "--no-privileges",
        str(dump_path),
    ]

    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = str(url.password)

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0 and "error" in result.stderr.lower():
            print(f"Warning: pg_restore issue: {result.stderr}")

        # Count rows after restore
        count_result = conn.execute(
            sa.text(f'SELECT COUNT(*) FROM {schema}."{table_name}"')
        )
        return count_result.scalar() or 0

    except FileNotFoundError:
        print("Warning: pg_restore not found. Skipping dump file.")
        return 0


def _load_seed_data(conn, table_name: str, schema: str) -> int:
    """Load seed data using format-aware resolution.

    Automatically detects the best format (dump > csv) and loads accordingly.

    Args:
        conn: SQLAlchemy connection
        table_name: Target table name
        schema: Target schema name

    Returns:
        Number of rows loaded
    """
    resolved = _resolve_seed_file(table_name)

    if resolved is None:
        # Fallback to CSV for backward compatibility
        csv_path = _get_seed_file_path(f"{table_name}.csv")
        if csv_path.exists():
            return _load_csv_seed_data(conn, f"{table_name}.csv", table_name, schema)
        print(f"Warning: No seed file found for {table_name}")
        return 0

    path, fmt = resolved
    print(f"  Using {fmt.value} format: {path.name}")

    if fmt == _SeedFormat.DUMP:
        return _load_dump_seed_data(conn, path, table_name, schema)
    else:
        return _load_csv_seed_data(conn, path.name, table_name, schema)


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

    # === 8. 年金客户 (985 rows - cascade filtered from 年金计划.company_id) ===
    # Story 7.6: Migrated from mapping to customer schema
    if _table_exists(conn, "年金客户", "customer"):
        count = _load_csv_seed_data(conn, "年金客户.csv", "年金客户", "customer")
        print(f"Seeded {count} rows into customer.年金客户")

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

    # === 11. base_info (27,535 rows - uses pg_dump format for JSON fields) ===
    if _table_exists(conn, "base_info", "enterprise"):
        count = _load_seed_data(conn, "base_info", "enterprise")
        print(f"Seeded {count} rows into enterprise.base_info")

    # === 12. enrichment_index (32,052 rows - format auto-detected) ===
    if _table_exists(conn, "enrichment_index", "enterprise"):
        count = _load_seed_data(conn, "enrichment_index", "enterprise")
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
        ("年金客户", "customer"),  # Story 7.6: Migrated to customer schema
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
