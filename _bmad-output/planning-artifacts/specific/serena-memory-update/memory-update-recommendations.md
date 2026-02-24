# Serena Memory 文件更新建议

> **生成日期:** 2025-01-30
> **分析范围:** WorkDataHub 项目 Serena Memory 文件
> **对比基准:** docs/project-context.md, pyproject.toml, 实际代码结构

---

## 📋 执行摘要

WorkDataHub 项目经过多轮迭代（特别是 Epic 7 模块化重构），项目架构、技术栈和开发规范都发生了显著变化。当前 Serena Memory 文件存在多项**关键过时信息**，可能导致 AI Agent 在代码生成和任务执行时出现错误。

**影响等级:** 🔴 高 - 建议立即更新

---

## 🎯 更新优先级矩阵

| Memory 文件 | 影响范围 | 错误严重度 | 优先级 |
|------------|---------|-----------|--------|
| `code_style_conventions.md` | 全局代码生成 | 🔴 严重 | P0 |
| `suggested_commands.md` | 命令执行 | 🔴 严重 | P0 |
| `task_completion_guidelines.md` | 质量验证 | 🟡 中等 | P1 |
| `project_overview.md` | 架构理解 | 🟡 中等 | P1 |

---

## 📊 详细差异分析

### 1️⃣ code_style_conventions.md (P0 - 严重)

#### 🔴 关键错误

| 配置项 | Memory 值 | 实际值 | 影响 |
|--------|----------|--------|------|
| **文件行数限制** | 500 行 | **800 行** | AI 可能过早拆分文件，违反项目标准 |
| **行长度** | 100 字符 | **88 字符** | 生成代码将触发 Ruff E501 警告 |

#### 🟢 缺失内容

```yaml
Ruff PLR 复杂度规则 (Epic 7.1-17):
  - max-statements: 50    # 每函数最大语句数
  - max-branches: 12      # 循环复杂度阈值

Pre-commit Hooks (Epic 7.6):
  - scripts/quality/check_file_length.py (强制 800 行限制)
  - Ruff 自动格式化和检查
  - 绕过策略: git commit --no-verify (仅紧急修复)

Clean Architecture 强制 (Story 1.6):
  - Domain 层禁止导入 io, orchestration
  - 通过 Ruff TID251 规则强制执行
```

#### 📝 建议更新内容

```markdown
## File and Function Limits
- **Files**: MAX 800 lines (Epic 7 模块化后新标准)
- **Functions**: MAX 50 lines with single responsibility
- **Classes**: MAX 100 lines representing single concept
- **Line Length**: MAX 88 characters (matches pyproject.toml ruff config)

## Code Complexity Enforcement
Ruff PLR rules (configured in pyproject.toml):
- `max-statements = 50`: Per-function statement limit
- `max-branches = 12`: Cyclomatic complexity threshold
- Files with complex logic are explicitly exempt via per-file-ignores

## Pre-commit Quality Gates
Run `pre-commit install` (one-time setup):
- File length validator (max 800 lines)
- Ruff formatting and linting
- Bypass: `git commit --no-verify` (emergency hotfixes only)
```

---

### 2️⃣ suggested_commands.md (P0 - 严重)

#### 🔴 关键错误

**Memory 中的命令将导致执行失败：**

```bash
# ❌ 错误：直接使用 python（会因找不到模块而失败）
uv run python script.py

# ❌ 错误：缺少 PYTHONPATH 配置
uv run script.py
```

#### ✅ 正确的命令模式

```bash
# ✅ 正确：使用 --env-file 加载 .wdh_env（包含 PYTHONPATH=src）
uv run --env-file .wdh_env script.py

# ✅ 或者使用 shell 环境变量
PYTHONPATH=src uv run script.py
```

#### 🟢 缺失内容

**项目特定的 pytest markers：**

```yaml
# pyproject.toml 中定义的 10+ markers
unit              # 快速单元测试（无外部依赖）
integration       # 集成测试（数据库或文件系统）
postgres          # 需要 PostgreSQL 数据库（可用 -m "not postgres" 跳过）
eqc_integration   # 调用企查查 API（需 opt-in）
monthly_data      # 需要参考/月度数据（需 opt-in）
legacy_data       # 需要历史样本数据（需 opt-in）
e2e               # Dagster/warehouse E2E 流程（需 opt-in）
performance       # 慢速或资源密集型场景
legacy_suite      # 历史栈回归测试（RUN_LEGACY_TESTS=1）
e2e_suite         # E2E Dagster 流程（RUN_E2E_TESTS=1）
sandbox_domain    # 非生产沙盒域测试
```

#### 📝 建议更新内容

```markdown
## Environment Configuration
**CRITICAL:** Always use `--env-file .wdh_env` to ensure PYTHONPATH=src is loaded.

```bash
# ✅ Standard command pattern
uv run --env-file .wdh_env src/your_script.py

# ❌ WRONG - will fail with module not found errors
uv run python script.py
python script.py
```

## Testing Commands with Markers
```bash
# Run fast unit tests only
uv run pytest -m "unit"

