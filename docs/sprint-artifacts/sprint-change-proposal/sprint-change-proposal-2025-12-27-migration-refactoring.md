# Sprint Change Proposal: Alembic Migration Refactoring

> **Created**: 2025-12-27
> **Status**: Draft - Pending User Approval
> **Triggered By**: User request (non-story trigger)
> **Mode**: Incremental

---

## 1. Issue Summary

### 1.1 Problem Statement

前期开发方向不明确导致 Alembic 迁移脚本混乱冗余，存在以下问题：

1. **分支结构复杂** - 迁移链在 `20251206` 后分叉为两个分支，需要 merge head
2. **冗余迁移** - `20251214_000002` 和 `20251214_000003` 添加的列在父迁移中已定义
3. **废弃表残留** - `annuity_performance_new` shadow table 已弃用但迁移仍存在
4. **非托管表** - 大量生产表不在 Alembic 迁移管理中
5. **自增字段命名不一致** - 部分表使用 `{entity}_id` 而非统一的 `id`

### 1.2 User Requirements

| 序号 | 需求 | 确认状态 |
|------|------|----------|
| 1 | 审视迁移计划，通过提问式方式确认 | ✅ 已确认 Option A |
| 2 | 清理配套测试脚本 | ✅ 已识别 5 个文件 |
| 3 | 业务明细表自增字段统一命名为 `id` | ✅ 已识别 2 个表 |
| 4 | 更新 `.wdh_env` 示例数据库 | 📋 待执行 |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | 状态 | 影响评估 |
|------|------|---------|
| Epic 7.1 | ✅ Done | 无影响 (已完成) |
| Epic 8 | ⏳ Backlog | **受阻** - 需要干净的迁移基础 |

**分析**: 此变更是 Epic 8 (Testing & Validation Infrastructure) 的前置条件。清理迁移脚本后才能建立可靠的测试基础设施。

### 2.2 Artifact Conflicts

#### Domain Registry Definitions (需修改)

| 文件 | 当前 primary_key | 目标 |
|------|------------------|------|
| `definitions/annuity_plans.py` | `annuity_plans_id` | `id` |
| `definitions/portfolio_plans.py` | `portfolio_plans_id` | `id` |
| `definitions/annuity_performance.py` | `id` | ✅ 无需修改 |
| `definitions/annuity_income.py` | `id` | ✅ 无需修改 |

#### DDL Scripts (需修改)

| 文件 | 当前 | 目标 |
|------|------|------|
| `scripts/create_table/ddl/annuity_plans.sql` | `annuity_plans_id` | `id` |
| `scripts/create_table/ddl/portfolio_plans.sql` | `portfolio_plans_id` | `id` |
| `scripts/create_table/generate_from_json.py` | `{entity}_id` 模式 | `id` 统一模式 |

#### Test Files (需评估)

| 文件 | 评估 |
|------|------|
| `tests/integration/migrations/test_enrichment_index_migration.py` | 需要更新或删除 |
| `tests/integration/migrations/test_enterprise_schema_migration.py` | 需要更新或删除 |
| `tests/integration/scripts/test_legacy_migration_integration.py` | 评估后决定 |
| `tests/io/schema/test_migrations.py` | 需要更新 |
| `tests/unit/test_enterprise_schema_migration_static.py` | 静态测试，可能保留 |

### 2.3 Technical Impact

| 组件 | 影响 |
|------|------|
| 数据库结构 | 需要重建 mapping 表的 `id` 列 |
| Domain Registry | 2 个定义文件需修改 |
| DDL Generator | 无需修改 (已使用 `id`) |
| Insert Builder | 无需修改 (已排除 auto-id) |
| `.wdh_env` | 需要重新初始化 |

---

## 3. Recommended Approach

### 3.1 Selected Path: **Option A - 全新起点 (Full Reset with Backup)**

**理由**:
1. 现有迁移链过于复杂，修复成本高于重建
2. 已有完整的表结构参考文档 (`table-structure-reference.md`)
3. 用户明确确认此方向

### 3.2 Effort & Risk Assessment

| 维度 | 评估 | 说明 |
|------|------|------|
| 工作量 | **Medium** | ~2-3 个工作日 |
| 风险 | **Low** | 有完整文档和备份策略 |
| 时间线影响 | **低** | 不阻塞其他开发 |

