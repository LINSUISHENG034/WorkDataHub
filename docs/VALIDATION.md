```bash
PS E:\Projects\WorkDataHub> uv run python -m ` 
>> src.work_data_hub.orchestration.jobs `
>> --domain annuity_performance `
>> --execute `
>> --execute --max-files 1 `
>> --backfill-refs all `
>> --backfill-mode insert_missing `
>> --sheet "规模明细" `
>> --mode append `
>> --debug `
>> --raise-on-error
WARNING:root:MySqlDBManager not available - legacy extraction will be disabled
🚀 Starting annuity_performance job...
   Domain: annuity_performance
   Mode: append
   Execute: True
   Plan-only: False
   Sheet: 规模明细
   Max files: 1
   Skip facts: False
   Backfill refs: all
   Backfill mode: insert_missing
==================================================
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - RUN_START - Started execution of run for "annuity_performance_job".
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - ENGINE_EVENT - Executing steps in process (pid: 112380)       
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - RESOURCE_INIT_STARTED - Starting initialization of resources [io_manager].
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - RESOURCE_INIT_SUCCESS - Finished initialization of resources [io_manager].
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - LOGS_CAPTURED - Started capturing logs in process (pid: 112380).
2025-09-20 11:27:16 +0800 - dagster - DEBUG - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - discover_files_op - STEP_START - Started execution of step "discover_files_op".
ERROR:src.work_data_hub.orchestration.ops:data_sources.yml validation failed: data_sources.yml validation failed: 2 validation errors for DataSourcesConfig
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
2025-09-20 11:27:16 +0800 - dagster - ERROR - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - discover_files_op - STEP_FAILURE - Execution of step "discover_files_op" failed.

dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "discover_files_op"::

src.work_data_hub.config.schema.DataSourcesValidationError: data_sources.yml validation failed: 2 validation errors for DataSourcesConfig
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing

Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 108, in invoke_compute_fn
    args_to_pass["config"] = construct_config_from_context(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 123, in construct_config_from_context
    return config_arg_cls(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_config\pythonic_config\config.py", line 253, in __init__
    super().__init__(**modified_data_by_config_key)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\main.py", line 253, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self) 
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 98, in validate_domain
    valid_domains = _load_valid_domains()
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 55, in _load_valid_domains
    validate_data_sources_config()
  File "E:\Projects\WorkDataHub\src\work_data_hub\config\schema.py", line 93, in validate_data_sources_config
    raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")

The above exception occurred during handling of the following exception:
pydantic_core._pydantic_core.ValidationError: 2 validation errors for DataSourcesConfig    
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing

Stack Trace:
  File "E:\Projects\WorkDataHub\src\work_data_hub\config\schema.py", line 87, in validate_data_sources_config
    config = DataSourcesConfig(**data)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\main.py", line 253, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self) 

2025-09-20 11:27:16 +0800 - dagster - ERROR - annuity_performance_job - 43077646-8199-4036-9b58-2af17f69d028 - 112380 - RUN_FAILURE - Execution of run for "annuity_performance_job" failed. An exception was thrown during execution.

src.work_data_hub.config.schema.DataSourcesValidationError: data_sources.yml validation failed: 2 validation errors for DataSourcesConfig
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing

Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\api.py", line 739, in job_execution_iterator
    for event in job_context.executor.execute(job_context, execution_plan):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\executor\in_process.py", line 57, in execute
    yield from iter(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\api.py", line 872, in __iter__
    yield from self.iterator(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\executor\in_process.py", line 28, in inprocess_execution_iterator
    yield from inner_plan_execution_iterator(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 88, in inner_plan_execution_iterator
    for step_event in check.generator(dagster_event_sequence_for_step(step_context)):      
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 318, in dagster_event_sequence_for_step
    raise dagster_user_error.user_exception
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 108, in invoke_compute_fn
    args_to_pass["config"] = construct_config_from_context(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 123, in construct_config_from_context
    return config_arg_cls(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_config\pythonic_config\config.py", line 253, in __init__
    super().__init__(**modified_data_by_config_key)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\main.py", line 253, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self) 
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 98, in validate_domain
    valid_domains = _load_valid_domains()
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 55, in _load_valid_domains
    validate_data_sources_config()
  File "E:\Projects\WorkDataHub\src\work_data_hub\config\schema.py", line 93, in validate_data_sources_config
    raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")

The above exception occurred during handling of the following exception:
dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "discover_files_op":

Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 246, in dagster_event_sequence_for_step
    yield from check.generator(step_events)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 504, in core_dagster_event_sequence_for_step
    for user_event in _step_output_error_checked_user_event_sequence(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 183, in _step_output_error_checked_user_event_sequence
    for user_event in user_event_sequence:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 88, in _process_asset_results_to_events
    for user_event in user_event_sequence:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute.py", line 190, in execute_core_compute
    for step_output in _yield_compute_results(step_context, inputs, compute_fn, compute_context):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute.py", line 159, in _yield_compute_results
    for event in iterate_with_context(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 390, in iterate_with_context
    with context_fn():
  File "C:\Users\LINSUISHENG034\AppData\Local\Programs\Python\Python310\lib\contextlib.py", line 153, in __exit__
    self.gen.throw(typ, value, traceback)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 87, in op_execution_error_boundary
    raise error_cls(

💥 Job execution failed: data_sources.yml validation failed: 2 validation errors for DataSourcesConfig
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing

🐛 Full traceback:
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 246, in dagster_event_sequence_for_step
    yield from check.generator(step_events)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 504, in core_dagster_event_sequence_for_step
    for user_event in _step_output_error_checked_user_event_sequence(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 183, in _step_output_error_checked_user_event_sequence
    for user_event in user_event_sequence:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_step.py", line 88, in _process_asset_results_to_events
    for user_event in user_event_sequence:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute.py", line 190, in execute_core_compute
    for step_output in _yield_compute_results(step_context, inputs, compute_fn, compute_context):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute.py", line 159, in _yield_compute_results
    for event in iterate_with_context(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 390, in iterate_with_context
    with context_fn():
  File "C:\Users\LINSUISHENG034\AppData\Local\Programs\Python\Python310\lib\contextlib.py", line 153, in __exit__
    self.gen.throw(typ, value, traceback)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 87, in op_execution_error_boundary
    raise error_cls(
dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "discover_files_op":

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\jobs.py", line 635, in main
    result = selected_job.execute_in_process(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\definitions\job_definition.py", line 766, in execute_in_process
    return core_execute_in_process(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\execute_in_process.py", line 157, in core_execute_in_process
    event_list = list(execute_run_iterable)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\api.py", line 872, in __iter__
    yield from self.iterator(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\api.py", line 739, in job_execution_iterator
    for event in job_context.executor.execute(job_context, execution_plan):
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\executor\in_process.py", line 57, in execute
    yield from iter(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\api.py", line 872, in __iter__
    yield from self.iterator(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\executor\in_process.py", line 28, in inprocess_execution_iterator
    yield from inner_plan_execution_iterator(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 88, in inner_plan_execution_iterator
    for step_event in check.generator(dagster_event_sequence_for_step(step_context)):      
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\execute_plan.py", line 318, in dagster_event_sequence_for_step
    raise dagster_user_error.user_exception
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 108, in invoke_compute_fn
    args_to_pass["config"] = construct_config_from_context(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 123, in construct_config_from_context
    return config_arg_cls(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_config\pythonic_config\config.py", line 253, in __init__
    super().__init__(**modified_data_by_config_key)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\main.py", line 253, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self) 
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 98, in validate_domain
    valid_domains = _load_valid_domains()
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 55, in _load_valid_domains
    validate_data_sources_config()
  File "E:\Projects\WorkDataHub\src\work_data_hub\config\schema.py", line 93, in validate_data_sources_config
    raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")
src.work_data_hub.config.schema.DataSourcesValidationError: data_sources.yml validation failed: 2 validation errors for DataSourcesConfig
domains.company_mapping.pattern
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
domains.company_mapping.select
  Field required [type=missing, input_value={'description': 'Company ...: 4, 'account_name': 5}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/missing
PS E:\Projects\WorkDataHub>
```