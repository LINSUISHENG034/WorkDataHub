"""Integration tests for pattern-based file matching.

Tests FilePatternMatcher with realistic folder structures
and Chinese character support according to Epic 3 Story 3.2 acceptance criteria.
"""

import pytest
from pathlib import Path
import tempfile
import time
from datetime import datetime

from work_data_hub.io.connectors.file_pattern_matcher import (
    FilePatternMatcher, FileMatchResult
)
from work_data_hub.io.connectors.exceptions import DiscoveryError


class TestFilePatternMatchingIntegration:
    """Integration tests for FilePatternMatcher with realistic scenarios."""

    def test_end_to_end_pattern_matching_with_chinese_files(self, tmp_path):
        """AC: End-to-end pattern matching works with Chinese characters."""
        # Create realistic scenario like in acceptance criteria
        (tmp_path / "年金数据2025.xlsx").touch()
        (tmp_path / "~$年金数据2025.xlsx").touch()  # Excel temp file
        (tmp_path / "规模明细回复.xlsx").touch()  # Reply file

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*年金*.xlsx", "*规模明细*.xlsx"],
            exclude_patterns=["~$*", "*回复*"]
        )

        # Should find exactly 1 file after filtering
        assert result.match_count == 1
        assert result.matched_file.name == "年金数据2025.xlsx"
        assert len(result.candidates_found) == 3
        assert len(result.excluded_files) == 2
        assert "~$年金数据2025.xlsx" in [f.name for f in result.excluded_files]
        assert "规模明细回复.xlsx" in [f.name for f in result.excluded_files]

    def test_ambiguous_match_scenario_with_real_files(self, tmp_path):
        """AC: Ambiguous match scenario raises appropriate error."""
        # Create files that would cause ambiguity
        (tmp_path / "年金数据V1.xlsx").touch()
        (tmp_path / "年金数据V2.xlsx").touch()

        matcher = FilePatternMatcher()

        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*年金数据*.xlsx"]
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "2 files" in str(exc_info.value)

    def test_no_files_found_scenario(self, tmp_path):
        """AC: No files found raises appropriate error."""
        matcher = FilePatternMatcher()

        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*不存在的*.xlsx"]
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "No files found matching patterns" in str(exc_info.value)

    def test_single_pattern_matching(self, tmp_path):
        """AC: Single pattern matching works correctly."""
        # Create files for single pattern test
        (tmp_path / "target_file.xlsx").touch()
        (tmp_path / "other_file.txt").touch()

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*target*.xlsx"]
        )

        assert result.match_count == 1
        assert result.matched_file.name == "target_file.xlsx"
        assert len(result.candidates_found) == 1

    def test_unicode_chinese_character_support(self, tmp_path):
        """AC: Chinese characters in filenames handled correctly."""
        # Create single file with Chinese characters to satisfy "exactly 1 file" requirement
        (tmp_path / "公司年金奖.xlsx").touch()

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*公司*.xlsx"]
        )

        # Should find exactly 1 file with Chinese characters
        assert result.match_count == 1
        assert result.matched_file.name == "公司年金奖.xlsx"

    def test_unicode_chinese_multiple_files_raises_error(self, tmp_path):
        """AC: Multiple Chinese character files raise ambiguous error."""
        # Create files with various Chinese character patterns
        (tmp_path / "公司年金奖.xlsx").touch()
        (tmp_path / "规模明细表.xlsx").touch()
        (tmp_path / "客户数据Ａ.xlsx").touch()  # Full-width character

        matcher = FilePatternMatcher()

        # Multiple patterns matching multiple files should raise DiscoveryError
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*公司*.xlsx", "*规模*.xlsx", "*客户*.xlsx"]
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "3 files" in str(exc_info.value)

    def test_performance_with_realistic_file_count(self, tmp_path):
        """AC: Performance meets requirement (<1 second)."""
        # Create realistic number of files - 49 to exclude, 1 target
        for i in range(49):
            (tmp_path / f"temp_file_{i:03d}.xlsx").touch()
        (tmp_path / "target_data.xlsx").touch()

        matcher = FilePatternMatcher()

        start_time = time.time()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            exclude_patterns=["temp_*"]  # Exclude all temp files
        )
        duration = time.time() - start_time

        # Performance requirement: <1 second for typical folder
        assert duration < 1.0, f"Pattern matching took {duration:.3f}s, expected <1.0s"
        # Should find 50 candidates but only 1 match after filtering
        assert len(result.candidates_found) == 50
        assert result.match_count == 1
        assert result.matched_file.name == "target_data.xlsx"

    def test_complex_exclude_patterns(self, tmp_path):
        """AC: Complex exclude patterns work correctly."""
        # Create various file types - only 1 should remain after filtering
        (tmp_path / "重要数据.xlsx").touch()
        (tmp_path / "~temp重要数据.xlsx").touch()
        (tmp_path / "重要数据回复.xlsx").touch()
        (tmp_path / "重要数据备份.eml").touch()

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*重要数据*.xlsx"],
            exclude_patterns=["~*", "*回复*"]  # Exclude temp and reply files
        )

        # Should find only 1 file after excluding others
        assert result.match_count == 1
        assert result.matched_file.name == "重要数据.xlsx"
        assert len(result.candidates_found) == 3  # xlsx files only (eml not matched by pattern)
        assert len(result.excluded_files) == 2  # temp and reply files

        excluded_names = [f.name for f in result.excluded_files]
        assert "~temp重要数据.xlsx" in excluded_names
        assert "重要数据回复.xlsx" in excluded_names

    def test_complex_exclude_patterns_ambiguous_raises_error(self, tmp_path):
        """AC: Multiple files after complex exclude filtering raises error."""
        # Create various file types - 2 should remain after filtering
        (tmp_path / "重要数据.xlsx").touch()
        (tmp_path / "~temp重要数据.xlsx").touch()
        (tmp_path / "重要数据回复.xlsx").touch()
        (tmp_path / "其他重要数据.xlsx").touch()

        matcher = FilePatternMatcher()

        # Multiple files remaining after exclude should raise DiscoveryError
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*重要数据*.xlsx"],
                exclude_patterns=["~*", "*回复*"]  # Leaves 重要数据.xlsx and 其他重要数据.xlsx
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "2 files" in str(exc_info.value)

    def test_metadata_accuracy(self, tmp_path):
        """AC: FileMatchResult metadata is accurate and complete."""
        # Create test scenario - only 1 file should match after filtering
        (tmp_path / "final_file.xlsx").touch()
        (tmp_path / "~$excluded_temp.xlsx").touch()  # Excel temp file format
        (tmp_path / "another_file.txt").touch()  # Won't match xlsx pattern

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            exclude_patterns=["~$*"]  # Exclude Excel temp files
        )

        # Verify metadata completeness
        assert isinstance(result, FileMatchResult)
        assert result.matched_file.name == "final_file.xlsx"
        assert result.patterns_used == ["*.xlsx"]
        assert result.exclude_patterns == ["~$*"]
        assert len(result.candidates_found) == 2  # final_file.xlsx and temp file
        assert len(result.excluded_files) == 1  # Only the temp file
        assert result.match_count == 1
        assert isinstance(result.selected_at, datetime)

    def test_empty_directory_handling(self, tmp_path):
        """AC: Empty directory raises appropriate DiscoveryError."""
        matcher = FilePatternMatcher()

        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*.xlsx"]
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "No files found matching patterns" in str(exc_info.value)