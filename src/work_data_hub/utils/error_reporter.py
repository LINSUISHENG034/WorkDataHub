"""Validation error collection and reporting.

This module provides utilities for collecting validation errors across
multiple validation layers (Bronze/Silver/Gold) and exporting them to CSV
with actionable error messages.

Usage:
    >>> reporter = ValidationErrorReporter()
    >>> reporter.collect_error(
    ...     row_index=15,
    ...     field_name='月度',
    ...     error_type='ValueError',
    ...     error_message="Cannot parse 'INVALID' as date",
    ...     original_value='INVALID'
    ... )
    >>> summary = reporter.get_summary(total_rows=100)
    >>> reporter.export_to_csv(Path('logs/failed_rows.csv'), 100, 'annuity', 10.5)
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Set


@dataclass
class ValidationError:
    """Single validation error record.

    Attributes:
        row_index: 0-indexed row number in DataFrame
        field_name: Name of field that failed validation
        error_type: Type of error (ValueError, SchemaError, ValidationError)
        error_message: Human-readable error description
        original_value: Sanitized raw value that failed validation
    """

    row_index: int
    field_name: str
    error_type: str
    error_message: str
    original_value: str  # Already sanitized


@dataclass
class ValidationSummary:
    """Aggregated validation statistics.

    Attributes:
        total_rows: Total number of rows processed
        valid_rows: Number of rows that passed validation
        failed_rows: Number of rows that failed validation (unique row indices)
        error_count: Total number of errors (can be > failed_rows if multiple errors per row)
        error_rate: Ratio of failed rows to total rows (0.0 to 1.0)
    """

    total_rows: int
    valid_rows: int
    failed_rows: int
    error_count: int
    error_rate: float


class ValidationThresholdExceeded(Exception):
    """Raised when validation error rate exceeds acceptable threshold.

    This indicates a likely systemic data quality issue that requires
    investigation before proceeding with the pipeline.
    """

    pass


class ValidationErrorReporter:
    """Collect and export validation errors with actionable feedback.

    This reporter aggregates validation errors from multiple validation layers
    (Bronze Pandera schemas, Silver Pydantic models, Gold schemas) and provides
    CSV export with error details for data quality debugging.

    Features:
    - Collects errors with row-level attribution
    - Tracks unique failed rows (prevents double-counting)
    - Enforces error rate thresholds (default 10%)
    - Exports to CSV with metadata header
    - Sanitizes values for safe CSV export

    Example:
        >>> reporter = ValidationErrorReporter()
        >>> # Collect errors from validation layers
        >>> reporter.collect_error(15, '月度', 'ValueError', 'Invalid date', 'BAD')
        >>> reporter.collect_error(23, '期末资产规模', 'ValueError', 'Negative', -1000)
        >>>
        >>> # Check if error rate is acceptable
        >>> reporter.check_threshold(total_rows=100)  # Raises if >= 10%
        >>>
        >>> # Get summary statistics
        >>> summary = reporter.get_summary(total_rows=100)
        >>> print(f"Error rate: {summary.error_rate:.1%}")
        >>>
        >>> # Export failed rows to CSV
        >>> csv_path = Path('logs/failed_rows_20251127_103000.csv')
        >>> reporter.export_to_csv(csv_path, 100, 'annuity_performance', 8.5)
    """

    def __init__(self) -> None:
        """Initialize empty error reporter."""
        self.errors: List[ValidationError] = []
        self._failed_row_indices: Set[int] = set()

    def collect_error(
        self,
        row_index: int,
        field_name: str,
        error_type: str,
        error_message: str,
        original_value: Any,
    ) -> None:
        """Add validation error to collection.

        Args:
            row_index: 0-indexed row number in DataFrame
            field_name: Name of field that failed validation
            error_type: Type of error (ValueError, SchemaError, ValidationError)
            error_message: Human-readable error description
            original_value: Raw value that failed (will be sanitized)

        Example:
            >>> reporter = ValidationErrorReporter()
            >>> reporter.collect_error(
            ...     row_index=15,
            ...     field_name='月度',
            ...     error_type='ValueError',
            ...     error_message="Cannot parse 'INVALID' as date",
            ...     original_value='INVALID'
            ... )
            >>> len(reporter.errors)
            1
        """
        sanitized_value = self._sanitize_value(original_value)

        self.errors.append(
            ValidationError(
                row_index=row_index,
                field_name=field_name,
                error_type=error_type,
                error_message=error_message,
                original_value=sanitized_value,
            )
        )
        self._failed_row_indices.add(row_index)

    def get_summary(self, total_rows: int) -> ValidationSummary:
        """Return aggregated validation statistics.

        Args:
            total_rows: Total number of rows processed

        Returns:
            ValidationSummary with error statistics

        Example:
            >>> reporter = ValidationErrorReporter()
            >>> reporter.collect_error(10, 'field', 'type', 'msg', 'val')
            >>> reporter.collect_error(20, 'field', 'type', 'msg', 'val')
            >>> summary = reporter.get_summary(total_rows=100)
            >>> summary.failed_rows
            2
            >>> summary.error_rate
            0.02
        """
        failed_rows = len(self._failed_row_indices)
        valid_rows = total_rows - failed_rows
        error_rate = failed_rows / total_rows if total_rows > 0 else 0.0

        return ValidationSummary(
            total_rows=total_rows,
            valid_rows=valid_rows,
            failed_rows=failed_rows,
            error_count=len(self.errors),
            error_rate=error_rate,
        )

    def check_threshold(
        self, total_rows: int, threshold: float = 0.10
    ) -> None:
        """Raise exception if error rate exceeds threshold.

        Args:
            total_rows: Total number of rows processed
            threshold: Maximum acceptable error rate (default 10%)

        Raises:
            ValidationThresholdExceeded: If error rate >= threshold

        Example:
            >>> reporter = ValidationErrorReporter()
            >>> # 9% error rate - under threshold
            >>> for i in range(9):
            ...     reporter.collect_error(i, 'f', 't', 'm', 'v')
            >>> reporter.check_threshold(total_rows=100)  # No exception
            >>>
            >>> # 15% error rate - exceeds threshold
            >>> for i in range(15):
            ...     reporter.collect_error(i, 'f', 't', 'm', 'v')
            >>> reporter.check_threshold(total_rows=100)  # Raises!
            Traceback (most recent call last):
                ...
            ValidationThresholdExceeded: Validation failure rate 15.0% exceeds threshold 10.0%...
        """
        summary = self.get_summary(total_rows)

        if summary.error_rate >= threshold:
            raise ValidationThresholdExceeded(
                f"Validation failure rate {summary.error_rate:.1%} exceeds "
                f"threshold {threshold:.1%}, likely systemic issue. "
                f"Failed {summary.failed_rows}/{total_rows} rows."
            )

    def export_to_csv(
        self,
        filepath: Path,
        total_rows: int,
        domain: str,
        duration_seconds: float,
    ) -> None:
        """Export errors to CSV with metadata header.

        CSV Format:
            # Validation Errors Export
            # Date: 2025-11-27T10:30:00Z
            # Domain: annuity_performance
            # Total Rows: 10000
            # Failed Rows: 50
            # Error Rate: 0.5%
            # Validation Duration: 8.5s
            row_index,field_name,error_type,error_message,original_value
            15,月度,ValueError,"Cannot parse 'INVALID' as date",INVALID
            23,期末资产规模,ValueError,"Value must be >= 0",-1000.50
            ...

        Args:
            filepath: Output CSV file path
            total_rows: Total number of rows processed
            domain: Domain name (e.g., 'annuity_performance')
            duration_seconds: Validation duration in seconds

        Example:
            >>> reporter = ValidationErrorReporter()
            >>> reporter.collect_error(15, '月度', 'ValueError', 'Bad date', 'INVALID')
            >>> csv_path = Path('logs/test_errors.csv')
            >>> reporter.export_to_csv(csv_path, 100, 'annuity', 10.5)
            >>> csv_path.exists()
            True
        """
        summary = self.get_summary(total_rows)

        # Create output directory if it doesn't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            # Write metadata header
            f.write("# Validation Errors Export\n")
            f.write(f"# Date: {datetime.now().isoformat()}\n")
            f.write(f"# Domain: {domain}\n")
            f.write(f"# Total Rows: {total_rows}\n")
            f.write(f"# Failed Rows: {summary.failed_rows}\n")
            f.write(f"# Error Rate: {summary.error_rate:.1%}\n")
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

            for error in self.errors:
                writer.writerow(
                    {
                        "row_index": error.row_index,
                        "field_name": error.field_name,
                        "error_type": error.error_type,
                        "error_message": error.error_message,
                        "original_value": error.original_value,
                    }
                )

    def _sanitize_value(self, value: Any) -> str:
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
            >>> reporter = ValidationErrorReporter()
            >>> reporter._sanitize_value(None)
            'NULL'
            >>> reporter._sanitize_value('A' * 150)
            'AAAA...AAA...'
            >>> reporter._sanitize_value('Line1\\nLine2')
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
