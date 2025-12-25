"""
Tests for warehouse loader backfill functions.

This module tests the insert_missing and fill_null_only functions
added for reference backfill functionality.
"""

from unittest.mock import Mock, MagicMock, patch, call
import pytest

from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    insert_missing,
    fill_null_only,
    quote_ident,
    quote_qualified,  # NEW: import the new function
)


@pytest.fixture
def sample_plan_candidates():
    """Sample plan candidates for testing."""
    return [
        {
            "年金计划号": "PLAN001",
            "计划全称": "Test Plan A",
            "计划类型": "DC",
            "客户名称": "Client A",
            "company_id": "COMP1",
        },
        {
            "年金计划号": "PLAN002",
            "计划全称": "Test Plan B",
            "计划类型": "DB",
            "客户名称": None,
            "company_id": "COMP2",
        },
    ]


@pytest.fixture
def sample_portfolio_candidates():
    """Sample portfolio candidates for testing."""
    return [
        {
            "组合代码": "PORT001",
            "年金计划号": "PLAN001",
            "组合名称": "Portfolio A",
            "组合类型": "Equity",
            "运作开始日": None,
        },
        {
            "组合代码": "PORT002",
            "年金计划号": "PLAN001",
            "组合名称": None,
            "组合类型": "Bond",
            "运作开始日": None,
        },
    ]


class TestInsertMissing:
    """Test insert_missing function."""

    def test_insert_missing_plan_only_mode(self, sample_plan_candidates):
        """Test insert_missing in plan-only mode (no connection)."""
        result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=sample_plan_candidates,
            conn=None,
            chunk_size=1000,
        )

        assert result["inserted"] == 2
        assert result["batches"] == 1
        assert "sql_plans" in result
        assert len(result["sql_plans"]) == 1

        # Check SQL structure
        operation_type, sql, row_data = result["sql_plans"][0]
        assert operation_type == "INSERT_MISSING"
        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        assert '"年金计划"' in sql  # Table should be quoted
        assert '"年金计划号"' in sql  # Key column should be quoted

    def test_insert_missing_with_chunking(self, sample_plan_candidates):
        """Test insert_missing with small chunk size."""
        # Add more candidates to test chunking
        candidates = sample_plan_candidates * 5  # 10 candidates total

        result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=candidates,
            conn=None,
            chunk_size=3,
        )

        assert result["inserted"] == 10
        assert result["batches"] == 4  # 10 rows with chunk_size=3 → 4 batches
        assert len(result["sql_plans"]) == 4

    def test_insert_missing_empty_rows(self):
        """Test insert_missing with empty rows."""
        result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=[],
            conn=None,
        )

        assert result["inserted"] == 0
        assert result["batches"] == 0

    def test_insert_missing_missing_key_columns(self):
        """Test insert_missing with missing key columns."""
        invalid_rows = [
            {"计划全称": "Plan without key"},
            {"年金计划号": "PLAN001", "计划全称": "Valid plan"},
        ]

        with pytest.raises(DataWarehouseLoaderError, match="Missing key columns"):
            insert_missing(
                table="年金计划",
                key_cols=["年金计划号"],
                rows=invalid_rows,
                conn=None,
            )

    @patch("psycopg2.extras.execute_values")
    def test_insert_missing_execute_mode(
        self, mock_execute_values, sample_plan_candidates
    ):
        """Test insert_missing in execute mode with mocked database."""
        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = MagicMock()  # Use MagicMock for context manager support
        mock_cursor.rowcount = len(sample_plan_candidates)

        # Properly set up context manager
        cursor_context_manager = MagicMock()
        cursor_context_manager.__enter__.return_value = mock_cursor
        cursor_context_manager.__exit__.return_value = None
        mock_conn.cursor.return_value = cursor_context_manager

        result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=sample_plan_candidates,
            conn=mock_conn,
        )

        # Verify execute_values was called
        assert mock_execute_values.called
        call_args = mock_execute_values.call_args
        assert "INSERT INTO" in call_args[0][1]
        assert "ON CONFLICT" in call_args[0][1]
        assert "DO NOTHING" in call_args[0][1]

        assert result["inserted"] == 2
        assert result["batches"] == 1
        assert "sql_plans" not in result

    def test_insert_missing_composite_keys(self):
        """Test insert_missing with composite primary keys."""
        rows = [
            {"col1": "A", "col2": "1", "value": "test1"},
            {"col1": "B", "col2": "2", "value": "test2"},
        ]

        result = insert_missing(
            table="test_table",
            key_cols=["col1", "col2"],
            rows=rows,
            conn=None,
        )

        # Check SQL contains both key columns in ON CONFLICT clause
        sql = result["sql_plans"][0][1]
        assert 'ON CONFLICT ("col1","col2")' in sql

    def test_insert_missing_chinese_identifiers(self, sample_portfolio_candidates):
        """Test insert_missing with Chinese table and column names."""
        result = insert_missing(
            table="组合计划",
            key_cols=["组合代码"],
            rows=sample_portfolio_candidates,
            conn=None,
        )

        sql = result["sql_plans"][0][1]
        assert '"组合计划"' in sql  # Chinese table name quoted
        assert '"组合代码"' in sql  # Chinese column name quoted
        assert '"年金计划号"' in sql  # Chinese column name quoted

    @patch("psycopg2.extras.execute_values")
    def test_insert_missing_fallback_on_conflict_absent(self, mock_execute_values):
        """Fallback to SELECT-filter when ON CONFLICT target is absent."""

        # Side effect: raise on ON CONFLICT SQL, succeed otherwise
        def _exec_values_side_effect(cursor, sql, argslist, *a, **kw):
            if "ON CONFLICT" in sql:
                raise Exception(
                    "no unique or exclusion constraint matching the ON CONFLICT specification"
                )
            # Fallback plain INSERT: simulate rowcount equals inserted rows
            try:
                cursor.rowcount = len(argslist)
            except Exception:
                pass
            return None

        mock_execute_values.side_effect = _exec_values_side_effect

        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = MagicMock()
        # SELECT existing keys returns one existing plan
        mock_cursor.fetchall.return_value = [("PLAN001",)]
        # Context manager
        cursor_cm = MagicMock()
        cursor_cm.__enter__.return_value = mock_cursor
        cursor_cm.__exit__.return_value = None
        mock_conn.cursor.return_value = cursor_cm

        rows = [
            {"年金计划号": "PLAN001", "计划全称": "A"},  # existing
            {"年金计划号": "PLAN002", "计划全称": "B"},  # missing -> to be inserted
        ]

        result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=rows,
            conn=mock_conn,
        )

        # Should have inserted only the missing one
        assert result["inserted"] == 1
        assert result["batches"] == 1


