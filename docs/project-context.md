# Project Context & Development Standards

## 0. 🤖 AI Agent Persona & Prime Directives

**Role:** You are a Senior Python Architect working in a strict **Pre-Production** environment.
**Primary Goal:** Deliver clean, modular, and maintainable code.
**Critical Constraint:** **NO LEGACY SUPPORT.** You have full authority to refactor, break APIs, and change schemas to achieve the best design.

---

## 1. 📏 Hard Constraints (Strictly Enforced)

_Violating these requires immediate self-correction._

### Code Structure Limits

- **File Size:** **MAX 800 lines**. _Action:_ If a file exceeds this, split it into sub-modules immediately.
- **Function Size:** **MAX 50 lines**. _Action:_ Extract logic into private helper functions.
- **Class Size:** **MAX 100 lines**. _Action:_ Use composition over inheritance; split large classes.
- **Line Length:** **MAX 88 characters** (Matches `ruff` config in pyproject.toml).

### Code Smell Prevention

- **Pre-commit Hooks:** Run `pre-commit install` in project root (one-time setup per clone).
  - All commits must pass `scripts/quality/check_file_length.py` (max 800 lines) and Ruff checks.
  - **Bypass Policy:** Use `git commit --no-verify` ONLY for emergency hotfixes.
  - See `docs/sprint-artifacts/stories/7-6-ci-integration-code-quality-tooling.md` for setup details.
- **Domain-Growth Modules:** Modules like `domain_registry.py` should be pre-modularized when domain count increases.
  - See `docs/sprint-artifacts/stories/7-5-domain-registry-pre-modularization.md` for modularization pattern.
- **Complexity Checks:** Ruff PLR rules enforce code complexity limits:
  - `max-statements = 50` (per function, aligns with MAX 50 lines guideline)
  - `max-branches = 12` (cyclomatic complexity threshold)

### Development Philosophy

- **Zero Legacy Policy:**
- ❌ **NEVER** keep commented-out code or "v1" backups. Delete them.
- ❌ **NEVER** create wrappers for backward compatibility.
- ✅ **ALWAYS** refactor atomicaly: Update the definition AND all call sites in one go.

- **KISS & YAGNI:** Implement only what is currently needed. No speculative features.

---

## 2. 🛠️ Tooling & Environment Standards

### Python Execution (Run via `uv`)

**Rule:** Never run `python` directly. Always use the project manager `uv`. Pre-requisite: Ensure `.wdh_env` contains `PYTHONPATH=src`.

- **Standard Command:**Use the env-file to automatically load PYTHONPATH and other configs.

```bash
uv run --env-file .wdh_env src/your_script.py

```

- **Dependency Management:** Do not use pip directly. Use `uv add` or `uv remove`.

### File Operations

**Priority Order:**

1. 🥇 **Agent Native Tools:** ALWAYS prefer using `read_file`, `write_file`, `replace_in_file` provided by your environment.
2. 🥈 **Shell Commands:** Use only if native tools are insufficient.

---

## 3. 💻 Shell Command Protocols (Context Aware)

**DETECT YOUR ENVIRONMENT BEFORE EXECUTING SHELL COMMANDS:**

### Scenario A: You are a "Bash Tool" Agent (e.g., Claude Code, Linux/WSL Context)

- **Environment:** Unix/Linux/WSL.
- **Allowed:** `rm`, `ls`, `cp`, `mv`, `test`, `mkdir -p`.
- **FORBIDDEN:** Windows CMD commands (`del`, `dir`, `copy`).
- **Example:**

```bash
# ✅ Correct
test -f "data.json" && rm "data.json"

```

### Scenario B: You are a "PowerShell" Agent (e.g., Windows Native CLI)

- **Environment:** Windows PowerShell.
- **Allowed:** `Remove-Item`, `Get-ChildItem`, `Test-Path`, or aliases (`rm`, `ls`, `mv`).
- **FORBIDDEN:** Unix specific syntax like `[ -f ... ]`, `export`, `source`.
- **Example:**

```powershell
# ✅ Correct
if (Test-Path "data.json") { Remove-Item "data.json" }

```

---

## 4. 🏗️ Design Principles (Pythonic)

- **Dependency Inversion:** Depend on abstractions, not concretions.
- **Fail Fast:** Raise customized exceptions (`ValueError`, `RuntimeError`) immediately upon invalid state.
- **Type Hinting:** All function signatures **must** include Python type hints.
- **Docstrings:** All public modules, classes, and functions **must** have a descriptive docstring.

