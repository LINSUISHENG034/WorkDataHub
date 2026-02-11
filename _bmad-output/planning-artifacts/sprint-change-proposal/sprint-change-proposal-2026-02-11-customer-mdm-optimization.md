# Sprint Change Proposal: Customer MDM Optimization

**Date:** 2026-02-11
**Author:** SM Agent (Correct Course Workflow)
**Status:** Pending Approval
**Epic:** 7.6 (Customer Master Data Management)

---

## 1. Issue Summary

### 1.1 Problem Statement

Customer MDM implementation in Epic 7.6 has identified optimization opportunities through business analysis:

| Issue | Description | Impact |
|-------|-------------|--------|
| **Semantic Confusion** | `年金客户` table name implies "customers" but actually represents "companies related to annuity business" | Data modeling clarity |
| **Incomplete Data Sources** | `annual_award` and `annual_loss` tables not configured for FK backfill to `年金客户` | Missing customer records |
| **Hardcoded Status Logic** | Status evaluation rules embedded in code, not configuration-driven | Maintainability |

### 1.2 Discovery Context

- **Trigger:** Business analysis document `docs/business-background/customer-mdm-backfill-analysis.md`
- **Timing:** During Epic 7.6 implementation (Story 7.6-11 in progress)
- **Evidence:** Documented in analysis with scenario simulations and confirmed business decisions

### 1.3 Current State

| Component | Status |
|-----------|--------|
| Dual-table design (Story 7.6-16) | ✅ Implemented |
| SCD Type 2 sync (Story 7.6-12) | ✅ Implemented |
| Annual cutover logic (Story 7.6-14) | ✅ Implemented |
| Ratchet rule (Story 7.6-15) | ✅ Implemented |
| FK backfill for annual_award/loss | ❌ Not configured |
| Config-driven status rules | ❌ Not implemented |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Action Required |
|------|--------|-----------------|
| **Epic 7.6** (Current) | Scope extension | Add 3 new stories |
| **Epic 8** (Backlog) | No direct impact | Continue waiting for 7.6 |

### 2.2 Artifact Conflicts

