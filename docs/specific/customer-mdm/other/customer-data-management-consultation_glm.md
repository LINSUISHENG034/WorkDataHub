# Customer Data Management Design Consultation Request

## Executive Summary

This document presents a comprehensive database design challenge for customer identity management in a pension/annuity fund management system. The legacy database contains multiple customer tables with inconsistent primary key design, fragmented customer classification, and lacks a unified data governance framework.

## Context and Background

### Business Domain
- **Industry**: Pension/Annuity Fund Management (年金基金管理)
- **Products**:
  - Enterprise Annuity (企业年金): Trustee (受托) + Investment (投资) services
  - Occupational Pension (职业年金): Trustee + Investment services
- **Customer Classifications**:
  - Strategic Customers (战客): High-value customers exceeding asset thresholds
  - Existing Customers (已客): Customers with assets from previous year
  - New Customers (新客): Customers without assets from previous year
  - Winning Customers (中标): Customers recently acquired
  - Churned Customers (流失): Customers recently lost

## Current Database Architecture

### Schema Overview

**Customer Schema (customer)**: 11 tables storing customer identity information across different classifications

| Table Name | Primary Key | Rows | Unique company_id | Unique Plan ID | Indexes |
|------------|-------------|------|-------------------|----------------|---------|
| 企年受托中标 | ❌ None | 275 | 275 | 17 | 0 |
| 企年受托已客 | ✅ 年金计划号 | 339 | 330 | 339 | 1 |
| 企年受托战客 | ✅ company_id | 114 | 114 | 114 | 1 |
| 企年受托流失 | ❌ None | 190 | 189 | 52 | 0 |
| 企年投资中标 | ❌ None | 120 | 120 | 42 | 0 |
| 企年投资已客 | ✅ 年金计划号 | 488 | 479 | 488 | 1 |
| 企年投资战客 | ✅ company_id | 239 | 239 | 239 | 1 |
| 企年投资流失 | ❌ None | 32 | 32 | 28 | 0 |
| 职年受托已客 | ✅ 年金计划号 | - | - | - | 1 |
| 职年投资已客 | ✅ 年金计划号 | - | - | - | 1 |
| 续签客户清单 | - | - | - | - | - |

**Business Schema (business)**: 9 tables storing operational transaction data

| Table Name | Rows | Unique Companies | Data Granularity | Latest Month |
|------------|------|------------------|------------------|--------------|
| 规模明细 (AUM Details) | 520K+ | 12K+ | Plan + Portfolio + Monthly | 2025-10 |
| 收入明细 (Revenue Details) | - | - | Transactional | - |
| 组合业绩 (Portfolio Performance) | - | - | Portfolio-level | - |
| ... (other tables) | - | - | - | - |

### Critical Data Design Issues

#### 1. Primary Key Inconsistency
**Problem**: No unified primary key strategy across customer tables

- **Tables with NO primary key** (4 tables):
  - `企年受托中标` (275 rows, 17 unique plans → **1:16 plan-to-company ratio**)
  - `企年受托流失` (190 rows, 52 unique plans)
  - `企年投资中标` (120 rows, 42 unique plans)
  - `企年投资流失` (32 rows, 28 unique plans)

- **Tables using company_id as PK** (2 tables):
  - `企年受托战客` (PK: company_id)
  - `企年投资战客` (PK: company_id)

- **Tables using 年金计划号 as PK** (4 tables):
  - `企年受托已客` (PK: 年金计划号)
  - `企年投资已客` (PK: 年金计划号)
  - `职年受托已客` (PK: 年金计划号)
  - `职年投资已客` (PK: 年金计划号)

**Impact**:
- Cannot enforce referential integrity
- Risk of duplicate records
- Difficult to track customer identity across classifications
- Complex join operations

#### 2. Fragmented Customer Classification
**Problem**: Customer identity spread across 8 classification tables (4 categories × 2 product types)

**Classification Logic**:

