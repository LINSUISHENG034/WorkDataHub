"""Phase G: Monthly snapshot & status evaluation tests (G-1 through G-6).

Verifies StatusEvaluator config parsing, SQL fragment generation
for all condition types, and snapshot refresh SQL structure.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

from work_data_hub.customer_mdm.snapshot_refresh import (
    get_current_period,
    period_to_snapshot_month,
)
from work_data_hub.customer_mdm.status_evaluator import StatusEvaluator

pytestmark = pytest.mark.slice_test

CONFIG_PATH = "config/customer_status_rules.yml"


@pytest.fixture(scope="module")
def evaluator():
    return StatusEvaluator(config_path=CONFIG_PATH)


# ===================================================================
# G-1: StatusEvaluator config parsing
# ===================================================================
class TestG1StatusEvaluatorConfig:
    """customer_status_rules.yml loads and validates via Pydantic."""

    def test_config_loads(self, evaluator):
        assert evaluator is not None

    def test_status_names_present(self, evaluator):
        names = evaluator.get_status_names()
        assert len(names) >= 3
        assert "is_winning_this_year" in names
        assert "is_new" in names


# ===================================================================
# G-2: exists_in_year operator
# ===================================================================
class TestG2ExistsInYear:
    """Generates EXISTS subquery with EXTRACT(YEAR FROM ...) filter."""

    def test_exists_in_year_sql(self, evaluator):
        params = {"snapshot_year": 2025}
        sql = evaluator.generate_sql_fragment(
            "is_winning_this_year",
            table_alias="c",
            params=params,
        )
        assert "EXISTS" in sql.upper()
        assert "EXTRACT" in sql.upper() or "snapshot_year" in sql


# ===================================================================
# G-3: status_reference operator
# ===================================================================
class TestG3StatusReference:
    """is_new references is_winning_this_year recursively."""

    def test_is_new_references_winning(self, evaluator):
        params = {"snapshot_year": 2025}
        sql = evaluator.generate_sql_fragment(
            "is_new",
            table_alias="c",
            params=params,
        )
        # is_new should contain the EXISTS from is_winning_this_year
        assert "EXISTS" in sql.upper()


# ===================================================================
# G-4: negation + aggregated_field
# ===================================================================
class TestG4NegationAggregatedField:
    """NOT BOOL_OR(c.is_existing) generation."""

    def test_is_new_has_negation(self, evaluator):
        params = {"snapshot_year": 2025}
        sql = evaluator.generate_sql_fragment(
            "is_new",
            table_alias="c",
            params=params,
        )
        assert "NOT" in sql.upper()
        assert "BOOL_OR" in sql.upper() or "is_existing" in sql


# ===================================================================
# G-5: Product line snapshot refresh SQL
# ===================================================================
class TestG5ProductLineSnapshot:
    """INSERT...ON CONFLICT DO UPDATE for 客户业务月度快照."""

    def test_period_to_snapshot_month(self):
        result = period_to_snapshot_month("202510")
        assert "2025" in result
        assert "10" in result

    def test_get_current_period_format(self):
        with patch("work_data_hub.customer_mdm.snapshot_refresh.date") as mock_date:
            mock_date.today.return_value = date(2025, 10, 15)
            period = get_current_period()
            assert period == "202510"


# ===================================================================
# G-6: Plan snapshot refresh (is_churned_this_year_plan)
# ===================================================================
class TestG6PlanSnapshot:
    """Plan-level snapshot uses is_churned_this_year_plan status."""

    def test_churned_plan_status_exists(self, evaluator):
        names = evaluator.get_status_names()
        assert "is_churned_this_year_plan" in names

    def test_churned_plan_sql_fragment(self, evaluator):
        params = {"snapshot_year": 2025}
        sql = evaluator.generate_sql_fragment(
            "is_churned_this_year_plan",
            table_alias="c",
            params=params,
        )
        assert "EXISTS" in sql.upper()
        assert "snapshot_year" in sql or "EXTRACT" in sql.upper()
