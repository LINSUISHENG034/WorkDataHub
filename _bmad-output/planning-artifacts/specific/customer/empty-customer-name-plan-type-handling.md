# 客户名称为空时的计划类型差异化处理方案

**文档版本:** 1.0
**创建日期:** 2026-01-01
**影响范围:** annuity_income、annuity_performance 域
**严重程度:** 中等
**状态:** 待实现

---

## 📋 执行摘要

### 业务需求

在 `annuity_income` 和 `annuity_performance` 域的 ETL 处理中，针对**客户名称字段为空**（包括 NULL、空字符串、"空白"）的记录，需要根据**计划类型**字段实施差异化处理：

1. **单一计划**：计划代码与客户属于一一对应关系

   - 当多优先级匹配无法返回正确的 `company_id` 时
   - 应优先通过**计划名称**生成正确的公司名称
   - 调用 EQC API 查询查找真实的 `company_id`
   - 将查询结果通过 Enrichment Index 更新机制写入数据库

2. **集合计划**：单个计划包含多个客户
   - 当多优先级匹配无法返回正确的 `company_id` 时
   - 应允许 `company_id` 为 NULL 存储（或使用临时 ID）
   - 不应强制从计划名称中提取公司名称（因为集合计划不属于单一客户）

### 验证目标

3. 针对客户名称为空且计划类型为'单一计划'的记录
   - 验证能否通过 Enrichment Index 更新机制
   - 正确将查询的 `company_id` 写入 enrichment_index 表
   - 确保 lookup_type = 'plan_code' 的映射关系能够被后续 ETL 复用

---

## 🔍 当前实现验证

### 1. 客户名称处理逻辑

#### 当前代码实现

**文件:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
**函数:** `_fill_customer_name()`
**行号:** 42-50

```python
def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Keep customer name as-is, allow null (consistent with annuity_performance).

    Story 7.3-6: Removed plan name fallback to match annuity_performance behavior.
    """
    if "客户名称" in df.columns:
        return df["客户名称"]  # Keep as-is, including nulls
    else:
        return pd.Series([pd.NA] * len(df), index=df.index)
```

**关键发现：**

- ✅ 允许客户名称为 NULL（正确行为）
- ❌ **已移除**计划名称回退逻辑（Story 7.3-6）
- ❌ 没有从计划名称中提取公司名称的逻辑
- ❌ 没有根据计划类型实施差异化处理

#### Pipeline 注释与实际代码不一致

**注释（line 198-199）：**

```python
# 6. CalculationStep: Customer/income defaults (客户名称 fallback to 计划名称,
#    income nulls → 0)
```

**实际代码（line 253）：**

```python
"客户名称": _fill_customer_name,  # 仅保持原值，不做任何回退
```

**结论：** 注释未更新，实际实现已经移除了计划名称回退逻辑。

---

### 2. 计划类型字段使用情况

#### 数据分布（202510 期间数据）

| 计划类型 | 总记录数 | 独特计划代码 | 有客户名称 | 无客户名称 | 无客户名称占比 |
| -------- | -------- | ------------ | ---------- | ---------- | -------------- |
| 单一计划 | 12,109   | 669          | 1,544      | 10,565     | 87.2%          |
| 集合计划 | 1,530    | 15           | 0          | 1,530      | 100%           |

**关键发现：**

- 单一计划中 87.2% 的记录没有客户名称
- 集合计划中 100% 的记录没有客户名称（符合业务逻辑）

#### 计划类型在 Pipeline 中的用途

**文件:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
**函数:** `_apply_plan_code_defaults()`
**行号:** 53-72

```python
def _apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (consistent with annuity_performance).

    Story 7.3-6: Copied from annuity_performance/domain/pipeline_builder.py
    """
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, "AN001")  # 集合计划默认代码
        result = result.mask(single_mask, "AN002")      # 单一计划默认代码

    return result
```

**当前用途：**

- ✅ 用于设置**计划代码**的默认值（AN001/AN002）
- ❌ **未用于**客户名称或 company_id 解析的差异化处理

---

### 3. 计划名称字段数据特征

#### 计划名称格式分析

**示例数据（202510 期间）：**

