"""
Unit tests for EQC Confidence Configuration (Story 7.1-8).

Tests cover configuration loading, validation, and confidence lookup logic.
"""

import pytest
import yaml
from pathlib import Path

from work_data_hub.infrastructure.enrichment.eqc_confidence_config import (
    EQCConfidenceConfig,
)


class TestEQCConfidenceConfigLoading:
    """Test configuration loading from YAML files."""

    def test_load_config_from_yaml(self, tmp_path):
        """Test loading configuration from YAML file."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: 1.00
  模糊匹配: 0.80
  拼音: 0.60
  default: 0.70

min_confidence_for_cache: 0.60
""",
            encoding="utf-8",
        )

        config = EQCConfidenceConfig.load_from_yaml(str(config_yaml))

        assert config.eqc_match_confidence["全称精确匹配"] == 1.00
        assert config.eqc_match_confidence["模糊匹配"] == 0.80
        assert config.eqc_match_confidence["拼音"] == 0.60
        assert config.min_confidence_for_cache == 0.60

    def test_load_config_missing_file_returns_default(self, tmp_path):
        """Test that missing config file returns default configuration."""
        nonexistent = tmp_path / "nonexistent.yml"
        config = EQCConfidenceConfig.load_from_yaml(str(nonexistent))

        assert config.eqc_match_confidence["全称精确匹配"] == 1.00
        assert config.eqc_match_confidence["模糊匹配"] == 0.80
        assert config.eqc_match_confidence["拼音"] == 0.60
        assert config.min_confidence_for_cache == 0.60


class TestConfidenceLookup:
    """Test confidence lookup for different match types."""

    def test_get_confidence_exact_match(self):
        """Test confidence returns 1.00 for 全称精确匹配."""
        config = EQCConfidenceConfig.get_default_config()
        assert config.get_confidence_for_match_type("全称精确匹配") == 1.00

    def test_get_confidence_fuzzy_match(self):
        """Test confidence returns 0.80 for 模糊匹配."""
        config = EQCConfidenceConfig.get_default_config()
        assert config.get_confidence_for_match_type("模糊匹配") == 0.80

    def test_get_confidence_pinyin(self):
        """Test confidence returns 0.60 for 拼音."""
        config = EQCConfidenceConfig.get_default_config()
        assert config.get_confidence_for_match_type("拼音") == 0.60

    def test_get_confidence_unknown_type_returns_default(self):
        """Test confidence returns default 0.70 for unknown types."""
        config = EQCConfidenceConfig.get_default_config()
        assert config.get_confidence_for_match_type("unknown") == 0.70

    def test_get_confidence_custom_default(self, tmp_path):
        """Test custom default value is respected."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: 1.00
  default: 0.50

min_confidence_for_cache: 0.60
""",
            encoding="utf-8",
        )

        config = EQCConfidenceConfig.load_from_yaml(str(config_yaml))
        assert config.get_confidence_for_match_type("unknown") == 0.50


class TestValidation:
    """Test configuration validation logic."""

    def test_confidence_range_validation_upper_bound(self, tmp_path):
        """Test that confidence > 1.0 raises ValueError."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: 1.50

min_confidence_for_cache: 0.60
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            EQCConfidenceConfig.load_from_yaml(str(config_yaml))

    def test_confidence_range_validation_lower_bound(self, tmp_path):
        """Test that confidence < 0.0 raises ValueError."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: -0.1

min_confidence_for_cache: 0.60
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            EQCConfidenceConfig.load_from_yaml(str(config_yaml))

    def test_confidence_type_validation(self, tmp_path):
        """Test that non-numeric confidence raises ValueError."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: "invalid"

min_confidence_for_cache: 0.60
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="must be numeric"):
            EQCConfidenceConfig.load_from_yaml(str(config_yaml))

    def test_min_confidence_validation(self, tmp_path):
        """Test that invalid min_confidence_for_cache raises ValueError."""
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: 1.00

min_confidence_for_cache: 1.50
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            EQCConfidenceConfig.load_from_yaml(str(config_yaml))


class TestMatchTypeExtraction:
    """Test match type extraction from raw API response."""

    def test_extract_match_type_from_raw_json(self):
        """Test extracting match type from well-formed raw JSON."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        raw_json = {
            "list": [
                {"type": "全称精确匹配", "name": "公司全称", "uniteCode": "123456"}
            ]
        }

        match_type = _extract_match_type_from_raw_json(raw_json)
        assert match_type == "全称精确匹配"

    def test_extract_match_type_missing_list(self):
        """Test extracting match type when 'list' key is missing."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        raw_json = {"other_key": "value"}
        match_type = _extract_match_type_from_raw_json(raw_json)
        assert match_type == "default"

    def test_extract_match_type_empty_list(self):
        """Test extracting match type when 'list' is empty."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        raw_json = {"list": []}
        match_type = _extract_match_type_from_raw_json(raw_json)
        assert match_type == "default"

    def test_extract_match_type_malformed_response(self):
        """Test extracting match type from malformed response."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        # None input
        assert _extract_match_type_from_raw_json(None) == "default"

        # Not a dict
        assert _extract_match_type_from_raw_json("invalid") == "default"

        # List not a list
        raw_json = {"list": "not a list"}
        assert _extract_match_type_from_raw_json(raw_json) == "default"

        # First result not a dict
        raw_json = {"list": ["not a dict"]}
        assert _extract_match_type_from_raw_json(raw_json) == "default"

    def test_extract_match_type_fuzzy(self):
        """Test extracting 模糊匹配 match type."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        raw_json = {"list": [{"type": "模糊匹配", "name": "公司名"}]}
        match_type = _extract_match_type_from_raw_json(raw_json)
        assert match_type == "模糊匹配"

    def test_extract_match_type_pinyin(self):
        """Test extracting 拼音 match type."""
        from work_data_hub.infrastructure.enrichment.eqc_provider import (
            _extract_match_type_from_raw_json,
        )

        raw_json = {"list": [{"type": "拼音", "name": "公司名"}]}
        match_type = _extract_match_type_from_raw_json(raw_json)
        assert match_type == "拼音"


class TestDefaultConfiguration:
    """Test default configuration behavior."""

    def test_get_default_config(self):
        """Test that default config has expected values."""
        config = EQCConfidenceConfig.get_default_config()

        assert config.eqc_match_confidence["全称精确匹配"] == 1.00
        assert config.eqc_match_confidence["模糊匹配"] == 0.80
        assert config.eqc_match_confidence["拼音"] == 0.60
        assert config.eqc_match_confidence["default"] == 0.70
        assert config.min_confidence_for_cache == 0.60

    def test_default_config_immutability(self):
        """Test that modifying default config doesn't affect original."""
        config1 = EQCConfidenceConfig.get_default_config()
        config2 = EQCConfidenceConfig.get_default_config()

        # Modify config1
        config1.eqc_match_confidence["全称精确匹配"] = 0.50

        # config2 should be unchanged
        assert config2.eqc_match_confidence["全称精确匹配"] == 1.00
