# INITIAL.md — C‑028 验证与收尾（P‑023）：别名序列化、年金E2E对齐与测试修复（KISS/YAGNI）

本 INITIAL 明确 P‑023 在 VALIDATING 阶段发现的阻断问题与收尾项，指导 Claude 以最小改动完成“列别名序列化、DDL 与字段对齐、^F 规则收窄、测试更新”，确保与新架构一致并通过全部校验门。

## Feature / Roadmap 对齐
- 任务：C‑028 Cleansing framework hardening（负/全角百分比、Excel头部规范化、年金组合^F前缀清理）
- PRP：P‑023（验证循环）
- 目标域：annuity_performance（规模明细） + 共用清洗框架

## 范围（Scope）
- In‑scope：
  - 在 Dagster ops 层统一启用 `by_alias=True, exclude_none=True` 的输出序列化，解决中文列名/DB列名别名与空值字段导致的装载问题。
  - 年金DDL对齐：`id` 列改为自增（IDENTITY/序列），匹配“模型不提供 id”的装载策略。
  - 年金 `^F` 前缀清理规则收窄，避免误伤如 “FIDELITY001”。
  - Excel 头部标准化/列名标准化按既有实现巩固；“流失（含待遇支付）”映射到“流失_含待遇支付”→ 输出再映射回 DB 列名。
  - 更新年金模型/服务相关测试，改用 `company_id`、别名序列化断言，并移除对已删除字段的依赖（如 data_source、processed_at、validation_warnings）。
- 非目标（Non‑goals）：
  - 不引入新的 Mapping Service 或复杂映射规则；不迁移公司名清洗/回填策略。
  - 不调整受托域数据契约（除非受 ops 统一序列化影响，预期无影响）。

## 关键决策与实现要点
- 列别名与JSON输出
  - 问题：年金输出模型中“流失_含待遇支付”通过 `alias/validation_alias/serialization_alias` 指向 DB 列“流失(含待遇支付)”，但 ops 使用 `model_dump(mode="json")` 未启用别名与排空，导致装载列名不匹配与空列污染。
  - 决策：在 `src/work_data_hub/orchestration/ops.py` 三处统一改为：`model_dump(mode="json", by_alias=True, exclude_none=True)`。

- DDL 与 id 列策略
  - 问题：DDL 中 `"id" INTEGER NOT NULL PRIMARY KEY` 无默认值；模型不提供 id，INSERT 省略该列将失败。
  - 决策：将 `scripts/dev/annuity_performance_real.sql` 的 `id` 改为 `GENERATED ALWAYS AS IDENTITY`（或等价自增），并在 execute 模式前应用该 DDL。

- ^F 前缀清理规则收窄
  - 现状：存在对以 F 开头的普通单词（如 FIDELITY）误剥离的风险。
  - 决策：仅当 `组合代码` 存在且 `计划代码` 满足编码样式（建议正则 `^F[0-9A-Z]+$`）时去除首字母 F；保留 `FIDELITY001` 等自然词。

- 列名标准化与别名回写
  - 输入：`ExcelReader` 已引入 `normalize_columns`，如“流失（含待遇支付）”→“流失_含待遇支付”。
  - 输出：年金输出模型通过 `serialization_alias="流失(含待遇支付)"` 保证入库列名与 DB 一致；ops `by_alias=True` 生效后，输出 dict 的键为 DB 实际列名。

- data_sources 主键
  - 已改为 `pk: ["月度", "计划代码", "company_id"]` 与输出一致；DELETE/INSERT 语句中引用的中文列名由装载器正确加引号并保持顺序。

## 具体修改点（Claude 执行）
- 文件：`src/work_data_hub/orchestration/ops.py`
  - 修改 3 处 `model_dump(...)` 为：`model_dump(mode="json", by_alias=True, exclude_none=True)`。
  - 位置：
    - `process_trustee_performance_op` 内结果转换
    - `process_annuity_performance_op` 内结果转换
    - `read_and_process_trustee_files_op` 内结果转换
- 文件：`scripts/dev/annuity_performance_real.sql`
  - 将 `"id" INTEGER NOT NULL` 调整为 `"id" INTEGER GENERATED ALWAYS AS IDENTITY`（或 PostgreSQL 版本允许的自增写法），保留主键与索引不变。
  - 执行顺序：在 execute 模式前应用。
- 文件：`src/work_data_hub/domain/annuity_performance/service.py`
  - `_extract_plan_code` 收窄规则：仅当 `hasattr(input_model, "组合代码")` 且 `组合代码` 非空，且 `计划代码` 匹配 `^F[0-9A-Z]+$` 时才剥离前缀 `F`。
- 测试更新（见下“测试与验证”）：
  - 年金模型/服务测试用例：
    - 输出/装载断言改为使用 `company_id` 而非 `公司代码`。
    - 删除对已去除字段（`data_source`、`processed_at`、`validation_warnings` 等）的硬性断言；如需校验来源信息，请在服务层单测中以“输入/传递变量”方式断言，而非依赖输出模型字段。
    - 别名序列化断言：`model.model_dump(by_alias=True)` 后包含 `"流失(含待遇支付)"` 键。

