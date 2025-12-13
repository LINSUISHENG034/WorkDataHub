# Issue: AnnuityIncome Domain Column Mismatch

**Severity:** HIGH
**Discovered:** 2025-12-06 (Code Review of Story 5.5.4)
**Root Cause:** Documentation error in Epic 5.5.1 propagated through implementation

## Problem Summary

The `annuity_income` domain implementation expects a `收入金额` column that **does not exist** in any real production data files. The actual data uses four separate income fields: `固费`, `浮费`, `回补`, `税`.

Additionally, the column name for plan code varies between data source versions:
- **202411 and earlier:** `计划号`, `机构`
- **202412 and later:** `计划代码`, `机构代码`

## Evidence

### Real Data Analysis

```
202311 V1 收入明细: ['月度', '业务类型', '计划类型', '计划号', '计划名称', '组合类型', '组合代码', '组合名称', '客户名称', '固费', '浮费', '回补', '税', '机构', '机构名称']
202411 V1 收入明细: ['月度', '业务类型', '计划类型', '计划号', '计划名称', '组合类型', '组合代码', '组合名称', '客户名称', '固费', '浮费', '回补', '税', '机构', '机构名称']
202412 V2 收入明细: ['月度', '业务类型', '计划类型', '计划代码', '计划名称', '组合类型', '组合代码', '组合名称', '客户名称', '固费', '浮费', '回补', '税', '机构代码', '机构名称']
```

**Key Observations:**
1. **NO `收入金额` column exists** in any real data file
2. Income is split into: `固费` (fixed fee), `浮费` (variable fee), `回补` (rebate), `税` (tax)
3. Column names changed between 202411 and 202412 versions

### Legacy Cleaner Analysis

The legacy `AnnuityIncomeCleaner` (lines 237-274 in `data_cleaner.py`) does NOT process or create a `收入金额` field. It preserves the original four income columns.

## Impact

1. **Story 5.5.2 (AnnuityIncome Implementation):** Built on incorrect schema assumptions
2. **Story 5.5.3 (Parity Validation):** Could not run with real data due to column mismatch
3. **Story 5.5.4 (Integration Test):** Performance baseline for annuity_income shows 50% row drop rate
4. **All unit tests:** Pass only because they use synthetic data with artificial `收入金额` column

## Files Requiring Changes

### Documentation
- [x] `docs/cleansing-rules/annuity-income.md` - Partially fixed (column mapping table updated)

### Code (Requires New Story)
- [ ] `src/work_data_hub/domain/annuity_income/schemas.py`
  - Replace `收入金额` with `固费`, `浮费`, `回补`, `税` in BRONZE/GOLD schemas
  - Update BRONZE_REQUIRED_COLUMNS, BRONZE_NUMERIC_COLUMNS, GOLD_REQUIRED_COLUMNS
- [ ] `src/work_data_hub/domain/annuity_income/models.py`
  - Replace `收入金额` field with four income fields in AnnuityIncomeIn/Out
- [ ] `src/work_data_hub/domain/annuity_income/constants.py`
  - Add COLUMN_ALIAS_MAPPING for `计划代码` → `计划号`, `机构` → `机构代码`
- [ ] `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
  - Add MappingStep for column aliases at pipeline start
  - Update CompanyIdResolutionStep to handle both column names
- [ ] `src/work_data_hub/domain/annuity_income/service.py`
  - Update upsert_keys if needed
- [ ] `tests/unit/domain/annuity_income/*` - Update all tests with correct columns
- [ ] `tests/fixtures/test_data_factory.py` - Remove artificial `收入金额` creation

### Configuration
- [ ] `config/data_sources.yml` - Add column alias configuration for annuity_income

## Recommended Action

**Create Story 5.5.5: Fix AnnuityIncome Column Schema**

This is a **breaking change** that requires:
1. Schema migration for any existing data
2. Full regression testing with real production data
3. Parity re-validation against legacy system

## Prevention Mechanism

To prevent similar issues in future domain implementations:

1. **Data Source Validation Script:** Create `scripts/tools/validate_data_source_columns.py`
   - Reads real data files from `tests/fixtures/real_data/`
   - Compares actual columns against domain schema definitions
   - Fails CI if mismatch detected

2. **Pre-Implementation Checklist:**
   - [ ] Verify column names against 3+ real data files from different periods
   - [ ] Cross-reference with legacy cleaner code
   - [ ] Document any column name variations across data source versions

3. **Integration Test Requirement:**
   - All domain implementations must pass integration tests with real data before Story completion
   - "Skipped due to missing data" is not acceptable for parity validation

## References

- Epic 5.5: `docs/epics/epic-5.5-pipeline-architecture-validation.md`
- Story 5.5.1: `docs/sprint-artifacts/stories/5.5-1-legacy-cleansing-rules-documentation.md`
- Story 5.5.2: `docs/sprint-artifacts/stories/5.5-2-annuity-income-domain-implementation.md`
- Legacy Cleaner: `legacy/annuity_hub/data_handler/data_cleaner.py:237-274`
- Cleansing Rules Doc: `docs/cleansing-rules/annuity-income.md`
