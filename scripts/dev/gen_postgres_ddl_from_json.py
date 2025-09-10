"""
Generate PostgreSQL DDL from MySQL table definitions in JSON format.

This script converts MySQL table definitions from JSON to PostgreSQL DDL,
preserving Chinese identifiers with proper quoting, accurate type mapping,
and optional foreign key staging.

Usage Examples:
  # Generate DDL with foreign keys
  uv run python scripts/dev/gen_postgres_ddl_from_json.py \
    --table 规模明细 \
    --json reference/db_migration/db_structure.json \
    --out scripts/dev/annuity_performance_real.sql \
    --include-fk

  # Generate DDL without foreign keys (for missing referenced tables)
  uv run python scripts/dev/gen_postgres_ddl_from_json.py \
    --table 规模明细 \
    --json reference/db_migration/db_structure.json \
    --out scripts/dev/annuity_performance_real_no_fk.sql

Notes:
- Chinese table and column names are automatically quoted for PostgreSQL compatibility
- MySQL COLLATE clauses are stripped during type conversion
- Primary keys are inferred from unique indexes when not explicitly marked
- Foreign keys reference other Chinese-named tables and may need --include-fk flag
- UTF-8 encoding is handled throughout for Chinese character support
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class ColumnDef:
    """Column definition for DDL generation."""
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    primary_key: bool


@dataclass
class IndexDef:
    """Index definition for DDL generation."""
    name: str
    columns: List[str]
    unique: bool


@dataclass
class ForeignKeyDef:
    """Foreign key definition for DDL generation."""
    name: str
    constrained_columns: List[str]
    referred_table: str
    referred_columns: List[str]


# Type mappings from MySQL to PostgreSQL
TYPE_MAPPINGS = {
    'INTEGER': 'INTEGER',
    'DATE': 'DATE',
    'DOUBLE': 'double precision',
    'TEXT': 'TEXT',
    'BIGINT': 'BIGINT',
    'SMALLINT': 'SMALLINT',
    'DECIMAL': 'DECIMAL',
    'NUMERIC': 'NUMERIC',
    'TIMESTAMP': 'TIMESTAMP',
    'TIME': 'TIME',
    'BOOLEAN': 'BOOLEAN',
    'BOOL': 'BOOLEAN',
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate PostgreSQL DDL from MySQL table definitions in JSON format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Usage Examples:')[1] if 'Usage Examples:' in __doc__ else ""
    )
    parser.add_argument(
        "--table",
        required=True,
        help="Name of the table to generate DDL for (supports Chinese names)",
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Path to the JSON file containing MySQL table definitions",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the generated PostgreSQL DDL file",
    )
    parser.add_argument(
        "--include-fk",
        action="store_true",
        help="Include foreign key constraints (may reference non-existent tables)",
    )
    return parser.parse_args()


def mysql_to_postgres_type(mysql_type: str) -> str:
    """
    Convert MySQL type to PostgreSQL equivalent.

    Args:
        mysql_type: MySQL column type (e.g., "VARCHAR(255) COLLATE \"utf8_general_ci\"")

    Returns:
        PostgreSQL equivalent type

    Examples:
        >>> mysql_to_postgres_type('VARCHAR(255) COLLATE "utf8_general_ci"')
        'VARCHAR(255)'
        >>> mysql_to_postgres_type('DOUBLE')
        'double precision'
    """
    # CRITICAL: Strip COLLATE clauses with regex - they're incompatible with PostgreSQL
    cleaned_type = re.sub(r'\s+COLLATE\s+"[^"]*"', '', mysql_type).strip()

    # Handle VARCHAR and other types with parameters - preserve them after COLLATE removal
    if cleaned_type.startswith('VARCHAR') or cleaned_type.startswith('CHAR'):
        return cleaned_type

    # Handle DECIMAL/NUMERIC with precision and scale
    if cleaned_type.startswith('DECIMAL') or cleaned_type.startswith('NUMERIC'):
        return cleaned_type

    # Direct mapping for common types
    return TYPE_MAPPINGS.get(cleaned_type, cleaned_type)


def infer_primary_key(indexes: List[dict]) -> List[str]:
    """
    Infer primary key columns from unique indexes.

    Args:
        indexes: List of index definitions from JSON

    Returns:
        List of column names that form the primary key
    """
    # Look for unique indexes, prefer one named "INDEX" or containing "id"
    unique_indexes = [idx for idx in indexes if idx.get("unique", False)]

    if not unique_indexes:
        return []

    # Prefer index with "INDEX" name or containing "id" column
    for idx in unique_indexes:
        if idx["name"] == "INDEX" or any("id" in col.lower() for col in idx["columns"]):
            return idx["columns"]

    # Fallback to first unique index
    return unique_indexes[0]["columns"]


def generate_table_ddl(table_name: str, table_def: dict) -> str:
    """
    Generate CREATE TABLE statement with Chinese identifiers.

    Args:
        table_name: Name of the table (supports Chinese)
        table_def: Table definition from JSON

    Returns:
        CREATE TABLE DDL statement
    """
    # CRITICAL: Quote Chinese table name for PostgreSQL compatibility
    quoted_table = f'"{table_name}"'

    lines = [f'CREATE TABLE IF NOT EXISTS {quoted_table} (']

    columns = table_def.get("columns", [])
    if not columns:
        raise ValueError(f"No columns found for table {table_name}")

    # Generate column definitions
    col_lines = []
    for col in columns:
        # CRITICAL: Quote Chinese column names
        col_name = f'"{col["name"]}"'
        col_type = mysql_to_postgres_type(col["type"])
        nullable = "" if col.get("nullable", True) else " NOT NULL"

        # Handle default values if present
        default = ""
        if col.get("default") is not None:
            default_val = col["default"]
            if isinstance(default_val, str):
                default = f" DEFAULT '{default_val}'"
            else:
                default = f" DEFAULT {default_val}"

        col_lines.append(f"  {col_name:<25} {col_type}{nullable}{default}")

    # Infer primary key from unique indexes
    pk_columns = infer_primary_key(table_def.get("indexes", []))
    if pk_columns:
        # CRITICAL: Quote Chinese column names in primary key definition
        pk_def = ", ".join(f'"{col}"' for col in pk_columns)
        col_lines.append(f"  CONSTRAINT pk_{table_name.replace(' ', '_')} PRIMARY KEY ({pk_def})")

    lines.extend([
        line + ("," if i < len(col_lines) - 1 else "")
        for i, line in enumerate(col_lines)
    ])
    lines.append(");")

    return "\n".join(lines)


def generate_indexes(table_name: str, indexes: List[dict]) -> str:
    """
    Generate CREATE INDEX statements.

    Args:
        table_name: Name of the table
        indexes: List of index definitions from JSON

    Returns:
        CREATE INDEX DDL statements
    """
    if not indexes:
        return ""

    lines = ["-- Indexes"]
    quoted_table = f'"{table_name}"'

    for idx in indexes:
        # Skip unique indexes already used for primary key
        if idx.get("unique", False) and (
            idx["name"] == "INDEX" or any("id" in col.lower() for col in idx["columns"])
        ):
            continue

        # CRITICAL: Quote Chinese index names and column names
        index_name = f'"{idx["name"]}"'
        column_list = ", ".join(f'"{col}"' for col in idx["columns"])

        unique_clause = "UNIQUE " if idx.get("unique", False) else ""

        index_sql = (
            f"CREATE {unique_clause}INDEX IF NOT EXISTS {index_name} "
            f"ON {quoted_table} ({column_list});"
        )
        lines.append(index_sql)

    return "\n".join(lines) if len(lines) > 1 else ""


def generate_foreign_keys(table_name: str, foreign_keys: List[dict]) -> str:
    """
    Generate ALTER TABLE statements for foreign keys.

    Args:
        table_name: Name of the table
        foreign_keys: List of foreign key definitions from JSON

    Returns:
        ALTER TABLE DDL statements for foreign keys
    """
    if not foreign_keys:
        return ""

    lines = ["-- Foreign Key Constraints"]
    quoted_table = f'"{table_name}"'

    for fk in foreign_keys:
        # CRITICAL: Quote Chinese table and column names
        constraint_name = fk["name"]
        local_cols = ", ".join(f'"{col}"' for col in fk["constrained_columns"])
        ref_table = f'"{fk["referred_table"]}"'
        ref_cols = ", ".join(f'"{col}"' for col in fk["referred_columns"])

        fk_sql = f"""ALTER TABLE {quoted_table}
    ADD CONSTRAINT {constraint_name}
    FOREIGN KEY ({local_cols})
    REFERENCES {ref_table}({ref_cols});"""

        lines.append(fk_sql)

    return "\n".join(lines) if len(lines) > 1 else ""


def generate_table_comments(table_name: str, table_def: dict) -> str:
    """
    Generate COMMENT statements for table and columns.

    Args:
        table_name: Name of the table
        table_def: Table definition from JSON

    Returns:
        COMMENT DDL statements
    """
    lines = ["-- Table and Column Comments"]
    quoted_table = f'"{table_name}"'

    # Table comment
    lines.append(
        f"COMMENT ON TABLE {quoted_table} IS '{table_name} (Generated from MySQL JSON schema)';"
    )

    # Column comments (use Chinese column names as comments for clarity)
    for col in table_def.get("columns", []):
        col_name = f'"{col["name"]}"'
        comment = col["name"]  # Use the Chinese name as the comment
        lines.append(f"COMMENT ON COLUMN {quoted_table}.{col_name} IS '{comment}';")

    return "\n".join(lines)


def load_json_table_def(json_path: Path, table_name: str) -> dict:
    """
    Load table definition from JSON file.

    Args:
        json_path: Path to the JSON file
        table_name: Name of the table to extract

    Returns:
        Table definition dictionary

    Raises:
        ValueError: If table not found in JSON
        FileNotFoundError: If JSON file doesn't exist
    """
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    try:
        # CRITICAL: UTF-8 encoding must be explicit for Chinese characters
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load JSON file: {e}")

    # Navigate to table definition - look in "business" section first
    if "business" in data and table_name in data["business"]:
        return data["business"][table_name]
    elif table_name in data:
        return data[table_name]
    else:
        available_tables = []
        if "business" in data:
            available_tables.extend(data["business"].keys())
        available_tables.extend([
            k for k in data.keys()
            if isinstance(data[k], dict) and "columns" in data[k]
        ])

        raise ValueError(
            f"Table '{table_name}' not found in JSON. "
            f"Available tables: {', '.join(available_tables)}"
        )


def generate_ddl_header(table_name: str, json_path: Path, include_fk: bool) -> str:
    """
    Generate DDL file header with metadata.

    Args:
        table_name: Name of the table
        json_path: Path to source JSON file
        include_fk: Whether foreign keys are included

    Returns:
        DDL header comment block
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fk_note = "with foreign keys" if include_fk else "without foreign keys"

    return f"""-- PostgreSQL DDL for table: {table_name}
-- Generated from: {json_path}
-- Generation time: {timestamp}
-- Configuration: {fk_note}
--
-- IMPORTANT: Chinese identifiers are properly quoted for PostgreSQL compatibility
-- IMPORTANT: MySQL COLLATE clauses have been stripped during conversion
-- IMPORTANT: Primary key inferred from unique indexes in source schema
--

"""


