"""
Base Info Parser - Unified field extraction for base_info table.

This module provides the BaseInfoParser service class that extracts and normalizes
fields from EQC API responses (Search and findDepart) for consistent base_info
table persistence.

Story: Base Info Parsing Enhancement
Architecture: Ensures data consistency between ETL keyword lookup and GUI direct ID lookup.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

# Data source constants
DATA_SOURCE_SEARCH = "search"
DATA_SOURCE_DIRECT_ID = "direct_id"
DATA_SOURCE_REFRESH = "refresh"


def _first_non_empty(payload: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Return the first non-empty string value from a list of keys."""
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float, return None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@dataclass
class ParsedBaseInfo:
    """
    Normalized base_info fields from any EQC response.

    This dataclass represents the unified field set that will be written
    to the base_info table, regardless of query method (keyword or direct ID).

    Attributes:
        company_id: EQC company ID (primary key).
        company_full_name: Official company name.
        unite_code: Unified social credit code (统一社会信用代码).
        search_key_word: The search term used to find this company.
        data_source: Origin of data ("search", "direct_id", "refresh").

        # Search API specific fields (null for direct_id lookup)
        match_type: EQC match quality (全称精确匹配/模糊匹配/拼音).
        score: Search relevance score.
        rank_score: Ranking score.

        # Fields from findDepart API (available for both lookup types)
        name: Company name.
        le_rep: Legal representative name.
        reg_cap: Registered capital (parsed float).
        est_date: Establishment date.
        province: Province.
        registered_status: Registration status.
        organization_code: Organization code.
        company_en_name: English company name.
        company_former_name: Former company name.
    """

    company_id: str
    company_full_name: str
    unite_code: Optional[str]
    search_key_word: str
    data_source: str

    # Search API specific fields
    match_type: Optional[str] = None
    score: Optional[float] = None
    rank_score: Optional[float] = None

    # Fields from findDepart API
    name: Optional[str] = None
    le_rep: Optional[str] = None
    reg_cap: Optional[float] = None
    est_date: Optional[str] = None
    province: Optional[str] = None
    registered_status: Optional[str] = None
    organization_code: Optional[str] = None
    company_en_name: Optional[str] = None
    company_former_name: Optional[str] = None


