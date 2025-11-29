"""Unit tests for FieldCleanupStep."""

import pytest

from work_data_hub.domain.pipelines.steps import FieldCleanupStep


class TestFieldCleanupStep:
    """Tests for FieldCleanupStep."""

    def test_step_name(self):
        """Test step name property."""
        step = FieldCleanupStep()
        assert step.name == "field_cleanup"

    def test_default_columns_to_drop(self):
        """Test default columns to drop are set correctly."""
        step = FieldCleanupStep()
        assert step.columns_to_drop == [
            "备注",
            "子企业号",
            "子企业名称",
            "集团企业客户号",
            "集团企业客户名称",
        ]

    def test_custom_columns_to_drop(self):
        """Test custom columns to drop can be provided."""
        custom_columns = ["col1", "col2", "col3"]
        step = FieldCleanupStep(columns_to_drop=custom_columns)
        assert step.columns_to_drop == custom_columns

    def test_drop_备注_column(self):
        """Test dropping 备注 column."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "备注": "test note", "金额": 1000}

        result = step.apply(row, {})

        assert "备注" not in result.row
        assert result.row["客户名称"] == "某公司"
        assert result.row["金额"] == 1000
        assert not result.errors

    def test_drop_子企业号_column(self):
        """Test dropping 子企业号 column."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "子企业号": "12345"}

        result = step.apply(row, {})

        assert "子企业号" not in result.row
        assert result.row["客户名称"] == "某公司"

    def test_drop_子企业名称_column(self):
        """Test dropping 子企业名称 column."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "子企业名称": "子公司A"}

        result = step.apply(row, {})

        assert "子企业名称" not in result.row
        assert result.row["客户名称"] == "某公司"

    def test_drop_集团企业客户号_column(self):
        """Test dropping 集团企业客户号 column."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "集团企业客户号": "G12345"}

        result = step.apply(row, {})

        assert "集团企业客户号" not in result.row
        assert result.row["客户名称"] == "某公司"

    def test_drop_集团企业客户名称_column(self):
        """Test dropping 集团企业客户名称 column."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "集团企业客户名称": "集团公司"}

        result = step.apply(row, {})

        assert "集团企业客户名称" not in result.row
        assert result.row["客户名称"] == "某公司"

    def test_drop_multiple_columns(self):
        """Test dropping multiple columns at once."""
        step = FieldCleanupStep()
        row = {
            "客户名称": "某公司",
            "备注": "note",
            "子企业号": "12345",
            "子企业名称": "子公司",
            "集团企业客户号": "G123",
            "集团企业客户名称": "集团",
            "金额": 1000,
        }

        result = step.apply(row, {})

        assert "备注" not in result.row
        assert "子企业号" not in result.row
        assert "子企业名称" not in result.row
        assert "集团企业客户号" not in result.row
        assert "集团企业客户名称" not in result.row
        assert result.row["客户名称"] == "某公司"
        assert result.row["金额"] == 1000

    def test_no_matching_columns(self):
        """Test when no columns match the drop list."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "金额": 1000}

        result = step.apply(row, {})

        assert result.row == row
        assert not result.errors
        assert result.metadata["dropped_fields"] == 0

    def test_empty_row(self):
        """Test with empty row."""
        step = FieldCleanupStep()
        row = {}

        result = step.apply(row, {})

        assert result.row == {}
        assert not result.errors
        assert result.metadata["dropped_fields"] == 0

    def test_warnings_generated_on_drop(self):
        """Test that warnings are generated when columns are dropped."""
        step = FieldCleanupStep()
        row = {"客户名称": "某公司", "备注": "note"}

        result = step.apply(row, {})

        assert len(result.warnings) == 1
        assert "Dropped invalid field: 备注" in result.warnings[0]

    def test_metadata_tracks_dropped_count(self):
        """Test that metadata tracks the number of dropped columns."""
        step = FieldCleanupStep()
        row = {"备注": "note", "子企业号": "12345", "客户名称": "某公司"}

        result = step.apply(row, {})

        assert result.metadata["dropped_fields"] == 2

    def test_preserves_other_fields(self):
        """Test that non-dropped fields are preserved unchanged."""
        step = FieldCleanupStep()
        row = {
            "备注": "note",
            "期初资产规模": 1000000.0,
            "期末资产规模": 1100000.0,
            "客户名称": "某某公司",
            "计划代码": "P0001",
        }

        result = step.apply(row, {})

        assert result.row["期初资产规模"] == 1000000.0
        assert result.row["期末资产规模"] == 1100000.0
        assert result.row["客户名称"] == "某某公司"
        assert result.row["计划代码"] == "P0001"

    def test_custom_columns_drop_correctly(self):
        """Test that custom columns are dropped correctly."""
        step = FieldCleanupStep(columns_to_drop=["custom_col", "another_col"])
        row = {
            "客户名称": "某公司",
            "custom_col": "value1",
            "another_col": "value2",
            "keep_col": "keep",
        }

        result = step.apply(row, {})

        assert "custom_col" not in result.row
        assert "another_col" not in result.row
        assert result.row["客户名称"] == "某公司"
        assert result.row["keep_col"] == "keep"

    def test_does_not_modify_original_row(self):
        """Test that the original row is not modified."""
        step = FieldCleanupStep()
        original_row = {"客户名称": "某公司", "备注": "note"}
        row_copy = dict(original_row)

        step.apply(row_copy, {})

        # Original should still have 备注
        assert "备注" in original_row

    def test_default_columns_list_is_independent(self):
        """Test that default columns list is independent per instance."""
        step1 = FieldCleanupStep()
        step2 = FieldCleanupStep()

        # Modifying one shouldn't affect the other
        step1.columns_to_drop.append("new_col")

        assert "new_col" not in step2.columns_to_drop
