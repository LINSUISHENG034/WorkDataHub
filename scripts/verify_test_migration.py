"""Test migration verification tool.

Collects pytest test IDs as a baseline before migration,
then verifies no tests were lost after migration.

Usage:
    PYTHONPATH=src uv run python scripts/verify_test_migration.py collect
    PYTHONPATH=src uv run python scripts/verify_test_migration.py verify
    PYTHONPATH=src uv run python scripts/verify_test_migration.py verify --strict
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASELINE_FILE = Path("tests/.migration_baseline.txt")
PROJECT_ROOT = Path(__file__).parent.parent

_MAX_MOVED_DISPLAY = 20
_MAX_ADDED_DISPLAY = 10


def _collect_test_ids() -> list[str]:
    """Run pytest --co -q and return sorted test node IDs."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q", "--no-header"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and "::" in line
    ]
    return sorted(lines)


def _normalize_test_id(test_id: str) -> str:
    """Extract the test function name, ignoring directory path.

    This allows detecting when a test was moved (path changed)
    but the test function itself still exists.
    """
    # tests/domain/foo/test_bar.py::test_baz -> test_bar.py::test_baz
    if "::" in test_id:
        file_part, func_part = test_id.rsplit("::", 1)
        filename = Path(file_part).name
        return f"{filename}::{func_part}"
    return test_id


def cmd_collect(args: argparse.Namespace) -> int:
    """Collect baseline test IDs and save to file."""
    print("Collecting test IDs...")
    test_ids = _collect_test_ids()

    if not test_ids:
        print("ERROR: No tests collected. Check pytest configuration.")
        return 1

    BASELINE_FILE.write_text("\n".join(test_ids) + "\n", encoding="utf-8")
    print(f"Saved {len(test_ids)} test IDs to {BASELINE_FILE}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify current tests against baseline."""
    if not BASELINE_FILE.exists():
        print(f"ERROR: No baseline found at {BASELINE_FILE}")
        print("Run 'collect' first.")
        return 1

    baseline = set(BASELINE_FILE.read_text(encoding="utf-8").splitlines())
    baseline.discard("")

    print("Collecting current test IDs...")
    current_ids = _collect_test_ids()
    current = set(current_ids)

    # Exact path comparison
    lost = sorted(baseline - current)
    added = sorted(current - baseline)

    # Normalized comparison (detect moves vs true losses)
    baseline_norm = {_normalize_test_id(t) for t in baseline}
    current_norm = {_normalize_test_id(t) for t in current}
    truly_lost = sorted(baseline_norm - current_norm)
    moved = [t for t in lost if _normalize_test_id(t) not in truly_lost]

    # Report
    print(f"\n{'=' * 60}")
    print("MIGRATION VERIFICATION REPORT")
    print(f"{'=' * 60}")
    print(f"Baseline tests:  {len(baseline)}")
    print(f"Current tests:   {len(current)}")
    print(f"Moved (OK):      {len(moved)}")
    print(f"Truly lost:      {len(truly_lost)}")
    print(f"New tests:       {len(added)}")

    if moved:
        print("\n--- Moved (path changed, test preserved) ---")
        for t in moved[:_MAX_MOVED_DISPLAY]:
            print(f"  {t}")
        if len(moved) > _MAX_MOVED_DISPLAY:
            print(f"  ... and {len(moved) - _MAX_MOVED_DISPLAY} more")

    if truly_lost:
        print("\n--- TRULY LOST (not found anywhere) ---")
        for t in truly_lost:
            print(f"  LOST: {t}")

    if added:
        print("\n--- New tests ---")
        for t in added[:_MAX_ADDED_DISPLAY]:
            print(f"  NEW: {t}")
        if len(added) > _MAX_ADDED_DISPLAY:
            print(f"  ... and {len(added) - _MAX_ADDED_DISPLAY} more")

    # Exit code logic
    if truly_lost:
        print(f"\nFAILED: {len(truly_lost)} tests truly lost!")
        return 1

    if args.strict and len(current) < len(baseline):
        print("\nFAILED (strict): test count decreased")
        return 1

    print("\nPASSED: No tests lost.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Test migration verification tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("collect", help="Collect baseline test IDs")

    verify_p = sub.add_parser("verify", help="Verify against baseline")
    verify_p.add_argument(
        "--strict",
        action="store_true",
        help="Fail if total test count decreased",
    )

    args = parser.parse_args()

    if args.command == "collect":
        return cmd_collect(args)
    elif args.command == "verify":
        return cmd_verify(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
