"""
Integration tests for EQC Provider confidence scoring (Story 7.1-8).

Tests cover end-to-end confidence assignment and caching behavior.
"""

from unittest.mock import MagicMock, Mock

import pytest

from work_data_hub.infrastructure.enrichment.eqc_confidence_config import (
    EQCConfidenceConfig,
)
from work_data_hub.infrastructure.enrichment.eqc_provider import (
    CompanyInfo,
    EqcProvider,
    _extract_match_type_from_raw_json,
)


class TestEQCProviderConfidenceAssignment:
    """Test confidence assignment in EQCProvider._call_api()."""

    def test_exact_match_gets_confidence_1_00(self):
        """Test that 全称精确匹配 results get confidence = 1.00."""
        # Setup mock client
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "全称精确匹配", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        # Setup mock repository
        mock_repo = MagicMock()

        # Create provider with default config
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        # Call API
        result, raw_json = provider._call_api("测试公司")

        # Verify confidence
        assert result is not None
        assert result.confidence == 1.00
        assert result.match_type == "eqc"

    def test_fuzzy_match_gets_confidence_0_80(self):
        """Test that 模糊匹配 results get confidence = 0.80."""
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "模糊匹配", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        result, raw_json = provider._call_api("测试公司")

        assert result is not None
        assert result.confidence == 0.80

    def test_pinyin_match_gets_confidence_0_60(self):
        """Test that 拼音 results get confidence = 0.60."""
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "拼音", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        result, raw_json = provider._call_api("测试公司")

        assert result is not None
        assert result.confidence == 0.60

    def test_unknown_match_type_gets_default_confidence(self):
        """Test that unknown match types get default confidence = 0.70."""
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "unknown_type", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        result, raw_json = provider._call_api("测试公司")

        assert result is not None
        assert result.confidence == 0.70  # Default value


class TestCacheThresholdFiltering:
    """Test min_confidence_for_cache threshold behavior."""

    def test_high_confidence_result_is_cached(self):
        """Test that results above threshold are cached to enrichment_index."""
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "全称精确匹配", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        # Call lookup (which triggers caching)
        result = provider.lookup("测试公司")

        # Verify enrichment_index cache was called
        assert mock_repo.insert_enrichment_index_batch.called

    def test_low_confidence_result_skips_cache(self):
        """Test that results below threshold skip enrichment_index cache."""
        # Create custom config with high threshold
        custom_config = EQCConfidenceConfig(
            eqc_match_confidence={
                "全称精确匹配": 1.00,
                "模糊匹配": 0.80,
                "拼音": 0.60,
                "default": 0.70,
            },
            min_confidence_for_cache=0.70,  # High threshold
        )

        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "拼音", "name": "测试公司"}]},  # Confidence = 0.60
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
            eqc_confidence_config=custom_config,
        )
        provider.client = mock_client

        # Call lookup
        result = provider.lookup("测试公司")

        # Verify enrichment_index cache was NOT called (below threshold)
        assert not mock_repo.insert_enrichment_index_batch.called

        # Verify base_info persistence was still called (for audit trail)
        assert mock_repo.upsert_base_info.called

    def test_threshold_edge_case_equal_is_cached(self):
        """Test that confidence == threshold is cached."""
        custom_config = EQCConfidenceConfig(
            eqc_match_confidence={
                "全称精确匹配": 1.00,
                "模糊匹配": 0.80,
                "拼音": 0.60,
                "default": 0.70,
            },
            min_confidence_for_cache=0.60,  # Equal to pinyin confidence
        )

        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "拼音", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
            eqc_confidence_config=custom_config,
        )
        provider.client = mock_client

        result = provider.lookup("测试公司")

        # Should be cached since confidence == threshold
        assert mock_repo.insert_enrichment_index_batch.called


class TestConfidenceConfigInjection:
    """Test custom EQCConfidenceConfig injection."""

    def test_custom_config_overrides_defaults(self):
        """Test that injected config overrides default values."""
        custom_config = EQCConfidenceConfig(
            eqc_match_confidence={
                "全称精确匹配": 0.90,  # Non-standard value
                "default": 0.50,
            },
            min_confidence_for_cache=0.80,
        )

        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "全称精确匹配", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
            eqc_confidence_config=custom_config,
        )
        provider.client = mock_client

        result, raw_json = provider._call_api("测试公司")

        # Verify custom config value is used
        assert result.confidence == 0.90  # Custom value, not 1.00

    def test_missing_config_loads_from_yaml(self, tmp_path):
        """Test that missing config loads from default YAML path."""
        # Create temporary config file
        config_yaml = tmp_path / "eqc_confidence.yml"
        config_yaml.write_text(
            """
eqc_match_confidence:
  全称精确匹配: 0.95
  default: 0.65

min_confidence_for_cache: 0.55
""",
            encoding="utf-8",
        )

        # Note: This test verifies the provider loads config when None is passed
        # In real scenario, config is loaded from config/eqc_confidence.yml
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "unknown", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (None, None)
        mock_client.get_label_info_with_raw.return_value = (None, None)

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
            # No eqc_confidence_config passed - should load from YAML
        )
        provider.client = mock_client

        result, raw_json = provider._call_api("测试公司")

        # Should use default config values (0.70 for unknown)
        assert result.confidence == 0.70


class TestEndToEndConfidenceFlow:
    """Test complete confidence flow from API to cache."""

    def test_exact_match_full_flow(self):
        """Test full flow: API → CompanyInfo → Cache (with confidence = 1.00)."""
        mock_client = MagicMock()
        mock_client.search_company_with_raw.return_value = (
            [
                MagicMock(
                    company_id="12345",
                    official_name="测试公司",
                    unite_code="123456789",
                )
            ],
            {"list": [{"type": "全称精确匹配", "name": "测试公司"}]},
        )
        mock_client.get_business_info_with_raw.return_value = (
            None,
            {"business": "data"},
        )
        mock_client.get_label_info_with_raw.return_value = (None, {"label": "data"})

        mock_repo = MagicMock()
        provider = EqcProvider(
            token="test_token",
            budget=5,
            base_url="http://test",
            mapping_repository=mock_repo,
        )
        provider.client = mock_client

        # Full lookup flow
        result = provider.lookup("测试公司")

        # Verify CompanyInfo
        assert result is not None
        assert result.company_id == "12345"
        assert result.confidence == 1.00
        assert result.match_type == "eqc"

        # Verify cache write
        assert mock_repo.insert_enrichment_index_batch.called
        call_args = mock_repo.insert_enrichment_index_batch.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0].confidence == 1.00
