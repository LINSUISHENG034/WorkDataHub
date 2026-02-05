# customer.customer_plan_contract 业务规格说明书

> **版本**: v0.6
> **创建日期**: 2026-01-10
> **状态**: 待验证
> **关联文档**: [customer-identity-monthly-snapshot-implementation-v3.2-project-based.md](./customer-identity-monthly-snapshot-implementation-v3.2-project-based.md)

---

## 0. 快速理解：表格关系总览

> 本节用最简单的语言解释各表之间的关系，帮助团队成员快速理解。

### 0.1 一句话解释每张表

| 表 | 一句话解释 |
|----|-----------|
| **年金客户** | 客户名单（谁是我们的客户） |
| **年金计划** | 产品目录（我们有哪些计划可以卖） |
| **产品线** | 业务分类（企年受托/企年投资/职年受托/职年投资等） |
| **规模明细** | 每月账单（这个月客户有多少钱） |
| **当年中标** | 好消息名单（今年新签了谁） |
| **当年解约** | 坏消息名单（今年流失了谁） |
| **contract** | 签约记录（哪个客户买了哪个计划，是战客吗？是已客吗？） |
| **fct_status** | 月度报告（这个月的客户状态快照） |

### 0.2 表格关系图

```
【我们有什么】           【发生了什么】           【我们想知道的】

 客户名单  ─────┐
                │
 产品目录  ─────┼──→  每月账单  ──┐
                │                 │
 业务分类  ─────┘                 ├──→  签约记录  ──→  月度报告
                                  │     (谁买了什么)   (状态快照)
              好消息名单  ────────┤     (是否战客)
              (今年中标)          │     (是否已客)
                                  │
              坏消息名单  ────────┘
              (今年解约)
```

---

## 1. 表概述

### 1.1 设计目标

`customer.customer_plan_contract` 是客户-计划签约关系的操作层表（OLTP），用于记录客户与年金计划之间的合约关系及其状态变化。

**核心功能**：
- 记录客户在不同产品线下的签约关系
- 支持 SCD Type 2（缓慢变化维度）历史追溯
- 为下游 `fct_customer_business_monthly_status` 快照表提供数据源

### 1.2 表定位

```
┌─────────────────────────────────────────────────────────────────┐
│                     数据分层架构                                  │
├─────────────────────────────────────────────────────────────────┤
│  [基础层 - 维度表]                                               │
│  customer."年金客户" / mapping."年金计划" / mapping."产品线"      │
│                          │                                       │
│                          ▼                                       │
│  [操作层 - OLTP] ◄────── customer.customer_plan_contract         │
│                          │                                       │
│                          ▼                                       │
│  [分析层 - OLAP]         customer.fct_customer_business_monthly_status │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 表结构定义

### 2.1 DDL（推荐方案）

```sql
CREATE TABLE customer.customer_plan_contract (
    -- 主键
    contract_id SERIAL PRIMARY KEY,

    -- 业务维度（复合业务键）
    company_id VARCHAR NOT NULL,                    -- 客户ID
    plan_code VARCHAR NOT NULL,                     -- 计划代码
    product_line_code VARCHAR(20) NOT NULL,         -- 产品线代码：PL201/PL202/PL203/PL204等

    -- 冗余字段（便于查询）
    product_line_name VARCHAR(50) NOT NULL,         -- 产品线名称：企年受托、企年投资等
    customer_name VARCHAR(200),                     -- 客户名称（冗余，自动同步）
    plan_name VARCHAR(200),                         -- 计划全称（冗余，自动同步）

    -- 年度初始化状态（每年1月更新）
    is_strategic BOOLEAN DEFAULT FALSE,             -- 是否战客
    is_existing BOOLEAN DEFAULT FALSE,              -- 是否已客（FALSE=新客）
    status_year INTEGER NOT NULL,                   -- 状态所属年度（如2026）

    -- 月度更新状态
    contract_status VARCHAR(20) NOT NULL,           -- 合约状态：正常/停缴

    -- SCD Type 2 时间维度（精确到日，使用月末最后一日）
    valid_from DATE NOT NULL,                       -- 生效日期
    valid_to DATE DEFAULT '9999-12-31',             -- 失效日期

    -- 审计字段
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_contract_company FOREIGN KEY (company_id)
        REFERENCES customer."年金客户"(company_id),
    CONSTRAINT fk_contract_product_line FOREIGN KEY (product_line_code)
        REFERENCES mapping."产品线"(产品线代码),

    -- 复合唯一约束（业务键 + 时间）
    CONSTRAINT uq_active_contract UNIQUE (company_id, plan_code, product_line_code, valid_to)
);

