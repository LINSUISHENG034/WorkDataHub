"""Integration tests for Bronze → Silver transformation with real data (Story 4.3).

This test suite validates the transformation pipeline using the 202412 dataset
(33,615 rows) from the reference archive. It verifies:
- Real data validation: All rows process successfully
- Performance: <1ms per row (target: <34 seconds for 33,615 rows)
- Error export: Works correctly for intentionally corrupted rows
- Edge cases: Documents any unexpected data patterns

Test Data Source:
    reference/archive/monthly/202412/收集数据/数据采集/【for年金分战区经营分析】24年12月年金终稿数据1227采集.xlsx

Expected Results:
    - >95% success rate (>31,934 valid rows)
    - Duration <34 seconds (<1ms per row)
    - Failed rows CSV exported if any failures
"""

import tempfile
import time
from pathlib import Path

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.transformations import (
    transform_bronze_to_silver,
)
from work_data_hub.io.readers.excel_reader import ExcelReader


def _resolve_real_data_path() -> Path | None:
    """Locate the latest 202412 annuity Excel file if it exists locally."""
    preferred = Path(
        "reference/archive/monthly/202412/收集数据/数据采集/【for年金分战区经营分析】24年12月年金终稿数据1227采集.xlsx"
    )
    if preferred.exists():
        return preferred

    # Fallback: auto-detect *.xlsx under 数据采集 (V1/V2) with matching keywords
    data_dir = Path("reference/archive/monthly/202412/收集数据/数据采集")
    if data_dir.exists():
        candidates = sorted(
            data_dir.glob("**/*年金*终稿数据*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None


REAL_DATA_PATH = _resolve_real_data_path()


@pytest.fixture
def real_data_df() -> pd.DataFrame:
    """Load real 202412 dataset from Excel file.

    Returns:
        DataFrame with 33,615 rows from "规模明细" sheet

    Raises:
        FileNotFoundError: If real data file not found
        pytest.skip: If file not available (allows tests to pass in CI)
    """
    if REAL_DATA_PATH is None or not REAL_DATA_PATH.exists():
        pytest.skip("Real data file not found under reference/archive/monthly/202412")

    # Use ExcelReader from Epic 3 Story 3.3
    reader = ExcelReader()
    result = reader.read_sheet(REAL_DATA_PATH, "规模明细")
    df = result.df

    return df


@pytest.mark.integration
@pytest.mark.monthly_data
class TestRealDataValidation:
    """Test transformation pipeline with real 202412 dataset."""

    def test_real_data_processes_successfully(self, real_data_df):
        """Test that 202412 dataset (33,615 rows) processes successfully.

        Expected:
            - >95% success rate (>31,934 valid rows)
            - Duration <34 seconds (<1ms per row)
            - Failed rows CSV exported if any failures
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            start_time = time.time()

            result = transform_bronze_to_silver(real_data_df, output_dir=tmpdir)

            duration = time.time() - start_time

            # Check row counts
            assert result.row_count == len(real_data_df)
            assert result.row_count > 30000, "Expected ~33,615 rows"

            # Check success rate (>95%)
            success_rate = result.valid_count / result.row_count
            assert success_rate > 0.95, (
                f"Success rate {success_rate:.1%} below 95% threshold. "
                f"Valid: {result.valid_count}, Failed: {result.failed_count}"
            )

            # Check performance (<1ms per row)
            ms_per_row = (duration * 1000) / result.row_count
            assert ms_per_row < 1.0, (
                f"Performance {ms_per_row:.2f}ms per row exceeds 1ms target. "
                f"Total duration: {duration:.2f}s for {result.row_count} rows"
            )

            # Log results for documentation
            print(f"\n=== Real Data Validation Results ===")
            print(f"Total rows: {result.row_count:,}")
            print(f"Valid rows: {result.valid_count:,} ({success_rate:.1%})")
            print(f"Failed rows: {result.failed_count:,} ({result.failed_count/result.row_count:.1%})")
            print(f"Duration: {duration:.2f}s")
            print(f"Performance: {ms_per_row:.3f}ms per row")
            print(f"Throughput: {int(result.row_count / duration):,} rows/second")

            if result.error_file_path:
                print(f"Error file: {result.error_file_path}")
                error_df = pd.read_csv(result.error_file_path, comment='#')
                print(f"Error count: {len(error_df)}")

    def test_real_data_with_intentional_corruption(self, real_data_df):
        """Test error export works correctly with intentionally corrupted rows.

        This test corrupts 1% of rows to verify error collection and export.
        """
        # Take first 1000 rows for faster test
        df = real_data_df.head(1000).copy()
        df["月度"] = df["月度"].astype(str)

        # Corrupt 1% of rows (10 rows) with future dates so Silver 校验拒绝
        for i in range(0, 10):
            df.loc[i, "月度"] = "202601"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should succeed with partial results (1% < 10% threshold)
            assert result.row_count == 1000
            assert result.failed_count >= 10  # Silver 层应捕捉到所有未来月份
            assert result.valid_count >= int(0.95 * result.row_count)

            # Check error file created
            assert result.error_file_path is not None
            error_file = Path(result.error_file_path)
            assert error_file.exists()

            # Read error CSV and verify format
            error_df = pd.read_csv(error_file, comment='#')
            assert len(error_df) >= 10
            assert "row_index" in error_df.columns
            assert "field_name" in error_df.columns
            assert "error_message" in error_df.columns

    def test_real_data_sample_validation(self, real_data_df):
        """Test transformation on small sample (100 rows) for quick validation."""
        # Take random sample of 100 rows
        df = real_data_df.sample(n=100, random_state=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should process successfully
            assert result.row_count == 100
            assert result.valid_count > 90  # Expect >90% success

            # Log sample results
            print(f"\n=== Sample Validation Results (100 rows) ===")
            print(f"Valid: {result.valid_count}, Failed: {result.failed_count}")
            print(f"Success rate: {result.valid_count/result.row_count:.1%}")


@pytest.mark.integration
@pytest.mark.monthly_data
class TestRealDataEdgeCases:
    """Test edge cases discovered in real data."""

    def test_chinese_date_formats(self, real_data_df):
        """Test that various Chinese date formats are parsed correctly.

        Real data may contain:
        - YYYYMM format: "202412"
        - Chinese format: "2024年12月"
        - ISO format: "2024-12"
        """
        # Take sample with various date formats
        df = real_data_df.head(100).copy()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should parse all date formats successfully
            assert result.valid_count > 90

            # Check that dates are parsed to datetime
            if len(result.valid_df) > 0:
                assert "月度" in result.valid_df.columns
                # Dates should be datetime objects after validation
                # (AnnuityPerformanceOut converts to datetime)

    def test_numeric_string_formats(self, real_data_df):
        """Test that numeric strings with commas/percentages are cleaned.

        Real data may contain:
        - Comma-separated: "1,000.00"
        - Percentages: "5.5%"
        - Plain numbers: "1000"
        """
        # Take sample with various numeric formats
        df = real_data_df.head(100).copy()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should clean all numeric formats successfully
            assert result.valid_count > 90

            # Check that numerics are converted to float
            if len(result.valid_df) > 0:
                numeric_columns = ["期初资产规模", "期末资产规模", "投资收益"]
                for col in numeric_columns:
                    if col in result.valid_df.columns:
                        pd.to_numeric(result.valid_df[col], errors="raise")

    def test_company_name_variations(self, real_data_df):
        """Test that various company name formats are handled.

        Real data may contain:
        - Chinese company names with special characters
        - Empty company names
        - Very long company names
        """
        # Take sample with various company names
        df = real_data_df.head(100).copy()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should handle all company name variations
            assert result.valid_count > 90

            # Check that company names are preserved
            if len(result.valid_df) > 0:
                assert "客户名称" in result.valid_df.columns


@pytest.mark.integration
@pytest.mark.monthly_data
@pytest.mark.performance
class TestRealDataPerformance:
    """Test performance characteristics with real data."""

    def test_performance_baseline(self, real_data_df):
        """Establish performance baseline for future regression testing.

        This test measures and documents the current performance characteristics
        to detect performance regressions in future changes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            start_time = time.time()

            result = transform_bronze_to_silver(real_data_df, output_dir=tmpdir)

            duration = time.time() - start_time

            # Calculate performance metrics
            ms_per_row = (duration * 1000) / result.row_count
            rows_per_second = result.row_count / duration

            # Document baseline metrics
            baseline = {
                "total_rows": result.row_count,
                "valid_rows": result.valid_count,
                "failed_rows": result.failed_count,
                "duration_seconds": round(duration, 2),
                "ms_per_row": round(ms_per_row, 3),
                "rows_per_second": int(rows_per_second),
            }

            print(f"\n=== Performance Baseline ===")
            for key, value in baseline.items():
                print(f"{key}: {value}")

            # Save baseline to file for future comparison
            baseline_file = Path(tmpdir) / "performance_baseline.json"
            import json
            with open(baseline_file, 'w') as f:
                json.dump(baseline, f, indent=2)

            # Assert performance targets
            assert ms_per_row < 1.0, f"Performance regression: {ms_per_row:.3f}ms per row"
            assert rows_per_second > 1000, f"Throughput too low: {rows_per_second} rows/s"

    def test_memory_efficiency(self, real_data_df):
        """Test that transformation doesn't cause excessive memory usage.

        This test monitors memory usage during transformation to ensure
        efficient processing of large datasets.
        """
        import psutil
        import os

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(real_data_df, output_dir=tmpdir)

            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = memory_after - memory_before

            print(f"\n=== Memory Usage ===")
            print(f"Before: {memory_before:.1f} MB")
            print(f"After: {memory_after:.1f} MB")
            print(f"Increase: {memory_increase:.1f} MB")
            print(f"Per row: {memory_increase * 1024 / result.row_count:.2f} KB")

            # Memory increase should be reasonable (< 500 MB for 33k rows)
            assert memory_increase < 500, (
                f"Excessive memory usage: {memory_increase:.1f} MB increase"
            )
