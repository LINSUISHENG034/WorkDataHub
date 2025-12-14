"""
EQC Data Refresh Service for maintaining data freshness.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 2.2: Service for refreshing enterprise data based on existing company_ids

This service provides:
- Staleness detection based on configurable threshold
- Batch refresh operations with rate limiting
- Progress tracking and error handling
"""

import json
import time
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import Connection, text

from work_data_hub.config.settings import get_settings
from work_data_hub.io.connectors.eqc_client import EQCClient, EQCClientError
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StaleCompanyInfo:
    """
    Information about a company with stale data.

    Attributes:
        company_id: EQC company ID.
        company_full_name: Official company name.
        updated_at: Last update timestamp (None if never updated).
        days_since_update: Days since last update (None if never updated).
    """

    company_id: str
    company_full_name: str
    updated_at: Optional[str]
    days_since_update: Optional[int]


@dataclass
class FreshnessStatus:
    """
    Overall data freshness statistics.

    Attributes:
        total_companies: Total number of companies in base_info.
        fresh_companies: Companies with data within threshold.
        stale_companies: Companies with data older than threshold.
        never_updated: Companies with NULL updated_at.
        threshold_days: Configured freshness threshold.
    """

    total_companies: int
    fresh_companies: int
    stale_companies: int
    never_updated: int
    threshold_days: int


@dataclass
class RefreshResult:
    """
    Result of a refresh operation.

    Attributes:
        total_requested: Total companies requested for refresh.
        successful: Number of successful refreshes.
        failed: Number of failed refreshes.
        skipped: Number of skipped companies.
        errors: List of error messages for failed refreshes.
    """

    total_requested: int
    successful: int
    failed: int
    skipped: int
    errors: List[str]


