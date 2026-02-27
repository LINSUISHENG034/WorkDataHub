"""
Unit tests for domain_registry module.

Story 6.2-P13: Unified Domain Schema Management Architecture
AC-0.4: Unit tests for domain registry
"""

from __future__ import annotations

import pytest

from work_data_hub.io.schema.domain_registry import (
    ColumnDef,
    ColumnType,
    DomainSchema,
    IndexDef,
    generate_create_table_sql,
    get_composite_key,
    get_delete_scope_key,
    get_domain,
    list_domains,
)


class TestDomainRegistryCoversExpectedDomains:
    """Test that registry contains all expected domains (AC-0.2)."""

    def test_list_domains_returns_all_four_domains(self) -> None:
        """Registry should contain exactly 4 domains."""
        domains = list_domains()
        assert len(domains) == 4
        assert "annuity_performance" in domains
        assert "annuity_income" in domains
        assert "annuity_plans" in domains
        assert "portfolio_plans" in domains

    def test_annuity_performance_registered(self) -> None:
        """annuity_performance domain should be accessible."""
        schema = get_domain("annuity_performance")
        assert schema.domain_name == "annuity_performance"
        assert schema.pg_schema == "business"
        assert schema.pg_table == "规模明细"

    def test_annuity_income_registered(self) -> None:
        """annuity_income domain should be accessible."""
        schema = get_domain("annuity_income")
        assert schema.domain_name == "annuity_income"
        assert schema.pg_schema == "business"
        assert schema.pg_table == "收入明细"

    def test_annuity_plans_registered(self) -> None:
        """annuity_plans domain should be accessible."""
        schema = get_domain("annuity_plans")
        assert schema.domain_name == "annuity_plans"
        assert schema.pg_schema == "mapping"
        assert schema.pg_table == "年金计划"

    def test_portfolio_plans_registered(self) -> None:
        """portfolio_plans domain should be accessible."""
        schema = get_domain("portfolio_plans")
        assert schema.domain_name == "portfolio_plans"
        assert schema.pg_schema == "mapping"
        assert schema.pg_table == "组合计划"


class TestGetDomainReturnsExpectedSchema:
    """Test that get_domain returns correct schema structures."""

    def test_get_domain_returns_domain_schema_instance(self) -> None:
        """get_domain should return a DomainSchema instance."""
        schema = get_domain("annuity_performance")
        assert isinstance(schema, DomainSchema)

    def test_get_domain_raises_key_error_for_unknown_domain(self) -> None:
        """get_domain should raise KeyError for unknown domain names."""
        with pytest.raises(KeyError) as exc_info:
            get_domain("nonexistent_domain")
        assert "nonexistent_domain" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    def test_annuity_performance_has_correct_delete_scope_key(self) -> None:
        """annuity_performance delete_scope_key should match DDL."""
        schema = get_domain("annuity_performance")
        assert schema.delete_scope_key == ["月度", "计划代码", "company_id"]

    def test_annuity_performance_has_correct_composite_key(self) -> None:
        """annuity_performance composite_key should include 组合代码."""
        schema = get_domain("annuity_performance")
        assert schema.composite_key == ["月度", "计划代码", "组合代码", "company_id"]

    def test_annuity_income_has_correct_delete_scope_key(self) -> None:
        """annuity_income delete_scope_key should match expected."""
        schema = get_domain("annuity_income")
        assert schema.delete_scope_key == ["月度", "计划代码", "company_id"]

    def test_portfolio_plans_has_correct_delete_scope_key(self) -> None:
        """portfolio_plans delete_scope_key should match DDL."""
        schema = get_domain("portfolio_plans")
        assert schema.delete_scope_key == ["年金计划号", "组合代码"]


