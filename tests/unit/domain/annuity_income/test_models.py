"""
Unit tests for AnnuityIncome models module.

Story 5.5.2: AnnuityIncome Domain Implementation
AC 7: Follows same patterns as annuity_performance domain

Tests:
- AnnuityIncomeIn permissive input model
- AnnuityIncomeOut strict output model
- Field validation and cleansing
- EnrichmentStats tracking
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

# Import directly from models module to avoid circular import via __init__
from work_data_hub.domain.annuity_income.models import (
    AnnuityIncomeIn,
    AnnuityIncomeOut,
    EnrichmentStats,
    ProcessingResultWithEnrichment,
)


class TestAnnuityIncomeIn:
    """Tests for AnnuityIncomeIn permissive input model."""

    def test_accepts_valid_data(self):
        """Model accepts valid input data."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "202412",
            "计划代码": "FP0001",
            "客户名称": "测试公司",
            "业务类型": "企年投资",
            "固费": 500000.0,
            "浮费": 300000.0,
            "回补": 200000.0,
            "税": 50000.0,
        }
        model = AnnuityIncomeIn(**data)
        assert model.计划代码 == "FP0001"
        assert model.客户名称 == "测试公司"
        assert model.固费 == 500000.0

    def test_allows_extra_fields(self):
        """Model allows extra fields (extra='allow')."""
        data = {
            "月度": "202412",
            "计划代码": "FP0001",
            "客户名称": "测试公司",
            "unknown_field": "should be allowed",
        }
        model = AnnuityIncomeIn(**data)
        assert (
            hasattr(model, "unknown_field")
            or model.model_extra.get("unknown_field") == "should be allowed"
        )

    def test_strips_whitespace(self):
        """Model strips whitespace from string fields."""
        data = {
            "计划代码": "  FP0001  ",
            "客户名称": "  测试公司  ",
        }
        model = AnnuityIncomeIn(**data)
        assert model.计划代码 == "FP0001"
        assert model.客户名称 == "测试公司"

    def test_converts_nan_to_none(self):
        """Model converts NaN values to None."""
        import math

        # Story 5.5.5: Updated to use 固费 instead of 收入金额
        data = {
            "计划代码": "FP0001",
            "固费": float("nan"),
        }
        model = AnnuityIncomeIn(**data)
        assert model.固费 is None

    def test_cleans_numeric_fields(self):
        """Model cleans numeric fields with currency symbols."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "计划代码": "FP0001",
            "固费": "1,000,000.00",
            "浮费": "500,000.00",
            "回补": "200,000.00",
            "税": "50,000.00",
        }
        model = AnnuityIncomeIn(**data)
        assert model.固费 == 1000000.0
        assert model.浮费 == 500000.0

    def test_preprocesses_report_date(self):
        """Model preprocesses YYYYMM integer to string."""
        data = {
            "月度": 202412,
            "计划代码": "FP0001",
        }
        model = AnnuityIncomeIn(**data)
        assert model.月度 == "202412"

    def test_cleans_code_fields(self):
        """Model cleans code fields by stripping whitespace."""
        data = {
            "计划代码": "  FP0001  ",
            "机构代码": "  G00  ",
            "company_id": "  COMP123  ",
        }
        model = AnnuityIncomeIn(**data)
        assert model.计划代码 == "FP0001"
        assert model.机构代码 == "G00"
        assert model.company_id == "COMP123"


class TestAnnuityIncomeOut:
    """Tests for AnnuityIncomeOut strict output model."""

    def test_requires_plan_code(self):
        """Model requires 计划代码 field."""
        data = {
            "月度": "2024-12-01",
            "客户名称": "测试公司",
        }
        with pytest.raises(ValidationError) as exc_info:
            AnnuityIncomeOut(**data)
        assert "计划代码" in str(exc_info.value)

    def test_forbids_extra_fields(self):
        """Model forbids extra fields (extra='forbid')."""
        data = {
            "月度": "2024-12-01",
            "计划代码": "FP0001",
            "客户名称": "测试公司",
            "unknown_field": "should fail",
        }
        with pytest.raises(ValidationError):
            AnnuityIncomeOut(**data)

    def test_parses_date_field(self):
        """Model parses various date formats."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "202412",
            "计划代码": "FP0001",
            "company_id": "COMP001",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 100.0,
            "浮费": 50.0,
            "回补": 30.0,
            "税": 10.0,
        }
        model = AnnuityIncomeOut(**data)
        assert isinstance(model.月度, date)
        assert model.月度.year == 2024
        assert model.月度.month == 12

    def test_normalizes_plan_code(self):
        """Model normalizes plan code to uppercase."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "2024-12-01",
            "计划代码": "fp0001",
            "company_id": "COMP123",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 10.0,
            "浮费": 5.0,
            "回补": 3.0,
            "税": 1.0,
        }
        model = AnnuityIncomeOut(**data)
        assert model.计划代码 == "FP0001"

    def test_normalizes_company_id(self):
        """Model normalizes company_id to uppercase."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "2024-12-01",
            "计划代码": "FP0001",
            "company_id": "comp123",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 10.0,
            "浮费": 5.0,
            "回补": 3.0,
            "税": 1.0,
        }
        model = AnnuityIncomeOut(**data)
        assert model.company_id == "COMP123"

    def test_cleans_decimal_fields(self):
        """Model cleans decimal fields."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "2024-12-01",
            "计划代码": "FP0001",
            "company_id": "COMP123",
            "固费": "1,000,000.00",
            "浮费": "500,000.00",
            "回补": "200,000.00",
            "税": "50,000.00",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
        }
        model = AnnuityIncomeOut(**data)
        assert isinstance(model.固费, Decimal)

    def test_validates_future_date(self):
        """Model rejects future dates."""
        from datetime import timedelta

        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        future_date = date.today() + timedelta(days=30)
        data = {
            "月度": future_date.isoformat(),
            "计划代码": "FP0001",
            "company_id": "COMP123",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 10.0,
            "浮费": 5.0,
            "回补": 3.0,
            "税": 1.0,
        }
        with pytest.raises(ValidationError) as exc_info:
            AnnuityIncomeOut(**data)
        assert "future" in str(exc_info.value).lower()

    def test_accepts_valid_complete_data(self):
        """Model accepts valid complete data."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        data = {
            "月度": "2024-12-01",
            "计划代码": "FP0001",
            "company_id": "COMP123",
            "客户名称": "测试公司",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 500000.0,
            "浮费": 300000.0,
            "回补": 200000.0,
            "税": 50000.0,
            "业务类型": "企年投资",
            "计划类型": "单一计划",
            "组合代码": "QTAN001",
            "年金账户名": "测试公司年金账户",
        }
        model = AnnuityIncomeOut(**data)
        assert model.计划代码 == "FP0001"
        assert model.company_id == "COMP123"
        assert model.固费 == 500000.0

    def test_accepts_null_customer_name_and_company_id(self):
        """Story 7.3-1: Model accepts null 客户名称 and company_id."""
        data = {
            "月度": "2024-12-01",
            "计划代码": "FP0001",
            "客户名称": None,  # Explicitly null - Story 7.3-1
            "company_id": None,  # Explicitly null - Story 7.3-1
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 10.0,
            "浮费": 5.0,
            "回补": 3.0,
            "税": 1.0,
        }
        model = AnnuityIncomeOut(**data)
        assert model.客户名称 is None
        assert model.company_id is None
        # Verify other required fields still work
        assert model.计划代码 == "FP0001"
        assert model.产品线代码 == "PL201"


