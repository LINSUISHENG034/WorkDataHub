# Sprint Change Proposal: Unified Domain Schema Management Architecture

**Date:** 2025-12-18
**Triggered By:** Multi-environment Deployment Readiness Review
**Change Scope:** Moderate
**Status:** Pending Approval

---

## 1. Issue Summary

### Problem Statement

当前项目存在两套并行的数据库 Schema 管理机制，导致：
1. **Schema 漂移风险**：列定义分散在 4+ 处，需手动同步
2. **部署复杂度高**：多环境部署需协调两套机制
3. **维护成本高**：新增 Domain 需在多处重复定义

### Discovery Context

- **When Discovered:** 2025-12-18，多环境部署规划评审
- **Discovery Method:** 架构分析：`io/schema/migrations/` vs `scripts/create_table/`
- **Affected Component:** Domain Schema 管理体系

### Current Architecture Analysis

| 机制 | 位置 | 管理范围 | 问题 |
|------|------|---------|------|
| **Alembic 迁移** | `io/schema/migrations/` | 新管道表 (`annuity_performance_new`) | 版本化，但产出 shadow 表 |
| **DDL 脚本** | `scripts/create_table/` | 遗留表 (`business."规模明细"`) | 手动维护，无版本控制 |

### Schema Definition Fragmentation

| 定义位置 | 内容 | 同步风险 |
|---------|------|---------|
| `scripts/create_table/ddl/*.sql` | PostgreSQL DDL | 高 |
| `io/schema/migrations/versions/*.py` | Alembic 迁移 | 高 |
| `domain/*/models.py` | Pydantic 模型 (In/Out) | 中 |
| `domain/*/schemas.py` | Pandera Schema (Bronze/Gold) | 中 |
| `domain/*/constants.py` | 列名常量 | 中 |

**核心问题**：缺乏 Single Source of Truth (单一真相来源)

### Physical Table Creation Gap

当前 Alembic 迁移 **不包括** Domain 主表的创建：

| 表类型 | 当前创建机制 | 示例 |
|-------|-------------|------|
| **Domain 物理表** | `scripts/create_table/` | `business."规模明细"` |
| **Shadow 表** | Alembic | `annuity_performance_new` |
| **企业 Schema 表** | Alembic | `enterprise.company_mapping` |
| **核心系统表** | Alembic | `pipeline_executions`, `sync_state` |

**问题**: Domain 主表与其他表使用不同的创建机制，导致部署不一致。

---

## 2. Impact Analysis

### Epic Impact

| Epic | Current Status | Impact | Action Required |
|------|----------------|--------|-----------------|
| **Epic 7+** | `backlog` | **Direct** | 新 Domain 开发依赖统一架构 |
| Epic 6.x | Various | Indirect | 现有代码需渐进式迁移 |

### Module Impact

| 模块 | 影响范围 | 变更类型 |
|------|---------|---------|
| `io/schema/` | 新增 `domain_registry.py` | Create |
| `io/schema/migrations/` | 成为唯一迁移机制 | Enhance |
| `scripts/create_table/` | 职责重新定位 | Scope Change |
| `domain/annuity_performance/` | 引用 registry | Refactor |
| `domain/annuity_income/` | 引用 registry | Refactor |
| `infrastructure/models/` | 新增共享模型 | Create |

### Code Duplication Identified (Detailed)

| 重复代码 | 位置 A | 位置 B | 行数 | 提取目标 |
|---------|--------|--------|------|---------|
| `EnrichmentStats` | `annuity_performance/models.py:340-365` | `annuity_income/models.py:180-210` | ~30×2 | `infrastructure/models/shared.py` |
| `BronzeValidationSummary` | `annuity_performance/schemas.py:66-71` | `annuity_income/schemas.py:52-59` | ~8×2 | `infrastructure/models/shared.py` |
| `GoldValidationSummary` | `annuity_performance/schemas.py:74-78` | `annuity_income/schemas.py:62-69` | ~8×2 | `infrastructure/models/shared.py` |
| `ProcessingResultWithEnrichment` | `annuity_performance/models.py:368-380` | `annuity_income/models.py:213-225` | ~12×2 | `infrastructure/models/shared.py` (泛型化) |
| `apply_domain_rules` | 两个 `models.py` | 几乎相同 | ~10×2 | `infrastructure/cleansing/helpers.py` |
| `validate_bronze_dataframe` | 两个 `schemas.py` | 结构相同 | ~40×2 | `infrastructure/validation/domain_validators.py` |
| `validate_gold_dataframe` | 两个 `schemas.py` | 结构相同 | ~50×2 | `infrastructure/validation/domain_validators.py` |

**总重复代码：约 316 行**

### Missing DDL Identified

