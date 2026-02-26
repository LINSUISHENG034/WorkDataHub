# Customer 数据库结构与 ETL 逻辑分析报告

## 1. 梳理范围与面 (Overview of Aspects)

经过对项目代码（`src/work_data_hub/customer_mdm`）、数据库迁移脚本（`io/schema/migrations/versions`）以及相关配置文件（`config`）的扫描，与 `customer` 数据库模式（Schema）相关的结构和 ETL 逻辑主要包括以下几个面：

1. **基础表结构 (Table Structures)**
   - 基础维度表: `customer."年金关联公司"` (前身为"年金客户")
   - 外部数据明细表: `customer.当年中标`, `customer.当年流失`
   - 核心状态拉链表: `customer.customer_plan_contract` (支持 SCD Type 2)
   - 月度快照事实表: `customer.fct_customer_product_line_monthly` (产品线粒度), `customer.fct_customer_plan_monthly` (计划粒度)
2. **ETL 处理逻辑 (ETL Logic)**
   - 外部 Excel 数据加载 (依赖 `data_sources.yml` 配置)
   - 拉链层同步 (SCD Type 2 Sync，由 `contract_sync.py` 驱动)
   - 月度快照加工 (由 `snapshot_refresh.py` 驱动，并结合 YAML 规则引擎 `status_evaluator.py`)
3. **数据库级触发器 (Database Triggers)**
   - 用于冗余字段名称修改时的同步更新。

---

## 2. 逐一细化分析 (Detailed Analysis)

### 2.1 表结构详细解析 (Table Structures)

#### 2.1.1 核心状态拉链表: `customer.customer_plan_contract`
- **粒度**: 关联公司 (company_id) + 计划 (plan_code) + 产品线 (product_line_code)。
- **SCD Type 2 设计**:
  - `valid_from` 和 `valid_to` 用于标记记录生命周期，当前生效数据的 `valid_to = '9999-12-31'`。
  - 核心状态字段：`contract_status` (正常/停缴)。
  - 战略/老客标记：`is_strategic` (是否战略客户), `is_existing` (是否已客), `status_year`。
- **冗余字段**: 包含 `product_line_name`, `customer_name`, `plan_name`，为了查询方便产生了反规范化，并在 DB 层利用 Trigger (`sync_contract_customer_name` 等) 强制同步更新名称变化。

#### 2.1.2 快照事实表 (Snapshot Fact Tables)
因业务诉求（对应 Story 7.6-16），快照表设计了双表粒度分离：
1. **`customer.fct_customer_product_line_monthly`（产品线粒度）**:
   - 对 `customer_plan_contract` 聚合，包含累计的 AUM (`aum_balance`)、计划数 (`plan_count`)。
   - 基于配置衍生的状态字段：`is_winning_this_year`, `is_churned_this_year`, `is_new`。
   - `is_strategic` 和 `is_existing` 状态依赖于底表 BOOL_OR 聚合。
2. **`customer.fct_customer_plan_monthly`（计划粒度）**:
   - 包含计划层级的 `is_churned_this_year`，当前 `contract_status` 和 `aum_balance`。

#### 2.1.3 外部数据明细表: `customer.当年中标` 与 `customer.当年流失`
- **来源**: 数据录入人员整理的 "*当年中标*.xlsx" 和 "*当年流失*.xlsx" 表格。
- **作用**: 供状态规则引擎判断 `is_winning_this_year` 及 `is_churned_this_year` 时进行 EXISTS 子查询。

### 2.2 ETL 处理逻辑解析 (ETL Logic)

#### 2.2.1 状态同步与拉链维护 (`contract_sync.py`)
主要将 `business.规模明细` 转换为 `customer_plan_contract` 的版本更迭。
- **Step 1 (Update)**: 调用 `close_old_records.sql`。只有当 `contract_status`、`is_existing` 发生实质改变，或者 `is_strategic` **从 FALSE 变为 TRUE** 时，才会关闭最新记录（置 valid_to 为昨天的日期）。
- **特有业务逻辑 - Ratchet Rule (棘轮法则)**：要求战略客户只升不降（代码里体现为只有 `old.is_strategic = FALSE AND new.is_strategic = TRUE` 时才发生拉链截断）。
- **12个月滚动供款校验**: 在 `common_ctes.sql` 的 `contribution_12m` CTE 中，回溯过去 12 个月规模明细的供款总和，作为是否“停缴”的判别因子。

