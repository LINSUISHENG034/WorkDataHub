"""Session-based failure record exporter with unified CSV schema.

This module provides centralized failure logging infrastructure for ETL jobs,
consolidating validation errors from all domains into a single session-based CSV
file with standardized schema for analysis and debugging.

Story: 7.5-5-unified-failed-records-logging
"""

from __future__ import annotations

import csv
import secrets
from datetime import datetime
from pathlib import Path

from work_data_hub.infrastructure.validation.failed_record import FailedRecord


def generate_session_id() -> str:
    r"""Generate unique session ID for ETL execution.

    Called from CLI layer at startup, passed through to domain services for
    unified failure logging. Ensures all failures from a single ETL run are
    grouped together.

    Format: etl_{YYYYMMDD_HHMMSS}_{random_6chars}
    Example: etl_20260102_181530_a1b2c3

    Returns:
        Unique session identifier string

    Note:
        Uses secrets.token_hex() for cryptographic randomness instead of
        random.random() to prevent collision in high-frequency ETL runs.
        6 hex characters = 3 bytes = 24 bits of entropy (16M combinations).

    Example:
        >>> from work_data_hub.infrastructure.validation import generate_session_id
        >>> session_id = generate_session_id()
        >>> assert session_id.startswith("etl_")
        >>> assert re.match(r'^etl_\d{8}_\d{6}_[a-f0-9]{6}$', session_id)  # noqa: W605
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = secrets.token_hex(3)  # 6 hex chars
    return f"etl_{timestamp}_{random_suffix}"


class FailureExporter:
    """Session-based failure record exporter with append mode support.

    Manages CSV export for failed records across multiple domains in a single
    ETL session. Supports append mode for multi-domain batch runs, writing
    header only on first export.

    Attributes:
        session_id: ETL session identifier (from generate_session_id())
        output_dir: Output directory for failure CSV (default: logs/)
        output_file: Full path to session-specific CSV file

    Example:
        >>> exporter = FailureExporter("etl_20260102_181530_a1b2c3")
        >>> records = [FailedRecord(...)]
        >>> csv_path = exporter.export(records)
        >>> print(csv_path)
        Path('logs/wdh_etl_failures_etl_20260102_181530_a1b2c3.csv')
    """

    FIELDNAMES = [
        "session_id",
        "timestamp",
        "domain",
        "source_file",
        "row_index",
        "error_type",
        "raw_data",
    ]

    def __init__(self, session_id: str, output_dir: Path = Path("logs")) -> None:
        """Initialize exporter with session ID and output directory.

        Args:
            session_id: ETL session identifier from generate_session_id()
            output_dir: Output directory (default: logs/)

        Raises:
            ValueError: If session_id is empty or invalid format
        """
        if not session_id:
            msg = "session_id cannot be empty"
            raise ValueError(msg)

        self.session_id = session_id
        self.output_dir = output_dir
        self.output_file = output_dir / f"wdh_etl_failures_{session_id}.csv"

    def export(self, records: list[FailedRecord]) -> Path:
        """Export failed records to CSV with append mode.

        Header is written only if file doesn't exist (AC-4). Supports multi-
        domain batch runs by appending to existing session file.

        Args:
            records: List of FailedRecord objects to export

        Returns:
            Path to generated CSV file

        Note:
            - Creates output directory if it doesn't exist (AC-6)
            - Append mode: multiple calls write to same file
            - Header written only on first export (file existence check)

        Example:
            >>> exporter = FailureExporter("etl_20260102_181530_a1b2c3")
            >>> records1 = [FailedRecord(...)]  # Domain 1 failures
            >>> path1 = exporter.export(records1)  # Writes header + data
            >>> records2 = [FailedRecord(...)]  # Domain 2 failures
            >>> path2 = exporter.export(records2)  # Appends data only
            >>> assert path1 == path2
        """
        self._ensure_directory()
        file_exists = self.output_file.exists()

        # Use utf-8-sig (with BOM) for new files, utf-8 for appending
        # This ensures Windows apps correctly detect Chinese encoding
        encoding = "utf-8" if file_exists else "utf-8-sig"
        with open(self.output_file, "a", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())

        return self.output_file

    def _ensure_directory(self) -> None:
        """Create output directory if it doesn't exist (AC-6).

        Uses pathlib.Path.mkdir() with parents=True and exist_ok=True to
        create full directory tree and ignore errors if directory exists.

        Example:
            >>> exporter = FailureExporter("etl_20260102_181530_a1b2c3")
            >>> exporter._ensure_directory()  # Creates logs/ if needed
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)


__all__ = [
    "generate_session_id",
    "FailureExporter",
]
