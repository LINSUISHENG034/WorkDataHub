# Customer MDM Backfill Analysis (客户主数据回填分析)

**Created:** 2026-02-10
**Last Updated:** 2026-02-11
**Status:** In Progress - Business Logic Confirmed
**Author:** Development Team

---

## 1. Background (背景)

### 1.1 Current Domain Structure

| Domain | Database Table | Data Source | Backfill Status |
|--------|----------------|-------------|-----------------|
| `annuity_performance` | business."规模明细" | Business system details | ✅ Backfills to customer."年金客户" |
| `annuity_income` | business."收入明细" | Business system details | ✅ Backfills to customer."年金客户" |
| `annual_award` | customer."当年中标" | Manual collection | ❌ Not configured (to be added) |
| `annual_loss` | customer."当年流失" | Manual collection | ❌ Not configured (to be added) |

### 1.2 Data Characteristics

| Characteristic | annuity_performance / income | annual_award / loss |
|----------------|------------------------------|---------------------|
| **Data Source** | Business system generated | Manually collected lists |
| **Data Status** | Already occurred in system | Not yet reflected in system |
| **company_id** | ✅ Resolved via Enrichment | ✅ Has company_id field |
| **Data Quality** | 🟢 High (system data) | 🟡 Medium (manual data) |

---

## 2. Core Problem: `年金客户` Table Positioning

### 2.1 Current Issues

| Issue | Description |
|-------|-------------|
| **Semantic Confusion** | Table name implies "customers", but actually "companies related to annuity business" |
| **Missing Timeliness** | `年金客户类型=新客` lacks year context (2025 new ≠ 2026 new) |
| **Mixed Responsibilities** | Combines dimension data (name) + temporal status (new/award/churn) |

### 2.2 Recommended Repositioning

| Aspect | Current | Recommended |
|--------|---------|-------------|
| **Table Name** | `年金客户` | `年金关联公司` (or similar) |
| **Positioning** | Customer dimension table | Complete company_id collection for annuity business |
| **Scope** | Only from 规模/收入 | All sources: 规模/收入 + 中标/流失 |

### 2.3 Data Layer Separation

