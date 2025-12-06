"""
Unit tests for failed records export functionality.

Story 5.6.1: Dry Run Failed Records Export
AC 1/2/3/6: Failed rows exported with original columns, logged with path+count, tests verify behavior.
AC 4: No function signature changes (backward compatible).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
from pandas.testing import assert_frame_equal

from work_data_hub.domain.annuity_performance.service import process_with_enrichment


class TestFailedRecordsExport:
    """Tests for failed records export in process_with_enrichment."""

    @patch("work_data_hub.domain.annuity_performance.service.convert_dataframe_to_models")
    @patch("work_data_hub.domain.annuity_performance.service.build_bronze_to_silver_pipeline")
    @patch("work_data_hub.domain.annuity_performance.service.export_error_csv")
    @patch("work_data_hub.domain.annuity_performance.service.export_unknown_names_csv")
    def test_exports_failed_rows_from_original_dataframe(
        self,
        mock_export_unknown,
        mock_export_error,
        mock_pipeline_builder,
        mock_convert_to_models,
    ):
        """AC1/AC2: Export uses original input columns for dropped rows."""
        mock_export_unknown.return_value = None
        mock_export_error.return_value = Path("logs/failed_records_test_20241206_120000.csv")

        pipeline = MagicMock()
        # Pipeline returns a transformed DataFrame, but export should use original rows
        pipeline.execute.return_value = pd.DataFrame(
            [
                {"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"},
                {"月度": "202412", "计划代码": "AP0002", "客户名称": "FAIL"},
            ]
        )
        mock_pipeline_builder.return_value = pipeline
        # Only first record passes conversion; second is dropped
        mock_convert_to_models.return_value = ([SimpleNamespace(计划代码="AP0001")], [])

        rows = [
            {"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"},
            {"月度": "202412", "计划代码": "AP0002", "客户名称": "FAIL", "额外列": "keep"},
        ]

        process_with_enrichment(rows, data_source="test_file.xlsx", export_unknown_names=False)

        mock_export_error.assert_called_once()
        failed_df = mock_export_error.call_args.args[0]
        expected_df = pd.DataFrame([rows[1]])
        assert_frame_equal(failed_df.reset_index(drop=True), expected_df.reset_index(drop=True))
        assert mock_export_error.call_args.kwargs["output_dir"] == Path("logs")
        assert "test_file" in mock_export_error.call_args.kwargs["filename_prefix"]

    @patch("work_data_hub.domain.annuity_performance.service.convert_dataframe_to_models")
    @patch("work_data_hub.domain.annuity_performance.service.build_bronze_to_silver_pipeline")
    @patch("work_data_hub.domain.annuity_performance.service.export_error_csv")
    @patch("work_data_hub.domain.annuity_performance.service.export_unknown_names_csv")
    def test_no_export_when_all_records_pass_validation(
        self,
        mock_export_unknown,
        mock_export_error,
        mock_pipeline_builder,
        mock_convert_to_models,
    ):
        """AC1: No export when dropped_count == 0."""
        mock_export_unknown.return_value = None
        pipeline = MagicMock()
        pipeline.execute.return_value = pd.DataFrame(
            [{"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"}]
        )
        mock_pipeline_builder.return_value = pipeline
        mock_convert_to_models.return_value = ([SimpleNamespace(计划代码="AP0001")], [])

        rows = [{"月度": "202412", "计划代码": "AP0001", "客户名称": "OK"}]

        process_with_enrichment(rows, data_source="test_file.xlsx", export_unknown_names=False)

        mock_export_error.assert_not_called()

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
