# 客户身份管理重构：月度快照模型实施方案 (V3.2 - 基于项目实际)

> **版本说明**：本文档基于WorkDataHub项目的实际数据库结构，修正了V2.0方案中的数据库设计与现实不符的问题。
>
> **核心差异**：
> - V2.0建议创建`customer.dim_company`，但项目已有`mapping."年金客户"`
> - V2.0建议创建`customer.dim_annuity_plan`，但项目已有`mapping."年金计划"`
> - V3.1基于现有表结构进行增量设计，避免重复建设
>
> **V3.2更新（2026-01-08）**：
> - **维度设计修正**：业务类型和产品线是一对一关系，移除冗余的`business_type`字段
> - 统一使用产品线维度：`product_line_code`（PL201-PL204）+ `product_line_name`（企年受托等）
> - 新增业务类型聚合视图：支持按"受托/投资"分组查询
> - 简化表结构：合约表和快照表均使用单一产品线维度
> - 新增3.3节：性能优化与索引策略（BRIN索引、部分索引）

---

## **X\. 业务背景与术语定义**

本文档旨在针对公司年金基金管理系统中的**客户主数据管理 (MDM)** 痛点寻求改进优化, 当前系统面临多维度客户身份割裂（战客/已客/中标/流失）、s主键设计不统一以及数据治理缺失的问题。

### **X.1 业务领域**

* **行业**：年金基金管理  
* **产品线**：企年受托、企年投资、职年受托、职年投资 (详见postgres数据库mapping."年金计划")  
* **服务角色**：受托人 (Trustee)、投资管理人 (Investment Manager)

### **X.2 客户状态定义 (基于 Claude 文档优化)**

客户身份具有多重性与动态性，单一客户可能同时具备多种状态。

| 状态类型 | 业务定义 | 数据来源 | 更新频率 | 关键逻辑 |
| :---- | :---- | :---- | :---- | :---- |
| **战客 (Strategic)** | 战略重点客户（资产规模≥5亿）或者机构前十大客户 | 1\. 规模明细表算逻辑 2\. 手工白名单 | 年度初始化 \+ 手工修正 | 存量高价值客户，需重点维护 |
| **已客 (Existing)** | 存量客户 | 规模明细表（上年末资产\>0） | 年度滚动 | 基础客户群 |
| **中标 (Winning)** | 新签约客户 | 外部中标名单导入 | 月度滚动 | 增量数据，尚未产生规模 |
| **流失 (Churned)** | 流失客户 | 外部流失名单导入 | 月度滚动 | 需保留历史记录 |

### **2.3 核心数据源**

* **业务明细表 (business.规模明细)**：
  * **数据量**：**625,126** 行 (2022.12 - 2025.10)
  * **唯一客户数** (company_id)：**10,153**
  * **唯一计划数** (计划代码)：**1,131**
  * **增长速度**：2022年3,517行 → 2023年48,987行 → 2024年223,249行 → 2025年349,373行（仅前10个月）
  * **年增长率**：约 4-5 倍增长，远超预期

---

## 1. 方案概述

### 1.1 核心目标

基于现有`mapping` schema表结构，构建**分层清晰**的数据体系：

1. **基础层**：利用现有`mapping."年金客户"`和`mapping."年金计划"`作为维度表
2. **操作层**：新增`customer.customer_plan_contract`表，记录客户签约关系的精确时间线
3. **分析层**：新增`customer.fct_customer_business_monthly_status`表，提供月度快照

### 1.2 架构变更摘要

- **保留**：`mapping."年金客户"`（10436条记录）和`mapping."年金计划"`（1158条记录）
- **新增**：`customer.customer_plan_contract`（OLTP合约表）
- **新增**：`customer.fct_customer_business_monthly_status`（OLAP快照表）
- **数据源**：Legacy MySQL（enterprise/business schema）→ PostgreSQL（mapping/customer/business schema）

---

## 2. 现有数据库结构分析

### 2.1 mapping."年金客户"（客户主数据表）

**实际表结构**：

