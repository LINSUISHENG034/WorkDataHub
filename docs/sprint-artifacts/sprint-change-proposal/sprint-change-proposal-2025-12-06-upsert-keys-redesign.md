# Sprint Change Proposal: Story 5.6.3 Upsert Keys Redesign

**Date:** 2025-12-06
**Triggered By:** Story 5.6.3 Implementation Review
**Status:** Draft
**Scope Classification:** Moderate

---

## Section 1: Issue Summary

### Problem Statement

Story 5.6.3 (Domain Upsert Keys Configuration) implemented an **UPSERT (ON CONFLICT DO UPDATE)** mechanism that is fundamentally incompatible with the business data model for `annuity_performance` and `annuity_income` domains.

These domains contain **business detail records** (明细数据) where the same combination of keys can have multiple records. The UPSERT approach requires UNIQUE constraints on the key columns, which violates the data model.

### Context

- **Discovery Time:** 2025-12-06
- **Discovery Phase:** Story 5.6.3 Code Review
- **Impact on MVP:** None - MVP completed, this is post-MVP optimization
- **Root Cause:** Misunderstanding of Legacy `update_based_on_field` mechanism

### Evidence

**Legacy Mechanism Analysis (`legacy/annuity_hub/data_handler/data_processor.py`):**

```python
def delete_existing_records(self, db, data, fields):
    """根据指定字段的唯一组合，从数据库的指定表中删除记录"""
    field_list = fields.split("+")  # e.g., "月度+业务类型" → ["月度", "业务类型"]
    unique_combinations = get_unique_combinations(data, field_list)
    db.delete_rows_by_criteria(table_name=self.target_table, criteria=unique_combinations, fields=field_list)

def _import(self, db):
    if self.update_based_on_field:
        self.delete_existing_records(db, data, self.update_based_on_field)  # DELETE first
    db.import_data(table_name=self.target_table, data=data)  # Then INSERT
```

**Legacy is DELETE + INSERT, NOT UPSERT!**

**Legacy `annuity_mapping` Configuration:**

| Domain | `update_based_on_field` | Meaning |
|--------|------------------------|---------|
| 规模明细 (annuity_performance) | `月度+业务类型` | Delete all records matching month+business_type, then insert |
| 收入明细 (annuity_income) | `月度` | Delete all records matching month, then insert |

**Story 5.6.3 Implementation (Incorrect):**

| Domain | `DEFAULT_UPSERT_KEYS` | Problem |
|--------|----------------------|---------|
| annuity_performance | `["月度", "计划代码", "组合代码", "company_id"]` | Requires UNIQUE constraint; data has duplicates |
| annuity_income | `["月度", "计划号", "组合代码", "company_id"]` | Requires UNIQUE constraint; data has duplicates |

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 5.6 | In Progress | Story 5.6.3 needs redesign |
| Epic 6+ | Backlog | No impact |

### Artifact Conflicts

| Artifact | Conflict | Action Needed |
|----------|----------|---------------|
| `annuity_performance/service.py` | `DEFAULT_UPSERT_KEYS` incorrect | Replace with refresh mode config |
| `annuity_income/service.py` | `DEFAULT_UPSERT_KEYS` incorrect | Replace with refresh mode config |
| `20251206_000001_add_upsert_constraints.py` | UNIQUE constraints invalid for detail tables | Rollback migration |
| `docs/guides/domain-development-guide.md` | Documents only UPSERT pattern | Add refresh mode documentation |

### Code Impact

**Files requiring modification:**

| File | Change Type | Estimated LOC |
|------|-------------|---------------|
| `io/loader/warehouse_loader.py` | Add `load_with_refresh()` method | +40 |
| `domain/annuity_performance/service.py` | Replace upsert with refresh config | ~15 |
| `domain/annuity_income/service.py` | Replace upsert with refresh config | ~15 |
| `io/schema/migrations/versions/20251206_000001_*.py` | Delete or modify | -74 |
| `docs/guides/domain-development-guide.md` | Add refresh mode section | +80 |

---

## Section 3: Recommended Approach

### Selected Path: Option 1 - Direct Adjustment with Architecture Enhancement

**Rationale:**
1. `warehouse_loader.py` already has `load()` function supporting `delete_insert` mode (lines 992-1192)
2. Minimal new code needed - wrap existing functionality
3. Preserves UPSERT capability for future aggregate tables
4. Maintains backward compatibility

### Effort and Risk Assessment

| Item | Effort | Risk | Notes |
|------|--------|------|-------|
| Add `load_with_refresh()` to WarehouseLoader | 1 hour | Low | Wraps existing `load()` function |
| Update domain services | 30 min | Low | Config change only |
| Rollback migration | 15 min | Low | Delete file or add downgrade |
| Update documentation | 1 hour | Low | Add new section |
| **Total** | **~3 hours** | **Low** | |

