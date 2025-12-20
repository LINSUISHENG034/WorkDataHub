# Sprint Change Proposal: Complex Mapping Backfill Enhancement

**Date:** 2025-12-20  
**Trigger:** `docs/specific/backfill-mechanism/complex-mapping-requirements-analysis.md`  
**Scope Classification:** Minor  
**Author:** SM Agent via Correct-Course Workflow

---

## 1. Issue Summary

### Problem Statement

During the validation of `年金计划` (Annuity Plan) reference table backfill, a technical limitation was discovered in the current `GenericBackfillService` implementation.

**Current Behavior:**
The `derive_candidates()` method uses `groupby.first` aggregation strategy, which only supports simple 1:1 field mapping - taking the first non-blank value for each group.

**Required Behavior:**
Two complex mapping scenarios are needed for the `年金计划` table:

1. **主拓代码/主拓机构 (Primary Agent Code/Name):**
   - Requires selecting `机构代码` and `机构名称` from the record with the **maximum** `期末资产规模` (End-of-Period Asset Scale)
   - SQL equivalent: `WHERE (计划代码, 期末资产规模) IN (SELECT 计划代码, MAX(期末资产规模) ...)`

2. **管理资格 (Management Qualification):**
   - Requires concatenating distinct `业务类型` values with `+` separator
   - SQL equivalent: `GROUP_CONCAT(DISTINCT 业务类型 ORDER BY 业务类型 SEPARATOR '+')`

### Evidence

From `complex-mapping-requirements-analysis.md`:
- Current implementation (line ~270 in `generic_service.py`): `grouped_first = source_df.groupby(config.source_column, sort=False).first()`
- This only retrieves the first encountered value, ignoring aggregation requirements

### Discovery Context

- **When:** During Epic 6.2-P14 Code Review completion (2025-12-20)
- **Where:** `docs/specific/backfill-mechanism/complex-mapping-requirements-analysis.md`
- **Impact:** Incomplete `年金计划` table data - `主拓代码`, `主拓机构`, and `管理资格` columns not populated correctly

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 6.2 | in-progress | **Direct** - Requires new story for enhancement |
| Epic 7 | backlog | **None** - No changes needed |

### Story Impact

| Story | Impact |
|-------|--------|
| 6.2-P14 (Config Modularization) | ✅ Completed - No changes needed |
| **NEW: 6.2-P15** | Required - Complex Mapping Enhancement |

### Artifact Conflicts

| Artifact | Conflict |
|----------|----------|
| PRD | ✅ No conflict - Aligns with "100% legacy parity validated" requirement |
| Architecture | ✅ No conflict - Extension within existing Infrastructure Layer |
| UI/UX | ⚪ N/A - Backend only |
| `foreign_keys.yml` | ⚠️ **Requires extension** - New aggregation config syntax |
| `GenericBackfillService` | ⚠️ **Requires enhancement** - New derive_candidates strategies |

### Technical Impact

**Files to Modify:**
1. `config/foreign_keys.yml` - Add aggregation configuration syntax
2. `src/work_data_hub/domain/reference_backfill/models.py` - Add new model fields
3. `src/work_data_hub/domain/reference_backfill/generic_service.py` - Implement new aggregation strategies
4. `tests/unit/domain/reference_backfill/test_generic_backfill_service.py` - Add aggregation tests
5. `docs/guides/infrastructure/backfill-mechanism-guide.md` - Document new feature

---

## 3. Recommended Approach

### Selected Path: **Direct Adjustment** (Option 1)

**Rationale:**
- The fix is **additive** - extends existing functionality without breaking changes
- Existing `groupby.first` strategy remains the default for simple mappings
- New aggregation strategies are opt-in via configuration
- Minimal risk - changes are isolated to the backfill subsystem
- No rollback needed - no existing functionality is modified

### Alternatives Considered

| Option | Evaluation |
|--------|------------|
| Option 2: Rollback | ❌ Not viable - No completed work to revert |
| Option 3: MVP Review | ❌ Not needed - Feature is achievable within current scope |

### Effort Estimate

| Task | Effort |
|------|--------|
| Configuration schema extension | 1 hour |
| Model updates | 0.5 hour |
| Service implementation | 2 hours |
| Unit tests | 1.5 hours |
| Documentation update | 0.5 hour |
| **Total** | **5.5 hours** |

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Breaking existing backfill | Low | New features are opt-in; default behavior unchanged |
| Complex SQL generation | Medium | Use pandas built-in aggregation; avoid raw SQL |
| Performance degradation | Low | Aggregation adds minimal overhead |

---

## 4. Detailed Change Proposals

### 4.1 Configuration Schema Extension (`config/foreign_keys.yml`)

**OLD:**
```yaml
backfill_columns:
  - source: "机构代码"
    target: "主拓代码"
    optional: true
```

**NEW:**
```yaml
backfill_columns:
  - source: "机构代码"
    target: "主拓代码"
    optional: true
    aggregation:
      type: "max_by"
      order_column: "期末资产规模"
      # Takes value from record with MAX(期末资产规模)
  
  - source: "业务类型"
    target: "管理资格"
    optional: true
    aggregation:
      type: "concat_distinct"
      separator: "+"
      sort: true
      # Concatenates distinct values: A+B+C
```

**Rationale:** Configuration-driven approach aligns with project principles (DI, SRP).

