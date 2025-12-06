"""
Tests for warehouse loader.

This module tests the DataWarehouseLoader SQL builders and orchestration
with both unit tests (no database required) and integration tests.
"""

import time
import uuid
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest


from src.work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    LoadResult,
    WarehouseLoader,
    build_delete_sql,
    build_insert_sql,
    load,
    quote_ident,
)


def _build_fake_connection():
    """Create a fake psycopg2 connection with context-aware cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    conn.cursor.return_value = cursor
    return conn, cursor


def _create_loader(monkeypatch, operational_error=Exception):
    """Instantiate WarehouseLoader with patched psycopg2 pool for unit tests."""
    pool_instance = MagicMock()
    health_conn, health_cursor = _build_fake_connection()
    pool_instance.getconn.return_value = health_conn
    pool_instance.putconn.return_value = None
    pool_cls = MagicMock(return_value=pool_instance)
    monkeypatch.setattr(
        "src.work_data_hub.io.loader.warehouse_loader.ThreadedConnectionPool",
        pool_cls,
    )
    monkeypatch.setattr(
        "src.work_data_hub.io.loader.warehouse_loader.OperationalError",
        operational_error,
    )
    loader = WarehouseLoader(connection_url="postgresql://user:pass@test/db")
    return loader, pool_instance, health_conn, health_cursor


@pytest.fixture
def sample_rows():
    """Sample data for testing."""
    return [
        {
            "report_date": "2024-01-01",
            "plan_code": "P001",
            "company_code": "C001",
            "return_rate": 0.05,
        },
        {
            "report_date": "2024-01-01",
            "plan_code": "P002",
            "company_code": "C001",
            "return_rate": 0.03,
        },
        {
            "report_date": "2024-02-01",
            "plan_code": "P001",
            "company_code": "C002",
            "return_rate": 0.07,
        },
    ]


class TestSQLBuilders:
    """Test SQL building functions."""

    def test_quote_ident_basic(self):
        """Test basic identifier quoting."""
        assert quote_ident("table_name") == '"table_name"'
        assert quote_ident("Column Name") == '"Column Name"'

    def test_quote_ident_escapes_quotes(self):
        """Test that internal quotes are escaped."""
        assert quote_ident('table"name') == '"table""name"'

    def test_quote_ident_validates_input(self):
        """Test input validation."""
        with pytest.raises(ValueError, match="non-empty string"):
            quote_ident("")

        with pytest.raises(ValueError, match="too long"):
            quote_ident("x" * 64)

    def test_build_insert_sql_basic(self, sample_rows):
        """Test basic INSERT SQL generation."""
        cols = ["report_date", "plan_code", "return_rate"]
        sql, params = build_insert_sql("trustee_performance", cols, sample_rows[:1])

        expected_sql = 'INSERT INTO "trustee_performance" ("report_date","plan_code","return_rate") VALUES (%s,%s,%s)'
        assert sql == expected_sql
        assert params == ["2024-01-01", "P001", 0.05]

    def test_build_insert_sql_multiple_rows(self, sample_rows):
        """Test multi-row INSERT with proper parameter flattening."""
        cols = ["plan_code", "return_rate"]
        sql, params = build_insert_sql("test_table", cols, sample_rows[:2])

        # Should have one VALUES clause per row
        assert sql.count("VALUES") == 1
        assert sql.count("(%s,%s)") == 1  # Template for execute_values

        # Parameters should be flattened row-major
        expected_params = ["P001", 0.05, "P002", 0.03]
        assert params == expected_params

    def test_build_insert_sql_empty_rows(self):
        """Test handling of empty row list."""
        cols = ["id", "name"]
        sql, params = build_insert_sql("test_table", cols, [])

        assert sql is None
        assert params == []

    def test_build_insert_sql_missing_columns(self, sample_rows):
        """Test handling of missing columns in rows."""
        cols = ["report_date", "plan_code", "missing_col"]
        sql, params = build_insert_sql("test_table", cols, sample_rows[:1])

        # Should include None for missing columns
        expected_params = ["2024-01-01", "P001", None]
        assert params == expected_params

    def test_build_insert_sql_validation_errors(self):
        """Test validation error handling."""
        rows = [{"id": 1}]

        # Empty table name
        with pytest.raises(ValueError, match="Table name is required"):
            build_insert_sql("", ["id"], rows)

        # Empty column list
        with pytest.raises(ValueError, match="Column list cannot be empty"):
            build_insert_sql("test", [], rows)

    def test_build_delete_sql_composite_key(self, sample_rows):
        """Test DELETE with composite primary key."""
        pk_cols = ["report_date", "plan_code", "company_code"]
        sql, params = build_delete_sql("trustee_performance", pk_cols, sample_rows)

        expected_sql = 'DELETE FROM "trustee_performance" WHERE ("report_date","plan_code","company_code") IN ((%s,%s,%s),(%s,%s,%s),(%s,%s,%s))'
        assert sql == expected_sql

        # Should have flattened PK values
        assert len(params) == 9  # 3 rows × 3 PK columns
        assert params[0:3] == ["2024-01-01", "P001", "C001"]

    def test_build_delete_sql_single_key(self):
        """Test DELETE with single primary key."""
        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        sql, params = build_delete_sql("test_table", ["id"], rows)

        expected_sql = 'DELETE FROM "test_table" WHERE ("id") IN ((%s),(%s),(%s))'
        assert sql == expected_sql
        assert params == [1, 2, 3]

    def test_build_delete_sql_deduplicates(self):
        """Test that duplicate PK combinations are deduplicated."""
        rows = [
            {"id": 1, "type": "A"},
            {"id": 1, "type": "A"},  # Duplicate
            {"id": 2, "type": "B"},
        ]

        sql, params = build_delete_sql("test", ["id", "type"], rows)

        # Should only have 2 unique tuples
        assert sql.count("(%s,%s)") == 2
        assert len(params) == 4  # 2 unique tuples × 2 columns

    def test_build_delete_sql_empty_rows(self):
        """Test handling of empty row list."""
        sql, params = build_delete_sql("test_table", ["id"], [])

        assert sql is None
        assert params == []

    def test_build_delete_sql_missing_pk_values(self):
        """Test error when PK values are missing."""
        rows = [{"id": 1}, {"id": 2, "type": None}]  # Missing 'type' values

        with pytest.raises(ValueError, match="Missing primary key values"):
            build_delete_sql("test", ["id", "type"], rows)

    def test_build_delete_sql_validation_errors(self):
        """Test validation error handling."""
        rows = [{"id": 1}]

        # Empty table name
        with pytest.raises(ValueError, match="Table name is required"):
            build_delete_sql("", ["id"], rows)

        # Empty PK columns
        with pytest.raises(ValueError, match="Primary key columns are required"):
            build_delete_sql("test", [], rows)


class TestLoaderOrchestration:
    """Test the main load function."""

    def test_load_append_mode_no_connection(self, sample_rows):
        """Test append mode returns SQL plan when no connection."""
        result = load(table="test_table", rows=sample_rows, mode="append", conn=None)

        assert result["mode"] == "append"
        assert result["table"] == "test_table"
        assert result["deleted"] == 0
        assert result["inserted"] == 3
        assert result["batches"] == 1
        assert "sql_plans" in result

        # Should only have INSERT operations
        operations = result["sql_plans"]
        assert len(operations) == 1
        assert operations[0][0] == "INSERT"

    def test_load_delete_insert_mode_no_connection(self, sample_rows):
        """Test delete_insert mode returns complete plan."""
        pk = ["report_date", "plan_code", "company_code"]
        result = load(
            table="trustee_performance",
            rows=sample_rows,
            mode="delete_insert",
            pk=pk,
            conn=None,
        )

        assert result["mode"] == "delete_insert"
        assert result["deleted"] == 3  # Unique PK combinations
        assert result["inserted"] == 3
        assert result["batches"] == 1

        # Should have DELETE then INSERT
        operations = result["sql_plans"]
        assert len(operations) == 2
        assert operations[0][0] == "DELETE"
        assert operations[1][0] == "INSERT"

    def test_load_chunking(self):
        """Test that large datasets are properly chunked."""
        # Create 2500 rows to test chunking
        rows = [{"id": i, "value": f"val_{i}"} for i in range(2500)]

        result = load(
            table="test_table", rows=rows, mode="append", chunk_size=1000, conn=None
        )

        assert result["inserted"] == 2500
        assert result["batches"] == 3  # ceil(2500/1000)

        # Should have 3 INSERT operations
        operations = result["sql_plans"]
        insert_ops = [op for op in operations if op[0] == "INSERT"]
        assert len(insert_ops) == 3

    def test_load_empty_rows(self):
        """Test graceful handling of empty input."""
        result = load(table="test_table", rows=[], mode="append", conn=None)

        assert result["deleted"] == 0
        assert result["inserted"] == 0
        assert result["batches"] == 0

    def test_load_validation_errors(self):
        """Test validation error handling."""
        rows = [{"id": 1}]

        # Invalid mode
        with pytest.raises(DataWarehouseLoaderError, match="Invalid mode"):
            load("test", rows, mode="invalid")

        # Missing PK for delete_insert
        with pytest.raises(DataWarehouseLoaderError, match="Primary key required"):
            load("test", rows, mode="delete_insert")

    def test_load_invalid_rows(self):
        """Test error handling for invalid row data."""
        # Non-list input
        with pytest.raises(ValueError, match="Rows must be a list"):
            load("test", "not_a_list", mode="append", conn=None)

        # Non-dict row
        with pytest.raises(ValueError, match="Row 0 must be a dictionary"):
            load("test", ["not_a_dict"], mode="append", conn=None)


class TestWarehouseLoaderClass:
    """Unit tests for the WarehouseLoader dataclass-driven implementation."""

    def test_project_columns_warns_when_many_removed(self, monkeypatch):
        """Ensure projection logs warning when >5 columns are removed."""
        loader, _, _, _ = _create_loader(monkeypatch)
        loader.get_allowed_columns = MagicMock(return_value=["col_a", "col_b"])
        loader._logger = MagicMock()

        df = pd.DataFrame(
            {
                "col_a": [1],
                "col_b": [2],
                "extra1": [3],
                "extra2": [4],
                "extra3": [5],
                "extra4": [6],
                "extra5": [7],
                "extra6": [8],
            }
        )

        projected = loader.project_columns(df, table="test_table")
        assert list(projected.columns) == ["col_a", "col_b"]
        loader._logger.warning.assert_called_once()

    def test_get_allowed_columns_cached(self, monkeypatch):
        """get_allowed_columns should cache schema introspection results."""
        loader, _, _, _ = _create_loader(monkeypatch)
        conn, cursor = _build_fake_connection()
        cursor.fetchall.return_value = [("plan_code",), ("return_rate",)]
        loader._get_connection_with_retry = MagicMock(return_value=conn)
        loader._pool.putconn = MagicMock()

        first = loader.get_allowed_columns("trustee_performance")
        second = loader.get_allowed_columns("trustee_performance")

        assert first == ["plan_code", "return_rate"]
        assert second == first
        cursor.execute.assert_called_once()
        loader._get_connection_with_retry.assert_called_once()
        loader._pool.putconn.assert_called_once_with(conn)

    def test_load_dataframe_executes_batches(self, monkeypatch):
        """load_dataframe should batch inserts and report row counts."""
        loader, _, _, _ = _create_loader(monkeypatch)
        df = pd.DataFrame(
            [
                {"plan_code": "A", "return_rate": 0.01},
                {"plan_code": "B", "return_rate": 0.02},
                {"plan_code": "C", "return_rate": 0.03},
            ]
        )
        loader.project_columns = MagicMock(return_value=df)
        loader.batch_size = 2
        loader._pool.putconn = MagicMock()

        conn, cursor = _build_fake_connection()
        cursor.fetchall.side_effect = [[(True,), (False,)], [(True,)]]
        loader._get_connection_with_retry = MagicMock(return_value=conn)

        mocked_execute_values = MagicMock()
        monkeypatch.setattr(
            "src.work_data_hub.io.loader.warehouse_loader.execute_values",
            mocked_execute_values,
        )

        result = loader.load_dataframe(
            df, table="trustee_performance", upsert_keys=["plan_code"]
        )

        assert isinstance(result, LoadResult)
        assert result.rows_inserted == 2
        assert result.rows_updated == 1
        assert mocked_execute_values.call_count == 2
        assert conn.commit.called
        loader.project_columns.assert_called_once()
        loader._pool.putconn.assert_called_once_with(conn)

    def test_connection_retry_on_operational_error(self, monkeypatch):
        """_get_connection_with_retry should handle transient OperationalErrors."""

        class FakeOperationalError(Exception):
            """Sentinel error type for retry verification."""

        loader, pool, _, _ = _create_loader(
            monkeypatch, operational_error=FakeOperationalError
        )
        conn, _ = _build_fake_connection()
        initial_calls = pool.getconn.call_count
        pool.getconn.side_effect = [FakeOperationalError("boom"), conn]

        acquired = loader._get_connection_with_retry()
        assert acquired is conn
        assert pool.getconn.call_count == initial_calls + 2

    def test_chunk_dataframe_meets_performance_target(self, monkeypatch):
        """Chunking more than 1000 rows should stay under 500ms."""
        loader, _, _, _ = _create_loader(monkeypatch)
        rows = [{"value": i} for i in range(1200)]
        df = pd.DataFrame(rows)
        start = time.perf_counter()
        chunks = list(loader._chunk_dataframe(df))
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 500, f"Chunking took too long: {duration_ms:.2f} ms"
        assert sum(len(chunk) for chunk in chunks) == len(df)


class TestDatabaseSettings:
    """Test database configuration."""

    def test_connection_string_from_parts(self):
        """Test connection string generation."""
        from src.work_data_hub.config.settings import DatabaseSettings

        db_settings = DatabaseSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password="testpass",
            db="testdb",
        )

        expected = "postgresql://testuser:testpass@localhost:5432/testdb"
        assert db_settings.get_connection_string() == expected

    def test_connection_string_from_uri(self):
        """Test URI override."""
        from src.work_data_hub.config.settings import DatabaseSettings

        db_settings = DatabaseSettings(
            host="ignored",
            user="ignored",
            password="ignored",
            db="ignored",
            uri="postgresql://user:pass@host:5432/db",
        )

        assert (
            db_settings.get_connection_string() == "postgresql://user:pass@host:5432/db"
        )


# Integration tests (skipped by default)
@pytest.mark.integration
@pytest.mark.postgres
class TestDatabaseIntegration:
    """Integration tests requiring actual PostgreSQL database."""

    @pytest.fixture
    def db_connection(self, postgres_connection):
        """Create test database connection and seed temp table."""
        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMP TABLE test_trustee_performance (
                    report_date DATE,
                    plan_code VARCHAR(50),
                    company_code VARCHAR(20),
                    return_rate NUMERIC(8,6),
                    PRIMARY KEY (report_date, plan_code, company_code)
                )
                """
            )

        yield postgres_connection

    def test_load_delete_insert_integration(self, db_connection, sample_rows):
        """Test actual database delete-insert operation."""
        pk = ["report_date", "plan_code", "company_code"]

        result = load(
            table="test_trustee_performance",
            rows=sample_rows,
            mode="delete_insert",
            pk=pk,
            conn=db_connection,
        )

        assert result["inserted"] == 3

        # Verify data was inserted
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_trustee_performance")
            count = cursor.fetchone()[0]
            assert count == 3

    def test_load_append_integration(self, db_connection):
        """Test actual database append operation."""
        rows = [
            {
                "report_date": "2024-12-01",
                "plan_code": "TEST",
                "company_code": "TEST",
                "return_rate": 0.01,
            }
        ]

        result = load(
            table="test_trustee_performance",
            rows=rows,
            mode="append",
            conn=db_connection,
        )

        assert result["inserted"] == 1
        assert result["deleted"] == 0