## 示例与参考（按文件）
- `src/work_data_hub/orchestration/ops.py`
  - 统一：`[m.model_dump(mode="json", by_alias=True, exclude_none=True) for m in processed_models]`
- `src/work_data_hub/domain/annuity_performance/models.py`
  - 已设置 `serialization_alias`，保持不变；此任务仅确保 ops 使用 by_alias。
- `src/work_data_hub/io/readers/excel_reader.py`
  - 已集成 `normalize_columns` 与去除 `\n/\t`；补充分支测试即可。
- `src/work_data_hub/utils/column_normalizer.py`
  - 规则已覆盖全/半角括号，按现实现新增/修正测试。

## 风险与对策
- 风险：DDL 未更新导致 execute 模式 INSERT 失败（id 无默认值）。
  - 对策：强制在 execute 前应用 DDL；若不可变更 DB，需临时在装载前人为生成 id（不推荐，违背新架构“由DB负责生成主键”的约定）。
- 风险：`by_alias=True` 改动可能影响受托域输出。
  - 对策：受托域字段未使用 alias，输出不变；补充一条受托域 E2E 校验。
- 风险：^F 规则收窄后，极少数历史数据可能保留 F 前缀。
  - 对策：以 regex 明确边界；必要时在 Mapping Service（M2）引入白/黑名单。

## 测试与验证（命令可复制）
- 环境与基线
  - `uv venv && uv sync`
  - `uv run ruff format .`
  - `uv run ruff check src/ --fix`
  - `uv run mypy src/`
  - `uv run pytest -v`
- 定位测试
  - 列名/清洗：`uv run pytest -v tests/unit/test_cleansing_framework.py -k "percent or percentage or currency"`
  - Excel 头部：`uv run pytest -v tests/io/test_excel_reader.py -k "header or column or newline or tab"`
  - 年金域：`uv run pytest -v tests/domain/annuity_performance/test_service.py`
  - 受托 E2E：`uv run pytest -v tests/e2e/test_trustee_performance_e2e.py -k completed`
- 计划模式（安全验证）
  - `WDH_DATA_BASE_DIR=./reference/monthly uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only --max-files 1`
  - 期望：打印 DELETE/INSERT 计划，列名含中文与 `"流失(含待遇支付)"`；无列不存在错误。
- 执行模式（需先应用 DDL）
  - 应用DDL：`psql "$WDH_DATABASE__URI" -f scripts/dev/annuity_performance_real.sql`
  - 执行：`WDH_DATA_BASE_DIR=./reference/monthly uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --execute --max-files 1 --mode delete_insert`
  - 期望：装载成功，deleted/inserted/batches 合理；`计划代码` 无 `F` 前缀异常；存在负收益率记录（验证百分比处理）。
- CLI 助手（可选）
  - 运行：`uv run python scripts/demos/prp_p023_cli.py test-all`
  - 管道：`uv run python scripts/demos/prp_p023_cli.py pipeline --data-dir ./reference/monthly --plan-only`

## 验收标准（Definition of Done）
- 别名与排空：ops 使用 `by_alias=True, exclude_none=True`，E2E 观察到 `"流失(含待遇支付)"` 正确出现在 INSERT 列中，且未出现空列导致的 SQL 失败。
- DDL：年金表 `id` 自增，execute 模式可不显式提供 `id` 即成功插入。
- ^F 清理：满足正则 `^F[0-9A-Z]+$` 且 `组合代码` 存在时才剥离；如 `FIDELITY001` 保留。
- 头部与列名：Excel 头部无 `\n/\t`；“流失（含待遇支付）”→“流失_含待遇支付”→ 输出再映射为 DB 列名。
- 主键一致：`data_sources.yml` 的 `pk=["月度","计划代码","company_id"]` 与输出一致；DELETE SQL 正确引用中文列名（带引号）。
- 基线全绿：`ruff/mypy/pytest` 通过；annuity/trustee E2E 关键用例通过。
- 文档与状态：如有必要，更新 README（列投影描述与现实一致）与 ROADMAP（C‑028 继续 VALIDATING → COMPLETED）。

## 依赖与外部约束
- 无网络依赖；如无法使用外部搜索，请依据仓库现有实现与测试模式推进，必要时在注释中说明假设。
- 数据库 DDL 必须在 execute 前预先应用；如环境无DB，仅做 plan‑only 验证。

## 备注与澄清点（如需人类决定）
- 是否确认以“DB自增主键”为年金域长期策略（推荐）？
- 是否同意将年金测试用例统一改为 `company_id`，并删除对已去除字段的硬性断言？
- 如发现极少样本仍需特殊 `F` 规则，是否延后到 Mapping Service（M2）而非在域内继续加复杂分支？

## 参考索引
- `AGENTS.md`（本文件遵循其“INITIAL/PRP流程”规范）
- `README.md`（运行与验证命令）
- `ROADMAP.md`（单一事实源：状态/依赖）
- `docs/overview/MIGRATION_REFERENCE.md`（迁移总览）
- `docs/overview/LEGACY_WORKFLOW_ANALYSIS.md`（历史事实）

