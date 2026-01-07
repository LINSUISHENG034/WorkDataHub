"""Unit tests for unified customer name normalization (normalize_customer_name).

Tests cover:
- Whitespace handling (complete removal)
- Status marker removal (33 patterns)
- Bracket normalization
- Full-width to half-width conversion
- UPPERCASE conversion
- Invalid placeholder handling
- Business pattern removal
- CSV fixture-based regression tests
"""

import csv
from pathlib import Path

import pytest

from work_data_hub.infrastructure.cleansing.normalizers import (
    normalize_customer_name,
    STATUS_MARKERS,
    INVALID_PLACEHOLDERS,
    ENTERPRISE_TYPES,
)


# =============================================================================
# CSV Fixture Loading for Regression Tests
# =============================================================================
# Path: tests/unit/infrastructure/cleansing/normalizers → tests/fixtures
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "company_name"
)
ABNORMAL_SAMPLES_CSV = FIXTURES_DIR / "company_name_abnormal_samples.csv"


def load_abnormal_samples() -> list[tuple[str, str, str, str]]:
    """Load abnormal company name samples from CSV fixture.

    Returns:
        List of (raw_name, issue_category, description, expected_result) tuples.
    """
    samples = []
    if not ABNORMAL_SAMPLES_CSV.exists():
        return samples

    with ABNORMAL_SAMPLES_CSV.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row.get("raw_name", "")
            issue_category = row.get("issue_category", "")
            description = row.get("description", "")
            expected = row.get("referenced_result", "")
            if raw_name:  # Skip empty rows
                samples.append((raw_name, issue_category, description, expected))
    return samples


ABNORMAL_SAMPLES = load_abnormal_samples()


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
        assert normalize_customer_name("abc（集团）公司") == "ABC（集团）公司"
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
        # Use enterprise type content that should be preserved
        # Note: （集团） is now intentionally removed by suffix cleaning
        result = normalize_customer_name("中国平安(普通合伙)")
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


class TestTrailingSuffixCleaning:
    """Tests for trailing parenthesized suffix cleaning (2026-01-07).

    Verifies that:
    - Enterprise types (普通合伙, 有限合伙, etc.) are preserved
    - Group indicators (集团) are removed
    - Status/redundant info in parentheses is removed
    - Aliases (long names in parentheses) are removed
    """

    def test_group_indicator_removed(self) -> None:
        """Test （集团） suffix is removed."""
        assert (
            normalize_customer_name("重庆机场集团有限公司(集团)")
            == "重庆机场集团有限公司"
        )
        assert normalize_customer_name("测试公司（集团）") == "测试公司"

    def test_status_in_parentheses_removed(self) -> None:
        """Test status info in parentheses is removed."""
        result = normalize_customer_name("深圳市燃气集团股份有限公司（原单一，已转出）")
        assert result == "深圳市燃气集团股份有限公司"

    def test_alias_removed(self) -> None:
        """Test long alias in parentheses is removed."""
        result = normalize_customer_name(
            "广州市职业技能鉴定指导中心（广州市高技能人才公共实训管理服务中心）"
        )
        assert result == "广州市职业技能鉴定指导中心"

    def test_enterprise_type_preserved(self) -> None:
        """Test enterprise types are preserved."""
        # 普通合伙 should be preserved
        result = normalize_customer_name("沈阳市铁西区鑫奇天然食品经销处（普通合伙）")
        assert "普通合伙" in result

    @pytest.mark.parametrize("etype", ENTERPRISE_TYPES)
    def test_all_enterprise_types_preserved(self, etype: str) -> None:
        """Test all enterprise types are preserved."""
        name = f"测试公司（{etype}）"
        result = normalize_customer_name(name)
        assert etype in result

    def test_short_content_preserved(self) -> None:
        """Test short parenthesis content (<=4 chars) is preserved."""
        # Short content that's not a status marker should be preserved
        result = normalize_customer_name("北京公司（北京）")
        assert "北京" in result

    def test_english_brackets_also_handled(self) -> None:
        """Test English brackets are handled the same way."""
        assert normalize_customer_name("公司(集团)") == "公司"
        result = normalize_customer_name("公司(普通合伙)")
        assert "普通合伙" in result


class TestAbnormalSamplesFromCSV:
    """Regression tests using CSV fixture with abnormal company name samples.

    Tests load from: tests/fixtures/company_name/company_name_abnormal_samples.csv

    Each sample includes:
    - raw_name: Original problematic company name
    - issue_category: Type of issue (Status Tag, Invisible/Punctuation, etc.)
    - description: Description of the problem
    - referenced_result: Expected normalized result
    """

    @pytest.mark.skipif(
        not ABNORMAL_SAMPLES,
        reason="CSV fixture file not found or empty",
    )
    @pytest.mark.parametrize(
        "raw_name,issue_category,description,expected",
        ABNORMAL_SAMPLES,
        ids=[f"{s[1]}:{s[0][:20]}..." for s in ABNORMAL_SAMPLES]
        if ABNORMAL_SAMPLES
        else [],
    )
    def test_abnormal_sample_normalization(
        self,
        raw_name: str,
        issue_category: str,
        description: str,
        expected: str,
    ) -> None:
        """Test that abnormal samples are normalized correctly.

        Args:
            raw_name: Original company name with issues.
            issue_category: Category of the issue.
            description: Description of the issue.
            expected: Expected normalized result.
        """
        result = normalize_customer_name(raw_name)
        # Note: normalize_customer_name returns UPPERCASE result
        assert result == expected.upper(), (
            f"Category: {issue_category}\n"
            f"Description: {description}\n"
            f"Input: {raw_name}\n"
            f"Expected: {expected.upper()}\n"
            f"Got: {result}"
        )

    @pytest.mark.skipif(
        not ABNORMAL_SAMPLES,
        reason="CSV fixture file not found or empty",
    )
    def test_csv_fixture_loaded(self) -> None:
        """Verify CSV fixture was loaded successfully."""
        assert len(ABNORMAL_SAMPLES) > 0, "CSV fixture should have samples"
        assert ABNORMAL_SAMPLES_CSV.exists(), "CSV fixture file should exist"
