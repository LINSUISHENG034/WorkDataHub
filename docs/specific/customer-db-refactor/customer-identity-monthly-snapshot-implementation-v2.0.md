这是一个为开发团队准备的详细技术实施方案。该方案基于**双层数据架构（OLTP合约层 \+ OLAP快照层）**，旨在解决“集合计划多对多关系”及“跨业务线状态冲突”的核心痛点，同时兼顾业务操作的实时性与报表分析的高性能。

# **\---**

**客户身份管理重构：实施方案 (V2.0)**

## **1\. 方案概述**

### **1.1 核心目标**

本方案旨在取代当前分散的 11 张客户标签表，构建一个**分层清晰**的数据体系：

1. **操作层 (OLTP)**：管理精准的客户签约关系与实时状态。  
2. **分析层 (OLAP)**：提供统一、维度化、可追溯的月度快照。

### **1.2 架构变更摘要**

* **引入实时合约表 (customer\_plan\_contract)**：解决“月内变动丢失”和“无法精确到日”的问题。  
* **引入实时标签 (tags JSONB)**：解决业务灵活性和实时打标需求。  
* **保留月度快照 (fct\_...\_monthly\_status)**：解决历史趋势分析和高性能报表查询问题。

## **\---**

**2\. 数据库模型设计 (PostgreSQL DDL)**

### **2.1 维度表设计**

#### **2.1.1 客户主数据表 (dim\_company)**

用于清洗和统一 company\_id，并承载实时业务标签。

CREATE TABLE customer.dim\_company (  
    company\_uuid UUID PRIMARY KEY DEFAULT gen\_random\_uuid(), \-- 内部代理键  
    original\_company\_id VARCHAR(100), \-- 原始系统ID (用于回溯)  
    customer\_name VARCHAR(200) NOT NULL, \-- 清洗后的标准化名称  
    customer\_name\_raw VARCHAR(200), \-- 原始名称  
    industry VARCHAR(100), \-- 行业  
    region VARCHAR(100), \-- 区域  
      
    \-- 【新增】实时标签字段 (OLTP)  
    \-- 用于存储 "VIP", "高风险", "拟上市" 等灵活、实时的业务标记  
    tags JSONB DEFAULT '{}',   
      
    is\_valid BOOLEAN DEFAULT TRUE,  
    created\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP  
);

\-- 索引  
CREATE UNIQUE INDEX idx\_dim\_company\_original ON customer.dim\_company(original\_company\_id);  
\-- GIN 索引用于加速 JSONB 查询  
CREATE INDEX idx\_dim\_company\_tags ON customer.dim\_company USING GIN (tags);

\-- 【重要】初始化 "未知客户" 占位符  
INSERT INTO customer.dim\_company (company\_uuid, original\_company\_id, customer\_name)  
VALUES ('00000000-0000-0000-0000-000000000000', 'UNKNOWN', '未知/未归集客户');

#### **2.1.2 计划维度表 (dim\_annuity\_plan)**

解决集合计划 (1:N) 问题，只描述计划本身的属性。

CREATE TABLE customer.dim\_annuity\_plan (  
    plan\_code VARCHAR(100) PRIMARY KEY, \-- 年金计划号  
    plan\_name VARCHAR(200),  
    plan\_type VARCHAR(50), \-- '单一计划' / '集合计划'  
    is\_collective BOOLEAN GENERATED ALWAYS AS (plan\_type LIKE '%集合%') STORED  
);

### **2.2 核心业务交易表 (OLTP)**

#### **2.2.1 客户签约关系表 (customer\_plan\_contract)**

**【新增核心表】** 这是业务系统的“心脏”。它是月度快照的**数据源头**，记录每一笔业务关系的生与死。

CREATE TABLE customer.customer\_plan\_contract (  
    contract\_id SERIAL PRIMARY KEY,  
    company\_uuid UUID NOT NULL REFERENCES customer.dim\_company(company\_uuid),  
    plan\_code VARCHAR(100) NOT NULL REFERENCES customer.dim\_annuity\_plan(plan\_code),  
      
    \-- 业务维度  
    business\_type VARCHAR(20) NOT NULL, \-- 枚举: '受托', '投资'  
    role\_type VARCHAR(20),              \-- 扩展字段: '主发起人', '参与人'  
      
    \-- 状态与时间 (SCD Type 2 风格)  
    status VARCHAR(20) NOT NULL,        \-- '正常', '流失', '冻结', '中标入围'  
    valid\_from DATE NOT NULL,           \-- 精确到日的生效时间  
    valid\_to DATE DEFAULT '9999-12-31', \-- 9999表示当前有效  
      
    \-- 审计  
    created\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP,  
      
    \-- 复合唯一约束：确保同一客户在同一计划同一业务下，同一时间只有一个有效状态  
    CONSTRAINT uq\_active\_contract UNIQUE (company\_uuid, plan\_code, business\_type, valid\_to)  
);

