"""
Unit tests for enrichment observability module.

Story 6.8: Enrichment Observability and Export
Tests for EnrichmentStats, UnknownCompanyRecord, and EnrichmentObserver classes.
"""

import threading
from datetime import datetime
from unittest.mock import patch

import pytest

from work_data_hub.domain.company_enrichment.observability import (
    EnrichmentObserver,
    EnrichmentStats,
    UnknownCompanyRecord,
    build_unknown_company_rows,
)


class TestEnrichmentStats:
    """Tests for EnrichmentStats dataclass."""

    def test_default_values(self) -> None:
        """Test default initialization values."""
        stats = EnrichmentStats()
        assert stats.total_lookups == 0
        assert stats.cache_hits == 0
        assert stats.temp_ids_generated == 0
        assert stats.api_calls == 0
        assert stats.sync_budget_used == 0
        assert stats.async_queued == 0
        assert stats.queue_depth_after == 0
        assert stats.hit_type_counts == {}

    def test_cache_hit_rate_calculation(self) -> None:
        """Test cache hit rate computed property (AC1)."""
        stats = EnrichmentStats(total_lookups=100, cache_hits=85)
        assert stats.cache_hit_rate == 0.85

    def test_cache_hit_rate_zero_lookups(self) -> None:
        """Test cache hit rate returns 0.0 when no lookups."""
        stats = EnrichmentStats(total_lookups=0, cache_hits=0)
        assert stats.cache_hit_rate == 0.0

    def test_temp_id_rate_calculation(self) -> None:
        """Test temp ID rate computed property."""
        stats = EnrichmentStats(total_lookups=100, temp_ids_generated=10)
        assert stats.temp_id_rate == 0.1

    def test_temp_id_rate_zero_lookups(self) -> None:
        """Test temp ID rate returns 0.0 when no lookups."""
        stats = EnrichmentStats(total_lookups=0, temp_ids_generated=0)
        assert stats.temp_id_rate == 0.0

    def test_to_dict_serialization(self) -> None:
        """Test JSON serialization via to_dict (AC1)."""
        stats = EnrichmentStats(
            total_lookups=1000,
            cache_hits=850,
            temp_ids_generated=100,
            api_calls=5,
            sync_budget_used=5,
            async_queued=45,
            queue_depth_after=120,
            hit_type_counts={"exact": 800, "fuzzy": 50}
        )
        result = stats.to_dict()

        assert result["total_lookups"] == 1000
        assert result["cache_hits"] == 850
        assert result["cache_hit_rate"] == 0.85
        assert result["temp_ids_generated"] == 100
        assert result["temp_id_rate"] == 0.1
        assert result["api_calls"] == 5
        assert result["sync_budget_used"] == 5
        assert result["async_queued"] == 45
        assert result["queue_depth_after"] == 120
        assert result["hit_type_counts"] == {"exact": 800, "fuzzy": 50}
        assert result["yaml_hits"] == {"exact": 800, "fuzzy": 50}

    def test_to_dict_rate_rounding(self) -> None:
        """Test that rates are rounded to 4 decimal places."""
        stats = EnrichmentStats(total_lookups=3, cache_hits=1)
        result = stats.to_dict()
        # 1/3 = 0.333333... should round to 0.3333
        assert result["cache_hit_rate"] == 0.3333

    def test_merge_stats(self) -> None:
        """Test merging two EnrichmentStats instances."""
        stats1 = EnrichmentStats(
            total_lookups=100,
            cache_hits=80,
            temp_ids_generated=10,
            api_calls=5,
            sync_budget_used=5,
            async_queued=5,
            queue_depth_after=50,
            hit_type_counts={"plan": 60, "name": 20}
        )
        stats2 = EnrichmentStats(
            total_lookups=50,
            cache_hits=40,
            temp_ids_generated=5,
            api_calls=2,
            sync_budget_used=2,
            async_queued=3,
            queue_depth_after=60,
            hit_type_counts={"plan": 30, "account": 10}
        )

        merged = stats1.merge(stats2)

        assert merged.total_lookups == 150
        assert merged.cache_hits == 120
        assert merged.temp_ids_generated == 15
        assert merged.api_calls == 7
        assert merged.sync_budget_used == 7
        assert merged.async_queued == 8
        # queue_depth_after takes latest value
        assert merged.queue_depth_after == 60
        # merged hit types
        assert merged.hit_type_counts["plan"] == 90
        assert merged.hit_type_counts["name"] == 20
        assert merged.hit_type_counts["account"] == 10


