import pandas as pd
import pytest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from work_data_hub.io.connectors.file_connector import (
    DataDiscoveryResult,
    FileDiscoveryService,
)
from work_data_hub.io.connectors.exceptions import DiscoveryError
from work_data_hub.io.connectors.file_pattern_matcher import FileMatchResult
from work_data_hub.io.connectors.version_scanner import VersionedPath
from work_data_hub.io.readers.excel_reader import ExcelReadResult, ExcelReader
from src.work_data_hub.infrastructure.settings.data_source_schema import DataSourceConfigV2, DomainConfigV2


class DummyScanner:
    def __init__(self):
        self.calls = []

    def detect_version(self, base_path, file_patterns, strategy, version_override=None):
        self.calls.append(
            {
                "base_path": base_path,
                "file_patterns": file_patterns,
                "strategy": strategy,
                "version_override": version_override,
            }
        )
        return VersionedPath(
            path=Path(base_path) / "V1",
            version="V1",
            strategy_used=strategy,
            selected_at=datetime.now(),
            rejected_versions=[],
        )


class DummyMatcher:
    def __init__(self, raise_error: Exception | None = None):
        self.raise_error = raise_error
        self.calls = []

    def match_files(self, search_path, include_patterns, exclude_patterns):
        self.calls.append(
            {
                "search_path": search_path,
                "include_patterns": include_patterns,
                "exclude_patterns": exclude_patterns,
            }
        )
        if self.raise_error:
            raise self.raise_error
        return FileMatchResult(
            matched_file=Path("/tmp/reference/monthly/202501/收集数据/数据采集/V1/file.xlsx"),
            patterns_used=include_patterns,
            exclude_patterns=exclude_patterns,
            candidates_found=[],
            excluded_files=[],
            match_count=1,
            selected_at=datetime.now(),
        )


class DummyReader:
    def __init__(self):
        self.calls = []

    def read_sheet(self, file_path, sheet_name, normalize_columns=True):
        self.calls.append(
            {
                "file_path": file_path,
                "sheet_name": sheet_name,
                "normalize_columns": normalize_columns,
            }
        )
        df = pd.DataFrame({"a": [1, 2]})
        return ExcelReadResult(
            df=df,
            sheet_name=sheet_name,
            row_count=len(df),
            column_count=len(df.columns),
            columns_renamed={},
            normalization_duration_ms=0,
            duration_breakdown={"read_ms": 1},
            file_path=Path(file_path),
            read_at=datetime.now(),
        )


def _fake_settings(domain_config: DomainConfigV2):
    return SimpleNamespace(
        data_sources=DataSourceConfigV2(
            schema_version="1.0",
            domains={"annuity_performance": domain_config},
        )
    )


