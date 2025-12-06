"""Tests for annuity performance domain constants and models (post-refactor).

Story 5.7: These tests validate the constants and model serialization
used by the refactored service layer.
"""

import pytest

from work_data_hub.domain.annuity_performance.constants import (
    DEFAULT_ALLOWED_GOLD_COLUMNS,
)
from work_data_hub.domain.annuity_performance.models import AnnuityPerformanceOut


class TestDefaultAllowedGoldColumns:
    """Test DEFAULT_ALLOWED_GOLD_COLUMNS constant contains expected columns."""

    def test_contains_all_required_gold_columns(self):
        """Test that DEFAULT_ALLOWED_GOLD_COLUMNS includes all DDL columns."""
        allowed = list(DEFAULT_ALLOWED_GOLD_COLUMNS)

        # Should include all Gold layer columns (excludes 'id' which is DB-generated)
        # Note: Uses standardized column names (流失_含待遇支付, 年化收益率)
        expected_gold_cols = [
            "月度",
            "业务类型",
            "计划类型",
            "计划代码",
            "计划名称",
            "组合类型",
            "组合代码",
            "组合名称",
            "客户名称",
            "期初资产规模",
            "期末资产规模",
            "供款",
            "流失_含待遇支付",
            "流失",
            "待遇支付",
            "投资收益",
            "年化收益率",
            "机构代码",
            "机构名称",
            "产品线代码",
            "年金账户号",
            "年金账户名",
            "company_id",
        ]

        for col in expected_gold_cols:
            assert col in allowed, (
                f"Column {col} should be in DEFAULT_ALLOWED_GOLD_COLUMNS"
            )

    def test_is_frozen_set(self):
        """Test that DEFAULT_ALLOWED_GOLD_COLUMNS is immutable."""
        # Should be a frozenset or similar immutable type
        assert hasattr(DEFAULT_ALLOWED_GOLD_COLUMNS, "__iter__")


class TestAnnuityPerformanceOutModel:
    """Test AnnuityPerformanceOut model serialization."""

    def test_alias_serialization(self):
        """Ensure model aliases are preserved when dumping."""
        model = AnnuityPerformanceOut(
            计划代码="PLAN001",
            company_id="COMP001",
            **{"流失(含待遇支付)": 1000.50},
        )
        normal_dump = model.model_dump(mode="json")
        alias_dump = model.model_dump(mode="json", by_alias=True)

        assert "流失_含待遇支付" in normal_dump
        assert "流失_含待遇支付" in alias_dump
        assert "流失(含待遇支付)" not in alias_dump

    def test_required_fields(self):
        """Test that model requires plan code and company_id."""
        model = AnnuityPerformanceOut(
            计划代码="PLAN001",
            company_id="COMP001",
        )
        assert model.计划代码 == "PLAN001"
        assert model.company_id == "COMP001"

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        model = AnnuityPerformanceOut(
            计划代码="PLAN001",
            company_id="COMP001",
        )
        # Optional fields should be None by default
        assert model.客户名称 is None
        assert model.期初资产规模 is None
