import pandas as pd
import pytest
from pandera.errors import SchemaError

from work_data_hub.domain.annuity_performance.schemas import (
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.validation.schema_steps import (
    BronzeSchemaValidationStep,
    GoldSchemaValidationStep,
)


def _build_bronze_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "月度": "2025-01",
                "计划代码": "PLAN001",
                "客户名称": "公司A",
                "期初资产规模": "1,000.00",
                "期末资产规模": "2,000.00",
                "投资收益": "500.00",
                "当期收益率": "5.5%",
            },
            {
                "月度": "2025年2月",
                "计划代码": "PLAN002",
                "客户名称": "公司B",
                "期初资产规模": 1500,
                "期末资产规模": 2500,
                "投资收益": 600,
                "当期收益率": 0.04,
            },
        ]
    )


def _build_gold_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "月度": pd.Timestamp("2025-01-01"),
                "业务类型": "企业年金",
                "计划类型": "单一计划",
                "计划代码": "PLAN001",
                "计划名称": "测试计划",
                "组合类型": "稳健型",
                "组合代码": "COMBO001",
                "组合名称": "稳健组合",
                "company_id": "COMP001",
                "客户名称": "公司A",
                "期初资产规模": 1000.0,
                "期末资产规模": 2000.0,
                "投资收益": 500.0,
                "供款": 100.0,
                "流失_含待遇支付": 10.0,
                "流失": 5.0,
                "待遇支付": 2.0,
                "年化收益率": 0.05,
                "机构代码": "G00",
                "机构名称": "总部",
                "产品线代码": "PROD001",
                "年金账户号": "ACC001",
                "年金账户名": "公司A年金账户",
                "extra_column": "ignore me",
            }
        ]
    )