# Run integration tests without database
uv run pytest -m "integration" -m "not postgres"

# Opt-in: Run legacy regression tests
RUN_LEGACY_TESTS=1 uv run pytest -m "legacy_suite"

# Opt-in: Run E2E Dagster flows
RUN_E2E_TESTS=1 uv run pytest -m "e2e_suite"
```
```

---

### 3️⃣ project_overview.md (P1 - 中等)

#### 🔴 架构描述严重过时

**Memory 描述（2024年早期状态）：**
```
简单的 4 层架构：
- config/   - 配置
- io/       - 输入/输出
- domain/   - 业务逻辑（仅 trustee_performance）
- utils/    - 工具
```

**实际架构（Epic 7 模块化后）：**

```
src/work_data_hub/
├── config/                    # 配置管理
├── domain/                    # 领域层（多域架构）
│   ├── annuity_performance/   # 年金规模明细
│   ├── annuity_income/        # 年金收入明细
│   ├── annual_award/          # 年度奖励明细
│   ├── annual_loss/           # 年度流失明细
│   ├── company_enrichment/    # 公司 ID 解析服务
│   ├── reference_backfill/    # 参考数据回填服务
│   ├── sandbox_trustee_performance/  # 沙盒测试域
│   ├── pipelines/             # 通用管道框架
│   │   ├── steps/             # 可复用管道步骤
│   │   └── validation/        # 管道验证工具
│   └── registry.py            # 域注册表 (Epic 7.4)
├── infrastructure/            # 基础设施层（Epic 7 新增）
│   ├── schema/                # Schema DDL 生成器
│   ├── enrichment/            # 公司 ID 解析基础设施
│   ├── cleansing/             # 数据清洗
│   ├── sql/                   # SQL 构建器
│   └── validation/            # 数据验证
├── io/                        # IO 层
│   ├── connectors/            # 文件/API 连接器
│   │   ├── eqc/               # 企查查 API 客户端
│   │   └── discovery/         # 文件发现服务
│   ├── readers/               # 数据读取器
│   └── loader/                # 数据库加载器
├── orchestration/             # 编排层
│   ├── jobs.py                # Dagster Job 注册表
│   └── ops/                   # Pipeline 操作
├── customer_mdm/              # 客户主数据管理（Epic 7.6 新增）
├── gui/                       # PyQt6 GUI（新增）
├── cli/                       # 命令行接口
│   ├── customer_mdm/          # 客户 MDM CLI
│   └── etl/                   # ETL CLI
└── utils/                     # 共享工具
```

#### 🟢 技术栈不完整

| 类别 | Memory 中已有 | 实际缺少的 |
|------|--------------|-----------|
| **数据处理** | pandas, openpyxl | ✅ pandera (数据验证) |
| **网络爬虫** | ❌ 无 | ✅ playwright, playwright-stealth, opencv-python-headless |
| **加密** | ❌ 无 | ✅ gmssl |
| **大数据** | ❌ 无 | ✅ pyarrow |
| **SQL 工具** | ❌ 无 | ✅ sqlglot, PyMySQL |
| **工具** | ❌ 无 | ✅ rich (终端输出), pyperclip (剪贴板) |

#### 🟢 缺少关键架构模式

**Domain Registry Pattern (Epic 7.4):**

```python
# 替代硬编码 if/elif 分发的配置驱动架构

JOB_REGISTRY = {
    "annuity_performance": JobEntry(
        job=annuity_performance_job,
        supports_backfill=True,
    ),
    "annuity_income": JobEntry(
        job=annuity_income_job,
        supports_backfill=True,
    ),
    # ... 添加新城无需修改分发逻辑
}

DOMAIN_SERVICE_REGISTRY = {
    "annuity_performance": DomainServiceEntry(
        service_fn=process_with_enrichment,
        supports_enrichment=True,
    ),
    # ...
}
```

#### 📝 建议更新内容

```markdown
## Project Architecture (Post-Epic 7 Modularization)

### Layer Structure
- **Domain Layer** (`domain/`): Multi-domain business logic
  - annuity_performance, annuity_income, annual_award, annual_loss
  - company_enrichment, reference_backfill, sandbox_trustee_performance
  - pipelines/: Reusable pipeline framework
  - registry.py: Domain Registry Pattern (Epic 7.4)

- **Infrastructure Layer** (`infrastructure/`): Cross-cutting services
  - schema/: Schema DDL generators
  - enrichment/: Company ID resolution
  - cleansing/: Data cleansing
  - sql/: SQL builders
  - validation/: Data validation

- **IO Layer** (`io/`): Input/Output operations
  - connectors/: File/API connectors (EQC, file discovery)
  - readers/: Data readers (Excel, CSV)
  - loader/: Database loader

- **Orchestration Layer** (`orchestration/`): Dagster pipelines
  - jobs.py: Job registry
  - ops/: Pipeline operations

- **Customer MDM** (`customer_mdm/`): Master data management (Epic 7.6)

## Technology Stack (Extended)
### Data Processing
- pandas, openpyxl, **pandera** (data validation)

### Web Scraping
- **playwright**, **playwright-stealth**, **opencv-python-headless** (EQC integration)

### Database
- psycopg2-binary, psycopg2, **PyMySQL**, sqlalchemy, alembic

### Utilities
- **sqlglot** (SQL translation), **pyarrow** (data interchange)
- **gmssl** (encryption), **rich** (terminal UI), **pyperclip** (clipboard)
```

