# Sprint Change Proposal: Customer Plan Contract Name Fields Enhancement

> **Date**: 2026-02-05
> **Status**: Pending Approval
> **Triggered By**: User Request (可读性优化)
> **Scope Classification**: Minor
> **Related Document**: [customer-plan-contract-specification.md](../../specific/customer-mdm/customer-plan-contract-specification.md)

---

## 1. Issue Summary

### 1.1 Problem Statement

The `customer.customer_plan_contract` table currently stores only ID/code references (`company_id`, `plan_code`) without human-readable names. This requires JOIN operations for every query that needs to display customer or plan names, reducing query convenience and BI report readability.

### 1.2 Discovery Context

- **When**: User request for readability enhancement
- **How**: Party Mode multi-agent discussion and analysis
- **Participants**: BMad Master, Mary (Analyst), Winston (Architect), Amelia (Dev), Murat (TEA)

### 1.3 Current State Analysis

**Current Table Structure**:

| Field | Type | Readable | Source |
|-------|------|----------|--------|
| `company_id` | VARCHAR | ❌ ID only | `customer.年金客户` |
| `plan_code` | VARCHAR | ❌ Code only | `mapping.年金计划` |
| `product_line_code` | VARCHAR(20) | ❌ Code only | `mapping.产品线` |
| `product_line_name` | VARCHAR(50) | ✅ **Already redundant** | `mapping.产品线.产品线` |

**Design Pattern Observation**: The table already uses `product_line_name` as a redundant field for query convenience, establishing a precedent for denormalization.

### 1.4 Proposed Enhancement

Add two new redundant fields:

| New Field | Type | Source | Purpose |
|-----------|------|--------|---------|
| `customer_name` | VARCHAR(200) | `customer.年金客户.客户名称` | Display customer name |
| `plan_name` | VARCHAR(200) | `mapping.年金计划.计划全称` | Display plan full name |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| Customer MDM | ⚠️ Minor | Schema enhancement, no logic change |
| Future Epics | ❌ None | No downstream epic dependencies affected |

### 2.2 Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 7.6-6 | Done | Table structure enhancement |
| 7.6-7 | Done | May benefit from new fields |
| 7.6-8 | Done | BI reports can use new fields directly |
| **7.6-13** | **NEW** | **Add name fields enhancement** |

### 2.3 Artifact Conflicts

| Artifact | Conflict | Action Needed |
|----------|----------|---------------|
| PRD | ❌ None | Enhancement, not requirement change |
| Architecture | ⚠️ Minor | Document denormalization pattern |
| Specification | ⚠️ Minor | Add new fields documentation |
| Alembic Migration | ⚠️ Minor | Modify existing script (from-scratch) |

### 2.4 Technical Impact

| Area | Impact | Description |
|------|--------|-------------|
| `008_create_customer_plan_contract.py` | 🟡 Moderate | Add new columns + triggers |
| `seed_customer_plan_contract.py` | 🟡 Moderate | Add new fields population |
| `sync_insert.sql` | 🟡 Moderate | Add new fields to INSERT |
| Database Schema | 🟡 Moderate | ALTER TABLE for existing DB |
| Seed Data | 🟡 Moderate | Export to `config/seeds/002/` |

### 2.5 Data Flow

```
┌─────────────────────┐                    ┌──────────────────────────────┐
│ customer.年金客户    │───(company_id)───→│ customer.customer_plan_contract │
│ (客户名称)          │    Trigger 1       │ (customer_name)               │
└─────────────────────┘                    └──────────────────────────────┘

┌─────────────────────┐                    ┌──────────────────────────────┐
│ mapping.年金计划     │───(年金计划号)───→│ customer.customer_plan_contract │
│ (计划全称)          │    Trigger 2       │ (plan_name)                   │
└─────────────────────┘                    └──────────────────────────────┘
```

---

## 3. Recommended Approach

### 3.1 Selected Path: Direct Enhancement

**Approach**: Add new Story 7.6-13 to implement name fields enhancement.

**Rationale**:
1. **Design Consistency**: Follows existing `product_line_name` redundancy pattern
2. **Query Performance**: Eliminates JOIN operations for common queries
3. **BI Readability**: Direct name display without lookup
4. **Low Risk**: Additive change, no existing functionality affected

### 3.2 User Decisions

| Decision Item | User Choice |
|---------------|-------------|
| Plan name field | `计划全称` (full name) |
| Sync triggers | ✅ Required (auto-sync on dimension change) |
| NOT NULL constraint | ❌ Not required (nullable) |
| Alembic strategy | Modify original script (from-scratch) |
| Existing DB update | Direct SQL script |
| Seed data location | `config/seeds/002/customer_plan_contract.dump` |

### 3.3 Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| Create View | ⚠️ Viable | Adds maintenance overhead, slightly lower performance |
| JOIN-only queries | ❌ Not Recommended | Inconsistent with existing pattern |
| New Alembic migration | ❌ Not Recommended | User prefers from-scratch approach |

### 3.4 Effort and Risk Assessment

| Metric | Value |
|--------|-------|
| **Risk Level** | Low |
| **Timeline Impact** | Minimal |
| **Rollback Complexity** | Low (columns can be dropped) |

---

## 4. Detailed Change Proposals

### 4.1 Story Changes

