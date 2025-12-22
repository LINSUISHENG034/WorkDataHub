"""
Integration tests for Reference Sync operations.

Story 6.2.4: Pre-load Reference Sync Service
Tests end-to-end sync, Dagster job execution, and schedule triggering.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
import pandas as pd

from dagster import build_op_context

from work_data_hub.domain.reference_backfill.sync_service import (
    ReferenceSyncService,
    SyncResult,
)
from work_data_hub.domain.reference_backfill.sync_models import (
    ReferenceSyncConfig,
    ReferenceSyncTableConfig,
)
from work_data_hub.domain.reference_backfill.sync_config_loader import (
    load_reference_sync_config,
)
from work_data_hub.io.connectors.legacy_mysql_connector import LegacyMySQLConnector
from work_data_hub.io.connectors.config_file_connector import ConfigFileConnector
from work_data_hub.orchestration.reference_sync_ops import (
    reference_sync_op,
    ReferenceSyncOpConfig,
)
from work_data_hub.orchestration.reference_sync_jobs import reference_sync_job
from work_data_hub.orchestration.schedules import reference_sync_schedule


class TestReferenceSyncEndToEnd:
    """End-to-end integration tests for reference sync operations."""

    @pytest.fixture
    def mock_legacy_mysql_data(self):
        """Sample data from Legacy MySQL."""
        return pd.DataFrame(
            {
                "plan_code": [f"P{i:04d}" for i in range(100)],
                "plan_name": [f"Plan {i}" for i in range(100)],
                "plan_type": ["Type A" if i % 2 == 0 else "Type B" for i in range(100)],
                "customer_name": [f"Customer {i}" for i in range(100)],
            }
        )

    @pytest.fixture
    def mock_config_file_data(self):
        """Sample data from config file."""
        return pd.DataFrame(
            {
                "产品线代码": ["PL001", "PL002", "PL003", "PL004"],
                "产品线名称": ["企业年金", "职业年金", "养老保障", "个人养老金"],
            }
        )

    @pytest.fixture
    def sample_sync_config(self):
        """Create sample sync configuration."""
        return ReferenceSyncConfig(
            enabled=True,
            schedule="0 1 * * *",
            concurrency=1,
            batch_size=5000,
            tables=[
                ReferenceSyncTableConfig(
                    name="年金计划",
                    target_table="年金计划",
                    target_schema="business",
                    source_type="legacy_mysql",
                    source_config={
                        "table": "annuity_plan",
                        "columns": [
                            {"source": "plan_code", "target": "年金计划号"},
                            {"source": "plan_name", "target": "计划名称"},
                            {"source": "plan_type", "target": "计划类型"},
                            {"source": "customer_name", "target": "客户名称"},
                        ],
                    },
                    sync_mode="upsert",
                    primary_key="年金计划号",
                ),
                ReferenceSyncTableConfig(
                    name="产品线",
                    target_table="产品线",
                    target_schema="business",
                    source_type="config_file",
                    source_config={
                        "file_path": "config/reference_data/product_lines.yml",
                        "schema_version": "1.0",
                    },
                    sync_mode="delete_insert",
                    primary_key="产品线代码",
                ),
            ],
        )

    def test_sync_service_with_multiple_sources(
        self,
        sample_sync_config,
        mock_legacy_mysql_data,
        mock_config_file_data,
    ):
        """Test sync service handles multiple data sources correctly."""
        # Create mock adapters
        mock_mysql_adapter = Mock()
        mock_mysql_adapter.fetch_data.return_value = mock_legacy_mysql_data.rename(
            columns={
                "plan_code": "年金计划号",
                "plan_name": "计划名称",
                "plan_type": "计划类型",
                "customer_name": "客户名称",
            }
        )

        mock_config_adapter = Mock()
        mock_config_adapter.fetch_data.return_value = mock_config_file_data

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.dialect.name = "postgresql"
        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_conn.execute.return_value = mock_result

        # Initialize service
        service = ReferenceSyncService(domain="reference_sync")

        # Execute sync
        results = service.sync_all(
            configs=sample_sync_config.tables,
            adapters={
                "legacy_mysql": mock_mysql_adapter,
                "config_file": mock_config_adapter,
            },
            conn=mock_conn,
            plan_only=False,
        )

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, SyncResult) for r in results)
        assert results[0].table == "年金计划"
        assert results[1].table == "产品线"

        # Verify adapters were called
        mock_mysql_adapter.fetch_data.assert_called_once()
        mock_config_adapter.fetch_data.assert_called_once()

    def test_sync_service_tracking_fields_applied(
        self,
        sample_sync_config,
        mock_legacy_mysql_data,
    ):
        """Test that authoritative tracking fields are correctly applied."""
        service = ReferenceSyncService()

        # Prepare test data
        df = mock_legacy_mysql_data.rename(
            columns={
                "plan_code": "年金计划号",
                "plan_name": "计划名称",
                "plan_type": "计划类型",
                "customer_name": "客户名称",
            }
        )

        # Apply tracking fields
        result_df = service._add_authoritative_tracking_fields(df)

        # Verify tracking fields
        assert "_source" in result_df.columns
        assert "_needs_review" in result_df.columns
        assert "_derived_from_domain" in result_df.columns
        assert "_derived_at" in result_df.columns

        # Verify values
        assert all(result_df["_source"] == "authoritative")
        assert all(result_df["_needs_review"] == False)
        assert all(result_df["_derived_from_domain"].isna())
        assert all(result_df["_derived_at"].isna())

    def test_sync_service_handles_partial_failures(self, sample_sync_config):
        """Test sync continues when one source fails."""
        # Create adapters - one fails, one succeeds
        mock_mysql_adapter = Mock()
        mock_mysql_adapter.fetch_data.side_effect = Exception("MySQL connection failed")

        mock_config_adapter = Mock()
        mock_config_adapter.fetch_data.return_value = pd.DataFrame(
            {
                "产品线代码": ["PL001"],
                "产品线名称": ["企业年金"],
            }
        )

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.dialect.name = "postgresql"
        mock_trans = MagicMock()
        mock_conn.begin.return_value = mock_trans
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn.execute.return_value = mock_result

        # Initialize service
        service = ReferenceSyncService(domain="reference_sync")

        # Execute sync
        results = service.sync_all(
            configs=sample_sync_config.tables,
            adapters={
                "legacy_mysql": mock_mysql_adapter,
                "config_file": mock_config_adapter,
            },
            conn=mock_conn,
            plan_only=False,
        )

        # Verify results - first failed, second succeeded
        assert len(results) == 2
        assert results[0].error is not None
        assert "MySQL connection failed" in results[0].error
        assert results[1].error is None


class TestDagsterJobExecution:
    """Tests for Dagster job and op execution."""

    @patch("work_data_hub.orchestration.reference_sync_ops.get_settings")
    @patch("work_data_hub.orchestration.reference_sync_ops.load_reference_sync_config")
    @patch("work_data_hub.orchestration.reference_sync_ops.create_engine")
    @patch("work_data_hub.orchestration.reference_sync_ops.AdapterFactory")
    @patch("work_data_hub.orchestration.reference_sync_ops.SyncStateRepository")
    def test_reference_sync_op_execution(
        self,
        mock_state_repo_class,
        mock_adapter_factory,
        mock_create_engine,
        mock_load_config,
        mock_get_settings,
    ):
        """Test reference_sync_op executes correctly."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.get_database_connection_string.return_value = "postgresql://test"
        mock_get_settings.return_value = mock_settings

        mock_config = Mock()
        mock_config.enabled = True
        mock_config.tables = []
        mock_config.batch_size = 5000
        mock_load_config.return_value = mock_config

        mock_adapter_factory.create_adapters_for_configs.return_value = {}

        mock_state_repo = MagicMock()
        mock_state_repo.get_all_states.return_value = {}
        mock_state_repo_class.return_value = mock_state_repo

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine

        # Build context and execute
        context = build_op_context()
        config = ReferenceSyncOpConfig(plan_only=True)

        result = reference_sync_op(context, config)

        # Verify result
        assert result["status"] == "success"
        assert "total_synced" in result
        assert "failed_count" in result
        assert "states_persisted" in result

    @patch("work_data_hub.orchestration.reference_sync_ops.get_settings")
    @patch("work_data_hub.orchestration.reference_sync_ops.load_reference_sync_config")
    def test_reference_sync_op_disabled(
        self,
        mock_load_config,
        mock_get_settings,
    ):
        """Test reference_sync_op skips when disabled."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        mock_config = Mock()
        mock_config.enabled = False
        mock_load_config.return_value = mock_config

        context = build_op_context()
        config = ReferenceSyncOpConfig(plan_only=True)

        result = reference_sync_op(context, config)

        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    @patch("work_data_hub.orchestration.reference_sync_ops.get_settings")
    @patch("work_data_hub.orchestration.reference_sync_ops.load_reference_sync_config")
    def test_reference_sync_op_no_config(
        self,
        mock_load_config,
        mock_get_settings,
    ):
        """Test reference_sync_op handles missing config."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        mock_load_config.return_value = None

        context = build_op_context()
        config = ReferenceSyncOpConfig(plan_only=True)

        result = reference_sync_op(context, config)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_config"