#### 2.2.2 月度快照组装 (`snapshot_refresh.py` & `status_evaluator.py`)
- **配置驱动的 SQL 生成**: 摒弃了硬编码状态计算，使用 YAML (`config/customer_status_rules.yml`) 来配置衍生状态判定。`StatusEvaluator` 会将 YAML 中如 `exists_in_year`, `aggregated_field` 等类型转化为 SQL 片段（生成大量的 `EXISTS (SELECT 1 ...)` 和 JOIN 逻辑）。
- **Idempotent Upsert (幂等更新)**: `snapshot_refresh.py` 向两个事实快照表中执行 `INSERT ... ON CONFLICT (...) DO UPDATE`。

---

## 3. 进一步优化和重构建议 (Optimization & Refactoring Suggestions)

结合实际代码与架构原则，现有的设计有较大的闪光点（例如 SCD Type 2 历史追溯、配置驱动的状态逻辑），但在可维护性、性能与职责边界上依然有优化空间：

### 3.1 架构分析与 dbt 引入评估 (Architecture & dbt Evaluation)
- **现状**: 目前大量复杂的清洗、校验、拉链表运算通过自建的 Python 脚本串联（读取文件 → 加载 SQL → `psycopg` 裸执行，并结合 YAML 进行规则解析）。
- **关于引入 dbt 的必要性评估**: 结合项目内网部署的网络受限环境，以及极简设计原则（KISS & YAGNI），**当前不建议引入 dbt**。
  - **部署与运维成本过高**: dbt 会增加构建、打包的负担。在受限的生产内网中引入和维护一个新的工具栈（特别是涉及各类 dbt adapter 依赖时），将极大地增加项目的部署复杂度和运维心智负担。
  - **现有方案已具备 "Mini-dbt" 的雏形**: 当前基于 `status_evaluator.py` 的 YAML 动态 SQL 生成引擎，已经实现了逻辑配置化管理。在当前数据量级和业务复杂度下，它足以胜任 Transform 环节并且完全自主可控，无需为暂时用不到的血缘分析等高级功能引入重量级框架。

### 3.2 配置驱动的局限性与统一架构演进策略 (Limits of Config-Driven & Evolution of Unified Architecture)
- **从 "万物皆配置" 的迷思中解脱**: 
  - **局限性**: 试图将所有的业务逻辑（如复杂的开窗函数、时间滑窗匹配、12个月滚动求和等分析型 SQL）全部塞入 `customer_status_rules.yml` 这样的配置文件中是不切实际的，也是违背 **KISS** 原则的。如果我们为了处理这些复杂逻辑而在 YAML 中去发明大量诸如 `condition`, `aggregation`, `operator` 的嵌套语法，不仅导致调试困难、缺乏编译期检查，更是变相在 YAML 里发明了一门缺乏约束的 "方言" 编程语言 (AST in YAML)。
  - **现状痛点**: 目前项目中的规则正处于分裂状态（简单判定逻辑在 YAML，Ratchet Rule 这种特定分支在 SQL WHERE，"十二个月滚动供款" 的时间滑窗在 SQL CTE 内）。

- **建议：构建务实的分层统一架构 (Pragmatic Layered Architecture)**
  如果在未来有更多的业务逻辑加入，为了保持架构的统一性和长期可维护性，应该明确划分系统的边界，而非追求单一技术的包打天下。具体的分层架构如下：
  1. **配置层 (Configuration Layer - YAML)**:
     - **职责**: 只负责维护简单的阈值设定（如 `5 亿`、`TOP 10`）、开关、源表元数据信息的映射定义，或者极简的 “如果A=1则B=2” 的字典转换。
     - **特点**: 让业务人员可以直观看到参数，剥离环境差异。
  2. **数据转换层 (Data Transformation Layer - SQL + 轻量级模板引擎)**:
     - **职责**: 承担一切**集合运算**、**复杂计算逻辑**。例如连续 12 个月的滚动业绩求和、同类产品线的排名、上下期状态的关联对比。
     - **实现**: 强烈建议引入内置的 `Jinja2`，将之前硬编码的各种 SQL Snippets (`common_ctes.sql`, `close_old_records.sql`) 参数化和模板化。这样不仅消灭了散乱的 `.sql` 裸文件拼接，还能够复用计算逻辑，同时 SQL 的语义依旧保留，可被所有 Data IDE 原生支持解析。
  3. **编排与执行引擎层 (Execution Layer - Python Core)**:
     - **职责**: 读取解析 YAML 参数与 Jinja 模板，管理数据库连接池 (psycopg)，编排数据加载顺序（DAG 雏形），并记录运行日志。
     - **实现**: 面向具体的业务模式设计 `Strategy Pattern`（策略模式），例如抽象出一个 `StatusEvaluationStrategy` 的接口类。如果有未来新型的或极度复杂的计算指标，通过实现该接口并外挂到系统内的方式来进行扩展，从而遵守 **开闭原则 (Open/Closed Principle)**。

