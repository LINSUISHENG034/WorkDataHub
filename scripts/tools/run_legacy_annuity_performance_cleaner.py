#!/usr/bin/env python3
"""
Legacy Annuity Performance Cleaner Baseline Generator

Generates a deterministic "golden" dataset by executing the extracted logic
from the real `AnnuityPerformanceCleaner` against curated Excel fixtures.
This avoids legacy MySQL dependencies by containing only the transformation logic.

Usage:
    python scripts/tools/run_legacy_annuity_performance_cleaner.py \
        --inputs tests/fixtures/sample_data/annuity_subsets \
        --output tests/fixtures/annuity_performance/golden_legacy.parquet \
        --mappings tests/fixtures/sample_legacy_mappings.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import numpy as np
import dateutil.parser as dp

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOGGER = logging.getLogger(__name__)


def parse_to_standard_date(data):
    """
    Convert date data to standard format - extracted from legacy common_utils.
    """
    if isinstance(data, (date, datetime)):
        return data
    else:
        date_string = str(data)

    try:
        # Match YYYY年MM月 or YY年MM月 format
        if re.match(r'(\d{2}|\d{4})年\d{1,2}月$', date_string):
            return datetime.strptime(date_string + '1日', '%Y年%m月%d日')

        # Match YYYY年MM月DD日 or YY年MM月DD日 format
        elif re.match(r'(\d{2}|\d{4})年\d{1,2}月\d{1,2}日$', date_string):
            return datetime.strptime(date_string, '%Y年%m月%d日')

        # Match YYYYMMDD format
        elif re.match(r'\d{8}', date_string):
            return datetime.strptime(date_string, '%Y%m%d')

        # Match YYYYMM format
        elif re.match(r'\d{6}', date_string):
            return datetime.strptime(date_string + '01', '%Y%m%d')

        # Match YYYY-MM format
        elif re.match(r'\d{4}-\d{2}', date_string):
            return datetime.strptime(date_string + '-01', '%Y-%m-%d')

        # Match other formats
        else:
            return dp.parse(date_string)

    except (ValueError, TypeError):
        return data


def clean_company_name(name: str) -> str:
    """
    Basic company name cleaning - simplified from legacy common_utils.
    """
    if not name:
        return ''

    # Remove extra spaces
    name = re.sub(r'\s+', '', name)

    # Remove specified characters
    name = re.sub(r'及下属子企业', '', name)
    name = re.sub(r'(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$', '', name)

    # Simple cleanup for common suffixes
    suffixes_to_remove = [
        '已转出', '待转出', '终止', '转出', '转移终止', '已作废', '已终止',
        '保留', '保留账户', '存量', '已转移终止', '本部', '未使用', '集合', '原'
    ]

    for suffix in suffixes_to_remove:
        if name.endswith(suffix):
            name = name[:-len(suffix)]

    return name


def load_mapping_fixture(path: Path) -> Dict[str, Any]:
    """Load mapping dictionaries from JSON fixture."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        LOGGER.info("Loaded mapping fixture from %s", path)
        return data.get("mappings", {})
    except Exception as exc:
        raise RuntimeError(f"Failed to load mapping fixture: {path}") from exc


def _extract_mapping_data(mappings: Dict[str, Any], key: str, fallback: Dict[str, Any] = None) -> Dict[str, Any]:
    """Extract mapping data from fixture."""
    if fallback is None:
        fallback = {}

    entry = mappings.get(key)
    if entry and isinstance(entry, dict):
        data = entry.get("data")
        if isinstance(data, dict):
            return data
    return fallback


