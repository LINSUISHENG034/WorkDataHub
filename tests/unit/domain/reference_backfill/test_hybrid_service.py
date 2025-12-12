"""
Unit tests for HybridReferenceService.

Tests the core functionality of the hybrid reference service including:
- Coverage checking
- Selective backfill
- Auto-derived ratio calculation
- Idempotency
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from work_data_hub.domain.reference_backfill.hybrid_service import (
    HybridReferenceService,
    HybridResult,
    CoverageMetrics,
)
from work_data_hub.domain.reference_backfill.generic_service import (
    GenericBackfillService,
    BackfillResult,
)
from work_data_hub.domain.reference_backfill.sync_service import (
    ReferenceSyncService,
)
from work_data_hub.domain.reference_backfill.models import (
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
def sample_fact_data():
    """Sample fact data for testing."""
    return pd.DataFrame(
        {
            "年金计划号": ["PLAN001", "PLAN002", "PLAN001", "PLAN003"],
            "产品线": ["LINE001", "LINE002", "LINE001", "LINE003"],
            "金额": [1000, 2000, 1500, 3000],
        }
    )


@pytest.fixture
def mock_conn():
    """Mock database connection."""
    conn = Mock()
    conn.dialect.name = "postgresql"
    return conn


@pytest.fixture
def backfill_service():
    """Create a GenericBackfillService instance."""
    return GenericBackfillService(domain="test_domain")


@pytest.fixture
def sync_service():
    """Create a ReferenceSyncService instance."""
    return ReferenceSyncService(domain="reference_sync")


class TestHybridReferenceServiceCore:
    """Test core functionality of HybridReferenceService."""

    def test_initialization_with_sync_service(self, backfill_service, sync_service):
        """Test service initialization with sync service."""
        service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=sync_service,
            auto_derived_threshold=0.15,
        )

        assert service.backfill == backfill_service
        assert service.sync == sync_service
        assert service.threshold == 0.15

    def test_initialization_without_sync_service(self, backfill_service):
        """Test service initialization without sync service (backfill-only mode)."""
        service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=None,
        )

        assert service.backfill == backfill_service
        assert service.sync is None
        assert service.threshold == 0.10  # Default threshold

    def test_check_coverage_full_coverage(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test coverage check when all FK values exist."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return all FK values as existing
        def mock_execute(query, params):
            result = Mock()
            if "年金计划" in str(query):
                result.fetchall.return_value = [
                    ("PLAN001",),
                    ("PLAN002",),
                    ("PLAN003",),
                ]
            elif "产品线" in str(query):
                result.fetchall.return_value = [
                    ("LINE001",),
                    ("LINE002",),
                    ("LINE003",),
                ]
            return result

        mock_conn.execute = mock_execute

        metrics = service._check_coverage(
            sample_fact_data, sample_fk_configs, mock_conn
        )

        assert len(metrics) == 2
        assert metrics[0].table == "年金计划"
        assert metrics[0].total_fk_values == 3
        assert metrics[0].covered_values == 3
        assert metrics[0].missing_values == 0
        assert metrics[0].coverage_rate == 1.0

        assert metrics[1].table == "产品线"
        assert metrics[1].total_fk_values == 3
        assert metrics[1].covered_values == 3
        assert metrics[1].missing_values == 0
        assert metrics[1].coverage_rate == 1.0

    def test_check_coverage_partial_coverage(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test coverage check when some FK values are missing."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return only some FK values as existing
        def mock_execute(query, params):
            result = Mock()
            if "年金计划" in str(query):
                # Only PLAN001 exists
                result.fetchall.return_value = [("PLAN001",)]
            elif "产品线" in str(query):
                # LINE001 and LINE002 exist
                result.fetchall.return_value = [("LINE001",), ("LINE002",)]
            return result

        mock_conn.execute = mock_execute

        metrics = service._check_coverage(
            sample_fact_data, sample_fk_configs, mock_conn
        )

        assert len(metrics) == 2
        assert metrics[0].table == "年金计划"
        assert metrics[0].total_fk_values == 3
        assert metrics[0].covered_values == 1
        assert metrics[0].missing_values == 2
        assert metrics[0].coverage_rate == pytest.approx(0.333, rel=0.01)

        assert metrics[1].table == "产品线"
        assert metrics[1].total_fk_values == 3
        assert metrics[1].covered_values == 2
        assert metrics[1].missing_values == 1
        assert metrics[1].coverage_rate == pytest.approx(0.667, rel=0.01)

    def test_check_coverage_zero_coverage(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test coverage check when no FK values exist."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return no FK values as existing
        def mock_execute(query, params):
            result = Mock()
            result.fetchall.return_value = []
            return result

        mock_conn.execute = mock_execute

        metrics = service._check_coverage(
            sample_fact_data, sample_fk_configs, mock_conn
        )

        assert len(metrics) == 2
        assert metrics[0].coverage_rate == 0.0
        assert metrics[0].missing_values == 3
        assert metrics[1].coverage_rate == 0.0
        assert metrics[1].missing_values == 3

    def test_check_coverage_empty_fact_data(
        self, backfill_service, sample_fk_configs, mock_conn
    ):
        """Test coverage check with empty fact data."""
        service = HybridReferenceService(backfill_service=backfill_service)

        empty_df = pd.DataFrame({"年金计划号": [], "产品线": []})

        metrics = service._check_coverage(empty_df, sample_fk_configs, mock_conn)

        assert len(metrics) == 2
        assert metrics[0].total_fk_values == 0
        assert metrics[0].coverage_rate == 1.0  # Empty is considered fully covered
        assert metrics[1].total_fk_values == 0
        assert metrics[1].coverage_rate == 1.0

    def test_check_coverage_missing_source_column(
        self, backfill_service, sample_fk_configs, mock_conn
    ):
        """Test coverage check when source column is missing from DataFrame."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # DataFrame missing one of the source columns (产品线 is missing)
        df = pd.DataFrame({"年金计划号": ["PLAN001", "PLAN002"]})

        # Mock database to return existing FK values
        def mock_execute(query, params=None):
            result = Mock()
            result.fetchall.return_value = [("PLAN001",), ("PLAN002",)]
            return result

        mock_conn.execute = mock_execute

        metrics = service._check_coverage(df, sample_fk_configs, mock_conn)

        # Should only have metrics for the column that exists (年金计划号)
        assert len(metrics) == 1
        assert metrics[0].table == "年金计划"

    def test_calculate_auto_derived_ratio_balanced(
        self, backfill_service, sample_fk_configs, mock_conn
    ):
        """Test auto_derived ratio calculation with balanced data."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return counts
        def mock_execute(query):
            result = Mock()
            if "auto_derived" in str(query):
                result.scalar.return_value = 5  # 5 auto_derived records per table
            elif "authoritative" in str(query):
                result.scalar.return_value = 15  # 15 authoritative records per table
            return result

        mock_conn.execute = mock_execute

        auto_derived, authoritative, ratio = service._calculate_auto_derived_ratio(
            sample_fk_configs, mock_conn
        )

        # 2 tables * 5 = 10 auto_derived
        # 2 tables * 15 = 30 authoritative
        # ratio = 10 / 40 = 0.25
        assert auto_derived == 10
        assert authoritative == 30
        assert ratio == 0.25

    def test_calculate_auto_derived_ratio_all_authoritative(
        self, backfill_service, sample_fk_configs, mock_conn
    ):
        """Test auto_derived ratio when all data is authoritative."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return counts
        def mock_execute(query):
            result = Mock()
            if "auto_derived" in str(query):
                result.scalar.return_value = 0
            elif "authoritative" in str(query):
                result.scalar.return_value = 20
            return result

        mock_conn.execute = mock_execute

        auto_derived, authoritative, ratio = service._calculate_auto_derived_ratio(
            sample_fk_configs, mock_conn
        )

        assert auto_derived == 0
        assert authoritative == 40
        assert ratio == 0.0

    def test_calculate_auto_derived_ratio_empty_tables(
        self, backfill_service, sample_fk_configs, mock_conn
    ):
        """Test auto_derived ratio with empty tables."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to return zero counts
        def mock_execute(query):
            result = Mock()
            result.scalar.return_value = 0
            return result

        mock_conn.execute = mock_execute

        auto_derived, authoritative, ratio = service._calculate_auto_derived_ratio(
            sample_fk_configs, mock_conn
        )

        assert auto_derived == 0
        assert authoritative == 0
        assert ratio == 0.0  # Avoid division by zero


class TestHybridReferenceServiceIntegration:
    """Test integrated functionality of HybridReferenceService."""

    def test_ensure_references_full_coverage_no_backfill(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test ensure_references when all FK values exist (no backfill needed)."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock full coverage
        def mock_execute(query, params=None):
            result = Mock()
            if "年金计划" in str(query) and "SELECT" in str(query):
                result.fetchall.return_value = [
                    ("PLAN001",),
                    ("PLAN002",),
                    ("PLAN003",),
                ]
            elif "产品线" in str(query) and "SELECT" in str(query):
                result.fetchall.return_value = [
                    ("LINE001",),
                    ("LINE002",),
                    ("LINE003",),
                ]
            elif "COUNT" in str(query):
                result.scalar.return_value = 10
            return result

        mock_conn.execute = mock_execute

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert isinstance(result, HybridResult)
        assert result.domain == "test_domain"
        assert result.pre_load_available is False  # No sync service
        assert len(result.coverage_metrics) == 2
        assert result.coverage_metrics[0].coverage_rate == 1.0
        assert result.coverage_metrics[1].coverage_rate == 1.0
        assert result.backfill_result is None  # No backfill needed
        assert result.degraded_mode is False

    def test_ensure_references_partial_coverage_with_backfill(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test ensure_references when some FK values are missing (backfill needed)."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock partial coverage
        call_count = {"execute": 0}

        def mock_execute(query, params=None):
            result = Mock()
            call_count["execute"] += 1

            # Coverage check queries
            if "年金计划" in str(query) and "SELECT" in str(query) and "WHERE" in str(query):
                result.fetchall.return_value = [("PLAN001",)]  # Only 1 exists
            elif "产品线" in str(query) and "SELECT" in str(query) and "WHERE" in str(query):
                result.fetchall.return_value = [("LINE001",)]  # Only 1 exists
            # Auto-derived ratio queries
            elif "COUNT" in str(query):
                result.scalar.return_value = 5
            # Backfill INSERT queries
            elif "INSERT" in str(query):
                result.rowcount = 2  # 2 records inserted per table
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert isinstance(result, HybridResult)
        assert result.domain == "test_domain"
        assert len(result.coverage_metrics) == 2
        assert result.coverage_metrics[0].missing_values == 2
        assert result.coverage_metrics[1].missing_values == 2
        assert result.backfill_result is not None
        assert result.backfill_result.total_inserted >= 0  # Some records inserted

    def test_ensure_references_with_sync_service(
        self, backfill_service, sync_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test ensure_references with sync service available."""
        service = HybridReferenceService(
            backfill_service=backfill_service,
            sync_service=sync_service,
        )

        # Mock full coverage (pre-load worked)
        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query):
                result.fetchall.return_value = [
                    ("PLAN001",),
                    ("PLAN002",),
                    ("PLAN003",),
                ]
            elif "COUNT" in str(query):
                result.scalar.return_value = 10
            return result

        mock_conn.execute = mock_execute

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert result.pre_load_available is True  # Sync service is available
        assert result.degraded_mode is False

    def test_ensure_references_threshold_warning(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn, caplog
    ):
        """Test that warning is logged when auto_derived ratio exceeds threshold."""
        service = HybridReferenceService(
            backfill_service=backfill_service,
            auto_derived_threshold=0.10,  # 10% threshold
        )

        # Mock partial coverage and high auto_derived ratio
        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query) and "COUNT" not in str(query):
                result.fetchall.return_value = [("PLAN001",)]
            elif "COUNT" in str(query) and "auto_derived" in str(query):
                # Mock scalar() to return integer directly
                result.scalar.return_value = 15  # High auto_derived count
            elif "COUNT" in str(query) and "authoritative" in str(query):
                # Mock scalar() to return integer directly
                result.scalar.return_value = 5  # Low authoritative count
            elif "INSERT" in str(query):
                result.rowcount = 2
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        with caplog.at_level("WARNING"):
            result = service.ensure_references(
                domain="test_domain",
                df=sample_fact_data,
                fk_configs=sample_fk_configs,
                conn=mock_conn,
            )

        # Check that warning was logged
        assert any("exceeds threshold" in record.message for record in caplog.records)
        assert result.auto_derived_ratio > 0.10