通过清晰的三层划分：**配置管常量、SQL管运算、Python管编排与扩展**，才能形成一套真正具备韧性且长效统一的架构。

### 3.3 数据库模型与触发器重构 (Remove Trigger-based Denormalization)
- **现状**: 在 `008_create_customer_plan_contract.py` 中，强行冗余了 `customer_name` 及 `plan_name` 等字段，并且为保证一致性，在 Postgres 里加了 `sync_contract_customer_name` 一类的触发器 (Trigger)。这带来了数据库层面的隐式性能开销及维护死角。
- **建议**:
  - **恢复规范化**: 基础主表（无论是拉链表还是快照）不应直接保存且同步修改维度的文本字段，应仅保留主键 `company_id`、`plan_code`。
  - **采用维度视图呈现**: 在下游应用或 BI 工具直接采用 View (视图) `JOIN customer."年金关联公司"` 和 `mapping."年金计划"`，完全可以屏蔽展示名字的需求，同时避免复杂的 DB 层触发器。

### 3.4 状态评估引擎 (StatusEvaluator) 性能预警与优化
- **现状**: 目前的 `status_evaluator.py` 为每个记录生成 `EXISTS (SELECT 1 FROM 业务表明...)` 大量子查询。例如在判断是否 "新到账" 或 "流失" 时产生复杂的嵌套查询。
- **建议**: 可以优化 SQL 引擎向生成以 `LEFT JOIN` 替代相关子查询，或者将高频校验的状态前置计算为临时宽表，再合并写入快照表中，以减少数据量增多后的全表扫描与 CPU 开销。

### 3.5 数据库表命名规范统一 (Table Naming Standardization)
- **现状痛点**: 目前 `customer` 模式（Schema）下的表名存在中英文混用的现象（如 `customer_plan_contract` 和 `"年金关联公司"`、`"当年流失"` 并存）。中英文混用以及直接使用中文作为物理表名是不符合数据库设计规范的（Anti-Pattern），可能会在各类 ORM 框架、BI 工具对接或跨库迁移时引发编码和转义强依赖问题。另外，诸如 `当年流失` 和 `当年中标` 这两个表名，带有显著的相对时间色彩（“当年”），而实际上这些表中存储的是带有 `上报月份` 维度的跨期数据，名称含有误导性。
- **建议: 物理表名全英文重构与清晰化语义更名**
  - **坚持物理表英文，逻辑注释中文**: 所有物理表名和字段名必须统一下划线全小写英文（Snake Case）。表或列的中文含义应通过数据库原生的 `COMMENT ON TABLE / COLUMN` 注释机制进行管理，将业务语义从表名中剥离为独立元数据。
  - **针对性更名建议 (配合你提出的清晰化语义)**: 
    1. **`customer."年金关联公司"`** -> 建议统一为英文表名 `customer.customer_company`。
    2. **`customer."当年流失"`** -> **非常赞同**将其业务概念修正为 `流失客户明细`，这直接消除了“当年”带来的时间维度误导。对应的物理表名建议使用 `customer.churned_customer_detail`。
    3. **`customer."当年中标"`** -> **非常赞同**将其业务概念修正为 `中标客户明细`。对应的物理表名建议使用 `customer.won_customer_detail`。

---
完成时间：2026-02-25
分析方式：全盘代码与 SQL DDL 分析