| 计划代码 | 计划名称                                   | 客户名称 | company_id         | 计划类型 |
| -------- | ------------------------------------------ | -------- | ------------------ | -------- |
| S6544    | 中关村发展集团股份有限公司**企业年金计划** | NULL     | IN7KZNPWPCVQXJ6AY7 | 单一计划 |
| XNP707   | 山东重工集团有限公司**企业年金计划**       | NULL     | IN7KZNPWPCVQXJ6AY7 | 单一计划 |
| P0190    | 平安相伴今生**企业年金集合计划**           | NULL     | IN7KZNPWPCVQXJ6AY7 | 集合计划 |
| P0401    | 平安阳光人生**企业年金集合计划**           | NULL     | IN7KZNPWPCVQXJ6AY7 | 集合计划 |

**命名规律：**

- **单一计划：** `{公司名称}企业年金计划`
- **集合计划：** `{计划品牌}企业年金集合计划`（包含多个客户）

**提取规则：**

- 单一计划：去除后缀 "企业年金计划" → 获得公司名称
- 集合计划：不应提取（因为属于多客户计划）

---

### 4. Company ID 解析结果分布

#### 202510 期间数据统计

**单一计划（客户名称为空）：**

| ID 类型     | 记录数  | 独特计划代码 | 独特 company_id | 占比     |
| ----------- | ------- | ------------ | --------------- | -------- |
| 正式 ID     | 10,268  | 534          | 532             | 97.2%    |
| **临时 ID** | **297** | **18**       | **1**           | **2.8%** |

**临时 ID 详情：**

- 唯一临时 ID：`IN7KZNPWPCVQXJ6AY7`
- 涉及 18 个计划代码（与 `plan-code-backflow-missing.md` 中分析的缺失映射一致）

**集合计划（所有记录均无客户名称）：**

- 100% 使用临时 ID `IN7KZNPWPCVQXJ6AY7`（符合预期）

---

### 5. 临时 ID 问题根因分析

#### 18 个单一计划使用临时 ID 的原因

**计划代码示例：**

| 计划代码 | 计划名称                                 | 提取的公司名称               | enrichment_index | base_info | 结论                |
| -------- | ---------------------------------------- | ---------------------------- | ---------------- | --------- | ------------------- |
| S6544    | 中关村发展集团股份有限公司企业年金计划   | 中关村发展集团股份有限公司   | ❌ 未找到        | ❌ 不存在 | **未通过 EQC 查询** |
| XNP707   | 山东重工集团有限公司企业年金计划         | 山东重工集团有限公司         | ❌ 未找到        | ❌ 不存在 | **未通过 EQC 查询** |
| XNP732   | 上海浦东发展银行股份有限公司企业年金计划 | 上海浦东发展银行股份有限公司 | ❌ 未找到        | ❌ 不存在 | **未通过 EQC 查询** |

**验证 SQL：**

```sql
-- 验证提取的公司名称是否在 enrichment_index 中（lookup_type = 'customer_name'）
-- 结果：所有 18 个公司名称均未找到
```

**根因定位：**

1. **ETL 执行使用了 `--no-enrichment` 标志**

   ```bash
   uv run --env-file .wdh_env python -m work_data_hub.cli etl \
     --all-domains --period 202510 --file-selection newest --execute --no-enrichment
   ```

   - `--no-enrichment` 禁用了 EQC API 调用
   - 导致无法通过 P4 (customer_name) 查找 company_id

2. **plan_code 映射缺失**

   - 18 个计划代码不在 legacy_migration 中
   - Backflow 逻辑不支持 plan_code 映射（参见 `plan-code-backflow-missing.md`）
   - 无法通过 P1 (plan_code) 查找 company_id

3. **计划名称未利用**
   - 当前实现未从计划名称中提取公司名称
   - 即使有 `计划名称` 字段，也未用于查询

**结论：**

- ❌ 如果没有 `--no-enrichment` 标志，这些记录**可能**通过 EQC API 查询到正确的 company_id
- ❌ 当前实现**没有**利用计划名称字段进行查询
- ❌ 需要实现：从计划名称中提取公司名称 → 调用 EQC API → 写入 enrichment_index

---

## 🎯 需求与实现差距分析

### 需求 1：单一计划 - 计划名称回退 + EQC 查询

**用户需求：**

> "单一计划"的记录与客户属于一一对应关系，在多优先级匹配无法返回正确的 `company_id` 时，应该优先通过计划名称生成正确的公司名称，并调用 EQC 查询查找真实的 `company_id`。