| Domain | DDL 文件 | manifest.yml | 状态 |
|--------|---------|--------------|------|
| `annuity_performance` | ✅ 存在 | ✅ 已配置 | 需迁移到 Alembic |
| `annuity_income` | ❌ **缺失** | ❌ **未配置** | 需新建 |
| `annuity_plans` | ✅ 存在 | ✅ 已配置 | 需迁移到 Alembic |
| `portfolio_plans` | ✅ 存在 | ✅ 已配置 | 需迁移到 Alembic |

---

## 3. Recommended Approach

### Selected Path: Unified Domain Registry + Gradual Migration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Single Source of Truth                       │
│           io/schema/domain_registry.py                          │
│                                                                 │
│  - Domain 元数据 (名称映射、表名、主键、索引)                      │
│  - 列定义 (类型、约束、默认值)                                    │
│  - 迁移配置 (delete_scope_key, composite_key)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Pydantic Model │  │  Pandera Schema │  │ Alembic Migration│
│    (Reference)  │  │    (Reference)  │  │    (Generated)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Implementation Phases (Detailed)

| Phase | Description | Priority | Effort | Immediate Benefit |
|-------|-------------|----------|--------|-------------------|
| **Phase 0** | 创建 `domain_registry.py` | Critical | 4h | 新 Domain 开发可用 |
| **Phase 1** | 提取共享模型到 `infrastructure/` | High | 3h | 代码重复消除 |
| **Phase 2** | 泛化验证函数 | High | 3h | 维护成本降低 |
| **Phase 3** | 统一到 Alembic 迁移 | High | 4h | 部署简化 |
| **Phase 4** | 重新定位 `scripts/create_table/` 职责 | Medium | 1h | 职责清晰化 |

---

### Phase 0: Domain Registry Creation

**目标：** 建立 Single Source of Truth

**任务清单：**
```yaml
tasks:
  - name: 创建 domain_registry.py 基础框架
    file: src/work_data_hub/io/schema/domain_registry.py
    includes:
      - ColumnType 枚举
      - ColumnDef 数据类
      - DomainSchema 数据类
      - register_domain() / get_domain() / list_domains()

  - name: 注册 annuity_performance 完整定义
    source: scripts/create_table/ddl/annuity_performance.sql + domain/annuity_performance/schemas.py
    fields: 22 列 + 9 索引

  - name: 注册 annuity_income 完整定义 (新增！)
    source: domain/annuity_income/schemas.py (DDL 缺失需补充)
    fields: 14 列 + 4 索引

  - name: 注册 annuity_plans 定义
    source: scripts/create_table/ddl/annuity_plans.sql

  - name: 注册 portfolio_plans 定义
    source: scripts/create_table/ddl/portfolio_plans.sql

  - name: 添加辅助方法
    methods:
      - generate_create_table_sql(domain_name) -> str
      - generate_pandera_schema(domain_name) -> pa.DataFrameSchema
      - get_composite_key(domain_name) -> List[str]
```

**验证步骤：**
```yaml
tests:
  - test_domain_registry_covers_all_domains
  - test_get_domain_returns_correct_schema
  - test_column_definitions_complete
  - test_generate_ddl_matches_existing
```

---

### Phase 1: Shared Models Extraction

**目标：** 消除 ~100 行重复代码

**任务清单：**
```yaml
tasks:
  - name: 创建 infrastructure/models/ 包
    files:
      - src/work_data_hub/infrastructure/models/__init__.py
      - src/work_data_hub/infrastructure/models/shared.py

  - name: 提取 EnrichmentStats
    from: domain/annuity_performance/models.py, domain/annuity_income/models.py
    to: infrastructure/models/shared.py

  - name: 提取 BronzeValidationSummary
    from: domain/*/schemas.py
    to: infrastructure/models/shared.py

  - name: 提取 GoldValidationSummary
    from: domain/*/schemas.py
    to: infrastructure/models/shared.py

  - name: 提取并泛型化 ProcessingResultWithEnrichment
    from: domain/*/models.py
    to: infrastructure/models/shared.py
    change: 使用 Generic[T] 支持不同 domain 的 Out 模型

  - name: 更新 domain 层 import
    files:
      - domain/annuity_performance/models.py
      - domain/annuity_performance/schemas.py
      - domain/annuity_income/models.py
      - domain/annuity_income/schemas.py
```

**验证步骤：**
```yaml
tests:
  - test_enrichment_stats_behavior_unchanged
  - test_validation_summary_serialization
  - test_existing_domain_tests_pass (回归测试)
```

---

### Phase 2: Validation Functions Generalization

**目标：** 消除 ~180 行重复代码

