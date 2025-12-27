"""
Unit tests for failed records export functionality.

Story 5.6.1: Dry Run Failed Records Export
AC 5/6: Implementation applies to annuity_income and is covered by tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from pandas.testing import assert_frame_equal

from work_data_hub.domain.annuity_income.models import AnnuityIncomeOut
from work_data_hub.domain.annuity_income.service import process_with_enrichment


class TestFailedRecordsExport:
    """Tests for failed records export in process_with_enrichment."""

    @patch("work_data_hub.domain.annuity_income.service.convert_dataframe_to_models")
    @patch("work_data_hub.domain.annuity_income.service.validate_gold_dataframe")
    @patch(
        "work_data_hub.domain.annuity_income.service.build_bronze_to_silver_pipeline"
    )
    @patch("work_data_hub.domain.annuity_income.service.export_error_csv")
    @patch("work_data_hub.domain.annuity_income.service.export_unknown_names_csv")
    def test_exports_failed_rows_using_composite_key(
        self,
        mock_export_unknown,
        mock_export_error,
        mock_pipeline_builder,
        mock_validate_gold,
        mock_convert_to_models,
    ):
        """AC5: Failed rows exported when dropped, filtered by 计划代码+组合代码."""
        mock_export_unknown.return_value = None
        mock_export_error.return_value = Path(
            "logs/failed_records_test_20241206_120000.csv"
        )
        pipeline = MagicMock()
        row_success = {
            "月度": "202412",
            "计划代码": "FP0001",
            "组合代码": "A",
            "客户名称": "公司A",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 1.0,
            "浮费": 0.5,
            "回补": 0.3,
            "税": 0.1,
            "company_id": "COMP1",
        }
        row_fail = {
            "月度": "202412",
            "计划代码": "FP0001",
            "组合代码": "B",
            "客户名称": "公司B",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 2.0,
            "浮费": 1.0,
            "回补": 0.6,
            "税": 0.2,
            "company_id": "COMP2",
            "额外列": "keep",
        }
        pipeline.execute.return_value = pd.DataFrame([row_success, row_fail])
        mock_pipeline_builder.return_value = pipeline
        mock_validate_gold.return_value = (pipeline.execute.return_value, [])
        # Only first record passes; second is dropped
        mock_convert_to_models.return_value = ([AnnuityIncomeOut(**row_success)], [])

        rows = [row_success, row_fail]

        process_with_enrichment(
            rows, data_source="test_file.xlsx", export_unknown_names=False
        )

        mock_export_error.assert_called_once()
        failed_df = mock_export_error.call_args.args[0]
        expected_df = pd.DataFrame([rows[1]])
        assert_frame_equal(
            failed_df.reset_index(drop=True), expected_df.reset_index(drop=True)
        )
        assert mock_export_error.call_args.kwargs["output_dir"] == Path("logs")
        assert "test_file" in mock_export_error.call_args.kwargs["filename_prefix"]

    @patch("work_data_hub.domain.annuity_income.service.convert_dataframe_to_models")
    @patch("work_data_hub.domain.annuity_income.service.validate_gold_dataframe")
    @patch(
        "work_data_hub.domain.annuity_income.service.build_bronze_to_silver_pipeline"
    )
    @patch("work_data_hub.domain.annuity_income.service.export_error_csv")
    @patch("work_data_hub.domain.annuity_income.service.export_unknown_names_csv")
    def test_no_export_when_all_records_pass_validation(
        self,
        mock_export_unknown,
        mock_export_error,
        mock_pipeline_builder,
        mock_validate_gold,
        mock_convert_to_models,
    ):
        """AC5: No export when dropped_count == 0 for annuity_income."""
        mock_export_unknown.return_value = None
        pipeline = MagicMock()
        row_success = {
            "月度": "202412",
            "计划代码": "FP0001",
            "组合代码": "A",
            "客户名称": "公司A",
            "产品线代码": "PL201",
            "机构代码": "G00",
            "固费": 1.0,
            "浮费": 0.5,
            "回补": 0.3,
            "税": 0.1,
            "company_id": "COMP1",
        }
        pipeline.execute.return_value = pd.DataFrame([row_success])
        mock_pipeline_builder.return_value = pipeline
        mock_validate_gold.return_value = (pipeline.execute.return_value, [])
        mock_convert_to_models.return_value = ([AnnuityIncomeOut(**row_success)], [])

        rows = [row_success]

        process_with_enrichment(
            rows, data_source="test_file.xlsx", export_unknown_names=False
        )

        mock_export_error.assert_not_called()

    def test_backward_compatible_no_signature_change(self):
        """Function signature unchanged - backward compatible."""
        result = process_with_enrichment(
            rows=[],
            data_source="test.xlsx",
            enrichment_service=None,
            sync_lookup_budget=0,
            export_unknown_names=False,
        )

        assert result.records == []
        assert result.data_source == "test.xlsx"
