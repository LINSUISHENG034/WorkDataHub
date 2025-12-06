"""
Integration test for end-to-end WorkDataHub flow.

This module tests the complete pipeline from file discovery through domain
processing to validate the full integration works correctly.

NOTE: These tests are skipped pending Epic 5 infrastructure refactoring.
The tests depend on sample_trustee_performance domain which is being deprecated.
"""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
import yaml

from src.work_data_hub.config.settings import Settings
from src.work_data_hub.domain.sample_trustee_performance.service import process
from src.work_data_hub.io.connectors.file_connector import DataSourceConnector
from src.work_data_hub.io.readers.excel_reader import read_excel_rows

pytestmark = pytest.mark.skip(
    reason="Tests depend on deprecated sample_trustee_performance domain - pending Epic 5"
)


@pytest.fixture
def integration_test_config(tmp_path):
    """Create integration test configuration."""
    config = {
        "domains": {
            "sample_trustee_performance": {
                "description": "Test trustee performance integration",
                "pattern": r"(?P<year>20\d{2})[-_](?P<month>0?[1-9]|1[0-2]).*受托业绩.*\.xlsx$",
                "select": "latest_by_year_month",
                "sheet": 0,
            }
        },
        "discovery": {"exclude_directories": ["backup"], "max_depth": 3},
    }

    config_path = tmp_path / "integration_config.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

    return str(config_path)


@pytest.fixture
def sample_trustee_data():
    """Create sample trustee performance data."""
    return pd.DataFrame(
        {
            "年": ["2024", "2024", "2024"],
            "月": ["11", "11", "11"],
            "计划代码": ["PLAN001", "PLAN002", "PLAN003"],
            "公司代码": ["COMP01", "COMP02", "COMP03"],
            "收益率": ["5.5%", "3.2%", "4.8%"],
            "净值": ["1.055", "1.032", "1.048"],
            "规模": ["1000000.00", "750000.50", "850000.25"],
        }
    )


@pytest.fixture
def test_data_directory(tmp_path, sample_trustee_data):
    """Create test data directory with sample Excel files."""
    # Create main test file
    main_file = tmp_path / "2024_11_受托业绩报告.xlsx"
    sample_trustee_data.to_excel(main_file, index=False, engine="openpyxl")

    # Create older version that should not be selected
    older_file = tmp_path / "2024_10_受托业绩报告.xlsx"
    older_data = sample_trustee_data.copy()
    older_data["月"] = ["10", "10", "10"]
    older_data.to_excel(older_file, index=False, engine="openpyxl")

    # Create non-matching file that should be ignored
    other_file = tmp_path / "other_report.xlsx"
    pd.DataFrame({"col1": ["data"]}).to_excel(
        other_file, index=False, engine="openpyxl"
    )

    # Create backup directory with file that should be ignored
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    backup_file = backup_dir / "2024_12_受托业绩报告.xlsx"
    sample_trustee_data.to_excel(backup_file, index=False, engine="openpyxl")

    return str(tmp_path)


