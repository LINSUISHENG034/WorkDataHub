"""Export seed tables as CSV using psycopg v3.

Pure Python, no pg_dump needed.

Usage::

    PYTHONPATH=src uv run --env-file .wdh_env \\
        python scripts/seed_data/export_seed_csv.py

    # Export to custom directory
    PYTHONPATH=src uv run --env-file .wdh_env \\
        python scripts/seed_data/export_seed_csv.py \\
        --output-dir config/seeds/003

    # Export specific table
    PYTHONPATH=src uv run --env-file .wdh_env \\
        python scripts/seed_data/export_seed_csv.py \\
        --tables enterprise.base_info
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from work_data_hub.config import get_settings

# Default tables to export as seed CSV
DEFAULT_TABLES: list[tuple[str, str]] = [
    ("enterprise", "base_info"),
    ("enterprise", "enrichment_index"),
]


def get_connection_string() -> str:
    """Get psycopg v3 connection string from project settings."""
    settings = get_settings()
    url = settings.get_database_connection_string()
    # Ensure we use plain postgresql:// for psycopg v3
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def export_table_to_csv(
    conn_string: str, schema: str, table: str, output_path: Path
) -> int:
    """Export a single table to CSV using psycopg v3 COPY protocol.

    Args:
        conn_string: PostgreSQL connection string
        schema: Schema name
        table: Table name
        output_path: Output CSV file path

    Returns:
        Number of bytes written
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            # Get row count first
            cur.execute(f'SELECT COUNT(*) FROM {schema}."{table}"')
            row_count = cur.fetchone()[0]

            # Export using COPY protocol (no external tools)
            copy_sql = (
                f'COPY {schema}."{table}" TO STDOUT'
                " WITH (FORMAT CSV, HEADER true,"
                " ENCODING 'UTF8')"
            )
            with open(output_path, "wb") as f:
                with cur.copy(copy_sql) as copy:
                    for block in copy:
                        f.write(block)

    file_size = output_path.stat().st_size
    print(
        f"  {schema}.{table}: {row_count:,} rows, {file_size:,} bytes -> {output_path}"
    )
    return file_size


def parse_table_identifier(table_id: str) -> tuple[str, str]:
    """Parse 'schema.table' identifier."""
    if "." not in table_id:
        raise ValueError(f"Invalid format: {table_id}. Use schema.table")
    schema, table = table_id.split(".", 1)
    return schema, table.strip('"')


def main() -> int:
    parser = argparse.ArgumentParser(description="Export seed tables as CSV")
    parser.add_argument(
        "--output-dir",
        default=Path("config/seeds/003"),
        type=Path,
        help="Output directory (default: config/seeds/003)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help='Tables in "schema.table" format (default: base_info + enrichment_index)',
    )
    args = parser.parse_args()

    tables = (
        [parse_table_identifier(t) for t in args.tables]
        if args.tables
        else DEFAULT_TABLES
    )

    conn_string = get_connection_string()
    print(f"Exporting {len(tables)} table(s) as CSV to {args.output_dir}/\n")

    for schema, table in tables:
        output_path = args.output_dir / f"{table}.csv"
        export_table_to_csv(conn_string, schema, table, output_path)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