---

### 4.2 Model Updates (`models.py`)

**NEW:**
```python
@dataclass
class AggregationConfig:
    """Configuration for column aggregation during backfill."""
    type: str  # "first" | "max_by" | "concat_distinct"
    order_column: Optional[str] = None  # For max_by
    separator: str = "+"  # For concat_distinct
    sort: bool = True  # For concat_distinct

@dataclass
class BackfillColumnMapping:
    source: str
    target: str
    optional: bool = False
    aggregation: Optional[AggregationConfig] = None  # NEW field
```

---

### 4.3 Service Implementation (`generic_service.py`)

**Strategy Pattern for Aggregation:**

```python
def derive_candidates(self, df: pd.DataFrame, config: ForeignKeyConfig) -> pd.DataFrame:
    # ... existing filtering logic ...
    
    # NEW: Apply aggregation strategies per column
    result_columns = {}
    for col_mapping in config.backfill_columns:
        if col_mapping.aggregation is None:
            # Default: first non-null value
            result_columns[col_mapping.target] = grouped_first[col_mapping.source]
        elif col_mapping.aggregation.type == "max_by":
            result_columns[col_mapping.target] = self._aggregate_max_by(
                source_df, config.source_column, col_mapping
            )
        elif col_mapping.aggregation.type == "concat_distinct":
            result_columns[col_mapping.target] = self._aggregate_concat_distinct(
                source_df, config.source_column, col_mapping
            )
    
    return pd.DataFrame(result_columns)

def _aggregate_max_by(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """Get value from row with maximum order_column value."""
    order_col = mapping.aggregation.order_column
    idx = df.groupby(group_col)[order_col].idxmax()
    return df.loc[idx, mapping.source].set_index(df.loc[idx, group_col])

def _aggregate_concat_distinct(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """Concatenate distinct values with separator."""
    sep = mapping.aggregation.separator
    sort = mapping.aggregation.sort
    
    def concat_func(x):
        unique = x.dropna().unique()
        if sort:
            unique = sorted(unique)
        return sep.join(str(v) for v in unique)
    
    return df.groupby(group_col)[mapping.source].agg(concat_func)
```

---

### 4.4 Updated FK Configuration for `annuity_performance`

```yaml
# config/foreign_keys.yml
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        target_schema: "mapping"
        mode: "insert_missing"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
          - source: "计划名称"
            target: "计划全称"
            optional: true
          - source: "计划类型"
            target: "计划类型"
            optional: true
          - source: "客户名称"
            target: "客户名称"
            optional: true
          # NEW: max_by aggregation for 主拓代码/主拓机构
          - source: "机构代码"
            target: "主拓代码"
            optional: true
            aggregation:
              type: "max_by"
              order_column: "期末资产规模"
          - source: "机构名称"
            target: "主拓机构"
            optional: true
            aggregation:
              type: "max_by"
              order_column: "期末资产规模"
          # NEW: concat_distinct aggregation for 管理资格
          - source: "业务类型"
            target: "管理资格"
            optional: true
            aggregation:
              type: "concat_distinct"
              separator: "+"
              sort: true
          - source: "company_id"
            target: "company_id"
            optional: true
```

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

This change can be implemented directly by the development team without backlog reorganization.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Dev Agent** | Implement code changes, write tests, update documentation |
| **SM Agent** | Create story file 6.2-P15, update sprint-status.yaml |
| **Code Review** | Adversarial review of implementation |

### Success Criteria

1. ✅ All existing tests pass (`pytest tests/unit/domain/reference_backfill/`)
2. ✅ New aggregation tests pass (max_by, concat_distinct)
3. ✅ `年金计划` table correctly populated with:
   - `主拓代码`: Institution code from record with max asset scale
   - `主拓机构`: Institution name from record with max asset scale  
   - `管理资格`: Concatenated distinct business types (e.g., "受托+账管+投管")
4. ✅ backfill-mechanism-guide.md updated with new aggregation syntax
5. ✅ Configuration schema backward compatible (existing configs work unchanged)

### Verification Commands

```bash
# Run existing backfill tests
pytest tests/unit/domain/reference_backfill/test_generic_backfill_service.py -v

# Run new aggregation-specific tests (to be added)
pytest tests/unit/domain/reference_backfill/test_generic_backfill_service.py -v -k "aggregation"

# Validate configuration loading
python -c "
from work_data_hub.domain.reference_backfill.config_loader import load_foreign_keys_config
config = load_foreign_keys_config(domain='annuity_performance')
print(f'Loaded {len(config)} FK configurations')
for fk in config:
    agg_cols = [c.target for c in fk.backfill_columns if hasattr(c, 'aggregation') and c.aggregation]
    if agg_cols:
        print(f'  {fk.name}: aggregation columns = {agg_cols}')
"
```

---

## 6. Approval Request

**Proposed New Story:**
- **ID:** 6.2-P15
- **Title:** Complex Mapping Backfill Enhancement
- **Epic:** 6.2 (Generic Reference Data Management)
- **Effort:** 5.5 hours
- **Priority:** Medium (blocks correct `年金计划` data population)

**Action Required:**
- [ ] Approve this Sprint Change Proposal
- [ ] Proceed with story creation and implementation

---

*Generated by Correct-Course Workflow on 2025-12-20*
