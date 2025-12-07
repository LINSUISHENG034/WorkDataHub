"""
Unit tests for CSV exporter infrastructure module.

Story 6.8: Enrichment Observability and Export (AC2, AC3, AC8)
"""

import csv
import tempfile
from pathlib import Path

import pytest

from work_data_hub.domain.company_enrichment.observability import (
    EnrichmentObserver,
    UnknownCompanyRecord,
)
from work_data_hub.infrastructure.enrichment.csv_exporter import (
    export_unknown_companies,
    write_unknown_companies_csv,
)


class TestWriteUnknownCompaniesCsv:
    """Tests for write_unknown_companies_csv function."""

    def test_writes_csv_with_headers_and_rows(self, tmp_path: Path) -> None:
        """Test CSV file is created with correct headers and data (AC2)."""
        rows = [
            ["Company A", "IN_001", "2025-12-07T10:00:00", "5"],
            ["Company B", "IN_002", "2025-12-07T11:00:00", "3"],
        ]

        result = write_unknown_companies_csv(rows, output_dir=str(tmp_path))

        assert result is not None
        assert result.exists()
        assert result.suffix == ".csv"

        # Verify CSV content
        with result.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            lines = list(reader)

        # Check headers
        assert lines[0] == UnknownCompanyRecord.csv_headers()
        # Check data rows
        assert lines[1] == rows[0]
        assert lines[2] == rows[1]

    def test_returns_none_for_empty_rows(self, tmp_path: Path) -> None:
        """Test returns None when no rows to export."""
        result = write_unknown_companies_csv([], output_dir=str(tmp_path))
        assert result is None

    def test_creates_output_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Test creates output directory if it doesn't exist (AC8)."""
        nested_dir = tmp_path / "nested" / "logs"
        rows = [["Company A", "IN_001", "2025-12-07T10:00:00", "1"]]

        result = write_unknown_companies_csv(rows, output_dir=str(nested_dir))

        assert result is not None
        assert nested_dir.exists()
        assert result.parent == nested_dir

    def test_filename_contains_timestamp(self, tmp_path: Path) -> None:
        """Test filename includes timestamp for uniqueness."""
        rows = [["Company A", "IN_001", "2025-12-07T10:00:00", "1"]]

        result = write_unknown_companies_csv(rows, output_dir=str(tmp_path))

        assert result is not None
        assert "unknown_companies_" in result.name
        # Filename format: unknown_companies_YYYYMMDD_HHMMSS.csv
        assert len(result.stem) > len("unknown_companies_")

    def test_csv_encoding_utf8(self, tmp_path: Path) -> None:
        """Test CSV is written with UTF-8 encoding for Chinese characters."""
        rows = [["中国平安保险", "IN_001", "2025-12-07T10:00:00", "10"]]

        result = write_unknown_companies_csv(rows, output_dir=str(tmp_path))

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "中国平安保险" in content


class TestExportUnknownCompanies:
    """Tests for export_unknown_companies convenience function."""

    def test_exports_from_observer(self, tmp_path: Path) -> None:
        """Test exporting unknown companies from observer."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company B", "IN_002")

        result = export_unknown_companies(observer, output_dir=str(tmp_path))

        assert result is not None
        assert result.exists()

        # Verify content
        with result.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            lines = list(reader)

        assert len(lines) == 3  # Header + 2 data rows

    def test_returns_none_for_empty_observer(self, tmp_path: Path) -> None:
        """Test returns None when observer has no unknown companies."""
        observer = EnrichmentObserver()

        result = export_unknown_companies(observer, output_dir=str(tmp_path))

        assert result is None

    def test_sorted_by_occurrence_count(self, tmp_path: Path) -> None:
        """Test unknown companies are sorted by occurrence count DESC (AC3)."""
        observer = EnrichmentObserver()

        # Add companies with different occurrence counts
        observer.record_temp_id("Low Freq", "IN_001")  # 1 occurrence

        observer.record_temp_id("High Freq", "IN_002")
        observer.record_temp_id("High Freq", "IN_002")
        observer.record_temp_id("High Freq", "IN_002")  # 3 occurrences

        observer.record_temp_id("Mid Freq", "IN_003")
        observer.record_temp_id("Mid Freq", "IN_003")  # 2 occurrences

        result = export_unknown_companies(observer, output_dir=str(tmp_path))

        assert result is not None

        with result.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            lines = list(reader)

        # Skip header, check order
        assert lines[1][0] == "High Freq"  # 3 occurrences
        assert lines[1][3] == "3"
        assert lines[2][0] == "Mid Freq"  # 2 occurrences
        assert lines[2][3] == "2"
        assert lines[3][0] == "Low Freq"  # 1 occurrence
        assert lines[3][3] == "1"


class TestCsvExporterIntegration:
    """Integration tests for CSV export flow."""

    def test_full_export_flow(self, tmp_path: Path) -> None:
        """Test complete export flow from observer to CSV file."""
        observer = EnrichmentObserver()

        # Simulate enrichment run
        observer.record_lookup()
        observer.record_cache_hit()

        observer.record_lookup()
        observer.record_temp_id("Unknown Corp 1", "IN_ABC001")

        observer.record_lookup()
        observer.record_temp_id("Unknown Corp 2", "IN_ABC002")
        observer.record_temp_id("Unknown Corp 2", "IN_ABC002")  # Duplicate

        observer.record_lookup()
        observer.record_api_call()

        # Export
        csv_path = export_unknown_companies(observer, output_dir=str(tmp_path))

        # Verify stats
        stats = observer.get_stats()
        assert stats.total_lookups == 4
        assert stats.cache_hits == 1
        assert stats.temp_ids_generated == 3
        assert stats.api_calls == 1

        # Verify CSV
        assert csv_path is not None
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            lines = list(reader)

        assert len(lines) == 3  # Header + 2 unique companies
        # Unknown Corp 2 should be first (2 occurrences)
        assert lines[1][0] == "Unknown Corp 2"
        assert lines[1][3] == "2"
