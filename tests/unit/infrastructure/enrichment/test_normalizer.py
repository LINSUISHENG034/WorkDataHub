"""
Unit tests for legacy-compatible name normalization (AC 5.4.7).

Tests cover:
- Whitespace handling
- Status marker removal
- Bracket conversion
- Full-width to half-width conversion
- Normalization parity with legacy
- Temp ID consistency across name variants
"""

import pytest

from work_data_hub.infrastructure.enrichment import (
    normalize_for_temp_id,
    generate_temp_company_id,
)
from tests.fixtures.legacy_normalized_names import LEGACY_TEST_CASES


class TestNormalizeForTempId:
    """Tests for normalize_for_temp_id function."""

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert normalize_for_temp_id("") == ""

    def test_none_like_input(self):
        """Test None-like input returns empty."""
        assert normalize_for_temp_id(None) == ""

    def test_whitespace_removal(self):
        """Test all whitespace is removed."""
        assert normalize_for_temp_id("中国 平安") == "中国平安"
        assert normalize_for_temp_id("中国平安 ") == "中国平安"
        assert normalize_for_temp_id(" 中国平安") == "中国平安"
        assert normalize_for_temp_id("  中国  平安  ") == "中国平安"
        assert normalize_for_temp_id("中国\t平安") == "中国平安"
        assert normalize_for_temp_id("中国\n平安") == "中国平安"

    def test_status_marker_removal_at_end(self):
        """Test status markers are removed from end."""
        assert normalize_for_temp_id("中国平安-已转出") == "中国平安"
        assert normalize_for_temp_id("中国平安-待转出") == "中国平安"
        assert normalize_for_temp_id("中国平安（已转出）") == "中国平安"
        assert normalize_for_temp_id("中国平安(终止)") == "中国平安"
        assert normalize_for_temp_id("中国平安-清算") == "中国平安"

    def test_status_marker_removal_at_start(self):
        """Test status markers are removed from start."""
        assert normalize_for_temp_id("已转出-中国平安") == "中国平安"
        assert normalize_for_temp_id("（已转出）中国平安") == "中国平安"

    def test_business_pattern_removal(self):
        """Test business-specific patterns are removed."""
        assert normalize_for_temp_id("中国平安及下属子企业") == "中国平安"
        assert normalize_for_temp_id("中国平安-养老") == "中国平安"
        assert normalize_for_temp_id("中国平安-福利") == "中国平安"
        assert normalize_for_temp_id("中国平安(团托)") == "中国平安"

    def test_bracket_normalization(self):
        """Test brackets are normalized to Chinese."""
        # English brackets should become Chinese
        result = normalize_for_temp_id("中国平安(集团)")
        assert "（" in result
        assert "）" in result
        assert "(" not in result
        assert ")" not in result

    def test_fullwidth_to_halfwidth(self):
        """Test full-width characters are converted to half-width."""
        # Full-width A (Ａ) should become half-width a
        result = normalize_for_temp_id("中国平安Ａ")
        assert "Ａ" not in result
        assert "a" in result  # lowercase after conversion

    def test_lowercase_conversion(self):
        """Test result is lowercased."""
        result = normalize_for_temp_id("ABC公司")
        assert result == "abc公司"

    def test_trailing_punctuation_removal(self):
        """Test trailing punctuation is removed."""
        assert normalize_for_temp_id("中国平安-") == "中国平安"
        assert normalize_for_temp_id("中国平安--") == "中国平安"
        assert normalize_for_temp_id("中国平安（）") == "中国平安"


class TestNormalizationConsistency:
    """Tests for normalization producing consistent results."""

    def test_whitespace_variants_same_result(self):
        """Test whitespace variants produce same normalized result."""
        variants = [
            "中国平安",
            "中国平安 ",
            " 中国平安",
            "中国 平安",
            "  中国平安  ",
        ]

        normalized = [normalize_for_temp_id(v) for v in variants]
        assert len(set(normalized)) == 1, (
            "All whitespace variants should normalize same"
        )

    def test_status_marker_variants_same_result(self):
        """Test status marker variants produce same normalized result."""
        base = normalize_for_temp_id("中国平安")
        with_status = normalize_for_temp_id("中国平安-已转出")

        assert base == with_status

    def test_bracket_variants_same_result(self):
        """Test bracket variants produce same normalized result."""
        chinese_brackets = normalize_for_temp_id("中国平安（集团）")
        english_brackets = normalize_for_temp_id("中国平安(集团)")

        assert chinese_brackets == english_brackets


