#!/usr/bin/env python
"""
MySQL Dump to PostgreSQL Migration Script.

Convenience wrapper for migrating legacy MySQL databases to PostgreSQL.
This script provides a simple interface for the common migration use case.

Usage:
    # Scan available databases
    PYTHONPATH=src uv run python scripts/migrations/migrate_mysql_dump_to_postgres.py scan

    # Dry run migration
    PYTHONPATH=src uv run python scripts/migrations/migrate_mysql_dump_to_postgres.py --dry-run

    # Full migration
    DATABASE_URL="postgresql://postgres:Post.169828@localhost:5432/postgres" \\
    PYTHONPATH=src uv run python scripts/migrations/migrate_mysql_dump_to_postgres.py

    # Migrate specific databases
    PYTHONPATH=src uv run python scripts/migrations/migrate_mysql_dump_to_postgres.py \\
        --databases mapping finance
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default configuration
DEFAULT_DUMP_FILE = "tests/fixtures/legacy_db/alldb_backup_20251208.sql"
DEFAULT_DATABASES = ["mapping", "business", "customer", "finance"]
DEFAULT_SCHEMA = "legacy"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy MySQL databases to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan dump file for available databases
  %(prog)s scan

  # Preview conversion for a specific database
  %(prog)s preview mapping

  # Dry run migration (no database changes)
  %(prog)s --dry-run

  # Full migration with default databases
  %(prog)s

  # Migrate specific databases only
  %(prog)s --databases mapping finance

  # Save converted SQL for review
  %(prog)s --dry-run --save-sql
        """,
    )

    parser.add_argument(
        "action",
        nargs="?",
        default="migrate",
        choices=["scan", "preview", "migrate"],
        help="Action to perform (default: migrate)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target database name (for preview action)",
    )
    parser.add_argument(
        "--dump-file",
        default=DEFAULT_DUMP_FILE,
        help=f"Path to MySQL dump file (default: {DEFAULT_DUMP_FILE})",
    )
    parser.add_argument(
        "--databases",
        "-d",
        nargs="+",
        default=DEFAULT_DATABASES,
        help=f"Databases to migrate (default: {' '.join(DEFAULT_DATABASES)})",
    )
    parser.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help=f"Target PostgreSQL schema (default: {DEFAULT_SCHEMA})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making database changes",
    )
    parser.add_argument(
        "--save-sql",
        action="store_true",
        help="Save converted SQL files for review",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/migrations/converted",
        help="Directory for converted SQL files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Resolve dump file path
    dump_file = Path(args.dump_file)
    if not dump_file.is_absolute():
        dump_file = PROJECT_ROOT / dump_file

    if not dump_file.exists():
        print(f"Error: Dump file not found: {dump_file}", file=sys.stderr)
        return 1

    # Import CLI module
    from scripts.migrations.mysql_dump_migrator.cli import (
        cmd_migrate,
        cmd_preview,
        cmd_scan,
        configure_logging,
    )

    # Create namespace for CLI commands
    cli_args = argparse.Namespace(
        dump_file=str(dump_file),
        databases=args.databases,
        schema=args.schema,
        dry_run=args.dry_run,
        save_sql=args.save_sql,
        output_dir=args.output_dir,
        verbose=args.verbose,
        summary=True,
        database=args.target,
        limit=5,
    )

    # Execute action
    if args.action == "scan":
        return cmd_scan(cli_args)
    elif args.action == "preview":
        if not args.target:
            print("Error: preview action requires a database name", file=sys.stderr)
            print("Usage: %(prog)s preview <database_name>")
            return 1
        return cmd_preview(cli_args)
    else:
        return cmd_migrate(cli_args)


if __name__ == "__main__":
    sys.exit(main())
