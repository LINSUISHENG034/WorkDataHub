"""
Domain-Agnostic Cleaner Comparison Script.

Compares Legacy cleaner output against New Pipeline output for any configured domain.
Uses a configuration-driven architecture where each domain defines its validation rules.

Usage:
    # Auto-discovery mode (recommended)
    PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py \
        --domain annuity_performance --month 202311 --limit 100

    # Manual file mode
    PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py \
        --domain annuity_performance data/202412_annuity.xlsx --limit 100

    # With deterministic export (for reproducible comparisons)
    PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py \
        --domain annuity_performance --month 202311 --limit 100 --export --run-id baseline-202311

See docs/guides/validation/cleaner-comparison-usage-guide.md for full documentation.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

# Add script directory to path for local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Add legacy paths for imports (lazy, only when needed)
LEGACY_PATH = SCRIPT_DIR.parent.parent.parent / "legacy"
LEGACY_ANNUITY_HUB_PATH = LEGACY_PATH / "annuity_hub"
sys.path.insert(0, str(LEGACY_PATH))
sys.path.insert(0, str(LEGACY_ANNUITY_HUB_PATH))

# Local imports - configuration-driven
from configs import DOMAIN_CONFIGS, get_domain_config
from domain_config import (
    ARTIFACTS_DIR,
    CLASSIFICATION_NEEDS_REVIEW,
    CLASSIFICATION_REGRESSION_MISMATCH,
    CLASSIFICATION_REGRESSION_MISSING,
    CLASSIFICATION_UPGRADE_EQC_RESOLVED,
    CLASSIFICATION_UPGRADE_NAME_CLEANING,
    DEBUG_SNAPSHOTS_SUBDIR,
    DEFAULT_ROW_LIMIT,
    INVALID_COMPANY_ID_VALUES,
)
from report_generator import (
    ComparisonReport,
    DerivedDiff,
    NumericDiff,
    UpgradeDiff,
    generate_csv_report,
    generate_markdown_summary,
    print_report,
    save_debug_snapshots,
)

if TYPE_CHECKING:
    from configs.base import DomainComparisonConfig


# =============================================================================
# Auto-Discovery (Epic 3: Version-Aware File Discovery)
# =============================================================================


def discover_source_file(month: str, domain: str) -> tuple:
    """
    Discover source file using New Pipeline's FileDiscoveryService.

    Args:
        month: Month in YYYYMM format (e.g., '202311')
        domain: Domain name for file discovery config

    Returns:
        Tuple of (file_path, sheet_name)

    Raises:
        SystemExit: If discovery fails
    """
    import re

    # Validate month format
    if not re.match(r'^\d{6}$', month):
        print(f"❌ Invalid month format: {month}")
        print("   Expected format: YYYYMM (e.g., 202311)")
        sys.exit(1)

    try:
        from work_data_hub.io.connectors.file_connector import FileDiscoveryService

        print(f"🔍 Auto-discovering source file for domain '{domain}', month {month}...")
        discovery_service = FileDiscoveryService()
        result = discovery_service.discover_file(
            domain=domain,
            month=month,
        )

        print(f"   ✓ Discovered: {result.file_path.name}")
        print(f"   ✓ Version: {result.version}")
        print(f"   ✓ Sheet: {result.sheet_name}")

        return str(result.file_path), result.sheet_name

    except Exception as e:
        print(f"❌ Auto-discovery failed: {e}")
        print(f"\n💡 Please specify the file path manually:")
        print(f"   python cleaner_compare.py --domain {domain} <excel_path> --limit 100")
        sys.exit(1)


# =============================================================================
# Token Validation (Story 6.2-P11: Auto-refresh for validation scripts)
# =============================================================================


def _validate_and_refresh_token(auto_refresh: bool = True) -> bool:
    """
    Validate EQC token at script startup and auto-refresh if invalid.

    Args:
        auto_refresh: If True, auto-refresh token when validation fails.

    Returns:
        True if token is valid (or was successfully refreshed), False otherwise.
    """
    import os

    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token

    try:
        settings = get_settings()
        token = settings.eqc_token
        base_url = settings.eqc_base_url

        if not token:
            print("⚠️  No EQC token configured (WDH_EQC_TOKEN not set)")
            if not auto_refresh:
                print("   Continuing without token (EQC lookup will be disabled)")
                return True
            print("   Attempting to refresh token via QR login...")
            return _trigger_token_refresh()

        # Validate existing token
        print("🔐 Validating EQC token...", end=" ", flush=True)
        if validate_eqc_token(token, base_url):
            print("✅ Token valid")
            return True

        # Token is invalid
        print("❌ Token invalid/expired")

        if not auto_refresh:
            print("⚠️  Auto-refresh disabled (--no-auto-refresh-token)")
            print("   Run: python -m work_data_hub.cli auth refresh")
            return True  # Continue without valid token

        print("   Attempting to refresh token via QR login...")
        return _trigger_token_refresh()

    except Exception as e:
        print(f"⚠️  Token validation error: {e}")
        return True  # Continue anyway to avoid blocking script


def _trigger_token_refresh() -> bool:
    """Trigger automatic token refresh via QR login."""
    import os

    try:
        from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

        token = run_get_token_auto_qr(save_to_env=True, timeout_seconds=180)
        if token:
            print("✅ Token refreshed successfully")
            os.environ["WDH_EQC_TOKEN"] = token
            try:
                from work_data_hub.config.settings import get_settings

                get_settings.cache_clear()
            except Exception:
                pass
            return True
        else:
            print("❌ Token refresh failed")
            print("   Please run manually: python -m work_data_hub.cli auth refresh")
            return False
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return False


# =============================================================================
# Cleaner Executors
# =============================================================================


def run_legacy_cleaner(
    config: "DomainComparisonConfig",
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Execute Legacy cleaner for the specified domain.

    Args:
        config: Domain comparison configuration
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration

    Returns:
        Cleaned DataFrame from Legacy cleaner

    Raises:
        ImportError: If Legacy dependencies are not installed
    """
    try:
        cleaner_class = config.get_legacy_cleaner()
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        print(f"\n❌ Legacy Cleaner Import Error: {e}")
        print(f"\n📦 The Legacy system requires additional dependencies.")
        print(f"   Missing module: {missing_module}")
        print(f"\n💡 Options:")
        print(f"   1. Install legacy dependencies")
        print(f"   2. Use --new-only mode to run only the New Pipeline:")
        print(f"      python cleaner_compare.py --domain {config.domain_name} <excel_path> --new-only")
        print("")
        raise ImportError(f"Legacy dependencies not available: {missing_module}") from e

    cleaner = cleaner_class(excel_path, sheet_name=sheet_name)
    df = cleaner.clean()

    # Validate that Legacy cleaner returned data
    if len(df) == 0:
        print(f"\n❌ Legacy Cleaner returned 0 rows!")
        print(f"   This usually indicates an internal cleaner error.")
        print(f"\n💡 Options:")
        print(f"   1. Check if the Excel file contains the expected columns")
        print(f"   2. Use --new-only mode to skip Legacy comparison")
        print("")
        raise RuntimeError("Legacy cleaner returned empty DataFrame - internal error")

    if row_limit and row_limit > 0:
        df = df.head(row_limit)

    return df


