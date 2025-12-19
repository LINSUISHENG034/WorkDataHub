"""
Integration tests for HybridReferenceService.

Tests the end-to-end functionality of the hybrid reference service including:
- Pre-load → Check Coverage → Selective Backfill workflow
- Integration with pipeline ops
- Performance benchmarks
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from work_data_hub.domain.reference_backfill import (
    HybridReferenceService,
    GenericBackfillService,
    ReferenceSyncService,
    HybridResult,
    ForeignKeyConfig,
    BackfillColumnMapping,
)


@pytest.fixture
def sample_fk_configs():
    """Sample FK configurations for testing."""
    return [
        ForeignKeyConfig(
            name="fk_plan",
            source_column="年金计划号",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(
                    source="年金计划号",
                    target="年金计划号",
                )
            ],
            depends_on=[],
        ),
        ForeignKeyConfig(
            name="fk_product_line",
            source_column="产品线",
            target_table="产品线",
            target_key="产品线代码",
            backfill_columns=[
                BackfillColumnMapping(
                    source="产品线",
                    target="产品线代码",
                )
            ],
            depends_on=[],
        ),
    ]


@pytest.fixture
def large_fact_data():
    """Generate large fact data for performance testing."""
    # Generate 10K rows
    data = {
        "年金计划号": [f"PLAN{i:05d}" for i in range(10000)],
        "产品线": [f"LINE{i % 100:03d}" for i in range(10000)],
        "金额": [1000 + i for i in range(10000)],
    }
    return pd.DataFrame(data)


class TestHybridReferenceIntegration:
    """Integration tests for HybridReferenceService."""

    def test_end_to_end_workflow_no_preload(self, sample_fk_configs):
        """Test end-to-end workflow without pre-load (pure backfill)."""
        # Setup
        backfill_service = GenericBackfillService(domain="test_domain")
        hybrid_service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=None,  # No pre-load
        )

        # Sample fact data
        fact_data = pd.DataFrame(
            {
                "年金计划号": ["PLAN001", "PLAN002", "PLAN003"],
                "产品线": ["LINE001", "LINE002", "LINE003"],
                "金额": [1000, 2000, 3000],
            }
        )

        # Mock database connection
        mock_conn = Mock()
        mock_conn.dialect.name = "postgresql"

        # Mock coverage check - no existing records
        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query) and "COUNT" not in str(query):
                result.fetchall.return_value = []  # No existing records
            elif "COUNT" in str(query):
                result.scalar.return_value = 0
            elif "INSERT" in str(query):
                result.rowcount = 3
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        # Execute
        result = hybrid_service.ensure_references(
            domain="test_domain",
            df=fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        # Verify
        assert isinstance(result, HybridResult)
        assert result.domain == "test_domain"
        assert result.pre_load_available is False
        assert len(result.coverage_metrics) == 2
        assert result.coverage_metrics[0].coverage_rate == 0.0  # No pre-load
        assert result.backfill_result is not None
        assert result.backfill_result.total_inserted >= 0

    def test_end_to_end_workflow_with_preload(self, sample_fk_configs):
        """Test end-to-end workflow with pre-load (hybrid strategy)."""
        # Setup
        backfill_service = GenericBackfillService(domain="test_domain")
        sync_service = ReferenceSyncService(domain="reference_sync")
        hybrid_service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=sync_service,  # Pre-load available
        )

        # Sample fact data
        fact_data = pd.DataFrame(
            {
                "年金计划号": ["PLAN001", "PLAN002", "PLAN003"],
                "产品线": ["LINE001", "LINE002", "LINE003"],
                "金额": [1000, 2000, 3000],
            }
        )

        # Mock database connection
        mock_conn = Mock()
        mock_conn.dialect.name = "postgresql"

        # Mock coverage check - partial coverage (PLAN001, LINE001 exist)
        def mock_execute(query, params=None):
            result = Mock()
            query_str = str(query)
            if "年金计划" in query_str and "SELECT" in query_str and "WHERE" in query_str and "COUNT" not in query_str:
                result.fetchall.return_value = [("PLAN001",)]  # 1 exists
            elif "产品线" in query_str and "SELECT" in query_str and "WHERE" in query_str and "COUNT" not in query_str:
                result.fetchall.return_value = [("LINE001",)]  # 1 exists
            elif "COUNT" in query_str and "auto_derived" in query_str:
                result.scalar = Mock(return_value=2)  # 2 auto-derived per table
            elif "COUNT" in query_str and "authoritative" in query_str:
                result.scalar = Mock(return_value=1)  # 1 authoritative per table
            elif "INSERT" in query_str:
                result.rowcount = 2  # 2 new records per table
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        # Execute
        result = hybrid_service.ensure_references(
            domain="test_domain",
            df=fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        # Verify
        assert isinstance(result, HybridResult)
        assert result.domain == "test_domain"
        assert result.pre_load_available is True  # Sync service available
        assert len(result.coverage_metrics) == 2
        # Partial coverage: 1/3 = 0.333
        assert 0.3 <= result.coverage_metrics[0].coverage_rate <= 0.4
        assert result.backfill_result is not None
        # Auto-derived ratio: 4 / 6 = 0.667
        assert 0.6 <= result.auto_derived_ratio <= 0.7

    def test_performance_benchmark_10k_rows(self, sample_fk_configs, large_fact_data):
        """Test performance with 10K fact rows."""
        # Setup
        backfill_service = GenericBackfillService(domain="test_domain")
        hybrid_service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=None,
        )

        # Mock database connection
        mock_conn = Mock()
        mock_conn.dialect.name = "postgresql"

        # Mock coverage check - no existing records
        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query) and "COUNT" not in str(query):
                result.fetchall.return_value = []
            elif "COUNT" in str(query):
                result.scalar.return_value = 0
            elif "INSERT" in str(query):
                result.rowcount = 100  # Mock batch insert
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        # Execute and measure time
        import time

        start_time = time.time()
        result = hybrid_service.ensure_references(
            domain="test_domain",
            df=large_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )
        duration = time.time() - start_time

        # Verify performance
        assert duration < 5.0  # Should complete in less than 5 seconds
        assert isinstance(result, HybridResult)
        assert result.domain == "test_domain"

    def test_idempotency_repeated_calls(self, sample_fk_configs):
        """Test that repeated calls are idempotent."""
        # Setup
        backfill_service = GenericBackfillService(domain="test_domain")
        hybrid_service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=None,
        )

        # Sample fact data
        fact_data = pd.DataFrame(
            {
                "年金计划号": ["PLAN001", "PLAN002"],
                "产品线": ["LINE001", "LINE002"],
                "金额": [1000, 2000],
            }
        )

        # Mock database connection
        mock_conn = Mock()
        mock_conn.dialect.name = "postgresql"

        # Track call count
        call_count = {"coverage_check": 0}

        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query) and "COUNT" not in str(query):
                call_count["coverage_check"] += 1
                if call_count["coverage_check"] <= 2:  # First call (2 tables)
                    result.fetchall.return_value = []  # No existing records
                else:  # Second call
                    # All requested keys exist now (return exactly what was asked for)
                    fk_values = (params or {}).get("fk_values", [])
                    result.fetchall.return_value = [(v,) for v in fk_values]
            elif "COUNT" in str(query):
                result.scalar.return_value = 2
            elif "INSERT" in str(query):
                result.rowcount = 2
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        # First call - should trigger backfill
        result1 = hybrid_service.ensure_references(
            domain="test_domain",
            df=fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert result1.backfill_result is not None

        # Second call - should not trigger backfill (full coverage now)
        result2 = hybrid_service.ensure_references(
            domain="test_domain",
            df=fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert result2.backfill_result is None  # No backfill needed
        assert result2.coverage_metrics[0].coverage_rate == 1.0


class TestHybridReferenceOpIntegration:
    """Integration tests for hybrid_reference_op."""

    def test_op_with_valid_config(self):
        """Test hybrid_reference_op with valid configuration."""
        from work_data_hub.orchestration.ops import (
            HybridReferenceConfig,
            hybrid_reference_op,
        )
        from dagster import build_op_context

        # Setup - build context without config, pass config as parameter
        context = build_op_context()

        # Config as parameter
        config = HybridReferenceConfig(
            domain="test_domain",
            auto_derived_threshold=0.15,
        )

        # Sample DataFrame
        df = pd.DataFrame(
            {
                "年金计划号": ["PLAN001", "PLAN002"],
                "产品线": ["LINE001", "LINE002"],
                "金额": [1000, 2000],
            }
        )

        # Mock database and FK config loading
        with patch(
            "work_data_hub.orchestration.ops.load_foreign_keys_config"
        ) as mock_load_fk:
            mock_load_fk.return_value = []  # No FK configs

            # Execute
            result = hybrid_reference_op(context, config, df)

            # Verify
            assert isinstance(result, dict)
            assert result["domain"] == "test_domain"
            assert result["coverage_metrics"] == []
            assert result["backfill_result"] is None

    def test_op_config_validation(self):
        """Test HybridReferenceConfig validation."""
        from work_data_hub.orchestration.ops import HybridReferenceConfig

        # Valid config
        config = HybridReferenceConfig(
            domain="test_domain",
            auto_derived_threshold=0.10,
        )
        assert config.domain == "test_domain"
        assert config.auto_derived_threshold == 0.10

        # Invalid domain (empty)
        with pytest.raises(ValueError, match="Domain must be a non-empty string"):
            HybridReferenceConfig(domain="", auto_derived_threshold=0.10)

        # Invalid threshold (out of range)
        with pytest.raises(
            ValueError, match="auto_derived_threshold must be between 0 and 1"
        ):
            HybridReferenceConfig(domain="test_domain", auto_derived_threshold=1.5)
