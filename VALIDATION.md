
# Output

- `uv run pytest -v tests/e2e/test_trustee_performance_e2e.py -k "Integration"`

```bash
===================================== FAILURES ====================================== 
_ TestTrusteePerformanceE2EIntegration.test_database_transaction_rollback_on_error __ 

self = <tests.e2e.test_trustee_performance_e2e.TestTrusteePerformanceE2EIntegration object at 0x0000024DF5379120>
db_connection = <connection object at 0x0000024DF534C260; dsn: 'user=root password=xxx connect_timeout=5 dbname=annuity host=192.168.0.200 port=5432', closed: 0>

    def test_database_transaction_rollback_on_error(self, db_connection):
        """Test that database transactions rollback properly on errors."""
        # Create data that will cause a constraint violation
        invalid_data = [{
            "report_date": "2024-11-01",
            "plan_code": "PLAN001",
            "company_code": "COMP001",
            "return_rate": Decimal("0.055"),
            "data_source": "test"
        }, {
            "report_date": "2024-11-01",
            "plan_code": "PLAN001",  # Duplicate primary key
            "company_code": "COMP001",
            "return_rate": Decimal("0.048"),
            "data_source": "test"
        }]

        # This should fail due to duplicate primary key
        with pytest.raises(DataWarehouseLoaderError):
            load(
                table="test_trustee_performance",
                rows=invalid_data,
                mode="append",  # Will try to insert duplicates
                conn=db_connection
            )

        # Verify no data was inserted (transaction rolled back)
        with db_connection.cursor() as cursor:
>           cursor.execute("SELECT COUNT(*) FROM test_trustee_performance")
E           psycopg2.errors.UndefinedTable: relation "test_trustee_performance" does not exist
E           LINE 1: SELECT COUNT(*) FROM test_trustee_performance
E                                        ^

tests\e2e\test_trustee_performance_e2e.py:539: UndefinedTable
--------------------------------- Captured log call --------------------------------- 
ERROR    src.work_data_hub.io.loader.warehouse_loader:warehouse_loader.py:344 Database operation failed: duplicate key value violates unique constraint "test_trustee_performance_pkey"
DETAIL:  Key (report_date, plan_code, company_code)=(2024-11-01, PLAN001, COMP001) already exists.
================================= warnings summary ================================== 
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================== short test summary info ============================== 
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2EIntegration::test_database_transaction_rollback_on_error - psycopg2.errors.UndefinedTable: relation "test_trustee_performance" does not exist
=============== 1 failed, 2 passed, 9 deselected, 1 warning in 2.59s ================
(WorkDataHub) PS E:\Projects\WorkDataHub> 
```

- `uv run pytest -v`

```bash
============================== short test summary info ============================== 
FAILED tests/domain/trustee_performance/test_models.py::TestFloatPrecisionEdgeCases::test_decimal_construction_from_float_string_conversion - AssertionError: assert 18 <= 17
FAILED tests/domain/trustee_performance/test_models.py::TestFieldValidatorInfoIntegration::test_field_validator_receives_correct_field_name - AssertionError: assert 'return_rate' in []
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2E::test_pipeline_error_handling_invalid_data - src.work_data_hub.domain.trustee_performance.service.TrusteePerformanceTransforma...
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2EIntegration::test_database_transaction_rollback_on_error - psycopg2.errors.UndefinedTable: relation "test_trustee_performance" does not exist
FAILED tests/io/test_warehouse_loader.py::TestJSONBParameterAdaptation::test_load_with_execute_values_jsonb_adaptation - AttributeError: __enter__
FAILED tests/io/test_warehouse_loader.py::TestJSONBParameterAdaptation::test_execute_values_parameter_structure_with_jsonb - AttributeError: __enter__
=============== 6 failed, 291 passed, 2 skipped, 2 warnings in 9.29s ================ 
Exception during reset or similar
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 985, in _finalize_fairy
    fairy._reset(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 1433, in _reset
    pool._dialect.do_rollback(self)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\engine\default.py", line 711, in do_rollback
    dbapi_connection.rollback()
sqlite3.ProgrammingError: Cannot operate on a closed database.
Exception during reset or similar
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 985, in _finalize_fairy
    fairy._reset(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 1433, in _reset
    pool._dialect.do_rollback(self)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\engine\default.py", line 711, in do_rollback
    dbapi_connection.rollback()
sqlite3.ProgrammingError: Cannot operate on a closed database.
Exception during reset or similar
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 985, in _finalize_fairy
    fairy._reset(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 1433, in _reset
    pool._dialect.do_rollback(self)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\engine\default.py", line 711, in do_rollback
    dbapi_connection.rollback()
sqlite3.ProgrammingError: Cannot operate on a closed database.
Exception during reset or similar
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 985, in _finalize_fairy
    fairy._reset(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\pool\base.py", line 1433, in _reset
    pool._dialect.do_rollback(self)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\sqlalchemy\engine\default.py", line 711, in do_rollback
    dbapi_connection.rollback()
sqlite3.ProgrammingError: Cannot operate on a closed database.
(WorkDataHub) PS E:\Projects\WorkDataHub> 
```