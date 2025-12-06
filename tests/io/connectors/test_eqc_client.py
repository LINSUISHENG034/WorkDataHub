"""
Comprehensive unit tests for EQC client.

This module provides thorough testing of the EQCClient class with mock responses,
error conditions, and edge cases to ensure >90% code coverage and robust
error handling validation.
"""

import json
import os
import time
from unittest import mock
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from work_data_hub.domain.company_enrichment.models import (
    CompanyDetail,
    CompanySearchResult,
)
from work_data_hub.io.connectors.eqc_client import (
    EQCAuthenticationError,
    EQCClient,
    EQCClientError,
    EQCNotFoundError,
    EQCRateLimitError,
)


class TestEQCClientInitialization:
    """Test EQC client initialization and configuration."""

    def test_client_initialization_with_token(self):
        """Test client initializes correctly with provided token."""
        client = EQCClient(token="test_token")
        assert client.token == "test_token"
        assert client.session.headers["token"] == "test_token"
        assert client.session.headers["Referer"] == "https://eqc.pingan.com/"
        assert "WorkDataHub EQC Client" in client.session.headers["User-Agent"]

    def test_client_initialization_with_env_token(self):
        """Test client reads token from environment variable."""
        with patch.dict(os.environ, {"WDH_EQC_TOKEN": "env_token"}):
            client = EQCClient()
            assert client.token == "env_token"
            assert client.session.headers["token"] == "env_token"

    def test_client_initialization_no_token_raises_error(self):
        """Test client raises error when no token is provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EQCAuthenticationError) as exc_info:
                EQCClient()
            assert "EQC token required" in str(exc_info.value)

    def test_client_initialization_with_custom_settings(self):
        """Test client initialization with custom configuration parameters."""
        client = EQCClient(
            token="test_token",
            timeout=60,
            retry_max=5,
            rate_limit=20,
            base_url="https://custom.eqc.com",
        )
        assert client.timeout == 60
        assert client.retry_max == 5
        assert client.rate_limit == 20
        assert client.base_url == "https://custom.eqc.com"
        assert len(client.request_times) == 0
        assert client.request_times.maxlen == 20

    @patch("work_data_hub.io.connectors.eqc_client.get_settings")
    def test_client_uses_settings_defaults(self, mock_get_settings):
        """Test client uses settings for default configuration."""
        mock_settings = Mock()
        mock_settings.eqc_timeout = 45
        mock_settings.eqc_retry_max = 4
        mock_settings.eqc_rate_limit = 15
        mock_settings.eqc_base_url = "https://settings.eqc.com"
        mock_get_settings.return_value = mock_settings

        client = EQCClient(token="test_token")
        assert client.timeout == 45
        assert client.retry_max == 4
        assert client.rate_limit == 15
        assert client.base_url == "https://settings.eqc.com"


class TestEQCClientRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiting_enforcement(self):
        """Test rate limiting prevents excessive requests."""
        client = EQCClient(token="test_token", rate_limit=2)

        # Fill rate limit with timestamps
        now = time.time()
        client.request_times.extend([now - 30, now - 10])

        # Mock time.sleep to track if it's called
        with mock.patch("time.sleep") as mock_sleep:
            start_time = time.time()
            client._enforce_rate_limit()
            elapsed = time.time() - start_time

            # Should have attempted to sleep (mocked, so elapsed time minimal)
            mock_sleep.assert_called_once()
            sleep_duration = mock_sleep.call_args[0][0]
            assert sleep_duration > 0
            assert sleep_duration <= 60  # Should not sleep more than window

    def test_rate_limiting_allows_requests_after_window(self):
        """Test rate limiting allows requests after time window expires."""
        client = EQCClient(token="test_token", rate_limit=2)

        # Add old timestamps (> 60 seconds ago)
        old_time = time.time() - 70
        client.request_times.extend([old_time, old_time + 5])

        # Should not sleep for old timestamps
        with mock.patch("time.sleep") as mock_sleep:
            client._enforce_rate_limit()
            mock_sleep.assert_not_called()

    def test_rate_limiting_sliding_window_cleanup(self):
        """Test rate limiting properly removes old timestamps."""
        client = EQCClient(token="test_token", rate_limit=5)

        # Add mix of old and recent timestamps
        now = time.time()
        client.request_times.extend(
            [
                now - 70,  # Old - should be removed
                now - 65,  # Old - should be removed
                now - 30,  # Recent - should remain
                now - 10,  # Recent - should remain
            ]
        )

        assert len(client.request_times) == 4

        # Trigger rate limit enforcement to clean up old timestamps
        client._enforce_rate_limit()

        # Only recent timestamps should remain
        assert len(client.request_times) == 2


class TestEQCClientSearchMethod:
    """Test company search functionality."""

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_search_company_success(self, mock_make_request):
        """Test successful company search."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "list": [
                {
                    "companyId": "123456789",
                    "companyFullName": "测试公司A",
                    "unite_code": "91110000000000001X",
                },
                {
                    "companyId": "987654321",
                    "companyFullName": "测试公司B",
                    "unite_code": None,
                },
            ]
        }
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")
        results = client.search_company("测试")

        # Verify request was made correctly
        mock_make_request.assert_called_once_with(
            "GET",
            "https://eqc.pingan.com/kg-api-hfd/api/search/searchAll",
            params={
                "keyword": "%E6%B5%8B%E8%AF%95",  # URL encoded "测试"
                "currentPage": 1,
                "pageSize": 10,
            },
        )

        # Verify results
        assert len(results) == 2
        assert isinstance(results[0], CompanySearchResult)
        assert results[0].company_id == "123456789"
        assert results[0].official_name == "测试公司A"
        assert results[0].unite_code == "91110000000000001X"
        assert results[0].match_score == 0.9

        assert results[1].company_id == "987654321"
        assert results[1].official_name == "测试公司B"
        assert results[1].unite_code is None

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_search_company_empty_results(self, mock_make_request):
        """Test search with empty results."""
        mock_response = Mock()
        mock_response.json.return_value = {"list": []}
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")
        results = client.search_company("NonexistentCompany")

        assert len(results) == 0
        assert isinstance(results, list)

    def test_search_company_empty_name_raises_error(self):
        """Test search with empty name raises ValueError."""
        client = EQCClient(token="test_token")

        with pytest.raises(ValueError) as exc_info:
            client.search_company("")
        assert "Company name cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            client.search_company("   ")
        assert "Company name cannot be empty" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_search_company_invalid_json_response(self, mock_make_request):
        """Test search handles invalid JSON response."""
        mock_response = Mock()
        mock_response.json.side_effect = requests.JSONDecodeError("Invalid JSON", "", 0)
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")

        with pytest.raises(EQCClientError) as exc_info:
            client.search_company("test")
        assert "Invalid JSON response" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_search_company_malformed_result_items(self, mock_make_request):
        """Test search handles malformed result items gracefully."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "list": [
                {"companyId": "123", "companyFullName": "Valid Company"},
                {
                    "companyId": "",
                    "companyFullName": "",
                },  # Invalid - empty required fields
                {"invalid": "structure"},  # Invalid - missing required fields
                {"companyId": "456", "companyFullName": "Another Valid Company"},
            ]
        }
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")
        results = client.search_company("test")

        # Should only return valid results
        assert len(results) == 2
        assert results[0].company_id == "123"
        assert results[1].company_id == "456"


class TestEQCClientDetailMethod:
    """Test company detail retrieval functionality."""

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_get_company_detail_success(self, mock_make_request):
        """Test successful company detail retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "businessInfodto": {
                "companyFullName": "详细公司信息",
                "unite_code": "91110000000000001X",
                "business_status": "在业",
                "alias_name": "公司别名",
                "short_name": "简称",
            }
        }
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")
        detail = client.get_company_detail("123456789")

        # Verify request was made correctly
        mock_make_request.assert_called_once_with(
            "GET",
            "https://eqc.pingan.com/kg-api-hfd/api/search/findDepart",
            params={"targetId": "123456789"},
        )

        # Verify result
        assert isinstance(detail, CompanyDetail)
        assert detail.company_id == "123456789"
        assert detail.official_name == "详细公司信息"
        assert detail.unite_code == "91110000000000001X"
        assert detail.business_status == "在业"
        assert "公司别名" in detail.aliases
        assert "简称" in detail.aliases

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_get_company_detail_empty_business_info(self, mock_make_request):
        """Test detail retrieval with empty business info raises not found error."""
        mock_response = Mock()
        mock_response.json.return_value = {"businessInfodto": {}}
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")

        with pytest.raises(EQCNotFoundError) as exc_info:
            client.get_company_detail("nonexistent")
        assert "No business information found" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_get_company_detail_missing_business_info(self, mock_make_request):
        """Test detail retrieval with missing businessInfodto key."""
        mock_response = Mock()
        mock_response.json.return_value = {"other_data": "value"}
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")

        with pytest.raises(EQCNotFoundError) as exc_info:
            client.get_company_detail("missing")
        assert "No business information found" in str(exc_info.value)

    def test_get_company_detail_empty_id_raises_error(self):
        """Test detail retrieval with empty company ID raises ValueError."""
        client = EQCClient(token="test_token")

        with pytest.raises(ValueError) as exc_info:
            client.get_company_detail("")
        assert "Company ID cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            client.get_company_detail("   ")
        assert "Company ID cannot be empty" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._make_request")
    def test_get_company_detail_alternative_field_names(self, mock_make_request):
        """Test detail retrieval handles alternative field names."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "businessInfodto": {
                "company_name": "使用备用字段名",  # Alternative to companyFullName
                "status": "正常",  # Alternative to business_status
                "aliases": ["别名1", "别名2"],  # Array format aliases
            }
        }
        mock_make_request.return_value = mock_response

        client = EQCClient(token="test_token")
        detail = client.get_company_detail("123")

        assert detail.official_name == "使用备用字段名"
        assert detail.business_status == "正常"
        assert "别名1" in detail.aliases
        assert "别名2" in detail.aliases


class TestEQCClientErrorHandling:
    """Test error handling for various HTTP status codes and network issues."""

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    def test_authentication_error_401(self, mock_enforce_rate_limit):
        """Test 401 authentication error handling."""
        client = EQCClient(token="invalid_token")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_request.return_value = mock_response

            with pytest.raises(EQCAuthenticationError) as exc_info:
                client.search_company("test")
            assert "Invalid or expired EQC token" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    def test_not_found_error_404(self, mock_enforce_rate_limit):
        """Test 404 not found error handling."""
        client = EQCClient(token="test_token")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = mock_response

            with pytest.raises(EQCNotFoundError) as exc_info:
                client.get_company_detail("nonexistent")
            assert "Resource not found" in str(exc_info.value)

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    @patch("time.sleep")
    def test_rate_limit_error_429_with_retries(
        self, mock_sleep, mock_enforce_rate_limit
    ):
        """Test 429 rate limit error with retry logic."""
        client = EQCClient(token="test_token", retry_max=2)

        with patch.object(client.session, "request") as mock_request:
            # All attempts return 429
            mock_response = Mock()
            mock_response.status_code = 429
            mock_request.return_value = mock_response

            with pytest.raises(EQCRateLimitError) as exc_info:
                client.search_company("test")
            assert "Rate limit exceeded, retries exhausted" in str(exc_info.value)

            # Verify retries were attempted
            assert mock_request.call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # 2 retry delays

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    @patch("time.sleep")
    def test_server_error_500_with_retries(self, mock_sleep, mock_enforce_rate_limit):
        """Test 500 server error with retry logic."""
        client = EQCClient(token="test_token", retry_max=2)

        with patch.object(client.session, "request") as mock_request:
            # All attempts return 500
            mock_response = Mock()
            mock_response.status_code = 500
            mock_request.return_value = mock_response

            with pytest.raises(EQCClientError) as exc_info:
                client.search_company("test")
            assert "Server error: 500" in str(exc_info.value)

            # Verify retries were attempted
            assert mock_request.call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # 2 retry delays

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    @patch("time.sleep")
    def test_request_exception_with_retries(self, mock_sleep, mock_enforce_rate_limit):
        """Test requests.RequestException with retry logic."""
        client = EQCClient(token="test_token", retry_max=2)

        with patch.object(client.session, "request") as mock_request:
            # All attempts raise RequestException
            mock_request.side_effect = requests.RequestException("Network error")

            with pytest.raises(EQCClientError) as exc_info:
                client.search_company("test")
            assert "Request failed after 3 attempts" in str(exc_info.value)
            assert "Network error" in str(exc_info.value)

            # Verify retries were attempted
            assert mock_request.call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # 2 retry delays


class TestEQCClientRetryLogic:
    """Test retry logic with exponential backoff."""

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    @patch("time.sleep")
    def test_exponential_backoff_calculation(self, mock_sleep, mock_enforce_rate_limit):
        """Test exponential backoff delays are calculated correctly."""
        client = EQCClient(token="test_token", retry_max=3)

        with patch.object(client.session, "request") as mock_request:
            # First few attempts fail, last succeeds
            mock_request.side_effect = [
                Mock(status_code=500),  # First attempt fails
                Mock(status_code=500),  # Second attempt fails
                Mock(status_code=500),  # Third attempt fails
                Mock(status_code=200, json=lambda: {"list": []}),  # Fourth succeeds
            ]

            client.search_company("test")

            # Verify exponential backoff was used
            assert mock_sleep.call_count == 3
            delays = [call[0][0] for call in mock_sleep.call_args_list]

            # First delay should be roughly 2^0 * (0.8-1.2) = 0.8-1.2 seconds
            assert 0.8 <= delays[0] <= 1.4

            # Second delay should be roughly 2^1 * (0.8-1.2) = 1.6-2.4 seconds
            assert 1.6 <= delays[1] <= 2.8

            # Third delay should be roughly 2^2 * (0.8-1.2) = 3.2-4.8 seconds
            assert 3.2 <= delays[2] <= 5.6

    @patch("work_data_hub.io.connectors.eqc_client.EQCClient._enforce_rate_limit")
    def test_successful_retry_after_transient_failure(self, mock_enforce_rate_limit):
        """Test successful request after transient failures."""
        client = EQCClient(token="test_token", retry_max=2)

        with patch.object(client.session, "request") as mock_request:
            # First attempt fails, second succeeds
            mock_request.side_effect = [
                Mock(status_code=500),  # First attempt fails
                Mock(
                    status_code=200,
                    json=lambda: {
                        "list": [{"companyId": "123", "companyFullName": "Test"}]
                    },
                ),
            ]

            with patch("time.sleep"):  # Mock sleep to speed up test
                results = client.search_company("test")

            # Should succeed and return results
            assert len(results) == 1
            assert results[0].company_id == "123"


class TestEQCClientAliasExtraction:
    """Test alias extraction functionality."""

    def test_extract_aliases_from_various_fields(self):
        """Test extraction of aliases from different response fields."""
        client = EQCClient(token="test_token")

        business_info = {
            "alias_name": "别名1",
            "short_name": "简称",
            "english_name": "English Name",
            "former_name": "旧名称",
            "other_names": "其他名称",
            "aliases": ["数组别名1", "数组别名2"],
        }

        aliases = client._extract_aliases(business_info)

        expected_aliases = [
            "别名1",
            "简称",
            "English Name",
            "旧名称",
            "其他名称",
            "数组别名1",
            "数组别名2",
        ]
        assert all(alias in aliases for alias in expected_aliases)
        assert len(aliases) == len(expected_aliases)

    def test_extract_aliases_handles_empty_values(self):
        """Test alias extraction handles empty and None values."""
        client = EQCClient(token="test_token")

        business_info = {
            "alias_name": "",
            "short_name": None,
            "english_name": "   ",  # Whitespace only
            "aliases": ["", None, "   ", "Valid Alias"],
        }

        aliases = client._extract_aliases(business_info)

        assert aliases == ["Valid Alias"]

    def test_extract_aliases_handles_string_aliases_field(self):
        """Test alias extraction when aliases field is a string instead of array."""
        client = EQCClient(token="test_token")

        business_info = {"aliases": "String Alias"}

        aliases = client._extract_aliases(business_info)

        assert aliases == ["String Alias"]

    def test_extract_aliases_avoids_duplicates(self):
        """Test alias extraction avoids duplicate entries."""
        client = EQCClient(token="test_token")

        business_info = {
            "alias_name": "重复别名",
            "short_name": "重复别名",  # Duplicate
            "aliases": ["重复别名", "独特别名"],  # Another duplicate
        }

        aliases = client._extract_aliases(business_info)

        assert aliases == ["重复别名", "独特别名"]
        assert len(aliases) == 2  # No duplicates


class TestEQCClientUrlSanitization:
    """Test URL sanitization for logging security."""

    def test_sanitize_url_removes_token_parameters(self):
        """Test URL sanitization removes token parameters."""
        client = EQCClient(token="test_token")

        url_with_token = (
            "https://eqc.pingan.com/api/search?keyword=test&token=secret123&other=param"
        )
        sanitized = client._sanitize_url_for_logging(url_with_token)

        assert "secret123" not in sanitized
        assert "[TOKEN_SANITIZED]" in sanitized
        assert "keyword=test" in sanitized

    def test_sanitize_url_leaves_clean_urls_unchanged(self):
        """Test URL sanitization leaves URLs without tokens unchanged."""
        client = EQCClient(token="test_token")

        clean_url = "https://eqc.pingan.com/api/search?keyword=test&page=1"
        sanitized = client._sanitize_url_for_logging(clean_url)

        assert sanitized == clean_url


# Integration test marker for optional real API tests
@pytest.mark.eqc_integration
class TestEQCClientIntegration:
    """Integration tests with real EQC API (requires valid token)."""

    def test_integration_search_and_detail(self):
        """Test integration with real EQC API."""
        token = os.getenv("WDH_EQC_TOKEN")
        if not token:
            pytest.skip("WDH_EQC_TOKEN not set - skipping integration tests")

        client = EQCClient(token=token)

        # Test search
        results = client.search_company("中国平安")
        assert isinstance(results, list)

        # If we got results, test detail retrieval
        if results:
            detail = client.get_company_detail(results[0].company_id)
            assert isinstance(detail, CompanyDetail)
            assert detail.company_id == results[0].company_id
            assert detail.official_name  # Should have a name
