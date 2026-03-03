# WorkDataHub 内网部署与运行指南

本文档面向**公司内网隔离环境**（无法直接访问外部 PyPI），完整覆盖从环境搭建、依赖安装到 CLI 运行的全部流程。内网用户只需参阅本文即可完成端到端部署与使用。

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
| Python | ≥ 3.10（已安装到系统） | 内网机器需提前安装 |
| PostgreSQL | ≥ 14 | 主数据库（业务输出目标） |
| Git | latest | 版本控制 |
| uv | latest（推荐） | 如未安装也可用 pip 替代（见[方式二](#方式二使用-pip-离线部署无需-uv)） |

### 1.2 目录结构

项目中 `vendor/` 目录包含了离线部署所需的全部依赖：

```
vendor/
├── requirements.txt        ← 完整依赖清单（由 uv pip compile 生成）
└── wheels/                 ← 预下载的 wheel 包（约 170 MB）
```

### 1.3 内网 PyPI 仓库（备选）

公司内网提供了 PyPI 仓库，可作为离线 wheel 的补充来源。使用前需确认本机到 `30.16.105.251:8445` 的网络已开通。

- 仓库地址：`http://maven.paic.com.cn:8445/repository/pypi/simple/`
- 查看包信息：`http://maven.paic.com.cn:8445/repository/pypi/simple/<包名>/`

> [!WARNING]
> 内网仓库**不是完整镜像**，可能缺少部分包。建议以 `vendor/wheels/` 离线安装为主，内网仓库仅作为缺包时的补充手段。

---

## 二、 依赖安装

### 方式一：使用 uv 离线部署（推荐）

> `uv.lock` 锁定了生成时的精确 Python 版本（如 3.12.10）。若内网系统安装的是不同 patch 版本（如 3.12.9），只需删除 `.python-version` 文件即可。

**CMD：**
```cmd
REM 1. 强制 uv 使用系统 Python（整个部署流程只需设置一次）
set UV_PYTHON_PREFERENCE=only-system

REM 2. 移除精确的 Python 版本锁定（切勿执行 uv lock）
del .python-version

REM 3. 创建虚拟环境
uv venv --python 3.12

REM 4. 从本地 wheel 包离线安装所有依赖（已含 psycopg v3，解决中文 Windows 的 UnicodeDecodeError）
uv pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

REM 5. (可选) 安装 pre-commit 钩子
REM 若提示 program not found，是因为之前导出包时未开启 --all-groups，纯部署可直接跳过此步！
uv run --no-sync pre-commit install
```

**Bash / PowerShell：**
```bash
# 1. 强制 uv 使用系统 Python
export UV_PYTHON_PREFERENCE=only-system

# 2. 移除精确的 Python 版本锁定
rm -f .python-version

# 3. 创建虚拟环境
uv venv --python 3.12

# 4. 从本地 wheel 包离线安装
uv pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

# 5. (可选) 安装 pre-commit 钩子
uv run --no-sync pre-commit install
```

> **提示**：如需永久免去每次 `set UV_PYTHON_PREFERENCE`，可在项目根目录创建 `uv.toml`，写入 `python-preference = "only-system"`。

### 方式二：使用 pip 离线部署（无需 uv）

**CMD：**
```cmd
REM 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate

REM 2. 从本地 wheel 包离线安装所有依赖
pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

REM 3. (可选) 安装 pre-commit 钩子（若提示找不到命令，纯部署可跳过）
pre-commit install
```

**Bash / PowerShell：**
```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # PowerShell: .venv\Scripts\Activate.ps1

# 2. 从本地 wheel 包离线安装
pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

# 3. (可选) 安装 pre-commit 钩子
pre-commit install
```

---

## 三、 环境变量配置

项目的数据库连接、外部配置路径及 Python 导入路径均通过环境变量文件注入。

1. 在项目根目录新建 `.wdh_env` 文件。
2. 填补以下核心配置项：

```env
# 【必须】将 src 目录加入 Python 路径，确保可正确 import 内部模块
PYTHONPATH=src

# 【必须】PostgreSQL 主数据库连接地址
DATABASE_URL=postgresql://user:password@localhost:5432/postgres

# 【可选】天眼查 API Key（内网离线环境可跳过，运行时使用 --no-enrichment 参数即可）
EQC_API_KEY=your_api_key_here

# 【内网必须】Playwright 浏览器路径（auth refresh 命令使用）
# 内网无法下载 Playwright 自带 Chromium，需指向系统已安装的 Edge 或 Chrome
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
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

## 四、 数据库部署

本项目采用**双数据库架构**，利用 Alembic 进行 ORM 模型的 Schema 迁移管理。

| 数据库 | 角色 | 读写权限 |
|--------|------|----------|
| **legacy** | 历史数据源（从原 MySQL 迁移） | 只读 |
| **postgres** | 主数据库（ETL 输出目标） | 读写 |

> [!IMPORTANT]
> **所有的 Schema 数据定义更新均不能使用直接的 DDL，必须通过 Alembic！**

**Bash / PowerShell：**
```bash
uv run --no-sync --env-file .wdh_env alembic upgrade head
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env alembic upgrade head
```

如使用 pip 方式部署：
```cmd
set PYTHONPATH=src
alembic upgrade head
```

更多迁移管理细节请参阅 [database-migrations.md](database-migrations.md)。

---

## 五、 原始数据目录规范

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

> **多版本文件**：当同一账期存在多个版本的 Excel（如 `V1` / `V2`），可通过 `--file-selection newest` 参数使系统自动挑选最新版本。详见 [5.2 节](#52-运行核心业务数据流转)。

---

## 六、 CLI 数据运行指南（ETL & Post-Hooks）

项目使用 Dagster 编排引擎与泛化业务抽象处理管线，通过 CLI 层高度封装以提供便捷访问。

> [!IMPORTANT]
> 🚨 **内网关键提醒**：所有 `uv run` 命令必须加上 **`--no-sync`** 参数！这可以阻止 uv 尝试联网同步依赖，避免出现 `invalid peer certificate: UnknownIssuer` 错误。
>
> 📌 如使用 pip 方式部署（已激活虚拟环境），则直接用 `python -m ...` 替代 `uv run --no-sync --env-file .wdh_env python -m ...`（需先 `set PYTHONPATH=src`）。

### 6.1 常用诊断命令

**Bash / PowerShell：**
```bash
# 查看所有支持的域和命令参数
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --help

# 测试数据库可用性（仅执行连接测试）
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --help
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

### 6.2 运行核心业务数据流转

ETL 会按以下生命周期自动进行流转：

```
文件发现 → 数据读取 → 领域管线处理(清洗+企业解析) → 外键维表回填 → 关卡校验 → 最终入库 → Post-ETL Hooks
```

> 💡 各阶段的详细机制解析请参阅 [数据处理指南](data_processing_guide.md)。

**Bash / PowerShell：**
```bash
# 【试运行模式】Dry-Run：清洗逻辑运作，但最终拦截入库（排查清洗错误首选）
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --dry-run

# 【单领域落地】真实写入并自动触发下游 Hook（客户合约同步及快照）
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --execute

# 【全领域执行】一键处理（如遇多版本同账期 Excel，挑选 newest 最新）
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains \
  --period 202510 \
  --file-selection newest \
  --execute
```

**CMD：**
```cmd
REM 【试运行模式】
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --dry-run

REM 【单领域落地】
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --execute

REM 【全领域执行】
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl ^
  --all-domains ^
  --period 202510 ^
  --file-selection newest ^
  --execute
```

> [!IMPORTANT]
> **推荐执行顺序**：快照需要所有事实先行落定，故应按 `annual_award` → `annual_loss` → `annuity_performance` 顺序依次执行，或使用 `--all-domains` 一键处理。

### 6.3 Post-ETL Hook 链（自动级联处理）

当 `annuity_performance` 领域 ETL 完成后，系统会**自动依次触发**以下 Post-ETL Hook：

| 执行顺序 | Hook 名称 | 功能描述 |
|:---:|---|---|
| 1 | `contract_status_sync` | 从 `business."规模明细"` 同步合约状态到 SCD2 维表 `customer."客户年金计划"` |
| 2 | `year_init` | 仅 1 月触发，初始化当年 `is_strategic` / `is_existing` 标识 |
| 3 | `snapshot_refresh` | 刷新两张月度快照宽表（ProductLine 粒度 + Plan 粒度） |

**Bash / PowerShell：**
```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance \
  --period 202510 \
  --execute --no-post-hooks
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annuity_performance ^
  --period 202510 ^
  --execute --no-post-hooks
```

### 6.4 离线 / 无网降级运行

对于内网无法触达 EQC（天眼查）接口的环境，**必须**使用 `--no-enrichment` 关闭企业解析的外呼 API。系统会自动降级采用本地 DB Cache 与 `IN*` 生成逻辑兜底解析。

**Bash / PowerShell：**
```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annual_award \
  --period 202510 \
  --no-enrichment \
  --execute
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl ^
  --domain annual_award ^
  --period 202510 ^
  --no-enrichment ^
  --execute
```

### 6.5 Customer MDM Post-Hooks 单独调用

若不随主 ETL 附带运行（如重构了快照配置或业务故障需手动修复），可以直接调用 MDM 工具钩子：

**Bash / PowerShell：**
```bash
# 1. 手动从 "规模明细" 反推 SCD2（渐变维）合约有效状态
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync

# 2. 手动依据事实计算生成指定账期的"客户/计划"月度管理看板快照
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202510
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202510
```

---

## 七、 CLI 参数快速参考

| 参数 | 说明 | 示例 |
|------|------|------|
| `--domain` | 单个域名称 | `--domain annuity_performance` |
| `--domains` | 多个域名称（逗号分隔） | `--domains annuity_performance,annuity_income` |
| `--all-domains` | 执行所有已注册域 | |
| `--period` | 指定处理月份（YYYYMM 格式） | `--period 202510` |
| `--dry-run` | 试运行，不写入数据库 | |
| `--execute` | 执行模式，写入数据库 | |
| `--no-enrichment` | 禁用 EQC API 调用（内网必用） | |
| `--no-post-hooks` | 禁用 Post-ETL Hooks | |
| `--file-selection` | 多版本文件选择策略：`error`（默认）/ `newest` / `oldest` | `--file-selection newest` |
| `--check-db` | 仅检查数据库连接 | |

---

## 八、 可视化监控（Dagster UI）

基于 Dagster 框架，可以将数据处理过程完全可视化。

**Bash / PowerShell：**
```bash
uv run --no-sync --env-file .wdh_env dagster dev
```

**CMD：**
```cmd
uv run --no-sync --env-file .wdh_env dagster dev
```

启动后在浏览器打开 `http://localhost:3000`，你将获得以下关键能力：

1. 直观地查看各个管道节点（Op）的执行拓扑图。
2. 检索并排查包含 "Company ID resolution" 与 "FK Backfill" 等核心环节记录的丰富结构化日志。
3. 追踪各账期数据的执行效率，以及捕获 Pandera 数据架构验证时的拦截异常。

---

## 九、 配置文件速查

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

## 十、 如何更新 vendor 包

当项目依赖发生变更时，需在**有外网的机器**上重新导出：

```cmd
REM 1. 重新生成依赖清单（加 --all-groups 包含 pre-commit 等开发依赖）
uv export --all-groups --no-hashes --format requirements-txt -o vendor/requirements.txt

REM 2. 安装 pip 到虚拟环境（如尚未安装）
uv pip install pip

REM 3. 重新下载所有 wheel 包
uv run python -m pip download -r vendor/requirements.txt -d vendor/wheels

REM 4. 额外下载 psycopg v3 wheel（中文 Windows 必需）
uv run python -m pip download psycopg psycopg-binary -d vendor/wheels --only-binary=:all: --python-version 3.12 --platform win_amd64
```

然后将更新后的 `vendor/` 目录同步到内网环境。

---

## 十一、 注意事项

- `vendor/wheels/` 中的包针对 **Windows x86_64 + Python 3.12** 平台下载，如目标环境的操作系统或 Python 版本不同，需重新导出。
- 建议在 `.gitignore` 中添加 `vendor/wheels/` 避免将大量二进制文件提交到 Git。

---

## 十二、 常见问题与排障

| 问题现象 | 原因 | 解决方案 |
|----------|------|----------|
| `invalid peer certificate: UnknownIssuer` | `uv run` 未加 `--no-sync`，尝试联网同步依赖，内网 HTTPS 代理替换了证书 | 所有 `uv run` 命令加 `--no-sync` |
| `alembic upgrade head` 报 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6` | 中文 Windows（GBK 区域）下 psycopg2 的 C 扩展无法解码 libpq 返回的信息 | 安装 `psycopg`（v3）：`uv pip install psycopg`。项目已自动切换驱动 |
| `pre-commit install` 报 `program not found` | 导出包时未开启 `--all-groups` | 纯部署环境可直接跳过 |
| `Failed to parse environment file` | `.wdh_env` 中 Windows 路径使用了裸反斜杠 | 用单引号包裹或换正斜杠（见[第三节](#三-环境变量配置)） |
| ETL 时 `Candidates found: 0` | `config/data_sources.yml` 的 glob 规则未匹配到文件 | 检查路径和递归通配符 `**/*.xlsx` |
| 大量 `IN*` 临时 company_id | EQC 解析未命中（内网无 API） | 在 `config/mappings/company_id/` 添加手工映射 |
| 业务字段计算错误（如日期、业务类型） | TransformStep 配置不符 | 检查 `src/work_data_hub/domain/<domain>/pipeline_builder.py` |
| 主拓、标签、客户类型聚合不正确 | 聚合算子配置错误 | 检查 `config/foreign_keys.yml`（max_by / concat_distinct） |
| 快照状态与事实不匹配 | match_fields 与明细表列名不对齐 | 检查 `config/customer_status_rules.yml` |
| `contract_status` 全为 NULL | Hook 未执行 | 确认未使用 `--no-post-hooks` |
| `aum_balance = 0` 但规模明细有数据 | 日期格式不对齐 | 确认 `snapshot_month` 为月末日期（如 `2025-10-31`） |
| `auth refresh` 报 `Executable doesn't exist` | Playwright 自带 Chromium 未安装（内网无法下载） | 在 `.wdh_env` 中设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向系统 Edge/Chrome |

> 更多详尽的验证 SQL 与端到端一致性校验流程，请参阅 [实盘数据验证指南](verification_guide_real_data.md)。