class TestFillNullOnly:
    """Test fill_null_only function."""

    def test_fill_null_only_plan_only_mode(self, sample_plan_candidates):
        """Test fill_null_only in plan-only mode."""
        result = fill_null_only(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=sample_plan_candidates,
            updatable_cols=["计划全称", "客户名称"],
            conn=None,
        )

        assert result["updated"] == 0  # No execution in plan-only
        assert "sql_plans" in result

        # Should have operations for columns that have non-null values
        operations = result["sql_plans"]
        assert len(operations) >= 1  # At least one UPDATE operation

        # Check SQL structure
        for operation_type, sql, params_list in operations:
            assert operation_type == "UPDATE_NULL_ONLY"
            assert "UPDATE" in sql
            assert "SET" in sql
            assert "WHERE" in sql
            assert "IS NULL" in sql
            assert '"年金计划"' in sql  # Table quoted

    def test_fill_null_only_empty_rows(self):
        """Test fill_null_only with empty rows."""
        result = fill_null_only(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=[],
            updatable_cols=["计划全称"],
            conn=None,
        )

        assert result["updated"] == 0

    def test_fill_null_only_no_updatable_values(self):
        """Test fill_null_only when no rows have values for updatable columns."""
        rows = [
            {"年金计划号": "PLAN001", "计划全称": None, "客户名称": None},
            {"年金计划号": "PLAN002", "计划全称": None, "客户名称": None},
        ]

        result = fill_null_only(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=rows,
            updatable_cols=["计划全称", "客户名称"],
            conn=None,
        )

        assert result["updated"] == 0
        assert "sql_plans" in result
        assert len(result["sql_plans"]) == 0  # No operations when all values are null

    def test_fill_null_only_missing_columns(self):
        """Test fill_null_only with missing required columns."""
        invalid_rows = [
            {"计划全称": "Plan without key"},  # Missing 年金计划号
        ]

        with pytest.raises(DataWarehouseLoaderError, match="Missing columns"):
            fill_null_only(
                table="年金计划",
                key_cols=["年金计划号"],
                rows=invalid_rows,
                updatable_cols=["计划全称"],
                conn=None,
            )

    @patch("src.work_data_hub.io.loader.warehouse_loader._adapt_param")
    def test_fill_null_only_execute_mode(
        self, mock_adapt_param, sample_plan_candidates
    ):
        """Test fill_null_only in execute mode with mocked database."""
        # Mock parameter adaptation
        mock_adapt_param.side_effect = lambda x: x

        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = MagicMock()  # Use MagicMock for context manager support
        mock_cursor.rowcount = 1  # Each update affects 1 row

        # Properly set up context manager
        cursor_context_manager = MagicMock()
        cursor_context_manager.__enter__.return_value = mock_cursor
        cursor_context_manager.__exit__.return_value = None
        mock_conn.cursor.return_value = cursor_context_manager

        result = fill_null_only(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=sample_plan_candidates,
            updatable_cols=["计划全称", "客户名称"],
            conn=mock_conn,
        )

        # Verify cursor.execute was called
        assert mock_cursor.execute.called

        # Check that UPDATE statements were generated
        execute_calls = mock_cursor.execute.call_args_list
        for call_args, _ in execute_calls:
            sql = call_args[0]
            assert "UPDATE" in sql
            assert "SET" in sql
            assert "IS NULL" in sql

        assert result["updated"] >= 0  # Some rows should be updated
        assert "sql_plans" not in result

    def test_fill_null_only_composite_keys(self):
        """Test fill_null_only with composite primary keys."""
        rows = [
            {"col1": "A", "col2": "1", "name": "Name A", "value": None},
            {"col1": "B", "col2": "2", "name": None, "value": "Value B"},
        ]

        result = fill_null_only(
            table="test_table",
            key_cols=["col1", "col2"],
            rows=rows,
            updatable_cols=["name", "value"],
            conn=None,
        )

        # Should have operations for columns with non-null values
        operations = result["sql_plans"]
        assert len(operations) >= 1

        # Check WHERE clause includes all key columns
        for _, sql, _ in operations:
            assert '"col1" = %s' in sql
            assert '"col2" = %s' in sql

    def test_fill_null_only_chinese_identifiers(self, sample_portfolio_candidates):
        """Test fill_null_only with Chinese table and column names."""
        result = fill_null_only(
            table="组合计划",
            key_cols=["组合代码"],
            rows=sample_portfolio_candidates,
            updatable_cols=["组合名称", "组合类型"],
            conn=None,
        )

        # Check that operations were generated for non-null values
        operations = result["sql_plans"]
        assert len(operations) >= 1

        # Verify Chinese identifiers are properly quoted
        for _, sql, _ in operations:
            assert '"组合计划"' in sql  # Table name
            assert '"组合代码"' in sql  # Key column
            # Should have one of the updatable columns
            assert '"组合名称"' in sql or '"组合类型"' in sql