```
┌─────────────────────────────────────────────────────────────┐
│  Dimension Layer - Stable entity attributes                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  年金客户 → Rename to "年金关联公司"                     ││
│  │  • company_id (PK)                                      ││
│  │  • 客户名称, 客户简称                                    ││
│  │  • 主拓机构, 管理资格 (stable attributes)               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Fact Layer - Temporal status and measures                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  customer_plan_contract (Contract status + SCD Type2)   ││
│  │  • 新客/中标/流失 status + valid_from/valid_to          ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │  fct_customer_*_monthly (Monthly snapshots)             ││
│  │  • is_new_arrival, is_churned                           ││
│  │  • is_winning_this_year, is_loss_reported               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Confirmed Business Decisions

### Decision 1: company_id Collection Scope

| Data Source | Backfill to `年金客户` | Notes |
|-------------|------------------------|-------|
| 规模明细 | ✅ Yes | Already configured |
| 收入明细 | ✅ Yes | Already configured |
| 当年中标 | ✅ Yes | **To be configured** |
| 当年流失 | ✅ Yes | **To be configured** |

**Conclusion:** `年金客户` table collects company_id from ALL sources.

---

### Decision 2: Data Quality Layering

| Data Source | Quality Level | Impact Scope |
|-------------|---------------|--------------|
| 规模明细/收入明细 | 🟢 High (system data) | Affects `customer_plan_contract` |
| 当年中标/当年流失 | 🟡 Medium (manual data) | Only affects monthly snapshot flags |

**Conclusion:** Manual data does NOT affect contract records, only snapshot markers.

---

### Decision 3: Status Label Differentiation

| Source | Inflow Status | Outflow Status |
|--------|---------------|----------------|
| 规模明细 | **新到账** (is_new_arrival) | **已流失** (is_churned) |
| 中标/流失 | **新中标** (is_winning_this_year) | **申报流失** (is_loss_reported) |

---

### Decision 4: Time Scope

| Status Field | Time Scope |
|--------------|------------|
| `is_winning_this_year` | Calendar year (Jan-Dec) |
| `is_loss_reported` | Calendar year (Jan-Dec) |

---

### Decision 5: `is_churned` Evaluation Conditions

| Condition | Description |
|-----------|-------------|
| Disappeared from 规模明细 | Had record last month, no record this month |
| 期末资产规模 = 0 | Has record but AUM is zero |

**Operator:** OR (either condition triggers churned status)

---

## 4. Table Positioning & Functions

### 4.1 Core Tables Overview

| Table | Schema | Positioning | Data Source | Update Mechanism |
|-------|--------|-------------|-------------|------------------|
| `年金客户` | customer | Company dimension | FK Backfill | INSERT_MISSING |
| `customer_plan_contract` | customer | Contract relationships (SCD Type 2) | Post-ETL Hook | SCD Type 2 |
| `fct_customer_business_monthly_status` | customer | Monthly snapshot fact | Post-ETL Hook | UPSERT by month |
| `当年中标` | customer | Award records | ETL (annual_award) | DELETE_INSERT |
| `当年流失` | customer | Loss records | ETL (annual_loss) | DELETE_INSERT |
| `规模明细` | business | Business details | ETL (annuity_performance) | DELETE_INSERT |

### 4.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Source Layer                                    │
│  Excel Files                                                            │
│  ├── 规模收入数据.xlsx (规模明细/收入明细 sheets)                        │
│  └── 台账登记.xlsx (中标/流失 sheets)                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ETL Pipeline                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │annuity_      │  │annuity_      │  │annual_       │  │annual_       ││
│  │performance   │  │income        │  │award         │  │loss          ││
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘│
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Transaction Data Layer                               │
│  business.规模明细    business.收入明细    customer.当年中标  customer.当年流失│
└─────────────────────────────────────────────────────────────────────────┘
          │                 │                 │                 │
          └────────┬────────┘                 └────────┬────────┘
                   │                                   │
                   ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Master Data Layer                                    │
│                 customer.年金客户 (to be renamed)                        │
│                    ← FK Backfill from ALL sources                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Contract/Snapshot Layer                              │
│  customer_plan_contract          fct_customer_business_monthly_status   │
│  ← Post-ETL Hook (规模明细 only) ← Post-ETL Hook (all sources)          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Scenario Simulations

### Scenario A: Normal Award → Landing

| Month | 当年中标 | 规模明细 | 年金客户 | 合同表 | Monthly Snapshot |
|-------|----------|----------|----------|--------|------------------|
| Jan | ✅ Won | - | ✅ Backfill | - | `is_winning=T` |
| Mar | ✅ | ✅ First appear | Exists | ✅ Create | `is_winning=T, is_new_arrival=T` |
| Jun | ✅ | ✅ Continue | Exists | Exists | `is_winning=T` |

**Note:** Mar marks both statuses independently.

---

### Scenario B: Award Without Landing

| Month | 当年中标 | 规模明细 | 年金客户 | 合同表 | Monthly Snapshot |
|-------|----------|----------|----------|--------|------------------|
| Jan | ✅ Won | - | ✅ Backfill | - | `is_winning=T` |
| Dec | ✅ | - | Exists | - | `is_winning=T` |

**Note:** Full year won but no business data, only snapshot marker.

---

### Scenario C: Pure New Arrival (No Award Record)

| Month | 当年中标 | 规模明细 | Monthly Snapshot |
|-------|----------|----------|------------------|
| May | - | ✅ First appear | `is_new_arrival=T` |
| Jun | - | ✅ Continue | - |

---

### Scenario D: Reported Loss vs Actual Churn

| Month | 当年流失 | 规模明细 | 合同表 | Monthly Snapshot |
|-------|----------|----------|--------|------------------|
| Jun | ✅ Reported | ✅ Still has data | No change | `is_loss_reported=T` |
| Sep | ✅ | ❌ Disappeared | Close | `is_loss_reported=T, is_churned=T` |

**Note:** Jun reports loss, Sep actually churns - two statuses recorded independently.

---

### Scenario E: Churn by Zero AUM

| Month | 规模明细 | 期末资产规模 | Monthly Snapshot |
|-------|----------|--------------|------------------|
| May | ✅ Has record | 50,000,000 | - |
| Jun | ✅ Has record | 0 | `is_churned=T` |

**Note:** Record exists but AUM=0 triggers churn status.

---

## 6. Status Evaluation Framework Design

### 6.1 Design Goals

| Goal | Description |
|------|-------------|
| **Config-driven** | Evaluation rules defined in config files, not hardcoded |
| **Composable** | Support AND/OR condition combinations |
| **Extensible** | Easy to add new status types and conditions |
| **Traceable** | Record evaluation basis for audit |

### 6.2 Framework Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Config Layer (config/customer_status_rules.yml)            │
│  ├── status_definitions                                     │
│  ├── evaluation_rules                                       │
│  └── source_mappings                                        │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Rule Engine (StatusEvaluator)                              │
│  ├── Load config                                            │
│  ├── Parse condition expressions                            │
│  └── Execute evaluation logic                               │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Output Layer (fct_customer_business_monthly_status)        │
│  ├── Status field values                                    │
│  └── Evaluation basis (optional: JSONB audit field)         │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Config File Example

```yaml
# config/customer_status_rules.yml
schema_version: "1.0"

