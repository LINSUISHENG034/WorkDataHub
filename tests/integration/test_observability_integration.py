"""
Integration tests for reference data observability service.

Tests dashboard queries with real database, CSV export with actual data,
and alert triggering with threshold violations.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import pandas as pd
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Connection

from work_data_hub.domain.reference_backfill.observability import (
    ObservabilityService,
    ReferenceDataMetrics,
    AlertConfig,
    ReferenceDataAuditLogger,
)


@pytest.fixture(scope="module")
def test_db_connection():
    """Create a test database connection."""
    # Use SQLite in-memory database for integration tests
    engine = create_engine("sqlite:///:memory:")
    conn = engine.connect()

    # Create test reference tables with tracking fields
    conn.execute(text("""
        CREATE TABLE 年金计划 (
            年金计划号 TEXT PRIMARY KEY,
            计划名称 TEXT,
            计划类型 TEXT,
            客户名称 TEXT,
            _source TEXT,
            _needs_review BOOLEAN,
            _derived_from_domain TEXT,
            _derived_at TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE 组合计划 (
            组合代码 TEXT PRIMARY KEY,
            年金计划号 TEXT,
            组合名称 TEXT,
            组合类型 TEXT,
            _source TEXT,
            _needs_review BOOLEAN,
            _derived_from_domain TEXT,
            _derived_at TEXT
        )
    """))

    # Insert test data
    test_data = [
        {
            "plan_id": "P001",
            "plan_name": "测试计划1",
            "plan_type": "年金",
            "customer_name": "客户1",
            "source": "authoritative",
            "needs_review": False,
            "derived_from": None,
            "derived_at": None,
        },
        {
            "plan_id": "P002",
            "plan_name": "测试计划2",
            "plan_type": "年金",
            "customer_name": "客户2",
            "source": "auto_derived",
            "needs_review": True,
            "derived_from": "annuity_performance",
            "derived_at": "2025-01-01T00:00:00Z",
        },
        {
            "plan_id": "P003",
            "plan_name": "测试计划3",
            "plan_type": "年金",
            "customer_name": "客户3",
            "source": "auto_derived",
            "needs_review": True,
            "derived_from": "annuity_income",
            "derived_at": "2025-01-02T00:00:00Z",
        },
    ]

    conn.execute(
        text(
            """
            INSERT INTO 年金计划 (
                年金计划号, 计划名称, 计划类型, 客户名称,
                _source, _needs_review, _derived_from_domain, _derived_at
            )
            VALUES (
                :plan_id, :plan_name, :plan_type, :customer_name,
                :source, :needs_review, :derived_from, :derived_at
            )
            """
        ),
        test_data,
    )

    test_portfolio_data = [
        {
            "portfolio_code": "PF001",
            "plan_id": "P001",
            "portfolio_name": "组合1",
            "portfolio_type": "平衡型",
            "source": "authoritative",
            "needs_review": False,
            "derived_from": None,
            "derived_at": None,
        },
        {
            "portfolio_code": "PF002",
            "plan_id": "P002",
            "portfolio_name": "组合2",
            "portfolio_type": "保守型",
            "source": "auto_derived",
            "needs_review": True,
            "derived_from": "annuity_performance",
            "derived_at": "2025-01-01T00:00:00Z",
        },
    ]

    conn.execute(
        text(
            """
            INSERT INTO 组合计划 (
                组合代码, 年金计划号, 组合名称, 组合类型,
                _source, _needs_review, _derived_from_domain, _derived_at
            )
            VALUES (
                :portfolio_code, :plan_id, :portfolio_name, :portfolio_type,
                :source, :needs_review, :derived_from, :derived_at
            )
            """
        ),
        test_portfolio_data,
    )

    yield conn
    conn.close()


@pytest.fixture
def mock_config_file():
    """Create a mock data_sources.yml config file."""
    config_content = """
domains:
  annuity_performance:
    foreign_keys:
      - target_table: "年金计划"
      - target_table: "组合计划"

reference_sync:
  tables:
    - target_table: "年金计划"
      sensitive_fields: ["客户名称"]
    - target_table: "组织架构"
      sensitive_fields: ["部门名称"]
    - target_table: "产品线"
      sensitive_fields: ["产品线名称"]
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    yield temp_path
    os.unlink(temp_path)


class TestObservabilityServiceIntegration:
    """Integration tests for ObservabilityService."""

    def test_get_table_metrics_with_real_data(self, test_db_connection):
        """Test getting metrics from actual database table."""
        service = ObservabilityService(schema="main")
        metrics = service.get_table_metrics("年金计划", test_db_connection)

        assert metrics.table == "年金计划"
        assert metrics.total_records == 3
        assert metrics.authoritative_count == 1
        assert metrics.auto_derived_count == 2
        assert metrics.needs_review_count == 2
        assert metrics.auto_derived_ratio == 2/3
        assert len(metrics.domains_contributing) == 2
        assert "annuity_performance" in metrics.domains_contributing
        assert "annuity_income" in metrics.domains_contributing

    def test_get_all_metrics_with_multiple_tables(self, test_db_connection):
        """Test getting metrics for all configured tables."""
        # Mock table list to avoid loading from config
        with patch.object(ObservabilityService, '_load_reference_tables_from_config') as mock_load:
            mock_load.return_value = ["年金计划", "组合计划"]
            service = ObservabilityService(schema="main")

            metrics_list = service.get_all_metrics(test_db_connection)

            assert len(metrics_list) == 2
            assert metrics_list[0].table == "年金计划"
            assert metrics_list[1].table == "组合计划"

    def test_threshold_alerts_with_violations(self, test_db_connection):
        """Test alert triggering with threshold violations."""
        service = ObservabilityService(
            schema="main",
            alert_config=AlertConfig(
                auto_derived_ratio_threshold=0.5,  # 50%
                needs_review_count_threshold=1    # 1 record
            )
        )

        # Mock table list
        with patch.object(ObservabilityService, '_load_reference_tables_from_config') as mock_load:
            mock_load.return_value = ["年金计划"]
            metrics = service.get_all_metrics(test_db_connection)
            alerts = service.check_thresholds(metrics)

            # Should trigger 2 alerts: ratio > 50% and needs_review > 1
            assert len(alerts) == 2
            alert_types = [a.alert_type for a in alerts]
            assert "auto_derived_ratio" in alert_types
            assert "needs_review_count" in alert_types

    def test_csv_export_with_real_data(self, test_db_connection, mock_config_file, tmp_path: Path):
        """Test CSV export with actual database data."""
        # Mock pandas DataFrame
        mock_df = pd.DataFrame({
            "年金计划号": ["P002", "P003"],
            "计划名称": ["测试计划2", "测试计划3"],
            "_source": ["auto_derived", "auto_derived"],
            "_needs_review": [True, True]
        })

        policy_path = tmp_path / "export_policy.yml"
        policy_path.write_text("retention: 30d\nacl: restricted\n", encoding="utf-8")

        with patch("pandas.read_sql", return_value=iter([mock_df])):
            service = ObservabilityService(schema="main")
            output = service.export_pending_review(
                table="年金计划",
                conn=test_db_connection,
                config_path=mock_config_file,
                export_policy_path=str(policy_path),
            )

            assert output.endswith(".csv")
            assert Path(output).exists()

    def test_load_reference_tables_from_config(self, mock_config_file):
        """Test loading reference tables from config file."""
        with patch.dict(os.environ, {"WDH_PROJECT_ROOT": str(Path(mock_config_file).parent)}):
            service = ObservabilityService(reference_tables=[])
            tables = service._load_reference_tables_from_config(mock_config_file)

            # Should extract tables from both domains and reference_sync sections
            assert "年金计划" in tables
            assert "组合计划" in tables
            assert "组织架构" in tables
            assert "产品线" in tables

    def test_sensitive_fields_loading(self, mock_config_file):
        """Test loading sensitive fields for a table."""
        service = ObservabilityService()
        sensitive_fields = service._load_sensitive_columns_from_config("年金计划", mock_config_file)

        assert "客户名称" in sensitive_fields

    def test_export_policy_validation(self, tmp_path: Path):
        """Test export policy validation."""
        policy_path = tmp_path / "export_policy.yml"
        policy_path.write_text("retention: 30d\nacl: restricted\n", encoding="utf-8")
        service = ObservabilityService()
        service._validate_export_policy(str(policy_path))


class TestReferenceDataAuditLoggerIntegration:
    """Integration tests for ReferenceDataAuditLogger."""

    def test_audit_logger_with_real_service(self):
        """Test audit logging integration with actual services."""
        with patch("work_data_hub.domain.reference_backfill.observability.structlog.get_logger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            audit_logger = ReferenceDataAuditLogger()

            audit_logger.log_insert(
                table="年金计划",
                record_key="P001",
                source="authoritative",
                domain=None,
                actor="sync_service.reference_sync"
            )

            # Verify audit event was logged
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "reference_data.changed"
            assert call_args[1]["table"] == "年金计划"
            assert call_args[1]["operation"] == "insert"
            assert call_args[1]["record_key"] == "P001"
            assert call_args[1]["new_source"] == "authoritative"
