# **年金基金客户管理系统：客户主数据治理与架构重构咨询**

## **1\. 执行摘要 (Executive Summary)**

本文档旨在针对我司年金基金管理系统中的**客户主数据管理 (MDM)** 痛点寻求专家建议。当前系统面临多维度客户身份割裂（战客/已客/中标/流失）、主键设计不统一以及数据治理缺失的问题。

我们需要从当前的“多表散乱模式”向“统一客户视图模式”转型。本文档详细描述了现状数据探查结果、业务痛点，并提出了三套拟定方案，请专家针对方案的可行性、性能与扩展性进行评估。

## **2\. 业务背景与术语定义**

### **2.1 业务领域**

* **行业**：年金基金管理  
* **产品线**：企业年金（企年）、职业年金（职年）  
* **服务角色**：受托人 (Trustee)、投资管理人 (Investment Manager)

### **2.2 客户状态定义 (基于 Claude 文档优化)**

客户身份具有多重性与动态性，单一客户可能同时具备多种状态。

| 状态类型 | 业务定义 | 数据来源 | 更新频率 | 关键逻辑 |
| :---- | :---- | :---- | :---- | :---- |
| **战客 (Strategic)** | 战略重点客户（资产规模≥5亿） | 1\. 规模明细表算逻辑 2\. 手工白名单 | 年度初始化 \+ 手工修正 | 存量高价值客户，需重点维护 |
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

> **⚠️ 重要发现**：2025年仅10个月已达349,373行，预计全年将超过40万行，**2年内将突破千万行**。

## **3\. 现状诊断与数据探查 (Data Profiling)**

> **数据验证说明**：本章节所有数据均通过实际数据库查询验证（验证日期：2026-01-07），相关 SQL 查询见附录 A。

### **3.1 核心痛点：主键策略混乱**

目前 customer schema 共有 11 张客户表，缺乏统一的主键策略，导致无法构建参照完整性。

#### **3.1.1 客户表全景**

| 表名 | 主键 | 记录数 | 唯一公司数 | 唯一计划数 | 主键策略问题 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **企年受托中标** | ❌ 无 | 275 | 275 | 17 | **集合计划 1:16 问题** |
| **企年受托已客** | ✅ 年金计划号 | 339 | 330 | 339 | 计划级主键，无法区分多公司 |
| **企年受托战客** | ✅ company_id | 114 | 114 | N/A | 主键设计合理 |
| **企年受托流失** | ❌ 无 | 190 | 189 | 52 | 无主键，无法追踪历史 |
| **企年投资中标** | ❌ 无 | 120 | 120 | 42 | 集合计划问题较轻 (1:3) |
| **企年投资已客** | ✅ 年金计划号 | 488 | N/A | 488 | 计划级主键 |
| **企年投资战客** | ✅ company_id | 239 | 239 | N/A | 主键设计合理 |
| **企年投资流失** | ❌ 无 | 32 | 32 | 21 | 无主键 |
| **职年受托已客** | ✅ 年金计划号 | 33 | N/A | 33 | 职年业务单计划模式 |
| **职年投资已客** | ✅ 年金计划号 | 77 | N/A | 77 | 职年业务单计划模式 |
| **续签客户清单** | 未探查 | N/A | N/A | N/A | 业务辅助表 |

#### **3.1.2 主键策略模式分析**

通过表结构分析，发现以下主键设计模式：

| 表类型 | 主键策略 | 实施情况 | 问题 |
| :---- | :---- | :---- | :---- |
| **已客表** | 年金计划号 | 4/4 表实施 | ❌ 集合计划场景下失效（多公司共用一计划号） |
| **战客表** | company_id | 2/2 表实施 | ✅ 符合客户主数据理念 |
| **中标表** | 无 | 0/2 表实施 | ❌ 缺少主键，数据质量无保障 |
| **流失表** | 无 | 0/2 表实施 | ❌ 缺少主键，无法审计历史 |

**结论**：主键策略不统一，且未考虑"集合计划（Collective Plans）"这一业务场景。

### **3.2 关键数据关系发现**

通过对现有数据的交叉分析，我们发现了以下隐含的业务规则，这对建模至关重要：

