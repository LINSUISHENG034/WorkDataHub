# Plan Code 映射未写入 Enrichment Index 问题分析

**文档版本:** 1.0
**创建日期:** 2026-01-01
**影响范围:** annuity_income 域 ETL
**严重程度:** 中等
**状态:** 待修复

---

## 📋 执行摘要

### 问题概述

在执行 `annuity_income` 域（收入明细表）的 202510 期间 ETL 后，发现部分计划代码（plan_code）与 company_id 的映射关系未自动写入 `enterprise.enrichment_index` 表。

**影响统计：**
- **符合条件记录总数:** 552 个计划代码（客户名称为空且计划类型='单一计划'）
- **已写入 enrichment_index:** 534 个（96.74%）
- **未写入 enrichment_index:** 18 个（3.26%）

### 缺失计划代码列表

```
S6544, S6548, S6550, S6556,
XNP707, XNP708, XNP711, XNP713, XNP714, XNP722, XNP723, XNP725,
XNP731, XNP732, XNP733, XNP735, XNP737, XNP742
```

### 根因分类

1. **架构缺陷（P0）:** Backflow 逻辑缺少 plan_code 映射支持
2. **临时 ID 跳过（P1）:** 临时 company_id 映射被跳过（设计如此，非 Bug）

---

## 🔍 详细分析

### 1.1 架构缺陷：Backflow 逻辑缺少 plan_code 映射

#### 问题描述

ETL Pipeline 的 backflow 机制（将已解析的映射关系回写到 enrichment_index）不支持 `plan_code` 查找类型。

#### 问题定位

**文件:** `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py`
**函数:** `backflow_new_mappings()`
**行号:** 56-60

**当前代码：**
```python
backflow_fields = [
    (strategy.account_number_column, "account", 2, False),  # P2: RAW
    (strategy.customer_name_column, "name", 4, True),  # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
]
# ❌ 缺少 plan_code_column (P1)
```

**支持的查找类型优先级（按 Company ID Resolver 5 层架构）：**
1. **P1 - plan_code**: 计划代码 → company_id ⚠️ **未实现**
2. **P2 - account_number**: 年金账户号 → company_id ✅ 已实现
3. **P3 - (YAML hardcode)**: 硬编码映射 → company_id ✅ 已实现
4. **P4 - customer_name**: 客户名称 → company_id ✅ 已实现
5. **P5 - account_name**: 年金账户名 → company_id ✅ 已实现

#### 影响范围

**直接影响：**
- annuity_income 域：所有通过 `plan_code` 解析出的 company_id 映射都不会回写到 enrichment_index
- annuity_performance 域：同样受影响（使用相同的 backflow 逻辑）

**间接影响：**
- 后续 ETL 执行时，无法从 enrichment_index 缓存中命中 plan_code 映射
- 可能导致重复调用 EQC API（如果未通过其他查找类型命中）

#### 数据验证

**验证方法：** 检查 enrichment_index 中现有的 plan_code 记录来源

```sql
SELECT
  source,
  COUNT(*) AS record_count,
  MIN(created_at) AS first_created,
  MAX(created_at) AS last_created
FROM enterprise.enrichment_index
WHERE lookup_type = 'plan_code'
GROUP BY source;
```

**验证结果：**
| source | record_count | first_created | last_created |
|--------|--------------|---------------|--------------|
| legacy_migration | 1104 | 2025-12-28 09:51:55 | 2025-12-28 09:51:55 |

**结论：**
- 现有 1104 条 plan_code 记录全部来自历史数据迁移
- **无** `pipeline_backflow` 或 `eqc_api` 来源的 plan_code 记录
- 证明 ETL 执行过程中不会自动写入 plan_code 映射

---

### 1.2 实例分析：S6544 记录详情

#### 计划代码 S6544 的完整数据

