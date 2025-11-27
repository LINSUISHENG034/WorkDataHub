"""Unit tests for ValidationErrorReporter (Story 2.5).

This module tests error collection, aggregation, CSV export, and threshold
enforcement for the ValidationErrorReporter class.

Test Coverage:
- AC-1.1: Single error collection
- AC-1.2: Multiple errors per row tracking
- AC-1.3: Summary statistics calculation
- AC-1.4: Threshold check under threshold
- AC-1.5: Threshold check exceeds threshold
- AC-1.6: CSV export format and metadata header
- AC-1.7: Value sanitization (long values truncated)
- AC-1.8: Special character sanitization (newlines/tabs removed)
"""

from pathlib import Path

import pytest

from work_data_hub.utils.error_reporter import (
    ValidationError,
    ValidationErrorReporter,
    ValidationSummary,
    ValidationThresholdExceeded,
)


class TestValidationErrorReporter:
    """Test error collection and aggregation."""

    def test_collect_single_error(self):
        """AC-1.1: Error collection works for single error."""
        reporter = ValidationErrorReporter()

        reporter.collect_error(
            row_index=15,
            field_name="月度",
            error_type="ValueError",
            error_message="Cannot parse 'INVALID' as date",
            original_value="INVALID",
        )

        assert len(reporter.errors) == 1
        assert reporter.errors[0].row_index == 15
        assert reporter.errors[0].field_name == "月度"
        assert reporter.errors[0].error_type == "ValueError"
        assert "Cannot parse" in reporter.errors[0].error_message
        assert reporter.errors[0].original_value == "INVALID"

    def test_collect_multiple_errors_same_row(self):
        """AC-1.2: Multiple errors per row tracked correctly."""
        reporter = ValidationErrorReporter()

        # Same row, different fields
        reporter.collect_error(15, "月度", "ValueError", "Invalid date", "BAD")
        reporter.collect_error(15, "期末资产规模", "ValueError", "Negative value", -1000)

        assert len(reporter.errors) == 2
        assert len(reporter._failed_row_indices) == 1  # Same row

    def test_get_summary_statistics(self):
        """AC-1.3: Summary calculates correct error rate."""
        reporter = ValidationErrorReporter()

        # 5 failed rows out of 100
        for i in [10, 20, 30, 40, 50]:
            reporter.collect_error(i, "field", "type", "message", "value")

        summary = reporter.get_summary(total_rows=100)

        assert summary.total_rows == 100
        assert summary.failed_rows == 5
        assert summary.valid_rows == 95
        assert summary.error_count == 5
        assert summary.error_rate == 0.05

    def test_get_summary_multiple_errors_per_row(self):
        """AC-1.2: Summary correctly counts unique failed rows."""
        reporter = ValidationErrorReporter()

        # Row 10 has 3 errors, row 20 has 1 error
        reporter.collect_error(10, "field1", "type", "msg", "val")
        reporter.collect_error(10, "field2", "type", "msg", "val")
        reporter.collect_error(10, "field3", "type", "msg", "val")
        reporter.collect_error(20, "field1", "type", "msg", "val")

        summary = reporter.get_summary(total_rows=100)

        assert summary.failed_rows == 2  # 2 unique rows
        assert summary.error_count == 4  # 4 total errors
        assert summary.error_rate == 0.02  # 2/100

    def test_threshold_check_under_threshold(self):
        """AC-1.4: Threshold check passes when <10% errors."""
        reporter = ValidationErrorReporter()

        # 9% error rate (under 10% threshold)
        for i in range(9):
            reporter.collect_error(i, "field", "type", "message", "value")

        # Should NOT raise
        reporter.check_threshold(total_rows=100)

    def test_threshold_check_exceeds_threshold(self):
        """AC-1.5: Threshold check fails when ≥10% errors."""
        reporter = ValidationErrorReporter()

        # 15% error rate (exceeds 10% threshold)
        for i in range(15):
            reporter.collect_error(i, "field", "type", "message", "value")

        # Should raise
        with pytest.raises(ValidationThresholdExceeded) as exc_info:
            reporter.check_threshold(total_rows=100)

        error_msg = str(exc_info.value)
        assert "15.0%" in error_msg
        assert "10.0%" in error_msg
        assert "likely systemic issue" in error_msg

    def test_threshold_check_exactly_at_threshold(self):
        """AC-1.5: Threshold check fails when exactly at 10%."""
        reporter = ValidationErrorReporter()

        # Exactly 10% error rate
        for i in range(10):
            reporter.collect_error(i, "field", "type", "message", "value")

        # Should raise (>=  threshold)
        with pytest.raises(ValidationThresholdExceeded):
            reporter.check_threshold(total_rows=100)

    def test_csv_export_format(self, tmp_path: Path):
        """AC-1.6: CSV export has correct format with metadata."""
        reporter = ValidationErrorReporter()

        reporter.collect_error(15, "月度", "ValueError", "Invalid date", "INVALID")
        reporter.collect_error(23, "期末资产规模", "ValueError", "Negative", -1000)

        csv_path = tmp_path / "errors.csv"
        reporter.export_to_csv(
            filepath=csv_path,
            total_rows=100,
            domain="annuity_performance",
            duration_seconds=8.5,
        )

        # Verify file created
        assert csv_path.exists()

        # Verify content
        content = csv_path.read_text(encoding="utf-8")

        # Metadata header
        assert "# Validation Errors Export" in content
        assert "# Total Rows: 100" in content
        assert "# Failed Rows: 2" in content
        assert "# Error Rate: 2.0%" in content
        assert "# Validation Duration: 8.5s" in content
        assert "# Domain: annuity_performance" in content

        # CSV headers
        assert "row_index,field_name,error_type,error_message,original_value" in content

        # CSV data
        assert "15,月度,ValueError" in content
        assert "23,期末资产规模,ValueError" in content

    def test_csv_export_creates_directory(self, tmp_path: Path):
        """AC-4.5: CSV export creates parent directory if doesn't exist."""
        reporter = ValidationErrorReporter()
        reporter.collect_error(0, "field", "type", "msg", "val")

        # Non-existent nested directory
        csv_path = tmp_path / "nested" / "logs" / "errors.csv"
        assert not csv_path.parent.exists()

        reporter.export_to_csv(csv_path, 100, "test", 1.0)

        assert csv_path.exists()
        assert csv_path.parent.exists()

    def test_sanitize_long_values(self):
        """AC-1.7: Long values truncated for CSV safety."""
        reporter = ValidationErrorReporter()

        long_value = "A" * 150  # >100 chars
        reporter.collect_error(0, "field", "type", "message", long_value)

        sanitized = reporter.errors[0].original_value

        assert len(sanitized) == 100  # 97 + "..."
        assert sanitized.endswith("...")
        assert sanitized.startswith("AAA")

    def test_sanitize_special_characters(self):
        """AC-1.8: Newlines and tabs removed for CSV safety."""
        reporter = ValidationErrorReporter()

        value_with_newlines = "Line1\nLine2\nLine3"
        value_with_tabs = "Col1\tCol2\tCol3"
        reporter.collect_error(0, "field1", "type", "msg", value_with_newlines)
        reporter.collect_error(1, "field2", "type", "msg", value_with_tabs)

        sanitized_1 = reporter.errors[0].original_value
        sanitized_2 = reporter.errors[1].original_value

        assert "\n" not in sanitized_1
        assert "\t" not in sanitized_2
        assert "Line1 Line2 Line3" == sanitized_1
        assert "Col1 Col2 Col3" == sanitized_2

    def test_sanitize_none_value(self):
        """AC-1.8: None values converted to 'NULL'."""
        reporter = ValidationErrorReporter()

        reporter.collect_error(0, "field", "type", "msg", None)

        assert reporter.errors[0].original_value == "NULL"

    def test_sanitize_complex_types(self):
        """AC-1.8: Complex types converted to string."""
        reporter = ValidationErrorReporter()

        reporter.collect_error(0, "field1", "type", "msg", {"key": "value"})
        reporter.collect_error(1, "field2", "type", "msg", [1, 2, 3])

        # Should be string representation
        assert "key" in reporter.errors[0].original_value
        assert "[1, 2, 3]" == reporter.errors[1].original_value

    def test_zero_errors_summary(self):
        """AC-4.1: Summary works with zero errors."""
        reporter = ValidationErrorReporter()

        summary = reporter.get_summary(total_rows=100)

        assert summary.total_rows == 100
        assert summary.failed_rows == 0
        assert summary.valid_rows == 100
        assert summary.error_count == 0
        assert summary.error_rate == 0.0

    def test_all_rows_fail_summary(self):
        """AC-4.2: Summary handles 100% error rate."""
        reporter = ValidationErrorReporter()

        # All 100 rows fail
        for i in range(100):
            reporter.collect_error(i, "field", "type", "msg", "val")

        summary = reporter.get_summary(total_rows=100)

        assert summary.failed_rows == 100
        assert summary.valid_rows == 0
        assert summary.error_rate == 1.0

    def test_empty_dataframe_summary(self):
        """AC-4.3: Summary handles empty DataFrame (0 rows)."""
        reporter = ValidationErrorReporter()

        summary = reporter.get_summary(total_rows=0)

        assert summary.total_rows == 0
        assert summary.failed_rows == 0
        assert summary.error_rate == 0.0

    def test_unicode_error_messages(self, tmp_path: Path):
        """AC-4.4: CSV handles Chinese characters correctly."""
        reporter = ValidationErrorReporter()

        # Error with Chinese company name
        reporter.collect_error(
            row_index=10,
            field_name="客户名称",
            error_type="ValueError",
            error_message="Invalid company name",
            original_value="北京测试公司有限公司",
        )

        csv_path = tmp_path / "errors_chinese.csv"
        reporter.export_to_csv(csv_path, 100, "annuity", 1.0)

        # Read back with UTF-8 encoding
        content = csv_path.read_text(encoding="utf-8")

        assert "客户名称" in content
        assert "北京测试公司有限公司" in content

    def test_custom_threshold(self):
        """AC-1.5: Custom threshold values work correctly."""
        reporter = ValidationErrorReporter()

        # 15% error rate
        for i in range(15):
            reporter.collect_error(i, "field", "type", "msg", "val")

        # Should pass with 20% threshold
        reporter.check_threshold(total_rows=100, threshold=0.20)

        # Should fail with 5% threshold
        with pytest.raises(ValidationThresholdExceeded):
            reporter.check_threshold(total_rows=100, threshold=0.05)


class TestValidationDataClasses:
    """Test ValidationError and ValidationSummary dataclasses."""

    def test_validation_error_dataclass(self):
        """Ensure ValidationError dataclass works correctly."""
        error = ValidationError(
            row_index=10,
            field_name="test_field",
            error_type="ValueError",
            error_message="Test error",
            original_value="test_value",
        )

        assert error.row_index == 10
        assert error.field_name == "test_field"
        assert error.error_type == "ValueError"

    def test_validation_summary_dataclass(self):
        """Ensure ValidationSummary dataclass works correctly."""
        summary = ValidationSummary(
            total_rows=100,
            valid_rows=95,
            failed_rows=5,
            error_count=8,
            error_rate=0.05,
        )

        assert summary.total_rows == 100
        assert summary.valid_rows == 95
        assert summary.failed_rows == 5
        assert summary.error_rate == 0.05