---

## 5. 📊 Reference Documentation

### Database Architecture

本项目采用**双数据库架构**：

| 数据库       | 角色                         | 读写权限 |
| ------------ | ---------------------------- | -------- |
| **legacy**   | 历史数据源 (从原 MySQL 迁移) | 只读     |
| **postgres** | 主数据库 (ETL 输出目标)      | 读写     |

> **详细文档:** 完整的 Schema 定义、表结构、ER 图、数据流架构请参见 **[Database Schema Panorama](database-schema-panorama.md)**。

### Key Architecture Files

> **Epic 7 Modularization (2025-12-22):** 大文件已按模块化原则拆分为包结构。

| Package / File                                 | Purpose                                              |
| ---------------------------------------------- | ---------------------------------------------------- |
| `src/work_data_hub/infrastructure/schema/`     | Domain Registry Package - 域 Schema 定义的唯一真相源 |
| `src/work_data_hub/orchestration/ops/`         | ETL Operations Package - Pipeline 编排与执行         |
| `src/work_data_hub/infrastructure/enrichment/` | Company Enrichment Package - 公司 ID 解析服务        |
| `src/work_data_hub/io/loader/`                 | Database Loader Package - 数据库写入服务             |
| `src/work_data_hub/io/connectors/eqc/`         | EQC Client Package - 企查查 API 客户端               |
| `src/work_data_hub/io/connectors/discovery/`   | File Discovery Package - 文件发现服务                |
| `src/work_data_hub/cli/etl/`                   | ETL CLI Package - 命令行界面                         |
| `config/data_sources.yml`                      | 域文件发现模式配置                                   |
| `config/foreign_keys.yml`                      | FK 回填配置                                          |
| `config/reference_sync.yml`                    | 参考数据同步配置 (legacy → postgres)                 |
| `config/company_mapping.yml`                   | Layer 1 硬编码公司映射                               |

---

## 6. 🏗️ Domain Registry Architecture

> **Epic 7.4 (2025-12-30):** 引入 Registry Pattern 替代硬编码 if/elif 分发，实现配置驱动的域管理。

### Overview

Domain Registry 架构通过**单一真相源（Single Source of Truth）**管理所有 ETL 域的元数据和配置，遵循**开闭原则（OCP）**，使得添加新城无需修改分发逻辑。

**核心改进：**

- **添加新城**: 从 5-7 个文件 → 2-3 个文件
- **消除硬编码**: 移除 `executors.py` 中的 if/elif 链
- **配置驱动**: `data_sources.yml` 声明式配置域能力

### Registries

#### JOB_REGISTRY (`orchestration/jobs.py`)

**作用**: 将域名映射到 Dagster Job 定义及域能力。

```python
@dataclass(frozen=True)
class JobEntry:
    job: Any  # Dagster JobDefinition
    multi_file_job: Optional[Any] = None  # max_files > 1 场景
    supports_backfill: bool = False  # 是否配置了 FK 回填

JOB_REGISTRY: Dict[str, JobEntry] = {
    "annuity_performance": JobEntry(
        job=annuity_performance_job,
        supports_backfill=True,
    ),
    "annuity_income": JobEntry(
        job=annuity_income_job,
        supports_backfill=True,
    ),
}
```

**CLI 使用**: `executors.py` 通过 `JOB_REGISTRY.get(domain)` 查找 Job，消除 if/elif 分发。

#### DOMAIN_SERVICE_REGISTRY (`orchestration/ops/pipeline_ops.py`)

**作用**: 将域名映射到域处理服务函数及支持的能力。

```python
@dataclass(frozen=True)
class DomainServiceEntry:
    service_fn: Callable[[List[Dict]], Any]  # 处理函数
    supports_enrichment: bool = False  # 是否支持公司ID解析
    domain_name: str = ""  # 人类可读域名

DOMAIN_SERVICE_REGISTRY: Dict[str, DomainServiceEntry] = {
    "annuity_performance": DomainServiceEntry(
        service_fn=process_with_enrichment,
        supports_enrichment=True,
        domain_name="Annuity Performance (规模明细)",
    ),
}
```

**Ops 使用**: `process_domain_op` 通过 registry 动态委托到域服务，无需为每个域创建专用 op。

### Configuration

#### `requires_backfill` (config/data_sources.yml)

声明式配置域是否需要 FK 回填：

