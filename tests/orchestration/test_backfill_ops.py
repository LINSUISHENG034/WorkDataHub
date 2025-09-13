"""
Tests for reference backfill orchestration ops.

This module tests the new backfill ops: derive_plan_refs_op, 
derive_portfolio_refs_op, and backfill_refs_op.
"""

import json
from datetime import date
from unittest.mock import Mock, patch

import pytest
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
            mock_conn = Mock()
            mock_psycopg2.connect.return_value = mock_conn
            
            with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
                mock_settings.return_value.get_database_connection_string.return_value = "postgresql://test"
                
                result = backfill_refs_op(context, config, plan_candidates, portfolio_candidates)
                
                # Verify insert_missing was called
                mock_insert_missing.assert_called_once_with(
                    table="年金计划",
                    key_cols=["年金计划号"],
                    rows=plan_candidates,
                    conn=mock_conn,
                    chunk_size=1000,
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