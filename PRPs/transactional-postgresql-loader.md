# PRP: Transactional PostgreSQL Loader with SQL Builder

## Summary

Implement a `DataWarehouseLoader` component that provides testable SQL building capabilities for PostgreSQL bulk operations with transactional safety. The loader supports both delete-then-insert (upsert) and append modes, with comprehensive parameter validation, identifier quoting, and chunking for large datasets. The implementation prioritizes testability by exposing pure SQL builders that can be unit tested without a database connection.

## Context & Architecture Analysis

### Current Codebase Patterns
This implementation extends the existing WorkDataHub architecture, following established patterns from:

- **`src/work_data_hub/config/settings.py`**: Pydantic v2 BaseSettings with environment variable support
- **`src/work_data_hub/io/connectors/file_connector.py`**: Error handling, logging, and configuration patterns
- **`tests/io/test_file_connector.py`**: Comprehensive testing with fixtures, mocking, and parametrized tests
- **`src/work_data_hub/domain/trustee_performance/models.py`**: Pydantic v2 data validation and field cleaning

### Technology Stack Alignment
- **UV**: Package management (as per CLAUDE.md)
- **Pydantic v2**: Configuration and data validation
- **psycopg2-binary**: PostgreSQL adapter (already in pyproject.toml)
- **pytest**: Testing framework with fixtures and markers

## Requirements Analysis

### Functional Requirements
1. **SQL Builder Functions**:
   - `quote_ident(name: str) -> str`: Safe identifier quoting
   - `build_insert_sql(table, cols, rows) -> tuple[str, list]`: Parameterized INSERT
   - `build_delete_sql(table, pk_cols, rows) -> tuple[str, list]`: Composite key DELETE

2. **Loader Orchestration**:
   - `load(table, rows, mode, pk, chunk_size, conn) -> dict`: Main entry point
   - Support delete_then_insert and append modes
   - Chunking for large datasets (default 1000 rows)
   - Transactional execution when connection provided

3. **Configuration Extension**:
   - Extend Settings with DatabaseSettings class
   - Environment variable support (WDH_DATABASE__*)

### Non-Functional Requirements
- **Testability**: SQL builders work without database
- **Security**: Parameterized queries, no SQL injection
- **Performance**: Bulk operations with execute_values()
- **Reliability**: Transactional consistency
- **Maintainability**: Clear separation of concerns

## Critical Implementation Context

### PostgreSQL & psycopg2 Best Practices

Based on latest 2024 research, the following patterns are essential:

#### 1. Bulk Insert Performance
```python
# Use execute_values() for 6-10x performance improvement
from psycopg2.extras import execute_values
execute_values(
    cursor, 
    "INSERT INTO table (col1, col2) VALUES %s", 
    data_list, 
    page_size=1000
)
```

#### 2. Safe Identifier Handling
```python
from psycopg2 import sql
# NEVER use string concatenation for table/column names
cursor.execute(
    sql.SQL("INSERT INTO {} (col) VALUES (%s)").format(
        sql.Identifier('table_name')
    ),
    (value,)
)
```

#### 3. Composite Key DELETE Pattern
```python
# PostgreSQL supports tuple IN syntax for composite keys
cursor.execute("""
    DELETE FROM "table" 
    WHERE ("pk1", "pk2") IN ((%s,%s), (%s,%s))
""", [val1, val2, val3, val4])  # Flattened parameters
```

#### 4. Decimal Handling
PostgreSQL NUMERIC ↔ Python Decimal conversion is automatic with psycopg2. No manual conversion needed.

### Security Considerations
- **Values**: Always use `%s` parameterization
- **Identifiers**: Use `sql.Identifier()` for table/column names  
- **Never**: String concatenation or interpolation in SQL
- **Validation**: Validate identifier names before quoting

### Testing Patterns
From existing codebase (`tests/io/test_file_connector.py`):
```python
@pytest.fixture
def mock_settings(monkeypatch):
    def mock_get_settings():
        settings = MagicMock()
        settings.database.host = "test_host"
        return settings
    monkeypatch.setattr("src.work_data_hub.config.settings.get_settings", mock_get_settings)

@pytest.mark.postgres  # Skip by default, run with -m postgres
def test_integration_with_real_db():
    # Integration test requiring actual database
    pass
```

