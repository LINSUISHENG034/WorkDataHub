"""Export seed data using pg_dump for large tables with complex fields.

This script exports PostgreSQL tables using pg_dump custom format for
efficient storage and restoration. Supports both enterprise and business
schema tables.

Usage:
    # Export default tables (enterprise.base_info, enterprise.enrichment_index)
    uv run --env-file .wdh_env python scripts/seed_data/export_seed_dump.py

    # Export specific tables
    uv run --env-file .wdh_env python scripts/seed_data/export_seed_dump.py \\
        --schema business --table "规模明细"

    # Export multiple tables at once
    uv run --env-file .wdh_env python scripts/seed_data/export_seed_dump.py \\
        --tables business."规模明细" business."收入明细"

    # Export to custom output directory
    uv run --env-file .wdh_env python scripts/seed_data/export_seed_dump.py \\
        --output-dir config/seeds/003

Environment Variables:
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    Overrides can be set in .wdh_env

Output:
    config/seeds/002/{table_name}.dump
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple


def get_db_config() -> dict:
    """Get database configuration from environment variables.

    Supports both PG* and WDH_DATABASE_* prefixes.

    Returns:
        Dict with host, port, user, password, database
    """
    return {
        "host": os.getenv("PGHOST") or os.getenv("WDH_DATABASE_HOST", "localhost"),
        "port": os.getenv("PGPORT") or os.getenv("WDH_DATABASE_PORT", "5432"),
        "user": os.getenv("PGUSER") or os.getenv("WDH_DATABASE_USER", "postgres"),
        "password": os.getenv("PGPASSWORD") or os.getenv("WDH_DATABASE_PASSWORD", ""),
        "database": os.getenv("PGDATABASE") or os.getenv("WDH_DATABASE_DB", "postgres"),
    }


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB", "12.3 KB")
    """
    for unit, threshold in [
        ("GB", 1024**3),
        ("MB", 1024**2),
        ("KB", 1024**1),
    ]:
        if size_bytes >= threshold:
            return f"{size_bytes / threshold:.1f} {unit}"
    return f"{size_bytes} bytes"


def parse_table_identifier(table_id: str) -> Tuple[str, str]:
    """Parse schema.table identifier.

    Args:
        table_id: Table identifier in format "schema.table" or "schema.\"table\""

    Returns:
        Tuple of (schema, table)

    Raises:
        ValueError: If format is invalid
    """
    if "." in table_id:
        parts = table_id.split(".", 1)
        schema = parts[0]
        table = parts[1].strip('"')
        return schema, table
    raise ValueError(f"Invalid table identifier: {table_id}. Use schema.table format.")


def export_table_dump(
    db_config: dict,
    schema: str,
    table: str,
    output_file: Path,
    verbose: bool = True,
) -> bool:
    """Export a single table using pg_dump custom format.

    Args:
        db_config: Database configuration dict
        schema: Schema name
        table: Table name (without quotes)
        output_file: Output file path
        verbose: Print progress messages

    Returns:
        True if successful, False otherwise
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Sanitize filename (replace spaces with underscores for filename)
    filename = table.replace(" ", "_").replace('"', "")
    output_path = output_file.parent / f"{filename}{output_file.suffix}"
    output_file = output_path

    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-d",
        db_config["database"],
        "-Fc",  # Custom format (compressed)
        "-t",
        f'"{schema}"."{table}"',  # Quote both schema and table
        "--data-only",  # Only data, no schema
        "--no-owner",  # Don't dump ownership
        "--no-acl",  # Don't dump ACLs
        "-f",
        str(output_file),
    ]

    env = {"PGPASSWORD": db_config["password"]}

    if verbose:
        print(f"Exporting {schema}.{table}...")

    try:
        result = subprocess.run(
            cmd,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=True,
        )

        # Verify file was created
        if output_file.exists():
            file_size = output_file.stat().st_size
            if verbose:
                print(f"  Success: {format_size(file_size)} -> {output_file}")
            return True
        else:
            if verbose:
                print(f"  Error: Output file not created")
            return False

    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"  Error: {e.stderr}")
        return False
    except FileNotFoundError:
        if verbose:
            print("  Error: pg_dump not found. Ensure PostgreSQL is installed.")
        return False


def verify_dump_file(dump_file: Path) -> bool:
    """Verify that a dump file is valid using pg_restore --list.

    Args:
        dump_file: Path to dump file

    Returns:
        True if valid, False otherwise
    """
    db_config = get_db_config()

    cmd = [
        "pg_restore",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-l",  # List contents
        str(dump_file),
    ]

    env = {"PGPASSWORD": db_config["password"]}

    try:
        subprocess.run(
            cmd,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def export_tables_parallel(
    tables: List[Tuple[str, str]],
    output_dir: Path,
    db_config: dict,
    max_workers: int = 2,
) -> bool:
    """Export multiple tables in parallel.

    Args:
        tables: List of (schema, table) tuples
        output_dir: Output directory
        db_config: Database configuration
        max_workers: Maximum parallel workers

    Returns:
        True if all successful, False otherwise
    """
    success = True

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                export_table_dump,
                db_config,
                schema,
                table,
                output_dir / f"{table.replace(' ', '_')}.dump",
            ): (schema, table)
            for schema, table in tables
        }

        for future in as_completed(futures):
            schema, table = futures[future]
            try:
                if not future.result():
                    print(f"Failed: {schema}.{table}")
                    success = False
            except Exception as e:
                print(f"Error exporting {schema}.{table}: {e}")
                success = False

    return success


def main() -> int:
    """Export seed data using pg_dump."""
    parser = argparse.ArgumentParser(
        description="Export seed data using pg_dump custom format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--schema",
        help="Schema name (use with --table)",
    )
    parser.add_argument(
        "--table",
        help="Table name (use with --schema)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help='Multiple tables in format "schema.table" or "schema.\\"table\\""',
    )
    parser.add_argument(
        "--output-dir",
        default=Path("config/seeds/002"),
        type=Path,
        help="Output directory (default: config/seeds/002)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Export tables in parallel",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify dump files after export",
    )
    parser.add_argument(
        "--default-enterprise",
        action="store_true",
        help="Export default enterprise tables (base_info, enrichment_index)",
    )

    args = parser.parse_args()
    db_config = get_db_config()
    output_dir = args.output_dir

    # Build table list
    tables_to_export: List[Tuple[str, str]] = []

    if args.tables:
        for table_id in args.tables:
            schema, table = parse_table_identifier(table_id)
            tables_to_export.append((schema, table))
    elif args.schema and args.table:
        tables_to_export.append((args.schema, args.table))
    elif args.default_enterprise:
        tables_to_export.extend(
            [
                ("enterprise", "base_info"),
                ("enterprise", "enrichment_index"),
            ]
        )
    else:
        parser.print_help()
        return 1

    print(f"Exporting {len(tables_to_export)} table(s) using pg_dump...")
    print(f"Output directory: {output_dir}")
    print(f"Database: {db_config['database']}@{db_config['host']}:{db_config['port']}\n")

    success = export_tables_parallel(
        tables_to_export,
        output_dir,
        db_config,
        max_workers=4 if args.parallel else 1,
    )

    # Verify if requested
    if args.verify and success:
        print("\nVerifying dump files...")
        for schema, table in tables_to_export:
            filename = table.replace(" ", "_")
            dump_file = output_dir / f"{filename}.dump"
            if dump_file.exists():
                is_valid = verify_dump_file(dump_file)
                status = "OK" if is_valid else "INVALID"
                print(f"  {schema}.{table}: {status}")

    print("\nExport complete.")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