def run_new_pipeline(
    config: "DomainComparisonConfig",
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
    enable_enrichment: bool = False,
    sync_lookup_budget: int = 1000,
) -> pd.DataFrame:
    """
    Execute New Pipeline for the specified domain.

    Args:
        config: Domain comparison configuration
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration
        enable_enrichment: Whether to enable EQC enrichment service
        sync_lookup_budget: Budget for EQC sync lookups

    Returns:
        Cleaned DataFrame from New Pipeline
    """
    return config.build_new_pipeline(
        excel_path=excel_path,
        sheet_name=sheet_name,
        row_limit=row_limit,
        enable_enrichment=enable_enrichment,
        sync_lookup_budget=sync_lookup_budget,
    )


# =============================================================================
# Comparison Functions
# =============================================================================


def _is_blank_value(value: Any) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in {"none", "nan"}


def _try_parse_decimal(value: Any) -> tuple[Optional[Decimal], bool]:
    """
    Convert value to Decimal for numeric comparison.

    Rules:
    - NULL/empty are treated as None (later normalized to 0 for comparison).
    - Invalid numerics are flagged (invalid=True) and MUST be treated as critical.
    """
    if _is_blank_value(value):
        return None, False

    text = str(value).strip()
    try:
        return Decimal(text), False
    except (InvalidOperation, ValueError):
        return None, True


