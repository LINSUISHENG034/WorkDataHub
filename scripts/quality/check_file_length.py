#!/usr/bin/env python
"""Check Python file length to enforce MAX 800 lines limit.

Usage:
    python check_file_length.py --max-lines 800 file1.py file2.py ...

Exit codes:
    0: All files pass
    1: One or more files exceed the limit
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Check file lengths against the specified maximum.

    Returns:
        0 if all files pass, 1 if any file exceeds the limit
    """
    parser = argparse.ArgumentParser(description="Check Python file length limits")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=800,
        help="Maximum allowed number of lines (default: 800)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to check",
    )

    args = parser.parse_args()

    failures: list[tuple[str, int]] = []

    for file_path in args.files:
        try:
            path = Path(file_path)
            # Count lines: count newlines + 1 (for last line if no trailing newline)
            content = path.read_text(encoding="utf-8")
            line_count = content.count("\n") + 1

            if line_count > args.max_lines:
                failures.append((file_path, line_count))
        except Exception as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            return 1

    if failures:
        print("File length violations detected:", file=sys.stderr)
        for file_path, line_count in failures:
            print(
                f"  {file_path}: {line_count} lines (max: {args.max_lines})",
                file=sys.stderr,
            )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