### 3.3 表格纳入策略

**确认迁移哪些表格的依据**:

| 优先级 | 迁移时机 | 确认依据 | 表格数量 |
|--------|---------|----------|---------|
| **P0** | 初始迁移 | 当前 4 个已注册 domain + 基础设施表 | 21 张 (18 张需数据 + 3 张仅结构) |
| **P1** | 增量迁移 | 按 domain 开发进度逐步添加 | 待定 |
| **P2** | 后续迁移 | 评估业务需求后决定 | 待定 |

**P0 表格确认来源**:
1. `infrastructure/schema/definitions/` - 已注册的 4 个 domain (annuity_performance, annuity_income, annuity_plans, portfolio_plans)
2. 现有迁移脚本中的基础设施表 (public, enterprise, system schemas)
3. `migration-checklist.md` 中标记为 "✅ 纳入" 的表

**原则**: 不一次性完成全部迁移，按需增量补充

### 3.4 数据来源唯一性原则

> **核心原则**: 生产环境数据只能来自 New Pipeline，禁止依赖 Legacy 数据库

```
┌─────────────────────────────────────────────────────────────┐
│  生产环境数据流 (唯一路径)                                   │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│   Excel/CSV (原始文件)  →  New Pipeline (ETL)  →  Postgres │
│                                                             │
│   ❌ 禁止: Legacy MySQL 作为生产数据来源                     │
└─────────────────────────────────────────────────────────────┘
```

**数据分类与来源**:

| 数据类型 | 示例 | 生产数据来源 | 备注 |
|---------|------|-------------|------|
| **静态参考数据** | 行业分类、公司类型 | `config/seeds/*.csv` + Alembic | 版本化管理 |
| **动态参考数据** | 年金客户、年金计划 | New Pipeline (Excel) | ETL 处理 |
| **业务明细数据** | 规模明细、收入明细 | New Pipeline (Excel) | ETL 处理 |
| **ETL 运行时数据** | enrichment_index | New Pipeline 生成 | 自动填充 |

**开发环境例外**:
- 开发人员可选择使用 `scripts/bootstrap/` 脚本从 Legacy 填充测试数据
- 此操作仅限开发环境，通过环境检查强制隔离

### 3.5 未来新增 Domain 规划

**标准流程 (3 步)**:

```
步骤 1: 创建域定义文件
└── definitions/new_domain.py (使用 register_domain())

步骤 2: 在 definitions/__init__.py 导入
└── from . import new_domain

步骤 3: 创建增量迁移
└── io/schema/migrations/versions/NNN_add_xxx_domain.py
```

**迁移文件命名规范**:

```
io/schema/migrations/versions/
├── 001_initial_infrastructure.py    # 基础设施表 (变化少)
├── 002_initial_domains.py           # 初始域表 (P0)
├── 003_seed_classification.py       # 种子数据
└── NNN_add_xxx_domain.py            # 后续增量迁移 (每个新域一个)
```

**设计优势**:

| 特性 | 说明 |
|------|------|
| **单一真相源** | DomainSchema 定义同时驱动 ETL 验证、DDL 生成、迁移脚本 |
| **声明式扩展** | 新增域只需创建定义文件，无需修改核心代码 |
| **增量迁移** | 每个新域一个迁移文件，不影响已有表 |
| **幂等性保证** | 所有迁移使用 `IF NOT EXISTS` 模式 |

---

## 4. Detailed Change Proposals

### 4.1 Phase 1: 备份与归档

#### [NEW] `io/schema/migrations/versions/_archived/`

```
Action: 创建归档目录
Content: 移动所有现有 10 个迁移文件到此目录
Rationale: 保留历史记录，待新策略稳定后删除
Note: 需修改 Alembic 配置 (如 env.py)，确保忽略 `_archived/` 目录，防止重复加载历史版本导致 ID 冲突。
```

### 4.2 Phase 2: 创建新迁移结构

按照 `migration-consolidation-strategy.md` 的分层设计：

#### [NEW] `001_initial_infrastructure.py`

