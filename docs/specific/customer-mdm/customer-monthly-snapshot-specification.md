# customer monthly snapshot (Dual Tables) 业务规格说明书

> **版本**: v0.3
> **创建日期**: 2026-01-11
> **更新日期**: 2026-02-09
> **状态**: 已实现
> **关联文档**:
> - [customer-plan-contract-specification.md](./customer-plan-contract-specification.md)
> - [customer-identity-monthly-snapshot-implementation-v3.2-project-based.md](./customer-identity-monthly-snapshot-implementation-v3.2-project-based.md)

> [!IMPORTANT]
> **实际实现 (Story 7.6-16: 双表粒度分离)**
>
> 本文档描述的是 **双表设计** 的实际实现：
>
> | 表名 | 粒度 | 用途 |
> |------|------|------|
> | `customer.fct_customer_product_line_monthly` | Company + ProductLine | 战客/已客/中标/AUM汇总 |
> | `customer.fct_customer_plan_monthly` | Company + Plan + ProductLine | 流失/合约状态/AUM明细 |
>
> **设计原因**：
> - `is_winning_this_year` (中标) 天然粒度是 ProductLine 级别
> - `is_churned_this_year` (流失) 天然粒度是 Plan 级别
> - 双表设计让每个业务事件在其天然粒度追踪，符合 Kimball 维度建模最佳实践

---

## 0. 快速理解：表格关系总览

### 0.1 一句话解释

| 表 | 一句话解释 |
|----|-----------|
| **customer_plan_contract** | 签约记录（谁买了什么，是否战客/已客） |
| **fct_customer_product_line_monthly** | 产品线级月度报告（中标/战客/AUM汇总） |
| **fct_customer_plan_monthly** | 计划级月度报告（流失/合约状态/AUM明细） |

### 0.2 两张事实表的关系

```
customer_plan_contract
(签约记录 - OLTP)
┌─────────────────────┐
│ company_id          │
│ plan_code           │
│ product_line_code   │
│ is_strategic        │
│ is_existing         │
│ contract_status     │
└─────────────────────┘
        │
        ├── 聚合到产品线粒度 ───────────────┐
        │                                 │
        ▼                                 ▼
fct_customer_product_line_monthly   fct_customer_plan_monthly
(产品线级快照 - OLAP)                (计划级快照 - OLAP)
```

---

## 1. 表概述

### 1.1 设计目标

双表快照用于：

- 每月月末固化客户状态和规模（历史趋势分析）
- 中标/流失事件在正确粒度落表
- 兼顾产品线级 BI 汇总与计划级明细分析

### 1.2 表职责分工

| 表 | 主要职责 |
|----|----------|
| `fct_customer_product_line_monthly` | 产品线级汇总：战客/已客/中标/AUM/计划数 |
| `fct_customer_plan_monthly` | 计划级明细：流失/合约状态/AUM |

---

## 2. 表结构定义（简化版）

### 2.1 产品线级事实表

```sql
CREATE TABLE customer.fct_customer_product_line_monthly (
    snapshot_month DATE NOT NULL,
    company_id VARCHAR NOT NULL,
    product_line_code VARCHAR(20) NOT NULL,
    product_line_name VARCHAR(50) NOT NULL,
    customer_name VARCHAR(200),
    is_strategic BOOLEAN DEFAULT FALSE,
    is_existing BOOLEAN DEFAULT FALSE,
    is_new BOOLEAN DEFAULT FALSE,
    is_winning_this_year BOOLEAN DEFAULT FALSE,
    is_churned_this_year BOOLEAN DEFAULT FALSE,
    aum_balance DECIMAL(20,2) DEFAULT 0,
    plan_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_month, company_id, product_line_code)
);
```

### 2.2 计划级事实表

```sql
CREATE TABLE customer.fct_customer_plan_monthly (
    snapshot_month DATE NOT NULL,
    company_id VARCHAR NOT NULL,
    plan_code VARCHAR NOT NULL,
    product_line_code VARCHAR(20) NOT NULL,
    customer_name VARCHAR(200),
    plan_name VARCHAR(200),
    product_line_name VARCHAR(50) NOT NULL,
    is_churned_this_year BOOLEAN DEFAULT FALSE,
    contract_status VARCHAR(50),
    aum_balance DECIMAL(20,2) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_month, company_id, plan_code, product_line_code)
);
```

### 2.3 核心索引（参考 migrations 完整列表）

- 产品线表：`idx_fct_pl_snapshot_month`, `idx_fct_pl_company`, `idx_fct_pl_product_line`
- 计划表：`idx_fct_plan_snapshot_month`, `idx_fct_plan_company`, `idx_fct_plan_plan_code`

---

## 3. 状态定义

### 3.1 ProductLine 级（汇总）