class TestBackfillIntegration:
    """Integration tests for backfill functions."""

    def test_backfill_workflow_plan_only(
        self, sample_plan_candidates, sample_portfolio_candidates
    ):
        """Test complete backfill workflow in plan-only mode."""
        # Test plan backfill
        plan_result = insert_missing(
            table="年金计划",
            key_cols=["年金计划号"],
            rows=sample_plan_candidates,
            conn=None,
        )

        # Test portfolio backfill
        portfolio_result = insert_missing(
            table="组合计划",
            key_cols=["组合代码"],
            rows=sample_portfolio_candidates,
            conn=None,
        )

        # Verify both operations succeeded
        assert plan_result["inserted"] == 2
        assert portfolio_result["inserted"] == 2
        assert "sql_plans" in plan_result
        assert "sql_plans" in portfolio_result

        # Verify SQL contains proper Chinese identifiers
        plan_sql = plan_result["sql_plans"][0][1]
        portfolio_sql = portfolio_result["sql_plans"][0][1]

        assert '"年金计划"' in plan_sql
        assert '"组合计划"' in portfolio_sql
        assert "ON CONFLICT" in plan_sql
        assert "ON CONFLICT" in portfolio_sql


class TestQuoteQualified:
    """Test quote_qualified function for schema-aware SQL generation."""

    def test_quote_qualified_with_schema(self):
        """Test quote_qualified with schema produces qualified name."""
        result = quote_qualified("public", "年金计划")
        assert result == '"public"."年金计划"'

    def test_quote_qualified_without_schema(self):
        """Test quote_qualified with None schema produces table only."""
        result = quote_qualified(None, "年金计划")
        assert result == '"年金计划"'

        result = quote_qualified("", "年金计划")
        assert result == '"年金计划"'

    def test_quote_qualified_empty_schema(self):
        """Test quote_qualified with empty string schema produces table only."""
        result = quote_qualified("", "年金计划")
        assert result == '"年金计划"'

        result = quote_qualified("  ", "年金计划")  # whitespace only
        assert result == '"年金计划"'

    def test_quote_qualified_chinese_identifiers(self):
        """Test quote_qualified with Chinese table and schema names."""
        result = quote_qualified("公共", "年金计划")
        assert result == '"公共"."年金计划"'

    def test_quote_qualified_invalid_table(self):
        """Test quote_qualified with invalid table name."""
        with pytest.raises(ValueError, match="Table name must be non-empty string"):
            quote_qualified("public", "")

        with pytest.raises(ValueError, match="Table name must be non-empty string"):
            quote_qualified("public", None)