@pytest.mark.unit
class TestBronzeSchemaValidation:
    def test_valid_dataset_passes(self):
        df, summary = validate_bronze_dataframe(_build_bronze_df())
        assert len(df) == 2
        assert summary.invalid_date_rows == []
        assert summary.numeric_error_rows == {}

    def test_missing_required_column(self):
        df = _build_bronze_df().drop(columns=["客户名称"])
        with pytest.raises(SchemaError):
            validate_bronze_dataframe(df)

    def test_invalid_date_ratio(self):
        """Test that >10% invalid dates triggers threshold error."""
        # Create more rows to avoid completely null column
        df = pd.concat([_build_bronze_df()] * 6, ignore_index=True)
        # Make 50% of dates invalid (exceeds 10% threshold)
        for i in range(0, 6):
            df.loc[i, "月度"] = "not-a-date"
        with pytest.raises(SchemaError, match="unparseable dates"):
            validate_bronze_dataframe(df)

    def test_invalid_numeric_ratio(self):
        """Test that >10% invalid numbers triggers threshold error."""
        # Create enough rows to test threshold without hitting null column check
        df = pd.concat([_build_bronze_df()] * 6, ignore_index=True)
        # Make 50% invalid (exceeds 10% threshold)
        for i in range(0, 6):
            df.loc[i, "期末资产规模"] = "invalid"
        with pytest.raises(SchemaError, match="non-numeric values"):
            validate_bronze_dataframe(df)

    def test_pipeline_step_records_metadata(self):
        step = BronzeSchemaValidationStep()
        context = PipelineContext(
            pipeline_name="test",
            execution_id="exec",
            timestamp=pd.Timestamp.utcnow(),
            config={},
            metadata={},
        )
        result = step.execute(_build_bronze_df(), context)
        assert len(result) == 2
        assert "bronze_schema_validation" in context.metadata

    # Edge case tests for Task 3.4
    def test_scientific_notation_coercion(self):
        """Test that scientific notation is properly coerced to float."""
        df = pd.DataFrame(
            [
                {
                    "月度": "2025-01",
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": "1.5e6",  # Scientific notation
                    "期末资产规模": "2.5e6",
                    "投资收益": "5e5",
                    "当期收益率": "5.5e-2",  # 0.055
                }
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)
        assert validated_df["期初资产规模"].iloc[0] == 1_500_000.0
        assert validated_df["期末资产规模"].iloc[0] == 2_500_000.0
        assert validated_df["投资收益"].iloc[0] == 500_000.0
        assert abs(validated_df["当期收益率"].iloc[0] - 0.055) < 0.001

    def test_mixed_null_representations(self):
        """Test that None null representations are handled in Bronze layer."""
        df = pd.DataFrame(
            [
                {
                    "月度": "2025-01",
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": 1000,
                    "期末资产规模": 2000,
                    "投资收益": 500,
                    "当期收益率": 0.05,
                },
                {
                    "月度": "2025-02",
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": 2500,
                    "投资收益": 600,
                    "当期收益率": None,  # Python None - standard null
                },
                {
                    "月度": "2025-03",
                    "计划代码": "PLAN003",
                    "客户名称": "公司C",
                    "期初资产规模": 2000,
                    "期末资产规模": 3000,
                    "投资收益": 700,
                    "当期收益率": 0.04,
                },
            ]
        )
        # Should pass - None values are allowed in Bronze layer
        validated_df, summary = validate_bronze_dataframe(df)
        assert len(validated_df) == 3
        assert validated_df["当期收益率"].iloc[0] == 0.05
        assert pd.isna(validated_df["当期收益率"].iloc[1])
        assert validated_df["当期收益率"].iloc[2] == 0.04

    def test_empty_string_coercion_to_nan(self):
        """Test that empty strings in numeric columns coerce to NaN."""
        df = pd.DataFrame(
            [
                {
                    "月度": "2025-01",
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": 1000,  # Valid value
                    "期末资产规模": 2000,  # Valid value
                    "投资收益": "",  # Empty string - should coerce to NaN
                    "当期收益率": "  ",  # Whitespace - should coerce to NaN
                },
                {
                    "月度": "2025-02",
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": 2500,
                    "投资收益": 600,  # Valid value prevents column from being all-null
                    "当期收益率": 0.05,
                },
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)
        # Empty strings should become NaN
        assert pd.isna(validated_df["投资收益"].iloc[0])
        assert pd.isna(validated_df["当期收益率"].iloc[0])
        # Valid values should remain
        assert validated_df["投资收益"].iloc[1] == 600

    def test_error_threshold_boundary_exactly_10_percent(self):
        """Test that exactly 10% error rate passes (threshold is >10%)."""
        # Create 10 rows with exactly 1 invalid date (10% error rate)
        df = pd.concat([_build_bronze_df()] * 5, ignore_index=True)
        df.loc[0, "月度"] = "invalid-date"
        # Should pass because 1/10 = 10% is not > 10%
        validated_df, summary = validate_bronze_dataframe(df, failure_threshold=0.10)
        assert len(summary.invalid_date_rows) == 1

    def test_error_threshold_boundary_just_over_10_percent(self):
        """Test that >10% error rate fails."""
        # Create 10 rows with 2 invalid dates (20% error rate)
        df = pd.concat([_build_bronze_df()] * 5, ignore_index=True)
        df.loc[0, "月度"] = "invalid-date-1"
        df.loc[1, "月度"] = "invalid-date-2"
        # Should fail because 2/10 = 20% > 10%
        with pytest.raises(SchemaError, match="unparseable dates"):
            validate_bronze_dataframe(df, failure_threshold=0.10)

    def test_error_threshold_boundary_just_under_10_percent(self):
        """Test that <10% error rate passes."""
        # Create 11 rows with 1 invalid date (9.09% error rate)
        df = pd.concat([_build_bronze_df()] * 5, ignore_index=True)
        df = pd.concat([df, _build_bronze_df().iloc[:1]], ignore_index=True)
        df.loc[0, "月度"] = "invalid-date"
        # Should pass because 1/11 = 9.09% < 10%
        validated_df, summary = validate_bronze_dataframe(df, failure_threshold=0.10)
        assert len(summary.invalid_date_rows) == 1

    def test_completely_null_column_raises_error(self):
        """Test AC-4.2.1: Completely null column indicates corrupted Excel."""
        df = pd.DataFrame(
            [
                {
                    "月度": "2025-01",
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": 1000,
                    "期末资产规模": None,  # All null
                    "投资收益": 500,
                    "当期收益率": 0.05,
                },
                {
                    "月度": "2025-02",
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": None,  # All null
                    "投资收益": 600,
                    "当期收益率": 0.04,
                },
            ]
        )
        with pytest.raises(SchemaError, match="no non-null values"):
            validate_bronze_dataframe(df)

    def test_error_message_lists_expected_vs_actual_columns(self):
        """Test AC-4.2.2: Error message lists expected vs. actual columns."""
        df = _build_bronze_df().drop(columns=["期末资产规模"])
        try:
            validate_bronze_dataframe(df)
            pytest.fail("Expected SchemaError to be raised")
        except SchemaError as e:
            error_msg = str(e)
            assert "期末资产规模" in error_msg
            assert "found columns:" in error_msg

    def test_validation_passes_for_valid_data(self):
        """Test AC-4.2.4: Validation passes for valid data with no errors."""
        df = _build_bronze_df()
        validated_df, summary = validate_bronze_dataframe(df)

        # Should return DataFrame ready for Silver layer
        assert len(validated_df) == 2
        assert summary.row_count == 2

        # No errors or warnings
        assert summary.invalid_date_rows == []
        assert summary.numeric_error_rows == {}
        assert summary.empty_columns == []

    def test_numeric_coercion_with_commas_and_percentages(self):
        """Test AC-4.2.1: Numeric columns coercible with Excel formatting."""
        df = pd.DataFrame(
            [
                {
                    "月度": "202501",
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": "1,234,567.89",  # Comma-separated
                    "期末资产规模": "2,345,678.90",
                    "投资收益": "500,000.00",
                    "当期收益率": "5.5%",  # Percentage
                }
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)

        # Verify numeric coercion worked
        assert validated_df["期初资产规模"].iloc[0] == 1234567.89
        assert validated_df["期末资产规模"].iloc[0] == 2345678.90
        assert validated_df["投资收益"].iloc[0] == 500000.00
        assert abs(validated_df["当期收益率"].iloc[0] - 0.055) < 0.001

    def test_date_parsing_with_chinese_format(self):
        """Test AC-4.2.1: Date column parseable with Epic 2 Story 2.4 parser."""
        df = pd.DataFrame(
            [
                {
                    "月度": "2024年12月",  # Chinese format
                    "计划代码": "PLAN001",
                    "客户名称": "公司A",
                    "期初资产规模": 1000,
                    "期末资产规模": 2000,
                    "投资收益": 500,
                    "当期收益率": 0.05,
                },
                {
                    "月度": "202501",  # Numeric format
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": 2500,
                    "投资收益": 600,
                    "当期收益率": 0.04,
                },
                {
                    "月度": "2025-02",  # ISO format
                    "计划代码": "PLAN003",
                    "客户名称": "公司C",
                    "期初资产规模": 2000,
                    "期末资产规模": 3000,
                    "投资收益": 700,
                    "当期收益率": 0.03,
                },
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)

        # All dates should be parsed successfully
        assert summary.invalid_date_rows == []
        assert len(validated_df) == 3
        assert pd.notna(validated_df["月度"].iloc[0])
        assert pd.notna(validated_df["月度"].iloc[1])
        assert pd.notna(validated_df["月度"].iloc[2])

    def test_at_least_one_data_row_required(self):
        """Test AC-4.2.1: At least 1 data row required (not just headers)."""
        df = pd.DataFrame(
            columns=[
                "月度",
                "计划代码",
                "客户名称",
                "期初资产规模",
                "期末资产规模",
                "投资收益",
                "当期收益率",
            ]
        )
        with pytest.raises(SchemaError, match="cannot be empty"):
            validate_bronze_dataframe(df)

    def test_strict_false_allows_extra_columns(self):
        """Test that strict=False allows extra columns from Excel."""
        df = _build_bronze_df()
        df["备注"] = "Extra column"
        df["子企业号"] = "12345"

        # Should pass - extra columns allowed
        validated_df, summary = validate_bronze_dataframe(df)
        assert len(validated_df) == 2
        assert "备注" in validated_df.columns
        assert "子企业号" in validated_df.columns


@pytest.mark.unit
class TestGoldSchemaValidation:
    def test_valid_dataset_passes(self):
        df, summary = validate_gold_dataframe(_build_gold_df())
        assert len(df) == 1
        assert summary.removed_columns == ["extra_column"]

    def test_duplicate_composite_key(self):
        df = pd.concat([_build_gold_df()] * 2, ignore_index=True)
        with pytest.raises(SchemaError, match="Composite PK"):
            validate_gold_dataframe(df)

    def test_pipeline_step_records_metadata(self):
        step = GoldSchemaValidationStep()
        context = PipelineContext(
            pipeline_name="test",
            execution_id="exec",
            timestamp=pd.Timestamp.utcnow(),
            config={},
            metadata={},
        )
        result = step.execute(_build_gold_df(), context)
        assert len(result) == 1
        assert context.metadata["gold_schema_validation"]["removed_columns"] == [
            "extra_column"
        ]

    def test_null_required_field_fails_validation(self):
        df = _build_gold_df()
        df.loc[0, "期初资产规模"] = None
        with pytest.raises(SchemaError) as excinfo:
            validate_gold_dataframe(df)
        assert "期初资产规模" in str(excinfo.value)

    def test_negative_asset_values_rejected(self):
        df = _build_gold_df()
        df.loc[0, "期末资产规模"] = -1.0
        with pytest.raises(SchemaError) as excinfo:
            validate_gold_dataframe(df)
        assert "期末资产规模" in str(excinfo.value)

    def test_extra_columns_rejected_in_strict_mode(self):
        df = _build_gold_df()
        with pytest.raises(SchemaError):
            validate_gold_dataframe(df, project_columns=False)