**任务清单：**
```yaml
tasks:
  - name: 创建泛化验证模块
    file: src/work_data_hub/infrastructure/validation/domain_validators.py

  - name: 提取 validate_bronze_dataframe 泛化版本
    signature: |
      def validate_bronze_dataframe(
          df: pd.DataFrame,
          domain_name: str,  # 从 registry 获取配置
          failure_threshold: float = 0.10
      ) -> Tuple[pd.DataFrame, BronzeValidationSummary]

  - name: 提取 validate_gold_dataframe 泛化版本
    signature: |
      def validate_gold_dataframe(
          df: pd.DataFrame,
          domain_name: str,  # 从 registry 获取配置
          project_columns: bool = True,
          aggregate_duplicates: bool = False
      ) -> Tuple[pd.DataFrame, GoldValidationSummary]

  - name: Domain 层改为调用泛化函数
    files:
      - domain/annuity_performance/schemas.py (保留别名导出兼容性)
      - domain/annuity_income/schemas.py (保留别名导出兼容性)
```

**验证步骤：**
```yaml
tests:
  - test_generalized_bronze_validation_matches_original
  - test_generalized_gold_validation_matches_original
  - test_domain_specific_configs_applied_correctly
```

---

### Phase 3: Alembic Migration Unification

**目标：** 统一部署机制

**任务清单：**
```yaml
tasks:
  - name: 创建 annuity_performance 表迁移
    file: io/schema/migrations/versions/YYYYMMDD_create_annuity_performance.py
    actions:
      - 主键重命名: id → id
      - 从 domain_registry 生成 DDL
      - Conditional Create 支持

  - name: 创建 annuity_income 表迁移 (新增！)
    file: io/schema/migrations/versions/YYYYMMDD_create_annuity_income.py
    actions:
      - 主键: id (新表直接使用统一命名)
      - 从 domain_registry 生成 DDL

  - name: 创建 mapping 表迁移
    file: io/schema/migrations/versions/YYYYMMDD_create_mapping_tables.py
    tables:
      - mapping."年金计划" (annuity_plans)
      - mapping."组合计划" (portfolio_plans)
    actions:
      - 主键重命名: *_id → id

  - name: 添加迁移生成辅助脚本
    file: scripts/generate_migration_from_registry.py
    function: 从 domain_registry 自动生成 Alembic 迁移代码
```

**验证步骤：**
```yaml
tests:
  - test_alembic_upgrade_creates_all_tables
  - test_alembic_downgrade_removes_tables
  - test_table_structure_matches_registry
  - test_primary_key_named_id
```

---

### Phase 4: scripts/create_table/ Scope Redefinition

**目标：** 职责清晰化

**任务清单：**
```yaml
tasks:
  - name: 更新 manifest.yml
    changes:
      - 标记 domain DDL 为 deprecated
      - 添加迁移说明注释
      - 定义新职责范围

  - name: 归档旧 DDL 文件
    action: 移动到 scripts/create_table/ddl/deprecated/
    files:
      - annuity_performance.sql
      - annuity_plans.sql
      - portfolio_plans.sql

  - name: 更新 README
    file: scripts/create_table/README.md
    content: 说明新职责范围和迁移指南
```

**验证步骤：**
```yaml
tests:
  - verify_deprecated_ddl_not_used_in_ci
  - verify_alembic_is_primary_migration_tool
```

### `scripts/create_table/` Scope Redefinition

**原职责 (废弃)**:
- 管理 Domain 主表 DDL (`annuity_performance`, `annuity_plans`, etc.)

**新职责 (保留)**:
- 创建临时数据表 (Temporary Tables)
- 创建独立数据表 (Standalone/Utility Tables)
- 一次性迁移脚本
- 数据修复脚本

**文件变更**:
```yaml
# scripts/create_table/manifest.yml - 更新说明
# SCOPE REDEFINITION (2025-12-18):
# This module is now ONLY for:
#   - Temporary tables for data processing
#   - Standalone utility tables not part of domain schema
#   - One-time migration scripts
#   - Data repair scripts
#
# Domain tables (annuity_performance, annuity_plans, etc.) are now managed via:
#   - io/schema/domain_registry.py (Single Source of Truth)
#   - io/schema/migrations/ (Alembic versioned migrations)
```

### ROI Analysis (Revised)

| 项目 | 估算值 |
|------|--------|
| **一次性投入** | |
| - Phase 0: 创建 domain_registry | 4h |
| - Phase 1: 提取共享模型 | 3h |
| - Phase 2: 泛化验证函数 | 3h |
| - Phase 3: Alembic 迁移统一 | 4h |
| - Phase 4: 重新定位 scripts/create_table | 1h |
| **总投入** | **~15h (约 2 人天)** |
| | |
| **技术债清理收益** | |
| - 消除重复代码 | ~316 行 |
| - 统一 Schema 定义位置 | 6 处 → 1 处 |
| - 补全缺失的 annuity_income DDL | 1 个 domain |
| - 主键命名统一化 | 4 张表 |
| | |
| **年度运维节省 (预估)** | |
| - 新 domain 开发 (5个 × 4h) | 20h |
| - Schema 变更维护 (10次 × 1.5h) | 15h |
| - 部署问题排查 | 10h |
| - Bug 修复效率提升 | 10h |
| **总节省** | **~55h (约 7 人天)** |
| | |
| **ROI** | **~3.7x** (首年) |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 迁移过程引入回归 | Medium | Medium | 渐进式迁移 + 完整测试 |
| 现有代码兼容性问题 | Low | Medium | 保持向后兼容别名 |
| 团队学习曲线 | Low | Low | 文档 + 示例代码 |

