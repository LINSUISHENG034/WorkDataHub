"""
CLI for EQC data refresh operations.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 2.3: CLI entry point for data refresh operations

Usage:
    # Check freshness status
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --status

    # Refresh stale data (interactive confirmation)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-stale

    # Refresh specific companies
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --company-ids 1000065057,1000087994

    # Refresh all data (with confirmation)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-all

    # Dry run (show what would be refreshed)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-stale --dry-run
"""

import argparse
import sys

from sqlalchemy import create_engine

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.data_refresh_service import (
    EqcDataRefreshService,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

# Constants
MAX_THRESHOLD_DAYS_FOR_ALL = 999999  # Used to fetch all companies regardless of freshness


def print_freshness_status(service: EqcDataRefreshService) -> None:
    """
    Print freshness status report.

    Args:
        service: EqcDataRefreshService instance.
    """
    status = service.get_freshness_status()

    print("\n" + "=" * 60)
    print("EQC Data Freshness Status")
    print("=" * 60)
    print(f"Threshold: {status.threshold_days} days")
    print(f"Total Companies: {status.total_companies}")
    print(f"Fresh (within threshold): {status.fresh_companies}")
    print(f"Stale (older than threshold): {status.stale_companies}")
    print(f"Never Updated: {status.never_updated}")
    print("=" * 60)

    if status.stale_companies > 0 or status.never_updated > 0:
        total_needs_refresh = status.stale_companies + status.never_updated
        print(f"\n⚠️  {total_needs_refresh} companies need refresh")
        print("\nRun with --refresh-stale to refresh stale data")
    else:
        print("\n✅ All data is fresh!")

    print()


def confirm_refresh(count: int, dry_run: bool = False) -> bool:
    """
    Ask user to confirm refresh operation.

    Args:
        count: Number of companies to refresh.
        dry_run: If True, this is a dry run.

    Returns:
        True if user confirms, False otherwise.
    """
    if dry_run:
        print(f"\n[DRY RUN] Would refresh {count} companies")
        return True

    print(f"\n⚠️  About to refresh {count} companies from EQC API")
    print("This operation may take some time and will consume API quota.")

    response = input("\nContinue? [y/N]: ").strip().lower()
    return response == "y"


def print_refresh_results(result) -> None:
    """Print refresh operation results."""
    print("\n" + "=" * 60)
    print("Refresh Results")
    print("=" * 60)
    print(f"Total Requested: {result.total_requested}")
    print(f"✅ Successful: {result.successful}")
    print(f"❌ Failed: {result.failed}")
    print(f"⏭️  Skipped: {result.skipped}")
    print("=" * 60)

    if result.errors:
        print("\nErrors:")
        for error in result.errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more errors")


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        description="EQC data refresh operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Operation modes (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--status",
        action="store_true",
        help="Show freshness status report",
    )
    group.add_argument(
        "--refresh-stale",
        action="store_true",
        help="Refresh stale data (interactive confirmation)",
    )
    group.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh all data (with confirmation)",
    )
    group.add_argument(
        "--company-ids",
        type=str,
        help="Refresh specific companies (comma-separated IDs)",
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - show what would be refreshed without making changes",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompts (explicit opt-in)",
    )
    parser.add_argument(
        "--threshold-days",
        type=int,
        help="Custom freshness threshold in days (overrides settings)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Batch size for refresh operations (overrides settings)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        help="Requests per second during refresh (overrides settings)",
    )
    parser.add_argument(
        "--max-companies",
        type=int,
        help="Maximum companies to refresh (for testing)",
    )

    args = parser.parse_args()

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}", file=sys.stderr)
        return 1

    # Create database engine
    try:
        engine = create_engine(settings.get_database_connection_string())
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}", file=sys.stderr)
        return 1

    # Use context manager for connection to ensure proper cleanup
    try:
        with engine.connect() as connection:
            # Create service
            service = EqcDataRefreshService(connection)

            # Handle --status
            if args.status:
                print_freshness_status(service)
                return 0

            # Handle --company-ids
            if args.company_ids:
                company_ids = [cid.strip() for cid in args.company_ids.split(",")]

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh {len(company_ids)} companies:")
                    for cid in company_ids:
                        print(f"  - {cid}")
                    return 0

                if not args.yes:
                    if not confirm_refresh(len(company_ids), dry_run=False):
                        print("❌ Refresh cancelled")
                        return 0

                print(f"\n🔄 Refreshing {len(company_ids)} companies...")
                result = service.refresh_by_company_ids(
                    company_ids=company_ids,
                    rate_limit=args.rate_limit,
                )

                connection.commit()
                print_refresh_results(result)
                return 0 if result.failed == 0 else 1

            # Handle --refresh-stale
            if args.refresh_stale:
                # Get stale companies
                stale_companies = service.get_stale_companies(
                    threshold_days=args.threshold_days,
                    limit=args.max_companies,
                )

                if not stale_companies:
                    print("\n✅ No stale companies found!")
                    return 0

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh {len(stale_companies)} stale companies")
                    print("\nSample (first 10):")
                    for company in stale_companies[:10]:
                        days_str = f"{company.days_since_update} days" if company.days_since_update else "never"
                        print(f"  - {company.company_id}: {company.company_full_name} (last updated: {days_str})")
                    if len(stale_companies) > 10:
                        print(f"  ... and {len(stale_companies) - 10} more companies")
                    return 0

                if not args.yes:
                    if not confirm_refresh(len(stale_companies), dry_run=False):
                        print("❌ Refresh cancelled")
                        return 0

                print(f"\n🔄 Refreshing {len(stale_companies)} stale companies...")
                result = service.refresh_stale_companies(
                    threshold_days=args.threshold_days,
                    batch_size=args.batch_size,
                    rate_limit=args.rate_limit,
                    max_companies=args.max_companies,
                )

                connection.commit()
                print_refresh_results(result)
                return 0 if result.failed == 0 else 1

            # Handle --refresh-all
            if args.refresh_all:
                # Get all companies
                status = service.get_freshness_status()
                total_companies = status.total_companies

                if total_companies == 0:
                    print("\n⚠️  No companies found in base_info table")
                    return 0

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh all {total_companies} companies")
                    return 0

                if not args.yes:
                    print(f"\n⚠️  WARNING: About to refresh ALL {total_companies} companies!")
                    print("This is a resource-intensive operation.")
                    if not confirm_refresh(total_companies, dry_run=False):
                        print("❌ Refresh cancelled")
                        return 0

                print(f"\n🔄 Refreshing all {total_companies} companies...")

                # Get all company IDs using large threshold
                all_companies = service.get_stale_companies(
                    threshold_days=MAX_THRESHOLD_DAYS_FOR_ALL,
                    limit=args.max_companies,
                )

                result = service.refresh_by_company_ids(
                    company_ids=[c.company_id for c in all_companies],
                    rate_limit=args.rate_limit,
                )

                connection.commit()
                print_refresh_results(result)
                return 0 if result.failed == 0 else 1

        # Should not reach here
        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        logger.error(
            "eqc_refresh.unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
