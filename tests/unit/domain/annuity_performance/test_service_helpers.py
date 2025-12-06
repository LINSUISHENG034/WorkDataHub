"""Unit tests for annuity performance helper functions after Story 5.7 refactor."""

from datetime import date

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.helpers import (
    convert_dataframe_to_models,
    export_unknown_names_csv,
    normalize_month,
    summarize_enrichment,
)
from work_data_hub.domain.pipelines.types import ErrorContext
from work_data_hub.utils.date_parser import parse_report_date, parse_report_period


class TestErrorContext:
    def test_to_log_dict(self):
        ctx = ErrorContext(
            error_type="validation_error",
            operation="bronze_validation",
            domain="annuity_performance",
            stage="validation",
            error_message="Validation failed",
            details={"field": "月度"},
            row_number=1,
            field="月度",
        )
        log = ctx.to_log_dict()
        assert log["error_type"] == "validation_error"
        assert log["operation"] == "bronze_validation"
        assert log["domain"] == "annuity_performance"
        assert "row_number" in log


class TestNormalizeMonth:
    def test_valid(self):
        assert normalize_month("202501") == "202501"

    @pytest.mark.parametrize("value", ["2025", "202513", "202501a", None])
    def test_invalid(self, value):
        with pytest.raises(ValueError):
            normalize_month(value)


class TestDateParsing:
    def test_parse_report_period(self):
        assert parse_report_period("2024年11月") == (2024, 11)
        assert parse_report_period("202411") == (2024, 11)
        assert parse_report_period("24年11月") == (2024, 11)

    def test_parse_report_date(self):
        assert parse_report_date("202411") == date(2024, 11, 1)
        assert parse_report_date("2024年11月") == date(2024, 11, 1)
        assert parse_report_date("bad") is None


class TestConvertDataFrameToModels:
    def test_converts_rows_and_collects_unknown(self):
        df = pd.DataFrame(
            [
                {"月度": date(2024, 11, 1), "计划代码": "P1", "company_id": "C1"},
                {
                    "月度": date(2024, 11, 1),
                    "计划代码": "P2",
                    "company_id": "IN_ABC",
                    "客户名称": "未识别",
                },
            ]
        )
        records, unknown = convert_dataframe_to_models(df)
        assert len(records) == 2
        assert unknown == ["未识别"]

    def test_skips_invalid_rows(self):
        df = pd.DataFrame([{"计划代码": "P1"}])  # Missing 月度
        records, unknown = convert_dataframe_to_models(df)
        assert records == []
        assert unknown == []


class TestExportUnknownNames:
    def test_disabled(self):
        assert export_unknown_names_csv(["a"], "source", export_enabled=False) is None

    def test_empty(self):
        assert export_unknown_names_csv([], "source") is None


class TestSummarizeEnrichment:
    def test_stats(self):
        stats = summarize_enrichment(10, 2, 123)
        assert stats.total_records == 10
        assert stats.temp_assigned == 2
        assert stats.processing_time_ms == 123
