"""Integration tests for config-driven status evaluation.

Story 7.6-18: Config-Driven Status Evaluation Framework

These tests verify that the StatusEvaluator generates SQL that produces
identical results to the original hardcoded implementation.
"""

import pytest

from work_data_hub.infrastructure.settings.customer_status_schema import (
    load_customer_status_config,
)
from work_data_hub.customer_mdm.status_evaluator import StatusEvaluator


class TestStatusEvaluatorSQLGeneration:
    """Integration tests for SQL generation correctness."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_is_winning_sql_matches_original(self, evaluator: StatusEvaluator):
        """Verify is_winning_this_year SQL matches original hardcoded version."""
        sql = evaluator.generate_sql_fragment(
            "is_winning_this_year",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        # Original SQL pattern:
        # EXISTS (
        #     SELECT 1 FROM customer."中标客户明细" w
        #     WHERE w.company_id = c.company_id
        #       AND w.产品线代码 = c.product_line_code
        #       AND EXTRACT(YEAR FROM w.上报月份) = %(snapshot_year)s
        # )
        assert "EXISTS" in sql
        assert "customer" in sql
        assert "中标客户明细" in sql
        assert "company_id" in sql
        assert "产品线代码" in sql
        assert "EXTRACT(YEAR FROM" in sql
        assert "上报月份" in sql

    def test_is_churned_sql_matches_original(self, evaluator: StatusEvaluator):
        """Verify is_churned_this_year SQL matches original hardcoded version."""
        sql = evaluator.generate_sql_fragment(
            "is_churned_this_year",
            table_alias="c",
            params={"snapshot_year": 2026, "snapshot_month": "2026-01-31"},
        )

        # Current business rule:
        # COALESCE(SUM(期末资产规模), 0) = 0 for the current snapshot month
        # on business."规模明细", matched by company_id + 产品线代码.
        assert "business" in sql
        assert "规模明细" in sql
        assert "SUM(sub.期末资产规模)" in sql
        assert "company_id" in sql
        assert "产品线代码" in sql
        assert "DATE_TRUNC('month', %(snapshot_month)s::date)" in sql

    def test_plan_level_churned_sql_matches_original(self, evaluator: StatusEvaluator):
        """Verify plan-level churn SQL matches original hardcoded version."""
        sql = evaluator.generate_sql_fragment(
            "is_churned_this_year_plan",
            table_alias="c",
            params={"snapshot_year": 2026, "snapshot_month": "2026-01-31"},
        )

        # Current business rule:
        # COALESCE(SUM(期末资产规模), 0) = 0 for the current snapshot month
        # on business."规模明细", matched by company_id + plan_code (+ product line).
        assert "规模明细" in sql
        assert "SUM(sub.期末资产规模)" in sql
        assert "计划代码" in sql
        assert "plan_code" in sql

    def test_is_new_combines_winning_and_existing(self, evaluator: StatusEvaluator):
        """Verify is_new combines is_winning AND NOT is_existing."""
        sql = evaluator.generate_sql_fragment(
            "is_new",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        # is_new = is_winning_this_year AND NOT BOOL_OR(is_existing)
        assert "EXISTS" in sql or "BOOL_OR" in sql
        assert "is_existing" in sql or "中标客户明细" in sql


class TestStatusEvaluatorConfigConsistency:
    """Tests for config consistency and completeness."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_all_product_line_statuses_defined(self, evaluator: StatusEvaluator):
        """Verify all ProductLine-level statuses are defined."""
        required = ["is_winning_this_year", "is_churned_this_year", "is_new"]
        for status in required:
            sql = evaluator.generate_sql_fragment(status, "c", {"snapshot_year": 2026})
            assert sql, f"Missing SQL for {status}"

    def test_all_plan_statuses_defined(self, evaluator: StatusEvaluator):
        """Verify all Plan-level statuses are defined."""
        required = ["is_churned_this_year_plan"]
        for status in required:
            sql = evaluator.generate_sql_fragment(status, "c", {"snapshot_year": 2026})
            assert sql, f"Missing SQL for {status}"

    def test_source_tables_correctly_referenced(self, evaluator: StatusEvaluator):
        """Verify source tables are correctly referenced in SQL."""
        # annual_award -> 中标客户明细
        winning_sql = evaluator.generate_sql_fragment(
            "is_winning_this_year", "c", {"snapshot_year": 2026}
        )
        assert "中标客户明细" in winning_sql

        # annual_loss -> 流失客户明细
        churned_sql = evaluator.generate_sql_fragment(
            "is_churned_this_year",
            "c",
            {"snapshot_year": 2026, "snapshot_month": "2026-01-31"},
        )
        assert "规模明细" in churned_sql

    def test_status_definitions_align_with_exists_in_year_rules(self):
        """Definition metadata should match the rule style in config."""
        config = load_customer_status_config("config/customer_status_rules.yml")

        for status_name, definition in config.status_definitions.items():
            if definition.source == "derived":
                continue

            rule = config.evaluation_rules[status_name]
            if len(rule.conditions) != 1:
                continue

            condition = rule.conditions[0]
            if condition.type == "exists_in_year":
                assert definition.source == condition.source
                assert definition.time_scope == "yearly"
            elif condition.type == "current_period_sum_zero":
                assert definition.source == condition.source
                assert definition.time_scope == "monthly"