- **is_strategic**：来自 `customer_plan_contract`，BOOL_OR 聚合
- **is_existing**：来自 `customer_plan_contract`，BOOL_OR 聚合
- **is_new**：`is_winning_this_year AND NOT is_existing`
- **is_winning_this_year**：`customer.当年中标` 按 `company_id + 产品线代码` 判定
- **is_churned_this_year**：`customer.当年流失` 按 `company_id + 产品线代码` 判定（产品线级聚合）

### 3.2 Plan 级（明细）

- **is_churned_this_year**：`customer.当年流失` 按 `company_id + 年金计划号` 判定
- **contract_status**：来自 `customer_plan_contract`

### 3.3 AUM 计算

- 产品线级：`SUM(business.规模明细.期末资产规模)` 按 `(company_id, 产品线代码, 月度)`
- 计划级：`SUM(business.规模明细.期末资产规模)` 按 `(company_id, 计划代码, 产品线代码, 月度)`

---

## 4. 数据更新逻辑（核心 SQL 摘要）

### 4.1 更新触发时机

| 触发方式 | 说明 | 频率 |
|----------|------|------|
| Post-ETL Hook | `customer_plan_contract` 更新后自动触发 | 月度 |
| 手动触发 | `customer-mdm snapshot --period YYYYMM` | 按需 |

### 4.2 产品线级快照刷新（摘要）

```sql
INSERT INTO customer.fct_customer_product_line_monthly (...)
SELECT
  :snapshot_month AS snapshot_month,
  c.company_id,
  c.product_line_code,
  MAX(c.product_line_name) AS product_line_name,
  MAX(c.customer_name) AS customer_name,
  BOOL_OR(c.is_strategic) AS is_strategic,
  BOOL_OR(c.is_existing) AS is_existing,
  (EXISTS (...) AND NOT BOOL_OR(c.is_existing)) AS is_new,
  EXISTS (...) AS is_winning_this_year,
  EXISTS (...) AS is_churned_this_year,
  COALESCE(SUM(s.期末资产规模), 0) AS aum_balance,
  COUNT(DISTINCT c.plan_code) AS plan_count
FROM customer.customer_plan_contract c
LEFT JOIN business.规模明细 s
  ON s.company_id = c.company_id
 AND s.产品线代码 = c.product_line_code
 AND s.月度 = DATE_TRUNC('month', :snapshot_month)
WHERE c.valid_to = '9999-12-31'
GROUP BY c.company_id, c.product_line_code
ON CONFLICT (...) DO UPDATE ...;
```

### 4.3 计划级快照刷新（摘要）

```sql
INSERT INTO customer.fct_customer_plan_monthly (...)
SELECT
  :snapshot_month AS snapshot_month,
  c.company_id,
  c.plan_code,
  c.product_line_code,
  c.customer_name,
  c.plan_name,
  c.product_line_name,
  EXISTS (...) AS is_churned_this_year,
  c.contract_status,
  COALESCE(SUM(s.期末资产规模), 0) AS aum_balance
FROM customer.customer_plan_contract c
LEFT JOIN business.规模明细 s
  ON s.company_id = c.company_id
 AND s.计划代码 = c.plan_code
 AND s.产品线代码 = c.product_line_code
 AND s.月度 = DATE_TRUNC('month', :snapshot_month)
WHERE c.valid_to = '9999-12-31'
GROUP BY c.company_id, c.plan_code, c.product_line_code
ON CONFLICT (...) DO UPDATE ...;
```

---

## 5. 典型查询示例

### 5.1 产品线级全量状态视图（示意）

```sql
CREATE VIEW v_customer_product_line_status AS
SELECT
  f.snapshot_month,
  f.company_id,
  f.product_line_code,
  f.product_line_name,
  f.customer_name,
  f.is_strategic,
  f.is_existing,
  f.is_new,
  f.is_winning_this_year,
  f.is_churned_this_year,
  f.aum_balance,
  f.plan_count
FROM customer.fct_customer_product_line_monthly f;
```

### 5.2 计划级明细视图（示意）

```sql
CREATE VIEW v_customer_plan_status AS
SELECT
  f.snapshot_month,
  f.company_id,
  f.plan_code,
  f.product_line_code,
  f.plan_name,
  f.customer_name,
  f.contract_status,
  f.is_churned_this_year,
  f.aum_balance
FROM customer.fct_customer_plan_monthly f;
```

---

## 6. 附录

### 6.1 相关文档

| 文档 | 路径 |
|------|------|
| contract表规格 | `customer-plan-contract-specification.md` |
| V3.2实施方案 | `customer-identity-monthly-snapshot-implementation-v3.2-project-based.md` |
| 数据血缘 | `customer-mdm-data-lineage.md` |

### 6.2 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v0.1 | 2026-01-11 | 初稿，基于contract表规格和用户验证反馈创建 |
| v0.2 | 2026-02-09 | Story 7.6-16: 双表粒度分离，更新实现说明 |
| v0.3 | 2026-02-09 | 替换单表 DDL/SQL 为双表实现，补充职责分工 |
