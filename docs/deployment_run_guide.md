# WorkDataHub 部署与运行指南

本文档详细介绍了 WorkDataHub 项目的基础环境配置、部署流程，以及核心业务数据流水线（ETL+MDM）的运行方式。本项目推荐且默认使用 `uv` 进行极速的 Python 环境依赖管理。

> [!TIP]
> **Shell 环境说明**：本文档所有命令同时提供 **Bash / PowerShell** 与 **CMD** 两种写法。
> - `\` 续行符 → Bash / PowerShell 通用
> - `^` 续行符 → Windows CMD 专用
> - 请根据你使用的终端选择对应代码块。

> **相关文档导航**
> - [数据处理指南](data_processing_guide.md) — ETL 六阶段处理机制、核心系统机制与业务领域详解
> - [实盘数据验证指南](verification_guide_real_data.md) — 端到端数据验证 SQL 与排障手册
> - [数据库 Schema 全景图](database-schema-panorama.md) — 表结构、ER 图与 Schema 分层说明

---

## 一、 环境准备

### 1.1 前置条件

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | ≥ 3.10 | 项目运行时 |
| PostgreSQL | ≥ 14 | 主数据库（业务输出目标） |
| Git | latest | 版本控制 |
| uv | latest | Python 包解析器与运行器 |

### 1.2 安装 uv

`uv` 是一个完全由 Rust 编写的极速 Python 包解析器和安装器，能够显著加快依赖准备过程。

- **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 1.3 获取代码与初始化环境

获取代码库之后，请执行以下命令搭建虚拟环境与代码提交钩子。

**Bash / PowerShell：**
```bash
# 1. 克隆代码库并进入项目
git clone <repository_url>
cd WorkDataHub

# 2. 使用 uv 创建虚拟环境并同步/安装所有的项目依赖
uv sync

# 3. 安装 pre-commit 钩子
uv run pre-commit install
```

**CMD：**
```cmd
git clone <repository_url>
cd WorkDataHub
uv sync
uv run pre-commit install
```

> [!NOTE]
> **内网离线环境**：如果部署环境无法访问外部 PyPI（如公司内网隔离），所有依赖（含中文 Windows 所需的 psycopg v3）已预下载至 `vendor/wheels/` 目录。请参阅 [内网部署与运行指南](deployment_run_guide_intranet.md)，该文档完整覆盖内网环境下的依赖安装、配置与 CLI 运行全流程。

### 1.4 环境变量配置

项目的数据库连接、外部配置路径及 Python 导入路径均通过环境变量文件注入。

1. 在项目根目录新建 `.wdh_env` 文件。
2. 填补以下核心配置项：

```env
# 【必须】将 src 目录加入 Python 路径，确保可正确 import 内部模块
PYTHONPATH=src

# 【必须】PostgreSQL 主数据库连接地址
DATABASE_URL=postgresql://user:password@localhost:5432/postgres

# 【可选】天眼查 API Key（外部企业检索服务，内网离线环境可跳过）
EQC_API_KEY=your_api_key_here

