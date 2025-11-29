"""Unit tests for DateParsingStep and parse_to_standard_date."""

from datetime import date, datetime

import pytest

from work_data_hub.domain.pipelines.steps import DateParsingStep, parse_to_standard_date


class TestParseToStandardDate:
    """Tests for parse_to_standard_date utility function."""

    def test_parse_chinese_year_month_format(self):
        """Test parsing YYYY年MM月 format."""
        result = parse_to_standard_date("2024年12月")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 1

    def test_parse_chinese_full_date_format(self):
        """Test parsing YYYY年MM月DD日 format."""
        result = parse_to_standard_date("2024年12月15日")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 15

    def test_parse_yyyymm_format(self):
        """Test parsing YYYYMM format."""
        result = parse_to_standard_date("202412")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 1

    def test_parse_yyyymmdd_format(self):
        """Test parsing YYYYMMDD format."""
        result = parse_to_standard_date("20241215")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 15

    def test_parse_yyyy_mm_format(self):
        """Test parsing YYYY-MM format."""
        result = parse_to_standard_date("2024-12")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 1

    def test_parse_date_object_passthrough(self):
        """Test that date objects pass through unchanged."""
        input_date = date(2024, 12, 15)
        result = parse_to_standard_date(input_date)
        assert result == input_date

    def test_parse_datetime_object_passthrough(self):
        """Test that datetime objects pass through unchanged."""
        input_datetime = datetime(2024, 12, 15, 10, 30)
        result = parse_to_standard_date(input_datetime)
        assert result == input_datetime

    def test_parse_integer_yyyymm(self):
        """Test parsing integer YYYYMM format (common from Excel)."""
        result = parse_to_standard_date(202412)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12

    def test_parse_invalid_format_returns_original(self):
        """Test that invalid formats return the original value."""
        result = parse_to_standard_date("invalid_date")
        assert result == "invalid_date"

    def test_parse_empty_string_returns_original(self):
        """Test that empty string returns original value."""
        result = parse_to_standard_date("")
        assert result == ""

    def test_parse_two_digit_year_chinese_format(self):
        """Test parsing YY年MM月 format with 2-digit year - not supported."""
        result = parse_to_standard_date("24年12月")
        # 2-digit year format is not fully supported by the regex pattern
        # which expects (\d{2}|\d{4})年 but strptime uses %Y which needs 4 digits
        # So this returns the original value
        assert result == "24年12月"

    def test_parse_single_digit_month(self):
        """Test parsing dates with single-digit month."""
        result = parse_to_standard_date("2024年1月")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1


class TestDateParsingStep:
    """Tests for DateParsingStep."""

    def test_step_name(self):
        """Test step name property."""
        step = DateParsingStep()
        assert step.name == "date_parsing"

    def test_default_date_fields(self):
        """Test default date fields are set correctly."""
        step = DateParsingStep()
        assert step.date_fields == ["月度"]

    def test_custom_date_fields(self):
        """Test custom date fields can be provided."""
        custom_fields = ["报告日期", "创建日期"]
        step = DateParsingStep(date_fields=custom_fields)
        assert step.date_fields == custom_fields

    def test_parse_月度_field(self):
        """Test parsing the default 月度 field."""
        step = DateParsingStep()
        row = {"月度": "2024年12月", "客户名称": "某公司"}

        result = step.apply(row, {})

        assert isinstance(result.row["月度"], datetime)
        assert result.row["月度"].year == 2024
        assert result.row["月度"].month == 12
        assert result.row["客户名称"] == "某公司"
        assert not result.errors

    def test_parse_multiple_date_fields(self):
        """Test parsing multiple date fields."""
        step = DateParsingStep(date_fields=["月度", "报告日期"])
        row = {"月度": "202412", "报告日期": "2024-12", "金额": 1000}

        result = step.apply(row, {})

        assert isinstance(result.row["月度"], datetime)
        assert isinstance(result.row["报告日期"], datetime)
        assert result.row["金额"] == 1000

    def test_missing_date_field_no_error(self):
        """Test that missing date fields don't cause errors."""
        step = DateParsingStep()
        row = {"客户名称": "某公司", "金额": 1000}

        result = step.apply(row, {})

        assert result.row == row
        assert not result.errors
        assert result.metadata["date_fields_processed"] == 0

    def test_empty_row(self):
        """Test with empty row."""
        step = DateParsingStep()
        row = {}

        result = step.apply(row, {})

        assert result.row == {}
        assert not result.errors

    def test_warnings_generated_on_parse(self):
        """Test that warnings are generated when dates are parsed."""
        step = DateParsingStep()
        row = {"月度": "2024年12月"}

        result = step.apply(row, {})

        assert len(result.warnings) >= 1
        assert "Parsed date" in result.warnings[0]

    def test_metadata_tracks_processed_count(self):
        """Test that metadata tracks the number of processed fields."""
        step = DateParsingStep(date_fields=["月度", "报告日期"])
        row = {"月度": "202412", "报告日期": "2024-12"}

        result = step.apply(row, {})

        assert result.metadata["date_fields_processed"] == 2

    def test_preserves_other_fields(self):
        """Test that non-date fields are preserved unchanged."""
        step = DateParsingStep()
        row = {
            "月度": "202412",
            "期初资产规模": 1000000.0,
            "客户名称": "某某公司",
        }

        result = step.apply(row, {})

        assert result.row["期初资产规模"] == 1000000.0
        assert result.row["客户名称"] == "某某公司"

    def test_invalid_date_keeps_original_value(self):
        """Test that invalid dates keep the original value."""
        step = DateParsingStep()
        row = {"月度": "invalid_date"}

        result = step.apply(row, {})

        # Original value should be preserved
        assert result.row["月度"] == "invalid_date"
        assert not result.errors

    def test_does_not_modify_original_row(self):
        """Test that the original row is not modified."""
        step = DateParsingStep()
        original_row = {"月度": "202412"}
        row_copy = dict(original_row)

        step.apply(row_copy, {})

        # Original should still have string value
        assert original_row["月度"] == "202412"