## Implementation Blueprint

### Phase 1: SQL Utility Functions (50 lines)

```python
# src/work_data_hub/io/loader/warehouse_loader.py

def quote_ident(name: str) -> str:
    """
    Quote PostgreSQL identifier with double quotes and escape internal quotes.
    
    Args:
        name: Identifier to quote (table, column name)
        
    Returns:
        Properly quoted identifier
        
    Raises:
        ValueError: If name is empty or contains invalid characters
    """
    if not name or not isinstance(name, str):
        raise ValueError("Identifier name must be non-empty string")
    
    # Basic validation - identifiers should be reasonable
    if len(name) > 63:  # PostgreSQL limit
        raise ValueError("Identifier too long (max 63 characters)")
        
    # Escape internal double quotes by doubling them
    escaped = name.replace('"', '""')
    return f'"{escaped}"'

def _ensure_list_of_dicts(rows: list[dict]) -> list[dict]:
    """Validate and normalize row data."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list")
    
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Row {i} must be a dictionary")
            
    return rows

def _get_column_order(rows: list[dict], provided_cols: list[str] = None) -> list[str]:
    """Determine deterministic column ordering."""
    if provided_cols:
        return provided_cols
    
    # Get union of all keys, sorted for deterministic order
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    
    return sorted(all_keys)
```

### Phase 2: SQL Builder Functions (100 lines)

```python
def build_insert_sql(
    table: str, 
    cols: list[str], 
    rows: list[dict]
) -> tuple[str, list]:
    """
    Build parameterized INSERT SQL for bulk operations.
    
    Args:
        table: Target table name
        cols: Column names in desired order
        rows: List of dictionaries with row data
        
    Returns:
        Tuple of (sql_string, flattened_parameters)
        
    Example:
        >>> sql, params = build_insert_sql("users", ["id", "name"], [{"id": 1, "name": "John"}])
        >>> sql
        'INSERT INTO "users" ("id","name") VALUES (%s,%s)'
        >>> params
        [1, "John"]
    """
    if not table:
        raise ValueError("Table name is required")
    if not cols:
        raise ValueError("Column list cannot be empty")
    
    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return None, []
    
    # Quote table and column identifiers
    quoted_table = quote_ident(table)
    quoted_cols = [quote_ident(col) for col in cols]
    
    # Build SQL template
    col_list = ",".join(quoted_cols)
    value_template = "(" + ",".join(["%s"] * len(cols)) + ")"
    
    sql = f"INSERT INTO {quoted_table} ({col_list}) VALUES {value_template}"
    
    # Flatten parameters in row-major order
    params = []
    for row in rows:
        for col in cols:
            params.append(row.get(col))  # None if key missing
    
    return sql, params

def build_delete_sql(
    table: str, 
    pk_cols: list[str], 
    rows: list[dict]
) -> tuple[str, list]:
    """
    Build DELETE SQL using composite key tuple IN pattern.
    
    Args:
        table: Target table name
        pk_cols: Primary key column names
        rows: Rows containing PK values to delete
        
    Returns:
        Tuple of (sql_string, flattened_parameters)
        
    Example:
        >>> sql, params = build_delete_sql("users", ["id", "type"], [{"id": 1, "type": "A"}])
        >>> sql
        'DELETE FROM "users" WHERE ("id","type") IN ((%s,%s))'
        >>> params
        [1, "A"]
    """
    if not table:
        raise ValueError("Table name is required")
    if not pk_cols:
        raise ValueError("Primary key columns are required")
    
    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return None, []
    
    # Validate all rows have PK values
    missing_keys = []
    pk_tuples = []
    
    for i, row in enumerate(rows):
        pk_values = []
        for col in pk_cols:
            if col not in row or row[col] is None:
                missing_keys.append(f"Row {i} missing key {col}")
            else:
                pk_values.append(row[col])
        
        if len(pk_values) == len(pk_cols):
            pk_tuples.append(tuple(pk_values))
    
    if missing_keys:
        raise ValueError("Missing primary key values: " + "; ".join(missing_keys))
    
    # Deduplicate PK tuples
    unique_tuples = list(set(pk_tuples))
    
    # Build SQL
    quoted_table = quote_ident(table)
    quoted_cols = [quote_ident(col) for col in pk_cols]
    col_list = "(" + ",".join(quoted_cols) + ")"
    
    # Create tuple placeholders: ((%s,%s),(%s,%s))
    tuple_template = "(" + ",".join(["%s"] * len(pk_cols)) + ")"
    tuples_list = ",".join([tuple_template] * len(unique_tuples))
    
    sql = f"DELETE FROM {quoted_table} WHERE {col_list} IN ({tuples_list})"
    
    # Flatten parameters
    params = []
    for pk_tuple in unique_tuples:
        params.extend(pk_tuple)
    
    return sql, params
```

