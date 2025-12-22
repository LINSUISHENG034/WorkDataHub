"""
FileDiscoveryService implementation for Epic 3 schema usage.
"""

import time
from pathlib import Path
from typing import Any, Optional

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourceConfigV2,
    DataSourcesValidationError,
    DomainConfigV2,
    get_domain_config_v2,
)
from work_data_hub.io.connectors.exceptions import DiscoveryError, DiscoveryStage
from work_data_hub.io.connectors.file_pattern_matcher import (
    FilePatternMatcher,
    SelectionStrategy,
)
from work_data_hub.io.connectors.version_scanner import VersionedPath, VersionScanner
from work_data_hub.io.readers.excel_reader import ExcelReader
from work_data_hub.utils.logging import get_logger

from .models import DataDiscoveryResult, DiscoveryMatch


class FileDiscoveryService:
    """
    Unified file discovery service orchestrating:
    - Template variable resolution
    - Version detection (Story 3.1)
    - File pattern matching (Story 3.2)
    - Excel reading (Story 3.3)
    - Column normalization (Story 3.4)
    """

    def __init__(
        self,
        settings: Optional[Any] = None,
        version_scanner: Optional[VersionScanner] = None,
        file_matcher: Optional[FilePatternMatcher] = None,
        excel_reader: Optional[ExcelReader] = None,
    ):
        self.settings = settings or get_settings()
        self.version_scanner = version_scanner or VersionScanner()
        self.file_matcher = file_matcher or FilePatternMatcher()
        self.excel_reader = excel_reader or ExcelReader()
        self.logger = get_logger(__name__)

    def discover_file(
        self,
        domain: str,
        version_override: Optional[str] = None,
        selection_strategy: Optional[Any] = None,
        **template_vars: Any,
    ) -> DiscoveryMatch:
        """
        Discover file for a domain without loading Excel data.
        """
        self.logger.info(
            "discovery.started", domain=domain, template_vars=template_vars
        )

        try:
            domain_config = self._load_domain_config(domain)
            base_path = self._resolve_template_vars(
                domain_config.base_path, template_vars
            )

            # Stage 1: Version detection
            version_result = self._detect_version_with_fallback(
                base_path, domain_config, version_override
            )
            self.logger.info(
                "discovery.version_detected",
                version=version_result.version,
                path=str(version_result.path),
                strategy=version_result.strategy_used,
            )

            # Stage 2: File matching
            strategy = (
                SelectionStrategy.ERROR
                if selection_strategy is None
                else selection_strategy
            )
            match_result = self.file_matcher.match_files(
                search_path=version_result.path,
                include_patterns=list(domain_config.file_patterns),
                exclude_patterns=list(domain_config.exclude_patterns or []),
                selection_strategy=strategy,
            )
            self.logger.info(
                "discovery.file_matched",
                file_path=str(match_result.matched_file),
                match_count=match_result.match_count,
            )

            result = DiscoveryMatch(
                file_path=match_result.matched_file,
                version=version_result.version,
                sheet_name=domain_config.sheet_name,
                resolved_base_path=base_path,
            )

            self.logger.info(
                "discovery.completed",
                domain=domain,
                file_path=str(result.file_path),
                version=result.version,
                sheet_name=result.sheet_name,
            )

            return result

        except DiscoveryError as exc:
            self.logger.error("discovery.failed", **exc.to_dict())
            raise
        except Exception as exc:  # pragma: no cover - defensive
            stage = self._identify_failed_stage(exc)
            wrapped = DiscoveryError(
                domain=domain,
                failed_stage=stage,
                original_error=exc,
                message=str(exc),
            )
            self.logger.error("discovery.failed", **wrapped.to_dict())
            raise wrapped

    def discover_and_load(
        self,
        domain: str,
        version_override: Optional[str] = None,
        selection_strategy: Optional[Any] = None,
        **template_vars: Any,
    ) -> DataDiscoveryResult:
        """
        Discover and load data file for a domain.
        """
        start_time = time.time()
        stage_durations = {}

        try:
            # Reuses discover_file for first steps (template, version, matcher)
            # but needs careful error handling to wrap intermediate steps if discovery fails
            discovery = self.discover_file(
                domain, version_override, selection_strategy, **template_vars
            )
            stage_durations["discovery"] = int((time.time() - start_time) * 1000)

            # Look up domain config again (could optimize to pass it through, but
            # discovery returns partial object)
            domain_config = self._load_domain_config(domain)

            # Stage 3: Excel Loading
            read_start = time.time()
            read_result = self.excel_reader.read_sheet(
                file_path=discovery.file_path,
                sheet_name=discovery.sheet_name,
            )
            df = read_result.df
            stage_durations["read"] = int((time.time() - read_start) * 1000)
            self.logger.info(
                "discovery.read_completed",
                rows=len(df),
                columns=len(df.columns),
            )

            # Stage 4: Normalization (renaming columns)
            norm_start = time.time()
            renamed_columns = {}
            columns_config = getattr(domain_config, "columns", None)
            if columns_config:
                # Apply column mapping (file_col -> domain_col)
                # Map is configured as: domain_field: file_header_name
                # We want to rename file_header_name -> domain_field
                mapping = {}
                for field_name, header_name in columns_config.items():
                    mapping[header_name] = field_name

                # Check for missing required columns
                missing_cols = [
                    header for header in mapping.keys() if header not in df.columns
                ]
                if missing_cols:
                    # In future strict mode this might error; currently we just warn or fail
                    # depending on reader restrictiveness. Reader already handled raw reads.
                    # We proceed with renaming what exists.
                    pass

                df = df.rename(columns=mapping)
                renamed_columns = {
                    old: new for old, new in mapping.items() if old in df.columns
                }

            stage_durations["normalization"] = int((time.time() - norm_start) * 1000)
            total_duration = int((time.time() - start_time) * 1000)

            return DataDiscoveryResult(
                df=df,
                file_path=discovery.file_path,
                version=discovery.version,
                sheet_name=discovery.sheet_name,
                row_count=len(df),
                column_count=len(df.columns),
                duration_ms=total_duration,
                columns_renamed=renamed_columns,
                stage_durations=stage_durations,
            )

        except DiscoveryError:
            # discover_file already logs error
            raise
        except Exception as exc:
            stage = self._identify_failed_stage(exc, post_discovery=True)
            wrapped = DiscoveryError(
                domain=domain,
                failed_stage=stage,
                original_error=exc,
                message=str(exc),
            )
            self.logger.error("discovery.failed", **wrapped.to_dict())
            raise wrapped

    def _load_domain_config(self, domain: str) -> DomainConfigV2:
        """Load and validate domain configuration.

        Supports two configuration sources:
        1. Direct injection: settings.data_sources (DataSourceConfigV2 object)
        2. YAML file: settings.data_sources_config (path to data_sources.yml)

        The first approach allows tests to inject configuration directly.
        """
        try:
            # Check for directly injected data_sources (for testing)
            if hasattr(self.settings, "data_sources") and isinstance(
                self.settings.data_sources, DataSourceConfigV2
            ):
                domains = self.settings.data_sources.domains
                if domain not in domains:
                    raise KeyError(domain)
                return domains[domain]

            # Default: load from YAML file
            config_path = self.settings.data_sources_config
            # Use the helper function that handles V2 validation and defaults merging
            return get_domain_config_v2(domain_name=domain, config_path=config_path)
        except (FileNotFoundError, DataSourcesValidationError) as e:
            raise DiscoveryError(
                domain=domain,
                failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                original_error=e,
                message=f"Configuration error: {e}",
            )
        except KeyError as e:
            raise DiscoveryError(
                domain=domain,
                failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                original_error=e,
                message=f"Domain '{domain}' not found in configuration",
            )
        except AttributeError as e:
            raise DiscoveryError(
                domain=domain,
                failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                original_error=e,
                message="Invalid settings configuration: missing data_sources or data_sources_config",
            )

    def _resolve_template_vars(self, path_template: str, template_vars: dict) -> Path:
        """Resolve template variables in base path."""
        # Security: Check for null byte injection in path template
        if "\x00" in path_template:
            raise DiscoveryError(
                domain="unknown",
                failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                original_error=ValueError("Null byte in path"),
                message="Security error: null byte detected in path",
            )

        # Validate YYYYMM format if present (security: prevent path traversal)
        if "YYYYMM" in template_vars:
            yyyymm = template_vars["YYYYMM"]
            if not isinstance(yyyymm, str) or len(yyyymm) != 6 or not yyyymm.isdigit():
                raise DiscoveryError(
                    domain="unknown",
                    failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                    original_error=ValueError(f"Invalid YYYYMM format: {yyyymm}"),
                    message=f"YYYYMM must be exactly 6 digits, got: {yyyymm}",
                )
            month = int(yyyymm[4:6])
            if month < 1 or month > 12:
                raise DiscoveryError(
                    domain="unknown",
                    failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                    original_error=ValueError(f"Invalid month: {yyyymm[4:6]}"),
                    message=f"Month must be between 01 and 12, got: {yyyymm[4:6]}",
                )

        try:
            resolved = Path(path_template.format(**template_vars))
            return resolved
        except KeyError as e:
            raise DiscoveryError(
                domain="unknown",  # context available in caller
                failed_stage=DiscoveryStage.CONFIG_VALIDATION,
                original_error=e,
                message=f"Missing Template variable: {e}",
            )

    def _detect_version_with_fallback(
        self,
        base_path: Path,
        config: DomainConfigV2,
        version_override: Optional[str],
    ) -> VersionedPath:
        """Detect version using configured strategy or override, with fallback support."""
        try:
            return self.version_scanner.detect_version(
                base_path=base_path,
                file_patterns=config.file_patterns,
                strategy=config.version_strategy,
                version_override=version_override,
            )
        except (DiscoveryError, Exception) as primary_error:
            # Check if fallback is configured
            fallback = getattr(config, "fallback", "error")
            if fallback == "error":
                raise

            # Map fallback config to strategy name
            fallback_strategy = None
            if fallback == "use_latest_modified":
                fallback_strategy = "latest_modified"
            elif fallback == "use_oldest_modified":
                fallback_strategy = "oldest_modified"

            if fallback_strategy:
                try:
                    return self.version_scanner.detect_version(
                        base_path=base_path,
                        file_patterns=config.file_patterns,
                        strategy=fallback_strategy,
                        version_override=version_override,
                    )
                except Exception:
                    # Fallback also failed, raise original error
                    raise primary_error

            # No valid fallback strategy, raise original error
            raise

    def _identify_failed_stage(
        self, exc: Exception, post_discovery: bool = False
    ) -> str:
        """Heuristic to identify initialization stage from exception."""
        error_msg = str(exc).lower()

        if post_discovery:
            # After discover_file(), we're in read or normalization
            if "excel" in error_msg:
                return "excel_reading"
            return "normalization"

        # During discover_file()
        # Check error message for hints
        if "version" in error_msg:
            return "version_detection"

        # Check exception type
        if isinstance(exc, FileNotFoundError):
            return "file_matching"

        return "unknown"