def main() -> int:
    """Main CLI orchestration function."""
    try:
        args = parse_args()

        # Validate input paths
        json_path = Path(args.json)
        out_path = Path(args.out)

        print(f"Generating PostgreSQL DDL for table: {args.table}")
        print(f"Source JSON: {json_path}")
        print(f"Output file: {out_path}")
        print(f"Include foreign keys: {args.include_fk}")

        # Load table definition from JSON
        table_def = load_json_table_def(json_path, args.table)
        print(f"Found table definition with {len(table_def.get('columns', []))} columns")

        # Generate all DDL components
        ddl_parts = []

        # Header
        ddl_parts.append(generate_ddl_header(args.table, json_path, args.include_fk))

        # Main table DDL
        ddl_parts.append(generate_table_ddl(args.table, table_def))
        ddl_parts.append("")

        # Indexes
        index_ddl = generate_indexes(args.table, table_def.get("indexes", []))
        if index_ddl:
            ddl_parts.append(index_ddl)
            ddl_parts.append("")

        # Foreign keys (conditional)
        if args.include_fk:
            fk_ddl = generate_foreign_keys(args.table, table_def.get("foreign_keys", []))
            if fk_ddl:
                ddl_parts.append(fk_ddl)
                ddl_parts.append("")

        # Table and column comments
        comment_ddl = generate_table_comments(args.table, table_def)
        ddl_parts.append(comment_ddl)

        # Write output file
        full_ddl = "\n".join(ddl_parts)

        # Ensure output directory exists
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # CRITICAL: UTF-8 encoding for Chinese characters
        out_path.write_text(full_ddl, encoding='utf-8')

        print(f"DDL generated successfully: {out_path}")
        print(f"File size: {out_path.stat().st_size} bytes")

        return 0

    except Exception as e:
        print(f"Error generating DDL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