class ExtractedAnnuityPerformanceCleaner:
    """
    Extracted transformation logic from legacy AnnuityPerformanceCleaner._clean_method()

    This contains only the data transformation logic without any database dependencies.
    """

    def __init__(self, mappings: Dict[str, Any]):
        """Initialize with mapping dictionaries from fixture."""
        # Extract all required mappings
        self.COMPANY_ID1_MAPPING = _extract_mapping_data(mappings, "company_id1_mapping")
        self.COMPANY_ID2_MAPPING = _extract_mapping_data(mappings, "company_id2_mapping")
        self.COMPANY_ID3_MAPPING = _extract_mapping_data(mappings, "company_id3_mapping")
        self.COMPANY_ID4_MAPPING = _extract_mapping_data(mappings, "company_id4_mapping")
        self.COMPANY_ID5_MAPPING = _extract_mapping_data(mappings, "company_id5_mapping")

        self.COMPANY_BRANCH_MAPPING = _extract_mapping_data(mappings, "company_branch_mapping")
        self.BUSINESS_TYPE_CODE_MAPPING = _extract_mapping_data(mappings, "business_type_code_mapping")

        # Default portfolio code mapping with fallbacks
        self.DEFAULT_PORTFOLIO_CODE_MAPPING = _extract_mapping_data(
            mappings, "default_portfolio_code_mapping",
            fallback={"集合计划": "QTAN001", "单一计划": "QTAN002", "职业年金": "QTAN003"}
        )

    def load_excel_data(self, excel_path: Path, sheet_name: str = "规模明细") -> pd.DataFrame:
        """Load Excel data with proper encoding and string handling."""
        try:
            # Read with string dtype to preserve leading zeros (as in legacy code)
            df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
            LOGGER.debug(f"Loaded {len(df)} rows from {excel_path.name}, sheet: {sheet_name}")
            return df
        except Exception as e:
            LOGGER.error(f"Failed to load Excel data from {excel_path}: {e}")
            raise

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the exact transformation logic from legacy AnnuityPerformanceCleaner._clean_method()

        This is a direct extraction of the transformation steps from the legacy cleaner.
        """
        if df.empty:
            LOGGER.warning("Input DataFrame is empty")
            return df

        # Make a copy to avoid modifying original
        df = df.copy()

        # Step 1: Column renaming (exact match to legacy)
        df.rename(columns={
            '机构': '机构名称',
            '计划号': '计划代码',
            '流失（含待遇支付）': '流失(含待遇支付)'
        }, inplace=True)

        # Step 2: Fix institution codes using institution name mapping
        if '机构名称' in df.columns:
            df['机构代码'] = df['机构名称'].map(self.COMPANY_BRANCH_MAPPING)

        # Step 3: Fix dates
        if '月度' in df.columns:
            df['月度'] = df['月度'].apply(parse_to_standard_date)

        # Step 4: Fix plan codes
        if '计划代码' in df.columns:
            df['计划代码'] = df['计划代码'].replace({
                '1P0290': 'P0290',
                '1P0807': 'P0807'
            })

            # Handle empty plan codes based on plan type
            if '计划类型' in df.columns:
                df['计划代码'] = df['计划代码'].mask(
                    (df['计划代码'].isna() | (df['计划代码'] == '')) & (df['计划类型'] == '集合计划'), 'AN001')
                df['计划代码'] = df['计划代码'].mask(
                    (df['计划代码'].isna() | (df['计划代码'] == '')) & (df['计划类型'] == '单一计划'), 'AN002')

        # Step 5: Replace null institution codes with G00
        if '机构代码' in df.columns:
            df['机构代码'] = df['机构代码'].replace('null', 'G00')
            df['机构代码'] = df['机构代码'].fillna('G00')

        # Step 6: Safe operation - fix portfolio codes
        if '组合代码' not in df.columns:
            df['组合代码'] = np.nan
        else:
            # Remove 'F' prefix from portfolio codes
            df['组合代码'] = df['组合代码'].str.replace('^F', '', regex=True)

        # Step 7: Set default portfolio codes
        if '组合代码' in df.columns and '业务类型' in df.columns and '计划类型' in df.columns:
            df['组合代码'] = df['组合代码'].mask(
                (df['组合代码'].isna() | (df['组合代码'] == '')),
                df.apply(
                    lambda x: 'QTAN003' if x['业务类型'] in ['职年受托', '职年投资']
                    else self.DEFAULT_PORTFOLIO_CODE_MAPPING.get(x['计划类型']),
                    axis=1
                )
            )

        # Step 8: Map business type codes
        if '业务类型' in df.columns:
            df['产品线代码'] = df['业务类型'].map(self.BUSINESS_TYPE_CODE_MAPPING)

        # Step 9: Fix customer names
        if '客户名称' in df.columns:
            df['年金账户名'] = df['客户名称']
            df['客户名称'] = df['客户名称'].apply(
                lambda x: clean_company_name(x) if isinstance(x, str) else x
            )

        # Step 10-14: Company ID resolution (5-step priority algorithm)
        self._apply_company_id_resolution(df)

        # Step 15: Remove invalid fields (same as legacy)
        columns_to_drop = [
            '备注', '子企业号', '子企业名称', '集团企业客户号', '集团企业客户名称'
        ]
        df.drop(columns=columns_to_drop, inplace=True, errors='ignore')

        return df

    def _apply_company_id_resolution(self, df: pd.DataFrame) -> None:
        """
        Apply the exact 5-step company_id resolution algorithm from legacy cleaner.
        """
        # Step 1: Map by plan code (priority 1)
        if '计划代码' in df.columns:
            df['company_id'] = df['计划代码'].map(self.COMPANY_ID1_MAPPING)

        # Clean enterprise customer number
        if '集团企业客户号' in df.columns:
            df['集团企业客户号'] = df['集团企业客户号'].str.lstrip('C')

        # Step 2: Map by enterprise customer number (priority 2)
        if '集团企业客户号' in df.columns:
            mask = df['company_id'].isna() | (df['company_id'] == '')
            company_id_from_group = df['集团企业客户号'].map(self.COMPANY_ID2_MAPPING)
            df.loc[mask, 'company_id'] = company_id_from_group[mask]

        # Step 3: Handle special cases with default value '600866980'
        if '客户名称' in df.columns and '计划代码' in df.columns:
            mask = ((df['company_id'].isna() | (df['company_id'] == '')) &
                   (df['客户名称'].isna() | (df['客户名称'] == '')))
            company_id_from_plan = df['计划代码'].map(self.COMPANY_ID3_MAPPING).fillna('600866980')
            df.loc[mask, 'company_id'] = company_id_from_plan[mask]

        # Step 4: Map by customer name (priority 4)
        if '客户名称' in df.columns:
            mask = df['company_id'].isna() | (df['company_id'] == '')
            company_id_from_customer = df['客户名称'].map(self.COMPANY_ID4_MAPPING)
            df.loc[mask, 'company_id'] = company_id_from_customer[mask]

        # Step 5: Map by account name (priority 5)
        if '年金账户名' in df.columns:
            mask = df['company_id'].isna() | (df['company_id'] == '')
            company_id_from_account = df['年金账户名'].map(self.COMPANY_ID5_MAPPING)
            df.loc[mask, 'company_id'] = company_id_from_account[mask]


def discover_excel_files(root: Path) -> List[Path]:
    """Return a sorted list of Excel files under *root*."""
    if root.is_file() and root.suffix.lower() in {".xlsx", ".xls"}:
        return [root]

    patterns = ("*.xlsx", "*.xls")
    files: List[Path] = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    for sub in root.iterdir():
        if sub.is_dir():
            for pattern in patterns:
                files.extend(sub.glob(pattern))
    files = sorted({f.resolve() for f in files})
    LOGGER.info("Discovered %d Excel files under %s", len(files), root)
    return list(files)


def process_excel_file(cleaner: ExtractedAnnuityPerformanceCleaner, excel_path: Path, sheet_name: str) -> pd.DataFrame:
    """Process a single Excel file using the extracted cleaner."""
    LOGGER.debug("Processing %s (sheet=%s)", excel_path.name, sheet_name)
    df = cleaner.load_excel_data(excel_path, sheet_name)
    if df.empty:
        LOGGER.warning("No rows loaded from %s", excel_path.name)
        return df

    cleaned_df = cleaner.clean(df)
    if not cleaned_df.empty:
        cleaned_df["_source_file"] = excel_path.name

    return cleaned_df


def canonicalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply deterministic sorting for reproducible output."""
    if df.empty:
        return df
    sort_cols: List[str] = [col for col in ("月度", "计划代码", "company_id") if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, na_position="last")
    return df.reset_index(drop=True)


