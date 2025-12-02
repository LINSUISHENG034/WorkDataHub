"""Validation types and exceptions for infrastructure layer.

This module defines shared types used across validation utilities:
- ValidationErrorDetail: Structured validation error for consistent handling
- ValidationSummary: Aggregated validation statistics
- ValidationThresholdExceeded: Exception for threshold violations

These types provide a consistent interface for validation error handling
across Pandera (DataFrame) and Pydantic (row-level) validation layers.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ValidationErrorDetail:
    """Structured validation error for consistent handling.

    This dataclass provides a unified format for validation errors from
    multiple sources (Pandera SchemaErrors, Pydantic ValidationError, etc.).

    Attributes:
        row_index: 0-indexed row number in DataFrame (None for schema-level errors)
        field_name: Name of field that failed validation
        error_type: Type of error (e.g., 'ValueError', 'SchemaError', 'type_error')
        error_message: Human-readable error description
        original_value: Raw value that failed validation (Any type, sanitized on export)

    Example:
        >>> error = ValidationErrorDetail(
        ...     row_index=15,
        ...     field_name='月度',
        ...     error_type='ValueError',
        ...     error_message="Cannot parse 'INVALID' as date",
        ...     original_value='INVALID'
        ... )
    """

    row_index: Optional[int]
    field_name: str
    error_type: str
    error_message: str
    original_value: Any


@dataclass
class ValidationSummary:
    """Aggregated validation statistics.

    Attributes:
        total_rows: Total number of rows processed
        valid_rows: Number of rows that passed validation
        failed_rows: Number of rows that failed validation (unique row indices)
        error_count: Total errors (can exceed failed_rows if multiple per row)
        error_rate: Ratio of failed rows to total rows (0.0 to 1.0)

    Example:
        >>> summary = ValidationSummary(
        ...     total_rows=1000,
        ...     valid_rows=950,
        ...     failed_rows=50,
        ...     error_count=75,
        ...     error_rate=0.05
        ... )
        >>> print(f"Error rate: {summary.error_rate:.1%}")
        Error rate: 5.0%
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

    Attributes:
        error_rate: The actual error rate that exceeded the threshold
        threshold: The configured threshold that was exceeded
        failed_rows: Number of rows that failed validation
        total_rows: Total number of rows processed

    Example:
        >>> raise ValidationThresholdExceeded(
        ...     "Validation failure rate 15.0% exceeds threshold 10.0%",
        ...     error_rate=0.15,
        ...     threshold=0.10,
        ...     failed_rows=150,
        ...     total_rows=1000
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        error_rate: float = 0.0,
        threshold: float = 0.0,
        failed_rows: int = 0,
        total_rows: int = 0,
    ) -> None:
        """Initialize ValidationThresholdExceeded exception.

        Args:
            message: Human-readable error message
            error_rate: The actual error rate that exceeded the threshold
            threshold: The configured threshold that was exceeded
            failed_rows: Number of rows that failed validation
            total_rows: Total number of rows processed
        """
        super().__init__(message)
        self.error_rate = error_rate
        self.threshold = threshold
        self.failed_rows = failed_rows
        self.total_rows = total_rows


__all__ = [
    "ValidationErrorDetail",
    "ValidationSummary",
    "ValidationThresholdExceeded",
]
