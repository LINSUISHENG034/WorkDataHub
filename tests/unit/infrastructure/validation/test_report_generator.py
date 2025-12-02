"""Tests for infrastructure.validation.report_generator module."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import pytest

from work_data_hub.infrastructure.validation import (
    ValidationErrorDetail,
    export_error_csv,
)
from work_data_hub.infrastructure.validation.report_generator import (
    _sanitize_value,
    export_error_details_csv,
    export_validation_summary,
)


class TestExportErrorCsv:
    """Tests for export_error_csv function."""

    def test_export_creates_file(
        self, failed_dataframe: pd.DataFrame, tmp_path: Path
    ) -> None:
        """Test that export_error_csv creates a CSV file."""
        csv_path = export_error_csv(
            failed_dataframe,
            filename_prefix="test_errors",
            output_dir=tmp_path,
        )

        assert csv_path.exists()
        assert csv_path.suffix == ".csv"
        assert "test_errors" in csv_path.name

    def test_export_contains_metadata_header(
        self, failed_dataframe: pd.DataFrame, tmp_path: Path
    ) -> None:
        """Test that exported CSV contains metadata header."""
        csv_path = export_error_csv(
            failed_dataframe,
            filename_prefix="test",
            output_dir=tmp_path,
        )

        content = csv_path.read_text(encoding="utf-8")

        assert "# Validation Errors Export" in content
        assert "# Date:" in content
        assert "# Total Failed Rows:" in content

    def test_export_contains_dataframe_data(
        self, failed_dataframe: pd.DataFrame, tmp_path: Path
    ) -> None:
        """Test that exported CSV contains DataFrame data."""
        csv_path = export_error_csv(
            failed_dataframe,
            filename_prefix="test",
            output_dir=tmp_path,
        )

        content = csv_path.read_text(encoding="utf-8")

        # Check column headers are present
        assert "月度" in content
        assert "计划代码" in content
        # Check data values
        assert "INVALID" in content
        assert "A001" in content

    def test_export_creates_output_directory(
        self, failed_dataframe: pd.DataFrame, tmp_path: Path
    ) -> None:
        """Test that export creates output directory if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "logs"

        csv_path = export_error_csv(
            failed_dataframe,
            filename_prefix="test",
            output_dir=nested_dir,
        )

        assert nested_dir.exists()
        assert csv_path.exists()

    def test_export_handles_unicode(self, tmp_path: Path) -> None:
        """Test that export handles Chinese characters correctly."""
        df = pd.DataFrame(
            {
                "客户名称": ["中国银行", "工商银行"],
                "计划代码": ["A001", "A002"],
            }
        )

        csv_path = export_error_csv(df, output_dir=tmp_path)
        content = csv_path.read_text(encoding="utf-8")

        assert "中国银行" in content
        assert "工商银行" in content


