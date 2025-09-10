"""
Comprehensive tests for annuity performance models.

This module provides tests for Pydantic v2 models with Chinese field names,
decimal field quantization, and validation patterns for "规模明细" data
according to PRP P-021 requirements.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
)


class TestAnnuityPerformanceIn:
    """Tests for AnnuityPerformanceIn input model with Chinese field names."""

    def test_basic_chinese_fields(self):
        """Test that Chinese field names are accepted and validated."""
        data = {
            "年": "2024",
            "月": "11",
            "计划代码": "TEST001",
            "业务类型": "企业年金",
        }

        model = AnnuityPerformanceIn(**data)
        assert model.年 == "2024"
        assert model.月 == "11"
        assert model.计划代码 == "TEST001"
        assert model.业务类型 == "企业年金"

    def test_financial_fields_flexible_types(self):
        """Test that financial fields accept various input types."""
        data = {
            "期初资产规模": "1000000.50",
            "期末资产规模": 2000000,
            "投资收益": Decimal("50000.25"),
            "当期收益率": "5.5%",  # Percentage format
        }

        model = AnnuityPerformanceIn(**data)
        assert model.期初资产规模 == "1000000.50"
        assert model.期末资产规模 == 2000000
        assert model.投资收益 == Decimal("50000.25")
        assert model.当期收益率 == "5.5%"

    def test_special_column_with_parentheses(self):
        """Test handling of special column name with parentheses."""
        data = {
            "流失(含待遇支付)": "10000.00"
        }

        model = AnnuityPerformanceIn(**data)
        assert model.流失_含待遇支付 == "10000.00"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed in input model."""
        data = {
            "年": "2024",
            "unknown_column": "should_be_ignored",
            "extra_field": 123,
        }

        model = AnnuityPerformanceIn(**data)
        assert model.年 == "2024"
        # Extra fields are allowed but not accessible as attributes

    def test_date_field_cleaning(self):
        """Test that date fields are cleaned properly."""
        data = {
            "年": "2024年",  # Contains "年" character
            "月": "11月",   # Contains "月" character
        }

        model = AnnuityPerformanceIn(**data)
        assert model.年 == "2024"  # Should be cleaned
        assert model.月 == "11"   # Should be cleaned

    def test_whitespace_stripping(self):
        """Test that string fields strip whitespace."""
        data = {
            "计划代码": "  TEST001  ",
            "客户名称": " 测试客户 ",
        }

        model = AnnuityPerformanceIn(**data)
        assert model.计划代码 == "TEST001"
        assert model.客户名称 == "测试客户"


class TestAnnuityPerformanceOut:
    """Tests for AnnuityPerformanceOut output model with strict validation."""

    def test_required_fields_validation(self):
        """Test that required fields are enforced."""
        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(data_source="test")

        error_str = str(exc_info.value)
        assert "计划代码" in error_str
        assert "公司代码" in error_str

    def test_basic_valid_model(self):
        """Test creating a valid model with minimal fields."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test_file.xlsx"
        )

        assert model.计划代码 == "TEST001"
        assert model.公司代码 == "COMP001"
        assert model.data_source == "test_file.xlsx"
        assert model.processed_at is not None
        assert model.has_financial_data is False

    def test_code_normalization(self):
        """Test that identifier codes are normalized properly."""
        model = AnnuityPerformanceOut(
            计划代码="test-001",
            公司代码="comp_002",
            data_source="test"
        )

        assert model.计划代码 == "TEST001"  # Uppercase, no separators
        assert model.公司代码 == "COMP002"  # Uppercase, no separators


class TestDecimalQuantization:
    """Test decimal field quantization according to DDL precision requirements."""

    def test_financial_fields_4_decimal_places(self):
        """Test that most financial fields are quantized to 4 decimal places."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模=1234.56789,  # Should be rounded to 4 places
            期末资产规模="2345.67891",  # String input
            供款=Decimal("3456.78901"),  # Decimal input
        )

        assert model.期初资产规模 == Decimal("1234.5679")
        assert model.期末资产规模 == Decimal("2345.6789")
        assert model.供款 == Decimal("3456.7890")

    def test_return_rate_6_decimal_places(self):
        """Test that return rate is quantized to 6 decimal places."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            当期收益率=0.048799999999999996,  # Float precision tail
        )

        # Should be quantized to 6 decimal places
        assert model.当期收益率 == Decimal("0.048800")
        assert str(model.当期收益率) == "0.048800"

    def test_percentage_conversion(self):
        """Test that percentage strings are converted to decimals."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            当期收益率="5.5%",  # Should become 0.055
        )

        assert model.当期收益率 == Decimal("0.055000")

    def test_currency_symbol_removal(self):
        """Test that currency symbols are removed from financial fields."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模="¥1,000,000.50",  # Currency and comma formatting
        )

        assert model.期初资产规模 == Decimal("1000000.5000")

    def test_placeholder_values_become_none(self):
        """Test that placeholder values become None."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模="N/A",  # Placeholder value
            投资收益="无",      # Chinese placeholder
            供款="-",          # Dash placeholder
        )

        assert model.期初资产规模 is None
        assert model.投资收益 is None
        assert model.供款 is None

    def test_invalid_decimal_raises_error(self):
        """Test that invalid decimal values raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                公司代码="COMP001",
                data_source="test",
                期初资产规模="not_a_number",
            )

        error_str = str(exc_info.value)
        assert "Cannot convert to decimal" in error_str


class TestModelValidators:
    """Test model-level validators and business logic."""

    def test_report_date_validation(self):
        """Test report date validation and consistency."""
        # Future date should raise error
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                公司代码="COMP001",
                data_source="test",
                月度=date(2030, 1, 1),  # Future date
            )

        assert "Report date cannot be in future" in str(exc_info.value)

    def test_old_date_warning(self):
        """Test that very old dates generate warnings."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            月度=date(2010, 1, 1),  # Very old date
        )

        assert len(model.validation_warnings) > 0
        assert "very old" in model.validation_warnings[0].lower()

    def test_financial_data_flag(self):
        """Test that has_financial_data flag is set correctly."""
        # Model without financial data
        model1 = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test"
        )
        assert model1.has_financial_data is False

        # Model with financial data
        model2 = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模=1000000,
        )
        assert model2.has_financial_data is True

    def test_consistency_validation_warnings(self):
        """Test cross-field consistency validation."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            当期收益率=0.8,  # 80% return rate - should trigger warning
        )

        assert len(model.validation_warnings) > 0
        assert "Unusually high return rate" in model.validation_warnings[0]

    def test_negative_asset_scale_warning(self):
        """Test that negative asset scales generate warnings."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模=-1000,  # Negative asset scale
        )

        assert len(model.validation_warnings) > 0
        assert "negative" in model.validation_warnings[0].lower()

    def test_asset_flow_balance_warning(self):
        """Test asset flow balance validation warning."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            公司代码="COMP001",
            data_source="test",
            期初资产规模=100000,
            期末资产规模=200000,  # Final much higher than expected
            供款=10000,
            投资收益=5000,
            # Expected final: 100000 + 10000 + 5000 = 115000, but actual is 200000
        )

        assert len(model.validation_warnings) > 0
        assert "doesn't balance" in model.validation_warnings[0]

    def test_extra_fields_not_allowed_in_output(self):
        """Test that extra fields are forbidden in output model."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                公司代码="COMP001",
                data_source="test",
                extra_field="should_fail",  # Extra field not allowed
            )

        assert "Extra inputs are not permitted" in str(exc_info.value)
