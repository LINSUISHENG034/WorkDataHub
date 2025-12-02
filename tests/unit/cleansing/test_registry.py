"""Unit tests for CleansingRegistry core behavior (Story 2.3)."""

import pytest

from src.work_data_hub.infrastructure.cleansing import get_cleansing_registry


@pytest.mark.unit
class TestCleansingRegistry:
    def setup_method(self):
        self.registry = get_cleansing_registry()

    def test_apply_rule_known_rule(self):
        result = self.registry.apply_rule("  值  ", "trim_whitespace")
        assert result == "值"

    def test_apply_rules_executes_in_order(self):
        value = "「  公司　有限  」"
        result = self.registry.apply_rules(
            value,
            ["trim_whitespace", "normalize_company_name"],
        )
        assert result == "公司 有限"

    def test_apply_rule_unknown_raises(self):
        with pytest.raises(ValueError) as exc_info:
            self.registry.apply_rule("value", "__missing_rule__")
        assert "not registered" in str(exc_info.value)

    def test_get_domain_rules_handles_domain_and_defaults(self):
        domain_rules = self.registry.get_domain_rules("annuity_performance", "客户名称")
        assert "normalize_company_name" in domain_rules

        missing_field_rules = self.registry.get_domain_rules("annuity_performance", "未知字段")
        assert missing_field_rules == []

        default_rules = self.registry.get_domain_rules("unknown-domain", "plan_code")
        # default_rules defined in YAML -> trim_whitespace
        assert default_rules == ["trim_whitespace"]