### Domain Physical Table Migration Strategy

#### 3.1 Alembic 统一管理所有 Domain 物理表

统一后，Alembic 将负责创建 **所有** Domain 物理表：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Alembic Migrations                           │
│                                                                 │
│  负责创建所有 Domain 物理表:                                      │
│  ├── business."规模明细"    (annuity_performance)               │
│  ├── business."收入明细"    (annuity_income)                    │
│  ├── mapping."年金计划"     (annuity_plans)                     │
│  └── mapping."组合计划"     (portfolio_plans)                   │
│                                                                 │
│  以及企业级表:                                                   │
│  ├── enterprise.company_mapping                                 │
│  ├── enrichment_index                                           │
│  └── 其他系统表...                                               │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.2 已存在表的迁移策略

对于已经在生产环境存在的表，采用 **Conditional Create** 策略：

```python
# io/schema/migrations/versions/YYYYMMDD_create_annuity_performance.py

def upgrade() -> None:
    """Create annuity_performance table (business.规模明细)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 检查表是否已存在（兼容已有生产环境）
    existing_tables = inspector.get_table_names(schema="business")
    if "规模明细" in existing_tables:
        # 表已存在，跳过创建，仅记录日志
        print("Table business.规模明细 already exists, skipping creation")
        return

    # 新环境：创建表
    op.create_table(
        "规模明细",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # ... 其他列
        schema="business"
    )
```

#### 3.3 Shadow 表 (`_new` 后缀) 处理计划

| 阶段 | 状态 | 操作 |
|------|------|------|
| 当前 | 平行验证中 | `annuity_performance_new` 与遗留表并存 |
| 验证完成后 | 切换 | 重命名或数据迁移 |
| 最终状态 | 废弃 | 删除 `_new` 表，统一使用标准表名 |

**切换迁移示例**:
```python
# io/schema/migrations/versions/YYYYMMDD_cutover_annuity_performance.py

def upgrade() -> None:
    """Cutover from shadow table to production table."""
    # Option A: 重命名（如果结构完全一致）
    # op.rename_table("annuity_performance_new", "规模明细", schema="business")

    # Option B: 数据迁移（如果需要转换）
    # op.execute("INSERT INTO business.\"规模明细\" SELECT ... FROM annuity_performance_new")
    # op.drop_table("annuity_performance_new")
    pass
```

#### 3.4 主键命名规范

**规范**: 所有业务明细表的自增主键统一命名为 `id`

| 变更前 | 变更后 | 原因 |
|-------|--------|------|
| `id` | `id` | 简洁统一 |
| `id` | `id` | 简洁统一 |
| `annuity_plans_id` | `id` | 简洁统一 |
| `portfolio_plans_id` | `id` | 简洁统一 |

**理由**:
1. **业务无关性**: 自增主键仅作为技术标识，无业务含义
2. **SQL 简洁性**: `SELECT id FROM ...` 比 `SELECT id FROM ...` 更简洁
3. **跨表一致性**: 所有业务明细表使用相同的主键命名，降低认知负担
4. **ORM 友好**: 大多数 ORM 框架默认使用 `id` 作为主键名

**DDL 示例**:
```sql
CREATE TABLE business."规模明细" (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- 业务字段...
    "月度" DATE NOT NULL,
    "计划代码" VARCHAR(255) NOT NULL,
    -- ...
);
```

---

## 4. Detailed Change Proposals

### 4.1 New File: Domain Registry

**File:** `src/work_data_hub/io/schema/domain_registry.py`

