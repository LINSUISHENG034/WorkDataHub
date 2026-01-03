"""
EQC Query Controller - Business logic for EQC query GUI.

Wraps EqcProvider for GUI interaction, handling:
- Token acquisition via auto_eqc_auth
- EQC API lookups with budget tracking
- Optional persistence to enrichment_index and base_info
"""

from dataclasses import dataclass
from typing import Optional

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.eqc_provider import (
    CompanyInfo,
    EqcProvider,
    validate_eqc_token,
)
from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr  # noqa: TID251
from work_data_hub.io.connectors.eqc.core import EQCClient  # noqa: TID251
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """Result of an EQC query for display in GUI."""

    success: bool
    company_id: Optional[str] = None
    official_name: Optional[str] = None
    unified_credit_code: Optional[str] = None
    confidence: Optional[float] = None
    match_type: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_company_info(cls, info: CompanyInfo) -> "QueryResult":
        """Create QueryResult from CompanyInfo."""
        return cls(
            success=True,
            company_id=info.company_id,
            official_name=info.official_name,
            unified_credit_code=info.unified_credit_code,
            confidence=info.confidence,
            match_type=info.match_type,
        )

    @classmethod
    def error(cls, message: str) -> "QueryResult":
        """Create error QueryResult."""
        return cls(success=False, error_message=message)