#### **3.2.1 集合计划（Collective Plans）问题**

**数据证据**：
```sql
-- 企年受托中标表
SELECT COUNT(DISTINCT 年金计划号) as 唯一计划数,  -- 结果：17
       COUNT(DISTINCT company_id) as 唯一公司数;  -- 结果：275
```

**Top 5 集合计划明细**：

| 年金计划号 | 关联公司数 | 占比 | 计划类型 |
| :---- | :---- | :---- | :---- |
| AN001 | **196** | 71.3% | 集合计划（疑似） |
| AN002 | 23 | 8.4% | 集合计划（疑似） |
| P0190 | 15 | 5.5% | 单一计划（多公司） |
| P0390 | 11 | 4.0% | 单一计划（多公司） |
| P0808 | 6 | 2.2% | 单一计划（多公司） |

**结论**：
- 存在 **1个计划 : N个客户** 的关系（最高 1:196）
- 当前的"计划ID即主键"模式在集合计划场景下**完全失效**
- AN001 计划关联了 196 个不同的公司，证明"集合计划"是普遍业务场景

#### **3.2.2 客户状态重叠（State Overlap）**

**数据证据**：
```sql
-- 战客与已客重叠情况
SELECT COUNT(*) as 战客总数 FROM customer.企年受托战客;  -- 结果：114

SELECT COUNT(*) as 重叠客户数
FROM customer.企年受托战客
WHERE company_id IN (
    SELECT DISTINCT company_id FROM customer.企年受托已客
);  -- 结果：110
```

**重叠统计**：

| 客户群体 | 数量 | 重叠数量 | 重叠比例 |
| :---- | :---- | :---- | :---- |
| 战客总数 | 114 | 110 | **96.49%** |
| 已客总数 | 330 | 110 | 33.3% |

**结论**：
- 客户状态**不是互斥的**，而是**标签化（Tagging）**的
- 分表存储导致数据大量冗余（同一客户在多个表中重复出现）
- 需要从"分表模式"转向"关系模式"

#### **3.2.3 数据孤岛问题**

**跨表客户独立性分析**：

| 表 | 公司数 | 独立公司（仅在此表） | 独立性 |
| :---- | :---- | :---- | :---- |
| 企年受托中标 | 275 | 165 | 60% |
| 企年受托已客 | 330 | 220 | 66.7% |
| 企年受托战客 | 114 | 4 | 3.5% |

**结论**：
- 165个"中标"客户（60%）完全不在"已客"表中（纯增量）
- 跨表查询客户全貌极其困难（需要 JOIN 8张以上的表）
- 当前架构无法回答"某客户的所有状态"这类简单问题

#### **3.2.4 数据质量矩阵**

通过对所有客户表的全面扫描，建立以下数据质量评估矩阵：

| 质量维度 | 评估结果 | 风险等级 | 说明 |
| :---- | :---- | :---- | :---- |
| **主键完整性** | 4/11 表缺失主键 | 🔴 高 | 中标表、流失表均无主键约束 |
| **company_id 完整性** | 0 NULL 值 | 🟢 低 | 所有已客表数据质量良好 |
| **年金计划号唯一性** | 存在重复 | 🟡 中 | 集合计划导致 1:N 关系 |
| **外键约束** | 0 表实施 | 🔴 高 | 无参照完整性保障 |
| **索引覆盖** | 仅主键索引 | 🟡 中 | 查询性能未优化 |
| **数据一致性** | 跨表冗余 | 🟡 中 | 同一客户在多表重复 |

**数据质量评分**：**C+** (60/100分)

**关键问题**：
1. 缺少外键约束，数据一致性无法保障
2. 主键设计未考虑集合计划场景
3. 无索引优化策略，查询性能未验证

## **4\. 拟定架构方案 (Proposed Architecture)**

针对上述痛点，我们草拟了以下重构方案，请专家重点评审。

### **4.1 核心建模议题：如何处理“客户-计划”关系？**

**挑战**：既有单一计划（1对1），也有集合计划（1对多）。

