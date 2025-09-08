"""
Tests for warehouse loader.

This module tests the DataWarehouseLoader SQL builders and orchestration
with both unit tests (no database required) and integration tests.
"""

import pytest

from src.work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    build_delete_sql,
    build_insert_sql,
    load,
    quote_ident,
)


@pytest.fixture
def sample_rows():
    """Sample data for testing."""
    return [
        {"report_date": "2024-01-01", "plan_code": "P001", "company_code": "C001", "return_rate": 0.05},
        {"report_date": "2024-01-01", "plan_code": "P002", "company_code": "C001", "return_rate": 0.03},
        {"report_date": "2024-02-01", "plan_code": "P001", "company_code": "C002", "return_rate": 0.07},
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
        result = load(
            table="test_table",
            rows=sample_rows,
            mode="append",
            conn=None
        )
        
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
            conn=None
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
            table="test_table",
            rows=rows,
            mode="append",
            chunk_size=1000,
            conn=None
        )
        
        assert result["inserted"] == 2500
        assert result["batches"] == 3  # ceil(2500/1000)
        
        # Should have 3 INSERT operations
        operations = result["sql_plans"]
        insert_ops = [op for op in operations if op[0] == "INSERT"]
        assert len(insert_ops) == 3
    
    def test_load_empty_rows(self):
        """Test graceful handling of empty input."""
        result = load(
            table="test_table",
            rows=[],
            mode="append",
            conn=None
        )
        
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
            db="testdb"
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
            uri="postgresql://user:pass@host:5432/db"
        )
        
        assert db_settings.get_connection_string() == "postgresql://user:pass@host:5432/db"


# Integration tests (skipped by default)
@pytest.mark.postgres
class TestDatabaseIntegration:
    """Integration tests requiring actual PostgreSQL database."""
    
    @pytest.fixture
    def db_connection(self):
        """Create test database connection.

        Preference order:
        1) WDH_TEST_DATABASE_URI (explicit test DSN)
        2) Settings-derived DSN from .env (development default)
        """
        import os

        # Prefer explicit test DSN if provided
        conn_str = os.getenv("WDH_TEST_DATABASE_URI")
        if not conn_str:
            # Fallback: use application settings (loads .env)
            try:
                from src.work_data_hub.config.settings import get_settings
                settings = get_settings()
                conn_str = settings.get_database_connection_string()
            except Exception:
                pytest.skip("Test database not configured")

        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 not available")

        # Keep a modest timeout to fail fast on misconfiguration
        conn = psycopg2.connect(conn_str, connect_timeout=5)
        
        # Setup test table
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE test_trustee_performance (
                    report_date DATE,
                    plan_code VARCHAR(50),
                    company_code VARCHAR(20),
                    return_rate NUMERIC(8,6),
                    PRIMARY KEY (report_date, plan_code, company_code)
                )
            """)
        
        yield conn
        conn.close()
    
    def test_load_delete_insert_integration(self, db_connection, sample_rows):
        """Test actual database delete-insert operation."""
        pk = ["report_date", "plan_code", "company_code"]
        
        result = load(
            table="test_trustee_performance",
            rows=sample_rows,
            mode="delete_insert", 
            pk=pk,
            conn=db_connection
        )
        
        assert result["inserted"] == 3
        
        # Verify data was inserted
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_trustee_performance")
            count = cursor.fetchone()[0]
            assert count == 3
    
    def test_load_append_integration(self, db_connection):
        """Test actual database append operation."""
        rows = [{"report_date": "2024-12-01", "plan_code": "TEST", "company_code": "TEST", "return_rate": 0.01}]
        
        result = load(
            table="test_trustee_performance",
            rows=rows,
            mode="append",
            conn=db_connection
        )
        
        assert result["inserted"] == 1
        assert result["deleted"] == 0

class TestJSONBParameterAdaptation:
    """Test JSONB parameter adaptation for execute_values."""
    
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
    
    def test_load_adapts_jsonb_parameters_in_sql_plan(self):
        """Test that load function properly adapts JSONB parameters in plan mode."""
        rows = [{
            "report_date": "2024-01-01",
            "plan_code": "P001",
            "company_code": "C001",
            "validation_warnings": ["warning1", "warning2"],  # List that needs JSONB adaptation
            "metadata": {"source": "test", "processed": True}   # Dict that needs JSONB adaptation
        }]
        
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
    
    def test_adapt_param_handles_nested_structures(self):
        """Test adaptation of complex nested dict/list structures."""
        from psycopg2.extras import Json
        from src.work_data_hub.io.loader.warehouse_loader import _adapt_param
        
        complex_dict = {
            "nested": {"key": "value"},
            "array": [1, 2, 3],
            "mixed": ["string", {"inner": "dict"}]
        }
        
        adapted = _adapt_param(complex_dict)
        assert isinstance(adapted, Json)
        
        # Verify the wrapped data is preserved
        assert adapted.adapted == complex_dict
