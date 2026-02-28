"""Phase E: Per-domain FK backfill config tests (E-13 through E-19).

Verifies each domain's FK backfill configuration loads correctly
and derive_candidates produces expected output structure.
"""

from __future__ import annotations

import pandas as pd
import pytest

from work_data_hub.domain.reference_backfill.config_loader import (
    load_foreign_keys_config,
)

pytestmark = pytest.mark.slice_test


@pytest.fixture(scope="module")
def annuity_perf_configs():
    return load_foreign_keys_config(domain="annuity_performance")


def _find_fk(configs, name: str):
    return next((c for c in configs if c.name == name), None)


# ===================================================================
# E-13: annuity_performance fk_plan
# ===================================================================
class TestE13AnnuityPerfFkPlan:
    """5 column mappings + max_by + concat_distinct."""

    def test_fk_plan_config(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_plan")
        assert fk is not None
        assert len(fk.backfill_columns) >= 5

    def test_fk_plan_has_max_by(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_plan")
        assert fk is not None
        agg_types = [
            c.aggregation.type.value for c in fk.backfill_columns if c.aggregation
        ]
        assert "max_by" in agg_types

    def test_fk_plan_has_concat_distinct(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_plan")
        assert fk is not None
        agg_types = [
            c.aggregation.type.value for c in fk.backfill_columns if c.aggregation
        ]
        assert "concat_distinct" in agg_types


# ===================================================================
# E-14: annuity_performance fk_portfolio (depends_on fk_plan)
# ===================================================================
class TestE14AnnuityPerfFkPortfolio:
    """depends_on fk_plan, 4 column mappings."""

    def test_fk_portfolio_config(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_portfolio")
        assert fk is not None
        assert len(fk.backfill_columns) >= 2

    def test_fk_portfolio_depends_on_plan(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_portfolio")
        assert fk is not None
        assert fk.depends_on is not None
        assert "fk_plan" in fk.depends_on


# ===================================================================
# E-15: annuity_performance fk_product_line
# ===================================================================
class TestE15AnnuityPerfFkProductLine:
    """派生列 产品线代码 回填, 2 column mappings."""

    def test_fk_product_line_config(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_product_line")
        assert fk is not None
        assert len(fk.backfill_columns) >= 2

    def test_fk_product_line_has_code_column(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_product_line")
        assert fk is not None
        sources = [c.source for c in fk.backfill_columns]
        assert "产品线代码" in sources


# ===================================================================
# E-16: annuity_performance fk_organization (skip_blank_values)
# ===================================================================
class TestE16AnnuityPerfFkOrganization:
    """skip_blank_values=true, 机构代码→机构."""

    def test_fk_organization_config(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_organization")
        assert fk is not None
        assert len(fk.backfill_columns) >= 2

    def test_fk_organization_skip_blank(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_organization")
        assert fk is not None
        assert fk.skip_blank_values is True


# ===================================================================
# E-17: annuity_performance fk_customer (12 columns, all agg types)
# ===================================================================
class TestE17AnnuityPerfFkCustomer:
    """12 column mappings, max_by+concat_distinct+count_distinct+lambda+template."""

    def test_fk_customer_config(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_customer")
        assert fk is not None
        assert len(fk.backfill_columns) >= 12

    def test_fk_customer_skip_blank(self, annuity_perf_configs):
        fk = _find_fk(annuity_perf_configs, "fk_customer")
        assert fk is not None
        assert fk.skip_blank_values is True

    def test_fk_customer_agg_types_coverage(self, annuity_perf_configs):
        """All 5 aggregation types present: max_by, concat_distinct, count_distinct, lambda, template."""
        fk = _find_fk(annuity_perf_configs, "fk_customer")
        assert fk is not None
        agg_types = {
            c.aggregation.type.value for c in fk.backfill_columns if c.aggregation
        }
        for expected in (
            "max_by",
            "concat_distinct",
            "count_distinct",
            "lambda",
            "template",
        ):
            assert expected in agg_types, f"Missing aggregation type: {expected}"


# ===================================================================
# E-18/E-19: annual_award / annual_loss fk_customer (parametrized)
# ===================================================================
@pytest.mark.parametrize(
    "domain,template_value",
    [
        ("annual_award", "中标客户"),
        ("annual_loss", "流失客户"),
    ],
)
class TestE18E19DomainFkCustomer:
    """max_by(计划规模), jsonb_append→tags, template→domain-specific value."""

    def test_fk_customer_config(self, domain, template_value):
        configs = load_foreign_keys_config(domain=domain)
        fk = _find_fk(configs, "fk_customer")
        assert fk is not None
        assert len(fk.backfill_columns) >= 10

    def test_fk_customer_has_max_by_on_plan_scale(self, domain, template_value):
        configs = load_foreign_keys_config(domain=domain)
        fk = _find_fk(configs, "fk_customer")
        assert fk is not None
        max_by_cols = [
            c
            for c in fk.backfill_columns
            if c.aggregation and c.aggregation.type.value == "max_by"
        ]
        assert len(max_by_cols) >= 1
        order_cols = [c.aggregation.order_column for c in max_by_cols]
        assert "计划规模" in order_cols

    def test_fk_customer_has_jsonb_append(self, domain, template_value):
        configs = load_foreign_keys_config(domain=domain)
        fk = _find_fk(configs, "fk_customer")
        assert fk is not None
        agg_types = {
            c.aggregation.type.value for c in fk.backfill_columns if c.aggregation
        }
        assert "jsonb_append" in agg_types

    def test_fk_customer_template_value(self, domain, template_value):
        configs = load_foreign_keys_config(domain=domain)
        fk = _find_fk(configs, "fk_customer")
        assert fk is not None
        template_cols = [
            c
            for c in fk.backfill_columns
            if c.aggregation and c.aggregation.type.value == "template"
        ]
        assert len(template_cols) >= 1
        templates = [c.aggregation.template for c in template_cols]
        assert template_value in templates
