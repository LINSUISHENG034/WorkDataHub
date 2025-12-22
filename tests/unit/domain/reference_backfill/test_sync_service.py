"""
Unit tests for ReferenceSyncService.

Tests the core sync logic, tracking fields, and sync modes.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import text

from work_data_hub.domain.reference_backfill.sync_service import (
    ReferenceSyncService,
    SyncResult,
    DataSourceAdapter,
)
from work_data_hub.domain.reference_backfill.sync_models import (
    ReferenceSyncTableConfig,
)


@pytest.fixture
def mock_adapter():
    """Create a mock data source adapter."""
    adapter = Mock(spec=DataSourceAdapter)
    return adapter


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = MagicMock()
    conn.dialect.name = "postgresql"
    return conn


@pytest.fixture
def sample_config():
    """Create a sample table sync configuration."""
    return ReferenceSyncTableConfig(
        name="test_sync",
        target_table="test_table",
        target_schema="business",
        source_type="legacy_mysql",
        source_config={"table": "source_table"},
        sync_mode="upsert",
        primary_key="id",
    )


@pytest.fixture
def sample_data():
    """Create sample reference data."""
    return pd.DataFrame(
        {
            "id": ["A001", "A002", "A003"],
            "name": ["Test 1", "Test 2", "Test 3"],
            "type": ["Type A", "Type B", "Type A"],
        }
    )


class TestReferenceSyncService:
    """Test suite for ReferenceSyncService."""

    def test_init(self):
        """Test service initialization."""
        service = ReferenceSyncService(domain="test_domain")
        assert service.domain == "test_domain"
        assert service.logger is not None

    def test_add_authoritative_tracking_fields(self, sample_data):
        """Test adding authoritative tracking fields."""
        service = ReferenceSyncService()
        result_df = service._add_authoritative_tracking_fields(sample_data)

        # Check tracking fields are added
        assert "_source" in result_df.columns
        assert "_needs_review" in result_df.columns
        assert "_derived_from_domain" in result_df.columns
        assert "_derived_at" in result_df.columns

        # Check values are correct
        assert all(result_df["_source"] == "authoritative")
        assert all(result_df["_needs_review"] == False)
        assert all(result_df["_derived_from_domain"].isna())
        assert all(result_df["_derived_at"].isna())

        # Check original data is preserved
        assert all(result_df["id"] == sample_data["id"])
        assert all(result_df["name"] == sample_data["name"])

    def test_sync_table_plan_only(
        self, sample_config, sample_data, mock_adapter, mock_connection
    ):
        """Test sync_table in plan-only mode."""
        service = ReferenceSyncService()
        mock_adapter.fetch_data.return_value = sample_data

        result = service.sync_table(
            sample_config, mock_adapter, mock_connection, plan_only=True
        )

        # Verify result
        assert isinstance(result, SyncResult)
        assert result.table == "test_table"
        assert result.source_type == "legacy_mysql"
        assert result.rows_synced == 0  # Plan-only doesn't sync
        assert result.rows_deleted == 0
        assert result.sync_mode == "upsert"
        assert result.error is None

        # Verify adapter was called
        mock_adapter.fetch_data.assert_called_once()

        # Verify no database operations
        mock_connection.execute.assert_not_called()

    def test_sync_table_empty_data(self, sample_config, mock_adapter, mock_connection):
        """Test sync_table with empty data from source."""
        service = ReferenceSyncService()
        mock_adapter.fetch_data.return_value = pd.DataFrame()

        result = service.sync_table(
            sample_config, mock_adapter, mock_connection, plan_only=False
        )

        # Verify result
        assert result.rows_synced == 0
        assert result.rows_deleted == 0
        assert result.error is None

        # Verify no database operations
        mock_connection.execute.assert_not_called()

    def test_sync_all_success(
        self, sample_config, sample_data, mock_adapter, mock_connection
    ):
        """Test sync_all with successful sync operations."""
        service = ReferenceSyncService()
        mock_adapter.fetch_data.return_value = sample_data

        # Mock database operations
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        configs = [sample_config]
        adapters = {"legacy_mysql": mock_adapter}

        results = service.sync_all(configs, adapters, mock_connection, plan_only=False)

        # Verify results
        assert len(results) == 1
        assert results[0].table == "test_table"
        assert results[0].error is None

    def test_sync_all_missing_adapter(self, sample_config, mock_connection):
        """Test sync_all with missing adapter."""
        service = ReferenceSyncService()

        configs = [sample_config]
        adapters = {}  # No adapters provided

        results = service.sync_all(configs, adapters, mock_connection, plan_only=False)

        # Verify error result
        assert len(results) == 1
        assert results[0].table == "test_table"
        assert results[0].error is not None
        assert "No adapter found" in results[0].error

    def test_sync_all_adapter_exception(
        self, sample_config, mock_adapter, mock_connection
    ):
        """Test sync_all when adapter raises exception."""
        service = ReferenceSyncService()
        mock_adapter.fetch_data.side_effect = Exception("Connection failed")

        configs = [sample_config]
        adapters = {"legacy_mysql": mock_adapter}

        results = service.sync_all(configs, adapters, mock_connection, plan_only=False)

        # Verify error result
        assert len(results) == 1
        assert results[0].table == "test_table"
        assert results[0].error is not None
        assert "Connection failed" in results[0].error

    def test_batch_insert(self, sample_config, sample_data, mock_connection):
        """Test batch insert functionality."""
        service = ReferenceSyncService()

        # Mock execute result
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        rows_inserted = service._batch_insert(
            sample_data,
            sample_config,
            mock_connection,
            batch_size=2,  # Small batch size to test batching
        )

        # Verify result
        assert rows_inserted == 6  # 3 rows * 2 batches

        # Verify execute was called twice (2 batches)
        assert mock_connection.execute.call_count == 2

        # Verify commit was called
        mock_connection.commit.assert_called()

    def test_batch_insert_empty_dataframe(self, sample_config, mock_connection):
        """Test batch insert with empty DataFrame."""
        service = ReferenceSyncService()

        rows_inserted = service._batch_insert(
            pd.DataFrame(), sample_config, mock_connection
        )

        # Verify no operations
        assert rows_inserted == 0
        mock_connection.execute.assert_not_called()

    def test_sync_upsert_postgresql(self, sample_config, sample_data, mock_connection):
        """Test upsert sync mode with PostgreSQL."""
        service = ReferenceSyncService()
        mock_connection.dialect.name = "postgresql"

        # Add tracking fields
        df_with_tracking = service._add_authoritative_tracking_fields(sample_data)

        # Mock execute result
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        rows_synced = service._sync_upsert(
            df_with_tracking, sample_config, mock_connection, batch_size=5000
        )

        # Verify result
        assert rows_synced == 3

        # Verify PostgreSQL-specific query was used
        call_args = mock_connection.execute.call_args
        query = str(call_args[0][0])
        assert "ON CONFLICT" in query
        assert "DO UPDATE" in query

    def test_sync_delete_insert(self, sample_config, sample_data, mock_connection):
        """Test delete-insert sync mode."""
        service = ReferenceSyncService()

        # Add tracking fields
        df_with_tracking = service._add_authoritative_tracking_fields(sample_data)

        # Mock transaction
        mock_trans = MagicMock()
        mock_connection.begin.return_value = mock_trans

        # Mock delete result
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 5

        # Mock insert result
        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 3

        def execute_side_effect(query, params=None):
            query_str = str(query).strip().upper()
            if query_str.startswith("DELETE"):
                return mock_delete_result
            return mock_insert_result

        mock_connection.execute.side_effect = execute_side_effect

        rows_deleted, rows_inserted = service._sync_delete_insert(
            df_with_tracking,
            sample_config,
            mock_connection,
            batch_size=5000,
        )

        # Verify results
        assert rows_deleted == 5
        assert rows_inserted == 3

        # Verify transaction was committed
        mock_trans.commit.assert_called_once()

    def test_sync_delete_insert_rollback_on_error(
        self, sample_config, sample_data, mock_connection
    ):
        """Test delete-insert rollback on error."""
        service = ReferenceSyncService()

        # Add tracking fields
        df_with_tracking = service._add_authoritative_tracking_fields(sample_data)

        # Mock transaction
        mock_trans = MagicMock()
        mock_connection.begin.return_value = mock_trans

        # Mock delete success, insert failure
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 5
        mock_connection.execute.side_effect = [
            mock_delete_result,
            Exception("Insert failed"),
        ]

        # Verify exception is raised
        with pytest.raises(Exception, match="Insert failed"):
            service._sync_delete_insert(
                df_with_tracking,
                sample_config,
                mock_connection,
                batch_size=5000,
            )

        # Verify transaction was rolled back
        mock_trans.rollback.assert_called_once()
        mock_trans.commit.assert_not_called()


class TestSyncResult:
    """Test suite for SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test creating a SyncResult."""
        result = SyncResult(
            table="test_table",
            source_type="legacy_mysql",
            rows_synced=100,
            rows_deleted=10,
            sync_mode="upsert",
            duration_seconds=5.5,
        )

        assert result.table == "test_table"
        assert result.source_type == "legacy_mysql"
        assert result.rows_synced == 100
        assert result.rows_deleted == 10
        assert result.sync_mode == "upsert"
        assert result.duration_seconds == 5.5
        assert result.error is None

    def test_sync_result_with_error(self):
        """Test creating a SyncResult with error."""
        result = SyncResult(
            table="test_table",
            source_type="legacy_mysql",
            rows_synced=0,
            rows_deleted=0,
            sync_mode="upsert",
            duration_seconds=1.0,
            error="Connection failed",
        )

        assert result.error == "Connection failed"
        assert result.rows_synced == 0