def _normalize_derived_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_type):
        return value.isoformat()
    return str(value).strip()


def compare_numeric_fields(
    config: "DomainComparisonConfig",
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[NumericDiff]:
    """
    Compare numeric fields with zero tolerance.

    NULL and 0 are treated as equivalent (not a difference).
    Uses Decimal for precise comparison.
    """
    diffs: List[NumericDiff] = []

    EXCEL_ROW_OFFSET = 2

    if len(legacy_df) != len(new_df):
        diffs.append(
            NumericDiff(
                field="__row_count__",
                diff_type="ROW_COUNT_MISMATCH",
                diff_count=abs(len(legacy_df) - len(new_df)),
                examples=[
                    {
                        "legacy_row_count": len(legacy_df),
                        "new_row_count": len(new_df),
                    }
                ],
            )
        )

    for legacy_col in config.numeric_fields:
        new_col = config.get_column_mapping(legacy_col)

        legacy_has = legacy_col in legacy_df.columns
        new_has = new_col in new_df.columns

        if not legacy_has or not new_has:
            diffs.append(
                NumericDiff(
                    field=legacy_col,
                    diff_type="COLUMN_MISSING",
                    diff_count=0,
                    examples=[
                        {
                            "legacy_has_column": legacy_has,
                            "new_has_column": new_has,
                            "new_column_name": new_col,
                        }
                    ],
                )
            )
            continue

        min_len = min(len(legacy_df), len(new_df))
        invalid_examples: List[Dict[str, Any]] = []
        mismatch_examples: List[Dict[str, Any]] = []

        for idx in range(min_len):
            legacy_raw = legacy_df.iloc[idx].get(legacy_col, None)
            new_raw = new_df.iloc[idx].get(new_col, None)

            legacy_dec, legacy_invalid = _try_parse_decimal(legacy_raw)
            new_dec, new_invalid = _try_parse_decimal(new_raw)

            if legacy_invalid or new_invalid:
                invalid_examples.append(
                    {
                        "row": idx + EXCEL_ROW_OFFSET,
                        "legacy_raw": "" if _is_blank_value(legacy_raw) else str(legacy_raw),
                        "new_raw": "" if _is_blank_value(new_raw) else str(new_raw),
                    }
                )
                continue

            legacy_val = legacy_dec if legacy_dec is not None else Decimal(0)
            new_val = new_dec if new_dec is not None else Decimal(0)

            if legacy_val != new_val:
                mismatch_examples.append(
                    {
                        "row": idx + EXCEL_ROW_OFFSET,
                        "legacy_value": str(legacy_val),
                        "new_value": str(new_val),
                    }
                )

        if invalid_examples:
            diffs.append(
                NumericDiff(
                    field=legacy_col,
                    diff_type="INVALID_NUMERIC_VALUE",
                    diff_count=len(invalid_examples),
                    examples=invalid_examples[:5],
                )
            )

        if mismatch_examples:
            diffs.append(
                NumericDiff(
                    field=legacy_col,
                    diff_type="CRITICAL_NUMERIC_MISMATCH",
                    diff_count=len(mismatch_examples),
                    examples=mismatch_examples[:5],
                )
            )

    return diffs


def compare_derived_fields(
    config: "DomainComparisonConfig",
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[DerivedDiff]:
    """Compare derived fields (mappings, transformations)."""
    diffs: List[DerivedDiff] = []

    EXCEL_ROW_OFFSET = 2

    for col in config.derived_fields:
        if col not in legacy_df.columns or col not in new_df.columns:
            continue

        legacy_vals = legacy_df[col].apply(_normalize_derived_value)
        new_vals = new_df[col].apply(_normalize_derived_value)

        min_len = min(len(legacy_vals), len(new_vals))
        diff_indices = []

        for idx in range(min_len):
            if legacy_vals.iloc[idx] != new_vals.iloc[idx]:
                diff_indices.append(idx)

        if diff_indices:
            examples = [
                {
                    "row": idx + EXCEL_ROW_OFFSET,
                    "legacy_value": legacy_vals.iloc[idx],
                    "new_value": new_vals.iloc[idx],
                }
                for idx in diff_indices[:5]
            ]

            diffs.append(
                DerivedDiff(
                    field=col,
                    diff_count=len(diff_indices),
                    examples=examples,
                )
            )

    return diffs


def classify_company_id_diff(legacy_val: str, new_val: str) -> str:
    """
    Classify company_id difference.

    Classifications:
    - upgrade_eqc_resolved: New resolved via EQC/DB when Legacy failed
    - regression_missing_resolution: Legacy was numeric, New is temp ID
    - regression_company_id_mismatch: Both numeric but different
    - needs_review: Cannot be automatically classified
    """
    legacy_val = legacy_val.strip() if legacy_val else ""
    new_val = new_val.strip() if new_val else ""

    legacy_is_numeric = legacy_val.isdigit() and len(legacy_val) > 1
    new_is_numeric = new_val.isdigit() and len(new_val) > 1

    legacy_is_temp = legacy_val.startswith("IN")
    legacy_is_invalid = legacy_val in INVALID_COMPANY_ID_VALUES or legacy_val == ""
    legacy_is_empty_or_invalid = legacy_is_temp or legacy_is_invalid or not legacy_is_numeric

    new_is_temp = new_val.startswith("IN")

    # Case 1: New resolved successfully, Legacy was empty/invalid/temp
    if new_is_numeric and legacy_is_empty_or_invalid:
        return CLASSIFICATION_UPGRADE_EQC_RESOLVED

    # Case 2: Legacy had valid ID, New is temp ID - REGRESSION
    if legacy_is_numeric and new_is_temp:
        return CLASSIFICATION_REGRESSION_MISSING

    # Case 3: Both numeric but different - REGRESSION
    if legacy_is_numeric and new_is_numeric and legacy_val != new_val:
        return CLASSIFICATION_REGRESSION_MISMATCH

    # Case 4: Both are temp IDs but different
    if legacy_is_temp and new_is_temp and legacy_val != new_val:
        return CLASSIFICATION_NEEDS_REVIEW

    return CLASSIFICATION_NEEDS_REVIEW


def compare_upgrade_fields(
    config: "DomainComparisonConfig",
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[UpgradeDiff]:
    """Compare upgrade fields with classification."""
    diffs: List[UpgradeDiff] = []

    EXCEL_ROW_OFFSET = 2

    # Company ID comparison
    if "company_id" in legacy_df.columns and "company_id" in new_df.columns:
        min_len = min(len(legacy_df), len(new_df))

        for idx in range(min_len):
            legacy_raw = legacy_df.iloc[idx].get("company_id", "")
            new_raw = new_df.iloc[idx].get("company_id", "")
            legacy_val = "" if pd.isna(legacy_raw) else str(legacy_raw)
            new_val = "" if pd.isna(new_raw) else str(new_raw)

            if legacy_val != new_val:
                classification = classify_company_id_diff(legacy_val, new_val)
                diffs.append(
                    UpgradeDiff(
                        field="company_id",
                        row=idx + EXCEL_ROW_OFFSET,
                        legacy_value=legacy_val,
                        new_value=new_val,
                        classification=classification,
                    )
                )

    # Customer name comparison (if in upgrade_fields)
    if "客户名称" in config.upgrade_fields:
        if "客户名称" in legacy_df.columns and "客户名称" in new_df.columns:
            min_len = min(len(legacy_df), len(new_df))

            for idx in range(min_len):
                legacy_raw = legacy_df.iloc[idx].get("客户名称", "")
                new_raw = new_df.iloc[idx].get("客户名称", "")
                legacy_val = "" if pd.isna(legacy_raw) else str(legacy_raw)
                new_val = "" if pd.isna(new_raw) else str(new_raw)

                if legacy_val != new_val:
                    classification = CLASSIFICATION_UPGRADE_NAME_CLEANING if new_val else CLASSIFICATION_NEEDS_REVIEW
                    diffs.append(
                        UpgradeDiff(
                            field="客户名称",
                            row=idx + EXCEL_ROW_OFFSET,
                            legacy_value=legacy_val[:50],
                            new_value=new_val[:50],
                            classification=classification,
                        )
                    )

    return diffs


# =============================================================================
# Main Comparison Function
# =============================================================================


def run_comparison(
    config: "DomainComparisonConfig",
    excel_path: str,
    sheet_name: str,
    row_limit: int,
    enable_enrichment: bool = False,
    sync_lookup_budget: int = 1000,
    save_debug: bool = False,
    run_id: Optional[str] = None,
) -> tuple:
    """
    Run full comparison between Legacy and New Pipeline cleaners.

    Returns:
        Tuple of (ComparisonReport, run_id)
    """
    start_time = time.perf_counter()

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"🔄 Running Legacy cleaner...")
    legacy_df = run_legacy_cleaner(config, excel_path, sheet_name, row_limit)

    print(f"🔄 Running New Pipeline...")
    new_df = run_new_pipeline(
        config, excel_path, sheet_name, row_limit, enable_enrichment, sync_lookup_budget
    )

    if save_debug:
        save_debug_snapshots(legacy_df, new_df, run_id=run_id)

    print(f"🔍 Comparing numeric fields...")
    numeric_diffs = compare_numeric_fields(config, legacy_df, new_df)

    print(f"🔍 Comparing derived fields...")
    derived_diffs = compare_derived_fields(config, legacy_df, new_df)

    print(f"🔍 Comparing upgrade fields...")
    upgrade_diffs = compare_upgrade_fields(config, legacy_df, new_df)

    execution_time_ms = int((time.perf_counter() - start_time) * 1000)

    report = ComparisonReport(
        excel_path=excel_path,
        sheet_name=sheet_name,
        row_limit=row_limit,
        legacy_row_count=len(legacy_df),
        new_row_count=len(new_df),
        legacy_column_count=len(legacy_df.columns),
        new_column_count=len(new_df.columns),
        numeric_diffs=numeric_diffs,
        derived_diffs=derived_diffs,
        upgrade_diffs=upgrade_diffs,
        execution_time_ms=execution_time_ms,
    )

    return report, run_id


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    # Get available domains for help text
    available_domains = list(DOMAIN_CONFIGS.keys())

    parser = argparse.ArgumentParser(
        description="Compare Legacy vs New Pipeline cleaners for any configured domain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Auto-discovery mode (recommended)
  python cleaner_compare.py --domain annuity_performance --month 202311 --limit 100

  # Manual mode - specify file path directly
  python cleaner_compare.py --domain annuity_performance data/202412_annuity.xlsx --limit 100

  # Full dataset with enrichment and export
  python cleaner_compare.py --domain annuity_performance --month 202311 --limit 0 --enrichment --export

  # Deterministic export for reproducible comparisons
  python cleaner_compare.py --domain annuity_performance --month 202311 --export --run-id baseline-202311

  # New Pipeline only (no Legacy dependencies needed)
  python cleaner_compare.py --domain annuity_performance --month 202311 --new-only --debug

Available domains: {', '.join(available_domains)}
        """,
    )
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        choices=available_domains,
        help=f"Domain to compare (choices: {', '.join(available_domains)})",
    )
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=None,
        help="Path to Excel file (optional if --month is used)",
    )
    parser.add_argument(
        "--month",
        type=str,
        help="Month in YYYYMM format for auto-discovery (e.g., 202311)",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Sheet name to process (default: domain-specific)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_ROW_LIMIT,
        help=f"Row limit for iteration (default: {DEFAULT_ROW_LIMIT}, 0 = no limit)",
    )
    parser.add_argument(
        "--enrichment",
        action="store_true",
        help="Enable EQC enrichment service (default: disabled)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save debug snapshots (CSV exports of both outputs)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export detailed CSV report and Markdown summary",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Run only New Pipeline (skip Legacy, no comparison)",
    )
    parser.add_argument(
        "--no-auto-refresh-token",
        action="store_true",
        help="Disable automatic token refresh when --enrichment is enabled",
    )
    parser.add_argument(
        "--sync-budget",
        type=int,
        default=1000,
        help="EQC sync lookup budget (default: 1000, 0 = disabled)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Custom run ID for deterministic export directory naming (default: timestamp)",
    )

    args = parser.parse_args()

    # Load domain configuration
    config = get_domain_config(args.domain)
    print(f"📋 Domain: {config.domain_name}")

    # Determine sheet name
    sheet_name = args.sheet if args.sheet else config.sheet_name

    # Determine file source: auto-discovery or manual path
    if args.month:
        # Auto-discovery mode
        excel_path_str, discovered_sheet = discover_source_file(args.month, config.domain_name)
        excel_path = Path(excel_path_str)
        # Use discovered sheet unless user explicitly specified one
        if not args.sheet:
            sheet_name = discovered_sheet
    elif args.excel_path:
        # Manual mode
        excel_path = Path(args.excel_path)
        if not excel_path.exists():
            print(f"❌ Error: File not found: {excel_path}")
            sys.exit(1)
    else:
        print("❌ Error: Either --month or excel_path is required")
        print(f"   Usage: python cleaner_compare.py --domain {args.domain} --month 202311")
        print(f"   Or:    python cleaner_compare.py --domain {args.domain} <file_path>")
        sys.exit(1)

    # Performance warning for full dataset (Hard Constraint #4)
    if args.limit == 0:
        print("⚠️  Warning: --limit 0 runs on full dataset. This may be slow and memory-intensive.")

    # Token validation: only when --enrichment is requested
    if args.enrichment:
        auto_refresh = not getattr(args, "no_auto_refresh_token", False)
        _validate_and_refresh_token(auto_refresh=auto_refresh)

    # Use provided run_id or generate one
    run_id = args.run_id if args.run_id else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # New-only mode: just run and display New Pipeline output
    if args.new_only:
        print(f"🔄 Running New Pipeline only (--new-only mode)...")
        new_df = run_new_pipeline(
            config=config,
            excel_path=str(excel_path),
            sheet_name=sheet_name,
            row_limit=args.limit,
            enable_enrichment=args.enrichment,
            sync_lookup_budget=args.sync_budget,
        )
        print(f"\n✅ New Pipeline completed:")
        print(f"   Rows: {len(new_df)}")
        print(f"   Columns: {len(new_df.columns)}")
        print(f"   Columns: {list(new_df.columns)}")
        if args.debug:
            run_dir = ARTIFACTS_DIR / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            snapshots_dir = run_dir / DEBUG_SNAPSHOTS_SUBDIR
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            output_path = snapshots_dir / "new_pipeline_output.csv"
            new_df.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"   Saved to: {snapshots_dir}")
        sys.exit(0)

    report, run_id = run_comparison(
        config=config,
        excel_path=str(excel_path),
        sheet_name=sheet_name,
        row_limit=args.limit,
        enable_enrichment=args.enrichment,
        sync_lookup_budget=args.sync_budget,
        save_debug=args.debug,
        run_id=run_id,
    )

    print_report(report)

    # Export reports if requested
    if args.export:
        csv_path = generate_csv_report(report, run_id=run_id)
        md_path = generate_markdown_summary(report, run_id=run_id)
        print(f"📄 Reports exported to: {csv_path.parent}")
        print(f"   - {csv_path.name}")
        print(f"   - {md_path.name}")

    # Exit with error code if critical issues found
    sys.exit(1 if report.has_critical_issues else 0)


if __name__ == "__main__":
    main()
