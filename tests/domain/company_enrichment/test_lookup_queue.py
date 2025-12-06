"""
Tests for LookupQueue DAO with atomic operations and database integration.

This module tests the lookup queue data access object with proper
database integration patterns, atomic operations, and concurrent
access scenarios for multi-worker queue processing.
"""

import time
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

from src.work_data_hub.domain.company_enrichment.lookup_queue import (
    LookupQueue,
    LookupQueueError,
    normalize_name,
)
from src.work_data_hub.domain.company_enrichment.models import LookupRequest


@pytest.fixture
def mock_connection():
    """Mock database connection for testing."""
    connection = Mock()
    cursor = Mock()

    # Setup cursor context manager
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    connection.cursor.return_value = cursor

    # Setup connection context manager
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)

    return connection


@pytest.fixture
def lookup_queue(mock_connection):
    """LookupQueue instance with mocked connection."""
    return LookupQueue(mock_connection, plan_only=False)


@pytest.fixture
def plan_only_queue(mock_connection):
    """LookupQueue instance in plan-only mode."""
    return LookupQueue(mock_connection, plan_only=True)


class TestNormalizeNameFunction:
    """Test the normalize_name utility function."""

    def test_normalize_basic_company_names(self):
        """Test basic company name normalization."""
        assert normalize_name("中国平安保险股份有限公司") == "中国平安保险股份有限公司"
        assert normalize_name("China Ping An Insurance") == "china ping an insurance"
        assert normalize_name("Test Company Ltd.") == "test company ltd."

    def test_normalize_whitespace_handling(self):
        """Test whitespace normalization."""
        assert normalize_name("  Test Company  ") == "test company"
        assert normalize_name("Company   With   Spaces") == "company with spaces"
        assert normalize_name("\t\nTest\t\nCompany\t\n") == "test company"

    def test_normalize_unicode_handling(self):
        """Test Unicode normalization (NFKC)."""
        # Test with various Unicode forms
        assert normalize_name("测试公司") == "测试公司"
        assert (
            normalize_name("Ｔｅｓｔ Ｃｏｍｐａｎｙ") == "test company"
        )  # Full-width characters

    def test_normalize_empty_and_none(self):
        """Test handling of empty strings and None."""
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""
        assert normalize_name(None) == ""

    def test_normalize_mixed_script(self):
        """Test mixed script handling."""
        assert normalize_name("Test测试Company") == "test测试company"
        assert normalize_name("ABC 123 测试") == "abc 123 测试"


class TestLookupQueueInitialization:
    """Test LookupQueue initialization."""

    def test_initialization_execute_mode(self, mock_connection):
        """Test initialization in execute mode."""
        queue = LookupQueue(mock_connection, plan_only=False)

        assert queue.connection == mock_connection
        assert queue.plan_only is False

    def test_initialization_plan_only_mode(self, mock_connection):
        """Test initialization in plan-only mode."""
        queue = LookupQueue(mock_connection, plan_only=True)

        assert queue.connection == mock_connection
        assert queue.plan_only is True


