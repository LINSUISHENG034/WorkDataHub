"""
Unit tests for LegacyMySQLConnector.

Tests connection management, retry logic, and data fetching with mocked MySQL.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch, call
import pymysql

from work_data_hub.io.connectors.legacy_mysql_connector import LegacyMySQLConnector
from work_data_hub.domain.reference_backfill.sync_models import (
    ReferenceSyncTableConfig,
    ColumnMapping,
)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.legacy_mysql_host = "test-host"
    settings.legacy_mysql_port = 3306
    settings.legacy_mysql_user = "test_user"
    settings.legacy_mysql_password = "test_password"
    settings.legacy_mysql_database = "test_db"
    return settings


@pytest.fixture
def sample_table_config():
    """Create sample table configuration."""
    return ReferenceSyncTableConfig(
        name="test_sync",
        target_table="target_table",
        target_schema="business",
        source_type="legacy_mysql",
        source_config={
            "table": "source_table",
            "columns": [
                {"source": "id", "target": "计划号"},
                {"source": "name", "target": "计划名称"},
                {"source": "type", "target": "计划类型"},
            ],
        },
        sync_mode="upsert",
        primary_key="计划号",
    )


@pytest.fixture
def sample_mysql_data():
    """Create sample MySQL query results."""
    return [
        {"id": "A001", "name": "Plan 1", "type": "Type A"},
        {"id": "A002", "name": "Plan 2", "type": "Type B"},
        {"id": "A003", "name": "Plan 3", "type": "Type A"},
    ]


class TestLegacyMySQLConnector:
    """Test suite for LegacyMySQLConnector."""

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    def test_init(self, mock_get_settings, mock_settings):
        """Test connector initialization."""
        mock_get_settings.return_value = mock_settings

        connector = LegacyMySQLConnector(
            pool_size=5,
            max_overflow=2,
            connect_timeout=30,
            read_timeout=30,
            max_retries=3,
        )

        assert connector.connect_timeout == 30
        assert connector.read_timeout == 30
        assert connector.max_retries == 3
        assert connector.retry_backoff_base == 2.0

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.pymysql.connect')
    def test_get_connection_success(self, mock_connect, mock_get_settings, mock_settings):
        """Test successful connection establishment."""
        mock_get_settings.return_value = mock_settings
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        connector = LegacyMySQLConnector(max_retries=3)

        with connector.get_connection() as conn:
            assert conn == mock_conn

        # Verify connection was established with correct parameters
        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs['host'] == "test-host"
        assert call_kwargs['port'] == 3306
        assert call_kwargs['user'] == "test_user"
        assert call_kwargs['database'] == "test_db"

        # Verify connection was closed
        mock_conn.close.assert_called_once()

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.pymysql.connect')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.time.sleep')
    def test_get_connection_retry_success(
        self, mock_sleep, mock_connect, mock_get_settings, mock_settings
    ):
        """Test connection retry logic with eventual success."""
        mock_get_settings.return_value = mock_settings

        # First attempt fails, second succeeds
        mock_conn = MagicMock()
        mock_connect.side_effect = [
            pymysql.Error("Connection failed"),
            mock_conn,
        ]

        connector = LegacyMySQLConnector(max_retries=3, retry_backoff_base=2.0)

        with connector.get_connection() as conn:
            assert conn == mock_conn

        # Verify retry was attempted
        assert mock_connect.call_count == 2

        # Verify backoff was applied (2^1 = 2 seconds)
        mock_sleep.assert_called_once_with(2.0)

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.pymysql.connect')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.time.sleep')
    def test_get_connection_retry_exhausted(
        self, mock_sleep, mock_connect, mock_get_settings, mock_settings
    ):
        """Test connection failure after all retries exhausted."""
        mock_get_settings.return_value = mock_settings

        # All attempts fail
        mock_connect.side_effect = pymysql.Error("Connection failed")

        connector = LegacyMySQLConnector(max_retries=3, retry_backoff_base=2.0)

        with pytest.raises(pymysql.Error, match="Failed to connect"):
            with connector.get_connection():
                pass

        # Verify all retries were attempted
        assert mock_connect.call_count == 3

        # Verify backoff was applied: 2^1=2s, 2^2=4s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(2.0), call(4.0)])

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch.object(LegacyMySQLConnector, 'get_connection')
    def test_fetch_data_success(
        self,
        mock_get_connection,
        mock_get_settings,
        mock_settings,
        sample_table_config,
        sample_mysql_data,
    ):
        """Test successful data fetch."""
        mock_get_settings.return_value = mock_settings

        # Mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = sample_mysql_data
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        mock_get_connection.return_value = mock_conn

        connector = LegacyMySQLConnector()
        df = connector.fetch_data(sample_table_config)

        # Verify DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

        # Verify column mappings were applied
        assert "计划号" in df.columns
        assert "计划名称" in df.columns
        assert "计划类型" in df.columns

        # Verify data values
        assert df["计划号"].tolist() == ["A001", "A002", "A003"]
        assert df["计划名称"].tolist() == ["Plan 1", "Plan 2", "Plan 3"]

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch.object(LegacyMySQLConnector, 'get_connection')
    def test_fetch_data_empty_result(
        self,
        mock_get_connection,
        mock_get_settings,
        mock_settings,
        sample_table_config,
    ):
        """Test fetch with empty result set."""
        mock_get_settings.return_value = mock_settings

        # Mock connection and cursor with empty result
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        mock_get_connection.return_value = mock_conn

        connector = LegacyMySQLConnector()
        df = connector.fetch_data(sample_table_config)

        # Verify empty DataFrame with correct columns
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "计划号" in df.columns
        assert "计划名称" in df.columns
        assert "计划类型" in df.columns

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    def test_fetch_data_invalid_config(self, mock_get_settings, mock_settings):
        """Test fetch with invalid source configuration."""
        mock_get_settings.return_value = mock_settings

        # Invalid config - missing required fields
        invalid_config = ReferenceSyncTableConfig(
            name="test_sync",
            target_table="target_table",
            target_schema="business",
            source_type="legacy_mysql",
            source_config={
                "invalid_field": "value"
            },
            sync_mode="upsert",
            primary_key="id",
        )

        connector = LegacyMySQLConnector()

        with pytest.raises(ValueError, match="Invalid Legacy MySQL source config"):
            connector.fetch_data(invalid_config)

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    @patch.object(LegacyMySQLConnector, 'get_connection')
    @patch('work_data_hub.io.connectors.legacy_mysql_connector.time.sleep')
    def test_fetch_data_query_retry(
        self,
        mock_sleep,
        mock_get_connection,
        mock_get_settings,
        mock_settings,
        sample_table_config,
        sample_mysql_data,
    ):
        """Test query retry logic on failure."""
        mock_get_settings.return_value = mock_settings

        # First query fails, second succeeds
        mock_cursor_fail = MagicMock()
        mock_cursor_fail.execute.side_effect = pymysql.Error("Query failed")
        mock_cursor_fail.__enter__ = Mock(return_value=mock_cursor_fail)
        mock_cursor_fail.__exit__ = Mock(return_value=False)

        mock_cursor_success = MagicMock()
        mock_cursor_success.fetchall.return_value = sample_mysql_data
        mock_cursor_success.__enter__ = Mock(return_value=mock_cursor_success)
        mock_cursor_success.__exit__ = Mock(return_value=False)

        mock_conn_fail = MagicMock()
        mock_conn_fail.cursor.return_value = mock_cursor_fail
        mock_conn_fail.__enter__ = Mock(return_value=mock_conn_fail)
        mock_conn_fail.__exit__ = Mock(return_value=False)

        mock_conn_success = MagicMock()
        mock_conn_success.cursor.return_value = mock_cursor_success
        mock_conn_success.__enter__ = Mock(return_value=mock_conn_success)
        mock_conn_success.__exit__ = Mock(return_value=False)

        mock_get_connection.side_effect = [mock_conn_fail, mock_conn_success]

        connector = LegacyMySQLConnector(max_retries=3)
        df = connector.fetch_data(sample_table_config)

        # Verify data was fetched successfully after retry
        assert len(df) == 3

        # Verify backoff was applied
        mock_sleep.assert_called_once_with(2.0)

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    def test_apply_column_mappings(self, mock_get_settings, mock_settings):
        """Test column mapping application."""
        mock_get_settings.return_value = mock_settings

        connector = LegacyMySQLConnector()

        # Create test DataFrame
        df = pd.DataFrame({
            'id': ['A001', 'A002'],
            'name': ['Plan 1', 'Plan 2'],
            'type': ['Type A', 'Type B'],
        })

        # Create source config with mappings
        from work_data_hub.domain.reference_backfill.sync_models import LegacyMySQLSourceConfig
        source_config = LegacyMySQLSourceConfig(
            table="source_table",
            columns=[
                ColumnMapping(source="id", target="计划号"),
                ColumnMapping(source="name", target="计划名称"),
                ColumnMapping(source="type", target="计划类型"),
            ],
        )

        # Apply mappings
        result_df = connector._apply_column_mappings(df, source_config)

        # Verify column names were mapped
        assert "计划号" in result_df.columns
        assert "计划名称" in result_df.columns
        assert "计划类型" in result_df.columns

        # Verify original columns are gone
        assert "id" not in result_df.columns
        assert "name" not in result_df.columns
        assert "type" not in result_df.columns

        # Verify data is preserved
        assert result_df["计划号"].tolist() == ['A001', 'A002']
        assert result_df["计划名称"].tolist() == ['Plan 1', 'Plan 2']

    @patch('work_data_hub.io.connectors.legacy_mysql_connector.get_settings')
    def test_apply_column_mappings_empty_dataframe(self, mock_get_settings, mock_settings):
        """Test column mapping with empty DataFrame."""
        mock_get_settings.return_value = mock_settings

        connector = LegacyMySQLConnector()

        # Create empty DataFrame
        df = pd.DataFrame()

        # Create source config with mappings
        from work_data_hub.domain.reference_backfill.sync_models import LegacyMySQLSourceConfig
        source_config = LegacyMySQLSourceConfig(
            table="source_table",
            columns=[
                ColumnMapping(source="id", target="计划号"),
                ColumnMapping(source="name", target="计划名称"),
            ],
        )

        # Apply mappings
        result_df = connector._apply_column_mappings(df, source_config)

        # Verify empty DataFrame with target column names
        assert len(result_df) == 0
        assert "计划号" in result_df.columns
        assert "计划名称" in result_df.columns
