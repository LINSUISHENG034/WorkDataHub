"""
Unit tests for reference data observability service.

Tests dashboard metrics, threshold alerts, CSV export, and audit logging.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from work_data_hub.domain.reference_backfill.observability import (
    ObservabilityService,
    ReferenceDataMetrics,
    AlertConfig,
    AlertResult,
    ReferenceDataAuditLogger,
)
from work_data_hub.domain.reference_backfill.hybrid_service import HybridResult


@pytest.fixture
def observability_config_file(tmp_path: Path) -> Path:
    """Create a minimal reference_sync.yml with required sensitive fields."""
    config_content = """
schema_version: "1.0"
enabled: true
schedule: "0 1 * * *"
tables:
  - target_table: "年金计划"
    sensitive_fields: ["客户名称"]
  - target_table: "组织架构"
    sensitive_fields: ["部门名称"]
  - target_table: "产品线"
    sensitive_fields: ["产品线名称"]
"""
    config_path = tmp_path / "reference_sync.yml"
    config_path.write_text(config_content, encoding="utf-8")
    return config_path


@pytest.fixture
def export_policy_file(tmp_path: Path) -> Path:
    """Create an export policy file required for exports."""
    policy_path = tmp_path / "export_policy.yml"
    policy_path.write_text("retention: 30d\nacl: restricted\n", encoding="utf-8")
    return policy_path


class TestReferenceDataMetrics:
    """Test ReferenceDataMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test metrics dataclass initialization."""
        metrics = ReferenceDataMetrics(
            table="年金计划",
            total_records=100,
            authoritative_count=90,
            auto_derived_count=10,
            needs_review_count=10,
            auto_derived_ratio=0.1,
        )

        assert metrics.table == "年金计划"
        assert metrics.total_records == 100
        assert metrics.authoritative_count == 90
        assert metrics.auto_derived_count == 10
        assert metrics.needs_review_count == 10
        assert metrics.auto_derived_ratio == 0.1
        assert metrics.domains_contributing == []

    def test_metrics_with_domains(self):
        """Test metrics with contributing domains."""
        metrics = ReferenceDataMetrics(
            table="年金计划",
            total_records=100,
            authoritative_count=90,
            auto_derived_count=10,
            needs_review_count=10,
            auto_derived_ratio=0.1,
            domains_contributing=["annuity_performance", "annuity_income"],
        )

        assert len(metrics.domains_contributing) == 2
        assert "annuity_performance" in metrics.domains_contributing


class TestAlertConfig:
    """Test AlertConfig dataclass."""

    def test_default_config(self):
        """Test default alert configuration."""
        config = AlertConfig()

        assert config.auto_derived_ratio_threshold == 0.10
        assert config.needs_review_count_threshold == 100
        assert config.per_table_thresholds == {}

    def test_custom_config(self):
        """Test custom alert configuration."""
        config = AlertConfig(
            auto_derived_ratio_threshold=0.15,
            needs_review_count_threshold=200,
            per_table_thresholds={"年金计划": 0.05},
        )

        assert config.auto_derived_ratio_threshold == 0.15
        assert config.needs_review_count_threshold == 200
        assert config.per_table_thresholds["年金计划"] == 0.05


class TestObservabilityService:
    """Test ObservabilityService."""

    def test_service_initialization(self):
        """Test service initialization with defaults."""
        service = ObservabilityService()

        assert service.schema == "business"
        assert service.alert_config.auto_derived_ratio_threshold == 0.10
        assert len(service.reference_tables) >= 1

    def test_service_custom_initialization(self):
        """Test service initialization with custom config."""
        alert_config = AlertConfig(auto_derived_ratio_threshold=0.15)
        service = ObservabilityService(
            schema="custom_schema",
            alert_config=alert_config,
            reference_tables=["table1", "table2"],
        )

        assert service.schema == "custom_schema"
        assert service.alert_config.auto_derived_ratio_threshold == 0.15
        assert len(service.reference_tables) == 2

    def test_get_table_metrics(self):
        """Test getting metrics for a single table."""
        service = ObservabilityService()
        mock_conn = Mock()

        # Mock main query result
        mock_result = Mock()
        mock_result.total_records = 100
        mock_result.authoritative_count = 90
        mock_result.auto_derived_count = 10
        mock_result.needs_review_count = 10
        mock_result.oldest_auto_derived = datetime(2025, 1, 1)
        mock_result.newest_auto_derived = datetime(2025, 1, 10)

        # Mock domains query result
        mock_domains_result = [(["annuity_performance"]), (["annuity_income"])]

        mock_conn.execute.side_effect = [
            Mock(fetchone=Mock(return_value=mock_result)),
            Mock(fetchall=Mock(return_value=mock_domains_result)),
        ]

        metrics = service.get_table_metrics("年金计划", mock_conn)

        assert metrics.table == "年金计划"
        assert metrics.total_records == 100
        assert metrics.authoritative_count == 90
        assert metrics.auto_derived_count == 10
        assert metrics.needs_review_count == 10
        assert metrics.auto_derived_ratio == 0.1
        assert len(metrics.domains_contributing) == 2

    def test_get_table_metrics_empty_table(self):
        """Test getting metrics for an empty table."""
        service = ObservabilityService()
        mock_conn = Mock()

        # Mock empty table result
        mock_result = Mock()
        mock_result.total_records = 0
        mock_result.authoritative_count = 0
        mock_result.auto_derived_count = 0
        mock_result.needs_review_count = 0
        mock_result.oldest_auto_derived = None
        mock_result.newest_auto_derived = None

        mock_conn.execute.side_effect = [
            Mock(fetchone=Mock(return_value=mock_result)),
            Mock(fetchall=Mock(return_value=[])),
        ]

        metrics = service.get_table_metrics("年金计划", mock_conn)

        assert metrics.total_records == 0
        assert metrics.auto_derived_ratio == 0.0

    def test_get_all_metrics_with_failure(self):
        """Test getting metrics when one table fails."""
        service = ObservabilityService(reference_tables=["table1", "table2"])
        mock_conn = Mock()

        # First table succeeds, second fails
        mock_result = Mock()
        mock_result.total_records = 100
        mock_result.authoritative_count = 90
        mock_result.auto_derived_count = 10
        mock_result.needs_review_count = 10

        mock_conn.execute.side_effect = [
            Mock(fetchone=Mock(return_value=mock_result)),
            Mock(fetchall=Mock(return_value=[])),
            Exception("Table not found"),
        ]

        metrics = service.get_all_metrics(mock_conn)

        # Should only return metrics for successful table
        assert len(metrics) == 1
        assert metrics[0].table == "table1"

    def test_check_thresholds_no_violations(self):
        """Test threshold checking with no violations."""
        service = ObservabilityService()
        metrics = [
            ReferenceDataMetrics(
                table="年金计划",
                total_records=100,
                authoritative_count=95,
                auto_derived_count=5,
                needs_review_count=5,
                auto_derived_ratio=0.05,
            )
        ]

        alerts = service.check_thresholds(metrics)

        assert len(alerts) == 0

    def test_check_thresholds_ratio_violation(self):
        """Test threshold checking with ratio violation."""
        service = ObservabilityService()
        metrics = [
            ReferenceDataMetrics(
                table="年金计划",
                total_records=100,
                authoritative_count=80,
                auto_derived_count=20,
                needs_review_count=150,  # Exceeds threshold of 100
                auto_derived_ratio=0.20,
            )
        ]

        alerts = service.check_thresholds(metrics)

        assert len(alerts) == 2  # Both ratio and count violations
        assert any(a.alert_type == "auto_derived_ratio" for a in alerts)
        assert any(a.alert_type == "needs_review_count" for a in alerts)

    def test_check_thresholds_per_table(self):
        """Test per-table threshold configuration."""
        alert_config = AlertConfig(
            auto_derived_ratio_threshold=0.10,
            per_table_thresholds={"年金计划": 0.05},
        )
        service = ObservabilityService(alert_config=alert_config)

        metrics = [
            ReferenceDataMetrics(
                table="年金计划",
                total_records=100,
                authoritative_count=92,
                auto_derived_count=8,
                needs_review_count=8,
                auto_derived_ratio=0.08,
            )
        ]

        alerts = service.check_thresholds(metrics)

        # Should trigger alert because 0.08 > 0.05 (per-table threshold)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "auto_derived_ratio"
        assert alerts[0].threshold == 0.05

    def test_check_thresholds_from_hybrid_result(self):
        """Test threshold checking from HybridResult."""
        service = ObservabilityService()
        hybrid_result = HybridResult(
            domain="annuity_performance",
            pre_load_available=True,
            coverage_metrics=[],
            backfill_result=None,
            total_auto_derived=20,
            total_authoritative=80,
            auto_derived_ratio=0.20,
            degraded_mode=False,
        )

        alerts = service.check_thresholds_from_hybrid_result(hybrid_result)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "auto_derived_ratio"
        assert alerts[0].table == "<global>"

    def test_check_thresholds_degraded_mode(self):
        """Test threshold checking with degraded mode."""
        service = ObservabilityService()
        hybrid_result = HybridResult(
            domain="annuity_performance",
            pre_load_available=True,
            coverage_metrics=[],
            backfill_result=None,
            total_auto_derived=5,
            total_authoritative=95,
            auto_derived_ratio=0.05,
            degraded_mode=True,
            degradation_reason="Pre-load failed",
        )

        alerts = service.check_thresholds_from_hybrid_result(hybrid_result)

        # No threshold alerts, but degraded mode should be logged
        assert len(alerts) == 0

    @patch("work_data_hub.domain.reference_backfill.observability.pd.read_sql")
    def test_export_pending_review(
        self,
        mock_read_sql,
        observability_config_file: Path,
        export_policy_file: Path,
    ):
        """Test CSV export for pending review records."""
        service = ObservabilityService()
        mock_conn = Mock()

        # Mock chunked data
        chunk1 = pd.DataFrame({
            "年金计划号": ["P001", "P002"],
            "_source": ["auto_derived", "auto_derived"],
            "_needs_review": [True, True],
        })
        chunk2 = pd.DataFrame({
            "年金计划号": ["P003"],
            "_source": ["auto_derived"],
            "_needs_review": [True],
        })

        mock_read_sql.return_value = iter([chunk1, chunk2])

        output_path = service.export_pending_review(
            table="年金计划",
            conn=mock_conn,
            config_path=str(observability_config_file),
            export_policy_path=str(export_policy_file),
        )

        # Use Path for cross-platform compatibility
        output_path_obj = Path(output_path)
        assert output_path_obj.name.startswith("pending_review_年金计划_")
        assert output_path_obj.suffix == ".csv"

        # Verify file was created
        assert output_path_obj.exists()

        # Clean up
        output_path_obj.unlink()
        output_path_obj.parent.rmdir()

    @patch("work_data_hub.domain.reference_backfill.observability.pd.read_sql")
    def test_export_pending_review_with_filter(
        self,
        mock_read_sql,
        observability_config_file: Path,
        export_policy_file: Path,
    ):
        """Test CSV export with domain filter."""
        service = ObservabilityService()
        mock_conn = Mock()

        chunk = pd.DataFrame({
            "年金计划号": ["P001"],
            "_source": ["auto_derived"],
            "_needs_review": [True],
            "_derived_from_domain": ["annuity_performance"],
        })

        mock_read_sql.return_value = iter([chunk])

        output_path = service.export_pending_review(
            table="年金计划",
            conn=mock_conn,
            domain_filter="annuity_performance",
            config_path=str(observability_config_file),
            export_policy_path=str(export_policy_file),
        )

        assert Path(output_path).exists()

        # Clean up
        Path(output_path).unlink()
        Path("exports").rmdir()

    @patch("work_data_hub.domain.reference_backfill.observability.pd.read_sql")
    def test_export_pending_review_exclude_columns(
        self,
        mock_read_sql,
        observability_config_file: Path,
        export_policy_file: Path,
    ):
        """Test CSV export with column exclusion."""
        service = ObservabilityService()
        mock_conn = Mock()

        chunk = pd.DataFrame({
            "年金计划号": ["P001"],
            "sensitive_field": ["secret"],
            "_source": ["auto_derived"],
            "_needs_review": [True],
        })

        mock_read_sql.return_value = iter([chunk])

        output_path = service.export_pending_review(
            table="年金计划",
            conn=mock_conn,
            exclude_columns=["sensitive_field"],
            config_path=str(observability_config_file),
            export_policy_path=str(export_policy_file),
        )

        # Read exported CSV and verify sensitive field is excluded
        exported_df = pd.read_csv(output_path)
        assert "sensitive_field" not in exported_df.columns
        assert "年金计划号" in exported_df.columns

        # Clean up
        Path(output_path).unlink()
        Path("exports").rmdir()


class TestReferenceDataAuditLogger:
    """Test ReferenceDataAuditLogger."""

    def test_logger_initialization(self):
        """Test audit logger initialization."""
        logger = ReferenceDataAuditLogger()
        assert logger.logger is not None

    @patch("work_data_hub.domain.reference_backfill.observability.structlog.get_logger")
    def test_log_insert(self, mock_get_logger):
        """Test logging insert operation."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = ReferenceDataAuditLogger()
        logger.log_insert(
            table="年金计划",
            record_key="P001",
            source="auto_derived",
            domain="annuity_performance",
            actor="backfill_service",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "reference_data.changed"
        assert call_args[1]["table"] == "年金计划"
        assert call_args[1]["operation"] == "insert"
        assert call_args[1]["record_key"] == "P001"
        assert call_args[1]["new_source"] == "auto_derived"

    @patch("work_data_hub.domain.reference_backfill.observability.structlog.get_logger")
    def test_log_update(self, mock_get_logger):
        """Test logging update operation."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = ReferenceDataAuditLogger()
        logger.log_update(
            table="年金计划",
            record_key="P001",
            old_source="auto_derived",
            new_source="authoritative",
            domain="annuity_performance",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[1]["operation"] == "update"
        assert call_args[1]["old_source"] == "auto_derived"
        assert call_args[1]["new_source"] == "authoritative"

    @patch("work_data_hub.domain.reference_backfill.observability.structlog.get_logger")
    def test_log_delete(self, mock_get_logger):
        """Test logging delete operation."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = ReferenceDataAuditLogger()
        logger.log_delete(
            table="年金计划",
            record_key="P001",
            old_source="auto_derived",
            domain="annuity_performance",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[1]["operation"] == "delete"
        assert call_args[1]["old_source"] == "auto_derived"
        assert call_args[1]["new_source"] is None
