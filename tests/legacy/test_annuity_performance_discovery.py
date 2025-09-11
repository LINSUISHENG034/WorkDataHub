"""
Test cases for annuity performance discovery with version-aware file selection.

This module tests the version extraction logic, year normalization, and
version-aware selection strategy for annuity performance data files
stored in versioned directories (V1/, V2/, etc.) under "数据采集" directories.
"""

import time
from unittest.mock import patch

import pytest

from src.work_data_hub.io.connectors.file_connector import DataSourceConnector


@pytest.mark.legacy_data
class TestAnnuityPerformanceDiscovery:
    """Test cases for annuity performance discovery with version awareness."""

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_version_extraction_from_directory(self, mock_settings, tmp_path):
        """Test version extraction from V* directory names."""
        # Create structure: 数据采集/V2/24年11月年金终稿数据.xlsx
        data_dir = tmp_path / "数据采集" / "V2"
        data_dir.mkdir(parents=True)
        test_file = data_dir / "24年11月年金终稿数据.xlsx"
        test_file.write_text("test content")

        # Create config for annuity performance
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        assert len(files) == 1
        assert files[0].metadata["version"] == 2
        assert files[0].year == 2024  # Normalized from 24
        assert files[0].month == 11
        assert "V2" in files[0].path

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_version_selection_within_month(self, mock_settings, tmp_path):
        """Test selection of highest version within same month."""
        # Create V1 and V2 directories with same month files
        v1_dir = tmp_path / "数据采集" / "V1"
        v2_dir = tmp_path / "数据采集" / "V2"
        v10_dir = tmp_path / "数据采集" / "V10"  # Test double-digit versions

        for vdir in [v1_dir, v2_dir, v10_dir]:
            vdir.mkdir(parents=True)
            (vdir / "24年11月年金终稿数据.xlsx").write_text("test content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should only return V10 file (highest version)
        assert len(files) == 1
        assert files[0].metadata["version"] == 10
        assert "V10" in files[0].path

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_malformed_version_fallback(self, mock_settings, tmp_path):
        """Test fallback to mtime when version is malformed."""
        # Create directories with malformed versions
        bad_dir = tmp_path / "数据采集" / "VX"
        good_dir = tmp_path / "数据采集" / "V1"

        bad_dir.mkdir(parents=True)
        good_dir.mkdir(parents=True)

        # Same filename in both, create good_file newer
        bad_file = bad_dir / "24年11月年金终稿数据.xlsx"
        good_file = good_dir / "24年11月年金终稿数据.xlsx"

        bad_file.write_text("test content")
        time.sleep(0.01)  # Ensure different mtime
        good_file.write_text("test content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should return V1 file (valid version beats None version)
        assert len(files) == 1
        assert files[0].metadata["version"] == 1
        assert "V1" in files[0].path

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_year_normalization(self, mock_settings, tmp_path):
        """Test two-digit year normalization (24 → 2024)."""
        data_dir = tmp_path / "数据采集" / "V1"
        data_dir.mkdir(parents=True)

        # Test different year formats
        test_files = [
            "24年11月年金终稿数据.xlsx",  # Two-digit year
            "2024年12月年金终稿数据.xlsx",  # Four-digit year
        ]

        for filename in test_files:
            (data_dir / filename).write_text("test content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should find both files with normalized years
        years = {f.year for f in files}
        assert 2024 in years  # Both should normalize to 2024

        # Check that 2-digit year was normalized
        two_digit_file = next((f for f in files if "24年" in f.path), None)
        assert two_digit_file is not None
        assert two_digit_file.year == 2024

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_version_extraction_only_under_data_collection(self, mock_settings, tmp_path):
        """Test that version extraction only occurs under '数据采集' directories."""
        # Create structure outside of 数据采集 directory
        other_dir = tmp_path / "其他目录" / "V2"
        other_dir.mkdir(parents=True)
        other_file = other_dir / "24年11月年金终稿数据.xlsx"
        other_file.write_text("test content")

        # Create structure under 数据采集 directory
        data_dir = tmp_path / "数据采集" / "V3"
        data_dir.mkdir(parents=True)
        data_file = data_dir / "24年11月年金终稿数据.xlsx"
        data_file.write_text("test content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        assert len(files) >= 1

        # Check that only the file under 数据采集 has version extracted
        data_collection_files = [f for f in files if "数据采集" in f.path]
        other_files = [f for f in files if "其他目录" in f.path]

        if data_collection_files:
            assert data_collection_files[0].metadata["version"] == 3

        if other_files:
            assert other_files[0].metadata["version"] is None

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_multiple_year_month_groups(self, mock_settings, tmp_path):
        """Test selection across multiple (year, month) groups."""
        # Create multiple versions across different months
        scenarios = [
            ("V1", "24年10月年金终稿数据.xlsx", 2024, 10),
            ("V2", "24年10月年金终稿数据.xlsx", 2024, 10),  # Same month, higher version
            ("V1", "24年11月年金终稿数据.xlsx", 2024, 11),
            ("V3", "2023年12月年金终稿数据.xlsx", 2023, 12),
        ]

        for version_dir, filename, year, month in scenarios:
            vdir = tmp_path / "数据采集" / version_dir  # Place files directly in version directory
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / filename).write_text("test content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should return 3 files: V2 for 2024/10, V1 for 2024/11, V3 for 2023/12
        assert len(files) == 3

        # Group by (year, month) and check versions
        files_by_month = {}
        for f in files:
            key = (f.year, f.month)
            files_by_month[key] = f

        # Check 2024/10 -> V2
        assert (2024, 10) in files_by_month
        assert files_by_month[(2024, 10)].metadata["version"] == 2

        # Check 2024/11 -> V1
        assert (2024, 11) in files_by_month
        assert files_by_month[(2024, 11)].metadata["version"] == 1

        # Check 2023/12 -> V3
        assert (2023, 12) in files_by_month
        assert files_by_month[(2023, 12)].metadata["version"] == 3

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_chinese_filename_handling(self, mock_settings, tmp_path):
        """Test proper handling of Chinese filenames and regex matching."""
        data_dir = tmp_path / "数据采集" / "V1"
        data_dir.mkdir(parents=True)

        # Test various Chinese filename patterns
        test_files = [
            "24年11月年金终稿数据1209采集.xlsx",
            "2024年12月年金业绩终稿数据.xlsm",
            "24年01月企业年金终稿数据报告.xlsx",
        ]

        for filename in test_files:
            (data_dir / filename).write_text("test content")

        # Create config with Unicode-aware pattern
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should find all three files
        assert len(files) == 3

        # Verify all files have Chinese characters properly handled
        for file in files:
            assert "年金" in file.path
            assert "终稿数据" in file.path
            assert file.metadata["version"] == 1  # All under V1

    @patch("src.work_data_hub.config.settings.get_settings")
    def test_empty_version_fallback_to_mtime(self, mock_settings, tmp_path):
        """Test fallback to mtime when no versions are available."""
        # Create files without version directories (not under 数据采集)
        regular_dir = tmp_path / "regular"
        regular_dir.mkdir(parents=True)

        older_file = regular_dir / "24年10月年金终稿数据.xlsx"
        newer_file = regular_dir / "24年11月年金终稿数据.xlsx"

        older_file.write_text("older content")
        time.sleep(0.01)
        newer_file.write_text("newer content")

        # Create config
        config_content = {
            "domains": {
                "annuity_performance": {
                    "pattern": r"(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$",
                    "select": "latest_by_year_month_and_version",
                    "sheet": "规模明细",
                }
            }
        }

        config_file = tmp_path / "config.yml"
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f, allow_unicode=True)

        mock_settings.return_value.data_base_dir = str(tmp_path)
        mock_settings.return_value.data_sources_config = str(config_file)

        connector = DataSourceConnector(config_path=str(config_file))
        files = connector.discover("annuity_performance")

        # Should return both files (different months)
        assert len(files) == 2

        # Both files should have version=None
        for file in files:
            assert file.metadata["version"] is None
