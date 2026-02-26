"""Unit tests for customer status rules configuration schema.

Story 7.6-18: Config-Driven Status Evaluation Framework
"""

import pytest

from work_data_hub.infrastructure.settings.customer_status_schema import (
    CustomerStatusConfigError,
    CustomerStatusRulesConfig,
    load_customer_status_config,
)


class TestCustomerStatusRulesConfig:
    """Tests for CustomerStatusRulesConfig Pydantic model."""

    def test_load_config_from_file(self):
        """Test loading config from actual file."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        assert config.schema_version == "1.0"
        assert "annual_award" in config.sources
        assert "annual_loss" in config.sources
        assert "is_winning_this_year" in config.status_definitions
        assert "is_winning_this_year" in config.evaluation_rules

    def test_source_config_structure(self):
        """Test source configuration is properly parsed."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        annual_award = config.sources["annual_award"]
        assert annual_award.schema_name == "customer"
        assert annual_award.table == "中标客户明细"
        assert "company_id" in annual_award.key_fields

    def test_status_definition_structure(self):
        """Test status definition is properly parsed."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        winning = config.status_definitions["is_winning_this_year"]
        assert winning.source == "annual_award"
        assert winning.time_scope == "yearly"
        assert "新中标" in winning.description

    def test_evaluation_rule_structure(self):
        """Test evaluation rule is properly parsed."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        rule = config.evaluation_rules["is_winning_this_year"]
        assert rule.granularity == "product_line"
        assert len(rule.conditions) >= 1
        assert rule.conditions[0].type == "exists_in_year"

    def test_invalid_config_path_raises_error(self):
        """Test that invalid path raises CustomerStatusConfigError."""
        with pytest.raises(CustomerStatusConfigError) as exc_info:
            load_customer_status_config("nonexistent/path.yml")

        assert "not found" in str(exc_info.value)

    def test_config_has_all_required_status_fields(self):
        """Test config defines all required status fields."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        required_statuses = [
            "is_winning_this_year",
            "is_loss_reported",
            "is_churned_this_year",
            "is_new",
        ]

        for status in required_statuses:
            assert status in config.status_definitions, f"Missing: {status}"
            assert status in config.evaluation_rules, f"Missing rule: {status}"
