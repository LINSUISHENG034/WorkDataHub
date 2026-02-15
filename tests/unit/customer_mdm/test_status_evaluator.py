"""Unit tests for StatusEvaluator class.

Story 7.6-18: Config-Driven Status Evaluation Framework
"""

from unittest.mock import MagicMock

import pytest

from work_data_hub.customer_mdm.status_evaluator import StatusEvaluator


class TestStatusEvaluator:
    """Tests for StatusEvaluator SQL generation."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_init_loads_config(self, evaluator: StatusEvaluator):
        """Test evaluator loads configuration on init."""
        assert evaluator.config is not None
        assert len(evaluator.config.evaluation_rules) > 0

    def test_get_status_names(self, evaluator: StatusEvaluator):
        """Test get_status_names returns configured statuses."""
        names = evaluator.get_status_names()
        assert "is_winning_this_year" in names
        assert "is_loss_reported" in names

    def test_get_status_description(self, evaluator: StatusEvaluator):
        """Test get_status_description returns description."""
        desc = evaluator.get_status_description("is_winning_this_year")
        assert "新中标" in desc

    def test_generate_exists_in_year_sql(self, evaluator: StatusEvaluator):
        """Test exists_in_year generates correct SQL."""
        sql = evaluator.generate_sql_fragment(
            "is_winning_this_year",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        assert "EXISTS" in sql
        assert "当年中标" in sql
        assert "company_id" in sql
        assert "产品线代码" in sql
        assert "EXTRACT(YEAR FROM" in sql
        assert "snapshot_year" in sql

    def test_generate_loss_reported_sql(self, evaluator: StatusEvaluator):
        """Test is_loss_reported generates correct SQL."""
        sql = evaluator.generate_sql_fragment(
            "is_loss_reported",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        assert "EXISTS" in sql
        assert "当年流失" in sql

    def test_generate_churned_sql(self, evaluator: StatusEvaluator):
        """Test is_churned_this_year generates correct SQL."""
        sql = evaluator.generate_sql_fragment(
            "is_churned_this_year",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        assert "EXISTS" in sql
        assert "当年流失" in sql

    def test_generate_is_new_sql(self, evaluator: StatusEvaluator):
        """Test is_new generates combined SQL with AND."""
        sql = evaluator.generate_sql_fragment(
            "is_new",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        # is_new = is_winning AND NOT is_existing
        assert "EXISTS" in sql or "BOOL_OR" in sql

    def test_unknown_status_raises_error(self, evaluator: StatusEvaluator):
        """Test unknown status raises KeyError."""
        with pytest.raises(KeyError):
            evaluator.generate_sql_fragment(
                "nonexistent_status",
                table_alias="c",
                params={},
            )

    def test_plan_level_churned_sql(self, evaluator: StatusEvaluator):
        """Test plan-level churn generates correct SQL."""
        sql = evaluator.generate_sql_fragment(
            "is_churned_this_year_plan",
            table_alias="c",
            params={"snapshot_year": 2026},
        )

        assert "EXISTS" in sql
        assert "年金计划号" in sql


class TestDisappearedCondition:
    """Tests for disappeared condition type."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_generate_disappeared_sql(self, evaluator: StatusEvaluator):
        """Test disappeared generates correct SQL pattern."""
        # Create mock condition
        condition = MagicMock()
        condition.source = "annuity_performance"
        condition.period_field = "snapshot_month"
        condition.scope_field = None
        condition.match_fields = [
            MagicMock(source_field="company_id", target_field="company_id"),
            MagicMock(
                source_field="product_line_code", target_field="product_line_code"
            ),
        ]

        rule = MagicMock()
        params = {}

        sql = evaluator._generate_disappeared(condition, "c", params, rule)

        # Should have EXISTS for previous period
        assert "EXISTS" in sql
        # Should have NOT EXISTS for current period
        assert "NOT EXISTS" in sql
        # Should reference the source table
        assert "规模明细" in sql
        # Should use interval for previous month
        assert "INTERVAL '1 month'" in sql
        # Should match on company_id
        assert "company_id" in sql

    def test_generate_disappeared_with_scope(self, evaluator: StatusEvaluator):
        """Test disappeared with scope_field generates correct SQL."""
        condition = MagicMock()
        condition.source = "annuity_performance"
        condition.period_field = "snapshot_month"
        condition.scope_field = "product_line_code"
        condition.match_fields = [
            MagicMock(source_field="company_id", target_field="company_id"),
        ]

        rule = MagicMock()
        params = {}

        sql = evaluator._generate_disappeared(condition, "c", params, rule)

        # Should include scope field in conditions
        assert "product_line_code" in sql


class TestFirstAppearanceCondition:
    """Tests for first_appearance condition type."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_generate_first_appearance_sql(self, evaluator: StatusEvaluator):
        """Test first_appearance generates correct SQL pattern."""
        condition = MagicMock()
        condition.source = "annuity_performance"
        condition.period_field = "snapshot_month"
        condition.scope_field = None
        condition.match_fields = [
            MagicMock(source_field="company_id", target_field="company_id"),
            MagicMock(
                source_field="product_line_code", target_field="product_line_code"
            ),
        ]

        rule = MagicMock()
        params = {}

        sql = evaluator._generate_first_appearance(condition, "c", params, rule)

        # Should have NOT EXISTS for historical records
        assert "NOT EXISTS" in sql
        # Should reference the source table
        assert "规模明细" in sql
        # Should check for records before current period
        assert "<" in sql
        # Should match on company_id
        assert "company_id" in sql

    def test_generate_first_appearance_with_scope(self, evaluator: StatusEvaluator):
        """Test first_appearance with scope_field generates correct SQL."""
        condition = MagicMock()
        condition.source = "annuity_performance"
        condition.period_field = "snapshot_month"
        condition.scope_field = "product_line_code"
        condition.match_fields = [
            MagicMock(source_field="company_id", target_field="company_id"),
        ]

        rule = MagicMock()
        params = {}

        sql = evaluator._generate_first_appearance(condition, "c", params, rule)

        # Should include scope field
        assert "product_line_code" in sql


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    @pytest.fixture
    def evaluator(self) -> StatusEvaluator:
        """Create StatusEvaluator instance."""
        return StatusEvaluator("config/customer_status_rules.yml")

    def test_invalid_field_name_raises_error(self, evaluator: StatusEvaluator):
        """Test invalid field names are rejected."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            evaluator._validate_identifier("field; DROP TABLE", "test")

    def test_valid_chinese_field_name_accepted(self, evaluator: StatusEvaluator):
        """Test Chinese field names are accepted."""
        result = evaluator._validate_identifier("产品线代码", "test")
        assert result == "产品线代码"

    def test_valid_alphanumeric_field_accepted(self, evaluator: StatusEvaluator):
        """Test alphanumeric field names are accepted."""
        result = evaluator._validate_identifier("company_id_123", "test")
        assert result == "company_id_123"

    def test_field_equals_uses_parameters(self, evaluator: StatusEvaluator):
        """Test field_equals uses parameterized queries."""
        condition = MagicMock()
        condition.field = "status"
        condition.value = "active'; DROP TABLE users; --"

        rule = MagicMock()
        params = {}

        sql = evaluator._generate_field_equals(condition, "c", params, rule)

        # Should NOT contain the raw value
        assert "DROP TABLE" not in sql
        # Should use parameter placeholder
        assert "%(" in sql
        assert ")s" in sql
        # Value should be in params dict
        assert any("active" in str(v) for v in params.values())
