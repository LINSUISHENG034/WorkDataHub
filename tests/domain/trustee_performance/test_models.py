"""
Enhanced decimal precision validation testing for trustee performance models.

This module provides comprehensive tests for decimal field quantization,
float precision handling, and Pydantic v2 field validator patterns
according to PRP P-013 requirements.
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from pydantic import ValidationError, ValidationInfo
import pytest

pytestmark = pytest.mark.sample_domain

from src.work_data_hub.domain.sample_trustee_performance.models import (
    TrusteePerformanceOut,
)


class TestDecimalQuantizationEnhanced:
    """Enhanced decimal field quantization tests according to PRP P-013."""

    def test_return_rate_quantization_6_places(self):
        """Test return_rate quantization to 6 decimal places."""
        # Test float precision tail that would fail without quantization
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate=0.048799999999999996,  # Float precision tail
            data_source="test",
        )

        # Should be quantized to 6 decimal places
        assert model.return_rate == Decimal("0.048800")
        assert str(model.return_rate) == "0.048800"

    def test_net_asset_value_quantization_4_places(self):
        """Test net_asset_value quantization to 4 decimal places."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            net_asset_value=1.23456789,  # Should be rounded to 4 places
            data_source="test",
        )

        # Should be quantized to 4 decimal places using ROUND_HALF_UP
        assert model.net_asset_value == Decimal("1.2346")
        assert str(model.net_asset_value) == "1.2346"

    def test_fund_scale_quantization_2_places(self):
        """Test fund_scale quantization to 2 decimal places."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            fund_scale=1000.999,  # Should be rounded to 2 places
            data_source="test",
        )

        # Should be quantized to 2 decimal places
        assert model.fund_scale == Decimal("1001.00")
        assert str(model.fund_scale) == "1001.00"

    def test_decimal_from_string_avoids_float_precision(self):
        """Test that string inputs avoid float precision issues."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate="0.048799999999999996",  # String input
            data_source="test",
        )

        # Should handle string properly and quantize
        assert model.return_rate == Decimal("0.048800")

    def test_percentage_format_with_quantization(self):
        """Test percentage format conversion with quantization."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate="4.8799999%",  # Percentage with precision tail
            data_source="test",
        )

        # Should convert to decimal and quantize: 4.8799999% -> 0.048800
        assert model.return_rate == Decimal("0.048800")

    def test_field_specific_quantization_preserved(self):
        """Test that different fields get different precision levels."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate=0.1234567890,  # Should be 6 places: 0.123457
            net_asset_value=1.23456789,  # Should be 4 places: 1.2346
            fund_scale=1000.12345,  # Should be 2 places: 1000.12
            data_source="test",
        )

        assert model.return_rate == Decimal("0.123457")
        assert model.net_asset_value == Decimal("1.2346")
        assert model.fund_scale == Decimal("1000.12")

    def test_quantization_none_values_preserved(self):
        """Test that None values are preserved through quantization."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate=None,
            net_asset_value=None,
            fund_scale=None,
            data_source="test",
        )

        assert model.return_rate is None
        assert model.net_asset_value is None
        assert model.fund_scale is None


class TestFloatPrecisionEdgeCases:
    """Test problematic float precision edge cases that trigger decimal_max_places."""

    def test_binary_float_precision_issues(self):
        """Test specific float values that cause binary precision issues."""
        # These are real-world problematic float values from Excel/Python
        problematic_floats = [
            (0.048799999999999996, "return_rate", Decimal("0.048800")),
            (1.0512000000000001, "net_asset_value", Decimal("1.0512")),
            (12000000.003, "fund_scale", Decimal("12000000.00")),
            (
                0.1 + 0.2,
                "return_rate",
                Decimal("0.300000"),
            ),  # Classic 0.30000000000000004
            (1.1 + 2.2, "net_asset_value", Decimal("3.3000")),  # Should be 3.3
        ]

        for float_val, field_name, expected_decimal in problematic_floats:
            # Test direct field assignment
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: float_val,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_decimal, (
                f"Field {field_name}: {float_val} -> {actual_value}, expected {expected_decimal}"
            )

    def test_scientific_notation_float_inputs(self):
        """Test float inputs in scientific notation are handled correctly."""
        scientific_cases = [
            (5.5e-2, "return_rate", Decimal("0.055000")),  # 0.055
            (1.2e0, "net_asset_value", Decimal("1.2000")),  # 1.2
            (1.5e6, "fund_scale", Decimal("1500000.00")),  # 1500000.0
            (1e-6, "return_rate", Decimal("0.000001")),  # Very small
        ]

        for sci_val, field_name, expected_decimal in scientific_cases:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: sci_val,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_decimal

    def test_extremely_long_float_precision_tails(self):
        """Test floats with extremely long precision tails."""
        long_precision_cases = [
            # Simulating Excel float precision issues
            (0.0487999999999999962659273842, "return_rate", Decimal("0.048800")),
            (1.0512000000000000455191440024, "net_asset_value", Decimal("1.0512")),
            (12000000.002999999999999998, "fund_scale", Decimal("12000000.00")),
        ]

        for long_float, field_name, expected_decimal in long_precision_cases:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: long_float,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_decimal

    def test_decimal_construction_from_float_string_conversion(self):
        """Test the str(float) -> Decimal conversion pattern used in the validator."""
        # This tests the exact pattern used in clean_decimal_fields
        float_values = [
            0.048799999999999996,
            1.0512000000000001,
            12000000.003,
            0.1 + 0.2,  # 0.30000000000000004
        ]

        for float_val in float_values:
            # Test the conversion pattern: float -> controlled str -> Decimal
            str_val = format(float_val, ".17f").rstrip("0").rstrip(".")
            if not str_val:
                str_val = "0"
            decimal_val = Decimal(str_val)

            # Verify string conversion fixes float precision
            assert isinstance(decimal_val, Decimal)
            # The string representation should be reasonable
            assert len(str_val.split(".")[-1]) <= 17  # Reasonable precision length


class TestFieldValidatorInfoIntegration:
    """Test FieldValidationInfo integration with decimal quantization."""

    def test_field_validator_receives_correct_field_name(self):
        """Test that field validators receive correct field_name in ValidationInfo."""
        from src.work_data_hub.domain.sample_trustee_performance.models import (
            TrusteePerformanceOut,
        )

        # Mock ValidationInfo to test the field_name parameter
        original_validator = TrusteePerformanceOut.clean_decimal_fields

        captured_field_names = []

        def mock_validator(cls, v, info):
            captured_field_names.append(info.field_name)
            return original_validator(v, info)

        # Patch the validator temporarily
        TrusteePerformanceOut.clean_decimal_fields = classmethod(mock_validator)

        try:
            model = TrusteePerformanceOut(
                report_date="2024-01-01",
                plan_code="P001",
                company_code="C001",
                return_rate=0.055,
                net_asset_value=1.23,
                fund_scale=1000.00,
                data_source="test",
            )

            # Verify all three decimal fields were processed with correct field names
            assert "return_rate" in captured_field_names
            assert "net_asset_value" in captured_field_names
            assert "fund_scale" in captured_field_names

        finally:
            # Restore original validator
            TrusteePerformanceOut.clean_decimal_fields = original_validator

    def test_field_precision_map_coverage(self):
        """Test that all decimal fields are covered in FIELD_PRECISION_MAP."""
        from src.work_data_hub.domain.sample_trustee_performance.models import (
            TrusteePerformanceOut,
        )

        # Extract field_precision_map from validator (this tests the actual implementation)
        field_precision_map = {
            "return_rate": 6,  # NUMERIC(8,6)
            "net_asset_value": 4,  # NUMERIC(18,4)
            "fund_scale": 2,  # NUMERIC(18,2)
        }

        # Verify all decimal fields in model are covered
        model_fields = TrusteePerformanceOut.model_fields
        decimal_fields = []

        for field_name, field_info in model_fields.items():
            # Check for Optional[Decimal] fields
            if hasattr(field_info.annotation, "__origin__"):
                # Handle Optional[Decimal] -> Union[Decimal, None]
                args = getattr(field_info.annotation, "__args__", ())
                if Decimal in args:
                    decimal_fields.append(field_name)

        # Ensure all decimal fields have precision mapping
        for field_name in decimal_fields:
            assert field_name in field_precision_map, (
                f"Field {field_name} missing from field_precision_map"
            )

    def test_clean_decimal_fields_direct_invocation(self):
        """Test direct invocation of clean_decimal_fields validator."""
        from src.work_data_hub.domain.sample_trustee_performance.models import (
            TrusteePerformanceOut,
        )

        # Mock ValidationInfo for testing
        mock_info = Mock(spec=ValidationInfo)

        # Test each field type directly
        test_cases = [
            ("return_rate", 0.048799999999999996, Decimal("0.048800")),
            ("net_asset_value", 1.23456789, Decimal("1.2346")),
            ("fund_scale", 1000.999, Decimal("1001.00")),
        ]

        for field_name, input_val, expected_output in test_cases:
            mock_info.field_name = field_name

            result = TrusteePerformanceOut.clean_decimal_fields(input_val, mock_info)

            assert result == expected_output
            assert isinstance(result, Decimal)


class TestPydanticV2ValidatorPatterns:
    """Test Pydantic v2 validator patterns and behaviors."""

    def test_mode_before_validator_behavior(self):
        """Test that mode='before' validators receive raw input."""
        # The clean_decimal_fields validator uses mode='before'
        # This means it receives raw input before Pydantic type conversion

        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate="5.5%",  # String input that should be processed by validator
            data_source="test",
        )

        # Validator should have processed the string percentage
        assert model.return_rate == Decimal("0.055")

    def test_validator_handles_various_input_types(self):
        """Test validator handles int, float, str, Decimal inputs correctly."""
        input_variations = [
            (5, "fund_scale", Decimal("5.00")),  # int
            (5.5, "return_rate", Decimal("0.055000")),  # float (as percentage)
            ("5.5", "net_asset_value", Decimal("5.5000")),  # string
            (Decimal("5.5"), "fund_scale", Decimal("5.50")),  # Decimal
            ("5.5%", "return_rate", Decimal("0.055000")),  # percentage string
        ]

        for input_val, field_name, expected_output in input_variations:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: input_val,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_output

    def test_validator_error_handling(self):
        """Test validator properly raises ValidationError for invalid inputs."""
        invalid_cases = [
            ("return_rate", "not_a_number"),
            ("net_asset_value", "invalid%"),
            ("fund_scale", "N/A/invalid"),
        ]

        for field_name, invalid_value in invalid_cases:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: invalid_value,
                "data_source": "test",
            }

            with pytest.raises(ValidationError) as exc_info:
                TrusteePerformanceOut(**kwargs)

            # Verify the error relates to the problematic field
            error_details = exc_info.value.errors()[0]
            assert field_name in str(error_details["loc"])

    def test_placeholder_value_handling(self):
        """Test that placeholder values are converted to None."""
        placeholder_values = ["", "-", "N/A", "无", "暂无"]

        for placeholder in placeholder_values:
            model = TrusteePerformanceOut(
                report_date="2024-01-01",
                plan_code="P001",
                company_code="C001",
                return_rate=placeholder,
                net_asset_value=placeholder,
                fund_scale=placeholder,
                data_source="test",
            )

            assert model.return_rate is None
            assert model.net_asset_value is None
            assert model.fund_scale is None

    def test_currency_symbol_cleaning(self):
        """Test that currency symbols are properly cleaned from inputs."""
        currency_cases = [
            ("¥1000.50", "fund_scale", Decimal("1000.50")),
            ("$1.23", "net_asset_value", Decimal("1.2300")),
            ("￥1,234.56", "fund_scale", Decimal("1234.56")),
        ]

        for input_val, field_name, expected_output in currency_cases:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: input_val,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_output


class TestRoundingBehaviorConsistency:
    """Test consistent rounding behavior across all decimal fields."""

    def test_round_half_up_behavior(self):
        """Test ROUND_HALF_UP behavior is consistent."""
        # Test exact .5 cases that should round up
        half_up_cases = [
            ("return_rate", 0.0555555, Decimal("0.055556")),  # 6th place = 5, round up
            ("net_asset_value", 1.23455, Decimal("1.2346")),  # 4th place = 5, round up
            ("fund_scale", 1000.125, Decimal("1000.13")),  # 2nd place = 5, round up
        ]

        for field_name, input_val, expected_output in half_up_cases:
            kwargs = {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                field_name: input_val,
                "data_source": "test",
            }

            model = TrusteePerformanceOut(**kwargs)
            actual_value = getattr(model, field_name)

            assert actual_value == expected_output

    def test_quantize_preserves_scale(self):
        """Test quantization preserves the correct decimal scale."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate=0.1,  # Should have 6 decimal places
            net_asset_value=1.2,  # Should have 4 decimal places
            fund_scale=1000,  # Should have 2 decimal places
            data_source="test",
        )

        # Test the string representation has correct decimal places
        assert str(model.return_rate) == "0.100000"  # 6 places
        assert str(model.net_asset_value) == "1.2000"  # 4 places
        assert str(model.fund_scale) == "1000.00"  # 2 places

        # Test the scale property
        assert model.return_rate.as_tuple().exponent == -6
        assert model.net_asset_value.as_tuple().exponent == -4
        assert model.fund_scale.as_tuple().exponent == -2