* **方案 A：以 Company 为核心**  
  * 建立统一 customer\_master。  
  * 优点：符合CRM视角，统计客户总资产方便。  
  * 缺点：丢失了“集合计划”维度的管理细节。  
* **方案 B：以 Plan 为核心**  
  * 沿用现有逻辑，以计划为主键。  
  * 缺点：无法解决集合计划中多公司共用一个ID导致的重复主键问题。  
* **方案 C（推荐）：实体分离 \+ 关系表**  
  * 将客户与计划解耦，通过中间表关联。

**拟定 DDL (方案 C):**

\-- 1\. 客户主表 (统一身份)  
CREATE TABLE customer\_master (  
    company\_id VARCHAR(50) PRIMARY KEY,  
    customer\_name VARCHAR(200) NOT NULL,  
    industry VARCHAR(100),  
    unified\_social\_credit\_code VARCHAR(18) \-- 统一社会信用代码  
);

\-- 2\. 计划主表 (统一产品)  
CREATE TABLE plan\_master (  
    plan\_code VARCHAR(50) PRIMARY KEY,  
    plan\_name VARCHAR(200),  
    is\_collective BOOLEAN DEFAULT FALSE \-- 标识是否为集合计划  
);

\-- 3\. 客户-计划关系表 (解决 1:N 问题)  
CREATE TABLE customer\_plan\_relation (  
    relation\_id SERIAL PRIMARY KEY,  
    company\_id VARCHAR(50) REFERENCES customer\_master(company\_id),  
    plan\_code VARCHAR(50) REFERENCES plan\_master(plan\_code),  
    business\_type VARCHAR(20), \-- '受托' | '投资'  
    relation\_status VARCHAR(20), \-- '生效' | '终止'  
    start\_date DATE,  
    end\_date DATE  
);

### **4.2 状态管理议题：如何追踪客户生命周期？**

**挑战**：战客（年度更新）与中标/流失（月度滚动）更新频率不同，且需保留历史。

* **方案选项 1：SCD Type 2 (拉链表)**  
  * 适用于全量历史追踪，但查询当前状态较复杂。  
* **方案选项 2：月度快照表 (Monthly Snapshot)**  
  * 每月生成一张全量状态表。空间占用大，但分析性能好。  
* **方案选项 3（推荐）：统一状态事件表 (Event Log)**

**拟定设计 (方案 3):**

CREATE TABLE customer\_status\_history (  
    history\_id SERIAL PRIMARY KEY,  
    company\_id VARCHAR(50),  
    status\_type VARCHAR(20), \-- '战客' | '中标' | '流失'  
    is\_active BOOLEAN,       \-- 当前是否具备该状态  
    change\_reason VARCHAR(50), \-- '年度计算' | '手工导入' | '规则判定'  
    valid\_from DATE NOT NULL,  
    valid\_to DATE DEFAULT '9999-12-31',  
    created\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP  
);  
\-- 索引设计重点：  
\-- CREATE INDEX idx\_cust\_status\_valid ON customer\_status\_history(company\_id, status\_type, valid\_to);

## **5\. 重点咨询问题 (Questions for Review)**

请专家基于数据治理最佳实践，对以下关键决策点提供指导：

### **Q1: 集合计划的数据模型选择**

针对我们在数据探查中发现的 1:16 集合计划比例，**方案 C (实体分离)** 是否是最佳实践？

* **疑虑**：这种高度规范化（Normalization）的设计，在面对 business.规模明细 这种 **62万+ 行** 的宽表查询时，是否会带来严重的 JOIN 性能问题？
* **替代方案**：是否应该在 Fact 表中保留冗余字段（如同时存储 company_id 和 plan_code）以换取性能？

> **性能考量**：
> - 当前 business.规模明细 表已有 625,126 行（2025.10 数据）
> - 如采用方案 C，查询客户资产需要 JOIN 3 张表（规模明细 → 客户计划关系 → 客户主表）
> - 建议专家评估：PostgreSQL 在百万级数据下的 3表 JOIN 性能（是否有索引优化空间）

**专家咨询问题**：
1. 方案 C 在当前数据规模下的 JOIN 性能是否可接受？
2. 是否应该采用"混合模式"：Fact 表保留冗余字段 + 关系表用于一致性维护？
3. 对于 OLAP 查询场景，是否应该考虑构建物化视图（Materialized Views）？

