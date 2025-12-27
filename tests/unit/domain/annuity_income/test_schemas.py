"""
Unit tests for AnnuityIncome schemas module.

Story 5.5.5: AnnuityIncome Schema Correction
Tests:
- BronzeAnnuityIncomeSchema (validation of raw types)
- GoldAnnuityIncomeSchema (validation of four income fields)
- Schema helpers (validation summaries)
"""

from decimal import Decimal
import pandas as pd
import pandera as pa
import pytest

from work_data_hub.domain.annuity_income.schemas import (
    BronzeAnnuityIncomeSchema,
    GoldAnnuityIncomeSchema,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)


class TestBronzeAnnuityIncomeSchema:
    """Tests for BronzeAnnuityIncomeSchema."""

    def test_validates_valid_data(self):
        """Schema validates correct data with four income fields."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01")],
                "计划代码": ["FP0001"],
                "机构代码": ["G00"],
                "客户名称": ["测试公司"],
                "业务类型": ["企年投资"],
                "固费": [500000.0],
                "浮费": [300000.0],
                "回补": [200000.0],
                "税": [50000.0],
                "extra_col": ["ignore_me"],  # strict=False allows extra
            }
        )
        validated = BronzeAnnuityIncomeSchema.validate(df)
        assert isinstance(validated, pd.DataFrame)

    def test_coerces_numeric_strings(self):
        """Schema coerces string numbers to floats."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01")],
                "固费": ["500000.00"],
                "浮费": ["300000"],
                "回补": [200000],
                "税": [50000],
            }
        )
        # Partial validation since we're testing coercion of specific columns
        # We can't use validate() directly if required cols are missing,
        # but validate_bronze_dataframe handles full flow.
        # Here we test the schema object directly on a subset for coercion logic
        # or create a full DF.

        full_df = df.assign(
            计划代码="FP0001", 机构代码="G00", 客户名称="测试公司", 业务类型="企年投资"
        )
        validated = BronzeAnnuityIncomeSchema.validate(full_df)
        assert isinstance(validated["固费"].iloc[0], float)
        assert validated["固费"].iloc[0] == 500000.0


class TestGoldAnnuityIncomeSchema:
    """Tests for GoldAnnuityIncomeSchema."""

    def test_validates_valid_gold_data(self):
        """Schema validates correct gold data."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01")],
                "计划代码": ["FP0001"],
                "company_id": ["COMP001"],
                "客户名称": ["测试公司"],
                "年金账户名": ["账户A"],
                "业务类型": ["企年投资"],
                "计划类型": ["单一计划"],
                "组合代码": ["QTAN001"],
                "产品线代码": ["PL201"],
                "机构代码": ["G00"],
                "固费": [500.0],
                "浮费": [300.0],
                "回补": [200.0],
                "税": [50.0],
            }
        )
        validated = GoldAnnuityIncomeSchema.validate(df)
        assert isinstance(validated, pd.DataFrame)

    def test_enforces_required_columns(self):
        """Schema fails if required columns are missing."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01")],
                # Missing 计划代码, company_id, income fields...
            }
        )
        with pytest.raises(pa.errors.SchemaError):
            GoldAnnuityIncomeSchema.validate(df)

    def test_enforces_unique_constraint(self):
        """Schema fails on duplicate composite key."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01"), pd.Timestamp("2024-12-01")],
                "计划代码": ["FP0001", "FP0001"],
                "company_id": ["COMP001", "COMP001"],
                "客户名称": ["A", "A"],
                "固费": [1.0, 1.0],
                "浮费": [1.0, 1.0],
                "回补": [1.0, 1.0],
                "税": [1.0, 1.0],
            }
        )
        # strict=True implies checks are run
        with pytest.raises(pa.errors.SchemaError):
            GoldAnnuityIncomeSchema.validate(df)


class TestValidationFunctions:
    """Tests for validation helper functions in schemas.py."""

    def test_validate_bronze_dataframe_returns_summary(self):
        """validate_bronze_dataframe returns validated DF and summary."""
        df = pd.DataFrame(
            {
                "月度": ["202412"],
                "计划代码": ["FP0001"],
                "机构代码": ["G00"],
                "客户名称": ["测试公司"],
                "业务类型": ["企年投资"],
                "固费": [500.0],
                "浮费": [300.0],
                "回补": [200.0],
                "税": [50.0],
            }
        )
        validated_df, summary = validate_bronze_dataframe(df)

        assert len(validated_df) == 1
        assert summary.row_count == 1
        assert len(summary.numeric_error_rows) == 0

    def test_validate_gold_dataframe_checks_duplicates(self):
        """validate_gold_dataframe detects duplicates."""
        df = pd.DataFrame(
            {
                "月度": [pd.Timestamp("2024-12-01"), pd.Timestamp("2024-12-01")],
                "计划代码": ["FP0001", "FP0001"],
                "company_id": ["COMP001", "COMP001"],
                "客户名称": ["A", "A"],
                "固费": [1.0, 1.0],
                "浮费": [1.0, 1.0],
                "回补": [1.0, 1.0],
                "税": [1.0, 1.0],
            }
        )

        # The helper function raises SchemaError for duplicates
        with pytest.raises(pa.errors.SchemaError):
            validate_gold_dataframe(df)