# Data source definitions
sources:
  annuity_performance:
    table: business."规模明细"
    key_fields: [company_id, product_line_code, snapshot_month]

  annual_award:
    table: customer."当年中标"
    key_fields: [company_id, 上报月份]

  annual_loss:
    table: customer."当年流失"
    key_fields: [company_id, 上报月份]

# Status definitions
status_definitions:
  is_new_arrival:
    description: "新到账 - First appearance in 规模明细"
    source: annuity_performance
    time_scope: monthly

  is_churned:
    description: "已流失 - Disappeared or zero AUM"
    source: annuity_performance
    time_scope: monthly

  is_winning_this_year:
    description: "新中标 - Has award record this year"
    source: annual_award
    time_scope: yearly

  is_loss_reported:
    description: "申报流失 - Has loss report this year"
    source: annual_loss
    time_scope: yearly

# Evaluation rules
evaluation_rules:
  is_new_arrival:
    conditions:
      - type: first_appearance
        compare_field: company_id
        scope: product_line_code

  is_churned:
    operator: OR
    conditions:
      - type: disappeared
        compare_field: company_id
        scope: product_line_code
      - type: field_equals
        field: 期末资产规模
        value: 0

  is_winning_this_year:
    conditions:
      - type: exists_in_year
        year_field: 上报月份
        match_field: company_id

  is_loss_reported:
    conditions:
      - type: exists_in_year
        year_field: 上报月份
        match_field: company_id
```

### 6.4 Condition Types

| Type | Description | Parameters |
|------|-------------|------------|
| `first_appearance` | First time appearing | compare_field, scope |
| `disappeared` | Gone (had last period, none this period) | compare_field, scope |
| `field_equals` | Field value equals | field, value |
| `field_gt` / `field_lt` | Field value comparison | field, value |
| `exists_in_year` | Record exists within year | year_field, match_field |

### 6.5 Extension Example

Adding "Strategic Customer" status in the future:

```yaml
is_strategic:
  description: "战略客户 - AUM exceeds threshold"
  conditions:
    - type: field_gt
      source: annuity_performance
      field: 期末资产规模
      value: 100000000  # 100M
