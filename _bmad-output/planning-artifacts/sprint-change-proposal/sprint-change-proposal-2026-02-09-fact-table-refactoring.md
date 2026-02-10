# Sprint Change Proposal: Customer MDM Fact Table Refactoring

**Date**: 2026-02-09
**Epic**: Epic 7 - Customer MDM
**Related Stories**: 7.6-7, 7.6-8, 7.6-13, 7.6-14, 7.6-15
**Proposal ID**: 2026-02-09-fact-table-refactoring
**Status**: Approved

---

## Section 1: Issue Summary

### 1.1 Problem Statement

当前 `customer.fct_customer_business_monthly_status` 表存在**粒度冲突**问题：

| 业务事件 | 天然粒度 | 当前表粒度 | 问题 |
|---------|---------|-----------|------|
| `is_winning_this_year` (中标) | Company + ProductLine | Company + ProductLine | ✅ 匹配 |
| `is_churned_this_year` (流失) | **Company + Plan + ProductLine** | Company + ProductLine | ❌ **丢失计划级别细节** |

### 1.2 Discovery Context

- **Source**: Correct Course workflow 触发
- **Trigger**: 评估 Story 7.6-13/7.6-14/7.6-15 对下游表的影响
- **Evidence**:
  - 中标时客户尚未签约具体计划 → 无法在 Plan 粒度记录
  - 流失是针对已签约的具体计划 → 需要 Plan 粒度追踪

### 1.3 Business Impact

| 影响 | 描述 |
|------|------|
| **查询能力缺失** | 无法回答"客户A的哪个具体计划流失了？" |
| **BI分析受限** | 流失分析只能聚合到产品线，无法钻取到计划级别 |
| **设计不一致** | 与源表 `customer_plan_contract` (Plan粒度) 不匹配 |

---

## Section 2: Impact Analysis

### 2.1 Epic Impact

| Epic | 影响评估 | 说明 |
|------|---------|------|
| **Epic 7 - Customer MDM** | 🟡 中等影响 | 需要新增 Story 实施双表重构 |
| **Epic 8 - BI & Reporting** | 🟢 正面影响 | 提供更细粒度的流失分析能力 |

### 2.2 Story Impact

| Story | 状态 | 影响评估 |
|-------|------|---------|
| **7.6-7** | done | 需要修改：代码引用表名需更新 |
| **7.6-8** | done | 需要修改：Power BI 数据源更新 |
| **7.6-13** | ready-for-dev | 🔄 **合并到本提案**：customer_name 字段 |
| **7.6-14** | done | 无影响：年度切断逻辑仅影响 SCD 表 |
| **7.6-15** | done | 无影响：Ratchet 规则确保数据一致性 |

### 2.3 Artifact Impact

| 工件 | 变更类型 | 说明 |
|------|---------|------|
| Alembic Migration 009 | 修改 | 表重命名 + 添加字段 |
| Alembic Migration 013 | 新建 | 创建 Plan 级别事实表 |
| `snapshot_refresh.py` | 修改 | 同时填充两张表 |
| 单元测试 | 修改 | 更新表名引用 |
| 集成测试 | 修改 | 验证双表逻辑 |
| 规格说明书 | 新建/修改 | 新表规格文档 |
| CLI 命令 | 修改 | 输出信息更新 |

---

## Section 3: Recommended Approach

### 3.1 Selected Option: 方案 A - 双表设计 + 重命名