class TestEndToEndIntegration:
    """Test complete end-to-end integration flow."""

    def test_complete_pipeline_flow(
        self, integration_test_config, test_data_directory, monkeypatch
    ):
        """Test the complete pipeline from discovery to domain processing."""
        # Step 1: Mock settings to use test directories
        test_settings = Settings()
        test_settings.data_base_dir = test_data_directory
        test_settings.data_sources_config = integration_test_config

        def mock_get_settings():
            return test_settings

        monkeypatch.setattr(
            "src.work_data_hub.config.settings.get_settings", mock_get_settings
        )

        # Step 2: File Discovery
        connector = DataSourceConnector(config_path=integration_test_config)
        discovered_files = connector.discover("sample_trustee_performance")

        # Verify file discovery results
        assert len(discovered_files) == 1, (
            "Should discover exactly one file after selection strategy"
        )

        selected_file = discovered_files[0]
        assert selected_file.domain == "sample_trustee_performance"
        assert selected_file.year == 2024
        assert selected_file.month == 11  # Latest version should be selected
        assert "2024_11_受托业绩报告.xlsx" in selected_file.path
        assert "受托业绩" in selected_file.path

        # Step 3: Excel Reading
        excel_rows = read_excel_rows(selected_file.path)

        # Verify Excel reading results
        assert len(excel_rows) == 3, "Should read 3 data rows"
        assert isinstance(excel_rows, list)
        assert all(isinstance(row, dict) for row in excel_rows)

        # Check sample row content
        first_row = excel_rows[0]
        assert first_row["年"] == "2024"
        assert first_row["月"] == "11"
        assert first_row["计划代码"] == "PLAN001"
        assert first_row["收益率"] == "5.5%"

        # Step 4: Domain Processing
        processed_records = process(excel_rows, data_source=selected_file.path)

        # Verify domain processing results
        assert len(processed_records) == 3, "Should successfully process all 3 rows"

        # Verify first processed record
        first_record = processed_records[0]
        assert first_record.report_date == date(2024, 11, 1)
        assert first_record.plan_code == "PLAN001"  # Normalized to uppercase
        assert first_record.company_code == "COMP01"
        assert first_record.return_rate == Decimal("0.055")  # 5.5% converted to decimal
        assert first_record.net_asset_value == Decimal("1.055")
        assert first_record.fund_scale == Decimal("1000000.00")
        assert first_record.data_source == selected_file.path
        assert first_record.has_performance_data is True

        # Verify all records have consistent report date
        assert all(
            record.report_date == date(2024, 11, 1) for record in processed_records
        )

        # Verify return rate conversions
        expected_rates = [Decimal("0.055"), Decimal("0.032"), Decimal("0.048")]
        actual_rates = [record.return_rate for record in processed_records]
        assert actual_rates == expected_rates

    def test_pipeline_with_no_matching_files(
        self, integration_test_config, tmp_path, monkeypatch
    ):
        """Test pipeline behavior when no files match the domain pattern."""
        # Create directory with non-matching files
        non_matching_file = tmp_path / "some_other_file.xlsx"
        pd.DataFrame({"col": ["data"]}).to_excel(
            non_matching_file, index=False, engine="openpyxl"
        )

        # Mock settings
        test_settings = Settings()
        test_settings.data_base_dir = str(tmp_path)
        test_settings.data_sources_config = integration_test_config

        def mock_get_settings():
            return test_settings

        monkeypatch.setattr(
            "src.work_data_hub.config.settings.get_settings", mock_get_settings
        )

        # Run discovery
        connector = DataSourceConnector(config_path=integration_test_config)
        discovered_files = connector.discover("sample_trustee_performance")

        # Should find no files
        assert len(discovered_files) == 0

    def test_pipeline_with_empty_excel_file(
        self, integration_test_config, tmp_path, monkeypatch
    ):
        """Test pipeline behavior with empty Excel file."""
        # Create empty Excel file with matching name
        empty_file = tmp_path / "2024_11_受托业绩报告.xlsx"
        empty_df = pd.DataFrame()  # Empty dataframe
        empty_df.to_excel(empty_file, index=False, engine="openpyxl")

        # Mock settings
        test_settings = Settings()
        test_settings.data_base_dir = str(tmp_path)
        test_settings.data_sources_config = integration_test_config

        def mock_get_settings():
            return test_settings

        monkeypatch.setattr(
            "src.work_data_hub.config.settings.get_settings", mock_get_settings
        )

        # Run pipeline
        connector = DataSourceConnector(config_path=integration_test_config)
        discovered_files = connector.discover("sample_trustee_performance")

        assert len(discovered_files) == 1

        # Reading empty file should return empty list
        excel_rows = read_excel_rows(discovered_files[0].path)
        assert excel_rows == []

        # Processing empty rows should return empty list
        processed_records = process(excel_rows, data_source=discovered_files[0].path)
        assert processed_records == []

    def test_pipeline_version_selection(
        self, integration_test_config, tmp_path, sample_trustee_data, monkeypatch
    ):
        """Test that the pipeline correctly selects the latest version by year/month."""
        # Create multiple versions
        versions = [
            ("2024_10_受托业绩报告.xlsx", "10"),
            ("2024_11_受托业绩报告.xlsx", "11"),  # This should be selected
            ("2024_09_受托业绩报告.xlsx", "09"),
        ]

        for filename, month in versions:
            file_path = tmp_path / filename
            version_data = sample_trustee_data.copy()
            version_data["月"] = [month, month, month]
            version_data.to_excel(file_path, index=False, engine="openpyxl")

        # Mock settings
        test_settings = Settings()
        test_settings.data_base_dir = str(tmp_path)
        test_settings.data_sources_config = integration_test_config

        def mock_get_settings():
            return test_settings

        monkeypatch.setattr(
            "src.work_data_hub.config.settings.get_settings", mock_get_settings
        )

        # Run discovery
        connector = DataSourceConnector(config_path=integration_test_config)
        discovered_files = connector.discover("sample_trustee_performance")

        # Should select the latest version (November)
        assert len(discovered_files) == 1
        selected_file = discovered_files[0]
        assert selected_file.month == 11
        assert "2024_11_受托业绩报告.xlsx" in selected_file.path

        # Process the selected file
        excel_rows = read_excel_rows(selected_file.path)
        processed_records = process(excel_rows, data_source=selected_file.path)

        # All records should have November date
        assert all(record.report_date.month == 11 for record in processed_records)

    def test_pipeline_handles_chinese_characters(
        self, integration_test_config, tmp_path, monkeypatch
    ):
        """Test that the pipeline correctly handles Chinese characters in filenames and data."""
        # Create file with Chinese characters
        chinese_data = pd.DataFrame(
            {
                "年": ["2024", "2024"],
                "月": ["11", "11"],
                "计划代码": ["计划A", "计划B"],  # Chinese plan codes
                "公司代码": ["公司01", "公司02"],  # Chinese company codes
                "收益率": ["5.5%", "3.2%"],
                "净值": ["1.055", "1.032"],
                "规模": ["1000000.00", "750000.50"],
            }
        )

        chinese_file = tmp_path / "2024_11_中国受托业绩报告.xlsx"
        chinese_data.to_excel(chinese_file, index=False, engine="openpyxl")

        # Mock settings
        test_settings = Settings()
        test_settings.data_base_dir = str(tmp_path)
        test_settings.data_sources_config = integration_test_config

        def mock_get_settings():
            return test_settings

        monkeypatch.setattr(
            "src.work_data_hub.config.settings.get_settings", mock_get_settings
        )

        # Run complete pipeline
        connector = DataSourceConnector(config_path=integration_test_config)
        discovered_files = connector.discover("trustee_performance")

        assert len(discovered_files) == 1

        excel_rows = read_excel_rows(discovered_files[0].path)
        processed_records = process(excel_rows, data_source=discovered_files[0].path)

        # Verify Chinese characters are handled correctly
        assert len(processed_records) == 2

        first_record = processed_records[0]
        assert (
            first_record.plan_code == "计划A"
        )  # Chinese characters preserved but normalized
        assert first_record.company_code == "公司01"
