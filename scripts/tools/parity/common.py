"""
Shared helpers for parity validation scripts.

Provides reusable comparison/report/output utilities so domain-specific
parity scripts can stay thin wrappers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

DEFAULT_EXCLUDE_COLS = ("_source", "_source_file", "company_id")


def normalize_date_value(val: object) -> str:
    """Normalize date-like values for string comparison (drops time part)."""
    if pd.isna(val):
        return "NaN"
    s = str(val)
    if " 00:00:00" in s:
        s = s.replace(" 00:00:00", "")
    return s


def compare_dataframes(
    legacy_df: pd.DataFrame,
    pipeline_df: pd.DataFrame,
    *,
    column_renames: Optional[Dict[str, str]] = None,
    exclude_cols: Sequence[str] = DEFAULT_EXCLUDE_COLS,
    expected_legacy_only: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """
    Generic set-based comparison between legacy and pipeline outputs.

    - Handles column renames
    - Excludes specified columns (default excludes company_id)
    - Returns column comparison, set comparison, differences, and summary
    """
    column_renames = column_renames or {}
    expected_legacy_only = set(expected_legacy_only or [])

    report: Dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "legacy_shape": {"rows": len(legacy_df), "columns": len(legacy_df.columns)},
        "pipeline_shape": {
            "rows": len(pipeline_df),
            "columns": len(pipeline_df.columns),
        },
        "column_comparison": {},
        "data_differences": [],
        "summary": {},
    }

    legacy_cols = set(legacy_df.columns)
    pipeline_cols = set(pipeline_df.columns)

    common_cols = legacy_cols.intersection(pipeline_cols)
    legacy_only = legacy_cols - pipeline_cols
    pipeline_only = pipeline_cols - legacy_cols

    matched_renames = {}
    for legacy_col in list(legacy_only):
        if legacy_col in column_renames and column_renames[legacy_col] in pipeline_only:
            matched_renames[legacy_col] = column_renames[legacy_col]
            legacy_only.discard(legacy_col)
            pipeline_only.discard(column_renames[legacy_col])

    unexpected_legacy_only = legacy_only - expected_legacy_only

    report["column_comparison"] = {
        "common": sorted(common_cols),
        "legacy_only": sorted(legacy_only),
        "pipeline_only": sorted(pipeline_only),
        "matched_renames": matched_renames,
        "expected_legacy_only": sorted(expected_legacy_only & legacy_only),
        "unexpected_legacy_only": sorted(unexpected_legacy_only),
    }

    comparison_cols = [
        c for c in legacy_df.columns if c in common_cols and c not in exclude_cols
    ]

    legacy_norm = legacy_df[comparison_cols].copy()
    pipeline_norm = pipeline_df[comparison_cols].copy()

    for col in comparison_cols:
        if col in {"月度"}:
            legacy_norm[col] = legacy_norm[col].apply(normalize_date_value)
            pipeline_norm[col] = pipeline_norm[col].apply(normalize_date_value)

        legacy_norm[col] = legacy_norm[col].fillna("__NULL__").astype(str)
        pipeline_norm[col] = pipeline_norm[col].fillna("__NULL__").astype(str)

    legacy_norm["_row_sig"] = legacy_norm.apply(
        lambda row: "|".join(row.values), axis=1
    )
    pipeline_norm["_row_sig"] = pipeline_norm.apply(
        lambda row: "|".join(row.values), axis=1
    )

    legacy_sigs = set(legacy_norm["_row_sig"].tolist())
    pipeline_sigs = set(pipeline_norm["_row_sig"].tolist())

    legacy_only_rows = legacy_sigs - pipeline_sigs
    pipeline_only_rows = pipeline_sigs - legacy_sigs
    common_rows = legacy_sigs.intersection(pipeline_sigs)

    differences: List[Dict[str, object]] = []
    for sig in list(legacy_only_rows)[:50]:
        row_data = legacy_norm[legacy_norm["_row_sig"] == sig].iloc[0]
        differences.append(
            {
                "type": "legacy_only",
                "row_signature": sig[:100] + "..." if len(sig) > 100 else sig,
                "sample_cols": {col: row_data[col] for col in comparison_cols[:5]},
            }
        )

    for sig in list(pipeline_only_rows)[:50]:
        row_data = pipeline_norm[pipeline_norm["_row_sig"] == sig].iloc[0]
        differences.append(
            {
                "type": "pipeline_only",
                "row_signature": sig[:100] + "..." if len(sig) > 100 else sig,
                "sample_cols": {col: row_data[col] for col in comparison_cols[:5]},
            }
        )

    report["set_comparison"] = {
        "total_legacy_rows": len(legacy_sigs),
        "total_pipeline_rows": len(pipeline_sigs),
        "common_rows": len(common_rows),
        "legacy_only_rows": len(legacy_only_rows),
        "pipeline_only_rows": len(pipeline_only_rows),
        "match_rate": len(common_rows) / max(len(legacy_sigs), 1) * 100,
    }

    report["data_differences"] = differences[:100]
    report["total_differences"] = len(legacy_only_rows) + len(pipeline_only_rows)

    row_match = len(legacy_df) == len(pipeline_df)
    col_match = len(unexpected_legacy_only) == 0 and len(pipeline_only) == 0
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
    report: Dict[str, object],
    output_dir: Path,
    prefix: str,
) -> Dict[str, Path]:
    """Save outputs (parquet/json/xlsx) with a common naming pattern."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir.mkdir(parents=True, exist_ok=True)

    legacy_path = output_dir / f"{prefix}_legacy_output_{timestamp}.parquet"
    pipeline_path = output_dir / f"{prefix}_pipeline_output_{timestamp}.parquet"
    report_path = output_dir / f"{prefix}_parity_{timestamp}.json"
    excel_path = output_dir / f"{prefix}_comparison_{timestamp}.xlsx"

    legacy_df.astype(str).to_parquet(legacy_path, index=False)
    pipeline_df.astype(str).to_parquet(pipeline_path, index=False)

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        legacy_df.to_excel(writer, sheet_name="Legacy", index=False)
        pipeline_df.to_excel(writer, sheet_name="Pipeline", index=False)

        if report.get("data_differences"):
            diff_df = pd.DataFrame(report["data_differences"])
            diff_df.to_excel(writer, sheet_name="Differences", index=False)

    return {
        "legacy": legacy_path,
        "pipeline": pipeline_path,
        "report": report_path,
        "excel": excel_path,
    }


def print_report_summary(report: Dict[str, object], title: str) -> None:
    """Compact console summary."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(f"\nTimestamp: {report['timestamp']}")

    print("\nShape Comparison:")
    print(
        f"  Legacy:   {report['legacy_shape']['rows']} rows, {report['legacy_shape']['columns']} columns"
    )
    print(
        f"  Pipeline: {report['pipeline_shape']['rows']} rows, {report['pipeline_shape']['columns']} columns"
    )

    col_comp = report["column_comparison"]
    print("\nColumn Comparison:")
    print(f"  Common columns: {len(col_comp['common'])}")
    if col_comp.get("legacy_only"):
        print(f"  Legacy only: {col_comp['legacy_only']}")
    if col_comp.get("pipeline_only"):
        print(f"  Pipeline only: {col_comp['pipeline_only']}")

    summary = report["summary"]
    print("\nSummary:")
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

    print("\n" + "=" * 80)


__all__ = [
    "compare_dataframes",
    "save_results",
    "print_report_summary",
    "normalize_date_value",
    "DEFAULT_EXCLUDE_COLS",
]