### Phase 3: Loader Orchestration (150 lines)

```python
def load(
    table: str,
    rows: list[dict],
    mode: str = "delete_insert",
    pk: list[str] = None,
    chunk_size: int = 1000,
    conn: Any = None
) -> dict:
    """
    Load data into PostgreSQL table with transactional safety.
    
    Args:
        table: Target table name
        rows: List of dictionaries with row data
        mode: "delete_insert" or "append"
        pk: Primary key columns (required for delete_insert)
        chunk_size: Rows per batch for chunking
        conn: psycopg2 connection object (None = return plan only)
        
    Returns:
        Dictionary with execution metadata:
        {
            "mode": str,
            "table": str,
            "deleted": int,
            "inserted": int, 
            "batches": int,
            "sql_plans": list  # If conn is None
        }
        
    Raises:
        DataWarehouseLoaderError: For validation or execution errors
    """
    # Validation
    if mode not in ["delete_insert", "append"]:
        raise DataWarehouseLoaderError(f"Invalid mode: {mode}")
    
    if mode == "delete_insert" and not pk:
        raise DataWarehouseLoaderError("Primary key required for delete_insert mode")
        
    rows = _ensure_list_of_dicts(rows)
    
    # Early return for empty data
    if not rows:
        return {"mode": mode, "table": table, "deleted": 0, "inserted": 0, "batches": 0}
    
    # Determine column order
    cols = _get_column_order(rows)
    
    # Build SQL operations
    operations = []
    total_deleted = 0
    
    if mode == "delete_insert":
        delete_sql, delete_params = build_delete_sql(table, pk, rows)
        if delete_sql:
            operations.append(("DELETE", delete_sql, delete_params))
            # Estimate deletions (may be less due to deduplication)
            total_deleted = len(set(tuple(row.get(col) for col in pk) for row in rows))
    
    # Chunk insertions
    total_inserted = 0
    batches = 0
    
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        insert_sql, insert_params = build_insert_sql(table, cols, chunk)
        
        if insert_sql:
            operations.append(("INSERT", insert_sql, insert_params))
            total_inserted += len(chunk)
            batches += 1
    
    result = {
        "mode": mode,
        "table": table,
        "deleted": total_deleted,
        "inserted": total_inserted,
        "batches": batches
    }
    
    # If no connection, return plan only (for testing)
    if conn is None:
        result["sql_plans"] = operations
        return result
    
    # Execute with database connection
    try:
        with conn:  # Automatic transaction management
            with conn.cursor() as cursor:
                for op_type, sql, params in operations:
                    if op_type == "DELETE":
                        cursor.execute(sql, params)
                        logger.info(f"Deleted {cursor.rowcount} rows from {table}")
                    elif op_type == "INSERT":
                        # Use execute_values for performance
                        from psycopg2.extras import execute_values
                        # Convert flattened params back to rows
                        cols_per_row = len(cols)
                        row_data = [
                            params[i:i + cols_per_row] 
                            for i in range(0, len(params), cols_per_row)
                        ]
                        
                        quoted_table = quote_ident(table)
                        quoted_cols = [quote_ident(col) for col in cols]
                        col_list = ",".join(quoted_cols)
                        
                        execute_values(
                            cursor,
                            f"INSERT INTO {quoted_table} ({col_list}) VALUES %s",
                            row_data,
                            page_size=min(chunk_size, 1000)
                        )
                        logger.info(f"Inserted {len(row_data)} rows into {table}")
                        
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise DataWarehouseLoaderError(f"Load failed: {e}") from e
    
    return result
```

### Phase 4: Configuration Extension (50 lines)