基础设施表 (14张):
- public: `pipeline_executions`, `data_quality_metrics`
- enterprise: `base_info`, `business_info`, `biz_label`, `enrichment_requests`, `enrichment_index`, `company_types_classification`, `industrial_classification`, `validation_results`
- mapping: `产品线`, `组织架构`, `计划层规模`
- system: `sync_state`

#### [NEW] `002_initial_domains.py`

域表 (7张):
- business: `规模明细`, `收入明细`
- mapping: `年金计划`, `组合计划`, `年金客户`, `产品明细`, `利润指标`

> **注**: 域表仅定义 DDL 结构，不包含数据迁移逻辑。业务数据通过 New Pipeline 获取。

#### [NEW] `003_seed_static_data.py`

种子数据 (~1,350行):
- **Large Datasets** (CSV Source): `company_types_classification` (104行), `industrial_classification` (1,183行)
- **Small Datasets** (Embedded): `产品线`, `组织架构`, `计划层规模`, `产品明细`, `利润指标`

### 4.2.1 种子数据来源指引

> **核心原则**: 种子数据必须版本化管理，提交到代码仓库，与任何外部数据库解耦。

#### 种子数据分类

| 类别 | 定义 | 示例 | 处理方式 |
|------|------|------|----------|
| **静态参考数据** | 变化频率极低，由业务定义 | 行业分类、公司类型 | CSV + Alembic Seed |
| **配置型数据** | 项目内部配置，可硬编码 | 产品线、组织架构 | 嵌入 Alembic 脚本 |

#### 种子数据文件结构

```
config/seeds/
├── company_types_classification.csv    # 104行 - 公司类型分类
├── industrial_classification.csv       # 1,183行 - 国标行业分类
├── product_lines.csv                   # 12行 - 产品线
├── organization.csv                    # 38行 - 组织架构
├── plan_scale_levels.csv               # 7行 - 计划层规模
├── product_details.csv                 # 18行 - 产品明细
└── profit_indicators.csv               # 12行 - 利润指标
```

#### 种子数据来源与维护

| 表名 | 行数 | 数据来源 | 维护方式 |
|------|------|----------|----------|
| company_types_classification | 104 | 国家标准/业务定义 | CSV 版本化，变更时更新 |
| industrial_classification | 1,183 | 国标行业分类 (GB/T 4754) | CSV 版本化，静态数据 |
| 产品线 | 12 | 业务部门定义 | 嵌入脚本或 CSV |
| 组织架构 | 38 | 业务部门定义 | 嵌入脚本或 CSV |
| 计划层规模 | 7 | 业务部门定义 | 嵌入脚本或 CSV |
| 产品明细 | 18 | 业务部门定义 | 嵌入脚本或 CSV |
| 利润指标 | 12 | 财务部门定义 | 嵌入脚本或 CSV |

#### 实现方式

**方式 A: 小量数据 (< 50行) - 嵌入迁移脚本**
```python
def upgrade():
    op.execute("""
        INSERT INTO mapping.产品线 (产品线代码, 产品线名称, ...) VALUES
        ('P01', '年金产品', ...),
        ('P02', '团养产品', ...),
        ...
        ON CONFLICT DO NOTHING;
    """)
```

**方式 B: 大量数据 (> 100行) - 外部 CSV 读取**
```python
import csv
from pathlib import Path

def upgrade():
    seed_file = Path(__file__).parent.parent.parent.parent / 'config' / 'seeds' / 'industrial_classification.csv'
    with open(seed_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            op.execute(f"""
                INSERT INTO enterprise.industrial_classification (...)
                VALUES ('{row["code"]}', '{row["name"]}', ...)
                ON CONFLICT DO NOTHING;
            """)
```

#### 种子数据初始化流程

```
步骤 1: 业务部门提供数据定义
       └── Excel/文档形式，由业务确认

步骤 2: 开发人员转换为 CSV 格式
       └── 保存到 config/seeds/ 目录

步骤 3: 提交到代码仓库
       └── 版本化管理，可追溯变更历史

步骤 4: Alembic 迁移加载
       └── 执行 alembic upgrade head 时自动填充
```

**禁止**: 在迁移脚本中直接连接外部数据库（包括 Legacy MySQL）获取种子数据


### 4.3 Phase 3: 自增字段统一命名

