"""Validation report generation utilities.

This module provides functions for exporting validation errors and summaries
to CSV files with metadata headers for debugging and data quality analysis.

Key Functions:
- export_error_csv: Export failed rows to CSV with metadata header
- export_validation_summary: Export comprehensive validation summary

Usage:
    >>> from work_data_hub.infrastructure.validation import (
    ...     export_error_csv,
    ...     export_validation_summary,
    ... )
    >>>
    >>> # Export failed rows
    >>> csv_path = export_error_csv(failed_df, filename_prefix="bronze_validation")
    >>>
    >>> # Export summary report
    >>> summary_path = export_validation_summary(
    ...     total_rows=1000,
    ...     failed_rows=50,
    ...     error_details=errors,
    ...     domain="annuity_performance",
    ...     duration_seconds=8.5,
    ... )
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence

from work_data_hub.infrastructure.validation.types import ValidationErrorDetail

if TYPE_CHECKING:
    import pandas as pd


def export_error_csv(
    failed_rows: "pd.DataFrame",
    filename_prefix: str = "validation_errors",
    output_dir: Optional[Path] = None,
) -> Path:
    """Export failed rows to CSV in standard log directory.

    Creates a timestamped CSV file containing the rows that failed validation,
    with a metadata header for context.

    Args:
        failed_rows: DataFrame containing rows that failed validation
        filename_prefix: Prefix for output filename (timestamp appended)
        output_dir: Output directory (defaults to logs/)

    Returns:
        Path to generated CSV file

    CSV Format:
        # Validation Errors Export
        # Date: 2025-12-02T10:30:00
        # Total Failed Rows: 50
        [original DataFrame columns as CSV]

    Example:
        >>> import pandas as pd
        >>> failed_df = pd.DataFrame({'col1': [1, 2], 'col2': ['a', 'b']})
        >>> csv_path = export_error_csv(failed_df, filename_prefix="bronze_errors")
        >>> csv_path.exists()
        True
    """
    # Default to logs directory
    if output_dir is None:
        output_dir = Path("logs")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    filepath = output_dir / filename

    # Write CSV with metadata header
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Write metadata header
        f.write("# Validation Errors Export\n")
        f.write(f"# Date: {datetime.now().isoformat()}\n")
        f.write(f"# Total Failed Rows: {len(failed_rows)}\n")

        # Write DataFrame as CSV
        failed_rows.to_csv(f, index=True, lineterminator="\n")

    return filepath


def export_error_details_csv(
    error_details: Sequence[ValidationErrorDetail],
    filename_prefix: str = "validation_error_details",
    output_dir: Optional[Path] = None,
    domain: str = "unknown",
    total_rows: int = 0,
    duration_seconds: float = 0.0,
) -> Path:
    """Export validation error details to CSV with metadata header.

    Creates a timestamped CSV file containing structured error details
    with row-level attribution for debugging.

    Args:
        error_details: Sequence of ValidationErrorDetail objects
        filename_prefix: Prefix for output filename (timestamp appended)
        output_dir: Output directory (defaults to logs/)
        domain: Domain name for metadata (e.g., 'annuity_performance')
        total_rows: Total number of rows processed
        duration_seconds: Validation duration in seconds

    Returns:
        Path to generated CSV file

    CSV Format:
        # Validation Errors Export
        # Date: 2025-12-02T10:30:00
        # Domain: annuity_performance
        # Total Rows: 10000
        # Failed Rows: 50
        # Error Rate: 0.5%
        # Validation Duration: 8.5s
        row_index,field_name,error_type,error_message,original_value
        15,月度,ValueError,"Cannot parse 'INVALID' as date",INVALID
        ...

    Example:
        >>> errors = [ValidationErrorDetail(15, '月度', 'ValueError', 'Bad date', 'X')]
        >>> csv_path = export_error_details_csv(errors, domain="annuity")
        >>> csv_path.exists()
        True
    """
    # Default to logs directory
    if output_dir is None:
        output_dir = Path("logs")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    filepath = output_dir / filename

    # Calculate statistics
    failed_row_indices = {e.row_index for e in error_details if e.row_index is not None}
    failed_rows = len(failed_row_indices)
    error_rate = failed_rows / total_rows if total_rows > 0 else 0.0

    # Write CSV with metadata header
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Write metadata header
        f.write("# Validation Errors Export\n")
        f.write(f"# Date: {datetime.now().isoformat()}\n")
        f.write(f"# Domain: {domain}\n")
        f.write(f"# Total Rows: {total_rows}\n")
        f.write(f"# Failed Rows: {failed_rows}\n")
        f.write(f"# Error Rate: {error_rate:.1%}\n")
        f.write(f"# Validation Duration: {duration_seconds:.1f}s\n")

        # Write CSV data
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "row_index",
                "field_name",
                "error_type",
                "error_message",
                "original_value",
            ],
        )
        writer.writeheader()

        for error in error_details:
            writer.writerow(
                {
                    "row_index": error.row_index if error.row_index is not None else "",
                    "field_name": error.field_name,
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "original_value": _sanitize_value(error.original_value),
                }
            )

    return filepath


def export_validation_summary(
    total_rows: int,
    failed_rows: int,
    error_details: Sequence[ValidationErrorDetail],
    domain: str,
    duration_seconds: float,
    output_dir: Optional[Path] = None,
) -> Path:
    """Export comprehensive validation summary with error breakdown.

    Creates a timestamped summary file containing validation statistics
    and error breakdown by field and error type.

    Args:
        total_rows: Total number of rows processed
        failed_rows: Number of rows that failed validation
        error_details: Sequence of ValidationErrorDetail objects
        domain: Domain name (e.g., 'annuity_performance')
        duration_seconds: Validation duration in seconds
        output_dir: Output directory (defaults to logs/)

    Returns:
        Path to generated summary file

    Example:
        >>> errors = [ValidationErrorDetail(15, '月度', 'ValueError', 'Bad', 'X')]
        >>> path = export_validation_summary(100, 1, errors, "annuity", 1.5)
        >>> path.exists()
        True
    """
    # Default to logs directory
    if output_dir is None:
        output_dir = Path("logs")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"validation_summary_{domain}_{timestamp}.txt"
    filepath = output_dir / filename

    # Calculate statistics
    error_rate = failed_rows / total_rows if total_rows > 0 else 0.0
    valid_rows = total_rows - failed_rows

    # Group errors by field
    errors_by_field: dict[str, int] = {}
    errors_by_type: dict[str, int] = {}
    for error in error_details:
        errors_by_field[error.field_name] = errors_by_field.get(error.field_name, 0) + 1
        errors_by_type[error.error_type] = errors_by_type.get(error.error_type, 0) + 1

    # Write summary
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("VALIDATION SUMMARY REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Domain: {domain}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Duration: {duration_seconds:.2f}s\n\n")

        f.write("-" * 40 + "\n")
        f.write("STATISTICS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Rows:    {total_rows:,}\n")
        f.write(f"Valid Rows:    {valid_rows:,}\n")
        f.write(f"Failed Rows:   {failed_rows:,}\n")
        f.write(f"Error Count:   {len(error_details):,}\n")
        f.write(f"Error Rate:    {error_rate:.2%}\n\n")

        if errors_by_field:
            f.write("-" * 40 + "\n")
            f.write("ERRORS BY FIELD\n")
            f.write("-" * 40 + "\n")
            for field, count in sorted(
                errors_by_field.items(), key=lambda x: x[1], reverse=True
            ):
                f.write(f"  {field}: {count:,}\n")
            f.write("\n")

        if errors_by_type:
            f.write("-" * 40 + "\n")
            f.write("ERRORS BY TYPE\n")
            f.write("-" * 40 + "\n")
            for error_type, count in sorted(
                errors_by_type.items(), key=lambda x: x[1], reverse=True
            ):
                f.write(f"  {error_type}: {count:,}\n")
            f.write("\n")

        f.write("=" * 60 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 60 + "\n")

    return filepath


def _sanitize_value(value: Any) -> str:
    """Sanitize value for safe CSV export.

    Rules:
    - Convert None to "NULL"
    - Convert all values to string
    - Remove newlines and tabs (replace with space)
    - Truncate long strings (>100 chars) to 97 chars + "..."

    Args:
        value: Raw value from validation failure

    Returns:
        Sanitized string safe for CSV export

    Example:
        >>> _sanitize_value(None)
        'NULL'
        >>> _sanitize_value('A' * 150)
        'AAAAAAA...AAA...'
        >>> _sanitize_value('Line1\\nLine2')
        'Line1 Line2'
    """
    if value is None:
        return "NULL"

    # Convert to string
    str_value = str(value)

    # Remove newlines and tabs
    str_value = str_value.replace("\n", " ").replace("\t", " ")

    # Truncate long values
    if len(str_value) > 100:
        str_value = str_value[:97] + "..."

    return str_value


__all__ = [
    "export_error_csv",
    "export_error_details_csv",
    "export_validation_summary",
]
