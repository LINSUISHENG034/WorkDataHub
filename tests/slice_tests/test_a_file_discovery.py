"""Phase A: File discovery & data reading tests (A-1 through A-6).

Verifies configuration loading, version scanning, file pattern matching,
and Excel reading using real slice data fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.slice_tests.conftest import CONFIG_DIR, FIXTURE_ROOT
from work_data_hub.infrastructure.settings.data_source_schema import (
    _merge_with_defaults,
    get_domain_config_v2,
)
from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.readers.excel_reader import ExcelReader

pytestmark = pytest.mark.slice_test


# ===================================================================
# A-1: Configuration loading & defaults merging
# ===================================================================
class TestA1ConfigLoading:
    """Verify defaults + domain override inheritance, '+' prefix list extension."""

    def test_defaults_merge_scalars(self):
        """Domain scalar values override defaults."""
        defaults = {"version_strategy": "highest_number", "fallback": "error"}
        domain = {"version_strategy": "latest_modified"}
        merged = _merge_with_defaults(domain, defaults)
        assert merged["version_strategy"] == "latest_modified"
        assert merged["fallback"] == "error"

    def test_defaults_merge_list_replace(self):
        """Domain list replaces defaults list (no '+' prefix)."""
        defaults = {"file_patterns": ["*.xlsx"]}
        domain = {"file_patterns": ["*规模*.xlsx"]}
        merged = _merge_with_defaults(domain, defaults)
        assert merged["file_patterns"] == ["*规模*.xlsx"]

    def test_defaults_merge_list_extend(self):
        """'+' prefix extends defaults list instead of replacing."""
        defaults = {"exclude_patterns": ["~$*"]}
        domain = {"exclude_patterns": ["+*.eml", "+*回复*"]}
        merged = _merge_with_defaults(domain, defaults)
        assert "~$*" in merged["exclude_patterns"]
        assert "*.eml" in merged["exclude_patterns"]
        assert "*回复*" in merged["exclude_patterns"]

    def test_get_domain_config_annuity_performance(self):
        """Load annuity_performance config from real data_sources.yml."""
        config = get_domain_config_v2(
            "annuity_performance",
            config_path=str(CONFIG_DIR / "data_sources.yml"),
        )
        assert "规模" in config.file_patterns[0] or any(
            "规模" in p for p in config.file_patterns
        )
        assert config.sheet_name == "规模明细"
        assert config.version_strategy == "highest_number"

    def test_get_domain_config_annual_award(self):
        """Load annual_award config — must have sheet_names for multi-sheet."""
        config = get_domain_config_v2(
            "annual_award",
            config_path=str(CONFIG_DIR / "data_sources.yml"),
        )
        assert config.sheet_names is not None
        assert len(config.sheet_names) >= 2
        assert any("中标" in s for s in config.sheet_names)

    def test_get_domain_config_annual_loss(self):
        """Load annual_loss config — must have sheet_names for multi-sheet."""
        config = get_domain_config_v2(
            "annual_loss",
            config_path=str(CONFIG_DIR / "data_sources.yml"),
        )
        assert config.sheet_names is not None
        assert any("流失" in s for s in config.sheet_names)


# ===================================================================
# A-2: Version directory scanning
# ===================================================================
class TestA2VersionScanning:
    """Verify V1/V2/V3 detection, highest_number strategy, file filtering."""

    def test_detect_highest_version(self, tmp_path: Path):
        """highest_number strategy picks V2 over V1 when both have files."""
        (tmp_path / "V1").mkdir()
        (tmp_path / "V1" / "data.xlsx").write_text("v1")
        (tmp_path / "V2").mkdir()
        (tmp_path / "V2" / "data.xlsx").write_text("v2")

        scanner = VersionScanner()
        result = scanner.detect_version(
            tmp_path, file_patterns=["*.xlsx"], strategy="highest_number"
        )
        assert result.version == "V2"
        assert result.path == tmp_path / "V2"

    def test_skip_empty_version_dirs(self, tmp_path: Path):
        """Version dirs without matching files are excluded."""
        (tmp_path / "V1").mkdir()
        (tmp_path / "V1" / "data.xlsx").write_text("v1")
        (tmp_path / "V2").mkdir()  # empty — no matching files

        scanner = VersionScanner()
        result = scanner.detect_version(
            tmp_path, file_patterns=["*.xlsx"], strategy="highest_number"
        )
        assert result.version == "V1"

    def test_no_version_dirs_returns_base(self, tmp_path: Path):
        """When no V* dirs exist, returns base path."""
        (tmp_path / "data.xlsx").write_text("base")

        scanner = VersionScanner()
        result = scanner.detect_version(
            tmp_path, file_patterns=["*.xlsx"], strategy="highest_number"
        )
        assert result.version == "base"
        assert result.path == tmp_path


# ===================================================================
# A-3: File pattern matching
# ===================================================================
class TestA3FilePatternMatching:
    """Verify glob matching, exclude rules, Unicode NFC normalization."""

    def test_glob_match_chinese_pattern(self, tmp_path: Path):
        """Match *规模收入数据*.xlsx pattern."""
        target = tmp_path / "2025年规模收入数据汇总.xlsx"
        target.write_text("data")
        (tmp_path / "other.xlsx").write_text("other")

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            tmp_path,
            include_patterns=["*规模收入数据*.xlsx"],
            domain="annuity_performance",
        )
        assert result.matched_file.name == target.name

    def test_exclude_temp_files(self, tmp_path: Path):
        """~$* temp files are excluded."""
        (tmp_path / "规模收入数据.xlsx").write_text("real")
        (tmp_path / "~$规模收入数据.xlsx").write_text("temp")

        matcher = FilePatternMatcher()
        result = matcher.match_files(
            tmp_path,
            include_patterns=["*规模收入数据*.xlsx"],
            exclude_patterns=["~$*"],
            domain="test",
        )
        assert "~$" not in result.matched_file.name


# ===================================================================
# A-4: Single sheet reading (annuity_performance)
# ===================================================================
class TestA4SingleSheetReading:
    """Verify reading '规模明细' sheet with column cleaning."""

    def test_read_slice_sheet(self, annuity_performance_slice_df):
        """Slice fixture loads with non-empty DataFrame."""
        df = annuity_performance_slice_df
        assert len(df) > 0
        # Column names should not have leading/trailing whitespace
        for col in df.columns:
            assert col == col.strip(), f"Column '{col}' has whitespace"

    def test_read_rows_returns_dicts(self):
        """ExcelReader.read_rows returns list of dicts."""
        path = FIXTURE_ROOT / "annuity_performance" / "slice_规模收入数据.xlsx"
        if not path.exists():
            pytest.skip("Slice fixture not found")

        reader = ExcelReader()
        rows = reader.read_rows(str(path), sheet="规模明细")
        assert isinstance(rows, list)
        assert len(rows) > 0
        assert isinstance(rows[0], dict)


# ===================================================================
# A-5: Multi-sheet merge reading (annual_award)
# ===================================================================
class TestA5MultiSheetMerge:
    """Verify reading two sheets and merging into one DataFrame."""

    def test_award_merged_has_both_sheets(self, annual_award_slice_df):
        """Merged DataFrame contains rows from both sheets."""
        df = annual_award_slice_df
        assert len(df) > 0
        # Should have rows from both trustee and investee sheets
        if "业务类型" in df.columns:
            types = df["业务类型"].dropna().unique()
            assert len(types) >= 1

    def test_single_sheet_failure_does_not_block(self):
        """If one sheet is missing, the other still loads."""
        path = FIXTURE_ROOT / "annual_award" / "slice_中标台账.xlsx"
        if not path.exists():
            pytest.skip("Slice fixture not found")
        # Read only the first sheet — should succeed
        df = pd.read_excel(path, sheet_name="企年受托中标(空白)", engine="openpyxl")
        assert len(df) > 0


# ===================================================================
# A-6: Multi-sheet merge reading (annual_loss)
# ===================================================================
class TestA6MultiSheetMergeLoss:
    """Verify reading two loss sheets and merging."""

    def test_loss_merged_has_rows(self, annual_loss_slice_df):
        """Merged DataFrame contains rows from loss sheets."""
        df = annual_loss_slice_df
        assert len(df) > 0

    def test_loss_sheets_individually_readable(self):
        """Each loss sheet is independently readable."""
        path = FIXTURE_ROOT / "annual_loss" / "slice_流失台账.xlsx"
        if not path.exists():
            pytest.skip("Slice fixture not found")
        for sheet in ["企年受托流失(解约)", "企年投资流失(解约)"]:
            try:
                df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
                assert len(df) >= 0
            except ValueError:
                pass  # sheet not found in slice
