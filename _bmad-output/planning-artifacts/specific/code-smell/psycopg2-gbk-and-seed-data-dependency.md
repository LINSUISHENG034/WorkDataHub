# Code Smell: psycopg2 编码崩溃, pg_restore 外部依赖与种子目录职责混淆

> **发现时间**: 2026-03-03
> **触发场景**: 在内网中文 Windows 环境部署项目时
> **影响范围**: 数据库迁移（Alembic）、种子数据加载、部署流程
> **严重程度**: 🔴 阻塞性（新环境部署完全失败）

---

## 一、问题一览

| # | 问题 | 状态 | 影响 |
|---|------|------|------|
| 1 | psycopg2 在中文 Windows（GBK）崩溃 | ✅ 已修复 | Alembic 迁移报 `UnicodeDecodeError` |
| 2 | 种子数据依赖外部工具 `pg_restore` | 🔲 待修复 | `base_info`、`enrichment_index` 静默跳过 |
| 3 | `config/seeds/` 混入业务数据备份 | 🔲 待修复 | 目录职责不清 |

---

## 二、详细分析

### 问题 1: psycopg2 C 扩展在 GBK 区域 Windows 崩溃（已修复）

**现象**：`alembic upgrade head` 报 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6`

**根因**：psycopg2 的 C 扩展底层调用 libpq，当连接 PostgreSQL 时（无论成功或失败），libpq 从中文 Windows 系统获取的错误消息/区域信息为 GBK 编码（代码页 936），但 psycopg2 硬编码以 UTF-8 解码，导致在 C 层面直接崩溃。

**已排除的方案**：
- `PGCLIENTENCODING=utf-8` ❌ — C 扩展在此之前已崩溃
- `chcp 65001` ❌ — C 扩展不走 Python IO 编码
- 修改系统区域设置 ❌ — 内网环境无管理员权限

**已实施的修复**：
- 安装 `psycopg`（v3）+ `psycopg-binary`（纯 Python 实现，正确处理编码）
- 在 `io/schema/migrations/env.py` 中自动将 `postgresql://` 替换为 `postgresql+psycopg://`
- 已更新 `vendor/wheels/`、`vendor/requirements.txt`、部署指南