class TestUnknownCompanyRecord:
    """Tests for UnknownCompanyRecord dataclass."""

    def test_default_values(self) -> None:
        """Test default initialization."""
        record = UnknownCompanyRecord(
            company_name="Test Corp",
            temporary_id="IN_ABC123",
        )
        assert record.company_name == "Test Corp"
        assert record.temporary_id == "IN_ABC123"
        assert record.occurrence_count == 1
        assert isinstance(record.first_seen, datetime)

    def test_csv_headers(self) -> None:
        """Test CSV header generation (AC2)."""
        headers = UnknownCompanyRecord.csv_headers()
        assert headers == ["company_name", "temporary_id", "first_seen", "occurrence_count"]

    def test_to_csv_row(self) -> None:
        """Test CSV row generation (AC2)."""
        fixed_time = datetime(2025, 12, 7, 10, 30, 0)
        record = UnknownCompanyRecord(
            company_name="Unknown Corp",
            temporary_id="IN_XYZ789",
            first_seen=fixed_time,
            occurrence_count=5,
        )
        row = record.to_csv_row()

        assert row[0] == "Unknown Corp"
        assert row[1] == "IN_XYZ789"
        assert row[2] == "2025-12-07T10:30:00"
        assert row[3] == "5"


class TestEnrichmentObserver:
    """Tests for EnrichmentObserver class."""

    def test_initial_state(self) -> None:
        """Test observer initializes with empty stats."""
        observer = EnrichmentObserver()
        stats = observer.get_stats()

        assert stats.total_lookups == 0
        assert stats.cache_hits == 0
        assert stats.temp_ids_generated == 0

    def test_record_lookup(self) -> None:
        """Test recording lookup attempts."""
        observer = EnrichmentObserver()
        observer.record_lookup()
        observer.record_lookup()
        observer.record_lookup()

        stats = observer.get_stats()
        assert stats.total_lookups == 3

    def test_record_cache_hit(self) -> None:
        """Test recording cache hits."""
        observer = EnrichmentObserver()
        observer.record_cache_hit(match_type="plan")
        observer.record_cache_hit(match_type="name")

        stats = observer.get_stats()
        assert stats.cache_hits == 2
        assert stats.hit_type_counts["plan"] == 1
        assert stats.hit_type_counts["name"] == 1

    def test_record_temp_id(self) -> None:
        """Test recording temporary ID generation."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company B", "IN_002")

        stats = observer.get_stats()
        assert stats.temp_ids_generated == 2

    def test_record_temp_id_tracks_unknown_companies(self) -> None:
        """Test that temp ID recording tracks unknown companies."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")

        unknown = observer.get_unknown_companies()
        assert len(unknown) == 1
        assert unknown[0].company_name == "Company A"
        assert unknown[0].temporary_id == "IN_001"
        assert unknown[0].occurrence_count == 1

    def test_record_temp_id_increments_occurrence_count(self) -> None:
        """Test that repeated temp IDs increment occurrence count (AC3)."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company A", "IN_001")

        unknown = observer.get_unknown_companies()
        assert len(unknown) == 1
        assert unknown[0].occurrence_count == 3

    def test_record_api_call(self) -> None:
        """Test recording API calls."""
        observer = EnrichmentObserver()
        observer.record_api_call()
        observer.record_api_call()

        stats = observer.get_stats()
        assert stats.api_calls == 2
        assert stats.sync_budget_used == 2

    def test_record_async_queued(self) -> None:
        """Test recording async queue operations."""
        observer = EnrichmentObserver()
        observer.record_async_queued()

        stats = observer.get_stats()
        assert stats.async_queued == 1

    def test_set_queue_depth(self) -> None:
        """Test setting queue depth."""
        observer = EnrichmentObserver()
        observer.set_queue_depth(120)

        stats = observer.get_stats()
        assert stats.queue_depth_after == 120

    def test_get_unknown_companies_sorted_by_occurrence(self) -> None:
        """Test unknown companies are sorted by occurrence count DESC (AC3)."""
        observer = EnrichmentObserver()

        # Add companies with different occurrence counts
        observer.record_temp_id("Low Freq Corp", "IN_001")  # 1 occurrence

        observer.record_temp_id("High Freq Corp", "IN_002")
        observer.record_temp_id("High Freq Corp", "IN_002")
        observer.record_temp_id("High Freq Corp", "IN_002")  # 3 occurrences

        observer.record_temp_id("Mid Freq Corp", "IN_003")
        observer.record_temp_id("Mid Freq Corp", "IN_003")  # 2 occurrences

        unknown = observer.get_unknown_companies()

        assert len(unknown) == 3
        assert unknown[0].company_name == "High Freq Corp"
        assert unknown[0].occurrence_count == 3
        assert unknown[1].company_name == "Mid Freq Corp"
        assert unknown[1].occurrence_count == 2
        assert unknown[2].company_name == "Low Freq Corp"
        assert unknown[2].occurrence_count == 1

    def test_get_unknown_company_rows(self) -> None:
        """Test getting CSV rows for unknown companies."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company B", "IN_002")
        observer.record_temp_id("Company A", "IN_001")  # Increment count

        rows = observer.get_unknown_company_rows()

        assert len(rows) == 2
        # First row should be Company A (2 occurrences)
        assert rows[0][0] == "Company A"
        assert rows[0][3] == "2"
        # Second row should be Company B (1 occurrence)
        assert rows[1][0] == "Company B"
        assert rows[1][3] == "1"

    def test_has_unknown_companies(self) -> None:
        """Test checking for unknown companies."""
        observer = EnrichmentObserver()
        assert observer.has_unknown_companies() is False

        observer.record_temp_id("Company A", "IN_001")
        assert observer.has_unknown_companies() is True

    def test_reset(self) -> None:
        """Test resetting observer state."""
        observer = EnrichmentObserver()
        observer.record_lookup()
        observer.record_cache_hit()
        observer.record_temp_id("Company A", "IN_001")

        observer.reset()

        stats = observer.get_stats()
        assert stats.total_lookups == 0
        assert stats.cache_hits == 0
        assert stats.temp_ids_generated == 0
        assert observer.has_unknown_companies() is False

    def test_thread_safety(self) -> None:
        """Test observer is thread-safe for concurrent access."""
        observer = EnrichmentObserver()
        num_threads = 10
        iterations_per_thread = 100

        def record_operations() -> None:
            for _ in range(iterations_per_thread):
                observer.record_lookup()
                observer.record_cache_hit()

        threads = [
            threading.Thread(target=record_operations)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = observer.get_stats()
        expected = num_threads * iterations_per_thread
        assert stats.total_lookups == expected
        assert stats.cache_hits == expected

    def test_get_stats_returns_copy(self) -> None:
        """Test that get_stats returns a copy, not the internal state."""
        observer = EnrichmentObserver()
        observer.record_lookup()

        stats1 = observer.get_stats()
        observer.record_lookup()
        stats2 = observer.get_stats()

        assert stats1.total_lookups == 1
        assert stats2.total_lookups == 2


class TestBuildUnknownCompanyRows:
    """Tests for build_unknown_company_rows helper function."""

    def test_builds_rows_from_observer(self) -> None:
        """Test building CSV rows from observer."""
        observer = EnrichmentObserver()
        observer.record_temp_id("Company A", "IN_001")
        observer.record_temp_id("Company B", "IN_002")

        rows = build_unknown_company_rows(observer)

        assert len(rows) == 2
        assert all(len(row) == 4 for row in rows)

    def test_empty_observer_returns_empty_list(self) -> None:
        """Test empty observer returns empty list."""
        observer = EnrichmentObserver()
        rows = build_unknown_company_rows(observer)
        assert rows == []


class TestEnrichmentStatsJsonFormat:
    """Tests for AC1 JSON format compliance."""

    def test_json_format_matches_ac1_spec(self) -> None:
        """Test that to_dict output matches AC1 specification exactly."""
        stats = EnrichmentStats(
            total_lookups=1000,
            cache_hits=850,
            temp_ids_generated=100,
            api_calls=5,
            sync_budget_used=5,
            async_queued=45,
            queue_depth_after=120,
            hit_type_counts={"exact": 850}
        )
        result = stats.to_dict()

        # Verify all required fields from AC1 are present
        required_fields = [
            "total_lookups",
            "cache_hits",
            "cache_hit_rate",
            "temp_ids_generated",
            "api_calls",
            "sync_budget_used",
            "async_queued",
            "queue_depth_after",
            "hit_type_counts",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Verify values match AC1 example
        assert result["total_lookups"] == 1000
        assert result["cache_hits"] == 850
        assert result["cache_hit_rate"] == 0.85
        assert result["temp_ids_generated"] == 100
        assert result["api_calls"] == 5
        assert result["sync_budget_used"] == 5
        assert result["async_queued"] == 45
        assert result["queue_depth_after"] == 120
        assert result["hit_type_counts"] == {"exact": 850}
