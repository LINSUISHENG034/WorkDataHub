"""
Generate PostgreSQL DDL from reference/db_migration/db_structure.json with project conventions.

Usage examples:
  uv run python -m scripts.create_table.generate_from_json --domain annuity_performance
  uv run python -m scripts.create_table.generate_from_json --domain annuity_performance --out scripts/create_table/ddl/annuity_performance.sql

Conventions applied:
  - Technical primary key: {entity}_id GENERATED ALWAYS AS IDENTITY PRIMARY KEY
  - Audit columns: created_at, updated_at (+ trigger to auto-update updated_at)
  - Delete scope key (non-unique) from manifest.yml; create composite index, not a unique constraint
  - Column name normalization via work_data_hub.utils.column_normalizer
  - Map vendor-specific types to PostgreSQL (DOUBLE -> double precision, strip collations)
  - Use DROP TABLE IF EXISTS for idempotent re-creation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from work_data_hub.utils.column_normalizer import normalize_column_name


def _load_manifest() -> Dict[str, Any]:
    manifest_path = Path("scripts/create_table/manifest.yml")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return data or {}


def _load_structure() -> Dict[str, Any]:
    json_path = Path("reference/db_migration/db_structure.json")
    return json.loads(json_path.read_text(encoding="utf-8"))


def _pg_type(vendor_type: str) -> str:
    t = vendor_type.strip().upper()
    # Remove MySQL-style COLLATE
    if "COLLATE" in t:
        t = t.split("COLLATE", 1)[0].strip()
    # Map common types
    mappings = {
        "DOUBLE": "double precision",
        "FLOAT": "double precision",
        "INTEGER": "INTEGER",
        "INT": "INTEGER",
        "BIGINT": "BIGINT",
        "DATE": "DATE",
        "DATETIME": "TIMESTAMP",
        "TIMESTAMP": "TIMESTAMP",
        "TEXT": "TEXT",
        "TINYINT": "SMALLINT",  # PostgreSQL equivalent of TINYINT
    }
    # VARCHAR(N)
    if t.startswith("VARCHAR"):
        return t.replace("VARCHAR", "VARCHAR").strip()
    return mappings.get(t, t)


def _emit_table_sql(
    table_name: str,
    entity: str,
    columns: List[Dict[str, Any]],
    delete_scope_key: List[str],
) -> str:
    lines: List[str] = []

    def q(s):
        escaped = s.replace('"', '""')
        return f'"{escaped}"'

    lines.append("-- Auto-generated baseline DDL (initial seed).")
    lines.append(f"-- Entity: {entity} | Table: {table_name}")
    lines.append("")
    lines.append(f"DROP TABLE IF EXISTS {q(table_name)} CASCADE;")
    lines.append("")
    lines.append(f"CREATE TABLE {q(table_name)} (")
    lines.append(
        f"  {q(entity + '_id')}    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
    )

    # Emit business columns (exclude original 'id' field per project conventions)
    normalized_seen = set()
    for col in columns:
        raw = col.get("name", "").strip()
        if not raw:
            continue
        # Skip original 'id' field - we use {entity}_id as primary key
        if raw.lower() == "id":
            continue
        normalized = normalize_column_name(raw) or raw
        if normalized in normalized_seen:
            continue
        normalized_seen.add(normalized)

        pgtype = _pg_type(col.get("type", "TEXT"))
        nullable = col.get("nullable", True)
        null_sql = "" if not nullable else ""
        # Emit line (allow NULL by default unless explicitly not nullable)
        col_line = f"  {q(normalized)} {pgtype}"
        if not nullable:
            col_line += " NOT NULL"
        col_line += ","
        lines.append(col_line)

    # Audit columns (no trailing comma after last one)
    lines.append(
        "  " + q("created_at") + " TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,"
    )
    lines.append(
        "  " + q("updated_at") + " TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
    )
    lines.append(");")
    lines.append("")

    # Common indexes - only for columns that exist
    existing_columns = {col["name"] for col in columns}
    common_idx_cols = [
        "月度",
        "计划代码",
        "company_id",
        "机构代码",
        "产品线代码",
        "年金账户号",
        "年金计划号",
        "组合代码",
    ]

    for idx_col in common_idx_cols:
        if idx_col in existing_columns:
            lines.append(
                f"CREATE INDEX IF NOT EXISTS {q('idx_' + table_name + '_' + idx_col)} ON {q(table_name)} ({q(idx_col)});"
            )

    # Composite indexes - only for columns that exist
    composite_indexes = [
        ("月度", "计划代码"),
        ("月度", "company_id"),
        ("年金计划号", "组合代码"),
        ("年金计划号", "company_id"),
    ]

    for col1, col2 in composite_indexes:
        if col1 in existing_columns and col2 in existing_columns:
            idx_name = "idx_" + table_name + "_" + col1 + "_" + col2
            lines.append(
                f"CREATE INDEX IF NOT EXISTS {q(idx_name)} ON {q(table_name)} ({q(col1)}, {q(col2)});"
            )

    # Delete scope key index
    if delete_scope_key and all(col in existing_columns for col in delete_scope_key):
        idx_name = "idx_" + table_name + "_" + "_".join(delete_scope_key)
        cols = ", ".join(q(c) for c in delete_scope_key)
        lines.append(
            f"CREATE INDEX IF NOT EXISTS {q(idx_name)} ON {q(table_name)} ({cols});"
        )
    lines.append("")

    # Trigger function
    func = "update_" + entity + "_updated_at"
    trig = "trigger_update_" + entity + "_updated_at"
    lines.append(f"CREATE OR REPLACE FUNCTION {func}()")
    lines.append("RETURNS TRIGGER AS $$")
    lines.append("BEGIN")
    lines.append("    NEW.updated_at = CURRENT_TIMESTAMP;")
    lines.append("    RETURN NEW;")
    lines.append("END;")
    lines.append("$$ LANGUAGE plpgsql;")
    lines.append("")
    lines.append(
        f"CREATE TRIGGER {trig}\n    BEFORE UPDATE ON {q(table_name)}\n    FOR EACH ROW\n    EXECUTE FUNCTION {func}();"
    )
    lines.append("")

    # Notices
    lines.append("DO $$")
    lines.append("BEGIN")
    lines.append(f"    RAISE NOTICE '=== {table_name} Table Creation Complete ===';")
    lines.append(
        f"    RAISE NOTICE 'Primary Key: {entity}_id (GENERATED ALWAYS AS IDENTITY)';"
    )
    if delete_scope_key:
        lines.append(
            f"    RAISE NOTICE 'Delete Scope Key (non-unique): {', '.join(delete_scope_key)}';"
        )
    lines.append(
        "    RAISE NOTICE 'Audit Fields: created_at, updated_at with auto-update trigger';"
    )
    lines.append(
        "    RAISE NOTICE 'Indexes: Performance indexes created for common query patterns';"
    )
    lines.append("END $$ LANGUAGE plpgsql;")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate PostgreSQL DDL from db_structure.json with project conventions",
    )
    parser.add_argument(
        "--domain", required=True, help="Domain name, e.g., annuity_performance"
    )
    parser.add_argument("--out", default=None, help="Output path for DDL (optional)")
    args = parser.parse_args()

    manifest = _load_manifest()
    domains = manifest.get("domains", {})
    if args.domain not in domains:
        print(f"Domain not found in manifest: {args.domain}")
        return 2

    dom = domains[args.domain]
    table_name = dom.get("table")
    entity = dom.get("entity", args.domain)
    delete_scope_key = dom.get("delete_scope_key", [])

    struct = _load_structure()

    # Search for table in nested structure
    tables = None
    for category in struct.values():
        if isinstance(category, dict) and table_name in category:
            tables = category
            break

    if not tables or table_name not in tables:
        print(f"Table not found in db_structure.json: {table_name}")
        return 2
    cols = tables[table_name].get("columns", [])

    ddl = _emit_table_sql(table_name, entity, cols, delete_scope_key)

    out_path = (
        Path(args.out)
        if args.out
        else Path(dom.get("ddl", f"scripts/create_table/ddl/{args.domain}.sql"))
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(ddl, encoding="utf-8")
    print(f"Generated DDL: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
