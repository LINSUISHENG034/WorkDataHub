"""Unit tests for Bronze → Silver transformation pipeline (Story 4.3).

This test suite validates the transformation pipeline that integrates:
- Bronze validation (Story 4.2): DataFrame-level structural checks
- Silver validation (Story 4.1): Row-level business rule validation
- Error collection and export (Epic 2 Story 2.5): Failed rows CSV export
- Partial success handling (Architecture Decision #6): <10% failure threshold

Test Coverage:
- AC-4.3.1: Bronze validation failure stops pipeline
- AC-4.3.2: Silver validation collects errors correctly
- AC-4.3.3: Partial success (<10% fail) returns valid DataFrame
- AC-4.3.3: Systemic failure (>10% fail) raises ValueError
- AC-4.3.3: Error export creates CSV with correct format
- AC-4.3.4: TransformationResult structure
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from pandera.errors import SchemaError

from work_data_hub.domain.annuity_performance.transformations import (
    TransformationResult,
    transform_bronze_to_silver,
)


def _build_valid_bronze_df(num_rows: int = 10) -> pd.DataFrame:
    """Build valid Bronze DataFrame for testing.

    Args:
        num_rows: Number of rows to generate

    Returns:
        DataFrame with all required Bronze columns and valid data
    """
    rows = []
    for i in range(num_rows):
        rows.append({
            "月度": f"2024{(i % 12) + 1:02d}",  # 使用历史月份，避免未来日期触发业务校验
            "计划代码": f"PLAN{i:03d}",
            "客户名称": f"公司{chr(65 + (i % 26))}",
            "期初资产规模": 1000.0 + i * 100,
            "期末资产规模": 2000.0 + i * 100,
            "投资收益": 500.0 + i * 10,
            "当期收益率": 0.05 + i * 0.001,
        })
    return pd.DataFrame(rows)


def _build_bronze_df_with_future_dates(valid_count: int, invalid_count: int) -> pd.DataFrame:
    """Construct rows where Silver 层因未来月份而报错，Bronze 可正常通过。"""
    df = _build_valid_bronze_df(valid_count + invalid_count)

    # 202812 虽然仍在解析允许范围，但会被 Silver 视为未来月份
    for i in range(valid_count, valid_count + invalid_count):
        df.loc[i, "月度"] = "202812"

    return df


def _build_bronze_df_with_negative_values(valid_count: int, invalid_count: int) -> pd.DataFrame:
    """Build Bronze DataFrame with mix of valid and negative asset values.

    Args:
        valid_count: Number of rows with valid values
        invalid_count: Number of rows with negative values

    Returns:
        DataFrame with mixed value validity
    """
    # Start with valid rows
    df = _build_valid_bronze_df(valid_count + invalid_count)

    # Set negative values in last invalid_count rows
    for i in range(valid_count, valid_count + invalid_count):
        df.loc[i, "期末资产规模"] = -1000.0

    return df


@pytest.mark.unit
class TestTransformationResult:
    """Test TransformationResult dataclass structure (AC-4.3.4)."""

    def test_result_structure(self):
        """Test that TransformationResult has all required fields."""
        result = TransformationResult(
            valid_df=pd.DataFrame([{"col": "val"}]),
            row_count=100,
            valid_count=95,
            failed_count=5,
            error_file_path="output/errors/test.csv"
        )

        assert isinstance(result.valid_df, pd.DataFrame)
        assert result.row_count == 100
        assert result.valid_count == 95
        assert result.failed_count == 5
        assert result.error_file_path == "output/errors/test.csv"

    def test_result_without_error_file(self):
        """Test that error_file_path can be None when no errors."""
        result = TransformationResult(
            valid_df=pd.DataFrame([{"col": "val"}]),
            row_count=100,
            valid_count=100,
            failed_count=0,
            error_file_path=None
        )

        assert result.error_file_path is None


@pytest.mark.unit
class TestBronzeValidationFailure:
    """Test Bronze validation failure stops pipeline (AC-4.3.1)."""

    def test_missing_required_column_raises_schema_error(self):
        """Test that missing required column raises SchemaError immediately."""
        df = _build_valid_bronze_df(10)
        df = df.drop(columns=["月度"])  # Remove required column

        with pytest.raises(SchemaError):
            transform_bronze_to_silver(df)

    def test_bronze_failure_stops_pipeline_immediately(self):
        """Test that Bronze failure prevents Silver validation from running."""
        df = _build_valid_bronze_df(10)
        df = df.drop(columns=["客户名称"])  # Remove required column

        # Should raise SchemaError before any Silver validation
        with pytest.raises(SchemaError):
            transform_bronze_to_silver(df)


@pytest.mark.unit
class TestSilverValidationErrorCollection:
    """Test Silver validation collects errors correctly (AC-4.3.2)."""

    def test_invalid_dates_collected_as_errors(self):
        """Silver 层应收集未来日期导致的业务错误，并在阈值超限时抛出 ValueError。"""
        df = _build_bronze_df_with_future_dates(valid_count=8, invalid_count=2)

        with pytest.raises(ValueError, match="Transformation failed"):
            transform_bronze_to_silver(df)

    def test_negative_values_collected_as_errors(self):
        """Test that rows with negative values are collected as errors."""
        # 8 valid, 2 negative values (20% failure - will raise ValueError)
        df = _build_bronze_df_with_negative_values(valid_count=8, invalid_count=2)

        # Should raise ValueError due to >10% failure
        with pytest.raises(ValueError, match="Transformation failed"):
            transform_bronze_to_silver(df)


@pytest.mark.unit
class TestPartialSuccess:
    """Test partial success (<10% fail) returns valid DataFrame (AC-4.3.3)."""

    def test_partial_success_under_threshold(self):
        """Test that <10% failure allows partial success."""
        # 95 valid, 5 invalid (5% failure - under threshold)
        df = _build_bronze_df_with_negative_values(valid_count=95, invalid_count=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should return valid rows only
            assert result.row_count == 100
            assert result.valid_count == 95
            assert result.failed_count == 5
            assert len(result.valid_df) == 95

            # Should export error file
            assert result.error_file_path is not None
            assert Path(result.error_file_path).exists()

    def test_exactly_10_percent_failure_allowed(self):
        """Test that exactly 10% failure is allowed (boundary case)."""
        # 90 valid, 10 invalid (10% failure - at threshold)
        df = _build_bronze_df_with_negative_values(valid_count=90, invalid_count=10)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should succeed with partial results
            assert result.row_count == 100
            assert result.valid_count == 90
            assert result.failed_count == 10
            assert len(result.valid_df) == 90

    def test_all_rows_valid_no_error_file(self):
        """Test that 100% success does not create error file."""
        df = _build_valid_bronze_df(100)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Should return all rows
            assert result.row_count == 100
            assert result.valid_count == 100
            assert result.failed_count == 0
            assert len(result.valid_df) == 100

            # Should NOT export error file
            assert result.error_file_path is None


@pytest.mark.unit
class TestSystemicFailure:
    """Test systemic failure (>10% fail) raises ValueError (AC-4.3.3)."""

    def test_over_10_percent_failure_raises_value_error(self):
        """Test that >10% failure raises ValueError with clear message."""
        # 85 valid, 15 invalid (15% failure - exceeds threshold)
        df = _build_bronze_df_with_negative_values(valid_count=85, invalid_count=15)

        with pytest.raises(ValueError) as exc_info:
            transform_bronze_to_silver(df)

        # Check error message includes percentage and systemic issue warning
        error_msg = str(exc_info.value)
        assert "15.0%" in error_msg or "15%" in error_msg
        assert "systemic issue" in error_msg.lower()
        assert "15/100" in error_msg

    def test_50_percent_failure_raises_value_error(self):
        """Test that 50% failure raises ValueError (extreme case)."""
        # 50 valid, 50 invalid (50% failure - severe systemic issue)
        df = _build_bronze_df_with_negative_values(valid_count=50, invalid_count=50)

        with pytest.raises(ValueError) as exc_info:
            transform_bronze_to_silver(df)

        error_msg = str(exc_info.value)
        assert "50.0%" in error_msg or "50%" in error_msg
        assert "systemic issue" in error_msg.lower()


@pytest.mark.unit
class TestErrorExport:
    """Test error export creates CSV with correct format (AC-4.3.3)."""

    def test_error_csv_created_with_correct_format(self):
        """Test that error CSV is created with required columns."""
        # 95 valid, 5 invalid (5% failure - under threshold)
        df = _build_bronze_df_with_negative_values(valid_count=95, invalid_count=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Check error file exists
            assert result.error_file_path is not None
            error_file = Path(result.error_file_path)
            assert error_file.exists()

            # Read error CSV and check format
            error_df = pd.read_csv(error_file, comment='#')

            # Check required columns
            required_columns = [
                "row_index",
                "field_name",
                "error_type",
                "error_message",
                "original_value"
            ]
            for col in required_columns:
                assert col in error_df.columns, f"Missing column: {col}"

            # Check error count matches
            assert len(error_df) >= 5  # At least 5 errors (one per failed row)

    def test_error_csv_contains_metadata_header(self):
        """Test that error CSV contains metadata header with summary."""
        # 95 valid, 5 invalid (5% failure - under threshold)
        df = _build_bronze_df_with_negative_values(valid_count=95, invalid_count=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Read raw file content to check metadata header
            with open(result.error_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check metadata header lines
            assert "# Validation Errors Export" in content
            assert "# Domain: annuity_performance" in content
            assert "# Total Rows: 100" in content
            assert "# Failed Rows: 5" in content
            assert "# Error Rate:" in content

    def test_error_csv_filename_format(self):
        """Test that error CSV filename follows expected format."""
        # 95 valid, 5 invalid (5% failure - under threshold)
        df = _build_bronze_df_with_negative_values(valid_count=95, invalid_count=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            # Check filename format: annuity_errors_{timestamp}.csv
            filename = Path(result.error_file_path).name
            assert filename.startswith("annuity_errors_")
            assert filename.endswith(".csv")

            # Check timestamp format (YYYYMMDD_HHMMSS)
            timestamp_part = filename.replace("annuity_errors_", "").replace(".csv", "")
            assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS
            assert timestamp_part[8] == "_"  # Underscore separator


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_dataframe(self):
        """Test that empty DataFrame is handled gracefully."""
        df = pd.DataFrame(columns=[
            "月度", "计划代码", "客户名称", "期初资产规模",
            "期末资产规模", "投资收益", "当期收益率"
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            assert result.row_count == 0
            assert result.valid_count == 0
            assert result.failed_count == 0
            assert len(result.valid_df) == 0
            assert result.error_file_path is None

    def test_single_row_valid(self):
        """Test that single valid row is processed correctly."""
        df = _build_valid_bronze_df(1)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = transform_bronze_to_silver(df, output_dir=tmpdir)

            assert result.row_count == 1
            assert result.valid_count == 1
            assert result.failed_count == 0
            assert len(result.valid_df) == 1
            assert result.error_file_path is None

    def test_single_row_invalid(self):
        """Test that single invalid row raises ValueError (100% failure)."""
        df = _build_bronze_df_with_negative_values(valid_count=0, invalid_count=1)

        with pytest.raises(ValueError, match="100.0%"):
            transform_bronze_to_silver(df)

    def test_custom_output_directory(self):
        """Test that custom output directory is used for error export."""
        df = _build_bronze_df_with_negative_values(valid_count=95, invalid_count=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom" / "errors"
            result = transform_bronze_to_silver(df, output_dir=str(custom_dir))

            # Check error file is in custom directory
            assert result.error_file_path is not None
            error_file = Path(result.error_file_path)
            assert error_file.parent == custom_dir
            assert error_file.exists()


@pytest.mark.unit
class TestPerformance:
    """Test performance characteristics."""

    def test_large_dataset_performance(self):
        """Test that large dataset (1000 rows) processes in reasonable time."""
        import time

        df = _build_valid_bronze_df(1000)

        with tempfile.TemporaryDirectory() as tmpdir:
            start_time = time.time()
            result = transform_bronze_to_silver(df, output_dir=tmpdir)
            duration = time.time() - start_time

            # Should complete successfully
            assert result.row_count == 1000
            assert result.valid_count == 1000

            # Performance target: <1ms per row = <1 second for 1000 rows
            # Allow 2x margin for test environment variability
            assert duration < 2.0, f"Processing took {duration:.2f}s, expected <2.0s"

            # Calculate rows per second
            rows_per_second = 1000 / duration
            assert rows_per_second > 500, f"Only {rows_per_second:.0f} rows/s, expected >500"