```

---

## 7. Next Steps

### 7.1 Immediate Actions

- [ ] Confirm table rename: `年金客户` → `年金关联公司` (or alternative)
- [ ] Configure FK backfill for `annual_award` and `annual_loss`
- [ ] Update `config/data_sources.yml` to set `requires_backfill: true`

### 7.2 Schema Changes

- [ ] Design field restructuring for `年金客户` table
- [ ] Add new status fields to `fct_customer_business_monthly_status`
- [ ] Create Alembic migration scripts

### 7.3 Framework Implementation

- [ ] Create `config/customer_status_rules.yml`
- [ ] Implement StatusEvaluator rule engine
- [ ] Update Post-ETL hooks to use new framework

---

## Appendix

### A. Related Documentation

| Document | Path |
|----------|------|
| FK Backfill Config | `config/foreign_keys.yml` |
| Data Sources Config | `config/data_sources.yml` |
| Database Schema | `docs/database-schema-panorama.md` |
| Project Context | `docs/project-context.md` |

### B. Revision History

| Date | Changes |
|------|---------|
| 2026-02-10 | Initial draft with overlap scenarios |
| 2026-02-11 | Added confirmed business decisions, scenario simulations, status framework design |
| 2026-02-11 | Added existing implementation integration, single source of truth architecture |

---

## 7. Existing Implementation Integration

### 7.1 Current Status Field Logic (from codebase)

#### is_strategic (战略客户)

| Condition | Logic | Source |
|-----------|-------|--------|
| AUM Threshold | `total_aum >= 500,000,000` (5亿) | `strategic.py` |
| Top N | Top 10 per branch per product line | `common_ctes.sql` |
| Data Basis | Prior year December 规模明细 | `common_ctes.sql` |
| Ratchet Rule | Upgrade only (TRUE→FALSE blocked) | `contract_sync.py` |

#### is_existing (已客)

| Condition | Logic | Source |
|-----------|-------|--------|
| Criteria | Prior year December has asset records | `common_ctes.sql` |
| Condition | `期末资产规模 > 0` | `prior_year_dec` CTE |
| Granularity | Company + Plan + ProductLine | `common_ctes.sql` |

#### is_new (新客)

| Condition | Logic | Source |
|-----------|-------|--------|
| Derived Rule | `is_winning_this_year AND NOT is_existing` | `snapshot_refresh.py` |

#### contract_status (合约状态)

| Status | Condition | Source |
|--------|-----------|--------|
| 正常 | `期末资产规模 > 0 AND 12个月滚动供款 > 0` | `sync_insert.sql` |
| 停缴 | `期末资产规模 > 0 AND 12个月滚动供款 = 0` | `sync_insert.sql` |

### 7.2 Single Source of Truth Architecture

#### Problem with Current Dual-Table Design

| Issue | Description |
|-------|-------------|
| Data Inconsistency Risk | Two independent tables need synchronized maintenance |
| Granularity Mismatch | Some fields stored at wrong granularity level |
| Maintenance Overhead | Changes require updating both tables |

#### Recommended Architecture: Plan Table + Materialized View

```
┌─────────────────────────────────────────────────────────────┐
│  fct_customer_plan_monthly (Fact Table - Single Source)     │
│  PK: (snapshot_month, company_id, plan_code, product_line_code)
│                                                             │
│  Existing Fields:                                           │
│  • is_strategic        ← AUM threshold OR Top N             │
│  • is_existing         ← Prior year Dec has assets          │
│  • contract_status     ← 正常/停缴                          │
│  • aum_balance         ← Plan-level AUM                     │
│                                                             │
│  New Fields:                                                │
│  • is_new_arrival      ← First appearance in 规模明细       │
│  • is_churned          ← Disappeared OR AUM=0               │
│  • is_winning_this_year ← EXISTS in 当年中标                │
│  • is_loss_reported    ← EXISTS in 当年流失                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼ (Materialized View Aggregation)
┌─────────────────────────────────────────────────────────────┐
│  v_customer_product_line_monthly (Materialized View)        │
│  PK: (snapshot_month, company_id, product_line_code)        │
│                                                             │
│  Aggregated Fields:                                         │
│  • is_strategic         ← BOOL_OR(is_strategic)             │
│  • is_existing          ← BOOL_OR(is_existing)              │
│  • is_new               ← BOOL_OR(is_winning) AND           │
│                           NOT BOOL_OR(is_existing)          │
│  • is_winning_this_year ← BOOL_OR(is_winning_this_year)     │
│  • is_churned_any       ← BOOL_OR(is_churned)               │
│  • is_loss_reported_any ← BOOL_OR(is_loss_reported)         │
│  • aum_total            ← SUM(aum_balance)                  │
│  • plan_count           ← COUNT(DISTINCT plan_code)         │
└─────────────────────────────────────────────────────────────┘
```

---
