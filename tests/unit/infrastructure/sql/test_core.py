"""
Unit tests for SQL core utilities: identifier and parameters.
"""

import pytest

from work_data_hub.infrastructure.sql.core.identifier import (
    quote_identifier,
    qualify_table,
)
from work_data_hub.infrastructure.sql.core.parameters import (
    build_indexed_params,
    remap_records,
)


class TestQuoteIdentifier:
    """Tests for quote_identifier function."""

    def test_quote_ascii_column(self):
        """ASCII column names should be double-quoted."""
        assert quote_identifier("company_id") == '"company_id"'

    def test_quote_chinese_column(self):
        """Chinese column names should be double-quoted."""
        assert quote_identifier("年金计划号") == '"年金计划号"'

    def test_quote_mixed_column(self):
        """Mixed ASCII/Chinese names should be double-quoted."""
        assert quote_identifier("company_名称") == '"company_名称"'

    def test_quote_with_internal_quotes(self):
        """Internal double quotes should be escaped."""
        assert quote_identifier('column"name') == '"column""name"'

    def test_quote_mysql_dialect(self):
        """MySQL dialect should use backticks."""
        assert quote_identifier("年金计划号", dialect="mysql") == "`年金计划号`"

    def test_quote_mysql_with_internal_backtick(self):
        """MySQL internal backticks should be escaped."""
        assert quote_identifier("column`name", dialect="mysql") == "`column``name`"


class TestQualifyTable:
    """Tests for qualify_table function."""

    def test_qualify_with_schema(self):
        """Table with schema should be schema.quoted_table."""
        result = qualify_table("年金计划", schema="mapping")
        assert result == 'mapping."年金计划"'

    def test_qualify_without_schema(self):
        """Table without schema should just be quoted."""
        result = qualify_table("users")
        assert result == '"users"'

    def test_qualify_ascii_table_with_schema(self):
        """ASCII table with schema."""
        result = qualify_table("company_mapping", schema="enterprise")
        assert result == 'enterprise."company_mapping"'


class TestBuildIndexedParams:
    """Tests for build_indexed_params function."""

    def test_basic_columns(self):
        """Basic column mapping should create col_0, col_1, etc."""
        columns = ["年金计划号", "计划全称"]
        col_map, placeholders = build_indexed_params(columns)

        assert col_map == {"年金计划号": "col_0", "计划全称": "col_1"}
        assert placeholders == [":col_0", ":col_1"]

    def test_single_column(self):
        """Single column should work."""
        col_map, placeholders = build_indexed_params(["id"])
        assert col_map == {"id": "col_0"}
        assert placeholders == [":col_0"]

    def test_many_columns(self):
        """Many columns should work."""
        columns = ["a", "b", "c", "d", "e"]
        col_map, placeholders = build_indexed_params(columns)

        assert len(col_map) == 5
        assert len(placeholders) == 5
        assert col_map["e"] == "col_4"
        assert placeholders[4] == ":col_4"


class TestRemapRecords:
    """Tests for remap_records function."""

    def test_basic_remap(self):
        """Basic record remapping."""
        records = [{"年金计划号": "001", "计划全称": "Test Plan"}]
        param_map = {"年金计划号": "col_0", "计划全称": "col_1"}

        result = remap_records(records, param_map)

        assert result == [{"col_0": "001", "col_1": "Test Plan"}]

    def test_multiple_records(self):
        """Multiple records should all be remapped."""
        records = [
            {"id": "001", "name": "A"},
            {"id": "002", "name": "B"},
        ]
        param_map = {"id": "col_0", "name": "col_1"}

        result = remap_records(records, param_map)

        assert len(result) == 2
        assert result[0] == {"col_0": "001", "col_1": "A"}
        assert result[1] == {"col_0": "002", "col_1": "B"}

    def test_ignores_unmapped_columns(self):
        """Columns not in param_map should be ignored."""
        records = [{"id": "001", "name": "A", "extra": "X"}]
        param_map = {"id": "col_0", "name": "col_1"}

        result = remap_records(records, param_map)

        assert result == [{"col_0": "001", "col_1": "A"}]