**当前实现：**
| 项目 | 状态 | 说明 |
|-----|------|------|
| 计划名称回退逻辑 | ❌ 未实现 | Story 7.3-6 已移除 |
| 从计划名称提取公司名称 | ❌ 未实现 | 无相关代码 |
| 调用 EQC API 查询 | ❌ 未实现 | 需要新增逻辑 |
| 写入 enrichment_index | ❌ 未实现 | 受限于 Backflow 缺陷（P0） |

**差距：** **完全未实现**

### 需求 2：集合计划 - 允许 company_id 为 NULL

**用户需求：**

> "集合计划"在多优先级匹配无法返回正确的 `company_id` 时，应该允许 company_id 为 NULL 存储。

**当前实现：**
| 项目 | 状态 | 说明 |
|-----|------|------|
| 集合计划识别 | ✅ 已实现 | 通过 `计划类型` 字段判断 |
| 允许 company_id 为 NULL | ⚠️ 部分实现 | 使用临时 ID，非 NULL |
| 计划名称不回退 | ✅ 正确行为 | 集合计划不应提取公司名称 |

**差距：**

- 当前使用临时 ID `IN7KZNPWPCVQXJ6AY7`，而非 NULL
- **是否需要修改为 NULL？** 需要用户确认业务需求

### 需求 3：Enrichment Index 更新机制验证

**用户需求：**

> 针对客户名称为空且计划类型为'单一计划'的记录，能否通过 Enrichment Index 更新机制正确将查询的 `company_id` 写入 enrichment_index 表。

**当前实现：**
| 项目 | 状态 | 问题 |
|-----|------|------|
| plan_code → company_id 映射写入 | ❌ 未实现 | Backflow 缺陷（P0） |
| customer_name → company_id 映射写入 | ✅ 已实现 | 支持 P4 (customer_name) |
| EQC API 结果写入 enrichment_index | ✅ 已实现 | 通过 CompanyEnrichmentLoader |

**差距：**

- **核心问题：** Backflow 逻辑缺少 plan_code 映射支持
- **影响：** 即使通过 EQC 查询到 company_id，也不会创建 plan_code → company_id 映射
- **解决方案：** 需要先修复 `plan-code-backflow-missing.md` 中的 P0 问题

---

## 📊 数据验证总结

### 关键数据指标

| 指标                            | 数值   | 说明                   |
| ------------------------------- | ------ | ---------------------- |
| 单一计划无客户名称记录          | 10,565 | 占单一计划总数 87.2%   |
| 单一计划临时 ID 记录            | 297    | 涉及 18 个计划代码     |
| 集合计划无客户名称记录          | 1,530  | 占集合计划总数 100%    |
| 集合计划临时 ID 记录            | 1,530  | 符合业务预期           |
| plan_code enrichment_index 缺失 | 18     | 需要修复 Backflow 逻辑 |

### 业务影响评估

**影响范围：**

- ✅ 有正式 company_id 的记录：10,268 条（97.2%）- 正常处理
- ⚠️ 临时 ID 记录：297 条（2.8%）- 需要改进处理逻辑

**潜在问题：**

1. **数据完整性：** 临时 ID 不代表真实的公司映射
2. **查询性能：** 临时 ID 无法用于关联查询
3. **业务分析：** 无法基于临时 ID 进行准确的客户分析

---

## 🔧 解决方案

### 方案概述

**核心原则：**

- **单一计划：** 从计划名称提取公司名称 → 调用 EQC API → 写入 enrichment_index
- **集合计划：** 保持当前行为（使用临时 ID 或改为 NULL）
- **前提条件：** 必须先修复 `plan-code-backflow-missing.md` 中的 P0 问题

### 实施计划

#### 阶段 1：修复 Backflow 逻辑（P0 - 必须优先）

**任务：** 在 backflow.py 中添加 plan_code 映射支持

**文件：** `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py`
**函数：** `backflow_new_mappings()`

**修改内容：**

```python
backflow_fields = [
    (strategy.plan_code_column, "plan", 1, False),  # ✅ 添加 P1
    (strategy.account_number_column, "account", 2, False),
    (strategy.customer_name_column, "name", 4, True),
    (strategy.account_name_column, "account_name", 5, False),
]
```

**验证：** 确保 ResolutionStrategy 包含 `plan_code_column` 字段

**参考：** `docs/specific/customer/plan-code-backflow-missing.md`

---

#### 阶段 2：实现计划名称回退逻辑（核心需求）

**任务：** 为单一计划添加计划名称回退机制

**文件：** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
**新函数：** `_fill_customer_name_from_plan_name()`