```python
# src/work_data_hub/config/settings.py - Add to existing file

class DatabaseSettings(BaseModel):
    """Database connection configuration."""
    
    model_config = ConfigDict(
        env_prefix="WDH_DATABASE__",
        case_sensitive=False,
    )
    
    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, description="Database port")  
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    db: str = Field(..., description="Database name")
    
    # Optional URI override
    uri: Optional[str] = Field(None, description="Complete database URI")
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        if self.uri:
            return self.uri
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

# Add to existing Settings class:
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Database configuration
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database connection settings"
    )
```

### Phase 5: Comprehensive Testing (200 lines)

```python
# tests/io/test_warehouse_loader.py

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
    
    def test_build_delete_sql_composite_key(self, sample_rows):
        """Test DELETE with composite primary key."""
        pk_cols = ["report_date", "plan_code", "company_code"]
        sql, params = build_delete_sql("trustee_performance", pk_cols, sample_rows)
        
        expected_sql = 'DELETE FROM "trustee_performance" WHERE ("report_date","plan_code","company_code") IN ((%s,%s,%s),(%s,%s,%s),(%s,%s,%s))'
        assert sql == expected_sql
        
        # Should have flattened PK values
        assert len(params) == 9  # 3 rows × 3 PK columns
        assert params[0:3] == ["2024-01-01", "P001", "C001"]
    
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
        
    def test_build_delete_sql_missing_pk_values(self):
        """Test error when PK values are missing."""
        rows = [{"id": 1}, {"id": 2, "type": None}]  # Missing 'type' values
        
        with pytest.raises(ValueError, match="Missing primary key values"):
            build_delete_sql("test", ["id", "type"], rows)

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

class TestDatabaseSettings:
    """Test database configuration."""
    
    def test_connection_string_from_parts(self):
        """Test connection string generation."""
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
        """Create test database connection."""
        import os
        import psycopg2
        
        # Requires environment variables for test database
        conn_str = os.getenv("WDH_TEST_DATABASE_URI")
        if not conn_str:
            pytest.skip("Test database not configured")
        
        conn = psycopg2.connect(conn_str)
        
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
```

## Documentation & Reference URLs

### Essential Documentation
- **PostgreSQL NUMERIC Type**: https://www.postgresql.org/docs/current/datatype-numeric.html
- **psycopg2 SQL Module**: https://www.psycopg.org/docs/sql.html
- **psycopg2 Extras (execute_values)**: https://www.psycopg.org/docs/extras.html
- **PostgreSQL DELETE Syntax**: https://www.postgresql.org/docs/current/sql-delete.html

### Performance References  
- **Bulk Insert Best Practices**: https://stackoverflow.com/questions/2271787/psycopg2-postgresql-python-fastest-way-to-bulk-insert
- **execute_values Performance**: https://naysan.ca/2020/05/09/pandas-to-postgresql-using-psycopg2-bulk-insert-performance-benchmark/

### Security References
- **SQL Injection Prevention**: https://www.psycopg.org/docs/usage.html#passing-parameters-to-sql-queries
- **Identifier Quoting**: https://stackoverflow.com/questions/71145124/syntax-to-guard-against-sql-injection-of-named-identifiers

## Implementation Tasks (Execution Order)

### Task 1: Create Loader Module Structure
```bash
mkdir -p src/work_data_hub/io/loader
touch src/work_data_hub/io/loader/__init__.py
touch src/work_data_hub/io/loader/warehouse_loader.py
```

### Task 2: Implement SQL Utilities  
- `quote_ident()` function with validation
- `_ensure_list_of_dicts()` helper
- `_get_column_order()` for deterministic ordering
- Custom exception `DataWarehouseLoaderError`

### Task 3: Implement SQL Builders
- `build_insert_sql()` with execute_values compatibility
- `build_delete_sql()` with composite key tuple IN pattern
- Parameter flattening for psycopg2
- Input validation and error handling

### Task 4: Implement Loader Orchestration  
- `load()` function with mode switching
- Chunking logic for large datasets
- Transactional execution with connection
- Return metadata for introspection

### Task 5: Extend Configuration
- Add `DatabaseSettings` class to settings.py
- Environment variable support with WDH_DATABASE__ prefix
- Connection string generation method
- Integration with existing Settings class

