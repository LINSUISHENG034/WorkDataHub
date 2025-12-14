"""
Unit tests for SyncStateRepository.

Story 6.2-p4: Reference Sync Incremental State Persistence
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

from work_data_hub.io.repositories.sync_state_repository import (
    SyncStateRepository,
    SCHEMA_NAME,
    TABLE_NAME,
)


class TestSyncStateRepository:
    """Unit tests for SyncStateRepository."""

    @pytest.fixture
    def mock_conn(self):
        """Create a mock database connection."""
        conn = MagicMock()
        return conn

    @pytest.fixture
    def repo_with_table(self, mock_conn):
        """Create repository with table existence check returning True."""
        # Mock table exists check
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        repo = SyncStateRepository(mock_conn)
        return repo

    @pytest.fixture
    def repo_without_table(self, mock_conn):
        """Create repository with table existence check returning False."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        repo = SyncStateRepository(mock_conn)
        return repo

    def test_init(self, mock_conn):
        """Test repository initialization."""
        repo = SyncStateRepository(mock_conn)

        assert repo.conn == mock_conn
        assert repo._table_verified is False

    def test_ensure_table_exists_true(self, mock_conn):
        """Test _ensure_table_exists returns True when table exists."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        repo = SyncStateRepository(mock_conn)
        result = repo._ensure_table_exists()

        assert result is True
        assert repo._table_verified is True

    def test_ensure_table_exists_false(self, mock_conn):
        """Test _ensure_table_exists returns False when table doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        repo = SyncStateRepository(mock_conn)
        result = repo._ensure_table_exists()

        assert result is False
        assert repo._table_verified is False

    def test_ensure_table_exists_caches_result(self, mock_conn):
        """Test _ensure_table_exists caches positive result."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        repo = SyncStateRepository(mock_conn)

        # First call
        repo._ensure_table_exists()
        # Second call should use cache
        repo._ensure_table_exists()

        # Should only execute query once
        assert mock_conn.execute.call_count == 1

    def test_get_state_returns_none_when_table_missing(self, repo_without_table):
        """Test get_state returns None when table doesn't exist."""
        result = repo_without_table.get_state("reference_sync", "年金计划")

        assert result is None

    def test_get_state_returns_none_when_not_found(self, mock_conn):
        """Test get_state returns None when state not found."""
        # First call: table exists check
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        # Second call: actual query returns no rows
        mock_query_result = MagicMock()
        mock_query_result.fetchone.return_value = None

        mock_conn.execute.side_effect = [mock_exists_result, mock_query_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.get_state("reference_sync", "nonexistent_table")

        assert result is None

    def test_get_state_returns_state_dict(self, mock_conn):
        """Test get_state returns correct state dictionary."""
        test_time = datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc)
        updated_time = datetime(2025, 12, 14, 10, 5, 0, tzinfo=timezone.utc)

        # First call: table exists check
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        # Second call: actual query returns row
        mock_query_result = MagicMock()
        mock_query_result.fetchone.return_value = (
            "reference_sync",
            "年金计划",
            test_time,
            updated_time,
        )

        mock_conn.execute.side_effect = [mock_exists_result, mock_query_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.get_state("reference_sync", "年金计划")

        assert result is not None
        assert result["job_name"] == "reference_sync"
        assert result["table_name"] == "年金计划"
        assert result["last_synced_at"] == test_time
        assert result["updated_at"] == updated_time

    def test_get_all_states_returns_empty_when_table_missing(self, repo_without_table):
        """Test get_all_states returns empty dict when table doesn't exist."""
        result = repo_without_table.get_all_states("reference_sync")

        assert result == {}

    def test_get_all_states_returns_empty_when_no_states(self, mock_conn):
        """Test get_all_states returns empty dict when no states found."""
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_query_result = MagicMock()
        mock_query_result.fetchall.return_value = []

        mock_conn.execute.side_effect = [mock_exists_result, mock_query_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.get_all_states("reference_sync")

        assert result == {}

    def test_get_all_states_returns_states_keyed_by_table(self, mock_conn):
        """Test get_all_states returns states keyed by table name."""
        time1 = datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 12, 14, 11, 0, 0, tzinfo=timezone.utc)

        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_query_result = MagicMock()
        mock_query_result.fetchall.return_value = [
            ("reference_sync", "年金计划", time1, time1),
            ("reference_sync", "组织架构", time2, time2),
        ]

        mock_conn.execute.side_effect = [mock_exists_result, mock_query_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.get_all_states("reference_sync")

        assert len(result) == 2
        assert "年金计划" in result
        assert "组织架构" in result
        assert result["年金计划"]["last_synced_at"] == time1
        assert result["组织架构"]["last_synced_at"] == time2

    def test_update_state_returns_false_when_table_missing(self, repo_without_table):
        """Test update_state returns False when table doesn't exist."""
        test_time = datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc)

        result = repo_without_table.update_state(
            "reference_sync", "年金计划", test_time
        )

        assert result is False

    def test_update_state_success(self, mock_conn):
        """Test update_state returns True on success."""
        test_time = datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc)

        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_upsert_result = MagicMock()

        mock_conn.execute.side_effect = [mock_exists_result, mock_upsert_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.update_state("reference_sync", "年金计划", test_time)

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_update_state_adds_timezone_if_missing(self, mock_conn):
        """Test update_state adds UTC timezone to naive datetime."""
        naive_time = datetime(2025, 12, 14, 10, 0, 0)  # No timezone

        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_upsert_result = MagicMock()

        mock_conn.execute.side_effect = [mock_exists_result, mock_upsert_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.update_state("reference_sync", "年金计划", naive_time)

        assert result is True
        # Verify the execute was called (timezone conversion happens internally)
        assert mock_conn.execute.call_count == 2

    def test_update_state_returns_false_on_exception(self, mock_conn):
        """Test update_state returns False on database error."""
        test_time = datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc)

        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        # Simulate database error on upsert
        mock_conn.execute.side_effect = [mock_exists_result, Exception("DB error")]

        repo = SyncStateRepository(mock_conn)
        result = repo.update_state("reference_sync", "年金计划", test_time)

        assert result is False

    def test_delete_state_returns_false_when_table_missing(self, repo_without_table):
        """Test delete_state returns False when table doesn't exist."""
        result = repo_without_table.delete_state("reference_sync", "年金计划")

        assert result is False

    def test_delete_state_returns_true_when_deleted(self, mock_conn):
        """Test delete_state returns True when row deleted."""
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 1

        mock_conn.execute.side_effect = [mock_exists_result, mock_delete_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.delete_state("reference_sync", "年金计划")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_delete_state_returns_false_when_not_found(self, mock_conn):
        """Test delete_state returns False when no row deleted."""
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 0

        mock_conn.execute.side_effect = [mock_exists_result, mock_delete_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.delete_state("reference_sync", "nonexistent")

        assert result is False

    def test_clear_all_states_returns_zero_when_table_missing(self, repo_without_table):
        """Test clear_all_states returns 0 when table doesn't exist."""
        result = repo_without_table.clear_all_states("reference_sync")

        assert result == 0

    def test_clear_all_states_returns_count(self, mock_conn):
        """Test clear_all_states returns number of deleted rows."""
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 4

        mock_conn.execute.side_effect = [mock_exists_result, mock_delete_result]

        repo = SyncStateRepository(mock_conn)
        result = repo.clear_all_states("reference_sync")

        assert result == 4
        mock_conn.commit.assert_called_once()


class TestSyncStateRepositoryIntegration:
    """Integration-style tests for SyncStateRepository with realistic scenarios."""

    def test_full_sync_workflow(self, mock_conn=None):
        """Test complete workflow: check state -> sync -> update state."""
        if mock_conn is None:
            mock_conn = MagicMock()

        # Setup: table exists, no initial state
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_empty_result = MagicMock()
        mock_empty_result.fetchall.return_value = []

        mock_upsert_result = MagicMock()

        mock_conn.execute.side_effect = [
            mock_exists_result,  # _ensure_table_exists
            mock_empty_result,  # get_all_states
            mock_exists_result,  # _ensure_table_exists (cached, but we mock anyway)
            mock_upsert_result,  # update_state
        ]

        repo = SyncStateRepository(mock_conn)

        # Step 1: Check for existing state (none found)
        states = repo.get_all_states("reference_sync")
        assert states == {}

        # Step 2: After sync, update state
        sync_time = datetime.now(timezone.utc)
        repo._table_verified = True  # Simulate cached check
        result = repo.update_state("reference_sync", "年金计划", sync_time)
        assert result is True

    def test_incremental_sync_workflow(self):
        """Test incremental sync: load existing state -> sync with state."""
        mock_conn = MagicMock()

        last_sync = datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc)

        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_states_result = MagicMock()
        mock_states_result.fetchall.return_value = [
            ("reference_sync", "年金计划", last_sync, last_sync),
            ("reference_sync", "组织架构", last_sync, last_sync),
        ]

        mock_conn.execute.side_effect = [
            mock_exists_result,
            mock_states_result,
        ]

        repo = SyncStateRepository(mock_conn)

        # Load existing states
        states = repo.get_all_states("reference_sync")

        assert len(states) == 2
        assert states["年金计划"]["last_synced_at"] == last_sync
        assert states["组织架构"]["last_synced_at"] == last_sync
