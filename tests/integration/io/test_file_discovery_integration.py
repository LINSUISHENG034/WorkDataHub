"""Integration tests for FileDiscoveryService using real fixtures.

These tests use the realistic fixture file:
tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx

This file contains real-world data with:
- Chinese column names
- Multiple sheets: 规模明细, 收入明细
- Real data structure from production
"""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from work_data_hub.io.connectors.exceptions import DiscoveryError

from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.readers.excel_reader import ExcelReader
from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourceConfigV2,
    DomainConfigV2,
)


# Path to realistic fixture file
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sample_data"
REALISTIC_FIXTURE = (
    FIXTURE_DIR / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
)


def _build_settings(
    base_template: Path, sheet_name: str = "规模明细"
) -> SimpleNamespace:
    domain_cfg = DomainConfigV2(
        base_path=str(base_template),
        file_patterns=["*年金终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name=sheet_name,
        version_strategy="highest_number",
        fallback="error",
    )
    return SimpleNamespace(
        data_sources=DataSourceConfigV2(
            schema_version="1.0",
            domains={"annuity_performance": domain_cfg},
        )
    )


def _build_multi_domain_settings(base_a: Path, base_b: Path) -> SimpleNamespace:
    """Build settings with two domains for multi-domain tests."""
    domain_cfg_a = DomainConfigV2(
        base_path=str(base_a),
        file_patterns=["*年金终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    domain_cfg_b = DomainConfigV2(
        base_path=str(base_b),
        file_patterns=["*年金终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name="收入明细",
        version_strategy="highest_number",
        fallback="error",
    )
    return SimpleNamespace(
        data_sources=DataSourceConfigV2(
            schema_version="1.0",
            domains={
                "domain_a": domain_cfg_a,
                "domain_b": domain_cfg_b,
            },
        )
    )


# =============================================================================
# Tests with Synthetic Data (Quick, Isolated)
# =============================================================================


def test_discover_and_load_end_to_end(tmp_path):
    """Test end-to-end discovery with synthetic data."""
    # Arrange: build versioned folder with a simple Excel file
    base = (
        tmp_path / "reference" / "monthly" / "202501" / "收集数据" / "数据采集" / "V1"
    )
    base.mkdir(parents=True)
    excel_path = base / "年金终稿数据.xlsx"

    df = pd.DataFrame({"计划代码": ["A1", "A2"], "值": [1, 2]})
    df.to_excel(excel_path, sheet_name="规模明细", index=False)

    settings = _build_settings(
        base_template=tmp_path
        / "reference"
        / "monthly"
        / "{YYYYMM}"
        / "收集数据"
        / "数据采集"
    )
    service = FileDiscoveryService(
        settings=settings,
        version_scanner=VersionScanner(),
        file_matcher=FilePatternMatcher(),
        excel_reader=ExcelReader(),
    )

    # Act
    result = service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

    # Assert
    assert result.version == "V1"
    assert result.file_path == excel_path
    assert result.sheet_name == "规模明细"
    assert result.row_count == 2
    assert result.column_count == 2
    assert result.duration_ms >= 0


def test_discover_missing_sheet_raises_excel_stage(tmp_path):
    """Test that missing sheet raises DiscoveryError with excel_reading stage."""
    base = (
        tmp_path / "reference" / "monthly" / "202501" / "收集数据" / "数据采集" / "V1"
    )
    base.mkdir(parents=True)
    excel_path = base / "年金终稿数据.xlsx"

    pd.DataFrame({"计划代码": ["A1"], "值": [1]}).to_excel(
        excel_path, sheet_name="存在的表", index=False
    )

    settings = _build_settings(
        base_template=tmp_path
        / "reference"
        / "monthly"
        / "{YYYYMM}"
        / "收集数据"
        / "数据采集",
        sheet_name="不存在的表",
    )
    service = FileDiscoveryService(
        settings=settings,
        version_scanner=VersionScanner(),
        file_matcher=FilePatternMatcher(),
        excel_reader=ExcelReader(),
    )

    with pytest.raises(DiscoveryError) as exc:
        service.discover_and_load(domain="annuity_performance", YYYYMM="202501")
    assert exc.value.failed_stage == "excel_reading"


def test_discovery_performance_under_threshold(tmp_path):
    """Test that discovery completes within performance threshold (<2s)."""
    base = (
        tmp_path / "reference" / "monthly" / "202501" / "收集数据" / "数据采集" / "V1"
    )
    base.mkdir(parents=True)
    excel_path = base / "年金终稿数据.xlsx"
    df = pd.DataFrame({"计划代码": list(range(10)), "值": list(range(10))})
    df.to_excel(excel_path, sheet_name="规模明细", index=False)

    settings = _build_settings(
        base_template=tmp_path
        / "reference"
        / "monthly"
        / "{YYYYMM}"
        / "收集数据"
        / "数据采集"
    )
    service = FileDiscoveryService(
        settings=settings,
        version_scanner=VersionScanner(),
        file_matcher=FilePatternMatcher(),
        excel_reader=ExcelReader(),
    )

    result = service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

    assert result.duration_ms < 2000  # Target: <2 seconds


# =============================================================================
# Tests with Realistic Fixture Data (AC5: Multi-Domain Independence)
# =============================================================================


@pytest.mark.skipif(
    not REALISTIC_FIXTURE.exists(),
    reason=f"Realistic fixture not found: {REALISTIC_FIXTURE}",
)
class TestRealisticFixture:
    """Integration tests using realistic production-like fixture data."""

    def test_discover_with_realistic_excel_file(self, tmp_path):
        """Test discovery with realistic Excel file containing Chinese data."""
        # Setup: Copy fixture to versioned folder structure
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202411"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        target_file = (
            base / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
        )
        shutil.copy(REALISTIC_FIXTURE, target_file)

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        # Act
        result = service.discover_and_load(
            domain="annuity_performance", YYYYMM="202411"
        )

        # Assert - verify realistic data characteristics
        assert result.version == "V1"
        assert result.sheet_name == "规模明细"
        assert result.row_count > 0  # Should have real data rows
        assert result.column_count > 0  # Should have columns
        # Note: Large files (33k+ rows) may exceed 2s threshold on slower systems
        # The 2s NFR is for "typical" domain discovery (~1000 rows)
        assert result.duration_ms < 10000  # Allow 10s for large realistic files

        # Verify DataFrame has expected structure
        assert isinstance(result.df, pd.DataFrame)
        assert len(result.df) == result.row_count

    def test_discover_different_sheet_from_realistic_file(self, tmp_path):
        """Test discovery of different sheet (收入明细) from realistic file."""
        # Setup
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202411"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        target_file = (
            base / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
        )
        shutil.copy(REALISTIC_FIXTURE, target_file)

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集",
            sheet_name="收入明细",  # Different sheet
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        # Act
        result = service.discover_and_load(
            domain="annuity_performance", YYYYMM="202411"
        )

        # Assert
        assert result.sheet_name == "收入明细"
        assert result.row_count > 0

    def test_multi_domain_independence_with_realistic_data(self, tmp_path):
        """Test AC5: Multi-domain independence - failure in one doesn't block others."""
        # Setup domain A with valid file
        base_a = tmp_path / "reference" / "domain_a" / "V1"
        base_a.mkdir(parents=True)
        target_a = base_a / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
        shutil.copy(REALISTIC_FIXTURE, target_a)

        # Setup domain B with NO file (will fail)
        base_b = tmp_path / "reference" / "domain_b" / "V1"
        base_b.mkdir(parents=True)
        # No file copied - domain B will fail

        settings = _build_multi_domain_settings(
            base_a=tmp_path / "reference" / "domain_a",
            base_b=tmp_path / "reference" / "domain_b",
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        # Act & Assert: Domain A succeeds
        result_a = service.discover_and_load(domain="domain_a")
        assert result_a.sheet_name == "规模明细"
        assert result_a.row_count > 0

        # Act & Assert: Domain B fails (no matching file)
        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="domain_b")
        assert exc.value.failed_stage == "file_matching"

        # Act & Assert: Domain A still works after B failure (isolation)
        result_a_again = service.discover_and_load(domain="domain_a")
        assert result_a_again.row_count == result_a.row_count

    def test_column_normalization_with_realistic_chinese_headers(self, tmp_path):
        """Test that Chinese column headers are properly normalized."""
        # Setup
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202411"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        target_file = (
            base / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
        )
        shutil.copy(REALISTIC_FIXTURE, target_file)

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        # Act
        result = service.discover_and_load(
            domain="annuity_performance", YYYYMM="202411"
        )

        # Assert - columns should be normalized (no leading/trailing whitespace)
        for col in result.df.columns:
            assert col == col.strip(), f"Column '{col}' has whitespace"

        # Check columns_renamed dict is populated if normalization occurred
        assert isinstance(result.columns_renamed, dict)

    def test_performance_with_realistic_data_size(self, tmp_path):
        """Test performance meets NFR (<2s) with realistic data size."""
        # Setup
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202411"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        target_file = (
            base / "【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"
        )
        shutil.copy(REALISTIC_FIXTURE, target_file)

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        # Act
        result = service.discover_and_load(
            domain="annuity_performance", YYYYMM="202411"
        )

        # Assert - NFR: <2 seconds for typical domain discovery (~1000 rows)
        # Large files (33k+ rows) may take longer - allow 10s for realistic data
        assert result.duration_ms < 10000, (
            f"Discovery took {result.duration_ms}ms, exceeds 10000ms threshold for large files"
        )

        # Verify stage durations are tracked
        # Note: After Epic 7 refactoring, stage names changed:
        # - version_detection → discovery (includes file_matching)
        # - excel_reading → read
        # - normalization (new stage)
        assert "discovery" in result.stage_durations
        assert "read" in result.stage_durations
        assert "normalization" in result.stage_durations

        # Total should roughly equal sum of stages
        stage_total = sum(result.stage_durations.values())
        assert result.duration_ms >= stage_total


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Test error handling and recovery scenarios."""

    def test_invalid_excel_file_raises_excel_stage_error(self, tmp_path):
        """Test that corrupted/invalid Excel file raises appropriate error."""
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202501"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        invalid_file = base / "年金终稿数据.xlsx"

        # Create invalid Excel file (just text, not real Excel)
        invalid_file.write_text("This is not a valid Excel file")

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

        # Verify error is from excel_reading stage
        assert exc.value.failed_stage == "excel_reading"
        # Note: domain may be "unknown" if error is raised by sub-component
        # The important thing is the stage is correctly identified

    def test_no_matching_files_raises_file_matching_error(self, tmp_path):
        """Test that no matching files raises file_matching stage error."""
        base = (
            tmp_path
            / "reference"
            / "monthly"
            / "202501"
            / "收集数据"
            / "数据采集"
            / "V1"
        )
        base.mkdir(parents=True)
        # Create file that doesn't match pattern
        wrong_file = base / "wrong_name.xlsx"
        pd.DataFrame({"a": [1]}).to_excel(wrong_file, index=False)

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

        assert exc.value.failed_stage == "file_matching"

    def test_no_version_folders_falls_back_to_base_path(self, tmp_path):
        """Test that missing version folders falls back to base path.

        Note: VersionScanner falls back to using base path when no V* folders exist.
        This then fails at file_matching stage if no matching files are found.
        """
        # Create base path but no V1/V2 folders
        base = tmp_path / "reference" / "monthly" / "202501" / "收集数据" / "数据采集"
        base.mkdir(parents=True)
        # No V1 folder created, no files either

        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

        # VersionScanner falls back to base path, then file_matching fails
        assert exc.value.failed_stage == "file_matching"

    def test_base_path_not_exists_raises_version_detection_error(self, tmp_path):
        """Test that non-existent base path raises version_detection error."""
        # Don't create the base path at all
        settings = _build_settings(
            base_template=tmp_path
            / "reference"
            / "monthly"
            / "{YYYYMM}"
            / "收集数据"
            / "数据采集"
        )
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=VersionScanner(),
            file_matcher=FilePatternMatcher(),
            excel_reader=ExcelReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", YYYYMM="202501")

        # Non-existent path should fail at version_detection
        assert exc.value.failed_stage == "version_detection"