class EqcDataRefreshService:
    """
    Service for refreshing enterprise data based on existing company_ids.

    This service manages data freshness by:
    - Detecting stale data based on configurable threshold
    - Refreshing data from EQC API with rate limiting
    - Tracking progress and handling errors gracefully

    Attributes:
        connection: SQLAlchemy Connection for database operations.
        eqc_client: EQC API client for data retrieval.
        repository: Repository for database operations.
        settings: Application settings.

    Example:
        >>> from sqlalchemy import create_engine
        >>> engine = create_engine(database_url)
        >>> with engine.connect() as conn:
        ...     service = EqcDataRefreshService(conn)
        ...     status = service.get_freshness_status()
        ...     print(f"Stale companies: {status.stale_companies}")
    """

    def __init__(
        self,
        connection: Connection,
        eqc_client: Optional[EQCClient] = None,
    ) -> None:
        """
        Initialize EqcDataRefreshService.

        Args:
            connection: SQLAlchemy Connection. Caller owns transaction lifecycle.
            eqc_client: Optional EQC client. If None, creates default client.
        """
        self.connection = connection
        self.repository = CompanyMappingRepository(connection)
        self.settings = get_settings()

        # Initialize EQC client if not provided
        if eqc_client is None:
            self.eqc_client = EQCClient(
                token=self.settings.eqc_token,
                timeout=self.settings.eqc_timeout,
                retry_max=self.settings.eqc_retry_max,
                base_url=self.settings.eqc_base_url,
                rate_limit=int(self.settings.eqc_data_refresh_rate_limit * 60),  # Convert to requests per minute
            )
        else:
            self.eqc_client = eqc_client

        logger.info(
            "data_refresh_service.initialized",
            threshold_days=self.settings.eqc_data_freshness_threshold_days,
            batch_size=self.settings.eqc_data_refresh_batch_size,
            rate_limit=self.settings.eqc_data_refresh_rate_limit,
        )

    def get_freshness_status(
        self,
        threshold_days: Optional[int] = None,
    ) -> FreshnessStatus:
        """
        Get overall data freshness statistics.

        Args:
            threshold_days: Custom threshold in days. If None, uses settings default.

        Returns:
            FreshnessStatus with overall statistics.

        Example:
            >>> status = service.get_freshness_status()
            >>> print(f"Total: {status.total_companies}")
            >>> print(f"Stale: {status.stale_companies}")
        """
        if threshold_days is None:
            threshold_days = self.settings.eqc_data_freshness_threshold_days

        query = text("""
            SELECT
                COUNT(*) AS total_companies,
                COUNT(*) FILTER (
                    WHERE updated_at IS NOT NULL
                      AND updated_at >= NOW() - INTERVAL '1 day' * :threshold_days
                ) AS fresh_companies,
                COUNT(*) FILTER (
                    WHERE updated_at IS NOT NULL
                      AND updated_at < NOW() - INTERVAL '1 day' * :threshold_days
                ) AS stale_companies,
                COUNT(*) FILTER (
                    WHERE updated_at IS NULL
                ) AS never_updated
            FROM enterprise.base_info
        """)

        result = self.connection.execute(
            query,
            {"threshold_days": threshold_days},
        )
        row = result.fetchone()

        status = FreshnessStatus(
            total_companies=row.total_companies,
            fresh_companies=row.fresh_companies,
            stale_companies=row.stale_companies,
            never_updated=row.never_updated,
            threshold_days=threshold_days,
        )

        logger.info(
            "data_refresh_service.freshness_status",
            total=status.total_companies,
            fresh=status.fresh_companies,
            stale=status.stale_companies,
            never_updated=status.never_updated,
            threshold_days=threshold_days,
        )

        return status

    def get_stale_companies(
        self,
        threshold_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[StaleCompanyInfo]:
        """
        Get list of companies with stale data.

        Returns companies where:
        - updated_at is NULL (never refreshed), OR
        - updated_at < NOW() - threshold_days

        Args:
            threshold_days: Custom threshold in days. If None, uses settings default.
            limit: Maximum number of companies to return. If None, returns all.

        Returns:
            List of StaleCompanyInfo for companies with stale data.

        Example:
            >>> stale = service.get_stale_companies(limit=10)
            >>> for company in stale:
            ...     print(f"{company.company_id}: {company.days_since_update} days")
        """
        if threshold_days is None:
            threshold_days = self.settings.eqc_data_freshness_threshold_days

        query_text = """
            SELECT
                company_id,
                "companyFullName" AS company_full_name,
                updated_at,
                CASE
                    WHEN updated_at IS NULL THEN NULL
                    ELSE EXTRACT(DAY FROM NOW() - updated_at)::INTEGER
                END AS days_since_update
            FROM enterprise.base_info
            WHERE updated_at IS NULL
               OR updated_at < NOW() - INTERVAL '1 day' * :threshold_days
            ORDER BY updated_at ASC NULLS FIRST
        """

        # Use parameterized query for LIMIT to prevent SQL injection
        if limit is not None:
            query_text += " LIMIT :limit"

        query = text(query_text)

        params = {"threshold_days": threshold_days}
        if limit is not None:
            params["limit"] = limit

        result = self.connection.execute(query, params)
        rows = result.fetchall()

        companies = []
        for row in rows:
            companies.append(
                StaleCompanyInfo(
                    company_id=row.company_id,
                    company_full_name=row.company_full_name or "",
                    updated_at=str(row.updated_at) if row.updated_at else None,
                    days_since_update=row.days_since_update,
                )
            )

        logger.info(
            "data_refresh_service.get_stale_companies",
            count=len(companies),
            threshold_days=threshold_days,
            limit=limit,
        )

        return companies

    def get_all_companies(
        self,
        limit: Optional[int] = None,
    ) -> List[StaleCompanyInfo]:
        """
        Get all companies from enterprise.base_info in stable order.

        Args:
            limit: Maximum number of companies to return. If None, returns all.

        Returns:
            List of StaleCompanyInfo (updated_at/days_since_update populated if available).
        """
        query_text = """
            SELECT
                company_id,
                "companyFullName" AS company_full_name,
                updated_at,
                CASE
                    WHEN updated_at IS NULL THEN NULL
                    ELSE EXTRACT(DAY FROM NOW() - updated_at)::INTEGER
                END AS days_since_update
            FROM enterprise.base_info
            ORDER BY company_id
        """

        if limit is not None:
            query_text += " LIMIT :limit"

        params = {}
        if limit is not None:
            params["limit"] = limit

        rows = self.connection.execute(text(query_text), params).fetchall()
        return [
            StaleCompanyInfo(
                company_id=row.company_id,
                company_full_name=row.company_full_name or "",
                updated_at=str(row.updated_at) if row.updated_at else None,
                days_since_update=row.days_since_update,
            )
            for row in rows
        ]

    def _cleanse_business_info_best_effort(self, company_id: str) -> None:
        """
        Best-effort cleansing integration for enterprise.business_info (Story 6.2-P5 AC16).

        This function must never fail the refresh operation.
        """
        try:
            from work_data_hub.infrastructure.cleansing.rule_engine import CleansingRuleEngine

            row = self.connection.execute(
                text("""
                    SELECT
                        company_id,
                        registered_date,
                        "registerCaptial",
                        registered_status,
                        legal_person_name,
                        address,
                        company_name,
                        credit_code,
                        company_type,
                        industry_name,
                        business_scope
                    FROM enterprise.business_info
                    WHERE company_id = :company_id
                """),
                {"company_id": company_id},
            ).fetchone()

            if not row:
                return

            record = dict(row._mapping)
            engine = CleansingRuleEngine()
            result = engine.cleanse_record("eqc_business_info", record)

            self.connection.execute(
                text("""
                    UPDATE enterprise.business_info
                    SET _cleansing_status = :cleansing_status::jsonb,
                        registered_date = :registered_date,
                        "registerCaptial" = :registerCaptial,
                        registered_status = :registered_status,
                        legal_person_name = :legal_person_name,
                        address = :address,
                        company_name = :company_name,
                        credit_code = :credit_code,
                        company_type = :company_type,
                        industry_name = :industry_name,
                        business_scope = :business_scope
                    WHERE company_id = :company_id
                """),
                {
                    "company_id": record["company_id"],
                    "cleansing_status": json.dumps(
                        result.cleansing_status, ensure_ascii=False
                    ),
                    "registered_date": record.get("registered_date"),
                    "registerCaptial": record.get("registerCaptial"),
                    "registered_status": record.get("registered_status"),
                    "legal_person_name": record.get("legal_person_name"),
                    "address": record.get("address"),
                    "company_name": record.get("company_name"),
                    "credit_code": record.get("credit_code"),
                    "company_type": record.get("company_type"),
                    "industry_name": record.get("industry_name"),
                    "business_scope": record.get("business_scope"),
                },
            )
        except Exception as exc:
            logger.warning(
                "data_refresh_service.business_info_cleansing_failed",
                company_id=company_id,
                error_type=type(exc).__name__,
            )

    def refresh_by_company_ids(
        self,
        company_ids: List[str],
        rate_limit: Optional[float] = None,
    ) -> RefreshResult:
        """
        Refresh enterprise data for given company_ids.

        Calls EQC API for each company_id and updates base_info table.
        Implements rate limiting to avoid overwhelming the API.

        Args:
            company_ids: List of EQC company IDs to refresh.
            rate_limit: Requests per second. If None, uses settings default.

        Returns:
            RefreshResult with success/failure statistics.

        Example:
            >>> result = service.refresh_by_company_ids(["1000065057", "1000087994"])
            >>> print(f"Success: {result.successful}/{result.total_requested}")
        """
        if rate_limit is None:
            rate_limit = self.settings.eqc_data_refresh_rate_limit

        if not company_ids:
            logger.debug("data_refresh_service.refresh_by_company_ids.empty_input")
            return RefreshResult(
                total_requested=0,
                successful=0,
                failed=0,
                skipped=0,
                errors=[],
            )

        successful = 0
        failed = 0
        skipped = 0
        errors = []

        delay_between_requests = 1.0 / rate_limit if rate_limit > 0 else 0

        logger.info(
            "data_refresh_service.refresh_by_company_ids.started",
            total_companies=len(company_ids),
            rate_limit=rate_limit,
        )

        for idx, company_id in enumerate(company_ids, 1):
            try:
                # Get company name from base_info for search
                name_query = text("""
                    SELECT "companyFullName" AS company_full_name
                    FROM enterprise.base_info
                    WHERE company_id = :company_id
                """)
                name_result = self.connection.execute(
                    name_query,
                    {"company_id": company_id},
                )
                name_row = name_result.fetchone()

                if not name_row or not name_row.company_full_name:
                    logger.warning(
                        "data_refresh_service.company_name_not_found",
                        company_id=company_id,
                    )
                    skipped += 1
                    continue

                company_name = name_row.company_full_name

                # Call EQC API with raw response
                results, raw_json = self.eqc_client.search_company_with_raw(company_name)

                if not results:
                    logger.warning(
                        "data_refresh_service.no_results_from_eqc",
                        company_id=company_id,
                    )
                    failed += 1
                    errors.append(f"{company_id}: No results from EQC")
                    continue

                # Find matching result by company_id
                matching_result = None
                for search_result in results:
                    if str(search_result.company_id) == str(company_id):
                        matching_result = search_result
                        break

                if not matching_result:
                    logger.warning(
                        "data_refresh_service.company_id_mismatch",
                        company_id=company_id,
                        search_name=company_name,
                    )
                    failed += 1
                    errors.append(f"{company_id}: Company ID not found in results")
                    continue

                # Update base_info with new data
                self.repository.upsert_base_info(
                    company_id=company_id,
                    search_key_word=company_name,
                    company_full_name=matching_result.official_name,
                    unite_code=getattr(matching_result, "unite_code", None),
                    raw_data=raw_json,
                )

                # AC16: Integrate cleansing into refresh flow (best-effort)
                self._cleanse_business_info_best_effort(company_id)

                successful += 1

                logger.debug(
                    "data_refresh_service.company_refreshed",
                    company_id=company_id,
                    progress=f"{idx}/{len(company_ids)}",
                )

                # Rate limiting
                if delay_between_requests > 0 and idx < len(company_ids):
                    time.sleep(delay_between_requests)

            except EQCClientError as e:
                logger.error(
                    "data_refresh_service.eqc_error",
                    company_id=company_id,
                    error=str(e),
                )
                failed += 1
                errors.append(f"{company_id}: {str(e)}")

            except Exception as e:
                logger.error(
                    "data_refresh_service.unexpected_error",
                    company_id=company_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                failed += 1
                errors.append(f"{company_id}: {type(e).__name__}: {str(e)}")

        result = RefreshResult(
            total_requested=len(company_ids),
            successful=successful,
            failed=failed,
            skipped=skipped,
            errors=errors,
        )

        logger.info(
            "data_refresh_service.refresh_by_company_ids.completed",
            total=result.total_requested,
            successful=result.successful,
            failed=result.failed,
            skipped=result.skipped,
        )

        return result

    def refresh_stale_companies(
        self,
        threshold_days: Optional[int] = None,
        batch_size: Optional[int] = None,
        rate_limit: Optional[float] = None,
        max_companies: Optional[int] = None,
    ) -> RefreshResult:
        """
        Refresh all stale companies with rate limiting and batch processing.

        Args:
            threshold_days: Custom threshold in days. If None, uses settings default.
            batch_size: Batch size for processing. If None, uses settings default.
                Companies are processed in batches of this size.
            rate_limit: Requests per second. If None, uses settings default.
            max_companies: Maximum companies to refresh. If None, refreshes all stale.

        Returns:
            RefreshResult with aggregated success/failure statistics across all batches.

        Example:
            >>> result = service.refresh_stale_companies(max_companies=100, batch_size=50)
            >>> print(f"Refreshed {result.successful} companies in batches of 50")
        """
        if threshold_days is None:
            threshold_days = self.settings.eqc_data_freshness_threshold_days
        if batch_size is None:
            batch_size = self.settings.eqc_data_refresh_batch_size
        if rate_limit is None:
            rate_limit = self.settings.eqc_data_refresh_rate_limit

        # Get stale companies
        stale_companies = self.get_stale_companies(
            threshold_days=threshold_days,
            limit=max_companies,
        )

        if not stale_companies:
            logger.info("data_refresh_service.no_stale_companies")
            return RefreshResult(
                total_requested=0,
                successful=0,
                failed=0,
                skipped=0,
                errors=[],
            )

        company_ids = [c.company_id for c in stale_companies]

        logger.info(
            "data_refresh_service.refresh_stale_companies.started",
            total_stale=len(company_ids),
            threshold_days=threshold_days,
            batch_size=batch_size,
            rate_limit=rate_limit,
        )

        # Process in batches
        total_successful = 0
        total_failed = 0
        total_skipped = 0
        all_errors: List[str] = []

        for batch_start in range(0, len(company_ids), batch_size):
            batch_end = min(batch_start + batch_size, len(company_ids))
            batch_ids = company_ids[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(company_ids) + batch_size - 1) // batch_size

            logger.info(
                "data_refresh_service.processing_batch",
                batch=batch_num,
                total_batches=total_batches,
                batch_size=len(batch_ids),
            )

            batch_result = self.refresh_by_company_ids(
                company_ids=batch_ids,
                rate_limit=rate_limit,
            )

            total_successful += batch_result.successful
            total_failed += batch_result.failed
            total_skipped += batch_result.skipped
            all_errors.extend(batch_result.errors)

            logger.info(
                "data_refresh_service.batch_completed",
                batch=batch_num,
                successful=batch_result.successful,
                failed=batch_result.failed,
            )

        result = RefreshResult(
            total_requested=len(company_ids),
            successful=total_successful,
            failed=total_failed,
            skipped=total_skipped,
            errors=all_errors,
        )

        logger.info(
            "data_refresh_service.refresh_stale_companies.completed",
            total=result.total_requested,
            successful=result.successful,
            failed=result.failed,
            skipped=result.skipped,
        )

        return result
