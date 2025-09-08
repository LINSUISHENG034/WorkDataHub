- `uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2`
```bash
PS E:\Projects\WorkDataHub> uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2
� Starting trustee performance job...
   Domain: trustee_performance
   Mode: delete_insert
   Execute: True
   Plan-only: False
   Sheet: 0
   Max files: 2
==================================================
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - RUN_START - Started execution of run for "trustee_performance_multi_file_job".
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - ENGINE_EVENT - Executing steps in process (pid: 74584)
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - RESOURCE_INIT_STARTED - Starting initialization of resources [io_manager].
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - RESOURCE_INIT_SUCCESS - Finished initialization of resources [io_manager].
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - LOGS_CAPTURED - Started capturing logs in process (pid: 74584).
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - discover_files_op - STEP_START - Started execution of step "discover_files_op".
2025-09-08 17:15:46 +0800 - dagster - INFO - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - discover_files_op - File discovery completed - domain: trustee_performance, found: 1 files, config: ./src/work_data_hub/config/data_sources.yml
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - discover_files_op - STEP_OUTPUT - Yielded output "result" of type "[String]". (Type check passed).
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - discover_files_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - discover_files_op - STEP_SUCCESS - Finished execution of step "discover_files_op" in 8.86ms.
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - read_and_process_trustee_files_op - STEP_START - Started execution of step "read_and_process_trustee_files_op".
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - read_and_process_trustee_files_op - LOADED_INPUT - Loaded input "file_paths" using input manager "io_manager", from output "result" of step "discover_files_op"
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - read_and_process_trustee_files_op - STEP_INPUT - Got input "file_paths" of type "[String]". (Type check passed).
Validation failed for row 0: 2 validation errors for TrusteePerformanceIn
净值
  Input should be a valid string [type=string_type, input_value=1.0512, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
规模
  Input should be a valid string [type=string_type, input_value=12000000, input_type=int]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
Validation failed for row 1: 2 validation errors for TrusteePerformanceIn
净值
  Input should be a valid string [type=string_type, input_value=1.0488, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
规模
  Input should be a valid string [type=string_type, input_value=25000000, input_type=int]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
Validation failed for row 2: 2 validation errors for TrusteePerformanceIn
净值
  Input should be a valid string [type=string_type, input_value=1.053, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
规模
  Input should be a valid string [type=string_type, input_value=18000000, input_type=int]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
Encountered 3 processing errors
2025-09-08 17:15:46 +0800 - dagster - ERROR - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - read_and_process_trustee_files_op - Failed to process file tests\fixtures\sample_data\2024-01_受托业绩_sample.xlsx: Too many processing errors (3/3). First error: Validation failed for row 0: 2 validation errors for TrusteePerformanceIn
净值
  Input should be a valid string [type=string_type, input_value=1.0512, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
规模
  Input should be a valid string [type=string_type, input_value=12000000, input_type=int]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
2025-09-08 17:15:46 +0800 - dagster - ERROR - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - read_and_process_trustee_files_op - STEP_FAILURE - Execution of step "read_and_process_trustee_files_op" failed.

dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "read_and_process_trustee_files_op"::

src.work_data_hub.domain.trustee_performance.service.TrusteePerformanceTransformationError: Too many processing errors (3/3). First error: Validation failed for row 0: 2 validation errors for TrusteePerformanceIn
净值
  Input should be a valid string [type=string_type, input_value=1.0512, input_type=float]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
规模
  Input should be a valid string [type=string_type, input_value=12000000, input_type=int]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type

Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator       
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 117, in invoke_compute_fn
    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 266, in read_and_process_trustee_files_op
    models = process(rows, data_source=file_path)
  File "E:\Projects\WorkDataHub\src\work_data_hub\domain\trustee_performance\service.py", line 90, in process
    raise TrusteePerformanceTransformationError(

2025-09-08 17:15:46 +0800 - dagster - ERROR - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - load_op - Dependencies for step load_op failed: ['read_and_process_trustee_files_op']. Not executing.
2025-09-08 17:15:46 +0800 - dagster - DEBUG - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - ENGINE_EVENT - Finished steps in process (pid: 74584) in 263ms
2025-09-08 17:15:46 +0800 - dagster - ERROR - trustee_performance_multi_file_job - 6bc4d2a9-537e-42c2-b999-c17a9b457b7b - 74584 - RUN_FAILURE - Execution of run for "trustee_performance_multi_file_job" failed. Steps failed: ['read_and_process_trustee_files_op'].
✅ Job completed successfully: False
❌ Job completed with failures
   Error in read_and_process_trustee_files_op: StepFailureData(error=SerializableErrorInfo(message='dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "read_and_process_trustee_files_op":\n', stack=['  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_plan.py", line 246, in dagster_event_sequence_for_step\n    yield from check.generator(step_events)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 504, in core_dagster_event_sequence_for_step\n    for user_event in _step_output_error_checked_user_event_sequence(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 183, in _step_output_error_checked_user_event_sequence\n    for user_event in user_event_sequence:\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\execute_step.py", line 88, in _process_asset_results_to_events\n    for user_event in user_event_sequence:\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute.py", line 190, in execute_core_compute\n    for step_output in _yield_compute_results(step_context, inputs, compute_fn, compute_context):\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute.py", line 159, in _yield_compute_results\n    for event in iterate_with_context(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_utils\\__init__.py", line 390, in iterate_with_context\n    with context_fn():\n', '  File "C:\\Users\\LINSUISHENG034\\AppData\\Local\\Programs\\Python\\Python310\\lib\\contextlib.py", line 153, in __exit__\n    self.gen.throw(typ, value, traceback)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\utils.py", line 87, in op_execution_error_boundary\n    raise error_cls(\n'], cls_name='DagsterExecutionStepExecutionError', cause=SerializableErrorInfo(message='src.work_data_hub.domain.trustee_performance.service.TrusteePerformanceTransformationError: Too many processing errors (3/3). First error: Validation failed for row 0: 2 validation errors for TrusteePerformanceIn\n净值\n  Input should be a valid string [type=string_type, input_value=1.0512, input_type=float]\n    For further information visit https://errors.pydantic.dev/2.11/v/string_type\n规模\n  Input should be a valid string [type=string_type, input_value=12000000, input_type=int]\n    For further information visit https://errors.pydantic.dev/2.11/v/string_type\n', stack=['  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\utils.py", line 57, in op_execution_error_boundary\n    yield\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_utils\\__init__.py", line 392, in iterate_with_context\n    next_output = next(iterator)\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator\n    result = invoke_compute_fn(\n', '  File "E:\\Projects\\WorkDataHub\\.venv\\lib\\site-packages\\dagster\\_core\\execution\\plan\\compute_generator.py", line 117, in invoke_compute_fn\n    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)\n', '  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\orchestration\\ops.py", line 266, in read_and_process_trustee_files_op\n    models = process(rows, data_source=file_path)\n', '  File "E:\\Projects\\WorkDataHub\\src\\work_data_hub\\domain\\trustee_performance\\service.py", line 90, in process\n    raise TrusteePerformanceTransformationError(\n'], cls_name='TrusteePerformanceTransformationError', cause=None, context=None), context=None), user_failure_data=None, error_source=<ErrorSource.USER_CODE_ERROR: 'USER_CODE_ERROR'>)  
PS E:\Projects\WorkDataHub> 
```