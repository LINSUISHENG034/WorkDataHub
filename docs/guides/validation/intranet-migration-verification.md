# 内网迁移验证 Runbook

> **目的**: 在公司内网环境中验证 WorkDataHub 项目的基础运行环境，确保 Python 依赖和 PostgreSQL 数据库可正常工作。

## 📦 最小化部署包内容

使用 `scripts/packaging/create_deploy_package.ps1` 脚本生成部署包，包含以下核心文件：

| 目录/文件 | 用途 | 必需 |
|-----------|------|------|
| `src/` | 源代码 | ✅ |
| `config/` | 配置文件 (YAML mappings) | ✅ |
| `io/schema/migrations/` | Alembic 迁移脚本 | ✅ |
| `pyproject.toml` | Python 依赖声明 | ✅ |
| `uv.lock` | 锁定版本依赖 | ✅ |
| `alembic.ini` | 数据库迁移配置 | ✅ |
| `.env.example` | 环境变量模板 | ✅ |
| `tests/fixtures/sample/` | 测试样例数据 (可选) | ⚪ |

**不包含**: `.git/`, `.venv/`, `node_modules/`, `__pycache__/`, `logs/`, `data/`, `.cache/`

---

## 🔧 环境准备

### 1. Python 环境验证

```powershell
# 检查 Python 版本 (需 >= 3.10)
python --version

# 如果使用 uv (推荐)
uv --version
```

### 2. 创建虚拟环境

```powershell
# 方式 A: 使用 uv (推荐，自动下载依赖)
uv venv
uv sync

# 方式 B: 使用标准 venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

---

## ✅ 验证检查清单

### Step 1: Python 依赖验证

```powershell
# 确认核心包安装成功
uv run python -c "import dagster; import pandas; import sqlalchemy; print('Core packages OK')"

# 确认 CLI 模块可加载
uv run python -c "from work_data_hub.cli import main; print('CLI module OK')"
```

**预期输出**: 无报错，打印 "Core packages OK" 和 "CLI module OK"

**常见问题**:
- `ModuleNotFoundError`: 检查是否在项目根目录执行，且 `.venv` 已激活
- `psycopg2` 编译失败: 确认系统已安装 PostgreSQL 开发头文件 (`libpq-dev`)

---

### Step 2: 配置文件验证

```powershell
# 复制环境变量模板
Copy-Item .env.example .wdh_env

# 编辑 .wdh_env 文件，设置实际的数据库连接信息:
# DATABASE_URL=postgresql://用户名:密码@主机:端口/数据库名
```

验证配置加载:
```powershell
uv run --env-file .wdh_env python -c "
from work_data_hub.config.settings import Settings
s = Settings()
print(f'Database URL: {s.database_url[:30]}...')
print(f'Environment: {s.environment}')
print('Settings loaded OK')
"
```

**预期输出**: 显示数据库 URL 前缀和环境名称

---

### Step 3: PostgreSQL 连接验证

```powershell
uv run --env-file .wdh_env python -c "
from sqlalchemy import create_engine, text
from work_data_hub.config.settings import Settings
s = Settings()
engine = create_engine(s.database_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT version();'))
    print(f'PostgreSQL: {result.scalar()}')
    print('Database connection OK')
"
```

**预期输出**: 显示 PostgreSQL 版本号

**常见问题**:
- `connection refused`: 检查 PostgreSQL 服务是否运行，端口是否正确
- `authentication failed`: 检查用户名/密码
- `database does not exist`: 需先创建数据库

---

### Step 4: 数据库 Schema 初始化

```powershell
# 查看当前迁移状态
uv run --env-file .wdh_env alembic current

# 执行全部迁移 (初始化 schema)
uv run --env-file .wdh_env alembic upgrade head

# 验证 schema 创建成功
uv run --env-file .wdh_env python -c "
from sqlalchemy import create_engine, inspect
from work_data_hub.config.settings import Settings
s = Settings()
engine = create_engine(s.database_url)
inspector = inspect(engine)
schemas = inspector.get_schema_names()
print(f'Schemas: {schemas}')
for schema in ['staging', 'mapping', 'raw', 'customer']:
    if schema in schemas:
        print(f'  ✅ {schema}')
    else:
        print(f'  ❌ {schema} MISSING')
"
```

**预期输出**: 显示 `staging`, `mapping`, `raw`, `customer` 四个 schema 均存在

---

### Step 5: CLI 功能验证

```powershell
# 帮助信息
uv run --env-file .wdh_env python -m work_data_hub.cli --help

# ETL dry-run (无实际数据变更)
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202501 --file-selection newest
```

**预期输出**: CLI 帮助信息正常显示；ETL dry-run 应显示 "No files matched" 或列出发现的文件（取决于数据目录配置）

---

## 📊 验证结果记录

| 检查项 | 状态 | 备注 |
|--------|------|------|
| Python 版本 >= 3.10 | ⬜ | |
| uv/pip 依赖安装 | ⬜ | |
| Settings 配置加载 | ⬜ | |
| PostgreSQL 连接 | ⬜ | |
| Alembic 迁移执行 | ⬜ | |
| Schema 验证 | ⬜ | |
| CLI 基本功能 | ⬜ | |

---

## 🔄 回滚步骤

如需回滚数据库 schema:
```powershell
# 回滚到初始状态
uv run --env-file .wdh_env alembic downgrade base
```

---

## 📞 问题反馈

遇到问题时，请收集以下信息：
1. 执行的命令和完整错误输出
2. `python --version` 和 `uv --version` 输出
3. `.wdh_env` 文件内容（隐藏密码）
4. `uv run pip list` 已安装包列表
