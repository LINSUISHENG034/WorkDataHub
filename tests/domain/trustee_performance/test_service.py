"""
Tests for trustee performance domain service.

This module tests the pure transformation functions in the trustee performance
domain service with various input scenarios and edge cases.
"""

from datetime import date
from decimal import Decimal

import pytest
pytestmark = pytest.mark.sample_domain

from src.work_data_hub.domain.sample_trustee_performance.models import (
    TrusteePerformanceIn,
    TrusteePerformanceOut,
)
from src.work_data_hub.domain.sample_trustee_performance.service import (
    TrusteePerformanceTransformationError,
    _extract_company_code,
    _extract_plan_code,
    _extract_report_date,
    _parse_report_period,
    _transform_single_row,
    process,
    validate_input_batch,
)


@pytest.fixture
def valid_row_chinese():
    """Sample valid row with Chinese field names."""
    return {
        "年": "2024",
        "月": "11",
        "计划代码": "PLAN001",
        "公司代码": "COMP001",
        "收益率": "5.5%",
        "净值": "1.05",
        "规模": "1000000.00",
    }


@pytest.fixture
def valid_row_english():
    """Sample valid row with English field names."""
    return {
        "year": 2024,
        "month": 11,
        "plan_code": "PLAN002",
        "company_code": "COMP002",
        "收益率": "0.055",
        "净值": "1.05",
    }


@pytest.fixture
def invalid_row():
    """Sample row missing required fields."""
    return {"收益率": "5%", "other_field": "some value"}


class TestProcessFunction:
    """Test the main process function."""

    def test_process_valid_rows(self, valid_row_chinese, valid_row_english):
        """Test processing valid input rows."""
        rows = [valid_row_chinese, valid_row_english]

        result = process(rows, data_source="test_source")

        assert len(result) == 2
        assert all(isinstance(item, TrusteePerformanceOut) for item in result)

        # Check first record
        first = result[0]
        assert first.report_date == date(2024, 11, 1)
        assert first.plan_code == "PLAN001"
        assert first.company_code == "COMP001"
        assert first.data_source == "test_source"
        assert first.return_rate == Decimal("0.055")  # 5.5% converted

        # Check second record
        second = result[1]
        assert second.report_date == date(2024, 11, 1)
        assert second.plan_code == "PLAN002"
        assert second.company_code == "COMP002"

    def test_process_empty_rows(self):
        """Test processing empty row list."""
        result = process([])
        assert result == []

    def test_process_invalid_input_type(self):
        """Test process function with invalid input type."""
        with pytest.raises(ValueError, match="Rows must be provided as a list"):
            process("not a list")

    def test_process_rows_with_missing_data(self, invalid_row):
        """Test processing rows with missing required data."""
        rows = [invalid_row]

        # Should raise TrusteePerformanceTransformationError due to 100% failure rate
        with pytest.raises(
            TrusteePerformanceTransformationError, match="Too many processing errors"
        ):
            process(rows, data_source="test")

    def test_process_mixed_valid_invalid_rows(self, valid_row_chinese, invalid_row):
        """Test processing mix of valid and invalid rows."""
        rows = [valid_row_chinese, invalid_row, valid_row_chinese]

        result = process(rows, data_source="mixed_test")

        # Should successfully process 2 valid rows, skip 1 invalid
        assert len(result) == 2
        assert all(item.data_source == "mixed_test" for item in result)

    def test_process_high_error_rate(self, invalid_row):
        """Test processing with high error rate raises exception."""
        # Create mostly invalid rows (>50% failure rate)
        rows = [invalid_row] * 10  # All invalid rows

        with pytest.raises(
            TrusteePerformanceTransformationError, match="Too many processing errors"
        ):
            process(rows, data_source="high_error_test")