-- 索引
CREATE INDEX idx_contract_company ON customer.customer_plan_contract(company_id);
CREATE INDEX idx_contract_plan ON customer.customer_plan_contract(plan_code);
CREATE INDEX idx_contract_product_line ON customer.customer_plan_contract(product_line_code);
CREATE INDEX idx_contract_strategic ON customer.customer_plan_contract(is_strategic) WHERE is_strategic = TRUE;
CREATE INDEX idx_contract_status_year ON customer.customer_plan_contract(status_year);
CREATE INDEX idx_active_contracts ON customer.customer_plan_contract(company_id, plan_code, product_line_code)
    WHERE valid_to = '9999-12-31';
CREATE INDEX idx_contract_valid_from_brin ON customer.customer_plan_contract USING BRIN (valid_from);
CREATE INDEX idx_contract_customer_name ON customer.customer_plan_contract(customer_name);
CREATE INDEX idx_contract_plan_name ON customer.customer_plan_contract(plan_name);
```

### 2.2 字段说明

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| `contract_id` | SERIAL | 自增主键 | 系统生成 |
| `company_id` | VARCHAR | 客户唯一标识 | `business.规模明细.company_id` |
| `plan_code` | VARCHAR | 计划代码 | `business.规模明细.计划代码` |
| `product_line_code` | VARCHAR(20) | 产品线代码（PL201-PL204） | `mapping."产品线".产品线代码` |
| `product_line_name` | VARCHAR(50) | 产品线名称（冗余） | `mapping."产品线".产品线` |
| `customer_name` | VARCHAR(200) | 客户名称（冗余，自动同步） | `customer."年金客户".客户名称` |
| `plan_name` | VARCHAR(200) | 计划全称（冗余，自动同步） | `mapping."年金计划".计划全称` |
| `is_strategic` | BOOLEAN | 是否战客 | 规模汇总 + 白名单 |
| `is_existing` | BOOLEAN | 是否已客（FALSE=新客） | 上年末规模汇总 |
| `status_year` | INTEGER | 状态所属年度 | 系统计算 |
| `contract_status` | VARCHAR(20) | 合约状态（正常/停缴） | 规模明细计算 |
| `valid_from` | DATE | 生效日期（月末最后一日） | `business.规模明细.月度` |
| `valid_to` | DATE | 失效日期（9999-12-31=当前有效） | 业务逻辑计算 |

### 2.3 业务键说明

**复合业务键**: `(company_id, plan_code, product_line_code)`

**业务含义**：
- 同一客户（`company_id`）可以有多个年金计划（`plan_code`）
- 同一年金计划可以有不同的产品线（`product_line_code`：PL201/PL202等）
- 例如：客户A的计划001可能同时有PL202(企年受托)和PL201(企年投资)两条记录

**产品线映射**：

| product_line_code | product_line_name | 管理资格 |
|-------------------|-------------------|----------|
| PL201 | 企年投资 | 投资管理人 |
| PL202 | 企年受托 | 受托人 |
| PL203 | 职年投资 | 投资管理人 |
| PL204 | 职年受托 | 受托人 |

---

## 3. 外键依赖关系

### 3.1 依赖表清单

| 依赖表 | 关联字段 | 记录数 | 说明 |
|--------|----------|--------|------|
| `customer."年金客户"` | `company_id` | ~10,436 | 客户主数据 |
| `mapping."年金计划"` | `年金计划号` | ~1,158 | 计划维度 |
| `mapping."产品线"` | `产品线代码` | 4 (PL201-PL204) | 产品线维度 |

### 3.2 数据源表

| 数据源表 | 用途 | 记录数 |
|----------|------|--------|
| `business.规模明细` | 主要数据源，提供合约关系和规模数据 | ~70,734 (PostgreSQL) |
| `当年中标` (待建) | 中标状态关联 | - |
| `当年解约` (待建) | 解约状态关联 | - |

### 3.3 数据完整性规则

1. **company_id 缺失处理**：不记录 `company_id` 为空的数据
2. **外键校验**：插入前需确保 `company_id` 存在于 `customer."年金客户"`
3. **产品线代码校验**：仅接受 PL201-PL204

---

## 4. 状态定义（待决策）

> [!WARNING]
> 本节内容存在设计问题，需要重新明确状态定义及其归属表。

### 4.1 原始状态定义

V3.2文档原定义的状态枚举：

| 状态 | 原始定义 | 判断逻辑 |
|------|----------|----------|
| 正常 | 合约有效 | `期末资产规模 > 0` |
| 流失 | 合约终止 | `期末资产规模 = 0` |
| 停缴 | 停止供款 | 未定义 |
| 新中标 | 新签约 | 未定义 |
| 新到账 | 新到账 | 未定义 |

### 4.2 修正后的状态定义

根据业务实际，状态定义修正如下：

| 状态 | 修正名称 | 判断逻辑 | 重置周期 | 数据来源 |
|------|----------|----------|----------|----------|
| 正常 | 正常 | `期末资产规模 > 0` 且 `过去12个月供款 > 0` | 无 | `business.规模明细` |
| 停缴 | 停缴 | `期末资产规模 > 0` 且 `过去12个月供款 = 0` | 无 | `business.规模明细` |
| 流失 | **当年解约** | 与`当年解约`domain关联 | **年度重置** | `当年解约`表 (待建) |
| 新中标 | **当年中标** | 与`当年中标`domain关联 | **年度重置** | `当年中标`表 (待建) |
| 新到账 | 新到账 | 上年无记录，本年新增 | **年度重置** | `business.规模明细` |

### 4.3 状态判断逻辑详解

#### 4.3.1 正常

```sql
-- 正常：期末资产规模 > 0 且 过去12个月有供款
SELECT company_id, 计划代码, 产品线代码
FROM business.规模明细
WHERE 期末资产规模 > 0
  AND EXISTS (
      SELECT 1 FROM business.规模明细 s2
      WHERE s2.company_id = business.规模明细.company_id
        AND s2.计划代码 = business.规模明细.计划代码
        AND s2.产品线代码 = business.规模明细.产品线代码
        AND s2.月度 >= (当前月度 - INTERVAL '12 months')
        AND s2.供款 > 0
  )
