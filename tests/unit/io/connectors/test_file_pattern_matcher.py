"""Unit tests for file pattern matching with include/exlude rules.

Tests Epic 3 Story 3.2 Pattern-Based File Matcher implementation
with comprehensive acceptance criteria validation.
"""

import pytest
from pathlib import Path
from datetime import datetime

from work_data_hub.io.connectors.file_pattern_matcher import (
    FilePatternMatcher,
    FileMatchResult,
)
from work_data_hub.io.connectors.exceptions import DiscoveryError


class TestFilePatternMatcher:
    """Test file pattern matching with include/exlude rules."""

    def test_include_patterns_find_matching_files(self, tmp_path):
        """AC: Include patterns find matching files."""
        # Create test files - only one should match the patterns
        (tmp_path / "年金数据2025.xlsx").touch()
        (tmp_path / "规模明细2025.xlsx").touch()
        (tmp_path / "其他文件.txt").touch()

        matcher = FilePatternMatcher()
        # Use separate patterns to get exactly 1 match each
        result1 = matcher.match_files(
            search_path=tmp_path, include_patterns=["*年金*.xlsx"]
        )

        result2 = matcher.match_files(
            search_path=tmp_path, include_patterns=["*规模明细*.xlsx"]
        )

        # Both results should find exactly 1 file
        assert result1.match_count == 1
        assert result2.match_count == 1
        assert "年金数据2025.xlsx" in [f.name for f in result1.candidates_found]
        assert "规模明细2025.xlsx" in [f.name for f in result2.candidates_found]

    def test_exclude_patterns_filter_temp_files(self, tmp_path):
        """AC: Exclude patterns filter out temp files."""
        # Create test files
        (tmp_path / "年金数据2025.xlsx").touch()
        (tmp_path / "~$年金数据2025.xlsx").touch()  # Excel temp file
        (tmp_path / "规模明细回复.xlsx").touch()  # Reply file

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            exclude_patterns=["~$*", "*回复*"],
        )

        assert len(result.candidates_found) == 3
        assert len(result.excluded_files) == 2
        assert result.match_count == 1
        assert result.matched_file.name == "年金数据2025.xlsx"
        assert "~$年金数据2025.xlsx" in [f.name for f in result.excluded_files]
        assert "规模明细回复.xlsx" in [f.name for f in result.excluded_files]

    def test_exactly_one_file_required(self, tmp_path):
        """AC: Exactly 1 file must remain after filtering."""
        # Create multiple matching files
        (tmp_path / "年金数据V1.xlsx").touch()
        (tmp_path / "年金数据V2.xlsx").touch()

        matcher = FilePatternMatcher()

        # Test no matches
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path, include_patterns=["*不存在的*.xlsx"]
            )
        assert exc_info.value.failed_stage == "file_matching"
        assert "No files found matching patterns" in str(exc_info.value)

        # Test ambiguous matches
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path, include_patterns=["*年金数据*.xlsx"]
            )
        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "2 files" in str(exc_info.value)

    def test_chinese_characters_in_patterns(self, tmp_path):
        """AC: Chinese characters handled correctly."""
        # Create file with Chinese name - only 1 file to satisfy "exactly 1 file" requirement
        (tmp_path / "年金数据2025.xlsx").touch()

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path, include_patterns=["*年金*.xlsx"]
        )

        # Should find exactly 1 file with Chinese characters
        assert result.match_count == 1
        assert result.matched_file.name == "年金数据2025.xlsx"
        assert "年金数据2025.xlsx" in [f.name for f in result.candidates_found]

    def test_chinese_characters_ambiguous_raises_error(self, tmp_path):
        """AC: Multiple Chinese character files raise ambiguous error."""
        # Create multiple files with Chinese names
        (tmp_path / "年金数据2025.xlsx").touch()
        (tmp_path / "规模明细表.xlsx").touch()

        matcher = FilePatternMatcher()

        # Multiple patterns matching multiple files should raise DiscoveryError
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path, include_patterns=["*年金*.xlsx", "*规模*.xlsx"]
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "2 files" in str(exc_info.value)

    def test_unicode_normalization(self, tmp_path):
        """AC: Unicode normalization works correctly."""
        # Create file with full-width characters
        (tmp_path / "公司Ａ.xlsx").touch()  # Full-width space

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path, include_patterns=["*公司*.xlsx"]
        )

        # Should find file with full-width characters
        assert len(result.candidates_found) == 1
        assert "公司Ａ.xlsx" in [f.name for f in result.candidates_found]

    def test_performance_requirement(self, tmp_path):
        """AC: File matching completes within 1 second."""
        import time

        # Create many test files - 99 to exclude, 1 target file
        for i in range(99):
            (tmp_path / f"temp_file_{i:03d}.xlsx").touch()
        (tmp_path / "target_file.xlsx").touch()

        matcher = FilePatternMatcher()

        start_time = time.time()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            exclude_patterns=["temp_*"],  # Exclude all temp files, keep only target
        )
        duration = time.time() - start_time

        # Performance requirement: <1 second for typical folder
        assert duration < 1.0, f"File matching took {duration:.2f}s, expected <1.0s"
        # Should find 100 candidates but only 1 match after filtering
        assert len(result.candidates_found) == 100
        assert result.match_count == 1
        assert result.matched_file.name == "target_file.xlsx"

    def test_result_metadata_complete(self, tmp_path):
        """AC: FileMatchResult contains all required metadata."""
        # Create test files - use correct Excel temp file format (~$)
        (tmp_path / "target_file.xlsx").touch()
        (tmp_path / "~$temp_file.xlsx").touch()  # Excel temp file format

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path, include_patterns=["*.xlsx"], exclude_patterns=["~$*"]
        )

        # Verify all fields are populated
        assert isinstance(result.matched_file, Path)
        assert result.matched_file.name == "target_file.xlsx"
        assert isinstance(result.patterns_used, list)
        assert "*.xlsx" in result.patterns_used
        assert isinstance(result.exclude_patterns, list)
        assert "~$*" in result.exclude_patterns
        assert isinstance(result.candidates_found, list)
        assert len(result.candidates_found) == 2  # target_file and temp file
        assert isinstance(result.excluded_files, list)
        assert len(result.excluded_files) == 1  # temp file excluded
        assert result.match_count == 1
        assert isinstance(result.selected_at, datetime)

    def test_empty_directory_handling(self, tmp_path):
        """AC: Empty directory raises appropriate error."""
        matcher = FilePatternMatcher()

        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(search_path=tmp_path, include_patterns=["*.xlsx"])
        assert exc_info.value.failed_stage == "file_matching"
        assert "No files found matching patterns" in str(exc_info.value)

    def test_pattern_matching_edge_cases(self, tmp_path):
        """AC: Edge cases in pattern matching handled correctly."""
        # Test files with various edge cases
        (tmp_path / "normal_file.xlsx").touch()
        (tmp_path / "file with spaces.xlsx").touch()
        (tmp_path / "file-with-dashes.xlsx").touch()
        (tmp_path / "file.with.dots.xlsx").touch()

        matcher = FilePatternMatcher()

        # Test exact match
        result = matcher.match_files(
            search_path=tmp_path, include_patterns=["normal_file.xlsx"]
        )
        assert result.match_count == 1
        assert result.matched_file.name == "normal_file.xlsx"

        # Test pattern with spaces
        result = matcher.match_files(
            search_path=tmp_path, include_patterns=["*file with spaces*"]
        )
        assert result.match_count == 1
        assert result.matched_file.name == "file with spaces.xlsx"

    def test_exclude_pattern_compatibility(self, tmp_path):
        """AC: Exclude patterns work with include patterns."""
        # Create test files - only 1 should remain after filtering
        (tmp_path / "keep_final.xlsx").touch()
        (tmp_path / "temp_keep.xlsx").touch()
        (tmp_path / "remove_temp.xlsx").touch()

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["keep*.xlsx", "temp_*.xlsx"],
            exclude_patterns=["*temp*"],  # Should exclude temp_keep and remove_temp
        )

        # Should find 2 candidates (keep_final, temp_keep) but only 1 match after filtering
        assert len(result.candidates_found) == 2  # keep_final, temp_keep
        assert result.match_count == 1  # Only keep_final (temp files excluded)
        assert result.matched_file.name == "keep_final.xlsx"
        assert "temp_keep.xlsx" in [f.name for f in result.excluded_files]

    def test_exclude_pattern_ambiguous_raises_error(self, tmp_path):
        """AC: Multiple files after exclude filtering raises ambiguous error."""
        # Create test files - 2 should remain after filtering
        (tmp_path / "keep1.xlsx").touch()
        (tmp_path / "keep2.xlsx").touch()
        (tmp_path / "temp_file.xlsx").touch()

        matcher = FilePatternMatcher()

        # Multiple files remaining after exclude should raise DiscoveryError
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*.xlsx"],
                exclude_patterns=[
                    "temp_*"
                ],  # Excludes temp_file, leaves keep1 and keep2
            )

        assert exc_info.value.failed_stage == "file_matching"
        assert "Ambiguous match" in str(exc_info.value)
        assert "2 files" in str(exc_info.value)