### Task 6: Comprehensive Testing
- Unit tests for SQL builders (no database required)
- Loader orchestration tests with SQL plan validation  
- Configuration tests
- Integration tests with @pytest.mark.postgres marker
- Edge cases: empty data, missing keys, chunking

## Gotchas & Critical Implementation Notes

### 1. Parameter Limits
PostgreSQL has limits on query parameters. Chunk conservatively (max 1000 rows) to avoid hitting limits with composite keys.

### 2. Empty Tuple Handling  
SQL doesn't allow empty IN clauses. Always check for empty rows early and return no-op results.

### 3. Identifier Quoting Rules
- Use double quotes for identifiers, single quotes for literals
- Don't quote `schema.table` as one identifier - quote each part separately
- PostgreSQL identifiers are case-sensitive when quoted

### 4. Decimal Precision
Let psycopg2 handle Decimal ↔ NUMERIC conversion automatically. Don't convert to strings manually.

### 5. Transaction Management
Use `with conn:` for automatic transaction management. Exceptions will rollback automatically.

### 6. execute_values() Data Format
execute_values expects list of tuples/lists, not flattened parameters. Convert accordingly.

### 7. Connection vs Cursor Context
Both connection AND cursor need proper context management for resource cleanup.

## Validation Gates

### Syntax & Style Validation  
```bash
# Install dependencies
uv venv && uv sync

# Code quality checks
uv run ruff check src/work_data_hub/io/loader/ --fix
uv run ruff format src/work_data_hub/io/loader/
uv run mypy src/work_data_hub/io/loader/
```

### Unit Tests (No Database Required)
```bash  
# Run loader-specific tests
uv run pytest -v tests/io/test_warehouse_loader.py

# Run with coverage
uv run pytest tests/io/test_warehouse_loader.py --cov=src/work_data_hub/io/loader --cov-report=term-missing
```

### Integration Tests (Optional - Real Database)
```bash
# Setup test environment
export WDH_TEST_DATABASE_URI="postgresql://testuser:testpass@localhost:5432/test_db"

# Run integration tests
uv run pytest -v -m postgres tests/io/test_warehouse_loader.py
```

### End-to-End Validation
```bash
# Run all loader tests
uv run pytest -v -k "warehouse_loader"

# Validate settings integration  
uv run python -c "from src.work_data_hub.config.settings import get_settings; print(get_settings().database)"
```

## Acceptance Criteria

- [ ] `warehouse_loader.py` implements all required functions with proper type hints
- [ ] SQL builders generate correct parameterized queries without string interpolation
- [ ] delete_then_insert mode executes DELETE followed by chunked INSERTs in single transaction  
- [ ] append mode executes only INSERT operations
- [ ] Chunking works correctly for datasets larger than chunk_size
- [ ] Unit tests validate SQL generation and parameters without requiring database
- [ ] Integration tests are marked with @pytest.mark.postgres and skipped by default
- [ ] All validation gates pass: ruff, mypy, pytest
- [ ] DatabaseSettings extends existing configuration with environment variable support
- [ ] Error handling provides clear messages for validation failures
- [ ] Performance optimizations use execute_values() for bulk operations

## Risk Assessment & Mitigation

### High Risk: SQL Injection  
**Mitigation**: Comprehensive testing of identifier quoting and parameter validation. Never use string concatenation.

### Medium Risk: Performance with Large Datasets
**Mitigation**: Implement chunking with configurable size. Use execute_values() for optimal bulk performance.

### Medium Risk: Transaction Failures
**Mitigation**: Use context managers for automatic cleanup. Comprehensive error handling with rollback.

### Low Risk: Configuration Complexity
**Mitigation**: Follow existing settings patterns. Provide clear environment variable examples.

## Confidence Score: 9/10

**Rationale**: This PRP provides comprehensive implementation guidance with:
- ✅ Detailed research on PostgreSQL/psycopg2 best practices  
- ✅ Complete code examples following existing patterns
- ✅ Thorough testing strategy with both unit and integration tests
- ✅ Security considerations and performance optimizations
- ✅ Clear validation gates and acceptance criteria  
- ✅ Risk mitigation strategies

**Potential Challenges**:
- Complex transaction management edge cases (1 point deduction)

The implementation should succeed in one pass given the comprehensive context, patterns, and validation approach provided.