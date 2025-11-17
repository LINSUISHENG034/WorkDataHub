"""Story 2.3 integration tests for annuity performance models."""

from decimal import Decimal

import pytest

from src.work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
)


@pytest.mark.unit
class TestAnnuityPerformanceCleansing:
    def test_customer_name_registry_rules_apply(self):
        model = AnnuityPerformanceOut(
            计划代码="PLAN-1",
            company_id="COMP-1",
            客户名称="「  公司　有限  」",
            期末资产规模=Decimal("0"),
        )
        assert model.客户名称 == "公司 有限"

    def test_output_model_numeric_cleaning(self):
        model = AnnuityPerformanceOut(
            计划代码="PLAN-1",
            company_id="COMP-1",
            期末资产规模="¥1,234,567.89",
            年化收益率="5.5%",
        )
        assert model.期末资产规模 == Decimal("1234567.89")
        assert model.年化收益率 == Decimal("0.055")

    def test_input_model_numeric_cleaning_preserves_float(self):
        model = AnnuityPerformanceIn(
            期末资产规模="¥1,000,000.50",
            年化收益率="5.5%",
        )
        assert model.期末资产规模 == pytest.approx(1000000.5)
        assert model.年化收益率 == pytest.approx(0.055)
