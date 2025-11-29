"""Unit tests for ColumnNormalizationStep."""

import pytest

from work_data_hub.domain.pipelines.steps import ColumnNormalizationStep


class TestColumnNormalizationStep:
    """Tests for ColumnNormalizationStep."""

    def test_step_name(self):
        """Test step name property."""
        step = ColumnNormalizationStep()
        assert step.name == "column_normalization"

    def test_default_column_mappings(self):
        """Test default column mappings are set correctly."""
        step = ColumnNormalizationStep()
        assert step.column_mappings == {
            "机构": "机构名称",
            "计划号": "计划代码",
            "流失（含待遇支付）": "流失(含待遇支付)",
        }

    def test_custom_column_mappings(self):
        """Test custom column mappings can be provided."""
        custom_mappings = {"old_col": "new_col", "another": "renamed"}
        step = ColumnNormalizationStep(column_mappings=custom_mappings)
        assert step.column_mappings == custom_mappings

    def test_rename_机构_to_机构名称(self):
        """Test renaming 机构 to 机构名称."""
        step = ColumnNormalizationStep()
        row = {"机构": "北京分公司", "其他字段": "value"}

        result = step.apply(row, {})

        assert result.row["机构名称"] == "北京分公司"
        assert "机构" not in result.row
        assert result.row["其他字段"] == "value"
        assert not result.errors

    def test_rename_计划号_to_计划代码(self):
        """Test renaming 计划号 to 计划代码."""
        step = ColumnNormalizationStep()
        row = {"计划号": "P0001", "客户名称": "某公司"}

        result = step.apply(row, {})

        assert result.row["计划代码"] == "P0001"
        assert "计划号" not in result.row
        assert result.row["客户名称"] == "某公司"

    def test_rename_流失_含待遇支付_parentheses(self):
        """Test renaming 流失（含待遇支付） to 流失(含待遇支付)."""
        step = ColumnNormalizationStep()
        row = {"流失（含待遇支付）": 1000.0}

        result = step.apply(row, {})

        assert result.row["流失(含待遇支付)"] == 1000.0
        assert "流失（含待遇支付）" not in result.row

    def test_multiple_renames_in_single_row(self):
        """Test multiple column renames in a single row."""
        step = ColumnNormalizationStep()
        row = {
            "机构": "上海分公司",
            "计划号": "P0002",
            "流失（含待遇支付）": 500.0,
            "保留字段": "unchanged",
        }

        result = step.apply(row, {})

        assert result.row["机构名称"] == "上海分公司"
        assert result.row["计划代码"] == "P0002"
        assert result.row["流失(含待遇支付)"] == 500.0
        assert result.row["保留字段"] == "unchanged"
        assert "机构" not in result.row
        assert "计划号" not in result.row
        assert "流失（含待遇支付）" not in result.row

    def test_no_matching_columns(self):
        """Test when no columns match the mapping."""
        step = ColumnNormalizationStep()
        row = {"客户名称": "某公司", "金额": 1000}

        result = step.apply(row, {})

        assert result.row == row
        assert not result.errors
        assert result.metadata["renamed_columns"] == 0

    def test_empty_row(self):
        """Test with empty row."""
        step = ColumnNormalizationStep()
        row = {}

        result = step.apply(row, {})

        assert result.row == {}
        assert not result.errors
        assert result.metadata["renamed_columns"] == 0

    def test_warnings_generated_on_rename(self):
        """Test that warnings are generated when columns are renamed."""
        step = ColumnNormalizationStep()
        row = {"机构": "北京分公司"}

        result = step.apply(row, {})

        assert len(result.warnings) == 1
        assert "Renamed 1 legacy column names" in result.warnings[0]

    def test_metadata_tracks_renamed_count(self):
        """Test that metadata tracks the number of renamed columns."""
        step = ColumnNormalizationStep()
        row = {"机构": "北京", "计划号": "P001"}

        result = step.apply(row, {})

        assert result.metadata["renamed_columns"] == 2

    def test_preserves_other_fields(self):
        """Test that non-mapped fields are preserved unchanged."""
        step = ColumnNormalizationStep()
        row = {
            "机构": "北京分公司",
            "期初资产规模": 1000000.0,
            "期末资产规模": 1100000.0,
            "客户名称": "某某公司",
        }

        result = step.apply(row, {})

        assert result.row["期初资产规模"] == 1000000.0
        assert result.row["期末资产规模"] == 1100000.0
        assert result.row["客户名称"] == "某某公司"

    def test_does_not_modify_original_row(self):
        """Test that the original row is not modified."""
        step = ColumnNormalizationStep()
        original_row = {"机构": "北京分公司"}
        row_copy = dict(original_row)

        step.apply(row_copy, {})

        # Original should still have 机构
        assert "机构" in original_row
