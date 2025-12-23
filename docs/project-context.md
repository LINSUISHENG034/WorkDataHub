# Project Context & Development Standards

## 0. 🤖 AI Agent Persona & Prime Directives

**Role:** You are a Senior Python Architect working in a strict **Pre-Production** environment.
**Primary Goal:** Deliver clean, modular, and maintainable code.
**Critical Constraint:** **NO LEGACY SUPPORT.** You have full authority to refactor, break APIs, and change schemas to achieve the best design.

---

## 1. 📏 Hard Constraints (Strictly Enforced)

*Violating these requires immediate self-correction.*

### Code Structure Limits

* **File Size:** **MAX 800 lines**. *Action:* If a file exceeds this, split it into sub-modules immediately.
* **Function Size:** **MAX 50 lines**. *Action:* Extract logic into private helper functions.
* **Class Size:** **MAX 100 lines**. *Action:* Use composition over inheritance; split large classes.
* **Line Length:** **MAX 100 characters** (Matches `ruff` config).

### Code Smell Prevention

* **Pre-commit Hooks:** Run `pre-commit install` in project root (one-time setup per clone).
  * All commits must pass `scripts/quality/check_file_length.py` (max 800 lines) and Ruff checks.
  * **Bypass Policy:** Use `git commit --no-verify` ONLY for emergency hotfixes.
  * See [Story 7.6](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/7-6-ci-integration-code-quality-tooling.md) for setup details.
* **Domain-Growth Modules:** Modules like `domain_registry.py` should be pre-modularized when domain count increases.
  * See [Story 7.5](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/7-5-domain-registry-pre-modularization.md) for modularization pattern.
* **Complexity Checks:** Ruff PLR rules enforce code complexity limits:
  * `max-statements = 50` (per function, aligns with MAX 50 lines guideline)
  * `max-branches = 12` (cyclomatic complexity threshold)

### Development Philosophy

* **Zero Legacy Policy:**
* ❌ **NEVER** keep commented-out code or "v1" backups. Delete them.
* ❌ **NEVER** create wrappers for backward compatibility.
* ✅ **ALWAYS** refactor atomicaly: Update the definition AND all call sites in one go.


* **KISS & YAGNI:** Implement only what is currently needed. No speculative features.

---

## 2. 🛠️ Tooling & Environment Standards

### Python Execution (Run via `uv`)

**Rule:** Never run `python` directly. Always use the project manager `uv`. Pre-requisite: Ensure `.wdh_env` contains `PYTHONPATH=src`.

* **Standard Command:**Use the env-file to automatically load PYTHONPATH and other configs.
```bash
uv run --env-file .wdh_env src/your_script.py

```


* **Dependency Management:** Do not use pip directly. Use `uv add` or `uv remove`.

### File Operations

**Priority Order:**

1. 🥇 **Agent Native Tools:** ALWAYS prefer using `read_file`, `write_file`, `replace_in_file` provided by your environment.
2. 🥈 **Shell Commands:** Use only if native tools are insufficient.

---

## 3. 💻 Shell Command Protocols (Context Aware)

**DETECT YOUR ENVIRONMENT BEFORE EXECUTING SHELL COMMANDS:**

### Scenario A: You are a "Bash Tool" Agent (e.g., Claude Code, Linux/WSL Context)

* **Environment:** Unix/Linux/WSL.
* **Allowed:** `rm`, `ls`, `cp`, `mv`, `test`, `mkdir -p`.
* **FORBIDDEN:** Windows CMD commands (`del`, `dir`, `copy`).
* **Example:**
```bash
# ✅ Correct
test -f "data.json" && rm "data.json"

```



### Scenario B: You are a "PowerShell" Agent (e.g., Windows Native CLI)

* **Environment:** Windows PowerShell.
* **Allowed:** `Remove-Item`, `Get-ChildItem`, `Test-Path`, or aliases (`rm`, `ls`, `mv`).
* **FORBIDDEN:** Unix specific syntax like `[ -f ... ]`, `export`, `source`.
* **Example:**
```powershell
# ✅ Correct
if (Test-Path "data.json") { Remove-Item "data.json" }

```



---