### Alternatives Considered

| Option | Evaluation | Decision |
|--------|------------|----------|
| Option 2: Rollback Story 5.6.3 completely | Loses UPSERT capability for future use | Rejected |
| Option 3: Keep UPSERT, change data model | Would require aggregating detail records | Rejected - violates business requirements |

---

## Section 4: Detailed Change Proposals

### Change 1: Add `load_with_refresh()` Method to WarehouseLoader

**File:** `src/work_data_hub/io/loader/warehouse_loader.py`

**Approach:** Add a new method that wraps the existing `load()` function with DataFrame support.

```python
def load_with_refresh(
    self,
    df: pd.DataFrame,
    table: str,
    schema: str = "public",
    refresh_keys: List[str],
) -> LoadResult:
    """
    Load data using DELETE + INSERT pattern (Legacy-compatible refresh mode).

    This mode deletes all existing records matching the refresh_keys combinations
    in the input data, then inserts all new records. Suitable for detail tables
    where the same key combination can have multiple records.

    Args:
        df: DataFrame to load
        table: Target table name
        schema: Database schema
        refresh_keys: Columns defining the refresh scope (Legacy: update_based_on_field)

    Returns:
        LoadResult with deleted and inserted counts

    Example:
        # Refresh all records for month=202401 and business_type=受托
        loader.load_with_refresh(
            df,
            table="annuity_performance_NEW",
            refresh_keys=["月度", "业务类型", "计划类型"],
        )
    """
    # Implementation wraps existing load() function
    ...
```

**Rationale:**
- Reuses existing, tested `load()` function
- Clear API distinction: `load_dataframe()` for UPSERT, `load_with_refresh()` for DELETE+INSERT
- Maintains backward compatibility

---

### Change 2: Update Domain Service Configuration

**File:** `src/work_data_hub/domain/annuity_performance/service.py`

**OLD:**
```python
# Default upsert keys for this domain (month + plan + portfolio + company)
DEFAULT_UPSERT_KEYS = ["月度", "计划代码", "组合代码", "company_id"]
```

**NEW:**
```python
# =============================================================================
# Data Loading Configuration
# =============================================================================
# This domain uses REFRESH mode (DELETE + INSERT) because it contains detail
# records where the same key combination can have multiple rows.
#
# UPSERT mode (ON CONFLICT DO UPDATE) is NOT suitable for detail tables.
# UPSERT is only appropriate for aggregate tables with unique key combinations.
#
# Legacy equivalent: annuity_mapping.update_based_on_field = "月度+业务类型"
# =============================================================================

# Enable/disable UPSERT mode (requires UNIQUE constraint on upsert_keys)
ENABLE_UPSERT_MODE = False  # Detail table - use refresh mode instead

# UPSERT keys (only used when ENABLE_UPSERT_MODE = True)
# For aggregate tables with unique records per key combination
DEFAULT_UPSERT_KEYS: Optional[List[str]] = None

# REFRESH keys (used when ENABLE_UPSERT_MODE = False)
# Defines scope for DELETE before INSERT (Legacy: update_based_on_field)
DEFAULT_REFRESH_KEYS = ["月度", "业务类型", "计划类型"]
```

**File:** `src/work_data_hub/domain/annuity_income/service.py`

**Same pattern with:**
```python
ENABLE_UPSERT_MODE = False
DEFAULT_UPSERT_KEYS: Optional[List[str]] = None
DEFAULT_REFRESH_KEYS = ["月度", "业务类型", "计划类型"]
```

---

### Change 3: Update Service Function Logic

**File:** `src/work_data_hub/domain/annuity_performance/service.py`

**OLD (lines 70-76):**
```python
actual_upsert_keys = upsert_keys if upsert_keys is not None else DEFAULT_UPSERT_KEYS
load_result = warehouse_loader.load_dataframe(
    dataframe,
    table=table_name,
    schema=schema,
    upsert_keys=actual_upsert_keys,
)
```

**NEW:**
```python
if ENABLE_UPSERT_MODE:
    # UPSERT mode: ON CONFLICT DO UPDATE (for aggregate tables)
    actual_upsert_keys = upsert_keys if upsert_keys is not None else DEFAULT_UPSERT_KEYS
    load_result = warehouse_loader.load_dataframe(
        dataframe,
        table=table_name,
        schema=schema,
        upsert_keys=actual_upsert_keys,
    )
else:
    # REFRESH mode: DELETE + INSERT (for detail tables)
    actual_refresh_keys = refresh_keys if refresh_keys is not None else DEFAULT_REFRESH_KEYS
    load_result = warehouse_loader.load_with_refresh(
        dataframe,
        table=table_name,
        schema=schema,
        refresh_keys=actual_refresh_keys,
    )
```