```sql
CREATE TABLE mapping."年金客户" (
    id SERIAL,
    company_id VARCHAR PRIMARY KEY,  -- 唯一标识，已建立 UNIQUE INDEX
    客户名称 VARCHAR,
    年金客户标签 VARCHAR,           -- 示例："仅受托流失"、"2502_新建客户"、"回流客户"
    年金客户类型 VARCHAR,           -- 枚举："流失客户"、"中标"、"已客"、"新客"、"空白"
    年金计划类型 VARCHAR,
    关键年金计划 VARCHAR,
    主拓机构代码 VARCHAR,
    主拓机构 VARCHAR,
    其他年金计划 VARCHAR,
    客户简称 VARCHAR,
    最新受托规模 DOUBLE PRECISION,
    最新投管规模 DOUBLE PRECISION,
    管理资格 VARCHAR,
    规模区间 VARCHAR,
    计划层规模 DOUBLE PRECISION,
    年缴费规模 DOUBLE PRECISION,
    外部受托规模 DOUBLE PRECISION,
    上报受托规模 DOUBLE PRECISION,
    上报投管规模 DOUBLE PRECISION,
    关联机构数 INTEGER,
    其他开拓机构 VARCHAR,
    计划状态 VARCHAR,
    关联计划数 INTEGER,
    备注 TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**关键字段说明**：

| 字段 | 用途 | 数据特点 |
|------|------|----------|
| `company_id` | 唯一标识 | 已有唯一索引，可作为外键 |
| `年金客户标签` | 业务标签 | 自由文本，如"2502_新建客户"、"仅受托流失" |
| `年金客户类型` | 客户分类 | 标准化枚举："新客"、"已客"、"中标"、"流失客户"、"空白" |
| `最新受托规模` | 当前规模 | 月末最新值，用于快速查询 |
| `最新投管规模` | 当前规模 | 月末最新值，用于快速查询 |

**明确需求**：
- 将现有表使用`年金客户标签 VARCHAR`修改为`tags JSONB`

### **为什么既要 tags JSONB 又要在快照里存 is\_strategic？**

| 维度 | dim\_company.tags (JSONB) | fct\_snapshot.is\_strategic |
| :---- | :---- | :---- |
| **时效** | **实时 (Real-time)** | **历史固化 (History)** |
| **场景** | **当下操作**：业务员打开系统，提示“这是VIP客户”。 | **历史回溯**：查询“2023年6月的战客流失率”。 |
| **逻辑** | 即使客户现在变为了普通客户，tags 会立即更新。 | 2023年6月的快照里，他依然记录为“战客”，确保历史报表不失真。 |
---

### 2.2 mapping."年金计划"（计划维度表）

**实际表结构**：

```sql
CREATE TABLE mapping."年金计划" (
    id SERIAL,
    年金计划号 VARCHAR PRIMARY KEY,  -- 业务主键，已建立 UNIQUE INDEX
    计划简称 VARCHAR,
    计划全称 VARCHAR,
    主拓代码 VARCHAR,
    计划类型 VARCHAR,                -- 枚举："单一计划"、"集合计划"
    客户名称 VARCHAR,
    company_id VARCHAR,               -- 外键，指向mapping."年金客户"
    管理资格 VARCHAR,
    计划状态 VARCHAR,
    主拓机构 VARCHAR,
    组合数 INTEGER,
    是否统括 INTEGER,
    备注 TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 现有索引
CREATE INDEX idx_年金计划_company_id ON mapping."年金计划"(company_id);
CREATE INDEX idx_年金计划_年金计划号 ON mapping."年金计划"("年金计划号");
```

---

### 2.3 数据源表（Legacy MySQL）

#### 2.3.1 business.规模明细（原始规模数据）

```sql
CREATE TABLE business.规模明细 (
    id INTEGER PRIMARY KEY,
    月度 DATE,
    业务类型 VARCHAR,                 -- 枚举："企年受托"、"企年投资"、"职年受托"、"职年投资"
                                     -- 注意：业务类型与产品线代码一对一映射（详见下文"产品线维度说明"）
    计划类型 VARCHAR,
    计划代码 VARCHAR,
    计划名称 VARCHAR,
    组合类型 VARCHAR,
    组合代码 VARCHAR,
    组合名称 VARCHAR,
    客户名称 VARCHAR,
    期初资产规模 DOUBLE PRECISION,
    期末资产规模 DOUBLE PRECISION,
    供款 DOUBLE PRECISION,
    流失(含待遇支付) DOUBLE PRECISION,
    流失 DOUBLE PRECISION,
    待遇支付 DOUBLE PRECISION,
    投资收益 DOUBLE PRECISION,
    当期收益率 DOUBLE PRECISION,
    机构代码 VARCHAR,
    机构名称 VARCHAR,
    产品线代码 VARCHAR,               -- 指向mapping."产品线".产品线代码
    年金账户号 VARCHAR,
    年金账户名 VARCHAR,
    company_id VARCHAR
);

-- 产品线维度说明
-- 业务类型与产品线代码一对一映射：
-- | 业务类型   | 产品线代码 | 产品线名称    |
-- |-----------|-----------|-------------|
-- | 企年受托   | PL202     | 企年受托     |
-- | 企年投资   | PL201     | 企年投资     |
-- | 职年投资   | PL203     | 职年投资     |
-- | 职年受托   | PL204     | 职年受托     |
-- 因此，在新表设计中统一使用产品线维度，业务类型可通过产品线代码派生。
```

---

## 3. 增量设计方案

### 3.1 新增表设计

#### 3.1.1 客户签约关系表（customer.customer_plan_contract）

**设计目标**：记录客户与计划的精确签约关系，支持SCD Type 2（缓慢变化维度）。

```sql
-- 在PostgreSQL中创建customer schema（如果不存在）
CREATE SCHEMA IF NOT EXISTS customer;

CREATE TABLE customer.customer_plan_contract (
    contract_id SERIAL PRIMARY KEY,
    company_id VARCHAR NOT NULL,                    -- 指向mapping."年金客户".company_id
    年金计划号 VARCHAR NOT NULL,                   -- 指向mapping."年金计划".年金计划号

    -- 产品线维度（统一维度，包含业务类型信息）
    产品线代码 VARCHAR(20) NOT NULL,                -- 指向mapping."产品线".产品线代码
    产品线名称 VARCHAR(50) NOT NULL,                 -- 冗余存储，便于查询（如"企年受托"、"企年投资"）

    -- 状态与时间（SCD Type 2风格）
    状态 VARCHAR(20) NOT NULL,                     -- 枚举："正常"、"流失"、"停缴"、"新中标"、"新到账"
    valid_from DATE NOT NULL,                      -- 精确到日的生效时间
    valid_to DATE DEFAULT '9999-12-31',           -- 9999表示当前有效

    -- 审计
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束（在数据清洗后建立）
    CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
        REFERENCES mapping."年金客户"(company_id),
    CONSTRAINT fk_contract_plan FOREIGN KEY (年金计划号)
        REFERENCES mapping."年金计划"(年金计划号),
    CONSTRAINT fk_contract_product_line FOREIGN KEY (产品线代码)
        REFERENCES mapping."产品线"(产品线代码),
    -- 复合唯一约束：确保同一客户在同一计划同一产品线下，同一时间只有一个有效状态
    CONSTRAINT uq_active_contract UNIQUE (company_id, 年金计划号, 产品线代码, valid_to)
);

-- 索引：加速当前有效合约的查询
CREATE INDEX idx_active_contracts ON customer.customer_plan_contract(company_id, 年金计划号)
WHERE valid_to = '9999-12-31';
CREATE INDEX idx_contract_product_line ON customer.customer_plan_contract(产品线代码);
```

**关键字段说明**：
- `company_id`：复用现有`mapping."年金客户".company_id`
- `年金计划号`：复用现有`mapping."年金计划".年金计划号`（业务主键）
- `产品线代码`：唯一标识产品线（PL201-PL204），同时确定了业务类型
- `产品线名称`：冗余存储产品线中文名称，便于查询和显示
- `valid_from`/`valid_to`：支持历史追溯和月内变动记录

**业务类型派生规则**：
```sql
-- 从产品线代码派生业务类型
CASE
    WHEN 产品线代码 IN ('PL202', 'PL204') THEN '受托'
    WHEN 产品线代码 IN ('PL201', 'PL203') THEN '投资'
    ELSE '未知'
END as business_type
```

---

#### 3.1.2 客户业务状态月度快照表（customer.fct_customer_business_monthly_status）

**设计目标**：每月月末生成快照，固化当月状态和规模，支持历史趋势分析。

```sql
CREATE TABLE customer.fct_customer_business_monthly_status (
    -- 复合主键维度
    snapshot_month DATE NOT NULL,                  -- 快照月份（例如 2025-10-01）
    company_id VARCHAR NOT NULL,                   -- 指向mapping."年金客户".company_id

    -- 产品线维度（统一维度，包含业务类型信息）
    product_line_code VARCHAR(20) NOT NULL,        -- 产品线代码（PL201-PL204）
    product_line_name VARCHAR(50) NOT NULL,         -- 产品线名称（企年受托、企年投资等）

    -- 状态标签（历史固化）
    is_strategic BOOLEAN DEFAULT FALSE,            -- 战客（基于mapping."年金客户".年金客户标签判断）
    is_existing BOOLEAN DEFAULT FALSE,             -- 已客（基于mapping."年金客户".年金客户类型）
    is_new BOOLEAN DEFAULT FALSE,                  -- 新客（基于mapping."年金客户".年金客户类型）
    is_winning BOOLEAN DEFAULT FALSE,              -- 本月中标（基于valid_from字段）
    is_churned BOOLEAN DEFAULT FALSE,              -- 本月流失（基于valid_to字段）

    -- 度量值
    aum_balance DECIMAL(20,2) DEFAULT 0,           -- 月末资产规模（来自business.规模明细）
    plan_count INTEGER DEFAULT 0,                  -- 关联计划数（来自customer_plan_contract）

    -- 审计字段
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    PRIMARY KEY (snapshot_month, company_id, product_line_code),

    -- 外键约束
    CONSTRAINT fk_snapshot_company FOREIGN KEY (company_id)
        REFERENCES mapping."年金客户"(company_id),
    CONSTRAINT fk_snapshot_product_line FOREIGN KEY (product_line_code)
        REFERENCES mapping."产品线"(产品线代码)
);

-- 索引：加速Power BI及常用查询
CREATE INDEX idx_snapshot_product_line ON customer.fct_customer_business_monthly_status(product_line_code);
CREATE INDEX idx_snapshot_product_name ON customer.fct_customer_business_monthly_status(product_line_name);
CREATE INDEX idx_snapshot_month_product ON customer.fct_customer_business_monthly_status(snapshot_month, product_line_code);
CREATE INDEX idx_snapshot_strategic ON customer.fct_customer_business_monthly_status(snapshot_month, is_strategic);
CREATE INDEX idx_snapshot_company ON customer.fct_customer_business_monthly_status(company_id);

-- 部分索引：只索引战客
CREATE INDEX idx_snapshot_strategic_customers
    ON customer.fct_customer_business_monthly_status(snapshot_month, company_id)
    WHERE is_strategic = TRUE;
```

**业务类型聚合视图**：

```sql
-- 为了支持按"受托/投资"分组的查询，创建业务类型聚合视图
CREATE VIEW v_customer_business_monthly_status_by_type AS
SELECT
    snapshot_month,
    company_id,
    product_line_code,
    product_line_name,
    -- 从产品线代码派生业务类型
    CASE
        WHEN product_line_code IN ('PL202', 'PL204') THEN '受托'
        WHEN product_line_code IN ('PL201', 'PL203') THEN '投资'
        ELSE '未知'
    END as business_type,
    is_strategic,
    is_existing,
    is_new,
    is_winning,
    is_churned,
    aum_balance,
    plan_count,
    updated_at
FROM customer.fct_customer_business_monthly_status;

-- 使用示例：按业务类型聚合
SELECT
    snapshot_month,
    business_type,
    SUM(aum_balance) as total_aum,
    COUNT(DISTINCT company_id) as customer_count
FROM v_customer_business_monthly_status_by_type
WHERE snapshot_month = '2025-10-01'
GROUP BY snapshot_month, business_type;
```

---

### 3.2 ETL数据处理逻辑

#### 3.2.1 维度与标签维护（Real-time/Daily）

**现状**：
- `mapping."年金客户"`和`mapping."年金计划"`已存在且定期更新
- `年金客户标签`和`年金客户类型`字段已有数据

**ETL任务**：
1. **从Legacy MySQL同步**：定期从`enterprise.business_info`、`enterprise.biz_label`同步到`mapping."年金客户"`
2. **标签处理**：将`enterprise.biz_label`的多维标签转换为`年金客户标签`字段的自由文本
3. **去重逻辑**：基于`company_id`进行UPSERT操作

---

#### 3.2.2 合约状态维护（Daily/Event-driven）

**核心逻辑**：基于`business.规模明细`的月度数据，生成合约关系。

```sql
-- 生成合约关系
-- 原则：如果在规模明细中出现，说明当月存在合约关系

INSERT INTO customer.customer_plan_contract (
    company_id,
    年金计划号,
    产品线代码,
    产品线名称,
    状态,
    valid_from,
    valid_to
)
SELECT DISTINCT ON (s.company_id, s.计划代码, s.产品线代码, s.月度)
    COALESCE(s.company_id, 'UNKNOWN') as company_id,
    s.计划代码 as 年金计划号,
    s.产品线代码,
    p.产品线 as 产品线名称,  -- 从产品线维度表获取名称
    CASE
        WHEN s.期末资产规模 > 0 THEN '正常'
        ELSE '流失'
    END as 状态,
    DATE_TRUNC('month', s.月度) as valid_from,
    '9999-12-31' as valid_to
FROM business.规模明细 s
LEFT JOIN mapping."产品线" p ON s.产品线代码 = p.产品线代码
WHERE s.月度 = (SELECT MAX(月度) FROM business.规模明细)  -- 最新月份
  AND s.产品线代码 IS NOT NULL
ORDER BY s.company_id, s.计划代码, s.产品线代码, s.月度 DESC
ON CONFLICT (company_id, 年金计划号, 产品线代码, valid_to)
DO UPDATE SET
    状态 = EXCLUDED.状态,
    产品线名称 = EXCLUDED.产品线名称,
    updated_at = CURRENT_TIMESTAMP;
```

**历史数据处理**：
- 对于历史数据，回溯`business.规模明细`，为每个月生成合约记录
- 处理集合计划的多对多关系：一个客户对应多个计划
- 注意：同一客户在同一计划下，不同产品线（如企年受托、企年投资）会生成多条合约记录

---

#### 3.2.3 生成月度快照（Monthly Job）

**核心逻辑**：基于`customer.customer_plan_contract`和`business.规模明细`，生成上月快照。

```sql
-- 生成月度快照
INSERT INTO customer.fct_customer_business_monthly_status (
    snapshot_month,
    company_id,
    product_line_code,
    product_line_name,
    is_strategic,
    is_existing,
    is_new,
    is_winning,
    is_churned,
    aum_balance,
    plan_count
)
WITH month_contracts AS (
    -- 查询当月有效的合约
    SELECT
        c.company_id,
        cb.产品线代码,
        cb.产品线名称,
        cb.状态,
        cb.valid_from,
        cb.valid_to
    FROM customer.customer_plan_contract cb
    JOIN mapping."年金客户" c ON cb.company_id = c.company_id
    WHERE cb.valid_from <= '2025-10-31'
      AND cb.valid_to >= '2025-10-01'
),
month_aum AS (
    -- 查询当月规模
    SELECT
        company_id,
        产品线代码,
        SUM(期末资产规模) as aum_balance
    FROM business.规模明细
    WHERE 月度 >= '2025-10-01' AND 月度 <= '2025-10-31'
      AND 产品线代码 IS NOT NULL
    GROUP BY company_id, 产品线代码
)
SELECT
    '2025-10-01'::DATE as snapshot_month,
    mc.company_id,
    mc.产品线代码,
    mc.产品线名称,

    -- 状态逻辑
    (c.年金客户类型 = '中标' OR c.年金客户标签 LIKE '%战客%') as is_strategic,
    (c.年金客户类型 = '已客') as is_existing,
    (c.年金客户类型 LIKE '新客%') as is_new,
    (mc.valid_from >= '2025-10-01' AND mc.状态 = '正常') as is_winning,
    (mc.valid_to <= '2025-10-31' AND mc.状态 = '流失') as is_churned,

    COALESCE(ma.aum_balance, 0) as aum_balance,
    COUNT(DISTINCT cb.年金计划号) as plan_count

FROM month_contracts mc
JOIN mapping."年金客户" c ON mc.company_id = c.company_id
LEFT JOIN month_aum ma ON mc.company_id = ma.company_id
    AND mc.产品线代码 = ma.产品线代码
LEFT JOIN customer.customer_plan_contract cb
    ON mc.company_id = cb.company_id
    AND mc.产品线代码 = cb.产品线代码
    AND cb.valid_from <= '2025-10-31'
    AND cb.valid_to >= '2025-10-01'
GROUP BY
    mc.company_id, mc.产品线代码, mc.产品线名称,
    c.年金客户类型, c.年金客户标签, mc.valid_from, mc.valid_to, ma.aum_balance
ON CONFLICT (snapshot_month, company_id, product_line_code)
DO UPDATE SET
    product_line_name = EXCLUDED.product_line_name,
    is_strategic = EXCLUDED.is_strategic,
    is_existing = EXCLUDED.is_existing,
    is_new = EXCLUDED.is_new,
    is_winning = EXCLUDED.is_winning,
    is_churned = EXCLUDED.is_churned,
    aum_balance = EXCLUDED.aum_balance,
    plan_count = EXCLUDED.plan_count,
    updated_at = CURRENT_TIMESTAMP;
```

---

### 3.3 性能优化与索引策略

**设计原则**：基于实际数据量（当前7万行，2年后预测<200万行），采用索引优化策略，暂不实施表分区。

#### 3.3.1 数据量分析

**当前数据量（PostgreSQL）**：

| 表 | 行数 | 大小 | 时间范围 | 月均增长 |
|---|---|---|---|---|
| business.规模明细 | 70,734 | 59MB | 2024-12 ~ 2025-10（11个月） | ~6,400行/月 |
| business.收入明细 | 16,270 | 10MB | 同上 | ~1,500行/月 |
| mapping.年金客户 | 10,436 | 2.8MB | - | - |
| mapping.年金计划 | 1,158 | 504KB | - | - |

**未来2年预测**：
- 基础增长：24个月 × 6,400行/月 = **15万行**
- 集合计划多对多放大5-10倍：**75万-150万行**
- **结论：远低于分区阈值（>500万行）**

---

#### 3.3.2 分区策略评估

| 建议 | 评估 | 决策 |
|------|------|------|
| 对业务明细表分区 | ❌ 数据量不足（2年后<200万行），分区收益<维护成本 | **暂不采纳** |
| MDM表分区 | ❌ 1万行级别，全表扫描已足够快 | **不采纳** |
| 预留分区扩展性 | ✅ 当单表>5GB或>500万行时再考虑 | **预留** |

**分区阈值参考**：
- PostgreSQL官方建议：表大小>10GB才考虑分区
- 行业实践：500万-1000万行以上才需要分区
- 维护成本：需要pg_partman或手动管理分区

**预留分区方案（仅供参考，暂不执行）**：

```sql
-- 当单表>5GB时，按月分区
CREATE TABLE business.规模明细_partitioned (
    LIKE business.规模明细 INCLUDING ALL
) PARTITION BY RANGE (月度);

-- 创建分区（示例）
CREATE TABLE business.规模明细_202510
    PARTITION OF business.规模明细_partitioned
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
```

---

#### 3.3.3 索引策略

**1. B-Tree索引（高基数、精确查询）**

```sql
-- ==================================================
-- 1.1 业务明细表索引（business.规模明细）
-- ==================================================

-- 高基数字段（客户、计划）
CREATE INDEX IF NOT EXISTS idx_规模明细_company_id
    ON business.规模明细(company_id);

CREATE INDEX IF NOT EXISTS idx_规模明细_计划代码
    ON business.规模明细(计划代码);

-- 复合索引（常见查询模式）
CREATE INDEX IF NOT EXISTS idx_规模明细_月度_业务类型
    ON business.规模明细(月度, 业务类型);

-- ==================================================
-- 1.2 维度表索引（mapping schema）
-- ==================================================

-- 已有唯一索引，无需额外创建
-- mapping.年金客户.company_id (PRIMARY KEY)
-- mapping.年金计划.年金计划号 (PRIMARY KEY)
```

**2. BRIN索引（时间范围查询）**

**BRIN vs B-Tree对比**：

| 索引类型 | 大小 | 查询性能 | 适用场景 |
|---------|------|---------|---------|
| B-Tree | 大（与表大小成正比） | O(log n) | 高基数、精确查询 |
| BRIN | 极小（固定大小，约1/100） | 顺序扫描+块过滤 | 时间范围查询、数据有序 |

**推荐BRIN索引**：

```sql
-- ==================================================
-- 2.1 业务明细表BRIN索引
-- ==================================================

-- 月度字段：数据按时间插入，自然有序
CREATE INDEX IF NOT EXISTS idx_规模明细_月度_brin
    ON business.规模明细 USING BRIN (月度);

-- 收入明细表（同理）
CREATE INDEX IF NOT EXISTS idx_收入明细_月度_brin
    ON business.收入明细 USING BRIN (月度);

-- ==================================================
-- 2.2 新表BRIN索引（customer schema）
-- ==================================================

-- 合约表：valid_from字段（时间序列）
CREATE INDEX IF NOT EXISTS idx_contract_valid_from_brin
    ON customer.customer_plan_contract USING BRIN (valid_from);

-- 快照表：snapshot_month字段（月度快照）
CREATE INDEX IF NOT EXISTS idx_snapshot_month_brin
    ON customer.fct_customer_business_monthly_status USING BRIN (snapshot_month);
```

**3. 部分索引（Conditional Index）**

```sql
-- ==================================================
-- 3.1 快照表部分索引（只索引战客）
-- ==================================================

-- 战客通常只占总客户的10-20%，部分索引节省空间
CREATE INDEX IF NOT EXISTS idx_snapshot_strategic_customers
    ON customer.fct_customer_business_monthly_status(snapshot_month, company_id)
    WHERE is_strategic = TRUE;

-- ==================================================
-- 3.2 合约表部分索引（只索引当前有效合约）
-- ==================================================

-- 已在表DDL中定义：idx_active_contracts
-- WHERE valid_to = '9999-12-31'
```

---

#### 3.3.4 索引优化检查清单

- [ ] **B-Tree索引**：确认高基数字段（company_id、计划代码）已建立索引
- [ ] **BRIN索引**：确认时间字段（月度、valid_from）已建立BRIN索引
- [ ] **部分索引**：确认战客和有效合约已建立部分索引
- [ ] **索引监控**：定期检查索引使用率（`pg_stat_user_indexes`）
- [ ] **冗余索引**：删除未使用的索引（`pg_stat_user_indexes.idx_scan = 0`）
- [ ] **分区阈值监控**：当单表>5GB时，评估是否需要分区

---

#### 3.3.5 查询性能优化建议

**1. 常见查询模式优化**

```sql
-- ❌ 低效查询：全表扫描
SELECT * FROM business.规模明细
WHERE 客户名称 LIKE '%某某%';

-- ✅ 高效查询：使用索引
SELECT * FROM business.规模明细
WHERE company_id = 'C001234'
  AND 月度 = '2025-10-01';
```

**2. 时间范围查询优化**

```sql
-- ❌ 未利用BRIN索引（无时间过滤）
SELECT * FROM business.规模明细
WHERE company_id = 'C001234';

-- ✅ 利用BRIN索引（时间范围过滤）
SELECT * FROM business.规模明细
WHERE company_id = 'C001234'
  AND 月度 >= '2025-01-01'
  AND 月度 < '2026-01-01';
```

**3. 覆盖索引优化**

```sql
-- 如果查询只需要company_id和期末资产规模，创建覆盖索引
CREATE INDEX idx_规模明细_月度公司资产
    ON business.规模明细(月度, company_id)
    INCLUDE (期末资产规模);
```

---

## 4. 维度设计关键决策

### 4.1 产品线 vs 业务类型

**数据事实验证**：

| 业务类型 | 产品线代码 | 产品线名称 | 记录数 | 占比 |
|---------|-----------|-----------|--------|------|
| 企年受托 | PL202 | 企年受托 | 50,290 | 70% |
| 企年投资 | PL201 | 企年投资 | 20,169 | 28% |
| 职年投资 | PL203 | 职年投资 | 208 | 0.3% |
| 职年受托 | PL204 | 职年受托 | 67 | 0.1% |

**核心发现**：
- 业务类型和产品线代码是**一对一映射关系**
- `business.规模明细.业务类型` = `mapping."产品线".产品线`（完全一致）
- 产品线代码（PL201-PL204）**唯一确定**了业务类型

**设计决策**：
- ❌ **不采用**：同时存储`business_type`和`product_line_code`（冗余设计）
- ✅ **采用**：仅使用产品线维度（`product_line_code` + `product_line_name`）
- ✅ **派生业务类型**：通过视图或`CASE WHEN`从产品线代码派生"受托/投资"

**优势**：
1. 消除冗余，符合数据规范化原则
2. 简化主键设计：`(snapshot_month, company_id, product_line_code)`
3. 业务类型可按需派生，不影响查询灵活性

---

### 4.2 业务类型派生规则

```sql
-- 从产品线代码派生业务类型
CASE
    WHEN product_line_code IN ('PL202', 'PL204') THEN '受托'
    WHEN product_line_code IN ('PL201', 'PL203') THEN '投资'
    ELSE '未知'
END as business_type

-- 映射关系
-- PL201 (企年投资) → 投资
-- PL202 (企年受托) → 受托
-- PL203 (职年投资) → 投资
-- PL204 (职年受托) → 受托
```

---

## 5. 数据治理与迁移计划

### Phase 1: 新表创建（Week 1）

1. **创建customer schema**：`CREATE SCHEMA customer;`
2. **创建合约表**：`customer.customer_plan_contract`
3. **创建快照表**：`customer.fct_customer_business_monthly_status`
4. **创建聚合视图**：`v_customer_business_monthly_status_by_type`（可选）
5. **建立外键**：确保数据清洗后再建立约束
6. **创建触发器**：`trg_sync_product_line_name`（可选，自动同步产品线名称）

---

### Phase 2: 历史数据回溯（Week 2）

1. **从Legacy MySQL同步**：
   - `enterprise.business_info` → `mapping."年金客户"`
   - `enterprise.biz_label` → 更新`年金客户标签`
   - `business.规模明细` → `business.规模明细`（已迁移）

2. **生成历史合约**：
   - 回溯过去12-24个月的`business.规模明细`
   - 为每个活跃的客户-计划-产品线组合生成合约记录
   - 同时填充`product_line_code`和`product_line_name`

3. **生成历史快照**：
   - 基于历史合约，生成过去12-24个月的月度快照
   - 关键逻辑：从`期末资产规模`倒推客户状态
   - 按产品线维度聚合，避免业务类型冗余

---

### Phase 3: ETL自动化（Week 3）

1. **部署新ETL任务**：
   - 每日：同步`mapping."年金客户"`更新
   - 每日：更新`customer.customer_plan_contract`
   - 每月：生成月度快照

2. **BI验证**：
   - Power BI连接新表或视图，与现有报表（基于`mapping."年金客户"`）进行核对
   - 重点核对：
     - 战客总资产是否一致？
     - 交叉客户（既受托又投资）的状态显示是否正确？
     - 按受托/投资分组的聚合数据是否正确？

---

### Phase 4: 切割上线（Week 4）

1. **将BI报表切换至新模型**：
   - 星型模型：`mapping."年金客户"`（维度）+ `mapping."产品线"`（维度）+ `customer.fct_customer_business_monthly_status`（事实表）
   - 或使用聚合视图：`v_customer_business_monthly_status_by_type`

2. **保留现有表**：
   - 不删除`mapping."年金客户"`，继续作为主数据表
   - 不删除`business.规模明细`，继续作为原始数据源
   - 标记旧表为`legacy_`前缀（如有需要）

---

## 6. 开发团队检查清单

- [ ] **DDL**：确认`customer` schema已创建，新表已建立
- [ ] **外键**：确认`company_id`、`年金计划号`和`产品线代码`的外键指向正确
- [ ] **数据同步**：确认Legacy MySQL到PostgreSQL的数据流正常
- [ ] **合约生成**：确认从`business.规模明细`生成合约的逻辑正确
- [ ] **快照生成**：确认月度快照的状态逻辑（`is_strategic`、`is_existing`等）与业务一致
- [ ] **产品线维度**：确认`product_line_code`和`product_line_name`正确填充
- [ ] **业务类型派生**：确认视图`v_customer_business_monthly_status_by_type`正确派生业务类型
- [ ] **B-Tree索引**：确认高基数字段（company_id、产品线代码）已建立索引
- [ ] **BRIN索引**：确认时间字段（月度、valid_from）已建立BRIN索引
- [ ] **部分索引**：确认战客索引已建立
- [ ] **索引监控**：定期检查索引使用率，删除未使用的索引
- [ ] **产品线同步**：确认产品线名称变更时同步脚本或触发器正常工作
- [ ] **BI验证**：确认Power BI模型关系正确，数据核对一致
- [ ] **集合计划**：确认多对多关系处理正确（一个客户→多个计划）
- [ ] **性能基准**：建立查询性能基准测试，监控慢查询
- [ ] **分区阈值**：监控单表大小，当>5GB时评估是否需要分区

---

## 7. 附录：关键SQL脚本

### 7.1 创建customer schema和新表

```sql
-- ==================================================
-- 1. 创建customer schema
-- ==================================================
CREATE SCHEMA IF NOT EXISTS customer;

-- ==================================================
-- 2. 创建合约表（customer.customer_plan_contract）
-- ==================================================
CREATE TABLE customer.customer_plan_contract (
    contract_id SERIAL PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    年金计划号 VARCHAR NOT NULL,

    -- 产品线维度（统一维度，包含业务类型信息）
    产品线代码 VARCHAR(20) NOT NULL,
    产品线名称 VARCHAR(50) NOT NULL,

    -- 状态与时间（SCD Type 2风格）
    状态 VARCHAR(20) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE DEFAULT '9999-12-31',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
        REFERENCES mapping."年金客户"(company_id),
    CONSTRAINT fk_contract_plan FOREIGN KEY (年金计划号)
        REFERENCES mapping."年金计划"(年金计划号),
    CONSTRAINT fk_contract_product_line FOREIGN KEY (产品线代码)
        REFERENCES mapping."产品线"(产品线代码),

    -- 复合唯一约束
    CONSTRAINT uq_active_contract UNIQUE (company_id, 年金计划号, 产品线代码, valid_to)
);

-- 索引
CREATE INDEX idx_active_contracts ON customer.customer_plan_contract(company_id, 年金计划号)
WHERE valid_to = '9999-12-31';
CREATE INDEX idx_contract_product_line ON customer.customer_plan_contract(产品线代码);
CREATE INDEX idx_contract_valid_from_brin
    ON customer.customer_plan_contract USING BRIN (valid_from);

-- ==================================================
-- 3. 创建快照表（customer.fct_customer_business_monthly_status）
-- ==================================================
CREATE TABLE customer.fct_customer_business_monthly_status (
    snapshot_month DATE NOT NULL,
    company_id VARCHAR NOT NULL,

    -- 产品线维度（统一维度，包含业务类型信息）
    product_line_code VARCHAR(20) NOT NULL,
    product_line_name VARCHAR(50) NOT NULL,

    -- 状态标签（历史固化）
    is_strategic BOOLEAN DEFAULT FALSE,
    is_existing BOOLEAN DEFAULT FALSE,
    is_new BOOLEAN DEFAULT FALSE,
    is_winning BOOLEAN DEFAULT FALSE,
    is_churned BOOLEAN DEFAULT FALSE,

    -- 度量值
    aum_balance DECIMAL(20,2) DEFAULT 0,
    plan_count INTEGER DEFAULT 0,

    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    PRIMARY KEY (snapshot_month, company_id, product_line_code),

    -- 外键约束
    CONSTRAINT fk_snapshot_company FOREIGN KEY (company_id)
        REFERENCES mapping."年金客户"(company_id),
    CONSTRAINT fk_snapshot_product_line FOREIGN KEY (product_line_code)
        REFERENCES mapping."产品线"(产品线代码)
);

-- 索引
CREATE INDEX idx_snapshot_product_line ON customer.fct_customer_business_monthly_status(product_line_code);
CREATE INDEX idx_snapshot_product_name ON customer.fct_customer_business_monthly_status(product_line_name);
CREATE INDEX idx_snapshot_month_product ON customer.fct_customer_business_monthly_status(snapshot_month, product_line_code);
CREATE INDEX idx_snapshot_strategic ON customer.fct_customer_business_monthly_status(snapshot_month, is_strategic);
CREATE INDEX idx_snapshot_company ON customer.fct_customer_business_monthly_status(company_id);
CREATE INDEX idx_snapshot_month_brin
    ON customer.fct_customer_business_monthly_status USING BRIN (snapshot_month);

-- 部分索引：只索引战客
CREATE INDEX idx_snapshot_strategic_customers
    ON customer.fct_customer_business_monthly_status(snapshot_month, company_id)
    WHERE is_strategic = TRUE;

-- ==================================================
-- 4. 创建业务类型聚合视图（可选，用于按受托/投资分组）
-- ==================================================
CREATE VIEW v_customer_business_monthly_status_by_type AS
SELECT
    snapshot_month,
    company_id,
    product_line_code,
    product_line_name,
    CASE
        WHEN product_line_code IN ('PL202', 'PL204') THEN '受托'
        WHEN product_line_code IN ('PL201', 'PL203') THEN '投资'
        ELSE '未知'
    END as business_type,
    is_strategic,
    is_existing,
    is_new,
    is_winning,
    is_churned,
    aum_balance,
    plan_count,
    updated_at
FROM customer.fct_customer_business_monthly_status;
```

---

### 7.2 性能优化索引脚本

```sql
-- ==================================================
-- 1. 业务明细表索引（business.规模明细）
-- ==================================================

-- B-Tree索引（高基数、精确查询）
CREATE INDEX IF NOT EXISTS idx_规模明细_company_id
    ON business.规模明细(company_id);
CREATE INDEX IF NOT EXISTS idx_规模明细_计划代码
    ON business.规模明细(计划代码);
CREATE INDEX IF NOT EXISTS idx_规模明细_月度_产品线代码
    ON business.规模明细(月度, 产品线代码);

-- BRIN索引（时间范围查询）
CREATE INDEX IF NOT EXISTS idx_规模明细_月度_brin
    ON business.规模明细 USING BRIN (月度);

-- ==================================================
-- 2. 收入明细表索引（business.收入明细）
-- ==================================================

CREATE INDEX IF NOT EXISTS idx_收入明细_company_id
    ON business.收入明细(company_id);
CREATE INDEX IF NOT EXISTS idx_收入明细_月度_产品线代码
    ON business.收入明细(月度, 产品线代码);
CREATE INDEX IF NOT EXISTS idx_收入明细_月度_brin
    ON business.收入明细 USING BRIN (月度);

-- ==================================================
-- 3. 索引监控查询
-- ==================================================

-- 查看索引使用率
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname IN ('business', 'customer', 'mapping')
ORDER BY idx_scan DESC;

-- 查找未使用的索引
SELECT
    schemaname || '.' || relname as table_name,
    indexrelname as index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname IN ('business', 'customer', 'mapping')
ORDER BY pg_relation_size(indexrelid) DESC;

-- 查看表大小
SELECT
    schemaname,
    relname,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||relname)) as table_size,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname IN ('business', 'customer', 'mapping')
ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC;
```

---

### 7.3 生成历史合约（示例）

```sql
-- ==================================================
-- 基于business.规模明细生成历史合约
-- ==================================================