class TestColumnDefinitionsComplete:
    """Test that column definitions are complete and correct (AC-0.4)."""

    def test_annuity_performance_has_columns(self) -> None:
        """annuity_performance should have column definitions."""
        schema = get_domain("annuity_performance")
        assert len(schema.columns) > 0
        column_names = [c.name for c in schema.columns]
        # Check key columns exist
        assert "月度" in column_names
        assert "计划代码" in column_names
        assert "company_id" in column_names
        assert "期初资产规模" in column_names

    def test_annuity_performance_column_types(self) -> None:
        """annuity_performance columns should have correct types."""
        schema = get_domain("annuity_performance")
        columns_by_name = {c.name: c for c in schema.columns}

        # Date column
        assert columns_by_name["月度"].column_type == ColumnType.DATE
        assert columns_by_name["月度"].nullable is False

        # String column
        assert columns_by_name["计划代码"].column_type == ColumnType.STRING
        assert columns_by_name["计划代码"].nullable is False

        # Decimal column
        assert columns_by_name["期初资产规模"].column_type == ColumnType.DECIMAL
        assert columns_by_name["期初资产规模"].precision == 18
        assert columns_by_name["期初资产规模"].scale == 4

    def test_annuity_income_has_columns(self) -> None:
        """annuity_income should have column definitions."""
        schema = get_domain("annuity_income")
        assert len(schema.columns) > 0
        column_names = [c.name for c in schema.columns]
        # Check key columns exist
        assert "月度" in column_names
        assert "计划代码" in column_names
        assert "固费" in column_names
        assert "浮费" in column_names

    def test_annuity_plans_has_columns(self) -> None:
        """annuity_plans should have column definitions."""
        schema = get_domain("annuity_plans")
        assert len(schema.columns) > 0
        column_names = [c.name for c in schema.columns]
        assert "年金计划号" in column_names
        assert "计划简称" in column_names

    def test_portfolio_plans_has_columns(self) -> None:
        """portfolio_plans should have column definitions."""
        schema = get_domain("portfolio_plans")
        assert len(schema.columns) > 0
        column_names = [c.name for c in schema.columns]
        assert "组合代码" in column_names
        assert "年金计划号" in column_names

    def test_columns_are_column_def_instances(self) -> None:
        """All columns should be ColumnDef instances."""
        for domain_name in list_domains():
            schema = get_domain(domain_name)
            for col in schema.columns:
                assert isinstance(col, ColumnDef)
                assert isinstance(col.column_type, ColumnType)


class TestGenerateCreateTableSqlIsDeterministic:
    """Test that DDL generation is deterministic (AC-0.4)."""

    def test_generate_sql_is_deterministic(self) -> None:
        """Calling generate_create_table_sql multiple times should yield same output."""
        sql1 = generate_create_table_sql("annuity_performance")
        sql2 = generate_create_table_sql("annuity_performance")
        assert sql1 == sql2

    def test_generate_sql_contains_no_timestamps(self) -> None:
        """Generated SQL should not contain dynamic timestamps."""
        sql = generate_create_table_sql("annuity_performance")
        # Should not contain date/time patterns like 2025-12-19
        assert "2025-" not in sql
        assert "CURRENT_DATE" not in sql.replace("CURRENT_TIMESTAMP", "")

    def test_generate_sql_contains_table_name(self) -> None:
        """Generated SQL should contain the correct table name."""
        sql = generate_create_table_sql("annuity_performance")
        assert '"规模明细"' in sql
        assert "business" in sql

    def test_generate_sql_contains_audit_columns(self) -> None:
        """Generated SQL should include audit columns."""
        sql = generate_create_table_sql("annuity_performance")
        assert "created_at" in sql
        assert "updated_at" in sql
        assert "CURRENT_TIMESTAMP" in sql

    def test_generate_sql_contains_trigger(self) -> None:
        """Generated SQL should include updated_at trigger."""
        sql = generate_create_table_sql("annuity_performance")
        assert "CREATE OR REPLACE FUNCTION" in sql
        assert "CREATE TRIGGER" in sql
        assert "BEFORE UPDATE" in sql

    def test_generate_sql_contains_indexes(self) -> None:
        """Generated SQL should include index definitions."""
        sql = generate_create_table_sql("annuity_performance")
        assert "CREATE INDEX IF NOT EXISTS" in sql
        assert "idx_" in sql

    def test_generate_sql_quotes_chinese_identifiers(self) -> None:
        """Generated SQL should properly quote Chinese identifiers."""
        sql = generate_create_table_sql("annuity_performance")
        # Chinese column names should be quoted
        assert '"月度"' in sql
        assert '"计划代码"' in sql
        assert '"期初资产规模"' in sql

    def test_generate_sql_for_each_domain(self) -> None:
        """DDL generation should work for all registered domains."""
        for domain_name in list_domains():
            sql = generate_create_table_sql(domain_name)
            assert len(sql) > 100  # Should produce substantial DDL
            assert "CREATE TABLE" in sql
            assert "DROP TABLE" in sql