class TestExportErrorDetailsCsv:
    """Tests for export_error_details_csv function."""

    def test_export_creates_file(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that export creates a CSV file."""
        csv_path = export_error_details_csv(
            sample_error_details,
            filename_prefix="error_details",
            output_dir=tmp_path,
            domain="test",
            total_rows=100,
            duration_seconds=1.5,
        )

        assert csv_path.exists()
        assert csv_path.suffix == ".csv"

    def test_export_contains_metadata(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that exported CSV contains metadata header."""
        csv_path = export_error_details_csv(
            sample_error_details,
            output_dir=tmp_path,
            domain="annuity",
            total_rows=1000,
            duration_seconds=5.5,
        )

        content = csv_path.read_text(encoding="utf-8")

        assert "# Domain: annuity" in content
        assert "# Total Rows: 1000" in content
        assert "# Validation Duration: 5.5s" in content

    def test_export_contains_error_details(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that exported CSV contains error details."""
        csv_path = export_error_details_csv(
            sample_error_details,
            output_dir=tmp_path,
            domain="test",
            total_rows=100,
        )

        content = csv_path.read_text(encoding="utf-8")

        # Check headers
        assert "row_index" in content
        assert "field_name" in content
        assert "error_type" in content
        assert "error_message" in content
        assert "original_value" in content

        # Check data
        assert "月度" in content
        assert "ValueError" in content

    def test_export_empty_errors(self, tmp_path: Path) -> None:
        """Test exporting empty error list."""
        csv_path = export_error_details_csv(
            [],
            output_dir=tmp_path,
            domain="test",
            total_rows=100,
        )

        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "# Failed Rows: 0" in content


class TestExportValidationSummary:
    """Tests for export_validation_summary function."""

    def test_export_creates_file(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that export creates a summary file."""
        summary_path = export_validation_summary(
            total_rows=1000,
            failed_rows=50,
            error_details=sample_error_details,
            domain="annuity",
            duration_seconds=8.5,
            output_dir=tmp_path,
        )

        assert summary_path.exists()
        assert summary_path.suffix == ".txt"
        assert "validation_summary" in summary_path.name

    def test_export_contains_statistics(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that summary contains statistics."""
        summary_path = export_validation_summary(
            total_rows=1000,
            failed_rows=50,
            error_details=sample_error_details,
            domain="annuity",
            duration_seconds=8.5,
            output_dir=tmp_path,
        )

        content = summary_path.read_text(encoding="utf-8")

        assert "Total Rows:" in content
        assert "1,000" in content
        assert "Failed Rows:" in content
        assert "50" in content
        assert "Error Rate:" in content
        assert "5.00%" in content

    def test_export_contains_error_breakdown(
        self, sample_error_details: List[ValidationErrorDetail], tmp_path: Path
    ) -> None:
        """Test that summary contains error breakdown by field and type."""
        summary_path = export_validation_summary(
            total_rows=100,
            failed_rows=3,
            error_details=sample_error_details,
            domain="test",
            duration_seconds=1.0,
            output_dir=tmp_path,
        )

        content = summary_path.read_text(encoding="utf-8")

        assert "ERRORS BY FIELD" in content
        assert "ERRORS BY TYPE" in content
        assert "月度" in content
        assert "ValueError" in content


class TestSanitizeValue:
    """Tests for _sanitize_value helper function."""

    def test_sanitize_none(self) -> None:
        """Test sanitizing None value."""
        assert _sanitize_value(None) == "NULL"

    def test_sanitize_string(self) -> None:
        """Test sanitizing string value."""
        assert _sanitize_value("hello") == "hello"

    def test_sanitize_number(self) -> None:
        """Test sanitizing numeric value."""
        assert _sanitize_value(123) == "123"
        assert _sanitize_value(123.45) == "123.45"

    def test_sanitize_removes_newlines(self) -> None:
        """Test that newlines are replaced with spaces."""
        assert _sanitize_value("line1\nline2") == "line1 line2"
        assert _sanitize_value("line1\tline2") == "line1 line2"

    def test_sanitize_truncates_long_strings(self) -> None:
        """Test that long strings are truncated."""
        long_string = "A" * 150
        result = _sanitize_value(long_string)

        assert len(result) == 100
        assert result.endswith("...")

    def test_sanitize_unicode(self) -> None:
        """Test sanitizing Unicode (Chinese) characters."""
        assert _sanitize_value("中国银行") == "中国银行"


class TestReportGeneratorPerformance:
    """Performance tests for report generator."""

    def test_csv_export_performance(self, tmp_path: Path) -> None:
        """Test that CSV export for 1000 rows completes in <50ms."""
        import time

        # Create 1000 error details
        errors = [
            ValidationErrorDetail(i, f"field_{i}", "type", "message", f"value_{i}")
            for i in range(1000)
        ]

        start = time.perf_counter()
        export_error_details_csv(
            errors,
            output_dir=tmp_path,
            domain="test",
            total_rows=10000,
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.050, f"CSV export too slow: {elapsed:.4f}s"
