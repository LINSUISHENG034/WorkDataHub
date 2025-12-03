r"""Version-aware folder scanner for intelligent file discovery.

Implements Story 3.1: Version-Aware Folder Scanner with configurable
precedence rules and file-pattern-aware detection (Decision #1).

Key Features:
- Detect version folders matching pattern V\d+ (V1, V2, V3, etc.)
- Select version based on strategy: highest_number, latest_modified, manual
- File-pattern-aware detection: skip version folders with no matching files
- Comprehensive error handling with DiscoveryError and stage markers
- Cross-platform compatibility with Unicode support
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

from work_data_hub.io.connectors.exceptions import DiscoveryError
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

VersionStrategy = Literal['highest_number', 'latest_modified', 'manual']


@dataclass
class VersionedPath:
    """Result of version detection.

    Attributes:
        path: Selected version path (or base path if no versions)
        version: Version identifier ("V2", "V3", etc.) or "base" if no versions
        strategy_used: Strategy that was used for selection
        selected_at: Timestamp when this selection was made
        rejected_versions: List of versions that were skipped and why
    """
    path: Path                 # Selected version path
    version: str               # "V2" or "base" if no versions
    strategy_used: str         # "highest_number", "latest_modified", "manual"
    selected_at: datetime      # Timestamp of selection
    rejected_versions: List[str]  # Versions skipped and why


class VersionScanner:
    """Detect and select versioned folders (V1, V2, V3) with configurable strategies.

    Supports three selection strategies:
    1. highest_number: Select version with highest numeric value (V3 > V2 > V1)
    2. latest_modified: Select most recently modified version folder
    3. manual: Use specified version regardless of automatic detection

    Features file-pattern-aware detection (Decision #1) which scopes version selection
    to domain-specific file patterns, enabling partial corrections without forcing
    all domains to use the same version.
    """

    VERSION_PATTERN = re.compile(r'^V(\d+)$')  # Matches V1, V2, ..., V99

    def detect_version(
        self,
        base_path: Path,
        file_patterns: List[str],
        strategy: VersionStrategy = 'highest_number',
        version_override: Optional[str] = None
    ) -> VersionedPath:
        """
        Detect and select version folder from base_path.

        Args:
            base_path: Directory to scan for V* folders
            file_patterns: Glob patterns to match (for file-pattern-aware detection)
            strategy: Selection strategy (highest_number, latest_modified, manual)
            version_override: Manual version selection (e.g., "V1")

        Returns:
            VersionedPath with selected path and metadata

        Raises:
            DiscoveryError: If version detection fails or ambiguous
        """
        # Manual override short-circuit
        if version_override:
            return self._handle_manual_override(base_path, version_override)

        # Validate base_path exists and is accessible
        if not base_path.exists():
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=FileNotFoundError(f"Base path does not exist: {base_path}"),
                message=f"Base path not found: {base_path}"
            )

        # Scan for version folders
        version_folders = self._scan_version_folders(base_path)

        if not version_folders:
            logger.info(
                "version_detection.no_folders",
                base_path=str(base_path),
                fallback="using base path"
            )
            return VersionedPath(
                path=base_path,
                version="base",
                strategy_used=strategy,
                selected_at=datetime.now(),
                rejected_versions=[]
            )

        # File-pattern-aware filtering (Decision #1)
        filtered_folders = self._filter_by_file_patterns(
            version_folders,
            file_patterns
        )

        if not filtered_folders:
            logger.warning(
                "version_detection.no_matching_files",
                base_path=str(base_path),
                version_folders=[v.name for v in version_folders],
                file_patterns=file_patterns
            )
            # Fallback to base path if no versions have matching files
            return VersionedPath(
                path=base_path,
                version="base",
                strategy_used=strategy,
                selected_at=datetime.now(),
                rejected_versions=[f"{v.name} (no matching files)" for v in version_folders]
            )

        # Select version based on strategy
        if strategy == 'highest_number':
            selected = self._select_highest_number(filtered_folders)
        elif strategy == 'latest_modified':
            selected = self._select_latest_modified(filtered_folders)
        else:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=ValueError(f"Invalid strategy: {strategy}"),
                message=f"Unsupported version strategy: {strategy}"
            )

        rejected = [
            f.name for f in filtered_folders
            if f != selected
        ] + [
            f"{v.name} (no matching files)"
            for v in version_folders if v not in filtered_folders
        ]

        logger.info(
            "version_detection.completed",
            base_path=str(base_path),
            strategy=strategy,
            discovered_versions=[v.name for v in version_folders],
            selected_version=selected.name,
            rejected_versions=rejected
        )

        return VersionedPath(
            path=selected,
            version=selected.name,
            strategy_used=strategy,
            selected_at=datetime.now(),
            rejected_versions=rejected
        )

    def _scan_version_folders(self, base_path: Path) -> List[Path]:
        """Scan base_path for V* folders."""
        version_folders = []
        try:
            for item in base_path.iterdir():
                if item.is_dir() and self.VERSION_PATTERN.match(item.name):
                    version_folders.append(item)
        except OSError as e:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=e,
                message=f"Failed to scan directory {base_path}: {e}"
            )

        logger.debug(
            "version_detection.found_folders",
            base_path=str(base_path),
            folders=[v.name for v in version_folders],
            count=len(version_folders)
        )

        return version_folders

    def _filter_by_file_patterns(
        self,
        version_folders: List[Path],
        file_patterns: List[str]
    ) -> List[Path]:
        """Filter version folders to those containing matching files (Decision #1)."""
        filtered = []
        for folder in version_folders:
            has_matching_files = False
            try:
                for pattern in file_patterns:
                    matches = list(folder.glob(pattern))
                    if matches:
                        has_matching_files = True
                        break
            except OSError as e:
                logger.warning(
                    "version_detection.folder_access_error",
                    folder=folder.name,
                    error=str(e)
                )
                continue

            if has_matching_files:
                filtered.append(folder)
            else:
                logger.debug(
                    "version_detection.skipped_folder",
                    folder=folder.name,
                    reason="no files matching patterns",
                    patterns=file_patterns
                )

        return filtered

    def _select_highest_number(self, folders: List[Path]) -> Path:
        """Select version with highest numeric value."""
        def version_number(folder: Path) -> int:
            match = self.VERSION_PATTERN.match(folder.name)
            return int(match.group(1)) if match else 0

        if not folders:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=ValueError("No folders provided"),
                message="No folders available for selection"
            )

        selected = max(folders, key=version_number)
        logger.debug(
            "version_detection.highest_number_selected",
            selected=selected.name,
            considered=[f.name for f in folders]
        )
        return selected

    def _select_latest_modified(self, folders: List[Path]) -> Path:
        """Select most recently modified version folder."""
        if not folders:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=ValueError("No folders provided"),
                message="No folders available for selection"
            )

        # Get modification times
        folders_with_mtime = []
        try:
            folders_with_mtime = [
                (f, f.stat().st_mtime)
                for f in folders
            ]
        except OSError as e:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=e,
                message=f"Failed to get modification times: {e}"
            )

        # Sort by modification time, newest first
        sorted_by_mtime = sorted(
            folders_with_mtime,
            key=lambda x: x[1],
            reverse=True
        )

        # Check for ambiguity (folders modified within 1 second of each other)
        if len(sorted_by_mtime) > 1:
            latest_mtime = sorted_by_mtime[0][1]
            same_mtime = [
                f.name for f, mtime in sorted_by_mtime
                if abs(mtime - latest_mtime) < 1  # Within 1 second
            ]

            if len(same_mtime) > 1:
                raise DiscoveryError(
                    domain="unknown",
                    failed_stage="version_detection",
                    original_error=ValueError("Ambiguous versions"),
                    message=(
                        f"Ambiguous versions: {same_mtime} "
                        f"modified at same time, configure precedence "
                        f"rule or specify --version manually"
                    )
                )

        selected = sorted_by_mtime[0][0]
        logger.debug(
            "version_detection.latest_modified_selected",
            selected=selected.name,
            modification_time=datetime.fromtimestamp(sorted_by_mtime[0][1]).isoformat(),
            considered=[f.name for f in folders]
        )
        return selected

    def _handle_manual_override(
        self,
        base_path: Path,
        version: str
    ) -> VersionedPath:
        """Handle manual version override."""
        version_path = base_path / version

        if not version_path.exists():
            raise DiscoveryError(
                domain="unknown",
                failed_stage="version_detection",
                original_error=FileNotFoundError(f"Version {version} not found"),
                message=f"Manual version '{version}' not found in {base_path}"
            )

        logger.info(
            "version_detection.manual_override",
            base_path=str(base_path),
            version=version
        )

        return VersionedPath(
            path=version_path,
            version=version,
            strategy_used="manual",
            selected_at=datetime.now(),
            rejected_versions=["manual override - automatic detection bypassed"]
        )
