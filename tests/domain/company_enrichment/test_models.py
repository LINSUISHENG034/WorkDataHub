"""
Unit tests for company enrichment domain models.

This module tests the Pydantic v2 data models for EQC API integration,
ensuring proper validation, serialization, and field handling.
"""

import pytest
from pydantic import ValidationError

from work_data_hub.domain.company_enrichment.models import (
    CompanyDetail,
    CompanySearchResult,
)


class TestCompanySearchResult:
    """Test CompanySearchResult model validation and behavior."""

    def test_valid_search_result_creation(self):
        """Test creation of valid CompanySearchResult."""
        result = CompanySearchResult(
            company_id="123456789",
            official_name="测试公司",
            unite_code="91110000000000001X",
            match_score=0.85,
        )

        assert result.company_id == "123456789"
        assert result.official_name == "测试公司"
        assert result.unite_code == "91110000000000001X"
        assert result.match_score == 0.85

    def test_search_result_with_minimal_fields(self):
        """Test creation with only required fields."""
        result = CompanySearchResult(company_id="123", official_name="最小公司")

        assert result.company_id == "123"
        assert result.official_name == "最小公司"
        assert result.unite_code is None
        assert result.match_score == 0.0  # Default value

    def test_search_result_normalizes_company_id(self):
        """Test company_id normalization from various types."""
        # Integer company ID
        result = CompanySearchResult(company_id=123456789, official_name="数字ID公司")
        assert result.company_id == "123456789"

        # String with whitespace
        result = CompanySearchResult(
            company_id="  987654321  ", official_name="空格ID公司"
        )
        assert result.company_id == "987654321"

    def test_search_result_normalizes_unite_code(self):
        """Test unite_code normalization and None handling."""
        # Valid unite code
        result = CompanySearchResult(
            company_id="123", official_name="公司", unite_code="  91110000000000001X  "
        )
        assert result.unite_code == "91110000000000001X"

        # Empty string becomes None
        result = CompanySearchResult(
            company_id="123", official_name="公司", unite_code=""
        )
        assert result.unite_code is None

        # Whitespace only becomes None
        result = CompanySearchResult(
            company_id="123", official_name="公司", unite_code="   "
        )
        assert result.unite_code is None

    def test_search_result_match_score_validation(self):
        """Test match_score field validation."""
        # Valid score range
        result = CompanySearchResult(
            company_id="123", official_name="公司", match_score=0.5
        )
        assert result.match_score == 0.5

        # Score at boundaries
        result = CompanySearchResult(
            company_id="123", official_name="公司", match_score=0.0
        )
        assert result.match_score == 0.0

        result = CompanySearchResult(
            company_id="123", official_name="公司", match_score=1.0
        )
        assert result.match_score == 1.0

        # Invalid score - too low
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(
                company_id="123", official_name="公司", match_score=-0.1
            )
        assert "greater than or equal to 0" in str(exc_info.value)

        # Invalid score - too high
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(company_id="123", official_name="公司", match_score=1.1)
        assert "less than or equal to 1" in str(exc_info.value)

    def test_search_result_required_field_validation(self):
        """Test validation of required fields."""
        # Missing company_id
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(official_name="公司")
        assert "company_id" in str(exc_info.value)

        # Missing official_name
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(company_id="123")
        assert "official_name" in str(exc_info.value)

        # Empty company_id
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(company_id="", official_name="公司")
        assert "at least 1 character" in str(exc_info.value)

        # Empty official_name
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(company_id="123", official_name="")
        assert "at least 1 character" in str(exc_info.value)

    def test_search_result_string_length_validation(self):
        """Test string length constraints."""
        # Official name too long
        long_name = "A" * 501  # Max is 500
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(company_id="123", official_name=long_name)
        assert "at most 500 characters" in str(exc_info.value)

        # Unite code too long
        long_unite_code = "A" * 101  # Max is 100
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(
                company_id="123", official_name="公司", unite_code=long_unite_code
            )
        assert "at most 100 characters" in str(exc_info.value)

    def test_search_result_whitespace_stripping(self):
        """Test automatic whitespace stripping."""
        result = CompanySearchResult(
            company_id="  123  ",
            official_name="  测试公司  ",
            unite_code="  91110000000000001X  ",
        )

        assert result.company_id == "123"
        assert result.official_name == "测试公司"
        assert result.unite_code == "91110000000000001X"

    def test_search_result_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            CompanySearchResult(
                company_id="123", official_name="公司", extra_field="不允许"
            )
        assert "extra_field" in str(exc_info.value)