```yaml
defaults:
  requires_backfill: false # 默认不需要回填

domains:
  annuity_performance:
    requires_backfill: true # 显式启用回填
    base_path: "..."
```

**消除硬编码**: 移除 `config.py:157` 中的域列表判断逻辑。

### Startup Validation

**函数**: `cli/etl/domain_validation.py:validate_domain_registry()`

**检查**: `data_sources.yml` 中的域是否都在 `JOB_REGISTRY` 中注册，防止配置不一致。

```python
# CLI 启动时自动验证
if data_sources_domains - registry_domains:
    warnings.warn(f"Domains in data_sources.yml without jobs: {missing}")
```

### Adding a New Domain (Post-Epic 7.4)

**最小步骤**（仅 2-3 个文件）：

1. **创建域包**: `src/work_data_hub/domain/{new_domain}/`（必须）
2. **配置数据源**: `config/data_sources.yml` 添加域条目（必须）
3. **配置 FK 回填**（可选）: `config/foreign_keys.yml`

**无需修改的文件**（Epic 7.4 前）：

- ❌ `orchestration/jobs.py` - 通过 `JOB_REGISTRY` 自动注册
- ❌ `cli/etl/executors.py` - 无需添加 elif 分支
- ❌ `cli/etl/config.py` - 通过 `requires_backfill` 配置

### Related Documentation

- **[Domain Registry Architecture](architecture/domain-registry.md)** - 完整技术文档
- **[Sprint Change Proposal (Epic 7.4)](sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-30-domain-registry-architecture.md)** - 架构演进方案
- **[New Domain Checklist](specific/multi-domain/new-domain-checklist.md)** - ✅ RESOLVED (Epic 7.4 已解决)

---

## 7. 🔍 Company Enrichment (公司 ID 解析)

ETL Pipeline 的核心能力是将原始数据中的"客户名称"解析为标准化的 `company_id`。

### EQC API 置信度评分 (Story 7.1-8)

**配置文件:** `config/eqc_confidence.yml`

EQC API 返回的匹配结果根据匹配类型分配不同的置信度分数：

| 匹配类型 (type) | 置信度 | 说明                         |
| --------------- | ------ | ---------------------------- |
| 全称精确匹配    | 1.00   | 公司名称完全匹配，最高可靠性 |
| 模糊匹配        | 0.80   | 部分匹配或相似名称           |
| 拼音            | 0.60   | 拼音匹配，最低可靠性         |

**配置示例:**

```yaml
eqc_match_confidence:
  全称精确匹配: 1.00
  模糊匹配: 0.80
  拼音: 0.60
  default: 0.70

min_confidence_for_cache: 0.60 # 低于此分数的结果不会缓存到 enrichment_index
```

**影响范围:**

- **Layer 4 (EQC API):** API 查询结果根据 `type` 字段分配动态置信度
- **Layer 2 (DB Cache):** 低置信度结果（如 0.60 的拼音匹配）可以设置阈值过滤
- **Domain Learning:** 可根据置信度阈值过滤低质量匹配

**数据分布** (基于现有 `base_info` 数据):

- 全称精确匹配: 13 条 (confidence = 1.00)
- 模糊匹配: 107 条 (confidence = 0.80)
- 拼音: 5 条 (confidence = 0.60)

### 5 层解析架构

```
Input: 客户名称 / 计划代码 / 年金账户号 / 年金账户名
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: YAML Config (config/company_mapping.yml)          │
│  硬编码映射，优先级最高                                        │
└─────────────────────────────────────────────────────────────┘
       │ Miss
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: DB Cache (5种查找类型，按优先级)                    │
│  plan_code > account_name > account_number >                 │
│  customer_name > plan_customer                               │
└─────────────────────────────────────────────────────────────┘
       │ Miss
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: Existing Column                                    │
│  检查源数据中是否已有 company_id                               │
└─────────────────────────────────────────────────────────────┘
       │ Miss
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: EQC API (Synchronous)                              │
│  调用企查查 API，受预算控制，结果缓存到 Layer 2                │
└─────────────────────────────────────────────────────────────┘
       │ Miss
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: Temp ID (HMAC-SHA1)                                │
│  生成临时ID (IN_xxx 格式)，加入异步队列待后续解析              │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
Output: company_id (已解析或临时)
```

