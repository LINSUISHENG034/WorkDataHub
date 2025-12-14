"""
EQC (Enterprise Query Center) HTTP client for WorkDataHub.

This module provides a simple, reliable HTTP client for company data enrichment
using the EQC API. Follows KISS/YAGNI principles with proper error handling,
rate limiting, retries, and configuration management.
"""

import logging
import random
import time
from collections import deque
from typing import Deque, List, Optional

import requests

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.company_enrichment.models import (
    CompanyDetail,
    CompanySearchResult,
)

logger = logging.getLogger(__name__)


class EQCClientError(Exception):
    """Base exception for EQC client errors."""

    pass


class EQCAuthenticationError(EQCClientError):
    """Raised when EQC authentication fails (401)."""

    pass


class EQCRateLimitError(EQCClientError):
    """Raised when rate limit exceeded and retries exhausted."""

    pass


class EQCNotFoundError(EQCClientError):
    """Raised when requested resource not found (404)."""

    pass


class EQCClient:
    """
    Synchronous HTTP client for EQC (Enterprise Query Center) API.

    Provides company search and detail retrieval capabilities with proper
    error handling, rate limiting, timeouts, and retries following the
    patterns established in the WorkDataHub codebase.

    Examples:
        >>> client = EQCClient()
        >>> results = client.search_company("中国平安")
        >>> if results:
        ...     detail = client.get_company_detail(results[0].company_id)
        ...     print(f"Found: {detail.official_name}")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        timeout: Optional[int] = None,
        retry_max: Optional[int] = None,
        rate_limit: Optional[int] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize EQC client with configuration.

        Args:
            token: EQC API token. If None, reads from WDH_EQC_TOKEN
                environment variable
            timeout: Request timeout in seconds. If None, uses settings default
            retry_max: Maximum retry attempts. If None, uses settings default
            rate_limit: Requests per minute limit. If None, uses settings
                default
            base_url: EQC API base URL. If None, uses settings default

        Raises:
            EQCAuthenticationError: If no token is provided and WDH_EQC_TOKEN is not set
        """
        # Load settings for configuration defaults
        self.settings = get_settings()

        # Token priority: constructor parameter > settings
        self.token = token or self.settings.eqc_token
        if not self.token:
            raise EQCAuthenticationError(
                "EQC token required via constructor parameter or "
                "WDH_EQC_TOKEN in .env configuration file"
            )

        # Configuration with settings fallbacks
        self.timeout = timeout if timeout is not None else self.settings.eqc_timeout
        self.retry_max = (
            retry_max if retry_max is not None else self.settings.eqc_retry_max
        )
        self.rate_limit = (
            rate_limit if rate_limit is not None else self.settings.eqc_rate_limit
        )
        self.base_url = base_url if base_url is not None else self.settings.eqc_base_url

        # Initialize requests session with proper headers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "token": self.token,
                "Referer": "https://eqc.pingan.com/",
                "User-Agent": "Mozilla/5.0 (WorkDataHub EQC Client)",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            }
        )

        # Rate limiting: track request timestamps using deque for efficient
        # sliding window
        self.request_times: Deque[float] = deque(maxlen=self.rate_limit)

        logger.info(
            "EQC client initialized",
            extra={
                "base_url": self.base_url,
                "timeout": self.timeout,
                "retry_max": self.retry_max,
                "rate_limit": self.rate_limit,
                "has_token": bool(self.token),
            },
        )

    def _sanitize_url_for_logging(self, url: str) -> str:
        """
        Sanitize URL for logging by removing token parameters.

        Args:
            url: Original URL that may contain sensitive data

        Returns:
            Sanitized URL safe for logging
        """
        # Remove any token-like query parameters for security
        if "token=" in url:
            return url.split("token=")[0] + "[TOKEN_SANITIZED]"
        return url

    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting using sliding window approach.

        Tracks request timestamps and sleeps if rate limit would be exceeded.
        Uses a sliding window of 60 seconds to determine current request rate.
        """
        now = time.time()

        # Remove timestamps older than 60 seconds (sliding window)
        while self.request_times and self.request_times[0] <= now - 60:
            self.request_times.popleft()

        # If at rate limit, sleep until oldest request expires
        if len(self.request_times) >= self.rate_limit:
            sleep_time = 60 - (now - self.request_times[0]) + 0.1  # Small buffer
            logger.debug(
                "Rate limit reached, sleeping",
                extra={
                    "sleep_seconds": round(sleep_time, 1),
                    "rate_limit": self.rate_limit,
                },
            )
            time.sleep(sleep_time)

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for requests

        Returns:
            Response object for successful requests

        Raises:
            EQCAuthenticationError: For 401 authentication errors
            EQCNotFoundError: For 404 not found errors
            EQCRateLimitError: For 429 rate limit errors after exhausting retries
            EQCClientError: For other HTTP errors or request failures
        """
        sanitized_url = self._sanitize_url_for_logging(url)

        for attempt in range(self.retry_max + 1):
            try:
                # Enforce rate limiting before each request
                self._enforce_rate_limit()

                # Record request timestamp
                self.request_times.append(time.time())

                logger.debug(
                    "Making EQC API request",
                    extra={
                        "method": method,
                        "url": sanitized_url,
                        "attempt": attempt + 1,
                        "max_attempts": self.retry_max + 1,
                    },
                )

                # Make the actual request
                response = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )

                # Handle different status codes
                if response.status_code == 200:
                    logger.debug(
                        "EQC API request successful",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                        },
                    )
                    return response

                elif response.status_code == 401:
                    logger.error(
                        "EQC authentication failed",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                        },
                    )
                    raise EQCAuthenticationError("Invalid or expired EQC token")

                elif response.status_code == 404:
                    logger.warning(
                        "EQC resource not found",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                        },
                    )
                    raise EQCNotFoundError("Resource not found")

                elif response.status_code == 429:
                    logger.warning(
                        "EQC rate limit exceeded",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                        },
                    )
                    if attempt < self.retry_max:
                        # Exponential backoff with jitter for 429 errors
                        delay = (2**attempt) * (0.8 + 0.4 * random.random())
                        logger.debug(f"Retrying after {delay:.1f}s due to rate limit")
                        time.sleep(delay)
                        continue
                    raise EQCRateLimitError("Rate limit exceeded, retries exhausted")

                elif response.status_code >= 500:
                    logger.warning(
                        "EQC server error",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                        },
                    )
                    if attempt < self.retry_max:
                        # Exponential backoff with jitter for server errors
                        delay = (2**attempt) * (0.8 + 0.4 * random.random())
                        logger.debug(f"Retrying after {delay:.1f}s due to server error")
                        time.sleep(delay)
                        continue
                    raise EQCClientError(f"Server error: {response.status_code}")

                else:
                    # Unexpected status code
                    logger.error(
                        "Unexpected EQC API response",
                        extra={
                            "url": sanitized_url,
                            "status_code": response.status_code,
                        },
                    )
                    raise EQCClientError(
                        f"Unexpected status code: {response.status_code}"
                    )

            except requests.RequestException as e:
                logger.warning(
                    "EQC request failed",
                    extra={
                        "url": sanitized_url,
                        "error": str(e),
                        "attempt": attempt + 1,
                    },
                )
                if attempt < self.retry_max:
                    # Exponential backoff with jitter for request errors
                    delay = (2**attempt) * (0.8 + 0.4 * random.random())
                    logger.debug(f"Retrying after {delay:.1f}s due to request error")
                    time.sleep(delay)
                    continue
                raise EQCClientError(
                    f"Request failed after {self.retry_max + 1} attempts: {e}"
                )

        # Should not reach here, but for completeness
        raise EQCClientError("Request failed for unknown reason")

    def search_company(self, name: str) -> List[CompanySearchResult]:
        """
        Search for companies by name using EQC API.

        Uses the EQC `/search/` endpoint (key-based search) to find companies matching
        the provided name. Handles Chinese character encoding and response parsing automatically.

        Args:
            name: Company name to search for (supports Chinese characters)

        Returns:
            List of CompanySearchResult objects representing matching companies

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCClientError: For other API errors or network issues
            ValueError: If name is empty or invalid

        Examples:
            >>> client = EQCClient()
            >>> results = client.search_company("中国平安")
            >>> for result in results:
            ...     print(f"{result.official_name} (ID: {result.company_id})")
        """
        if not name or not name.strip():
            raise ValueError("Company name cannot be empty")

        # Clean the search name (do NOT pre-encode - requests handles encoding)
        cleaned_name = name.strip()

        # Construct search URL
        url = f"{self.base_url}/kg-api-hfd/api/search/"
        params = {"key": cleaned_name}  # requests will handle URL encoding

        logger.info(
            "Searching companies via EQC",
            extra={
                "query": cleaned_name,
                "query_length": len(cleaned_name),
                "endpoint": "search",
            },
        )

        try:
            # Make the API request
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Parse response based on EQC API structure
            # From legacy code: response contains 'list' array with results
            results_list = data.get("list", [])

            # Map EQC response fields to our domain models
            companies = []
            for item in results_list:
                try:
                    # Map EQC field names to our model fields
                    # Based on legacy analysis: companyId, companyFullName,
                    # unite_code
                    company = CompanySearchResult(
                        company_id=str(item.get("companyId", "")),
                        official_name=item.get("companyFullName", ""),
                        unite_code=item.get("unite_code"),
                        match_score=0.9,  # EQC doesn't provide scores, use high default
                    )
                    companies.append(company)

                except Exception as e:
                    logger.warning(
                        "Failed to parse search result item",
                        extra={"item": item, "error": str(e)},
                    )
                    continue

            logger.info(
                "Company search completed",
                extra={
                    "query": cleaned_name,
                    "results_count": len(companies),
                    "raw_results": len(results_list),
                },
            )

            return companies

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC search response",
                extra={"query": cleaned_name, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC search API: {e}")

        except KeyError as e:
            logger.error(
                "Unexpected EQC search response structure",
                extra={"query": cleaned_name, "missing_key": str(e)},
            )
            raise EQCClientError(
                f"Unexpected response structure from EQC search API: {e}"
            )

    def search_company_with_raw(self, name: str) -> tuple[List[CompanySearchResult], dict]:
        """
        Search for companies by name and return both parsed results and raw JSON.

        This method is identical to search_company() but also returns the raw
        API response for persistence purposes (Story 6.2-P5).

        Args:
            name: Company name to search for (supports Chinese characters)

        Returns:
            Tuple of (parsed_results, raw_json_response)
            - parsed_results: List of CompanySearchResult objects
            - raw_json_response: Complete API response as dict (response body only)

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCClientError: For other API errors or network issues
            ValueError: If name is empty or invalid

        Security:
            Only returns response body JSON - no headers, no token, no URL params.

        Examples:
            >>> client = EQCClient()
            >>> results, raw_json = client.search_company_with_raw("中国平安")
            >>> print(f"Found {len(results)} companies")
            >>> print(f"Raw response keys: {raw_json.keys()}")
        """
        if not name or not name.strip():
            raise ValueError("Company name cannot be empty")

        # Clean the search name (do NOT pre-encode - requests handles encoding)
        cleaned_name = name.strip()

        # Construct search URL - using legacy endpoint format
        url = f"{self.base_url}/kg-api-hfd/api/search/"
        params = {"key": cleaned_name}

        logger.info(
            "Searching companies via EQC (with raw response)",
            extra={
                "query": cleaned_name,
                "query_length": len(cleaned_name),
                "endpoint": "search",
            },
        )

        try:
            # Make the API request
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Parse response based on EQC API structure
            results_list = data.get("list", [])

            # Map EQC response fields to our domain models
            companies = []
            for item in results_list:
                try:
                    company = CompanySearchResult(
                        company_id=str(item.get("companyId", "")),
                        official_name=item.get("companyFullName", ""),
                        unite_code=item.get("unite_code"),
                        match_score=0.9,
                    )
                    companies.append(company)

                except Exception as e:
                    logger.warning(
                        "Failed to parse search result item",
                        extra={"item": item, "error": str(e)},
                    )
                    continue

            logger.info(
                "Company search with raw response completed",
                extra={
                    "query": cleaned_name,
                    "results_count": len(companies),
                    "raw_results": len(results_list),
                },
            )

            # Return both parsed results and raw JSON (response body only)
            return companies, data

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC search response",
                extra={"query": cleaned_name, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC search API: {e}")

        except KeyError as e:
            logger.error(
                "Unexpected EQC search response structure",
                extra={"query": cleaned_name, "missing_key": str(e)},
            )
            raise EQCClientError(
                f"Unexpected response structure from EQC search API: {e}"
            )

    def get_company_detail(self, company_id: str) -> CompanyDetail:
        """
        Get detailed company information by EQC company ID.

        Uses the EQC findDepart endpoint to retrieve comprehensive company details
        including business information and status.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            CompanyDetail object with comprehensive company information

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCNotFoundError: If company ID is not found
            EQCClientError: For other API errors or network issues
            ValueError: If company_id is empty or invalid

        Examples:
            >>> client = EQCClient()
            >>> detail = client.get_company_detail("123456789")
            >>> print(f"Company: {detail.official_name}")
            >>> print(f"Status: {detail.business_status}")
        """
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        # Clean the company ID
        cleaned_id = str(company_id).strip()

        # Construct detail URL - using findDepart endpoint from legacy analysis
        url = f"{self.base_url}/kg-api-hfd/api/search/findDepart"
        params = {"targetId": cleaned_id}

        logger.info(
            "Retrieving company details via EQC",
            extra={
                "company_id": cleaned_id,
                "endpoint": "findDepart",
            },
        )

        try:
            # Make the API request
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Parse response based on EQC API structure
            # From legacy code: response contains 'businessInfodto' object
            business_info = data.get("businessInfodto", {})

            if not business_info:
                logger.warning(
                    "Empty business info in EQC response",
                    extra={
                        "company_id": cleaned_id,
                        "response_keys": list(data.keys()),
                    },
                )
                raise EQCNotFoundError(
                    f"No business information found for company ID: {cleaned_id}"
                )

            # Extract company detail fields
            # Map EQC response fields to our domain model
            try:
                detail = CompanyDetail(
                    company_id=cleaned_id,
                    official_name=business_info.get(
                        "companyFullName", business_info.get("company_name", "")
                    ),
                    unite_code=business_info.get("unite_code"),
                    aliases=self._extract_aliases(business_info),
                    business_status=business_info.get(
                        "business_status", business_info.get("status")
                    ),
                )

                logger.info(
                    "Company details retrieved successfully",
                    extra={
                        "company_id": cleaned_id,
                        "official_name": detail.official_name,
                        "has_unite_code": bool(detail.unite_code),
                        "aliases_count": len(detail.aliases),
                    },
                )

                return detail

            except Exception as e:
                logger.error(
                    "Failed to parse company detail response",
                    extra={
                        "company_id": cleaned_id,
                        "error": str(e),
                        "business_info_keys": list(business_info.keys()),
                    },
                )
                raise EQCClientError(f"Failed to parse company detail response: {e}")

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC detail response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC detail API: {e}")

        except KeyError as e:
            logger.error(
                "Unexpected EQC detail response structure",
                extra={"company_id": cleaned_id, "missing_key": str(e)},
            )
            raise EQCClientError(
                f"Unexpected response structure from EQC detail API: {e}"
            )

    def _extract_aliases(self, business_info: dict) -> List[str]:
        """
        Extract company aliases from business info response.

        Args:
            business_info: Business information dictionary from EQC API

        Returns:
            List of company aliases/alternative names
        """
        aliases = []

        # Common fields that might contain alternative names
        alias_fields = [
            "alias_name",
            "short_name",
            "english_name",
            "former_name",
            "other_names",
        ]

        for field in alias_fields:
            value = business_info.get(field)
            if value and str(value).strip():
                cleaned_alias = str(value).strip()
                if cleaned_alias not in aliases:
                    aliases.append(cleaned_alias)

        # Check if aliases is a list/array in the response
        if "aliases" in business_info:
            alias_data = business_info["aliases"]
            if isinstance(alias_data, list):
                for alias in alias_data:
                    if alias and str(alias).strip():
                        cleaned_alias = str(alias).strip()
                        if cleaned_alias not in aliases:
                            aliases.append(cleaned_alias)
            elif isinstance(alias_data, str) and alias_data.strip():
                cleaned_alias = alias_data.strip()
                if cleaned_alias not in aliases:
                    aliases.append(cleaned_alias)

        return aliases