class TestEnqueueOperations:
    """Test enqueue functionality with atomic operations."""

    def test_enqueue_successful(self, lookup_queue, mock_connection):
        """Test successful enqueue operation."""
        # Setup cursor mock to return a row
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Test Company",
            "normalized_name": "test company",
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = lookup_queue.enqueue("Test Company", "test company")

        # Verify SQL was executed correctly
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "INSERT INTO enterprise.lookup_requests" in sql_call[0]
        assert "RETURNING" in sql_call[0]

        # Verify parameters
        params = mock_cursor.execute.call_args[0][1]
        assert params == ("Test Company", "test company")

        # Verify result
        assert isinstance(result, LookupRequest)
        assert result.name == "Test Company"
        assert result.normalized_name == "test company"
        assert result.status == "pending"

    def test_enqueue_auto_normalize(self, lookup_queue, mock_connection):
        """Test enqueue with automatic normalization."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Test Company",
            "normalized_name": "test company",
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Call without providing normalized_name
        result = lookup_queue.enqueue("  Test Company  ")

        # Should auto-normalize the name
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == "Test Company"  # cleaned name
        assert params[1] == "test company"  # normalized name

    def test_enqueue_plan_only_mode(self, plan_only_queue):
        """Test enqueue in plan-only mode returns mock data."""
        result = plan_only_queue.enqueue("Test Company")

        # Should return mock LookupRequest without database operations
        assert isinstance(result, LookupRequest)
        assert result.name == "Test Company"
        assert result.status == "pending"

    def test_enqueue_empty_name_validation(self, lookup_queue):
        """Test enqueue validation for empty names."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            lookup_queue.enqueue("")

        with pytest.raises(ValueError, match="Name cannot be empty"):
            lookup_queue.enqueue("   ")

        with pytest.raises(ValueError, match="Name cannot be empty"):
            lookup_queue.enqueue(None)

    def test_enqueue_database_error(self, lookup_queue, mock_connection):
        """Test enqueue handles database errors properly."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")

        with pytest.raises(LookupQueueError, match="Failed to enqueue lookup request"):
            lookup_queue.enqueue("Test Company")

    def test_enqueue_no_row_returned(self, lookup_queue, mock_connection):
        """Test enqueue handles case when no row is returned."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        with pytest.raises(LookupQueueError, match="no row returned"):
            lookup_queue.enqueue("Test Company")


class TestDequeueAtomicOperations:
    """Test atomic dequeue operations with FOR UPDATE SKIP LOCKED."""

    def test_dequeue_successful_batch(self, lookup_queue, mock_connection):
        """Test successful atomic dequeue operation using CTE pattern."""
        # Setup cursor to return multiple rows
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_rows = [
            {
                "id": 1,
                "name": "Company 1",
                "normalized_name": "company 1",
                "status": "processing",
                "attempts": 0,
                "last_error": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "name": "Company 2",
                "normalized_name": "company 2",
                "status": "processing",
                "attempts": 0,
                "last_error": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ]
        mock_cursor.fetchall.return_value = mock_rows

        results = lookup_queue.dequeue(batch_size=10)

        # Verify SQL uses CTE pattern to avoid FOR UPDATE in subquery
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "WITH pending AS (" in sql_call[0]
        assert "SELECT id FROM enterprise.lookup_requests" in sql_call[0]
        assert "FOR UPDATE SKIP LOCKED" in sql_call[0]
        assert "UPDATE enterprise.lookup_requests" in sql_call[0]
        assert "FROM pending" in sql_call[0]
        assert "WHERE enterprise.lookup_requests.id = pending.id" in sql_call[0]
        assert "SET status = 'processing'" in sql_call[0]

        # Verify batch_size parameter
        params = mock_cursor.execute.call_args[0][1]
        assert params == (10,)

        # Verify results
        assert len(results) == 2
        assert all(isinstance(req, LookupRequest) for req in results)
        assert results[0].status == "processing"
        assert results[1].status == "processing"

    def test_dequeue_empty_queue(self, lookup_queue, mock_connection):
        """Test dequeue when queue is empty."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchall.return_value = []

        results = lookup_queue.dequeue(batch_size=5)

        assert results == []

    def test_dequeue_plan_only_mode(self, plan_only_queue):
        """Test dequeue in plan-only mode returns mock data."""
        results = plan_only_queue.dequeue(batch_size=2)

        # Should return mock requests
        assert len(results) <= 3  # Mock returns up to 3
        assert all(isinstance(req, LookupRequest) for req in results)
        assert all(req.status == "processing" for req in results)

    def test_dequeue_invalid_batch_size(self, lookup_queue):
        """Test dequeue validation for invalid batch size."""
        with pytest.raises(ValueError, match="Batch size must be positive"):
            lookup_queue.dequeue(batch_size=0)

        with pytest.raises(ValueError, match="Batch size must be positive"):
            lookup_queue.dequeue(batch_size=-1)

    def test_dequeue_database_error(self, lookup_queue, mock_connection):
        """Test dequeue handles database errors."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")

        with pytest.raises(LookupQueueError, match="Failed to dequeue requests"):
            lookup_queue.dequeue(batch_size=5)