INSERT INTO customer.customer_plan_contract (
    company_id,
    年金计划号,
    产品线代码,
    产品线名称,
    状态,
    valid_from,
    valid_to
)
SELECT DISTINCT ON (s.company_id, s.计划代码, s.产品线代码, s.月度)
    COALESCE(s.company_id, 'UNKNOWN') as company_id,
    s.计划代码 as 年金计划号,
    s.产品线代码,
    p.产品线 as 产品线名称,
    CASE
        WHEN s.期末资产规模 > 0 THEN '正常'
        ELSE '流失'
    END as 状态,
    DATE_TRUNC('month', s.月度) as valid_from,
    LAST_DAY(s.月度) as valid_to
FROM business.规模明细 s
LEFT JOIN mapping."产品线" p ON s.产品线代码 = p.产品线代码
WHERE s.company_id IS NOT NULL
  AND s.产品线代码 IS NOT NULL
  AND s.月度 >= '2023-01-01'  -- 回溯起始时间
ORDER BY s.company_id, s.计划代码, s.产品线代码, s.月度 DESC
ON CONFLICT (company_id, 年金计划号, 产品线代码, valid_to)
DO NOTHING;
```

---

### 7.4 产品线名称同步脚本

当`mapping."产品线".产品线`发生变更时，同步更新业务表：

```sql
-- ==================================================
-- 同步产品线名称到合约表
-- ==================================================
UPDATE customer.customer_plan_contract t
SET
    产品线名称 = p.产品线,
    updated_at = CURRENT_TIMESTAMP