```python
"""
Domain Registry - Single Source of Truth for all domain schema definitions.

This module provides centralized metadata for:
- Domain name mappings (English ↔ Chinese table names)
- Column definitions (types, constraints, nullability)
- Migration configurations (delete_scope_key, composite_key)
- Index definitions

Usage:
    from work_data_hub.io.schema.domain_registry import get_domain, DOMAIN_REGISTRY

    schema = get_domain("annuity_performance")
    print(schema.table_name)  # "规模明细"
    print(schema.delete_scope_key)  # ["月度", "计划代码", "company_id"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class ColumnType(Enum):
    """Supported column types for domain schemas."""
    STRING = "string"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"


@dataclass
class ColumnDef:
    """Definition of a single column in a domain schema."""
    name: str
    column_type: ColumnType
    nullable: bool = True
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    check_constraint: Optional[str] = None
    description: str = ""
    is_primary_key: bool = False


@dataclass
class DomainSchema:
    """Complete schema definition for a domain."""
    domain_name: str              # Standard domain name: annuity_performance
    table_name: str               # Database table name: 规模明细
    sheet_name: str               # Excel sheet name (may differ from table_name)
    schema_name: str = "business" # Database schema
    primary_key: str = "id"       # Technical primary key (unified as 'id' for all business tables)
    delete_scope_key: List[str] = field(default_factory=list)
    composite_key: List[str] = field(default_factory=list)
    columns: List[ColumnDef] = field(default_factory=list)
    bronze_required: List[str] = field(default_factory=list)
    gold_required: List[str] = field(default_factory=list)
    numeric_columns: List[str] = field(default_factory=list)
    indexes: List[List[str]] = field(default_factory=list)


# Central registry of all domains
DOMAIN_REGISTRY: Dict[str, DomainSchema] = {}


def register_domain(schema: DomainSchema) -> None:
    """Register a domain schema in the central registry."""
    DOMAIN_REGISTRY[schema.domain_name] = schema


def get_domain(name: str) -> DomainSchema:
    """Retrieve a domain schema by name."""
    if name not in DOMAIN_REGISTRY:
        raise KeyError(f"Domain '{name}' not found in registry. Available: {list(DOMAIN_REGISTRY.keys())}")
    return DOMAIN_REGISTRY[name]


def list_domains() -> List[str]:
    """List all registered domain names."""
    return list(DOMAIN_REGISTRY.keys())


# =============================================================================
# Domain Registrations
# =============================================================================

register_domain(DomainSchema(
    domain_name="annuity_performance",
    table_name="规模明细",
    sheet_name="规模明细",
    schema_name="business",
    primary_key="id",  # Unified primary key naming
    delete_scope_key=["月度", "计划代码", "company_id"],
    composite_key=["月度", "计划代码", "组合代码", "company_id"],
    bronze_required=["月度", "计划代码", "客户名称", "期初资产规模", "期末资产规模", "投资收益", "当期收益率"],
    gold_required=["月度", "计划代码", "company_id", "客户名称", "期初资产规模", "期末资产规模", "投资收益"],
    numeric_columns=["期初资产规模", "期末资产规模", "供款", "流失_含待遇支付", "流失", "待遇支付", "投资收益", "年化收益率"],
    columns=[
        ColumnDef("月度", ColumnType.DATE, nullable=False, description="Report date (月度)"),
        ColumnDef("计划代码", ColumnType.STRING, nullable=False, max_length=255, description="Plan code (计划代码)"),
        ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50, description="Company identifier"),
        ColumnDef("业务类型", ColumnType.STRING, nullable=True, max_length=255, description="Business type"),
        ColumnDef("计划类型", ColumnType.STRING, nullable=True, max_length=255, description="Plan type"),
        ColumnDef("计划名称", ColumnType.STRING, nullable=True, max_length=255, description="Plan name"),
        ColumnDef("组合类型", ColumnType.STRING, nullable=True, max_length=255, description="Portfolio type"),
        ColumnDef("组合代码", ColumnType.STRING, nullable=True, max_length=255, description="Portfolio code"),
        ColumnDef("组合名称", ColumnType.STRING, nullable=True, max_length=255, description="Portfolio name"),
        ColumnDef("客户名称", ColumnType.STRING, nullable=True, max_length=255, description="Customer name"),
        ColumnDef("期初资产规模", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, check_constraint=">=0", description="Starting assets"),
        ColumnDef("期末资产规模", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, check_constraint=">=0", description="Ending assets"),
        ColumnDef("供款", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, description="Contribution"),
        ColumnDef("流失_含待遇支付", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, description="Loss with benefit"),
        ColumnDef("流失", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, description="Loss"),
        ColumnDef("待遇支付", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, description="Benefit payment"),
        ColumnDef("投资收益", ColumnType.DECIMAL, nullable=True, precision=18, scale=4, description="Investment return"),
        ColumnDef("年化收益率", ColumnType.DECIMAL, nullable=True, precision=10, scale=6, description="Annualized return rate"),
        ColumnDef("机构代码", ColumnType.STRING, nullable=True, max_length=255, description="Institution code"),
        ColumnDef("机构名称", ColumnType.STRING, nullable=True, max_length=255, description="Institution name"),
        ColumnDef("产品线代码", ColumnType.STRING, nullable=True, max_length=255, description="Product line code"),
        ColumnDef("年金账户号", ColumnType.STRING, nullable=True, max_length=50, description="Pension account number"),
        ColumnDef("年金账户名", ColumnType.STRING, nullable=True, max_length=255, description="Pension account name"),
    ],
    indexes=[
        ["月度"],
        ["计划代码"],
        ["company_id"],
        ["机构代码"],
        ["产品线代码"],
        ["年金账户号"],
        ["月度", "计划代码"],
        ["月度", "company_id"],
        ["月度", "计划代码", "company_id"],
    ],
))

register_domain(DomainSchema(
    domain_name="annuity_income",
    table_name="收入明细",
    sheet_name="收入明细",
    schema_name="business",
    primary_key="id",  # Unified primary key naming
    delete_scope_key=["月度", "计划号", "company_id"],
    composite_key=["月度", "计划号", "组合代码", "company_id"],
    bronze_required=["月度", "计划号", "客户名称", "业务类型", "固费", "浮费", "回补", "税"],
    gold_required=["月度", "计划号", "company_id", "客户名称", "固费", "浮费", "回补", "税"],
    numeric_columns=["固费", "浮费", "回补", "税"],
    columns=[
        ColumnDef("月度", ColumnType.DATE, nullable=False, description="Report date"),
        ColumnDef("计划号", ColumnType.STRING, nullable=False, max_length=255, description="Plan code"),
        ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50, description="Company identifier"),
        ColumnDef("客户名称", ColumnType.STRING, nullable=False, max_length=255, description="Customer name"),
        ColumnDef("年金账户名", ColumnType.STRING, nullable=True, max_length=255, description="Pension account name"),
        ColumnDef("业务类型", ColumnType.STRING, nullable=True, max_length=255, description="Business type"),
        ColumnDef("计划类型", ColumnType.STRING, nullable=True, max_length=255, description="Plan type"),
        ColumnDef("组合代码", ColumnType.STRING, nullable=True, max_length=255, description="Portfolio code"),
        ColumnDef("产品线代码", ColumnType.STRING, nullable=True, max_length=255, description="Product line code"),
        ColumnDef("机构代码", ColumnType.STRING, nullable=True, max_length=255, description="Institution code"),
        ColumnDef("固费", ColumnType.DECIMAL, nullable=False, precision=18, scale=4, description="Fixed fee"),
        ColumnDef("浮费", ColumnType.DECIMAL, nullable=False, precision=18, scale=4, description="Variable fee"),
        ColumnDef("回补", ColumnType.DECIMAL, nullable=False, precision=18, scale=4, description="Rebate"),
        ColumnDef("税", ColumnType.DECIMAL, nullable=False, precision=18, scale=4, description="Tax"),
    ],
    indexes=[
        ["月度"],
        ["计划号"],
        ["company_id"],
        ["月度", "计划号", "company_id"],
    ],
))

register_domain(DomainSchema(
    domain_name="annuity_plans",
    table_name="年金计划",
    sheet_name="年金计划",
    schema_name="mapping",
    primary_key="id",  # Unified primary key naming
    delete_scope_key=["年金计划号", "company_id"],
    columns=[
        ColumnDef("年金计划号", ColumnType.STRING, nullable=False, max_length=255),
        ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),
        # Additional columns to be defined
    ],
))

register_domain(DomainSchema(
    domain_name="portfolio_plans",
    table_name="组合计划",
    sheet_name="组合计划",
    schema_name="mapping",
    primary_key="id",  # Unified primary key naming
    delete_scope_key=["年金计划号", "组合代码"],
    columns=[
        ColumnDef("年金计划号", ColumnType.STRING, nullable=False, max_length=255),
        ColumnDef("组合代码", ColumnType.STRING, nullable=False, max_length=255),
        # Additional columns to be defined
    ],
))
```