class TestMarkDoneAndFailedOperations:
    """Test mark_done and mark_failed state transitions."""

    def test_mark_done_successful(self, lookup_queue, mock_connection):
        """Test successful mark_done operation."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.rowcount = 1  # One row updated

        lookup_queue.mark_done(request_id=123)

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "UPDATE enterprise.lookup_requests" in sql_call[0]
        assert "SET status = 'done'" in sql_call[0]
        assert "WHERE id = %s AND status = 'processing'" in sql_call[0]

        # Verify parameters
        params = mock_cursor.execute.call_args[0][1]
        assert params == (123,)

    def test_mark_done_request_not_found(self, lookup_queue, mock_connection):
        """Test mark_done when request not found or not in processing state."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.rowcount = 0  # No rows updated

        with pytest.raises(
            LookupQueueError, match="not found or not in processing state"
        ):
            lookup_queue.mark_done(request_id=999)

    def test_mark_failed_successful(self, lookup_queue, mock_connection):
        """Test successful mark_failed operation."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.rowcount = 1

        lookup_queue.mark_failed(
            request_id=456, error_message="EQC lookup failed", attempts=2
        )

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "SET status = 'failed'" in sql_call[0]
        assert "last_error = %s" in sql_call[0]
        assert "attempts = %s" in sql_call[0]

        # Verify parameters
        params = mock_cursor.execute.call_args[0][1]
        assert params == ("EQC lookup failed", 2, 456)

    def test_mark_failed_validation(self, lookup_queue):
        """Test mark_failed input validation."""
        with pytest.raises(ValueError, match="Request ID must be positive"):
            lookup_queue.mark_failed(request_id=0, error_message="Error", attempts=1)

        with pytest.raises(ValueError, match="Attempts must be non-negative"):
            lookup_queue.mark_failed(request_id=1, error_message="Error", attempts=-1)

    def test_mark_operations_plan_only_mode(self, plan_only_queue):
        """Test mark operations in plan-only mode."""
        # Should not raise errors, just log
        plan_only_queue.mark_done(request_id=123)
        plan_only_queue.mark_failed(request_id=456, error_message="Error", attempts=1)

    def test_mark_operations_database_errors(self, lookup_queue, mock_connection):
        """Test mark operations handle database errors."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")

        with pytest.raises(LookupQueueError):
            lookup_queue.mark_done(request_id=123)

        with pytest.raises(LookupQueueError):
            lookup_queue.mark_failed(request_id=456, error_message="Error", attempts=1)


