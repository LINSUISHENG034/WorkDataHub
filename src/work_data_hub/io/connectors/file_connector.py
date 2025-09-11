"""
File discovery connector for WorkDataHub.

This module provides configuration-driven file discovery with Unicode-aware
regex patterns, version selection strategies, and robust error handling.
It supports complex filename patterns including Chinese characters and
handles versioned directory structures automatically.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

import yaml

from ...config import settings as settings_module
from ...utils.types import (
    DiscoveredFile,
    extract_file_metadata,
    is_temporary_file,
    validate_excel_file,
)

logger = logging.getLogger(__name__)


class DataSourceConnectorError(Exception):
    """Raised when data source connector encounters an error."""

    pass


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
        # Fetch settings from module to support test monkeypatching
        self.settings = settings_module.get_settings()

        # Use provided config path or default from settings
        self.config_path = config_path or self.settings.data_sources_config

        # Load and validate configuration
        self.config = self._load_config()

        # Pre-compile regex patterns with Unicode support
        self.compiled_patterns = self._compile_patterns()

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
        domains_to_scan = [domain] if domain else list(self.config["domains"].keys())

        # Validate requested domain exists
        if domain and domain not in self.config["domains"]:
            raise DataSourceConnectorError(f"Unknown domain: {domain}")

        logger.info(f"Starting file discovery for domains: {domains_to_scan}")

        discovered_files = []

        for domain_name in domains_to_scan:
            domain_config = self.config["domains"][domain_name]
            pattern = self.compiled_patterns[domain_name]

            logger.debug(
                f"Scanning for domain '{domain_name}' with pattern: {domain_config['pattern']}"
            )

            # Discover files for this domain
            domain_files = self._scan_directory_for_domain(domain_name, pattern, domain_config)
            discovered_files.extend(domain_files)

            logger.info(f"Found {len(domain_files)} files for domain '{domain_name}'")

        # Apply selection strategies to discovered files
        selected_files = self._apply_selection_strategies(discovered_files)

        logger.info(f"Selected {len(selected_files)} files after applying selection strategies")

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
            raise DataSourceConnectorError(f"Configuration file not found: {self.config_path}")

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

        logger.info(f"Loaded configuration for {len(config['domains'])} domains")
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
                compiled[domain_name] = re.compile(pattern_str, re.UNICODE | re.IGNORECASE)
                logger.debug(f"Compiled pattern for domain '{domain_name}': {pattern_str}")
            except re.error as e:
                raise DataSourceConnectorError(
                    f"Invalid regex pattern for domain '{domain_name}': {e}"
                )

        return compiled

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
        base_dir = Path(self.settings.data_base_dir)

        if not base_dir.exists():
            logger.warning(f"Data base directory does not exist: {base_dir}")
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
                excluded_dirs = self.config.get("discovery", {}).get("exclude_directories", [])
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
                        year = int(groups["year"]) if "year" in groups and groups["year"] else None

                        # Post-process month extraction for robustness
                        month_str = groups.get("month")
                        if month_str and len(month_str) == 1 and month_str in "12":
                            # Check if this is actually part of "10", "11", or "12"
                            match_end = match.end("month")
                            if match_end < len(filename):
                                next_char = filename[match_end]
                                if month_str == "1" and next_char in "012":
                                    month_str = month_str + next_char  # Form "10", "11", "12"

                        month = int(month_str) if month_str else None

                        # Apply two-digit year normalization (24 → 2024, but 2024 → 2024)
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
                                logger.debug(
                                    f"Extracted version {version} from directory {parent_path.name}"
                                )
                            except ValueError:
                                version = None  # Fallback for malformed versions like 'VX'
                                logger.debug(
                                    f"Malformed version in {parent_path.name}, using mtime fallback"
                                )

                        # Extract additional file metadata
                        try:
                            file_metadata = extract_file_metadata(file_path)
                            file_metadata.update(groups)  # Add regex groups to metadata
                            file_metadata["version"] = version  # Add version to metadata
                        except OSError as e:
                            logger.warning(f"Cannot extract metadata for {file_path}: {e}")
                            file_metadata = groups
                            file_metadata["version"] = version  # Add version to metadata

                        discovered_file = DiscoveredFile(
                            domain=domain_name,
                            path=file_path,
                            year=year,
                            month=month,
                            metadata=file_metadata,
                        )

                        discovered.append(discovered_file)
                        logger.debug(f"Discovered file: {file_path} (year={year}, month={month})")

        except OSError as e:
            logger.error(f"Error scanning directory {base_dir}: {e}")
            raise DataSourceConnectorError(f"Directory scan failed: {e}")

        return discovered

    def _apply_selection_strategies(self, files: List[DiscoveredFile]) -> List[DiscoveredFile]:
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
            domain_config = self.config["domains"][domain]
            strategy = domain_config["select"]

            if strategy == "latest_by_year_month":
                selected = self._select_latest_by_year_month(domain_files)
            elif strategy == "latest_by_mtime":
                selected = self._select_latest_by_mtime(domain_files)
            elif strategy == "latest_by_year_month_and_version":
                selected = self._select_latest_by_year_month_and_version(domain_files)
            else:
                logger.warning(f"Unknown selection strategy '{strategy}' for domain '{domain}'")
                selected = domain_files  # Return all files if strategy unknown

            if selected:
                selected_files.extend(selected)
                logger.info(
                    f"Domain '{domain}': Selected {len(selected)} files using '{strategy}' strategy"
                )

        return selected_files

    def _select_latest_by_year_month(self, files: List[DiscoveredFile]) -> List[DiscoveredFile]:
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

    def _select_latest_by_mtime(self, files: List[DiscoveredFile]) -> List[DiscoveredFile]:
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
            logger.error(f"Error accessing file modification times: {e}")
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
        for (year, month), group_files in groupby(sorted_files, key=lambda f: (f.year, f.month)):
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
                logger.debug(
                    f"Selected file with version {best_file.metadata.get('version')} "
                    f"for year={year}, month={month}: {best_file.path}"
                )
            except (OSError, FileNotFoundError) as e:
                logger.error(f"Error accessing file modification times in version selection: {e}")
                # Fallback to first file if stat() fails
                if group_list:
                    selected.append(group_list[0])

        return selected