FROM mapping."产品线" p
WHERE t.产品线代码 = p.产品线代码
  AND t.产品线名称 != p.产品线;  -- 仅更新名称不同的记录

-- ==================================================
-- 同步产品线名称到快照表
-- ==================================================
UPDATE customer.fct_customer_business_monthly_status t
SET
    product_line_name = p.产品线,
    updated_at = CURRENT_TIMESTAMP
FROM mapping."产品线" p
WHERE t.product_line_code = p.产品线代码
  AND t.product_line_name != p.产品线;  -- 仅更新名称不同的记录

-- ==================================================
-- 触发器（可选）：自动同步产品线名称变更
-- ==================================================
CREATE OR REPLACE FUNCTION sync_product_line_name()
RETURNS TRIGGER AS $$
BEGIN
    -- 同步到合约表
    UPDATE customer.customer_plan_contract
    SET
        产品线名称 = NEW.产品线,
        updated_at = CURRENT_TIMESTAMP
    WHERE 产品线代码 = NEW.产品线代码
      AND 产品线名称 != NEW.产品线;

    -- 同步到快照表
    UPDATE customer.fct_customer_business_monthly_status
    SET
        product_line_name = NEW.产品线,
        updated_at = CURRENT_TIMESTAMP
    WHERE product_line_code = NEW.产品线代码
      AND product_line_name != NEW.产品线;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_product_line_name
    AFTER UPDATE ON mapping."产品线"
    FOR EACH ROW
    WHEN (OLD.产品线 != NEW.产品线)
    EXECUTE FUNCTION sync_product_line_name();
```

---

**文档版本**：V3.2
**创建日期**：2026-01-08
**更新日期**：2026-01-08（维度设计修正：统一使用产品线维度）
**作者**：WorkDataHub开发团队
**基于**：实际数据库结构验证 + 产品线维度分析