class TestScheduleTrigger:
    """Tests for schedule triggering."""

    @patch("work_data_hub.orchestration.schedules.get_settings")
    def test_reference_sync_schedule_enabled(self, mock_get_settings):
        """Test schedule triggers when enabled."""
        from dagster import build_schedule_context

        mock_settings = Mock()
        mock_settings.reference_sync_enabled = True
        mock_get_settings.return_value = mock_settings

        # Use Dagster's build_schedule_context for proper testing
        context = build_schedule_context(
            scheduled_execution_time=datetime(
                2025, 12, 12, 1, 0, 0, tzinfo=timezone.utc
            )
        )

        result = reference_sync_schedule(context)

        # Verify RunRequest is returned
        assert result is not None
        assert "reference_sync_" in result.run_key
        assert (
            result.run_config["ops"]["reference_sync_op"]["config"]["plan_only"]
            == False
        )

    @patch("work_data_hub.orchestration.schedules.get_settings")
    def test_reference_sync_schedule_disabled(self, mock_get_settings):
        """Test schedule skips when disabled."""
        from dagster import build_schedule_context

        mock_settings = Mock()
        mock_settings.reference_sync_enabled = False
        mock_get_settings.return_value = mock_settings

        context = build_schedule_context(
            scheduled_execution_time=datetime(
                2025, 12, 12, 1, 0, 0, tzinfo=timezone.utc
            )
        )

        result = reference_sync_schedule(context)

        # Verify no RunRequest when disabled
        assert result is None

    @patch("work_data_hub.orchestration.schedules.get_settings")
    def test_reference_sync_schedule_run_key_format(self, mock_get_settings):
        """Test run_key follows expected format."""
        from dagster import build_schedule_context

        mock_settings = Mock()
        mock_settings.reference_sync_enabled = True
        mock_get_settings.return_value = mock_settings

        context = build_schedule_context(
            scheduled_execution_time=datetime(
                2025, 12, 12, 1, 0, 0, tzinfo=timezone.utc
            )
        )

        result = reference_sync_schedule(context)

        # Verify run_key format: reference_sync_{timestamp}
        assert result.run_key.startswith("reference_sync_")
        assert "2025-12-12" in result.run_key


