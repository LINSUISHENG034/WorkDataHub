"""Tests for infrastructure.validation.schema_helpers module."""

from __future__ import annotations

import pandas as pd
import pandera as pa
import pytest
from pandera.errors import SchemaError

from work_data_hub.infrastructure.validation import (
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)


@pytest.fixture
def sample_schema() -> pa.DataFrameSchema:
    """Sample Pandera schema for testing."""
    return pa.DataFrameSchema(
        columns={
            "col_a": pa.Column(pa.String, nullable=True),
            "col_b": pa.Column(pa.Int, nullable=True),
            "col_c": pa.Column(pa.Float, nullable=True),
        },
        strict=False,
    )


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "col_a": ["a", "b", "c"],
            "col_b": [1, 2, 3],
            "col_c": [1.0, 2.0, 3.0],
        }
    )


class TestRaiseSchemaError:
    """Tests for raise_schema_error function."""

    def test_raises_schema_error(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that raise_schema_error raises SchemaError."""
        with pytest.raises(SchemaError) as exc_info:
            raise_schema_error(
                sample_schema,
                sample_dataframe,
                message="Test error message",
            )

        assert "Test error message" in str(exc_info.value)

    def test_raises_with_failure_cases(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test raise_schema_error with failure_cases DataFrame."""
        failure_cases = pd.DataFrame(
            {"column": ["col_a"], "failure": ["invalid value"]}
        )

        with pytest.raises(SchemaError) as exc_info:
            raise_schema_error(
                sample_schema,
                sample_dataframe,
                message="Validation failed",
                failure_cases=failure_cases,
            )

        assert exc_info.value.failure_cases is not None

    def test_raises_with_none_failure_cases(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test raise_schema_error with None failure_cases."""
        with pytest.raises(SchemaError):
            raise_schema_error(
                sample_schema,
                sample_dataframe,
                message="Error without failure cases",
                failure_cases=None,
            )


class TestEnsureRequiredColumns:
    """Tests for ensure_required_columns function."""

    def test_passes_when_all_columns_present(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that validation passes when all required columns are present."""
        # Should not raise
        ensure_required_columns(
            sample_schema,
            sample_dataframe,
            required=["col_a", "col_b"],
            schema_name="TestSchema",
        )

    def test_raises_when_column_missing(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that validation raises when required column is missing."""
        with pytest.raises(SchemaError) as exc_info:
            ensure_required_columns(
                sample_schema,
                sample_dataframe,
                required=["col_a", "col_d"],  # col_d doesn't exist
                schema_name="TestSchema",
            )

        error_msg = str(exc_info.value)
        assert "TestSchema validation failed" in error_msg
        assert "missing required columns" in error_msg
        assert "col_d" in error_msg

    def test_raises_with_multiple_missing_columns(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that validation reports all missing columns."""
        with pytest.raises(SchemaError) as exc_info:
            ensure_required_columns(
                sample_schema,
                sample_dataframe,
                required=["col_a", "col_x", "col_y", "col_z"],
                schema_name="TestSchema",
            )

        error_msg = str(exc_info.value)
        assert "col_x" in error_msg
        assert "col_y" in error_msg
        assert "col_z" in error_msg

    def test_includes_found_columns_in_error(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that error message includes found columns."""
        with pytest.raises(SchemaError) as exc_info:
            ensure_required_columns(
                sample_schema,
                sample_dataframe,
                required=["missing_col"],
                schema_name="TestSchema",
            )

        error_msg = str(exc_info.value)
        assert "found columns" in error_msg
        assert "col_a" in error_msg

    def test_empty_required_list_passes(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that empty required list passes."""
        # Should not raise
        ensure_required_columns(
            sample_schema,
            sample_dataframe,
            required=[],
            schema_name="TestSchema",
        )


class TestEnsureNotEmpty:
    """Tests for ensure_not_empty function."""

    def test_passes_when_dataframe_not_empty(
        self, sample_schema: pa.DataFrameSchema, sample_dataframe: pd.DataFrame
    ) -> None:
        """Test that validation passes when DataFrame is not empty."""
        # Should not raise
        ensure_not_empty(sample_schema, sample_dataframe, schema_name="TestSchema")

    def test_raises_when_dataframe_empty(
        self, sample_schema: pa.DataFrameSchema
    ) -> None:
        """Test that validation raises when DataFrame is empty."""
        empty_df = pd.DataFrame()

        with pytest.raises(SchemaError) as exc_info:
            ensure_not_empty(sample_schema, empty_df, schema_name="TestSchema")

        error_msg = str(exc_info.value)
        assert "TestSchema validation failed" in error_msg
        assert "DataFrame cannot be empty" in error_msg

    def test_raises_when_dataframe_has_columns_but_no_rows(
        self, sample_schema: pa.DataFrameSchema
    ) -> None:
        """Test that validation raises when DataFrame has columns but no rows."""
        empty_with_columns = pd.DataFrame(columns=["col_a", "col_b"])

        with pytest.raises(SchemaError) as exc_info:
            ensure_not_empty(
                sample_schema, empty_with_columns, schema_name="TestSchema"
            )

        assert "DataFrame cannot be empty" in str(exc_info.value)

    def test_default_schema_name(self, sample_schema: pa.DataFrameSchema) -> None:
        """Test that default schema name is used when not provided."""
        empty_df = pd.DataFrame()

        with pytest.raises(SchemaError) as exc_info:
            ensure_not_empty(sample_schema, empty_df)

        assert "Schema validation failed" in str(exc_info.value)


class TestSchemaHelpersIntegration:
    """Integration tests for schema helpers."""

    def test_combined_validation_flow(self, sample_schema: pa.DataFrameSchema) -> None:
        """Test typical validation flow using multiple helpers."""
        df = pd.DataFrame(
            {
                "col_a": ["x", "y"],
                "col_b": [1, 2],
                "col_c": [1.0, 2.0],
            }
        )

        # Should pass all checks
        ensure_not_empty(sample_schema, df, "TestSchema")
        ensure_required_columns(sample_schema, df, ["col_a", "col_b"], "TestSchema")

    def test_validation_with_chinese_column_names(self) -> None:
        """Test validation with Chinese column names."""
        schema = pa.DataFrameSchema(
            columns={
                "月度": pa.Column(pa.String),
                "客户名称": pa.Column(pa.String),
            }
        )
        df = pd.DataFrame(
            {
                "月度": ["2024-01"],
                "客户名称": ["测试客户"],
            }
        )

        # Should pass
        ensure_not_empty(schema, df, "中文Schema")
        ensure_required_columns(schema, df, ["月度", "客户名称"], "中文Schema")

        # Should fail with Chinese column name in error
        with pytest.raises(SchemaError) as exc_info:
            ensure_required_columns(schema, df, ["月度", "缺失列"], "中文Schema")

        assert "缺失列" in str(exc_info.value)