#### [MODIFY] `definitions/annuity_plans.py`

```diff
-        primary_key="annuity_plans_id",
+        primary_key="id",
```

#### [MODIFY] `definitions/portfolio_plans.py`

```diff
-        primary_key="portfolio_plans_id",
+        primary_key="id",
```

#### [MODIFY] `scripts/create_table/ddl/annuity_plans.sql`

```diff
-  "annuity_plans_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
+  "id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
```

#### [MODIFY] `scripts/create_table/ddl/portfolio_plans.sql`

```diff
-  "portfolio_plans_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
+  "id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
```

### 4.4 Phase 4: 测试脚本清理

| 文件 | 操作 |
|------|------|
| `test_enrichment_index_migration.py` | 评估后更新或删除 |
| `test_enterprise_schema_migration.py` | 评估后更新或删除 |
| `test_legacy_migration_integration.py` | 评估后决定 |
| `test_migrations.py` | 更新以匹配新迁移 |
| `test_enterprise_schema_migration_static.py` | 保留静态测试 |

### 4.5 Phase 5: 交叉校验 (新增)

**目的**: 确保新迁移脚本与项目代码保持一致性

#### 校验目标 1: `infrastructure/schema/definitions/`

| 文件 | 校验项 |
|------|--------|
| `annuity_performance.py` | 表结构、索引、primary_key |
| `annuity_income.py` | 表结构、索引、primary_key |
| `annuity_plans.py` | 表结构、索引、primary_key (修改后为 `id`) |
| `portfolio_plans.py` | 表结构、索引、primary_key (修改后为 `id`) |

**校验方法**:
```python
# 使用 DDL Generator 生成 SQL 与迁移脚本对比
from work_data_hub.infrastructure.schema import ddl_generator

for domain in ['annuity_performance', 'annuity_income', 'annuity_plans', 'portfolio_plans']:
    sql = ddl_generator.generate_create_table_sql(domain)
    # 对比迁移脚本中的表定义
```

#### 校验目标 2: `domain/` 层

| 模块 | 校验项 |
|------|--------|
| `domain/annuity_performance/` | models.py 字段与迁移一致 |
| `domain/annuity_income/` | models.py 字段与迁移一致 |
| `domain/pipelines/` | ETL 管道使用的字段 |
| `domain/reference_backfill/` | FK 关系与迁移一致 |

**校验方法**:
1. 比对 `DomainSchema.columns` 与迁移中 `op.create_table()` 的列
2. 验证 `composite_key` 与 UNIQUE 约束一致
3. 确认 Domain 层 models.py 中的字段名与数据库列名一致

### 4.6 Phase 6: 更新 `.wdh_env`

```
Action: 运行 alembic upgrade head
Verify: 所有表结构正确
Data: 确保示例数据可用
```

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

**Scope**: **Moderate** - 需要跨多个组件协调

### 5.2 Handoff Recipients

| 角色 | 责任 |
|------|------|
| **Dev Team** | 执行迁移脚本重构、定义文件修改 |
| **SM** | 创建对应的 Story 跟踪 |

### 5.3 Success Criteria

1. ✅ 所有现有迁移归档到 `_archived/` 目录
2. ✅ 新迁移链线性且无分支
3. ✅ 所有业务明细表自增字段统一为 `id`
4. ✅ `alembic upgrade head` 在新环境成功执行
5. ✅ 相关测试通过或已清理
6. ✅ `.wdh_env` 示例数据库可正常使用

---

## 6. Verification Plan

### 6.1 Automated Tests

```bash
# Run all migration-related tests
pytest tests/integration/migrations/ -v
pytest tests/io/schema/test_migrations.py -v
pytest tests/unit/test_enterprise_schema_migration_static.py -v
```

### 6.2 Manual Verification

1. **迁移验证**: 在干净数据库上执行 `alembic upgrade head`
2. **表结构验证**: 检查所有表的 `id` 字段命名
3. **示例数据验证**: 验证 `.wdh_env` 配置的数据库可正常使用

---

## 7. Structure Diff Analysis Summary

