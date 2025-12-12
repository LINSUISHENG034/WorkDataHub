# Foreign Key Constraint Problem Analysis

**Created:** 2025-12-11
**Status:** Under Discussion
**Triggered By:** Story 6.1 Development - `annuity_performance` Domain

---

## 1. Problem Statement

### 1.1 Background

After completing Story 6.1, the `annuity_performance` domain has a relatively complete functional architecture. However, when executing data writes to the target database, foreign key constraints may cause write failures if referenced records don't exist in parent tables.

### 1.2 Core Issue

**Scenario:** When fact data contains foreign key values that don't exist in the referenced parent tables, database INSERT operations fail with FK constraint violations.

**Impact:**
- Significantly reduces data processing automation level
- Requires manual intervention to resolve FK violations
- Blocks pipeline execution until parent records are created

### 1.3 Business Context

In complex business scenarios, it's common for child tables to contain new key values that weren't pre-planned. This is a widespread issue affecting all domains with foreign key relationships.

---

## 2. Current Architecture Analysis

### 2.1 Existing Backfill Mechanism

The project has an existing `reference_backfill` domain that handles FK dependencies:

**Location:** `src/work_data_hub/domain/reference_backfill/service.py`

**Current Coverage:**
| Reference Table | Derive Function | Status |
|----------------|-----------------|--------|
| 年金计划 (Plans) | `derive_plan_candidates()` | ✅ Covered |
| 组合计划 (Portfolios) | `derive_portfolio_candidates()` | ✅ Covered |
| 产品线 (Product Lines) | - | ❌ Not Covered |
| 组织架构 (Organization) | - | ❌ Not Covered |

### 2.2 Pipeline Execution Order (FK-Safe)

```
processed_data
    → derive_plan_refs_op        # Derive plan candidates
    → derive_portfolio_refs_op   # Derive portfolio candidates
    → backfill_refs_op           # Backfill reference tables
    → gate_after_backfill        # Dependency gate ⭐
    → load_op                    # Load fact data
```

**Key Mechanism:** `gate_after_backfill` ensures fact data loading cannot start until reference backfill completes.

### 2.3 Backfill Modes

- `insert_missing`: Insert new reference records that don't exist
- `fill_null_only`: Update NULL fields in existing records

### 2.4 Configuration (data_sources.yml)

```yaml
refs:
  plans:
    table: "年金计划"
    key: "年金计划号"
  portfolios:
    table: "组合计划"
    key: "组合代码"
```

---

## 3. Gap Analysis

### 3.1 Foreign Keys in 规模明细 (Fact Table)

From MySQL migration scripts (`scripts/migrations/mysql_to_postgres_sync/README.md`):

| FK Constraint | Reference Table | Current Backfill |
|--------------|-----------------|------------------|
| `fk_规模明细_年金计划` | 年金计划 | ✅ Covered |
| `fk_规模明细_组合计划` | 组合计划 | ✅ Covered |
| `fk_规模明细_产品线` | 产品线 | ❌ **Gap** |
| `fk_规模明细_组织架构` | 组织架构 | ❌ **Gap** |

**Coverage:** 2/4 (50%)

### 3.2 Current Limitations

1. **Partial FK Coverage:** Only 2 out of 4 foreign keys are handled
2. **Hardcoded Domain:** `domain = "annuity_performance"  # TODO: pass from discover_files_op`
3. **No Multi-Domain Support:** Other domains (e.g., `annuity_income`) cannot use this mechanism
4. **Manual Code Required:** Each new FK requires a dedicated `derive_*_candidates()` function

### 3.3 Scalability Concerns

As the system grows:
- More domains will be added (Epic 9: Growth Domains)
- Each domain may have different FK relationships
- Current approach leads to code bloat and maintenance burden

---

## 4. Requirements for Solution

### 4.1 Functional Requirements

1. **Multi-FK Support:** Handle multiple foreign keys per fact table simultaneously
2. **Domain Agnostic:** Work with any domain without code changes
3. **Configuration Driven:** New FKs should only require configuration updates
4. **Dependency Aware:** Respect FK dependencies (e.g., 组合计划 → 年金计划)

### 4.2 Non-Functional Requirements

1. **Performance:** Efficient batch processing for large datasets
2. **Maintainability:** Minimal code changes when adding new domains/FKs
3. **Backward Compatibility:** Support existing domains during migration
4. **Observability:** Clear logging of backfill operations and results

---

## 5. Solution Options Evaluated

| Option | Description | Multi-FK | New Domain Friendly | Complexity | Recommendation |
|--------|-------------|----------|---------------------|------------|----------------|
| A | Extend existing mechanism | ⚠️ Manual | ❌ Code bloat | Low | ⭐⭐ |
| B | Generic backfill framework | ✅ Config-driven | ✅ Config only | Medium | ⭐⭐⭐⭐⭐ |
| C | Database-level (DEFERRABLE) | ✅ Auto | ✅ No changes | Low | ⭐⭐ |
| D | Pre-load reference tables | ⚠️ Can't cover new values | ⚠️ Extra process | Medium | ⭐⭐⭐ |

**Selected:** Option B - Configuration-Driven Generic Backfill Framework

---

## 6. References

- **Existing Backfill Service:** `src/work_data_hub/domain/reference_backfill/service.py`
- **Pipeline Jobs:** `src/work_data_hub/orchestration/jobs.py:100-118`
- **Backfill Ops:** `src/work_data_hub/orchestration/ops.py:783-1062`
- **MySQL FK Definitions:** `scripts/migrations/mysql_to_postgres_sync/README.md:101-119`
- **Data Sources Config:** `config/data_sources.yml`

---

## 7. Next Steps

1. Review recommended solution in `recommended-solution.md`
2. Discuss implementation approach
3. Create Sprint Change Proposal if approved
4. Implement in appropriate Epic/Story
