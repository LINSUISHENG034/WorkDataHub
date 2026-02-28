"""Slice data generation script.

Extracts minimal subsets from real Excel files in data/real_data/202510/
to create reproducible test fixtures in tests/fixtures/slice_data/202510/.

Usage:
    PYTHONPATH=src uv run python tests/slice_tests/generate_slices.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_DATA_ROOT = PROJECT_ROOT / "data" / "real_data" / "202510"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "slice_data" / "202510"

# Source file patterns
PERF_BASE = REAL_DATA_ROOT / "收集数据" / "数据采集"
BIZ_BASE = REAL_DATA_ROOT / "收集数据" / "业务收集"


def _find_file(base: Path, pattern: str) -> Path:
    """Find a single file matching glob pattern under base/V*/ or base/."""
    # Try versioned directories first (V1, V2, ...)
    for vdir in sorted(base.glob("V*"), reverse=True):
        matches = list(vdir.glob(pattern))
        if matches:
            return matches[0]
    # Fallback to base directory
    matches = list(base.glob(pattern))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"No file matching '{pattern}' under {base}")


def _select_rows(
    df: pd.DataFrame, conditions: list[dict], fallback_n: int = 3
) -> pd.DataFrame:
    """Select rows matching conditions, plus fallback random rows to reach target count."""
    selected_indices: list[int] = []
    for cond in conditions:
        mask = pd.Series(True, index=df.index)
        for col, check in cond.items():
            if callable(check):
                mask &= df[col].apply(check)
            else:
                mask &= df[col] == check
        matches = df[mask].index.tolist()
        if matches:
            selected_indices.append(matches[0])

    # Deduplicate while preserving order
    seen = set(selected_indices)
    # Fill remaining with random rows
    remaining = [i for i in df.index if i not in seen]
    needed = max(0, fallback_n - len(seen))
    if needed and remaining:
        import random

        random.seed(42)
        extra = random.sample(remaining, min(needed, len(remaining)))
        selected_indices.extend(extra)

    return df.loc[list(dict.fromkeys(selected_indices))].reset_index(drop=True)


def generate_annuity_performance_slice() -> None:
    """Extract ~15 rows from 规模明细 sheet covering boundary cases."""
    src = _find_file(PERF_BASE, "*规模收入数据*.xlsx")
    print(f"  Reading: {src}")
    df = pd.read_excel(src, sheet_name="规模明细", engine="openpyxl")
    print(f"  Source rows: {len(df)}")

    # Boundary conditions to cover
    conditions = [
        # B-5: empty/blank 机构 → fallback G00
        {"机构": lambda x: pd.isna(x) or str(x).strip() in ("", "(空白)")},
        # B-9: 集团企业客户号 with C prefix
        {"集团企业客户号": lambda x: isinstance(x, str) and str(x).startswith("C")},
        # B-8: empty 组合代码
        {"组合代码": lambda x: pd.isna(x) or str(x).strip() == ""},
        # B-4: empty 计划代码 (or 计划号)
        {"计划号": lambda x: pd.isna(x) or str(x).strip() == ""},
        # B-6: 企年受托
        {"业务类型": "企年受托"},
        # B-6: 企年投资
        {"业务类型": "企年投资"},
        # B-7: Chinese date format
        {"月度": lambda x: isinstance(x, str) and "年" in str(x)},
    ]
    # Use column name variants (source may use 机构 or 机构名称, 计划号 or 计划代码)
    col_map = {}
    for c in df.columns:
        col_map[c.strip()] = c

    # Adapt conditions to actual column names
    adapted = []
    for cond in conditions:
        new_cond = {}
        for k, v in cond.items():
            actual = col_map.get(k, k)
            if actual in df.columns:
                new_cond[actual] = v
        if new_cond:
            adapted.append(new_cond)

    sliced = _select_rows(df, adapted, fallback_n=8)
    print(f"  Selected rows: {len(sliced)}")

    out_dir = FIXTURE_ROOT / "annuity_performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "slice_规模收入数据.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        sliced.to_excel(writer, sheet_name="规模明细", index=False)
    print(f"  Written: {out_path}")


def _extract_award_loss_sheets(
    sheet_pairs: list[tuple[str, str]],
    conditions: list[dict],
    out_path: Path,
    rows_per_sheet: int = 5,
) -> None:
    """Extract rows from multiple sheets of the same file into a new Excel."""
    src = _find_file(BIZ_BASE, "*台账登记*.xlsx")
    print(f"  Reading: {src}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sheet_name, label in sheet_pairs:
            try:
                df = pd.read_excel(src, sheet_name=sheet_name, engine="openpyxl")
            except Exception as e:
                print(f"  WARNING: Sheet '{sheet_name}' not found: {e}")
                continue

            print(f"  Sheet '{sheet_name}': {len(df)} rows")

            # Adapt conditions to actual columns
            col_map = {c.strip(): c for c in df.columns}
            adapted = []
            for cond in conditions:
                new_cond = {}
                for k, v in cond.items():
                    actual = col_map.get(k, k)
                    if actual in df.columns:
                        new_cond[actual] = v
                if new_cond:
                    adapted.append(new_cond)

            sliced = _select_rows(df, adapted, fallback_n=rows_per_sheet)
            sliced.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  Selected {len(sliced)} rows for '{sheet_name}'")

    print(f"  Written: {out_path}")


def generate_annual_award_slice() -> None:
    """Extract rows from 中标 sheets covering boundary cases."""
    print("\n[annual_award]")
    award_conditions = [
        {"业务类型": "受托"},
        {"业务类型": lambda x: str(x).strip() in ("投资", "投管")},
        {"计划类型": "集合"},
        {"年金计划号": lambda x: pd.isna(x) or str(x).strip() == ""},
        {"中标日期": lambda x: pd.isna(x) or str(x).strip() == ""},
    ]
    _extract_award_loss_sheets(
        sheet_pairs=[
            ("企年受托中标(空白)", "trustee_award"),
            ("企年投资中标(空白)", "investee_award"),
        ],
        conditions=award_conditions,
        out_path=FIXTURE_ROOT / "annual_award" / "slice_中标台账.xlsx",
    )


def generate_annual_loss_slice() -> None:
    """Extract rows from 流失 sheets covering boundary cases."""
    print("\n[annual_loss]")
    loss_conditions = [
        {"业务类型": "受托"},
        {"业务类型": lambda x: str(x).strip() in ("投资", "投管")},
        {"计划类型": "集合"},
        {"年金计划号": lambda x: pd.isna(x) or str(x).strip() == ""},
        {"流失日期": lambda x: pd.isna(x) or str(x).strip() == ""},
    ]
    _extract_award_loss_sheets(
        sheet_pairs=[
            ("企年受托流失(解约)", "trustee_loss"),
            ("企年投资流失(解约)", "investee_loss"),
        ],
        conditions=loss_conditions,
        out_path=FIXTURE_ROOT / "annual_loss" / "slice_流失台账.xlsx",
    )


def main() -> None:
    print("=== Slice Data Generation ===")
    print(f"Source: {REAL_DATA_ROOT}")
    print(f"Output: {FIXTURE_ROOT}")

    if not REAL_DATA_ROOT.exists():
        print(f"ERROR: Real data directory not found: {REAL_DATA_ROOT}")
        sys.exit(1)

    print("\n[annuity_performance]")
    generate_annuity_performance_slice()
    generate_annual_award_slice()
    generate_annual_loss_slice()

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
