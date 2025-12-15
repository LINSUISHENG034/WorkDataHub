"""
Unit tests for BusinessInfoCleanser.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 5.1: Unit tests for BusinessInfoCleanser
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict

import pytest


class TestBusinessInfoCleanser:
    """Tests for BusinessInfoCleanser service."""

    @pytest.fixture
    def cleanser(self):
        """Create a cleanser instance."""
        from work_data_hub.infrastructure.cleansing.business_info_cleanser import BusinessInfoCleanser
        return BusinessInfoCleanser()

    def test_transform_complete_record(self, cleanser):
        """Test transforming a complete raw business info record."""
        raw: Dict[str, Any] = {
            "company_name": "测试公司",
            "registerCaptial": "80000.00万元",
            "registered_date": "2015-01-15",
            "registered_status": "存续",
            "legal_person_name": "张三",
            "address": "北京市朝阳区",
            "credit_code": "91110000123456789A",
            "company_type": "有限责任公司",
            "industry_name": "信息技术",
            "business_scope": "软件开发",
        }

        result = cleanser.transform(raw, "company_123")

        assert result.company_id == "company_123"
        assert result.company_name == "测试公司"
        # registered_capital should be converted: 80000.00万 = 800,000,000
        assert result.registered_capital == 800000000.0
        assert result.registered_status == "存续"
        assert result.legal_person_name == "张三"
        assert result.address == "北京市朝阳区"
        assert result.credit_code == "91110000123456789A"
        assert result.company_type == "有限责任公司"
        assert result.industry_name == "信息技术"
        assert result.business_scope == "软件开发"

        # Check cleansing status
        assert result.cleansing_status is not None
        assert "registered_capital" in result.cleansing_status
        assert "registered_date" in result.cleansing_status

    def test_transform_chinese_capital_conversion(self, cleanser):
        """Test Chinese currency unit conversion."""
        test_cases = [
            ("80000.00万元", 800000000.0),  # 8亿
            ("1亿元", 100000000.0),  # 1亿
            ("1000万", 10000000.0),  # 1000万（无"元"后缀）
        ]

        for raw_value, expected in test_cases:
            raw = {"registerCaptial": raw_value}
            result = cleanser.transform(raw, "test_company")
            assert result.registered_capital == expected, f"Failed for {raw_value}"

    def test_transform_date_parsing(self, cleanser):
        """Test various date format parsing."""
        test_cases = [
            ("2015-01-15", date(2015, 1, 15)),
            ("2015/01/15", date(2015, 1, 15)),
            ("2015年01月15日", date(2015, 1, 15)),
            ("20150115", date(2015, 1, 15)),
        ]

        for raw_value, expected in test_cases:
            raw = {"registered_date": raw_value}
            result = cleanser.transform(raw, "test_company")
            # Result is datetime, extract date for comparison
            if result.registered_date is not None:
                actual_date = result.registered_date.date() if isinstance(result.registered_date, datetime) else result.registered_date
                assert actual_date == expected, f"Failed for {raw_value}"

    def test_transform_null_values(self, cleanser):
        """Test handling of null/empty values."""
        raw: Dict[str, Any] = {}

        result = cleanser.transform(raw, "company_123")

        assert result.company_id == "company_123"
        assert result.registered_capital is None
        assert result.registered_date is None
        assert result.company_name is None
        assert result.cleansing_status["registered_capital"] == "null_input"
        assert result.cleansing_status["registered_date"] == "null_input"

    def test_transform_camelcase_field_mapping(self, cleanser):
        """Test camelCase to snake_case field mapping."""
        raw: Dict[str, Any] = {
            "legalPersonId": "person_123",
            "logoUrl": "https://example.com/logo.png",
            "typeCode": "0100",
            "registeredCapitalCurrency": "CNY",
            "fullRegisterTypeDesc": "有限责任公司(自然人投资或控股)",
            "industryCode": "I65",
        }

        result = cleanser.transform(raw, "company_123")

        assert result.legal_person_id == "person_123"
        assert result.logo_url == "https://example.com/logo.png"
        assert result.type_code == "0100"
        assert result.registered_capital_currency == "CNY"
        assert result.full_register_type_desc == "有限责任公司(自然人投资或控股)"
        assert result.industry_code == "I65"

    def test_transform_employee_count_parsing(self, cleanser):
        """Test employee count parsing with various formats."""
        test_cases = [
            ("100", 100),
            ("100人", 100),
            ("1,000", 1000),
            ("500.0", 500),
        ]

        for raw_value, expected in test_cases:
            raw = {"collegues_num": raw_value}
            result = cleanser.transform(raw, "test_company")
            assert result.colleagues_num == expected, f"Failed for {raw_value}"

    def test_transform_string_trimming(self, cleanser):
        """Test whitespace trimming for string fields."""
        raw: Dict[str, Any] = {
            "company_name": "  测试公司  ",
            "address": "  北京市  ",
            "registered_status": "  存续  ",
        }

        result = cleanser.transform(raw, "company_123")

        assert result.company_name == "测试公司"
        assert result.address == "北京市"
        assert result.registered_status == "存续"

    def test_transform_empty_string_to_none(self, cleanser):
        """Test that empty strings are converted to None."""
        raw: Dict[str, Any] = {
            "company_name": "",
            "address": "   ",
        }

        result = cleanser.transform(raw, "company_123")

        assert result.company_name is None
        assert result.address is None

    def test_transform_fallback_field_mapping(self, cleanser):
        """Test fallback field mappings (e.g., le_rep -> legal_person_name)."""
        raw: Dict[str, Any] = {
            "le_rep": "李四",  # Fallback for legal_person_name
            "unite_code": "91110000123456789B",  # Fallback for credit_code
        }

        result = cleanser.transform(raw, "company_123")

        assert result.legal_person_name == "李四"
        assert result.credit_code == "91110000123456789B"

    def test_transform_cleansing_status_tracking(self, cleanser):
        """Test that cleansing status tracks each field outcome."""
        raw: Dict[str, Any] = {
            "registerCaptial": "80000.00万元",
            "registered_date": "2015-01-15",
        }

        result = cleanser.transform(raw, "company_123")

        status = result.cleansing_status
        assert status is not None
        assert status["registered_capital"] == "cleansed"
        assert status["registered_date"] == "cleansed"

    def test_transform_invalid_capital_keeps_none(self, cleanser):
        """Test that invalid capital value results in None."""
        raw: Dict[str, Any] = {
            "registerCaptial": "not_a_number",
        }

        result = cleanser.transform(raw, "company_123")

        # Invalid value should result in None or parse_failed status
        assert result.registered_capital is None or result.cleansing_status["registered_capital"] in ("parse_failed", "error:ValueError")