### 4.2 Update: scripts/create_table/manifest.yml

**File:** `scripts/create_table/manifest.yml`

```yaml
# =============================================================================
# CREATE TABLE SCRIPTS - MANIFEST
# =============================================================================
#
# SCOPE REDEFINITION (2025-12-18):
# ================================
# This module is now ONLY for:
#   - Temporary tables for data processing
#   - Standalone utility tables not part of domain schema
#   - One-time migration scripts
#   - Data repair scripts
#
# Domain tables (annuity_performance, annuity_plans, portfolio_plans, etc.)
# are now managed via:
#   - io/schema/domain_registry.py (Single Source of Truth)
#   - io/schema/migrations/ (Alembic versioned migrations)
#
# For domain schema changes, use:
#   1. Update io/schema/domain_registry.py
#   2. Create Alembic migration: alembic revision -m "description"
#   3. Apply migration: alembic upgrade head
#
# =============================================================================

# DEPRECATED: Domain tables (managed by Alembic now)
# These entries are kept for historical reference only.
# DO NOT use these for new deployments.
deprecated_domains:
  annuity_performance:
    note: "Migrated to io/schema/migrations/ and domain_registry.py"
    migration_date: "2025-12-18"
    alembic_revision: "TBD"

  annuity_plans:
    note: "Migrated to io/schema/migrations/ and domain_registry.py"
    migration_date: "2025-12-18"
    alembic_revision: "TBD"

  portfolio_plans:
    note: "Migrated to io/schema/migrations/ and domain_registry.py"
    migration_date: "2025-12-18"
    alembic_revision: "TBD"

# ACTIVE: Utility and temporary tables
utility_tables:
  # Example: Temporary staging table for bulk imports
  # staging_import:
  #   table: "staging.temp_import"
  #   ddl: "scripts/create_table/ddl/staging_import.sql"
  #   purpose: "Temporary table for bulk data import processing"
  #   auto_cleanup: true

  # Example: Lookup table not managed by domain
  # lookup_requests:
  #   table: "enterprise.lookup_requests"
  #   ddl: "scripts/create_table/ddl/lookup_requests.sql"
  #   purpose: "EQC API request queue"

# One-time scripts
one_time_scripts:
  # Example: Data repair script
  # fix_company_id_nulls:
  #   script: "scripts/create_table/repairs/fix_company_id_nulls.sql"
  #   executed_date: null
  #   purpose: "Repair NULL company_id values from legacy migration"
```

