"""Unit tests for unified customer name normalization (normalize_customer_name).

Tests cover:
- Whitespace handling (complete removal)
- Status marker removal (33 patterns)
- Bracket normalization
- Full-width to half-width conversion
- UPPERCASE conversion
- Invalid placeholder handling
- Business pattern removal
"""

import pytest

from work_data_hub.infrastructure.cleansing.normalizers import (
    normalize_customer_name,
    STATUS_MARKERS,
    INVALID_PLACEHOLDERS,
)


class TestBasicNormalization:
    """Tests for basic normalization operations."""

    def test_empty_string_returns_empty(self) -> None:
        assert normalize_customer_name("") == ""

    def test_none_returns_empty(self) -> None:
        assert normalize_customer_name(None) == ""

    def test_non_string_returns_empty(self) -> None:
        assert normalize_customer_name(123) == ""  # type: ignore

    def test_simple_name_unchanged_except_case(self) -> None:
        assert normalize_customer_name("中国平安") == "中国平安"

    def test_uppercase_conversion(self) -> None:
        """Test UPPERCASE conversion is applied."""
        assert normalize_customer_name("abc公司") == "ABC公司"
        assert normalize_customer_name("China Life") == "CHINALIFE"


class TestWhitespaceHandling:
    """Tests for whitespace removal."""

    def test_leading_whitespace_removed(self) -> None:
        assert normalize_customer_name("  中国平安") == "中国平安"

    def test_trailing_whitespace_removed(self) -> None:
        assert normalize_customer_name("中国平安  ") == "中国平安"

    def test_middle_whitespace_removed(self) -> None:
        assert normalize_customer_name("中国 平安") == "中国平安"

    def test_multiple_whitespace_removed(self) -> None:
        assert normalize_customer_name("  ABC  公司  ") == "ABC公司"

    def test_tab_and_newline_removed(self) -> None:
        assert normalize_customer_name("中国\t平安\n公司") == "中国平安公司"

    def test_fullwidth_space_removed(self) -> None:
        assert normalize_customer_name("中国\u3000平安") == "中国平安"


class TestStatusMarkerRemoval:
    """Tests for status marker removal."""

    def test_status_at_end_with_dash(self) -> None:
        assert normalize_customer_name("中国平安-已转出") == "中国平安"

    def test_status_at_end_in_brackets(self) -> None:
        assert normalize_customer_name("中国平安（已转出）") == "中国平安"

    def test_status_at_end_in_english_brackets(self) -> None:
        assert normalize_customer_name("中国平安(终止)") == "中国平安"

    def test_status_at_start_with_dash(self) -> None:
        assert normalize_customer_name("已转出-中国平安") == "中国平安"

    def test_status_at_start_in_brackets(self) -> None:
        assert normalize_customer_name("（已转出）中国平安") == "中国平安"

    @pytest.mark.parametrize("marker", STATUS_MARKERS[:10])  # Test first 10
    def test_common_status_markers_removed(self, marker: str) -> None:
        """Test common status markers are removed."""
        base = "中国平安"
        with_marker = f"{base}-{marker}"
        assert normalize_customer_name(with_marker) == base


class TestBracketNormalization:
    """Tests for bracket handling."""

    def test_english_brackets_normalized_to_chinese(self) -> None:
        result = normalize_customer_name("中国平安(集团)")
        assert "(" not in result
        assert ")" not in result
        assert "（" in result
        assert "）" in result

    def test_middle_brackets_preserved(self) -> None:
        """Brackets in middle should be preserved."""
        assert normalize_customer_name("中国（北京）科技") == "中国（北京）科技"

    def test_trailing_empty_brackets_removed(self) -> None:
        assert normalize_customer_name("中国平安（）") == "中国平安"


class TestBusinessPatternRemoval:
    """Tests for business-specific pattern removal."""

    def test_subsidiary_pattern_removed(self) -> None:
        assert normalize_customer_name("中国平安及下属子企业") == "中国平安"

    def test_pension_suffix_removed(self) -> None:
        assert normalize_customer_name("中国平安-养老") == "中国平安"

    def test_welfare_suffix_removed(self) -> None:
        assert normalize_customer_name("中国平安-福利") == "中国平安"

    def test_tuantuo_removed(self) -> None:
        assert normalize_customer_name("中国平安(团托)") == "中国平安"


class TestInvalidPlaceholders:
    """Tests for invalid placeholder handling."""

    @pytest.mark.parametrize("placeholder", INVALID_PLACEHOLDERS)
    def test_invalid_placeholders_return_empty(self, placeholder: str) -> None:
        """Test all invalid placeholders return empty string."""
        assert normalize_customer_name(placeholder) == ""

    def test_null_string_returns_empty(self) -> None:
        assert normalize_customer_name("null") == ""

    def test_na_returns_empty(self) -> None:
        assert normalize_customer_name("N/A") == ""


class TestFullWidthConversion:
    """Tests for full-width to half-width conversion."""

    def test_fullwidth_ascii_converted(self) -> None:
        """Full-width ASCII should become half-width."""
        result = normalize_customer_name("中国平安Ａ")
        assert "Ａ" not in result
        assert "A" in result

    def test_fullwidth_digits_converted(self) -> None:
        """Full-width digits should become half-width."""
        result = normalize_customer_name("第１公司")
        assert "１" not in result
        assert "1" in result


class TestDecorativeCharRemoval:
    """Tests for decorative character removal."""

    def test_corner_brackets_removed(self) -> None:
        result = normalize_customer_name("「测试公司」")
        assert "「" not in result
        assert "」" not in result

    def test_double_corner_brackets_removed(self) -> None:
        result = normalize_customer_name("『测试公司』")
        assert "『" not in result
        assert "』" not in result


class TestConsistency:
    """Tests for normalization consistency across variants."""

    def test_whitespace_variants_same_result(self) -> None:
        """All whitespace variants should produce same result."""
        variants = [
            "中国平安",
            "中国平安 ",
            " 中国平安",
            "中国 平安",
            "  中国平安  ",
        ]
        normalized = [normalize_customer_name(v) for v in variants]
        assert len(set(normalized)) == 1

    def test_status_marker_variants_same_result(self) -> None:
        """Status marker variants should produce same result."""
        base = normalize_customer_name("中国平安")
        with_status = normalize_customer_name("中国平安-已转出")
        assert base == with_status

    def test_bracket_variants_same_result(self) -> None:
        """Different bracket types should produce same result."""
        chinese = normalize_customer_name("中国平安（集团）")
        english = normalize_customer_name("中国平安(集团)")
        assert chinese == english
