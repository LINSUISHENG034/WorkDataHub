"""
Tests for reference backfill orchestration ops.

This module tests the new backfill ops: derive_plan_refs_op, 
derive_portfolio_refs_op, and backfill_refs_op.
"""

import json
from datetime import date
from unittest.mock import Mock, patch

import pytest
import yaml
from dagster import build_op_context

from src.work_data_hub.orchestration.ops import (
    BackfillRefsConfig,
    backfill_refs_op,
    derive_plan_refs_op,
    derive_portfolio_refs_op,
)


class TestBackfillOps:
    """Test reference backfill operations."""

    @pytest.fixture
    def sample_processed_annuity_rows(self):
        """Sample processed annuity performance data."""
        return [
            {
                "计划代码": "PLAN001",
                "计划名称": "Test Plan A",
                "计划类型": "DC",
                "客户名称": "Client A",
                "company_id": "COMP1",
                "组合代码": "PORT001",
                "组合名称": "Portfolio A",
                "组合类型": "Equity",
                "月度": date(2024, 1, 31),
            },
            {
                "计划代码": "PLAN002",
                "计划名称": "Test Plan B",
                "计划类型": "DB",
                "客户名称": None,
                "company_id": "COMP2",
                "组合代码": "PORT002",
                "组合名称": None,
                "组合类型": "Bond",
                "月度": date(2024, 1, 31),
            },
        ]

    def test_derive_plan_refs_op_success(self, sample_processed_annuity_rows):
        """Test successful plan reference derivation."""
        context = build_op_context()
        
        result = derive_plan_refs_op(context, sample_processed_annuity_rows)
        
        # Verify result is JSON-serializable
        json.dumps(result)
        
        # Verify structure
        assert isinstance(result, list)
        assert len(result) == 2  # Two unique plans
        
        # Check first plan
        plan1 = next(p for p in result if p["年金计划号"] == "PLAN001")
        assert plan1["计划全称"] == "Test Plan A"
        assert plan1["计划类型"] == "DC"
        assert plan1["客户名称"] == "Client A"
        assert plan1["company_id"] == "COMP1"

    def test_derive_plan_refs_op_empty_input(self):
        """Test plan derivation with empty input."""
        context = build_op_context()
        
        result = derive_plan_refs_op(context, [])
        
        assert result == []

    def test_derive_portfolio_refs_op_success(self, sample_processed_annuity_rows):
        """Test successful portfolio reference derivation."""
        context = build_op_context()
        
        result = derive_portfolio_refs_op(context, sample_processed_annuity_rows)
        
        # Verify result is JSON-serializable
        json.dumps(result)
        
        # Verify structure
        assert isinstance(result, list)
        assert len(result) == 2  # Two unique portfolios
        
        # Check first portfolio
        port1 = next(p for p in result if p["组合代码"] == "PORT001")
        assert port1["年金计划号"] == "PLAN001"
        assert port1["组合名称"] == "Portfolio A"
        assert port1["组合类型"] == "Equity"

    def test_derive_portfolio_refs_op_empty_input(self):
        """Test portfolio derivation with empty input."""
        context = build_op_context()
        
        result = derive_portfolio_refs_op(context, [])
        
        assert result == []

    def test_backfill_refs_op_plan_only_mode(self):
        """Test backfill_refs_op in plan-only mode."""
        plan_candidates = [{"年金计划号": "PLAN001", "计划全称": "Test Plan"}]
        portfolio_candidates = [{"组合代码": "PORT001", "年金计划号": "PLAN001"}]
        
        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["all"],
            mode="insert_missing",
            plan_only=True,
        )
        
        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
        
        # Verify result is JSON-serializable
        json.dumps(result)
        
        # Check structure
        assert result["plan_only"] is True
        assert isinstance(result["operations"], list)
        assert len(result["operations"]) == 2  # Plans and portfolios

    def test_backfill_refs_op_no_targets(self):
        """Test backfill_refs_op with no targets (disabled)."""
        plan_candidates = [{"年金计划号": "PLAN001"}]
        portfolio_candidates = [{"组合代码": "PORT001", "年金计划号": "PLAN001"}]
        
        context = build_op_context()
        config = BackfillRefsConfig(
            targets=[],  # Empty targets = disabled
            mode="insert_missing",
            plan_only=True,
        )
        
        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
        
        # Should skip operations
        assert result["plan_only"] is True
        assert len(result["operations"]) == 0

    def test_backfill_refs_op_plans_only(self):
        """Test backfill_refs_op with plans target only."""
        plan_candidates = [{"年金计划号": "PLAN001", "计划全称": "Test Plan"}]
        portfolio_candidates = [{"组合代码": "PORT001", "年金计划号": "PLAN001"}]
        
        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["plans"],
            mode="insert_missing",
            plan_only=True,
        )
        
        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
        
        # Should only process plans
        assert len(result["operations"]) == 1
        assert result["operations"][0]["table"] == "年金计划"

    def test_backfill_refs_op_portfolios_only(self):
        """Test backfill_refs_op with portfolios target only."""
        plan_candidates = [{"年金计划号": "PLAN001"}]
        portfolio_candidates = [{"组合代码": "PORT001", "年金计划号": "PLAN001"}]
        
        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["portfolios"],
            mode="insert_missing",
            plan_only=True,
        )
        
        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
        
        # Should only process portfolios
        assert len(result["operations"]) == 1
        assert result["operations"][0]["table"] == "组合计划"

    def test_backfill_refs_op_fill_null_only_mode(self):
        """Test backfill_refs_op with fill_null_only mode."""
        plan_candidates = [
            {
                "年金计划号": "PLAN001",
                "计划全称": "Test Plan",
                "计划类型": "DC",
                "客户名称": "Client A",
                "company_id": "COMP1",
                "资格": None,
                "主拓机构": None,
                "备注": None,
                "主拓代码": None,
            }
        ]
        portfolio_candidates = []
        
        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["plans"],
            mode="fill_null_only",
            plan_only=True,
        )
        
        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
        
        # Should process with fill_null_only mode
        assert len(result["operations"]) == 1
        operation = result["operations"][0]
        assert operation["table"] == "年金计划"
        assert "updated" in operation  # fill_null_only returns updated count

    @patch("src.work_data_hub.orchestration.ops.insert_missing")
    def test_backfill_refs_op_execute_mode(self, mock_insert_missing):
        """Test backfill_refs_op in execute mode with mocked database."""
        mock_insert_missing.return_value = {"inserted": 1, "batches": 1}

        plan_candidates = [{"年金计划号": "PLAN001", "计划全称": "Test Plan"}]
        portfolio_candidates = []

        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["plans"],
            mode="insert_missing",
            plan_only=False,  # Execute mode
        )

        with patch("src.work_data_hub.orchestration.ops.psycopg2", create=True) as mock_psycopg2:
            # Create a proper mock connection with cursor context manager
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.__enter__ = Mock(return_value=mock_cursor)
            mock_cursor.__exit__ = Mock(return_value=None)
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
                mock_settings_instance = Mock()
                mock_settings_instance.get_database_connection_string.return_value = "postgresql://test"
                mock_settings_instance.data_sources_config = "test_config.yml"
                mock_settings.return_value = mock_settings_instance

                # Mock the YAML loading for refs config
                mock_yaml_content = {
                    "domains": {
                        "annuity_performance": {
                            "refs": {
                                "plans": {
                                    "schema": "public",
                                    "table": "年金计划",
                                    "key": ["年金计划号"],
                                    "updatable": ["计划全称", "计划类型", "客户名称", "company_id"]
                                }
                            }
                        }
                    }
                }

                with patch("builtins.open", create=True):
                    with patch("yaml.safe_load", return_value=mock_yaml_content):
                        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)

                        # Verify insert_missing was called with schema parameter
                        mock_insert_missing.assert_called_once_with(
                            table="年金计划",
                            key_cols=["年金计划号"],
                            rows=plan_candidates,
                            conn=mock_conn,
                            chunk_size=1000,
                            schema="public",  # NEW: schema parameter
                        )

                        # Verify connection cleanup
                        mock_conn.close.assert_called_once()

    def test_backfill_refs_config_validation(self):
        """Test BackfillRefsConfig validation."""
        # Valid config
        config = BackfillRefsConfig(targets=["plans"], mode="insert_missing")
        assert config.targets == ["plans"]
        assert config.mode == "insert_missing"
        
        # Invalid target
        with pytest.raises(ValueError, match="Invalid target"):
            BackfillRefsConfig(targets=["invalid_target"])
        
        # Invalid mode
        with pytest.raises(ValueError, match="not supported"):
            BackfillRefsConfig(targets=["plans"], mode="invalid_mode")
        
        # Empty targets (should be allowed)
        config = BackfillRefsConfig(targets=[])
        assert config.targets == []