class TestCompanyDetail:
    """Test CompanyDetail model validation and behavior."""

    def test_valid_company_detail_creation(self):
        """Test creation of valid CompanyDetail."""
        detail = CompanyDetail(
            company_id="123456789",
            official_name="详细测试公司",
            unite_code="91110000000000001X",
            aliases=["别名1", "别名2"],
            business_status="在业",
        )

        assert detail.company_id == "123456789"
        assert detail.official_name == "详细测试公司"
        assert detail.unite_code == "91110000000000001X"
        assert detail.aliases == ["别名1", "别名2"]
        assert detail.business_status == "在业"

    def test_company_detail_with_minimal_fields(self):
        """Test creation with only required fields."""
        detail = CompanyDetail(company_id="123", official_name="最小详情公司")

        assert detail.company_id == "123"
        assert detail.official_name == "最小详情公司"
        assert detail.unite_code is None
        assert detail.aliases == []  # Default empty list
        assert detail.business_status is None

    def test_company_detail_normalizes_company_id(self):
        """Test company_id normalization in CompanyDetail."""
        detail = CompanyDetail(company_id=987654321, official_name="数字ID详情公司")
        assert detail.company_id == "987654321"

    def test_company_detail_normalizes_unite_code(self):
        """Test unite_code normalization in CompanyDetail."""
        # Valid unite code with whitespace
        detail = CompanyDetail(
            company_id="123", official_name="公司", unite_code="  91110000000000001X  "
        )
        assert detail.unite_code == "91110000000000001X"

        # Empty string becomes None
        detail = CompanyDetail(company_id="123", official_name="公司", unite_code="")
        assert detail.unite_code is None

    def test_company_detail_normalizes_aliases(self):
        """Test aliases field normalization."""
        # List of strings
        detail = CompanyDetail(
            company_id="123", official_name="公司", aliases=["别名1", "别名2", "别名3"]
        )
        assert detail.aliases == ["别名1", "别名2", "别名3"]

        # Single string converted to list
        detail = CompanyDetail(
            company_id="123", official_name="公司", aliases="单个别名"
        )
        assert detail.aliases == ["单个别名"]

        # Empty string becomes empty list
        detail = CompanyDetail(company_id="123", official_name="公司", aliases="")
        assert detail.aliases == []

        # List with empty/None values filtered out
        detail = CompanyDetail(
            company_id="123",
            official_name="公司",
            aliases=["有效别名", "", None, "   ", "另一个有效别名"],
        )
        assert detail.aliases == ["有效别名", "另一个有效别名"]

        # None becomes empty list
        detail = CompanyDetail(company_id="123", official_name="公司", aliases=None)
        assert detail.aliases == []

    def test_company_detail_required_field_validation(self):
        """Test validation of required fields in CompanyDetail."""
        # Missing company_id
        with pytest.raises(ValidationError) as exc_info:
            CompanyDetail(official_name="公司")
        assert "company_id" in str(exc_info.value)

        # Missing official_name
        with pytest.raises(ValidationError) as exc_info:
            CompanyDetail(company_id="123")
        assert "official_name" in str(exc_info.value)

    def test_company_detail_string_length_validation(self):
        """Test string length constraints in CompanyDetail."""
        # Official name too long
        long_name = "A" * 501
        with pytest.raises(ValidationError) as exc_info:
            CompanyDetail(company_id="123", official_name=long_name)
        assert "at most 500 characters" in str(exc_info.value)

        # Business status too long
        long_status = "A" * 101
        with pytest.raises(ValidationError) as exc_info:
            CompanyDetail(
                company_id="123", official_name="公司", business_status=long_status
            )
        assert "at most 100 characters" in str(exc_info.value)

    def test_company_detail_whitespace_stripping(self):
        """Test automatic whitespace stripping in CompanyDetail."""
        detail = CompanyDetail(
            company_id="  123  ",
            official_name="  详细公司  ",
            unite_code="  91110000000000001X  ",
            business_status="  在业  ",
        )

        assert detail.company_id == "123"
        assert detail.official_name == "详细公司"
        assert detail.unite_code == "91110000000000001X"
        assert detail.business_status == "在业"

    def test_company_detail_extra_fields_forbidden(self):
        """Test that extra fields are forbidden in CompanyDetail."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyDetail(
                company_id="123", official_name="公司", forbidden_extra="不允许"
            )
        assert "forbidden_extra" in str(exc_info.value)

    def test_company_detail_serialization(self):
        """Test model serialization to dict."""
        detail = CompanyDetail(
            company_id="123456789",
            official_name="序列化测试公司",
            unite_code="91110000000000001X",
            aliases=["别名1", "别名2"],
            business_status="在业",
        )

        data = detail.model_dump()

        expected = {
            "company_id": "123456789",
            "official_name": "序列化测试公司",
            "unite_code": "91110000000000001X",
            "aliases": ["别名1", "别名2"],
            "business_status": "在业",
        }

        assert data == expected

    def test_company_detail_json_serialization(self):
        """Test model JSON serialization."""
        detail = CompanyDetail(company_id="123", official_name="JSON测试公司")

        json_str = detail.model_dump_json()
        assert '"company_id":"123"' in json_str
        assert '"official_name":"JSON测试公司"' in json_str
        assert '"unite_code":null' in json_str
        assert '"aliases":[]' in json_str
        assert '"business_status":null' in json_str


class TestModelInteroperability:
    """Test interoperability between CompanySearchResult and CompanyDetail."""

    def test_search_result_to_detail_conversion(self):
        """Test converting search result data to detail model."""
        # This tests a common pattern where search results are used to create detail requests
        search_result = CompanySearchResult(
            company_id="123456789",
            official_name="搜索结果公司",
            unite_code="91110000000000001X",
            match_score=0.95,
        )

        # Create detail using data from search result
        detail = CompanyDetail(
            company_id=search_result.company_id,
            official_name=search_result.official_name,
            unite_code=search_result.unite_code,
            aliases=["搜索别名"],
            business_status="活跃",
        )

        assert detail.company_id == search_result.company_id
        assert detail.official_name == search_result.official_name
        assert detail.unite_code == search_result.unite_code

    def test_model_field_compatibility(self):
        """Test that common fields between models are compatible."""
        common_data = {
            "company_id": "999888777",
            "official_name": "兼容性测试公司",
            "unite_code": "91110000000000002Y",
        }

        # Both models should accept the same common data
        search_result = CompanySearchResult(**common_data, match_score=0.8)
        detail = CompanyDetail(**common_data, aliases=[], business_status=None)

        assert search_result.company_id == detail.company_id
        assert search_result.official_name == detail.official_name
        assert search_result.unite_code == detail.unite_code