| Artifact | Conflict Level | Changes Needed |
|----------|----------------|----------------|
| PRD | None | N/A (no standalone PRD) |
| Architecture (Decision #12) | Compatible | Extend with new hooks |
| `config/foreign_keys.yml` | Extension needed | Add annual_award/loss configs |
| `config/customer_status_rules.yml` | New file | Create status evaluation rules |

### 2.3 Technical Impact

| Area | Impact |
|------|--------|
| Database Schema | Minor - table rename migration |
| ETL Pipeline | Minor - add FK backfill hooks |
| Post-ETL Hooks | Minor - extend registry |
| BI Layer | None - views auto-update |

---

## 3. Recommended Approach

### 3.1 Selected Path: Direct Adjustment

**Rationale:**

| Factor | Assessment |
|--------|------------|
| Implementation Effort | Medium (3 new stories) |
| Technical Risk | Low (extends existing patterns) |
| Team Impact | Low (no direction change) |
| Long-term Maintainability | High (config-driven design) |
| Business Value | High (complete customer lifecycle tracking) |

### 3.2 Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| Rollback | Not viable | Completed work is correct |
| MVP Review | Not needed | This is incremental optimization |

---

## 4. Detailed Change Proposals

### 4.1 New Stories for Epic 7.6

#### Story 7.6-17: FK Backfill Configuration for Annual Award/Loss

**Objective:** Configure FK backfill for `annual_award` and `annual_loss` domains to populate `年金客户` table.

**Changes:**

```yaml
# config/foreign_keys.yml - ADD sections

domains:
  annual_award:
    foreign_keys:
      - name: "fk_customer"
        source_column: "company_id"
        target_table: "年金客户"
        target_key: "company_id"
        target_schema: "customer"
        mode: "insert_missing"
        backfill_columns:
          - source: "company_id"
            target: "company_id"
          - source: "客户全称"
            target: "客户名称"
            optional: true

  annual_loss:
    foreign_keys:
      - name: "fk_customer"
        source_column: "company_id"
        target_table: "年金客户"
        target_key: "company_id"
        target_schema: "customer"
        mode: "insert_missing"
        backfill_columns:
          - source: "company_id"
            target: "company_id"
          - source: "客户全称"
            target: "客户名称"
            optional: true
```

**Effort:** Low (configuration only)

---

#### Story 7.6-18: Config-Driven Status Evaluation Framework

**Objective:** Implement configuration-driven status evaluation rules for customer monthly snapshots.

**New File:** `config/customer_status_rules.yml`

```yaml
schema_version: "1.0"

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

evaluation_rules:
  is_churned:
    operator: OR
    conditions:
      - type: disappeared
        compare_field: company_id
        scope: product_line_code
      - type: field_equals
        field: 期末资产规模
        value: 0
```

**Implementation:**
- Create `StatusEvaluator` class in `src/work_data_hub/customer_mdm/status_evaluator.py`
- Load rules from config file
- Integrate with `snapshot_refresh.py`

**Effort:** Medium

---

#### Story 7.6-19: Table Rename Migration (Optional)

**Objective:** Rename `年金客户` to `年金关联公司` for semantic clarity.

**Migration Script:**

```sql
-- Alembic migration
ALTER TABLE customer."年金客户" RENAME TO "年金关联公司";

-- Update FK constraints
ALTER TABLE customer.customer_plan_contract
  DROP CONSTRAINT fk_contract_company,
  ADD CONSTRAINT fk_contract_company
    FOREIGN KEY (company_id) REFERENCES customer."年金关联公司"(company_id);

-- Create alias view for backward compatibility
CREATE VIEW customer."年金客户" AS SELECT * FROM customer."年金关联公司";
```

**Effort:** Low
**Risk:** Low (alias view maintains compatibility)

---

### 4.2 Architecture Document Updates

**File:** `docs/architecture/architectural-decisions.md`

**Section:** Decision #12 - Customer MDM Post-ETL Hook Architecture

**Changes:**
- Add `annual_award` and `annual_loss` to data sources
- Document FK backfill hooks for these domains
- Reference new `customer_status_rules.yml` config

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

**Classification:** **Minor**

**Rationale:** Changes extend existing patterns without architectural restructuring.

### 5.2 Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Dev Agent** | Implement stories 7.6-17, 7.6-18, 7.6-19 |
| **SM Agent** | Update sprint-status.yaml with new stories |
| **Architect** | Review architecture changes (optional) |

### 5.3 Success Criteria

| Criteria | Measurement |
|----------|-------------|
| FK backfill works for annual_award/loss | company_id records appear in 年金客户 |
| Status evaluation is config-driven | Rules loaded from YAML, not hardcoded |
| Table rename complete (if approved) | Migration runs without errors |
| All existing tests pass | CI pipeline green |

### 5.4 Timeline Impact

| Item | Estimate |
|------|----------|
| Story 7.6-17 | 0.5 day |
| Story 7.6-18 | 1-2 days |
| Story 7.6-19 | 0.5 day |
| **Total** | 2-3 days |

---

## 6. Appendix

### A. Related Documents

| Document | Path |
|----------|------|
| Business Analysis | `docs/business-background/customer-mdm-backfill-analysis.md` |
| Contract Specification | `docs/specific/customer-mdm/customer-plan-contract-specification.md` |
| Snapshot Specification | `docs/specific/customer-mdm/customer-monthly-snapshot-specification.md` |
| FK Config | `config/foreign_keys.yml` |
| Architecture Decisions | `docs/architecture/architectural-decisions.md` |

### B. Checklist Completion Summary

| Section | Status |
|---------|--------|
| 1. Understand Trigger | ✅ Done |
| 2. Epic Impact | ✅ Done |
| 3. Artifact Conflicts | ✅ Done |
| 4. Path Forward | ✅ Done (Direct Adjustment) |
| 5. Proposal Components | ✅ Done |
| 6. Final Review | Pending User Approval |

---

**Document Generated:** 2026-02-11
**Workflow:** correct-course
**Mode:** Incremental
