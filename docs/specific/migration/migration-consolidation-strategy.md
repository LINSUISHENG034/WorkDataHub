# Migration Consolidation Strategy

> **文档状态**: Draft
> **创建日期**: 2024-12-24
> **决策参与者**: Link, Claude (Quick-Dev Workflow)

---

## 1. 背景与动机

### 1.1 问题陈述

由于前期开发方向不明确，`io/schema/migrations/versions/` 目录中产生了过多冗余迁移文件，存在以下问题：

1. **分支结构复杂** - 迁移链在 `20251206` 后分叉为两个分支，需要 merge head
2. **冗余迁移** - 部分迁移添加的列在父迁移中已定义
3. **废弃表残留** - `annuity_performance_new` 等 shadow table 已弃用但迁移仍存在
4. **非托管表** - 大量生产表不在 Alembic 迁移管理中

### 1.2 目标

- 建立**清晰、线性**的迁移历史
- 将关键表纳入迁移管理，实现**新环境一键部署**
- 区分**结构迁移**与**数据导入**的职责边界

---

## 2. 现状分析

### 2.1 原迁移文件清单 (10个)

| 文件 | Revision | Down Revision | 内容 | 状态 |
|------|----------|---------------|------|------|
| `20251113_000001_create_core_tables.py` | 20251113_000001 | None (根) | pipeline_executions, data_quality_metrics | 有效 |
| `20251129_000001_create_annuity_performance_new.py` | 20251129_000001 | 20251113_000001 | annuity_performance_new | ⚠️ 废弃 |
| `20251206_000001_create_enterprise_schema.py` | 20251206_000001 | 20251129_000001 | enterprise schema 全套 | 有效 |
| `20251207_000001_add_next_retry_at_column.py` | 20251207_000001 | 20251206_000001 | enrichment_requests.next_retry_at | 有效 |
| `20251208_000001_create_enrichment_index.py` | 20251208_000001 | 20251206_000001 | enrichment_index 表 | ⚠️ 分支点 |
| `20251212_120000_add_reference_tracking_fields.py` | 20251212_120000 | 20251208_000001 | 参考表跟踪字段 | 有效 |
| `20251214_000001_create_sync_state_table.py` | 20251214_000001 | 20251212_120000 | system.sync_state | 有效 |
| `20251214_000002_add_raw_data_to_base_info.py` | 20251214_000002 | 20251214_000001 | base_info.raw_data | ⚠️ 冗余 |
| `20251214_000003_add_cleansing_status_to_business_info.py` | 20251214_000003 | 20251214_000002 | business_info._cleansing_status | ⚠️ 冗余 |
| `20251219_000001_create_domain_tables.py` | 20251219_000001 | (merge) | business.收入明细 | 合并点 |

### 2.2 原迁移依赖图

```
20251113_000001 (根: core tables)
       ↓
20251129_000001 (annuity_performance_new) ← 废弃
       ↓
20251206_000001 (enterprise schema)
      ↓↘
      ↓  20251208_000001 (enrichment_index) ← 分支点
      ↓         ↓
      ↓  20251212_120000 (reference tracking)
      ↓         ↓
      ↓  20251214_000001 (sync_state)
      ↓         ↓
      ↓  20251214_000002 (raw_data) ← 冗余
      ↓         ↓
      ↓  20251214_000003 (_cleansing_status) ← 冗余
      ↓        ↙
20251207_000001 (next_retry_at)
      ↓↙
20251219_000001 (合并点: domain tables)
```

### 2.3 数据库当前版本

```sql
SELECT version_num FROM alembic_version;
-- 结果: 20251208_000001
```

**问题**: 数据库停留在分支点，后续 5 个迁移未执行。

---

## 3. 决策记录

### 3.1 迁移文件处理策略

| 选项 | 描述 | 决策 |
|------|------|------|
| A | **全新起点** - 删除所有迁移，创建单一 initial migration | ✅ 选中 |
| B | 压缩合并 - 保留根迁移，压缩为 2-3 个逻辑迁移 | - |
| C | 修复链条 - 保留所有迁移，仅删除冗余 | - |

### 3.2 Schema 保留决策

