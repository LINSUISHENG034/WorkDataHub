"""Unit tests for string cleansing rules (Story 5.6.2).

.. note:: Updated 2026-01-05 to reflect unified normalize_customer_name behavior:
    - Output is now UPPERCASE
    - Only brackets containing status markers are removed (not all trailing brackets)
"""

import pytest

from work_data_hub.infrastructure.cleansing.rules.string_rules import (
    normalize_company_name,
    trim_whitespace,
)


class TestTrimWhitespace:
    """Tests for trim_whitespace rule."""

    def test_none_returns_none(self) -> None:
        assert trim_whitespace(None) is None

    def test_non_string_returns_unchanged(self) -> None:
        assert trim_whitespace(123) == 123
        assert trim_whitespace(12.5) == 12.5

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert trim_whitespace("  hello  ") == "hello"

    def test_converts_fullwidth_space_to_halfwidth(self) -> None:
        assert trim_whitespace("\u3000hello\u3000") == "hello"


class TestNormalizeCompanyName:
    """Tests for normalize_company_name rule.

    Note: As of 2026-01-05, this function delegates to normalize_customer_name
    which outputs UPPERCASE and has different bracket handling.
    """

    def test_none_returns_none(self) -> None:
        assert normalize_company_name(None) is None

    def test_non_string_returns_unchanged(self) -> None:
        assert normalize_company_name(123) == 123

    def test_removes_decorative_chars(self) -> None:
        result = normalize_company_name("「测试公司」")
        assert "「" not in result
        assert "」" not in result

    def test_preserves_angle_brackets(self) -> None:
        """Verify 《》 are preserved as valid characters in company names."""
        result = normalize_company_name("《国家大剧院》有限公司")
        assert result == "《国家大剧院》有限公司"

    def test_converts_halfwidth_brackets_to_fullwidth(self) -> None:
        result = normalize_company_name("中国(北京)科技公司")
        assert "(" not in result
        assert ")" not in result
        assert "（" in result
        assert "）" in result


class TestNormalizeCompanyNameBracketFix:
    """Story 5.6.2: Tests for bracket cleanup at start/end of company names.

    Note: As of 2026-01-05, only brackets containing status markers are removed.
    Regular brackets like (集团) at the end are now PRESERVED unless they contain
    status markers.
    """

    def test_leading_bracket_with_status_removed(self) -> None:
        """Leading brackets with status markers are removed."""
        result = normalize_company_name("(原)中国机械公司")
        assert result == "中国机械公司"

    def test_trailing_status_bracket_removed(self) -> None:
        """Trailing brackets with status markers are removed."""
        result = normalize_company_name("中国机械公司(已转出)")
        assert result == "中国机械公司"

    def test_trailing_group_bracket_preserved(self) -> None:
        """Trailing (集团) is now PRESERVED (not a status marker)."""
        result = normalize_company_name("中国机械公司(集团)")
        # As of 2026-01-05: 集团 is NOT a status marker, so it's preserved
        assert result == "中国机械公司（集团）"

    def test_middle_bracket_preserved(self) -> None:
        """Brackets in middle of company name are preserved unchanged."""
        result = normalize_company_name("中国（北京）科技公司")
        assert result == "中国（北京）科技公司"

    def test_no_brackets_unchanged(self) -> None:
        """No brackets, company name unchanged."""
        result = normalize_company_name("华为技术有限公司")
        assert result == "华为技术有限公司"

    def test_empty_brackets_leading(self) -> None:
        """Empty brackets at start should be removed."""
        result = normalize_company_name("()中国公司")
        assert result == "中国公司"

    def test_empty_brackets_trailing(self) -> None:
        """Empty brackets at end should be removed."""
        result = normalize_company_name("中国公司()")
        assert result == "中国公司"

    def test_trailing_obsolete_marker_removed(self) -> None:
        """Status marker （作废） is removed."""
        result = normalize_company_name("浙江温州鹿城农村商业银行股份有限公司（作废）")
        assert result == "浙江温州鹿城农村商业银行股份有限公司"

    def test_status_with_dash_removed(self) -> None:
        """Status marker with dash removed."""
        result = normalize_company_name("中国平安-已转出")
        assert result == "中国平安"
