"""
CSV export utilities for annuity performance domain.

This module provides functions for exporting enrichment-related data to CSV files,
supporting manual review workflows and data analysis. All exports use UTF-8 encoding
to properly handle Chinese characters in company names.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from work_data_hub.config.settings import get_settings

logger = logging.getLogger(__name__)


def write_unknowns_csv(
    unknown_names: List[str], data_source: str, output_dir: Optional[str] = None
) -> str:
    """
    Export unknown company names to CSV file for manual review.

    Creates a CSV file containing unique unknown company names that could not be
    resolved through internal mappings or EQC lookups. The file includes
    timestamps and data source information for tracking and analysis.

    Args:
        unknown_names: List of company names that could not be resolved
        data_source: Source file or identifier for tracking
        output_dir: Optional output directory (uses settings data_base_dir if None)

    Returns:
        Path to the generated CSV file

    Raises:
        IOError: If file creation fails
        ValueError: If unknown_names is empty

    Examples:
        >>> names = ["未知公司A", "Unknown Company B", "测试企业"]
        >>> csv_path = write_unknowns_csv(names, "2024年11月年金终稿数据.xlsx")
        >>> print(f"Unknown names exported to: {csv_path}")
    """
    if not unknown_names:
        raise ValueError("Cannot export empty unknown names list")

    # Remove duplicates while preserving order
    unique_names = list(dict.fromkeys(unknown_names))

    # Determine output directory
    if output_dir is None:
        settings = get_settings()
        output_dir = settings.data_base_dir

    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize data source for filename
    safe_source = _sanitize_filename(data_source)
    filename = f"unknown_companies_{safe_source}_{timestamp}.csv"
    csv_path = output_path / filename

    logger.info(
        "Exporting unknown company names to CSV",
        extra={
            "unknown_count": len(unique_names),
            "data_source": data_source,
            "output_path": str(csv_path),
        },
    )

    try:
        # Write CSV with UTF-8 encoding for Chinese character support
        with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Write header row
            writer.writerow(
                ["company_name", "data_source", "export_timestamp", "notes"]
            )

            # Write data rows
            export_timestamp = datetime.now().isoformat()
            for name in unique_names:
                writer.writerow(
                    [
                        name,
                        data_source,
                        export_timestamp,
                        "Requires manual company ID mapping",
                    ]
                )

        logger.info(
            "Successfully exported unknown company names",
            extra={
                "exported_count": len(unique_names),
                "file_path": str(csv_path),
                "file_size_bytes": csv_path.stat().st_size,
            },
        )

        return str(csv_path)

    except Exception as e:
        logger.error(f"Failed to export unknown company names CSV: {e}")
        raise IOError(f"CSV export failed: {e}") from e


def read_unknowns_csv(csv_path: str) -> List[str]:
    """
    Read unknown company names from previously exported CSV file.

    Utility function for loading previously exported unknown names for
    analysis or batch processing workflows.

    Args:
        csv_path: Path to the CSV file to read

    Returns:
        List of company names from the CSV file

    Raises:
        FileNotFoundError: If CSV file does not exist
        IOError: If file reading fails

    Examples:
        >>> names = read_unknowns_csv("unknown_companies_20241101_143022.csv")
        >>> print(f"Loaded {len(names)} unknown company names")
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logger.debug(f"Reading unknown company names from: {csv_path}")

    try:
        company_names = []
        with open(csv_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                if "company_name" in row and row["company_name"]:
                    company_names.append(row["company_name"].strip())

        logger.debug(f"Loaded {len(company_names)} company names from CSV")
        return company_names

    except Exception as e:
        logger.error(f"Failed to read unknown company names CSV: {e}")
        raise IOError(f"CSV reading failed: {e}") from e


def _sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Sanitize filename by removing special characters and limiting length.

    Args:
        filename: Original filename or data source identifier
        max_length: Maximum length for sanitized filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    import re

    # Remove file extension if present
    name = Path(filename).stem

    # Replace special characters with underscores
    sanitized = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)

    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # Ensure we have a valid filename
    return sanitized if sanitized else "unknown_source"
