"""Tests for infrastructure.validation.types module."""

from __future__ import annotations

import pytest

from work_data_hub.infrastructure.validation import (
    ValidationErrorDetail,
    ValidationSummary,
    ValidationThresholdExceeded,
)


class TestValidationErrorDetail:
    """Tests for ValidationErrorDetail dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Test creating ValidationErrorDetail with all fields."""
        error = ValidationErrorDetail(
            row_index=15,
            field_name="月度",
            error_type="ValueError",
            error_message="Cannot parse 'INVALID' as date",
            original_value="INVALID",
        )

        assert error.row_index == 15
        assert error.field_name == "月度"
        assert error.error_type == "ValueError"
        assert error.error_message == "Cannot parse 'INVALID' as date"
        assert error.original_value == "INVALID"

    def test_create_with_none_row_index(self) -> None:
        """Test creating ValidationErrorDetail with None row_index (schema-level error)."""
        error = ValidationErrorDetail(
            row_index=None,
            field_name="schema",
            error_type="SchemaError",
            error_message="Missing required columns",
            original_value=None,
        )

        assert error.row_index is None
        assert error.field_name == "schema"

    def test_create_with_complex_original_value(self) -> None:
        """Test creating ValidationErrorDetail with complex original value."""
        complex_value = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        error = ValidationErrorDetail(
            row_index=0,
            field_name="data",
            error_type="type_error",
            error_message="Invalid type",
            original_value=complex_value,
        )

        assert error.original_value == complex_value


class TestValidationSummary:
    """Tests for ValidationSummary dataclass."""

    def test_create_summary(self) -> None:
        """Test creating ValidationSummary."""
        summary = ValidationSummary(
            total_rows=1000,
            valid_rows=950,
            failed_rows=50,
            error_count=75,
            error_rate=0.05,
        )

        assert summary.total_rows == 1000
        assert summary.valid_rows == 950
        assert summary.failed_rows == 50
        assert summary.error_count == 75
        assert summary.error_rate == 0.05

    def test_summary_with_zero_errors(self) -> None:
        """Test ValidationSummary with no errors."""
        summary = ValidationSummary(
            total_rows=100,
            valid_rows=100,
            failed_rows=0,
            error_count=0,
            error_rate=0.0,
        )

        assert summary.failed_rows == 0
        assert summary.error_rate == 0.0


class TestValidationThresholdExceeded:
    """Tests for ValidationThresholdExceeded exception."""

    def test_exception_with_message_only(self) -> None:
        """Test creating exception with message only."""
        exc = ValidationThresholdExceeded("Error rate exceeded")

        assert str(exc) == "Error rate exceeded"
        assert exc.error_rate == 0.0
        assert exc.threshold == 0.0

    def test_exception_with_all_attributes(self) -> None:
        """Test creating exception with all attributes."""
        exc = ValidationThresholdExceeded(
            "Validation failure rate 15.0% exceeds threshold 10.0%",
            error_rate=0.15,
            threshold=0.10,
            failed_rows=150,
            total_rows=1000,
        )

        assert exc.error_rate == 0.15
        assert exc.threshold == 0.10
        assert exc.failed_rows == 150
        assert exc.total_rows == 1000

    def test_exception_is_raisable(self) -> None:
        """Test that exception can be raised and caught."""
        with pytest.raises(ValidationThresholdExceeded) as exc_info:
            raise ValidationThresholdExceeded(
                "Test error",
                error_rate=0.20,
                threshold=0.10,
                failed_rows=20,
                total_rows=100,
            )

        assert exc_info.value.error_rate == 0.20
        assert "Test error" in str(exc_info.value)
