"""
Core types and utilities for WorkDataHub.

This module defines the fundamental data types and helper functions used across
the WorkDataHub platform for file discovery and metadata extraction.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class DiscoveredFile:
    """
    Represents a discovered data file with extracted metadata.

    This class encapsulates information about files found during the discovery
    process, including domain classification, file path, and extracted metadata
    such as year/month from filename patterns.

    Args:
        domain: The business domain this file belongs to (e.g., 'trustee_performance')
        path: Full filesystem path to the discovered file
        year: Year extracted from filename pattern (None if not extractable)
        month: Month extracted from filename pattern (None if not extractable)
        metadata: Additional metadata dictionary from regex groups and file stats
    """

    domain: str
    path: str
    year: Optional[int]
    month: Optional[int]
    metadata: Dict[str, Any]


def extract_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract filesystem metadata from a file path.

    Args:
        file_path: Path to the file to analyze

    Returns:
        Dictionary containing file metadata (size, mtime, etc.)

    Raises:
        OSError: If file cannot be accessed or does not exist
    """
    try:
        path = Path(file_path)
        stat = path.stat()

        return {
            "size_bytes": stat.st_size,
            "modified_time": stat.st_mtime,
            "created_time": stat.st_ctime,
            "filename": path.name,
            "extension": path.suffix,
            "directory": str(path.parent),
        }
    except (OSError, FileNotFoundError) as e:
        raise OSError(f"Cannot extract metadata from file {file_path}: {e}")


def validate_excel_file(file_path: str) -> bool:
    """
    Validate that a file is a readable Excel file.

    Performs basic validation to ensure the file exists, has a valid Excel
    extension, and is accessible for reading.

    Args:
        file_path: Path to the file to validate

    Returns:
        True if file appears to be a valid Excel file, False otherwise
    """
    try:
        path = Path(file_path)

        # Check file exists and is readable
        if not path.exists() or not path.is_file():
            return False

        # Check for Excel extensions
        valid_extensions = {".xlsx", ".xls", ".xlsm", ".xlsb"}
        if path.suffix.lower() not in valid_extensions:
            return False

        # Check file is not zero bytes
        if path.stat().st_size == 0:
            return False

        return True

    except (OSError, FileNotFoundError):
        return False


def is_temporary_file(filename: str) -> bool:
    """
    Check if a filename indicates a temporary or backup file.

    Identifies common patterns for temporary files that should be ignored
    during file discovery (e.g., Excel temp files, backup files).

    Args:
        filename: Name of the file to check

    Returns:
        True if file appears to be temporary, False otherwise
    """
    filename_lower = filename.lower()

    # Excel temporary files
    if filename_lower.startswith("~$"):
        return True

    # Backup files
    if filename_lower.endswith((".bak", ".tmp", ".temp")):
        return True

    # Email files (often mixed with data files)
    if filename_lower.endswith(".eml"):
        return True

    # Hidden files
    if filename.startswith("."):
        return True

    return False