class TestConfigLoaderIntegration:
    """Integration tests for config loading."""

    @patch("work_data_hub.domain.reference_backfill.sync_config_loader.Path.exists")
    @patch("builtins.open")
    @patch("work_data_hub.domain.reference_backfill.sync_config_loader.yaml.safe_load")
    def test_load_full_config_from_data_sources(
        self,
        mock_yaml_load,
        mock_open,
        mock_exists,
    ):
        """Test loading complete config from reference_sync.yml."""
        mock_exists.return_value = True

        # Full config matching reference_sync.yml structure (Story 6.2-P14)
        mock_yaml_load.return_value = {
            "schema_version": "1.0",
            "enabled": True,
            "schedule": "0 1 * * *",
            "concurrency": 1,
            "batch_size": 5000,
            "tables": [
                {
                    "name": "年金计划",
                    "target_table": "年金计划",
                    "target_schema": "business",
                    "source_type": "legacy_mysql",
                    "source_config": {
                        "table": "annuity_plan",
                        "columns": [
                            {"source": "plan_code", "target": "年金计划号"},
                            {"source": "plan_name", "target": "计划名称"},
                        ],
                    },
                    "sync_mode": "upsert",
                    "primary_key": "年金计划号",
                },
                {
                    "name": "组合计划",
                    "target_table": "组合计划",
                    "target_schema": "business",
                    "source_type": "legacy_mysql",
                    "source_config": {
                        "table": "portfolio_plan",
                        "columns": [
                            {"source": "portfolio_code", "target": "组合代码"},
                            {"source": "plan_code", "target": "年金计划号"},
                        ],
                    },
                    "sync_mode": "upsert",
                    "primary_key": "组合代码",
                },
                {
                    "name": "组织架构",
                    "target_table": "组织架构",
                    "target_schema": "business",
                    "source_type": "legacy_mysql",
                    "source_config": {
                        "table": "organization",
                        "columns": [
                            {"source": "org_code", "target": "组织代码"},
                            {"source": "org_name", "target": "组织名称"},
                        ],
                        "incremental": {
                            "where": "updated_at >= :last_synced_at",
                            "updated_at_column": "updated_at",
                        },
                    },
                    "sync_mode": "upsert",
                    "primary_key": "组织代码",
                },
                {
                    "name": "产品线",
                    "target_table": "产品线",
                    "target_schema": "business",
                    "source_type": "config_file",
                    "source_config": {
                        "file_path": "config/reference_data/product_lines.yml",
                        "schema_version": "1.0",
                    },
                    "sync_mode": "delete_insert",
                    "primary_key": "产品线代码",
                },
            ],
        }

        config = load_reference_sync_config("config/reference_sync.yml")

        # Verify all 4 tables loaded
        assert config is not None
        assert config.enabled is True
        assert config.schedule == "0 1 * * *"
        assert len(config.tables) == 4

        # Verify table names
        table_names = [t.name for t in config.tables]
        assert "年金计划" in table_names
        assert "组合计划" in table_names
        assert "组织架构" in table_names
        assert "产品线" in table_names

        # Verify source types
        source_types = {t.name: t.source_type for t in config.tables}
        assert source_types["年金计划"] == "legacy_mysql"
        assert source_types["产品线"] == "config_file"


