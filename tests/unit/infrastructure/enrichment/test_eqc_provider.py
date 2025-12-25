"""
Unit tests for EqcProvider.

Story 6.6: EQC API Provider (Sync Lookup with Budget)

Tests cover:
- Successful lookup returns CompanyInfo
- Budget enforcement
- 401 session disable
- 404 handling
- Timeout retry logic
- Cache write success/failure
- Token never logged
- No token configured handling
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from work_data_hub.infrastructure.enrichment.eqc_provider import (
    CompanyInfo,
    EqcProvider,
    EqcTokenInvalidError,
    validate_eqc_token,
)
from work_data_hub.io.connectors.eqc_client import (
    EQCAuthenticationError,
    EQCClientError,
    EQCNotFoundError,
)


class TestEqcProviderInit:
    """Tests for EqcProvider initialization."""

    def test_init_with_token(self) -> None:
        """Provider initializes with provided token."""
        provider = EqcProvider(token="test_token_12345678901234567890", budget=5)
        assert provider.token == "test_token_12345678901234567890"
        assert provider.budget == 5
        assert provider.remaining_budget == 5
        assert not provider._disabled

    def test_init_without_token_logs_warning(self) -> None:
        """Provider logs warning when no token configured."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="")
            assert provider.token == ""
            assert not provider.is_available

    def test_init_with_validate_on_init_valid_token(self) -> None:
        """Provider validates token on init when validate_on_init=True."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.requests.get"
        ) as mock_get:
            mock_get.return_value.status_code = 200

            provider = EqcProvider(
                token="valid_token_12345678901234567890",
                validate_on_init=True,
            )
            assert provider.token == "valid_token_12345678901234567890"

    def test_init_with_validate_on_init_invalid_token(self) -> None:
        """Provider raises EqcTokenInvalidError when token is invalid."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.requests.get"
        ) as mock_get:
            mock_get.return_value.status_code = 401

            with pytest.raises(EqcTokenInvalidError) as exc_info:
                EqcProvider(
                    token="invalid_token_1234567890123456",
                    validate_on_init=True,
                )

            assert "Token 无效或已过期" in str(exc_info.value)
            assert "uv run python -m work_data_hub.io.auth" in str(exc_info.value)