| Schema | 决策 |
|--------|------|
| public | ✅ 保留 |
| enterprise | ✅ 保留 |
| business | ✅ 保留 |
| mapping | ✅ 保留 |
| system | ✅ 保留 |

### 3.3 表格纳入策略

采用**增量迁移**策略：仅纳入当前架构运行所需的表，后续按 domain 开发进度逐步补充。

| 优先级 | 迁移时机 | 表格范围 |
|--------|---------|---------|
| **P0** | 初始迁移 | 当前 4 个已注册 domain + 基础设施表 (19张) |
| **P1/P2** | 增量迁移 | 按 domain 开发进度逐步添加 |

**P0 初始迁移纳入范围 (19张)**:

| Schema | 纳入迁移管理 | 排除 |
|--------|-------------|------|
| public | pipeline_executions, data_quality_metrics | alembic_version (系统表) |
| enterprise | base_info, business_info, biz_label, enrichment_*, *_classification, validation_results | archive_* (3张) |
| business | 规模明细, 收入明细 | 其他 7 张 (待后续 domain) |
| mapping | 年金计划, 组合计划, 年金客户, 产品线, 组织架构, 计划层规模 | 其他 5 张 (待后续) |
| system | sync_state | - |
| customer | - | 全部 21 张 (待后续 domain) |
| finance | - | 全部 7 张 (待后续 domain) |

### 3.4 数据保留策略

采用**幂等迁移**（Idempotent Migration）：
- 已存在的表：跳过创建，保留数据
- 不存在的表：按定义创建
- 新环境部署：自动创建全部表

---

## 4. Legacy 数据库验证分析

### 4.1 数据量统计

通过 `legacy-mysql` MCP 连接验证，获取各表实际数据量：

#### 4.1.1 Mapping Schema

| 表名 | 行数 | 分类 |
|------|------|------|
| 产品线 | 12 | 🟢 种子数据 |
| 利润指标 | 12 | 🟢 种子数据 |
| 产品明细 | 18 | 🟢 种子数据 |
| 管理架构 | 28 | 🟢 种子数据 |
| 组织架构 | 38 | 🟢 种子数据 |
| 计划层规模 | 7 | 🟢 种子数据 |
| 客户灌入 | 144 | 🟢 种子数据 |
| 全量客户 | 0 | 空表 |
| 年金计划 | 1,159 | 🟡 参考数据 |
| 组合计划 | 1,338 | 🟡 参考数据 |
| 年金客户 | 10,997 | 🔴 业务数据 |

#### 4.1.2 Enterprise Schema

| 表名 | 行数 | 分类 |
|------|------|------|
| company_types_classification | 104 | 🟢 种子数据 |
| industrial_classification | 1,183 | 🟢 种子数据 |
| blank_company_id | 494 | 🟡 参考数据 |
| base_info | 28,576 | 🔴 业务数据 |
| business_info | 11,542 | 🔴 业务数据 |
| biz_label | 126,332 | 🔴 业务数据 |
| company_id_mapping | 19,141 | 🔴 业务数据 |
| annuity_account_mapping | 18,248 | 🔴 业务数据 |
| eqc_search_result | 11,820 | 🔴 业务数据 |

#### 4.1.3 Business Schema

| 表名 | 行数 | 分类 |
|------|------|------|
| 规模明细 | 625,126 | 🔴 业务数据 |
| 收入明细 | 158,480 | 🔴 业务数据 |
| 组合业绩 | 571 | 🔴 业务数据 |
| 账管数据 | 8,776 | 🔴 业务数据 |
| 企康缴费 | 2,087 | 🔴 业务数据 |
| 团养缴费 | 2,907 | 🔴 业务数据 |
| 提费扩面 | 812 | 🔴 业务数据 |
| 灌入数据 | 60 | 🔴 业务数据 |
| 手工调整 | 60 | 🔴 业务数据 |

### 4.2 数据分类标准

| 分类 | 行数范围 | 导入策略 |
|------|---------|---------|
| 🟢 种子数据 | < 200 | 纳入 Alembic 迁移 |
| 🟡 参考数据 | 200 - 2,000 | 独立 Python 脚本 |
| 🔴 业务数据 | > 2,000 | 仅结构迁移，数据走 ETL |