class TestSingleRowTransformation:
    """Test single row transformation logic."""

    def test_transform_valid_row(self, valid_row_chinese):
        """Test transforming a valid single row."""
        result = _transform_single_row(valid_row_chinese, "test_source", 0)

        assert result is not None
        assert isinstance(result, TrusteePerformanceOut)
        assert result.plan_code == "PLAN001"
        assert result.company_code == "COMP001"
        assert result.return_rate == Decimal("0.055")

    def test_transform_row_missing_date(self):
        """Test transforming row missing date information."""
        row = {
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            # Missing year/month
        }

        result = _transform_single_row(row, "test_source", 0)

        # Should return None (filtered out)
        assert result is None

    def test_transform_row_missing_identifiers(self):
        """Test transforming row missing required identifiers."""
        row = {
            "年": "2024",
            "月": "11",
            # Missing plan_code and company_code
        }

        result = _transform_single_row(row, "test_source", 0)

        # Should return None (filtered out)
        assert result is None

    def test_transform_row_invalid_output_validation(self):
        """Test row that passes input validation but has invalid date (now returns None)."""
        row = {
            "年": "2024",
            "月": "13",  # Invalid month
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
        }

        # After bug fix: invalid dates cause the row to be filtered out (return None)
        result = _transform_single_row(row, "test_source", 0)
        assert result is None