**查询：**
```sql
SELECT DISTINCT
  "计划代码",
  "组合代码",
  "客户名称",
  company_id,
  CASE
    WHEN company_id LIKE 'IN%' THEN '临时ID'
    ELSE '正式ID'
  END AS id_type
FROM business."收入明细"
WHERE "月度" = '2025-10-01'
  AND "计划代码" = 'S6544'
ORDER BY "组合代码", id_type;
```

**结果：**

| 计划代码 | 组合代码 | 客户名称 | company_id | ID类型 | 应否写入enrichment_index |
|---------|---------|---------|-----------|--------|----------------------|
| S6544 | I44Q0745 | *NULL* | IN7KZNPWPCVQXJ6AY7 | 临时ID | ❌ Backflow跳过（设计行为） |
| S6544 | I44Q0745 | 中关村发展集团股份有限公司 | 600093406 | 正式ID | ✅ **应该写入但未写入** |
| S6544 | QTAN002 | 中关村发展集团股份有限公司 | 600093406 | 正式ID | ✅ **应该写入但未写入** |

**预期映射关系：**
- **lookup_key:** `S6544`
- **lookup_type:** `plan_code`
- **company_id:** `600093406`
- **source:** `pipeline_backflow`

**实际状态：**
- enrichment_index 中不存在此映射
- 查询结果：`SELECT * FROM enterprise.enrichment_index WHERE lookup_key = 'S6544' AND lookup_type = 'plan_code'` → **0 rows**

---

### 1.3 临时 ID 跳过逻辑

#### 设计说明

**文件:** `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py`
**行号:** 67-68

```python
# Skip temporary IDs
if company_id.startswith("IN"):
    continue
```

**设计意图：**
- 临时 ID（以 `IN` 开头）是由 HMAC-SHA1 生成的占位符
- 这些映射关系不是"真实的"公司 ID 解析结果
- 不应该被缓存到 enrichment_index 中

**影响：**
- 所有使用临时 company_id 的记录都不会创建映射关系
- 这是**正确的设计行为**，不是 Bug

**示例：**
- S6544 组合 I44Q0745（无客户名称）→ company_id = `IN7KZNPWPCVQXJ6AY7`
- **不写入** enrichment_index（设计如此）

---

## 🎯 问题分类

### P0 - 架构缺陷（需修复）

**问题：** Backflow 逻辑缺少 plan_code 映射支持

**影响：**
- 无法通过 plan_code 建立映射缓存
- 降低 enrichment_index 的缓存命中率
- 可能导致重复的 EQC API 调用

**修复方案：**

**方案 1：修改 backflow.py（推荐）**

在 `backflow_new_mappings()` 函数中添加 plan_code 支持：

```python
backflow_fields = [
    (strategy.plan_code_column, "plan", 1, False),  # ✅ 添加 P1
    (strategy.account_number_column, "account", 2, False),  # P2: RAW
    (strategy.customer_name_column, "name", 4, True),  # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
]
```

**注意事项：**
- 需要检查 `ResolutionStrategy` 数据类是否包含 `plan_code_column` 字段
- 需要验证 `strategy.plan_code_column` 在 annuity_income 和 annuity_performance 域中的配置
- 需要更新相关单元测试

**方案 2：使用 DomainLearningService（备选）**

检查是否可以通过 DomainLearningService 从域数据中学习 plan_code 映射。

**优点：**
- 不修改核心 backflow 逻辑
- 可以作为补充机制

**缺点：**
- 需要额外的配置和触发逻辑
- 可能与现有的 backflow 机制重复

---

### P1 - 临时 ID 跳过（设计如此，非 Bug）

**问题：** 临时 company_id 映射不写入 enrichment_index

**状态：** ✅ **正确的设计行为**

**说明：**
- 临时 ID 是占位符，不是真实的解析结果
- 不应该被缓存到 enrichment_index

---

## 📊 数据统计

### enrichment_index 当前状态

**按 lookup_type 分组统计：**

