"""
Story 2.1 Acceptance Criteria Tests

This module tests all acceptance criteria for Story 2.1:
- AC1: Loose validation model (AnnuityPerformanceIn)
- AC2: Strict validation model (AnnuityPerformanceOut)
- AC3: Custom validators (date parsing, company name cleaning)
- AC4: Error messages with field context
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.work_data_hub.cleansing import get_cleansing_registry
from src.work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
    parse_yyyymm_or_chinese,
)


class TestAC1_LooseValidationModel:
    """AC1: AnnuityPerformanceIn accepts messy Excel data with Optional[Union[...]] types"""

    def test_accepts_chinese_field_names(self):
        """AC1: Model accepts Chinese field names"""
        data = {
            "月度": "202501",
            "计划代码": "TEST001",
            "客户名称": "测试公司",
            "期初资产规模": 1000000,
            "期末资产规模": 2000000,
            "投资收益": 50000,
        }
        model = AnnuityPerformanceIn(**data)
        assert model.计划代码 == "TEST001"
        assert model.客户名称 == "测试公司"

    def test_accepts_optional_union_types(self):
        """AC1: Fields use Optional[Union[str, int, float, Decimal]] for flexibility"""
        # String input
        model1 = AnnuityPerformanceIn(期末资产规模="1234.56")
        assert model1.期末资产规模 == 1234.56

        # Int input
        model2 = AnnuityPerformanceIn(期末资产规模=1234)
        assert model2.期末资产规模 == 1234.0

        # Decimal input (validator converts to float for consistency)
        model3 = AnnuityPerformanceIn(期末资产规模=Decimal("1234.56"))
        assert model3.期末资产规模 == 1234.56  # Cleaned to float

        # None input
        model4 = AnnuityPerformanceIn(期末资产规模=None)
        assert model4.期末资产规模 is None

    def test_parses_comma_separated_numbers(self):
        """AC1: Handles comma-separated numbers like '1,234.56'"""
        model = AnnuityPerformanceIn(
            期初资产规模="1,000,000.50",
            期末资产规模="2,000,000.00",
        )
        assert model.期初资产规模 == 1000000.5
        assert model.期末资产规模 == 2000000.0

    def test_handles_currency_symbols(self):
        """AC1: Removes currency symbols (¥, $)"""
        model = AnnuityPerformanceIn(
            期初资产规模="¥1,234.56",
            供款="$5,000",
        )
        assert model.期初资产规模 == 1234.56
        assert model.供款 == 5000.0

    def test_handles_percentage_format(self):
        """AC1: Converts percentage strings to decimal ('5.5%' → 0.055)"""
        # Note: Using 当期收益率 field name from AnnuityPerformanceIn model
        model = AnnuityPerformanceIn(当期收益率="5.5%")
        assert model.当期收益率 == 0.055

    def test_handles_null_mixed_types(self):
        """AC1: Accepts None, empty strings, placeholders"""
        model = AnnuityPerformanceIn(
            期初资产规模=None,
            期末资产规模="",
            供款="N/A",
            流失="无",
            待遇支付="-",
        )
        assert model.期初资产规模 is None
        assert model.期末资产规模 is None
        assert model.供款 is None
        assert model.流失 is None
        assert model.待遇支付 is None


class TestAC2_StrictValidationModel:
    """AC2: AnnuityPerformanceOut enforces strict validation and business rules"""

    def test_required_fields_enforced(self):
        """AC2: Required fields raise ValidationError if missing"""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut()

        errors = exc_info.value.errors()
        error_fields = {e['loc'][0] for e in errors}
        assert '计划代码' in error_fields
        assert 'company_id' in error_fields

    def test_non_negative_constraints(self):
        """AC2: Asset fields must be non-negative (>= 0)"""
        # Valid: zero is allowed
        model_zero = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            期初资产规模=Decimal("0"),
            期末资产规模=Decimal("0"),
            供款=Decimal("0"),
        )
        assert model_zero.期初资产规模 == Decimal("0")

        # Invalid: negative values should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期初资产规模=Decimal("-1000"),
            )
        assert '期初资产规模' in str(exc_info.value)

    def test_business_rule_zero_asset_no_return(self):
        """AC2: When 期末资产规模=0, 年化收益率 must be None"""
        # Valid: 期末资产规模=0, 年化收益率=None
        model_valid = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            期末资产规模=Decimal("0"),
            年化收益率=None,
        )
        assert model_valid.年化收益率 is None

        # Invalid: 期末资产规模=0, 年化收益率 != None
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期末资产规模=Decimal("0"),
                年化收益率=Decimal("0.05"),
            )
        assert "Business Rule Violation" in str(exc_info.value)
        assert "年化收益率 must be None" in str(exc_info.value)

    def test_strict_types_validation(self):
        """AC2: Output model enforces strict types"""
        # Valid data
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度=date(2025, 1, 1),
            期末资产规模=Decimal("1000000.50"),
        )
        assert isinstance(model.月度, date)
        assert isinstance(model.期末资产规模, Decimal)


class TestAC3_CustomValidators:
    """AC3: Custom validators integrate with cleansing registry + date parser"""

    def test_date_parsing_validator(self):
        """AC3: @field_validator('月度') parses Chinese date formats"""
        # YYYYMM integer
        model1 = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度=202501,
        )
        assert model1.月度 == date(2025, 1, 1)

        # YYYY年MM月 string
        model2 = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="2025年1月",
        )
        assert model2.月度 == date(2025, 1, 1)

        # YYYY-MM string
        model3 = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            月度="2025-01",
        )
        assert model3.月度 == date(2025, 1, 1)

    def test_company_name_cleaning_validator(self):
        """AC3: @field_validator('客户名称') cleans company names"""
        model = AnnuityPerformanceOut(
            计划代码="TEST001",
            company_id="COMP001",
            客户名称="  测试公司　名称  ",  # Has whitespace and full-width space
        )
        # Should trim and normalize spaces
        assert model.客户名称 == "测试公司 名称"

    def test_cleansing_registry_rules_available(self):
        """AC3: Cleansing registry exposes reusable rule chains"""
        registry = get_cleansing_registry()

        # Test parse_yyyymm_or_chinese
        assert parse_yyyymm_or_chinese(202501) == date(2025, 1, 1)
        assert parse_yyyymm_or_chinese("2025年1月") == date(2025, 1, 1)
        assert parse_yyyymm_or_chinese("2025-01") == date(2025, 1, 1)

        # Test CleansingRegistry string rules
        assert registry.apply_rules(
            "  测试　ABC  ",
            ["trim_whitespace", "normalize_company_name"],
        ) == "测试 ABC"
        assert registry.apply_rules(
            "「测试」",
            ["trim_whitespace", "normalize_company_name"],
        ) == "测试"

        numeric_rules = [
            "standardize_null_values",
            "remove_currency_symbols",
            "clean_comma_separated_number",
            {"name": "handle_percentage_conversion"},
        ]
        assert float(registry.apply_rules("1,234.56", numeric_rules)) == 1234.56
        assert float(registry.apply_rules("¥1,234", numeric_rules)) == 1234.0
        assert registry.apply_rules("N/A", numeric_rules) is None
        assert registry.apply_rules("5.5%", numeric_rules) == pytest.approx(0.055)


class TestAC4_ErrorMessages:
    """AC4: Error messages include field names and context"""

    def test_error_message_includes_field_name(self):
        """AC4: Validation errors include field name for context"""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度="INVALID_DATE",
            )

        error_msg = str(exc_info.value)
        # Should mention the field name
        assert "月度" in error_msg or "Field '月度'" in error_msg

    def test_error_message_for_date_parsing(self):
        """AC4: Date parsing errors are descriptive"""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度="INVALID",
            )

        error_msg = str(exc_info.value)
        # Should explain supported formats
        assert "Cannot parse" in error_msg or "Supported formats" in error_msg.lower()

    def test_error_message_for_number_parsing(self):
        """AC4: Number parsing errors are descriptive"""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                期末资产规模="not_a_number",
            )

        error_msg = str(exc_info.value)
        # Should explain expected format
        assert (
            "Cannot convert" in error_msg
            or "Expected format" in error_msg
            or "Cannot clean numeric value" in error_msg
        )

    def test_error_message_for_business_rule(self):
        """AC4: Business rule violations have clear error messages"""
        with pytest.raises(ValidationError) as exc_info:
            AnnuityPerformanceOut(
                计划代码="TEST001",
                company_id="COMP001",
                月度=date(2030, 1, 1),  # Future date
            )

        error_msg = str(exc_info.value)
        # Should explain the issue clearly
        assert "cannot be in the future" in error_msg.lower()


class TestAC5_IntegrationWithPipelineFramework:
    """AC5: Models integrate with Epic 1 Pipeline Framework (verified via imports)"""

    def test_models_can_be_imported_and_used(self):
        """AC5: Models can be instantiated and used in pipelines"""
        # Input model creates flexible input
        input_data = {
            "月度": "202501",
            "计划代码": "TEST001",
            "company_id": "COMP001",
            "期末资产规模": "1,000,000.50",
        }
        input_model = AnnuityPerformanceIn(**input_data)

        # Output model enforces strict validation
        output_model = AnnuityPerformanceOut(
            计划代码=input_model.计划代码,
            company_id="COMP001",
            月度=date(2025, 1, 1),
            期末资产规模=Decimal(str(input_model.期末资产规模)),
        )

        assert output_model.计划代码 == "TEST001"
        assert output_model.期末资产规模 == Decimal("1000000.50")


# Note: AC6 (Performance tests) are in separate test file:
# tests/performance/test_story_2_1_performance.py
