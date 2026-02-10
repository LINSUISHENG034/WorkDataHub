"""Customer MDM snapshot CLI command.

Story 7.6-7: Monthly Snapshot Refresh (Post-ETL Hook)
Story 7.6-16: Fact Table Refactoring (双表粒度分离)

Manual trigger for monthly snapshot refresh.
Refreshes both ProductLine and Plan level fact tables.

Usage:
    python -m work_data_hub.cli customer-mdm snapshot --period 202601
    python -m work_data_hub.cli customer-mdm snapshot --period 202601 --dry-run
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Main entry point for customer-mdm snapshot command.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli customer-mdm snapshot",
        description="Manually trigger monthly snapshot refresh",
    )

    parser.add_argument(
        "--period",
        type=str,
        required=True,
        help=("Period to refresh (YYYYMM format). Example: 202601 for January 2026"),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing database changes",
    )

    args = parser.parse_args(argv)

    # Import refresh function
    from work_data_hub.customer_mdm import refresh_monthly_snapshot

    try:
        print(f"🔄 Starting monthly snapshot refresh for period {args.period}...")

        result = refresh_monthly_snapshot(
            period=args.period,
            dry_run=args.dry_run,
        )

        print("✓ Snapshot refresh completed:")
        print(f"  ProductLine table: {result['product_line_upserted']} records")
        print(f"  Plan table: {result['plan_upserted']} records")

        if args.dry_run:
            print("\n⚠ Dry-run mode: No changes were made to the database")

        return 0

    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        return 1

    except Exception as e:
        print(f"❌ Snapshot refresh failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
