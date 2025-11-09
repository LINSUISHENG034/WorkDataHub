#!/usr/bin/env python3
"""
Standalone migration script for legacy company ID mappings.

This script migrates the existing 5-layer COMPANY_ID mapping logic
(COMPANY_ID1-5_MAPPING) from MySQL to PostgreSQL enterprise.company_mapping table,
maintaining 100% backward compatibility with the legacy _update_company_id logic.

Usage:
    python migrate_company_mappings.py --plan-only    # Preview migration
    python migrate_company_mappings.py --execute      # Execute migration

Requirements:
    - Access to legacy MySQL databases (mapping, enterprise, business)
    - PostgreSQL connection with enterprise schema
    - Proper environment variables set (WDH_DATABASE__*)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import psycopg2

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.work_data_hub.config.settings import get_settings  # noqa: E402
from src.work_data_hub.domain.company_enrichment.service import (  # noqa: E402
    validate_mapping_consistency,
)
from src.work_data_hub.io.loader.company_mapping_loader import (  # noqa: E402
    CompanyMappingLoaderError,
    extract_legacy_mappings,
    generate_load_plan,
    load_company_mappings,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("company_mapping_migration.log"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy company ID mappings to PostgreSQL"
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate migration plan without executing (safe preview mode)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (will modify database)",
    )
    parser.add_argument(
        "--schema",
        default="enterprise",
        help="Target PostgreSQL schema (default: enterprise)",
    )
    parser.add_argument(
        "--table",
        default="company_mapping",
        help="Target table name (default: company_mapping)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Batch size for INSERT operations (default: 1000)",
    )

    args = parser.parse_args()

    if not (args.plan_only or args.execute):
        parser.error("Must specify either --plan-only or --execute")

    if args.plan_only and args.execute:
        parser.error("Cannot specify both --plan-only and --execute")

    try:
        logger.info("=" * 60)
        logger.info("COMPANY ID MAPPING MIGRATION - PRP S-001")
        logger.info("=" * 60)

        if args.plan_only:
            logger.info("MODE: Plan-only (preview) - no database changes will be made")
        else:
            logger.info("MODE: Execute - database will be modified")

        # Step 1: Extract legacy mappings
        logger.info("Step 1: Extracting legacy mappings from 5 sources...")
        try:
            mappings = extract_legacy_mappings()
        except CompanyMappingLoaderError as e:
            logger.error(f"Legacy mapping extraction failed: {e}")
            sys.exit(1)

        if not mappings:
            logger.warning("No mappings extracted - migration aborted")
            sys.exit(0)

        logger.info(f"Successfully extracted {len(mappings)} total mappings")

        # Step 2: Validate mapping consistency
        logger.info("Step 2: Validating mapping consistency...")
        warnings = validate_mapping_consistency(mappings)

        if warnings:
            logger.warning(f"Found {len(warnings)} validation warnings:")
            for i, warning in enumerate(warnings[:10], 1):  # Show first 10
                logger.warning(f"  {i}. {warning}")
            if len(warnings) > 10:
                logger.warning(f"  ... and {len(warnings) - 10} more warnings")

        # Step 3: Generate execution plan
        logger.info("Step 3: Generating execution plan...")
        plan = generate_load_plan(mappings, args.schema, args.table)

        logger.info("MIGRATION PLAN:")
        logger.info(f"  Target: {plan['table']}")
        logger.info(f"  Total mappings: {plan['total_mappings']:,}")
        logger.info("  Breakdown by type:")

        for match_type, count in plan["mapping_breakdown"].items():
            priority = {
                "plan": 1,
                "account": 2,
                "hardcode": 3,
                "name": 4,
                "account_name": 5,
            }.get(match_type, "?")
            logger.info(
                "    %s (priority %s): %s mappings", match_type, priority, count
            )

        if args.plan_only:
            logger.info("\n" + "=" * 60)
            logger.info("PLAN DETAILS:")
            logger.info(json.dumps(plan, indent=2, ensure_ascii=False))
            logger.info("=" * 60)
            logger.info("Plan generation complete - no database changes made")
            sys.exit(0)

        # Step 4: Execute migration
        logger.info("Step 4: Executing database migration...")

        settings = get_settings()
        conn_string = settings.get_database_connection_string()

        try:
            with psycopg2.connect(conn_string) as conn:
                logger.info(
                    "Connected to PostgreSQL: %s:%s/%s",
                    settings.database_host,
                    settings.database_port,
                    settings.database_db,
                )

                # Verify target table exists
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    );
                """,
                    (args.schema, args.table),
                )

                table_exists = cursor.fetchone()[0]
                cursor.close()

                if not table_exists:
                    logger.error(
                        f"Target table {args.schema}.{args.table} does not exist"
                    )
                    logger.error(
                        "Please run the DDL script first: "
                        "scripts/create_table/ddl/company_mapping.sql"
                    )
                    sys.exit(1)

                # Execute the load
                stats = load_company_mappings(
                    mappings=mappings,
                    conn=conn,
                    schema=args.schema,
                    table=args.table,
                    mode="delete_insert",
                    chunk_size=args.chunk_size,
                )

                logger.info("MIGRATION COMPLETED SUCCESSFULLY:")
                logger.info(f"  Deleted: {stats['deleted']} existing records")
                logger.info(f"  Inserted: {stats['inserted']} new records")
                logger.info(f"  Batches processed: {stats['batches']}")

        except psycopg2.Error as e:
            logger.error(f"PostgreSQL connection/operation failed: {e}")
            sys.exit(1)

        logger.info("=" * 60)
        logger.info("MIGRATION SUCCESS - All legacy mappings migrated")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected migration failure: {e}", exc_info=True)
        sys.exit(1)


def validate_environment() -> bool:
    """
    Validate that required environment variables and dependencies are available.

    Returns:
        True if environment is properly configured
    """
    try:
        settings = get_settings()

        # Check PostgreSQL configuration
        settings.get_database_connection_string()
        logger.debug(
            f"PostgreSQL config: {settings.database_host}:{settings.database_port}"
        )

        # Check legacy MySQL access
        try:
            from legacy.annuity_hub.database_operations.mysql_ops import (
                MySqlDBManager,
            )

            _ = MySqlDBManager

            logger.debug("Legacy MySqlDBManager is available")
        except ImportError:
            logger.error(
                "Cannot import MySqlDBManager - legacy database access unavailable"
            )
            return False

        return True

    except Exception as e:
        logger.error(f"Environment validation failed: {e}")
        return False


if __name__ == "__main__":
    # Validate environment before starting
    if not validate_environment():
        logger.error("Environment validation failed - aborting migration")
        sys.exit(1)

    main()