class TestHelperFunctions:
    """Test helper functions for accessing domain configuration."""

    def test_get_composite_key(self) -> None:
        """get_composite_key should return correct values."""
        key = get_composite_key("annuity_performance")
        assert key == ["月度", "计划代码", "组合代码", "company_id"]

    def test_get_delete_scope_key(self) -> None:
        """get_delete_scope_key should return correct values."""
        key = get_delete_scope_key("annuity_performance")
        assert key == ["月度", "计划代码", "company_id"]

    def test_get_composite_key_raises_for_unknown_domain(self) -> None:
        """get_composite_key should raise KeyError for unknown domain."""
        with pytest.raises(KeyError):
            get_composite_key("unknown_domain")

    def test_get_delete_scope_key_raises_for_unknown_domain(self) -> None:
        """get_delete_scope_key should raise KeyError for unknown domain."""
        with pytest.raises(KeyError):
            get_delete_scope_key("unknown_domain")


class TestIndexDefinitions:
    """Test that index definitions are correct."""

    def test_annuity_performance_has_indexes(self) -> None:
        """annuity_performance should have index definitions."""
        schema = get_domain("annuity_performance")
        assert len(schema.indexes) > 0
        for idx in schema.indexes:
            assert isinstance(idx, IndexDef)
            assert len(idx.columns) > 0

    def test_annuity_performance_indexes_match_ddl(self) -> None:
        """annuity_performance indexes should match existing DDL patterns."""
        schema = get_domain("annuity_performance")
        index_columns = [tuple(idx.columns) for idx in schema.indexes]
        # Key indexes from the DDL
        assert ("月度",) in index_columns
        assert ("计划代码",) in index_columns
        assert ("company_id",) in index_columns
        assert ("月度", "计划代码", "company_id") in index_columns


class TestBronzeGoldConfiguration:
    """Test Bronze/Gold layer configuration is present."""

    def test_annuity_performance_bronze_required(self) -> None:
        """annuity_performance should have bronze_required columns."""
        schema = get_domain("annuity_performance")
        assert len(schema.bronze_required) > 0
        assert "月度" in schema.bronze_required
        assert "计划代码" in schema.bronze_required

    def test_annuity_performance_gold_required(self) -> None:
        """annuity_performance should have gold_required columns."""
        schema = get_domain("annuity_performance")
        assert len(schema.gold_required) > 0
        assert "company_id" in schema.gold_required

    def test_annuity_performance_numeric_columns(self) -> None:
        """annuity_performance should have numeric_columns list."""
        schema = get_domain("annuity_performance")
        assert len(schema.numeric_columns) > 0
        assert "期初资产规模" in schema.numeric_columns
        assert "投资收益" in schema.numeric_columns

    def test_annuity_income_bronze_required(self) -> None:
        """annuity_income should have bronze_required columns."""
        schema = get_domain("annuity_income")
        assert len(schema.bronze_required) > 0
        assert "月度" in schema.bronze_required
        assert "固费" in schema.bronze_required