| Classification | Update Frequency | Data Source | Business Rule |
|----------------|------------------|-------------|---------------|
| **Strategic (战客)** | Annual | business.规模明细 | Rule: AUM > threshold (previous year-end) OR Manual flag |
| **Existing (已客)** | Annual | business.规模明细 | Rule: Has assets at previous year-end |
| **New (新客)** | Derived | business.规模明细 | Rule: No assets at previous year-end |
| **Winning (中标)** | Monthly | External list | Rolling update from monthly winning list |
| **Churned (流失)** | Monthly | External list | Rolling update from monthly churn list |

**Cross-Product Matrix**:
```
                    企年受托    企年投资    职年受托    职年投资
Strategic (战客)      ✓          ✓          -          -
Existing (已客)       ✓          ✓          ✓          ✓
Winning (中标)        ✓          ✓          -          -
Churned (流失)        ✓          ✓          -          -
```

**Impact**:
- Same company exists in multiple tables simultaneously
- No single source of truth for customer state
- Complex queries to determine customer lifecycle position
- Classification transition not auditable

#### 3. Field Schema Heterogeneity
**Problem**: Different tables use different field sets for similar concepts

**Example: Field Comparison across 企年受托 series**

| Field | 战客 (Strategic) | 已客 (Existing) | 中标 (Winning) | 流失 (Churned) |
|-------|------------------|-----------------|----------------|----------------|
| id | ✓ | ✓ | ✓ | ✓ |
| company_id | ✓ (PK) | nullable | nullable | nullable |
| 年金计划号 | ✓ | ✓ (PK) | ✓ (NOT NULL) | nullable |
| 客户名称/客户全称 | 客户名称 | 客户名称 | 客户全称 | 客户全称 |
| 管理资格 | ✓ | ✓ | ✗ | ✗ |
| 中标日期/流失日期 | ✗ | ✗ | 中标日期 | 流失日期 |
| 上报月份 | ✗ | ✗ | ✓ | ✓ |
| 考核标签/考核有效 | ✗ | ✗ | ✓ | ✓ |
| 计划规模/年缴规模 | ✗ | ✗ | ✓ | ✓ |
| 特有字段 (战区前五大...) | ✗ | ✗ | ✓ (Winning only) | ✓ (Churned only) |

**Impact**:
- Inconsistent field naming (客户名称 vs 客户全称)
- Missing standard fields in some tables
- Different nullable constraints
- Complex ETL logic to normalize

#### 4. Business Detail Table Design Issues
**Table**: `business.规模明细` (AUM Details) - **52万+ rows**

**Schema** (26 fields):
```
id, 月度, 业务类型, 计划类型, 计划代码, 计划名称,
组合类型, 组合代码, 组合名称, 客户名称,
期初资产规模, 期末资产规模, 供款, 流失(含待遇支付),
流失, 待遇支付, 投资收益, 当期收益率,
机构代码, 机构名称, 产品线代码, 年金账户号, 年金账户名, company_id
```

**Issues**:
- ❌ **No primary key** (should be composite: 月度 + 业务类型 + 计划代码 + 组合代码)
- ❌ **No unique index** (risk of duplicate monthly records)
- ❌ **company_id is nullable** (should be NOT NULL for customer attribution)
- ❌ **Mixed granularity** (some rows at plan level, some at portfolio level)

**Data Distribution** (by 业务类型 × 计划类型 × 组合类型):
| Type | Plan Type | Portfolio Type | Rows | Companies | Plans |
|------|-----------|----------------|------|-----------|-------|
| 企年受托 | 单一计划 | NULL | 212K | 400 | 401 |
| 企年受托 | 集合计划 | NULL | 181K | 9,033 | 10 |
| 企年投资 | 单一计划 | 单一固收 | 10K | 383 | 383 |
| 企年投资 | 单一计划 | 单一含权 | 18K | 676 | 680 |
| 职年受托 | 单一计划 | NULL | 1,158 | 34 | 34 |

## Data Flow and Update Logic

