"""Customer MDM cutover CLI command.

Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
AC-5: CLI Support

Usage:
    python -m work_data_hub.cli customer-mdm cutover --year 2026
    python -m work_data_hub.cli customer-mdm cutover --year 2026 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from structlog import get_logger

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for customer-mdm cutover command.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli customer-mdm cutover",
        description="Execute annual cutover for customer contracts",
    )

    current_year = datetime.now().year
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help=f"Year for cutover (e.g., {current_year})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without committing to database",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Skip confirmation prompt (for automation)",
    )

    args = parser.parse_args(argv)

    # M3: Confirmation prompt for non-dry-run execution
    if not args.dry_run and not args.yes:
        print("⚠️  WARNING: Annual cutover is a significant operation!")
        print("   This will:")
        print(f"   - Close ALL current records (valid_to → {args.year}-01-01)")
        print(f"   - Insert new records with status_year = {args.year}")
        print(f"   - Use prior year ({args.year - 1}) December data for strategic calc")
        print()
        confirm = input("Type 'yes' to proceed, or anything else to cancel: ")
        if confirm.lower() != "yes":
            print("❌ Cutover cancelled.")
            return 1

    from work_data_hub.customer_mdm.year_init import annual_cutover

    try:
        print(f"🔄 Executing annual cutover for year {args.year}...")
        if args.dry_run:
            print("   (Dry-run mode: changes will be rolled back)")

        result = annual_cutover(
            year=args.year,
            dry_run=args.dry_run,
        )

        print("✓ Annual cutover completed:")
        print(f"  Records closed: {result['closed_count']}")
        print(f"  Records inserted: {result['inserted_count']}")

        if args.dry_run:
            print("\n⚠ Dry-run mode: No changes were committed")

        return 0

    except Exception as e:
        print(f"❌ Annual cutover failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
