"""Seed version resolution for migration scripts.

This module provides utilities to automatically detect and select
the highest version of seed data files on a per-file basis.

Directory structure expected:
    config/seeds/
    ├── 001/  # Version 1
    │   ├── company_types_classification.csv
    │   ├── 客户明细.csv
    │   └── ...
    ├── 002/  # Version 2 (may have subset of files)
    │   └── 客户明细.csv  # Updated version
    ├── 003/  # Version 3
    │   ├── base_info.csv
    │   └── enrichment_index.csv
    └── README.md

Each file independently resolves to its highest available version.
Empty directories are ignored.

Supported formats:
    - .csv: Standard CSV files (the only supported format)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class SeedFormat(enum.Enum):
    """Supported seed data formats."""

    CSV = "csv"

    @property
    def extension(self) -> str:
        """Get file extension for this format."""
        return f".{self.value}"


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


def get_versions_containing_file(seeds_base_dir: Path, filename: str) -> list[str]:
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

        If 001/ has 客户明细.csv and 002/ also has 客户明细.csv:
        >>> get_seed_file_path("客户明细.csv", Path("config/seeds"))
        Path("config/seeds/002/客户明细.csv")
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
) -> Optional[tuple[Path, SeedFormat]]:
    """Find CSV file for a table in a specific version directory."""
    version_dir = seeds_base_dir / version
    if not version_dir.exists():
        return None

    file_path = version_dir / f"{table_name}.csv"
    if file_path.exists():
        return (file_path, SeedFormat.CSV)

    return None


def resolve_seed_file(
    table_name: str,
    seeds_base_dir: Path,
    version: Optional[str] = None,
    preferred_format: Optional[SeedFormat] = None,
) -> Optional[SeedFileInfo]:
    """Resolve seed file for a table.

    Searches for CSV seed files and returns the best match
    based on version (highest version wins).

    Args:
        table_name: Name of the table (without extension)
        seeds_base_dir: Path to the base seeds directory
        version: Optional explicit version override
        preferred_format: Ignored (kept for API compatibility)

    Returns:
        SeedFileInfo if found, None otherwise.
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
        result = _find_table_files_in_version(seeds_base_dir, version, table_name)
        if result is None:
            return None
        path, fmt = result
        return SeedFileInfo(path, fmt, table_name, version)

    # Search all versions, find highest version with the file
    versions_with_table: dict[str, tuple[Path, SeedFormat]] = {}
    for ver in version_dirs:
        result = _find_table_files_in_version(seeds_base_dir, ver, table_name)
        if result is not None:
            versions_with_table[ver] = result

    if not versions_with_table:
        return None

    # Get highest version
    highest_version = max(versions_with_table.keys(), key=int)
    path, fmt = versions_with_table[highest_version]
    return SeedFileInfo(path, fmt, table_name, highest_version)
