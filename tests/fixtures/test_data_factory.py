"""Test data factory for creating realistic test fixtures from production data.

This module provides utilities to create test data based on actual production
Excel files, with proper anonymization of PII (company names).

Usage:
    >>> factory = AnnuityTestDataFactory()
    >>> valid_df = factory.create_valid_sample(n=100)
    >>> invalid_df = factory.create_invalid_sample(n=50, error_type='date')
"""

import hashlib
import re
from pathlib import Path
from typing import List, Literal, Optional

import pandas as pd


class AnnuityTestDataFactory:
    """Factory for creating realistic annuity test data from production samples.

    This factory reads real production data and creates anonymized test fixtures
    that maintain realistic distributions, edge cases, and data quality issues.

    Features:
    - Anonymizes company names while preserving structure
    - Maintains realistic data distributions (business types, plan types)
    - Includes real edge cases (negative numbers, missing values)
    - Creates both valid and intentionally invalid test data

    Example:
        >>> factory = AnnuityTestDataFactory()
        >>>
        >>> # Create 100 valid rows for integration tests
        >>> valid_df = factory.create_valid_sample(n=100)
        >>>
        >>> # Create 50 rows with invalid dates
        >>> invalid_df = factory.create_invalid_sample(n=50, error_type='date')
        >>>
        >>> # Create 10K rows for performance tests
        >>> perf_df = factory.create_performance_fixture(n=10000)
    """

    def __init__(self, source_file: Optional[Path] = None):
        """Initialize factory with production data source.

        Args:
            source_file: Path to production Excel file.
                        Defaults to tests/fixtures/sample_data/*.xlsx
        """
        if source_file is None:
            # Use the actual production file in fixtures
            source_file = Path(__file__).parent / 'sample_data' / '【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx'

        self.source_file = source_file
        self._production_df: Optional[pd.DataFrame] = None

    @property
    def production_df(self) -> pd.DataFrame:
        """Lazy load production data.

        Raises:
            FileNotFoundError: If source file does not exist, with helpful message
                about expected location and alternative data sources.
        """
        if self._production_df is None:
            if not self.source_file.exists():
                alt_paths = [
                    "tests/fixtures/real_data/202411/收集数据/数据采集/V1/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx",
                    "tests/fixtures/real_data/202412/收集数据/数据采集/V2/【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx",
                ]
                raise FileNotFoundError(
                    f"Production data file not found: {self.source_file}\n"
                    f"Expected location: tests/fixtures/sample_data/\n"
                    f"Alternative sources (if available):\n"
                    + "\n".join(f"  - {p}" for p in alt_paths)
                    + "\n\nTo use an alternative source, pass source_file parameter:\n"
                    "  factory = AnnuityTestDataFactory(source_file=Path('path/to/file.xlsx'))"
                )
            self._production_df = pd.read_excel(
                self.source_file,
                sheet_name='规模明细'
            )
        return self._production_df

    def anonymize_company_name(self, name: str) -> str:
        """Anonymize company name while preserving structure.

        Replaces real company names with anonymized versions that maintain
        similar length and structure for realistic testing.

        Args:
            name: Original company name

        Returns:
            Anonymized company name

        Example:
            >>> factory = AnnuityTestDataFactory()
            >>> factory.anonymize_company_name('北京测试科技有限公司')
            '测试公司A1B2'
        """
        if pd.isna(name):
            return name

        # Generate deterministic hash for consistent anonymization
        hash_suffix = hashlib.md5(str(name).encode()).hexdigest()[:4].upper()

        # Preserve company type suffixes
        company_types = ['有限公司', '股份有限公司', '集团', '责任公司', '公司']
        suffix = next((t for t in company_types if str(name).endswith(t)), '')

        # Create anonymized name
        return f"测试企业{hash_suffix}{suffix}"

    def create_valid_sample(
        self,
        n: int = 100,
        include_edge_cases: bool = True
    ) -> pd.DataFrame:
        """Create sample of valid test data from production data.

        Args:
            n: Number of rows to generate
            include_edge_cases: Whether to include realistic edge cases
                              (negative numbers, missing values, etc.)

        Returns:
            DataFrame with valid test data (all fields present, realistic values)

        Example:
            >>> factory = AnnuityTestDataFactory()
            >>> df = factory.create_valid_sample(n=100)
            >>> assert len(df) == 100
            >>> assert df['月度'].notna().all()  # All dates valid
        """
        # Sample from production data
        sample = self.production_df.sample(n=n, random_state=42).copy()

        # Anonymize PII
        sample['客户名称'] = sample['客户名称'].apply(self.anonymize_company_name)
        sample['计划名称'] = sample['计划名称'].apply(
            lambda x: f"测试计划{hashlib.md5(str(x).encode()).hexdigest()[:6]}" if pd.notna(x) else x
        )
        sample['组合名称'] = sample['组合名称'].apply(self.anonymize_company_name)

        # Add required fields for Pydantic model (Story 2.1)
        sample['company_id'] = sample['客户名称'].apply(
            lambda x: f"ID{hashlib.md5(str(x).encode()).hexdigest()[:8]}" if pd.notna(x) else "ID_TEMP"
        )
        sample['id'] = sample.apply(
            lambda row: f"{row['月度']}_{row['计划代码']}_{row.name}",
            axis=1
        )

        # Add missing optional fields that are commonly present in production data
        # These fields are Optional in Pydantic model but needed for realistic tests
        if '业务类型' not in sample.columns:
            sample['业务类型'] = '企业年金'
        if '计划类型' not in sample.columns:
            sample['计划类型'] = '固定缴费型'
        if '组合类型' not in sample.columns:
            sample['组合类型'] = '测试组合'
        if '机构代码' not in sample.columns:
            sample['机构代码'] = 'ORG001'
        if '机构名称' not in sample.columns:
            sample['机构名称'] = '测试机构'
        if '产品线代码' not in sample.columns:
            sample['产品线代码'] = 'PROD001'
        if '年金账户号' not in sample.columns:
            sample['年金账户号'] = sample.apply(
                lambda row: f"ACC{hashlib.md5(str(row['计划代码']).encode()).hexdigest()[:6]}",
                axis=1
            )
        if '年金账户名' not in sample.columns:
            sample['年金账户名'] = sample['客户名称'] + '年金账户'
        if '组合代码' not in sample.columns:
            sample['组合代码'] = sample['计划代码'].apply(lambda x: f"COMBO_{x}" if pd.notna(x) else "COMBO_DEFAULT")

        # Fill missing values for required fields
        if not include_edge_cases:
            sample['计划代码'] = sample['计划代码'].fillna('PLAN_DEFAULT')
            sample['客户名称'] = sample['客户名称'].fillna('测试客户DEFAULT')
            sample['期初资产规模'] = sample['期初资产规模'].fillna(0)
            sample['期末资产规模'] = sample['期末资产规模'].fillna(0)
            sample['供款'] = sample['供款'].fillna(0)
            sample['流失(含待遇支付)'] = sample['流失(含待遇支付)'].fillna(0)
            sample['流失'] = sample['流失'].fillna(0)
            sample['待遇支付'] = sample['待遇支付'].fillna(0)
            sample['投资收益'] = sample['投资收益'].fillna(0)

            # Ensure no negative values
            numeric_cols = ['期初资产规模', '期末资产规模', '供款']
            for col in numeric_cols:
                sample.loc[sample[col] < 0, col] = 0

        # Add critical Bronze schema required column if missing (after fillna)
        if '年化收益率' not in sample.columns:
            # Calculate from 当期收益率 if available, otherwise use default
            if '当期收益率' in sample.columns:
                sample['年化收益率'] = sample['当期收益率'].fillna(0.05)
            else:
                sample['年化收益率'] = 0.05  # Default 5% annual return
        elif sample['年化收益率'].isna().all():
            # Column exists but all values are NaN
            if '当期收益率' in sample.columns:
                sample['年化收益率'] = sample['当期收益率'].fillna(0.05)
            else:
                sample['年化收益率'] = 0.05

        # Rename columns to match Pydantic model (Story 2.1)
        column_mapping = {
            '流失(含待遇支付)': '流失_含待遇支付'
        }
        sample = sample.rename(columns=column_mapping)

        return sample

    def create_annuity_income_sample(
        self,
        n: int = 100,
        month: str = "202412",
        include_edge_cases: bool = True,
    ) -> pd.DataFrame:
        """Create sample data aligned to annuity_income schema (four income fields).

        - Provides plan code under 计划号 (falls back to 计划代码 or generated)
        - Ensures 机构 / 机构名称 present for alias mapping
        - Generates 固费/浮费/回补/税 from asset scale to avoid artificial 收入金额
        """
        df = self.create_valid_sample(n=n, include_edge_cases=include_edge_cases).copy()
        df["月度"] = int(month)

        if "计划号" not in df.columns:
            if "计划代码" in df.columns:
                df = df.rename(columns={"计划代码": "计划号"})
            else:
                df["计划号"] = [f"PLAN{i:04d}" for i in range(n)]

        if "机构名称" not in df.columns:
            df["机构名称"] = "北京"
        if "机构" not in df.columns:
            df["机构"] = df["机构名称"]

        if "业务类型" not in df.columns:
            df["业务类型"] = "企年投资"
        if "计划类型" not in df.columns:
            df["计划类型"] = "单一计划"
        if "组合代码" not in df.columns:
            df["组合代码"] = [f"QTAN{i:03d}" for i in range(n)]

        # Generate four income fields from a stable numeric base
        base = df["期末资产规模"] if "期末资产规模" in df.columns else pd.Series([1_000_000] * n)
        base = base.fillna(1_000_000).abs()
        df["固费"] = (base * 0.015).round(2)
        df["浮费"] = (base * 0.01).round(2)
        df["回补"] = (base * 0.005).round(2)
        df["税"] = ((df["固费"] + df["浮费"] + df["回补"]) * 0.05).round(2)

        return df

    def create_invalid_sample(
        self,
        n: int = 50,
        error_type: Literal['date', 'negative', 'empty', 'mixed'] = 'mixed',
        error_rate: float = 0.3
    ) -> pd.DataFrame:
        """Create sample with intentional validation errors.

        Args:
            n: Number of rows to generate
            error_type: Type of errors to inject:
                - 'date': Invalid date formats
                - 'negative': Negative values in non-negative fields
                - 'empty': Empty required fields
                - 'mixed': Mix of all error types
            error_rate: Proportion of rows with errors (0.0 to 1.0)

        Returns:
            DataFrame with intentional validation errors

        Example:
            >>> factory = AnnuityTestDataFactory()
            >>> df = factory.create_invalid_sample(n=50, error_type='date', error_rate=0.4)
            >>> # ~40% of rows will have invalid dates
        """
        # Start with valid sample
        sample = self.create_valid_sample(n=n, include_edge_cases=False)

        # Calculate number of rows to corrupt
        n_errors = int(n * error_rate)
        error_indices = sample.sample(n=n_errors, random_state=42).index

        if error_type in ['date', 'mixed']:
            # Inject invalid dates
            n_date_errors = n_errors if error_type == 'date' else n_errors // 3
            date_error_indices = error_indices[:n_date_errors]
            invalid_dates = ['INVALID', 'BAD_DATE', '99999999', 'NULL', '0']
            # Cycle through invalid dates for each error index
            for i, idx in enumerate(date_error_indices):
                sample.loc[idx, '月度'] = invalid_dates[i % len(invalid_dates)]

        if error_type in ['negative', 'mixed']:
            # Inject negative values
            n_neg_errors = n_errors if error_type == 'negative' else n_errors // 3
            neg_error_indices = error_indices[n_errors//3:n_errors//3 + n_neg_errors] if error_type == 'mixed' else error_indices[:n_neg_errors]
            sample.loc[neg_error_indices, '期末资产规模'] = -1000.0

        if error_type in ['empty', 'mixed']:
            # Inject empty required fields
            n_empty_errors = n_errors if error_type == 'empty' else n_errors // 3
            empty_error_indices = error_indices[2*n_errors//3:] if error_type == 'mixed' else error_indices[:n_empty_errors]
            sample.loc[empty_error_indices, '计划代码'] = ''

        return sample

    def create_performance_fixture(
        self,
        n: int = 10000,
        valid_rate: float = 0.9
    ) -> pd.DataFrame:
        """Create large fixture for performance testing (AC-PERF).

        Args:
            n: Number of rows (minimum 10,000 for Epic 2 AC-PERF)
            valid_rate: Proportion of valid rows (0.9 = 90% valid, 10% invalid)

        Returns:
            DataFrame with realistic mix of valid/invalid data for performance tests

        Example:
            >>> factory = AnnuityTestDataFactory()
            >>> df = factory.create_performance_fixture(n=10000)
            >>> assert len(df) == 10000
            >>> # ~90% valid, ~10% invalid (realistic error rate)
        """
        if n < 10000:
            raise ValueError("Performance fixtures must have ≥10,000 rows (Epic 2 AC-PERF)")

        # Create mostly valid data
        n_valid = int(n * valid_rate)
        n_invalid = n - n_valid

        valid_df = self.create_valid_sample(n=n_valid, include_edge_cases=True)
        invalid_df = self.create_invalid_sample(
            n=n_invalid,
            error_type='mixed',
            error_rate=1.0  # All invalid rows have errors
        )

        # Combine and shuffle
        combined = pd.concat([valid_df, invalid_df], ignore_index=True)
        combined = combined.sample(frac=1.0, random_state=42).reset_index(drop=True)

        return combined

    def save_fixture(
        self,
        df: pd.DataFrame,
        filename: str,
        output_dir: Optional[Path] = None
    ) -> Path:
        """Save test fixture to CSV file.

        Args:
            df: DataFrame to save
            filename: Output filename (e.g., 'integration_test_100.csv')
            output_dir: Output directory (defaults to tests/fixtures/performance/)

        Returns:
            Path to saved file

        Example:
            >>> factory = AnnuityTestDataFactory()
            >>> df = factory.create_valid_sample(n=100)
            >>> path = factory.save_fixture(df, 'integration_valid_100.csv')
        """
        if output_dir is None:
            output_dir = Path(__file__).parent / 'performance'

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename

        df.to_csv(output_path, index=False, encoding='utf-8')
        return output_path
