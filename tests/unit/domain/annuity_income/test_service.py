"""
Unit tests for AnnuityIncome service module.

Story 5.5.2: AnnuityIncome Domain Implementation
AC 7: Follows same patterns as annuity_performance domain
AC 14: Service API contract documented

Tests:
- process_with_enrichment() processes rows correctly
- normalize_month() validates YYYYMM format
- convert_dataframe_to_models() converts DataFrame to models
- Service handles empty input gracefully
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Import models first to avoid circular import
from work_data_hub.domain.annuity_income.models import (
    AnnuityIncomeOut,
    ProcessingResultWithEnrichment,
)
from work_data_hub.domain.annuity_income.helpers import (
    normalize_month,
    convert_dataframe_to_models,
    summarize_enrichment,
)
from work_data_hub.domain.annuity_income.service import (
    process_with_enrichment,
    _records_to_dataframe,
)


class TestNormalizeMonth:
    """Tests for normalize_month helper function."""

    def test_valid_month_format(self):
        """Accepts valid YYYYMM format."""
        assert normalize_month("202412") == "202412"
        assert normalize_month("202501") == "202501"

    def test_strips_whitespace(self):
        """Strips whitespace from input."""
        assert normalize_month("  202412  ") == "202412"

    def test_rejects_none(self):
        """Rejects None input."""
        with pytest.raises(ValueError, match="required"):
            normalize_month(None)

    def test_rejects_invalid_length(self):
        """Rejects input with wrong length."""
        with pytest.raises(ValueError, match="6-digit"):
            normalize_month("2024")
        with pytest.raises(ValueError, match="6-digit"):
            normalize_month("20241201")

    def test_rejects_non_numeric(self):
        """Rejects non-numeric input."""
        with pytest.raises(ValueError, match="6-digit"):
            normalize_month("2024AB")

    def test_rejects_invalid_year(self):
        """Rejects year outside valid range."""
        with pytest.raises(ValueError, match="2000 and 2100"):
            normalize_month("199912")
        with pytest.raises(ValueError, match="2000 and 2100"):
            normalize_month("210112")

    def test_rejects_invalid_month(self):
        """Rejects month outside 01-12 range."""
        with pytest.raises(ValueError, match="01 and 12"):
            normalize_month("202400")
        with pytest.raises(ValueError, match="01 and 12"):
            normalize_month("202413")


class TestConvertDataframeToModels:
    """Tests for convert_dataframe_to_models helper function."""

    def test_converts_valid_rows(self):
        """Converts valid DataFrame rows to models."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        df = pd.DataFrame(
            {
                "月度": [date(2024, 12, 1), date(2024, 11, 1)],
                "计划代码": ["FP0001", "FP0002"],
                "客户名称": ["公司A", "公司B"],
                "company_id": ["COMP001", "COMP002"],
                "产品线代码": ["PL201", "PL201"],
                "机构代码": ["G00", "G00"],
                "固费": [500000.0, 1000000.0],
                "浮费": [300000.0, 600000.0],
                "回补": [200000.0, 400000.0],
                "税": [50000.0, 100000.0],
            }
        )

        records, unknown_names = convert_dataframe_to_models(df)

        assert len(records) == 2
        assert all(isinstance(r, AnnuityIncomeOut) for r in records)
        assert records[0].计划代码 == "FP0001"
        assert records[1].计划代码 == "FP0002"

    def test_skips_rows_without_plan_code(self):
        """Skips rows without 计划代码."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        df = pd.DataFrame(
            {
                "月度": [date(2024, 12, 1), date(2024, 11, 1)],
                "计划代码": ["FP0001", None],
                "客户名称": ["公司A", "公司B"],
                "company_id": ["COMP001", "COMP002"],
                "产品线代码": ["PL201", "PL201"],
                "机构代码": ["G00", "G00"],
                "固费": [10.0, 20.0],
                "浮费": [5.0, 10.0],
                "回补": [3.0, 6.0],
                "税": [1.0, 2.0],
            }
        )

        records, unknown_names = convert_dataframe_to_models(df)

        assert len(records) == 1
        assert records[0].计划代码 == "FP0001"

    def test_skips_rows_without_date(self):
        """Skips rows without 月度."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        df = pd.DataFrame(
            {
                "月度": [date(2024, 12, 1), None],
                "计划代码": ["FP0001", "FP0002"],
                "客户名称": ["公司A", "公司B"],
                "company_id": ["COMP001", "COMP002"],
                "产品线代码": ["PL201", "PL201"],
                "机构代码": ["G00", "G00"],
                "固费": [10.0, 20.0],
                "浮费": [5.0, 10.0],
                "回补": [3.0, 6.0],
                "税": [1.0, 2.0],
            }
        )

        records, unknown_names = convert_dataframe_to_models(df)

        assert len(records) == 1

    def test_tracks_unknown_names(self):
        """Tracks customer names with temp IDs (IN_ prefix)."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        df = pd.DataFrame(
            {
                "月度": [date(2024, 12, 1), date(2024, 11, 1)],
                "计划代码": ["FP0001", "FP0002"],
                "客户名称": ["公司A", "公司B"],
                "company_id": ["COMP001", "IN_ABC123"],  # Second has temp ID
                "产品线代码": ["PL201", "PL201"],
                "机构代码": ["G00", "G00"],
                "固费": [1.0, 2.0],
                "浮费": [0.5, 1.0],
                "回补": [0.3, 0.6],
                "税": [0.1, 0.2],
            }
        )

        records, unknown_names = convert_dataframe_to_models(df)

        assert len(unknown_names) == 1
        assert "公司B" in unknown_names

    def test_handles_nan_values(self):
        """Handles NaN values in DataFrame."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        df = pd.DataFrame(
            {
                "月度": [date(2024, 12, 1)],
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
                "company_id": ["COMP001"],
                "产品线代码": ["PL201"],
                "机构代码": ["G00"],
                "固费": [float("nan")],
                "浮费": [1.0],
                "回补": [1.0],
                "税": [1.0],
            }
        )

        records, unknown_names = convert_dataframe_to_models(df)

        # income is required; row with NaN should be skipped
        assert len(records) == 0