---

### Change 4: Rollback Database Migration

**File:** `io/schema/migrations/versions/20251206_000001_add_upsert_constraints.py`

**Action:** Delete this file or modify to remove UNIQUE constraints for detail tables.

**Rationale:** UNIQUE constraints are incompatible with detail tables that have multiple records per key combination.

---

### Change 5: Update Domain Development Guide

**File:** `docs/guides/domain-development-guide.md`

**Add new section after "UPSERT_KEYS Configuration":**

```markdown
### Data Loading Mode Configuration

WorkDataHub supports two data loading modes. Choose based on your table type:

#### Mode 1: REFRESH Mode (DELETE + INSERT) - For Detail Tables

Use this mode when:
- Table contains **detail records** (明细数据)
- Same key combination can have **multiple rows**
- You want to **replace all records** matching certain criteria

**Configuration:**
```python
# service.py
ENABLE_UPSERT_MODE = False  # Use refresh mode

# Keys defining refresh scope (Legacy: update_based_on_field)
DEFAULT_REFRESH_KEYS = ["月度", "业务类型", "计划类型"]
```

**Behavior:**
1. Extract unique combinations of `refresh_keys` from input data
2. DELETE all existing records matching those combinations
3. INSERT all new records

**Example:** If input has records for `月度=202401, 业务类型=受托, 计划类型=企业年金`:
- All existing records with that combination are deleted
- All new records are inserted (even if >1 record per combination)

**Database Requirements:** No UNIQUE constraint needed.

#### Mode 2: UPSERT Mode (ON CONFLICT DO UPDATE) - For Aggregate Tables

Use this mode when:
- Table contains **aggregate records** (汇总数据)
- Each key combination has **exactly one row**
- You want to **update existing records** or insert new ones

**Configuration:**
```python
# service.py
ENABLE_UPSERT_MODE = True  # Use upsert mode

# Keys for conflict detection (must be UNIQUE in database)
DEFAULT_UPSERT_KEYS = ["月度", "计划代码"]
```

**Behavior:**
- INSERT new records
- UPDATE existing records when key conflict occurs

**Database Requirements:** UNIQUE constraint required on `upsert_keys`.

```sql
ALTER TABLE {table_name}
ADD CONSTRAINT uq_{table_name}_upsert_key
UNIQUE ({upsert_key_columns});
```

#### Quick Reference

| Table Type | Mode | Config | DB Constraint |
|------------|------|--------|---------------|
| Detail (明细) | REFRESH | `ENABLE_UPSERT_MODE = False` | None |
| Aggregate (汇总) | UPSERT | `ENABLE_UPSERT_MODE = True` | UNIQUE required |

#### Current Domain Configurations

| Domain | Table Type | Mode | Refresh/Upsert Keys |
|--------|------------|------|---------------------|
| `annuity_performance` | Detail | REFRESH | `["月度", "业务类型", "计划类型"]` |
| `annuity_income` | Detail | REFRESH | `["月度", "业务类型", "计划类型"]` |
```

---

## Section 5: Implementation Handoff

### Scope Classification: Moderate

This change requires code modifications and documentation updates, but no architectural changes.

### Handoff Recipients

| Role | Responsibility | Items |
|------|----------------|-------|
| **Development Team** | Code implementation | Changes 1-4 |
| **Technical Writer / Dev** | Documentation | Change 5 |

### Recommended Execution Order

1. **Change 1:** Add `load_with_refresh()` to WarehouseLoader
2. **Change 4:** Rollback/delete UNIQUE constraint migration
3. **Change 2-3:** Update domain service configurations
4. **Change 5:** Update documentation
5. **Testing:** Verify refresh behavior matches Legacy

### Success Criteria

1. `annuity_performance` pipeline uses DELETE+INSERT with keys `["月度", "业务类型", "计划类型"]`
2. `annuity_income` pipeline uses DELETE+INSERT with keys `["月度", "业务类型", "计划类型"]`
3. Re-running pipeline replaces (not duplicates) records for the same month/type combination
4. UPSERT capability preserved for future aggregate table domains
5. Documentation updated with both loading modes
6. All existing tests pass

---

## Approval

**Prepared By:** Claude (AI Assistant)
**Date:** 2025-12-06

**Approval Status:** [x] Approved / [ ] Rejected / [ ] Revise

**Approver:** Link
**Date:** 2025-12-06

**Notes:**
两个 domain 的 refresh_keys 均调整为 ["月度", "业务类型", "计划类型"]，保留 UPSERT 能力供未来聚合表使用。

---

*Generated by Correct Course Workflow*
