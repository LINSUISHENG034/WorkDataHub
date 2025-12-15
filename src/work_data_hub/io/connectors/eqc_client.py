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
from pydantic import ValidationError

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.company_enrichment.models import (
    BusinessInfoResult,
    CompanyDetail,
    CompanySearchResult,
    LabelInfo,
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

                elif response.status_code == 403:
                    # Some EQC environments reject additional browser-mimic headers.
                    # Retry once with a minimal header set (token-only) if caller didn't
                    # explicitly pass headers.
                    if attempt == 0 and "headers" not in kwargs:
                        logger.warning(
                            "EQC request forbidden; retrying with minimal headers",
                            extra={
                                "url": sanitized_url,
                                "status_code": response.status_code,
                            },
                        )
                        response = self.session.request(
                            method,
                            url,
                            timeout=self.timeout,
                            headers={"token": self.token},
                            **kwargs,
                        )
                        if response.status_code == 200:
                            return response
                        if response.status_code == 401:
                            raise EQCAuthenticationError("Invalid or expired EQC token")
                        if response.status_code == 404:
                            raise EQCNotFoundError("Resource not found")
                        if response.status_code == 429:
                            raise EQCRateLimitError("Rate limit exceeded")
                        raise EQCClientError(
                            f"Unexpected status code after minimal-header retry: {response.status_code}"
                        )

                    raise EQCClientError("Forbidden (403) from EQC API")

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

        cleaned_id = str(company_id).strip()

        logger.info(
            "Retrieving company details via EQC",
            extra={
                "company_id": cleaned_id,
                "endpoint": "findDepart",
            },
        )

        try:
            # Use shared helper to avoid code duplication
            business_info, _ = self._fetch_find_depart(cleaned_id)

            # Extract company detail fields
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
                },
            )
            # Re-raise as EQCClientError if it's not already an EQC error
            if isinstance(e, (EQCNotFoundError, EQCAuthenticationError, EQCClientError)):
                raise
            raise EQCClientError(f"Failed to parse company detail response: {e}")

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

    def _fetch_find_depart(self, company_id: str) -> tuple[dict, dict]:
        """
        Call findDepart API and return (businessInfodto, raw_response).

        Shared by get_company_detail() and get_business_info_with_raw().
        Handles rate limiting, error handling, and logging internally.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            Tuple of (businessInfodto dict, complete raw response dict)

        Raises:
            EQCNotFoundError: If company not found (404 or empty businessInfodto)
            EQCAuthenticationError: If token invalid (401)
            EQCClientError: For other errors
        """
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        url = f"{self.base_url}/kg-api-hfd/api/search/findDepart"
        params = {"targetId": cleaned_id}

        logger.info(
            "Fetching business info via EQC findDepart",
            extra={
                "company_id": cleaned_id,
                "endpoint": "findDepart",
            },
        )

        try:
            response = self._make_request("GET", url, params=params)
            data = response.json()

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
                    f"No business information found for company: {cleaned_id}"
                )

            return business_info, data

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC findDepart response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC findDepart API: {e}")

    @staticmethod
    def _first_non_empty_str(payload: dict, keys: list[str]) -> Optional[str]:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
        return None

    def _parse_business_info(
        self,
        business_info: dict,
        *,
        fallback_company_id: str,
    ) -> BusinessInfoResult:
        """
        Parse business_infodto dict into BusinessInfoResult model.

        Maps EQC API fields to our domain model with proper validation.

        Args:
            business_info: businessInfodto dictionary from EQC API response

        Returns:
            BusinessInfoResult with mapped fields
        """
        company_id = (
            self._first_non_empty_str(business_info, ["company_id", "companyId", "id"])
            or fallback_company_id
        )

        company_name = self._first_non_empty_str(
            business_info,
            ["companyFullName", "company_name", "companyName", "name", "coname"],
        )

        registered_date = self._first_non_empty_str(
            business_info, ["registered_date", "registeredDate", "est_date", "estDate"]
        )

        registered_capital_raw = self._first_non_empty_str(
            business_info, ["registerCaptial", "reg_cap", "registered_capital"]
        )

        registered_status = self._first_non_empty_str(
            business_info, ["registered_status", "registeredStatus", "registered_status"]
        )

        legal_person_name = self._first_non_empty_str(
            business_info, ["legal_person_name", "legalPersonName", "le_rep"]
        )

        address = self._first_non_empty_str(business_info, ["address"])

        credit_code = self._first_non_empty_str(
            business_info, ["unite_code", "uniteCode", "credit_code", "creditCode"]
        )

        company_type = self._first_non_empty_str(
            business_info, ["company_type", "companyType", "type"]
        )

        industry_name = self._first_non_empty_str(
            business_info, ["industry_name", "industryName"]
        )

        business_scope = self._first_non_empty_str(
            business_info, ["business_scope", "businessScope"]
        )

        codename = self._first_non_empty_str(business_info, ["codename"])
        company_en_name = self._first_non_empty_str(business_info, ["company_en_name"])
        currency = self._first_non_empty_str(business_info, ["currency"])
        register_code = self._first_non_empty_str(business_info, ["register_code"])
        organization_code = self._first_non_empty_str(
            business_info, ["organization_code", "organizationCode"]
        )
        registration_organ_name = self._first_non_empty_str(
            business_info, ["registration_organ_name"]
        )
        start_date = self._first_non_empty_str(business_info, ["start_date", "startDate"])
        end_date = self._first_non_empty_str(business_info, ["end_date", "endDate"])
        start_end = self._first_non_empty_str(business_info, ["start_end"])
        telephone = self._first_non_empty_str(business_info, ["telephone"])
        email_address = self._first_non_empty_str(business_info, ["email_address"])
        website = self._first_non_empty_str(business_info, ["website"])
        colleagues_num = self._first_non_empty_str(
            business_info, ["colleagues_num", "collegues_num"]
        )
        company_former_name = self._first_non_empty_str(business_info, ["company_former_name"])
        control_id = self._first_non_empty_str(business_info, ["control_id"])
        control_name = self._first_non_empty_str(business_info, ["control_name"])
        bene_id = self._first_non_empty_str(business_info, ["bene_id"])
        bene_name = self._first_non_empty_str(business_info, ["bene_name"])
        legal_person_id = self._first_non_empty_str(business_info, ["legalPersonId", "legal_person_id"])
        province = self._first_non_empty_str(business_info, ["province"])
        logo_url = self._first_non_empty_str(business_info, ["logoUrl", "logo_url"])
        type_code = self._first_non_empty_str(business_info, ["typeCode", "type_code"])
        department = self._first_non_empty_str(business_info, ["department"])
        update_time = self._first_non_empty_str(business_info, ["updateTime", "update_time"])
        actual_capital_raw = self._first_non_empty_str(business_info, ["actualCapi", "actual_capital"])
        registered_capital_currency = self._first_non_empty_str(
            business_info, ["registeredCapitalCurrency", "registered_capital_currency"]
        )
        full_register_type_desc = self._first_non_empty_str(
            business_info, ["fullRegisterTypeDesc", "full_register_type_desc"]
        )
        industry_code = self._first_non_empty_str(business_info, ["industryCode", "industry_code"])

        return BusinessInfoResult(
            company_id=company_id,
            company_name=company_name,
            registered_date=registered_date,
            registered_capital_raw=registered_capital_raw,
            registered_status=registered_status,
            legal_person_name=legal_person_name,
            address=address,
            credit_code=credit_code,
            company_type=company_type,
            industry_name=industry_name,
            business_scope=business_scope,
            codename=codename,
            company_en_name=company_en_name,
            currency=currency,
            register_code=register_code,
            organization_code=organization_code,
            registration_organ_name=registration_organ_name,
            start_date=start_date,
            end_date=end_date,
            start_end=start_end,
            telephone=telephone,
            email_address=email_address,
            website=website,
            colleagues_num=colleagues_num,
            company_former_name=company_former_name,
            control_id=control_id,
            control_name=control_name,
            bene_id=bene_id,
            bene_name=bene_name,
            legal_person_id=legal_person_id,
            province=province,
            logo_url=logo_url,
            type_code=type_code,
            department=department,
            update_time=update_time,
            actual_capital_raw=actual_capital_raw,
            registered_capital_currency=registered_capital_currency,
            full_register_type_desc=full_register_type_desc,
            industry_code=industry_code,
        )

    def get_business_info(self, company_id: str) -> BusinessInfoResult:
        """
        Get business information by EQC company ID.

        Uses the EQC findDepart endpoint to retrieve comprehensive business
        registration information.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            BusinessInfoResult with comprehensive business information

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCNotFoundError: If company ID is not found
            EQCClientError: For other API errors or network issues
            ValueError: If company_id is empty or invalid
        """
        cleaned_id = str(company_id).strip()
        business_info, _ = self._fetch_find_depart(cleaned_id)
        try:
            return self._parse_business_info(
                business_info,
                fallback_company_id=cleaned_id,
            )
        except ValidationError as e:
            raise EQCClientError(
                f"Unexpected response structure from EQC findDepart API: {e}"
            )

    def get_business_info_with_raw(self, company_id: str) -> tuple[BusinessInfoResult, dict]:
        """
        Get business information and return both parsed result and raw JSON.

        This method is identical to get_business_info() but also returns the raw
        API response for persistence purposes.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            Tuple of (parsed_result, raw_json_response)
            - parsed_result: BusinessInfoResult object
            - raw_json_response: Complete API response as dict (response body only)

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCClientError: For other API errors or network issues
            ValueError: If company_id is empty or invalid

        Security:
            Only returns response body JSON - no headers, no token, no URL params.
        """
        cleaned_id = str(company_id).strip()
        business_info, raw = self._fetch_find_depart(cleaned_id)
        try:
            parsed = self._parse_business_info(
                business_info,
                fallback_company_id=cleaned_id,
            )
        except ValidationError as e:
            raise EQCClientError(
                f"Unexpected response structure from EQC findDepart API: {e}"
            )
        return parsed, raw

    def _parse_labels_with_fallback(self, labels_response: dict, target_company_id: str) -> List[LabelInfo]:
        """
        Parse labels response with null companyId fallback logic.

        When companyId is None, search siblings for a non-null value.
        From legacy crawler pattern.

        Args:
            labels_response: Response from findLabels API
            target_company_id: Company ID to use as final fallback

        Returns:
            List of LabelInfo objects
        """
        results = []
        for category in labels_response.get("labels", []):
            label_type = category.get("type", "")
            for lab in category.get("labels", []):
                company_id = lab.get("companyId")
                # Fallback: if companyId is None, try siblings
                if company_id is None:
                    for sibling in category.get("labels", []):
                        if sibling.get("companyId"):
                            company_id = sibling["companyId"]
                            break
                # Final fallback: use the target_company_id from search
                if company_id is None:
                    company_id = target_company_id

                lv1 = lab.get("lv1Name")
                lv2 = lab.get("lv2Name")
                lv3 = lab.get("lv3Name")
                lv4 = lab.get("lv4Name")

                # Legacy quirk: some responses encode region labels as:
                # lv1Name="地区分类", lv2Name=<province>, lv3Name=<city>.
                # Normalize to make the hierarchy usable without special handling downstream.
                if lv1 == "地区分类" and lv2:
                    lv1, lv2, lv3, lv4 = lv2, lv3, lv4, None

                results.append(LabelInfo(
                    company_id=company_id,
                    type=label_type,
                    lv1_name=lv1,
                    lv2_name=lv2,
                    lv3_name=lv3,
                    lv4_name=lv4,
                ))
        return results

    def get_label_info(self, company_id: str) -> List[LabelInfo]:
        """
        Get label information by EQC company ID.

        Uses the EQC findLabels endpoint to retrieve classification labels
        for a company.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            List of LabelInfo objects representing company labels

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCClientError: For other API errors or network issues
            ValueError: If company_id is empty or invalid
        """
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        url = f"{self.base_url}/kg-api-hfd/api/search/findLabels"
        params = {"targetId": cleaned_id}

        logger.info(
            "Retrieving label info via EQC",
            extra={
                "company_id": cleaned_id,
                "endpoint": "findLabels",
            },
        )

        try:
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Parse labels with fallback logic for null companyId
            labels = self._parse_labels_with_fallback(data, cleaned_id)

            logger.info(
                "Label info retrieved successfully",
                extra={
                    "company_id": cleaned_id,
                    "labels_count": len(labels),
                },
            )

            return labels

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC findLabels response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC findLabels API: {e}")

    def get_label_info_with_raw(self, company_id: str) -> tuple[List[LabelInfo], dict]:
        """
        Get label information and return both parsed result and raw JSON.

        This method is identical to get_label_info() but also returns the raw
        API response for persistence purposes.

        Args:
            company_id: EQC company ID (as string)

        Returns:
            Tuple of (parsed_result, raw_json_response)
            - parsed_result: List of LabelInfo objects
            - raw_json_response: Complete API response as dict (response body only)

        Raises:
            EQCAuthenticationError: If authentication fails
            EQCClientError: For other API errors or network issues
            ValueError: If company_id is empty or invalid

        Security:
            Only returns response body JSON - no headers, no token, no URL params.
        """
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        url = f"{self.base_url}/kg-api-hfd/api/search/findLabels"
        params = {"targetId": cleaned_id}

        logger.info(
            "Retrieving label info via EQC (with raw response)",
            extra={
                "company_id": cleaned_id,
                "endpoint": "findLabels",
            },
        )

        try:
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Parse labels with fallback logic
            labels = self._parse_labels_with_fallback(data, cleaned_id)

            logger.info(
                "Label info with raw response retrieved successfully",
                extra={
                    "company_id": cleaned_id,
                    "labels_count": len(labels),
                },
            )

            # Return both parsed results and raw JSON
            return labels, data

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC findLabels response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC findLabels API: {e}")