```

#### 4.3.2 停缴

```sql
-- 停缴：期末资产规模 > 0 且 过去12个月无供款
SELECT company_id, 计划代码, 产品线代码
FROM business.规模明细
WHERE 期末资产规模 > 0
  AND NOT EXISTS (
      SELECT 1 FROM business.规模明细 s2
      WHERE s2.company_id = business.规模明细.company_id
        AND s2.计划代码 = business.规模明细.计划代码
        AND s2.产品线代码 = business.规模明细.产品线代码
        AND s2.月度 >= (当前月度 - INTERVAL '12 months')
        AND s2.供款 > 0
  )
```

#### 4.3.3 当年解约

```sql
-- 当年解约：与"当年解约"domain关联
-- 关联字段：company_id + 计划代码 + 产品线代码
SELECT c.company_id, c.年金计划号, c.产品线代码
FROM customer.customer_plan_contract c
INNER JOIN 当年解约 d ON
    c.company_id = d.company_id
    AND c.年金计划号 = d.plan_code
    AND c.产品线代码 = d.product_line_code
WHERE EXTRACT(YEAR FROM d.解约日期) = EXTRACT(YEAR FROM CURRENT_DATE)
```

#### 4.3.4 当年中标

```sql
-- 当年中标：与"当年中标"domain关联
-- 关联字段：company_id + 计划代码 + 产品线代码
SELECT c.company_id, c.年金计划号, c.产品线代码
FROM customer.customer_plan_contract c
INNER JOIN 当年中标 d ON
    c.company_id = d.company_id
    AND c.年金计划号 = d.plan_code
    AND c.产品线代码 = d.product_line_code