def test_template_variable_resolution_and_call_order():
    domain_cfg = DomainConfigV2(
        base_path="reference/monthly/{YYYYMM}/收集数据/数据采集",
        file_patterns=["*终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    scanner = DummyScanner()
    matcher = DummyMatcher()
    reader = DummyReader()
    service = FileDiscoveryService(
        settings=_fake_settings(domain_cfg),
        version_scanner=scanner,
        file_matcher=matcher,
        excel_reader=reader,
    )

    result = service.discover_and_load(
        domain="annuity_performance",
        month="202501",
    )

    assert isinstance(result, DataDiscoveryResult)
    assert result.version == "V1"
    assert scanner.calls[0]["base_path"] == Path("reference/monthly/202501/收集数据/数据采集")
    assert matcher.calls[0]["search_path"] == scanner.calls[0]["base_path"] / "V1"
    assert reader.calls[0]["sheet_name"] == "规模明细"
    assert result.row_count == 2
    assert result.column_count == 1
    assert result.stage_durations["version_detection"] >= 0
    assert result.duration_ms >= sum(result.stage_durations.values())


def test_file_matching_failure_wrapped_with_stage():
    domain_cfg = DomainConfigV2(
        base_path="reference/monthly/{YYYYMM}/收集数据/数据采集",
        file_patterns=["*终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    scanner = DummyScanner()
    matcher = DummyMatcher(raise_error=FileNotFoundError("no file"))
    reader = DummyReader()
    service = FileDiscoveryService(
        settings=_fake_settings(domain_cfg),
        version_scanner=scanner,
        file_matcher=matcher,
        excel_reader=reader,
    )

    with pytest.raises(DiscoveryError) as exc:
        service.discover_and_load(domain="annuity_performance", month="202501")

    assert exc.value.failed_stage == "file_matching"
    assert "no file" in str(exc.value)


def test_missing_template_variable_raises_config_validation():
    domain_cfg = DomainConfigV2(
        base_path="reference/monthly/{YYYYMM}/收集数据/数据采集",
        file_patterns=["*终稿*.xlsx"],
        exclude_patterns=["~$*"],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    scanner = DummyScanner()
    matcher = DummyMatcher()
    reader = DummyReader()
    service = FileDiscoveryService(
        settings=_fake_settings(domain_cfg),
        version_scanner=scanner,
        file_matcher=matcher,
        excel_reader=reader,
    )

    with pytest.raises(DiscoveryError) as exc:
        service.discover_and_load(domain="annuity_performance")

    assert exc.value.failed_stage == "config_validation"
    assert "Template variable" in str(exc.value)


def test_multi_domain_independence_and_failure_isolated(tmp_path):
    # Domain A succeeds
    base_a = tmp_path / "reference" / "A" / "V1"
    base_a.mkdir(parents=True)
    excel_a = base_a / "fileA.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(excel_a, sheet_name="规模明细", index=False)

    # Domain B path will cause matcher to fail by design
    base_b = tmp_path / "reference" / "B"

    domain_cfg_a = DomainConfigV2(
        base_path=str(tmp_path / "reference" / "A"),
        file_patterns=["*A*.xlsx"],
        exclude_patterns=[],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    domain_cfg_b = DomainConfigV2(
        base_path=str(base_b),
        file_patterns=["*B*.xlsx"],
        exclude_patterns=[],
        sheet_name="规模明细",
        version_strategy="highest_number",
        fallback="error",
    )
    settings = SimpleNamespace(
        data_sources=DataSourceConfigV2(
            schema_version="1.0",
            domains={
                "domain_a": domain_cfg_a,
                "domain_b": domain_cfg_b,
            },
        )
    )

    class SelectorMatcher:
        def match_files(self, search_path, include_patterns, exclude_patterns):
            if "B" in str(search_path):
                raise FileNotFoundError("no domain B files")
            return FileMatchResult(
                matched_file=excel_a,
                patterns_used=include_patterns,
                exclude_patterns=exclude_patterns,
                candidates_found=[excel_a],
                excluded_files=[],
                match_count=1,
                selected_at=datetime.now(),
            )

    service = FileDiscoveryService(
        settings=settings,
        version_scanner=DummyScanner(),
        file_matcher=SelectorMatcher(),
        excel_reader=ExcelReader(),
    )

    # Domain A succeeds
    result_a = service.discover_and_load(domain="domain_a")
    assert result_a.file_path == excel_a

    # Domain B fails but should not affect Domain A run
    with pytest.raises(DiscoveryError) as exc:
        service.discover_and_load(domain="domain_b")
    assert exc.value.failed_stage == "file_matching"

    # Domain A still succeeds after B failure (state isolation)
    result_a_again = service.discover_and_load(domain="domain_a")
    assert result_a_again.file_path == excel_a


# =============================================================================
# Security Tests - Path Traversal Prevention (Code Review Critical Issue #2)
# =============================================================================


class TestPathTraversalSecurity:
    """Test suite for path traversal attack prevention.

    Note: DomainConfigV2 Pydantic model already validates path traversal at schema level.
    These tests verify both schema-level and runtime-level security.
    """

    def _make_service(self, base_path: str):
        """Helper to create service with given base_path."""
        domain_cfg = DomainConfigV2(
            base_path=base_path,
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        return FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

    def test_path_traversal_with_double_dots_rejected_at_schema_level(self):
        """Test that '../' in path template is rejected by Pydantic schema."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError) as exc:
            DomainConfigV2(
                base_path="reference/../../../etc/passwd",
                file_patterns=["*.xlsx"],
                exclude_patterns=[],
                sheet_name="规模明细",
                version_strategy="highest_number",
                fallback="error",
            )

        assert "directory traversal" in str(exc.value).lower()

    def test_path_traversal_with_template_variable_injection(self):
        """Test that path traversal via template variable is rejected at runtime."""
        service = self._make_service("reference/monthly/{YYYYMM}/data")

        with pytest.raises(DiscoveryError) as exc:
            # Attempt to inject traversal via month parameter (non-numeric)
            service.discover_and_load(domain="annuity_performance", month="../../..")

        # Should fail at config_validation due to invalid YYYYMM format
        assert exc.value.failed_stage == "config_validation"

    def test_path_traversal_backslash_rejected_at_schema_level(self):
        """Test that backslash traversal is also detected by Pydantic schema."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError) as exc:
            DomainConfigV2(
                base_path="reference\\..\\..\\etc\\passwd",
                file_patterns=["*.xlsx"],
                exclude_patterns=[],
                sheet_name="规模明细",
                version_strategy="highest_number",
                fallback="error",
            )

        assert "directory traversal" in str(exc.value).lower()

    def test_null_byte_injection_rejected_at_runtime(self):
        """Test that null byte injection is rejected at runtime.

        Note: Null bytes pass Pydantic validation but are caught by
        _validate_path_security at runtime.
        """
        service = self._make_service("reference/data\x00.xlsx")

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance")

        # Null byte is caught at runtime, stage depends on where it's detected
        assert "null byte" in str(exc.value).lower()

    def test_valid_path_without_traversal_accepted(self):
        """Test that valid paths without traversal are accepted."""
        service = self._make_service("reference/monthly/{YYYYMM}/收集数据")

        # Should not raise - path is valid
        result = service.discover_and_load(domain="annuity_performance", month="202501")
        assert result is not None
        assert result.version == "V1"


# =============================================================================
# Template Variable Resolution Tests
# =============================================================================


class TestTemplateVariableResolution:
    """Test suite for template variable resolution edge cases."""

    def test_yyyymm_format_validation_non_numeric(self):
        """Test that non-numeric YYYYMM is rejected."""
        domain_cfg = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", month="2025AB")

        assert exc.value.failed_stage == "config_validation"
        assert "6 digits" in str(exc.value)

    def test_yyyymm_format_validation_wrong_length(self):
        """Test that wrong length YYYYMM is rejected."""
        domain_cfg = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", month="20251")

        assert exc.value.failed_stage == "config_validation"

    def test_invalid_month_value_rejected(self):
        """Test that invalid month (13, 00) is rejected."""
        domain_cfg = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance", month="202513")

        assert exc.value.failed_stage == "config_validation"
        assert "01 and 12" in str(exc.value)

    def test_path_without_template_variables_passes_through(self):
        """Test that paths without template variables work correctly."""
        domain_cfg = DomainConfigV2(
            base_path="reference/static/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        # Should work without month parameter
        result = service.discover_and_load(domain="annuity_performance")
        assert result is not None

    def test_unresolved_template_variable_rejected(self):
        """Test that unresolved template variables are rejected.

        Note: DomainConfigV2 only allows {YYYYMM}, {YYYY}, {MM} placeholders.
        Custom variables like {CUSTOM_VAR} are rejected at schema level.
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError) as exc:
            DomainConfigV2(
                base_path="reference/{CUSTOM_VAR}/data",
                file_patterns=["*.xlsx"],
                exclude_patterns=[],
                sheet_name="规模明细",
                version_strategy="highest_number",
                fallback="error",
            )

        # Schema validates only allowed placeholders
        assert "placeholder" in str(exc.value).lower() or "custom_var" in str(exc.value).lower()


# =============================================================================
# Domain Configuration Tests
# =============================================================================


class TestDomainConfiguration:
    """Test suite for domain configuration handling."""

    def test_unknown_domain_raises_config_validation_error(self):
        """Test that unknown domain raises appropriate error."""
        domain_cfg = DomainConfigV2(
            base_path="reference/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="unknown_domain")

        assert exc.value.failed_stage == "config_validation"
        assert "not found" in str(exc.value).lower()

    def test_missing_data_sources_config_raises_error(self):
        """Test that missing data_sources config raises appropriate error."""
        settings = SimpleNamespace()  # No data_sources attribute
        service = FileDiscoveryService(
            settings=settings,
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="any_domain")

        assert exc.value.failed_stage == "config_validation"


# =============================================================================
# Version Detection Fallback Tests
# =============================================================================


class TestVersionDetectionFallback:
    """Test suite for version detection fallback behavior."""

    def test_fallback_to_latest_modified_on_version_error(self):
        """Test that fallback strategy is used when version detection fails."""

        class FailingThenSucceedingScanner:
            def __init__(self):
                self.call_count = 0

            def detect_version(self, base_path, file_patterns, strategy, version_override=None):
                self.call_count += 1
                if strategy == "highest_number":
                    raise DiscoveryError(
                        domain="test",
                        failed_stage="version_detection",
                        original_error=ValueError("Ambiguous versions"),
                        message="Ambiguous versions",
                    )
                # Fallback strategy succeeds
                return VersionedPath(
                    path=Path(base_path) / "V1",
                    version="V1",
                    strategy_used="latest_modified",
                    selected_at=datetime.now(),
                    rejected_versions=[],
                )

        domain_cfg = DomainConfigV2(
            base_path="reference/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="use_latest_modified",  # Enable fallback
        )
        scanner = FailingThenSucceedingScanner()
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=scanner,
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        result = service.discover_and_load(domain="annuity_performance")

        assert result is not None
        assert scanner.call_count == 2  # First attempt + fallback

    def test_no_fallback_when_fallback_is_error(self):
        """Test that no fallback occurs when fallback='error'."""

        class AlwaysFailingScanner:
            def detect_version(self, base_path, file_patterns, strategy, version_override=None):
                raise DiscoveryError(
                    domain="test",
                    failed_stage="version_detection",
                    original_error=ValueError("No versions found"),
                    message="No versions found",
                )

        domain_cfg = DomainConfigV2(
            base_path="reference/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",  # No fallback
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=AlwaysFailingScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance")

        assert exc.value.failed_stage == "version_detection"


# =============================================================================
# Error Stage Identification Tests
# =============================================================================


class TestErrorStageIdentification:
    """Test suite for error stage identification logic."""

    def test_excel_error_identified_correctly(self):
        """Test that Excel-related errors are identified as excel_reading stage."""

        class FailingReader:
            def read_sheet(self, file_path, sheet_name, normalize_columns=True):
                raise ValueError("Excel file corrupted")

        domain_cfg = DomainConfigV2(
            base_path="reference/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=DummyScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=FailingReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance")

        # The error message contains "excel" so it should be identified as excel_reading
        assert exc.value.failed_stage == "excel_reading"

    def test_version_error_identified_correctly(self):
        """Test that version-related errors are identified correctly."""

        class VersionFailingScanner:
            def detect_version(self, base_path, file_patterns, strategy, version_override=None):
                raise ValueError("version conflict detected")

        domain_cfg = DomainConfigV2(
            base_path="reference/data",
            file_patterns=["*.xlsx"],
            exclude_patterns=[],
            sheet_name="规模明细",
            version_strategy="highest_number",
            fallback="error",
        )
        service = FileDiscoveryService(
            settings=_fake_settings(domain_cfg),
            version_scanner=VersionFailingScanner(),
            file_matcher=DummyMatcher(),
            excel_reader=DummyReader(),
        )

        with pytest.raises(DiscoveryError) as exc:
            service.discover_and_load(domain="annuity_performance")

        assert exc.value.failed_stage == "version_detection"


# =============================================================================
# DiscoveryError Tests
# =============================================================================


class TestDiscoveryError:
    """Test suite for DiscoveryError exception class."""

    def test_to_dict_returns_complete_structure(self):
        """Test that to_dict returns all required fields."""
        original = ValueError("Original error message")
        error = DiscoveryError(
            domain="test_domain",
            failed_stage="file_matching",
            original_error=original,
            message="Test error message",
        )

        result = error.to_dict()

        assert result["error_type"] == "DiscoveryError"
        assert result["domain"] == "test_domain"
        assert result["failed_stage"] == "file_matching"
        assert "test_domain" in result["message"]
        assert result["original_error_type"] == "ValueError"
        assert result["original_error_message"] == "Original error message"

    def test_str_representation(self):
        """Test string representation of DiscoveryError."""
        error = DiscoveryError(
            domain="annuity",
            failed_stage="excel_reading",
            original_error=IOError("File not found"),
            message="Cannot read Excel file",
        )

        str_repr = str(error)

        assert "annuity" in str_repr
        assert "excel_reading" in str_repr
        assert "Cannot read Excel file" in str_repr


# =============================================================================
# DataDiscoveryResult Tests
# =============================================================================


class TestDataDiscoveryResult:
    """Test suite for DataDiscoveryResult dataclass."""

    def test_result_contains_all_required_fields(self):
        """Test that DataDiscoveryResult has all required fields."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = DataDiscoveryResult(
            df=df,
            file_path=Path("/test/file.xlsx"),
            version="V2",
            sheet_name="Sheet1",
            row_count=3,
            column_count=1,
            duration_ms=150,
            columns_renamed={"old": "new"},
            stage_durations={"version_detection": 50, "file_matching": 30, "excel_reading": 70},
        )

        assert result.df is df
        assert result.file_path == Path("/test/file.xlsx")
        assert result.version == "V2"
        assert result.sheet_name == "Sheet1"
        assert result.row_count == 3
        assert result.column_count == 1
        assert result.duration_ms == 150
        assert result.columns_renamed == {"old": "new"}
        assert result.stage_durations["version_detection"] == 50