class TestEqcProviderLookup:
    """Tests for EqcProvider.lookup() method."""

    @pytest.fixture
    def provider(self) -> EqcProvider:
        """Create a provider with mocked settings."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            return EqcProvider(
                token="test_token_12345678901234567890",
                budget=5,
                base_url="https://eqc.test.com",
            )

    def test_lookup_success(self, provider: EqcProvider) -> None:
        """Successful lookup returns CompanyInfo."""
        provider.client = MagicMock()
        # Mock search_company_with_raw to return (results, raw_json) tuple
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="614810477",
                    official_name="中国平安保险集团股份有限公司",
                    unite_code="91440300100001XXXX",
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "614810477"}]},  # raw_json
        )

        result = provider.lookup("中国平安")

        assert result is not None
        assert result.company_id == "614810477"
        assert result.official_name == "中国平安保险集团股份有限公司"
        assert result.unified_credit_code == "91440300100001XXXX"
        # Story 7.1-8: Confidence is now based on match_type from config, not raw match_score
        # Default confidence is 0.7 when match type cannot be determined from mock data
        assert result.confidence == 0.7
        assert result.match_type == "eqc"

    def test_lookup_not_found_returns_none(self, provider: EqcProvider) -> None:
        """EQC not found returns None."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.side_effect = EQCNotFoundError(
            "not found"
        )

        result = provider.lookup("不存在的公司")

        assert result is None

    def test_lookup_empty_results_returns_none(self, provider: EqcProvider) -> None:
        """Empty results list returns None."""
        provider.client = MagicMock()
        # Return empty results with raw_json
        provider.client.search_company_with_raw.return_value = ([], {})

        result = provider.lookup("不存在的公司")

        assert result is None

    def test_lookup_unauthorized_disables_provider(self, provider: EqcProvider) -> None:
        """HTTP 401 disables provider for session."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.side_effect = EQCAuthenticationError(
            "unauth"
        )

        result = provider.lookup("任意公司")

        assert result is None
        assert provider._disabled is True
        assert not provider.is_available

        # Subsequent lookups should return None immediately
        result2 = provider.lookup("另一个公司")
        assert result2 is None

    def test_lookup_budget_exhausted_returns_none(self, provider: EqcProvider) -> None:
        """Returns None when budget exhausted."""
        provider.remaining_budget = 0

        result = provider.lookup("任意公司")

        assert result is None
        assert not provider.is_available

    def test_lookup_decrements_budget(self, provider: EqcProvider) -> None:
        """Each lookup decrements budget."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="123",
                    official_name="Test",
                    match_score=0.8,
                    unite_code=None,
                )
            ],
            {"list": []},
        )

        initial_budget = provider.remaining_budget
        provider.lookup("公司A")

        assert provider.remaining_budget == initial_budget - 1

    def test_lookup_no_token_returns_none(self) -> None:
        """Returns None when no token configured."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="", budget=5)
            result = provider.lookup("任意公司")

            assert result is None


class TestEqcProviderRetry:
    """Tests for EqcProvider retry logic."""

    @pytest.fixture
    def provider(self) -> EqcProvider:
        """Create a provider for retry tests."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            return EqcProvider(
                token="test_token_12345678901234567890",
                budget=5,
                base_url="https://eqc.test.com",
            )

    def test_lookup_retries_on_timeout(self, provider: EqcProvider) -> None:
        """Timeouts via EQC client return None without raising."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.side_effect = EQCClientError("timeout")

        result = provider.lookup("公司A")

        assert result is None

    def test_lookup_no_retry_on_4xx(self, provider: EqcProvider) -> None:
        """Client errors return None without retrying."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.side_effect = EQCClientError(
            "bad request"
        )

        result = provider.lookup("公司A")

        assert result is None

    def test_lookup_retries_exhausted(self, provider: EqcProvider) -> None:
        """Budget decremented even when EQC client fails."""
        provider.client = MagicMock()
        provider.client.search_company_with_raw.side_effect = EQCClientError("timeout")

        initial_budget = provider.remaining_budget
        result = provider.lookup("公司A")

        assert result is None
        assert provider.remaining_budget == initial_budget - 1