class TestTempIdGeneration:
    """Test atomic temporary ID generation."""

    def test_get_next_temp_id_successful(self, lookup_queue, mock_connection):
        """Test successful temp ID generation."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (42,)  # Sequence value

        temp_id = lookup_queue.get_next_temp_id()

        # Verify SQL uses UPDATE...RETURNING for atomicity with new schema
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "UPDATE enterprise.temp_id_sequence" in sql_call[0]
        assert "SET last_number = last_number + 1, updated_at = now()" in sql_call[0]
        assert "RETURNING last_number" in sql_call[0]

        # Verify formatted temp ID
        assert temp_id == "TEMP_000042"

    def test_get_next_temp_id_handles_dict_row(self, lookup_queue, mock_connection):
        """Test temp ID generation works with dict-like cursor rows."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = {"last_number": 7}

        temp_id = lookup_queue.get_next_temp_id()

        assert temp_id == "TEMP_000007"
        mock_cursor.execute.assert_called_once()

    def test_get_next_temp_id_bootstraps_empty_sequence(
        self, lookup_queue, mock_connection
    ):
        """Test sequence table is seeded when empty."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.side_effect = [None, {"last_number": 1}]

        temp_id = lookup_queue.get_next_temp_id()

        assert temp_id == "TEMP_000001"
        sql_calls = [
            call_args[0][0] for call_args in mock_cursor.execute.call_args_list
        ]
        assert any(
            "INSERT INTO enterprise.temp_id_sequence" in sql for sql in sql_calls
        )
        assert mock_cursor.execute.call_count == 3

    def test_get_next_temp_id_uniqueness_sequential(
        self, lookup_queue, mock_connection
    ):
        """Test temp ID generation produces unique sequential IDs."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value

        # Simulate sequential sequence values
        mock_cursor.fetchone.side_effect = [(1,), (2,), (3,)]

        temp_id_1 = lookup_queue.get_next_temp_id()
        temp_id_2 = lookup_queue.get_next_temp_id()
        temp_id_3 = lookup_queue.get_next_temp_id()

        assert temp_id_1 == "TEMP_000001"
        assert temp_id_2 == "TEMP_000002"
        assert temp_id_3 == "TEMP_000003"

        # Verify each call incremented the sequence
        assert mock_cursor.execute.call_count == 3

    def test_get_next_temp_id_plan_only_mode(self, plan_only_queue):
        """Test temp ID generation in plan-only mode."""
        temp_id = plan_only_queue.get_next_temp_id()

        assert temp_id == "TEMP_000001"  # Mock value

    def test_get_next_temp_id_database_error(self, lookup_queue, mock_connection):
        """Test temp ID generation handles database errors."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = psycopg2.Error("Sequence error")

        with pytest.raises(LookupQueueError, match="Failed to generate temp ID"):
            lookup_queue.get_next_temp_id()

    def test_get_next_temp_id_no_sequence_value(self, lookup_queue, mock_connection):
        """Test temp ID generation when no sequence value returned."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.side_effect = [None, None]

        with pytest.raises(LookupQueueError, match="no sequence value returned"):
            lookup_queue.get_next_temp_id()

        sql_calls = [
            call_args[0][0] for call_args in mock_cursor.execute.call_args_list
        ]
        assert any(
            "INSERT INTO enterprise.temp_id_sequence" in sql for sql in sql_calls
        )
        assert mock_cursor.execute.call_count == 3


class TestConcurrentAccess:
    """Test concurrent access patterns for multi-worker scenarios."""

    def test_concurrent_temp_id_generation(self, mock_connection):
        """Test concurrent temp ID generation produces unique IDs."""
        # Simulate atomic sequence increment behavior
        sequence_counter = 0

        def mock_execute(sql, params=None):
            nonlocal sequence_counter
            if "UPDATE enterprise.temp_id_sequence" in sql:
                sequence_counter += 1

        def mock_fetchone():
            return (sequence_counter,)

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = mock_execute
        mock_cursor.fetchone.side_effect = mock_fetchone

        queue = LookupQueue(mock_connection)

        # Simulate concurrent access with multiple threads
        def generate_temp_id():
            return queue.get_next_temp_id()

        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit 10 concurrent temp ID generation requests
            futures = [executor.submit(generate_temp_id) for _ in range(10)]
            temp_ids = [future.result() for future in futures]

        # All temp IDs should be unique
        assert len(set(temp_ids)) == len(temp_ids)
        assert all(temp_id.startswith("TEMP_") for temp_id in temp_ids)

    def test_concurrent_dequeue_operations(self, mock_connection):
        """Test concurrent dequeue operations don't interfere."""
        call_count = 0

        def mock_execute(sql, params=None):
            nonlocal call_count
            call_count += 1

        def mock_fetchall():
            # Return different batches for each call
            if call_count == 1:
                return [
                    {
                        "id": 1,
                        "name": "Company 1",
                        "normalized_name": "company 1",
                        "status": "processing",
                        "attempts": 0,
                        "last_error": None,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                ]
            else:
                return []  # Subsequent calls return empty

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = mock_execute
        mock_cursor.fetchall.side_effect = mock_fetchall

        queue = LookupQueue(mock_connection)

        def dequeue_batch():
            return queue.dequeue(batch_size=5)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(dequeue_batch) for _ in range(3)]
            results = [future.result() for future in futures]

        # Only first call should get results due to atomic locking
        non_empty_results = [r for r in results if r]
        assert len(non_empty_results) <= 1  # At most one worker gets the batch