| lookup_type | record_count | unique_companies | 占比 |
|------------|--------------|------------------|------|
| account_name | 10,948 | 9,794 | 33.2% |
| account_number | 10,265 | 9,809 | 31.1% |
| customer_name | 9,735 | 6,207 | 29.5% |
| **plan_code** | **1,104** | **980** | **3.3%** |
| **总计** | **32,052** | **N/A** | **100%** |

**plan_code 来源分布：**

| source | record_count | 创建时间 |
|--------|--------------|---------|
| legacy_migration | 1,104 | 2025-12-28 09:51:55 |
| **pipeline_backflow** | **0** | **N/A** |
| **eqc_api** | **0** | **N/A** |

### 202510 期间数据统计

**收入明细表（月度 = 2025-10-01）：**

| 筛选条件 | 计划代码数量 |
|---------|------------|
| 客户名称 IS NULL AND 计划类型 = '单一计划' | 552 |
| 已写入 enrichment_index (lookup_type = 'plan_code') | 534 |
| 未写入 enrichment_index | 18 |
| **覆盖率** | **96.74%** |

**未写入的 18 个计划代码：**

```
S6544, S6548, S6550, S6556,
XNP707, XNP708, XNP711, XNP713, XNP714, XNP722, XNP723, XNP725,
XNP731, XNP732, XNP733, XNP735, XNP737, XNP742
```

**特征分析：**
- 所有缺失的计划代码都关联到临时 company_id `IN7KZNPWPCVQXJ6AY7`
- 部分计划代码（如 S6544）同时存在正式 company_id 的记录，但未写入 plan_code 映射

---

## 🔧 修复计划

### 阶段 1：代码修复（P0）

**任务：** 在 backflow.py 中添加 plan_code 映射支持

**步骤：**
1. ✅ 分析问题根因（本文档）
2. ⏳ 修改 `backflow_new_mappings()` 函数
3. ⏳ 更新单元测试
4. ⏳ 运行回归测试
5. ⏳ 提交 Pull Request

**预计工作量：** 2-4 小时

### 阶段 2：数据修复（可选）

**任务：** 补充 202510 期间缺失的 plan_code 映射

**方案：**
- 手动执行 SQL INSERT 语句
- 或开发一次性数据修复脚本

**注意事项：**
- 仅修复有正式 company_id 的映射
- 临时 ID 映射不应补充

**预计工作量：** 1-2 小时

### 阶段 3：验证测试（必须）

**验证项目：**
1. ✅ enrichment_index 中有 plan_code 记录且 source = 'pipeline_backflow'
2. ✅ 后续 ETL 执行能自动写入 plan_code 映射
3. ✅ 缓存命中率提升（可通过日志统计）
4. ✅ 回归测试全部通过

---

## 📚 相关文档

### 架构文档
- [Database Schema Panorama](../../database-schema-panorama.md) - enrichment_index 表结构
- [Company Enrichment Architecture](../../architecture/infrastructure-layer.md) - 公司 ID 解析架构

### 相关 Story
- [Story 6.2-P17](../../sprint-artifacts/stories/6-2-p17-eqc-lookup-config-unification.md) - EQC Lookup Config 统一
- [Story 7.3-6](../../sprint-artifacts/stories/7-3-6-annuity-income-enrichment.md) - annuity_income enrichment 支持

### 源代码
- `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py` - Backflow 逻辑
- `src/work_data_hub/infrastructure/enrichment/resolver/core.py` - CompanyIdResolver
- `src/work_data_hub/domain/annuity_income/pipeline_builder.py` - annuity_income pipeline

---

## 📝 变更历史

| 版本 | 日期 | 作者 | 变更说明 |
|-----|------|------|---------|
| 1.0 | 2026-01-01 | Barry (Quick Flow Agent) | 初始版本，完成问题根因分析 |

---

## 🏷️ 标签

`enrichment_index` `plan_code` `backflow` `annuity_income` `etl` `p0` `architecture-defect`