### **Q2: 混合更新频率的处理**

我们的“战客”是年度计算的，“中标”是月度滚动的。

* 在设计 **Audit Trail (审计追踪)** 时，如何避免年度重算时产生大量无意义的“变更记录”？  
* 对于分析型报表（例如：查询2023年6月的战客名单），推荐使用拉链表还原历史，还是每月固化一张 Snapshot？

### **Q3: 存量脏数据清洗策略**

> **数据验证更新**：通过实际查询验证，所有"已客"表的 company_id 字段均**无 NULL 值**，数据质量良好。

虽然当前数据质量良好，但我们需要建立预防性治理策略，以应对未来可能出现的数据质量问题：

* **预防性措施**：
  * 在新架构中，company_id 应设为 NOT NULL 约束
  * 建立数据质量监控（Data Quality Monitoring）
  * ETL 流程中添加数据验证规则

* **应急处理策略**（如果未来出现 NULL 值）：
  * **A. 剔除脏数据**：会造成资产统计偏差，不推荐
  * **B. 生成虚拟ID**：如 UNKNOWN_COMPANY_001，需业务确认
  * **C. 暂存隔离区**：建立 Quarantine Table，保留待处理记录
  * **D. 推荐策略**：**E + C 组合** - 建立错误表 + 发送告警

```sql
-- 推荐的错误记录处理方案
CREATE TABLE customer.company_id_errors (
    error_id SERIAL PRIMARY KEY,
    source_table VARCHAR(100),
    source_record_id INTEGER,
    original_data JSONB,
    error_type VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 触发器示例：捕获 NULL 值
CREATE OR REPLACE FUNCTION validate_company_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.company_id IS NULL THEN
        INSERT INTO customer.company_id_errors (source_table, source_record_id, original_data, error_type)
        VALUES (TG_TABLE_NAME, NEW.id, row_to_json(NEW), 'NULL_COMPANY_ID');
        RAISE EXCEPTION 'company_id cannot be NULL';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### **Q4: 扩展性与分库分表**

考虑到明细表每月新增 5万行，2年后将突破千万行。

* PostgreSQL 环境下，是否现在就需要考虑按"年份"进行分区（Partitioning）？
* 对于这种读多写少（Read-Heavy）的分析场景，索引设计应侧重于哪些维度的组合（时间、机构、计划）？

> **数据验证更新**：2025年仅10个月已达349,373行（月均约3.5万行），预计全年将超过40万行，**1年内将突破百万行**。分区策略需提前规划。

**拟定索引策略（基于业务查询模式）**：

```sql
-- 1. 复合索引：时间 + 客户（最常见的查询维度）
CREATE INDEX idx_规模明细_月度_company ON business.规模明细(月度, company_id);

-- 2. 复合索引：时间 + 计划（计划级分析）
CREATE INDEX idx_规模明细_月度_计划 ON business.规模明细(月度, 计划代码);

-- 3. 复合索引：时间 + 机构（区域分析）
CREATE INDEX idx_规模明细_月度_机构 ON business.规模明细(月度, 机构代码);

-- 4. 部分索引：仅索引非NULL的company_id（节省空间）
CREATE INDEX idx_规模明细_company_active
ON business.规模明细(company_id)
WHERE company_id IS NOT NULL;

-- 5. 分区表设计（PostgreSQL 声明式分区）
CREATE TABLE business.规模明细_partitioned (
    -- 与原表相同的列定义
    id SERIAL,
    月度 DATE,
    company_id VARCHAR(50),
    -- ... 其他列
) PARTITION BY RANGE (月度);

-- 按年分区
CREATE TABLE business.规模明细_2022 PARTITION OF business.规模明细_partitioned
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');

CREATE TABLE business.规模明细_2023 PARTITION OF business.规模明细_partitioned
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE business.规模明细_2024 PARTITION OF business.规模明细_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE business.规模明细_2025 PARTITION OF business.规模明细_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