#### NEW Story: 7.6-13 Name Fields Enhancement

```
Story: [7.6-13] Customer Plan Contract Name Fields Enhancement
Section: NEW STORY

Goal: Add customer_name and plan_name redundant fields for query convenience

Acceptance Criteria:
- AC-1: New fields added to table schema
- AC-2: Sync triggers created for dimension table changes
- AC-3: Existing data populated with correct names
- AC-4: Seed data exported to config/seeds/002/
- AC-5: All sync operations populate new fields

Tasks:
- Task 1: Modify Alembic migration script (008)
- Task 2: Create SQL script for existing database
- Task 3: Update seed_customer_plan_contract.py
- Task 4: Update sync_insert.sql
- Task 5: Create dimension sync triggers
- Task 6: Export seed data to config/seeds/002/
- Task 7: Update specification document

Priority: P1 (Medium)
```

### 4.2 Schema Changes

#### 4.2.1 New Columns

```sql
-- Add to customer.customer_plan_contract
customer_name VARCHAR(200),    -- From customer.年金客户.客户名称
plan_name VARCHAR(200)         -- From mapping.年金计划.计划全称
```

#### 4.2.2 New Indexes

```sql
-- Optional: Index for name-based queries
CREATE INDEX idx_contract_customer_name
    ON customer.customer_plan_contract(customer_name);
CREATE INDEX idx_contract_plan_name
    ON customer.customer_plan_contract(plan_name);
```

### 4.3 Trigger Design

#### 4.3.1 Customer Name Sync Trigger

```sql
-- Trigger: Sync customer_name when 年金客户.客户名称 changes
CREATE OR REPLACE FUNCTION customer.sync_contract_customer_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
        UPDATE customer.customer_plan_contract
        SET customer_name = NEW.客户名称,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = NEW.company_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_contract_customer_name
AFTER UPDATE OF 客户名称 ON customer."年金客户"
FOR EACH ROW
EXECUTE FUNCTION customer.sync_contract_customer_name();
```

#### 4.3.2 Plan Name Sync Trigger

```sql
-- Trigger: Sync plan_name when 年金计划.计划全称 changes
CREATE OR REPLACE FUNCTION customer.sync_contract_plan_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.计划全称 IS DISTINCT FROM NEW.计划全称 THEN
        UPDATE customer.customer_plan_contract
        SET plan_name = NEW.计划全称,
            updated_at = CURRENT_TIMESTAMP
        WHERE plan_code = NEW.年金计划号;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_contract_plan_name
AFTER UPDATE OF 计划全称 ON mapping."年金计划"
FOR EACH ROW
EXECUTE FUNCTION customer.sync_contract_plan_name();
```

---

## 5. File Changes Summary

### 5.1 Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `io/schema/migrations/versions/008_create_customer_plan_contract.py` | Modify | Add columns + triggers |
| `scripts/seed_data/seed_customer_plan_contract.py` | Modify | Add new fields population |
| `src/work_data_hub/customer_mdm/sql/sync_insert.sql` | Modify | Add new fields to INSERT |
| `docs/specific/customer-mdm/customer-plan-contract-specification.md` | Modify | Document new fields |

### 5.2 Files to Create

| File | Purpose |
|------|---------|
| `scripts/migrations/add_contract_name_fields.sql` | ALTER existing database |
| `config/seeds/002/customer_plan_contract.dump` | Seed data export |

---

## 6. Implementation Handoff

### 6.1 Scope Classification

**Classification**: Minor

**Rationale**:
- Additive schema change (no breaking changes)
- Follows existing design pattern
- Limited file scope
- No architectural changes

### 6.2 Success Criteria

- [ ] New columns `customer_name` and `plan_name` added to schema
- [ ] Sync triggers created and functional
- [ ] Existing data populated correctly
- [ ] Seed data exported to `config/seeds/002/`
- [ ] All sync operations populate new fields
- [ ] Specification document updated
- [ ] All existing tests pass

### 6.3 Recommended Implementation Order

1. Modify Alembic migration script (008)
2. Create SQL script for existing database ALTER
3. Update `sync_insert.sql` with new fields
4. Update `seed_customer_plan_contract.py`
5. Run ALTER script on existing database
6. Backfill existing records with names
7. Export seed data to `config/seeds/002/`
8. Update specification document

---

## 7. Appendix

### 7.1 Related Files

| File | Path | Purpose |
|------|------|---------|
| Specification | `docs/specific/customer-mdm/customer-plan-contract-specification.md` | Design document |
| Alembic Migration | `io/schema/migrations/versions/008_create_customer_plan_contract.py` | Schema creation |
| Seed Script | `scripts/seed_data/seed_customer_plan_contract.py` | Data seeding |
| Sync SQL | `src/work_data_hub/customer_mdm/sql/sync_insert.sql` | INSERT logic |
| Seeds README | `config/seeds/README.md` | Seed data documentation |

### 7.2 Source Tables Reference

| Table | Key Field | Name Field | Records |
|-------|-----------|------------|---------|
| `customer.年金客户` | `company_id` | `客户名称` | ~10,436 |
| `mapping.年金计划` | `年金计划号` | `计划全称` | ~1,158 |

### 7.3 Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-05 | Initial proposal from Party Mode discussion |