# 【可选】Playwright 浏览器路径（auth refresh 命令使用）
# 若未安装 Playwright 自带 Chromium（如内网环境），可指向系统 Edge/Chrome
# PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
```

> [!CAUTION]
> `.wdh_env` 文件包含数据库凭证，**不要**提交到 Git。请确保 `.gitignore` 中已忽略此文件。

> [!WARNING]
> **Windows 路径配置防坑**：在 `.wdh_env` 中配置目录路径（如 `WDH_DATA_BASE_DIR`）时，**千万不要直接复制不带引号的反斜杠路径**（如 `D:\Share\Data`），这会导致 uv 环境变量解析失败（报 `Failed to parse environment file`），进而导致 `PYTHONPATH=src` 失效，爆出 `ModuleNotFoundError: No module named 'work_data_hub'`。
> 
> **正确写法**（二选一）：
> 1. 用单引号包裹：`WDH_DATA_BASE_DIR='D:\Share\Data'`
> 2. 将反斜杠改为正斜杠：`WDH_DATA_BASE_DIR=D:/Share/Data`

---

## 二、 数据库部署

本项目采用**双数据库架构**，利用 Alembic 进行 ORM 模型的 Schema 迁移管理。

| 数据库 | 角色 | 读写权限 |
|--------|------|----------|
| **legacy** | 历史数据源（从原 MySQL 迁移） | 只读 |
| **postgres** | 主数据库（ETL 输出目标） | 读写 |

> [!IMPORTANT]
> **所有的 Schema 数据定义更新均不能使用直接的 DDL，必须通过 Alembic！**

**Bash / PowerShell：**
```bash
uv run --env-file .wdh_env alembic upgrade head
```

**CMD：**
```cmd
uv run --env-file .wdh_env alembic upgrade head
```

更多迁移管理细节请参阅 [database-migrations.md](database-migrations.md)。

---

## 三、 原始数据目录规范

ETL 流水线通过 `config/data_sources.yml` 中的 glob 规则自动发现待处理的 Excel 报告。数据文件请按以下结构存放：

```
data/
└── real_data/
    ├── 202509/
    │   ├── 规模明细_202509.xlsx
    │   ├── 中标客户_202509_V2.xlsx
    │   └── 流失客户_202509.xlsx
    ├── 202510/
    │   └── ...
    └── 202511/
        └── ...
```

> **多版本文件**：当同一账期存在多个版本的 Excel（如 `V1` / `V2`），可通过 `--file-selection newest` 参数使系统自动挑选最新版本。详见 [3.2 节](#32-运行核心业务数据流转)。

---

## 四、 CLI 数据运行指南（ETL & Post-Hooks）

项目使用 Dagster 编排引擎与泛化业务抽象处理管线，通过 CLI 层高度封装以提供便捷访问。

> [!WARNING]
> 🚨 任何情况下不要单独使用系统默认的 `python`，**一律使用 `uv run` 去触发包含环境变量注入的执行上下文。**

### 4.1 常用诊断命令

**Bash / PowerShell：**
```bash
# 查看所有支持的域和命令参数
uv run --env-file .wdh_env python -m work_data_hub.cli etl --help

# 测试数据库可用性（仅执行连接测试）
uv run --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

**CMD：**
```cmd
uv run --env-file .wdh_env python -m work_data_hub.cli etl --help
uv run --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

### 4.2 运行核心业务数据流转

ETL 会按以下生命周期自动进行流转：

```
文件发现 → 数据读取 → 领域管线处理(清洗+企业解析) → 外键维表回填 → 关卡校验 → 最终入库 → Post-ETL Hooks
```

> 💡 各阶段的详细机制解析请参阅 [数据处理指南](data_processing_guide.md)。

**Bash / PowerShell：**
```bash
# 【试运行模式】Dry-Run：清洗逻辑运作，但最终拦截入库（排查清洗错误首选）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --dry-run

# 【单领域落地】真实写入并自动触发下游 Hook（客户合约同步及快照）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --execute

# 【全领域执行】一键处理（如遇多版本同账期 Excel，挑选 newest 最新）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains \
  --period 202510 \
  --file-selection newest \
  --execute
```

**CMD：**
```cmd
REM 【试运行模式】
uv run --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --dry-run

REM 【单领域落地】
uv run --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --execute

REM 【全领域执行】
uv run --env-file .wdh_env python -m work_data_hub.cli etl ^
  --all-domains ^
  --period 202510 ^
  --file-selection newest ^
  --execute