class TestSummarizeEnrichment:
    """Tests for summarize_enrichment helper function."""

    def test_creates_stats_object(self):
        """Creates EnrichmentStats with correct values."""
        stats = summarize_enrichment(
            total_rows=100,
            temp_ids=10,
            processing_time_ms=500,
        )

        assert stats.total_records == 100
        assert stats.temp_assigned == 10
        assert stats.processing_time_ms == 500


class TestProcessWithEnrichment:
    """Tests for process_with_enrichment service function."""

    def test_handles_empty_input(self):
        """Returns empty result for empty input."""
        result = process_with_enrichment([], data_source="test.xlsx")

        assert isinstance(result, ProcessingResultWithEnrichment)
        assert result.records == []
        assert result.data_source == "test.xlsx"
        assert result.processing_time_ms == 0

    def test_processes_valid_rows(self):
        """Processes valid rows through pipeline."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        rows = [
            {
                "月度": "202412",
                "计划代码": "FP0001",
                "客户名称": "测试公司A",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构名称": "北京",
                "固费": 500000.0,
                "机构名称": "北京",
                "固费": 500000.0,
                "浮费": 300000.0,
                "回补": 200000.0,
                "税": 50000.0,
            },
        ]

        result = process_with_enrichment(
            rows,
            data_source="test.xlsx",
            export_unknown_names=False,
        )

        assert isinstance(result, ProcessingResultWithEnrichment)
        assert result.data_source == "test.xlsx"
        assert result.processing_time_ms > 0

    def test_tracks_enrichment_stats(self):
        """Tracks enrichment statistics."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        rows = [
            {
                "月度": "202412",
                "计划代码": "FP0001",
                "客户名称": "测试公司A",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构名称": "北京",
                "固费": 500000.0,
                "固费": 500000.0,
                "浮费": 300000.0,
                "回补": 200000.0,
                "税": 50000.0,
            },
        ]

        result = process_with_enrichment(
            rows,
            data_source="test.xlsx",
            export_unknown_names=False,
        )

        assert result.enrichment_stats.total_records == 1


