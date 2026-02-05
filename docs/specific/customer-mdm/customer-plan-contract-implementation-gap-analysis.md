# Customer Plan Contract 实现差距分析

**文档版本**: 1.0
**创建日期**: 2026-02-05
**分析人**: Barry (Quick Flow Solo Dev)
**关联规范**: `docs/memories/战客身份定义与更新逻辑.md`

---

## 1. 执行摘要

本文档分析 `customer.customer_plan_contract` 表的当前实现与业务规范之间的差距。

### 关键发现

| 类别 | 严重程度 | 描述 |
|------|----------|------|
| 数据一致性 | **严重** | 10,417 条记录状态不一致（应为"停缴"但显示"正常"） |
| 年度切断 | **严重** | 未实现1月1日强制生成新记录的逻辑 |
| 只增不减 | **中等** | `contract_sync.py` 未实现战客身份保护规则 |
| 设计冲突 | **中等** | `year_init.py` 与 `contract_sync.py` 设计理念冲突 |

---

## 2. 业务规范要求

根据 `docs/memories/战客身份定义与更新逻辑.md`，系统必须遵循三大原则：

### 2.1 原则一：年度切断 (Annual Cutover)

- **规则**: 跨年时刻（1月1日）必须强制生成新记录
- **目的**: 区分"2024年的战客"与"2025年的战客"
- **操作**:
  - 关旧: `UPDATE valid_to = 'YYYY-01-01'` 所有当前记录
  - 开新: INSERT 新记录，`status_year = 当前年份`, `valid_from = 'YYYY-01-01'`

### 2.2 原则二：期初锁定 (Initial Lock)

- **规则**: 每年的初始名单基于**上一年12月31日**的数据快照
- **条件**: 按 机构 + 产品线 排名 Top N 或 AUM >= 阈值

### 2.3 原则三：只增不减 (Ratchet Rule)

- **规则**: 同一 `status_year` 内，战客身份具有棘轮效应
  - **可以晋升**: 普通客户 → 战客（年中 AUM 达标）
  - **不可降级**: 战客 → 普通客户（即使 AUM 下跌）

---

## 3. 当前实现分析

### 3.1 表结构

```
customer.customer_plan_contract
├── contract_id (PK)
├── company_id (FK)
├── plan_code
├── product_line_code
├── product_line_name
├── customer_name
├── plan_name
├── is_strategic (boolean)
├── is_existing (boolean)
├── status_year (integer)
├── contract_status (varchar)
├── valid_from (date)
├── valid_to (date, default '9999-12-31')
├── created_at
└── updated_at
```

**唯一约束**: `(company_id, plan_code, product_line_code, valid_to)`

### 3.2 核心代码文件

| 文件 | 职责 | 问题 |
|------|------|------|
| `contract_sync.py` | SCD Type 2 状态同步 | 未实现"只增不减"规则 |
| `year_init.py` | 年度初始化 | 直接 UPDATE，破坏 SCD 版本 |
| `common_ctes.sql` | 共享 CTE 定义 | 逻辑正确 |
| `sync_insert.sql` | 插入新记录 | 未检查现有战客身份 |
| `close_old_records.sql` | 关闭旧记录 | 未考虑"只增不减" |

---

## 4. 数据验证结果

### 4.1 数据量级验证

**源数据 (2025年10月)**:
- `business.规模明细` 总记录: 37,124
- 不重复 company_id: 7,470
- 不重复合约组合: 14,773

**目标表**:
- `customer.customer_plan_contract` 总记录: 19,882
- 当前有效记录 (valid_to = '9999-12-31'): 19,882 (100%)
- 历史版本记录: 0 ❌

### 4.2 status_year 分布

| status_year | 不重复 company_id | 总记录数 |
|-------------|-------------------|----------|
| 2022 | 88 | 90 |
| 2023 | 4,562 | 4,757 |
| 2024 | 7,708 | 10,778 |
| 2025 | 3,722 | 4,257 |

**结论**: 2025年10月源数据的 7,470 个 company_id 全部在表中有记录，覆盖率 100%。
但只有 3,722 个是 2025 年创建的新记录，其余沿用旧记录（符合 SCD Type 2 设计）。

### 4.3 contract_status 一致性检查

| 当前状态 | 应有状态 | 数量 | 说明 |
|----------|----------|------|------|
| 正常 | **停缴** | **10,417** | ❌ 严重不一致 |
| 正常 | 正常 | 7,572 | ✓ 正确 |
| 停缴 | 停缴 | 1,638 | ✓ 正确 |
| 停缴 | 正常 | 255 | ❌ 不一致 |

