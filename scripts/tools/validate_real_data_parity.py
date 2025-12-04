#!/usr/bin/env python3
"""
Real Data Parity Validation Script

Validates that the new pipeline architecture produces equivalent results to the
legacy AnnuityPerformanceCleaner using real production data from 202412.

This script:
1. Processes real data through the legacy cleaner
2. Processes the same data through the new pipeline
3. Compares results and saves both outputs for manual inspection
4. Generates a detailed comparison report

Usage:
    uv run python scripts/tools/validate_real_data_parity.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import legacy cleaner components
from scripts.tools.run_legacy_annuity_cleaner import (
    ExtractedAnnuityPerformanceCleaner,
    canonicalize_dataframe,
    load_mapping_fixture,
)

# Import new pipeline components
from work_data_hub.domain.annuity_performance.pipeline_builder import (
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.io.readers.excel_reader import read_excel_rows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger(__name__)

# Configuration
REAL_DATA_PATH = PROJECT_ROOT / "tests/fixtures/real_data/202412/收集数据/数据采集/V2/【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx"
MAPPING_FIXTURE_PATH = PROJECT_ROOT / "tests/fixtures/sample_legacy_mappings.json"
OUTPUT_DIR = PROJECT_ROOT / "tests/fixtures/validation_results"
SHEET_NAME = "规模明细"


def ensure_output_dir() -> Path:
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def load_real_data(excel_path: Path, sheet_name: str) -> List[Dict[str, Any]]:
    """Load real data from Excel file."""
    LOGGER.info(f"Loading real data from: {excel_path}")
    LOGGER.info(f"Sheet: {sheet_name}")

    if not excel_path.exists():
        raise FileNotFoundError(f"Real data file not found: {excel_path}")

    # Use the same Excel reader as the pipeline
    rows = read_excel_rows(excel_path, sheet=sheet_name)

    if not rows:
        raise ValueError(f"No data loaded from {excel_path}")

    LOGGER.info(f"Loaded {len(rows)} rows from real data")
    return rows


def process_with_legacy(rows: List[Dict[str, Any]], mappings: Dict[str, Any]) -> pd.DataFrame:
    """Process data using the legacy cleaner."""
    LOGGER.info("Processing with LEGACY cleaner...")

    cleaner = ExtractedAnnuityPerformanceCleaner(mappings)
    df = pd.DataFrame(rows)

    # Apply legacy cleaning
    cleaned_df = cleaner.clean(df)
    cleaned_df["_source"] = "legacy"

    # Canonicalize for consistent comparison
    result = canonicalize_dataframe(cleaned_df)

    LOGGER.info(f"Legacy output: {len(result)} rows, {len(result.columns)} columns")
    return result


def process_with_pipeline(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """Process data using the new pipeline architecture."""
    LOGGER.info("Processing with NEW pipeline...")

    # Load plan overrides (use fixture for consistency)
    plan_overrides = load_plan_override_mapping(str(MAPPING_FIXTURE_PATH))

    # Build pipeline without enrichment service (for deterministic comparison)
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=None,
        plan_override_mapping=plan_overrides,
        sync_lookup_budget=0,
    )

    # Create pipeline context
    context = PipelineContext(
        pipeline_name="bronze_to_silver_validation",
        execution_id=f"validation-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance"},
    )

    # Execute pipeline
    df = pd.DataFrame(rows)
    result_df = pipeline.execute(df, context)
    result_df["_source"] = "pipeline"

    # Don't sort here - we'll normalize sorting in compare_dataframes
    result_df = result_df.reset_index(drop=True)

    LOGGER.info(f"Pipeline output: {len(result_df)} rows, {len(result_df.columns)} columns")
    return result_df


def normalize_date_value(val: Any) -> str:
    """Normalize date values for comparison (ignore time component)."""
    if pd.isna(val):
        return "NaN"
    s = str(val)
    # Normalize datetime strings: "2024-12-01 00:00:00" -> "2024-12-01"
    if " 00:00:00" in s:
        s = s.replace(" 00:00:00", "")
    return s


def compare_dataframes(legacy_df: pd.DataFrame, pipeline_df: pd.DataFrame) -> Dict[str, Any]:
    """Compare two DataFrames and generate comparison report."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "legacy_shape": {"rows": len(legacy_df), "columns": len(legacy_df.columns)},
        "pipeline_shape": {"rows": len(pipeline_df), "columns": len(pipeline_df.columns)},
        "column_comparison": {},
        "data_differences": [],
        "summary": {},
    }

    # Column comparison - treat renamed columns as equivalent
    legacy_cols = set(legacy_df.columns)
    pipeline_cols = set(pipeline_df.columns)

    # Known column renames (legacy -> pipeline)
    column_renames = {
        "流失(含待遇支付)": "流失_含待遇支付",
    }

    common_cols = legacy_cols.intersection(pipeline_cols)
    legacy_only = legacy_cols - pipeline_cols
    pipeline_only = pipeline_cols - legacy_cols

    # Check if legacy_only columns have pipeline equivalents
    matched_renames = {}
    for legacy_col in list(legacy_only):
        if legacy_col in column_renames and column_renames[legacy_col] in pipeline_only:
            matched_renames[legacy_col] = column_renames[legacy_col]
            legacy_only.discard(legacy_col)
            pipeline_only.discard(column_renames[legacy_col])

    report["column_comparison"] = {
        "common": sorted(common_cols),
        "legacy_only": sorted(legacy_only),
        "pipeline_only": sorted(pipeline_only),
        "matched_renames": matched_renames,
    }

    # Data comparison for common columns + renamed columns
    # Exclude company_id as it's an expected design difference (Pipeline generates temp IDs, Legacy keeps NaN)
    excluded_cols = ("_source", "_source_file", "company_id")
    comparison_cols = [col for col in legacy_df.columns if col in common_cols and col not in excluded_cols]

    # Create normalized copies for set-based comparison
    legacy_norm = legacy_df[comparison_cols].copy()
    pipeline_norm = pipeline_df[comparison_cols].copy()

    # Normalize date columns
    date_columns = ["月度"]
    for col in date_columns:
        if col in legacy_norm.columns:
            legacy_norm[col] = legacy_norm[col].apply(normalize_date_value)
        if col in pipeline_norm.columns:
            pipeline_norm[col] = pipeline_norm[col].apply(normalize_date_value)

    # Convert all columns to string for consistent comparison
    for col in comparison_cols:
        legacy_norm[col] = legacy_norm[col].fillna("__NULL__").astype(str)
        pipeline_norm[col] = pipeline_norm[col].fillna("__NULL__").astype(str)

    # Create row signatures for set-based comparison
    legacy_norm["_row_sig"] = legacy_norm.apply(lambda row: "|".join(row.values), axis=1)
    pipeline_norm["_row_sig"] = pipeline_norm.apply(lambda row: "|".join(row.values), axis=1)

    legacy_sigs = set(legacy_norm["_row_sig"].tolist())
    pipeline_sigs = set(pipeline_norm["_row_sig"].tolist())

    # Find rows only in legacy or only in pipeline
    legacy_only_rows = legacy_sigs - pipeline_sigs
    pipeline_only_rows = pipeline_sigs - legacy_sigs
    common_rows = legacy_sigs.intersection(pipeline_sigs)

    differences = []

    # Report rows only in legacy
    for sig in list(legacy_only_rows)[:50]:
        row_data = legacy_norm[legacy_norm["_row_sig"] == sig].iloc[0]
        differences.append({
            "type": "legacy_only",
            "row_signature": sig[:100] + "..." if len(sig) > 100 else sig,
            "sample_cols": {col: row_data[col] for col in ["计划代码", "业务类型", "客户名称"] if col in row_data.index},
        })

    # Report rows only in pipeline
    for sig in list(pipeline_only_rows)[:50]:
        row_data = pipeline_norm[pipeline_norm["_row_sig"] == sig].iloc[0]
        differences.append({
            "type": "pipeline_only",
            "row_signature": sig[:100] + "..." if len(sig) > 100 else sig,
            "sample_cols": {col: row_data[col] for col in ["计划代码", "业务类型", "客户名称"] if col in row_data.index},
        })

    # Update summary with set-based metrics
    report["set_comparison"] = {
        "total_legacy_rows": len(legacy_sigs),
        "total_pipeline_rows": len(pipeline_sigs),
        "common_rows": len(common_rows),
        "legacy_only_rows": len(legacy_only_rows),
        "pipeline_only_rows": len(pipeline_only_rows),
        "match_rate": len(common_rows) / max(len(legacy_sigs), 1) * 100,
    }

    report["data_differences"] = differences[:100]  # Limit to first 100 differences
    report["total_differences"] = len(legacy_only_rows) + len(pipeline_only_rows)

    # Summary using set-based comparison
    row_match = len(legacy_df) == len(pipeline_df)
    col_match = len(legacy_only) == 0 and len(pipeline_only) == 0
    # Data match based on set comparison - all rows should be in common
    data_match = len(legacy_only_rows) == 0 and len(pipeline_only_rows) == 0

    match_rate = len(common_rows) / max(len(legacy_sigs), 1) * 100

    report["summary"] = {
        "row_count_match": row_match,
        "column_match": col_match,
        "data_match": data_match,
        "overall_parity": row_match and col_match and data_match,
        "difference_count": len(legacy_only_rows) + len(pipeline_only_rows),
        "match_rate": f"{match_rate:.2f}%",
        "common_rows": len(common_rows),
        "legacy_only_rows": len(legacy_only_rows),
        "pipeline_only_rows": len(pipeline_only_rows),
    }

    return report