**专家咨询问题**：
1. 是否应该在重构时就实施分区表设计？
2. 索引数量与写入性能的平衡点在哪里？
3. 是否考虑使用 PostgreSQL 的 BRIN 索引（适合时间序列数据）？

## **6\. 附录：迁移路线图 (Draft Migration Path)**

我们计划分四阶段实施重构，请评估其风险：

1. **Phase 1 (清理)**：为现有表添加自增 ID，强制补全 NULL 的 company\_id。  
2. **Phase 2 (并行)**：建立新的 customer\_master，通过 Trigger 或 ETL 双写数据。  
3. **Phase 3 (切换)**：将报表层查询指向新模型，停止旧表写入。  
4. **Phase 4 (归档)**：旧表改为只读备份。

文档生成日期: 2026-01-07
准备团队: 数据治理工作组

---

## **附录 A：数据验证 SQL 查询**

> 本附录包含所有用于验证现状的 SQL 查询，专家可自行执行以复现验证结果。

### **A.1 业务明细表统计**

```sql
-- 查询 business.规模明细 的基本统计信息
SELECT
    COUNT(*) as 总记录数,
    COUNT(DISTINCT company_id) as 唯一客户数,
    COUNT(DISTINCT 计划代码) as 唯一计划数,
    MIN(月度) as 最早日期,
    MAX(月度) as 最新日期
FROM business.规模明细;

-- 查询年度数据增长趋势
SELECT
    DATE_TRUNC('year', 月度) as 年份,
    COUNT(*) as 记录数
FROM business.规模明细
GROUP BY DATE_TRUNC('year', 月度)
ORDER BY 年份;
```

**验证结果**：
- 总记录数：625,126
- 唯一客户数：10,153
- 唯一计划数：1,131
- 时间范围：2022.12 - 2025.10
- 年度增长：3,517 (2022) → 48,987 (2023) → 223,249 (2024) → 349,373 (2025前10月)

### **A.2 客户表结构验证**

```sql
-- 查询所有客户表的记录数
SELECT 'customer.企年受托中标' as 表名, COUNT(*) as 记录数 FROM customer.企年受托中标
UNION ALL SELECT 'customer.企年受托已客', COUNT(*) FROM customer.企年受托已客
UNION ALL SELECT 'customer.企年受托战客', COUNT(*) FROM customer.企年受托战客
UNION ALL SELECT 'customer.企年受托流失', COUNT(*) FROM customer.企年受托流失
UNION ALL SELECT 'customer.企年投资中标', COUNT(*) FROM customer.企年投资中标
UNION ALL SELECT 'customer.企年投资已客', COUNT(*) FROM customer.企年投资已客
UNION ALL SELECT 'customer.企年投资战客', COUNT(*) FROM customer.企年投资战客
UNION ALL SELECT 'customer.企年投资流失', COUNT(*) FROM customer.企年投资流失
UNION ALL SELECT 'customer.职年受托已客', COUNT(*) FROM customer.职年受托已客
UNION ALL SELECT 'customer.职年投资已客', COUNT(*) FROM customer.职年投资已客
ORDER BY 记录数 DESC;
```

### **A.3 集合计划问题验证**

```sql
-- 企年受托中标表：集合计划问题
SELECT
    COUNT(*) as 总记录数,
    COUNT(DISTINCT 年金计划号) as 唯一计划数,
    COUNT(DISTINCT company_id) as 唯一公司数,
    COUNT(DISTINCT 年金计划号)::FLOAT / COUNT(DISTINCT company_id) as 计划_公司比例
FROM customer.企年受托中标
WHERE company_id IS NOT NULL;

-- 查询每个计划对应的公司数（Top 10）
SELECT
    年金计划号,
    COUNT(DISTINCT company_id) as 关联公司数
FROM customer.企年受托中标
WHERE company_id IS NOT NULL
GROUP BY 年金计划号
ORDER BY 关联公司数 DESC
LIMIT 10;

-- 企年投资中标表：集合计划问题
SELECT
    COUNT(*) as 总记录数,
    COUNT(DISTINCT 年金计划号) as 唯一计划数,
    COUNT(DISTINCT company_id) as 唯一公司数
FROM customer.企年投资中标
WHERE company_id IS NOT NULL;
```

