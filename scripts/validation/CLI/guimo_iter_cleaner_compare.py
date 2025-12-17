"""
Annuity Performance Cleaner Comparison Script

Compares Legacy AnnuityPerformanceCleaner output against New Pipeline output
using the same input data, enabling row-by-row comparison without join keys.

Usage:
    # From project root:
    PYTHONPATH=src uv run python scripts/validation/CLI/guimo_iter_cleaner_compare.py <excel_path> [--sheet SHEET] [--limit N]

    # PowerShell:
    $env:PYTHONPATH='src'; uv run python scripts/validation/CLI/guimo_iter_cleaner_compare.py <excel_path> --limit 100

Example:
    $env:PYTHONPATH='src'; uv run python scripts/validation/CLI/guimo_iter_cleaner_compare.py "data/202412_annuity.xlsx" --limit 100
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Add script directory to path for local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Add legacy paths for imports
# Legacy code is structured as: legacy/annuity_hub/data_handler/data_cleaner.py
# and uses internal imports like: from common_utils.common_utils import ...
LEGACY_PATH = SCRIPT_DIR.parent.parent.parent / "legacy"
LEGACY_ANNUITY_HUB_PATH = LEGACY_PATH / "annuity_hub"
sys.path.insert(0, str(LEGACY_PATH))
sys.path.insert(0, str(LEGACY_ANNUITY_HUB_PATH))

# Local imports
from guimo_iter_config import (
    CLASSIFICATION_NEEDS_REVIEW,
    CLASSIFICATION_REGRESSION_MISMATCH,
    CLASSIFICATION_REGRESSION_MISSING,
    CLASSIFICATION_UPGRADE_EQC_RESOLVED,
    CLASSIFICATION_UPGRADE_NAME_CLEANING,
    COLUMN_NAME_MAPPING,
    DEFAULT_ROW_LIMIT,
    DEFAULT_SHEET_NAME,
    DERIVED_FIELDS,
    INVALID_COMPANY_ID_VALUES,
    NUMERIC_FIELDS,
    UPGRADE_FIELDS,
)
from guimo_iter_report_generator import (
    ComparisonReport,
    DerivedDiff,
    NumericDiff,
    UpgradeDiff,
    generate_csv_report,
    generate_markdown_summary,
    print_report,
    save_debug_snapshots,
)


# =============================================================================
# Cleaner Executors
# =============================================================================


def run_legacy_cleaner(
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Execute Legacy AnnuityPerformanceCleaner.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration

    Returns:
        Cleaned DataFrame from Legacy cleaner

    Raises:
        ImportError: If Legacy dependencies are not installed
    """
    try:
        from annuity_hub.data_handler.data_cleaner import AnnuityPerformanceCleaner
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        print(f"\n❌ Legacy Cleaner Import Error: {e}")
        print(f"\n📦 The Legacy system requires additional dependencies.")
        print(f"   Missing module: {missing_module}")
        print(f"\n💡 Options:")
        print(f"   1. Install legacy dependencies:")
        print(f"      uv pip install -r legacy/annuity_hub/requirements.txt")
        print(
            "      (Note: legacy requirements may reference internal indexes; "
            "use --new-only if install fails.)"
        )
        print(f"   2. Use --new-only mode to run only the New Pipeline:")
        print(f"      python guimo_iter_cleaner_compare.py <excel_path> --new-only")
        print("")
        raise ImportError(f"Legacy dependencies not available: {missing_module}") from e

    cleaner = AnnuityPerformanceCleaner(excel_path, sheet_name=sheet_name)
    df = cleaner.clean()

    if row_limit and row_limit > 0:
        df = df.head(row_limit)

    return df


