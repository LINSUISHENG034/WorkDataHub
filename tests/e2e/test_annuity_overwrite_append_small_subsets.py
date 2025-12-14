"""
End-to-End testing for annuity performance delete_insert vs append modes.

This module validates the complete ETL pipeline for annuity performance data using
strategically generated small test datasets. Tests both delete_insert (覆盖写入) and
append (非覆盖写入) modes with runtime primary key overrides to ensure correct SQL
plan generation and row counting.
"""

import os

import pytest

pytestmark = pytest.mark.e2e_suite

from unittest.mock import Mock, patch
from dagster import build_op_context

from src.work_data_hub.cli.etl import build_run_config
from src.work_data_hub.orchestration.jobs import annuity_performance_job
from src.work_data_hub.orchestration.ops import (
    DiscoverFilesConfig,
    LoadConfig,
    ReadExcelConfig,
    discover_files_op,
    load_op,
    process_annuity_performance_op,
    read_excel_op,
)


class TestAnnuityOverwriteAppendSmallSubsets:
    """Test delete_insert vs append modes with small strategic datasets."""

    @pytest.fixture
    def subset_dir(self):
        """Return path to generated subset directory."""
        return "tests/fixtures/sample_data/annuity_subsets"

    @pytest.fixture
    def mock_connector_for_distinct_file(self, subset_dir):
        """Mock DataSourceConnector to return distinct_5 subset file."""
        distinct_file = os.path.join(
            subset_dir, "2024年11月年金终稿数据_subset_distinct_5.xlsx"
        )

        mock_discovered = Mock()
        mock_discovered.path = distinct_file
        mock_discovered.year = 2024
        mock_discovered.month = 11

        mock_connector = Mock()
        mock_connector.discover.return_value = [mock_discovered]

        return mock_connector

    @pytest.fixture
    def mock_connector_for_overlap_file(self, subset_dir):
        """Mock DataSourceConnector to return overlap_pk_6 subset file."""
        overlap_file = os.path.join(
            subset_dir, "2024年11月年金终稿数据_subset_overlap_pk_6.xlsx"
        )

        mock_discovered = Mock()
        mock_discovered.path = overlap_file
        mock_discovered.year = 2024
        mock_discovered.month = 11

        mock_connector = Mock()
        mock_connector.discover.return_value = [mock_discovered]

        return mock_connector

    @pytest.fixture
    def mock_connector_for_append_file(self, subset_dir):
        """Mock DataSourceConnector to return append_3 subset file."""
        append_file = os.path.join(
            subset_dir, "2024年11月年金终稿数据_subset_append_3.xlsx"
        )

        mock_discovered = Mock()
        mock_discovered.path = append_file
        mock_discovered.year = 2024
        mock_discovered.month = 11

        mock_connector = Mock()
        mock_connector.discover.return_value = [mock_discovered]

        return mock_connector

    def test_delete_insert_distinct_pk_default(
        self, monkeypatch, subset_dir, mock_connector_for_distinct_file
    ):
        """Test delete_insert with distinct PKs using default configuration."""
        # Environment isolation - point to subset directory
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_distinct_file

            # Build configuration for delete_insert mode with default PK
            context = build_op_context()

            # Step 1: Discover files
            discover_config = DiscoverFilesConfig(domain="annuity_performance")
            file_paths = discover_files_op(context, discover_config)

            assert len(file_paths) == 1
            assert "subset_distinct_5.xlsx" in file_paths[0]

            # Step 2: Read Excel data (mocked)
            read_config = ReadExcelConfig(sheet=0)

            # Mock the Excel reader to return sample data
            with patch(
                "src.work_data_hub.orchestration.ops.read_excel_rows"
            ) as mock_read_excel:
                # Mock sample Excel data for distinct subset
                mock_read_excel.return_value = [
                    {
                        "年": "2024",
                        "月": "11",
                        "计划代码": "PLAN001",
                        "客户名称": "公司A",
                        "期初资产规模": "1000000",
                    },
                    {
                        "年": "2024",
                        "月": "11",
                        "计划代码": "PLAN002",
                        "客户名称": "公司B",
                        "期初资产规模": "2000000",
                    },
                    {
                        "年": "2024",
                        "月": "11",
                        "计划代码": "PLAN003",
                        "客户名称": "公司C",
                        "期初资产规模": "1500000",
                    },
                    {
                        "年": "2024",
                        "月": "11",
                        "计划代码": "PLAN004",
                        "客户名称": "公司D",
                        "期初资产规模": "800000",
                    },
                    {
                        "年": "2024",
                        "月": "11",
                        "计划代码": "PLAN005",
                        "客户名称": "公司E",
                        "期初资产规模": "1200000",
                    },
                ]

                excel_rows = read_excel_op(context, read_config, file_paths)

            assert len(excel_rows) >= 1  # Should have some rows

            # Step 3: Process through domain service
            processed_rows = process_annuity_performance_op(
                context, excel_rows, file_paths
            )

            assert len(processed_rows) >= 1
            # Verify expected structure
            if processed_rows:
                assert "月度" in processed_rows[0] or "report_date" in processed_rows[0]
                assert (
                    "计划代码" in processed_rows[0] or "plan_code" in processed_rows[0]
                )
                assert "company_id" in processed_rows[0]

            # Step 4: Load with default PK (plan-only mode)
            load_config = LoadConfig(
                table="规模明细",
                mode="delete_insert",
                pk=[
                    "月度",
                    "计划代码",
                    "company_id",
                ],  # Default PK from data_sources.yml
                plan_only=True,
            )
            load_result = load_op(context, load_config, processed_rows)

            # Validation: Expected counts based on distinct subset characteristics
            assert load_result["mode"] == "delete_insert"
            assert load_result["deleted"] == len(
                processed_rows
            )  # Unique PK combinations
            assert load_result["inserted"] == len(processed_rows)
            assert "sql_plans" in load_result  # Plan-only mode

            # Verify SQL plan structure
            operations = load_result["sql_plans"]
            assert len(operations) == 2  # DELETE + INSERT
            assert operations[0][0] == "DELETE"
            assert operations[1][0] == "INSERT"

    def test_delete_insert_overlapping_pk_default(
        self, monkeypatch, subset_dir, mock_connector_for_overlap_file
    ):
        """Test delete_insert with overlapping PKs using default configuration."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_overlap_file

            context = build_op_context()

            # Discover and read overlap subset
            discover_config = DiscoverFilesConfig(domain="annuity_performance")
            file_paths = discover_files_op(context, discover_config)

            read_config = ReadExcelConfig(sheet=0)
            excel_rows = read_excel_op(context, read_config, file_paths)

            # Process data
            processed_rows = process_annuity_performance_op(
                context, excel_rows, file_paths
            )

            # Load with default PK
            load_config = LoadConfig(
                table="规模明细",
                mode="delete_insert",
                pk=["月度", "计划代码", "company_id"],
                plan_only=True,
            )
            load_result = load_op(context, load_config, processed_rows)

            # Validation: Should have fewer deletes than inserts due to PK overlap
            assert load_result["mode"] == "delete_insert"
            assert load_result["inserted"] == len(processed_rows)  # All rows inserted
            # deleted count should be <= inserted count due to PK overlaps
            assert load_result["deleted"] <= load_result["inserted"]
            assert "sql_plans" in load_result

    def test_delete_insert_with_pk_override(
        self, monkeypatch, subset_dir, mock_connector_for_overlap_file
    ):
        """Test delete_insert with runtime PK override."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_overlap_file

            context = build_op_context()

            # Discover and read data
            discover_config = DiscoverFilesConfig(domain="annuity_performance")
            file_paths = discover_files_op(context, discover_config)

            read_config = ReadExcelConfig(sheet=0)
            excel_rows = read_excel_op(context, read_config, file_paths)

            processed_rows = process_annuity_performance_op(
                context, excel_rows, file_paths
            )

            # Load with PK override (two-column grouping)
            load_config = LoadConfig(
                table="规模明细",
                mode="delete_insert",
                pk=["月度", "计划代码"],  # Override: exclude company_id
                plan_only=True,
            )
            load_result = load_op(context, load_config, processed_rows)

            # Validation: Different delete count due to two-column PK grouping
            assert load_result["mode"] == "delete_insert"
            assert load_result["inserted"] == len(processed_rows)

            # With two-column PK, delete count should reflect unique (月度, 计划代码) combinations
            # This should be different from three-column PK grouping
            assert load_result["deleted"] >= 1
            assert "sql_plans" in load_result

            # Verify DELETE SQL uses the overridden PK
            operations = load_result["sql_plans"]
            delete_sql = operations[0][1]  # First operation should be DELETE
            assert '"月度"' in delete_sql
            assert '"计划代码"' in delete_sql
            # Should not include company_id in WHERE clause
            assert (
                '"company_id"' not in delete_sql
                or delete_sql.count('"company_id"') <= 1
            )

    def test_append_mode_validation(
        self, monkeypatch, subset_dir, mock_connector_for_append_file
    ):
        """Test append mode validation - should ignore PK requirements."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_append_file

            context = build_op_context()

            # Process append dataset
            discover_config = DiscoverFilesConfig(domain="annuity_performance")
            file_paths = discover_files_op(context, discover_config)

            read_config = ReadExcelConfig(sheet=0)
            excel_rows = read_excel_op(context, read_config, file_paths)

            processed_rows = process_annuity_performance_op(
                context, excel_rows, file_paths
            )

            # Test append mode - should work without PK requirement
            load_config = LoadConfig(
                table="规模明细",
                mode="append",
                pk=[],  # Empty PK should be fine for append mode
                plan_only=True,
            )
            load_result = load_op(context, load_config, processed_rows)

            # Validation: Append mode characteristics
            assert load_result["mode"] == "append"
            assert load_result["deleted"] == 0  # append never deletes
            assert load_result["inserted"] == len(processed_rows)
            assert "sql_plans" in load_result

            # Should only have INSERT operations
            operations = load_result["sql_plans"]
            assert len(operations) == 1  # Only INSERT
            assert operations[0][0] == "INSERT"

    def test_complete_job_execution_plan_only(
        self, monkeypatch, subset_dir, mock_connector_for_distinct_file
    ):
        """Test complete annuity_performance_job execution in plan-only mode."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_distinct_file

            # Build run config for job execution
            args = build_args(
                domain="annuity_performance",
                mode="delete_insert",
                plan_only=True,
                max_files=1,
                sheet=0,
            )
            run_config = build_run_config(args)

            # Execute complete job
            result = annuity_performance_job.execute_in_process(
                run_config=run_config, instance=None
            )

            # Verify successful execution
            assert result.success

            # Extract load operation results
            load_result = result.output_for_node("load_op")

            assert load_result["mode"] == "delete_insert"
            assert load_result["inserted"] >= 1
            assert load_result["deleted"] >= 1
            assert "sql_plans" in load_result

    def test_job_execution_with_pk_override_via_cli_args(
        self, monkeypatch, subset_dir, mock_connector_for_overlap_file
    ):
        """Test job execution with --pk CLI parameter override."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_overlap_file

            # Simulate CLI args with PK override
            args = build_args(
                domain="annuity_performance",
                mode="delete_insert",
                plan_only=True,
                max_files=1,
                pk="月度,计划代码",  # Override to two-column PK
                sheet=0,
            )
            run_config = build_run_config(args)

            # Execute job
            result = annuity_performance_job.execute_in_process(
                run_config=run_config, instance=None
            )

            assert result.success

            # Verify PK override was applied
            load_result = result.output_for_node("load_op")

            assert load_result["mode"] == "delete_insert"
            assert "sql_plans" in load_result

            # Check that DELETE SQL reflects the overridden PK
            operations = load_result["sql_plans"]
            delete_operation = next(op for op in operations if op[0] == "DELETE")
            delete_sql = delete_operation[1]

            # Should contain the two PK columns
            assert '"月度"' in delete_sql
            assert '"计划代码"' in delete_sql

    def test_job_execution_append_mode(
        self, monkeypatch, subset_dir, mock_connector_for_append_file
    ):
        """Test complete job execution in append mode."""
        monkeypatch.setenv("WDH_DATA_BASE_DIR", subset_dir)

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector_for_append_file

            # Build args for append mode
            args = build_args(
                domain="annuity_performance",
                mode="append",
                plan_only=True,
                max_files=1,
                sheet=0,
            )
            run_config = build_run_config(args)

            # Execute job
            result = annuity_performance_job.execute_in_process(
                run_config=run_config, instance=None
            )

            assert result.success

            load_result = result.output_for_node("load_op")

            assert load_result["mode"] == "append"
            assert load_result["deleted"] == 0  # No deletions in append mode
            assert load_result["inserted"] >= 1

            # Only INSERT operation
            operations = load_result["sql_plans"]
            insert_operations = [op for op in operations if op[0] == "INSERT"]
            delete_operations = [op for op in operations if op[0] == "DELETE"]

            assert len(insert_operations) >= 1
            assert len(delete_operations) == 0

    def test_error_handling_missing_subset_files(self, monkeypatch, subset_dir):
        """Test graceful error handling when subset files are missing."""
        # Point to non-existent directory
        nonexistent_dir = "/nonexistent/path/to/subsets"
        monkeypatch.setenv("WDH_DATA_BASE_DIR", nonexistent_dir)

        # Mock connector that returns non-existent file
        mock_discovered = Mock()
        mock_discovered.path = os.path.join(nonexistent_dir, "missing_file.xlsx")

        mock_connector = Mock()
        mock_connector.discover.return_value = [mock_discovered]

        with patch(
            "src.work_data_hub.orchestration.ops.DataSourceConnector"
        ) as mock_connector_class:
            mock_connector_class.return_value = mock_connector

            context = build_op_context()

            # Should handle missing files gracefully
            discover_config = DiscoverFilesConfig(domain="annuity_performance")
            file_paths = discover_files_op(context, discover_config)

            read_config = ReadExcelConfig(sheet=0)

            # This should handle the missing file error gracefully
            excel_rows = read_excel_op(context, read_config, file_paths)

            # Should return empty list for missing files
            assert excel_rows == []


def build_args(
    domain: str,
    mode: str = "delete_insert",
    plan_only: bool = True,
    max_files: int = 1,
    pk: str = None,
    sheet: int = 0,
):
    """Helper to build mock CLI args for testing."""
    from argparse import Namespace

    return Namespace(
        domain=domain,
        mode=mode,
        plan_only=plan_only,
        execute=not plan_only,
        max_files=max_files,
        pk=pk,
        sheet=sheet,
        debug=False,
        raise_on_error=True,
    )