\-- 索引：加速当前有效合约的查询  
CREATE INDEX idx\_active\_contracts ON customer.customer\_plan\_contract(company\_uuid, plan\_code)   
WHERE valid\_to \= '9999-12-31';

### **2.3 核心分析事实表 (OLAP)**

#### **2.3.1 客户业务状态月度快照表 (fct\_customer\_business\_monthly\_status)**

这是报表层的核心。它是由 customer\_plan\_contract 在月末“冻结”生成的切片。

CREATE TABLE customer.fct\_customer\_business\_monthly\_status (  
    \-- 复合主键维度  
    snapshot\_month DATE NOT NULL,       \-- 快照月份 (例如 2025-10-01)  
    company\_uuid UUID NOT NULL REFERENCES customer.dim\_company(company\_uuid),  
    product\_line VARCHAR(20) NOT NULL,  \-- 枚举: '企年', '职年'  
    business\_type VARCHAR(20) NOT NULL, \-- 枚举: '受托', '投资'  
      
    \-- 状态标签 (历史固化)  
    \-- 注意：这些字段来自当月的 Contract 表或当时的 Tags 快照  
    is\_strategic BOOLEAN DEFAULT FALSE, \-- 战客 (当时状态)  
    is\_existing BOOLEAN DEFAULT FALSE,  \-- 已客  
    is\_new BOOLEAN DEFAULT FALSE,       \-- 新客  
    is\_winning BOOLEAN DEFAULT FALSE,   \-- 本月中标  
    is\_churned BOOLEAN DEFAULT FALSE,   \-- 本月流失  
      
    \-- 度量值  
    aum\_balance DECIMAL(20,2) DEFAULT 0, \-- 月末资产规模  
      
    \-- 审计字段  
    updated\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP,  
      
    \-- 约束  
    PRIMARY KEY (snapshot\_month, company\_uuid, product\_line, business\_type)  
);

\-- 索引：加速 Power BI 及常用查询  
CREATE INDEX idx\_status\_query ON customer.fct\_customer\_business\_monthly\_status   
(snapshot\_month, business\_type, is\_strategic);

## **\---**

**3\. 关键架构设计辩证 (Design Rationale)**

为确保团队理解架构意图，特对关键设计决策进行说明：

### **3.1 为什么既要“合约表”又要“月度快照”？**

| 维度 | Contract 表 (OLTP) | Snapshot 表 (OLAP) |
| :---- | :---- | :---- |
| **定位** | **源头 (Source of Truth)** | **结果 (Derived Result)** |
| **精度** | **精确到日**。记录 10月5日入职、10月20日离职的全过程。 | **按月切片**。只记录 10月31日当天的最终状态。 |
| **用途** | 支撑业务操作（校验、计费、变更）。 | 支撑历史趋势分析、高性能报表查询。 |
| **必要性** | 若无此表，无法处理月内变动，无法计算精确收益。 | 若无此表，查历史趋势需回溯海量日志，性能极差。 |

### **3.2 为什么既要 tags JSONB 又要在快照里存 is\_strategic？**

| 维度 | dim\_company.tags (JSONB) | fct\_snapshot.is\_strategic |
| :---- | :---- | :---- |
| **时效** | **实时 (Real-time)** | **历史固化 (History)** |
| **场景** | **当下操作**：业务员打开系统，提示“这是VIP客户”。 | **历史回溯**：查询“2023年6月的战客流失率”。 |
| **逻辑** | 即使客户现在变为了普通客户，tags 会立即更新。 | 2023年6月的快照里，他依然记录为“战客”，确保历史报表不失真。 |

## **\---**

**4\. ETL 数据处理逻辑**

### **步骤 1: 维度与标签维护 (Real-time/Daily)**

1. **清洗**: 维护 dim\_company 和 dim\_annuity\_plan。  
2. **打标**: 业务系统通过 API 更新 dim\_company.tags (如：UPDATE dim\_company SET tags \= tags || '{"segment": "strategic"}')。

### **步骤 2: 合约状态维护 (Daily/Event-driven)**

