#!/usr/bin/env python
"""
MySQL Dump to PostgreSQL Migration CLI.

Command-line interface for migrating MySQL dump files to PostgreSQL.

Usage:
    # Scan dump file for available databases
    PYTHONPATH=src uv run python -m scripts.migrations.mysql_dump_migrator.cli scan \\
        tests/fixtures/legacy_db/alldb_backup_20251208.sql

    # Dry run migration
    PYTHONPATH=src uv run python -m scripts.migrations.mysql_dump_migrator.cli migrate \\
        tests/fixtures/legacy_db/alldb_backup_20251208.sql \\
        --databases mapping business customer finance \\
        --dry-run

    # Full migration
    DATABASE_URL="postgresql://postgres:Post.169828@localhost:5432/postgres" \\
    PYTHONPATH=src uv run python -m scripts.migrations.mysql_dump_migrator.cli migrate \\
        tests/fixtures/legacy_db/alldb_backup_20251208.sql \\
        --databases mapping business customer finance
"""

import argparse
import logging
import sys

import structlog

from .migrator import MigrationConfig, PostgreSQLMigrator
from .parser import MySQLDumpParser


def configure_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    log_level = logging.DEBUG if verbose else logging.INFO

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    # Also configure standard logging for libraries
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan dump file and list available databases."""
    print(f"\nScanning dump file: {args.dump_file}\n")

    try:
        parser = MySQLDumpParser(args.dump_file)
        databases = parser.scan_databases()

        print(f"Found {len(databases)} databases:\n")
        for i, db_name in enumerate(databases, 1):
            print(f"  {i:2}. {db_name}")

        if args.summary:
            print("\nGathering table counts (this may take a moment)...")
            summary = parser.get_database_summary()
            print("\nDatabase Summary:")
            print("-" * 40)
            for db_name, info in summary.items():
                print(f"  {db_name}: {info['table_count']} tables")

        print()
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error scanning dump file: {e}", file=sys.stderr)
        return 1


def cmd_migrate(args: argparse.Namespace) -> int:
    """Run the migration."""
    configure_logging(args.verbose)

    print(f"\n{'=' * 60}")
    print("MySQL to PostgreSQL Migration")
    print(f"{'=' * 60}")
    print(f"Dump file: {args.dump_file}")
    print(f"Target databases: {', '.join(args.databases)}")
    print(f"Target schema: {args.schema}")
    print(f"Dry run: {args.dry_run}")
    print(f"{'=' * 60}\n")

    try:
        # Create configuration
        config = MigrationConfig.from_env(
            dump_file_path=args.dump_file,
            target_databases=args.databases,
            target_schema=args.schema,
            dry_run=args.dry_run,
            save_converted_sql=args.save_sql,
            output_dir=args.output_dir,
        )

        # Run migration
        migrator = PostgreSQLMigrator(config)
        report = migrator.run()

        # Print report
        report.print_summary()

        # Return appropriate exit code
        if report.successful_databases == report.total_databases:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\nMigration failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_preview(args: argparse.Namespace) -> int:
    """Preview converted SQL for a database."""
    configure_logging(args.verbose)

    print(f"\nPreviewing conversion for database: {args.database}\n")

    try:
        parser = MySQLDumpParser(args.dump_file)

        # Check if database exists
        available = parser.scan_databases()
        if args.database not in available:
            print(f"Error: Database '{args.database}' not found in dump file.")
            print(f"Available databases: {', '.join(available)}")
            return 1

        # Extract and convert
        from .converter import MySQLToPostgreSQLConverter

        db_content = parser.extract_database(args.database)
        converter = MySQLToPostgreSQLConverter()

        print(f"Database: {db_content.name}")
        print(f"Tables: {db_content.table_count}")
        print(f"Total rows (estimated): {db_content.total_rows:,}")
        print("\n" + "-" * 60)

        # Show sample conversions
        for table_name, table_content in list(db_content.tables.items())[: args.limit]:
            print(f"\n-- Table: {table_name}")
            print(f"-- Rows: {table_content.row_count:,}")

            if table_content.create_statement:
                converted = converter.convert(
                    table_content.create_statement, args.database
                )
                print("\n-- Converted CREATE TABLE:")
                print(converted[:2000])  # Limit output
                if len(converted) > 2000:
                    print("... (truncated)")

            print()

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate MySQL dump files to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser(
        "scan", help="Scan dump file and list available databases"
    )
    scan_parser.add_argument("dump_file", help="Path to MySQL dump file")
    scan_parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Show table counts for each database",
    )

    # Migrate command
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate databases from dump file to PostgreSQL"
    )
    migrate_parser.add_argument("dump_file", help="Path to MySQL dump file")
    migrate_parser.add_argument(
        "--databases",
        "-d",
        nargs="+",
        required=True,
        help="Database names to migrate",
    )
    migrate_parser.add_argument(
        "--schema",
        default="legacy",
        help="Target PostgreSQL schema prefix (default: legacy)",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making database changes",
    )
    migrate_parser.add_argument(
        "--save-sql",
        action="store_true",
        help="Save converted SQL files for review",
    )
    migrate_parser.add_argument(
        "--output-dir",
        default="docs/migrations/converted",
        help="Directory for converted SQL files",
    )
    migrate_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    # Preview command
    preview_parser = subparsers.add_parser(
        "preview", help="Preview SQL conversion for a database"
    )
    preview_parser.add_argument("dump_file", help="Path to MySQL dump file")
    preview_parser.add_argument("database", help="Database name to preview")
    preview_parser.add_argument(
        "--limit", "-l", type=int, default=3, help="Number of tables to preview"
    )
    preview_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "migrate":
        return cmd_migrate(args)
    elif args.command == "preview":
        return cmd_preview(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