**实现逻辑：**

```python
def _fill_customer_name_from_plan_name(df: pd.DataFrame) -> pd.Series:
    """Fill customer name from plan name for single-plan records.

    Extraction rule:
    - Single plan: "{CompanyName}企业年金计划" → "{CompanyName}"
    - Collective plan: Skip (belongs to multiple customers)

    Returns:
        pd.Series: Filled customer names (original values preserved if not empty)
    """
    if "客户名称" not in df.columns or "计划名称" not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)

    result = df["客户名称"].copy()

    # Only process single-plan records with empty customer name
    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "") | (result == "0")
        single_plan_mask = empty_mask & (df["计划类型"] == "单一计划")
        has_plan_name = df["计划名称"].notna() & (df["计划名称"] != "")

        # Apply extraction to matching records
        target_mask = single_plan_mask & has_plan_name

        def extract_company_name(plan_name: str) -> str:
            """Extract company name from plan name.

            Example: "中关村发展集团股份有限公司企业年金计划"
                  → "中关村发展集团股份有限公司"
            """
            if pd.isna(plan_name) or not isinstance(plan_name, str):
                return pd.NA

            # Remove suffix "企业年金计划"
            suffix = "企业年金计划"
            if plan_name.endswith(suffix):
                return plan_name[:-len(suffix)].strip()

            return plan_name  # Return as-is if no suffix match

        result.loc[target_mask] = df.loc[target_mask, "计划名称"].apply(
            extract_company_name
        )

    return result
```

**Pipeline 集成：**

```python
# Step 6: Customer defaults (plan name fallback for single-plan)
CalculationStep(
    {
        "客户名称": _fill_customer_name_from_plan_name,  # ✅ 新函数
        "固费": lambda df: df["固费"].fillna(0),
        # ... 其他字段
    }
),
```

**注意事项：**

- ⚠️ 必须在 CleansingStep（数据清洗）**之前**执行
- ⚠️ 提取的公司名称需要经过 CleansingStep 的规范化处理
- ⚠️ 仅对单一计划生效，集合计划跳过

---

#### 阶段 3：启用 EQC API 查询

**任务：** 确保提取的公司名称能够触发 EQC API 查询

**ETL 执行命令：**

```bash
# ❌ 错误：禁用了 EQC API
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains --period 202510 --file-selection newest --execute --no-enrichment

# ✅ 正确：启用 EQC API（移除 --no-enrichment）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains --period 202510 --file-selection newest --execute
```

**EqcLookupConfig 配置：**

- 确保 `eqc_config.enabled = True`（默认启用）
- 确保 `sync_budget > 0`（允许同步查询）

---

#### 阶段 4：验证 enrichment_index 更新

**验证项目：**

1. ✅ 从计划名称提取的公司名称通过 EQC API 查询成功
2. ✅ 查询结果写入 enrichment_index（lookup_type = 'customer_name'）
3. ✅ plan_code 映射写入 enrichment_index（lookup_type = 'plan_code'，依赖阶段 1）
4. ✅ 后续 ETL 执行能够从 enrichment_index 命中缓存

**验证 SQL：**

```sql
-- 验证 1：提取的公司名称是否在 enrichment_index 中
SELECT lookup_key, company_id, source
FROM enterprise.enrichment_index
WHERE lookup_type = 'customer_name'
  AND lookup_key IN (
    '中关村发展集团股份有限公司',
    '山东重工集团有限公司',
    -- ... 其他提取的公司名称
  );

-- 验证 2：plan_code 映射是否写入
SELECT lookup_key, company_id, source
FROM enterprise.enrichment_index
WHERE lookup_type = 'plan_code'
  AND lookup_key IN ('S6544', 'XNP707', /* ... */);
```

---

#### 阶段 5：集合计划处理优化（可选）

**任务：** 决定集合计划的 company_id 存储策略

**选项 A：保持当前行为**

- 使用临时 ID `IN7KZNPWPCVQXJ6AY7`
- 优点：与现有逻辑一致
- 缺点：无法用于关联查询

**选项 B：改为 NULL**

- 修改 `generate_temp_ids` 配置，对集合计划不生成临时 ID
- 优点：语义更清晰（集合计划不属于单一客户）
- 缺点：需要修改数据库约束（允许 NULL）

**建议：** 保持选项 A（当前行为），除非有明确的业务需求要求改为 NULL。

---

### 实施顺序