WHERE EXTRACT(YEAR FROM d.中标日期) = EXTRACT(YEAR FROM CURRENT_DATE)
```

#### 4.3.5 新到账

```sql
-- 新到账：上年无记录，本年新增
SELECT company_id, 计划代码, 产品线代码
FROM business.规模明细 curr
WHERE EXTRACT(YEAR FROM curr.月度) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND NOT EXISTS (
      SELECT 1 FROM business.规模明细 prev
      WHERE prev.company_id = curr.company_id
        AND prev.计划代码 = curr.计划代码
        AND prev.产品线代码 = curr.产品线代码
        AND EXTRACT(YEAR FROM prev.月度) = EXTRACT(YEAR FROM CURRENT_DATE) - 1
  )
```

### 4.4 状态归属设计（推荐方案）

> [!NOTE]
> 基于业务实际，采用**分层存储**设计，明确两张表的职责分工。

#### 4.4.1 业务主键定义

**统一业务主键**：`company_id + plan_code + product_line_code`

| 字段 | 说明 | 来源 |
|------|------|------|
| `company_id` | 客户ID | `business.规模明细.company_id` |
| `plan_code` | 计划代码 | `business.规模明细.计划代码` |
| `product_line_code` | 产品线代码 | `mapping."产品线".产品线代码` |

#### 4.4.2 状态分层设计（推荐）

| 表 | 存储状态 | 更新频率 | 数据来源 |
|---|----------|----------|----------|
| `customer_plan_contract` | is_strategic, is_existing, contract_status | 年度初始化 + 月度更新 | 规模明细、白名单 |
| `fct_customer_business_monthly_status` | is_winning_this_year, is_churned_this_year | 月度滚动 | 中标名单、解约名单 |

**设计理由**：

| 状态 | 归属表 | 理由 |
|------|--------|------|
| **is_strategic** (战客) | `customer_plan_contract` | 年度初始化，基于上年末规模或白名单，变化频率低 |
| **is_existing** (已客) | `customer_plan_contract` | 年度初始化，基于上年末是否有资产，变化频率低 |
| **contract_status** (正常/停缴) | `customer_plan_contract` | 持续性状态，基于规模明细计算 |
| **is_winning_this_year** (当年中标) | `fct_...monthly_status` | 事件性状态，月度滚动更新，需要快照固化 |
| **is_churned_this_year** (当年解约) | `fct_...monthly_status` | 事件性状态，月度滚动更新，需要快照固化 |

#### 4.4.3 状态判定逻辑汇总

**is_strategic (是否战客)**：
```
判定时机：年度初始化（每年1月）
数据来源：
  1. 上年度末资产规模汇总（business.规模明细）
  2. 战客白名单（手工维护）
判定规则：
  - 上年末资产规模 >= 阈值 → 战客
  - 在白名单中 → 战客
  - 其他 → 非战客
```

**is_existing (是否已客)**：
```
判定时机：年度初始化（每年1月）
数据来源：上年度末资产规模汇总（business.规模明细）
判定规则：
  - 上年末有资产（规模 > 0）→ 已客
  - 上年末无资产 → 新客
```

**contract_status (合约状态)**：
```
判定时机：月度更新
数据来源：business.规模明细
判定规则：
  - 期末资产规模 > 0 且 过去12个月有供款 → 正常
  - 期末资产规模 > 0 且 过去12个月无供款 → 停缴
  - 期末资产规模 = 0 → 无效（不记录或标记）
```

**is_winning_this_year (当年中标)**：
```
判定时机：月度滚动更新
数据来源：当年中标名单（每月收集）
判定规则：
  - 在当年中标名单中 → TRUE
  - 年度重置（每年1月清零）
```

**is_churned_this_year (当年解约)**：
```
判定时机：月度滚动更新
数据来源：当年解约名单（每月收集）
判定规则：
  - 在当年解约名单中 → TRUE
  - 年度重置（每年1月清零）
