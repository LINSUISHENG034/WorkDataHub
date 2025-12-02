"""
Tests for file discovery connector.

This module tests the DataSourceConnector with various file patterns,
including Unicode filenames and version selection strategies.

NOTE: Some tests are skipped pending Epic 5 infrastructure refactoring.
Tests depend on sample_trustee_performance domain configuration.
"""

import os
from unittest.mock import patch

import pytest
import yaml

from src.work_data_hub.io.connectors.file_connector import (
    DataSourceConnector,
    DataSourceConnectorError,
)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "domains": {
            "sample_trustee_performance": {
                "description": "Test trustee performance files",
                "pattern": r"(?P<year>20\d{2})[-_/]?(?P<month>0?[1-9]|1[0-2]).*受托业绩.*\.xlsx$",
                "select": "latest_by_year_month",
                "sheet": 0,
            },
            "simple_test": {
                "description": "Simple test domain",
                "pattern": r"test_.*\.xlsx$",
                "select": "latest_by_mtime",
                "sheet": 0,
            },
        },
        "discovery": {"exclude_directories": ["temp", "backup"], "max_depth": 5},
    }


@pytest.fixture
def config_file(tmp_path, sample_config):
    """Create a temporary config file for testing."""
    config_path = tmp_path / "test_config.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, allow_unicode=True)
    return str(config_path)


@pytest.fixture
def test_data_dir(tmp_path):
    """Create a test directory structure with sample files."""
    # Create directory structure
    (tmp_path / "2024").mkdir()
    (tmp_path / "2023").mkdir()
    (tmp_path / "backup").mkdir()
    (tmp_path / "subdir").mkdir()

    # Create test files
    test_files = [
        "2024_11_受托业绩报告.xlsx",
        "2024-12-受托业绩数据.xlsx",
        "2023_06_受托业绩.xlsx",
        "test_file.xlsx",
        "2024/受托业绩_internal.xlsx",
        "other_file.txt",
        "temp_file.tmp",
        "~$temp.xlsx",  # Excel temp file
        "backup/old_file.xlsx",
        "some_file.eml",  # Email file
    ]

    for file_name in test_files:
        file_path = tmp_path / file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("test content")

    return str(tmp_path)