## 4. 🏗️ Design Principles (Pythonic)

* **Dependency Inversion:** Depend on abstractions, not concretions.
* **Fail Fast:** Raise customized exceptions (`ValueError`, `RuntimeError`) immediately upon invalid state.
* **Type Hinting:** All function signatures **must** include Python type hints.
* **Docstrings:** All public modules, classes, and functions **must** have a descriptive docstring.

---

## 5. 📊 Reference Documentation

### Database Architecture Overview

本项目使用两个 PostgreSQL 数据库，理解它们的关系是开发的前提：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Database Architecture                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐      ┌──────────────────────────┐        │
│  │   legacy (只读数据源)     │      │  postgres (主数据库)      │        │
│  │   localhost:5432/legacy  │ ───▶ │  localhost:5432/postgres │        │
│  │                          │ Sync │                          │        │
│  │  • 58 tables             │      │  • 22 tables             │        │
│  │  • 历史业务数据           │      │  • ETL处理后的数据        │        │
│  │  • 参考数据源             │      │  • 公司enrichment数据     │        │
│  └──────────────────────────┘      └──────────────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 两个数据库的职责

| 数据库 | 连接地址 | 用途 | 读写权限 |
|--------|----------|------|----------|
| **legacy** | `postgresql://localhost:5432/legacy` | 历史数据源，从原 MySQL 迁移而来 | **只读** |
| **postgres** | `postgresql://localhost:5432/postgres` | 主数据库，ETL 输出目标 | **读写** |

#### legacy 数据库 (只读)

**来源:** 原 MySQL `annuity_hub` 数据库已完整迁移至此。

**用途:**
- 📖 参考数据同步 (Reference Sync) - 年金计划、组合计划等主数据
- 📖 公司信息同步 - base_info、business_info 等 EQC 数据
- 📖 历史数据对比验证

**关键 Schema:**
- `enterprise` (9 tables) - 公司主数据、EQC 搜索结果
- `business` (9 tables) - 规模明细、收入明细等业务数据
- `mapping` (11 tables) - 年金计划、组合计划等参考数据
- `customer` (20 tables) - 客户生命周期数据
- `finance` (7 tables) - 财务相关数据

#### postgres 数据库 (主数据库)

**用途:**
- ✍️ ETL Pipeline 输出目标
- ✍️ 公司 Enrichment 缓存 (enrichment_index)
- ✍️ Pipeline 执行记录

**关键 Schema:**
- `enterprise` (12 tables) - 公司 enrichment、EQC API 数据
- `business` (1 table) - ETL 处理后的规模明细
- `mapping` (6 tables) - 参考数据 (从 legacy 同步)
- `public` (3 tables) - Pipeline 基础设施

#### 数据流向

```
Excel Files ──▶ ETL Pipeline ──▶ postgres.business.规模明细
                    │
                    ▼
              Company Enrichment
                    │
         ┌─────────┴─────────┐
         ▼                   ▼
  postgres.enterprise   legacy.enterprise
  (enrichment_index)    (base_info sync)
```

#### 环境变量配置

```bash
# .wdh_env 文件
# 主数据库 (postgres)
DATABASE_URL=postgresql://postgres:Post.169828@localhost:5432/postgres

# Legacy 数据库 (只读)
WDH_LEGACY_PG_HOST=localhost
WDH_LEGACY_PG_PORT=5432
WDH_LEGACY_PG_DATABASE=legacy
WDH_LEGACY_PG_USER=postgres
WDH_LEGACY_PG_PASSWORD=Post.169828
```

### Detailed Documentation

* **[Database Schema Panorama](database-schema-panorama.md)** - 完整数据库结构文档
  * 两个数据库的完整 schema 和表定义
  * Entity Relationship 图
  * Data Flow Architecture

### Key Architecture Files

| File | Purpose |
|------|---------|
| `src/work_data_hub/infrastructure/schema/` | Domain Registry - Single Source of Truth for schema definitions |
| `config/data_sources.yml` | Domain file discovery patterns |
| `config/foreign_keys.yml` | FK backfill configuration |
| `config/reference_sync.yml` | Reference data sync settings (legacy → postgres) |

---