class TestDateExtraction:
    """Test date extraction logic."""

    def test_extract_date_chinese_fields(self):
        """Test extracting date from Chinese field names."""
        input_model = TrusteePerformanceIn(年="2024", 月="11")

        result = _extract_report_date(input_model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_date_english_fields(self):
        """Test extracting date from English field names."""
        input_model = TrusteePerformanceIn(year=2024, month=11)

        result = _extract_report_date(input_model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_date_mixed_fields(self):
        """Test extracting date with mixed field names (Chinese takes priority)."""
        input_model = TrusteePerformanceIn(年="2024", month=5)  # Chinese year, English month

        result = _extract_report_date(input_model, 0)

        assert result == date(2024, 5, 1)

    def test_extract_date_from_report_period(self):
        """Test extracting date from report_period string."""
        input_model = TrusteePerformanceIn(report_period="2024年11月")

        result = _extract_report_date(input_model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_date_invalid_year(self):
        """Test extracting date with invalid year."""
        input_model = TrusteePerformanceIn(年="1999", 月="11")  # Year too old

        result = _extract_report_date(input_model, 0)

        assert result is None

    def test_extract_date_invalid_month(self):
        """Test extracting date with invalid month."""
        input_model = TrusteePerformanceIn(年="2024", 月="13")  # Invalid month

        result = _extract_report_date(input_model, 0)

        assert result is None

    def test_extract_date_missing_data(self):
        """Test extracting date when no date data available."""
        input_model = TrusteePerformanceIn()

        result = _extract_report_date(input_model, 0)

        assert result is None


class TestReportPeriodParsing:
    """Test report period string parsing."""

    @pytest.mark.parametrize(
        "period_string,expected",
        [
            ("2024年11月", (2024, 11)),
            ("2024-11", (2024, 11)),
            ("2024/11", (2024, 11)),
            ("11月2024", (2024, 11)),
            ("202411", (2024, 11)),
            ("2024年11月报告", (2024, 11)),
            ("invalid string", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_report_period_formats(self, period_string, expected):
        """Test parsing various report period string formats."""
        result = _parse_report_period(period_string)
        assert result == expected


class TestFieldExtraction:
    """Test individual field extraction functions."""

    def test_extract_plan_code_chinese(self):
        """Test extracting plan code from Chinese field."""
        input_model = TrusteePerformanceIn(计划代码="PLAN123")

        result = _extract_plan_code(input_model, 0)

        assert result == "PLAN123"

    def test_extract_plan_code_english(self):
        """Test extracting plan code from English field."""
        input_model = TrusteePerformanceIn(plan_code="PLAN456")

        result = _extract_plan_code(input_model, 0)

        assert result == "PLAN456"

    def test_extract_plan_code_missing(self):
        """Test extracting plan code when not available."""
        input_model = TrusteePerformanceIn()

        result = _extract_plan_code(input_model, 0)

        assert result is None

    def test_extract_company_code_chinese(self):
        """Test extracting company code from Chinese field."""
        input_model = TrusteePerformanceIn(公司代码="COMP001")

        result = _extract_company_code(input_model, 0)

        assert result == "COMP001"

    def test_extract_company_code_english(self):
        """Test extracting company code from English field."""
        input_model = TrusteePerformanceIn(company_code="COMP002")

        result = _extract_company_code(input_model, 0)

        assert result == "COMP002"


class TestBatchValidation:
    """Test batch validation utility."""

    def test_validate_input_batch_all_valid(self, valid_row_chinese, valid_row_english):
        """Test batch validation with all valid rows."""
        rows = [valid_row_chinese, valid_row_english]

        valid_rows, errors = validate_input_batch(rows)

        assert len(valid_rows) == 2
        assert len(errors) == 0

    def test_validate_input_batch_mixed(self, valid_row_chinese, invalid_row):
        """Test batch validation with mixed valid/invalid rows."""
        rows = [valid_row_chinese, invalid_row]

        valid_rows, errors = validate_input_batch(rows)

        assert len(valid_rows) == 1
        assert len(errors) == 1
        assert "Row 1:" in errors[0]

    def test_validate_input_batch_all_invalid(self, invalid_row):
        """Test batch validation with all invalid rows."""
        rows = [invalid_row, invalid_row]

        valid_rows, errors = validate_input_batch(rows)

        assert len(valid_rows) == 0
        assert len(errors) == 2


class TestPerformanceMetrics:
    """Test performance metrics extraction and processing."""

    def test_percentage_conversion(self):
        """Test conversion of percentage strings to decimals."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "收益率": "5.5%",  # Percentage format
        }

        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert result.return_rate == Decimal("0.055")  # Converted to decimal

    def test_decimal_cleaning(self):
        """Test cleaning of decimal values with various formatting."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "净值": "¥1,234.56",  # With currency symbol and comma
        }

        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert result.net_asset_value == Decimal("1234.56")

    def test_empty_performance_fields(self):
        """Test handling of empty performance metric fields."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "收益率": "",  # Empty string
            "净值": "N/A",  # Placeholder value
            "规模": "-",  # Dash placeholder
        }

        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert result.return_rate is None
        assert result.net_asset_value is None
        assert result.fund_scale is None
        assert not result.has_performance_data

    def test_numeric_cells_are_accepted_and_converted(self):
        """Numeric Excel cells (float/int) should be accepted and converted to Decimals."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "净值": 1.0512,  # float from Excel cell
            "规模": 12000000,  # int from Excel cell
            "收益率": 0.055,  # float decimal form
        }

        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert result.net_asset_value == Decimal("1.0512")
        assert result.fund_scale == Decimal("12000000")
        assert result.return_rate == Decimal("0.055")

    def test_numeric_cells_are_accepted_and_converted(self):
        """Test that numeric Excel cells work without ValidationError."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "净值": 1.0512,  # Excel float (was causing error)
            "规模": 12000000,  # Excel int (was causing error)
            "收益率": 0.055,  # Excel decimal
        }

        # Should not raise ValidationError
        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert isinstance(result, TrusteePerformanceOut)
        assert result.net_asset_value == Decimal("1.0512")
        assert result.fund_scale == Decimal("12000000")
        assert result.return_rate == Decimal("0.055")

    def test_mixed_numeric_string_inputs(self):
        """Test mixing numeric and string inputs (backward compatibility)."""
        row = {
            "年": "2024",
            "月": "11",
            "计划代码": "PLAN001",
            "公司代码": "COMP001",
            "净值": "1.0512",  # String (existing behavior)
            "规模": 12000000,  # Numeric (new capability)
            "收益率": "5.5%",  # String percentage (existing behavior)
        }

        result = _transform_single_row(row, "test", 0)

        assert result is not None
        assert isinstance(result, TrusteePerformanceOut)
        assert result.net_asset_value == Decimal("1.0512")
        assert result.fund_scale == Decimal("12000000")
        assert result.return_rate == Decimal("0.055")  # 5.5% -> 0.055


class TestDecimalQuantization:
    """Test field-specific decimal quantization in TrusteePerformanceOut."""

    def test_return_rate_quantization_6_places(self):
        """Test return_rate quantization to 6 decimal places."""
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
        from decimal import Decimal

        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

        model = TrusteePerformanceOut(
            report_date="2024-01-01",
            plan_code="P001",
            company_code="C001",
            return_rate=0.123456789,  # Should be 6 places: 0.123457
            net_asset_value=1.123456789,  # Should be 4 places: 1.1235
            fund_scale=100.123456789,  # Should be 2 places: 100.12
            data_source="test",
        )

        assert model.return_rate == Decimal("0.123457")
        assert model.net_asset_value == Decimal("1.1235")
        assert model.fund_scale == Decimal("100.12")

    def test_none_values_preserved(self):
        """Test that None values are preserved through quantization."""
        from src.work_data_hub.domain.sample_trustee_performance.models import TrusteePerformanceOut

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
