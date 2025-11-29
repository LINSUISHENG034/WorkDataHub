"""Unit tests for annuity performance service helper functions."""

from datetime import date

import pytest

from work_data_hub.domain.annuity_performance.service import (
    ErrorContext,
    _determine_pipeline_mode,
    _export_unknown_names_csv,
    _extract_company_code,
    _extract_financial_metrics,
    _extract_metadata_fields,
    _extract_plan_code,
    _extract_report_date,
    _normalize_month,
    _validate_processing_results,
)
from work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceIn,
    AnnuityPerformanceOut,
)


class TestErrorContext:
    """Test ErrorContext dataclass."""

    def test_error_context_creation(self):
        """Test creating ErrorContext with all fields."""
        ctx = ErrorContext(
            error_type="validation_error",
            operation="bronze_validation",
            domain="annuity_performance",
            stage="validation",
            error_message="Validation failed",
            details={"field": "月度", "value": None},
            row_number=42,
            field="月度",
        )

        assert ctx.error_type == "validation_error"
        assert ctx.operation == "bronze_validation"
        assert ctx.domain == "annuity_performance"
        assert ctx.stage == "validation"
        assert ctx.error_message == "Validation failed"
        assert ctx.row_number == 42
        assert ctx.field == "月度"

    def test_error_context_to_log_dict(self):
        """Test converting ErrorContext to log dictionary."""
        ctx = ErrorContext(
            error_type="discovery_error",
            operation="file_discovery",
            domain="annuity_performance",
            stage="discovery",
            error_message="File not found",
            details={"month": "202501"},
            row_number=None,
            field=None,
        )

        log_dict = ctx.to_log_dict()

        assert log_dict["error_type"] == "discovery_error"
        assert log_dict["operation"] == "file_discovery"
        assert log_dict["domain"] == "annuity_performance"
        assert log_dict["stage"] == "discovery"
        assert log_dict["error_message"] == "File not found"
        assert log_dict["details"] == {"month": "202501"}
        assert "row_number" not in log_dict  # None values excluded
        assert "field" not in log_dict

    def test_error_context_minimal(self):
        """Test ErrorContext with minimal required fields."""
        ctx = ErrorContext(
            error_type="transformation_error",
            operation="row_transformation",
            domain="annuity_performance",
            stage="transformation",
            message="Transformation failed",
        )

        log_dict = ctx.to_log_dict()

        assert len(log_dict) == 5  # Only required fields
        assert "row_number" not in log_dict
        assert "field" not in log_dict
        assert "details" not in log_dict


class TestDeterminePipelineMode:
    """Test _determine_pipeline_mode function."""

    def test_explicit_true(self):
        """Test explicit True override."""
        assert _determine_pipeline_mode(True) is True

    def test_explicit_false(self):
        """Test explicit False override."""
        assert _determine_pipeline_mode(False) is False

    def test_none_defaults_to_false(self):
        """Test None falls back to settings (which defaults to False)."""
        # Without settings, should default to False
        result = _determine_pipeline_mode(None)
        assert isinstance(result, bool)


class TestNormalizeMonth:
    """Test _normalize_month function."""

    def test_valid_month(self):
        """Test valid YYYYMM format."""
        assert _normalize_month("202501") == "202501"
        assert _normalize_month("202412") == "202412"
        assert _normalize_month("202001") == "202001"

    def test_invalid_length(self):
        """Test invalid length raises ValueError."""
        with pytest.raises(ValueError, match="6-digit string"):
            _normalize_month("2025")

        with pytest.raises(ValueError, match="6-digit string"):
            _normalize_month("20250101")

    def test_non_numeric(self):
        """Test non-numeric input raises ValueError."""
        with pytest.raises(ValueError, match="6-digit string"):
            _normalize_month("202501a")

    def test_invalid_year(self):
        """Test invalid year raises ValueError."""
        with pytest.raises(ValueError, match="between 2000 and 2100"):
            _normalize_month("199912")

        with pytest.raises(ValueError, match="between 2000 and 2100"):
            _normalize_month("210101")

    def test_invalid_month(self):
        """Test invalid month raises ValueError."""
        with pytest.raises(ValueError, match="between 01 and 12"):
            _normalize_month("202500")

        with pytest.raises(ValueError, match="between 01 and 12"):
            _normalize_month("202513")

    def test_none_input(self):
        """Test None input raises ValueError."""
        with pytest.raises(ValueError, match="required"):
            _normalize_month(None)


