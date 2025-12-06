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

        assert "cannot be in the future" in str(exc_info.value)

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


class TestDateParsingAC412:
    """
    AC-4.1.2: Date validator parses Chinese formats.

    Tests for parse_yyyymm_or_chinese() integration in 月度 field validator.
    """

    def test_parse_yyyymm_integer_format(self):
        """Test parsing YYYYMM format (e.g., 202501 → date(2025, 1, 1))."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度=202501,  # Integer YYYYMM format
        )

        assert model.月度 == date(2025, 1, 1)

    def test_parse_yyyymm_string_format(self):
        """Test parsing YYYYMM string format (e.g., '202501' → date(2025, 1, 1))."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="202501",  # String YYYYMM format
        )

        assert model.月度 == date(2025, 1, 1)

    def test_parse_chinese_year_month_format(self):
        """Test parsing YYYY年MM月 format (e.g., '2025年1月' → date(2025, 1, 1))."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="2025年1月",  # Chinese format
        )

        assert model.月度 == date(2025, 1, 1)

    def test_parse_iso_year_month_format(self):
        """Test parsing YYYY-MM format (e.g., '2025-01' → date(2025, 1, 1))."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="2025-01",  # ISO format
        )

        assert model.月度 == date(2025, 1, 1)

    def test_parse_date_object_passthrough(self):
        """Test that date objects are passed through unchanged."""
        input_date = date(2025, 1, 1)
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度=input_date,
        )

        assert model.月度 == input_date

    def test_invalid_date_format_raises_clear_error(self):
        """Test that invalid formats raise ValueError with supported format list."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度="INVALID_DATE",  # Invalid format
            )

        error_str = str(exc_info.value)
        assert "Cannot parse" in error_str
        # Should mention supported formats
        assert any(fmt in error_str for fmt in ["YYYYMM", "YYYY年MM月", "YYYY-MM"])

    def test_date_out_of_range_raises_error(self):
        """Test that dates outside 2000-2030 range raise ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度=199912,  # Year 1999, outside valid range
            )

        error_str = str(exc_info.value)
        assert "outside valid range" in error_str or "2000" in error_str


class TestBusinessRulesAC413:
    """
    AC-4.1.3: Validation enforces business rules.

    Tests for strict validation in AnnuityPerformanceOut model.
    """

    def test_negative_ending_assets_rejected(self):
        """Test that 期末资产规模 >= 0 (non-negative ending assets)."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期末资产规模=-1000.0,  # Negative value should fail
            )

        error_str = str(exc_info.value)
        assert "期末资产规模" in error_str
        assert "greater than or equal to 0" in error_str

    def test_negative_starting_assets_rejected(self):
        """Test that 期初资产规模 >= 0 (non-negative starting assets)."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期初资产规模=-500.0,  # Negative value should fail
            )

        error_str = str(exc_info.value)
        assert "期初资产规模" in error_str
        assert "greater than or equal to 0" in error_str

    def test_zero_assets_accepted(self):
        """Test that zero asset values are accepted (edge case)."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            期初资产规模=0.0,
            期末资产规模=0.0,
        )

        assert model.期初资产规模 == Decimal("0.0000")
        assert model.期末资产规模 == Decimal("0.0000")

    def test_empty_plan_code_rejected(self):
        """Test that 计划代码 is non-empty string (plan code required)."""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="",  # Empty string should fail
                company_id="COMP001",
            )

        error_str = str(exc_info.value)
        assert "计划代码" in error_str

    def test_company_id_optional_but_validated_when_present(self):
        """Test that company_id is optional but validated when provided."""
        # None is allowed (Epic 5 will generate it)
        model1 = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id=None,
        )
        assert model1.company_id is None

        # Non-empty string is required when provided
        model2 = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
        )
        assert model2.company_id == "COMP001"

    def test_date_must_be_date_object_not_string(self):
        """Test that 月度 is valid date object (not string) after validation."""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="202501",  # String input
        )

        # After validation, should be date object
        assert isinstance(model.月度, date)
        assert model.月度 == date(2025, 1, 1)


class TestLegacyParityAC414:
    """
    AC-4.1.4: Models support legacy parity requirements.

    Tests for legacy field mappings and column renaming support.
    """

    def test_institution_name_alias_support(self):
        """Test column renaming: 机构 → 机构名称 (both names accepted)."""
        # Test with alias '机构'
        model = AnnuityPerformanceIn(机构="测试机构")
        assert model.机构名称 == "测试机构"

        # Test with standard name '机构名称'
        model2 = AnnuityPerformanceIn(机构名称="测试机构2")
        assert model2.机构名称 == "测试机构2"

    def test_account_name_preservation_field_exists(self):
        """Test 年金账户名 field for original company name before cleansing."""
        # In AnnuityPerformanceIn
        model_in = AnnuityPerformanceIn(
            年金账户名="原始公司名称（未清洗）",
            客户名称="清洗后公司名称",
        )
        assert model_in.年金账户名 == "原始公司名称（未清洗）"
        assert model_in.客户名称 == "清洗后公司名称"

        # In AnnuityPerformanceOut
        model_out = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            年金账户名="原始公司名称",
            客户名称="清洗后公司名称",
        )
        assert model_out.年金账户名 == "原始公司名称"
        assert model_out.客户名称 == "清洗后公司名称"

    def test_all_legacy_fields_present_in_models(self):
        """Test that all legacy fields from AnnuityPerformanceCleaner are supported."""
        legacy_fields = {
            "机构名称": "测试机构",
            "机构代码": "G01",
            "组合代码": "P001",
            "产品线代码": "L001",
            "年金账户名": "原始账户名",
            "计划代码": "TEST001",
            "客户名称": "测试客户",
        }

        # All fields should be accepted in input model
        model_in = AnnuityPerformanceIn(**legacy_fields)
        assert model_in.机构名称 == "测试机构"
        assert model_in.机构代码 == "G01"
        assert model_in.组合代码 == "P001"
        assert model_in.产品线代码 == "L001"
        assert model_in.年金账户名 == "原始账户名"

        # All fields should be accepted in output model
        model_out = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            机构名称="测试机构",
            机构代码="G01",
            组合代码="P001",
            产品线代码="L001",
            年金账户名="原始账户名",
            客户名称="测试客户",
        )
        assert model_out.机构名称 == "测试机构"
        assert model_out.机构代码 == "G01"
        assert model_out.组合代码 == "P001"
        assert model_out.产品线代码 == "L001"
        assert model_out.年金账户名 == "原始账户名"

    def test_parentheses_column_alias_support(self):
        """Test 流失（含待遇支付）→ 流失_含待遇支付 column renaming."""
        # Input model accepts both forms
        model_in = AnnuityPerformanceIn(**{"流失(含待遇支付)": "1000.0"})
        assert model_in.流失_含待遇支付 == 1000.0

        # Output model accepts both forms
        model_out = AnnuityPerformanceOut(
            计划代码="TEST001", company_id="COMP001", **{"流失(含待遇支付)": "2000.0"}
        )
        assert model_out.流失_含待遇支付 == Decimal("2000.0000")