```

---

## 5. 数据更新逻辑

### 5.1 更新触发时机

| 触发方式 | 说明 | 频率 |
|----------|------|------|
| Post-ETL Hook | `business.规模明细` ETL完成后自动触发 | 月度 |
| 手动触发 | `customer-mdm sync` CLI命令 | 按需 |

### 5.2 更新策略（待状态定义明确后确定）

> [!NOTE]
> 更新策略依赖于状态定义的最终决策。以下为初步设计。

**全量刷新 vs 增量更新**：

| 策略 | 适用场景 | 复杂度 |
|------|----------|--------|
| 全量刷新 | 状态定义简单，数据量小 | 低 |
| 增量更新 | 状态定义复杂，需要保留历史 | 高 |

### 5.3 SCD Type 2 实现逻辑

当客户状态发生变化时：

```sql
-- Step 1: 关闭旧记录
UPDATE customer.customer_plan_contract
SET valid_to = :snapshot_date - INTERVAL '1 day',
    updated_at = CURRENT_TIMESTAMP
WHERE company_id = :company_id
  AND 年金计划号 = :plan_code
  AND 产品线代码 = :product_line_code
  AND valid_to = '9999-12-31';

-- Step 2: 插入新记录
INSERT INTO customer.customer_plan_contract (
    company_id, 年金计划号, 产品线代码, 产品线名称,
    状态, valid_from, valid_to
) VALUES (
    :company_id, :plan_code, :product_line_code, :product_line_name,
    :new_status, :snapshot_date, '9999-12-31'
);
```

#### 5.3.1 状态变化检测字段 (Story 7.6-12)

以下字段的变化会触发版本创建：

| 字段 | 说明 | 变化示例 |
|------|------|----------|
| `contract_status` | 合约状态 | 正常 ↔ 停缴 |
| `is_strategic` | 战客状态 | FALSE → TRUE |
| `is_existing` | 已客状态 | FALSE → TRUE |

**检测逻辑**：
```python
def has_status_changed(old: Record, new: Record) -> bool:
    """检测是否需要创建新版本。"""
    return (
        old.contract_status != new.contract_status or
        old.is_strategic != new.is_strategic or
        old.is_existing != new.is_existing
    )
