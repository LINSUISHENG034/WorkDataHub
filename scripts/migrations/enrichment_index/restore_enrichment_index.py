#!/usr/bin/env python
"""
Unified Enrichment Index Recovery Script.

Restores enterprise.enrichment_index from all Legacy data sources.
Runs all migration scripts in the correct order.

Usage:
    # Dry run (recommended first)
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py --dry-run

    # Full recovery
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py

    # Verify results after recovery
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py --verify-only
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import structlog
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logger = structlog.get_logger(__name__)


def create_target_engine():
    """Create engine for target database (postgres/enterprise schema)."""
    load_dotenv(".wdh_env")
    database_url = os.environ.get("WDH_DATABASE__URI")
    if not database_url:
        raise ValueError("WDH_DATABASE__URI is required")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url)


def verify_results():
    """Verify enrichment_index contents after recovery."""
    engine = create_target_engine()

    print("\n" + "=" * 70)
    print("ENRICHMENT INDEX VERIFICATION")
    print("=" * 70)

    with engine.connect() as conn:
        # Total count
        total = conn.execute(
            text("SELECT COUNT(*) FROM enterprise.enrichment_index")
        ).scalar()
        print(f"\nTotal rows: {total:,}")

        # Count by lookup_type
        print("\nBy lookup_type:")
        result = conn.execute(
            text("""
            SELECT lookup_type, COUNT(*) as cnt
            FROM enterprise.enrichment_index
            GROUP BY lookup_type
            ORDER BY cnt DESC
        """)
        )
        for row in result:
            print(f"  {row[0]}: {row[1]:,}")

        # Count by source
        print("\nBy source:")
        result = conn.execute(
            text("""
            SELECT source, COUNT(*) as cnt
            FROM enterprise.enrichment_index
            GROUP BY source
            ORDER BY cnt DESC
        """)
        )
        for row in result:
            print(f"  {row[0]}: {row[1]:,}")

        # Sample records
        print("\nSample records:")
        result = conn.execute(
            text("""
            SELECT lookup_type, lookup_key, company_id
            FROM enterprise.enrichment_index
            ORDER BY lookup_type, lookup_key
            LIMIT 10
        """)
        )
        for row in result:
            lookup_key_display = row[1][:40] + "..." if len(row[1]) > 40 else row[1]
            print(f"  [{row[0]}] {lookup_key_display} -> {row[2]}")

    print("\n" + "=" * 70)
    return total


def run_migration_script(script_name: str, dry_run: bool = False) -> int:
    """Run a migration script and return status code."""
    import subprocess

    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"  ERROR: Script not found: {script_path}")
        return 1

    cmd = [
        sys.executable,
        str(script_path),
    ]
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent.parent / "src")

    result = subprocess.run(
        cmd, env=env, cwd=str(Path(__file__).parent.parent.parent.parent)
    )
    return result.returncode


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Enrichment Index Recovery Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually inserting data",
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify current data, don't run migration",
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv(".wdh_env")

    # Configure logging
    import logging

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    if args.verify_only:
        verify_results()
        return 0

    print("\n" + "=" * 70)
    print("ENRICHMENT INDEX RECOVERY")
    if args.dry_run:
        print(">>> DRY RUN MODE - No data will be actually inserted <<<")
    print("=" * 70)

    start_time = time.perf_counter()

    # Define migration scripts in order
    migrations = [
        (
            "migrate_customer_name_mapping.py",
            "customer_name from company_id_mapping + eqc_search_result",
        ),
        ("migrate_plan_mapping.py", "plan_code from mapping.年金计划"),
        (
            "migrate_account_number_mapping.py",
            "account_number from enterprise.annuity_account_mapping",
        ),
        ("migrate_account_name_mapping.py", "account_name from business.规模明细"),
    ]

    results = {}

    for script, description in migrations:
        print(f"\n[{len(results) + 1}/{len(migrations)}] Running: {script}")
        print(f"    Description: {description}")

        result = run_migration_script(script, dry_run=args.dry_run)
        results[script] = result

        if result != 0:
            print(f"    FAILED with exit code {result}")
        else:
            print("    SUCCESS")

    duration = time.perf_counter() - start_time

    print("\n" + "=" * 70)
    print("RECOVERY SUMMARY")
    print("=" * 70)
    print(f"Total runtime: {duration:.2f}s")
    print(f"Dry run: {args.dry_run}")

    failed = [s for s, r in results.items() if r != 0]
    if failed:
        print(f"\nFailed scripts ({len(failed)}):")
        for script in failed:
            print(f"  - {script}")
        return 1
    else:
        print("\nAll migrations completed successfully!")

        if not args.dry_run:
            print("\nVerifying results...")
            verify_results()

        return 0


if __name__ == "__main__":
    sys.exit(main())