class TestSkipFactsAndQualifiedSQL:
    """Test skip-facts mode and qualified SQL generation integration."""

    def test_skip_facts_mode_integration(self):
        """Test skip-facts mode works end-to-end (backfill only)."""
        from src.work_data_hub.orchestration.ops import LoadConfig, load_op

        # Setup with skip flag enabled
        context = build_op_context()
        config = LoadConfig(
            table="trustee_performance",
            mode="delete_insert",
            pk=["月度", "计划代码", "company_id"],
            plan_only=False,
            skip=True,  # Skip facts flag
        )

        # Mock processed rows (should be ignored due to skip)
        processed_rows = [
            {
                "月度": "202411",
                "计划代码": "PLAN001",
                "计划名称": "Test Plan",
                "company_id": "COMP1",
            }
        ]

        result = load_op(context, config, processed_rows)

        # Verify facts loading was skipped
        assert result["skipped"] is True
        assert result["table"] == "trustee_performance"
        assert result["mode"] == "delete_insert"
        # Should return zero values for all operations
        assert result["inserted"] == 0
        assert result["deleted"] == 0
        assert result["batches"] == 0

    @patch("src.work_data_hub.orchestration.ops.get_settings")
    @patch("builtins.open")
    @patch("yaml.safe_load")
    def test_qualified_sql_generation_with_schema_config(self, mock_yaml_load, mock_open, mock_get_settings):
        """Test qualified SQL generation uses configured schema properly."""
        from src.work_data_hub.orchestration.ops import BackfillRefsConfig, backfill_refs_op

        # Mock settings to return test data sources config path
        mock_settings_instance = Mock()
        mock_settings_instance.data_sources_config = "test_data_sources.yml"
        mock_get_settings.return_value = mock_settings_instance

        # Mock YAML content with refs configuration
        mock_yaml_content = {
            "domains": {
                "annuity_performance": {
                    "refs": {
                        "plans": {
                            "schema": "public",
                            "table": "年金计划",
                            "key": ["年金计划号"],
                            "updatable": ["计划全称", "计划类型", "客户名称", "company_id"]
                        },
                        "portfolios": {
                            "schema": "custom_schema",
                            "table": "组合计划",
                            "key": ["组合代码"],
                            "updatable": ["组合名称", "组合类型", "运作开始日"]
                        }
                    }
                }
            }
        }
        mock_yaml_load.return_value = mock_yaml_content

        # Test data
        plan_candidates = [
            {
                "年金计划号": "PLAN001",
                "计划全称": "Test Plan",
                "计划类型": "DC",
                "客户名称": "Client A",
                "company_id": "COMP1",
            }
        ]
        portfolio_candidates = [
            {
                "组合代码": "PORT001",
                "年金计划号": "PLAN001",
                "组合名称": "Test Portfolio",
                "组合类型": "Equity",
            }
        ]

        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["all"],
            mode="insert_missing",
            plan_only=True,  # Plan-only mode to avoid database operations
        )

        result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)

        # Verify configuration was read and used
        assert result["plan_only"] is True
        assert len(result["operations"]) == 2  # Plans and portfolios

        # Find the operations by table name
        plans_op = next((op for op in result["operations"] if op["table"] == "年金计划"), None)
        portfolios_op = next((op for op in result["operations"] if op["table"] == "组合计划"), None)

        assert plans_op is not None, "Plans operation not found"
        assert portfolios_op is not None, "Portfolios operation not found"

        # Verify the YAML file was opened and parsed
        mock_open.assert_called_with("test_data_sources.yml", "r", encoding="utf-8")
        mock_yaml_load.assert_called_once()

    def test_enhanced_derivations_in_full_pipeline(self):
        """Test enhanced derivations work in full pipeline context."""
        from src.work_data_hub.orchestration.ops import derive_plan_refs_op

        # Sample data with enhanced derivation requirements
        processed_rows = [
            {
                "计划代码": "PLAN001",
                "计划名称": "Enhanced Test Plan",
                "计划类型": "DC",
                "客户名称": "Client A",  # Should win tie-break
                "期末资产规模": 2000000,  # Maximum value
                "月度": 202411,  # Should format as 2411_新建
                "业务类型": "企年受托",
                "主拓代码": "AGENT001",  # From max row
                "主拓机构": "BRANCH001",  # From max row
                "company_id": "COMP1",
            },
            {
                "计划代码": "PLAN001",
                "客户名称": "Client A",  # Tied frequency
                "期末资产规模": 1000000,  # Lower value
                "月度": 202411,
                "业务类型": "年",
                "主拓代码": "AGENT002",
                "主拓机构": "BRANCH002",
                "company_id": "COMP1",
            },
            {
                "计划代码": "PLAN001",
                "客户名称": "Client B",  # Less frequent
                "期末资产规模": 1500000,
                "月度": 202411,
                "业务类型": "职年投资",
                "主拓代码": "AGENT003",
                "主拓机构": "BRANCH003",
                "company_id": "COMP1",
            },
        ]

        context = build_op_context()
        result = derive_plan_refs_op(context, processed_rows)

        # Verify enhanced derivation logic
        assert len(result) == 1
        plan = result[0]

        # Test tie-breaking: Client A wins due to max 期末资产规模
        assert plan["客户名称"] == "Client A"

        # Test max row selection for 主拓 fields
        assert plan["主拓代码"] == "AGENT001"  # From row with max 期末资产规模
        assert plan["主拓机构"] == "BRANCH001"  # From row with max 期末资产规模

        # Test date formatting
        assert plan["备注"] == "2411_新建"  # Formatted from 月度

        # Test business type ordering
        assert plan["资格"] == "企年受托+年+职年投资"  # Correct order

        # Test standard fields
        assert plan["年金计划号"] == "PLAN001"
        assert plan["计划全称"] == "Enhanced Test Plan"
        assert plan["计划类型"] == "DC"
        assert plan["company_id"] == "COMP1"

    @patch("src.work_data_hub.io.loader.warehouse_loader.quote_qualified")
    @patch("src.work_data_hub.orchestration.ops.insert_missing")
    def test_qualified_sql_generation_called_correctly(self, mock_insert_missing, mock_quote_qualified):
        """Test that qualified SQL generation is called with proper schema."""
        from src.work_data_hub.orchestration.ops import BackfillRefsConfig, backfill_refs_op

        mock_quote_qualified.return_value = '"public"."年金计划"'
        mock_insert_missing.return_value = {"inserted": 1, "batches": 1}

        plan_candidates = [
            {
                "年金计划号": "PLAN001",
                "计划全称": "Test Plan",
                "计划类型": "DC",
                "客户名称": "Client A",
                "company_id": "COMP1",
            }
        ]

        context = build_op_context()
        config = BackfillRefsConfig(
            targets=["plans"],
            mode="insert_missing",
            plan_only=True,  # Plan-only mode to see SQL generation
        )

        # Mock the settings and YAML loading for refs config
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_get_settings:
            mock_settings_instance = Mock()
            mock_settings_instance.data_sources_config = "test_config.yml"
            mock_get_settings.return_value = mock_settings_instance

            mock_yaml_content = {
                "domains": {
                    "annuity_performance": {
                        "refs": {
                            "plans": {
                                "schema": "public",
                                "table": "年金计划",
                                "key": ["年金计划号"],
                                "updatable": ["计划全称", "计划类型", "客户名称", "company_id"]
                            }
                        }
                    }
                }
            }

            with patch("builtins.open", create=True):
                with patch("yaml.safe_load", return_value=mock_yaml_content):
                    result = backfill_refs_op(context, config, plan_candidates, [])

                    # Verify operation completed
                    assert result["plan_only"] is True
                    assert len(result["operations"]) == 1

                    # Verify insert_missing was called with schema parameter
                    mock_insert_missing.assert_called_once()
                    call_args = mock_insert_missing.call_args
                    assert call_args[1]["schema"] == "public"
                    assert call_args[1]["table"] == "年金计划"