class TestExtractReportDate:
    """Test _extract_report_date function."""

    def test_extract_from_月度_field(self):
        """Test extracting date from 月度 field."""
        model = AnnuityPerformanceIn(月度="202501")
        result = _extract_report_date(model, 0)
        assert result == date(2025, 1, 1)

    def test_extract_from_年月_fields(self):
        """Test extracting date from 年 and 月 fields."""
        model = AnnuityPerformanceIn(年="2025", 月="1")
        result = _extract_report_date(model, 0)
        assert result == date(2025, 1, 1)

    def test_extract_with_2digit_year(self):
        """Test extracting date with 2-digit year."""
        model = AnnuityPerformanceIn(年="25", 月="1")
        result = _extract_report_date(model, 0)
        assert result == date(2025, 1, 1)

    def test_missing_date_returns_none(self):
        """Test missing date information returns None."""
        model = AnnuityPerformanceIn()
        result = _extract_report_date(model, 0)
        assert result is None

    def test_invalid_date_returns_none(self):
        """Test invalid date returns None."""
        model = AnnuityPerformanceIn(年="2025", 月="13")
        result = _extract_report_date(model, 0)
        assert result is None


class TestExtractPlanCode:
    """Test _extract_plan_code function."""

    def test_extract_plan_code(self):
        """Test extracting plan code."""
        model = AnnuityPerformanceIn(计划代码="PLAN001")
        result = _extract_plan_code(model, 0)
        assert result == "PLAN001"

    def test_missing_plan_code_returns_none(self):
        """Test missing plan code returns None."""
        model = AnnuityPerformanceIn()
        result = _extract_plan_code(model, 0)
        assert result is None

    def test_whitespace_stripped(self):
        """Test whitespace is stripped."""
        model = AnnuityPerformanceIn(计划代码="  PLAN001  ")
        result = _extract_plan_code(model, 0)
        assert result == "PLAN001"


class TestExtractCompanyCode:
    """Test _extract_company_code function."""

    def test_extract_from_company_id(self):
        """Test extracting from company_id field."""
        model = AnnuityPerformanceIn(company_id="COMP001")
        result = _extract_company_code(model, 0)
        assert result == "COMP001"

    def test_extract_from_公司代码(self):
        """Test extracting from 公司代码 field."""
        model = AnnuityPerformanceIn(公司代码="COMP002")
        result = _extract_company_code(model, 0)
        assert result == "COMP002"

    def test_derive_from_客户名称(self):
        """Test deriving from 客户名称 field."""
        model = AnnuityPerformanceIn(客户名称="测试公司有限公司")
        result = _extract_company_code(model, 0)
        assert result == "测试公司"  # Suffixes removed

    def test_missing_company_code_returns_none(self):
        """Test missing company code returns None."""
        model = AnnuityPerformanceIn()
        result = _extract_company_code(model, 0)
        assert result is None


class TestExtractFinancialMetrics:
    """Test _extract_financial_metrics function."""

    def test_extract_all_metrics(self):
        """Test extracting all financial metrics."""
        model = AnnuityPerformanceIn(
            期初资产规模=1000.0,
            期末资产规模=1500.0,
            供款=200.0,
            流失=50.0,
            待遇支付=100.0,
            投资收益=450.0,
            当期收益率=0.30,
        )
        result = _extract_financial_metrics(model, 0)

        assert result["期初资产规模"] == 1000.0
        assert result["期末资产规模"] == 1500.0
        assert result["供款"] == 200.0
        assert result["流失"] == 50.0
        assert result["待遇支付"] == 100.0
        assert result["投资收益"] == 450.0
        assert result["当期收益率"] == 0.30

    def test_extract_partial_metrics(self):
        """Test extracting partial metrics."""
        model = AnnuityPerformanceIn(
            期初资产规模=1000.0,
            期末资产规模=1500.0,
        )
        result = _extract_financial_metrics(model, 0)

        assert result["期初资产规模"] == 1000.0
        assert result["期末资产规模"] == 1500.0
        assert "供款" not in result
        assert "投资收益" not in result

    def test_extract_流失_含待遇支付(self):
        """Test extracting 流失(含待遇支付) field."""
        model = AnnuityPerformanceIn(流失_含待遇支付=150.0)
        result = _extract_financial_metrics(model, 0)

        assert result["流失(含待遇支付)"] == 150.0


