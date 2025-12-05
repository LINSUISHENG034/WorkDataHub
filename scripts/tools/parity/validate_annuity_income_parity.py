#!/usr/bin/env python3
"""
AnnuityIncome Parity Validation Script

Validates that the new AnnuityIncome pipeline architecture produces equivalent results
to the legacy AnnuityIncomeCleaner using real production data.

This script:
1. Processes real data through the legacy cleaner (WITH COMPANY_ID5_MAPPING)
2. Processes the same data through the new pipeline (WITHOUT COMPANY_ID5_MAPPING)
3. Compares results and documents the intentional company_id difference
4. Generates a detailed comparison report

CRITICAL: The COMPANY_ID5_MAPPING fallback is an INTENTIONAL difference:
- Legacy: Uses ID5 fallback for company_id resolution
- Pipeline: Does NOT use ID5 fallback (architecture decision per Tech Spec)

Usage:
    uv run python scripts/tools/validate_annuity_income_parity.py
"""

from __future__ import annotations

import argparse
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import legacy cleaner components
from scripts.tools.run_legacy_annuity_income_cleaner import (
    ExtractedAnnuityIncomeCleaner,
    canonicalize_dataframe,
    load_mapping_fixture,
)

# Import new pipeline components
from work_data_hub.domain.annuity_income.pipeline_builder import (
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.io.readers.excel_reader import read_excel_rows

from scripts.tools.parity.common import (
    DEFAULT_EXCLUDE_COLS,
    compare_dataframes,
    print_report_summary,
    save_results,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger(__name__)

# Configuration - Use 202412 V2 for consistency with AnnuityPerformance validation
REAL_DATA_PATH = PROJECT_ROOT / "tests/fixtures/real_data/202412/收集数据/数据采集/V2/【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx"
MAPPING_FIXTURE_PATH = PROJECT_ROOT / "tests/fixtures/sample_legacy_mappings.json"
OUTPUT_DIR = PROJECT_ROOT / "tests/fixtures/validation_results"
SHEET_NAME = "收入明细"


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
    """Process data using the legacy cleaner (WITH COMPANY_ID5_MAPPING fallback)."""
    LOGGER.info("Processing with LEGACY cleaner (includes ID5 fallback)...")

    cleaner = ExtractedAnnuityIncomeCleaner(mappings)
    df = pd.DataFrame(rows)

    # Apply legacy cleaning
    cleaned_df = cleaner.clean(df)
    cleaned_df["_source"] = "legacy"

    # Canonicalize for consistent comparison
    result = canonicalize_dataframe(cleaned_df)

    LOGGER.info(f"Legacy output: {len(result)} rows, {len(result.columns)} columns")
    return result


def process_with_pipeline(
    rows: List[Dict[str, Any]],
    plan_overrides: Dict[str, str],
    generate_temp_ids: bool = True,
) -> pd.DataFrame:
    """Process data using the new pipeline architecture (WITHOUT COMPANY_ID5_MAPPING fallback)."""
    LOGGER.info("Processing with NEW pipeline (NO ID5 fallback)...")

    # Build pipeline without enrichment service (for deterministic comparison)
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=None,
        plan_override_mapping=plan_overrides,
        sync_lookup_budget=0,
        generate_temp_ids=generate_temp_ids,
    )

    # Create pipeline context
    context = PipelineContext(
        pipeline_name="bronze_to_silver_validation",
        execution_id=f"validation-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_income"},
        domain="annuity_income",
        run_id=f"annuity_income-validation-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    )

    # Execute pipeline
    df = pd.DataFrame(rows)

    # Handle column name variation: actual Excel uses 计划代码, legacy expects 计划号
    # Rename to match pipeline expectation
    if "计划代码" in df.columns and "计划号" not in df.columns:
        df = df.rename(columns={"计划代码": "计划号"})
        LOGGER.info("Renamed column: 计划代码 → 计划号")

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


def normalize_parentheses(val: Any) -> str:
    """
    Normalize parentheses for comparison.

    Pipeline uses full-width parentheses (Chinese standard), legacy uses half-width.
    This is an intentional improvement, not a parity failure.
    """
    if pd.isna(val) or val == "__NULL__":
        return str(val) if val == "__NULL__" else "NaN"
    s = str(val)
    # Normalize to full-width for comparison (pipeline standard)
    s = s.replace("(", "（").replace(")", "）")
    return s


def analyze_company_id_differences(
    legacy_df: pd.DataFrame, pipeline_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Analyze company_id differences to identify ID5 fallback usage.

    This is the CRITICAL analysis for documenting the intentional difference.
    """
    analysis = {
        "total_rows": len(legacy_df),
        "legacy_has_company_id": 0,
        "pipeline_has_company_id": 0,
        "both_have_company_id": 0,
        "legacy_only_has_company_id": 0,  # ID5 fallback cases
        "pipeline_only_has_company_id": 0,
        "neither_has_company_id": 0,
        "company_id_matches": 0,
        "company_id_differs": 0,
        "id5_fallback_rows": [],
    }

    if "company_id" not in legacy_df.columns or "company_id" not in pipeline_df.columns:
        LOGGER.warning("company_id column missing from one or both DataFrames")
        return analysis

    # Ensure same row count for comparison
    if len(legacy_df) != len(pipeline_df):
        LOGGER.warning(
            f"Row count mismatch: legacy={len(legacy_df)}, pipeline={len(pipeline_df)}"
        )
        return analysis

    for idx in range(len(legacy_df)):
        legacy_id = legacy_df.iloc[idx].get("company_id")
        pipeline_id = pipeline_df.iloc[idx].get("company_id")

        legacy_has = pd.notna(legacy_id) and str(legacy_id).strip() != ""
        pipeline_has = pd.notna(pipeline_id) and str(pipeline_id).strip() != ""

        if legacy_has:
            analysis["legacy_has_company_id"] += 1
        if pipeline_has:
            analysis["pipeline_has_company_id"] += 1

        if legacy_has and pipeline_has:
            analysis["both_have_company_id"] += 1
            if str(legacy_id) == str(pipeline_id):
                analysis["company_id_matches"] += 1
            else:
                analysis["company_id_differs"] += 1
        elif legacy_has and not pipeline_has:
            # This is the ID5 fallback case - legacy resolved via ID5, pipeline did not
            analysis["legacy_only_has_company_id"] += 1
            if len(analysis["id5_fallback_rows"]) < 50:  # Limit sample size
                row_sample = {
                    "row_index": idx,
                    "legacy_company_id": str(legacy_id),
                    "年金账户名": str(legacy_df.iloc[idx].get("年金账户名", "N/A")),
                    "客户名称": str(legacy_df.iloc[idx].get("客户名称", "N/A")),
                    "计划号": str(legacy_df.iloc[idx].get("计划号", "N/A")),
                }
                analysis["id5_fallback_rows"].append(row_sample)
        elif pipeline_has and not legacy_has:
            analysis["pipeline_only_has_company_id"] += 1
        else:
            analysis["neither_has_company_id"] += 1

    return analysis


def build_report_with_company_id_notes(
    legacy_df: pd.DataFrame, pipeline_df: pd.DataFrame
) -> Dict[str, Any]:
    """Wrap generic comparison with company_id intentional difference notes."""
    base_report = compare_dataframes(
        legacy_df,
        pipeline_df,
        column_renames={},
        exclude_cols=DEFAULT_EXCLUDE_COLS,
        expected_legacy_only={"机构名称"},
    )

    company_id_analysis = analyze_company_id_differences(legacy_df, pipeline_df)
    base_report["intentional_differences"] = {
        "company_id_id5_fallback": {
            "description": "Legacy uses COMPANY_ID5_MAPPING fallback, new pipeline does not",
            "affected_rows": company_id_analysis["legacy_only_has_company_id"],
            "reason": "Architecture decision per Tech Spec - company_id parity deferred to Epic-6",
            "analysis": company_id_analysis,
        }
    }
    # Add counts for convenience
    base_report["summary"]["company_id_id5_fallback_count"] = company_id_analysis[
        "legacy_only_has_company_id"
    ]
    base_report["summary"]["company_id_pipeline_only"] = company_id_analysis["pipeline_only_has_company_id"]
    return base_report


def main() -> int:
    """Main entry point."""
    LOGGER.info("Starting AnnuityIncome parity validation")

    parser = argparse.ArgumentParser(description="Validate AnnuityIncome parity against legacy.")
    parser.add_argument(
        "--data",
        type=Path,
        default=REAL_DATA_PATH,
        help="Path to real data Excel file",
    )
    parser.add_argument(
        "--sheet",
        default=SHEET_NAME,
        help="Excel sheet name (default: 收入明细)",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=MAPPING_FIXTURE_PATH,
        help="Path to legacy mapping fixture (JSON or YAML with plan_overrides)",
    )
    parser.add_argument(
        "--generate-temp-ids",
        action="store_true",
        help="Enable temp ID generation for pipeline resolution (default: disabled for strict parity)",
    )
    args = parser.parse_args()

    LOGGER.info(f"Data source: {args.data}")
    LOGGER.info(f"Sheet: {args.sheet}")

    try:
        # Ensure output directory exists
        output_dir = ensure_output_dir()

        # Check if real data exists
        if not args.data.exists():
            LOGGER.error(f"Real data file not found: {args.data}")
            LOGGER.info("Please ensure the real data file exists at the specified path")
            return 1

        # Load mapping fixture
        if not args.mapping.exists():
            LOGGER.error(f"Mapping fixture not found: {args.mapping}")
            return 1

        mappings = load_mapping_fixture(args.mapping)
        # Derive plan overrides from fixture data (fallback to YAML loader if present)
        plan_overrides = mappings.get("company_id1_mapping", {}).get("data", {})
        if not plan_overrides:
            plan_overrides = load_plan_override_mapping(str(args.mapping))

        # Load real data
        raw_rows = load_real_data(args.data, args.sheet)

        # Add source file tracking
        for row in raw_rows:
            row["_source_file"] = args.data.name

        # Process with both systems
        legacy_df = process_with_legacy(raw_rows, mappings)
        pipeline_df = process_with_pipeline(
            raw_rows,
            plan_overrides=plan_overrides,
            generate_temp_ids=bool(args.generate_temp_ids),
        )

        # Compare results
        report = build_report_with_company_id_notes(legacy_df, pipeline_df)

        # Save all results
        saved_files = save_results(
            legacy_df,
            pipeline_df,
            report,
            output_dir,
            prefix="annuity_income",
        )

        # Print summary
        print_report_summary(report, title="ANNUITY INCOME PARITY VALIDATION REPORT")

        LOGGER.info(f"\nResults saved to: {output_dir}")
        for name, path in saved_files.items():
            LOGGER.info(f"  {name}: {path.name}")

        # Return exit code based on parity (excluding intentional company_id difference)
        return 0 if report["summary"]["overall_parity"] else 1

    except Exception as e:
        LOGGER.exception(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
