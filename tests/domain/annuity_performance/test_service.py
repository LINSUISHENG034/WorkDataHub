"""
Tests for annuity performance domain service.

This module tests the pure transformation functions in the annuity performance
domain service with various input scenarios, column projection, and edge cases
for Chinese "规模明细" data.
"""

from datetime import date

import pytest

from src.work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
)
from src.work_data_hub.domain.annuity_performance.service import (
    AnnuityPerformanceTransformationError,
    _extract_company_code,
    _extract_plan_code,
    _extract_report_date,
    get_allowed_columns,
    project_columns,
)


@pytest.fixture
def valid_row_chinese():
    """Sample valid row with Chinese field names for annuity performance."""
    return {
        "年": "2024",
        "月": "11",
        "计划代码": "PLAN001",
        "客户名称": "测试企业有限公司",
        "期初资产规模": "1000000.50",
        "期末资产规模": "1050000.25",
        "投资收益": "49999.75",
        "当期收益率": "5.0%",
        "业务类型": "企业年金",
        "组合代码": "PORTFOLIO001",
    }


@pytest.fixture
def valid_row_with_date():
    """Sample valid row with 月度 date field."""
    return {
        "月度": "2024-11-01",
        "计划代码": "PLAN002",
        "company_id": "COMP002",
        "期初资产规模": "2000000.00",
        "当期收益率": "0.045",
    }


@pytest.fixture
def row_with_extra_columns():
    """Sample row with extra columns that should be filtered out."""
    return {
        "年": "2024",
        "月": "11",
        "计划代码": "PLAN003",
        "客户名称": "测试客户",
        "期初资产规模": "500000.00",
        # Extra columns that don't exist in DDL
        "extra_column_1": "should_be_removed",
        "unknown_field": 12345,
        "temp_calculation": "temporary_value",
    }


class TestColumnProjection:
    """Test column projection functionality for safe SQL loading."""

    def test_get_allowed_columns(self):
        """Test that allowed columns include all DDL columns."""
        allowed = get_allowed_columns()

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
            assert col in allowed, f"Column {col} should be in allowed columns"

        # Do not assume non-DDL helper fields exist in allowed set
        # (实际规模明细原始数据不包含 年/月/公司代码/报告日期 这些模拟字段)

    def test_project_columns_filters_extra(self, row_with_extra_columns):
        """Test that project_columns removes extra columns."""
        rows = [row_with_extra_columns]
        allowed = ["年", "月", "计划代码", "客户名称", "期初资产规模"]

        projected = project_columns(rows, allowed)

        assert len(projected) == 1
        projected_row = projected[0]

        # Should keep allowed columns
        assert "年" in projected_row
        assert "计划代码" in projected_row

        # Should remove extra columns
        assert "extra_column_1" not in projected_row
        assert "unknown_field" not in projected_row
        assert "temp_calculation" not in projected_row

    def test_project_columns_empty_rows(self):
        """Test column projection with empty input."""
        result = project_columns([], ["年", "月"])
        assert result == []

    def test_project_columns_preserves_values(self):
        """Test that column projection preserves values for kept columns."""
        rows = [{"年": "2024", "计划代码": "TEST001", "extra": "remove_me"}]
        allowed = ["年", "计划代码"]

        projected = project_columns(rows, allowed)

        assert len(projected) == 1
        assert projected[0]["年"] == "2024"
        assert projected[0]["计划代码"] == "TEST001"
        assert "extra" not in projected[0]


# Story 4.9: TestProcess removed (tested deleted process() function)


