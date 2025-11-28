"""File discovery connector anchored in the I/O layer (Story 1.6).

Configuration-driven scanning, version resolution, and filesystem access live
here so that Story 1.5 domain pipelines only depend on pure inputs. Dagster
ops inject this connector into domain transformations instead of importing
`work_data_hub.io` from domain modules, keeping the dependency direction
domain ← io ← orchestration intact.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

import pandas as pd
import yaml

import src.work_data_hub.config.settings as settings_module
from src.work_data_hub.config.schema import (
    DataSourceConfigV2,
    DataSourcesValidationError,
    DomainConfigV2,
)
from src.work_data_hub.utils.types import (
    DiscoveredFile,
    extract_file_metadata,
    is_temporary_file,
    validate_excel_file,
)
from work_data_hub.io.connectors.exceptions import DiscoveryError
from work_data_hub.io.connectors.file_pattern_matcher import (
    FileMatchResult,
    FilePatternMatcher,
)
from work_data_hub.io.connectors.version_scanner import VersionScanner, VersionedPath
from work_data_hub.io.readers.excel_reader import ExcelReadResult, ExcelReader
from work_data_hub.utils.logging import get_logger


class DataSourceConnectorError(Exception):
    """Raised when data source connector encounters an error."""

    pass


# Module-level logger for DataSourceConnector (legacy class)
_connector_logger = get_logger(__name__)


class DataSourceConnector:
    """
    Configuration-driven file discovery connector.

    This class handles the discovery of data files based on configurable
    regex patterns and selection strategies. It supports Unicode filename
    matching, version directory handling, and various file filtering options.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the data source connector.

        Args:
            config_path: Path to YAML configuration file. If None, uses default
                        from settings.
        """
        # Lazily load settings to make it easy to inject patched versions in tests
        self.settings: Optional[Any] = None
        self.logger = _connector_logger

        # Use provided config path or default from settings
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = self._get_settings().data_sources_config

        # Load and validate configuration
        self.config = self._load_config()

        # Prepare canonical/alias mappings for domain names
        self._canonical_domains = {
            name: self._canonicalize_domain(name, cfg)
            for name, cfg in self.config["domains"].items()
        }
        self._domain_aliases = {
            canonical: name for name, canonical in self._canonical_domains.items()
        }

        # Pre-compile regex patterns with Unicode support
        self.compiled_patterns = self._compile_patterns()

    def _get_settings(self) -> Any:
        """
        Lazily resolve settings so tests can patch get_settings easily.
        """
        if self.settings is None:
            self.settings = settings_module.get_settings()
        return self.settings

    def discover(self, domain: Optional[str] = None) -> List[DiscoveredFile]:
        """
        Discover files matching domain patterns.

        Args:
            domain: Specific domain to discover files for. If None, discovers
                   files for all configured domains.

        Returns:
            List of DiscoveredFile objects representing found files

        Raises:
            DataSourceConnectorError: If discovery fails
        """
        # Determine domains to scan
        domains_to_scan: List[str]
        if domain:
            config_domain = self._domain_aliases.get(domain, domain)
            domains_to_scan = [config_domain]
        else:
            domains_to_scan = list(self.config["domains"].keys())

        # Validate requested domain exists (after alias resolution)
        if domain:
            config_domain = self._domain_aliases.get(domain, domain)
            if config_domain not in self.config["domains"]:
                raise DataSourceConnectorError(f"Unknown domain: {domain}")

        self.logger.info(f"Starting file discovery for domains: {domains_to_scan}")

        discovered_files = []

        for domain_name in domains_to_scan:
            domain_config = self.config["domains"][domain_name]
            pattern = self.compiled_patterns[domain_name]

            self.logger.debug(
                "Scanning for domain '%s' with pattern: %s",
                domain_name,
                domain_config["pattern"],
            )

            # Discover files for this domain
            domain_files = self._scan_directory_for_domain(
                domain_name, pattern, domain_config
            )
            discovered_files.extend(domain_files)

            self.logger.info(f"Found {len(domain_files)} files for domain '{domain_name}'")

        # Apply selection strategies to discovered files
        selected_files = self._apply_selection_strategies(discovered_files)

        self.logger.info(
            f"Selected {len(selected_files)} files after applying selection strategies"
        )

        return selected_files

    def _load_config(self) -> Dict[str, Any]:
        """
        Load and validate YAML configuration file.

        Returns:
            Dictionary containing parsed configuration

        Raises:
            DataSourceConnectorError: If config cannot be loaded or is invalid
        """
        config_path = Path(self.config_path)

        if not config_path.exists():
            raise DataSourceConnectorError(
                f"Configuration file not found: {self.config_path}"
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise DataSourceConnectorError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise DataSourceConnectorError(f"Failed to load configuration: {e}")

        # Validate required sections exist
        if "domains" not in config:
            raise DataSourceConnectorError("Configuration missing 'domains' section")

        # Validate each domain configuration
        for domain_name, domain_config in config["domains"].items():
            required_keys = ["pattern", "select"]
            for key in required_keys:
                if key not in domain_config:
                    raise DataSourceConnectorError(
                        f"Domain '{domain_name}' missing required key: {key}"
                    )

        self.logger.info(f"Loaded configuration for {len(config['domains'])} domains")
        return config

    def _compile_patterns(self) -> Dict[str, Pattern[str]]:
        """
        Pre-compile all regex patterns with Unicode support.

        Returns:
            Dictionary mapping domain names to compiled regex patterns

        Raises:
            DataSourceConnectorError: If any pattern fails to compile
        """
        compiled = {}

        for domain_name, domain_config in self.config["domains"].items():
            pattern_str = domain_config["pattern"]

            try:
                # Compile with Unicode support for Chinese characters
                compiled[domain_name] = re.compile(
                    pattern_str, re.UNICODE | re.IGNORECASE
                )
                self.logger.debug(
                    f"Compiled pattern for domain '{domain_name}': {pattern_str}"
                )
            except re.error as e:
                raise DataSourceConnectorError(
                    f"Invalid regex pattern for domain '{domain_name}': {e}"
                )

        return compiled

    @staticmethod
    def _canonicalize_domain(
        domain_name: str, domain_config: Dict[str, Any]
    ) -> str:
        """
        Determine the canonical domain name for reporting and API usage.
        """
        if "canonical_domain" in domain_config:
            return domain_config["canonical_domain"]
        if domain_name.startswith("sample_"):
            return domain_name.replace("sample_", "", 1)
        return domain_name

    def _resolve_config_domain(self, canonical_domain: str) -> str:
        """
        Map a canonical domain name back to its configuration key.
        """
        return self._domain_aliases.get(canonical_domain, canonical_domain)

    def _scan_directory_for_domain(
        self, domain_name: str, pattern: Pattern[str], domain_config: Dict[str, Any]
    ) -> List[DiscoveredFile]:
        """
        Scan base directory for files matching the domain pattern.

        Args:
            domain_name: Name of the domain being scanned
            pattern: Compiled regex pattern for the domain
            domain_config: Configuration dictionary for the domain

        Returns:
            List of DiscoveredFile objects for this domain
        """
        base_dir = Path(self._get_settings().data_base_dir)

        if not base_dir.exists():
            self.logger.warning(f"Data base directory does not exist: {base_dir}")
            return []

        discovered = []
        max_depth = self.config.get("discovery", {}).get("max_depth", 10)

        # Use os.walk for performance with large directory trees
        try:
            for root, dirs, files in os.walk(str(base_dir)):
                # Calculate current depth
                current_depth = len(Path(root).relative_to(base_dir).parts)
                if current_depth >= max_depth:
                    continue

                # Filter out excluded directories
                excluded_dirs = self.config.get("discovery", {}).get(
                    "exclude_directories", []
                )
                dirs[:] = [d for d in dirs if d not in excluded_dirs]

                # Process files in current directory
                for filename in files:
                    file_path = os.path.join(root, filename)

                    # Skip temporary and non-Excel files early
                    if is_temporary_file(filename):
                        continue

                    if not validate_excel_file(file_path):
                        continue

                    # Apply domain-specific pattern matching
                    match = pattern.search(filename)
                    if match:
                        # Extract year/month from named groups if present
                        groups = match.groupdict()
                        year = (
                            int(groups["year"])
                            if "year" in groups and groups["year"]
                            else None
                        )

                        # Post-process month extraction for robustness
                        month_str = groups.get("month")
                        if month_str and len(month_str) == 1 and month_str in "12":
                            # Check if this is actually part of "10", "11", or "12"
                            match_end = match.end("month")
                            if match_end < len(filename):
                                next_char = filename[match_end]
                                if month_str == "1" and next_char in "012":
                                    month_str = (
                                        month_str + next_char
                                    )  # Form "10", "11", "12"

                        month = int(month_str) if month_str else None

                        # Apply two-digit year normalization
                        # (24 → 2024, but 2024 → 2024)
                        if year and year < 100:
                            year = 2000 + year

                        # Extract version from parent directory (only under "数据采集")
                        version = None
                        parent_path = Path(file_path).parent
                        if (
                            parent_path.parent.name == "数据采集"
                            and parent_path.name.upper().startswith("V")
                        ):
                            try:
                                version_str = parent_path.name[1:]  # Remove 'V' prefix
                                version = int(version_str)
                                self.logger.debug(
                                    "Extracted version %s from directory %s",
                                    version,
                                    parent_path.name,
                                )
                            except ValueError:
                                version = (
                                    None  # Fallback for malformed versions like 'VX'
                                )
                                self.logger.debug(
                                    "Malformed version in %s, using mtime fallback",
                                    parent_path.name,
                                )

                        # Extract additional file metadata
                        try:
                            file_metadata = extract_file_metadata(file_path)
                            file_metadata.update(groups)  # Add regex groups to metadata
                            file_metadata["version"] = (
                                version  # Add version to metadata
                            )
                        except OSError as e:
                            self.logger.warning(
                                "Cannot extract metadata for %s: %s", file_path, e
                            )
                            file_metadata = groups
                            file_metadata["version"] = (
                                version  # Add version to metadata
                            )

                        discovered_file = DiscoveredFile(
                            domain=self._canonical_domains.get(
                                domain_name, domain_name
                            ),
                            path=file_path,
                            year=year,
                            month=month,
                            metadata=file_metadata,
                        )

                        discovered.append(discovered_file)
                        self.logger.debug(
                            "Discovered file: %s (year=%s, month=%s)",
                            file_path,
                            year,
                            month,
                        )

        except OSError as e:
            self.logger.error(f"Error scanning directory {base_dir}: {e}")
            raise DataSourceConnectorError(f"Directory scan failed: {e}")

        return discovered

    def _apply_selection_strategies(
        self, files: List[DiscoveredFile]
    ) -> List[DiscoveredFile]:
        """
        Apply selection strategies to discovered files by domain.

        Args:
            files: List of all discovered files

        Returns:
            List of selected files after applying strategies
        """
        # Group files by domain
        by_domain: dict[str, list[DiscoveredFile]] = {}
        for file in files:
            if file.domain not in by_domain:
                by_domain[file.domain] = []
            by_domain[file.domain].append(file)

        selected_files = []

        for domain, domain_files in by_domain.items():
            config_domain = self._resolve_config_domain(domain)
            domain_config = self.config["domains"][config_domain]
            strategy = domain_config["select"]

            if strategy == "latest_by_year_month":
                selected = self._select_latest_by_year_month(domain_files)
            elif strategy == "latest_by_mtime":
                selected = self._select_latest_by_mtime(domain_files)
            elif strategy == "latest_by_year_month_and_version":
                selected = self._select_latest_by_year_month_and_version(domain_files)
            else:
                self.logger.warning(
                    "Unknown selection strategy '%s' for domain '%s'",
                    strategy,
                    domain,
                )
                selected = domain_files  # Return all files if strategy unknown

            if selected:
                selected_files.extend(selected)
                self.logger.info(
                    "Domain '%s': Selected %s files using '%s' strategy",
                    domain,
                    len(selected),
                    strategy,
                )

        return selected_files

    def _select_latest_by_year_month(
        self, files: List[DiscoveredFile]
    ) -> List[DiscoveredFile]:
        """
        Select latest file by year/month, with mtime fallback.

        Args:
            files: List of files to select from

        Returns:
            List containing the selected file (or empty if none found)
        """
        if not files:
            return []

        # Separate files with and without year/month data
        with_dates = [f for f in files if f.year is not None and f.month is not None]
        without_dates = [f for f in files if f.year is None or f.month is None]

        if with_dates:
            # Select file with highest (year, month) tuple
            latest = max(with_dates, key=lambda f: (f.year, f.month))
            return [latest]
        elif without_dates:
            # Fallback to modification time
            return self._select_latest_by_mtime(without_dates)
        else:
            return []

    def _select_latest_by_mtime(
        self, files: List[DiscoveredFile]
    ) -> List[DiscoveredFile]:
        """
        Select file with the most recent modification time.

        Args:
            files: List of files to select from

        Returns:
            List containing the selected file (or empty if none found)
        """
        if not files:
            return []

        try:
            # Find file with maximum modification time
            latest = max(files, key=lambda f: Path(f.path).stat().st_mtime)
            return [latest]
        except (OSError, FileNotFoundError) as e:
            self.logger.error(f"Error accessing file modification times: {e}")
            # Fallback to first file if mtime comparison fails
            return [files[0]] if files else []

    def _select_latest_by_year_month_and_version(
        self, files: List[DiscoveredFile]
    ) -> List[DiscoveredFile]:
        """
        Select latest file by year/month/version, with mtime fallback.

        Groups files by (year, month) and selects file with highest
        (version, mtime) tuple within each group. Files without versions
        are assigned version=0 for comparison.

        Args:
            files: List of files to select from

        Returns:
            List of selected files (one per unique year/month combination)
        """
        if not files:
            return []

        # Group by (year, month) - same as existing method
        from itertools import groupby

        # Sort first by year/month for grouping
        sorted_files = sorted(files, key=lambda f: (f.year or 0, f.month or 0))

        selected = []
        for (year, month), group_files in groupby(
            sorted_files, key=lambda f: (f.year, f.month)
        ):
            group_list = list(group_files)

            # Within group, select by (version, mtime) descending
            try:
                best_file = max(
                    group_list,
                    key=lambda f: (
                        f.metadata.get("version") or 0,  # None versions get 0
                        Path(f.path).stat().st_mtime,
                    ),
                )
                selected.append(best_file)
                self.logger.debug(
                    f"Selected file with version {best_file.metadata.get('version')} "
                    f"for year={year}, month={month}: {best_file.path}"
                )
            except (OSError, FileNotFoundError) as e:
                self.logger.error(
                    f"Error accessing file modification times in version selection: {e}"
                )
                # Fallback to first file if stat() fails
                if group_list:
                    selected.append(group_list[0])

        return selected


# ---------------------------------------------------------------------------
# Epic 3 Story 3.5: FileDiscoveryService (facade orchestrator)
# ---------------------------------------------------------------------------


@dataclass
class DataDiscoveryResult:
    """Result of file discovery operation with rich metadata."""

    df: pd.DataFrame
    file_path: Path
    version: str
    sheet_name: str
    row_count: int
    column_count: int
    duration_ms: int
    columns_renamed: Dict[str, str]
    stage_durations: Dict[str, int]


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
        self.settings = settings or settings_module.get_settings()
        self.version_scanner = version_scanner or VersionScanner()
        self.file_matcher = file_matcher or FilePatternMatcher()
        self.excel_reader = excel_reader or ExcelReader()
        self.logger = get_logger(__name__)

    def discover_and_load(
        self,
        domain: str,
        version_override: Optional[str] = None,
        **template_vars: Any,
    ) -> DataDiscoveryResult:
        """
        Discover and load data file for a domain.

        Args:
            domain: Domain identifier (e.g., 'annuity_performance')
            version_override: Optional manual version (e.g., "V1")
            **template_vars: Template variables for path resolution (e.g., month="202501")

        Returns:
            DataDiscoveryResult with loaded DataFrame and metadata

        Raises:
            DiscoveryError: With structured context if any stage fails
        """
        start_time = time.perf_counter()
        self.logger.info("discovery.started", domain=domain, template_vars=template_vars)

        try:
            domain_config = self._load_domain_config(domain)
            base_path = self._resolve_template_vars(
                domain_config.base_path, template_vars
            )
            stage_durations: Dict[str, int] = {}

            # Stage 1: Version detection
            stage_start = time.perf_counter()
            version_result = self._detect_version_with_fallback(
                base_path, domain_config, version_override
            )
            stage_durations["version_detection"] = self._log_stage(
                "discovery.version_detected",
                stage_start,
                version=version_result.version,
                path=str(version_result.path),
                strategy=version_result.strategy_used,
            )

            # Stage 2: File matching
            stage_start = time.perf_counter()
            match_result = self.file_matcher.match_files(
                search_path=version_result.path,
                include_patterns=list(domain_config.file_patterns),
                exclude_patterns=list(domain_config.exclude_patterns or []),
            )
            stage_durations["file_matching"] = self._log_stage(
                "discovery.file_matched",
                stage_start,
                file_path=str(match_result.matched_file),
                match_count=match_result.match_count,
            )

            # Stage 3: Excel reading (normalization happens inside reader)
            stage_start = time.perf_counter()
            excel_result = self.excel_reader.read_sheet(
                file_path=match_result.matched_file,
                sheet_name=domain_config.sheet_name,
                normalize_columns=True,
            )
            stage_durations["excel_reading"] = self._log_stage(
                "discovery.excel_read",
                stage_start,
                row_count=excel_result.row_count,
                column_count=excel_result.column_count,
            )

            total_duration = int((time.perf_counter() - start_time) * 1000)
            result = DataDiscoveryResult(
                df=excel_result.df,
                file_path=match_result.matched_file,
                version=version_result.version,
                sheet_name=excel_result.sheet_name,
                row_count=excel_result.row_count,
                column_count=excel_result.column_count,
                duration_ms=total_duration,
                columns_renamed=excel_result.columns_renamed,
                stage_durations=stage_durations,
            )

            self.logger.info(
                "discovery.completed",
                domain=domain,
                file_path=str(result.file_path),
                version=result.version,
                sheet_name=result.sheet_name,
                row_count=result.row_count,
                column_count=result.column_count,
                duration_ms=result.duration_ms,
                stage_durations=stage_durations,
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_version_with_fallback(
        self,
        base_path: Path,
        domain_config: DomainConfigV2,
        version_override: Optional[str],
    ) -> VersionedPath:
        """Detect version, applying fallback strategy if configured."""
        try:
            return self.version_scanner.detect_version(
                base_path=base_path,
                file_patterns=list(domain_config.file_patterns),
                strategy=domain_config.version_strategy,
                version_override=version_override,
            )
        except DiscoveryError as exc:
            if (
                domain_config.fallback == "use_latest_modified"
                and domain_config.version_strategy != "latest_modified"
            ):
                return self.version_scanner.detect_version(
                    base_path=base_path,
                    file_patterns=list(domain_config.file_patterns),
                    strategy="latest_modified",
                    version_override=version_override,
                )
            raise exc

    def _load_domain_config(self, domain: str) -> DomainConfigV2:
        """Load domain configuration from validated settings."""
        data_sources: Optional[DataSourceConfigV2] = getattr(
            self.settings, "data_sources", None
        )
        if not data_sources:
            raise DataSourcesValidationError(
                "Epic 3 data sources configuration is not loaded"
            )

        if domain not in data_sources.domains:
            raise DataSourcesValidationError(
                f"Domain '{domain}' not found in configuration"
            )

        return data_sources.domains[domain]

    def _resolve_template_vars(
        self, path_template: str, template_vars: Dict[str, Any]
    ) -> Path:
        """Resolve {YYYYMM}, {YYYY}, {MM} placeholders.

        Security: Validates resolved path to prevent directory traversal attacks.
        """
        needs_resolution = any(
            token in path_template for token in ("{YYYYMM}", "{YYYY}", "{MM}")
        )
        if not needs_resolution:
            resolved = path_template
        else:
            yyyymm = template_vars.get("month") or template_vars.get("YYYYMM")
            if not yyyymm:
                raise ValueError("Template variable {YYYYMM} not provided")

            yyyymm_str = str(yyyymm)
            if not (yyyymm_str.isdigit() and len(yyyymm_str) == 6):
                raise ValueError("Template variable {YYYYMM} must be 6 digits (YYYYMM)")

            yyyy, mm = yyyymm_str[:4], yyyymm_str[4:6]
            if int(mm) < 1 or int(mm) > 12:
                raise ValueError("Template variable {MM} must be between 01 and 12")

            resolved = path_template.replace("{YYYYMM}", yyyymm_str)
            resolved = resolved.replace("{YYYY}", yyyy)
            resolved = resolved.replace("{MM}", mm)

            if "{" in resolved or "}" in resolved:
                raise ValueError(f"Unresolved template variables in path: {resolved}")

        # Security: Prevent path traversal attacks
        self._validate_path_security(resolved)

        return Path(resolved)

    def _validate_path_security(self, path_str: str) -> None:
        """Validate path does not contain directory traversal sequences.

        Args:
            path_str: The resolved path string to validate.

        Raises:
            ValueError: If path contains traversal sequences or is outside allowed scope.
        """
        # Check for directory traversal patterns
        if ".." in path_str:
            raise ValueError(
                f"Path traversal detected: '..' not allowed in path: {path_str}"
            )

        # Normalize and check for traversal via different separators
        normalized = path_str.replace("\\", "/")
        if "../" in normalized or "/.." in normalized:
            raise ValueError(
                f"Path traversal detected in normalized path: {path_str}"
            )

        # Check for absolute paths that could escape the reference directory
        path_obj = Path(path_str)
        if path_obj.is_absolute():
            # Allow absolute paths only if they don't contain traversal
            # The actual base directory restriction is enforced by the caller
            pass

        # Check for null bytes (path injection)
        if "\x00" in path_str:
            raise ValueError(
                f"Null byte injection detected in path: {path_str!r}"
            )

    def _identify_failed_stage(self, error: Exception) -> str:
        """Map exceptions to discovery stages for structured errors."""
        if isinstance(error, DiscoveryError):
            return error.failed_stage

        name = type(error).__name__
        msg = str(error)

        if "ValidationError" in name or "DataSourcesValidationError" in name:
            return "config_validation"
        if "template" in msg.lower():
            return "config_validation"
        if "Version" in name or "version" in msg.lower():
            return "version_detection"
        if isinstance(error, FileNotFoundError):
            return "file_matching"
        if "Excel" in name or "excel" in msg.lower():
            return "excel_reading"
        if "Normalization" in name or "normalize" in msg.lower():
            return "normalization"
        return "file_matching"

    def _log_stage(self, event: str, stage_start: float, **kwargs: Any) -> int:
        """Log stage completion with duration and return it."""
        duration_ms = int((time.perf_counter() - stage_start) * 1000)
        self.logger.info(event, duration_ms=duration_ms, **kwargs)
        return duration_ms