def save_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """Save DataFrame as Parquet with proper data type preservation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, compression="snappy", engine="pyarrow")
    LOGGER.info("Wrote %d rows to %s", len(df), output_path)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True, help="Excel file or directory of Excel files")
    parser.add_argument("--output", type=Path, required=True, help="Output Parquet path for golden baseline")
    parser.add_argument("--mappings", type=Path, required=True, help="JSON file containing mapping dictionaries")
    parser.add_argument("--sheet", default="规模明细", help="Sheet name to process (default: 规模明细)")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if not args.inputs.exists():
        LOGGER.error("Inputs path does not exist: %s", args.inputs)
        return 1
    if not args.mappings.exists():
        LOGGER.error("Mappings fixture does not exist: %s", args.mappings)
        return 1

    # Load mappings and create cleaner
    mapping_fixture = load_mapping_fixture(args.mappings)
    cleaner = ExtractedAnnuityPerformanceCleaner(mapping_fixture)

    # Discover and process Excel files
    excel_files = discover_excel_files(args.inputs)
    if not excel_files:
        LOGGER.error("No Excel files found under %s", args.inputs)
        return 1

    dataframes: List[pd.DataFrame] = []
    for excel_file in excel_files:
        try:
            df = process_excel_file(cleaner, excel_file, args.sheet)
            if not df.empty:
                dataframes.append(df)
        except Exception as e:
            LOGGER.error("Failed to process %s: %s", excel_file, e)
            # Continue with other files
            continue

    if not dataframes:
        LOGGER.error("All Excel files produced empty data")
        return 1

    # Combine and canonicalize results
    combined = canonicalize_dataframe(pd.concat(dataframes, ignore_index=True))
    if combined.empty:
        LOGGER.error("Combined dataframe is empty")
        return 1

    # Save golden baseline
    save_parquet(combined, args.output)
    LOGGER.info("Baseline generation completed successfully")
    LOGGER.info("Final dataset: %d rows, %d columns", len(combined), len(combined.columns))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
