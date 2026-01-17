# customer.customer_monthly_snapshot 业务规格说明书

> **版本**: v0.1
> **创建日期**: 2026-01-11
> **状态**: 待验证
> **关联文档**:
> - [customer-plan-contract-specification.md](./customer-plan-contract-specification.md)
> - [customer-identity-monthly-snapshot-implementation-v3.2-project-based.md](./customer-identity-monthly-snapshot-implementation-v3.2-project-based.md)

---

## 0. 快速理解：表格关系总览

### 0.1 一句话解释

| 表 | 一句话解释 |
|----|-----------|
| **customer_plan_contract** | 签约记录（谁买了什么，是否战客/已客） |
| **customer_monthly_snapshot** | 月度报告（这个月中标了谁？解约了谁？规模多少？） |

### 0.2 两张表的关系

```
customer_plan_contract              customer_monthly_snapshot
(签约记录 - OLTP)                   (月度快照 - OLAP)
┌─────────────────────┐             ┌─────────────────────┐
│ company_id          │             │ snapshot_month      │
│ plan_code           │             │ company_id          │
│ product_line_code   │─────JOIN───→│ plan_code           │
│                     │             │ product_line_code   │
│ is_strategic  ──────┼─────────────┼→ (通过JOIN获取)     │
│ is_existing   ──────┼─────────────┼→ (通过JOIN获取)     │
│ contract_status     │             │                     │
│                     │             │ is_winning_this_year│
│                     │             │ is_churned_this_year│
│                     │             │ aum_balance         │
└─────────────────────┘             └─────────────────────┘
```

### 0.3 为什么需要两张表？

| 问题 | contract表 | snapshot表 |
|------|-----------|------------|
| 战客/已客状态 | ✅ 唯一真相来源 | ❌ 通过JOIN获取 |
| 中标/解约状态 | ❌ | ✅ 月度滚动更新 |
| 历史规模 | ❌ | ✅ 每月固化 |
| 查询场景 | 当前状态 | 历史趋势 |

---

## 1. 表概述

### 1.1 设计目标

`customer.customer_monthly_snapshot` 是客户业务状态的月度快照表（OLAP），用于：

- 每月月末固化客户状态和规模
- 记录当年中标/解约事件
- 支持历史趋势分析和Power BI报表

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| 状态固化 | 每月快照，不可修改历史数据 |
| 中标追踪 | 记录当年中标客户（年度重置） |
| 解约追踪 | 记录当年解约客户（年度重置） |
| 规模汇总 | 按业务主键聚合月末资产规模 |

---

## 2. 表结构定义

### 2.1 DDL

```sql
CREATE TABLE customer.customer_monthly_snapshot (
    -- 复合主键
    snapshot_month DATE NOT NULL,                   -- 快照月份（月末最后一日）
    company_id VARCHAR NOT NULL,                    -- 客户ID
    plan_code VARCHAR NOT NULL,                     -- 计划代码
    product_line_code VARCHAR(20) NOT NULL,         -- 产品线代码

    -- 冗余字段（便于查询）
    product_line_name VARCHAR(50) NOT NULL,         -- 产品线名称

    -- 状态标签（当年事件，年度重置）
    is_winning_this_year BOOLEAN DEFAULT FALSE,     -- 当年中标
    is_churned_this_year BOOLEAN DEFAULT FALSE,     -- 当年解约

    -- 度量值
    aum_balance DECIMAL(20,2) DEFAULT 0,            -- 月末资产规模

    -- 审计字段
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 主键约束
    PRIMARY KEY (snapshot_month, company_id, plan_code, product_line_code),

    -- 外键约束
    CONSTRAINT fk_snapshot_company FOREIGN KEY (company_id)
        REFERENCES customer."年金客户"(company_id),
    CONSTRAINT fk_snapshot_product_line FOREIGN KEY (product_line_code)
        REFERENCES mapping."产品线"(产品线代码)
);
```

### 2.2 索引

```sql
-- 常用查询索引
CREATE INDEX idx_snapshot_month ON customer.customer_monthly_snapshot(snapshot_month);
CREATE INDEX idx_snapshot_company ON customer.customer_monthly_snapshot(company_id);
CREATE INDEX idx_snapshot_product_line ON customer.customer_monthly_snapshot(product_line_code);

-- 复合索引
CREATE INDEX idx_snapshot_month_company ON customer.customer_monthly_snapshot(snapshot_month, company_id);

-- BRIN索引（时间范围查询）
CREATE INDEX idx_snapshot_month_brin ON customer.customer_monthly_snapshot USING BRIN (snapshot_month);

-- 部分索引
CREATE INDEX idx_snapshot_winning ON customer.customer_monthly_snapshot(snapshot_month, company_id)
    WHERE is_winning_this_year = TRUE;
CREATE INDEX idx_snapshot_churned ON customer.customer_monthly_snapshot(snapshot_month, company_id)
    WHERE is_churned_this_year = TRUE;
```

