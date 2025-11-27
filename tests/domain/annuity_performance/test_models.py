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
        """Test that financial fields accept various input types and clean them."""
        data = {
            "期初资产规模": "1000000.50",
            "期末资产规模": 2000000,
            "投资收益": Decimal("50000.25"),
            "当期收益率": "5.5%",  # Percentage format
        }

        model = AnnuityPerformanceIn(**data)
        # Story 2.1: Numeric fields are cleaned to float/Decimal
        assert model.期初资产规模 == 1000000.5  # Cleaned from string
        assert model.期末资产规模 == 2000000.0  # Cleaned from int
        assert model.投资收益 == Decimal("50000.25")  # Decimal passthrough
        assert model.当期收益率 == 0.055  # Percentage converted to decimal

    def test_special_column_with_parentheses(self):
        """Test handling of special column name with parentheses."""
        data = {"流失(含待遇支付)": "10000.00"}

        model = AnnuityPerformanceIn(**data)
        # Story 2.1: Numeric fields are cleaned to float
        assert model.流失_含待遇支付 == 10000.0

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
            "月": "11月",  # Contains "月" character
        }

        model = AnnuityPerformanceIn(**data)
        assert model.年 == "2024"  # Should be cleaned
        assert model.月 == "11"  # Should be cleaned

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
            AnnuityPerformanceOut()

        error_str = str(exc_info.value)
        assert "计划代码" in error_str
        # company_id is now Optional (generated in Epic 5), so not required anymore

    def test_basic_valid_model(self):
        """Test creating a valid model with minimal fields."""
        # company_id is now Optional
        model = AnnuityPerformanceOut(计划代码="TEST001", company_id=None)

        assert model.计划代码 == "TEST001"
        assert model.company_id is None

    def test_code_normalization(self):
        """Test that identifier codes are normalized properly."""
        # company_id is now Optional
        model = AnnuityPerformanceOut(计划代码="test-001", company_id="comp_002")

        assert model.计划代码 == "TEST001"  # Uppercase, no separators
        assert model.company_id == "COMP002"  # Uppercase, no separators (when provided)


class TestDecimalQuantization:
    """Test decimal field quantization according to DDL precision requirements."""

    def test_financial_fields_4_decimal_places(self):
        """Test that most financial fields are quantized to 4 decimal places."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
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
            company_id="COMP001",
            当期收益率=0.048799999999999996,  # Float precision tail
        )

        # Should be quantized to 6 decimal places
        assert model.当期收益率 == Decimal("0.048800")
        assert str(model.当期收益率) == "0.048800"

    def test_percentage_conversion(self):
        """Test that percentage strings are converted to decimals."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            当期收益率="5.5%",  # Should become 0.055
        )

        assert model.当期收益率 == Decimal("0.055000")

    def test_currency_symbol_removal(self):
        """Test that currency symbols are removed from financial fields."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            期初资产规模="¥1,000,000.50",  # Currency and comma formatting
        )

        assert model.期初资产规模 == Decimal("1000000.5000")

    def test_placeholder_values_become_none(self):
        """Test that placeholder values become None."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            期初资产规模="N/A",  # Placeholder value
            投资收益="无",  # Chinese placeholder
            供款="-",  # Dash placeholder
        )

        assert model.期初资产规模 is None
        assert model.投资收益 is None
        assert model.供款 is None

    def test_invalid_decimal_raises_error(self):
        """Test that invalid decimal values raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期初资产规模="not_a_number",
            )

        error_str = str(exc_info.value)
        assert "could not convert string to float" in error_str


class TestModelValidators:
    """Test model-level validators and business logic."""

    def test_report_date_validation(self):
        """Test report date validation and consistency."""
        # Future date should raise error
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度=date(2030, 1, 1),  # Future date
            )

        assert "Report date cannot be in future" in str(exc_info.value)

    def test_old_date_warning(self):
        """Test that very old dates generate warnings."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度=date(2010, 1, 1),  # Very old date
        )

        # Old dates should be accepted (warnings were removed from model)

    def test_extra_fields_not_allowed_in_output(self):
        """Test that extra fields are forbidden in output model."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                extra_field="should_fail",  # Extra field not allowed
            )

        assert "Extra inputs are not permitted" in str(exc_info.value)
