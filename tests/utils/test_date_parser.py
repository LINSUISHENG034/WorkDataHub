"""
Tests for unified date parsing utilities.
"""

import pytest
from datetime import date

from src.work_data_hub.utils.date_parser import (
    parse_chinese_date,
    extract_year_month_from_date,
    format_date_as_chinese,
    normalize_date_for_database,
)


class TestParseChineseDate:
    """Test the main date parsing function."""

    def test_none_input(self):
        """Test that None input returns None."""
        assert parse_chinese_date(None) is None

    def test_empty_string_input(self):
        """Test that empty string returns None."""
        assert parse_chinese_date("") is None
        assert parse_chinese_date("   ") is None

    def test_date_object_passthrough(self):
        """Test that date objects are returned as-is."""
        test_date = date(2024, 11, 15)
        assert parse_chinese_date(test_date) == test_date

    def test_integer_format_yyyymm(self):
        """Test integer YYYYMM format parsing."""
        # Valid cases
        assert parse_chinese_date(202411) == date(2024, 11, 1)
        assert parse_chinese_date(202401) == date(2024, 1, 1)
        assert parse_chinese_date(202412) == date(2024, 12, 1)
        assert parse_chinese_date(202307) == date(2023, 7, 1)

        # String representation of integers
        assert parse_chinese_date("202411") == date(2024, 11, 1)

    def test_integer_format_invalid_month(self):
        """Test integer format with invalid month raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date value"):
            parse_chinese_date(202413)  # Month 13
        with pytest.raises(ValueError, match="Invalid date value"):
            parse_chinese_date(202400)  # Month 0

    def test_integer_format_out_of_range(self):
        """Test integers outside valid YYYYMM range return None."""
        assert parse_chinese_date(123) is None  # Too small
        assert parse_chinese_date(1000000) is None  # Too large

    def test_chinese_format_four_digit_year(self):
        """Test Chinese format with 4-digit year."""
        assert parse_chinese_date("2024年11月") == date(2024, 11, 1)
        assert parse_chinese_date("2023年1月") == date(2023, 1, 1)
        assert parse_chinese_date("2024年12月") == date(2024, 12, 1)
        assert parse_chinese_date("2024年11") == date(2024, 11, 1)  # Without 月

    def test_chinese_format_two_digit_year(self):
        """Test Chinese format with 2-digit year (assumes 20xx)."""
        assert parse_chinese_date("24年11月") == date(2024, 11, 1)
        assert parse_chinese_date("23年1月") == date(2023, 1, 1)
        assert parse_chinese_date("25年12月") == date(2025, 12, 1)

    def test_chinese_format_invalid_month(self):
        """Test Chinese format with invalid month raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date value"):
            parse_chinese_date("2024年13月")
        with pytest.raises(ValueError, match="Invalid date value"):
            parse_chinese_date("24年0月")

    def test_standard_date_formats(self):
        """Test standard date formats with various separators."""
        # YYYY-MM-DD format
        assert parse_chinese_date("2024-11-15") == date(2024, 11, 15)
        assert parse_chinese_date("2023-01-05") == date(2023, 1, 5)

        # YYYY/MM/DD format
        assert parse_chinese_date("2024/11/15") == date(2024, 11, 15)
        assert parse_chinese_date("2023/01/05") == date(2023, 1, 5)

        # YYYY.MM.DD format
        assert parse_chinese_date("2024.11.15") == date(2024, 11, 15)

        # YY-MM-DD format (assumes 20xx)
        assert parse_chinese_date("24-11-15") == date(2024, 11, 15)

    def test_year_month_format(self):
        """Test YYYY-MM format (assumes day 1)."""
        assert parse_chinese_date("2024-11") == date(2024, 11, 1)
        assert parse_chinese_date("2023/07") == date(2023, 7, 1)
        assert parse_chinese_date("24.12") == date(2024, 12, 1)

    def test_unrecognized_format(self):
        """Test unrecognized formats return None."""
        assert parse_chinese_date("not a date") is None
        assert parse_chinese_date("2024年") is None  # Missing month
        assert parse_chinese_date("11月") is None  # Missing year
        assert parse_chinese_date("2024-11-15-extra") is None

    def test_invalid_date_values(self):
        """Test invalid date values that don't match patterns return None."""
        # These don't match recognized patterns, so they return None
        assert parse_chinese_date("2024-02-30") is None  # Invalid day (pattern doesn't validate)
        assert parse_chinese_date("2024/13/01") is None  # Invalid month (pattern doesn't validate)


class TestExtractYearMonth:
    """Test year/month extraction function."""

    def test_successful_extraction(self):
        """Test successful year/month extraction."""
        assert extract_year_month_from_date(202411) == (2024, 11)
        assert extract_year_month_from_date("2024年11月") == (2024, 11)
        assert extract_year_month_from_date("24年1月") == (2024, 1)
        assert extract_year_month_from_date(date(2024, 11, 15)) == (2024, 11)

    def test_failed_extraction(self):
        """Test failed extraction returns (None, None)."""
        assert extract_year_month_from_date(None) == (None, None)
        assert extract_year_month_from_date("invalid") == (None, None)
        assert extract_year_month_from_date("") == (None, None)


class TestFormatDateAsChinese:
    """Test Chinese date formatting function."""

    def test_format_various_dates(self):
        """Test formatting various dates."""
        assert format_date_as_chinese(date(2024, 11, 1)) == "2024年11月"
        assert format_date_as_chinese(date(2023, 1, 15)) == "2023年1月"
        assert format_date_as_chinese(date(2025, 12, 31)) == "2025年12月"


class TestNormalizeDateForDatabase:
    """Test database date normalization function."""

    def test_successful_normalization(self):
        """Test successful normalization to ISO format."""
        assert normalize_date_for_database(202411) == "2024-11-01"
        assert normalize_date_for_database("2024年11月") == "2024-11-01"
        assert normalize_date_for_database("24年1月") == "2024-01-01"
        assert normalize_date_for_database(date(2024, 11, 15)) == "2024-11-15"
        assert normalize_date_for_database("2024-11-15") == "2024-11-15"

    def test_failed_normalization(self):
        """Test failed normalization returns None."""
        assert normalize_date_for_database(None) is None
        assert normalize_date_for_database("invalid") is None
        assert normalize_date_for_database("") is None


# Integration tests with real-world scenarios
class TestRealWorldScenarios:
    """Test real-world date parsing scenarios."""

    def test_excel_integer_dates(self):
        """Test parsing Excel integer dates like those found in actual files."""
        # These are actual formats found in the 规模明细 Excel files
        test_cases = [
            (202411, date(2024, 11, 1)),
            (202410, date(2024, 10, 1)),
            (202401, date(2024, 1, 1)),
            (202312, date(2023, 12, 1)),
        ]

        for input_val, expected in test_cases:
            assert parse_chinese_date(input_val) == expected

    def test_mixed_format_batch(self):
        """Test parsing a batch of mixed format dates."""
        test_data = [
            202411,  # Excel integer
            "2024年11月",  # Chinese format
            "24年11月",  # 2-digit year Chinese
            "2024-11-01",  # ISO format
            date(2024, 11, 1),  # Already a date
            None,  # None value
        ]

        expected = date(2024, 11, 1)

        for value in test_data:
            if value is not None:
                result = parse_chinese_date(value)
                assert result == expected or result.replace(day=1) == expected
            else:
                assert parse_chinese_date(value) is None