class TestHybridReferenceServiceIdempotency:
    """Test idempotency of HybridReferenceService."""

    def test_repeated_calls_idempotent(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test that repeated calls to ensure_references are idempotent."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock partial coverage on first call, full coverage on second call
        call_count = {"coverage_check": 0}

        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query):
                call_count["coverage_check"] += 1
                if call_count["coverage_check"] <= 2:  # First call (2 tables)
                    result.fetchall.return_value = [("PLAN001",)]  # Partial coverage
                else:  # Second call
                    result.fetchall.return_value = [
                        ("PLAN001",),
                        ("PLAN002",),
                        ("PLAN003",),
                    ]  # Full coverage
            elif "COUNT" in str(query):
                result.scalar.return_value = 5
            elif "INSERT" in str(query):
                result.rowcount = 2
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        # First call - should trigger backfill
        result1 = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert result1.backfill_result is not None

        # Second call - should not trigger backfill (full coverage now)
        result2 = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        assert result2.backfill_result is None  # No backfill needed
        assert result2.coverage_metrics[0].coverage_rate == 1.0


class TestHybridReferenceServiceDegradation:
    """Test degradation mode of HybridReferenceService (AC #5)."""

    def test_degraded_mode_on_coverage_check_failure(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test that coverage check failure triggers degraded mode."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database to raise exception on coverage check
        call_count = {"execute": 0}

        def mock_execute(query, params=None):
            call_count["execute"] += 1
            result = Mock()
            query_str = str(query)

            # First table coverage check fails
            if "年金计划" in query_str and "SELECT" in query_str and "WHERE" in query_str:
                raise Exception("Database connection lost")
            # Second table works
            elif "产品线" in query_str and "SELECT" in query_str and "WHERE" in query_str:
                result.fetchall.return_value = [("LINE001",), ("LINE002",)]
            elif "COUNT" in query_str:
                result.scalar.return_value = 5
            elif "INSERT" in query_str:
                result.rowcount = 2
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        # Should be in degraded mode due to first table failure
        assert result.degraded_mode is True
        assert result.degradation_reason is not None
        assert "年金计划" in result.degradation_reason
        # Should still have coverage metrics for both tables
        assert len(result.coverage_metrics) == 2
        # Failed table should have 0% coverage (triggers full backfill)
        assert result.coverage_metrics[0].coverage_rate == 0.0

    def test_degraded_mode_on_backfill_failure(
        self, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test that backfill failure triggers degraded mode."""
        # Create a backfill service that will fail
        backfill_service = GenericBackfillService(domain="test_domain")

        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database - coverage check works but backfill fails
        def mock_execute(query, params=None):
            result = Mock()
            query_str = str(query)

            if "SELECT" in query_str and "WHERE" in query_str and "COUNT" not in query_str:
                result.fetchall.return_value = []  # No existing records
            elif "COUNT" in query_str:
                result.scalar.return_value = 0
            elif "INSERT" in query_str:
                raise Exception("Backfill insert failed")
            return result

        mock_conn.execute = mock_execute
        mock_conn.commit = Mock()
        mock_conn.begin = Mock(return_value=Mock(commit=Mock(), rollback=Mock()))

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        # Should be in degraded mode due to backfill failure
        assert result.degraded_mode is True
        assert result.degradation_reason is not None
        assert "Backfill failed" in result.degradation_reason
        # Backfill result should be None due to failure
        assert result.backfill_result is None

    def test_no_degradation_on_success(
        self, backfill_service, sample_fk_configs, sample_fact_data, mock_conn
    ):
        """Test that successful operation does not trigger degraded mode."""
        service = HybridReferenceService(backfill_service=backfill_service)

        # Mock database - everything works
        def mock_execute(query, params=None):
            result = Mock()
            if "SELECT" in str(query) and "WHERE" in str(query) and "COUNT" not in str(query):
                result.fetchall.return_value = [
                    ("PLAN001",), ("PLAN002",), ("PLAN003",)
                ]
            elif "COUNT" in str(query):
                result.scalar.return_value = 10
            return result

        mock_conn.execute = mock_execute

        result = service.ensure_references(
            domain="test_domain",
            df=sample_fact_data,
            fk_configs=sample_fk_configs,
            conn=mock_conn,
        )

        # Should NOT be in degraded mode
        assert result.degraded_mode is False
        assert result.degradation_reason is None
