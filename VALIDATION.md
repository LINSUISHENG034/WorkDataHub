
- `uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2`

```bash
(WorkDataHub) PS E:\Projects\WorkDataHub> uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2                     
� Starting trustee performance job...
   Domain: trustee_performance
   Mode: delete_insert
   Execute: True
   Plan-only: False
   Sheet: 0
   Max files: 2
==================================================
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - RUN_START - Started execution of run for "trustee_performance_multi_file_job".
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - ENGINE_EVENT - Executing steps in process (pid: 74848)
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - RESOURCE_INIT_STARTED - Starting initialization of resources [io_manager].
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - RESOURCE_INIT_SUCCESS - Finished initialization of resources [io_manager].
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - LOGS_CAPTURED - Started capturing logs in process (pid: 74848).
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - discover_files_op - STEP_START - Started execution of step "discover_files_op".
2025-09-08 22:02:02 +0800 - dagster - INFO - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - discover_files_op - File discovery completed - domain: trustee_performance, found: 1 files, config: ./src/work_data_hub/config/data_sources.yml
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - discover_files_op - STEP_OUTPUT - Yielded output "result" of type "[String]". (Type check passed).      
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - discover_files_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - discover_files_op - STEP_SUCCESS - Finished execution of step "discover_files_op" in 10ms.
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - STEP_START - Started execution of step "read_and_process_trustee_files_op".
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - LOADED_INPUT - Loaded input "file_paths" using input manager "io_manager", from output "result" of step "discover_files_op"
2025-09-08 22:02:02 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - STEP_INPUT - Got input "file_paths" of type "[String]". (Type check passed).
Validation failed for row 1: 1 validation error for TrusteePerformanceOut
return_rate
  Decimal input should have no more than 6 decimal places [type=decimal_max_places, input_value=0.048799999999999996, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/decimal_max_places
Encountered 1 processing errors
2025-09-08 22:02:04 +0800 - dagster - INFO - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - read_and_process_trustee_files_op - Processed tests\fixtures\sample_data\2024-01_受托业绩_sample.xlsx: 3 rows -> 2 records
2025-09-08 22:02:04 +0800 - dagster - INFO - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - read_and_process_trustee_files_op - Multi-file processing completed: 1 files, 2 total records
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - STEP_OUTPUT - Yielded output "result" of type "[dict]". (Type check passed).
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - read_and_process_trustee_files_op - STEP_SUCCESS - Finished execution of step "read_and_process_trustee_files_op" in 1.89s.
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - load_op - STEP_START - Started execution of step "load_op".
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - load_op - LOADED_INPUT - Loaded input "processed_rows" using input manager "io_manager", from output "result" of step "read_and_process_trustee_files_op"
2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - load_op - STEP_INPUT - Got input "processed_rows" of type "[Dict[String,Any]]". (Type check passed).    
2025-09-08 22:02:04 +0800 - dagster - INFO - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - load_op - Connecting to database for execution (table: trustee_performance)
Database operation failed: the connection cannot be re-entered recursively
2025-09-08 22:02:04 +0800 - dagster - ERROR - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - load_op - Load operation failed: Database connection failed: Load failed: the connection cannot be re-entered recursively. Check WDH_DATABASE__* environment variables.
2025-09-08 22:02:04 +0800 - dagster - ERROR - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - load_op - STEP_FAILURE - Execution of step "load_op" failed.

dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "load_op"::

src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: Load failed: the connection cannot be re-entered recursively. Check WDH_DATABASE__* environment variables.

Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 117, in invoke_compute_fn
    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 357, in load_op
    raise DataWarehouseLoaderError(

The above exception was caused by the following exception:
src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Load failed: the connection cannot be re-entered recursively

Stack Trace:
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 343, in load_op
    result = load(
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 319, in load
    raise DataWarehouseLoaderError(f"Load failed: {e}") from e

The above exception was caused by the following exception:
psycopg2.ProgrammingError: the connection cannot be re-entered recursively

Stack Trace:
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 283, in load
    with conn:  # Automatic transaction management

2025-09-08 22:02:04 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - ENGINE_EVENT - Finished steps in process (pid: 74848) in 1.97s
2025-09-08 22:02:04 +0800 - dagster - ERROR - trustee_performance_multi_file_job - aa66e402-d0a0-4593-b536-b47c64acd110 - 74848 - RUN_FAILURE - Execution of run for "trustee_performance_multi_file_job" failed. Steps failed: ['load_op'].
✅ Job completed successfully: False
❌ Job completed with failures
   Error in load_op: StepFailureData(error=SerializableErrorInfo(message='dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "load_op":\n', stack=['  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_plan.py", line 246, in dagster_event_sequence_for_step\n    yield from check.generator(step_events)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 504, in core_dagster_event_sequence_for_step\n    for user_event in _step_output_error_checked_user_event_sequence(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 183, in _step_output_error_checked_user_event_sequence\n    for user_event in user_event_sequence:\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 88, in _process_asset_results_to_events\n    for user_event in user_event_sequence:\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute.py", line 190, in execute_core_compute\n    for step_output in _yield_compute_results(step_context, inputs, compute_fn, compute_context):\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute.py", line 159, in _yield_compute_results\n    for event in iterate_with_context(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_utils\\__init__.py", line 390, in iterate_with_context\n    with context_fn():\n', '  File "C:\\Users\\LINSUISHENG034\\AppData\\Local\\Programs\\Python\\Python310\\lib\\contextlib.py", line 153, in __exit__\n    self.gen.throw(typ, value, traceback)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\utils.py", line 87, in op_execution_error_boundary\n    raise error_cls(\n'], cls_name='DagsterExecutionStepExecutionError', cause=SerializableErrorInfo(message='src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Database connection failed: Load failed: the connection cannot be re-entered recursively. Check WDH_DATABASE__* environment variables.\n', stack=['  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\utils.py", line 57, in op_execution_error_boundary\n    yield\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_utils\\__init__.py", line 392, in iterate_with_context\n    next_output = next(iterator)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator\n    result = invoke_compute_fn(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute_generator.py", line 117, in invoke_compute_fn\n    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)\n', '  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\orchestration\\ops.py", line 357, in load_op\n    raise DataWarehouseLoaderError(\n'], cls_name='DataWarehouseLoaderError', cause=SerializableErrorInfo(message='src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Load failed: the connection cannot be re-entered recursively\n', stack=['  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\orchestration\\ops.py", line 343, in load_op\n    result = load(\n', '  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\io\\loader\\warehouse_loader.py", line 319, in load\n    raise DataWarehouseLoaderError(f"Load failed: {e}") from e\n'], cls_name='DataWarehouseLoaderError', cause=SerializableErrorInfo(message='psycopg2.ProgrammingError: the connection cannot be re-entered recursively\n', stack=['  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\io\\loader\\warehouse_loader.py", line 283, in load\n    with conn:  # Automatic transaction management\n'], cls_name='ProgrammingError', cause=None, context=None), context=None), context=None), context=None), user_failure_data=None, error_source=<ErrorSource.USER_CODE_ERROR: 'USER_CODE_ERROR'>)
(WorkDataHub) PS E:\Projects\WorkDataHub> 
```