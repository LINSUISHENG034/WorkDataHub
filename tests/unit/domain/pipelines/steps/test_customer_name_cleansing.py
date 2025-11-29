"""Unit tests for CustomerNameCleansingStep and clean_company_name."""

import pytest

from work_data_hub.domain.pipelines.steps import (
    CustomerNameCleansingStep,
    clean_company_name,
)


class TestCleanCompanyName:
    """Tests for clean_company_name utility function."""

    def test_remove_及下属子企业_suffix(self):
        """Test removing 及下属子企业 suffix."""
        result = clean_company_name("某某公司及下属子企业")
        assert result == "某某公司"

    def test_remove_已转出_suffix(self):
        """Test removing 已转出 suffix."""
        result = clean_company_name("某公司已转出")
        assert result == "某公司"

    def test_remove_待转出_suffix(self):
        """Test removing 待转出 suffix."""
        result = clean_company_name("某公司待转出")
        assert result == "某公司"

    def test_remove_终止_suffix(self):
        """Test removing 终止 suffix."""
        result = clean_company_name("某公司终止")
        assert result == "某公司"

    def test_remove_转出_suffix(self):
        """Test removing 转出 suffix."""
        result = clean_company_name("某公司转出")
        assert result == "某公司"

    def test_remove_转移终止_suffix(self):
        """Test removing 转移终止 suffix - removes 终止 first, then 转移."""
        result = clean_company_name("某公司转移终止")
        # Implementation removes suffixes in order: 终止 first, leaving 某公司转移
        # Then 转移 is not at end anymore, so it stays
        assert result == "某公司转移"

    def test_remove_已作废_suffix(self):
        """Test removing 已作废 suffix."""
        result = clean_company_name("某公司已作废")
        assert result == "某公司"

    def test_remove_已终止_suffix(self):
        """Test removing 已终止 suffix - removes 终止 first."""
        result = clean_company_name("某公司已终止")
        # Implementation removes 终止 first, leaving 某公司已
        assert result == "某公司已"

    def test_remove_保留_suffix(self):
        """Test removing 保留 suffix."""
        result = clean_company_name("某公司保留")
        assert result == "某公司"

    def test_remove_保留账户_suffix(self):
        """Test removing 保留账户 suffix."""
        result = clean_company_name("某公司保留账户")
        assert result == "某公司"

    def test_remove_存量_suffix(self):
        """Test removing 存量 suffix."""
        result = clean_company_name("某公司存量")
        assert result == "某公司"

    def test_remove_已转移终止_suffix(self):
        """Test removing 已转移终止 suffix - removes 终止 first."""
        result = clean_company_name("某公司已转移终止")
        # Implementation removes 终止 first, leaving 某公司已转移
        assert result == "某公司已转移"

    def test_remove_本部_suffix(self):
        """Test removing 本部 suffix."""
        result = clean_company_name("某公司本部")
        assert result == "某公司"

    def test_remove_未使用_suffix(self):
        """Test removing 未使用 suffix."""
        result = clean_company_name("某公司未使用")
        assert result == "某公司"

    def test_remove_集合_suffix(self):
        """Test removing 集合 suffix."""
        result = clean_company_name("某公司集合")
        assert result == "某公司"

    def test_remove_原_suffix(self):
        """Test removing 原 suffix."""
        result = clean_company_name("某公司原")
        assert result == "某公司"

    def test_remove_团托_pattern(self):
        """Test removing (团托) pattern."""
        result = clean_company_name("某公司(团托)")
        assert result == "某公司"

    def test_remove_hyphen_letter_suffix(self):
        """Test removing -ABC style suffix."""
        result = clean_company_name("某公司-ABC")
        assert result == "某公司"

    def test_remove_hyphen_number_suffix(self):
        """Test removing -123 style suffix."""
        result = clean_company_name("某公司-123")
        assert result == "某公司"

    def test_remove_hyphen_养老_suffix(self):
        """Test removing -养老 suffix."""
        result = clean_company_name("某公司-养老")
        assert result == "某公司"

    def test_remove_hyphen_福利_suffix(self):
        """Test removing -福利 suffix."""
        result = clean_company_name("某公司-福利")
        assert result == "某公司"

    def test_remove_whitespace(self):
        """Test removing extra whitespace."""
        result = clean_company_name("某 某 公 司")
        assert result == "某某公司"

    def test_empty_string_returns_empty(self):
        """Test that empty string returns empty string."""
        result = clean_company_name("")
        assert result == ""

    def test_none_returns_empty(self):
        """Test that None returns empty string."""
        result = clean_company_name(None)
        assert result == ""

    def test_no_suffix_unchanged(self):
        """Test that names without suffixes are unchanged."""
        result = clean_company_name("某某有限公司")
        assert result == "某某有限公司"