```
┌─────────────────────────────────────────────────────────────────┐
│  fct_customer_product_line_monthly (重命名)                      │
│  粒度: Company + ProductLine                                     │
│  用途: 客户级别汇总视图 - 战客/已客/中标/AUM汇总                  │
├─────────────────────────────────────────────────────────────────┤
│  - snapshot_month, company_id, product_line_code/name            │
│  - customer_name (新增, 同步7.6-13)                               │
│  - is_strategic, is_existing, is_new                             │
│  - is_winning_this_year ← 天然粒度匹配 ✅                         │
│  - aum_balance (聚合), plan_count                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  fct_customer_plan_monthly (新建)                                │
│  粒度: Company + Plan + ProductLine                              │
│  用途: 计划级别明细视图 - 流失/合约状态/AUM明细                    │
├─────────────────────────────────────────────────────────────────┤
│  - snapshot_month, company_id, plan_code, product_line_code/name │
│  - customer_name, plan_name (新增)                               │
│  - is_churned_this_year ← 天然粒度匹配 ✅                         │
│  - contract_status (当前合约状态)                                 │
│  - aum_balance (计划级别)                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Rationale

| 优点 | 说明 |
|------|------|
| ✅ **语义清晰** | 每张表在其天然粒度追踪业务事件 |
| ✅ **符合最佳实践** | Kimball 维度建模：不同粒度用不同事实表 |
| ✅ **查询灵活** | BI 可选择汇总表或明细表 |
| ✅ **扩展性好** | 未来可添加其他计划级别指标 |
| ✅ **向后兼容** | 保留原有数据结构（重命名而非删除） |

### 3.3 Effort & Risk Assessment

| 项目 | 评估 |
|------|------|
| **工作量** | 中等 (2-3天) |
| **风险级别** | 低 (在线迁移，可回滚) |
| **时间线影响** | 无阻塞，可独立实施 |
| **依赖关系** | 无外部依赖 |

---

## Section 4: Detailed Change Proposals

### 4.1 Migration 009 修改 (从零创建)

**File**: `io/schema/migrations/versions/009_create_fct_customer_monthly_status.py`

- 表名: `fct_customer_business_monthly_status` → `fct_customer_product_line_monthly`
- 新增字段: `customer_name VARCHAR(200)`
- 新增索引: `idx_fct_pl_customer_name`
- 新增触发器: `trg_sync_fct_pl_customer_name`

### 4.2 Migration 013 新建 (Plan级别表)

**File**: `io/schema/migrations/versions/013_create_fct_customer_plan_monthly.py`

- 表名: `fct_customer_plan_monthly`
- 主键: `(snapshot_month, company_id, plan_code, product_line_code)`
- 字段: `customer_name`, `plan_name`, `is_churned_this_year`, `contract_status`, `aum_balance`
- 触发器: `trg_sync_fct_plan_customer_name`, `trg_sync_fct_plan_plan_name`

### 4.3 现有数据库迁移 SQL

**File**: `scripts/migrations/migrate_fct_tables_2026-02-09.sql`

- Part 1: 重命名表 + 添加字段
- Part 2: 更新触发器
- Part 3: 创建新表
- Part 4: 创建索引
- Part 5: 创建触发器
- Part 6-7: 数据回填

### 4.4 代码修改

**File**: `src/work_data_hub/customer_mdm/snapshot_refresh.py`

- 重命名函数: `refresh_product_line_snapshot()`
- 新增函数: `refresh_plan_snapshot()`
- 统一入口: `refresh_monthly_snapshot()` 同时刷新两张表

---

## Section 5: Implementation Handoff

### 5.1 变更范围分类

| 分类 | 评估 |
|------|------|
| **范围** | 🟡 **Moderate** - 需要 Schema 变更 + 代码修改 |
| **风险** | 🟢 **Low** - 在线迁移，可回滚 |
| **影响** | Epic 7 Customer MDM 内部变更 |

### 5.2 实施步骤

| 步骤 | 操作 | 预估时间 |
|------|------|---------|
| 1 | 修改 Migration 009 | 30min |
| 2 | 新建 Migration 013 | 30min |
| 3 | 执行迁移 SQL 脚本 | 15min |
| 4 | 执行回填 SQL 脚本 | 30min |
| 5 | 修改 snapshot_refresh.py | 1h |
| 6 | 更新单元测试 | 1h |
| 7 | 更新集成测试 | 30min |
| 8 | 更新文档 | 30min |
| 9 | 验证测试通过 | 30min |

**总预估时间**: 5-6小时

### 5.3 文件变更清单

| 文件 | 变更类型 |
|------|---------|
| `io/schema/migrations/versions/009_create_fct_customer_monthly_status.py` | 修改 |
| `io/schema/migrations/versions/013_create_fct_customer_plan_monthly.py` | 新建 |
| `scripts/migrations/migrate_fct_tables_2026-02-09.sql` | 新建 |
| `src/work_data_hub/customer_mdm/snapshot_refresh.py` | 修改 |
| `src/work_data_hub/cli/customer_mdm/snapshot.py` | 修改 |
| `tests/unit/customer_mdm/test_snapshot_refresh.py` | 修改 |
| `tests/integration/customer_mdm/test_hook_chain.py` | 修改 |
| `docs/specific/customer-mdm/customer-monthly-snapshot-specification.md` | 修改 |

### 5.4 验收标准

| ID | 验收项 | 验证方法 |
|----|--------|---------|
| AC-1 | 表 `fct_customer_product_line_monthly` 存在且包含 `customer_name` | SQL 查询 |
| AC-2 | 表 `fct_customer_plan_monthly` 存在且包含所有必需字段 | SQL 查询 |
| AC-3 | 现有数据 `customer_name` 已回填 | `WHERE customer_name IS NULL` 返回 0 |
| AC-4 | Plan 级别历史数据已回填 | `SELECT COUNT(*) > 0` |
| AC-5 | 同步触发器正常工作 | 更新 `年金客户.客户名称` 后验证 |
| AC-6 | `snapshot_refresh.py` 同时刷新两张表 | CLI 执行验证 |
| AC-7 | 所有单元测试通过 | `pytest tests/unit/customer_mdm/` |
| AC-8 | 所有集成测试通过 | `pytest tests/integration/customer_mdm/` |

### 5.5 回滚方案

如需回滚，执行以下操作：
1. 删除新表 `fct_customer_plan_monthly`
2. 删除新触发器函数
3. 删除 `customer_name` 字段
4. 重命名表回 `fct_customer_business_monthly_status`

---

## Approval

- **Approved by**: Link
- **Approval Date**: 2026-02-09
- **Next Action**: 创建实施 Story 7.6-16