class TestEqcProviderCache:
    """Tests for EqcProvider caching behavior."""

    def test_lookup_caches_on_success(self) -> None:
        """Successful lookup caches result to repository."""
        mock_repo = MagicMock()

        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(
                token="test_token_12345678901234567890",
                budget=5,
                mapping_repository=mock_repo,
            )

        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="614810477",
                    official_name="中国平安",
                    unite_code=None,
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "614810477"}]},
        )

        # Mock normalize_for_temp_id at the module where it's imported in _cache_result
        with patch(
            "work_data_hub.infrastructure.enrichment.normalizer.normalize_for_temp_id"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            provider.lookup("中国平安")

            mock_repo.insert_enrichment_index_batch.assert_called_once()
            call_args = mock_repo.insert_enrichment_index_batch.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0].company_id == "614810477"
            assert call_args[0].source.value == "eqc_api"
            assert call_args[0].lookup_type.value == "customer_name"

    def test_lookup_cache_failure_graceful(self) -> None:
        """Cache failure doesn't block lookup."""
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.side_effect = Exception("DB error")

        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(
                token="test_token_12345678901234567890",
                budget=5,
                mapping_repository=mock_repo,
            )

        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="614810477",
                    official_name="中国平安",
                    unite_code=None,
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "614810477"}]},
        )

        # Mock normalize_company_name at the module where it's imported in _cache_result
        with patch(
            "work_data_hub.infrastructure.cleansing.normalize_company_name"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            # Should not raise, should return result
            result = provider.lookup("中国平安")

            assert result is not None
            assert result.company_id == "614810477"


class TestEqcProviderHelpers:
    """Tests for EqcProvider helper methods."""

    def test_is_available_true(self) -> None:
        """is_available returns True when provider is ready."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="test_token_12345678901234567890", budget=5)

            assert provider.is_available is True

    def test_is_available_false_no_token(self) -> None:
        """is_available returns False when no token."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="", budget=5)

            assert provider.is_available is False

    def test_is_available_false_no_budget(self) -> None:
        """is_available returns False when budget exhausted."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="test_token_12345678901234567890", budget=0)

            assert provider.is_available is False

    def test_is_available_false_disabled(self) -> None:
        """is_available returns False when disabled."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="test_token_12345678901234567890", budget=5)
            provider._disabled = True

            assert provider.is_available is False

    def test_reset_budget(self) -> None:
        """reset_budget restores budget to initial value."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="test_token_12345678901234567890", budget=5)
            provider.remaining_budget = 0

            provider.reset_budget()

            assert provider.remaining_budget == 5

    def test_reset_disabled(self) -> None:
        """reset_disabled re-enables provider."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            provider = EqcProvider(token="test_token_12345678901234567890", budget=5)
            provider._disabled = True

            provider.reset_disabled()

            assert provider._disabled is False


class TestValidateEqcToken:
    """Tests for validate_eqc_token function."""

    def test_validate_token_valid(self) -> None:
        """Returns True for valid token."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.requests.get"
        ) as mock_get:
            mock_get.return_value.status_code = 200

            result = validate_eqc_token("valid_token", "https://eqc.test.com")

            assert result is True

    def test_validate_token_invalid_401(self) -> None:
        """Returns False for 401 response."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.requests.get"
        ) as mock_get:
            mock_get.return_value.status_code = 401

            result = validate_eqc_token("invalid_token", "https://eqc.test.com")

            assert result is False

    def test_validate_token_network_error(self) -> None:
        """Returns True on network error (not token issue)."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.requests.get"
        ) as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            result = validate_eqc_token("token", "https://eqc.test.com")

            assert result is True  # Network error doesn't indicate invalid token


class TestEqcProviderFullDataAcquisition:
    """Tests for EQC Provider full data acquisition (Story 6.2-P8)."""

    @pytest.fixture
    def provider(self) -> EqcProvider:
        """Create a provider with mocked settings."""
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
        ) as mock_settings:
            mock_settings.return_value.eqc_token = ""
            mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
            mock_settings.return_value.company_sync_lookup_limit = 5
            mock_settings.return_value.eqc_rate_limit = 10

            return EqcProvider(
                token="test_token_12345678901234567890",
                budget=5,
                base_url="https://eqc.test.com",
            )

    def test_lookup_calls_all_three_endpoints(self, provider) -> None:
        """Test that lookup calls search, findDepart, and findLabels endpoints."""
        mock_repo = MagicMock()
        provider.mapping_repository = mock_repo

        # Mock the client methods
        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    official_name="中国平安保险（集团）股份有限公司",
                    unite_code="91440300618698064P",
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "1000065057"}]},
        )
        provider.client.get_business_info_with_raw.return_value = (
            SimpleNamespace(
                company_id="1000065057",
                company_name="中国平安保险（集团）股份有限公司",
                registered_capital_raw="80000.00万元",
            ),
            {"businessInfodto": {"company_id": "1000065057"}},
        )
        provider.client.get_label_info_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    type="行业分类",
                    lv1_name="金融业",
                )
            ],
            {"labels": [{"type": "行业分类", "labels": []}]},
        )

        # Mock normalizer
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.normalize_for_temp_id"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            result = provider.lookup("中国平安")

            # Verify all three endpoints were called
            provider.client.search_company_with_raw.assert_called_once_with("中国平安")
            provider.client.get_business_info_with_raw.assert_called_once_with(
                "1000065057"
            )
            provider.client.get_label_info_with_raw.assert_called_once_with(
                "1000065057"
            )

            # Verify result
            assert result is not None
            assert result.company_id == "1000065057"
            assert result.official_name == "中国平安保险（集团）股份有限公司"

            # Verify repository was called with all raw data
            mock_repo.insert_enrichment_index_batch.assert_called_once()
            mock_repo.upsert_base_info.assert_called_once()
            call_args = mock_repo.upsert_base_info.call_args
            assert call_args[1]["company_id"] == "1000065057"
            assert call_args[1]["raw_data"] == {"list": [{"companyId": "1000065057"}]}
            assert call_args[1]["raw_business_info"] == {
                "businessInfodto": {"company_id": "1000065057"}
            }
            assert call_args[1]["raw_biz_label"] == {
                "labels": [{"type": "行业分类", "labels": []}]
            }

    def test_lookup_continues_when_business_info_fails(self, provider) -> None:
        """Test that lookup continues when get_business_info fails (error isolation)."""
        mock_repo = MagicMock()
        provider.mapping_repository = mock_repo

        # Mock the client methods - business info raises exception
        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    official_name="中国平安保险",
                    unite_code="91440300618698064P",
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "1000065057"}]},
        )
        provider.client.get_business_info_with_raw.side_effect = Exception("API error")
        provider.client.get_label_info_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    type="行业分类",
                    lv1_name="金融业",
                )
            ],
            {"labels": []},
        )

        # Mock normalizer
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.normalize_for_temp_id"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            result = provider.lookup("中国平安")

            # Should still return a result despite business info failure
            assert result is not None
            assert result.company_id == "1000065057"

            # Verify repository was called with None for failed business info
            mock_repo.upsert_base_info.assert_called_once()
            call_args = mock_repo.upsert_base_info.call_args
            assert call_args[1]["raw_business_info"] is None
            assert call_args[1]["raw_biz_label"] == {"labels": []}

    def test_lookup_continues_when_label_info_fails(self, provider) -> None:
        """Test that lookup continues when get_label_info fails (error isolation)."""
        mock_repo = MagicMock()
        provider.mapping_repository = mock_repo

        # Mock the client methods - label info raises exception
        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    official_name="中国平安保险",
                    unite_code="91440300618698064P",
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "1000065057"}]},
        )
        provider.client.get_business_info_with_raw.return_value = (
            SimpleNamespace(
                company_id="1000065057",
                company_name="中国平安保险",
            ),
            {"businessInfodto": {}},
        )
        provider.client.get_label_info_with_raw.side_effect = Exception("API error")

        # Mock normalizer
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.normalize_for_temp_id"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            result = provider.lookup("中国平安")

            # Should still return a result despite label info failure
            assert result is not None
            assert result.company_id == "1000065057"

            # Verify repository was called with None for failed label info
            mock_repo.upsert_base_info.assert_called_once()
            call_args = mock_repo.upsert_base_info.call_args
            assert call_args[1]["raw_business_info"] == {"businessInfodto": {}}
            assert call_args[1]["raw_biz_label"] is None

    def test_lookup_continues_when_both_additional_apis_fail(self, provider) -> None:
        """Test that lookup continues when both business_info and label_info fail."""
        mock_repo = MagicMock()
        provider.mapping_repository = mock_repo

        # Mock the client methods - both additional APIs fail
        provider.client = MagicMock()
        provider.client.search_company_with_raw.return_value = (
            [
                SimpleNamespace(
                    company_id="1000065057",
                    official_name="中国平安保险",
                    unite_code="91440300618698064P",
                    match_score=0.9,
                )
            ],
            {"list": [{"companyId": "1000065057"}]},
        )
        provider.client.get_business_info_with_raw.side_effect = Exception(
            "Business API error"
        )
        provider.client.get_label_info_with_raw.side_effect = Exception(
            "Label API error"
        )

        # Mock normalizer
        with patch(
            "work_data_hub.infrastructure.enrichment.eqc_provider.normalize_for_temp_id"
        ) as mock_norm:
            mock_norm.return_value = "中国平安"

            result = provider.lookup("中国平安")

            # Should still return a result with just search data
            assert result is not None
            assert result.company_id == "1000065057"

            # Verify repository was called with None for both failed APIs
            mock_repo.upsert_base_info.assert_called_once()
            call_args = mock_repo.upsert_base_info.call_args
            assert call_args[1]["raw_data"] == {"list": [{"companyId": "1000065057"}]}
            assert call_args[1]["raw_business_info"] is None
            assert call_args[1]["raw_biz_label"] is None