> **详细表结构:** Enrichment 相关表定义请参见 **[Database Schema Panorama](database-schema-panorama.md#2-schema-enterprise)**。

---

## 8. 📋 Domain Terminology (域术语对照)

本项目采用**双命名体系**：

| 标准域名称 (Code)     | 数据库表名 / Sheet 名 | Schema   | 说明             |
| --------------------- | --------------------- | -------- | ---------------- |
| `annuity_performance` | `规模明细`            | business | 年金业绩规模数据 |
| `annuity_income`      | `收入明细`            | business | 年金收入明细数据 |
| `annuity_plans`       | `年金计划`            | mapping  | 年金计划主数据   |
| `portfolio_plans`     | `组合计划`            | mapping  | 组合计划主数据   |

**命名约定：**

- **标准域名称** (`annuity_performance`): 用于代码、配置文件、CLI 参数
- **数据库表名** (`规模明细`): 沿用原 MySQL 表名，保持业务连续性
- 两者为**完全对等关系**，在 Domain Registry 中映射

---

## 9. 🏢 Customer MDM (客户主数据管理)

> **Epic 7.6 (2026-01):** 实现客户合同状态跟踪和月度快照生成，支持 Power BI 自助分析。

### Post-ETL Hook 架构

Customer MDM 通过 **Post-ETL Hook** 机制在 ETL 完成后自动触发数据同步：

```
ETL Pipeline (annuity_performance)
    │
    ▼
Post-ETL Hook Registry
    │
    ├── 1. contract_status_sync  → customer.customer_plan_contract
    │       (ON CONFLICT DO NOTHING)
    │
    └── 2. snapshot_refresh      → customer.fct_customer_product_line_monthly
                                   customer.fct_customer_plan_monthly
            (ON CONFLICT DO UPDATE)
```

**关键特性：**
- **执行顺序保证**: `contract_status_sync` 必须先于 `snapshot_refresh` 执行
- **幂等性**: 多次执行产生相同结果，支持安全重试
- **CLI 跳过**: 使用 `--no-post-hooks` 禁用自动触发

### CLI 命令

```bash
# ETL 自动触发 Hooks
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance --execute

# 禁用 Hooks (仅 ETL)
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance --execute --no-post-hooks

# 手动触发 Contract Sync
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync

# 手动触发 Snapshot Refresh
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202601
```

### 相关文档

| 文档 | 路径 |
|------|------|
| CLI 使用指南 | `docs/specific/customer-mdm/cli-usage-guide.md` |
| 架构决策 #12 | `docs/architecture/architectural-decisions.md#decision-12` |
| Schema 全景图 | `docs/database-schema-panorama.md` (§6-7: customer/bi schema) |

---

## 10. 🚀 Quick Reference (快速参考)

### CLI 常用命令

```bash
# 查看帮助
uv run --env-file .wdh_env python -m work_data_hub.cli.etl --help

# 试运行 (不写入数据库)
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domain annuity_performance --dry-run

# 执行 ETL (写入数据库)
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domain annuity_performance --execute

# 数据库连接检查
uv run --env-file .wdh_env python -m work_data_hub.cli.etl --check-db

# 多域批量处理
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domains annuity_performance,annuity_income --execute

# 禁用 EQC 调用 (离线模式)
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domain annuity_performance --no-enrichment --execute
```

### 关键 CLI 参数

| 参数               | 说明                                             |
| ------------------ | ------------------------------------------------ |
| `--domain`         | 单个域名称                                       |
| `--domains`        | 多个域名称 (逗号分隔)                            |
| `--dry-run`        | 试运行，不写入数据库                             |
| `--execute`        | 执行模式，写入数据库                             |
| `--no-enrichment`  | 禁用 EQC API 调用                                |
| `--check-db`       | 仅检查数据库连接                                 |
| `--period YYYY-MM` | 指定处理月份                                     |
| `--file-selection` | 文件选择策略: `error` (默认), `newest`, `oldest` |

### 配置文件速查

| 配置用途           | 文件路径                     |
| ------------------ | ---------------------------- |
| 数据源发现模式     | `config/data_sources.yml`    |
| FK 回填规则        | `config/foreign_keys.yml`    |
| 参考数据同步       | `config/reference_sync.yml`  |
| 公司硬编码映射     | `config/company_mapping.yml` |
| EQC 匹配类型置信度 | `config/eqc_confidence.yml`  |
| 环境变量           | `.wdh_env`                   |

### 测试命令

```bash
# 运行所有测试
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/ -v

# 运行特定模块测试
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/io/schema/ -v

# 代码质量检查
uv run ruff check src/
uv run ruff format --check src/
```

---
