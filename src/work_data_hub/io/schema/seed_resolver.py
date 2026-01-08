"""Seed version resolution for migration scripts.

This module provides utilities to automatically detect and select
the highest version of seed data files on a per-file basis.

Directory structure expected:
    config/seeds/
    ├── 001/  # Version 1
    │   ├── company_types_classification.csv
    │   ├── 年金客户.csv
    │   └── ...
    ├── 002/  # Version 2 (may have subset of files)
    │   └── 年金客户.csv  # Updated version
    └── README.md

Each file independently resolves to its highest available version.
Empty directories are ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


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

        If 001/ has 年金客户.csv and 002/ also has 年金客户.csv:
        >>> get_seed_file_path("年金客户.csv", Path("config/seeds"))
        Path("config/seeds/002/年金客户.csv")
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
