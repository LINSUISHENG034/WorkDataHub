# customer_plan_contract 状态字段实现缺口分析

> **创建日期**: 2026-02-03
> **分析人**: Claude Code
> **状态**: 待审核
> **关联文档**:
> - [customer-plan-contract-specification.md](./customer-plan-contract-specification.md)
> - [Story 7.6-6](../../sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md)
> - [Story 7.6-9](../../sprint-artifacts/stories/epic-customer-mdm/7.6-9-index-trigger-optimization.md)

---

## 1. 问题概述

### 1.1 问题描述

`customer.customer_plan_contract` 表中的三个关键状态字段 (`is_strategic`, `is_existing`, `contract_status`) 未按规范实现完整的业务逻辑。当前实现仅使用占位值或简化逻辑。

### 1.2 发现背景

- Story 7.6-6 (Contract Status Sync) 实现时，将这些字段标记为 "placeholder, to be implemented in Story 7.6-9"
- Story 7.6-9 (Index & Trigger Optimization) 实际范围仅包括触发器和索引优化，**未包含**这些业务逻辑
- 结果是这些字段的完整逻辑被遗漏

---

## 2. 预期 vs 实际对比

### 2.1 字段级对比

| 字段 | 规范定义 | Story 7.6-6 预期 | 实际实现 | 状态 |
|------|----------|------------------|----------|------|
| `is_strategic` | 战客标识 (5亿阈值+白名单) | "Full logic in Story 7.6-9" | 固定 `FALSE` | **缺失** |
| `is_existing` | 已客标识 (上年末有资产) | "Full logic in Story 7.6-9" | 固定 `FALSE` | **缺失** |
| `contract_status` | 正常/停缴 (12个月滚动窗口) | "Full v2 logic when 供款 data available" | 简化逻辑 (单月AUM) | **不完整** |

### 2.2 Story 范围对比

**Story 7.6-6 Dev Notes 中的声明**:
```
> [!IMPORTANT]
> For Story 7.6-6 (v1), initialize placeholder values:
> - `is_strategic = FALSE` — Full logic implemented in Story 7.6-9
> - `is_existing = FALSE` — Full logic implemented in Story 7.6-9
> - `status_year = EXTRACT(YEAR FROM CURRENT_DATE)`
```

**Story 7.6-9 实际验收标准**:
- AC-1: 创建 `trg_sync_product_line_name` 触发器
- AC-2: 验证 BRIN 和 Partial 索引覆盖
- AC-3: 验证触发器功能

**结论**: Story 7.6-9 的范围定义中**不包含**状态字段的业务逻辑实现。

---

## 3. 缺失的业务逻辑详解

### 3.1 is_strategic (战客标识)

**规范来源**: `customer-plan-contract-specification.md` §4.4.3

```
判定时机：年度初始化（每年1月）
数据来源：
  1. 上年度末资产规模汇总（business.规模明细）
  2. 战客白名单（手工维护）
判定规则：
  - 上年末资产规模 >= 5亿阈值 → 战客
  - 在白名单中（各机构前10大）→ 战客
  - 其他 → 非战客
```

**当前实现** (`contract_sync.py:110`):
```python
FALSE as is_strategic,  -- Story 7.6-9 implements full logic
```

**缺失内容**:
1. 5亿阈值判定逻辑
2. 白名单生成逻辑（各机构前10大客户）
3. 年度初始化触发机制

### 3.2 is_existing (已客标识)

**规范来源**: `customer-plan-contract-specification.md` §4.4.3

```
判定时机：年度初始化（每年1月）
数据来源：上年度末资产规模汇总（business.规模明细）
判定规则：
  - 上年末有资产（规模 > 0）→ 已客
  - 上年末无资产 → 新客
```

**当前实现** (`contract_sync.py:111`):
```python
FALSE as is_existing,  -- Story 7.6-9 implements full logic
```

**缺失内容**:
1. 上年末资产查询逻辑
2. 已客/新客判定逻辑
3. 年度初始化触发机制

### 3.3 contract_status (合约状态)

**规范来源**: `customer-plan-contract-specification.md` §4.3.1-4.3.2

```
判定时机：月度更新
数据来源：business.规模明细
判定规则：
  - 期末资产规模 > 0 且 过去12个月有供款 → 正常
  - 期末资产规模 > 0 且 过去12个月无供款 → 停缴
  - 期末资产规模 = 0 → 无效（不记录或标记）
```

**当前实现** (`contract_sync.py:113-115`):
```python
CASE
    WHEN s.期末资产规模 > 0 THEN '正常'
    ELSE '停缴'
END as contract_status,
```

**缺失内容**:
1. 12个月滚动窗口供款查询
2. 正常 vs 停缴的完整判定逻辑
3. 依赖 `供款` 字段数据可用性

---

## 4. 影响分析

### 4.1 数据质量影响

