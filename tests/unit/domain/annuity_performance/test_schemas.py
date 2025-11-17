import pandas as pd
import pytest
from pandera.errors import SchemaError

from work_data_hub.domain.annuity_performance.pipeline_steps import (
    BronzeSchemaValidationStep,
    GoldSchemaValidationStep,
)
from work_data_hub.domain.annuity_performance.schemas import (
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.types import PipelineContext


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
                "年化收益率": "5.5%",
            },
            {
                "月度": "2025年2月",
                "计划代码": "PLAN002",
                "客户名称": "公司B",
                "期初资产规模": 1500,
                "期末资产规模": 2500,
                "投资收益": 600,
                "年化收益率": 0.04,
            },
        ]
    )


def _build_gold_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "月度": pd.Timestamp("2025-01-01"),
                "计划代码": "PLAN001",
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
                    "年化收益率": "5.5e-2",  # 0.055
                }
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)
        assert validated_df["期初资产规模"].iloc[0] == 1_500_000.0
        assert validated_df["期末资产规模"].iloc[0] == 2_500_000.0
        assert validated_df["投资收益"].iloc[0] == 500_000.0
        assert abs(validated_df["年化收益率"].iloc[0] - 0.055) < 0.001

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
                    "年化收益率": 0.05,
                },
                {
                    "月度": "2025-02",
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": 2500,
                    "投资收益": 600,
                    "年化收益率": None,  # Python None - standard null
                },
                {
                    "月度": "2025-03",
                    "计划代码": "PLAN003",
                    "客户名称": "公司C",
                    "期初资产规模": 2000,
                    "期末资产规模": 3000,
                    "投资收益": 700,
                    "年化收益率": 0.04,
                },
            ]
        )
        # Should pass - None values are allowed in Bronze layer
        validated_df, summary = validate_bronze_dataframe(df)
        assert len(validated_df) == 3
        assert validated_df["年化收益率"].iloc[0] == 0.05
        assert pd.isna(validated_df["年化收益率"].iloc[1])
        assert validated_df["年化收益率"].iloc[2] == 0.04

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
                    "年化收益率": "  ",  # Whitespace - should coerce to NaN
                },
                {
                    "月度": "2025-02",
                    "计划代码": "PLAN002",
                    "客户名称": "公司B",
                    "期初资产规模": 1500,
                    "期末资产规模": 2500,
                    "投资收益": 600,  # Valid value prevents column from being all-null
                    "年化收益率": 0.05,
                },
            ]
        )
        validated_df, summary = validate_bronze_dataframe(df)
        # Empty strings should become NaN
        assert pd.isna(validated_df["投资收益"].iloc[0])
        assert pd.isna(validated_df["年化收益率"].iloc[0])
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
