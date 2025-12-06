#!/usr/bin/env python3
"""
AnnuityPerformance Parity Validation Script

Validates that the new annuity_performance pipeline matches legacy output
for real data. company_id parity is deferred (Epic-6); comparison excludes
company_id and records counts only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from scripts.tools.parity.common import (
    DEFAULT_EXCLUDE_COLS,
    compare_dataframes,
    print_report_summary,
    save_results,
)
from scripts.tools.run_legacy_annuity_performance_cleaner import (
    ExtractedAnnuityPerformanceCleaner,
    canonicalize_dataframe,
    load_mapping_fixture,
)
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA = (
    PROJECT_ROOT
    / "tests/fixtures/real_data/202412/收集数据/数据采集/V2/【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx"
)
DEFAULT_MAPPING = PROJECT_ROOT / "tests/fixtures/sample_legacy_mappings.json"
DEFAULT_SHEET = "规模明细"
OUTPUT_DIR = PROJECT_ROOT / "tests/fixtures/validation_results"


def load_real_data(excel_path: Path, sheet_name: str) -> List[Dict[str, Any]]:
    if not excel_path.exists():
        raise FileNotFoundError(f"Real data file not found: {excel_path}")
    rows = read_excel_rows(excel_path, sheet=sheet_name)
    if not rows:
        raise ValueError(f"No data loaded from {excel_path}")
    LOGGER.info("Loaded %s rows from %s", len(rows), excel_path)
    return rows


def process_with_legacy(
    rows: List[Dict[str, Any]], mappings: Dict[str, Any]
) -> pd.DataFrame:
    cleaner = ExtractedAnnuityPerformanceCleaner(mappings)
    df = cleaner.clean(pd.DataFrame(rows))
    df["_source"] = "legacy"
    return canonicalize_dataframe(df)


def process_with_pipeline(
    rows: List[Dict[str, Any]],
    plan_overrides: Dict[str, str],
    generate_temp_ids: bool = False,
) -> pd.DataFrame:
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=None,
        plan_override_mapping=plan_overrides,
        sync_lookup_budget=0,
        generate_temp_ids=generate_temp_ids,
    )
    context = PipelineContext(
        pipeline_name="bronze_to_silver_validation",
        execution_id=f"validation-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance"},
    )
    df = pd.DataFrame(rows)
    result_df = pipeline.execute(df, context)
    result_df["_source"] = "pipeline"
    return result_df.reset_index(drop=True)


def build_report(legacy_df: pd.DataFrame, pipeline_df: pd.DataFrame) -> Dict[str, Any]:
    return compare_dataframes(
        legacy_df,
        pipeline_df,
        column_renames={"流失(含待遇支付)": "流失_含待遇支付"},
        exclude_cols=DEFAULT_EXCLUDE_COLS,
        expected_legacy_only=set(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate annuity_performance parity vs legacy."
    )
    parser.add_argument(
        "--data", type=Path, default=DEFAULT_DATA, help="Path to real data Excel"
    )
    parser.add_argument(
        "--sheet", default=DEFAULT_SHEET, help="Sheet name (default: 规模明细)"
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
        help="Mapping fixture (JSON/YAML) for legacy and plan overrides",
    )
    parser.add_argument(
        "--generate-temp-ids",
        action="store_true",
        help="Enable temp IDs in pipeline resolution (default: off for parity)",
    )
    args = parser.parse_args()

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        mappings = load_mapping_fixture(args.mapping)
        plan_overrides = load_plan_override_mapping(str(args.mapping))

        raw_rows = load_real_data(args.data, args.sheet)
        for row in raw_rows:
            row["_source_file"] = args.data.name

        legacy_df = process_with_legacy(raw_rows, mappings)
        pipeline_df = process_with_pipeline(
            raw_rows,
            plan_overrides=plan_overrides,
            generate_temp_ids=bool(args.generate_temp_ids),
        )

        report = build_report(legacy_df, pipeline_df)
        saved = save_results(
            legacy_df, pipeline_df, report, OUTPUT_DIR, prefix="annuity_performance"
        )
        print_report_summary(
            report, title="ANNUITY PERFORMANCE PARITY VALIDATION REPORT"
        )

        LOGGER.info("Results saved to %s", OUTPUT_DIR)
        for name, path in saved.items():
            LOGGER.info("  %s: %s", name, path.name)

        return 0 if report["summary"]["overall_parity"] else 1
    except Exception as exc:
        LOGGER.exception("Validation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