> **重要说明**:
> - Alembic 迁移脚本是针对**从0创建数据库**的场景设计，仅包含 DDL（表结构定义）
> - `p0-table-diff-analysis.md` 中记录的差异仅供参考，用于理解 Legacy 与新架构的设计差异
> - **不在 Alembic 中处理**: 字段重命名、数据清洗、数据类型转换等 DML 操作

### 差异分析用途说明

| 差异类型 | Alembic 处理 | 说明 |
|---------|-------------|------|
| 表结构定义 | ✅ 是 | 使用目标结构（Postgres snake_case 规范）|
| 主键定义 | ✅ 是 | 直接使用 `id` SERIAL 主键 |
| 索引/约束 | ✅ 是 | 按新架构设计创建 |
| 字段重命名 | ❌ 否 | 不适用于 Greenfield 场景 |
| 数据类型转换 | ❌ 否 | 不适用于 Greenfield 场景 |
| 数据过滤 | ❌ 否 | 业务数据由 New Pipeline 获取 |

### 已完成差异分析 (9张表) - 仅供参考

| 表名 | 新架构特性 | 备注 |
|------|-----------|------|
| base_info | +4字段(JSONB), +3索引 | Story 6.2-P7 升级 |
| business_info | id 主键, snake_case 字段 | 新架构规范 |
| biz_label | id 主键, NOT NULL约束 | 新架构规范 |
| 年金客户 | 27字段 | 结构完整 |
| company_types_classification | 8字段 | 静态参考数据 |
| industrial_classification | 10字段 | 静态参考数据 |
| 产品线 | 6字段 | 种子数据 |
| 组织架构 | 9字段 | 种子数据 |
| 计划层规模 | 5字段 | 种子数据 |

---

## 8. 开发环境数据填充 (可选)

> **适用场景**: 开发人员需要快速填充测试数据
> **⚠️ 警告**: 仅限开发环境使用，禁止在生产环境执行

### 8.1 现有脚本 (复用)

项目已有完善的数据迁移脚本体系，无需新建 Bootstrap：

| 脚本目录 | 功能 | 使用场景 |
|---------|------|---------|
| `scripts/migrations/enrichment_index/` | enrichment_index 映射数据迁移 | 公司ID解析缓存填充 |
| `scripts/migrations/mysql_dump_migrator/` | MySQL Dump 批量迁移 | 开发环境完整数据恢复 |
| `scripts/migrations/mysql_to_postgres_sync/` | 索引/外键同步 | DDL 结构补全 |

### 8.2 使用示例

```bash
# 1. 从 MySQL Dump 恢复数据
PYTHONPATH=src uv run python -m scripts.migrations.mysql_dump_migrator.cli migrate \
    tests/fixtures/legacy_db/alldb_backup_20251208.sql \
    --databases mapping business

# 2. 恢复 enrichment_index 映射
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py

# 3. 同步索引和外键 (可选)
PYTHONPATH=src uv run python scripts/migrations/mysql_to_postgres_sync/sync_schema.py \
    --table business.规模明细 --dry-run
```

### 8.3 开发环境 vs 生产环境

| 方面 | 开发环境 | 生产环境 |
|------|---------|---------|
| 数据来源 | Legacy MySQL Dump (临时) | New Pipeline (Excel/CSV) |
| 执行时机 | 环境初始化 | 日常 ETL 运行 |
| 数据质量 | 历史数据，可能不完整 | 业务确认，完整准确 |
| 依赖 | 需要 Dump 文件或 Legacy 连接 | 零外部数据库依赖 |

> **注**: 详细使用说明请参考各脚本目录下的 `README.md`

---

## 9. Related Documents

- [Migration Checklist](file:///e:/Projects/WorkDataHub/docs/specific/migration/migration-checklist.md) - 事实基准
- [P0 Migration Tables](file:///e:/Projects/WorkDataHub/docs/specific/migration/p0-migration-tables.md) - 表格清单
- [P0 Table Diff Analysis](file:///e:/Projects/WorkDataHub/docs/specific/migration/p0-table-diff-analysis.md) - 结构差异分析
- [Migration Consolidation Strategy](file:///e:/Projects/WorkDataHub/docs/specific/migration/migration-consolidation-strategy.md)
- [Table Structure Reference](file:///e:/Projects/WorkDataHub/docs/specific/migration/table-structure-reference.md)
