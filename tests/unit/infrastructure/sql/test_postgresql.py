"""
Unit tests for PostgreSQL dialect and InsertBuilder.
"""

import pytest

from work_data_hub.infrastructure.sql.dialects.postgresql import PostgreSQLDialect
from work_data_hub.infrastructure.sql.operations.insert import InsertBuilder


class TestPostgreSQLDialect:
    """Tests for PostgreSQL dialect."""

    @pytest.fixture
    def dialect(self):
        return PostgreSQLDialect()

    def test_dialect_name(self, dialect):
        """Dialect should have correct name."""
        assert dialect.name == "postgresql"

    def test_quote_identifier(self, dialect):
        """Quote should use double quotes."""
        assert dialect.quote("年金计划号") == '"年金计划号"'

    def test_qualify_table(self, dialect):
        """Qualify should add schema prefix."""
        result = dialect.qualify("年金计划", schema="mapping")
        assert result == 'mapping."年金计划"'

    def test_build_insert(self, dialect):
        """Simple INSERT statement."""
        sql = dialect.build_insert(
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
            schema="mapping",
        )

        assert "INSERT INTO" in sql
        assert 'mapping."年金计划"' in sql
        assert '"年金计划号"' in sql
        assert '"计划全称"' in sql
        assert ":col_0" in sql
        assert ":col_1" in sql

    def test_build_insert_on_conflict_do_nothing(self, dialect):
        """INSERT ... ON CONFLICT DO NOTHING."""
        sql = dialect.build_insert_on_conflict_do_nothing(
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
            conflict_columns=["年金计划号"],
            schema="mapping",
        )

        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        assert '"年金计划号"' in sql

    def test_build_insert_on_conflict_do_update(self, dialect):
        """INSERT ... ON CONFLICT DO UPDATE with null guard."""
        sql = dialect.build_insert_on_conflict_do_update(
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
            conflict_columns=["年金计划号"],
            update_columns=["计划全称"],
            null_guard=True,
            schema="mapping",
        )

        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
        assert "CASE WHEN" in sql
        assert "IS NULL" in sql
        assert "EXCLUDED" in sql


class TestInsertBuilder:
    """Tests for InsertBuilder."""

    @pytest.fixture
    def builder(self):
        return InsertBuilder(PostgreSQLDialect())

    def test_simple_insert(self, builder):
        """Build simple INSERT statement."""
        sql = builder.insert(
            schema="mapping",
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
        )

        assert 'INSERT INTO mapping."年金计划"' in sql
        assert '"年金计划号"' in sql
        assert '"计划全称"' in sql

    def test_upsert_do_nothing(self, builder):
        """Build upsert with DO NOTHING mode."""
        sql = builder.upsert(
            schema="mapping",
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
            conflict_columns=["年金计划号"],
            mode="do_nothing",
        )

        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    def test_upsert_do_update(self, builder):
        """Build upsert with DO UPDATE mode."""
        sql = builder.upsert(
            schema="mapping",
            table="年金计划",
            columns=["年金计划号", "计划全称"],
            placeholders=[":col_0", ":col_1"],
            conflict_columns=["年金计划号"],
            mode="do_update",
            update_columns=["计划全称"],
        )

        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
        assert '"计划全称"' in sql

    def test_upsert_auto_update_columns(self, builder):
        """Update columns should be auto-derived if not provided."""
        sql = builder.upsert(
            schema="mapping",
            table="年金计划",
            columns=["年金计划号", "计划全称", "计划类型"],
            placeholders=[":col_0", ":col_1", ":col_2"],
            conflict_columns=["年金计划号"],
            mode="do_update",
        )

        # Should update 计划全称 and 计划类型, but not 年金计划号
        assert "DO UPDATE" in sql
        assert '"计划全称"' in sql
        assert '"计划类型"' in sql

    def test_upsert_with_jsonb_merge_columns(self, builder):
        """JSONB columns should use array merge syntax on conflict."""
        sql = builder.upsert(
            schema="customer",
            table="年金关联公司",
            columns=["company_id", "客户名称", "tags"],
            placeholders=[":col_0", ":col_1", ":col_2"],
            conflict_columns=["company_id"],
            mode="do_update",
            update_columns=["客户名称", "tags"],
            null_guard=True,
            jsonb_merge_columns=["tags"],
        )

        # tags should use JSONB merge syntax
        assert "COALESCE" in sql
        assert "||" in sql
        assert "jsonb_agg" in sql