class BaseInfoParser:
    """
    Unified parser for extracting base_info fields from EQC API responses.

    This class provides two main parsing methods:
    1. parse_from_search_response() - For keyword lookup (Search API + findDepart)
    2. parse_from_find_depart_response() - For direct ID lookup (findDepart only)

    Both methods produce a consistent ParsedBaseInfo output that can be written
    to the base_info table.
    """

    @staticmethod
    def parse_from_search_response(
        raw_json: Dict[str, Any],
        raw_business_info: Optional[Dict[str, Any]],
        search_key_word: str,
    ) -> ParsedBaseInfo:
        """
        Parse fields from Search API response with optional findDepart supplement.

        This is the primary parsing path for keyword lookups in ETL and GUI.
        Search API provides match quality info; findDepart provides detailed fields.

        Args:
            raw_json: Complete Search API response JSON.
            raw_business_info: Optional findDepart API response JSON.
            search_key_word: The search term used for lookup.

        Returns:
            ParsedBaseInfo with all available fields populated.

        Example:
            >>> parsed = BaseInfoParser.parse_from_search_response(
            ...     raw_json={"list": [{"companyId": "123", "type": "全称精确匹配"}]},
            ...     raw_business_info={"le_rep": "张三"},
            ...     search_key_word="中国平安",
            ... )
            >>> parsed.match_type
            '全称精确匹配'
        """
        # Extract first result from search response
        results = raw_json.get("list", [])
        if not results or not isinstance(results, list):
            raise ValueError("Search response has no results in 'list' field")

        first_result = results[0]
        if not isinstance(first_result, dict):
            raise ValueError("First search result is not a dictionary")

        # Extract core fields from search result
        company_id = str(
            _first_non_empty(first_result, ["companyId", "company_id", "id"]) or ""
        )
        if not company_id:
            raise ValueError("Search result missing company_id")

        company_full_name = _first_non_empty(
            first_result, ["companyFullName", "name", "coname"]
        )
        if not company_full_name:
            raise ValueError("Search result missing company name")

        unite_code = _first_non_empty(
            first_result, ["unite_code", "uniteCode", "creditCode"]
        )

        # Search-specific fields
        match_type = first_result.get("type")
        score = _safe_float(first_result.get("_score"))
        rank_score = _safe_float(first_result.get("rank_score"))

        # Extract fields from findDepart if available
        business_fields = BaseInfoParser._extract_business_fields(raw_business_info)

        logger.debug(
            "base_info_parser.parse_from_search_response",
            company_id=company_id,
            match_type=match_type,
            has_business_info=raw_business_info is not None,
        )

        return ParsedBaseInfo(
            company_id=company_id,
            company_full_name=company_full_name,
            unite_code=unite_code,
            search_key_word=search_key_word,
            data_source=DATA_SOURCE_SEARCH,
            match_type=match_type,
            score=score,
            rank_score=rank_score,
            **business_fields,
        )

    @staticmethod
    def parse_from_find_depart_response(
        raw_business_info: Dict[str, Any],
        search_key_word: str,
    ) -> ParsedBaseInfo:
        """
        Parse fields from findDepart API response only.

        This is the parsing path for direct ID lookups in GUI.
        Search-specific fields (match_type, score, rank_score) will be null.

        Args:
            raw_business_info: Complete findDepart API response JSON.
            search_key_word: The company name to use for search_key_word.

        Returns:
            ParsedBaseInfo with findDepart fields populated, Search fields as null.

        Example:
            >>> parsed = BaseInfoParser.parse_from_find_depart_response(
            ...     raw_business_info={"companyFullName": "中国平安", "le_rep": "张三"},
            ...     search_key_word="中国平安保险（集团）股份有限公司",
            ... )
            >>> parsed.match_type  # Always None for direct_id
            None
            >>> parsed.le_rep
            '张三'
        """
        if not raw_business_info or not isinstance(raw_business_info, dict):
            raise ValueError("findDepart response is empty or not a dictionary")

        # Extract businessInfodto if nested
        business_dto = raw_business_info.get("businessInfodto", raw_business_info)

        # Extract core fields
        company_id = str(
            _first_non_empty(business_dto, ["company_id", "companyId", "id"]) or ""
        )
        if not company_id:
            raise ValueError("findDepart response missing company_id")

        company_full_name = _first_non_empty(
            business_dto, ["companyFullName", "company_name", "companyName", "name"]
        )
        if not company_full_name:
            # Fall back to search_key_word if no name in response
            company_full_name = search_key_word

        unite_code = _first_non_empty(
            business_dto, ["unite_code", "uniteCode", "credit_code", "creditCode"]
        )

        # Extract detailed business fields
        business_fields = BaseInfoParser._extract_business_fields(raw_business_info)
        # Remove name from business_fields as we'll explicitly set it to company_full_name
        business_fields.pop("name", None)

        logger.debug(
            "base_info_parser.parse_from_find_depart_response",
            company_id=company_id,
            data_source=DATA_SOURCE_DIRECT_ID,
        )

        return ParsedBaseInfo(
            company_id=company_id,
            company_full_name=company_full_name,
            unite_code=unite_code,
            search_key_word=search_key_word,
            data_source=DATA_SOURCE_DIRECT_ID,
            # Search-specific fields are null for direct_id
            match_type=None,
            score=None,
            rank_score=None,
            **business_fields,
            # Force name to match company_full_name as requested (Solution C)
            name=company_full_name,
        )

    @staticmethod
    def _extract_business_fields(
        raw_business_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Extract detailed business fields from findDepart response.

        Maps findDepart API fields to base_info table columns.

        Args:
            raw_business_info: findDepart API response JSON or None.

        Returns:
            Dictionary of business field values.
        """
        if not raw_business_info or not isinstance(raw_business_info, dict):
            return {
                "name": None,
                "le_rep": None,
                "reg_cap": None,
                "est_date": None,
                "province": None,
                "registered_status": None,
                "organization_code": None,
                "company_en_name": None,
                "company_former_name": None,
            }

        # Handle nested businessInfodto structure
        dto = raw_business_info.get("businessInfodto", raw_business_info)

        # Parse registered capital (remove currency suffix like "万元")
        reg_cap_raw = _first_non_empty(
            dto, ["registerCaptial", "reg_cap", "registered_capital"]
        )
        reg_cap = BaseInfoParser._parse_capital(reg_cap_raw)

        return {
            "name": _first_non_empty(
                dto, ["companyFullName", "company_name", "companyName", "name"]
            ),
            "le_rep": _first_non_empty(
                dto, ["legal_person_name", "legalPersonName", "le_rep"]
            ),
            "reg_cap": reg_cap,
            "est_date": _first_non_empty(
                dto, ["registered_date", "registeredDate", "est_date", "estDate"]
            ),
            "province": _first_non_empty(dto, ["province"]),
            "registered_status": _first_non_empty(
                dto, ["registered_status", "registeredStatus"]
            ),
            "organization_code": _first_non_empty(
                dto, ["organization_code", "organizationCode"]
            ),
            "company_en_name": _first_non_empty(dto, ["company_en_name"]),
            "company_former_name": _first_non_empty(dto, ["company_former_name"]),
        }

    @staticmethod
    def _parse_capital(raw_value: Optional[str]) -> Optional[float]:
        """
        Parse capital string to float value.

        Handles formats like "80000.00万元", "1000万", "5000.00".

        Args:
            raw_value: Raw capital string from API.

        Returns:
            Parsed float value or None if parsing fails.
        """
        if not raw_value:
            return None

        # Remove common suffixes
        cleaned = raw_value.replace("万元", "").replace("万", "").replace("元", "")
        cleaned = cleaned.replace(",", "").strip()

        return _safe_float(cleaned)


def build_upsert_kwargs(
    parsed: Optional["ParsedBaseInfo"],
    fallback_data_source: str = "search",
) -> Dict[str, Any]:
    """
    Build keyword arguments for upsert_base_info from ParsedBaseInfo.

    This helper centralizes the mapping between ParsedBaseInfo fields and
    upsert_base_info parameters, eliminating code duplication between
    EqcQueryController.save_last_result() and EqcProvider._cache_result().

    Args:
        parsed: ParsedBaseInfo from parser, or None if parsing failed.
        fallback_data_source: Data source to use if parsed is None.

    Returns:
        Dictionary of keyword arguments for upsert_base_info.

    Example:
        >>> parsed = BaseInfoParser.parse_from_search_response(...)
        >>> kwargs = build_upsert_kwargs(parsed)
        >>> repository.upsert_base_info(company_id=..., **kwargs)
    """
    if parsed is None:
        return {
            "data_source": fallback_data_source,
            "match_type": None,
            "le_rep": None,
            "est_date": None,
            "province": None,
            "registered_status": None,
            "organization_code": None,
            "company_en_name": None,
            "company_former_name": None,
            "reg_cap": None,
            "score": None,
            "rank_score": None,
            "name": None,
        }

    return {
        "data_source": parsed.data_source,
        "match_type": parsed.match_type,
        "le_rep": parsed.le_rep,
        "est_date": parsed.est_date,
        "province": parsed.province,
        "registered_status": parsed.registered_status,
        "organization_code": parsed.organization_code,
        "company_en_name": parsed.company_en_name,
        "company_former_name": parsed.company_former_name,
        "reg_cap": parsed.reg_cap,
        "score": parsed.score,
        "rank_score": parsed.rank_score,
        "name": parsed.name,
    }