class TestExtractFunctions:
    """Test individual extraction functions."""

    def test_extract_report_date_from_年月(self):
        """Test date extraction from 年/月 fields."""
        model = AnnuityPerformanceIn(年="2024", 月="11")
        result = _extract_report_date(model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_report_date_from_月度(self):
        """Test date extraction from 月度 field."""
        model = AnnuityPerformanceIn(月度=date(2024, 11, 1))
        result = _extract_report_date(model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_report_date_2digit_year(self):
        """Test date extraction with 2-digit year."""
        model = AnnuityPerformanceIn(年="24", 月="11")  # Should become 2024
        result = _extract_report_date(model, 0)

        assert result == date(2024, 11, 1)

    def test_extract_report_date_invalid_returns_none(self):
        """Test that invalid date returns None."""
        model = AnnuityPerformanceIn(年="invalid", 月="not_a_month")
        result = _extract_report_date(model, 0)

        assert result is None

    def test_extract_plan_code_chinese(self):
        """Test plan code extraction from Chinese field."""
        model = AnnuityPerformanceIn(计划代码="PLAN001")
        result = _extract_plan_code(model, 0)

        assert result == "PLAN001"

    def test_extract_plan_code_missing_returns_none(self):
        """Test plan code extraction when missing."""
        model = AnnuityPerformanceIn()
        result = _extract_plan_code(model, 0)

        assert result is None

    def test_extract_plan_code_no_f_prefix_stripping(self):
        """Test that F-prefix is NOT stripped from 计划代码 (plan code)."""
        # F-prefix should NOT be stripped from plan code anymore
        model = AnnuityPerformanceIn(计划代码="FPLAN001", 组合代码="FPORTFOLIO001")
        result = _extract_plan_code(model, 0)
        assert result == "FPLAN001", "F-prefix should NOT be stripped from plan code"

        # Test without F prefix (should not change)
        model = AnnuityPerformanceIn(计划代码="PLAN002", 组合代码="PORTFOLIO002")
        result = _extract_plan_code(model, 0)
        assert result == "PLAN002", "Non-F codes should not change"

        # Test F prefix without 组合代码 field (should not strip)
        model = AnnuityPerformanceIn(计划代码="FPLAN003")  # No 组合代码
        result = _extract_plan_code(model, 0)
        assert result == "FPLAN003", "F prefix should never be stripped from plan code"

    # Story 4.9: test_strip_f_prefix_from_portfolio_code removed (tested deleted function)

    def test_alias_serialization(self):
        """Test that model serialization uses aliases for column mapping."""
        from src.work_data_hub.domain.annuity_performance.models import AnnuityPerformanceOut

        # Create a model with aliased field - use the validation alias
        model = AnnuityPerformanceOut(
            计划代码="PLAN001",
            company_id="COMP001",
            **{"流失(含待遇支付)": 1000.50},  # Use validation alias in dict
        )

        # Test serialization without aliases (should use field names)
        normal_dump = model.model_dump(mode="json")
        assert "流失_含待遇支付" in normal_dump

        # Test serialization with aliases (should use alias names)
        alias_dump = model.model_dump(mode="json", by_alias=True)
        assert "流失(含待遇支付)" in alias_dump  # Should use alias
        assert "流失_含待遇支付" not in alias_dump  # Should not use field name

        # Test exclude_none functionality
        model_with_none = AnnuityPerformanceOut(
            计划代码="PLAN001", company_id="COMP001", **{"流失(含待遇支付)": None}
        )

        normal_dump_with_none = model_with_none.model_dump(mode="json")
        assert "流失_含待遇支付" in normal_dump_with_none  # Should include None field

        exclude_none_dump = model_with_none.model_dump(mode="json", exclude_none=True)
        assert "流失_含待遇支付" not in exclude_none_dump  # Should exclude None field

    def test_extract_company_code_from_company_id(self):
        """Test company code extraction from company_id field."""
        model = AnnuityPerformanceIn(company_id="COMP001")
        result = _extract_company_code(model, 0)

        assert result == "COMP001"

    def test_extract_company_code_from_chinese_field(self):
        """Test company code extraction from 公司代码 field."""
        model = AnnuityPerformanceIn(公司代码="COMP002")
        result = _extract_company_code(model, 0)

        assert result == "COMP002"

    def test_extract_company_code_from_customer_name(self):
        """Test company code derivation from customer name."""
        model = AnnuityPerformanceIn(客户名称="测试企业有限公司")
        result = _extract_company_code(model, 0)

        assert result == "测试企业"  # Should remove common suffixes

    def test_extract_company_code_truncates_long_names(self):
        """Test that very long company names are truncated."""
        long_name = "非常长的公司名称" * 10  # Very long name
        model = AnnuityPerformanceIn(客户名称=long_name)
        result = _extract_company_code(model, 0)

        assert len(result) <= 20  # Should be truncated


# Story 4.9: TestReportPeriodParsing and TestValidateInputBatch removed (tested deleted functions)