def run_new_pipeline(
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
    enable_enrichment: bool = False,
    sync_lookup_budget: int = 50,
) -> pd.DataFrame:
    """
    Execute New Pipeline cleaner with full company ID resolution.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration
        enable_enrichment: Whether to enable EQC enrichment service (default: False)
        sync_lookup_budget: Budget for EQC sync lookups (default: 50)

    Returns:
        Cleaned DataFrame from New Pipeline
    """
    from work_data_hub.config.settings import get_settings
    from work_data_hub.domain.annuity_performance.pipeline_builder import (
        build_bronze_to_silver_pipeline,
        load_plan_override_mapping,
    )
    from work_data_hub.domain.pipelines.types import PipelineContext

    # Load raw data (same as Legacy cleaner input)
    raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)

    if row_limit and row_limit > 0:
        raw_df = raw_df.head(row_limit)

    # Load plan override mapping from YAML
    plan_override_mapping = load_plan_override_mapping()

    # Get mapping repository for database cache lookup
    mapping_repository = None
    enrichment_service = None

    if enable_enrichment:
        try:
            from work_data_hub.infrastructure.database.connection import get_engine
            from work_data_hub.infrastructure.enrichment.mapping_repository import (
                CompanyMappingRepository,
            )

            engine = get_engine()
            mapping_repository = CompanyMappingRepository(engine)
            print(f"   ✓ Database mapping repository enabled")
        except Exception as e:
            print(f"   ⚠️ Database connection failed: {e}")

    # Build pipeline with full company ID resolution support
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=enrichment_service,  # EQC via eqc_provider auto-creation
        plan_override_mapping=plan_override_mapping,
        sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
        mapping_repository=mapping_repository,
    )

    # Create context
    context = PipelineContext(
        pipeline_name="cleaner_comparison",
        execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={},
        domain="annuity_performance",
        run_id="compare",
        extra={},
    )

    return pipeline.execute(raw_df.copy(), context)


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
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[NumericDiff]:
    """
    Compare numeric fields with zero tolerance.

    NULL and 0 are treated as equivalent (not a difference).
    Uses Decimal for precise comparison.

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of numeric differences found
    """
    diffs: List[NumericDiff] = []

    # Row alignment is foundational for row-by-row comparison.
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

    for legacy_col in NUMERIC_FIELDS:
        # Handle column name mapping
        new_col = COLUMN_NAME_MAPPING.get(legacy_col, legacy_col)

        # Check column existence
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
                        "row": idx,
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
                        "row": idx,
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
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[DerivedDiff]:
    """
    Compare derived fields (mappings, transformations).

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of derived field differences found
    """
    diffs: List[DerivedDiff] = []

    for col in DERIVED_FIELDS:
        if col not in legacy_df.columns or col not in new_df.columns:
            continue

        # Normalize values for comparison (avoid NaN -> "nan" false positives).
        legacy_vals = legacy_df[col].apply(_normalize_derived_value)
        new_vals = new_df[col].apply(_normalize_derived_value)

        # Find differences
        min_len = min(len(legacy_vals), len(new_vals))
        diff_indices = []

        for idx in range(min_len):
            if legacy_vals.iloc[idx] != new_vals.iloc[idx]:
                diff_indices.append(idx)

        if diff_indices:
            examples = [
                {
                    "row": idx,
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
    - upgrade_resolved: New resolved to numeric, Legacy was temp/empty/invalid
    - upgrade_eqc_resolved: (alias) New resolved via EQC/DB when Legacy failed
    - regression_missing_resolution: Legacy was numeric, New is temp ID
    - regression_company_id_mismatch: Both numeric but different
    - needs_review: Cannot be automatically classified

    Args:
        legacy_val: Legacy company_id value
        new_val: New Pipeline company_id value

    Returns:
        Classification string
    """
    # Normalize values
    legacy_val = legacy_val.strip() if legacy_val else ""
    new_val = new_val.strip() if new_val else ""

    # Check if values are valid numeric company IDs
    legacy_is_numeric = legacy_val.isdigit() and len(legacy_val) > 1
    new_is_numeric = new_val.isdigit() and len(new_val) > 1

    # Check for temp IDs and invalid values
    legacy_is_temp = legacy_val.startswith("IN")
    legacy_is_invalid = legacy_val in INVALID_COMPANY_ID_VALUES or legacy_val == ""
    legacy_is_empty_or_invalid = legacy_is_temp or legacy_is_invalid or not legacy_is_numeric

    new_is_temp = new_val.startswith("IN")

    # Case 1: New resolved successfully, Legacy was empty/invalid/temp
    # This is an UPGRADE - New Pipeline is doing better!
    if new_is_numeric and legacy_is_empty_or_invalid:
        return CLASSIFICATION_UPGRADE_EQC_RESOLVED

    # Case 2: Legacy had valid ID, New is temp ID - REGRESSION
    if legacy_is_numeric and new_is_temp:
        return CLASSIFICATION_REGRESSION_MISSING

    # Case 3: Both numeric but different - REGRESSION (possible data issue)
    if legacy_is_numeric and new_is_numeric and legacy_val != new_val:
        return CLASSIFICATION_REGRESSION_MISMATCH

    # Case 4: Both are temp IDs but different - needs review
    if legacy_is_temp and new_is_temp and legacy_val != new_val:
        return CLASSIFICATION_NEEDS_REVIEW

    return CLASSIFICATION_NEEDS_REVIEW


def compare_upgrade_fields(
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[UpgradeDiff]:
    """
    Compare upgrade fields with classification.

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of upgrade field differences with classifications
    """
    diffs: List[UpgradeDiff] = []

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
                        row=idx,
                        legacy_value=legacy_val,
                        new_value=new_val,
                        classification=classification,
                    )
                )

    # Customer name comparison (simplified - just flag differences)
    if "客户名称" in legacy_df.columns and "客户名称" in new_df.columns:
        min_len = min(len(legacy_df), len(new_df))

        for idx in range(min_len):
            legacy_raw = legacy_df.iloc[idx].get("客户名称", "")
            new_raw = new_df.iloc[idx].get("客户名称", "")
            legacy_val = "" if pd.isna(legacy_raw) else str(legacy_raw)
            new_val = "" if pd.isna(new_raw) else str(new_raw)

            if legacy_val != new_val:
                # Simple classification for customer name
                classification = CLASSIFICATION_UPGRADE_NAME_CLEANING if new_val else CLASSIFICATION_NEEDS_REVIEW
                diffs.append(
                    UpgradeDiff(
                        field="客户名称",
                        row=idx,
                        legacy_value=legacy_val[:50],  # Truncate for readability
                        new_value=new_val[:50],
                        classification=classification,
                    )
                )

    return diffs


# =============================================================================
# Main Comparison Function
# =============================================================================


def run_comparison(
    excel_path: str,
    sheet_name: str = DEFAULT_SHEET_NAME,
    row_limit: int = DEFAULT_ROW_LIMIT,
    enable_enrichment: bool = False,
    save_debug: bool = False,
    run_id: Optional[str] = None,
) -> tuple:
    """
    Run full comparison between Legacy and New Pipeline cleaners.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Row limit for iteration (0 = no limit)
        enable_enrichment: Whether to enable EQC enrichment
        save_debug: Whether to save debug snapshots
        run_id: Optional run ID (timestamp) for output directory

    Returns:
        Tuple of (ComparisonReport, run_id)
    """
    start_time = time.perf_counter()

    # Generate run_id if not provided
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Run both cleaners
    print(f"🔄 Running Legacy cleaner...")
    legacy_df = run_legacy_cleaner(excel_path, sheet_name, row_limit)

    print(f"🔄 Running New Pipeline...")
    new_df = run_new_pipeline(excel_path, sheet_name, row_limit, enable_enrichment)

    # Save debug snapshots if requested
    if save_debug:
        save_debug_snapshots(legacy_df, new_df, run_id=run_id)

    # Run comparisons
    print(f"🔍 Comparing numeric fields...")
    numeric_diffs = compare_numeric_fields(legacy_df, new_df)

    print(f"🔍 Comparing derived fields...")
    derived_diffs = compare_derived_fields(legacy_df, new_df)

    print(f"🔍 Comparing upgrade fields...")
    upgrade_diffs = compare_upgrade_fields(legacy_df, new_df)

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
    parser = argparse.ArgumentParser(
        description="Compare Legacy vs New Pipeline cleaners for annuity_performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comparison with 100 row limit
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --limit 100

  # Full dataset comparison
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --limit 0

  # New Pipeline only (no Legacy dependencies needed)
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --new-only --debug

  # With debug snapshots
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --limit 100 --debug

  # Export reports
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --limit 100 --export
        """,
    )
    parser.add_argument(
        "excel_path",
        help="Path to Excel file containing source data",
    )
    parser.add_argument(
        "--sheet",
        default=DEFAULT_SHEET_NAME,
        help=f"Sheet name to process (default: {DEFAULT_SHEET_NAME})",
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

    args = parser.parse_args()

    # Verify input file exists
    excel_path = Path(args.excel_path)
    if not excel_path.exists():
        print(f"❌ Error: File not found: {excel_path}")
        sys.exit(1)

    # Generate run_id for this execution
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # New-only mode: just run and display New Pipeline output
    if args.new_only:
        print(f"🔄 Running New Pipeline only (--new-only mode)...")
        new_df = run_new_pipeline(
            excel_path=str(excel_path),
            sheet_name=args.sheet,
            row_limit=args.limit,
            enable_enrichment=args.enrichment,
        )
        print(f"\n✅ New Pipeline completed:")
        print(f"   Rows: {len(new_df)}")
        print(f"   Columns: {len(new_df.columns)}")
        print(f"   Columns: {list(new_df.columns)}")
        if args.debug:
            from guimo_iter_config import ARTIFACTS_DIR, DEBUG_SNAPSHOTS_SUBDIR
            run_dir = ARTIFACTS_DIR / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            snapshots_dir = run_dir / DEBUG_SNAPSHOTS_SUBDIR
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            output_path = snapshots_dir / "new_pipeline_output.csv"
            new_df.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"   Saved to: {snapshots_dir}")
        sys.exit(0)

    report, run_id = run_comparison(
        excel_path=str(excel_path),
        sheet_name=args.sheet,
        row_limit=args.limit,
        enable_enrichment=args.enrichment,
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