* 当业务发生变更（中标、流失）时，**必须先更新 customer\_plan\_contract**。  
* 逻辑：将旧记录 valid\_to 更新为昨天，插入新记录 valid\_from 为今天。

### **步骤 3: 生成月度快照 (Monthly Job)**

每月初，基于 customer\_plan\_contract 和 business.规模明细 生成上月快照。

\-- 伪代码逻辑：生成快照  
INSERT INTO customer.fct\_customer\_business\_monthly\_status   
SELECT   
    '2025-10-01' as snapshot\_month,  
    c.company\_uuid,  
    '企年', '受托',  
      
    \-- 状态逻辑：从 Tags 和 Contract 派生  
    (c.tags \-\>\> 'segment' \= 'strategic') as is\_strategic, \-- 固化当时的标签  
    (contract.status \= '正常') as is\_existing,  
    (contract.status \= '流失') as is\_churned,  
      
    SUM(s.期末资产规模) as aum\_balance  
FROM customer.dim\_company c  
JOIN customer.customer\_plan\_contract contract   
    ON c.company\_uuid \= contract.company\_uuid  
    AND contract.valid\_to \>= '2025-10-01' AND contract.valid\_from \<= '2025-10-31'  
LEFT JOIN business.规模明细 s ON ...  
WHERE ...  
## ---

**5\. Power BI 建模与开发指南**

为了支持前端灵活分析，BI 团队需按以下规范建模。

### **5.1 Power Query 准备**

在两张表中创建**完全一致**的连接键（Link Key）。

**表 A: fct\_customer\_business\_monthly\_status (作为 Header)**

Code snippet

Link\_Key \= Text.From(\[snapshot\_month\]) & "|" & \[original\_company\_id\] & "|" & \[product\_line\] & "|" & \[business\_type\]

**表 B: business.规模明细 (作为 Detail)**

Code snippet

// 确保字段映射与表 A 一致  
Link\_Key \= Text.From(\[月度\]) & "|" & \[company\_id\] & "|" & \[产品线代码\] & "|" & \[业务类型\]

### **5.2 模型关系设置**

* **关系**: 表 A (1) \---\> 表 B (\*)  
* **连接键**: Link\_Key  
* **方向**: 单向 (Single)

### **5.3 度量值开发 (DAX)模板**

**需求：统计“受托战客”的期末规模**

Code snippet

AUM\_受托战客 \=   
CALCULATE(  
    SUM('business.规模明细'\[期末资产规模\]),  
    'fct\_customer\_business\_monthly\_status'\[business\_type\] \= "受托",  
    'fct\_customer\_business\_monthly\_status'\[is\_strategic\] \= TRUE,  
    'fct\_customer\_business\_monthly\_status'\[product\_line\] \= "企年"  
)

## ---

**6\. 数据治理与迁移计划**

### **Phase 1: 数据准备 (Week 1\)**

1. **创建维度表**: 部署 dim\_company，并在 ETL 中处理空值逻辑。  
2. **补全历史数据**: 为过去 12-24 个月的数据生成 fct\_customer\_business\_monthly\_status 历史快照（依据历史 AUM 倒推）。

### **Phase 2: 双轨运行 (Week 2-3)**

1. **部署新 ETL**: 每月自动生成新快照表。  
2. **BI 验证**: Power BI 开发一套新报表，连接新模型，与旧报表（基于 11 张表）的数据进行核对。重点核对：  
   * 战客总资产是否一致？  
   * 交叉客户（既受托又投资）的状态显示是否正确？

### **Phase 3: 切割上线 (Week 4\)**

1. 将 BI 报表数据源切换至新模型。  
2. 归档并重命名旧的 11 张表（如 legacy\_企年受托中标）。  
3. 停止旧表的 ETL 任务。

## **7\. 开发团队检查清单 (Checklist)**

* \[ \] **DDL**: 确认所有新建表包含 company\_uuid 且建立了外键约束（在数据清洗后）。  
* \[ \] **ETL**: 确认空值 (NULL) 已被强制转换为 'UNKNOWN' 或 '0000'，防止 Join 丢失。  
* \[ \] **Constraint**: 确认快照表的复合主键无重复记录。  
* \[ \] **Performance**: 确认 Power BI 中 Link\_Key 的基数，如果超过 1000 万行，考虑在 SQL 层将其哈希为 INT64。

---

此方案解决了\*\*数据粒度（Granularity）\*\*不匹配的根本问题，是兼顾开发成本与长期可维护性的最佳实践。