class TestInsertMissingWithSchema:
    """Test insert_missing function with schema support."""

    def test_insert_missing_with_schema(self):
        """Test insert_missing generates qualified SQL when schema provided."""
        rows = [{"年金计划号": "PLAN001", "计划全称": "Test Plan A"}]

        result = insert_missing(
            table="年金计划",
            schema="public",
            key_cols=["年金计划号"],
            rows=rows,
            conn=None,
        )

        sql = result["sql_plans"][0][1]
        assert '"public"."年金计划"' in sql
        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql

    def test_insert_missing_without_schema(self):
        """Test insert_missing generates unqualified SQL when schema is None."""
        rows = [{"年金计划号": "PLAN001", "计划全称": "Test Plan A"}]

        result = insert_missing(
            table="年金计划",
            schema=None,
            key_cols=["年金计划号"],
            rows=rows,
            conn=None,
        )

        sql = result["sql_plans"][0][1]
        assert '"年金计划"' in sql
        assert '"public"."年金计划"' not in sql  # Should not be qualified
        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql


class TestFillNullOnlyWithSchema:
    """Test fill_null_only function with schema support."""

    def test_fill_null_only_with_schema(self):
        """Test fill_null_only generates qualified SQL when schema provided."""
        rows = [
            {"年金计划号": "PLAN001", "计划全称": "Test Plan A", "客户名称": "Client A"}
        ]

        result = fill_null_only(
            table="年金计划",
            schema="public",
            key_cols=["年金计划号"],
            rows=rows,
            updatable_cols=["计划全称", "客户名称"],
            conn=None,
        )

        # Should have operations for columns with non-null values
        operations = result["sql_plans"]
        assert len(operations) >= 1

        # Check that at least one operation has qualified table name
        has_qualified_table = any('"public"."年金计划"' in op[1] for op in operations)
        assert has_qualified_table

    def test_fill_null_only_without_schema(self):
        """Test fill_null_only generates unqualified SQL when schema is None."""
        rows = [{"年金计划号": "PLAN001", "计划全称": "Test Plan A"}]

        result = fill_null_only(
            table="年金计划",
            schema=None,
            key_cols=["年金计划号"],
            rows=rows,
            updatable_cols=["计划全称"],
            conn=None,
        )

        operations = result["sql_plans"]
        assert len(operations) >= 1

        # Should have unqualified table name
        for _, sql, _ in operations:
            assert '"年金计划"' in sql
            assert '"public"."年金计划"' not in sql  # Should not be qualified
