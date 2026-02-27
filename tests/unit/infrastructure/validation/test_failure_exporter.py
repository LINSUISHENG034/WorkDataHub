"""Unit tests for unified failure logging infrastructure.

Tests the FailedRecord dataclass, ErrorType enum, FailureExporter class,
and session_id generation functionality.

Story: 7.5-5-unified-failed-records-logging
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from work_data_hub.infrastructure.validation import (
    ErrorType,
    FailedRecord,
    FailureExporter,
    export_failed_records,
    generate_session_id,
)


class TestErrorType:
    """Test ErrorType enum values and properties."""

    def test_error_type_values(self) -> None:
        """ErrorType enum should have all required values."""
        assert ErrorType.VALIDATION_FAILED == "VALIDATION_FAILED"
        assert ErrorType.DROPPED_IN_PIPELINE == "DROPPED_IN_PIPELINE"
        assert ErrorType.ENRICHMENT_FAILED == "ENRICHMENT_FAILED"
        assert ErrorType.FK_CONSTRAINT_VIOLATION == "FK_CONSTRAINT_VIOLATION"

    def test_error_type_is_string_enum(self) -> None:
        """ErrorType should be a string enum for JSON serialization."""
        assert isinstance(ErrorType.VALIDATION_FAILED, str)
        assert ErrorType.VALIDATION_FAILED.value == "VALIDATION_FAILED"


class TestFailedRecord:
    """Test FailedRecord dataclass functionality."""

    def test_create_failed_record(self) -> None:
        """Should create FailedRecord with all required fields."""
        record = FailedRecord(
            session_id="etl_20260102_181530_a1b2c3",
            timestamp="2026-01-02T18:15:30.123456",
            domain="annuity_performance",
            source_file="data.xlsx",
            row_index=42,
            error_type=ErrorType.VALIDATION_FAILED,
            raw_data='{"月度": "202401", "规模": 1000}',
        )

        assert record.session_id == "etl_20260102_181530_a1b2c3"
        assert record.domain == "annuity_performance"
        assert record.row_index == 42
        assert record.error_type == "VALIDATION_FAILED"

    def test_to_dict(self) -> None:
        """to_dict() should convert FailedRecord to dictionary for CSV export."""
        record = FailedRecord(
            session_id="etl_20260102_181530_a1b2c3",
            timestamp="2026-01-02T18:15:30.123456",
            domain="annuity_performance",
            source_file="data.xlsx",
            row_index=42,
            error_type=ErrorType.VALIDATION_FAILED,
            raw_data='{"月度": "202401"}',
        )

        result = record.to_dict()

        assert isinstance(result, dict)
        assert result["session_id"] == "etl_20260102_181530_a1b2c3"
        assert result["timestamp"] == "2026-01-02T18:15:30.123456"
        assert result["domain"] == "annuity_performance"
        assert result["source_file"] == "data.xlsx"
        assert result["row_index"] == 42
        assert result["error_type"] == "VALIDATION_FAILED"
        assert result["raw_data"] == '{"月度": "202401"}'

    def test_from_validation_error(self) -> None:
        """from_validation_error() should create FailedRecord with auto-generated timestamp."""
        from datetime import timezone

        before = datetime.now(timezone.utc)

        record = FailedRecord.from_validation_error(
            session_id="etl_20260102_181530_a1b2c3",
            domain="annuity_performance",
            source_file="data.xlsx",
            row_index=42,
            error_type=ErrorType.VALIDATION_FAILED,
            raw_row={"月度": "202401", "规模": 1000},
        )

        after = datetime.now(timezone.utc)

        assert record.session_id == "etl_20260102_181530_a1b2c3"
        assert record.domain == "annuity_performance"
        assert record.source_file == "data.xlsx"
        assert record.row_index == 42
        assert record.error_type == "VALIDATION_FAILED"

        # Verify timestamp is ISO-8601 format and recent
        parsed_timestamp = datetime.fromisoformat(record.timestamp)
        assert before <= parsed_timestamp <= after

        # Verify JSON serialization with ensure_ascii=False
        assert "202401" in record.raw_data
        assert "1000" in record.raw_data

    def test_failed_record_is_immutable(self) -> None:
        """FailedRecord should be frozen (immutable) dataclass."""
        record = FailedRecord(
            session_id="etl_20260102_181530_a1b2c3",
            timestamp="2026-01-02T18:15:30.123456",
            domain="annuity_performance",
            source_file="data.xlsx",
            row_index=42,
            error_type=ErrorType.VALIDATION_FAILED,
            raw_data="{}",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            record.row_index = 100  # type: ignore


class TestGenerateSessionId:
    """Test session ID generation."""

    def test_session_id_format(self) -> None:
        """Session ID should match required format: etl_YYYYMMDD_HHMMSS_xxxxxx."""
        session_id = generate_session_id()

        # Check format: etl_\d{8}_\d{6}_[a-f0-9]{6}
        pattern = r"^etl_\d{8}_\d{6}_[a-f0-9]{6}$"
        assert re.match(pattern, session_id), (
            f"Session ID {session_id} doesn't match pattern {pattern}"
        )

    def test_session_id_uniqueness(self) -> None:
        """Session IDs should be unique across multiple calls."""
        session_ids = [generate_session_id() for _ in range(100)]

        # All should be unique
        assert len(set(session_ids)) == 100

        # All should match format
        for session_id in session_ids:
            pattern = r"^etl_\d{8}_\d{6}_[a-f0-9]{6}$"
            assert re.match(pattern, session_id)

    def test_session_id_prefix(self) -> None:
        """Session ID should start with 'etl_' prefix."""
        session_id = generate_session_id()
        assert session_id.startswith("etl_")

    def test_session_id_timestamp_component(self) -> None:
        """Session ID timestamp component should be valid."""
        session_id = generate_session_id()

        # Extract timestamp part: etl_YYYYMMDD_HHMMSS_xxxxxx
        parts = session_id.split("_")
        timestamp_part = parts[1] + parts[2]  # YYYYMMDD + HHMMSS

        # Should be parseable as datetime
        datetime.strptime(timestamp_part, "%Y%m%d%H%M%S")


class TestFailureExporter:
    """Test FailureExporter class functionality."""

    def test_init(self) -> None:
        """Should initialize with session_id and default output_dir."""
        exporter = FailureExporter("etl_20260102_181530_a1b2c3")

        assert exporter.session_id == "etl_20260102_181530_a1b2c3"
        assert exporter.output_dir == Path("logs")
        assert exporter.output_file == Path(
            "logs/wdh_etl_failures_etl_20260102_181530_a1b2c3.csv"
        )

    def test_init_custom_output_dir(self) -> None:
        """Should accept custom output directory."""
        exporter = FailureExporter(
            "etl_20260102_181530_a1b2c3", output_dir=Path("custom_logs")
        )

        assert exporter.output_dir == Path("custom_logs")
        assert exporter.output_file == Path(
            "custom_logs/wdh_etl_failures_etl_20260102_181530_a1b2c3.csv"
        )

    def test_init_empty_session_id_raises(self) -> None:
        """Should raise ValueError if session_id is empty."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            FailureExporter("")

    def test_export_creates_directory(self, tmp_path: Path) -> None:
        """Should create output directory if it doesn't exist (AC-6)."""
        output_dir = tmp_path / "logs"
        exporter = FailureExporter("etl_20260102_181530_a1b2c3", output_dir=output_dir)

        # Directory doesn't exist yet
        assert not output_dir.exists()

        # Export should create it
        records = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="test",
                source_file="test.xlsx",
                row_index=1,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data="{}",
            )
        ]
        exporter.export(records)

        assert output_dir.exists()
        assert exporter.output_file.exists()

    def test_export_writes_header_on_first_call(self, tmp_path: Path) -> None:
        """Should write CSV header on first export (AC-4)."""
        exporter = FailureExporter("etl_20260102_181530_a1b2c3", output_dir=tmp_path)

        records = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="test",
                source_file="test.xlsx",
                row_index=1,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data='{"field": "value"}',
            )
        ]

        result_path = exporter.export(records)

        # Verify file exists
        assert result_path.exists()

        # Read and verify header
        with open(result_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == FailureExporter.FIELDNAMES

            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["domain"] == "test"
            assert rows[0]["source_file"] == "test.xlsx"
            assert rows[0]["row_index"] == "1"
            assert rows[0]["error_type"] == "VALIDATION_FAILED"
            assert rows[0]["raw_data"] == '{"field": "value"}'

    def test_export_append_mode_no_duplicate_header(self, tmp_path: Path) -> None:
        """Append mode: second export should not write header (AC-4)."""
        exporter = FailureExporter("etl_20260102_181530_a1b2c3", output_dir=tmp_path)

        # First export
        records1 = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="domain1",
                source_file="file1.xlsx",
                row_index=1,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data="{}",
            )
        ]
        exporter.export(records1)

        # Second export (different domain)
        records2 = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:31",
                domain="domain2",
                source_file="file2.xlsx",
                row_index=2,
                error_type=ErrorType.ENRICHMENT_FAILED,
                raw_data="{}",
            )
        ]
        exporter.export(records2)

        # Verify only 1 header and 2 data rows
        with open(exporter.output_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Header line + 2 data rows
        assert len(lines) == 3

        # Verify header appears only once (at line 0)
        assert "session_id" in lines[0]

        # Verify both data rows
        assert "domain1" in lines[1]
        assert "domain2" in lines[2]

    def test_export_unified_schema(self, tmp_path: Path) -> None:
        """CSV export should use unified schema across domains (AC-3)."""
        exporter = FailureExporter("etl_20260102_181530_a1b2c3", output_dir=tmp_path)

        records = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="annuity_performance",
                source_file="file1.xlsx",
                row_index=10,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data='{"月度": "202401"}',
            ),
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:31",
                domain="annuity_income",
                source_file="file2.xlsx",
                row_index=20,
                error_type=ErrorType.ENRICHMENT_FAILED,
                raw_data='{"月度": "202402"}',
            ),
        ]

        exporter.export(records)

        # Verify unified schema
        with open(exporter.output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == FailureExporter.FIELDNAMES

            rows = list(reader)
            assert len(rows) == 2

            # Check first record
            assert rows[0]["domain"] == "annuity_performance"
            assert rows[0]["source_file"] == "file1.xlsx"
            assert rows[0]["row_index"] == "10"
            assert rows[0]["error_type"] == "VALIDATION_FAILED"

            # Check second record
            assert rows[1]["domain"] == "annuity_income"
            assert rows[1]["source_file"] == "file2.xlsx"
            assert rows[1]["row_index"] == "20"
            assert rows[1]["error_type"] == "ENRICHMENT_FAILED"

    def test_ensure_directory(self, tmp_path: Path) -> None:
        """_ensure_directory() should create directory with exist_ok=True."""
        output_dir = tmp_path / "nested" / "logs"
        exporter = FailureExporter("etl_20260102_181530_a1b2c3", output_dir=output_dir)

        # Create nested directory structure
        exporter._ensure_directory()

        assert output_dir.exists()
        assert output_dir.is_dir()

        # Calling again should not raise error
        exporter._ensure_directory()


class TestExportFailedRecords:
    """Test export_failed_records convenience function."""

    def test_export_failed_records(self, tmp_path: Path) -> None:
        """export_failed_records() should export and return absolute path."""
        records = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="test",
                source_file="test.xlsx",
                row_index=1,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data="{}",
            )
        ]

        output_dir = str(tmp_path / "logs")
        csv_path = export_failed_records(
            records, "etl_20260102_181530_a1b2c3", output_dir=output_dir
        )

        # Should return absolute path as string
        assert isinstance(csv_path, str)
        assert Path(csv_path).is_absolute()

        # File should exist
        assert Path(csv_path).exists()

    def test_export_failed_records_default_output_dir(self, tmp_path: Path) -> None:
        """Should use 'logs' as default output directory."""
        records = [
            FailedRecord(
                session_id="etl_20260102_181530_a1b2c3",
                timestamp="2026-01-02T18:15:30",
                domain="test",
                source_file="test.xlsx",
                row_index=1,
                error_type=ErrorType.VALIDATION_FAILED,
                raw_data="{}",
            )
        ]

        # Change to temp directory to test default "logs" creation
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)

            csv_path = export_failed_records(records, "etl_20260102_181530_a1b2c3")

            # Should create logs/ in current directory
            assert Path(csv_path).parent.name == "logs"
            assert Path(csv_path).exists()
        finally:
            os.chdir(original_cwd)
