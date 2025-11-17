"""Unit tests for built-in cleansing rules (Story 2.3)."""

import pytest

from src.work_data_hub.cleansing.rules.numeric_rules import (
    clean_comma_separated_number,
    remove_currency_symbols,
)
from src.work_data_hub.cleansing.rules.string_rules import (
    normalize_company_name,
    trim_whitespace,
)


@pytest.mark.unit
class TestStringRules:
    def test_trim_whitespace_handles_full_width_space(self):
        assert trim_whitespace("  公司　有限  ") == "公司 有限"
        assert trim_whitespace(None) is None
        assert trim_whitespace(123) == 123

    def test_normalize_company_name_collapses_spaces(self):
        assert normalize_company_name("「公司　有限」") == "公司 有限"
        assert normalize_company_name("『测试』") == "测试"


@pytest.mark.unit
class TestNumericRules:
    def test_remove_currency_symbols(self):
        assert remove_currency_symbols("¥1,200") == "1,200"
        assert remove_currency_symbols(None) is None
        assert remove_currency_symbols(1000) == 1000

    def test_clean_comma_separated_number(self):
        assert clean_comma_separated_number("1,234,567.89") == "1234567.89"
        assert clean_comma_separated_number("  N/A  ") is None
        assert clean_comma_separated_number(1000) == 1000
