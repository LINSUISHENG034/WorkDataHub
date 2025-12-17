from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def _import_compare_module():
    repo_root = Path(__file__).resolve().parents[2]
    cli_dir = repo_root / "scripts" / "validation" / "CLI"
    sys.path.insert(0, str(cli_dir))
    import guimo_iter_cleaner_compare as module  # type: ignore

    return module


def test_compare_derived_fields_does_not_flag_nan_string() -> None:
    compare = _import_compare_module()

    legacy_df = pd.DataFrame(
        {
            "月度": [None],
            "机构代码": [None],
            "计划代码": [None],
            "组合代码": [None],
            "产品线代码": [None],
        }
    )
    new_df = legacy_df.copy()

    diffs = compare.compare_derived_fields(legacy_df, new_df)
    assert diffs == []


def test_compare_numeric_fields_flags_invalid_numeric_values() -> None:
    compare = _import_compare_module()

    legacy_df = pd.DataFrame(
        {
            "期初资产规模": ["abc"],
            "期末资产规模": ["0"],
            "供款": ["0"],
            "流失(含待遇支付)": ["0"],
            "流失": ["0"],
            "待遇支付": ["0"],
        }
    )
    new_df = legacy_df.copy()

    diffs = compare.compare_numeric_fields(legacy_df, new_df)
    assert any(
        d.field == "期初资产规模" and d.diff_type == "INVALID_NUMERIC_VALUE" for d in diffs
    )


def test_compare_numeric_fields_flags_row_count_mismatch() -> None:
    compare = _import_compare_module()

    legacy_df = pd.DataFrame(
        {
            "期初资产规模": ["0"],
            "期末资产规模": ["0"],
            "供款": ["0"],
            "流失(含待遇支付)": ["0"],
            "流失": ["0"],
            "待遇支付": ["0"],
        }
    )
    new_df = pd.concat([legacy_df, legacy_df], ignore_index=True)

    diffs = compare.compare_numeric_fields(legacy_df, new_df)
    assert any(d.field == "__row_count__" and d.diff_type == "ROW_COUNT_MISMATCH" for d in diffs)