| 影响项 | 严重程度 | 说明 |
|--------|----------|------|
| 战客分析 | **高** | 所有客户 `is_strategic = FALSE`，无法识别战略客户 |
| 新客/已客分析 | **高** | 所有客户 `is_existing = FALSE`，无法区分新客和已客 |
| 停缴预警 | **中** | 简化逻辑可能误判（无供款数据时） |

### 4.2 下游影响

| 下游系统/表 | 影响 |
|-------------|------|
| `fct_customer_business_monthly_status` | 快照表依赖 contract 表的状态字段 |
| Power BI 报表 | 战客/已客筛选功能失效 |
| 业务分析 | 客户分层分析不可用 |

### 4.3 当前数据状态

基于 Story 7.6-6 完成记录：
- 总记录数: 19,882
- `is_strategic = FALSE`: 19,882 (100%)
- `is_existing = FALSE`: 19,882 (100%)
- `contract_status = '正常'`: 17,989 (90.5%)
- `contract_status = '停缴'`: 1,893 (9.5%)

---

## 5. 根因分析

### 5.1 范围遗漏 (Scope Gap)

```
Story 7.6-6 (Contract Status Sync)
    ↓
    声明: "is_strategic/is_existing full logic in Story 7.6-9"
    ↓
Story 7.6-9 (Index & Trigger Optimization)
    ↓
    实际范围: 仅触发器 + 索引验证
    ↓
    结果: 状态字段逻辑被遗漏
```

### 5.2 原因推测

1. **Story 标题误导**: "Index & Trigger Optimization" 未明确包含业务逻辑
2. **验收标准不完整**: Story 7.6-9 的 AC 未包含状态字段实现
3. **交接断层**: Story 7.6-6 的预期未被 Story 7.6-9 承接

---

## 6. 修复建议

### 6.1 建议方案

创建新的 Story 来补充缺失的业务逻辑：

**Story 7.6-11: Customer Status Field Enhancement**

| 任务 | 说明 | 优先级 |
|------|------|--------|
| Task 1 | 实现 `is_strategic` 战客判定逻辑 | P0 |
| Task 2 | 实现 `is_existing` 已客判定逻辑 | P0 |
| Task 3 | 实现 `contract_status` 完整逻辑 (依赖供款数据) | P1 |
| Task 4 | 创建年度初始化 CLI 命令 | P1 |
| Task 5 | 更新 Post-ETL Hook 调用增强后的逻辑 | P1 |

### 6.2 实现优先级

```
Phase 1 (立即): is_strategic + is_existing
  - 数据源已就绪 (business.规模明细)
  - 配置已存在 (config/customer_mdm.yaml)

Phase 2 (待数据): contract_status 完整逻辑
  - 依赖 供款 字段数据可用性
  - 需确认 business.规模明细 是否包含供款数据
```

### 6.3 验收标准建议

```yaml
AC-1: is_strategic 战客判定
  - 上年末资产规模 >= 5亿 → is_strategic = TRUE
  - 各机构前10大客户 → is_strategic = TRUE
  - 其他 → is_strategic = FALSE

AC-2: is_existing 已客判定
  - 上年末有资产记录 → is_existing = TRUE
  - 上年末无资产记录 → is_existing = FALSE

AC-3: 年度初始化命令
  - CLI: `customer-mdm init-year --year 2026`
  - 更新当年所有合约的 is_strategic/is_existing

AC-4: contract_status 完整逻辑 (Phase 2)
  - 期末资产 > 0 且 12个月有供款 → 正常
  - 期末资产 > 0 且 12个月无供款 → 停缴
```

---

## 7. 附录

### 7.1 相关代码位置

| 文件 | 说明 |
|------|------|
| `src/work_data_hub/customer_mdm/contract_sync.py` | 当前同步逻辑 |
| `io/schema/migrations/versions/008_create_customer_plan_contract.py` | 表结构定义 |
| `src/work_data_hub/cli/etl/hooks.py` | Post-ETL Hook 注册 |
| `config/customer_mdm.yaml` | 配置文件 (阈值、白名单参数) |

### 7.2 配置参数 (已存在)

```yaml
# config/customer_mdm.yaml
customer_mdm:
  strategic_threshold: 500000000  # 5亿元
  whitelist_top_n: 10             # 各机构前10大
  status_year: 2026
```

### 7.3 参考 SQL (规范文档)

**战客白名单生成**:
```sql
WITH ranked_customers AS (
    SELECT
        company_id,
        计划代码 as plan_code,
        产品线代码 as product_line_code,
        机构代码,
        SUM(期末资产规模) as total_aum,
        ROW_NUMBER() OVER (
            PARTITION BY 机构代码, 产品线代码
            ORDER BY SUM(期末资产规模) DESC
        ) as rank_in_branch
    FROM business.规模明细
    WHERE 月度 = (上年12月)
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码, 机构代码
)
SELECT company_id, plan_code, product_line_code
FROM ranked_customers
WHERE rank_in_branch <= 10
   OR total_aum >= 500000000;
```

---

## 8. 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.0 | 2026-02-03 | 初稿，完整问题分析 |
