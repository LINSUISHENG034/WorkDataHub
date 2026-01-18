"""Customer MDM sync CLI command.

Story 7.6-6: Contract Status Sync
Manual trigger for contract status synchronization.

Usage:
    python -m work_data_hub.cli customer-mdm sync
    python -m work_data_hub.cli customer-mdm sync --dry-run
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Main entry point for customer-mdm sync command.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli customer-mdm sync",
        description="Manually trigger customer MDM data synchronization",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing database changes",
    )

    parser.add_argument(
        "--period",
        type=str,
        default=None,
        help=(
            "Period to sync (YYYYMM format). "
            "If not specified, syncs all available data."
        ),
    )

    args = parser.parse_args(argv)

    # Import sync function
    from work_data_hub.customer_mdm import sync_contract_status

    try:
        print("🔄 Starting contract status sync...")

        result = sync_contract_status(
            period=args.period,
            dry_run=args.dry_run,
        )

        print("✓ Sync completed:")
        print(f"  Inserted: {result['inserted']}")
        print(f"  Updated: {result['updated']}")
        print(f"  Total processed: {result['total']}")

        if args.dry_run:
            print("\n⚠ Dry-run mode: No changes were made to the database")

        return 0

    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