---

## 5. 最终迁移策略

### 5.1 迁移文件结构 (分层设计)

采用**分层迁移**策略，将变化频率不同的表分离：

```
io/schema/migrations/versions/
│
├── 001_initial_infrastructure.py    # 基础设施表 (变化少，手动维护)
│   ├── public.pipeline_executions
│   ├── public.data_quality_metrics
│   ├── enterprise.base_info
│   ├── enterprise.business_info
│   ├── enterprise.biz_label
│   ├── enterprise.enrichment_requests
│   ├── enterprise.enrichment_index
│   ├── enterprise.company_types_classification (结构)
│   ├── enterprise.industrial_classification (结构)
│   ├── enterprise.validation_results
│   ├── mapping.产品线
│   ├── mapping.组织架构
│   ├── mapping.计划层规模
│   └── system.sync_state
│
├── 002_initial_domains.py           # 初始域表 (基于 domain_registry)
│   ├── business.规模明细 (annuity_performance)
│   ├── business.收入明细 (annuity_income)
│   ├── mapping.年金计划 (annuity_plans)
│   ├── mapping.组合计划 (portfolio_plans)
│   └── mapping.年金客户
│
├── 003_seed_classification.py       # 种子数据 (~1,300行)
│   ├── enterprise.company_types_classification (104行)
│   └── enterprise.industrial_classification (1,183行)
│
└── NNN_add_xxx_domain.py            # 后续增量迁移 (每个新域一个文件)
```

**分层原则**:
- **001**: 基础设施表 - 结构稳定，变化少，手动维护
- **002**: 域表 - 可利用 `domain_registry.ddl_generator` 生成
- **003**: 种子数据 - 分类参考数据
- **NNN**: 增量迁移 - 新增域时创建

### 5.2 独立数据导入脚本

```
scripts/data/
├── seed_mapping_reference.py       # mapping 参考数据
│   ├── 产品线 (12行)
│   ├── 产品明细 (18行)
│   ├── 利润指标 (12行)
│   ├── 管理架构 (28行)
│   ├── 组织架构 (38行)
│   ├── 计划层规模 (7行)
│   ├── 客户灌入 (144行)
│   ├── 年金计划 (1,159行)
│   ├── 组合计划 (1,338行)
│   └── 年金客户 (10,997行)
│
└── seed_enterprise_mapping.py      # enterprise 映射数据
    └── blank_company_id (494行)
```

### 5.3 幂等迁移模板

```python
def _table_exists(conn, table_name: str, schema: str) -> bool:
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
        )
    """), {"schema": schema, "table": table_name})
    return result.scalar()

def upgrade():
    conn = op.get_bind()

    # 仅在表不存在时创建
    if not _table_exists(conn, "年金计划", "mapping"):
        op.create_table(...)
```

---

## 6. 执行计划

### 6.1 Phase 1: 准备

- [ ] 备份当前 `alembic_version` 表
- [ ] 备份现有迁移文件到 `migrations/versions/_archived/`
- [ ] 清空 `alembic_version` 表

### 6.2 Phase 2: 创建新迁移

- [ ] 创建 `001_initial_infrastructure.py` (基础设施表)
- [ ] 创建 `002_initial_domains.py` (域表，可利用 ddl_generator)
- [ ] 创建 `003_seed_classification.py` (种子数据)
- [ ] 验证迁移脚本语法

### 6.3 Phase 3: 验证

- [ ] 在测试数据库执行 `alembic upgrade head`
- [ ] 验证表结构正确性
- [ ] 验证种子数据完整性

### 6.4 Phase 4: 生产部署

- [ ] 设置 `alembic_version` 为新的 head
- [ ] 验证生产数据库状态

---

## 7. 附录

### 7.1 Legacy 数据库连接信息

- **MCP Server**: legacy-mysql
- **实际类型**: PostgreSQL (从 schema_owner 判断)
- **验证时间**: 2024-12-24

### 7.2 相关文档

- [Database Schema Panorama](../../database-schema-panorama.md)
- [Project Context](../../project-context.md)

---

## 8. 可扩展性设计 (新增 Domain)

### 8.1 架构基础