class TestGenerateTempCompanyId:
    """Tests for generate_temp_company_id function."""

    def test_format(self):
        """Test temp ID format is IN<16-char-Base32> (no underscore)."""
        temp_id = generate_temp_company_id("中国平安", "test_salt")

        assert temp_id.startswith("IN")
        assert len(temp_id) == 18  # "IN" + 16 chars

    def test_consistency(self):
        """Test same input produces same output."""
        id1 = generate_temp_company_id("中国平安", "test_salt")
        id2 = generate_temp_company_id("中国平安", "test_salt")

        assert id1 == id2

    def test_different_names_different_ids(self):
        """Test different names produce different IDs."""
        id1 = generate_temp_company_id("公司A", "test_salt")
        id2 = generate_temp_company_id("公司B", "test_salt")

        assert id1 != id2

    def test_different_salts_different_ids(self):
        """Test different salts produce different IDs."""
        id1 = generate_temp_company_id("中国平安", "salt1")
        id2 = generate_temp_company_id("中国平安", "salt2")

        assert id1 != id2

    def test_empty_name_handled(self):
        """Test empty name produces valid ID."""
        temp_id = generate_temp_company_id("", "test_salt")

        assert temp_id.startswith("IN")
        assert len(temp_id) == 18

    def test_whitespace_variants_same_id(self):
        """Test whitespace variants produce same temp ID."""
        id1 = generate_temp_company_id("中国平安", "test_salt")
        id2 = generate_temp_company_id("中国平安 ", "test_salt")
        id3 = generate_temp_company_id(" 中国平安", "test_salt")

        assert id1 == id2 == id3

    def test_status_marker_variants_same_id(self):
        """Test status marker variants produce same temp ID."""
        id_clean = generate_temp_company_id("中国平安", "test_salt")
        id_with_status = generate_temp_company_id("中国平安-已转出", "test_salt")

        assert id_clean == id_with_status

    def test_bracket_variants_same_id(self):
        """Test bracket variants produce same temp ID."""
        id_chinese = generate_temp_company_id("中国平安（集团）", "test_salt")
        id_english = generate_temp_company_id("中国平安(集团)", "test_salt")

        assert id_chinese == id_english


class TestAllStatusMarkers:
    """Tests for all 29 status markers."""

    @pytest.mark.parametrize(
        "marker",
        [
            "已转出",
            "待转出",
            "终止",
            "转出",
            "保留",
            "暂停",
            "注销",
            "清算",
            "解散",
            "吊销",
            "撤销",
            "停业",
            "歇业",
            "关闭",
            "迁出",
            "迁入",
            "变更",
            "合并",
            "分立",
            "破产",
            "重整",
            "托管",
            "接管",
            "整顿",
            "清盘",
            "退出",
            "终结",
            "结束",
            "完结",
        ],
    )
    def test_status_marker_removed(self, marker):
        """Test each status marker is properly removed."""
        base = "中国平安"
        with_marker = f"{base}-{marker}"

        normalized_base = normalize_for_temp_id(base)
        normalized_with_marker = normalize_for_temp_id(with_marker)

        assert normalized_base == normalized_with_marker, (
            f"Status marker '{marker}' should be removed"
        )


class TestLegacyParity:
    """Tests for parity with legacy clean_company_name behavior."""

    @pytest.mark.parametrize("original,expected_normalized", LEGACY_TEST_CASES)
    def test_normalization_parity(self, original, expected_normalized):
        """Test normalization matches expected legacy behavior."""
        result = normalize_for_temp_id(original)
        # Note: We add .lower() which legacy doesn't have
        assert result == expected_normalized.lower()
