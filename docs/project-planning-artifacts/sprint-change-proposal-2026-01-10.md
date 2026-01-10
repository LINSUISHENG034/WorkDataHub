# Sprint Change Proposal: Customer Identity MDM & Monthly Snapshot Model

**Generated**: 2026-01-10  
**Triggered by**: [customer-identity-monthly-snapshot-implementation-v3.2-project-based.md](file:///e:/Projects/WorkDataHub/docs/specific/customer-db-refactor/customer-identity-monthly-snapshot-implementation-v3.2-project-based.md)  
**Change Scope**: **Major** (New Epic Required)

---

## 1. Issue Summary

### 1.1 Problem Statement

The current WorkDataHub project lacks a comprehensive **Customer Master Data Management (MDM)** solution for tracking customer identity across time. While Epic 6 addresses company ID enrichment for cross-domain joins, there is no mechanism to:

1. **Track customer status transitions** (战客/已客/中标/流失) over time
2. **Generate monthly snapshots** for historical trend analysis
3. **Manage customer-plan contract relationships** (SCD Type 2)
4. **Distinguish product lines** (企年受托/企年投资/职年受托/职年投资) in customer analysis

### 1.2 Discovery Context

This proposal emerged from a parallel workstream analyzing the `legacy` PostgreSQL database structure, specifically:
- `mapping."年金客户"` (10,436 records) - existing customer dimension
- `mapping."年金计划"` (1,158 records) - existing plan dimension
- `business."规模明细"` (625,126 rows, 2022-2025) - core business data

### 1.3 Evidence

| Data Point | Value | Implication |
|------------|-------|-------------|
| `business.规模明细` rows | 625,126 | Large dataset requiring optimized schema |
| Unique companies | 10,153 | Manageable dimension table size |
| Growth rate (2024-2025) | ~4-5x YoY | Need for scalable design |
| Product lines | 4 (PL201-PL204) | Unified dimension, not redundant business_type |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Status | Impact Level | Description |
|------|--------|--------------|-------------|
| Epic 1-4 | Completed | ⚪ None | No retroactive changes needed |
| Epic 5 | Completed | ⚪ None | Infrastructure layer unaffected |
| Epic 6 | In Progress | 🟡 Moderate | Company enrichment may need coordination with MDM |
| **New Epic 7** | Proposed | 🔴 Major | New epic required for Customer MDM |
| Future Epics | Planned | 🟡 Moderate | May consume customer snapshot data |

### 2.2 PRD Impact

| Functional Requirement | Current Status | Required Change |
|------------------------|----------------|-----------------|
| FR-3.3: Company Enrichment | Defined | **Extend** to include customer status tracking |
| FR-4: Database Loading | Defined | **Add** new tables (`customer` schema) |
| FR-8: Monitoring | Defined | **Add** customer snapshot ETL observability |
| **NEW FR-9** | N/A | **Create** Customer MDM requirements |

### 2.3 Architecture Impact

| Component | Current State | Required Change |
|-----------|---------------|-----------------|
| Database Schema | `business`, `mapping`, `enterprise` schemas | **Add** `customer` schema with 2 tables + 1 view |
| ETL Pipeline | Domain-focused (annuity_performance, etc.) | **Add** Customer snapshot ETL job |
| BI Integration | Direct table queries | **Add** star schema model for Power BI |

### 2.4 Artifact Conflicts

| Artifact | Conflict Type | Resolution |
|----------|---------------|------------|
| `docs/architecture/domain-registry.md` | Missing customer domain | Add customer domain registration |
| `docs/epics/index.md` | Missing Epic 7 | Add Epic 7 reference |
| `docs/prd/functional-requirements.md` | Missing FR-9 | Add Customer MDM requirements |

---

## 3. Recommended Approach

### 3.1 Decision: **Create New Epic 7 - Customer Master Data Management**

> [!IMPORTANT]
> This change introduces a new business capability not covered by existing epics. Direct adjustment within Epic 5/6 would violate Single Responsibility Principle.

### 3.2 Rationale

| Factor | Evaluation | Score |
|--------|------------|-------|
| Effort | 4 weeks (per V3.2 proposal) | Medium |
| Risk | New schema, no existing code dependency | Low |
| Business Value | Historical trend analysis, customer attribution | High |
| Technical Debt | Clean greenfield implementation | Low |
| Timeline Impact | Parallel track, does not block Epic 6 | None |

### 3.3 Alternative Approaches Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Extend Epic 6 | Simpler epic structure | Scope creep, SRP violation | ❌ Rejected |
| Post-MVP Enhancement | Defer complexity | Business need is immediate | ❌ Rejected |
| **New Epic 7** | Clean separation, proper scope | Additional planning overhead | ✅ Selected |

---

## 4. Detailed Change Proposals

### 4.1 New Epic: Epic 7 - Customer Master Data Management

**Goal**: Build a comprehensive customer identity management system with monthly snapshots for historical trend analysis.

**Proposed Stories**:

| Story ID | Title | Effort |
|----------|-------|--------|
| 7.1 | Customer Schema Setup (`customer.customer_plan_contract`) | 0.5 days |
| 7.2 | Monthly Snapshot Table (`customer.fct_customer_business_monthly_status`) | 0.5 days |
| 7.3 | Business Type Aggregation View | 0.5 days |
| 7.4 | Historical Data Backfill (12-24 months) | 1 day |
| 7.5 | Contract Status ETL (Daily/Event-driven) | 1 day |
| 7.6 | Monthly Snapshot Job | 1 day |
| 7.7 | Power BI Star Schema Integration | 1 day |
| 7.8 | Index Optimization (BRIN, Partial) | 0.5 days |
| 7.9 | Integration Testing & Documentation | 1 day |

**Total Estimated Effort**: 7 working days (~1.5 weeks)

---

### 4.2 PRD Modification: Add FR-9

```markdown
### FR-9: Customer Master Data Management
**"Track customer identity and status over time"**

**FR-9.1: Customer-Plan Contract Tracking**
- **Description:** Record customer-plan relationships with SCD Type 2 versioning
- **User Value:** Know exactly when customers signed/churned contracts

**FR-9.2: Monthly Customer Status Snapshots**
- **Description:** Generate monthly snapshots of customer status and AUM
- **User Value:** Historical trend analysis for战客流失率、新客转化率

**FR-9.3: Product Line Dimension**
- **Description:** Unified product line dimension (PL201-PL204) with derived business type
- **User Value:** Consistent reporting across 受托/投资 business types
```

---

### 4.3 Architecture Modification: Add `customer` Schema

```sql
-- New schema and tables
CREATE SCHEMA IF NOT EXISTS customer;

-- Table 1: Contract relationships (OLTP)
CREATE TABLE customer.customer_plan_contract (...);

-- Table 2: Monthly snapshots (OLAP)
CREATE TABLE customer.fct_customer_business_monthly_status (...);

-- View: Business type aggregation
CREATE VIEW v_customer_business_monthly_status_by_type AS ...;
```

**Full DDL**: See [customer-identity-monthly-snapshot-implementation-v3.2-project-based.md §7.1](file:///e:/Projects/WorkDataHub/docs/specific/customer-db-refactor/customer-identity-monthly-snapshot-implementation-v3.2-project-based.md#71-创建customer-schema和新表)

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

| Scope | Criteria | Match |
|-------|----------|-------|
| Minor | Direct dev team implementation | ❌ |
| Moderate | Backlog reorganization needed | ❌ |
| **Major** | Fundamental replan with PM/Architect | ✅ |

### 5.2 Handoff Plan

| Role | Responsibility | Deliverable |
|------|----------------|-------------|
| **Product Manager** | Review and approve FR-9 requirements | Updated PRD |
| **Solution Architect** | Validate customer schema design | Architecture approval |
| **Development Team** | Implement Epic 7 stories | Working code |
| **Data Engineer** | Configure ETL jobs | Dagster job definitions |

### 5.3 Success Criteria

- [ ] `customer` schema created with 2 tables + 1 view
- [ ] Historical data backfilled (2023-01 to present)
- [ ] Monthly snapshot job runs successfully
- [ ] Power BI connects to star schema model
- [ ] 战客/已客/中标/流失 status queries return correct data

### 5.4 Next Steps

1. ✅ **Immediate**: Approve this Sprint Change Proposal
2. 🔲 **Week 1**: Create Epic 7 document (`docs/epics/epic-7-customer-mdm.md`)
3. 🔲 **Week 1**: Update PRD with FR-9 requirements
4. 🔲 **Week 2**: Begin Story 7.1-7.3 (Schema & Tables)
5. 🔲 **Week 3-4**: Complete remaining stories

---

## 6. Appendix: Checklist Completion Status

### Section 1: Understand the Trigger and Context
- [x] 1.1 Triggering story identified: Customer DB Refactor initiative (not a specific story)
- [x] 1.2 Core problem defined: Missing customer MDM with historical tracking
- [x] 1.3 Evidence gathered: Data volume, growth rate, schema analysis

### Section 2: Epic Impact Assessment
- [x] 2.1 Current epic evaluated: No current epic addresses this
- [x] 2.2 Epic-level changes determined: New Epic 7 required
- [x] 2.3 Future epics reviewed: Epic 6 may need coordination
- [x] 2.4 Epic validity checked: Existing epics remain valid
- [x] 2.5 Priority considered: Can run in parallel with Epic 6

### Section 3: Artifact Conflict Analysis
- [x] 3.1 PRD checked: FR-9 addition needed
- [x] 3.2 Architecture reviewed: New `customer` schema required
- [x] 3.3 UI/UX examined: No UI changes (BI layer only)
- [x] 3.4 Other artifacts reviewed: Epic index needs update

### Section 4: Path Forward Evaluation
- [x] 4.1 Direct Adjustment: Not viable (scope too large)
- [x] 4.2 Potential Rollback: Not applicable (no existing work)
- [x] 4.3 MVP Review: Not needed (MVP unchanged)
- [x] 4.4 Selected approach: **New Epic 7**

### Section 5: Sprint Change Proposal Components
- [x] 5.1 Issue summary created
- [x] 5.2 Impact documented
- [x] 5.3 Recommended path presented
- [x] 5.4 MVP impact defined: None
- [x] 5.5 Handoff plan established
