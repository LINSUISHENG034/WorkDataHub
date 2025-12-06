"""Tests for infrastructure.validation.error_handler module."""

from __future__ import annotations

from typing import List

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors
from pydantic import BaseModel, ValidationError as PydanticValidationError

from work_data_hub.infrastructure.validation import (
    ValidationErrorDetail,
    ValidationSummary,
    ValidationThresholdExceeded,
    collect_error_details,
    handle_validation_errors,
)


class TestHandleValidationErrors:
    """Tests for handle_validation_errors function."""

    def test_low_error_rate_passes(
        self, low_error_rate_details: List[ValidationErrorDetail]
    ) -> None:
        """Test that low error rate (<10%) passes without exception."""
        summary = handle_validation_errors(
            low_error_rate_details,
            threshold=0.1,
            total_rows=100,
            domain="test",
        )

        assert isinstance(summary, ValidationSummary)
        assert summary.failed_rows == 5
        assert summary.error_rate == 0.05
        assert summary.total_rows == 100

    def test_high_error_rate_raises(
        self, high_error_rate_details: List[ValidationErrorDetail]
    ) -> None:
        """Test that high error rate (>10%) raises ValidationThresholdExceeded."""
        with pytest.raises(ValidationThresholdExceeded) as exc_info:
            handle_validation_errors(
                high_error_rate_details,
                threshold=0.1,
                total_rows=100,
                domain="test",
            )

        assert exc_info.value.error_rate == 0.15
        assert exc_info.value.threshold == 0.1
        assert exc_info.value.failed_rows == 15

    def test_exact_threshold_raises(self) -> None:
        """Test that error rate exactly at threshold raises exception."""
        errors = [ValidationErrorDetail(i, "f", "t", "m", "v") for i in range(10)]

        with pytest.raises(ValidationThresholdExceeded):
            handle_validation_errors(errors, threshold=0.1, total_rows=100)

    def test_empty_errors_passes(
        self, empty_error_details: List[ValidationErrorDetail]
    ) -> None:
        """Test that empty error list passes."""
        summary = handle_validation_errors(
            empty_error_details,
            threshold=0.1,
            total_rows=100,
        )

        assert summary.failed_rows == 0
        assert summary.error_rate == 0.0

    def test_custom_threshold(self) -> None:
        """Test with custom threshold value."""
        errors = [ValidationErrorDetail(i, "f", "t", "m", "v") for i in range(5)]

        # 5% error rate with 20% threshold - should pass
        summary = handle_validation_errors(errors, threshold=0.2, total_rows=100)
        assert summary.error_rate == 0.05

        # 5% error rate with 3% threshold - should raise
        with pytest.raises(ValidationThresholdExceeded):
            handle_validation_errors(errors, threshold=0.03, total_rows=100)

    def test_invalid_total_rows_raises(self) -> None:
        """Test that invalid total_rows raises ValueError."""
        errors = [ValidationErrorDetail(0, "f", "t", "m", "v")]

        with pytest.raises(ValueError, match="total_rows must be a positive integer"):
            handle_validation_errors(errors, total_rows=0)

        with pytest.raises(ValueError, match="total_rows must be a positive integer"):
            handle_validation_errors(errors, total_rows=None)

    def test_multiple_errors_same_row(self) -> None:
        """Test that multiple errors on same row count as one failed row."""
        errors = [
            ValidationErrorDetail(0, "field1", "t", "m", "v"),
            ValidationErrorDetail(0, "field2", "t", "m", "v"),
            ValidationErrorDetail(0, "field3", "t", "m", "v"),
        ]

        summary = handle_validation_errors(errors, threshold=0.1, total_rows=100)

        assert summary.failed_rows == 1  # Only one unique row
        assert summary.error_count == 3  # Three errors total
        assert summary.error_rate == 0.01

    def test_none_row_index_not_counted(self) -> None:
        """Test that errors with None row_index don't count toward failed rows."""
        errors = [
            ValidationErrorDetail(None, "schema", "SchemaError", "m", "v"),
            ValidationErrorDetail(0, "field", "t", "m", "v"),
        ]

        summary = handle_validation_errors(errors, threshold=0.1, total_rows=100)

        assert summary.failed_rows == 1  # Only row 0 counted
        assert summary.error_count == 2