**涉及文件**：
- [env.py](file:///e:/Projects/WorkDataHub/io/schema/migrations/env.py) — 核心修复
- [INTRANET_DEPLOY.md](file:///e:/Projects/WorkDataHub/vendor/INTRANET_DEPLOY.md) — 部署指南更新
- [deployment_run_guide.md](file:///e:/Projects/WorkDataHub/docs/deployment_run_guide.md) — 排障表更新

> [!WARNING]
> **潜在扩散风险**：当前修复仅覆盖 Alembic 迁移连接。项目其余模块（ETL、Dagster、CLI 等）仍使用 psycopg2，若在同一中文 Windows 环境运行也可能触发相同错误。需全局评估是否统一切换到 psycopg v3。

---

### 问题 2: 种子数据依赖外部工具 pg_restore

**现象**：`alembic upgrade head` 执行后，`enterprise.base_info`（27,535 行）和 `enterprise.enrichment_index`（32,052 行）数据未导入，仅打印 `Warning: pg_restore not found. Skipping dump file.` 后静默跳过。

**根因**：`003_seed_static_data.py` 中 `_load_dump_seed_data()` 通过 `subprocess.run()` 调用 `pg_restore` 外部命令来加载 `.dump` 格式文件。新部署环境未安装 PostgreSQL 客户端工具。

**代码位置**：[003_seed_static_data.py](file:///e:/Projects/WorkDataHub/io/schema/migrations/versions/003_seed_static_data.py)

```
_load_dump_seed_data()          # Line 234-281 — 调用 pg_restore 子进程
_resolve_seed_file()            # Line 113-155 — 格式优先级解析（DUMP > CSV）
_SeedFormat enum                # Line 35-43 — 定义 CSV/DUMP 两种格式
_SEED_FORMAT_PRIORITY           # Line 47 — [CSV, DUMP]，DUMP 优先级更高
```

**修复方案**：

1. 将 `base_info` 和 `enrichment_index` 从开发数据库导出为 CSV 格式
2. 放入 `config/seeds/003/` 目录（版本号最高，自动覆盖旧版）
3. 简化迁移代码：删除 `_SeedFormat`、`_resolve_seed_file()`、`_load_dump_seed_data()` 等所有 dump 相关逻辑
4. `base_info` 和 `enrichment_index` 改为直接调用 `_load_csv_seed_data()`

**JSON 字段兼容性**：`base_info` 包含 JSONB 字段（这是当初选择 `.dump` 格式的原因），但 Python `csv.writer` 会自动对 JSON 内容加引号转义，读取时 PostgreSQL 也能正确解析 JSON 字符串，**完全兼容**。

**关于高效数据加载**：对于未来可能需要的大批量数据恢复场景（如 `规模明细` 62.5 万行），推荐使用 PostgreSQL 的 `COPY FROM` 命令通过 psycopg2 的 `copy_expert()` 或 psycopg3 的 `cursor.copy()` API 调用，性能与 `pg_restore` 的数据加载几乎一致，且为纯 Python 实现。

---

### 问题 3: `config/seeds/` 目录职责混淆

**现象**：`config/seeds/002/` 目录下混入了 3 个业务事实数据的备份文件。

**当前目录内容**：

```
config/seeds/
├── 001/                          ← 种子数据 v1
│   ├── company_types_classification.csv    ✅ 种子数据
│   ├── enrichment_index.csv                ✅ 种子数据
│   ├── industrial_classification.csv       ✅ 种子数据
│   ├── 产品线.csv / 组织架构.csv / ...       ✅ 种子数据
│   └── ...
├── 002/                          ← 种子数据 v2 + ⚠️ 业务数据混入
│   ├── 客户明细.csv                         ✅ 种子数据（更新版）
│   ├── base_info.dump                      ✅ 种子数据（待转 CSV）
│   ├── enrichment_index.dump               ✅ 种子数据（待转 CSV）
│   ├── customer_plan_contract.dump         ⚠️ 业务数据备份（无代码引用）
│   ├── 收入明细.dump                        ⚠️ 业务数据备份（无代码引用）
│   └── 规模明细.dump                        ⚠️ 业务数据备份（无代码引用）
```

**分析**：

| 文件 | 实际性质 | 代码引用 | 行数量级 |
|------|---------|---------|---------|
| `customer_plan_contract.dump` | 客户年金计划事实数据 | ❌ 无 | ~1,000+ |
| `收入明细.dump` | 收入业务事实数据 | ❌ 无 | 158,480 |
| `规模明细.dump` | 规模业务事实数据 | ❌ 无 | 625,126 |

这 3 个文件是由 ETL 流水线产生和维护的**业务事实数据**，不属于"应用初始化所必需的参考配置"。它们：
- 数据量大（十万级），不应在 `alembic upgrade head` 时自动导入
- 有独立的生命周期（由 ETL 产生、更新、覆盖）
- 恢复操作是按需手动触发的

**修复方案**：将这 3 个 `.dump` 文件迁移至独立的备份目录（如 `data/backups/`），保持 `config/seeds/` 的纯净职责。

---

## 三、实施计划

### Phase 1: 种子数据 CSV 化（消除 pg_restore 依赖）

1. 从开发数据库导出 `base_info` 和 `enrichment_index` 为 CSV → `config/seeds/003/`
2. 简化 `003_seed_static_data.py`：删除全部 dump 相关代码
3. 删除 `import subprocess`、`import os`、`import enum`
4. 验证迁移正常执行

### Phase 2: 目录职责分离

1. 创建 `data/backups/` 目录
2. 将 `config/seeds/002/` 中的 3 个业务 `.dump` 文件迁移过去
3. 更新 `.gitignore`（备份文件不入库或单独管理）
4. 如需恢复工具，创建 CLI 命令使用 `COPY FROM` 纯 Python 加载

### Phase 3: 全局 psycopg v3 评估（可选）

评估是否将整个项目从 psycopg2 统一切换到 psycopg v3，彻底消除 GBK 编码风险。

---

## 四、涉及文件清单

| 文件 | 操作 | Phase |
|------|------|-------|
| `config/seeds/003/base_info.csv` | **[NEW]** 从数据库导出 | 1 |
| `config/seeds/003/enrichment_index.csv` | **[NEW]** 从数据库导出 | 1 |
| `io/schema/migrations/versions/003_seed_static_data.py` | **[MODIFY]** 删除 dump 逻辑 | 1 |
| `config/seeds/002/customer_plan_contract.dump` | **[MOVE]** → `data/backups/` | 2 |
| `config/seeds/002/收入明细.dump` | **[MOVE]** → `data/backups/` | 2 |
| `config/seeds/002/规模明细.dump` | **[MOVE]** → `data/backups/` | 2 |