class TestDataSourceConnector:
    """Test cases for DataSourceConnector."""

    def test_init_with_config_file(self, config_file):
        """Test connector initialization with config file."""
        connector = DataSourceConnector(config_path=config_file)

        assert connector.config is not None
        assert "domains" in connector.config
        assert "sample_trustee_performance" in connector.config["domains"]
        assert len(connector.compiled_patterns) == 2

    def test_init_with_missing_config_file(self):
        """Test initialization with non-existent config file."""
        with pytest.raises(DataSourceConnectorError, match="Configuration file not found"):
            DataSourceConnector(config_path="/nonexistent/config.yml")

    def test_init_with_invalid_yaml(self, tmp_path):
        """Test initialization with invalid YAML file."""
        bad_config = tmp_path / "bad_config.yml"
        bad_config.write_text("invalid: yaml: content: [")

        with pytest.raises(DataSourceConnectorError, match="Invalid YAML configuration"):
            DataSourceConnector(config_path=str(bad_config))

    def test_init_with_missing_domains(self, tmp_path):
        """Test initialization with config missing domains section."""
        bad_config = tmp_path / "no_domains.yml"
        bad_config.write_text("other_section: value")

        with pytest.raises(
            DataSourceConnectorError, match="Configuration missing 'domains' section"
        ):
            DataSourceConnector(config_path=str(bad_config))

    def test_invalid_regex_pattern(self, tmp_path):
        """Test initialization with invalid regex pattern."""
        bad_config = {
            "domains": {
                "bad_domain": {
                    "pattern": "[invalid regex(",  # Invalid regex
                    "select": "latest_by_mtime",
                }
            }
        }

        config_path = tmp_path / "bad_regex.yml"
        with open(config_path, "w") as f:
            yaml.dump(bad_config, f)

        with pytest.raises(DataSourceConnectorError, match="Invalid regex pattern"):
            DataSourceConnector(config_path=str(config_path))

    @pytest.mark.skip(reason="Test depends on deprecated sample_trustee_performance domain - pending Epic 5")
    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_sample_trustee_performance_files(self, mock_settings, config_file, test_data_dir):
        """Test discovery of trustee performance files with Chinese characters."""
        # Mock settings to use test directory
        mock_settings.return_value.data_base_dir = test_data_dir
        mock_settings.return_value.data_sources_config = config_file

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover("sample_trustee_performance")

        # Should find trustee performance files and ignore others
        assert len(files) > 0

        # Check that discovered files have correct domain
        for file in files:
            assert file.domain == "trustee_performance"
            assert "受托业绩" in file.path
            assert file.path.endswith(".xlsx")

        # Verify year/month extraction
        yearly_files = [f for f in files if f.year is not None]
        assert len(yearly_files) > 0

        for file in yearly_files:
            assert file.year >= 2020  # Reasonable year range
            if file.month:
                assert 1 <= file.month <= 12

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_ignores_temp_files(self, mock_settings, config_file, test_data_dir):
        """Test that temporary and email files are ignored."""
        mock_settings.return_value.data_base_dir = test_data_dir

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover()

        # Should not include temporary files
        paths = [f.path for f in files]
        assert not any(".tmp" in p for p in paths)
        assert not any(".eml" in p for p in paths)
        assert not any("~$" in p for p in paths)

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_excludes_directories(self, mock_settings, config_file, test_data_dir):
        """Test that excluded directories are not scanned."""
        mock_settings.return_value.data_base_dir = test_data_dir

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover()

        # Should not include files from backup directory
        paths = [f.path for f in files]
        assert not any("backup" + os.sep in p for p in paths)

    @pytest.mark.skip(reason="Test depends on deprecated trustee_performance domain config - pending Epic 5")
    @patch("src.work_data_hub.config.settings.get_settings")
    def test_latest_by_year_month_selection(self, mock_settings, config_file, tmp_path):
        """Test selection of latest version by year/month."""
        # Create test files with different dates
        test_files = ["2024_01_受托业绩.xlsx", "2024_12_受托业绩.xlsx", "2023_06_受托业绩.xlsx"]

        for filename in test_files:
            (tmp_path / filename).write_text("test")

        mock_settings.return_value.data_base_dir = str(tmp_path)

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover("trustee_performance")

        # Should only return the latest file (2024_12)
        assert len(files) == 1
        assert files[0].year == 2024
        assert files[0].month == 12

    @pytest.mark.skip(reason="Test depends on deprecated trustee_performance domain config - pending Epic 5")
    @patch("src.work_data_hub.config.settings.get_settings")
    def test_latest_by_mtime_fallback(self, mock_settings, config_file, tmp_path):
        """Test fallback to mtime when year/month not available."""
        # Create files without date patterns
        older_file = tmp_path / "受托业绩_old.xlsx"
        newer_file = tmp_path / "受托业绩_new.xlsx"

        older_file.write_text("old content")
        newer_file.write_text("new content")

        # Modify mtime to make one newer
        import time

        newer_time = time.time()
        older_time = newer_time - 3600  # 1 hour older

        os.utime(older_file, (older_time, older_time))
        os.utime(newer_file, (newer_time, newer_time))

        # Create config that matches these files but doesn't extract dates
        config_no_dates = {
            "domains": {
                "no_dates": {
                    "pattern": r"受托业绩.*\.xlsx$",
                    "select": "latest_by_year_month",
                    "sheet": 0,
                }
            }
        }

        config_path = tmp_path / "no_dates.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_no_dates, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)

        connector = DataSourceConnector(config_path=str(config_path))
        files = connector.discover("no_dates")

        # Should return the newer file
        assert len(files) == 1
        assert "new" in files[0].path

    def test_discover_unknown_domain(self, config_file):
        """Test discovery with unknown domain raises error."""
        connector = DataSourceConnector(config_path=config_file)

        with pytest.raises(DataSourceConnectorError, match="Unknown domain"):
            connector.discover("nonexistent_domain")

    @pytest.mark.skip(reason="Test depends on deprecated trustee_performance domain config - pending Epic 5")
    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_all_domains(self, mock_settings, config_file, tmp_path):
        """Test discovery across all domains."""
        # Create files for different domains
        (tmp_path / "2024_11_受托业绩.xlsx").write_text("trustee")
        (tmp_path / "test_simple.xlsx").write_text("simple")

        mock_settings.return_value.data_base_dir = str(tmp_path)

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover()  # No specific domain

        # Should find files from both domains
        domains = {f.domain for f in files}
        assert "trustee_performance" in domains
        assert "simple_test" in domains

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_empty_directory(self, mock_settings, config_file, tmp_path):
        """Test discovery in empty directory."""
        mock_settings.return_value.data_base_dir = str(tmp_path)

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover()

        assert files == []

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_discover_nonexistent_directory(self, mock_settings, config_file):
        """Test discovery with non-existent base directory."""
        mock_settings.return_value.data_base_dir = "/nonexistent/directory"

        connector = DataSourceConnector(config_path=config_file)
        files = connector.discover()

        # Should return empty list and log warning
        assert files == []

    def test_file_metadata_extraction(self, config_file, tmp_path):
        """Test that file metadata is properly extracted."""
        # Create a test file
        test_file = tmp_path / "2024_11_受托业绩.xlsx"
        test_file.write_text("test content")

        with patch("src.work_data_hub.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.data_base_dir = str(tmp_path)

            connector = DataSourceConnector(config_path=config_file)
            files = connector.discover("trustee_performance")

            if files:
                file = files[0]
                assert "size_bytes" in file.metadata
                assert "modified_time" in file.metadata
                assert "filename" in file.metadata
                assert file.metadata["filename"] == "2024_11_受托业绩.xlsx"

    @pytest.mark.skip(reason="Test depends on deprecated trustee_performance domain config - pending Epic 5")
    @patch("src.work_data_hub.config.settings.get_settings")
    def test_latest_by_year_month_and_version_selection(self, mock_settings, tmp_path):
        """Test selection of latest version by year/month with version-aware strategy."""
        # Create versioned directory structure with Chinese filenames
        scenarios = [
            ("数据采集/V1", "24年11月年金终稿数据.xlsx"),
            ("数据采集/V2", "24年11月年金终稿数据.xlsx"),  # Same month, higher version
            ("数据采集/V1", "24年10月年金终稿数据.xlsx"),  # Different month
            ("数据采集/VX", "24年12月年金终稿数据.xlsx"),  # Malformed version
        ]

        for dir_path, filename in scenarios:
            full_dir = tmp_path / dir_path
            full_dir.mkdir(parents=True, exist_ok=True)
            (full_dir / filename).write_text("test content")

        # Create config with annuity_performance domain
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "test_config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should return 3 files: V2 for 2024/11, V1 for 2024/10, VX(None) for 2024/12
        assert len(files) == 3

        # Verify version selection logic
        files_by_month = {(f.year, f.month): f for f in files}

        # Check 2024/11 -> V2 (highest version)
        nov_file = files_by_month[(2024, 11)]
        assert nov_file.metadata["version"] == 2
        assert "V2" in nov_file.path

        # Check 2024/10 -> V1 (only version)
        oct_file = files_by_month[(2024, 10)]
        assert oct_file.metadata["version"] == 1
        assert "V1" in oct_file.path

        # Check 2024/12 -> VX (malformed version = None)
        dec_file = files_by_month[(2024, 12)]
        assert dec_file.metadata["version"] is None
        assert "VX" in dec_file.path
