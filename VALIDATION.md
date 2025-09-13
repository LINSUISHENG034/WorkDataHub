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
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - RUN_START - Started execution of run for "annuity_performance_job".
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - ENGINE_EVENT - Executing steps in process (pid: 109956)
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - RESOURCE_INIT_STARTED - Starting initialization of resources [io_manager].
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - RESOURCE_INIT_SUCCESS - Finished initialization of resources [io_manager].
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - LOGS_CAPTURED - Started capturing logs in process (pid: 109956).
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - discover_files_op - STEP_START - Started execution of step "discover_files_op".
2025-09-13 22:09:24 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - discover_files_op - File discovery completed - domain: annuity_performance, found: 1 files, config: ./src/work_data_hub/config/data_sources.yml   
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - discover_files_op - STEP_OUTPUT - Yielded output "result" of type "[String]". (Type check passed).
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - discover_files_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - discover_files_op - STEP_SUCCESS - Finished execution of step "discover_files_op" in 26ms.
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - STEP_START - Started execution of step "read_excel_op".
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - LOADED_INPUT - Loaded input "file_paths" using input manager "io_manager", from output "result" of step "discover_files_op"
2025-09-13 22:09:24 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - STEP_INPUT - Got input "file_paths" of type "[String]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - read_excel_op - Excel reading completed - file: tests\fixtures\sample_data\annuity_subsets\2024年11月年金终稿数据_subset_append_3.xlsx, sheet: 规 模明细, rows: 3, columns: ['月度', '业务类型', '计划类型', '计划代码', '计划名称', '组合类型', '组合代码', '组合名称', '客户名称', '期初资产规模', '期末资产规模', '供款', '流失_含待遇支付', '流失', '待遇支付', '投资收益', '当期收益率', '机构代码', '机构', '子企业号', '子企业名称', '集团企业客户号', '集团企业客户名称']
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - STEP_OUTPUT - Yielded output "result" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - read_excel_op - STEP_SUCCESS - Finished execution of step "read_excel_op" in 227ms.
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - STEP_START - Started execution of step "process_annuity_performance_op".
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - LOADED_INPUT - Loaded input "excel_rows" using input manager "io_manager", from output "result" of step "read_excel_op"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - LOADED_INPUT - Loaded input "file_paths" using input manager "io_manager", from output "result" of step "discover_files_op"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - STEP_INPUT - Got input "excel_rows" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - STEP_INPUT - Got input "file_paths" of type "[String]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - process_annuity_performance_op - Domain processing completed - source: tests\fixtures\sample_data\annuity_subsets\2024年11月年金终稿数据_subset_append_3.xlsx, input_rows: 3, output_records: 3, domain: annuity_performance
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - STEP_OUTPUT - Yielded output "result" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - process_annuity_performance_op - STEP_SUCCESS - Finished execution of step "process_annuity_performance_op" in 19ms.
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - STEP_START - Started execution of step "derive_plan_refs_op".
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - LOADED_INPUT - Loaded input "processed_rows" using input manager "io_manager", from output "result" of step "process_annuity_performance_op"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - STEP_INPUT - Got input "processed_rows" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - derive_plan_refs_op - Plan candidate derivation completed
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - STEP_OUTPUT - Yielded output "result" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_plan_refs_op - STEP_SUCCESS - Finished execution of step "derive_plan_refs_op" in 7.3ms.
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - STEP_START - Started execution of step "derive_portfolio_refs_op".
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - LOADED_INPUT - Loaded input "processed_rows" using input manager "io_manager", from output "result" of step "process_annuity_performance_op"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - STEP_INPUT - Got input "processed_rows" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - derive_portfolio_refs_op - Portfolio candidate derivation completed
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - STEP_OUTPUT - Yielded output "result" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - HANDLED_OUTPUT - Handled output "result" using IO manager "io_manager"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - derive_portfolio_refs_op - STEP_SUCCESS - Finished execution of step "derive_portfolio_refs_op" in 7.67ms.
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - load_op - STEP_START - Started execution of step "load_op".
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - load_op - LOADED_INPUT - Loaded input "processed_rows" using input manager "io_manager", from output "result" of step "process_annuity_performance_op"
2025-09-13 22:09:25 +0800 - dagster - DEBUG - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - load_op - STEP_INPUT - Got input "processed_rows" of type "[Dict[String,Any]]". (Type check passed).
2025-09-13 22:09:25 +0800 - dagster - INFO - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - load_op - Connecting to database for execution (table: 规模明细)
Database operation failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.

2025-09-13 22:09:25 +0800 - dagster - ERROR - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - load_op - Load operation failed: Load failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.

2025-09-13 22:09:25 +0800 - dagster - ERROR - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - load_op - STEP_FAILURE - Execution of step "load_op" failed.

dagster._core.errors.DagsterExecutionStepExecutionError: Error occurred while executing op "load_op"::

src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Load failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


Stack Trace:
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\utils.py", line 57, in op_execution_error_boundary
    yield
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_utils\__init__.py", line 392, in iterate_with_context
    next_output = next(iterator)
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 137, in _coerce_op_compute_fn_to_iterator
    result = invoke_compute_fn(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 117, in invoke_compute_fn
    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 492, in load_op
    result = load(
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 744, in load
    raise DataWarehouseLoaderError(f"Load failed: {e}") from e

The above exception was caused by the following exception:
psycopg2.errors.ForeignKeyViolation: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


Stack Trace:
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 719, in load
    execute_values(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\psycopg2\extras.py", line 1299, in execute_values
    cur.execute(b''.join(parts))

2025-09-13 22:09:25 +0800 - dagster - ERROR - annuity_performance_job - fa63276a-aa8b-487b-a164-93bfdfab530b - 109956 - RUN_FAILURE - Execution of run for "annuity_performance_job" failed. An exception was thrown during execution.

src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Load failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


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
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 117, in invoke_compute_fn
    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 492, in load_op
    result = load(
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 744, in load
    raise DataWarehouseLoaderError(f"Load failed: {e}") from e

The above exception was caused by the following exception:
psycopg2.errors.ForeignKeyViolation: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


Stack Trace:
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 719, in load
    execute_values(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\psycopg2\extras.py", line 1299, in execute_values
    cur.execute(b''.join(parts))

💥 Job execution failed: Load failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


🐛 Full traceback:
Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 719, in load
    execute_values(
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\psycopg2\extras.py", line 1299, in execute_values
    cur.execute(b''.join(parts))
psycopg2.errors.ForeignKeyViolation: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\jobs.py", line 347, in main
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
  File "E:\Projects\WorkDataHub\.venv\lib\site-packages\dagster\_core\execution\plan\compute_generator.py", line 117, in invoke_compute_fn
    return fn(context, **args_to_pass) if context_arg_provided else fn(**args_to_pass)
  File "E:\Projects\WorkDataHub\src\work_data_hub\orchestration\ops.py", line 492, in load_op
    result = load(
  File "E:\Projects\WorkDataHub\src\work_data_hub\io\loader\warehouse_loader.py", line 744, in load
    raise DataWarehouseLoaderError(f"Load failed: {e}") from e
src.work_data_hub.io.loader.warehouse_loader.DataWarehouseLoaderError: Load failed: 错误:  插入或更新表 "规模明细" 违反外键约束 "fk_performance_plan"
DETAIL:  键值对(计划代码)=(Z0005)没有在表"年金计划"中出现.
```