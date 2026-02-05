"""Customer MDM init-year CLI command.

Story 7.6-11: Customer Status Field Enhancement
AC-3: Create CLI command for annual status initialization

Usage:
    python -m work_data_hub.cli customer-mdm init-year --year 2026
    python -m work_data_hub.cli customer-mdm init-year --year 2026 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from structlog import get_logger

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for customer-mdm init-year command.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli customer-mdm init-year",
        description="Initialize annual customer status fields",
    )

    current_year = datetime.now().year
    parser.add_argument(
        "--year",
        type=int,
        default=current_year,
        help=f"Year to initialize status for (default: {current_year})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing database changes",
    )

    args = parser.parse_args(argv)

    from work_data_hub.customer_mdm.year_init import initialize_year_status

    try:
        print(f"🔄 Initializing customer status for year {args.year}...")

        result = initialize_year_status(
            year=args.year,
            dry_run=args.dry_run,
        )

        print("✓ Year initialization completed:")
        print(f"  Strategic customers updated: {result['strategic_updated']}")
        print(f"  Existing customers updated: {result['existing_updated']}")
        print(f"  Total contracts processed: {result['total']}")

        if args.dry_run:
            print("\n⚠ Dry-run mode: No changes were made to the database")

        return 0

    except Exception as e:
        print(f"❌ Year initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
