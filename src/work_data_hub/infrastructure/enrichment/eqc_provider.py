"""
EQC Platform API Provider for Company ID Resolution.

This module provides the EqcProvider class that implements the EnterpriseInfoProvider
protocol for synchronous company ID lookup via the EQC (Enterprise Query Center) API.

Story 6.6: EQC API Provider (Sync Lookup with Budget)
Architecture Reference: AD-002 (Temporary ID Generation), AD-010 (Infrastructure Layer)

Features:
- Budget-limited API calls (default: 5 per session)
- 5-second timeout per request with fail-fast behavior
- 2 retries on network timeout (not on 4xx errors)
- Automatic result caching to database
- Session disable on HTTP 401 (unauthorized)
- Token pre-validation mechanism

Security:
- NEVER logs API token or sensitive response data
- Only logs counts and status codes
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

import requests

from work_data_hub.config.settings import get_settings
from work_data_hub.io.connectors.eqc_client import (
    EQCAuthenticationError,
    EQCClient,
    EQCClientError,
    EQCNotFoundError,
)
from work_data_hub.utils.logging import get_logger

if TYPE_CHECKING:
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)

# Configuration constants
REQUEST_TIMEOUT_SECONDS = 5
MAX_RETRIES = 2
DEFAULT_BUDGET = 5


class EqcTokenInvalidError(Exception):
    """
    Exception raised when EQC token is invalid or expired.

    Provides helpful guidance on how to update the token.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        self.help_command = "uv run python -m work_data_hub.io.auth --capture --save"
        super().__init__(
            f"{message}\n\n"
            f"请运行以下命令更新 Token:\n"
            f"  {self.help_command}"
        )


@dataclass
class CompanyInfo:
    """
    Company information returned from EQC lookup.

    Attributes:
        company_id: Canonical company ID from EQC.
        official_name: Official registered company name.
        unified_credit_code: Unified social credit code (统一社会信用代码).
        confidence: Match confidence score (0.0-1.0).
        match_type: Type of match (exact, fuzzy, alias).
    """

    company_id: str
    official_name: str
    unified_credit_code: Optional[str]
    confidence: float
    match_type: str


class EnterpriseInfoProvider(Protocol):
    """Protocol for company information providers."""

    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        """
        Resolve company name to CompanyInfo or None if not found.

        Args:
            company_name: Company name to look up.

        Returns:
            CompanyInfo if found, None otherwise.
        """
        ...


