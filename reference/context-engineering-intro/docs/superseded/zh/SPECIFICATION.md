  新架构模块与职责

  - 配置层: 负责环境参数与数据源配置（settings.py、schema.py、
  data_sources.yml）；驱动发现、表名/主键映射、运行模式。
  - IO 层:
      - 连接器: 文件发现（file_connector.py）按配置匹配路径与模式。
      - 读取器: Excel 读取（excel_reader.py）做表头标准化、稳健
  解析。
      - 装载器: 仓库写入（warehouse_loader.py）支持 plan-only 生
  成 SQL 计划与 execute 事务提交，处理 delete_insert/append、主键与
  批次。
  - 领域层: Pydantic 模型与纯函数服务（如 annuity_performance）；聚
  焦业务校验、清洗与字段映射，避免编排耦合。
  - 编排层（薄封装）:
      - Ops: 将发现→读取→处理→加载以最小形态封装（ops.py），统一配
  置校验、结构化日志。
      - Jobs/CLI: 组合 ops 为作业并提供统一 CLI（jobs.py），本地使
  用 execute_in_process 运行，无需 Dagster 后台。
      - Dagster 注册: repository.py 暴露 Definitions，便于将来启用
  UI/daemon；schedules.py 与 sensors.py 作为样例占位，按需启用。
  - 工具与类型: 公共类型、工具函数，保证类型安全与可测试性。

  整体工作流

  - 触发方式:
      - 当下推荐: CLI-first 手动或由计划任务/cron 调用。
      - 未来（条件满足时）: Dagster 的 schedule/sensor 触发，提供运
  行历史与回填。
  - 执行链路:
      - discover_files_op: 基于 data_sources.yml 发现匹配文件列表。
      - read_excel_op / read_and_process_*: 读取 Excel 行数据，做表
  头标准化。
      - process_*_op: 进入领域服务进行校验与转换，输出 JSON 友好结
  构（alias/排空）。
      - load_op: plan-only 生成 SQL 计划或 execute 进行事务写入
  （delete_insert/append），统计删除/插入/批次数。
  - 观测与安全:
      - 统一日志输出、运行结果摘要与（计划模式）SQL 预演；执行模式
  严格依赖 DDL 和 DSN，先跑 plan-only。

  运行模式（KISS/YAGNI）

  - CLI-first（当前）: 使用 uv run python -m
  src.work_data_hub.orchestration.jobs 即可，--plan-only 安全演
  练，--execute 实际写库。
  - 简单定时（按需）: 通过系统计划任务/cron 调用 CLI，够用且易
  维护。
  - Dagster UI/Daemon（延后）: 仅当以下任一条件满足再启用：
      - 多域（≥3）+ 稳定定时与回填需求；
      - 文件到达即触发、跨域依赖或并发/资源治理；
      - 需要 UI 面向非工程用户展示运行历史、定位与重跑；
      - 需要系统化告警、重试与审计追踪（run history/lineage）。

  如需，我可以继续补一个简短的计划任务/cron 示例脚本（Windows/Linux
  各一）用于托管当前 CLI 触发。


  小样本数据集（从真实样本派生）

  - tests/fixtures/sample_data/annuity_subsets/
      - 2024年11月年金终稿数据_subset_distinct_5.xlsx：5 行，PK 全
  部唯一（验证 delete_insert 与 append 的基础计数）。
      - 2024年11月年金终稿数据_subset_overlap_pk_6.xlsx：6 行，
  3 个唯一 PK（每个重复 2 次，用于验证“先删后插”的删除量按唯一 PK
  计数）。
      - 2024年11月年金终稿数据_subset_append_3.xlsx：3 行（append
  非覆盖写入基础用例）。

  生成与运行（复制即可）

  - 生成小数据集
      - uv run python -m scripts.testdata.make_annuity_subsets --src tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx --sheet 规模明细
  - E2E 计划模式（默认 PK）
      - WDH_DATA_BASE_DIR=tests/fixtures/
  sample_data/annuity_subsets uv run python -m
  src.work_data_hub.orchestration.jobs --domain annuity_performance
  --plan-only --max-files 1
  - 运行时覆盖 PK
      - WDH_DATA_BASE_DIR=tests/fixtures/
  sample_data/annuity_subsets uv run python -m
  src.work_data_hub.orchestration.jobs --domain annuity_performance
  --plan-only --max-files 1 --mode delete_insert --pk "月度,计划
  代码"
  - 非覆盖写入（append）
      - WDH_DATA_BASE_DIR=tests/fixtures/
  sample_data/annuity_subsets uv run python -m
  src.work_data_hub.orchestration.jobs --domain annuity_performance
  --plan-only --max-files 1 --mode append