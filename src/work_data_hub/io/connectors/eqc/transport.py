"""
HTTP Transport layer for EQC connector.
Handles connection, configuration, rate limiting, and retries.
"""

import logging
import random
import time
from collections import deque
from typing import Deque, Optional

import requests

from work_data_hub.config.settings import get_settings
from .models import (
    EQCAuthenticationError,
    EQCClientError,
    EQCNotFoundError,
    EQCRateLimitError,
)
from .utils import sanitize_url_for_logging

logger = logging.getLogger(__name__)


class EQCTransport:
    """
    Base HTTP transport for EQC API.
    Handles session management, headers, rate limiting, and retries.
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
        Initialize EQC transport with configuration.

        Args:
            token: EQC API token. If None, reads from WDH_EQC_TOKEN
                environment variable
            timeout: Request timeout in seconds. If None, uses settings default
            retry_max: Maximum retry attempts. If None, uses settings default
            rate_limit: Requests per minute limit. If None, uses settings
                default
            base_url: EQC API base URL. If None, uses settings default
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
            "EQC transport initialized",
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
        Wrapper for backward compatibility.
        """
        return sanitize_url_for_logging(url)

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
        sanitized_url = sanitize_url_for_logging(url)

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
