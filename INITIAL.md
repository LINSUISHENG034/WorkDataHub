# INITIAL.md — C-023: DB连接语义对齐（ops与loader）

目的：统一并稳固数据库连接/事务/会话语义，确保Dagster ops与loader在多种测试场景（裸连接、上下文管理器、同会话临时表、连接失败与清理）下行为一致，收敛剩余连接相关失败。

## 任务
- ROADMAP：C-023（Milestone 2）
- 标题：DB连接语义对齐（ops与loader连接生命周期/模式对齐）
- 范围：仅聚焦连接/事务/会话与错误分类，确保相关用例与E2E通过；不处理领域“invalid data”容错与Pydantic信息捕获类用例（留待后续）。

## 背景与当前症状（VALIDATION.md节选）
- Orchestration连接生命周期用例失败（多项）：
  - 期望兼容“上下文管理器连接（带__enter__/__exit__）”与“裸连接”两种模式；
  - 期望连接失败抛出`Database connection failed`，load失败抛出原始`Exception("Load operation failed")`；
  - 期望plan_only严格不建立连接；
  - 期望无“上下文管理器嵌套”。
- E2E Integration：
  - `UndefinedTable`（TEMP表不可见）需保证同一会话可见性（传入连接即同会话）；
  - 连接生命周期集成：需确保ops尊重外部mock/fixture连接。

## 交付物
1) `ops.load_op` 连接语义对齐
   - 动态导入`psycopg2`（兼容`builtins.__import__`型mock）
   - DSN解析（已有）：先统一方法，失败回退`settings.database.get_connection_string()`；校验返回为`str`
   - 连接建立错误分类：仅对`psycopg2.connect`失败映射`DataWarehouseLoaderError("Database connection failed: ...")`
   - 成功连接后：
     - 若连接对象具备`__enter__/__exit__`，走`with raw_conn as managed_conn`路径；
     - 否则走“裸连接”路径；
     - 不屏蔽`load()`抛出的异常（保持原始异常文案，满足`match="Load operation failed"`）。
   - 资源回收：
     - 裸连接：在`finally`中`close()`；
     - 上下文管理器：由`with`释放。

2) `loader.load` 会话与事务语义核验
   - 维持`with conn:`事务块（提交/回滚）；
   - 确保传入连接即同一会话（测试用例通过将fixture连接注入，验证TEMP表可见）；
   - 不在`load`中主动`close()`连接（由调用方管理）。

3) 错误信息一致性（测试期望）
   - 连接失败：`DataWarehouseLoaderError("Database connection failed: <原始错误>")`
   - 模块缺失：`DataWarehouseLoaderError("psycopg2 not available for database execution. Install with: uv sync")`
   - load过程失败：保留原始异常（如`Exception("Load operation failed")`）。

4) 测试文件小修（已执行）
   - `tests/io/test_warehouse_loader.py` 补充`from unittest.mock import Mock, patch`，修复`NameError: Mock`。

## 非目标
- 不处理以下两类（后续任务跟进）：
  - 领域invalid数据容错策略（过严导致`Too many processing errors`）；
  - Pydantic v2 Validator `ValidationInfo`捕获类用例稳定性；
  - 浮点字符串长度脆弱断言（`18 <= 17`）。

## 集成点
- 入口：`src/work_data_hub/orchestration/ops.py::load_op`
- Loader：`src/work_data_hub/io/loader/warehouse_loader.py::load`
- 配置：`src/work_data_hub/config/settings.py`（已具备DSN统一/回退机制）

## 验证步骤（本地）
- 运行基线：
  - `uv run ruff check src/ --fix`
  - `uv run mypy src/`
  - `uv run pytest -v`
- 重点关注：
  - `tests/orchestration/test_ops.py -k "LoadOp and ConnectionLifecycle"`
  - `tests/e2e/test_trustee_performance_e2e.py -k "Integration"`

## 验收标准（C-023）
- Orchestration连接生命周期相关用例全部通过：
  - 裸连接/上下文管理器两套路径均验证；
  - 连接失败报文匹配；
  - load失败保留原始异常文案；
  - plan_only不建连；
  - 资源清理正确（成功/失败皆关闭）。
- E2E Integration：
  - `test_database_transaction_rollback_on_error`与`test_database_connection_lifecycle_integration`通过（TEMP表可见、会话一致、事务回滚）
- 不新增mypy/ruff错误。

## 风险与回退
- 个别真实连接错误（如`could not translate host name "test"`）应仅在未mock场景出现；测试均通过patch防止真实连接，若仍出现，需排查导入/patch路径。
- 与领域容错/验证器相关失败非本任务范围；如执行过程中牵动到这些行为，需在PR中明确说明并回退。

## 受影响文件
- `src/work_data_hub/orchestration/ops.py`
- （核验）`src/work_data_hub/io/loader/warehouse_loader.py`

## 提交要求
- 只改必要代码路径；
- 通过指定用例与全量回归（CI范围内）；
- PR描述中附带受影响路径、失败样例与修复前后对比。