项目已具备完善的 Domain Registry 架构，支持**声明式域定义**：

```
infrastructure/schema/
├── core.py          # DomainSchema, ColumnDef, IndexDef 类型定义
├── registry.py      # 全局注册表 (register_domain, get_domain, list_domains)
├── ddl_generator.py # generate_create_table_sql() - 从定义生成 DDL
└── definitions/     # 域定义文件 (每个域一个文件)
```

### 8.2 新增 Domain 的标准流程

**步骤 1**: 创建域定义文件 `definitions/new_domain.py`

```python
from ..core import ColumnDef, ColumnType, DomainSchema, IndexDef
from ..registry import register_domain

register_domain(
    DomainSchema(
        domain_name="new_domain",
        pg_schema="business",
        pg_table="新域表",
        sheet_name="新域表",
        primary_key="new_domain_id",
        delete_scope_key=["月度", "company_id"],
        composite_key=["月度", "关键字段", "company_id"],
        columns=[
            ColumnDef("月度", ColumnType.DATE, nullable=False),
            ColumnDef("关键字段", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),
            # ... 更多列定义
        ],
        indexes=[
            IndexDef(["月度"]),
            IndexDef(["company_id"]),
            IndexDef(["月度", "company_id"]),
        ],
    )
)
```

**步骤 2**: 在 `definitions/__init__.py` 导入新域

```python
from . import new_domain  # 添加这一行
```

**步骤 3**: 创建增量迁移

```python
# io/schema/migrations/versions/YYYYMMDD_000001_add_new_domain.py
from work_data_hub.infrastructure.schema import ddl_generator

def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "新域表", "business"):
        # 方式 A: 使用 ddl_generator (推荐)
        sql = ddl_generator.generate_create_table_sql("new_domain")
        conn.execute(sa.text(sql))

        # 方式 B: 手动定义 (与现有迁移一致)
        op.create_table(...)
```

### 8.3 迁移文件分层策略

采用**分层迁移**，隔离变化频率不同的表：

```
io/schema/migrations/versions/
│
├── 001_initial_infrastructure.py    # 基础设施表 (变化少)
│   ├── public.pipeline_executions
│   ├── public.data_quality_metrics
│   ├── enterprise.* (全部)
│   └── system.sync_state
│
├── 002_initial_domains.py           # 初始域表 (基于 domain_registry)
│   ├── business.规模明细
│   ├── business.收入明细
│   ├── mapping.年金计划
│   └── mapping.组合计划
│
├── 003_seed_classification.py       # 种子数据
│   ├── enterprise.company_types_classification
│   └── enterprise.industrial_classification
│
└── NNN_add_xxx_domain.py            # 后续增量迁移 (每个新域一个)
```

### 8.4 设计优势

| 特性 | 描述 |
|------|------|
| **单一真相源** | DomainSchema 定义同时驱动 ETL 验证、DDL 生成、迁移脚本 |
| **声明式扩展** | 新增域只需创建定义文件，无需修改核心代码 |
| **增量迁移** | 每个新域一个迁移文件，不影响已有表 |
| **幂等性保证** | 所有迁移使用 `IF NOT EXISTS` 模式 |
| **向后兼容** | 基础设施表与域表分离，互不干扰 |

### 8.5 DDL Generator 验证

现有 `ddl_generator.generate_create_table_sql()` 输出示例：

```sql
-- DDL for domain: annuity_performance
-- Table: business."规模明细"

DROP TABLE IF EXISTS business."规模明细" CASCADE;

CREATE TABLE business."规模明细" (
  "id" INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- Business columns
  "月度" DATE NOT NULL,
  "业务类型" VARCHAR(255),
  "计划代码" VARCHAR(255) NOT NULL,
  -- ... (24 columns total)

  -- Audit columns
  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度" ON business."规模明细" ("月度");
-- ... (9 indexes total)

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_annuity_performance_updated_at() ...
```

---

## 9. 变更历史

| 日期 | 变更内容 | 作者 |
|------|---------|------|
| 2024-12-24 | 初始版本 - 策略讨论与决策记录 | Link, Claude |
| 2024-12-24 | 新增可扩展性设计章节 (Section 8) | Link, Claude |
