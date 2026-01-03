"""
Unit tests for BaseInfoParser.

Tests cover:
- parse_from_search_response extracts all fields correctly
- parse_from_find_depart_response extracts all fields correctly
- data_source is set correctly for each parse method
- Missing fields are handled gracefully
- Capital parsing handles various formats
"""

import pytest

from work_data_hub.infrastructure.enrichment.base_info_parser import (
    BaseInfoParser,
    DATA_SOURCE_DIRECT_ID,
    DATA_SOURCE_SEARCH,
    ParsedBaseInfo,
)


class TestParseFromSearchResponse:
    """Tests for BaseInfoParser.parse_from_search_response()."""

    def test_extracts_core_fields(self) -> None:
        """Core fields are extracted from search response."""
        raw_json = {
            "list": [
                {
                    "companyId": "614810477",
                    "companyFullName": "中国平安保险（集团）股份有限公司",
                    "unite_code": "91440300618698064P",
                    "type": "全称精确匹配",
                    "_score": 0.95,
                    "rank_score": 100.0,
                }
            ]
        }

        parsed = BaseInfoParser.parse_from_search_response(
            raw_json=raw_json,
            raw_business_info=None,
            search_key_word="中国平安",
        )

        assert parsed.company_id == "614810477"
        assert parsed.company_full_name == "中国平安保险（集团）股份有限公司"
        assert parsed.unite_code == "91440300618698064P"
        assert parsed.search_key_word == "中国平安"
        assert parsed.data_source == DATA_SOURCE_SEARCH
        assert parsed.match_type == "全称精确匹配"
        assert parsed.score == 0.95
        assert parsed.rank_score == 100.0

    def test_extracts_business_fields_from_raw_business_info(self) -> None:
        """Business fields are extracted from raw_business_info."""
        raw_json = {
            "list": [
                {
                    "companyId": "614810477",
                    "companyFullName": "中国平安保险（集团）股份有限公司",
                }
            ]
        }
        raw_business_info = {
            "businessInfodto": {
                "le_rep": "马明哲",
                "registered_date": "1988-03-21",
                "province": "广东",
                "registered_status": "存续",
                "organization_code": "100001XXX",
                "registerCaptial": "80000.00万元",
            }
        }

        parsed = BaseInfoParser.parse_from_search_response(
            raw_json=raw_json,
            raw_business_info=raw_business_info,
            search_key_word="中国平安",
        )

        assert parsed.le_rep == "马明哲"
        assert parsed.est_date == "1988-03-21"
        assert parsed.province == "广东"
        assert parsed.registered_status == "存续"
        assert parsed.organization_code == "100001XXX"
        assert parsed.reg_cap == 80000.00

    def test_handles_missing_business_info(self) -> None:
        """Missing raw_business_info results in null business fields."""
        raw_json = {
            "list": [
                {
                    "companyId": "614810477",
                    "companyFullName": "中国平安保险（集团）股份有限公司",
                }
            ]
        }

        parsed = BaseInfoParser.parse_from_search_response(
            raw_json=raw_json,
            raw_business_info=None,
            search_key_word="中国平安",
        )

        assert parsed.le_rep is None
        assert parsed.est_date is None
        assert parsed.province is None
        assert parsed.reg_cap is None

    def test_raises_on_empty_results(self) -> None:
        """Raises ValueError when search response has empty results."""
        raw_json = {"list": []}

        with pytest.raises(ValueError, match="no results"):
            BaseInfoParser.parse_from_search_response(
                raw_json=raw_json,
                raw_business_info=None,
                search_key_word="test",
            )

    def test_raises_on_missing_company_id(self) -> None:
        """Raises ValueError when company_id is missing."""
        raw_json = {"list": [{"companyFullName": "测试公司"}]}

        with pytest.raises(ValueError, match="missing company_id"):
            BaseInfoParser.parse_from_search_response(
                raw_json=raw_json,
                raw_business_info=None,
                search_key_word="test",
            )