### 1. Customer Classification Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    business.规模明细 (Monthly AUM)               │
│                  Source: ETL from operational systems           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├──► Annual Calculation (Year-end AUM)
                            │    ├─► AUM > Threshold → customer.企年受托战客
                            │    ├─► AUM > 0 → customer.企年受托已客
                            │    └─► AUM = 0 → New Customer (not stored)
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│              Monthly External Lists (Excel/CSV)                 │
│           Manual upload: Winning List + Churn List              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├──► Rolling Update (Monthly)
                            │    ├─► New winning → customer.企年受托中标
                            │    └─► New churn → customer.企年受托流失
                            │
                            ▼
                    [Multiple tables updated independently]
```

### 2. Data Quality Issues Identified

**Issue 1: company_id Missing**
- Query result: `企年受托已客` has 339 rows but only 330 unique company_id
- **Root cause**: 9 records lack company_id (NULL values)
- **Business impact**: Cannot link to master customer data

**Issue 2: Plan ID Duplication**
- Query result: `企年受托中标` has 275 rows but only 17 unique plan IDs
- **Root cause**: One plan has multiple companies (集合计划 scenario)
- **Design flaw**: Using plan ID as PK when 1 plan : N companies

**Issue 3: No Audit Trail**
- No timestamp columns (created_at, updated_at)
- No effective date ranges for classification changes
- Cannot reconstruct customer lifecycle history

**Issue 4: Manual Data Entry**
- Fields like `证明材料`, `考核标签`, `备注` are manually maintained
- No validation constraints
- Risk of data inconsistency

## Consultation Questions

### Core Design Principles Questions

#### Q1: Customer Identity Granularity
**Context**:
- One `company_id` can have multiple `年金计划号` (plans)
- One `年金计划号` (集合计划) can have multiple `company_id`
- Current tables mix these two concepts

**Question**: What should be the **primary entity** for customer management?
- Option A: `company_id` as primary entity (one company, multiple plans)
- Option B: `年金计划号` as primary entity (plan-based customer view)
- Option C: Composite entity (company + plan as separate dimensions)

**Pros/Cons**:
| Option | Pros | Cons |
|--------|------|------|
| A (company) | Simplifies cross-plan analysis | Loses plan-level detail |
| B (plan) | Matches current operational granularity | Complicates company-level rollups |
| C (composite) | Most flexible | Most complex ETL and reporting |

#### Q2: Classification State Management
**Context**:
- Customer can be simultaneously: Strategic + Existing + (Future Winning/Churned)
- 8 separate tables store different classifications
- No audit trail for state transitions

**Question**: What is the best design pattern for multi-dimensional customer classification?

**Proposed Patterns**:

**Pattern 1: Type 2 SCD (Slowly Changing Dimension)**
```sql
customer_state_history:
  - company_id (FK)
  - 年金计划号 (FK)
  - classification_type (战客/已客/中标/流失)
  - is_current (boolean)
  - effective_from (date)
  - effective_to (date, NULL for current)
  - source_system (varchar)
  - created_at (timestamp)
```

**Pattern 2: Snapshot Table**
```sql
customer_monthly_snapshot:
  - snapshot_month (date, PK part 1)
  - company_id (PK part 2)
  - 年金计划号 (PK part 3)
  - is_strategic (boolean)
  - is_existing (boolean)
  - is_winning (boolean)
  - is_churned (boolean)
  - aum (decimal)
  - classification_source (varchar)
```

**Pattern 3: Classification Bridge Table**
```sql
customer_classification:
  - company_id (FK)
  - 年金计划号 (FK)
  - business_type (企年受托/企年投资/...)
  - classification_type (战客/已客/中标/流失)
  - effective_date (date)
  - attributes (JSONB for flexible fields)