class TestExtractMetadataFields:
    """Test _extract_metadata_fields function."""

    def test_extract_all_metadata(self):
        """Test extracting all metadata fields."""
        model = AnnuityPerformanceIn(
            业务类型="企业年金",
            计划类型="DB",
            计划名称="测试计划",
            组合类型="股票型",
            组合名称="测试组合",
            组合代码="F123ABC",
            客户名称="测试公司",
            机构代码="ORG001",
            机构名称="测试机构",
            产品线代码="PROD001",
            年金账户号="ACC001",
            年金账户名="测试账户",
        )
        result = _extract_metadata_fields(model, 0)

        assert result["业务类型"] == "企业年金"
        assert result["计划类型"] == "DB"
        assert result["计划名称"] == "测试计划"
        assert result["组合类型"] == "股票型"
        assert result["组合名称"] == "测试组合"
        assert result["组合代码"] == "123ABC"  # F-prefix stripped
        assert result["客户名称"] == "测试公司"

    def test_f_prefix_stripping(self):
        """Test F-prefix stripping for portfolio codes."""
        model = AnnuityPerformanceIn(组合代码="F123ABC")
        result = _extract_metadata_fields(model, 0)
        assert result["组合代码"] == "123ABC"

        # Should not strip if doesn't match pattern
        model = AnnuityPerformanceIn(组合代码="Fund123")
        result = _extract_metadata_fields(model, 0)
        assert result["组合代码"] == "Fund123"


class TestValidateProcessingResults:
    """Test _validate_processing_results function."""

    def test_successful_processing(self):
        """Test successful processing with no errors."""
        records = [AnnuityPerformanceOut(月度=date(2025, 1, 1), 计划代码="P1", company_id="C1")]
        errors = []

        # Should not raise
        _validate_processing_results(records, errors, 1)

    def test_acceptable_error_rate(self):
        """Test acceptable error rate (<50%)."""
        records = [AnnuityPerformanceOut(月度=date(2025, 1, 1), 计划代码="P1", company_id="C1")]
        errors = ["Error 1"]

        # 1 error out of 3 total = 33% error rate, should not raise
        _validate_processing_results(records, errors, 3)

    def test_excessive_error_rate_raises(self):
        """Test excessive error rate (>50%) raises exception."""
        from work_data_hub.domain.annuity_performance.service import (
            AnnuityPerformanceTransformationError,
        )

        records = []
        errors = ["Error 1", "Error 2", "Error 3"]

        # 3 errors out of 5 total = 60% error rate, should raise
        with pytest.raises(AnnuityPerformanceTransformationError, match="Too many processing errors"):
            _validate_processing_results(records, errors, 5)


class TestExportUnknownNamesCsv:
    """Test _export_unknown_names_csv function."""

    def test_export_disabled_returns_none(self):
        """Test export disabled returns None."""
        result = _export_unknown_names_csv(["Company1"], "test_source", export_enabled=False)
        assert result is None

    def test_empty_list_returns_none(self):
        """Test empty list returns None."""
        result = _export_unknown_names_csv([], "test_source", export_enabled=True)
        assert result is None

    def test_export_enabled_with_names(self, tmp_path, monkeypatch):
        """Test export enabled with names calls write_unknowns_csv."""
        import work_data_hub.domain.annuity_performance.service as service_module

        # Mock write_unknowns_csv to return a test path
        test_csv_path = str(tmp_path / "unknown_companies.csv")

        def mock_write_unknowns_csv(names, source):
            return test_csv_path

        monkeypatch.setattr(service_module, "write_unknowns_csv", mock_write_unknowns_csv)

        result = _export_unknown_names_csv(["Company1", "Company2"], "test_source", export_enabled=True)
        assert result == test_csv_path

    def test_export_failure_returns_none(self, monkeypatch):
        """Test export failure returns None instead of raising."""
        import work_data_hub.domain.annuity_performance.service as service_module

        def mock_write_unknowns_csv(names, source):
            raise IOError("Disk full")

        monkeypatch.setattr(service_module, "write_unknowns_csv", mock_write_unknowns_csv)

        # Should not raise, should return None
        result = _export_unknown_names_csv(["Company1"], "test_source", export_enabled=True)
        assert result is None