def _reset_test_table(dsn: str, table_name: str) -> None:
    """Create a deterministic test table for WarehouseLoader integration tests."""
    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2 import sql

    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name))
            )
            cursor.execute(
                sql.SQL(
                    """
                    CREATE TABLE {} (
                        plan_code TEXT PRIMARY KEY,
                        report_date DATE NOT NULL,
                        return_rate NUMERIC(8,6) NOT NULL,
                        note TEXT
                    )
                    """
                ).format(sql.Identifier(table_name))
            )


@pytest.mark.integration
@pytest.mark.postgres
class TestWarehouseLoaderIntegration:
    """Integration tests for the WarehouseLoader class."""

    def test_dataframe_loads_successfully(self, postgres_db_with_migrations: str):
        """End-to-end verification of load_dataframe success path."""
        dsn = postgres_db_with_migrations
        table_name = f"warehouse_loader_story18_{uuid.uuid4().hex[:6]}"
        _reset_test_table(dsn, table_name)

        loader = WarehouseLoader(connection_url=dsn, pool_size=2, batch_size=2)
        df = pd.DataFrame(
            [
                {
                    "plan_code": "A101",
                    "report_date": "2024-01-01",
                    "return_rate": 0.01,
                    "extra": "x",
                },
                {
                    "plan_code": "A102",
                    "report_date": "2024-01-02",
                    "return_rate": 0.02,
                    "extra": "y",
                },
            ]
        )

        result = loader.load_dataframe(
            df, table=table_name, schema="public", upsert_keys=["plan_code"]
        )
        assert result.success is True
        assert result.rows_inserted == 2
        assert result.rows_updated == 0

        psycopg2 = pytest.importorskip("psycopg2")
        from psycopg2 import sql

        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table_name)
                    )
                )
                assert cursor.fetchone()[0] == 2

        loader.close()

    def test_dataframe_load_rolls_back_on_error(self, postgres_db_with_migrations: str):
        """Ensure transactional rollback occurs when batch fails."""
        dsn = postgres_db_with_migrations
        table_name = f"warehouse_loader_story18_{uuid.uuid4().hex[:6]}"
        _reset_test_table(dsn, table_name)

        loader = WarehouseLoader(connection_url=dsn, pool_size=2, batch_size=2)
        df = pd.DataFrame(
            [
                {"plan_code": "B201", "report_date": "2024-02-01", "return_rate": 0.01},
                {
                    "plan_code": "B202",
                    "report_date": "2024-02-01",
                    "return_rate": "invalid",
                },
            ]
        )

        with pytest.raises(DataWarehouseLoaderError):
            loader.load_dataframe(df, table=table_name, schema="public")

        psycopg2 = pytest.importorskip("psycopg2")
        from psycopg2 import sql

        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table_name)
                    )
                )
                assert cursor.fetchone()[0] == 0

        loader.close()