---

### 4️⃣ task_completion_guidelines.md (P1 - 中等)

#### 🟢 缺失验证门槛

```yaml
# 当前缺少的检查项

Pre-commit Hooks:
  command: uv run pre-commit run --all-files
  purpose: Automated quality checks before commit

File Length Validation:
  script: scripts/quality/check_file_length.py
  limit: 800 lines per file
  enforcement: Pre-commit hook
```

#### 🟢 pytest markers 列表不完整

**当前只有 4 个：**
```yaml
- unit
- integration
- postgres
- e2e (legacy marker)
```

**实际有 10+ 个：**
```yaml
- unit, integration, postgres
- eqc_integration, monthly_data, legacy_data
- e2e, performance
- legacy_suite, e2e_suite (opt-in regression tests)
- sandbox_domain
```

#### 📝 建议更新内容

```markdown
## Mandatory Validation Gates

```bash
# 1. Pre-commit quality checks (NEW - Epic 7)
uv run pre-commit run --all-files

# 2. Code formatting and linting
uv run ruff check src/ --fix

# 3. Type checking
uv run mypy src/

# 4. All tests must pass
uv run pytest -v
```

## Testing with Markers

```bash
# Fast feedback: unit tests only
uv run pytest -m "unit"

# Integration without database
uv run pytest -m "integration" -m "not postgres"

# Opt-in regression tests
RUN_LEGACY_TESTS=1 uv run pytest -m "legacy_suite"
RUN_E2E_TESTS=1 uv run pytest -m "e2e_suite"
```

## Code Review Checklist (Updated)
- [ ] Code follows project style guidelines (88-char line limit)
- [ ] All tests pass (including marker-specific tests)
- [ ] Type checking passes (mypy strict mode)
- [ ] No linting errors (Ruff E, F, W, I, PLR, TID)
- [ ] File length under 800 lines (pre-commit enforced)
- [ ] Documentation is updated if needed
- [ ] Error handling is appropriate
- [ ] No sensitive information is exposed
- [ ] Clean Architecture compliance (no domain→io imports)
```

---

## 🎯 更新执行计划

### Phase 1: 立即更新 (P0)

```bash
# 更新 code_style_conventions.md
- 修正行数限制 (500 → 800)
- 修正行长度 (100 → 88)
- 添加 Ruff PLR 规则说明
- 添加 Pre-commit hooks 说明
- 添加 Clean Architecture 强制规则

# 更新 suggested_commands.md
- 修正所有命令示例（添加 --env-file .wdh_env）
- 添加完整的 pytest markers 列表
- 更新 Windows 特定命令说明
```

### Phase 2: 尽快更新 (P1)

```bash
# 更新 task_completion_guidelines.md
- 添加 pre-commit 检查要求
- 更新 pytest markers 列表
- 添加文件长度验证说明

# 更新 project_overview.md
- 更新架构描述（添加 infrastructure, customer_mdm, gui）
- 更新技术栈列表（添加 pandera, playwright 等）
- 添加 Domain Registry Pattern 说明
- 更新域列表（从 1 个扩展到 6+ 个）
```

---

## 📚 参考文档

- **项目主文档:** `docs/project-context.md`
- **数据库架构:** `docs/database-schema-panorama.md`
- **配置文件:** `pyproject.toml`
- **Ruff 配置:** `[tool.ruff]` section in pyproject.toml
- **Epic 7 文档:** `docs/sprint-artifacts/stories/epic-7-modularization/`
- **Serena 官方文档:** https://oraios.github.io/serena/

---

## ⚠️ 变更影响评估

如果不更新这些 memory 文件，可能导致：

1. **代码生成错误:** AI 生成的代码可能违反项目标准（88/800 限制）
2. **命令执行失败:** 使用错误的命令格式导致 `ModuleNotFoundError`
3. **架构理解偏差:** AI 可能生成不符合当前模块化架构的代码
4. **测试遗漏:** 不完整的 markers 列表导致测试策略不完整

---

## ✅ 验证清单

更新完成后，请验证：

- [ ] 所有行数/长度限制与 pyproject.toml 一致
- [ ] 所有命令示例包含 `--env-file .wdh_env`
- [ ] pytest markers 列表与 pyproject.toml 完全一致
- [ ] 架构描述反映实际的 6 层结构
- [ ] 技术栈列表包含所有依赖
- [ ] Domain Registry Pattern 已说明

---

> **文档维护者:** AI Agent
> **下次审查日期:** Epic 8 完成后
> **相关问题:** Serena Memory 应与项目文档同步更新
