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
# Auto-Discovery (Epic 3: Version-Aware File Discovery)
# =============================================================================


def discover_source_file(month: str, domain: str = "annuity_performance") -> tuple:
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

        print(f"🔍 Auto-discovering source file for month {month}...")
        discovery_service = FileDiscoveryService()
        result = discovery_service.discover_file(
            domain=domain,
            month=month,  # Note: template var is 'month' not 'YYYYMM'
        )

        print(f"   ✓ Discovered: {result.file_path.name}")
        print(f"   ✓ Version: {result.version}")
        print(f"   ✓ Sheet: {result.sheet_name}")

        return str(result.file_path), result.sheet_name

    except Exception as e:
        print(f"❌ Auto-discovery failed: {e}")
        print(f"\n💡 Please specify the file path manually:")
        print(f"   python guimo_iter_cleaner_compare.py <excel_path> --limit 100")
        sys.exit(1)


# =============================================================================
# Token Validation (Story 6.2-P11: Auto-refresh for validation scripts)
# =============================================================================


def _validate_and_refresh_token(auto_refresh: bool = True) -> bool:
    """
    Validate EQC token at script startup and auto-refresh if invalid.

    Replicates the token validation logic from cli/etl.py (Story 6.2-P11).

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

    # Validate that Legacy cleaner returned data
    if len(df) == 0:
        print(f"\n❌ Legacy Cleaner returned 0 rows!")
        print(f"   This usually indicates an internal cleaner error.")
        print(f"   Check the log output above for 'Error in class AnnuityPerformanceCleaner'.")
        print(f"\n💡 Options:")
        print(f"   1. Check if the Excel file contains the expected columns")
        print(f"   2. Use --new-only mode to skip Legacy comparison:")
        print(f"      python guimo_iter_cleaner_compare.py <excel_path> --new-only")
        print("")
        raise RuntimeError("Legacy cleaner returned empty DataFrame - internal error")

    if row_limit and row_limit > 0:
        df = df.head(row_limit)

    return df


def run_new_pipeline(
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
    enable_enrichment: bool = False,
    sync_lookup_budget: int = 1000,
) -> pd.DataFrame:
    """
    Execute New Pipeline cleaner with full company ID resolution.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration
        enable_enrichment: Whether to enable EQC enrichment service (default: False)
        sync_lookup_budget: Budget for EQC sync lookups (default: 1000)

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

    # Enable DB cache lookups whenever possible (independent of EQC enrichment).
    # EQC sync lookups are controlled by enable_enrichment + sync_lookup_budget.
    settings = get_settings()
    engine = None

    try:
        from sqlalchemy import create_engine

        engine = create_engine(settings.get_database_connection_string())
    except Exception as e:
        print(f"   ⚠️ Database engine init failed (DB cache disabled): {e}")

    if engine is None:
        pipeline = build_bronze_to_silver_pipeline(
            enrichment_service=None,
            plan_override_mapping=plan_override_mapping,
            sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
            mapping_repository=None,
        )

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

    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    # Keep the connection open for the whole pipeline execution (CompanyMappingRepository owns a Connection).
    with engine.connect() as conn:
        mapping_repository = CompanyMappingRepository(conn)
        print("   ✓ Database mapping repository enabled (enterprise.enrichment_index)")

        pipeline = build_bronze_to_silver_pipeline(
            enrichment_service=None,
            plan_override_mapping=plan_override_mapping,
            sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
            mapping_repository=mapping_repository,
        )

        context = PipelineContext(
            pipeline_name="cleaner_comparison",
            execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(timezone.utc),
            config={},
            domain="annuity_performance",
            run_id="compare",
            extra={},
        )

        result_df = pipeline.execute(raw_df.copy(), context)

        # CRITICAL: Commit to persist EQC cache writes to database
        # Without this, all insert_enrichment_index_batch calls are rolled back!
        conn.commit()

        return result_df


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

    # Excel row offset: +1 for 0-based index, +1 for header row = +2
    EXCEL_ROW_OFFSET = 2

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

    # Excel row offset: +1 for 0-based index, +1 for header row = +2
    EXCEL_ROW_OFFSET = 2

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

    # Excel row offset: +1 for 0-based index, +1 for header row = +2
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
                        row=idx + EXCEL_ROW_OFFSET,
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
    sync_lookup_budget: int = 1000,
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
        sync_lookup_budget: Budget for EQC sync lookups (default: 1000)
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
    new_df = run_new_pipeline(
        excel_path, sheet_name, row_limit, enable_enrichment, sync_lookup_budget
    )

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
  # Auto-discovery mode (recommended) - automatically finds correct file version
  python guimo_iter_cleaner_compare.py --month 202311 --limit 100

  # Manual mode - specify file path directly
  python guimo_iter_cleaner_compare.py data/202412_annuity.xlsx --limit 100

  # Full dataset comparison with auto-discovery
  python guimo_iter_cleaner_compare.py --month 202311 --limit 0 --enrichment --export

  # New Pipeline only (no Legacy dependencies needed)
  python guimo_iter_cleaner_compare.py --month 202311 --new-only --debug
        """,
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

    args = parser.parse_args()

    # Determine file source: auto-discovery or manual path
    sheet_name = args.sheet
    if args.month:
        # Auto-discovery mode
        excel_path_str, discovered_sheet = discover_source_file(args.month)
        excel_path = Path(excel_path_str)
        # Use discovered sheet unless user explicitly specified one
        if args.sheet == DEFAULT_SHEET_NAME:
            sheet_name = discovered_sheet
    elif args.excel_path:
        # Manual mode
        excel_path = Path(args.excel_path)
        if not excel_path.exists():
            print(f"❌ Error: File not found: {excel_path}")
            sys.exit(1)
    else:
        print("❌ Error: Either --month or excel_path is required")
        print("   Usage: python guimo_iter_cleaner_compare.py --month 202311")
        print("   Or:    python guimo_iter_cleaner_compare.py <file_path>")
        sys.exit(1)

    # Token validation: only when --enrichment is requested
    if args.enrichment:
        auto_refresh = not getattr(args, "no_auto_refresh_token", False)
        _validate_and_refresh_token(auto_refresh=auto_refresh)

    # Generate run_id for this execution
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # New-only mode: just run and display New Pipeline output
    if args.new_only:
        print(f"🔄 Running New Pipeline only (--new-only mode)...")
        new_df = run_new_pipeline(
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