```

> [!IMPORTANT]
> **推荐执行顺序**：快照需要所有事实先行落定，故应按 `annual_award` → `annual_loss` → `annuity_performance` 顺序依次执行，或使用 `--all-domains` 一键处理。

### 4.3 Post-ETL Hook 链（自动级联处理）

当 `annuity_performance` 领域 ETL 完成后，系统会**自动依次触发**以下 Post-ETL Hook：

| 执行顺序 | Hook 名称 | 功能描述 |
|:---:|---|---|
| 1 | `contract_status_sync` | 从 `business."规模明细"` 同步合约状态到 SCD2 维表 `customer."客户年金计划"` |
| 2 | `year_init` | 仅 1 月触发，初始化当年 `is_strategic` / `is_existing` 标识 |
| 3 | `snapshot_refresh` | 刷新两张月度快照宽表（ProductLine 粒度 + Plan 粒度） |

**Bash / PowerShell：**
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --execute --no-post-hooks
```

**CMD：**
```cmd
uv run --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --execute --no-post-hooks
```

### 4.4 离线 / 无网降级运行

对于内网无法触达 EQC（天眼查）接口的环境，可以使用 `--no-enrichment` 关闭企业解析的外呼 API。系统会自动降级采用本地 DB Cache 与 `IN*` 生成逻辑兜底解析。

**Bash / PowerShell：**
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annual_award \
  --period 202510 \
  --no-enrichment \
  --execute
```

**CMD：**
```cmd
uv run --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annual_award ^
  --period 202510 ^
  --no-enrichment ^
  --execute
```

### 4.5 Customer MDM Post-Hooks 单独调用

若不随主 ETL 附带运行（如重构了快照配置或业务故障需手动修复），可以直接调用 MDM 工具钩子：

**Bash / PowerShell：**
```bash
# 1. 手动从 "规模明细" 反推 SCD2（渐变维）合约有效状态
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync

# 2. 手动依据事实计算生成指定账期的"客户/计划"月度管理看板快照
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202510
```

**CMD：**
```cmd
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202510
```

---

## 五、 CLI 参数快速参考

| 参数 | 说明 | 示例 |
|------|------|------|
| `--domain` | 单个域名称 | `--domain annuity_performance` |
| `--domains` | 多个域名称（逗号分隔） | `--domains annuity_performance,annuity_income` |
| `--all-domains` | 执行所有已注册域 | |
| `--period` | 指定处理月份（YYYYMM 格式） | `--period 202510` |
| `--dry-run` | 试运行，不写入数据库 | |
| `--execute` | 执行模式，写入数据库 | |
| `--no-enrichment` | 禁用 EQC API 调用（离线模式） | |
| `--no-post-hooks` | 禁用 Post-ETL Hooks | |
| `--file-selection` | 多版本文件选择策略：`error`（默认）/ `newest` / `oldest` | `--file-selection newest` |
| `--check-db` | 仅检查数据库连接 | |

---

## 六、 可视化监控（Dagster UI）

基于 Dagster 框架，可以将数据处理过程完全可视化。

**Bash / PowerShell：**
```bash
uv run --env-file .wdh_env dagster dev
```

**CMD：**
```cmd
uv run --env-file .wdh_env dagster dev
```

启动后在浏览器打开 `http://localhost:3000`，你将获得以下关键能力：

1. 直观地查看各个管道节点（Op）的执行拓扑图。
2. 检索并排查包含 "Company ID resolution" 与 "FK Backfill" 等核心环节记录的丰富结构化日志。
3. 追踪各账期数据的执行效率，以及捕获 Pandera 数据架构验证时的拦截异常。

---

## 七、 配置文件速查

项目采用**配置驱动**（Config-driven）的设计理念，核心行为均通过 YAML 配置文件声明。

| 配置用途 | 文件路径 | 说明 |
|----------|----------|------|
| 数据源发现模式 | `config/data_sources.yml` | glob 路径、域注册、Sheet 合并规则 |
| FK 回填规则 | `config/foreign_keys.yml` | 聚合算子（max_by, concat_distinct 等） |
| 参考数据同步 | `config/reference_sync.yml` | legacy → postgres 数据同步 |
| 公司硬编码映射 | `config/mappings/company_id/` | Layer 1 强制覆盖字典 |
| EQC 匹配类型置信度 | `config/eqc_confidence.yml` | API 结果评分阈值 |
| 客户状态规则 | `config/customer_status_rules.yml` | 快照状态评定引擎规则 |
| 客户 MDM 配置 | `config/customer_mdm.yaml` | Hook 触发与同步设置 |
| 环境变量 | `.wdh_env` | 数据库连接、PYTHONPATH |