**问题案例**: `company_id = 839950425`
- 2025年1月起供款变为 0
- 当前状态: "正常" (2024-04-30 创建)
- 应有状态: "停缴"
- **根因**: SCD Type 2 状态变更检测未正确触发

### 4.4 valid_from 分布

所有记录的 `valid_from` 都是月末日期（28/29/30/31日），没有1月1日的年度切断记录。

| 日期 | 记录数 |
|------|--------|
| 28日 | 431 |
| 29日 | 55 |
| 30日 | 6,318 |
| 31日 | 13,078 |
| **1日** | **0** ❌ |

---

## 5. 差距详细分析

### 5.1 GAP-1: 年度切断未实现 (严重)

**规范要求**:
```
每年1月1日:
1. 关闭所有当前记录: UPDATE valid_to = 'YYYY-01-01'
2. 插入新记录: status_year = 当前年份, valid_from = 'YYYY-01-01'
```

**当前实现**:
- `year_init.py` 只做 UPDATE 现有记录的 `is_strategic` 和 `is_existing`
- 没有关闭旧记录
- 没有创建新的 `status_year` 记录

**影响**:
- 无法区分"2024年的战客"与"2025年的战客"
- 历史数据可能被污染
- KPI 统计不准确

### 5.2 GAP-2: 只增不减规则未实现 (严重)

**规范要求**:
```python
if is_strategic_db == True and is_strategic_calculated == False:
    # 战客 AUM 下跌 -> 依然保持战客身份
    final_strategic_status = True
    trigger_scd_update = False  # 不更新记录
```

**当前实现** (`close_old_records.sql` line 57-60):
```sql
AND (
    old.contract_status IS DISTINCT FROM new.contract_status
    OR old.is_strategic IS DISTINCT FROM new.is_strategic  -- ❌ 会触发降级
    OR old.is_existing IS DISTINCT FROM new.is_existing
)
```

**影响**:
- 战客可能被错误降级
- 违反业务"棘轮效应"规则

### 5.3 GAP-3: 设计理念冲突 (中等)

**问题**: `year_init.py` 和 `contract_sync.py` 的设计理念冲突

| 模块 | 设计假设 | 操作方式 |
|------|----------|----------|
| `year_init.py` | 单记录设计 | 直接 UPDATE |
| `contract_sync.py` | SCD Type 2 | 关旧开新 |

**`year_init.py` 问题代码** (line 155-161):
```sql
UPDATE customer.customer_plan_contract c
SET is_strategic = TRUE
...
WHERE c.is_strategic = FALSE
```

**影响**:
- 直接修改现有记录，破坏 SCD 版本历史
- 无法追溯状态变更时间点

### 5.4 GAP-4: contract_status 同步失效 (严重)

**现象**: 10,417 条记录应从"正常"变为"停缴"但未更新

**可能原因**:
1. ETL Hook 未正确触发 `sync_contract_status()`
2. `contribution_12m` CTE 的时间窗口计算问题
3. SCD Type 2 变更检测逻辑缺陷

**验证 SQL**:
```sql
-- 检查 839950425 的 12 个月供款
SELECT SUM(供款) FROM business."规模明细"
WHERE company_id = '839950425'
  AND 月度 >= (CURRENT_DATE - INTERVAL '12 months');
-- 结果: 0 (应触发状态变更)
```

---

## 6. 修复建议

### 6.1 优先级排序

| 优先级 | GAP | 修复工作量 | 业务影响 |
|--------|-----|------------|----------|
| P0 | GAP-4 contract_status 同步失效 | 中 | 高 |
| P0 | GAP-1 年度切断未实现 | 高 | 高 |
| P1 | GAP-2 只增不减规则 | 中 | 中 |
| P2 | GAP-3 设计理念冲突 | 高 | 中 |

### 6.2 GAP-4 修复方案: contract_status 同步

**目标**: 修复 10,417 条状态不一致的记录

**方案 A: 重新执行全量同步**
```bash
uv run python -m work_data_hub.customer_mdm.contract_sync
```

**方案 B: 增量修复 SQL**
```sql
-- Step 1: 关闭状态不一致的旧记录
-- Step 2: 插入正确状态的新记录
```

**验证**: 执行后检查不一致记录数应为 0

### 6.3 GAP-1 修复方案: 年度切断

**目标**: 实现1月1日强制生成新记录

**修改文件**: `src/work_data_hub/customer_mdm/year_init.py`

**新增函数**: `annual_cutover(year: int)`
```python
def annual_cutover(year: int):
    """年度切断 - 1月1日执行"""
    # Step 1: 关闭所有当前记录
    UPDATE valid_to = f'{year}-01-01'
    WHERE valid_to = '9999-12-31'

    # Step 2: 为所有活跃客户插入新记录
    INSERT INTO customer_plan_contract
    SELECT ..., status_year = year, valid_from = f'{year}-01-01'
```

