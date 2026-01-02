"""Failed record data model and error type enumeration.

This module provides the core data structures for unified failure logging
across all ETL domains, enabling session-based consolidation of validation
errors, pipeline drops, and enrichment failures.

Story: 7.5-5-unified-failed-records-logging
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ErrorType(str, Enum):
    """Standard error type categories for unified logging.

    Prevents typos and enables consistent error categorization across domains.
    Maps exception types to high-level error categories for analysis.

    Values:
        VALIDATION_FAILED: Schema validation errors (pandera, pydantic)
        DROPPED_IN_PIPELINE: Rows removed during DataFrame transforms
        ENRICHMENT_FAILED: Company ID resolution failures
        FK_CONSTRAINT_VIOLATION: Foreign key constraint violations
    """

    VALIDATION_FAILED = "VALIDATION_FAILED"
    DROPPED_IN_PIPELINE = "DROPPED_IN_PIPELINE"
    ENRICHMENT_FAILED = "ENRICHMENT_FAILED"
    FK_CONSTRAINT_VIOLATION = "FK_CONSTRAINT_VIOLATION"


@dataclass(frozen=True)
class FailedRecord:
    """Immutable record of a failed ETL row for unified logging.

    Designed for CSV export with standardized schema across all domains.
    Frozen dataclass ensures data integrity after creation.

    Attributes:
        session_id: ETL session identifier (format: etl_YYYYMMDD_HHMMSS_xxxxxx)
        timestamp: ISO-8601 timestamp of failure detection
        domain: Business domain name (e.g., 'annuity_performance')
        source_file: Source filename where failure occurred
        row_index: Row number in source file (0-based or 1-based)
        error_type: Error category from ErrorType enum
        raw_data: Serialized raw row data as JSON string

    Example:
        >>> record = FailedRecord(
        ...     session_id="etl_20260102_181530_a1b2c3",
        ...     timestamp="2026-01-02T18:15:30.123456",
        ...     domain="annuity_performance",
        ...     source_file="data.xlsx",
        ...     row_index=42,
        ...     error_type=ErrorType.VALIDATION_FAILED,
        ...     raw_data='{"col1": "value1", "col2": 123}',
        ... )
        >>> record.to_dict()
        {'session_id': 'etl_20260102_181530_a1b2c3', ...}
    """

    session_id: str
    timestamp: str
    domain: str
    source_file: str
    row_index: int
    error_type: str
    raw_data: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for CSV export.

        Returns:
            Dictionary with all field names and values

        Example:
            >>> record = FailedRecord(...)
            >>> dict_repr = record.to_dict()
            >>> csv_writer.writerow(dict_repr)
        """
        return asdict(self)

    @classmethod
    def from_validation_error(
        cls,
        session_id: str,
        domain: str,
        source_file: str,
        row_index: int,
        error_type: ErrorType,
        raw_row: dict[str, Any],
    ) -> "FailedRecord":
        """Factory method to create FailedRecord from validation error.

        Automates timestamp generation and JSON serialization for consistent
        failure record creation across domain services.

        Args:
            session_id: ETL session identifier
            domain: Business domain name
            source_file: Source filename
            row_index: Row number in source
            error_type: Error category from ErrorType enum
            raw_row: Raw row data as dictionary (will be JSON-serialized)

        Returns:
            Frozen FailedRecord instance with current timestamp

        Example:
            >>> record = FailedRecord.from_validation_error(
            ...     session_id="etl_20260102_181530_a1b2c3",
            ...     domain="annuity_performance",
            ...     source_file="data.xlsx",
            ...     row_index=42,
            ...     error_type=ErrorType.VALIDATION_FAILED,
            ...     raw_row={"月度": "202401", "规模": 1000},
            ... )
        """
        return cls(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            domain=domain,
            source_file=source_file,
            row_index=row_index,
            error_type=error_type.value,
            raw_data=json.dumps(raw_row, ensure_ascii=False, default=str),
        )


__all__ = [
    "ErrorType",
    "FailedRecord",
]
