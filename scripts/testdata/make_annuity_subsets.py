"""
Generate small annuity test datasets from a large real sample Excel file.

This script reads the source Excel using the project's ExcelReader (which applies
header normalization) and writes several small-sized Excel files that reflect
realistic scenarios for overwrite (delete_insert) and non-overwrite (append)
testing.

Outputs (written under tests/fixtures/sample_data/annuity_subsets/):
  - 2024年11月年金终稿数据_subset_distinct_5.xlsx   # 5 rows with distinct composite keys
  - 2024年11月年金终稿数据_subset_overlap_pk_6.xlsx # 6 rows with 3 unique keys
  - 2024年11月年金终稿数据_subset_append_3.xlsx    # 3 rows for simple append tests

Usage:
  uv run python -m scripts.testdata.make_annuity_subsets \
    --src tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx \
    --sheet 规模明细

Notes:
  - The script is best-effort: if exact duplicates on (月度,计划代码,机构代码) are scarce,
    it will duplicate sampled rows programmatically to form the overlap dataset.
  - Columns are written as normalized headers produced by ExcelReader; domain service
    expects these names and will re-map aliases for DB output as needed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from work_data_hub.io.readers.excel_reader import ExcelReader


def _ensure_out_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _detect_sheet(src: Path, preferred: str | None) -> str | int:
    reader = ExcelReader()
    try:
        names = reader.get_sheet_names(str(src))
        if preferred and preferred in names:
            return preferred
        # Prefer a likely Chinese sheet name if present
        for cand in ["规模明细", "明细", "Sheet1", names[0]]:
            if cand in names:
                return cand
        return names[0]
    except Exception:
        return 0


def _as_dataframe(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Keep only non-empty columns
    non_empty_cols = [c for c in df.columns if any(pd.notna(df[c]))]
    return df[non_empty_cols]


def _pick_distinct(df: pd.DataFrame, size: int) -> pd.DataFrame:
    # Use proxy key columns in priority order; fall back to any available columns
    candidates: List[Tuple[str, ...]] = [
        ("月度", "计划代码", "机构代码"),
        ("月度", "计划代码", "客户名称"),
        ("月度", "计划代码"),
        ("计划代码", "机构代码"),
    ]
    for cols in candidates:
        if all(c in df.columns for c in cols):
            dedup = df.dropna(subset=list(cols)).drop_duplicates(subset=list(cols))
            if len(dedup) >= size:
                return dedup.head(size).copy()
    # Fallback: take first N non-null rows
    non_null = df.dropna(how="all")
    return non_null.head(size).copy()


def _make_overlap(df: pd.DataFrame, unique_keys: int = 3, dup_each: int = 2) -> pd.DataFrame:
    base = _pick_distinct(df, unique_keys)
    if base.empty:
        return base
    parts = []
    for _, row in base.iterrows():
        parts.extend([row.to_frame().T.copy() for _ in range(max(1, dup_each))])
    return pd.concat(parts, ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate annuity test subsets")
    ap.add_argument("--src", required=True, help="Source Excel file path")
    ap.add_argument("--sheet", default=None, help="Sheet name (optional, auto-detect)")
    ap.add_argument(
        "--outdir",
        default="tests/fixtures/sample_data/annuity_subsets",
        help="Output directory for subset Excel files",
    )
    args = ap.parse_args()

    src = Path(args.src)
    outdir = Path(args.outdir)
    _ensure_out_dir(outdir)

    sheet = _detect_sheet(src, args.sheet)

    reader = ExcelReader()
    rows = reader.read_rows(str(src), sheet=sheet)
    df = _as_dataframe(rows)
    if df.empty:
        print("No data rows found; aborting subset generation.")
        return 1

    # 1) Distinct 5
    df_distinct_5 = _pick_distinct(df, 5)
    path1 = outdir / "2024年11月年金终稿数据_subset_distinct_5.xlsx"
    with pd.ExcelWriter(path1, engine="openpyxl") as w:
        df_distinct_5.to_excel(w, index=False, sheet_name="规模明细")
    print(f"Wrote {len(df_distinct_5)} rows to {path1}")

    # 2) Overlap PK (3 keys × 2 dup = 6 rows)
    df_overlap = _make_overlap(df, unique_keys=3, dup_each=2)
    path2 = outdir / "2024年11月年金终稿数据_subset_overlap_pk_6.xlsx"
    with pd.ExcelWriter(path2, engine="openpyxl") as w:
        df_overlap.to_excel(w, index=False, sheet_name="规模明细")
    print(f"Wrote {len(df_overlap)} rows to {path2}")

    # 3) Append 3
    df_append_3 = _pick_distinct(df, 3)
    path3 = outdir / "2024年11月年金终稿数据_subset_append_3.xlsx"
    with pd.ExcelWriter(path3, engine="openpyxl") as w:
        df_append_3.to_excel(w, index=False, sheet_name="规模明细")
    print(f"Wrote {len(df_append_3)} rows to {path3}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