class TestCollectErrorDetails:
    """Tests for collect_error_details function."""

    def test_passthrough_validation_error_details(
        self, sample_error_details: List[ValidationErrorDetail]
    ) -> None:
        """Test that ValidationErrorDetail list passes through unchanged."""
        result = collect_error_details(sample_error_details)

        assert result == sample_error_details
        assert len(result) == 3

    def test_empty_list_passthrough(self) -> None:
        """Test that empty list passes through."""
        result = collect_error_details([])
        assert result == []

    def test_pydantic_validation_error(self) -> None:
        """Test collecting errors from Pydantic ValidationError."""

        class TestModel(BaseModel):
            name: str
            age: int

        try:
            TestModel(name=123, age="not_an_int")  # type: ignore
        except PydanticValidationError as exc:
            result = collect_error_details(exc)

            assert len(result) >= 1
            assert all(isinstance(e, ValidationErrorDetail) for e in result)
            # Check that field names are captured
            field_names = [e.field_name for e in result]
            assert any("age" in f or "name" in f for f in field_names)

    def test_pydantic_nested_error(self) -> None:
        """Test collecting errors from nested Pydantic model."""

        class Inner(BaseModel):
            value: int

        class Outer(BaseModel):
            inner: Inner

        try:
            Outer(inner={"value": "not_int"})  # type: ignore
        except PydanticValidationError as exc:
            result = collect_error_details(exc)

            assert len(result) >= 1
            # Nested field should have dot notation
            assert any("inner" in e.field_name for e in result)


class TestCollectErrorDetailsPandera:
    """Tests for collect_error_details with Pandera errors."""

    def test_pandera_schema_errors_lazy_validation(self) -> None:
        """Test collecting errors from Pandera SchemaErrors (lazy validation)."""
        import pandera as pa

        schema = pa.DataFrameSchema(
            columns={
                "col_a": pa.Column(pa.Int, checks=pa.Check.ge(0)),
            }
        )
        df = pd.DataFrame({"col_a": [-1, -2, 3]})

        try:
            schema.validate(df, lazy=True)
        except SchemaErrors as exc:
            result = collect_error_details(exc)

            assert len(result) >= 1
            assert all(isinstance(e, ValidationErrorDetail) for e in result)
            # Check that field name is captured
            assert any("col_a" in e.field_name for e in result)

    def test_pandera_schema_error_fail_fast(self) -> None:
        """Test collecting errors from Pandera SchemaError (fail-fast)."""
        import pandera as pa

        schema = pa.DataFrameSchema(
            columns={
                "col_a": pa.Column(pa.Int, checks=pa.Check.ge(0)),
            }
        )
        df = pd.DataFrame({"col_a": [-1, 2, 3]})

        try:
            schema.validate(df, lazy=False)
        except SchemaError as exc:
            result = collect_error_details(exc)

            assert len(result) >= 1
            assert all(isinstance(e, ValidationErrorDetail) for e in result)

    def test_pandera_schema_error_missing_column(self) -> None:
        """Test collecting errors from missing column SchemaError."""
        import pandera as pa

        schema = pa.DataFrameSchema(
            columns={
                "required_col": pa.Column(pa.Int),
            }
        )
        df = pd.DataFrame({"other_col": [1, 2, 3]})

        try:
            schema.validate(df)
        except SchemaError as exc:
            result = collect_error_details(exc)

            assert len(result) >= 1
            # Schema-level errors may have None row_index
            assert all(isinstance(e, ValidationErrorDetail) for e in result)


class TestCollectErrorDetailsEdgeCases:
    """Edge case tests for collect_error_details."""

    def test_unknown_error_type_returns_empty(self) -> None:
        """Test that unknown error type returns empty list."""
        result = collect_error_details("not_an_error_object")  # type: ignore

        assert result == []

    def test_list_of_pydantic_errors(self) -> None:
        """Test collecting from list of Pydantic ValidationErrors."""

        class TestModel(BaseModel):
            value: int

        errors = []
        for val in ["a", "b", "c"]:
            try:
                TestModel(value=val)  # type: ignore
            except PydanticValidationError as exc:
                errors.append(exc)

        result = collect_error_details(errors)

        assert len(result) == 3
        assert all(isinstance(e, ValidationErrorDetail) for e in result)


class TestCollectErrorDetailsPerformance:
    """Performance tests for collect_error_details."""

    def test_performance_1000_errors(self) -> None:
        """Test that collecting 1000 errors completes in <5ms."""
        import time

        errors = [
            ValidationErrorDetail(i, f"field_{i}", "type", "message", f"value_{i}")
            for i in range(1000)
        ]

        start = time.perf_counter()
        result = collect_error_details(errors)
        elapsed = time.perf_counter() - start

        assert len(result) == 1000
        assert elapsed < 0.005, f"Error collection too slow: {elapsed:.4f}s"