### 4.3 New File: Shared Models

**File:** `src/work_data_hub/infrastructure/models/shared.py`

```python
"""
Shared models used across multiple domains.

Extracted from domain-specific modules to eliminate code duplication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.models import ResolutionStatus


@dataclass
class BronzeValidationSummary:
    """Summary of bronze layer validation results."""
    row_count: int
    invalid_date_rows: List[int] = field(default_factory=list)
    numeric_error_rows: Dict[str, List[int]] = field(default_factory=dict)
    empty_columns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GoldValidationSummary:
    """Summary of gold layer validation results."""
    row_count: int
    removed_columns: List[str] = field(default_factory=list)
    duplicate_keys: List[Tuple[str, ...]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnrichmentStats(BaseModel):
    """Statistics for company ID enrichment process."""

    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )

    total_records: int = 0
    success_internal: int = 0  # Resolved via internal mappings
    success_external: int = 0  # Resolved via EQC lookup + cached
    pending_lookup: int = 0    # Queued for async processing
    temp_assigned: int = 0     # Assigned temporary ID
    failed: int = 0            # Resolution failed completely
    sync_budget_used: int = 0  # EQC lookups consumed from budget
    processing_time_ms: int = 0  # Total enrichment processing time

    def record(self, status: "ResolutionStatus", source: Optional[str] = None) -> None:
        from work_data_hub.domain.company_enrichment.models import ResolutionStatus

        self.total_records += 1
        if status == ResolutionStatus.SUCCESS_INTERNAL:
            self.success_internal += 1
        elif status == ResolutionStatus.SUCCESS_EXTERNAL:
            self.success_external += 1
            self.sync_budget_used += 1
        elif status == ResolutionStatus.PENDING_LOOKUP:
            self.pending_lookup += 1
        elif status == ResolutionStatus.TEMP_ASSIGNED:
            self.temp_assigned += 1
        else:
            self.failed += 1

    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        return (self.success_internal + self.success_external) / self.total_records
```

### 4.4 New Alembic Migration Template

**File:** `io/schema/migrations/versions/YYYYMMDD_HHMMSS_create_{domain}_table.py.template`

```python
"""
Template for generating domain table migrations from domain_registry.

Usage:
    from work_data_hub.io.schema.domain_registry import get_domain
    schema = get_domain("annuity_performance")
    # Generate migration code from schema
"""

# Migration generation logic will be implemented in Phase 2
```

---

## 5. Implementation Handoff

### Change Scope Classification: **Moderate**

This change requires:
- New infrastructure module (`domain_registry.py`)
- Scope redefinition for existing module (`scripts/create_table/`)
- Gradual migration of existing domains
- Documentation updates

### Deliverables

| Deliverable | Owner | Priority | Status |
|-------------|-------|----------|--------|
| Sprint Change Proposal (this document) | Architecture Review | High | Complete |
| `io/schema/domain_registry.py` | Dev Team | High | To Create |
| `infrastructure/models/shared.py` | Dev Team | Medium | To Create |
| `scripts/create_table/manifest.yml` update | Dev Team | High | To Update |
| Alembic migration for existing tables | Dev Team | Medium | To Create |
| Architecture documentation update | Dev Team | Low | To Update |

### Success Criteria

1. **Domain Registry Created:** `domain_registry.py` with all existing domains registered
2. **Scope Clarified:** `scripts/create_table/manifest.yml` clearly documents new scope
3. **Shared Models Extracted:** `EnrichmentStats` and validation summaries in `infrastructure/models/`
4. **Deployment Unified:** Single `alembic upgrade head` provisions all domain tables
5. **Tests Pass:** All existing tests pass, no regression
6. **Documentation Updated:** Architecture docs reflect new structure

### Migration Strategy: Strangler Fig Pattern

