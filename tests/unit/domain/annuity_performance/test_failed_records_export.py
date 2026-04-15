"""
Unit tests for failed records export functionality.

Story 5.6.1: Dry Run Failed Records Export
AC 1/2/3/6: Failed rows exported with original columns, logged with path+count, tests verify behavior.
AC 4: No function signature changes (backward compatible).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import json
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from pandera.errors import SchemaError

from work_data_hub.domain.annuity_performance.service import process_with_enrichment


def _build_valid_gold_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "月度": pd.Timestamp("2025-10-01"),
                "业务类型": "企年投资",
                "计划类型": "集合计划",
                "计划代码": "AP0001",
                "计划名称": "测试计划A",
                "组合类型": "稳健型",
                "组合代码": "COMBO001",
                "组合名称": "稳健组合A",
                "company_id": "614810477",
                "客户名称": "OK",
                "期初资产规模": 100.0,
                "期末资产规模": 120.0,
                "投资收益": 5.0,
                "供款": 0.0,
                "流失_含待遇支付": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "年化收益率": 0.05,
                "机构代码": "G01",
                "机构名称": "北京",
                "产品线代码": "L001",
                "年金账户号": "ACC001",
                "年金账户名": "OK",
            },
            {
                "月度": pd.Timestamp("2025-10-01"),
                "业务类型": "职年受托",
                "计划类型": "单一计划",
                "计划代码": "AP0002",
                "计划名称": "测试计划B",
                "组合类型": "进取型",
                "组合代码": "COMBO002",
                "组合名称": "进取组合B",
                "company_id": "614810478",
                "客户名称": "FAIL",
                "期初资产规模": 200.0,
                "期末资产规模": 240.0,
                "投资收益": 10.0,
                "供款": 0.0,
                "流失_含待遇支付": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "年化收益率": 0.05,
                "机构代码": "G02",
                "机构名称": "上海",
                "产品线代码": "L002",
                "年金账户号": "ACC002",
                "年金账户名": "FAIL",
            },
        ]
    )


class TestFailedRecordsExport:
    """Tests for failed records export in process_with_enrichment."""

    @patch("sqlalchemy.create_engine")
    @patch(
        "work_data_hub.domain.annuity_performance.service.load_plan_override_mapping"
    )
    @patch(
        "work_data_hub.domain.annuity_performance.service.convert_dataframe_to_models"
    )
    @patch(
        "work_data_hub.domain.annuity_performance.service.build_bronze_to_silver_pipeline"
    )
    @patch("work_data_hub.domain.annuity_performance.service.FailureExporter")
    @patch("work_data_hub.domain.annuity_performance.service.export_unknown_names_csv")
    def test_exports_failed_rows_from_original_dataframe(
        self,
        mock_export_unknown,
        mock_failure_exporter,
        mock_pipeline_builder,
        mock_convert_to_models,
        mock_load_plan_override_mapping,
        mock_create_engine,
    ):
        """AC1/AC2: Export uses original input columns for dropped rows."""
        mock_export_unknown.return_value = None
        mock_load_plan_override_mapping.return_value = {}
        exporter = MagicMock()
        exporter.export.return_value = Path(
            "logs/failed_records_test_20241206_120000.csv"
        )
        mock_failure_exporter.return_value = exporter
        mock_connection = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connection
        mock_create_engine.return_value = mock_engine

        pipeline = MagicMock()
        # Pipeline returns a transformed DataFrame, but export should use original rows
        pipeline.execute.return_value = _build_valid_gold_rows()
        mock_pipeline_builder.return_value = pipeline
        # Only first record passes conversion; second is dropped
        mock_convert_to_models.return_value = ([SimpleNamespace(计划代码="AP0001")], [])

        rows = [
            {"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"},
            {
                "月度": "202412",
                "计划代码": "AP0002",
                "客户名称": "FAIL",
                "额外列": "keep",
            },
        ]

        process_with_enrichment(
            rows,
            data_source="test_file.xlsx",
            export_unknown_names=False,
            session_id="sess-001",
        )

        mock_failure_exporter.assert_called_once_with(session_id="sess-001")
        exporter.export.assert_called_once()
        failed_records = exporter.export.call_args.args[0]
        assert len(failed_records) == 1
        assert failed_records[0].source_file == "test_file.xlsx"
        assert failed_records[0].error_type == "DROPPED_IN_PIPELINE"
        assert json.loads(failed_records[0].raw_data) == rows[1]

    @patch("sqlalchemy.create_engine")
    @patch(
        "work_data_hub.domain.annuity_performance.service.load_plan_override_mapping"
    )
    @patch(
        "work_data_hub.domain.annuity_performance.service.convert_dataframe_to_models"
    )
    @patch(
        "work_data_hub.domain.annuity_performance.service.build_bronze_to_silver_pipeline"
    )
    @patch("work_data_hub.domain.annuity_performance.service.FailureExporter")
    @patch("work_data_hub.domain.annuity_performance.service.export_unknown_names_csv")
    def test_no_export_when_all_records_pass_validation(
        self,
        mock_export_unknown,
        mock_failure_exporter,
        mock_pipeline_builder,
        mock_convert_to_models,
        mock_load_plan_override_mapping,
        mock_create_engine,
    ):
        """AC1: No export when dropped_count == 0."""
        mock_export_unknown.return_value = None
        mock_load_plan_override_mapping.return_value = {}
        mock_connection = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connection
        mock_create_engine.return_value = mock_engine
        pipeline = MagicMock()
        pipeline.execute.return_value = _build_valid_gold_rows().iloc[:1].copy()
        mock_pipeline_builder.return_value = pipeline
        mock_convert_to_models.return_value = ([SimpleNamespace(计划代码="AP0001")], [])

        rows = [{"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"}]

        process_with_enrichment(
            rows,
            data_source="test_file.xlsx",
            export_unknown_names=False,
            session_id="sess-001",
        )

        mock_failure_exporter.assert_not_called()

    def test_backward_compatible_no_signature_change(self):
        """AC4: Function signature unchanged - backward compatible."""
        result = process_with_enrichment(
            rows=[],
            data_source="test.xlsx",
            enrichment_service=None,
            sync_lookup_budget=0,
            export_unknown_names=False,
        )

        assert result.records == []
        assert result.data_source == "test.xlsx"

    @patch("sqlalchemy.create_engine")
    @patch(
        "work_data_hub.domain.annuity_performance.service.load_plan_override_mapping"
    )
    @patch(
        "work_data_hub.domain.annuity_performance.service.build_bronze_to_silver_pipeline"
    )
    def test_invalid_gold_output_fails_before_model_conversion(
        self,
        mock_pipeline_builder,
        mock_load_plan_override_mapping,
        mock_create_engine,
    ):
        """Active runtime path should enforce Gold validation before model conversion."""
        mock_load_plan_override_mapping.return_value = {}

        mock_connection = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connection
        mock_create_engine.return_value = mock_engine

        pipeline = MagicMock()
        pipeline.execute.return_value = pd.DataFrame(
            [
                {
                    "月度": pd.Timestamp("2025-10-01"),
                    "业务类型": "企年投资",
                    "计划类型": "集合计划",
                    "计划代码": "FP0001",
                    "计划名称": "测试计划",
                    "组合类型": "稳健型",
                    "组合代码": "COMBO001",
                    "组合名称": "稳健组合",
                    "company_id": "614810477",
                    "客户名称": "测试公司",
                    "期初资产规模": 100.0,
                    "期末资产规模": -1.0,
                    "投资收益": 5.0,
                    "供款": 0.0,
                    "流失_含待遇支付": 0.0,
                    "流失": 0.0,
                    "待遇支付": 0.0,
                    "年化收益率": 0.05,
                    "机构代码": "G01",
                    "机构名称": "北京",
                    "产品线代码": "L001",
                    "年金账户号": "12345678",
                    "年金账户名": "测试公司",
                }
            ]
        )
        mock_pipeline_builder.return_value = pipeline

        with pytest.raises(SchemaError):
            process_with_enrichment(
                rows=[{"计划代码": "FP0001", "客户名称": "测试公司"}],
                data_source="test.xlsx",
                export_unknown_names=False,
            )