def save_results(
    legacy_df: pd.DataFrame,
    pipeline_df: pd.DataFrame,
    report: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    """Save all results to files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Convert all columns to string to avoid parquet type issues
    legacy_df_str = legacy_df.astype(str)
    pipeline_df_str = pipeline_df.astype(str)

    # Save legacy output
    legacy_path = output_dir / f"legacy_output_{timestamp}.parquet"
    legacy_df_str.to_parquet(legacy_path, index=False)
    LOGGER.info(f"Saved legacy output: {legacy_path}")

    # Save pipeline output
    pipeline_path = output_dir / f"pipeline_output_{timestamp}.parquet"
    pipeline_df_str.to_parquet(pipeline_path, index=False)
    LOGGER.info(f"Saved pipeline output: {pipeline_path}")

    # Save comparison report
    report_path = output_dir / f"comparison_report_{timestamp}.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    LOGGER.info(f"Saved comparison report: {report_path}")

    # Save Excel for easy viewing
    excel_path = output_dir / f"comparison_{timestamp}.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        legacy_df.to_excel(writer, sheet_name="Legacy", index=False)
        pipeline_df.to_excel(writer, sheet_name="Pipeline", index=False)

        # Create differences sheet if there are differences
        if report["data_differences"]:
            diff_df = pd.DataFrame(report["data_differences"])
            diff_df.to_excel(writer, sheet_name="Differences", index=False)

    LOGGER.info(f"Saved Excel comparison: {excel_path}")

    return {
        "legacy": legacy_path,
        "pipeline": pipeline_path,
        "report": report_path,
        "excel": excel_path,
    }


def print_report_summary(report: Dict[str, Any]) -> None:
    """Print a human-readable summary of the comparison report."""
    print("\n" + "=" * 80)
    print("PARITY VALIDATION REPORT")
    print("=" * 80)

    print(f"\nTimestamp: {report['timestamp']}")

    print(f"\nShape Comparison:")
    print(f"  Legacy:   {report['legacy_shape']['rows']} rows, {report['legacy_shape']['columns']} columns")
    print(f"  Pipeline: {report['pipeline_shape']['rows']} rows, {report['pipeline_shape']['columns']} columns")

    col_comp = report["column_comparison"]
    print(f"\nColumn Comparison:")
    print(f"  Common columns: {len(col_comp['common'])}")
    if col_comp["legacy_only"]:
        print(f"  Legacy only: {col_comp['legacy_only']}")
    if col_comp["pipeline_only"]:
        print(f"  Pipeline only: {col_comp['pipeline_only']}")

    summary = report["summary"]
    print(f"\nSummary:")
    print(f"  Row count match: {'✅' if summary['row_count_match'] else '❌'}")
    print(f"  Column match: {'✅' if summary['column_match'] else '❌'}")
    print(f"  Data match: {'✅' if summary['data_match'] else '❌'}")
    print(f"  Match rate: {summary.get('match_rate', 'N/A')}")
    print(f"  Common rows: {summary.get('common_rows', 'N/A')}")
    print(f"  Legacy-only rows: {summary.get('legacy_only_rows', 0)}")
    print(f"  Pipeline-only rows: {summary.get('pipeline_only_rows', 0)}")

    if summary["overall_parity"]:
        print("\n✅ PARITY VALIDATION PASSED")
    else:
        print("\n❌ PARITY VALIDATION FAILED")

        # Show first few differences
        if report["data_differences"]:
            print("\nFirst 10 row differences:")
            for diff in report["data_differences"][:10]:
                diff_type = diff.get("type", "unknown")
                sample = diff.get("sample_cols", {})
                print(f"  [{diff_type}] 计划代码={sample.get('计划代码', 'N/A')}, 业务类型={sample.get('业务类型', 'N/A')}")

    print("\n" + "=" * 80)


def main() -> int:
    """Main entry point."""
    LOGGER.info("Starting real data parity validation")
    LOGGER.info(f"Data source: {REAL_DATA_PATH}")

    try:
        # Ensure output directory exists
        output_dir = ensure_output_dir()

        # Check if real data exists
        if not REAL_DATA_PATH.exists():
            LOGGER.error(f"Real data file not found: {REAL_DATA_PATH}")
            LOGGER.info("Please ensure the real data file exists at the specified path")
            return 1

        # Load mapping fixture
        if not MAPPING_FIXTURE_PATH.exists():
            LOGGER.error(f"Mapping fixture not found: {MAPPING_FIXTURE_PATH}")
            return 1

        mappings = load_mapping_fixture(MAPPING_FIXTURE_PATH)

        # Load real data
        raw_rows = load_real_data(REAL_DATA_PATH, SHEET_NAME)

        # Add source file tracking
        for row in raw_rows:
            row["_source_file"] = REAL_DATA_PATH.name

        # Process with both systems
        legacy_df = process_with_legacy(raw_rows, mappings)
        pipeline_df = process_with_pipeline(raw_rows)

        # Compare results
        report = compare_dataframes(legacy_df, pipeline_df)

        # Save all results
        saved_files = save_results(legacy_df, pipeline_df, report, output_dir)

        # Print summary
        print_report_summary(report)

        LOGGER.info(f"\nResults saved to: {output_dir}")
        for name, path in saved_files.items():
            LOGGER.info(f"  {name}: {path.name}")

        # Return exit code based on parity
        return 0 if report["summary"]["overall_parity"] else 1

    except Exception as e:
        LOGGER.exception(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
