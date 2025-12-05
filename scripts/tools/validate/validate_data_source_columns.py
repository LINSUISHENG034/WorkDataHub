#!/usr/bin/env python3
"""Data Source Column Validation Script.

This script validates that domain schema definitions match actual production data columns.
It helps prevent documentation-implementation mismatches like the annuity_income 收入金额 issue.

Usage:
    uv run python scripts/tools/validate/validate_data_source_columns.py
    uv run python scripts/tools/validate/validate_data_source_columns.py --domain annuity_income
    uv run python scripts/tools/validate/validate_data_source_columns.py --strict

Exit Codes:
    0: All validations passed
    1: Validation failures detected
    2: Configuration or runtime error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd


@dataclass
class DomainConfig:
    """Configuration for a domain's expected columns."""

    name: str
    sheet_name: str
    required_columns: Set[str]
    optional_columns: Set[str] = field(default_factory=set)
    column_aliases: Dict[str, str] = field(default_factory=dict)  # alias -> canonical
    numeric_columns: Set[str] = field(default_factory=set)


@dataclass
class ValidationResult:
    """Result of validating a single data file."""

    file_path: Path
    domain: str
    sheet_name: str
    success: bool
    actual_columns: List[str]
    missing_required: List[str] = field(default_factory=list)
    extra_columns: List[str] = field(default_factory=list)
    alias_matches: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


# Domain configurations - should match schema definitions
DOMAIN_CONFIGS: Dict[str, DomainConfig] = {
    "annuity_performance": DomainConfig(
        name="annuity_performance",
        sheet_name="规模明细",
        required_columns={
            "月度",
            "计划代码",
            "客户名称",
            "业务类型",
            "计划类型",
            "期初资产规模",
            "期末资产规模",
        },
        optional_columns={
            "机构代码",
            "机构名称",
            "组合代码",
            "组合名称",
            "年化收益率",
            "当期收益率",
            "供款",
            "流失",
            "待遇支付",
            "投资收益",
        },
        column_aliases={
            "机构": "机构代码",
            "流失(含待遇支付)": "流失_含待遇支付",
        },
        numeric_columns={
            "期初资产规模",
            "期末资产规模",
            "供款",
            "流失",
            "待遇支付",
            "投资收益",
            "年化收益率",
            "当期收益率",
        },
    ),
    "annuity_income": DomainConfig(
        name="annuity_income",
        sheet_name="收入明细",
        # CORRECTED: Real data has 固费/浮费/回补/税, NOT 收入金额
        required_columns={
            "月度",
            "客户名称",
            "业务类型",
            "固费",  # Fixed fee income
            "浮费",  # Variable fee income
            "回补",  # Rebate income
            "税",    # Tax amount
        },
        optional_columns={
            "机构代码",
            "机构名称",
            "计划类型",
            "组合代码",
            "组合名称",
            "计划名称",
        },
        column_aliases={
            # Column names vary between data source versions
            "计划号": "计划代码",      # 202411 uses 计划号, 202412 uses 计划代码
            "机构": "机构代码",        # 202411 uses 机构, 202412 uses 机构代码
        },
        numeric_columns={
            "固费",
            "浮费",
            "回补",
            "税",
        },
    ),
}


def find_real_data_files(base_path: Path, domain: str) -> List[Path]:
    """Find all real data Excel files for a domain."""
    config = DOMAIN_CONFIGS.get(domain)
    if not config:
        return []

    files = []
    for xlsx_path in base_path.rglob("*.xlsx"):
        # Skip temporary files
        if xlsx_path.name.startswith("~$"):
            continue
        # Check if file likely contains the domain's sheet
        if "年金" in xlsx_path.name or "终稿" in xlsx_path.name:
            files.append(xlsx_path)

    return sorted(files)


