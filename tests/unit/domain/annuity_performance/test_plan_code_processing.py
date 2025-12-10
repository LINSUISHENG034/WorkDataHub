"""
Unit tests for plan code processing in annuity performance pipeline.

Tests for:
- Plan code corrections (1P0290 → P0290, 1P0807 → P0807)
- Plan code default values (empty → AN001/AN002 based on plan type)
- Edge cases (None, empty string, string "None")
"""

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.pipeline_builder import (
    _apply_plan_code_defaults,
    build_bronze_to_silver_pipeline,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone


def make_context(pipeline_name: str = "test_pipeline") -> PipelineContext:
    """Helper to create a valid PipelineContext for testing."""
    return PipelineContext(
        pipeline_name=pipeline_name,
        execution_id="test-run-001",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance"},
    )


class TestPlanCodeCorrections:
    """Test plan code correction rules."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame with various plan codes."""
        return pd.DataFrame({
            "月度": ["202411"] * 7,
            "计划代码": ["1P0290", "1P0807", "NORMAL123", None, "", "None", "FP0001"],
            "计划类型": ["集合计划", "单一计划", "集合计划", "单一计划", "集合计划", "单一计划", "集合计划"],
        })

    def test_plan_code_corrections_applied(self, sample_df):
        """Test that plan code corrections are applied correctly."""
        pipeline = build_bronze_to_silver_pipeline()
        context = make_context("test")

        result_df = pipeline.execute(sample_df.copy(), context)

        # Check corrections
        assert result_df.loc[0, "计划代码"] == "P0290"  # 1P0290 → P0290
        assert result_df.loc[1, "计划代码"] == "P0807"  # 1P0807 → P0807
        assert result_df.loc[2, "计划代码"] == "NORMAL123"  # Unchanged
        assert result_df.loc[6, "计划代码"] == "FP0001"  # Unchanged


class TestPlanCodeDefaults:
    """Test plan code default value application."""

    def test_apply_defaults_for_collective_plans(self):
        """Test default AN001 for empty collective plan codes."""
        df = pd.DataFrame({
            "计划代码": [None, "", "NORMAL123"],
            "计划类型": ["集合计划", "集合计划", "集合计划"],
        })

        result = _apply_plan_code_defaults(df)

        assert result.iloc[0] == "AN001"  # None → AN001
        assert result.iloc[1] == "AN001"  # "" → AN001
        assert result.iloc[2] == "NORMAL123"  # Unchanged

    def test_apply_defaults_for_individual_plans(self):
        """Test default AN002 for empty individual plan codes."""
        df = pd.DataFrame({
            "计划代码": [None, "", "NORMAL123"],
            "计划类型": ["单一计划", "单一计划", "单一计划"],
        })

        result = _apply_plan_code_defaults(df)

        assert result.iloc[0] == "AN002"  # None → AN002
        assert result.iloc[1] == "AN002"  # "" → AN002
        assert result.iloc[2] == "NORMAL123"  # Unchanged

    def test_preserve_string_none(self):
        """Test that string 'None' is preserved (legacy parity)."""
        df = pd.DataFrame({
            "计划代码": ["None", "NORMAL123"],
            "计划类型": ["集合计划", "单一计划"],
        })

        result = _apply_plan_code_defaults(df)

        # String "None" should be preserved, not treated as empty
        assert result.iloc[0] == "None"
        assert result.iloc[1] == "NORMAL123"

    def test_no_plan_type_column(self):
        """Test behavior when 计划类型 column doesn't exist."""
        df = pd.DataFrame({
            "计划代码": [None, "", "NORMAL123"],
        })

        result = _apply_plan_code_defaults(df)

        # Should preserve original values when no 计划类型 column
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == ""
        assert result.iloc[2] == "NORMAL123"

    def test_no_plan_code_column(self):
        """Test behavior when 计划代码 column doesn't exist."""
        df = pd.DataFrame({
            "计划类型": ["集合计划", "单一计划"],
        })

        result = _apply_plan_code_defaults(df)

        # Should return Series of None values
        assert result.isna().all()


class TestPlanCodeIntegration:
    """Integration tests for plan code processing in full pipeline."""

    @pytest.fixture
    def sample_bronze_df(self):
        """Create sample Bronze DataFrame with various plan code scenarios."""
        return pd.DataFrame({
            "月度": ["202411", "202411", "202411", "202411", "202411", "202411"],
            "计划代码": ["1P0290", "1P0807", None, "", "None", "VALID123"],
            "计划类型": ["集合计划", "单一计划", "集合计划", "单一计划", "集合计划", "单一计划"],
            "客户名称": ["公司A", "公司B", "公司C", "公司D", "公司E", "公司F"],
            "业务类型": ["企年投资", "职年受托", "企年受托", "职年投资", "企年投资", "职年受托"],
            "机构名称": ["北京", "上海", "深圳", "广东", "江苏", "浙江"],
            "期初资产规模": [1000000.0, 2000000.0, 3000000.0, 4000000.0, 5000000.0, 6000000.0],
            "期末资产规模": [1100000.0, 2200000.0, 3300000.0, 4400000.0, 5500000.0, 6600000.0],
        })

    def test_full_pipeline_plan_code_processing(self, sample_bronze_df):
        """Test plan code processing in full pipeline execution."""
        pipeline = build_bronze_to_silver_pipeline()
        context = make_context("test")

        result_df = pipeline.execute(sample_bronze_df, context)

        # Verify corrections and defaults
        assert result_df.loc[0, "计划代码"] == "P0290"  # 1P0290 → P0290
        assert result_df.loc[1, "计划代码"] == "P0807"  # 1P0807 → P0807
        assert result_df.loc[2, "计划代码"] == "AN001"  # None + 集合计划 → AN001
        assert result_df.loc[3, "计划代码"] == "AN002"  # "" + 单一计划 → AN002
        assert result_df.loc[4, "计划代码"] == "None"   # String "None" preserved
        assert result_df.loc[5, "计划代码"] == "VALID123"  # Unchanged

    def test_legacy_parity_with_test_data(self):
        """Test that pipeline maintains parity with legacy processing."""
        # Create test data that covers all edge cases
        test_data = pd.DataFrame({
            "计划代码": ["1P0290", "1P0807", None, "", "None", "EXISTING001"],
            "计划类型": ["集合计划", "单一计划", "集合计划", "单一计划", "单一计划", "集合计划"],
        })

        # Expected results based on legacy behavior
        expected = {
            0: "P0290",      # 1P0290 → P0290
            1: "P0807",      # 1P0807 → P0807
            2: "AN001",      # None + 集合计划 → AN001
            3: "AN002",      # "" + 单一计划 → AN002
            4: "None",       # String "None" preserved
            5: "EXISTING001" # Existing plan code unchanged
        }

        # Apply corrections
        test_data["计划代码"] = test_data["计划代码"].replace({"1P0290": "P0290", "1P0807": "P0807"})

        # Apply defaults
        result = _apply_plan_code_defaults(test_data)

        # Verify all results match expected legacy behavior
        for idx, expected_val in expected.items():
            assert result.iloc[idx] == expected_val, f"Row {idx}: expected {expected_val}, got {result.iloc[idx]}"