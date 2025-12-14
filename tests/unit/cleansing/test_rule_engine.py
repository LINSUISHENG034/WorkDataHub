"""Unit tests for CleansingRuleEngine behavior (Story 6.2-P5)."""

from datetime import date

import pytest

from work_data_hub.infrastructure.cleansing.rule_engine import CleansingRuleEngine


@pytest.mark.unit
class TestCleansingRuleEngine:
    def test_cleanse_field_parses_chinese_date(self):
        engine = CleansingRuleEngine()
        result = engine.cleanse_field("eqc_business_info", "registered_date", "2024年11月")
        assert result.success is True
        assert result.cleansed_value == date(2024, 11, 1)

    def test_cleanse_field_converts_register_capital_units(self):
        engine = CleansingRuleEngine()
        result = engine.cleanse_field("eqc_business_info", "registerCaptial", "1,000万元")
        assert result.success is True
        assert result.cleansed_value == 1000 * 10_000.0

    def test_cleanse_record_updates_values_and_status(self):
        engine = CleansingRuleEngine()
        record = {
            "company_id": "CID1",
            "registerCaptial": "2亿元",
            "company_name": "「  测试公司  」",
        }
        result = engine.cleanse_record("eqc_business_info", record)

        assert result.fields_cleansed >= 2
        assert record["registerCaptial"] == 2 * 100_000_000.0
        assert record["company_name"] == "测试公司"
        assert result.cleansing_status["fields_failed"] == 0