---

## 八、 代码规约与开发测试

> 本项目采用 **NO LEGACY SUPPORT** 策略。开发者拥有随时打破旧 API 并进行整体替换/重构的独立权限，前提是务必通过以下质量检查。

### 8.1 代码质量检查

**Bash / PowerShell：**
```bash
uv run ruff check src/
uv run ruff format --check src/
uv run mypy src/
```

**CMD：**
```cmd
uv run ruff check src\
uv run ruff format --check src\
uv run mypy src\
```

### 8.2 运行测试

**Bash / PowerShell：**
```bash
# 运行全量测试用例
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/ -v

# 仅运行单元测试
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/ -v -m unit

# 运行特定模块测试
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/io/schema/ -v
```

**CMD：**
```cmd
REM 运行全量测试用例（先设置环境变量）
set PYTHONPATH=src
uv run --env-file .wdh_env pytest tests\ -v

REM 仅运行单元测试
set PYTHONPATH=src
uv run --env-file .wdh_env pytest tests\ -v -m unit

REM 运行特定模块测试
set PYTHONPATH=src
uv run --env-file .wdh_env pytest tests\io\schema\ -v
```

> [!NOTE]
> CMD 中无法使用 `PYTHONPATH=src` 内联前缀，需先通过 `set PYTHONPATH=src` 设置，或确保 `.wdh_env` 文件中已包含 `PYTHONPATH=src`（推荐做法，则无需手动 set）。

> **测试标记说明**：项目使用 pytest markers 区分测试级别——`unit`（快速单元测试）、`integration`（需数据库）、`postgres`（需 PostgreSQL）、`e2e_suite`（端到端，需环境变量 `RUN_E2E_TESTS=1`）。

### 8.3 硬性编码约束

| 约束项 | 阈值 |
|--------|------|
| 文件最大行数 | 800 行 |
| 函数最大行数 | 50 行 |
| 类最大行数 | 100 行 |
| 行最大字符数 | 88 字符 |
| 函数最大语句数 | 50 |
| 最大圈复杂度分支 | 12 |

---

## 九、 常见问题与排障

| 问题现象 | 排查方向 |
|----------|----------|
| ETL 时 `Candidates found: 0` | `config/data_sources.yml` 的 glob 规则未匹配到文件，检查路径和递归通配符 `**/*.xlsx` |
| 大量 `IN*` 临时 company_id | EQC 解析未命中，考虑在 `config/mappings/company_id/` 添加手工映射 |
| 业务字段计算错误（如日期、业务类型） | 检查 `src/work_data_hub/domain/<domain>/pipeline_builder.py` 中的 TransformStep |
| 主拓、标签、客户类型聚合不正确 | 检查 `config/foreign_keys.yml` 中的聚合算子配置（max_by / concat_distinct） |
| 快照状态与事实不匹配 | 检查 `config/customer_status_rules.yml` 中 match_fields 是否与明细表列名对齐 |
| `contract_status` 全为 NULL | 确认 `contract_status_sync` Hook 已执行（未使用 `--no-post-hooks`） |
| `aum_balance = 0` 但规模明细有数据 | 确认 `snapshot_month` 格式为月末日期（如 `2025-10-31`），日期必须对齐 |
| `alembic upgrade head` 报 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6` | 中文 Windows（GBK 区域）下 psycopg2 的 C 扩展无法解码 libpq 返回的信息。安装 `psycopg`（v3）：`uv pip install psycopg`，项目已自动切换驱动 |

> 更多详尽的验证 SQL 与端到端一致性校验流程，请参阅 [实盘数据验证指南](verification_guide_real_data.md)。
