"""
Unit tests for CompanyMappingRepository (Story 6.3).

This module tests the database access layer for company mappings using
mocked database connections to ensure fast, isolated unit tests.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
    MatchResult,
    InsertBatchResult,
)


@dataclass
class MockRow:
    """Mock database row for testing."""

    alias_name: str
    canonical_id: str
    match_type: str
    priority: int
    source: str
    created_at: Any = None
    updated_at: Any = None


@pytest.fixture
def mock_connection():
    """Create a mock SQLAlchemy connection."""
    return MagicMock()


@pytest.fixture
def repository(mock_connection):
    """Create a CompanyMappingRepository with mock connection."""
    return CompanyMappingRepository(mock_connection)


@pytest.fixture
def sample_lookup_rows():
    """Sample rows returned from lookup query."""
    return [
        MockRow(
            alias_name="FP0001",
            canonical_id="614810477",
            match_type="plan",
            priority=1,
            source="internal",
        ),
        MockRow(
            alias_name="FP0002",
            canonical_id="614810477",
            match_type="plan",
            priority=1,
            source="internal",
        ),
        MockRow(
            alias_name="中国平安",
            canonical_id="600866980",
            match_type="name",
            priority=4,
            source="internal",
        ),
    ]


@pytest.fixture
def sample_mappings():
    """Sample mappings for insert tests."""
    return [
        {
            "alias_name": "FP0001",
            "canonical_id": "614810477",
            "match_type": "plan",
            "priority": 1,
            "source": "internal",
        },
        {
            "alias_name": "FP0002",
            "canonical_id": "614810477",
            "match_type": "plan",
            "priority": 1,
            "source": "internal",
        },
        {
            "alias_name": "中国平安",
            "canonical_id": "600866980",
            "match_type": "name",
            "priority": 4,
        },  # source defaults to 'internal'
    ]


class TestMatchResult:
    """Test cases for MatchResult dataclass."""

    def test_match_result_creation(self):
        """MatchResult can be created with all fields."""
        result = MatchResult(
            company_id="614810477",
            match_type="plan",
            priority=1,
            source="internal",
        )
        assert result.company_id == "614810477"
        assert result.match_type == "plan"
        assert result.priority == 1
        assert result.source == "internal"


class TestInsertBatchResult:
    """Test cases for InsertBatchResult dataclass."""

    def test_insert_batch_result_creation(self):
        """InsertBatchResult can be created with all fields."""
        result = InsertBatchResult(
            inserted_count=5,
            skipped_count=2,
            conflicts=[{"alias_name": "test", "existing_id": "1", "new_id": "2"}],
        )
        assert result.inserted_count == 5
        assert result.skipped_count == 2
        assert len(result.conflicts) == 1

    def test_insert_batch_result_default_conflicts(self):
        """InsertBatchResult defaults to empty conflicts list."""
        result = InsertBatchResult(inserted_count=5, skipped_count=0)
        assert result.conflicts == []


class TestLookupBatch:
    """Test cases for lookup_batch method."""

    def test_lookup_batch_exact_match(
        self, repository, mock_connection, sample_lookup_rows
    ):
        """Single alias returns correct MatchResult."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_lookup_rows[0]]
        mock_connection.execute.return_value = mock_result

        # Execute
        results = repository.lookup_batch(["FP0001"])

        # Verify
        assert "FP0001" in results
        assert results["FP0001"].company_id == "614810477"
        assert results["FP0001"].match_type == "plan"
        assert results["FP0001"].priority == 1
        assert results["FP0001"].source == "internal"

    def test_lookup_batch_multiple_aliases(
        self, repository, mock_connection, sample_lookup_rows
    ):
        """Multiple aliases return correct MatchResults."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_lookup_rows
        mock_connection.execute.return_value = mock_result

        results = repository.lookup_batch(["FP0001", "FP0002", "中国平安"])

        assert len(results) == 3
        assert results["FP0001"].company_id == "614810477"
        assert results["中国平安"].company_id == "600866980"
        assert results["中国平安"].match_type == "name"

    def test_lookup_batch_no_match(self, repository, mock_connection):
        """Missing alias returns empty dict (no exception)."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_connection.execute.return_value = mock_result

        results = repository.lookup_batch(["NONEXISTENT"])

        assert results == {}
        assert "NONEXISTENT" not in results

    def test_lookup_batch_empty_input(self, repository, mock_connection):
        """Empty input returns empty dict without database call."""
        results = repository.lookup_batch([])

        assert results == {}
        mock_connection.execute.assert_not_called()

    def test_lookup_batch_filter_by_match_type(
        self, repository, mock_connection, sample_lookup_rows
    ):
        """Filter by match_type works correctly."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_lookup_rows[0]]
        mock_connection.execute.return_value = mock_result

        results = repository.lookup_batch(["FP0001"], match_types=["plan"])

        assert "FP0001" in results
        # Verify query included match_types parameter
        call_args = mock_connection.execute.call_args
        assert "match_types" in call_args[0][1]

    def test_lookup_batch_priority_ordering(self, repository, mock_connection):
        """Multiple matches return highest priority (lowest number)."""
        # Simulate DISTINCT ON returning highest priority match
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MockRow(
                alias_name="FP0001",
                canonical_id="614810477",
                match_type="plan",
                priority=1,  # Highest priority
                source="internal",
            ),
        ]
        mock_connection.execute.return_value = mock_result

        results = repository.lookup_batch(["FP0001"])

        assert results["FP0001"].priority == 1

    def test_lookup_batch_performance_1000_aliases(self, repository, mock_connection):
        """1000 lookups complete in <100ms with mock (AC5)."""
        # Generate 1000 mock results
        mock_rows = [
            MockRow(
                alias_name=f"ALIAS_{i}",
                canonical_id=f"ID_{i}",
                match_type="plan",
                priority=1,
                source="internal",
            )
            for i in range(1000)
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_result

        alias_names = [f"ALIAS_{i}" for i in range(1000)]

        start_time = time.perf_counter()
        results = repository.lookup_batch(alias_names)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert len(results) == 1000
        assert elapsed_ms < 100, f"Lookup took {elapsed_ms:.2f}ms, expected <100ms"
        mock_connection.execute.assert_called_once()


class TestInsertBatch:
    """Test cases for insert_batch method."""

    def test_insert_batch_success(self, repository, mock_connection, sample_mappings):
        """Batch insert returns correct count."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        inserted = repository.insert_batch(sample_mappings)

        assert inserted == 3
        mock_connection.execute.assert_called_once()

    def test_insert_batch_empty_input(self, repository, mock_connection):
        """Empty input returns 0 without database call."""
        inserted = repository.insert_batch([])

        assert inserted == 0
        mock_connection.execute.assert_not_called()

    def test_insert_batch_idempotent(
        self, repository, mock_connection, sample_mappings
    ):
        """Duplicate inserts don't fail (ON CONFLICT DO NOTHING)."""
        # First insert: all succeed
        mock_result1 = MagicMock()
        mock_result1.rowcount = 3
        mock_connection.execute.return_value = mock_result1

        inserted1 = repository.insert_batch(sample_mappings)
        assert inserted1 == 3

        # Second insert: all skipped (duplicates)
        mock_result2 = MagicMock()
        mock_result2.rowcount = 0
        mock_connection.execute.return_value = mock_result2

        inserted2 = repository.insert_batch(sample_mappings)
        assert inserted2 == 0

    def test_insert_batch_default_source(self, repository, mock_connection):
        """Missing source defaults to 'internal'."""
        mappings = [
            {
                "alias_name": "TEST",
                "canonical_id": "123",
                "match_type": "plan",
                "priority": 1,
                # No source specified
            }
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        repository.insert_batch(mappings)

        # Verify the values passed to execute include source='internal'
        call_args = mock_connection.execute.call_args
        values = call_args[0][1]
        assert values[0]["source"] == "internal"

    def test_insert_batch_performance_100_mappings(self, repository, mock_connection):
        """100 inserts complete in <50ms with mock."""
        mappings = [
            {
                "alias_name": f"ALIAS_{i}",
                "canonical_id": f"ID_{i}",
                "match_type": "plan",
                "priority": 1,
            }
            for i in range(100)
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_connection.execute.return_value = mock_result

        start_time = time.perf_counter()
        inserted = repository.insert_batch(mappings)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert inserted == 100
        assert elapsed_ms < 50, f"Insert took {elapsed_ms:.2f}ms, expected <50ms"


class TestInsertBatchWithConflictCheck:
    """Test cases for insert_batch_with_conflict_check method."""

    def test_conflict_detection(self, repository, mock_connection):
        """Conflicts are detected when canonical_id differs."""
        # Setup: existing entry with different canonical_id
        existing_rows = [
            MockRow(
                alias_name="FP0001",
                canonical_id="OLD_ID",
                match_type="plan",
                priority=1,
                source="internal",
            )
        ]

        # Mock the existing lookup
        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = existing_rows

        # Mock the insert (no new inserts since all conflict)
        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 0

        mock_connection.execute.side_effect = [mock_existing_result, mock_insert_result]

        mappings = [
            {
                "alias_name": "FP0001",
                "canonical_id": "NEW_ID",  # Different from OLD_ID
                "match_type": "plan",
                "priority": 1,
            }
        ]

        result = repository.insert_batch_with_conflict_check(mappings)

        assert result.inserted_count == 0
        assert result.skipped_count == 1
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["alias_name"] == "FP0001"
        assert result.conflicts[0]["existing_id"] == "OLD_ID"
        assert result.conflicts[0]["new_id"] == "NEW_ID"

    def test_conflict_detection_uses_positional_pairing(self, repository, mock_connection):
        """Ensure conflict lookup pairs alias/match_type by position (ordinality)."""
        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = []

        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 0

        mock_connection.execute.side_effect = [mock_existing_result, mock_insert_result]

        mappings = [
            {"alias_name": "ALIAS_A", "canonical_id": "ID_A", "match_type": "plan", "priority": 1},
            {"alias_name": "ALIAS_B", "canonical_id": "ID_B", "match_type": "name", "priority": 4},
        ]

        repository.insert_batch_with_conflict_check(mappings)

        first_call = mock_connection.execute.call_args_list[0]
        query_text = str(first_call[0][0])
        assert "WITH input_pairs" in query_text  # ordinality-based pairing
        params = first_call[0][1]
        assert params["alias_names"] == ["ALIAS_A", "ALIAS_B"]
        assert params["match_types"] == ["plan", "name"]

    def test_no_conflict_same_id(self, repository, mock_connection):
        """No conflict when canonical_id is the same."""
        existing_rows = [
            MockRow(
                alias_name="FP0001",
                canonical_id="SAME_ID",
                match_type="plan",
                priority=1,
                source="internal",
            )
        ]

        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = existing_rows
        mock_connection.execute.return_value = mock_existing_result

        mappings = [
            {
                "alias_name": "FP0001",
                "canonical_id": "SAME_ID",  # Same as existing
                "match_type": "plan",
                "priority": 1,
            }
        ]

        result = repository.insert_batch_with_conflict_check(mappings)

        assert len(result.conflicts) == 0
        assert result.skipped_count == 1  # Skipped because already exists

    def test_new_entries_inserted(self, repository, mock_connection):
        """New entries are inserted when no existing match."""
        # No existing entries
        mock_existing_result = MagicMock()
        mock_existing_result.fetchall.return_value = []

        # Insert succeeds
        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 2

        mock_connection.execute.side_effect = [mock_existing_result, mock_insert_result]

        mappings = [
            {
                "alias_name": "NEW1",
                "canonical_id": "ID1",
                "match_type": "plan",
                "priority": 1,
            },
            {
                "alias_name": "NEW2",
                "canonical_id": "ID2",
                "match_type": "plan",
                "priority": 1,
            },
        ]

        result = repository.insert_batch_with_conflict_check(mappings)

        assert result.inserted_count == 2
        assert result.skipped_count == 0
        assert len(result.conflicts) == 0

    def test_empty_input(self, repository, mock_connection):
        """Empty input returns zero counts."""
        result = repository.insert_batch_with_conflict_check([])

        assert result.inserted_count == 0
        assert result.skipped_count == 0
        assert result.conflicts == []
        mock_connection.execute.assert_not_called()


class TestGetAllMappings:
    """Test cases for get_all_mappings method."""

    def test_get_all_mappings(self, repository, mock_connection):
        """Returns all mappings as list of dicts."""
        mock_rows = [
            MockRow(
                alias_name="FP0001",
                canonical_id="614810477",
                match_type="plan",
                priority=1,
                source="internal",
                created_at="2025-01-01",
                updated_at="2025-01-01",
            )
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_result

        mappings = repository.get_all_mappings()

        assert len(mappings) == 1
        assert mappings[0]["alias_name"] == "FP0001"
        assert mappings[0]["canonical_id"] == "614810477"

    def test_get_all_mappings_with_filter(self, repository, mock_connection):
        """Filter by match_types works."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_connection.execute.return_value = mock_result

        repository.get_all_mappings(match_types=["plan", "name"])

        call_args = mock_connection.execute.call_args
        assert "match_types" in call_args[0][1]


class TestDeleteBySource:
    """Test cases for delete_by_source method."""

    def test_delete_by_source(self, repository, mock_connection):
        """Deletes entries by source and returns count."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_connection.execute.return_value = mock_result

        deleted = repository.delete_by_source("pipeline_backflow")

        assert deleted == 5
        mock_connection.execute.assert_called_once()


# =============================================================================
# Story 6.5: Async Enrichment Queue Tests
# =============================================================================


class TestEnqueueResult:
    """Test cases for EnqueueResult dataclass (Story 6.5)."""

    def test_enqueue_result_creation(self):
        """EnqueueResult can be created with all fields."""
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            EnqueueResult,
        )

        result = EnqueueResult(queued_count=5, skipped_count=2)
        assert result.queued_count == 5
        assert result.skipped_count == 2


class TestEnqueueForEnrichment:
    """Test cases for enqueue_for_enrichment method (Story 6.5)."""

    def test_enqueue_batch_success(self, repository, mock_connection):
        """Batch enqueue returns correct counts (AC7)."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        requests = [
            {"raw_name": "公司A", "normalized_name": "公司a", "temp_id": "IN_ABC123"},
            {"raw_name": "公司B", "normalized_name": "公司b", "temp_id": "IN_DEF456"},
            {"raw_name": "公司C", "normalized_name": "公司c", "temp_id": "IN_GHI789"},
        ]

        result = repository.enqueue_for_enrichment(requests)

        assert result.queued_count == 3
        assert result.skipped_count == 0
        mock_connection.execute.assert_called_once()
        query_text = str(mock_connection.execute.call_args[0][0])
        params = mock_connection.execute.call_args[0][1]
        assert "unnest" in query_text
        assert params["raw_names"] == ["公司A", "公司B", "公司C"]
        assert params["normalized_names"] == ["公司a", "公司b", "公司c"]
        assert params["temp_ids"] == ["IN_ABC123", "IN_DEF456", "IN_GHI789"]

    def test_enqueue_empty_input(self, repository, mock_connection):
        """Empty input returns zero counts without database call."""
        result = repository.enqueue_for_enrichment([])

        assert result.queued_count == 0
        assert result.skipped_count == 0
        mock_connection.execute.assert_not_called()

    def test_enqueue_deduplication_via_conflict(self, repository, mock_connection):
        """Duplicates are skipped via ON CONFLICT DO NOTHING (AC2)."""
        # Simulate 2 of 3 being duplicates (rowcount=1)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        requests = [
            {"raw_name": "公司A", "normalized_name": "公司a", "temp_id": "IN_ABC123"},
            {"raw_name": "公司A变体", "normalized_name": "公司a", "temp_id": "IN_ABC123"},
            {"raw_name": "公司B", "normalized_name": "公司b", "temp_id": "IN_DEF456"},
        ]

        result = repository.enqueue_for_enrichment(requests)

        assert result.queued_count == 1
        assert result.skipped_count == 2
        # Still single-statement execution
        mock_connection.execute.assert_called_once()

    def test_enqueue_includes_required_fields(self, repository, mock_connection):
        """Enqueue includes raw_name, normalized_name, temp_id, status (AC3)."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        requests = [
            {"raw_name": "公司A", "normalized_name": "公司a", "temp_id": "IN_ABC123"},
        ]

        repository.enqueue_for_enrichment(requests)

        # Verify arrays passed to execute
        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        assert params["raw_names"] == ["公司A"]
        assert params["normalized_names"] == ["公司a"]
        assert params["temp_ids"] == ["IN_ABC123"]

    def test_enqueue_performance_100_requests(self, repository, mock_connection):
        """100 enqueues complete in <50ms with mock (AC9)."""
        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_connection.execute.return_value = mock_result

        requests = [
            {
                "raw_name": f"公司{i}",
                "normalized_name": f"公司{i}",
                "temp_id": f"IN_{i:016d}",
            }
            for i in range(100)
        ]

        start_time = time.perf_counter()
        result = repository.enqueue_for_enrichment(requests)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert result.queued_count == 100
        assert elapsed_ms < 50, f"Enqueue took {elapsed_ms:.2f}ms, expected <50ms"
        # Single batch insert
        mock_connection.execute.assert_called_once()


class TestCompanyMappingRepositoryUpsertBaseInfo:
    """Test upsert_base_info method (Story 6.2-P5)."""

    def test_upsert_base_info_inserts_new_record(self, repository, mock_connection):
        """Test upsert_base_info inserts new record successfully."""
        # Mock fetchone to return inserted=True (xmax=0)
        mock_row = MagicMock()
        mock_row.inserted = True
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        raw_data = {"list": [{"companyId": "123", "companyFullName": "Test"}], "total": 1}

        inserted = repository.upsert_base_info(
            company_id="1000065057",
            search_key_word="中国平安",
            company_full_name="中国平安保险（集团）股份有限公司",
            unite_code="91440300618698064P",
            raw_data=raw_data,
        )

        assert inserted is True
        mock_connection.execute.assert_called_once()

        # Verify SQL parameters
        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        assert params["company_id"] == "1000065057"
        assert params["search_key_word"] == "中国平安"
        assert params["company_full_name"] == "中国平安保险（集团）股份有限公司"
        assert params["unite_code"] == "91440300618698064P"
        # raw_data should be JSON string
        import json
        assert json.loads(params["raw_data"]) == raw_data

    def test_upsert_base_info_updates_existing_record(self, repository, mock_connection):
        """Test upsert_base_info updates existing record."""
        # Mock fetchone to return inserted=False (xmax!=0)
        mock_row = MagicMock()
        mock_row.inserted = False
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        raw_data = {"list": [{"companyId": "123"}], "total": 1}

        inserted = repository.upsert_base_info(
            company_id="1000065057",
            search_key_word="平安",
            company_full_name="中国平安保险（集团）股份有限公司",
            unite_code="91440300618698064P",
            raw_data=raw_data,
        )

        assert inserted is False
        mock_connection.execute.assert_called_once()

    def test_upsert_base_info_handles_null_unite_code(self, repository, mock_connection):
        """Test upsert_base_info handles NULL unite_code."""
        mock_row = MagicMock()
        mock_row.inserted = True
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        raw_data = {"list": [], "total": 0}

        inserted = repository.upsert_base_info(
            company_id="123",
            search_key_word="Test",
            company_full_name="Test Company",
            unite_code=None,  # NULL value
            raw_data=raw_data,
        )

        assert inserted is True
        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        assert params["unite_code"] is None

    def test_upsert_base_info_serializes_raw_data_correctly(self, repository, mock_connection):
        """Test upsert_base_info serializes raw_data as JSON string."""
        mock_row = MagicMock()
        mock_row.inserted = True
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        # Complex raw data with nested structures
        raw_data = {
            "list": [
                {
                    "companyId": "123",
                    "companyFullName": "测试公司",
                    "nested": {"key": "value"},
                }
            ],
            "total": 1,
            "metadata": {"timestamp": "2025-12-14"},
        }

        repository.upsert_base_info(
            company_id="123",
            search_key_word="测试",
            company_full_name="测试公司",
            unite_code="ABC123",
            raw_data=raw_data,
        )

        call_args = mock_connection.execute.call_args
        params = call_args[0][1]

        # Verify JSON serialization
        import json
        serialized = params["raw_data"]
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized == raw_data
        # Verify Chinese characters are preserved (ensure_ascii=False)
        assert "测试公司" in serialized

    def test_upsert_base_info_handles_empty_raw_data(self, repository, mock_connection):
        """Test upsert_base_info handles empty raw_data dict."""
        mock_row = MagicMock()
        mock_row.inserted = True
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        repository.upsert_base_info(
            company_id="123",
            search_key_word="Test",
            company_full_name="Test Company",
            unite_code="ABC",
            raw_data={},  # Empty dict
        )

        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        import json
        assert json.loads(params["raw_data"]) == {}

    def test_upsert_base_info_uses_on_conflict_do_update(self, repository, mock_connection):
        """Test upsert_base_info uses ON CONFLICT DO UPDATE semantics."""
        mock_row = MagicMock()
        mock_row.inserted = False
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        raw_data = {"list": [], "total": 0}

        repository.upsert_base_info(
            company_id="123",
            search_key_word="Test",
            company_full_name="Test Company",
            unite_code="ABC",
            raw_data=raw_data,
        )

        # Verify SQL contains ON CONFLICT clause
        call_args = mock_connection.execute.call_args
        sql_text = str(call_args[0][0])
        assert "ON CONFLICT" in sql_text
        assert "DO UPDATE" in sql_text
        # Verify only raw_data and updated_at are updated
        assert "raw_data = EXCLUDED.raw_data" in sql_text
        assert "updated_at = NOW()" in sql_text
