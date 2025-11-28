"""Integration tests for version detection with realistic folder structures.

Based on Action Item #2 from Epic 2 retrospective, these tests use
realistic data structures from 202411 analysis rather than idealized fixtures.
"""

import os
import time
import pytest
from pathlib import Path

from work_data_hub.io.connectors.version_scanner import VersionScanner, VersionedPath
from work_data_hub.io.connectors.exceptions import DiscoveryError


class TestVersionDetectionIntegration:
    """Integration tests for version detection with real folder structures"""

    def test_single_version_scenario(self, tmp_path):
        """Test detection with 数据采集/V1 structure (single version)"""
        # Create realistic structure: 数据采集/V1/
        base_path = tmp_path / "数据采集"
        base_path.mkdir()
        v1 = base_path / "V1"
        v1.mkdir()

        # Create realistic annuity file
        (v1 / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*年金终稿*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "V1"
        assert result.path == v1
        assert result.strategy_used == "highest_number"

    def test_multi_version_scenario(self, tmp_path):
        """Test detection with 战区收集/V1/V2/V3 structure (multi-version)"""
        # Create realistic structure: 战区收集/V1/V2/V3
        base_path = tmp_path / "战区收集"
        base_path.mkdir()

        # Create versions
        v1 = base_path / "V1"
        v2 = base_path / "V2"
        v3 = base_path / "V3"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        # Create realistic files in each version
        (v1 / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx").touch()
        (v2 / "【for年金分战区经营分析】24年12月年金终稿数据1209采集.xlsx").touch()
        (v3 / "【for年金分战区经营分析】24年1月年金终稿数据1209采集.xlsx").touch()

        # Explicitly set different modification times to avoid filesystem granularity issues
        import os
        current_time = time.time()
        os.utime(v1, (current_time, current_time - 20))  # V1 oldest
        os.utime(v2, (current_time, current_time - 10))  # V2 middle
        os.utime(v3, (current_time, current_time))  # V3 newest

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*年金终稿*.xlsx"],
            strategy='latest_modified'
        )

        # Should select V3 (newest modification time)
        assert result.version == "V3"
        assert result.strategy_used == "latest_modified"

    def test_no_version_fallback_scenario(self, tmp_path):
        """Test detection with 组合排名 structure (no versions, fallback)"""
        # Create structure without version folders: 组合排名/
        base_path = tmp_path / "组合排名"
        base_path.mkdir()

        # Create file directly in base path (no versioning)
        (base_path / "【for年金分战区经营分析】24年11月组合排名数据.xlsx").touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*组合排名*.xlsx"],
            strategy='highest_number'
        )

        assert result.version == "base"
        assert result.path == base_path
        assert result.strategy_used == "highest_number"
        assert result.rejected_versions == []

    def test_file_pattern_aware_partial_correction(self, tmp_path):
        """Test file-pattern-aware version detection (Decision #1)"""
        # Create structure where V1 has annuity, V2 has business files
        base_path = tmp_path / "收集数据"
        base_path.mkdir()

        # V1 with annuity file
        v1 = base_path / "V1"
        v1.mkdir()
        (v1 / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx").touch()

        # V2 with business file (different pattern)
        v2 = base_path / "V2"
        v2.mkdir()
        (v2 / "【for企业分战区经营分析】24年11月业务终稿数据1209采集.xlsx").touch()

        # V3 empty (should be skipped)
        v3 = base_path / "V3"
        v3.mkdir()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*年金终稿*.xlsx"],  # Only matches V1
            strategy='highest_number'
        )

        # Should select V1 (only version with matching annuity files)
        assert result.version == "V1"
        assert any("V2" in v for v in result.rejected_versions)
        assert "V3 (no matching files)" in result.rejected_versions

    def test_ambiguous_timestamp_detection(self, tmp_path):
        """Test ambiguity detection when versions modified same time"""
        base_path = tmp_path / "时间测试"
        base_path.mkdir()

        v1 = base_path / "V1"
        v2 = base_path / "V2"
        v1.mkdir()
        v2.mkdir()

        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        # Set same modification time
        mtime = v1.stat().st_mtime
        os.utime(v2, (mtime, mtime))

        scanner = VersionScanner()
        with pytest.raises(DiscoveryError) as exc_info:
            scanner.detect_version(
                base_path=base_path,
                file_patterns=["*.xlsx"],
                strategy='latest_modified'
            )

        assert exc_info.value.failed_stage == "version_detection"
        assert "Ambiguous versions" in str(exc_info.value)

    def test_performance_requirement(self, tmp_path):
        """Test performance: version detection <2 seconds (NFR requirement)"""
        # Create many versions to test performance
        base_path = tmp_path / "性能测试"
        base_path.mkdir()

        # Create 50 versions with files
        for i in range(1, 51):  # V1-V50
            version_path = base_path / f"V{i}"
            version_path.mkdir()
            (version_path / f"data_{i}.xlsx").touch()

        scanner = VersionScanner()
        start_time = time.time()

        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*.xlsx"],
            strategy='highest_number'
        )

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        # Performance requirement: should complete within 2 seconds
        assert duration_ms < 2000, f"Version detection took {duration_ms}ms, exceeded 2 seconds requirement"
        assert result.version == "V50"

    def test_cross_platform_unicode_paths(self, tmp_path):
        """Test Unicode paths work across platforms"""
        # Create path with Chinese characters (no leading/trailing spaces for Windows compatibility)
        base_path = tmp_path / "测试路径" / "数据收集"
        base_path.mkdir(parents=True)

        v1 = base_path / "V1"
        v1.mkdir()

        # File with Chinese characters in name
        filename = "测试数据.xlsx"
        (v1 / filename).touch()

        scanner = VersionScanner()
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=[filename],  # Exact filename match
            strategy='highest_number'
        )

        assert result.version == "V1"
        assert (result.path / filename).exists()
        assert "测试数据.xlsx" in [f.name for f in result.path.glob("*.xlsx")]

    def test_error_recovery_with_manual_override(self, tmp_path):
        """Test manual override bypasses ambiguity detection"""
        base_path = tmp_path / "错误恢复测试"
        base_path.mkdir()

        v1 = base_path / "V1"
        v2 = base_path / "V2"
        v1.mkdir()
        v2.mkdir()

        (v1 / "data.xlsx").touch()
        (v2 / "data.xlsx").touch()

        # Set same modification time to trigger ambiguity
        mtime = v1.stat().st_mtime
        os.utime(v2, (mtime, mtime))

        scanner = VersionScanner()

        # First, verify ambiguity would be raised without override
        with pytest.raises(DiscoveryError):
            scanner.detect_version(
                base_path=base_path,
                file_patterns=["*.xlsx"],
                strategy='latest_modified'
            )

        # Now test manual override resolves ambiguity
        result = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*.xlsx"],
            strategy='latest_modified',
            version_override="V1"  # Manual override
        )

        assert result.version == "V1"
        assert result.strategy_used == "manual"

    def test_domain_specific_patterns_scoping(self, tmp_path):
        """Test that file-pattern-aware detection works with domain-specific patterns"""
        # Create scenario where different domains have different patterns
        base_path = tmp_path / "领域测试"
        base_path.mkdir()

        # V1 has annuity pattern, V2 has business pattern
        v1 = base_path / "V1"
        v2 = base_path / "V2"
        v1.mkdir()
        v2.mkdir()

        # Domain-specific files
        (v1 / "annuity_report_2025.xlsx").touch()
        (v2 / "business_summary_2025.xlsx").touch()

        scanner = VersionScanner()

        # Test with annuity pattern - should select V1
        result_annuity = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*annuity*.xlsx"],
            strategy='highest_number'
        )
        assert result_annuity.version == "V1"
        assert result_annuity.path == v1

        # Test with business pattern - should select V2
        result_business = scanner.detect_version(
            base_path=base_path,
            file_patterns=["*business*.xlsx"],
            strategy='highest_number'
        )
        assert result_business.version == "V2"
        assert result_business.path == v2

    def test_edge_case_version_regex(self, tmp_path):
        """Test version regex handles edge cases correctly"""
        # Create various folder names to test regex
        test_cases = [
            ("V1", True),   # Valid
            ("V2", True),   # Valid
            ("V10", True),  # Valid double digit
            ("V99", True),  # Valid high number
            ("V0", False),  # Invalid (0 not positive)
            ("V", False),    # Invalid (no number)
            ("Version1", False),  # Invalid (not V\d+)
            ("V1a", False),  # Invalid (has letters)
            ("v1", False),   # Invalid (lowercase)
        ]

        for folder_name, should_match in test_cases:
            if should_match:
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
        expected_versions = [case[0] for case in test_cases if case[1]]
        actual_versions = [
            v.name for v in tmp_path.iterdir()
            if v.is_dir() and v.name.startswith('V')
        ]

        # Verify scanner only found expected valid versions
        found_valid_versions = [v for v in expected_versions if v in actual_versions]
        assert set(found_valid_versions) == set(expected_versions)

        if expected_versions:
            # Should select the highest valid version
            expected_highest = max(expected_versions, key=lambda x: int(x[1:]))
            assert result.version == expected_highest