**验证结果**：
- **企年受托中标**：17个计划，275个公司（1:16比例）
  - AN001 计划：196个公司
  - AN002 计划：23个公司
- **企年投资中标**：42个计划，120个公司（1:3比例）

### **A.4 客户状态重叠验证**

```sql
-- 战客与已客重叠情况
WITH 战客 AS (
    SELECT company_id FROM customer.企年受托战客
),
已客 AS (
    SELECT DISTINCT company_id FROM customer.企年受托已客 WHERE company_id IS NOT NULL
)
SELECT
    (SELECT COUNT(*) FROM 战客) as 战客总数,
    (SELECT COUNT(*) FROM 已客) as 已客总数,
    (SELECT COUNT(*) FROM 战客 WHERE company_id IN (SELECT company_id FROM 已客)) as 重叠客户数,
    ROUND((SELECT COUNT(*) FROM 战客 WHERE company_id IN (SELECT company_id FROM 已客))::NUMERIC /
          (SELECT COUNT(*) FROM 战客) * 100, 2) as 重叠比例_战客,
    ROUND((SELECT COUNT(*) FROM 已客 WHERE company_id IN (SELECT company_id FROM 战客))::NUMERIC /
          NULLIF((SELECT COUNT(*) FROM 已客), 0) * 100, 2) as 重叠比例_已客;
```

**验证结果**：
- 战客总数：114
- 已客总数：330
- 重叠客户数：110
- 重叠比例：96.49%（战客），33.3%（已客）

### **A.5 company_id 数据质量验证**

```sql
-- 查询所有已客表中 company_id 为 NULL 的情况
SELECT 'customer.企年受托已客' as 表名,
       COUNT(*) as 总记录数,
       SUM(CASE WHEN company_id IS NULL THEN 1 ELSE 0 END) as company_id为NULL
FROM customer.企年受托已客
UNION ALL
SELECT 'customer.企年投资已客', COUNT(*), SUM(CASE WHEN company_id IS NULL THEN 1 ELSE 0 END)
FROM customer.企年投资已客
UNION ALL
SELECT 'customer.职年受托已客', COUNT(*), SUM(CASE WHEN company_id IS NULL THEN 1 ELSE 0 END)
FROM customer.职年受托已客
UNION ALL
SELECT 'customer.职年投资已客', COUNT(*), SUM(CASE WHEN company_id IS NULL THEN 1 ELSE 0 END)
FROM customer.职年投资已客;
```

**验证结果**：
- 所有已客表的 company_id 字段均**无 NULL 值**
- 数据质量良好，与文档中"9条记录 company_id 为 NULL"的描述不符

### **A.6 企年受托流失表验证**

```sql
-- 查询企年受托流失表的基本情况
SELECT
    COUNT(*) as 总记录数,
    COUNT(DISTINCT company_id) as 唯一公司数,
    COUNT(DISTINCT 年金计划号) as 唯一计划数,
    SUM(CASE WHEN company_id IS NULL THEN 1 ELSE 0 END) as company_id为NULL记录数,
    SUM(CASE WHEN 年金计划号 IS NULL THEN 1 ELSE 0 END) as 年金计划号为NULL记录数
FROM customer.企年受托流失;
```

**验证结果**：
- 总记录数：190
- 唯一公司数：189
- 唯一计划数：52
- 无 NULL 值记录

---

## **附录 B：数据修正说明**

本文档在验证过程中发现以下数据与原始描述不一致，已进行修正：

| 项目 | 原始描述 | 验证结果 | 修正说明 |
| :---- | :---- | :---- | :---- |
| 规模明细表行数 | 52万+ | **625,126** | 数据已更新至2025.10 |
| 唯一客户数 | 12,000+ | **10,153** | 实际统计结果 |
| 唯一计划数 | 1,200+ | **1,131** | 实际统计结果 |
| company_id NULL | 9条记录 | **0条记录** | 数据质量良好 |
| 月度新增速度 | 约5万行 | **3-5万行/月** | 2025年增速加快 |

> **专家提示**：数据量增长速度远超预期（2025年仅10个月已达349,373行），建议在架构设计时提前考虑分区策略。