**触发机制**: 添加到 ETL Hook 或定时任务

### 6.4 GAP-2 修复方案: 只增不减规则

**目标**: 战客身份只能晋升不能降级

**修改文件**: `src/work_data_hub/customer_mdm/sql/close_old_records.sql`

**修改逻辑**:
```sql
-- 原逻辑 (会触发降级)
OR old.is_strategic IS DISTINCT FROM new.is_strategic

-- 新逻辑 (只允许晋升)
OR (old.is_strategic = FALSE AND new.is_strategic = TRUE)
```

### 6.5 GAP-3 修复方案: 统一设计理念

**目标**: 统一 `year_init.py` 和 `contract_sync.py` 的设计

**方案**: 重构 `year_init.py` 使用 SCD Type 2 模式
- 删除直接 UPDATE 逻辑
- 改为调用 `contract_sync.py` 的关旧开新逻辑

---

## 7. 测试验证清单

### 7.1 单元测试

- [ ] 测试"只增不减"规则：战客 AUM 下跌不触发降级
- [ ] 测试"晋升"规则：普通客户 AUM 达标触发晋升
- [ ] 测试年度切断：1月1日正确生成新记录

### 7.2 集成测试

- [ ] 验证 ETL Hook 正确触发 `sync_contract_status()`
- [ ] 验证 `contribution_12m` 时间窗口计算正确
- [ ] 验证 SCD Type 2 版本链完整性

### 7.3 数据验证 SQL

```sql
-- 验证状态一致性
SELECT COUNT(*) FROM (
    -- 计算预期状态 vs 实际状态
) WHERE expected != actual;
-- 预期结果: 0

-- 验证年度切断记录
SELECT COUNT(*) FROM customer.customer_plan_contract
WHERE EXTRACT(DAY FROM valid_from) = 1
  AND EXTRACT(MONTH FROM valid_from) = 1;
-- 预期结果: > 0 (修复后)
```

---

## 8. 附录

### 8.1 相关文件清单

| 文件路径 | 说明 |
|----------|------|
| `src/work_data_hub/customer_mdm/contract_sync.py` | 主同步逻辑 |
| `src/work_data_hub/customer_mdm/year_init.py` | 年度初始化 |
| `src/work_data_hub/customer_mdm/sql/common_ctes.sql` | 共享 CTE |
| `src/work_data_hub/customer_mdm/sql/sync_insert.sql` | 插入 SQL |
| `src/work_data_hub/customer_mdm/sql/close_old_records.sql` | 关闭 SQL |
| `src/work_data_hub/customer_mdm/strategic.py` | 战客阈值配置 |
| `config/customer_mdm.yaml` | 配置文件 |
| `docs/memories/战客身份定义与更新逻辑.md` | 业务规范 |

### 8.2 配置参数

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `strategic_threshold` | 500,000,000 | 战客 AUM 阈值 (5亿) |
| `whitelist_top_n` | 10 | 每机构每产品线 Top N |
| `status_year` | 2026 | 当前考核年度 |

### 8.3 关键 SQL 验证脚本

```sql
-- 检查状态不一致记录数
WITH contribution_12m AS (
    SELECT company_id, 计划代码, 产品线代码,
           CASE WHEN SUM(COALESCE(供款, 0)) > 0 THEN TRUE ELSE FALSE END as has_contribution
    FROM business."规模明细"
    WHERE 月度 >= (CURRENT_DATE - INTERVAL '12 months')
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码
),
latest_source AS (
    SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
        company_id, 计划代码, 产品线代码, 期末资产规模
    FROM business."规模明细"
    WHERE company_id IS NOT NULL
    ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
)
SELECT
    cpc.contract_status as current_status,
    CASE WHEN ls.期末资产规模 > 0 AND COALESCE(c12.has_contribution, FALSE) = TRUE
         THEN '正常' ELSE '停缴' END as expected_status,
    COUNT(*) as count
FROM customer.customer_plan_contract cpc
JOIN latest_source ls ON cpc.company_id = ls.company_id
    AND cpc.plan_code = ls.计划代码 AND cpc.product_line_code = ls.产品线代码
LEFT JOIN contribution_12m c12 ON ls.company_id = c12.company_id
    AND ls.计划代码 = c12.计划代码 AND ls.产品线代码 = c12.产品线代码
WHERE cpc.valid_to = '9999-12-31'
GROUP BY cpc.contract_status, expected_status;
```

---

**文档结束**