def validate_eqc_token(token: str, base_url: str) -> bool:
    """
    Lightweight token validation via single API call.

    Uses a simple search request to verify token validity without
    consuming significant API resources.

    Args:
        token: EQC API token to validate.
        base_url: EQC API base URL.

    Returns:
        True if token is valid, False if invalid (401) or network error.
    """
    try:
        response = requests.get(
            f"{base_url}/kg-api-hfd/api/search/searchAll",
            params={"keyword": "test", "currentPage": 1, "pageSize": 1},
            headers={"token": token},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        # 401 means token is invalid; other errors don't indicate token invalidity
        return response.status_code != 401
    except requests.RequestException:
        # Network errors don't indicate token invalidity
        return True


class EqcProvider:
    """
    EQC platform API provider for company ID lookup.

    Implements EnterpriseInfoProvider protocol with:
    - Budget-limited API calls
    - 5-second timeout per request
    - 2 retries on network timeout (not on 4xx errors)
    - Automatic result caching to database

    Attributes:
        token: EQC API authentication token.
        budget: Maximum API calls allowed per session.
        remaining_budget: Remaining API calls in current session.
        _disabled: Flag set on HTTP 401 to disable provider for session.

    Example:
        >>> provider = EqcProvider(budget=5)
        >>> result = provider.lookup("中国平安保险")
        >>> if result:
        ...     print(f"Found: {result.company_id}")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        budget: Optional[int] = None,
        base_url: Optional[str] = None,
        mapping_repository: Optional["CompanyMappingRepository"] = None,
        validate_on_init: bool = False,
    ) -> None:
        """
        Initialize EqcProvider.

        Args:
            token: EQC API token. If None, loads from settings.
            budget: Maximum API calls per session. If None, uses settings default.
            base_url: EQC API base URL. If None, uses settings default.
            mapping_repository: Optional repository for caching results.
            validate_on_init: If True, validate token on initialization.

        Raises:
            EqcTokenInvalidError: If validate_on_init=True and token is invalid.
        """
        settings = get_settings()

        self.token = token or getattr(settings, "eqc_token", "")
        self.base_url = base_url or settings.eqc_base_url
        self.budget = budget if budget is not None else settings.company_sync_lookup_limit
        self.remaining_budget = self.budget
        self.mapping_repository = mapping_repository
        self._disabled = False
        self.client: Optional[EQCClient] = None

        # Log initialization (never log token)
        if not self.token:
            logger.warning(
                "eqc_provider.no_token_configured",
                msg="No EQC API token configured. Provider will return None for all lookups.",
            )

        # Optional token validation on init
        if validate_on_init and self.token:
            if not validate_eqc_token(self.token, self.base_url):
                raise EqcTokenInvalidError("EQC Token 无效或已过期")

        # Initialize EQC client (reuse hardened connector)
        if self.token:
            try:
                self.client = EQCClient(
                    token=self.token,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    retry_max=MAX_RETRIES,
                    base_url=self.base_url,
                    rate_limit=settings.eqc_rate_limit,
                )
            except EQCAuthenticationError:
                self._disabled = True
                logger.warning(
                    "eqc_provider.client_init_failed",
                    msg="EQC client authentication failed - disabling provider",
                )
            except Exception as e:
                self._disabled = True
                logger.warning(
                    "eqc_provider.client_init_failed",
                    error_type=type(e).__name__,
                )

        logger.info(
            "eqc_provider.initialized",
            budget=self.budget,
            has_token=bool(self.token),
            validate_on_init=validate_on_init,
        )

    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        """
        Look up company information from EQC API.

        Args:
            company_name: Company name to look up.

        Returns:
            CompanyInfo if found, None if not found or error.
        """
        # Check if provider is disabled (after 401)
        if self._disabled:
            logger.debug(
                "eqc_provider.disabled",
                msg="Provider disabled for session due to previous 401",
            )
            return None

        # Check budget
        if self.remaining_budget <= 0:
            logger.debug(
                "eqc_provider.budget_exhausted",
                msg="EQC sync budget exhausted",
                budget=self.budget,
            )
            return None

        # Check token
        if not self.token:
            logger.debug(
                "eqc_provider.no_token",
                msg="No API token configured",
            )
            return None

        # Make API call with retry
        result = self._call_api_with_retry(company_name)

        # Decrement budget regardless of result
        self.remaining_budget -= 1

        # Cache successful result
        if result and self.mapping_repository:
            self._cache_result(company_name, result)

        return result

    def _call_api_with_retry(self, company_name: str) -> Optional[CompanyInfo]:
        """
        Call EQC API with retry logic for network timeouts.

        Args:
            company_name: Company name to look up.

        Returns:
            CompanyInfo if found, None otherwise.
        """
        try:
            return self._call_api(company_name)
        except EQCAuthenticationError:
            logger.error(
                "eqc_provider.unauthorized",
                msg="EQC authentication failed - disabling provider",
            )
            self._disabled = True
            return None
        except EQCNotFoundError:
            logger.debug("eqc_provider.not_found")
            return None
        except EQCClientError as e:
            logger.warning(
                "eqc_provider.request_error",
                error_type=type(e).__name__,
            )
            return None
        except requests.Timeout:
            logger.warning(
                "eqc_provider.timeout",
                attempt=MAX_RETRIES,
                max_retries=MAX_RETRIES,
            )
            return None

    def _call_api(self, company_name: str) -> Optional[CompanyInfo]:
        """
        Make single API call to EQC search endpoint.

        Args:
            company_name: Company name to look up.

        Returns:
            CompanyInfo if found, None otherwise.
        """
        if not self.client:
            return None

        results = self.client.search_company(company_name)
        if not results:
            return None

        top = results[0]

        if not top.company_id or not top.official_name:
            logger.debug("eqc_provider.incomplete_result")
            return None

        return CompanyInfo(
            company_id=str(top.company_id),
            official_name=top.official_name,
            unified_credit_code=getattr(top, "unite_code", None),
            confidence=getattr(top, "match_score", 0.9) or 0.9,
            match_type="eqc",
        )

    def _cache_result(self, company_name: str, result: CompanyInfo) -> None:
        """
        Cache successful lookup result to database (non-blocking).

        Args:
            company_name: Original company name query.
            result: CompanyInfo from successful lookup.
        """
        try:
            from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
            from work_data_hub.infrastructure.enrichment.types import (
                EnrichmentIndexRecord, LookupType, SourceType
            )

            # Normalize using the same method as Layer 2 lookup for consistency
            normalized = normalize_for_temp_id(company_name) or company_name.strip()

            # Write to enterprise.enrichment_index with match_type=eqc (Epic 6.1)
            record = EnrichmentIndexRecord(
                lookup_key=normalized,
                lookup_type=LookupType.CUSTOMER_NAME,
                company_id=result.company_id,
                confidence=result.confidence,
                source=SourceType.EQC_API,
                source_domain="eqc_sync_lookup"
            )

            self.mapping_repository.insert_enrichment_index_batch([record])

            logger.debug(
                "eqc_provider.cached_result",
                msg="Cached EQC lookup result to enrichment_index",
            )
        except Exception:
            # Non-blocking: log and continue
            logger.warning(
                "eqc_provider.cache_failed",
                msg="Failed to cache EQC result - continuing without cache",
            )

    @property
    def is_available(self) -> bool:
        """
        Check if provider is available for lookups.

        Returns:
            True if provider has token, budget, and is not disabled.
        """
        return bool(self.token) and self.remaining_budget > 0 and not self._disabled

    def reset_budget(self) -> None:
        """Reset budget to initial value for new session."""
        self.remaining_budget = self.budget
        logger.debug(
            "eqc_provider.budget_reset",
            budget=self.budget,
        )

    def reset_disabled(self) -> None:
        """Re-enable provider after 401 (use with caution)."""
        self._disabled = False
        logger.debug("eqc_provider.re_enabled")