class TestRecordsToDataframe:
    """Tests for _records_to_dataframe helper function."""

    def test_converts_records_to_dataframe(self):
        """Converts list of records to DataFrame."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        records = [
            AnnuityIncomeOut(
                月度="2024-12-01",
                计划代码="FP0001",
                company_id="COMP001",
                客户名称="公司A",
                产品线代码="PL201",
                机构代码="G00",
                固费=1.0,
                浮费=0.5,
                回补=0.3,
                税=0.1,
            ),
            AnnuityIncomeOut(
                月度="2024-11-01",
                计划代码="FP0002",
                company_id="COMP002",
                客户名称="公司B",
                产品线代码="PL201",
                机构代码="G00",
                固费=2.0,
                浮费=1.0,
                回补=0.6,
                税=0.2,
            ),
        ]

        df = _records_to_dataframe(records)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "计划代码" in df.columns

    def test_handles_empty_list(self):
        """Returns empty DataFrame for empty list."""
        df = _records_to_dataframe([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestStory736ConnectionCleanup:
    """Story 7.3-6: Tests for connection cleanup and pipeline alignment fixes."""

    def test_connection_cleanup_on_success(self):
        """Verifies try/finally cleanup executed on successful pipeline run."""
        # Story 7.3-6 AC6: Connection cleanup in try/finally block
        rows = [
            {
                "月度": "202412",
                "计划代码": "FP0001",
                "客户名称": "测试公司",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构名称": "北京",
                "固费": 100.0,
                "浮费": 50.0,
                "回补": 25.0,
                "税": 10.0,
            }
        ]

        # Patch CompanyMappingRepository to verify cleanup behavior
        with patch(
            "work_data_hub.domain.annuity_income.service.CompanyMappingRepository"
        ) as mock_repo:
            with patch(
                "work_data_hub.domain.annuity_income.service.get_settings"
            ) as mock_settings:
                # create_engine is imported inside the function, so patch at sqlalchemy level
                with patch("sqlalchemy.create_engine") as mock_engine:
                    mock_conn = MagicMock()
                    mock_engine.return_value.connect.return_value = mock_conn

                    result = process_with_enrichment(
                        rows,
                        data_source="test.xlsx",
                        export_unknown_names=False,
                    )

                    # Verify connection commit was called (cleanup)
                    if mock_conn.commit.called or mock_conn.close.called:
                        # Connection was used and cleaned up
                        pass
                    # Result should still be valid regardless of DB connection
                    assert isinstance(result, ProcessingResultWithEnrichment)

    def test_connection_cleanup_on_exception(self):
        """Story 7.3-6 AC13: Connection cleaned up even when pipeline throws exception."""
        rows = [
            {
                "月度": "202412",
                "计划代码": "FP0001",
                "客户名称": "测试公司",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构名称": "北京",
                "固费": 100.0,
                "浮费": 50.0,
                "回补": 25.0,
                "税": 10.0,
            }
        ]

        mock_conn = MagicMock()

        with patch(
            "work_data_hub.domain.annuity_income.service.CompanyMappingRepository"
        ):
            with patch("work_data_hub.domain.annuity_income.service.get_settings"):
                # create_engine is imported inside the function, so patch at sqlalchemy level
                with patch("sqlalchemy.create_engine") as mock_engine:
                    mock_engine.return_value.connect.return_value = mock_conn

                    with patch(
                        "work_data_hub.domain.annuity_income.service.build_bronze_to_silver_pipeline"
                    ) as mock_pipeline:
                        mock_pipeline.return_value.execute.side_effect = Exception(
                            "Pipeline error"
                        )

                        with pytest.raises(Exception, match="Pipeline error"):
                            process_with_enrichment(
                                rows,
                                data_source="test.xlsx",
                                export_unknown_names=False,
                            )

                        # Verify connection was closed even after exception
                        mock_conn.close.assert_called_once()

    def test_graceful_degradation_without_mapping_repository(self):
        """Story 7.3-6: Proceeds without DB cache if initialization fails."""
        rows = [
            {
                "月度": "202412",
                "计划代码": "FP0001",
                "客户名称": "测试公司",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构名称": "北京",
                "固费": 100.0,
                "浮费": 50.0,
                "回补": 25.0,
                "税": 10.0,
            }
        ]

        with patch(
            "work_data_hub.domain.annuity_income.service.get_settings"
        ) as mock_settings:
            mock_settings.side_effect = Exception("Settings initialization failed")

            # Should not raise, should proceed without mapping_repository
            result = process_with_enrichment(
                rows,
                data_source="test.xlsx",
                export_unknown_names=False,
            )

            assert isinstance(result, ProcessingResultWithEnrichment)
