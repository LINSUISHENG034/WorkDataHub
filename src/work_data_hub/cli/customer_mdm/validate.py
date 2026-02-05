"""Customer MDM validate CLI command.

Story 7.6-11: Customer Status Field Enhancement
AC-5: Validate updated data distributions

Usage:
    python -m work_data_hub.cli customer-mdm validate
    python -m work_data_hub.cli customer-mdm validate --year 2025
"""

from __future__ import annotations

import argparse
import sys

from structlog import get_logger

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for customer-mdm validate command."""
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli customer-mdm validate",
        description="Validate customer status field distributions (AC-5)",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year to validate (default: latest year)",
    )

    args = parser.parse_args(argv)

    from work_data_hub.customer_mdm.validation import validate_status_distribution

    try:
        print("🔍 Validating customer status distributions...")
        report = validate_status_distribution(status_year=args.year)

        print(f"\n📊 Validation Report for Year {report.status_year}")
        print(f"   Total records: {report.total_records}")
        print("-" * 50)

        for r in report.results:
            status = "✅ PASS" if r.passed else "⚠️ WARN"
            pct = f"{r.actual_value:.1f}%"
            print(f"{status} {r.name}: {pct} (expected: {r.expected_range})")
            print(f"       {r.message}")

        if report.all_passed:
            print("\n✅ All validations passed!")
            return 0
        else:
            print(f"\n⚠️ {len(report.warnings)} validation(s) failed")
            return 0  # Warning only, not error

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