```

**Which pattern best fits**:
- Monthly rolling updates for winning/churned?
- Annual calculations for strategic/existing?
- Historical reporting requirements?

#### Q3: Referential Integrity with Legacy Data
**Context**:
- 4 tables have NO primary key (data quality issues)
- company_id is nullable in many tables (9 records missing in 企年受托已客)
- Cannot add FK constraints without data cleanup

**Question**: What is the recommended approach for **migration to proper schema design**?

**Proposed Approach**:
1. **Phase 1**: Data quality assessment and cleanup
   - Identify and fix NULL company_id
   - Detect and deduplicate records
   - Validate business rules (e.g., one company cannot be in same table twice)

2. **Phase 2**: Add surrogate keys and constraints
   - Add `id` IDENTITY column to all tables
   - Create unique indexes on natural keys
   - Add NOT NULL constraints on company_id

3. **Phase 3**: Refactor to unified customer table
   - Consolidate 8 classification tables into single customer_master
   - Migrate classification logic to type 2 SCD
   - Build views for backward compatibility

**Question**: Is this phased approach optimal? What are the risks?

#### Q4: Performance vs Normalization Trade-off
**Context**:
- `business.规模明细` has 520K+ rows and growing (monthly inserts)
- Current design: Denormalized (redundant customer_name in every row)
- Reporting queries frequently JOIN customer tables

**Question**: For a **read-heavy analytical workload**, what is the optimal normalization level?

**Options**:

**Option 1: Fully Normalized (3NF)**
```sql
customer_dimension (company_id PK):
  - company_id, company_name, industry, region, ...

plan_dimension (plan_code PK):
  - plan_code, plan_name, plan_type, business_type, ...

aum_fact (monthly surrogate PK):
  - month (FK), company_id (FK), plan_code (FK),
  - portfolio_code, aum_begin, aum_end, ...
```
- **Pros**: No data redundancy, easy updates
- **Cons**: Complex joins for every query, potential performance issues

**Option 2: Dimensional Model (Star Schema)**
```sql
customer_dimension (company_id PK): ...
plan_dimension (plan_code PK): ...
aum_fact (FKs to dimensions): ...
```
- **Pros**: Optimized for OLAP queries
- **Cons**: Requires ETL to maintain slowly changing dimensions

**Option 3: Hybrid (Current + Improvements)**
```sql
business.规模明细 (add indexes, not full normalization):
  - Add composite PK: (月度, 业务类型, 计划代码, 组合代码)
  - Add unique index to prevent duplicates
  - Create materialized views for common query patterns
```
- **Pros**: Minimal disruption, better query performance
- **Cons**: Still has some redundancy

**Recommendation needed**: Which approach balances performance and maintainability?

### Specific Implementation Questions

#### Q5: Handling 集合计划 (Collective Plans)
**Context**:
- One `年金计划号` (集合计划) groups multiple `company_id`
- Example: `企年受托中标` has 17 unique plans but 275 company records (1:16 ratio)
- Current tables incorrectly use plan ID as PK when 1 plan : N companies

**Question**: How should collective plans be modeled?

**Option A: Composite Key**
```sql
customer_table:
  PK: (年金计划号, company_id)
  -- Allows multiple companies per plan
```

**Option B: Hierarchical Design**
```sql
plan_header (plan_code PK):
  - plan_code, plan_name, is_collective (boolean), ...

plan_participants (plan_code FK, company_id FK):
  - PK: (plan_code, company_id)
  - Links collective plans to member companies
```

**Option C: Denormalized Flags**
```sql
customer_table:
  - company_id (PK)
  - is_collective_plan_member (boolean)
  - collective_plan_code (nullable)
```

**Which approach best supports**:
- Querying by plan (all companies in 集合计划XX)?
- Querying by company (all plans that company participates in)?
- Maintaining historical membership changes?

#### Q6: Audit Trail Design for State Transitions
**Context**:
- Strategic customers: Calculated annually (needs yearly recalculation)
- Winning/Churned: Rolling monthly updates (need historical tracking)
- No current mechanism to track WHEN a customer changed classification

**Question**: How to design audit trail for **different update frequencies**?

**Proposed Design**:
```sql
classification_event_log:
  - event_id (PK, IDENTITY)
  - event_timestamp (timestamp)
  - event_type (ENUM: 'CALCULATED', 'MANUAL', 'ROLLING_UPDATE')
  - company_id (FK)
  - 年金计划号 (FK)
  - classification_before (JSONB)
  - classification_after (JSONB)
  - change_reason (varchar)
  - source_batch_id (FK to ETL batch table)