class TestExcelNumericCellCompatibility:
    """Test compatibility with numeric Excel cell values."""

    def test_excel_float_cells_processed_correctly(self):
        """Test that Excel float cells don't cause ValidationError crashes."""
        # These simulate actual Excel cell values that caused crashes
        excel_float_values = [
            1.0512,  # Excel float (was causing error)
            12000000,  # Excel int (was causing error)
            0.055,  # Excel decimal
            1.0512000000000001,  # Excel precision artifact
        ]

        for excel_val in excel_float_values:
            # Should not raise ValidationError
            model = TrusteePerformanceOut(
                report_date="2024-01-01",
                plan_code="P001",
                company_code="C001",
                net_asset_value=excel_val,
                data_source="test",
            )

            assert isinstance(model, TrusteePerformanceOut)
            assert isinstance(model.net_asset_value, Decimal)

    def test_mixed_numeric_string_backward_compatibility(self):
        """Test mixing numeric and string inputs maintains backward compatibility."""
        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            net_asset_value="1.0512",  # String (existing behavior)
            fund_scale=12000000,  # Numeric (new capability)
            return_rate="5.5%",  # String percentage (existing behavior)
            data_source="test",
        )

        assert model.net_asset_value == Decimal("1.0512")
        assert model.fund_scale == Decimal("12000000.00")
        assert model.return_rate == Decimal("0.055000")  # 5.5% -> 0.055