| 阶段 | 任务                                      | 优先级 | 预计工时 | 前置条件     |
| ---- | ----------------------------------------- | ------ | -------- | ------------ |
| 1    | 修复 Backflow 逻辑（plan_code 映射）      | P0     | 2-4h     | 无           |
| 2    | 实现计划名称回退逻辑                      | P1     | 4-6h     | 阶段 1       |
| 3    | 启用 EQC API 查询（移除 --no-enrichment） | P1     | 0.5h     | 阶段 2       |
| 4    | 验证 enrichment_index 更新                | P1     | 2-3h     | 阶段 1, 2, 3 |
| 5    | 集合计划处理优化（可选）                  | P2     | 1-2h     | 无           |

**总计：** 10-16 小时（不含可选阶段）

---

## 🧪 测试计划

### 单元测试

**测试用例 1：计划名称提取逻辑**

```python
def test_extract_company_name_from_plan_name():
    """Test company name extraction from plan name."""
    # Single plan
    assert extract("中关村发展集团股份有限公司企业年金计划") == "中关村发展集团股份有限公司"
    assert extract("山东重工集团有限公司企业年金计划") == "山东重工集团有限公司"

    # Edge cases
    assert extract("无后缀计划") == "无后缀计划"
    assert extract(None) == pd.NA
    assert extract("") == pd.NA
```

**测试用例 2：计划类型差异化处理**

```python
def test_plan_type_based_fallback():
    """Test different handling for single vs collective plans."""
    df = pd.DataFrame({
        "客户名称": [None, None, None],
        "计划名称": ["A公司企业年金计划", "B集合计划", "C公司企业年金计划"],
        "计划类型": ["单一计划", "集合计划", "单一计划"],
    })

    result = _fill_customer_name_from_plan_name(df)

    assert result[0] == "A公司"  # ✅ 单一计划：提取
    assert result[1] is pd.NA    # ✅ 集合计划：跳过
    assert result[2] == "C公司"  # ✅ 单一计划：提取
```

### 集成测试

**测试场景 1：单一计划端到端流程**

```bash
# 1. 执行 ETL（启用 enrichment）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_income --period 202511 --execute

# 2. 验证 enrichment_index
psql -c "
SELECT lookup_key, lookup_type, company_id, source
FROM enterprise.enrichment_index
WHERE lookup_type IN ('customer_name', 'plan_code')
  AND created_at >= NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
"

# 3. 验证数据写入
psql -c "
SELECT \"计划代码\", \"客户名称\", company_id
FROM business.\"收入明细\"
WHERE \"月度\" = '2025-11-01'
  AND \"计划类型\" = '单一计划'
  AND \"客户名称\" IS NOT NULL
LIMIT 10;
"
```

**测试场景 2：集合计划不提取**

```bash
# 验证集合计划未提取公司名称
psql -c "
SELECT \"计划代码\", \"计划名称\", \"客户名称\", company_id
FROM business.\"收入明细\"
WHERE \"月度\" = '2025-11-01'
  AND \"计划类型\" = '集合计划'
  AND \"客户名称\" IS NOT NULL  -- 应该为 0 行
LIMIT 10;
"
```

---

## 📚 相关文档

### 核心文档

- [Plan Code Backflow Missing](plan-code-backflow-missing.md) - Backflow 逻辑缺陷分析
- [Empty Customer Name Handling](empty-customer-name-handling.md) - 客户名称为空处理策略
- [Database Schema Panorama](../../database-schema-panorama.md) - 数据库架构
- [Company Enrichment Architecture](../../architecture/infrastructure-layer.md) - 公司 ID 解析架构

### 源代码

- `src/work_data_hub/domain/annuity_income/pipeline_builder.py` - annuity_income Pipeline
- `src/work_data_hub/domain/annuity_performance/pipeline_builder.py` - annuity_performance Pipeline
- `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py` - Backflow 逻辑
- `src/work_data_hub/infrastructure/enrichment/resolver/core.py` - CompanyIdResolver

---

## 📝 变更历史

| 版本 | 日期       | 作者                     | 变更说明                                       |
| ---- | ---------- | ------------------------ | ---------------------------------------------- |
| 1.0  | 2026-01-01 | Barry (Quick Flow Agent) | 初始版本，完成需求分析、实现验证、解决方案设计 |

---

## 🏷️ 标签

`annuity_income` `annuity_performance` `customer_name` `plan_name` `plan_type` `enrichment_index` `etl` `p1` `requirement`