class TestJSONBParameterAdaptation:
    """Enhanced JSONB parameter adaptation testing according to PRP P-013."""

    def test_adapt_param_wraps_dict_and_list(self):
        """Test parameter adaptation for JSONB types."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        dict_param = {"key": "value"}
        list_param = ["item1", "item2"]
        scalar_param = "scalar"
        none_param = None

        assert isinstance(_adapt_param(dict_param), Json)
        assert isinstance(_adapt_param(list_param), Json)
        assert _adapt_param(scalar_param) == "scalar"
        assert _adapt_param(none_param) is None

    def test_adapt_param_handles_nested_structures(self):
        """Test adaptation of complex nested dict/list structures."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        complex_dict = {
            "nested": {"key": "value"},
            "array": [1, 2, 3],
            "mixed": ["string", {"inner": "dict"}],
        }

        adapted = _adapt_param(complex_dict)
        assert isinstance(adapted, Json)

        # Verify the wrapped data is preserved
        assert adapted.adapted == complex_dict

    def test_adapt_param_handles_deeply_nested_structures(self):
        """Test adaptation of deeply nested dict/list structures from PRP requirements."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        # Test deeply nested structure similar to real validation_warnings
        complex_nested = {
            "validation_warnings": [
                "High return rate detected: 15.5%",
                "Fund scale inconsistency with NAV",
                {
                    "warning_type": "data_quality",
                    "details": {
                        "field": "return_rate",
                        "value": 0.155,
                        "threshold": 0.10,
                        "metadata": {
                            "source_row": 42,
                            "processing_timestamp": "2024-01-01T12:00:00Z",
                            "validation_rules": ["range_check", "outlier_detection"],
                        },
                    },
                },
            ],
            "metadata": {
                "processing_context": {
                    "data_source": "/path/to/trustee_performance_2024_11.xlsx",
                    "batch_id": "batch_20241101_001",
                    "processor_version": "2.1.0",
                },
                "data_lineage": [
                    {"step": "extraction", "timestamp": "2024-01-01T11:00:00Z"},
                    {"step": "validation", "timestamp": "2024-01-01T11:30:00Z"},
                    {"step": "transformation", "timestamp": "2024-01-01T12:00:00Z"},
                ],
            },
        }

        adapted = _adapt_param(complex_nested)
        assert isinstance(adapted, Json)
        assert adapted.adapted == complex_nested

    def test_adapt_param_preserves_json_types(self):
        """Test that JSON types are correctly preserved in adaptation."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        # Test various JSON-compatible types
        test_cases = [
            {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
            },
            [1, "two", 3.0, True, None, {"nested": "object"}],
            {
                "empty_dict": {},
                "empty_list": [],
                "nested": {"deep": {"deeper": "value"}},
            },
        ]

        for case in test_cases:
            adapted = _adapt_param(case)
            assert isinstance(adapted, Json)
            assert adapted.adapted == case

    def test_load_adapts_jsonb_parameters_in_sql_plan(self):
        """Test that load function properly adapts JSONB parameters in plan mode."""
        rows = [
            {
                "report_date": "2024-01-01",
                "plan_code": "P001",
                "company_code": "C001",
                "validation_warnings": [
                    "warning1",
                    "warning2",
                ],  # List that needs JSONB adaptation
                "metadata": {
                    "source": "test",
                    "processed": True,
                },  # Dict that needs JSONB adaptation
            }
        ]

        result = load("trustee_performance", rows, mode="append", conn=None)

        # Verify sql_plans are generated
        assert "sql_plans" in result
        operations = result["sql_plans"]
        assert len(operations) == 1
        assert operations[0][0] == "INSERT"

        # The actual adaptation happens during execution, not in plan mode
        # But we can verify the function is available and the structure is correct
        sql, params = operations[0][1], operations[0][2]
        assert "INSERT INTO" in sql
        assert len(params) == 5  # Should have all row values flattened

    def test_load_with_execute_values_jsonb_adaptation(self):
        """Test JSONB parameter adaptation in execute_values context (mocked)."""
        rows = [
            {
                "id": 1,
                "validation_warnings": [
                    "warning1",
                    {"type": "error", "msg": "Invalid data"},
                ],
                "metadata": {"source": "file1.xlsx", "processed": True},
            },
            {
                "id": 2,
                "validation_warnings": ["warning2"],
                "metadata": {
                    "source": "file2.xlsx",
                    "processed": False,
                    "errors": [{"code": 500}],
                },
            },
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None

        # Mock execute_values to capture the adapted parameters
        with patch("psycopg2.extras.execute_values") as mock_execute_values:
            result = load(table="test_table", rows=rows, mode="append", conn=mock_conn)

            # Verify execute_values was called
            mock_execute_values.assert_called_once()

            # Get the call arguments to verify JSONB adaptation
            call_args = mock_execute_values.call_args
            cursor, sql, adapted_rows = call_args[0][:3]

            assert cursor == mock_cursor
            assert "INSERT INTO" in sql
            assert len(adapted_rows) == 2

            # Verify that dict/list parameters were adapted with psycopg2.extras.Json
            from psycopg2.extras import Json

            start = sql.index("(") + 1
            end = sql.index(")")
            columns = [col.strip().strip('"') for col in sql[start:end].split(",")]

            assert "validation_warnings" in columns
            assert "metadata" in columns

            for idx, row_values in enumerate(adapted_rows):
                row_map = dict(zip(columns, row_values))
                assert isinstance(row_map["validation_warnings"], Json)
                assert isinstance(row_map["metadata"], Json)
                assert (
                    row_map["validation_warnings"].adapted
                    == rows[idx]["validation_warnings"]
                )
                assert row_map["metadata"].adapted == rows[idx]["metadata"]

    def test_execute_values_parameter_structure_with_jsonb(self):
        """Test that execute_values receives properly structured JSONB parameters."""
        # Test specific to execute_values parameter format requirements
        rows = [
            {
                "report_date": "2024-01-01",
                "plan_code": "PLAN001",
                "company_code": "COMP001",
                "return_rate": 0.055,
                "validation_warnings": ["Rate exceeds threshold"],
                "metadata": {
                    "file_source": "2024_11_trustee_performance.xlsx",
                    "processing_info": {"batch_size": 1000, "warnings_count": 1},
                },
            }
        ]

        # Mock the database components
        mock_conn = MagicMock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None

        with patch("psycopg2.extras.execute_values") as mock_execute_values:
            load(table="trustee_performance", rows=rows, mode="append", conn=mock_conn)

            # Verify execute_values call structure
            mock_execute_values.assert_called_once()
            call_args = mock_execute_values.call_args

            cursor, sql, row_data, page_size = (
                call_args[0][0],
                call_args[0][1],
                call_args[0][2],
                call_args[1]["page_size"],
            )

            # Verify SQL structure
            assert 'INSERT INTO "trustee_performance"' in sql
            assert "VALUES %s" in sql

            # Verify row_data structure for execute_values
            assert len(row_data) == 1

            # Verify JSONB parameters are Json-wrapped
            from psycopg2.extras import Json

            start = sql.index("(") + 1
            end = sql.index(")")
            columns = [col.strip().strip('"') for col in sql[start:end].split(",")]

            row_params = dict(zip(columns, row_data[0]))
            validation_warnings_param = row_params["validation_warnings"]
            metadata_param = row_params["metadata"]

            assert validation_warnings_param.adapted == ["Rate exceeds threshold"]
            assert (
                metadata_param.adapted["file_source"]
                == "2024_11_trustee_performance.xlsx"
            )

            # Verify page_size parameter
            assert page_size == 1000  # min(chunk_size=1000, 1000)

    def test_load_chunks_large_jsonb_datasets_properly(self):
        """Test that large datasets with JSONB columns are chunked correctly."""
        # Create dataset larger than chunk_size to test chunking with JSONB
        large_dataset = []
        for i in range(2500):  # Larger than default chunk_size=1000
            large_dataset.append(
                {
                    "id": i,
                    "data": f"row_{i}",
                    "jsonb_field": {
                        "index": i,
                        "metadata": {
                            "created": f"2024-01-{(i % 28) + 1:02d}",
                            "tags": [f"tag_{j}" for j in range(i % 3 + 1)],
                        },
                    },
                }
            )

        # Plan-only mode to test chunking logic
        result = load(
            table="test_table",
            rows=large_dataset,
            mode="append",
            chunk_size=1000,
            conn=None,
        )

        # Verify chunking worked correctly
        assert result["inserted"] == 2500
        assert result["batches"] == 3  # ceil(2500/1000)

        # Verify operations structure
        operations = result["sql_plans"]
        insert_ops = [op for op in operations if op[0] == "INSERT"]
        assert len(insert_ops) == 3  # Should have 3 INSERT operations for chunks

    def test_jsonb_adaptation_with_unicode_and_special_chars(self):
        """Test JSONB adaptation handles Unicode and special characters correctly."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        unicode_data = {
            "chinese_text": "测试数据",
            "emoji": "🚀📊💰",
            "special_chars": 'Quote: "Test", Backslash: \\, Newline: \n, Tab: \t',
            "unicode_escape": "\u4e2d\u6587",
            "mixed_array": ["English", "中文", "🎯", {"nested": "测试"}],
        }

        adapted = _adapt_param(unicode_data)
        assert isinstance(adapted, Json)
        assert adapted.adapted == unicode_data

        # Verify that special characters are preserved
        assert adapted.adapted["chinese_text"] == "测试数据"
        assert adapted.adapted["emoji"] == "🚀📊💰"
        assert "\n" in adapted.adapted["special_chars"]
        assert adapted.adapted["mixed_array"][1] == "中文"

    def test_jsonb_null_and_empty_value_handling(self):
        """Test JSONB adaptation handles null and empty values appropriately."""
        from psycopg2.extras import Json

        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param

        test_cases = [
            ({}, Json),  # Empty dict should be wrapped
            ([], Json),  # Empty list should be wrapped
            (None, type(None)),  # None should remain None
            ({"key": None}, Json),  # Dict with None value should be wrapped
            ([None, None], Json),  # List with None values should be wrapped
            (
                {"empty_list": [], "empty_dict": {}},
                Json,
            ),  # Nested empties should be wrapped
        ]

        for input_val, expected_type in test_cases:
            result = _adapt_param(input_val)
            if expected_type == Json:
                assert isinstance(result, Json)
                assert result.adapted == input_val
            else:
                assert result is None
