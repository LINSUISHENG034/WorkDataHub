"""
EQC (Enterprise Query Center) HTTP client core implementation.
"""

import logging
from typing import List, Tuple

import requests
from pydantic import ValidationError

from work_data_hub.domain.company_enrichment.models import (
    BusinessInfoResult,
    CompanyDetail,
    CompanySearchResult,
    LabelInfo,
)

from .models import (
    EQCAuthenticationError,
    EQCClientError,
    EQCNotFoundError,
)
from .parsers import (
    extract_aliases,
    parse_business_info,
    parse_company_search_item,
    parse_labels_with_fallback,
)
from .transport import EQCTransport

logger = logging.getLogger(__name__)


class EQCClient(EQCTransport):
    """
    Synchronous HTTP client for EQC (Enterprise Query Center) API.

    Provides high-level methods for company search and detail retrieval.
    Inherits transport logic (rate limiting, retries, auth) from EQCTransport.
    """

    def search_company(self, name: str) -> List[CompanySearchResult]:
        """
        Search for companies by name using EQC API.

        Args:
            name: Company name to search for (supports Chinese characters)

        Returns:
            List of CompanySearchResult objects
        """
        return self.search_company_with_raw(name)[0]

    def search_company_with_raw(
        self, name: str
    ) -> Tuple[List[CompanySearchResult], dict]:
        """
        Search for companies and return both parsed results and raw JSON.

        Args:
            name: Company name to search for

        Returns:
            Tuple of (parsed_results, raw_json_response)
        """
        if not name or not name.strip():
            raise ValueError("Company name cannot be empty")

        cleaned_name = name.strip()
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
            response = self._make_request("GET", url, params=params)
            data = response.json()

            # Check for TokenExpired error in response body
            if "error" in data:
                error_msg = data.get("error", "")
                if error_msg == "TokenExpired":
                    logger.error(
                        "EQC token expired (detected in response body)",
                        extra={"query": cleaned_name, "error": error_msg},
                    )
                    raise EQCAuthenticationError("EQC token expired")
                else:
                    logger.warning(
                        "EQC API returned error in response body",
                        extra={"query": cleaned_name, "error": error_msg},
                    )

            results_list = data.get("list", [])
            companies = []
            for item in results_list:
                try:
                    companies.append(parse_company_search_item(item))
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

        Args:
            company_id: EQC company ID

        Returns:
            CompanyDetail object
        """
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        logger.info(
            "Retrieving company details via EQC",
            extra={"company_id": cleaned_id, "endpoint": "findDepart"},
        )

        try:
            business_info, _ = self._fetch_find_depart(cleaned_id)

            detail = CompanyDetail(
                company_id=cleaned_id,
                official_name=business_info.get(
                    "companyFullName", business_info.get("company_name", "")
                ),
                unite_code=business_info.get("unite_code"),
                aliases=extract_aliases(business_info),
                business_status=business_info.get(
                    "business_status", business_info.get("status")
                ),
            )

            logger.info(
                "Company details retrieved successfully",
                extra={
                    "company_id": cleaned_id,
                    "official_name": detail.official_name,
                },
            )
            return detail

        except Exception as e:
            logger.error(
                "Failed to parse company detail response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            if isinstance(
                e, (EQCNotFoundError, EQCAuthenticationError, EQCClientError)
            ):
                raise
            raise EQCClientError(f"Failed to parse company detail response: {e}")

    def _extract_aliases(self, business_info: dict) -> List[str]:
        """Wrapper for alias extraction logic."""
        return extract_aliases(business_info)

    def get_business_info(self, company_id: str) -> BusinessInfoResult:
        """Get business information by EQC company ID."""
        return self.get_business_info_with_raw(company_id)[0]

    def get_business_info_with_raw(
        self, company_id: str
    ) -> Tuple[BusinessInfoResult, dict]:
        """Get business information and return both parsed result and raw JSON."""
        cleaned_id = str(company_id).strip()
        business_info, raw = self._fetch_find_depart(cleaned_id)
        try:
            parsed = parse_business_info(business_info, fallback_company_id=cleaned_id)
        except ValidationError as e:
            raise EQCClientError(
                f"Unexpected response structure from EQC findDepart API: {e}"
            )
        return parsed, raw

    def get_label_info(self, company_id: str) -> List[LabelInfo]:
        """Get label information by EQC company ID."""
        return self.get_label_info_with_raw(company_id)[0]

    def get_label_info_with_raw(self, company_id: str) -> Tuple[List[LabelInfo], dict]:
        """Get label information and return both parsed result and raw JSON."""
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        url = f"{self.base_url}/kg-api-hfd/api/search/findLabels"
        params = {"targetId": cleaned_id}

        logger.info(
            "Retrieving label info via EQC (with raw response)",
            extra={"company_id": cleaned_id, "endpoint": "findLabels"},
        )

        try:
            response = self._make_request("GET", url, params=params)
            data = response.json()

            labels = parse_labels_with_fallback(data, cleaned_id)

            logger.info(
                "Label info with raw response retrieved successfully",
                extra={"company_id": cleaned_id, "labels_count": len(labels)},
            )

            return labels, data

        except requests.JSONDecodeError as e:
            logger.error(
                "Failed to parse EQC findLabels response",
                extra={"company_id": cleaned_id, "error": str(e)},
            )
            raise EQCClientError(f"Invalid JSON response from EQC findLabels API: {e}")

    def _fetch_find_depart(self, company_id: str) -> Tuple[dict, dict]:
        """Call findDepart API and return (businessInfodto, raw_response)."""
        if not company_id or not str(company_id).strip():
            raise ValueError("Company ID cannot be empty")

        cleaned_id = str(company_id).strip()
        url = f"{self.base_url}/kg-api-hfd/api/search/findDepart"
        params = {"targetId": cleaned_id}

        logger.info(
            "Fetching business info via EQC findDepart",
            extra={"company_id": cleaned_id, "endpoint": "findDepart"},
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