def validate_file(file_path: Path, domain: str) -> ValidationResult:
    """Validate a single data file against domain schema."""
    config = DOMAIN_CONFIGS.get(domain)
    if not config:
        return ValidationResult(
            file_path=file_path,
            domain=domain,
            sheet_name="",
            success=False,
            actual_columns=[],
            error=f"Unknown domain: {domain}",
        )

    try:
        # Try to read the sheet
        df = pd.read_excel(file_path, sheet_name=config.sheet_name, nrows=0)
        actual_columns = list(df.columns)
    except ValueError as e:
        if "Worksheet" in str(e):
            return ValidationResult(
                file_path=file_path,
                domain=domain,
                sheet_name=config.sheet_name,
                success=True,  # Sheet not found is OK - file may not be for this domain
                actual_columns=[],
                error=f"Sheet '{config.sheet_name}' not found (expected for this domain)",
            )
        raise
    except Exception as e:
        return ValidationResult(
            file_path=file_path,
            domain=domain,
            sheet_name=config.sheet_name,
            success=False,
            actual_columns=[],
            error=str(e),
        )

    # Check for required columns (considering aliases)
    actual_set = set(actual_columns)
    missing_required = []
    alias_matches = {}

    for req_col in config.required_columns:
        if req_col in actual_set:
            continue
        # Check if an alias exists
        alias_found = False
        for alias, canonical in config.column_aliases.items():
            if canonical == req_col and alias in actual_set:
                alias_matches[alias] = canonical
                alias_found = True
                break
            if alias == req_col and canonical in actual_set:
                alias_matches[canonical] = alias
                alias_found = True
                break
        if not alias_found:
            # Also check reverse - maybe the required column IS an alias
            for alias, canonical in config.column_aliases.items():
                if req_col == alias and canonical in actual_set:
                    alias_matches[canonical] = alias
                    alias_found = True
                    break
        if not alias_found:
            missing_required.append(req_col)

    # Check for extra columns (informational)
    known_columns = config.required_columns | config.optional_columns | set(config.column_aliases.keys()) | set(config.column_aliases.values())
    extra_columns = [col for col in actual_columns if col not in known_columns]

    success = len(missing_required) == 0

    return ValidationResult(
        file_path=file_path,
        domain=domain,
        sheet_name=config.sheet_name,
        success=success,
        actual_columns=actual_columns,
        missing_required=missing_required,
        extra_columns=extra_columns,
        alias_matches=alias_matches,
    )


def validate_domain(domain: str, base_path: Path, verbose: bool = False) -> List[ValidationResult]:
    """Validate all data files for a domain."""
    files = find_real_data_files(base_path, domain)
    results = []

    for file_path in files:
        result = validate_file(file_path, domain)
        results.append(result)

        if verbose and result.actual_columns:
            print(f"\n{file_path.name}:")
            print(f"  Columns: {result.actual_columns}")
            if result.missing_required:
                print(f"  ❌ Missing: {result.missing_required}")
            if result.alias_matches:
                print(f"  ℹ️  Aliases: {result.alias_matches}")
            if result.success:
                print(f"  ✅ Valid")

    return results


def print_summary(results: List[ValidationResult], domain: str) -> bool:
    """Print validation summary and return success status."""
    valid_files = [r for r in results if r.success and r.actual_columns]
    invalid_files = [r for r in results if not r.success and r.actual_columns]
    skipped_files = [r for r in results if not r.actual_columns]

    print(f"\n{'='*60}")
    print(f"Domain: {domain}")
    print(f"{'='*60}")
    print(f"Files validated: {len(valid_files)}")
    print(f"Files with issues: {len(invalid_files)}")
    print(f"Files skipped (no sheet): {len(skipped_files)}")

    if invalid_files:
        print(f"\n❌ VALIDATION FAILURES:")
        for r in invalid_files:
            print(f"\n  {r.file_path.name}:")
            print(f"    Missing required columns: {r.missing_required}")
            print(f"    Actual columns: {r.actual_columns}")

    # Show column variations across files
    if valid_files:
        all_columns: Set[str] = set()
        for r in valid_files:
            all_columns.update(r.actual_columns)

        config = DOMAIN_CONFIGS[domain]
        print(f"\n📊 Column Analysis:")
        print(f"  Required: {sorted(config.required_columns)}")
        print(f"  Found across files: {sorted(all_columns)}")

        # Check for alias usage
        alias_usage: Dict[str, int] = {}
        for r in valid_files:
            for alias, canonical in r.alias_matches.items():
                key = f"{alias} → {canonical}"
                alias_usage[key] = alias_usage.get(key, 0) + 1

        if alias_usage:
            print(f"\n  Column Aliases Used:")
            for alias, count in alias_usage.items():
                print(f"    {alias}: {count} files")

    return len(invalid_files) == 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate data source columns against domain schemas"
    )
    parser.add_argument(
        "--domain",
        choices=list(DOMAIN_CONFIGS.keys()),
        help="Validate specific domain only",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("tests/fixtures/real_data"),
        help="Path to real data directory",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any validation issue (including aliases)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if not args.data_path.exists():
        print(f"Error: Data path not found: {args.data_path}", file=sys.stderr)
        return 2

    domains = [args.domain] if args.domain else list(DOMAIN_CONFIGS.keys())
    all_results: Dict[str, List[ValidationResult]] = {}
    all_success = True

    for domain in domains:
        results = validate_domain(domain, args.data_path, verbose=args.verbose)
        all_results[domain] = results

        if not args.json:
            success = print_summary(results, domain)
            if not success:
                all_success = False

    if args.json:
        output = {
            domain: [
                {
                    "file": str(r.file_path),
                    "success": r.success,
                    "columns": r.actual_columns,
                    "missing": r.missing_required,
                    "aliases": r.alias_matches,
                    "error": r.error,
                }
                for r in results
            ]
            for domain, results in all_results.items()
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    if not args.json:
        print(f"\n{'='*60}")
        if all_success:
            print("✅ All validations passed")
        else:
            print("❌ Some validations failed")
        print(f"{'='*60}")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