class TestLargeDatasetPerformance:
    """Performance tests with larger datasets."""

    def test_sync_10k_rows_performance(self):
        """Test sync performance with 10K row dataset."""
        # Create 10K row dataset
        large_df = pd.DataFrame(
            {
                "id": [f"ID{i:06d}" for i in range(10000)],
                "name": [f"Name {i}" for i in range(10000)],
                "type": ["Type A" if i % 2 == 0 else "Type B" for i in range(10000)],
            }
        )

        service = ReferenceSyncService()

        # Add tracking fields
        import time

        start = time.time()
        result_df = service._add_authoritative_tracking_fields(large_df)
        duration = time.time() - start

        # Verify performance (should be < 1 second for 10K rows)
        assert duration < 1.0, (
            f"Tracking field addition took {duration:.2f}s for 10K rows"
        )

        # Verify all rows processed
        assert len(result_df) == 10000
        assert all(result_df["_source"] == "authoritative")

    def test_batch_insert_chunking(self):
        """Test batch insert correctly chunks large datasets."""
        service = ReferenceSyncService()

        # Create test data
        df = pd.DataFrame(
            {
                "id": [f"ID{i:04d}" for i in range(12000)],
                "name": [f"Name {i}" for i in range(12000)],
            }
        )

        # Mock connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5000
        mock_conn.execute.return_value = mock_result

        config = ReferenceSyncTableConfig(
            name="test",
            target_table="test_table",
            target_schema="business",
            source_type="legacy_mysql",
            source_config={"table": "source"},
            sync_mode="upsert",
            primary_key="id",
        )

        # Execute batch insert with 5000 batch size
        rows_inserted = service._batch_insert(df, config, mock_conn, batch_size=5000)

        # Verify chunking: 12000 rows / 5000 batch = 3 batches
        assert mock_conn.execute.call_count == 3
        assert rows_inserted == 15000  # 3 batches * 5000 rowcount
