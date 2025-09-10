
- `uv run pytest -v` (updated)

```bash
----------------------------------------------------- Captured stderr call ----------------------------------------------------- 
2025-09-10 13:37:38 +0800 - dagster - INFO - system - Connecting to database for execution (table: test)
2025-09-10 13:37:46 +0800 - dagster - ERROR - system - Load operation failed: Database connection failed: could not translate host name "test" to address: No such host is known.
. Check WDH_DATABASE__* environment variables.
======================================================= warnings summary ======================================================= 
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

tests/io/test_excel_reader.py::TestExcelReader::test_dataframe_to_rows_column_name_cleaning
  E:\Projects\WorkDataHub\src\work_data_hub\io\readers\excel_reader.py:212: UserWarning: DataFrame columns are not unique, some columns will be omitted.
    rows = df.to_dict(orient="records")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================================================== short test summary info ==================================================== 
FAILED tests/domain/trustee_performance/test_models.py::TestFloatPrecisionEdgeCases::test_decimal_construction_from_float_string_conversion - AssertionError: assert 18 <= 17
FAILED tests/domain/trustee_performance/test_models.py::TestFieldValidatorInfoIntegration::test_field_validator_receives_correct_field_name - AssertionError: assert 'return_rate' in []
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2E::test_pipeline_error_handling_invalid_data - src.work_data_hub.domain.trustee_performance.service.TrusteePerformanceTransformationError: Too many processing errors (3/3)...
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2EIntegration::test_database_transaction_rollback_on_error - psycopg2.errors.UndefinedTable: relation "test_trustee_performance" does not exist
FAILED tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2EIntegration::test_database_connection_lifecycle_integration - AttributeError: <module 'src.work_data_hub.orchestration.ops' from 'E:\\Projects\\WorkDataHub\\src\\work_data_hub\\orchestra...
FAILED tests/io/test_warehouse_loader.py::TestJSONBParameterAdaptation::test_load_with_execute_values_jsonb_adaptation - NameError: name 'Mock' is not defined
FAILED tests/io/test_warehouse_loader.py::TestJSONBParameterAdaptation::test_execute_values_parameter_structure_with_jsonb - NameError: name 'Mock' is not defined
FAILED tests/orchestration/test_ops.py::TestLoadOp::test_load_op_execute_mode_mocked - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: __enter__. Check WDH_DATA...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_uses_bare_connection_not_context_manager - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...    
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_cleanup_on_success - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_cleanup_on_load_failure - AssertionError: Regex pattern did not match.
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_no_context_manager_nesting_detected - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_dsn_building - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: connection to server at "...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_db_context_manager_mocked - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
==================================== 14 failed, 283 passed, 2 skipped, 2 warnings in 44.56s ==================================== 
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

- `uv run pytest -v tests/e2e/test_trustee_performance_e2e.py -k "complete_pipeline_plan_only_mode"`
```bash
(WorkDataHub) PS E:\Projects\WorkDataHub> uv run pytest -v tests/e2e/test_trustee_performance_e2e.py -k "complete_pipeline_plan_only_mode"
===================================================== test session starts ======================================================
platform win32 -- Python 3.10.11, pytest-8.4.2, pluggy-1.6.0 -- E:\Projects\WorkDataHub\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: E:\Projects\WorkDataHub
configfile: pyproject.toml
plugins: anyio-4.10.0, cov-6.2.1
collected 12 items / 11 deselected / 1 selected                                                                                 

tests/e2e/test_trustee_performance_e2e.py::TestTrusteePerformanceE2E::test_complete_pipeline_plan_only_mode PASSED        [100%]

======================================================= warnings summary =======================================================
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================================= 1 passed, 11 deselected, 1 warning in 2.08s ==========================================
(WorkDataHub) PS E:\Projects\WorkDataHub> 
```

- `uv run pytest -v tests/orchestration/test_ops.py -k "LoadOp and ConnectionLifecycle"`
```bash
----------------------------------------------------- Captured stderr call ----------------------------------------------------- 
2025-09-10 13:41:38 +0800 - dagster - INFO - system - Connecting to database for execution (table: test)
2025-09-10 13:41:45 +0800 - dagster - ERROR - system - Load operation failed: Database connection failed: could not translate host name "test" to address: No such host is known.
. Check WDH_DATABASE__* environment variables.
======================================================= warnings summary ======================================================= 
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================================================== short test summary info ==================================================== 
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_uses_bare_connection_not_context_manager - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...    
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_cleanup_on_success - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_cleanup_on_load_failure - AssertionError: Regex pattern did not match.
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_no_context_manager_nesting_detected - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_connection_dsn_building - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: connection to server at "...
FAILED tests/orchestration/test_ops.py::TestLoadOpConnectionLifecycle::test_load_op_db_context_manager_mocked - src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: could not translate host ...
==================================== 6 failed, 3 passed, 29 deselected, 1 warning in 35.80s ==================================== 
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