-- Indexes for common queries:
CREATE INDEX idx_event_log_company_time ON classification_event_log(company_id, event_timestamp DESC);
CREATE INDEX idx_event_log_classification ON classification_event_log(classification_after);
```

**Question**:
- Is this design appropriate for mixed-frequency updates?
- How to handle "recalculation" events (annual strategic customer refresh)?
- Should we store full snapshots or just deltas?

#### Q7: Handling Missing Data (Data Quality Strategy)
**Context**:
- 9 records in `企年受托已客` have NULL company_id
- Some tables have NULL `年金计划号`
- Cannot enforce referential integrity without cleanup

**Question**: What is the **industry best practice** for handling missing master data?

**Proposed Strategy**:
1. **Data Profiling Phase**
   ```sql
   -- Identify all records with missing keys
   SELECT table_name, COUNT(*) as missing_count
   FROM information_schema.columns
   WHERE is_nullable = 'YES'
     AND column_name IN ('company_id', '年金计划号')
   GROUP BY table_name;
   ```

2. **Data Enrichment Options**
   - Option A: Fuzzy matching on customer_name (Levenshtein distance)
   - Option B: Manual data entry workflow for flagged records
   - Option C: Mark as "UNKNOWN" entity (special company_id = 'UNKNOWN')

3. **Preventive Measures**
   - Add CHECK constraints: `company_id <> ''`
   - Add triggers to validate on INSERT/UPDATE
   - Implement data quality checks in ETL pipeline

**Question**: What is the recommended balance between automated matching vs manual correction?

#### Q8: Scalability Considerations
**Context**:
- Current `business.规模明细`: 520K rows
- Expected growth: ~50K rows/month (6M rows/year)
- 8 customer classification tables: ~2K rows total (small, stable)

**Question**: What are the **long-term scalability concerns** with current design?

**Concerns**:
1. **Monthly table growth**: `规模明细` will reach 10M+ rows in 2 years
   - Should we implement partitioning by year?
   - Should we archive older data to cold storage?

2. **Query performance**: JOINs between 520K fact table and customer dimensions
   - Current: No indexes on `company_id` in `规模明细`
   - Needed: Composite indexes on (月度, 业务类型, company_id)

3. **Concurrent updates**: Monthly ETL load + user queries
   - Risk: Long-running ETL blocks reporting queries
   - Solution: Partition swapping or materialized view refresh?

**Recommendation needed**: Partitioning strategy and index design for 10M+ row fact table.

## Proposed Target Architecture (Draft)

### Unified Customer Master Design

```sql
-- Core customer entity
CREATE TABLE customer_master (
    company_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL,
    customer_type VARCHAR(20), -- '企年' | '职年'
    industry VARCHAR(100),
    region VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Plan dimension (handles 1:1 and 1:N relationships)
CREATE TABLE plan_master (
    plan_code VARCHAR(50) PRIMARY KEY,
    plan_name VARCHAR(200) NOT NULL,
    plan_type VARCHAR(20), -- '单一' | '集合'
    business_type VARCHAR(20), -- '受托' | '投资'
    is_collective BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Company-Plan relationship (many-to-many)
CREATE TABLE customer_plan_relationship (
    company_id VARCHAR(50) REFERENCES customer_master(company_id),
    plan_code VARCHAR(50) REFERENCES plan_master(plan_code),
    relationship_type VARCHAR(50), -- '受托客户' | '投资客户'
    effective_from DATE NOT NULL,
    effective_to DATE, -- NULL for current
    PRIMARY KEY (company_id, plan_code, effective_from)
);

-- Classification state (Type 2 SCD)
CREATE TABLE customer_classification (
    classification_id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) REFERENCES customer_master(company_id),
    plan_code VARCHAR(50) REFERENCES plan_master(plan_code),
    classification_type VARCHAR(20) NOT NULL, -- '战客' | '已客' | '中标' | '流失'
    is_current BOOLEAN DEFAULT TRUE,
    effective_from DATE NOT NULL,
    effective_to DATE, -- NULL for current
    aum DECIMAL(18,2),
    classification_source VARCHAR(100), -- 'CALCULATED_AUM' | 'MANUAL_UPLOAD' | 'ROLLING_UPDATE'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for query performance
CREATE INDEX idx_classification_current ON customer_classification(company_id, is_current, effective_from DESC);
CREATE INDEX idx_classification_plan ON customer_classification(plan_code, is_current);
CREATE INDEX idx_classification_type ON customer_classification(classification_type, is_current);
```

### Business Detail Table Improvements

```sql
-- Add proper constraints to existing table
ALTER TABLE business.规模明细
    ADD CONSTRAINT pk_aum_details
    PRIMARY KEY (月度, 业务类型, 计划类型, 计划代码, 组合代码);

ALTER TABLE business.规模明细
    ADD CONSTRAINT fk_company
    FOREIGN KEY (company_id)
    REFERENCES customer_master(company_id);

ALTER TABLE business.规模明细
    ALTER COLUMN company_id SET NOT NULL;

-- Performance indexes
CREATE INDEX idx_aum_company_month ON business.规模明细(company_id, 月度 DESC);
CREATE INDEX idx_aum_plan_month ON business.规模明细(计划代码, 月度 DESC);
```

## Migration Strategy (High-Level)

### Phase 1: Assessment (1-2 weeks)
1. Data profiling on all customer tables
2. Identify data quality issues (NULL keys, duplicates, orphans)
3. Document business rules for each classification
4. Estimate data cleanup effort

### Phase 2: Stabilization (2-3 weeks)
1. Add surrogate keys and NOT NULL constraints
2. Create unique indexes on natural keys
3. Implement data quality checks in ETL
4. Backfill missing company_id where possible

### Phase 3: Refactoring (4-6 weeks)
1. Create new unified schema (customer_master, plan_master, etc.)
2. ETL migration scripts (historical data load)
3. Create views for backward compatibility
4. Update application layer queries

### Phase 4: Cutover (1-2 weeks)
1. Parallel run (old + new schema)
2. Validate data consistency
3. Switch application to new schema
4. Deprecate old tables (keep for 6 months as backup)

## Questions for External Experts

### High-Level Design Questions
1. **Customer Identity**: Should `company_id` or `plan_code` be the primary entity? How to handle collective plans (1 plan : N companies)?

2. **Classification Model**: Type 2 SCD vs Snapshot table vs Bridge table - which pattern best fits mixed update frequencies (annual vs monthly)?

3. **Normalization Level**: For analytical workload on 520K+ row fact table, what is the optimal normalization level (3NF vs Star Schema vs Hybrid)?

4. **Referential Integrity**: How to migrate from no-constraint legacy tables to properly designed schema with minimal downtime?

### Technical Implementation Questions
5. **Missing Data Strategy**: Industry best practices for handling NULL master data (company_id, plan_code) - automated matching vs manual correction?

6. **Audit Trail Design**: How to design event logging for state transitions when classification updates have different frequencies (annual strategic calculation vs monthly rolling updates)?

7. **Scalability**: Partitioning strategy and index design for fact table growing at 50K rows/month (10M+ rows in 2 years)?

8. **Collective Plans**: Optimal data model for 1:N plan-to-company relationships while maintaining query performance for both plan-centric and company-centric queries?

### Data Governance Questions
9. **Data Ownership**: Who should be responsible for data quality in customer master? Business team (manual tagging) vs Data team (automated validation)?

10. **Change Management**: How to handle "recalculation events" (e.g., annual strategic customer refresh) in audit trail without creating duplicate historical records?

11. **Cross-System Consistency**: If customer data exists in multiple operational systems, which system should be the "source of truth" for customer_master?

12. **Regulatory Compliance**: Any data retention requirements for customer classification history in pension fund industry?

## Supporting Data

### Database Statistics (Legacy MySQL)

**Customer Tables Row Counts**:
```
企年受托中标: 275 rows (17 unique plans → 1:16 ratio)
企年受托已客: 339 rows (330 unique company_id, 9 NULLs)
企年受托战客: 114 rows (114 unique company_id)
企年受托流失: 190 rows (52 unique plans)

企年投资中标: 120 rows (42 unique plans)
企年投资已客: 488 rows (479 unique company_id)
企年投资战客: 239 rows (239 unique company_id)
企年投资流失: 32 rows (28 unique plans)
```

**Business Detail Table Row Counts**:
```
规模明细 (AUM Details): 520K+ rows
- Latest data: 2025-10
- Granularity: Monthly × 业务类型 × 计划类型 × 组合类型
- Unique companies: 12,000+
- Unique plans: 1,200+
```

### Current Data Quality Scorecard

| Table | Primary Key | NOT NULL company_id | Unique Index | Duplicate Risk |
|-------|-------------|---------------------|--------------|----------------|
| 企年受托中标 | ❌ | ⚠️ (nullable) | ❌ | **HIGH** |
| 企年受托已客 | ✅ (plan_id) | ⚠️ (9 NULLs) | ✅ | LOW |
| 企年受托战客 | ✅ (company_id) | ✅ | ✅ | LOW |
| 企年受托流失 | ❌ | ⚠️ (nullable) | ❌ | **HIGH** |
| 企年投资中标 | ❌ | ⚠️ (nullable) | ❌ | **HIGH** |
| 企年投资已客 | ✅ (plan_id) | ⚠️ (nullable) | ✅ | LOW |
| 企年投资战客 | ✅ (company_id) | ✅ | ✅ | LOW |
| 企年投资流失 | ❌ | ⚠️ (nullable) | ❌ | **HIGH** |
| 规模明细 | ❌ | ⚠️ (nullable) | ❌ | **CRITICAL** |

## Appendices

### Appendix A: Sample Query for Data Profiling
```sql
-- Find duplicate records by company_id
SELECT company_id, COUNT(*) as duplicate_count
FROM customer.企年受托已客
GROUP BY company_id
HAVING COUNT(*) > 1;

-- Find records with missing master data
SELECT '企年受托已客' as table_name, COUNT(*) as null_count
FROM customer.企年受托已客
WHERE company_id IS NULL
UNION ALL
SELECT '企年投资已客', COUNT(*)
FROM customer.企年投资已客
WHERE company_id IS NULL;

-- Analyze collective plan distribution
SELECT 年金计划号, COUNT(*) as company_count
FROM customer.企年受托中标
GROUP BY 年金计划号
ORDER BY company_count DESC
LIMIT 10;
```

### Appendix B: Business Glossary
- **company_id**: Unified customer identifier (should be primary key)
- **年金计划号 (Plan Code)**: Annuity plan identifier (1:1 for single plans, 1:N for collective plans)
- **集合计划 (Collective Plan)**: Plan that groups multiple companies (e.g., industry-specific funds)
- **单一计划 (Single Plan)**: Plan for one company
- **业务类型 (Business Type)**: 企年受托 | 企年投资 | 职年受托 | 职年投资
- **战客 (Strategic Customer)**: Customer with AUM > threshold (strategic priority)
- **已客 (Existing Customer)**: Customer with assets at previous year-end
- **中标 (Winning Customer)**: Customer acquired in recent monthly list
- **流失 (Churned Customer)**: Customer lost in recent monthly list

### Appendix C: Current Database Technology Stack
- **Database**: PostgreSQL (legacy MySQL migrated to PostgreSQL)
- **ETL Tool**: Custom Python-based (WorkDataHub project)
- **Reporting**: Direct SQL queries + Business Intelligence tools
- **Data Volume**: ~1M rows across all tables (growing at ~50K/month)

---

**Document Prepared**: 2026-01-07
**Prepared By**: WorkDataHub Development Team
**Purpose**: External expert consultation on customer data management architecture
**Contact**: [Project Repository](https://github.com/your-org/WorkDataHub)