class EqcQueryController:
    """
    Controller for EQC query operations.

    Manages token acquisition, EQC lookups, and optional persistence.
    """

    def __init__(self) -> None:
        """
        Initialize controller.

        Note: Persistence is disabled during lookup. Use save_last_result() to
        manually save after reviewing results.
        """
        self._token: Optional[str] = None
        self._provider: Optional[EqcProvider] = None
        self._client: Optional[EQCClient] = None
        self._repository = None
        # Cache last result for manual save (Story 7.x: ALL three raw JSON)
        self._last_result: Optional[CompanyInfo] = None
        self._last_raw_search: Optional[dict] = None  # search API response
        self._last_raw_business_info: Optional[dict] = None  # findDepart API response
        self._last_raw_biz_label: Optional[dict] = None  # findLabels API response
        self._last_keyword: Optional[str] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if token is available."""
        return bool(self._token)

    @property
    def remaining_budget(self) -> int:
        """Get remaining API call budget."""
        if self._provider:
            return self._provider.remaining_budget
        return 0

    @property
    def total_budget(self) -> int:
        """Get total API call budget."""
        if self._provider:
            return self._provider.budget
        return 0

    def try_load_existing_token(self) -> bool:
        """
        Try to load and validate existing token from settings.

        This allows skipping QR code authentication if a valid token already exists.

        Returns:
            True if existing token is valid and loaded, False otherwise.
        """
        logger.info("eqc_query_controller.try_load_existing_token.started")
        try:
            settings = get_settings()
            existing_token = getattr(settings, "eqc_token", None)

            if not existing_token:
                logger.info(
                    "eqc_query_controller.try_load_existing_token.no_token",
                    msg="No existing token found in settings",
                )
                return False

            # Validate the existing token
            base_url = settings.eqc_base_url
            is_valid = validate_eqc_token(existing_token, base_url)

            if is_valid:
                self._token = existing_token
                self._initialize_provider()
                logger.info(
                    "eqc_query_controller.try_load_existing_token.success",
                    msg="Existing token validated and loaded",
                )
                return True
            else:
                logger.warning(
                    "eqc_query_controller.try_load_existing_token.invalid",
                    msg="Existing token is invalid or expired",
                )
                return False
        except Exception as e:
            logger.warning(
                "eqc_query_controller.try_load_existing_token.failed",
                error_type=type(e).__name__,
            )
            return False

    def authenticate(self) -> bool:
        """
        Acquire EQC token via QR code scan.

        Returns:
            True if authentication successful, False otherwise.
        """
        logger.info("eqc_query_controller.authenticate.started")
        try:
            token = run_get_token_auto_qr(save_to_env=True)
            if token:
                self._token = token
                self._initialize_provider()
                logger.info("eqc_query_controller.authenticate.success")
                return True
            logger.warning("eqc_query_controller.authenticate.no_token")
            return False
        except Exception as e:
            logger.error(
                "eqc_query_controller.authenticate.failed",
                error_type=type(e).__name__,
            )
            return False

    def _initialize_provider(self) -> None:
        """Initialize EqcProvider WITHOUT auto-persistence for manual save."""
        if not self._token:
            return

        # Initialize repository for manual save
        try:
            from sqlalchemy import create_engine

            from work_data_hub.infrastructure.enrichment.mapping_repository import (
                CompanyMappingRepository,
            )

            settings = get_settings()
            engine = create_engine(settings.get_database_connection_string())
            connection = engine.connect()
            self._repository = CompanyMappingRepository(connection)
            logger.info("eqc_query_controller.repository.initialized")
        except Exception as e:
            logger.warning(
                "eqc_query_controller.repository.init_failed",
                msg="Manual save will not be available",
                error_type=type(e).__name__,
            )

        # Initialize provider WITHOUT mapping_repository to disable auto-save
        self._provider = EqcProvider(
            token=self._token,
            mapping_repository=None,  # Disable auto-persistence
        )

        # Initialize EQC client for direct company_id lookups
        settings = get_settings()
        self._client = EQCClient(
            token=self._token,
            timeout=5,
            retry_max=2,
            base_url=settings.eqc_base_url,
        )

        logger.info(
            "eqc_query_controller.provider.initialized",
            budget=self._provider.budget,
            auto_persistence=False,
        )

    def lookup(self, keyword: str) -> QueryResult:
        """
        Look up company by keyword (name search).

        Captures ALL three raw API responses for complete base_info persistence:
        - raw_data: search API response
        - raw_business_info: findDepart API response
        - raw_biz_label: findLabels API response

        Results are NOT auto-saved. Use save_last_result() after reviewing.

        Args:
            keyword: Company name or keyword to search.

        Returns:
            QueryResult with company information or error.
        """
        if not keyword.strip():
            return QueryResult.error("请输入查询关键字")

        if not self._provider:
            return QueryResult.error("请先登录获取 Token")

        if self._provider.remaining_budget <= 0:
            return QueryResult.error("API 调用次数已用完，请重新登录")

        logger.info("eqc_query_controller.lookup.started", keyword=keyword)
        try:
            # Step 1: Search API (get raw_data)
            results, raw_search_json = self._client.search_company_with_raw(
                keyword.strip()
            )
            if not results:
                logger.info("eqc_query_controller.lookup.not_found")
                return QueryResult.error(f"未找到匹配的企业信息: {keyword}")

            top = results[0]
            company_id = str(top.company_id) if top.company_id else None
            if not company_id:
                logger.info("eqc_query_controller.lookup.no_company_id")
                return QueryResult.error(f"查询结果缺少 company_id: {keyword}")

            # Step 2: Get business info (get raw_business_info)
            raw_business_info = None
            try:
                _, raw_business_info = self._client.get_business_info_with_raw(
                    company_id
                )
                logger.debug(
                    "eqc_query_controller.lookup.business_info_acquired",
                    company_id=company_id,
                )
            except Exception as e:
                logger.warning(
                    "eqc_query_controller.lookup.business_info_failed",
                    msg="Failed to get business info - continuing without it",
                    company_id=company_id,
                    error_type=type(e).__name__,
                )

            # Step 3: Get label info (get raw_biz_label)
            raw_biz_label = None
            try:
                _, raw_biz_label = self._client.get_label_info_with_raw(company_id)
                logger.debug(
                    "eqc_query_controller.lookup.label_info_acquired",
                    company_id=company_id,
                )
            except Exception as e:
                logger.warning(
                    "eqc_query_controller.lookup.label_info_failed",
                    msg="Failed to get label info - continuing without it",
                    company_id=company_id,
                    error_type=type(e).__name__,
                )

            # Decrement budget manually (since we bypassed provider.lookup)
            self._provider.remaining_budget -= 1

            # Create CompanyInfo result
            result = CompanyInfo(
                company_id=company_id,
                official_name=top.official_name,
                unified_credit_code=getattr(top, "unite_code", None),
                confidence=top.confidence if hasattr(top, "confidence") else 1.0,
                match_type=getattr(top, "match_type", "eqc"),
            )

            # Cache ALL three raw JSON for manual save
            self._last_result = result
            self._last_keyword = keyword.strip()
            self._last_raw_search = raw_search_json
            self._last_raw_business_info = raw_business_info
            self._last_raw_biz_label = raw_biz_label

            logger.info(
                "eqc_query_controller.lookup.success",
                company_id=result.company_id,
                confidence=result.confidence,
                has_raw_search=raw_search_json is not None,
                has_raw_business_info=raw_business_info is not None,
                has_raw_biz_label=raw_biz_label is not None,
            )
            return QueryResult.from_company_info(result)
        except Exception as e:
            logger.error(
                "eqc_query_controller.lookup.failed",
                error_type=type(e).__name__,
            )
            return QueryResult.error(f"查询失败: {e!s}")

    def lookup_by_id(self, company_id: str) -> QueryResult:
        """
        Look up company by company_id directly.

        Captures ALL three raw API responses for complete base_info persistence:
        - raw_data: Uses findDepart response as fallback (no search API call needed)
        - raw_business_info: findDepart API response
        - raw_biz_label: findLabels API response

        Strategy (Solution C): When querying by company_id directly, we skip the
        search API call and use the findDepart response as raw_data. This ensures
        data consistency since we don't risk storing mismatched search results
        from a reverse name lookup.

        Args:
            company_id: EQC company ID (numeric string).

        Returns:
            QueryResult with company information or error.
        """
        if not company_id.strip():
            return QueryResult.error("请输入 Company ID")

        if not self._client:
            return QueryResult.error("请先登录获取 Token")

        logger.info("eqc_query_controller.lookup_by_id.started", company_id=company_id)
        try:
            # Step 1: Get business info with raw response
            business_info, raw_business_info = self._client.get_business_info_with_raw(
                company_id.strip()
            )
            if not business_info:
                logger.info("eqc_query_controller.lookup_by_id.not_found")
                return QueryResult.error(f"未找到 Company ID: {company_id}")

            # Step 2: Get label info with raw response
            raw_biz_label = None
            try:
                _, raw_biz_label = self._client.get_label_info_with_raw(
                    business_info.company_id
                )
                logger.debug(
                    "eqc_query_controller.lookup_by_id.label_info_acquired",
                    company_id=business_info.company_id,
                )
            except Exception as e:
                logger.warning(
                    "eqc_query_controller.lookup_by_id.label_info_failed",
                    msg="Failed to get label info - continuing without it",
                    company_id=business_info.company_id,
                    error_type=type(e).__name__,
                )

            # Solution C: Use findDepart response as raw_data fallback
            # This avoids the unreliable reverse name search that could return
            # mismatched results (e.g., different company with same name).
            # The findDepart response contains all essential company info fields.
            raw_search_json = raw_business_info  # Use findDepart as raw_data source

            logger.debug(
                "eqc_query_controller.lookup_by_id.using_finddepart_as_raw_data",
                company_id=business_info.company_id,
                msg="Using findDepart response as raw_data (Solution C)",
            )

            # Create CompanyInfo from BusinessInfoResult
            # Note: BusinessInfoResult uses company_name/credit_code,
            # not official_name/unite_code
            result = CompanyInfo(
                company_id=business_info.company_id,
                official_name=business_info.company_name,
                unified_credit_code=business_info.credit_code,
                confidence=1.0,  # Direct ID lookup = full confidence
                match_type="direct_id",
            )

            # Cache ALL three raw JSON for manual save
            # Note: _last_raw_search now contains findDepart response (Solution C)
            self._last_result = result
            self._last_keyword = company_id.strip()
            self._last_raw_search = raw_search_json  # findDepart response
            self._last_raw_business_info = raw_business_info
            self._last_raw_biz_label = raw_biz_label

            logger.info(
                "eqc_query_controller.lookup_by_id.success",
                company_id=result.company_id,
                raw_data_source="findDepart",  # Indicate source for debugging
                has_raw_data=raw_search_json is not None,
                has_raw_business_info=raw_business_info is not None,
                has_raw_biz_label=raw_biz_label is not None,
            )
            return QueryResult.from_company_info(result)
        except Exception as e:
            logger.error(
                "eqc_query_controller.lookup_by_id.failed",
                error_type=type(e).__name__,
            )
            return QueryResult.error(f"查询失败: {e!s}")

    def save_last_result(self) -> bool:
        """
        Save the last lookup result to database.

        Writes ALL three raw API responses to base_info for ETL consistency:
        - raw_data: search API response (keyword lookup) OR findDepart response (ID lookup)
        - raw_business_info: findDepart API response
        - raw_biz_label: findLabels API response

        Solution C Implementation:
        - For keyword lookup: raw_data contains search API response (same as ETL)
        - For ID lookup: raw_data contains findDepart response as fallback
          This ensures data consistency by avoiding unreliable reverse name searches.

        Note: lookup_key and search_key_word always use official_name (公司全称)
        to ensure consistent cache hits regardless of how the company was found.

        Returns:
            True if saved successfully, False otherwise.
        """
        if not self._last_result:
            logger.warning("eqc_query_controller.save.no_result")
            return False

        if not self._repository:
            logger.warning("eqc_query_controller.save.no_repository")
            return False

        try:
            from decimal import Decimal

            from work_data_hub.infrastructure.enrichment.base_info_parser import (
                BaseInfoParser,
            )
            from work_data_hub.infrastructure.enrichment.normalizer import (
                normalize_for_temp_id,
            )
            from work_data_hub.infrastructure.enrichment.types import (
                EnrichmentIndexRecord,
                LookupType,
                SourceType,
            )

            result = self._last_result

            # Always use official_name for lookup_key to ensure cache consistency
            # This prevents writing company_id as lookup_key when searching by ID
            company_name = result.official_name
            if not company_name:
                logger.warning("eqc_query_controller.save.no_official_name")
                return False

            # Normalize for cache
            normalized = normalize_for_temp_id(company_name) or company_name.strip()

            # Get raw responses (initialized in __init__)
            raw_search = self._last_raw_search
            raw_business_info = self._last_raw_business_info
            raw_biz_label = self._last_raw_biz_label

            # Parse fields using BaseInfoParser based on lookup method
            parsed = None
            try:
                if result.match_type == "direct_id":
                    # Direct ID lookup: use findDepart parser
                    if raw_business_info:
                        parsed = BaseInfoParser.parse_from_find_depart_response(
                            raw_business_info=raw_business_info,
                            search_key_word=company_name,
                        )
                # Keyword lookup: use Search parser
                elif raw_search:
                    parsed = BaseInfoParser.parse_from_search_response(
                        raw_json=raw_search,
                        raw_business_info=raw_business_info,
                        search_key_word=self._last_keyword or company_name,
                    )
            except Exception as e:
                logger.warning(
                    "eqc_query_controller.save.parse_failed",
                    msg="Failed to parse raw response - falling back to basic fields",
                    error_type=type(e).__name__,
                )

            # Create enrichment record with company name as lookup_key
            record = EnrichmentIndexRecord(
                lookup_key=normalized,
                lookup_type=LookupType.CUSTOMER_NAME,
                company_id=result.company_id,
                confidence=Decimal(str(result.confidence)),
                source=SourceType.EQC_API,
                source_domain="eqc_gui_manual",
            )

            self._repository.insert_enrichment_index_batch([record])

            # Write former names to enrichment_index (DB-P6) with conflict detection
            if parsed and parsed.company_former_name:
                self._write_former_names_to_enrichment_index(
                    former_names_str=parsed.company_former_name,
                    company_id=result.company_id,
                    base_confidence=result.confidence,
                )

            # Save to base_info with ALL three raw API responses + parsed fields
            # Use build_upsert_kwargs helper to avoid code duplication
            from work_data_hub.infrastructure.enrichment.base_info_parser import (
                build_upsert_kwargs,
            )

            fallback_source = (
                "direct_id" if result.match_type == "direct_id" else "search"
            )
            upsert_kwargs = build_upsert_kwargs(
                parsed, fallback_data_source=fallback_source
            )

            self._repository.upsert_base_info(
                company_id=result.company_id,
                search_key_word=company_name,
                company_full_name=company_name,
                unite_code=result.unified_credit_code,
                raw_data=raw_search,
                raw_business_info=raw_business_info,
                raw_biz_label=raw_biz_label,
                **upsert_kwargs,
            )

            # Commit the transaction to persist changes
            self._repository.connection.commit()

            # Log with all three raw data flags
            logger.info(
                "eqc_query_controller.save.success",
                company_id=result.company_id,
                lookup_key=normalized,
                data_source=parsed.data_source if parsed else result.match_type,
                has_raw_data=raw_search is not None,
                has_raw_business_info=raw_business_info is not None,
                has_raw_biz_label=raw_biz_label is not None,
                has_former_names=bool(parsed and parsed.company_former_name),
            )
            return True
        except Exception as e:
            logger.error(
                "eqc_query_controller.save.failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            return False

    @property
    def can_save(self) -> bool:
        """Check if there is a result that can be saved."""
        has_result = self._last_result is not None
        has_repo = self._repository is not None
        logger.debug(
            "eqc_query_controller.can_save.check",
            has_result=has_result,
            has_repository=has_repo,
        )
        return has_result and has_repo

    def reset_budget(self) -> None:
        """Reset API call budget for new session."""
        if self._provider:
            self._provider.reset_budget()
            logger.info("eqc_query_controller.budget.reset")

    def close(self) -> None:
        """Clean up resources."""
        if self._repository:
            try:
                if hasattr(self._repository, "connection"):
                    self._repository.connection.close()
            except Exception:
                pass

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

        from work_data_hub.infrastructure.enrichment.normalizer import (
            normalize_for_temp_id,
        )
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
                source_domain="eqc_gui_former_name",
            )
            records.append(record)

        if records:
            # Use conflict-aware insert for former names
            result = self._repository.insert_former_name_with_conflict_check(records)
            logger.info(
                "eqc_query_controller.save.former_names_written",
                company_id=company_id,
                total_names=len(records),
                inserted=result.inserted_count,
                skipped=result.skipped_count,
                conflicts=len(result.conflicts) if result.conflicts else 0,
            )