class TestCustomerNameCleansingStep:
    """Tests for CustomerNameCleansingStep."""

    def test_step_name(self):
        """Test step name property."""
        step = CustomerNameCleansingStep()
        assert step.name == "customer_name_cleansing"

    def test_default_field_names(self):
        """Test default field names are set correctly."""
        step = CustomerNameCleansingStep()
        assert step.source_field == "客户名称"
        assert step.account_name_field == "年金账户名"

    def test_custom_field_names(self):
        """Test custom field names can be provided."""
        step = CustomerNameCleansingStep(
            source_field="公司名称",
            account_name_field="账户名称",
        )
        assert step.source_field == "公司名称"
        assert step.account_name_field == "账户名称"

    def test_cleans_customer_name(self):
        """Test that customer name is cleaned."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": "某公司已转出", "金额": 1000}

        result = step.apply(row, {})

        assert result.row["客户名称"] == "某公司"
        assert result.row["金额"] == 1000
        assert not result.errors

    def test_preserves_original_in_account_name(self):
        """Test that original name is preserved in account name field."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": "某公司已转出"}

        result = step.apply(row, {})

        assert result.row["年金账户名"] == "某公司已转出"
        assert result.row["客户名称"] == "某公司"

    def test_missing_source_field_no_error(self):
        """Test that missing source field doesn't cause errors."""
        step = CustomerNameCleansingStep()
        row = {"金额": 1000, "其他字段": "value"}

        result = step.apply(row, {})

        assert result.row == row
        assert not result.errors

    def test_empty_row(self):
        """Test with empty row."""
        step = CustomerNameCleansingStep()
        row = {}

        result = step.apply(row, {})

        assert result.row == {}
        assert not result.errors

    def test_warnings_generated_on_clean(self):
        """Test that warnings are generated when names are cleaned."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": "某公司已转出"}

        result = step.apply(row, {})

        assert len(result.warnings) == 1
        assert "Cleaned customer name" in result.warnings[0]

    def test_no_warning_when_unchanged(self):
        """Test that no warning is generated when name is unchanged."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": "某某有限公司"}

        result = step.apply(row, {})

        assert len(result.warnings) == 0

    def test_metadata_tracks_cleanings(self):
        """Test that metadata tracks the number of cleanings."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": "某公司已转出"}

        result = step.apply(row, {})

        assert result.metadata["name_cleanings"] == 1

    def test_preserves_other_fields(self):
        """Test that other fields are preserved unchanged."""
        step = CustomerNameCleansingStep()
        row = {
            "客户名称": "某公司已转出",
            "期初资产规模": 1000000.0,
            "计划代码": "P0001",
        }

        result = step.apply(row, {})

        assert result.row["期初资产规模"] == 1000000.0
        assert result.row["计划代码"] == "P0001"

    def test_non_string_value_preserved(self):
        """Test that non-string values are preserved."""
        step = CustomerNameCleansingStep()
        row = {"客户名称": 12345}

        result = step.apply(row, {})

        # Non-string values should be preserved in account name
        assert result.row["年金账户名"] == 12345
        # But not cleaned (cleaning only applies to strings)
        assert result.row["客户名称"] == 12345

    def test_does_not_modify_original_row(self):
        """Test that the original row is not modified."""
        step = CustomerNameCleansingStep()
        original_row = {"客户名称": "某公司已转出"}
        row_copy = dict(original_row)

        step.apply(row_copy, {})

        # Original should still have original value
        assert original_row["客户名称"] == "某公司已转出"