### 2.3 字段说明

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| `snapshot_month` | DATE | 快照月份（月末最后一日） | 系统生成 |
| `company_id` | VARCHAR | 客户ID | `customer_plan_contract` |
| `plan_code` | VARCHAR | 计划代码 | `customer_plan_contract` |
| `product_line_code` | VARCHAR(20) | 产品线代码 | `customer_plan_contract` |
| `product_line_name` | VARCHAR(50) | 产品线名称（冗余） | `mapping."产品线"` |
| `is_winning_this_year` | BOOLEAN | 当年中标 | `ledger.当年中标` |
| `is_churned_this_year` | BOOLEAN | 当年解约 | `ledger.当年解约` |
| `aum_balance` | DECIMAL(20,2) | 月末资产规模 | `business.规模明细` |

---

## 3. 状态定义

### 3.1 is_winning_this_year（当年中标）

```
判定时机：月度滚动更新
数据来源：ledger.当年中标
重置周期：每年1月清零
判定规则：
  - 业务主键存在于当年中标名单 → TRUE
  - 否则 → FALSE
```

### 3.2 is_churned_this_year（当年解约）

```
判定时机：月度滚动更新
数据来源：ledger.当年解约
重置周期：每年1月清零
判定规则：
  - 业务主键存在于当年解约名单 → TRUE
  - 否则 → FALSE
```

### 3.3 aum_balance（月末资产规模）

```
判定时机：月度更新
数据来源：business.规模明细
计算规则：
  - 按业务主键(company_id + plan_code + product_line_code)聚合
  - SUM(期末资产规模)
```

---

## 4. 数据更新逻辑

### 4.1 更新触发时机

| 触发方式 | 说明 | 频率 |
|----------|------|------|
| Post-ETL Hook | `customer_plan_contract` 更新后自动触发 | 月度 |
| 手动触发 | `customer-mdm snapshot --period 202501` | 按需 |

### 4.2 快照生成SQL

```sql
INSERT INTO customer.customer_monthly_snapshot (
    snapshot_month,
    company_id,
    plan_code,
    product_line_code,
    product_line_name,
    is_winning_this_year,
    is_churned_this_year,
    aum_balance
)
SELECT
    :snapshot_month as snapshot_month,
    c.company_id,
    c.plan_code,
    c.product_line_code,
    p.产品线 as product_line_name,

    -- 当年中标判定
    EXISTS (
        SELECT 1 FROM ledger.当年中标 w
        WHERE w.company_id = c.company_id
          AND w.年金计划号 = c.plan_code
          AND w.产品线代码 = c.product_line_code
          AND EXTRACT(YEAR FROM w.中标日期) = EXTRACT(YEAR FROM :snapshot_month)
    ) as is_winning_this_year,

    -- 当年解约判定
    EXISTS (
        SELECT 1 FROM ledger.当年解约 l
        WHERE l.company_id = c.company_id
          AND l.年金计划号 = c.plan_code
          AND l.产品线代码 = c.product_line_code
          AND EXTRACT(YEAR FROM l.流失日期) = EXTRACT(YEAR FROM :snapshot_month)
    ) as is_churned_this_year,

    -- 月末资产规模
    COALESCE(SUM(s.期末资产规模), 0) as aum_balance

FROM customer.customer_plan_contract c
LEFT JOIN mapping."产品线" p ON c.product_line_code = p.产品线代码
LEFT JOIN business.规模明细 s ON
    c.company_id = s.company_id
    AND c.plan_code = s.计划代码
    AND c.product_line_code = s.产品线代码
    AND s.月度 = :snapshot_month
WHERE c.valid_to = '9999-12-31'  -- 仅当前有效合约
GROUP BY c.company_id, c.plan_code, c.product_line_code, p.产品线

ON CONFLICT (snapshot_month, company_id, plan_code, product_line_code)
DO UPDATE SET
    is_winning_this_year = EXCLUDED.is_winning_this_year,
    is_churned_this_year = EXCLUDED.is_churned_this_year,
    aum_balance = EXCLUDED.aum_balance,
    updated_at = CURRENT_TIMESTAMP;
```

---

## 5. 与contract表的关联查询

### 5.1 完整客户状态视图

```sql
-- 获取完整客户状态（合并两张表）
CREATE VIEW v_customer_full_status AS
SELECT
    s.snapshot_month,
    s.company_id,
    s.plan_code,
    s.product_line_code,
    s.product_line_name,

    -- 来自contract表
    c.is_strategic,
    c.is_existing,
    c.contract_status,

    -- 来自snapshot表
    s.is_winning_this_year,
    s.is_churned_this_year,
    s.aum_balance

FROM customer.customer_monthly_snapshot s
JOIN customer.customer_plan_contract c ON
    s.company_id = c.company_id
    AND s.plan_code = c.plan_code
    AND s.product_line_code = c.product_line_code
    AND c.valid_to = '9999-12-31';
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