```
Phase 0-1 (Immediate):
┌─────────────────────────────────────────────────────────┐
│  domain_registry.py (NEW)                               │
│  └── All domain metadata                                │
│                                                         │
│  scripts/create_table/ (SCOPE CHANGED)                  │
│  └── Only utility/temp tables                           │
└─────────────────────────────────────────────────────────┘

Phase 2-3 (Gradual):
┌─────────────────────────────────────────────────────────┐
│  domain/*/constants.py                                  │
│  └── Import from domain_registry (backward compatible)  │
│                                                         │
│  domain/*/schemas.py                                    │
│  └── Reference domain_registry for column lists         │
└─────────────────────────────────────────────────────────┘

Phase 4 (Optional):
┌─────────────────────────────────────────────────────────┐
│  domain/*/models.py                                     │
│  └── Import EnrichmentStats from infrastructure/models/ │
└─────────────────────────────────────────────────────────┘
```

### Next Steps

1. **Immediate:** Get this proposal approved
2. **Phase 0:** Create `domain_registry.py` with existing domain definitions
3. **Phase 1:** Update `scripts/create_table/manifest.yml` with scope redefinition
4. **Phase 2:** Create unified Alembic migrations for domain tables
5. **Phase 3-4:** Gradual migration of existing code (can be done incrementally)

---

## 6. Appendix

### File Change Summary (Complete)

| File | Change Type | Priority | Phase |
|------|-------------|----------|-------|
| **Phase 0: Domain Registry** | | | |
| `src/work_data_hub/io/schema/domain_registry.py` | Create | Critical | 0 |
| `src/work_data_hub/io/schema/__init__.py` | Update | High | 0 |
| **Phase 1: Shared Models** | | | |
| `src/work_data_hub/infrastructure/models/__init__.py` | Create | High | 1 |
| `src/work_data_hub/infrastructure/models/shared.py` | Create | High | 1 |
| `src/work_data_hub/domain/annuity_performance/models.py` | Update | High | 1 |
| `src/work_data_hub/domain/annuity_performance/schemas.py` | Update | High | 1 |
| `src/work_data_hub/domain/annuity_income/models.py` | Update | High | 1 |
| `src/work_data_hub/domain/annuity_income/schemas.py` | Update | High | 1 |
| **Phase 2: Validation Generalization** | | | |
| `src/work_data_hub/infrastructure/validation/domain_validators.py` | Create | High | 2 |
| `src/work_data_hub/infrastructure/validation/__init__.py` | Update | Medium | 2 |
| **Phase 3: Alembic Migrations** | | | |
| `io/schema/migrations/versions/YYYYMMDD_create_annuity_performance.py` | Create | High | 3 |
| `io/schema/migrations/versions/YYYYMMDD_create_annuity_income.py` | Create | High | 3 |
| `io/schema/migrations/versions/YYYYMMDD_create_mapping_tables.py` | Create | High | 3 |
| `scripts/generate_migration_from_registry.py` | Create | Medium | 3 |
| **Phase 4: Scope Redefinition** | | | |
| `scripts/create_table/manifest.yml` | Update | Medium | 4 |
| `scripts/create_table/ddl/deprecated/` | Create (directory) | Low | 4 |
| `scripts/create_table/README.md` | Create | Low | 4 |
| **Documentation** | | | |
| `docs/brownfield-architecture.md` | Update | Low | - |

**Total Files: 18** (10 Create, 8 Update)

### Database Schema Changes

| Table | Current PK | New PK | Migration Required |
|-------|------------|--------|-------------------|
| `business."规模明细"` | `id` | `id` | Yes (rename column) |
| `business."收入明细"` | `id` | `id` | Yes (rename column) |
| `mapping."年金计划"` | `annuity_plans_id` | `id` | Yes (rename column) |
| `mapping."组合计划"` | `portfolio_plans_id` | `id` | Yes (rename column) |

**Migration Script Example**:
```sql
-- Rename primary key column (idempotent)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'business'
        AND table_name = '规模明细'
        AND column_name = 'id'
    ) THEN
        ALTER TABLE business."规模明细"
        RENAME COLUMN "id" TO "id";
    END IF;
END $$;
```

### Comparison: Before vs After (Revised)

| Aspect | Before | After |
|--------|--------|-------|
| Schema 定义位置 | **6 处** (DDL, manifest, constants, schemas, models, 缺失的 income DDL) | **1 处** (domain_registry) |
| 新 Domain 开发时间 | ~8.5h (需同步多处) | ~2h (单一入口) |
| 部署步骤 | **2 套机制** (DDL 脚本 + Alembic) | **1 套** (Alembic only) |
| Schema 漂移风险 | **高** (手动同步) | **低** (单一来源) |
| 代码重复 | **~316 行** (精确统计) | **消除** |
| 主键命名 | 各表不同 (`*_id`) | **统一** (`id`) |
| annuity_income DDL | **缺失** | 自动生成 |
| 验证函数 | 每个 domain 各一份 (~90行×2) | 泛化共享 |
| 共享模型 | 分散在各 domain | 集中在 infrastructure |

---

## Approval

| Role | Name | Date | Decision |
|------|------|------|----------|
| User | | 2025-12-18 | Pending |
| Architecture Review | Claude | 2025-12-18 | Generated |

---

*Generated by Architecture Review on 2025-12-18*
