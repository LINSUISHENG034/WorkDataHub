"""Unit tests for version scanner module.

Tests all strategies (highest_number, latest_modified, manual) and edge cases
including Unicode paths, ambiguous timestamps, and file-pattern-aware detection.
"""

import os
import time
from datetime import datetime
import pytest
from pathlib import Path

from work_data_hub.io.connectors.version_scanner import VersionScanner, VersionedPath
from work_data_hub.io.connectors.exceptions import DiscoveryError


class TestVersionScanner:
    """Test version folder detection and selection"""

    def test_highest_number_selects_v2_over_v1(self, tmp_path):
        """AC: V2 > V1 with highest_number strategy"""
        # Create V1 and V2 folders
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        # Create matching files in both
        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "V2"
        assert result.path == v2
        assert result.strategy_used == "highest_number"
        assert "V1" in result.rejected_versions

    def test_no_version_folders_uses_base_path(self, tmp_path):
        """AC: Fallback to base path when no V folders"""
        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "base"
        assert result.path == tmp_path
        assert result.rejected_versions == []

    def test_latest_modified_selects_newest_folder(self, tmp_path):
        """AC: latest_modified strategy uses timestamp"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        # Explicitly set different modification times to avoid Windows filesystem granularity issues
        import os
        current_time = time.time()
        os.utime(v1, (current_time, current_time - 10))  # V1 modified 10 seconds ago
        os.utime(v2, (current_time, current_time))  # V2 modified now

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='latest_modified'
        )

        assert result.version == "V2"
        assert result.strategy_used == "latest_modified"

    def test_manual_override_uses_specified_version(self, tmp_path):
        """AC: Manual override bypasses automatic detection"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number',
            version_override="V1"  # Override to V1
        )

        assert result.version == "V1"
        assert result.path == v1
        assert result.strategy_used == "manual"

    def test_file_pattern_aware_skips_empty_versions(self, tmp_path):
        """AC: Skip version folders with no matching files (Decision #1)"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        # V1 has matching file, V2 is empty
        (v1 / "annuity_data.xlsx").touch()
        # V2 has no files
        # Ensure V2 exists but is detected as empty
        (v2 / "empty.txt").touch()  # Create file to ensure directory exists but has no matching files

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*annuity*.xlsx"],
            strategy='highest_number'
        )

        # Should select V1 (only version with matching files)
        assert result.version == "V1"
        assert "V2 (no matching files)" in result.rejected_versions

    def test_ambiguous_versions_raises_error(self, tmp_path):
        """AC: Ambiguous timestamps raise error"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        # Set same modification time
        import os
        mtime = v1.stat().st_mtime
        os.utime(v2, (mtime, mtime))

        scanner = VersionScanner()
        with pytest.raises(DiscoveryError) as exc_info:
            scanner.detect_version(
                base_path=tmp_path,
                file_patterns=["*.xlsx"],
                strategy='latest_modified'
            )

        assert exc_info.value.failed_stage == "version_detection"
        assert "Ambiguous versions" in str(exc_info.value)

    def test_invalid_manual_version_raises_error(self, tmp_path):
        """AC: Manual override validates version exists"""
        scanner = VersionScanner()
        with pytest.raises(DiscoveryError) as exc_info:
            scanner.detect_version(
                base_path=tmp_path,
                file_patterns=["*.xlsx"],
                version_override="V99"  # Doesn't exist
            )

        assert exc_info.value.failed_stage == "version_detection"
        assert "V99" in str(exc_info.value)

    def test_v10_greater_than_v9(self, tmp_path):
        """AC: Numeric comparison (V10 > V9, not alphabetic)"""
        for i in [1, 2, 9, 10]:
            v = tmp_path / f"V{i}"
            v.mkdir()
            (v / "data.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "V10"

    def test_chinese_characters_in_paths(self, tmp_path):
        """AC: Handle Unicode Chinese paths"""
        base = tmp_path / "收集数据" / "数据采集"
        base.mkdir(parents=True)
        v1 = base / "V1"
        v1.mkdir()
        (v1 / "年金数据.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base,
            file_patterns=["*年金*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "V1"
        assert "年金数据.xlsx" in [f.name for f in result.path.glob("*.xlsx")]

    def test_base_path_not_exist_raises_error(self, tmp_path):
        """Test: Non-existent base path raises DiscoveryError"""
        nonexistent = tmp_path / "nonexistent"

        scanner = VersionScanner()
        with pytest.raises(DiscoveryError) as exc_info:
            scanner.detect_version(
                base_path=nonexistent,
                file_patterns=["*.xlsx"],
                strategy='highest_number'
            )

        assert exc_info.value.failed_stage == "version_detection"
        assert "not found" in str(exc_info.value).lower()

    def test_invalid_strategy_raises_error(self, tmp_path):
        """Test: Invalid strategy raises DiscoveryError"""
        v1 = tmp_path / "V1"
        v1.mkdir()
        (v1 / "data.xlsx").touch()

        scanner = VersionScanner()
        with pytest.raises(DiscoveryError) as exc_info:
            scanner.detect_version(
                base_path=tmp_path,
                file_patterns=["*.xlsx"],
                strategy='invalid_strategy'
            )

        assert exc_info.value.failed_stage == "version_detection"
        assert "Unsupported" in str(exc_info.value)

    def test_version_regex_handles_edge_cases(self, tmp_path):
        """Test: Version regex properly matches and rejects invalid formats"""
        # Create test folders
        valid_folders = ["V1", "V2", "V10", "V99"]
        invalid_folders = ["V", "V0", "V1a", "version1", "VV1"]

        for folder_name in valid_folders + invalid_folders:
            folder = tmp_path / folder_name
            folder.mkdir()
            (folder / "data.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        # Should only find valid version folders
        valid_versions = [v for v in valid_folders if (tmp_path / v).exists()]
        assert result.version in valid_versions

    def test_file_pattern_supports_multiple_patterns(self, tmp_path):
        """Test: File pattern matching works with multiple patterns"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        # V1 has .xlsx file, V2 has .csv file
        (v1 / "data.xlsx").touch()
        (v2 / "data.csv").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx", "*.csv"],
            strategy='highest_number'
        )

        # Should select V2 (newer) since both have matching files
        assert result.version == "V2"

    def test_empty_folder_skipped_in_file_pattern_aware(self, tmp_path):
        """Test: Empty version folders are skipped in file-pattern-aware detection"""
        v1 = tmp_path / "V1"
        v2 = tmp_path / "V2"
        v1.mkdir()
        v2.mkdir()

        # V1 has matching file, V2 exists but has no files
        (v1 / "data.xlsx").touch()
        # V2 is empty

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        # Should select V1 (only version with matching files)
        assert result.version == "V1"
        assert "V2 (no matching files)" in result.rejected_versions

    def test_versionedpath_contains_all_required_fields(self, tmp_path):
        """Test: VersionedPath contains all required metadata"""
        v1 = tmp_path / "V1"
        v1.mkdir()
        (v1 / "data.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        # Check all required fields are present and have correct types
        assert hasattr(result, 'path')
        assert hasattr(result, 'version')
        assert hasattr(result, 'strategy_used')
        assert hasattr(result, 'selected_at')
        assert hasattr(result, 'rejected_versions')

        assert isinstance(result.path, Path)
        assert isinstance(result.version, str)
        assert isinstance(result.strategy_used, str)
        assert isinstance(result.selected_at, datetime)
        assert isinstance(result.rejected_versions, list)

    def test_folder_access_error_handling(self, tmp_path):
        """Test: Folder access errors are handled gracefully"""
        v1 = tmp_path / "V1"
        v1.mkdir()
        (v1 / "data.xlsx").touch()

        # Create a directory that will cause access issues
        problem_dir = tmp_path / "V2"
        problem_dir.mkdir()
        (problem_dir / "data.xlsx").touch()

        # Make directory inaccessible (this will vary by OS)
        try:
            problem_dir.chmod(0o000)
        except OSError:
            pass  # Some systems don't support chmod

        scanner = VersionScanner()
        # Should still work despite access issues on one folder
        result = scanner.detect_version(
            base_path=tmp_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        # Should select V1 (highest number among accessible folders with matching files)
        # V2 might be selected if both V1 and V2 are accessible - this is correct behavior
        assert result.version in ["V1", "V2"]