class TestSelectionStrategy:
    """Story 6.2-P16 AC-1, AC-4: Tests for file selection strategies."""

    def test_default_error_strategy_raises_on_ambiguity(self, tmp_path):
        """AC: Default behavior raises error on ambiguous match (backward compatible)."""
        (tmp_path / "file1.xlsx").touch()
        (tmp_path / "file2.xlsx").touch()

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()

        # Default (ERROR strategy) should raise
        with pytest.raises(DiscoveryError) as exc_info:
            matcher.match_files(search_path=tmp_path, include_patterns=["*.xlsx"])
        assert "Ambiguous match" in str(exc_info.value)

        # Explicit ERROR strategy should also raise
        with pytest.raises(DiscoveryError):
            matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*.xlsx"],
                selection_strategy=SelectionStrategy.ERROR,
            )

    def test_first_strategy_alphabetical_selection(self, tmp_path):
        """AC: FIRST strategy selects first file alphabetically."""
        # Create files - z comes after a
        (tmp_path / "z_file.xlsx").touch()
        (tmp_path / "a_file.xlsx").touch()
        (tmp_path / "m_file.xlsx").touch()

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            selection_strategy=SelectionStrategy.FIRST,
        )

        # Should select first alphabetically
        assert result.matched_file.name == "a_file.xlsx"
        assert result.match_count == 3  # All 3 files matched

    def test_newest_strategy_mtime_selection(self, tmp_path):
        """AC: NEWEST strategy selects most recently modified file."""
        import os
        import time

        # Create files with explicit, deterministic modification times
        old_file = tmp_path / "old_file.xlsx"
        old_file.touch()
        mid_file = tmp_path / "mid_file.xlsx"
        mid_file.touch()
        new_file = tmp_path / "new_file.xlsx"
        new_file.touch()

        base_time = time.time()
        os.utime(old_file, (base_time - 30, base_time - 30))
        os.utime(mid_file, (base_time - 20, base_time - 20))
        os.utime(new_file, (base_time - 10, base_time - 10))

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            selection_strategy=SelectionStrategy.NEWEST,
        )

        # Should select newest (most recently modified)
        assert result.matched_file.name == "new_file.xlsx"

    def test_oldest_strategy_mtime_selection(self, tmp_path):
        """AC: OLDEST strategy selects oldest modified file."""
        import os
        import time

        # Create files with explicit, deterministic modification times
        old_file = tmp_path / "old_file.xlsx"
        old_file.touch()
        mid_file = tmp_path / "mid_file.xlsx"
        mid_file.touch()
        new_file = tmp_path / "new_file.xlsx"
        new_file.touch()

        base_time = time.time()
        os.utime(old_file, (base_time - 30, base_time - 30))
        os.utime(mid_file, (base_time - 20, base_time - 20))
        os.utime(new_file, (base_time - 10, base_time - 10))

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            selection_strategy=SelectionStrategy.OLDEST,
        )

        # Should select oldest
        assert result.matched_file.name == "old_file.xlsx"

    def test_selection_strategy_single_file_bypass(self, tmp_path):
        """AC: Strategy only used when multiple files match - single file works regardless."""
        (tmp_path / "only_file.xlsx").touch()

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()

        # All strategies should return the single file
        for strategy in SelectionStrategy:
            result = matcher.match_files(
                search_path=tmp_path,
                include_patterns=["*.xlsx"],
                selection_strategy=strategy,
            )
            assert result.matched_file.name == "only_file.xlsx"

    def test_selection_strategy_with_excludes(self, tmp_path):
        """AC: Selection strategy works correctly with exclude patterns."""
        (tmp_path / "a_keep.xlsx").touch()
        (tmp_path / "z_keep.xlsx").touch()
        (tmp_path / "temp_file.xlsx").touch()

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*.xlsx"],
            exclude_patterns=["temp_*"],
            selection_strategy=SelectionStrategy.FIRST,
        )

        # Should exclude temp_file, then select first from remaining
        assert result.matched_file.name == "a_keep.xlsx"
        assert result.match_count == 2  # 2 files after excluding temp
        assert len(result.excluded_files) == 1

    def test_selection_strategy_with_chinese_filenames(self, tmp_path):
        """AC: Selection strategy works with Chinese filenames."""
        (tmp_path / "报表A2024.xlsx").touch()
        (tmp_path / "报表B2024.xlsx").touch()
        (tmp_path / "报表C2024.xlsx").touch()

        from work_data_hub.io.connectors.file_pattern_matcher import SelectionStrategy

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            search_path=tmp_path,
            include_patterns=["*报表*.xlsx"],
            selection_strategy=SelectionStrategy.FIRST,
        )

        # Should select first alphabetically (containing A)
        assert result.matched_file.name == "报表A2024.xlsx"

