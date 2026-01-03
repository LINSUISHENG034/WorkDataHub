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
from http import HTTPStatus
from typing import TYPE_CHECKING, Optional, Protocol

import requests

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.io.connectors.eqc_client import (  # noqa: TID251 - Infrastructure needs EQC client
    EQCAuthenticationError,
    EQCClient,
    EQCClientError,
    EQCNotFoundError,
)
from work_data_hub.utils.logging import get_logger

if TYPE_CHECKING:
    from work_data_hub.infrastructure.enrichment.eqc_confidence_config import (
        EQCConfidenceConfig,
    )
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
            f"{message}\n\n请运行以下命令更新 Token:\n  {self.help_command}"
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

    Story 6.2-P16 AC-3: Adds diagnostic logging (status codes + decision),
    without ever logging the token or response body.

    Args:
        token: EQC API token to validate.
        base_url: EQC API base URL.

    Returns:
        True if token is valid, False if invalid (401) or network error.
    """
    endpoint_path = "/kg-api-hfd/api/search/searchAll"
    url = f"{base_url.rstrip('/')}{endpoint_path}"
    params = {"keyword": "test", "currentPage": 1, "pageSize": 1}

    logger.info(
        "eqc.token_validation.started",
        base_url=base_url,
        endpoint=endpoint_path,
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    )
    try:
        response = requests.get(
            url,
            params=params,
            headers={"token": token},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        elapsed_seconds = None
        try:
            elapsed_seconds = response.elapsed.total_seconds()
        except Exception:
            pass

        logger.info(
            "eqc.token_validation.response",
            status_code=response.status_code,
            elapsed_seconds=elapsed_seconds,
        )
        if response.status_code == HTTPStatus.OK:
            logger.info("eqc.token_validation.result", valid=True, reason="http_200")
            return True
        # 401/403 are strong signals that the token/session is not usable.
        if response.status_code in {401, 403}:
            logger.warning(
                "eqc.token_validation.result",
                valid=False,
                reason="http_auth_error",
                status_code=response.status_code,
            )
            return False
        # Other errors (e.g., transient 5xx) don't prove token invalidity.
        logger.warning(
            "eqc.token_validation.result",
            valid=True,
            reason="non_auth_http_error_assume_valid",
            status_code=response.status_code,
        )
        return True
    except requests.RequestException as e:
        # Network errors don't indicate token invalidity (but log it for diagnosis)
        logger.warning(
            "eqc.token_validation.request_error_assume_valid",
            error=str(e),
            exc_info=True,
        )
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
        eqc_confidence_config: Optional["EQCConfidenceConfig"] = None,
    ) -> None:
        """
        Initialize EqcProvider.

        Args:
            token: EQC API token. If None, loads from settings.
            budget: Maximum API calls per session. If None, uses settings default.
            base_url: EQC API base URL. If None, uses settings default.
            mapping_repository: Optional repository for caching results.
            validate_on_init: If True, validate token on initialization.
            eqc_confidence_config: Optional config for match type confidence scoring.

        Raises:
            EqcTokenInvalidError: If validate_on_init=True and token is invalid.
        """
        settings = get_settings()

        self.token = token or getattr(settings, "eqc_token", "")
        self.base_url = base_url or settings.eqc_base_url
        self.budget = (
            budget if budget is not None else settings.company_sync_lookup_limit
        )
        self.remaining_budget = self.budget
        self.mapping_repository = mapping_repository
        self._disabled = False
        self.client: Optional[EQCClient] = None

        # Story 7.1-8: Load EQC confidence config for dynamic confidence scoring
        if eqc_confidence_config is None:
            from work_data_hub.infrastructure.enrichment.eqc_confidence_config import (
                EQCConfidenceConfig,
            )

            self.eqc_confidence_config = EQCConfidenceConfig.load_from_yaml()
        else:
            self.eqc_confidence_config = eqc_confidence_config

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
        result, raw_json = self._call_api_with_retry(company_name)

        # Decrement budget regardless of result
        self.remaining_budget -= 1

        # Cache successful result
        if result and self.mapping_repository:
            self._cache_result(company_name, result, raw_json)

        return result

    def _call_api_with_retry(
        self, company_name: str
    ) -> tuple[Optional[CompanyInfo], Optional[dict]]:
        """
        Call EQC API with retry logic for network timeouts.

        Args:
            company_name: Company name to look up.

        Returns:
            Tuple of (CompanyInfo, raw_json) if found, (None, None) otherwise.
        """
        try:
            return self._call_api(company_name)
        except EQCAuthenticationError:
            logger.error(
                "eqc_provider.unauthorized",
                msg="EQC authentication failed - disabling provider",
            )
            self._disabled = True
            return None, None
        except EQCNotFoundError:
            logger.debug("eqc_provider.not_found")
            return None, None
        except EQCClientError as e:
            logger.warning(
                "eqc_provider.request_error",
                error_type=type(e).__name__,
            )
            return None, None
        except requests.Timeout:
            logger.warning(
                "eqc_provider.timeout",
                attempt=MAX_RETRIES,
                max_retries=MAX_RETRIES,
            )
            return None, None

    def _call_api(
        self, company_name: str
    ) -> tuple[Optional[CompanyInfo], Optional[dict]]:
        """
        Make API calls to EQC search, findDepart, and findLabels endpoints.

        Story 6.2-P8: Orchestrate all 3 API calls to acquire complete enterprise data.

        Args:
            company_name: Company name to look up.

        Returns:
            Tuple of (CompanyInfo, raw_search_json) if found, (None, None) otherwise.
            Additional raw responses (business_info, labels) are passed via
            _cache_result.
        """
        if not self.client:
            return None, None

        # Step 1: Search for company
        # Use search_company_with_raw to get both parsed results and raw JSON
        results, raw_search_json = self.client.search_company_with_raw(company_name)
        if not results:
            return None, None

        top = results[0]

        if not top.company_id or not top.official_name:
            logger.debug("eqc_provider.incomplete_result")
            return None, None

        # Story 7.1-8: Extract match type and get dynamic confidence
        company_id = str(top.company_id)
        eqc_match_quality = _extract_match_type_from_raw_json(raw_search_json)
        confidence = self.eqc_confidence_config.get_confidence_for_match_type(
            eqc_match_quality
        )

        # Step 2: Get additional data (findDepart and findLabels)
        # Store these as instance variables for _cache_result to use
        self._raw_business_info = None
        self._raw_biz_label = None

        # Error isolation: Try to get business info, but continue if it fails
        try:
            _, self._raw_business_info = self.client.get_business_info_with_raw(
                company_id
            )
            logger.debug(
                "eqc_provider.business_info_acquired",
                company_id=company_id,
            )
        except Exception as e:
            logger.warning(
                "eqc_provider.business_info_failed",
                msg="Failed to get business info - continuing without it",
                company_id=company_id,
                error_type=type(e).__name__,
            )

        # Error isolation: Try to get label info, but continue if it fails
        try:
            _, self._raw_biz_label = self.client.get_label_info_with_raw(company_id)
            logger.debug(
                "eqc_provider.label_info_acquired",
                company_id=company_id,
            )
        except Exception as e:
            logger.warning(
                "eqc_provider.label_info_failed",
                msg="Failed to get label info - continuing without it",
                company_id=company_id,
                error_type=type(e).__name__,
            )

        # Create CompanyInfo with dynamic confidence (Story 7.1-8)
        company_info = CompanyInfo(
            company_id=company_id,
            official_name=top.official_name,
            unified_credit_code=getattr(top, "unite_code", None),
            confidence=confidence,  # Dynamic based on eqc_match_quality
            match_type="eqc",  # Source type (unchanged)
        )

        return company_info, raw_search_json

    def _cache_result(
        self,
        company_name: str,
        result: CompanyInfo,
        raw_json: Optional[dict] = None,
    ) -> None:
        """
        Cache successful lookup result to database (non-blocking).

        Writes to both:
        1. enterprise.enrichment_index (Epic 6.1 cache)
        2. enterprise.base_info (Story 6.2-P5 persistence with parsed fields)

        Args:
            company_name: Original company name query.
            result: CompanyInfo from successful lookup.
            raw_json: Raw API response for persistence (Story 6.2-P5).
        """
        try:
            from work_data_hub.infrastructure.enrichment.base_info_parser import (
                BaseInfoParser,
                build_upsert_kwargs,
            )
            from work_data_hub.infrastructure.enrichment.types import (
                EnrichmentIndexRecord,
                LookupType,
                SourceType,
            )

            # Normalize using the same method as Layer 2 lookup for consistency
            normalized = normalize_for_temp_id(company_name) or company_name.strip()

            # Parse fields from raw responses using BaseInfoParser
            raw_business_info = getattr(self, "_raw_business_info", None)
            raw_biz_label = getattr(self, "_raw_biz_label", None)

            parsed = None
            if raw_json is not None:
                try:
                    parsed = BaseInfoParser.parse_from_search_response(
                        raw_json=raw_json,
                        raw_business_info=raw_business_info,
                        search_key_word=company_name,
                    )
                except Exception as e:
                    logger.warning(
                        "eqc_provider.parse_failed",
                        msg="Failed to parse raw response - falling back to "
                        "basic fields",
                        error_type=type(e).__name__,
                    )

            # Story 7.1-8: Check minimum confidence threshold before caching
            if result.confidence < self.eqc_confidence_config.min_confidence_for_cache:
                logger.info(
                    "eqc_provider.cache_skipped_low_confidence",
                    msg="EQC result below confidence threshold, not cached",
                    confidence=result.confidence,
                    threshold=self.eqc_confidence_config.min_confidence_for_cache,
                )
                # Still write to base_info for persistence (Story 6.2-P5)
                # But skip enrichment_index cache
                if raw_json is not None and self.mapping_repository:
                    try:
                        upsert_kwargs = build_upsert_kwargs(parsed)
                        self.mapping_repository.upsert_base_info(
                            company_id=result.company_id,
                            search_key_word=company_name,
                            company_full_name=result.official_name,
                            unite_code=result.unified_credit_code,
                            raw_data=raw_json,
                            raw_business_info=raw_business_info,
                            raw_biz_label=raw_biz_label,
                            **upsert_kwargs,
                        )
                        logger.debug(
                            "eqc_provider.persisted_to_base_info_only",
                            msg="Persisted EQC result to base_info only (below "
                            "cache threshold)",
                        )
                    except Exception as e:
                        logger.warning(
                            "eqc_provider.base_info_persistence_failed",
                            msg="Failed to persist to base_info - continuing without "
                            "persistence",
                            error_type=type(e).__name__,
                        )
                return

            # Write to enterprise.enrichment_index with match_type=eqc (Epic 6.1)
            record = EnrichmentIndexRecord(
                lookup_key=normalized,
                lookup_type=LookupType.CUSTOMER_NAME,
                company_id=result.company_id,
                confidence=result.confidence,
                source=SourceType.EQC_API,
                source_domain="eqc_sync_lookup",
            )

            self.mapping_repository.insert_enrichment_index_batch([record])

            # Write former names to enrichment_index (DB-P6) with conflict detection
            if parsed and parsed.company_former_name:
                self._write_former_names_to_enrichment_index(
                    former_names_str=parsed.company_former_name,
                    company_id=result.company_id,
                    base_confidence=result.confidence,
                )

            logger.debug(
                "eqc_provider.cached_result",
                msg="Cached EQC lookup result to enrichment_index",
            )

            # Story 6.2-P5/P8: Write to enterprise.base_info with all raw API responses
            # Now includes parsed fields from BaseInfoParser
            if raw_json is not None and self.mapping_repository:
                try:
                    upsert_kwargs = build_upsert_kwargs(parsed)
                    self.mapping_repository.upsert_base_info(
                        company_id=result.company_id,
                        search_key_word=company_name,
                        company_full_name=result.official_name,
                        unite_code=result.unified_credit_code,
                        raw_data=raw_json,
                        raw_business_info=raw_business_info,
                        raw_biz_label=raw_biz_label,
                        **upsert_kwargs,
                    )
                    logger.debug(
                        "eqc_provider.persisted_to_base_info",
                        msg="Persisted EQC result to base_info table with parsed fields",
                    )
                except Exception as e:
                    # Non-blocking: log and continue
                    logger.warning(
                        "eqc_provider.base_info_persistence_failed",
                        msg="Failed to persist to base_info - continuing without persistence",
                        error_type=type(e).__name__,
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

    def _write_former_names_to_enrichment_index(
        self,
        former_names_str: str,
        company_id: str,
        base_confidence: float,
    ) -> None:
        """
        Split and write company former names to enrichment_index.

        Uses conflict-aware insert to handle cases where the same former name
        is used by multiple companies (deletes on conflict).

        Args:
            former_names_str: Comma-separated former company names.
            company_id: Company ID to associate with these former names.
            base_confidence: Base confidence score (will be multiplied by 0.9).
        """
        from decimal import Decimal

        from work_data_hub.infrastructure.enrichment.types import (
            EnrichmentIndexRecord,
            LookupType,
            SourceType,
        )

        # Split comma-separated former names
        former_names = [n.strip() for n in former_names_str.split(",") if n.strip()]

        if not former_names:
            return

        records = []
        for name in former_names:
            normalized = normalize_for_temp_id(name) or name.strip()
            if not normalized:
                continue

            # Use 0.9x confidence for former names
            record = EnrichmentIndexRecord(
                lookup_key=normalized,
                lookup_type=LookupType.FORMER_NAME,
                company_id=company_id,
                confidence=Decimal(str(base_confidence * 0.9)),
                source=SourceType.EQC_API,
                source_domain="eqc_sync_former_name",
            )
            records.append(record)

        if records and self.mapping_repository:
            # Use conflict-aware insert for former names
            result = self.mapping_repository.insert_former_name_with_conflict_check(
                records
            )
            logger.debug(
                "eqc_provider.former_names_cached",
                company_id=company_id,
                total_names=len(records),
                inserted=result.inserted_count,
                skipped=result.skipped_count,
                conflicts=len(result.conflicts) if result.conflicts else 0,
            )


def _extract_match_type_from_raw_json(raw_json: Optional[dict]) -> str:
    """
    Extract EQC match quality from raw API response (Story 7.1-8).

    The EQC API returns results with a 'type' field indicating match quality:
    - 全称精确匹配 (exact full name match) - highest reliability
    - 模糊匹配 (fuzzy match) - medium reliability
    - 拼音 (pinyin match) - lowest reliability

    Example raw_json structure:
    {"list": [{"type": "全称精确匹配", "name": "公司全称", ...}]}

    Args:
        raw_json: Raw API response from EQC search endpoint.

    Returns:
        EQC match quality string, or "default" if not found.
    """
    if not raw_json or not isinstance(raw_json, dict):
        return "default"

    results = raw_json.get("list", [])
    if not results or not isinstance(results, list):
        return "default"

    first_result = results[0]
    if not isinstance(first_result, dict):
        return "default"

    return first_result.get("type", "default")