```

#### 5.3.2 实现参考

生产实现详见 `src/work_data_hub/customer_mdm/contract_sync.py`：
- `_build_close_old_records_sql()`: 关闭状态已变化的旧记录
- `_build_sync_sql()`: 插入新/变化的记录
- `has_status_changed()`: 状态变化检测函数

### 5.4 日期格式化规则

| 场景 | 日期格式 | 示例 |
|------|----------|------|
| `valid_from` | 月末最后一日 | 2026-01-31 |
| `valid_to` | 月末最后一日（或9999-12-31） | 2026-02-28 |
| `snapshot_date` | 月末最后一日 | 2026-01-31 |

---

## 6. 待决策事项汇总

| # | 决策项 | 状态 | 说明 |
|---|--------|------|------|
| D1 | 状态归属表 | ✅ 已决策 | 采用分层存储：contract存储战客/已客/正常/停缴，snapshot存储中标/解约 |
| D2 | 业务主键 | ✅ 已决策 | `company_id + plan_code + product_line_code` |
| D3 | 战客判定阈值 | ✅ 已决策 | 5亿元，配置于`config/customer_mdm.yaml` |
| D4 | 战客白名单生成 | ✅ 已决策 | 各机构前10大客户，基于上年12月规模明细 |
| D5 | 当年中标名单表结构 | ✅ 已决策 | 详见附录8.1 |
| D6 | 当年解约名单表结构 | ✅ 已决策 | 详见附录8.2 |
| D7 | 更新策略 | ✅ 已决策 | 年度初始化 + 月度增量更新 |

---

## 7. 附录

### 7.1 相关文档

| 文档 | 路径 |
|------|------|
| V3.2实施方案 | `docs/specific/customer-db-refactor/customer-identity-monthly-snapshot-implementation-v3.2-project-based.md` |
| Sprint变更提案 | `docs/project-planning-artifacts/sprint-change-proposal-2026-01-10.md` |

### 7.2 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v0.1 | 2026-01-10 | 初稿，整合V3.2文档与业务补充信息 |
| v0.2 | 2026-01-10 | 根据业务反馈更新：采用分层存储设计，明确业务主键 |
| v0.3 | 2026-01-10 | 补充战客阈值、白名单生成逻辑、中标/解约名单表结构 |
| v0.4 | 2026-01-11 | 新增第0节"快速理解"，用简单语言解释表格关系 |
| v0.5 | 2026-01-11 | 修正business_type定义：直接取自产品线名称，非派生值 |
| v0.6 | 2026-01-11 | 业务主键改用product_line_code，统一英文键名 |

---

## 8. 数据源表结构详解

### 8.1 当年中标名单表结构

**数据源**：`【导入模板】台账登记.xlsx`

#### 8.1.1 企年受托中标

| 字段 | 类型 | 说明 | 是否必填 |
|------|------|------|----------|
| 区域 | VARCHAR | 战区 | 是 |
| 年金中心 | VARCHAR | 年金中心 | 是 |
| 机构 | VARCHAR | 机构名称 | 是 |
| 业务类型 | VARCHAR | 固定值"受托" | 是 |
| 客户类型 | VARCHAR | 空白/已客等 | 是 |
| 客户全称 | VARCHAR | 客户名称 | 是 |
| 受托人 | VARCHAR | 受托人名称 | 否 |
| 计划规模 | NUMERIC | 计划规模（亿元） | 否 |
| 年缴规模 | NUMERIC | 年缴规模（亿元） | 否 |
| 计划类型 | VARCHAR | 单一/集合 | 否 |
| **中标日期** | DATE | 中标日期 | **是** |
| 证明材料 | VARCHAR | 合同/中标函等 | 否 |
| 上报月份 | VARCHAR | 上报月份（如202402） | 是 |
| 上报人 | VARCHAR | 上报人 | 否 |
| 考核有效 | INTEGER | 0/1 | 否 |
| **年金计划号** | VARCHAR | 计划代码 | **是** |
| **company_id** | VARCHAR | 客户ID | **是** |
| 备注 | TEXT | 备注 | 否 |

#### 8.1.2 企年投资中标

| 字段 | 类型 | 说明 | 是否必填 |
|------|------|------|----------|
| 区域 | VARCHAR | 战区 | 是 |
| 年金中心 | VARCHAR | 年金中心 | 是 |
| 机构 | VARCHAR | 机构名称 | 是 |
| 业务类型 | VARCHAR | 固定值"投资" | 是 |
| 客户类型 | VARCHAR | 空白/已客等 | 是 |
| 客户全称 | VARCHAR | 客户名称 | 是 |
| 受托人 | VARCHAR | 受托人名称 | 否 |
| 计划规模 | NUMERIC | 计划规模（亿元） | 否 |
| 年缴规模 | NUMERIC | 年缴规模（亿元） | 否 |
| 计划类型 | VARCHAR | 单一/集合 | 否 |
| **中标日期** | DATE | 中标日期 | **是** |
| 证明材料 | VARCHAR | 合同/中标函等 | 否 |
| 战区前五大 | INTEGER | 0/1 | 否 |
| 中心前十大 | INTEGER | 0/1 | 否 |
| 机构前十大 | INTEGER | 0/1 | 否 |
| 五亿以上 | INTEGER | 0/1 | 否 |
| 上报月份 | VARCHAR | 上报月份 | 是 |
| 上报人 | VARCHAR | 上报人 | 否 |
| 考核有效 | INTEGER | 0/1 | 否 |
| **年金计划号** | VARCHAR | 计划代码 | **是** |
| **company_id** | VARCHAR | 客户ID | **是** |
| 备注 | TEXT | 备注 | 否 |

### 8.2 当年解约名单表结构

**数据源**：`【导入模板】台账登记.xlsx`

#### 8.2.1 企年受托流失(解约)

| 字段 | 类型 | 说明 | 是否必填 |
|------|------|------|----------|
| 区域 | VARCHAR | 战区 | 是 |
| 年金中心 | VARCHAR | 年金中心 | 是 |
| 机构 | VARCHAR | 机构名称 | 是 |
| 业务类型 | VARCHAR | 固定值"受托" | 是 |
| 客户类型 | VARCHAR | 客户类型 | 是 |
| 客户全称 | VARCHAR | 客户名称 | 是 |
| 受托人 | VARCHAR | 受托人名称 | 否 |
| 计划规模 | NUMERIC | 计划规模（亿元） | 否 |
| 年缴规模 | NUMERIC | 年缴规模（亿元） | 否 |
| 计划类型 | VARCHAR | 单一/集合 | 否 |
| **流失日期** | DATE | 解约日期 | **是** |
| 证明材料 | VARCHAR | 证明材料 | 否 |
| 上报月份 | VARCHAR | 上报月份 | 是 |
| 上报人 | VARCHAR | 上报人 | 否 |
| 考核有效 | INTEGER | 0/1 | 否 |
| **年金计划号** | VARCHAR | 计划代码 | **是** |
| **company_id** | VARCHAR | 客户ID | **是** |
| 备注 | TEXT | 备注 | 否 |

#### 8.2.2 企年投资流失(解约)

| 字段 | 类型 | 说明 | 是否必填 |
|------|------|------|----------|
| 区域 | VARCHAR | 战区 | 是 |
| 年金中心 | VARCHAR | 年金中心 | 是 |
| 机构 | VARCHAR | 机构名称 | 是 |
| 业务类型 | VARCHAR | 固定值"投资" | 是 |
| 客户类型 | VARCHAR | 客户类型 | 是 |
| 客户全称 | VARCHAR | 客户名称 | 是 |
| 受托人 | VARCHAR | 受托人名称 | 否 |
| 计划规模 | NUMERIC | 计划规模（亿元） | 否 |
| 年缴规模 | NUMERIC | 年缴规模（亿元） | 否 |
| 计划类型 | VARCHAR | 单一/集合 | 否 |
| **流失日期** | DATE | 解约日期 | **是** |
| 证明材料 | VARCHAR | 证明材料 | 否 |
| 战区前五大 | INTEGER | 0/1 | 否 |
| 中心前十大 | INTEGER | 0/1 | 否 |
| 机构前十大 | INTEGER | 0/1 | 否 |
| 五亿以上 | INTEGER | 0/1 | 否 |
| 上报月份 | VARCHAR | 上报月份 | 是 |
| **年金计划号** | VARCHAR | 计划代码 | **是** |
| **company_id** | VARCHAR | 客户ID | **是** |
| 考核有效 | INTEGER | 0/1 | 否 |
| 上报人 | VARCHAR | 上报人 | 否 |
| 备注 | TEXT | 备注 | 否 |

---

### 8.3 战客白名单生成逻辑

**数据源**：`business.规模明细`（上年12月数据）

**生成规则**：各机构前10大客户（按期末资产规模排序）

```sql
-- 战客白名单生成SQL
WITH ranked_customers AS (
    SELECT
        company_id,
        计划代码 as plan_code,
        产品线代码 as product_line_code,
        机构代码,
        机构名称,
        SUM(期末资产规模) as total_aum,
        ROW_NUMBER() OVER (
            PARTITION BY 机构代码, 产品线代码
            ORDER BY SUM(期末资产规模) DESC
        ) as rank_in_branch
    FROM business.规模明细
    WHERE 月度 = (
        SELECT MAX(月度) FROM business.规模明细
        WHERE EXTRACT(MONTH FROM 月度) = 12
    )
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码, 机构代码, 机构名称
)
SELECT company_id, plan_code, product_line_code, 机构代码, 机构名称, total_aum
FROM ranked_customers
WHERE rank_in_branch <= 10;
```

---

### 8.4 配置参数

**配置文件路径**：`config/customer_mdm.yaml`

```yaml
# Customer MDM Configuration
customer_mdm:
  # 战客判定阈值（单位：元）
  strategic_threshold: 500000000  # 5亿元

  # 战客白名单：各机构前N大客户
  whitelist_top_n: 10

  # 状态年度（用于年度初始化）
  status_year: 2026
```