class TestQueueStatistics:
    """Test queue statistics and monitoring."""

    def test_get_queue_stats_successful(self, lookup_queue, mock_connection):
        """Test successful queue statistics retrieval."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchall.return_value = [
            ("pending", 15),
            ("processing", 3),
            ("done", 250),
            ("failed", 7),
        ]

        stats = lookup_queue.get_queue_stats()

        # Verify SQL query
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0]
        assert "SELECT" in sql_call[0]
        assert "COUNT(*)" in sql_call[0]
        assert "GROUP BY status" in sql_call[0]

        # Verify results
        assert stats == {"pending": 15, "processing": 3, "done": 250, "failed": 7}

    def test_get_queue_stats_missing_statuses(self, lookup_queue, mock_connection):
        """Test queue stats fills in missing status types."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchall.return_value = [
            ("pending", 5),
            ("done", 100),
        ]  # Missing 'processing' and 'failed'

        stats = lookup_queue.get_queue_stats()

        # Should include all status types with zero counts
        assert stats == {"pending": 5, "processing": 0, "done": 100, "failed": 0}

    def test_get_queue_stats_plan_only_mode(self, plan_only_queue):
        """Test queue stats in plan-only mode."""
        stats = plan_only_queue.get_queue_stats()

        # Should return mock stats
        assert isinstance(stats, dict)
        assert "pending" in stats
        assert "processing" in stats
        assert "done" in stats
        assert "failed" in stats

    def test_get_queue_stats_database_error(self, lookup_queue, mock_connection):
        """Test queue stats handles database errors."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = psycopg2.Error("Stats query failed")

        with pytest.raises(LookupQueueError, match="Failed to get queue stats"):
            lookup_queue.get_queue_stats()


class TestIntegrationPatterns:
    """Test integration patterns and real-world scenarios."""

    def test_full_queue_lifecycle(self, lookup_queue, mock_connection):
        """Test complete queue lifecycle: enqueue → dequeue → mark_done."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value

        # Enqueue phase
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Test Company",
            "normalized_name": "test company",
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        enqueued = lookup_queue.enqueue("Test Company")
        assert enqueued.status == "pending"

        # Dequeue phase
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "name": "Test Company",
                "normalized_name": "test company",
                "status": "processing",
                "attempts": 0,
                "last_error": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ]

        dequeued = lookup_queue.dequeue(batch_size=1)
        assert len(dequeued) == 1
        assert dequeued[0].status == "processing"

        # Mark done phase
        mock_cursor.rowcount = 1
        lookup_queue.mark_done(request_id=1)

        # Verify all phases called appropriate SQL
        assert mock_cursor.execute.call_count == 3

    def test_queue_error_recovery_patterns(self, lookup_queue, mock_connection):
        """Test error recovery patterns in queue operations."""
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value

        # First attempt fails
        mock_cursor.execute.side_effect = [
            psycopg2.Error("Transient error"),
            None,  # Second attempt succeeds
        ]
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "Retry Company",
            "normalized_name": "retry company",
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # First call should raise error
        with pytest.raises(LookupQueueError):
            lookup_queue.enqueue("Retry Company")

        # Reset mock for second attempt
        mock_cursor.execute.side_effect = None
        mock_cursor.execute.return_value = None

        # Second attempt should succeed
        result = lookup_queue.enqueue("Retry Company")
        assert result.name == "Retry Company"