class TestParseFromFindDepartResponse:
    """Tests for BaseInfoParser.parse_from_find_depart_response()."""

    def test_extracts_core_fields(self) -> None:
        """Core fields are extracted from findDepart response."""
        raw_business_info = {
            "businessInfodto": {
                "company_id": "614810477",
                "companyFullName": "中国平安保险（集团）股份有限公司",
                "credit_code": "91440300618698064P",
                "le_rep": "马明哲",
                "registered_date": "1988-03-21",
                "province": "广东",
            }
        }

        parsed = BaseInfoParser.parse_from_find_depart_response(
            raw_business_info=raw_business_info,
            search_key_word="中国平安",
        )

        assert parsed.company_id == "614810477"
        assert parsed.company_full_name == "中国平安保险（集团）股份有限公司"
        assert parsed.unite_code == "91440300618698064P"
        assert parsed.search_key_word == "中国平安"
        assert parsed.data_source == DATA_SOURCE_DIRECT_ID
        # Search-specific fields should be null
        assert parsed.match_type is None
        assert parsed.score is None
        assert parsed.rank_score is None

    def test_extracts_business_fields(self) -> None:
        """Business fields are extracted from findDepart response."""
        raw_business_info = {
            "businessInfodto": {
                "company_id": "614810477",
                "companyFullName": "中国平安",
                "le_rep": "马明哲",
                "registered_date": "1988-03-21",
                "province": "广东",
                "registered_status": "存续",
                "organization_code": "100001XXX",
                "registerCaptial": "80000.00万元",
                "company_en_name": "PING AN",
                "company_former_name": "旧名称",
            }
        }

        parsed = BaseInfoParser.parse_from_find_depart_response(
            raw_business_info=raw_business_info,
            search_key_word="中国平安",
        )

        assert parsed.le_rep == "马明哲"
        assert parsed.est_date == "1988-03-21"
        assert parsed.province == "广东"
        assert parsed.registered_status == "存续"
        assert parsed.organization_code == "100001XXX"
        assert parsed.reg_cap == 80000.00
        assert parsed.company_en_name == "PING AN"
        assert parsed.company_former_name == "旧名称"

    def test_raises_on_empty_response(self) -> None:
        """Raises ValueError when findDepart response is empty."""
        with pytest.raises(ValueError, match="empty or not a dictionary"):
            BaseInfoParser.parse_from_find_depart_response(
                raw_business_info=None,
                search_key_word="test",
            )


class TestParseCapital:
    """Tests for capital parsing logic."""

    def test_parses_wan_yuan_format(self) -> None:
        """Parses '80000.00万元' format."""
        assert BaseInfoParser._parse_capital("80000.00万元") == 80000.00

    def test_parses_wan_format(self) -> None:
        """Parses '5000万' format."""
        assert BaseInfoParser._parse_capital("5000万") == 5000.0

    def test_parses_plain_number(self) -> None:
        """Parses plain number format."""
        assert BaseInfoParser._parse_capital("12345.67") == 12345.67

    def test_handles_comma_separator(self) -> None:
        """Handles comma thousand separator."""
        assert BaseInfoParser._parse_capital("1,000,000") == 1000000.0

    def test_returns_none_for_empty(self) -> None:
        """Returns None for empty input."""
        assert BaseInfoParser._parse_capital(None) is None
        assert BaseInfoParser._parse_capital("") is None

    def test_returns_none_for_invalid(self) -> None:
        """Returns None for invalid input."""
        assert BaseInfoParser._parse_capital("not a number") is None


class TestParseFromFindDepartNameField:
    """Tests for name field handling in direct_id lookups (Solution C)."""

    def test_name_equals_company_full_name(self) -> None:
        """name field equals company_full_name for direct_id lookup (Solution C)."""
        raw_business_info = {
            "businessInfodto": {
                "company_id": "614810477",
                "companyFullName": "中国平安保险（集团）股份有限公司",
            }
        }

        parsed = BaseInfoParser.parse_from_find_depart_response(
            raw_business_info=raw_business_info,
            search_key_word="中国平安",
        )

        # Key assertion: name must equal company_full_name for direct_id
        assert parsed.name == parsed.company_full_name
        assert parsed.name == "中国平安保险（集团）股份有限公司"


class TestBuildUpsertKwargs:
    """Tests for build_upsert_kwargs helper function."""

    def test_returns_all_fields_from_parsed(self) -> None:
        """Returns all fields when parsed is provided."""
        from work_data_hub.infrastructure.enrichment.base_info_parser import (
            build_upsert_kwargs,
        )

        raw_business_info = {
            "businessInfodto": {
                "company_id": "614810477",
                "companyFullName": "中国平安",
                "le_rep": "马明哲",
                "registered_date": "1988-03-21",
            }
        }

        parsed = BaseInfoParser.parse_from_find_depart_response(
            raw_business_info=raw_business_info,
            search_key_word="中国平安",
        )

        kwargs = build_upsert_kwargs(parsed)

        assert kwargs["data_source"] == "direct_id"
        assert kwargs["le_rep"] == "马明哲"
        assert kwargs["est_date"] == "1988-03-21"
        assert kwargs["name"] == "中国平安"

    def test_returns_fallback_when_parsed_is_none(self) -> None:
        """Returns fallback data_source when parsed is None."""
        from work_data_hub.infrastructure.enrichment.base_info_parser import (
            build_upsert_kwargs,
        )

        kwargs = build_upsert_kwargs(None, fallback_data_source="direct_id")

        assert kwargs["data_source"] == "direct_id"
        assert kwargs["le_rep"] is None
        assert kwargs["name"] is None
