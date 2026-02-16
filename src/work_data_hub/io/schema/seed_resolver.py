"""Seed version resolution for migration scripts.

This module provides utilities to automatically detect and select
the highest version of seed data files on a per-file basis.

Directory structure expected:
    config/seeds/
    ├── 001/  # Version 1
    │   ├── company_types_classification.csv
    │   ├── 年金关联公司.csv
    │   └── ...
    ├── 002/  # Version 2 (may have subset of files)
    │   ├── 年金关联公司.csv  # Updated version
    │   └── base_info.dump  # pg_dump format for large tables
    └── README.md

Each file independently resolves to its highest available version.
Empty directories are ignored.

Supported formats:
    - .csv: Standard CSV files for small/medium tables
    - .dump: pg_dump custom format for large tables with complex fields (JSON, etc.)

Format priority (when multiple formats exist for same table):
    1. .dump (preferred for large data)
    2. .csv (fallback for compatibility)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


class SeedFormat(enum.Enum):
    """Supported seed data formats."""

    CSV = "csv"
    DUMP = "dump"  # pg_dump custom format

    @property
    def extension(self) -> str:
        """Get file extension for this format."""
        return f".{self.value}"


# Format priority: higher index = higher priority
SEED_FORMAT_PRIORITY: List[SeedFormat] = [SeedFormat.CSV, SeedFormat.DUMP]


@dataclass
class SeedFileInfo:
    """Information about a resolved seed file."""

    path: Path
    format: SeedFormat
    table_name: str
    version: str

    @property
    def exists(self) -> bool:
        """Check if the seed file exists."""
        return self.path.exists()


def get_versions_containing_file(seeds_base_dir: Path, filename: str) -> List[str]:
    """Find all version directories that contain the specified file.

    Args:
        seeds_base_dir: Path to the base seeds directory (e.g., config/seeds/)
        filename: Name of the seed file to search for

    Returns:
        List of version directory names (e.g., ["001", "002"]) containing the file.
        Empty list if no version directories contain the file.
    """
    if not seeds_base_dir.exists():
        return []

    versions = []
    for d in seeds_base_dir.iterdir():
        if d.is_dir() and d.name.isdigit():
            if (d / filename).exists():
                versions.append(d.name)

    return versions


def get_seed_file_path(
    filename: str,
    seeds_base_dir: Path,
    version: Optional[str] = None,
) -> Path:
    """Get path to a seed file using highest version containing that file.

    Scans all numeric version directories and selects the highest one
    that actually contains the specified file. Empty directories are ignored.

    Args:
        filename: Name of the seed CSV file (e.g., "产品线.csv")
        seeds_base_dir: Path to the base seeds directory
        version: Optional explicit version override. If None, uses highest.

    Returns:
        Full path to the seed file.

    Example:
        If 001/ has 产品线.csv and 002/ is empty:
        >>> get_seed_file_path("产品线.csv", Path("config/seeds"))
        Path("config/seeds/001/产品线.csv")

        If 001/ has 年金关联公司.csv and 002/ also has 年金关联公司.csv:
        >>> get_seed_file_path("年金关联公司.csv", Path("config/seeds"))
        Path("config/seeds/002/年金关联公司.csv")
    """
    # Explicit version override
    if version is not None:
        return seeds_base_dir / version / filename

    # Find versions containing this file
    versions_with_file = get_versions_containing_file(seeds_base_dir, filename)

    if versions_with_file:
        highest = max(versions_with_file, key=int)
        return seeds_base_dir / highest / filename

    # Fallback to base directory for backward compatibility
    return seeds_base_dir / filename


def get_latest_seed_version(seeds_base_dir: Path) -> Optional[str]:
    """Find the highest numbered version directory in seeds base.

    Note: This function is kept for backward compatibility but
    get_seed_file_path() is preferred for file-level resolution.

    Args:
        seeds_base_dir: Path to the base seeds directory

    Returns:
        The name of the highest versioned directory (e.g., "002"),
        or None if no version directories exist.
    """
    if not seeds_base_dir.exists():
        return None

    version_dirs = [
        d.name for d in seeds_base_dir.iterdir() if d.is_dir() and d.name.isdigit()
    ]

    if not version_dirs:
        return None

    return max(version_dirs, key=int)


def get_versioned_seeds_dir(seeds_base_dir: Path) -> Path:
    """Get the path to the latest versioned seeds directory.

    Note: This function is kept for backward compatibility but
    get_seed_file_path() is preferred for file-level resolution.

    Args:
        seeds_base_dir: Path to the base seeds directory

    Returns:
        Path to the latest versioned subdirectory, or base directory
        if no version directories exist.
    """
    version = get_latest_seed_version(seeds_base_dir)

    if version is None:
        return seeds_base_dir

    return seeds_base_dir / version


def _find_table_files_in_version(
    seeds_base_dir: Path, version: str, table_name: str
) -> List[tuple[Path, SeedFormat]]:
    """Find all format variants of a table in a specific version directory."""
    version_dir = seeds_base_dir / version
    if not version_dir.exists():
        return []

    found = []
    for fmt in SEED_FORMAT_PRIORITY:
        file_path = version_dir / f"{table_name}{fmt.extension}"
        if file_path.exists():
            found.append((file_path, fmt))

    return found


def resolve_seed_file(  # noqa: PLR0911, PLR0912
    table_name: str,
    seeds_base_dir: Path,
    version: Optional[str] = None,
    preferred_format: Optional[SeedFormat] = None,
) -> Optional[SeedFileInfo]:
    """Resolve seed file for a table with format awareness.

    Searches for seed files across all supported formats and returns
    the best match based on version and format priority.

    Args:
        table_name: Name of the table (without extension)
        seeds_base_dir: Path to the base seeds directory
        version: Optional explicit version override
        preferred_format: Optional format preference override

    Returns:
        SeedFileInfo if found, None otherwise.

    Example:
        >>> info = resolve_seed_file("base_info", Path("config/seeds"))
        >>> if info and info.format == SeedFormat.DUMP:
        ...     # Use pg_restore
        >>> elif info and info.format == SeedFormat.CSV:
        ...     # Use CSV loader
    """
    if not seeds_base_dir.exists():
        return None

    # Get all version directories
    version_dirs = [
        d.name for d in seeds_base_dir.iterdir() if d.is_dir() and d.name.isdigit()
    ]

    if not version_dirs:
        return None

    # If explicit version, search only that version
    if version is not None:
        files = _find_table_files_in_version(seeds_base_dir, version, table_name)
        if not files:
            return None

        # Select by preferred format or highest priority
        if preferred_format:
            for path, fmt in files:
                if fmt == preferred_format:
                    return SeedFileInfo(path, fmt, table_name, version)

        # Return highest priority format
        path, fmt = files[-1]  # Last item has highest priority
        return SeedFileInfo(path, fmt, table_name, version)

    # Search all versions, find highest version with any format
    versions_with_table: dict[str, List[tuple[Path, SeedFormat]]] = {}
    for ver in version_dirs:
        files = _find_table_files_in_version(seeds_base_dir, ver, table_name)
        if files:
            versions_with_table[ver] = files

    if not versions_with_table:
        return None

    # Get highest version
    highest_version = max(versions_with_table.keys(), key=int)
    files = versions_with_table[highest_version]

    # Select by preferred format or highest priority
    if preferred_format:
        for path, fmt in files:
            if fmt == preferred_format:
                return SeedFileInfo(path, fmt, table_name, highest_version)

    # Return highest priority format
    path, fmt = files[-1]
    return SeedFileInfo(path, fmt, table_name, highest_version)