class TestEnrichmentStats:
    """Tests for EnrichmentStats model."""

    def test_default_values(self):
        """Stats have correct default values."""
        stats = EnrichmentStats()
        assert stats.total_records == 0
        assert stats.success_internal == 0
        assert stats.success_external == 0
        assert stats.pending_lookup == 0
        assert stats.temp_assigned == 0
        assert stats.failed == 0

    def test_record_increments_counters(self):
        """Record method increments appropriate counters."""
        from work_data_hub.domain.company_enrichment.models import ResolutionStatus

        stats = EnrichmentStats()
        stats.record(ResolutionStatus.SUCCESS_INTERNAL)
        assert stats.total_records == 1
        assert stats.success_internal == 1

        stats.record(ResolutionStatus.SUCCESS_EXTERNAL)
        assert stats.total_records == 2
        assert stats.success_external == 1
        assert stats.sync_budget_used == 1

        stats.record(ResolutionStatus.TEMP_ASSIGNED)
        assert stats.total_records == 3
        assert stats.temp_assigned == 1


class TestProcessingResultWithEnrichment:
    """Tests for ProcessingResultWithEnrichment model."""

    def test_default_values(self):
        """Result has correct default values."""
        result = ProcessingResultWithEnrichment(records=[])
        assert result.records == []
        assert result.data_source == "unknown"
        assert result.processing_time_ms == 0
        assert result.unknown_names_csv is None

    def test_accepts_records(self):
        """Result accepts list of AnnuityIncomeOut records."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        record = AnnuityIncomeOut(
            月度="2024-12-01",
            计划代码="FP0001",
            company_id="COMP001",
            客户名称="测试公司",
            产品线代码="PL201",
            机构代码="G00",
            固费=1.0,
            浮费=0.5,
            回补=0.3,
            税=0.1,
        )
        result = ProcessingResultWithEnrichment(
            records=[record],
            data_source="test.xlsx",
            processing_time_ms=100,
        )
        assert len(result.records) == 1
        assert result.data_source == "test.xlsx"
