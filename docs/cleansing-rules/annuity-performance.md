# AnnuityPerformance Domain Cleansing Rules

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`
> Last verified: `2026-04-11`
> Scope: Domain-specific cleansing and migration notes

## 1. Domain Overview

| Item | Value |
|------|-------|
| Legacy Cleaner Class | `AnnuityPerformanceCleaner` |
| Source File | `legacy/annuity_hub/data_handler/data_cleaner.py` (lines 194-293) |
| Excel Sheet Name | `规模明细` |
| Target Database Table | `business."规模明细"` |

## 2. Dependency Table Inventory

> **Implementation:** Execute migration scripts before Phase 3. See [Mapping Guide - Section 2](../guides/domain-migration/code-mapping.md#section-2-dependency-table-inventory--migration-execution)

### Critical Dependencies (Migration Status Verified)

| # | Table Name | Database | Purpose | Actual Rows | Migration Status |
|---|------------|----------|---------|------------|-----------------|
| 1 | company_id_mapping | **enterprise.enrichment_index** | Company name to ID mapping | 19,840 | ✅ MIGRATED |
| 2 | eqc_search_result | **NOT FOUND** | EQC company lookups | 0 | ❌ Missing |
| 3 | 产品线 | mapping | Business type code mapping | 12 | ✅ In Place |
| 4 | 组织架构 | mapping | Branch office mapping | 38 | ✅ In Place |
| 5 | 年金计划 | mapping | Plan code to company ID | 1,159 | ✅ In Place |
| 6 | annuity_account_mapping | **NOT FOUND** | Account number mapping | 0 | ❌ Missing |
| 7 | 规模明细 | business | Account name to company ID | 441,356 | ✅ Source Table |

### Optional Dependencies

| # | Table Name | Database | Purpose | Notes |
|---|------------|----------|---------|-------|
| 1 | 组合计划 | mapping | Plan portfolio code mapping | Used for default portfolio codes |

---

## 3. Migration Strategy Decisions

### Decision Summary

- **Decision Date**: 2025-12-10
- **Decision Maker**: Technical Lead
- **Reviewed By**: Development Team

### Strategy Options Reference

| Strategy | Description | Typical Use Cases |
|----------|-------------|-------------------|
| Direct Migration | Move table as-is | Simple lookup tables |
| Enrichment Index | Migrate to enterprise.enrichment_index | Company/entity mappings |
| Transform & Load | Restructure data | Complex schema changes |
| Static Embedding | Hardcode in constants | Small, stable lookups |
| Decommission | Mark obsolete | Unused tables |
| Custom Strategy | Team-defined approach | Unique requirements |

### Dependency Table Strategies (Actual Implementation)

| # | Table Name | Legacy Schema | Target Strategy | Target Location | Actual Status |
|---|------------|---------------|-----------------|-----------------|--------------|
| 1 | company_id_mapping | legacy.company_id_mapping | Enrichment Index | enterprise.enrichment_index | ✅ Complete (19,840 rows) |
| 2 | eqc_search_result | legacy.eqc_search_result | **NOT AVAILABLE** | **TABLE MISSING** | ❌ Need to create/restore |
| 3 | 产品线 | mapping.产品线 | Static Embedding | infrastructure.mappings | ✅ Complete (shared.py) |
| 4 | 组织架构 | mapping.组织架构 | Static Embedding | infrastructure.mappings | ✅ Complete (shared.py) |
| 5 | 年金计划 | mapping.年金计划 | Database Query | mapping.年金计划 | ✅ Available (1,159 rows) |
| 6 | annuity_account_mapping | enterprise.annuity_account_mapping | **NOT AVAILABLE** | **TABLE MISSING** | ❌ Need to create/restore |
| 7 | 规模明细 | business.规模明细 | Source of Truth | business.规模明细 | ✅ Complete (441,356 rows) |

---

## 4. Migration Validation Checklist

### Pre-Migration
- [x] Source database accessible
- [x] Target schema/index exists
- [x] Migration script tested in dry-run mode

### Migration Execution
- [x] Run migration script: `PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py`
- [x] Verify batch completion without errors

### Post-Migration Validation
- [x] Row count validation (source vs target)
- [x] Data sampling validation (10 random keys)
- [x] Performance validation (lookup latency < 10ms)

---

## 5. Column Mappings

> **Implementation:** Convert to `constants.py` → `COLUMN_MAPPING` and `COLUMN_ALIAS_MAPPING` dicts. See [Mapping Guide - Section 5](../guides/domain-migration/code-mapping.md#section-5-column-mappings--constantspy)

| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | 机构 | 机构名称 | `df.rename(columns={'机构': '机构名称'})` | Initial rename |
| 2 | 计划号 | 计划代码 | `df.rename(columns={'计划号': '计划代码'})` | Initial rename |
| 3 | 流失（含待遇支付） | 流失(含待遇支付) | `df.rename(columns={'流失（含待遇支付）': '流失(含待遇支付)'})` | Special character handling |
| 4 | 机构名称 | 机构代码 | `df['机构代码'] = df['机构名称'].map(COMPANY_BRANCH_MAPPING)` | Overwrites renamed column |
| 5 | 月度 | 月度 | `df['月度'].apply(parse_to_standard_date)` | Chinese date format standardization |
| 6 | 计划代码 | 计划代码 | `df['计划代码'].replace({"1P0290": "P0290", "1P0807": "P0807"})` | Remove leading '1' from specific codes |
| 7 | 计划代码 | 计划代码 | Conditional fill based on 计划类型 | See CR-004 |
| 8 | 机构代码 | 机构代码 | `df['机构代码'].replace("null", "G00")` | Null to default code |
| 9 | 机构代码 | 机构代码 | `df['机构代码'].fillna("G00")` | Fill remaining nulls |
| 10 | 组合代码 | 组合代码 | `df['组合代码'].str.replace("^F", "", regex=True)` | Remove leading 'F' |
| 11 | 组合代码 | 组合代码 | Conditional default based on 业务类型 | See CR-005 |
| 12 | 业务类型 | 产品线代码 | `df['产品线代码'] = df['业务类型'].map(BUSINESS_TYPE_CODE_MAPPING)` | Business type mapping |
| 13 | 客户名称 | 年金账户名 | `df['年金账户名'] = df['客户名称']` | Copy before normalization |
| 14 | 客户名称 | 客户名称 | `df['客户名称'].apply(clean_company_name)` | Normalized in-place |
| 15 | 计划代码 | company_id | 5-step resolution process | See Section 7 |
| 16 | 集团企业客户号 | 年金账户号 | `df['年金账户号'] = df['集团企业客户号'].str.lstrip("C")` | Derived before drop (Story 6.2-P11) |
| 17 | 集团企业客户号 | [DROPPED] | `df.drop(columns=['集团企业客户号'])` | Dropped after derivation |

---

## 6. Cleansing Rules

| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | 机构代码 | mapping | `df['机构代码'] = df['机构名称'].map(COMPANY_BRANCH_MAPPING)` | 1 | Includes manual overrides (see mappings.py lines 128-137) |
| CR-002 | 月度 | transformation | `df['月度'].apply(parse_to_standard_date)` | 1 | Chinese date format standardization |
| CR-003 | 计划代码 | conditional | `df['计划代码'].replace({"1P0290": "P0290", "1P0807": "P0807"})` | 2 | Fix specific codes with leading '1' |
| CR-004 | 计划代码 | conditional | Fill AN001 for 集合计划, AN002 for 单一计划 when null/empty | 2 | Default plan codes by type |
| CR-005 | 组合代码 | conditional | `df.apply(lambda x: "QTAN003" if x["业务类型"] in ["职年受托", "职年投资"] else DEFAULT_PORTFOLIO_CODE_MAPPING.get(x["计划类型"]), axis=1)` | 2 | Default portfolio codes |
| CR-006 | 组合代码 | transformation | `df['组合代码'].str.replace("^F", "", regex=True)` | 1 | Remove leading 'F' character |
| CR-007 | 产品线代码 | mapping | `df['产品线代码'] = df['业务类型'].map(BUSINESS_TYPE_CODE_MAPPING)` | 1 | Business type to product line mapping |
| CR-008 | 机构代码 | default | `df['机构代码'].replace("null", "G00").fillna("G00")` | 1 | Default to headquarters code |
| CR-009 | 客户名称 | transformation | `df['客户名称'].apply(clean_company_name)` | 1 | Name normalization |
| CR-010 | company_id | 5-step resolution | Complex multi-source resolution | 1 | See Section 7 for details |
| CR-011 | 年金账户号 | derivation | `df['年金账户号'] = df['集团企业客户号'].str.lstrip("C")` | 1 | Story 6.2-P11: Derive before 集团企业客户号 is dropped |

---

## 7. Company ID Resolution Strategy

> **Implementation:** Implement in `pipeline_builder.py` using enrichment service. See [Mapping Guide - Section 7](../guides/domain-migration/code-mapping.md#section-7-company-id-resolution-strategy--enrichment-service)

### Resolution Priority Order

1. **Step 1:** 计划代码 → COMPANY_ID1_MAPPING (年金计划 table)
   - Source: `mapping.年金计划` (单一计划 only)
   - Applied to all rows first

2. **Step 2:** 集团企业客户号 → COMPANY_ID2_MAPPING (after cleaning)
   - Source: `enterprise.annuity_account_mapping`
   - Applied where Step 1 failed
   - Pre-processing: `df['集团企业客户号'].str.lstrip("C")`

3. **Step 3:** Special case default
   - Applied where both customer name and plan code are null/empty
   - Uses COMPANY_ID3_MAPPING with fallback "600866980"
   - Static mapping for known problematic plans

4. **Step 4:** 客户名称 → COMPANY_ID4_MAPPING
   - Source: `enterprise.company_id_mapping`
   - Applied where previous steps failed

5. **Step 5:** 年金账户名 → COMPANY_ID5_MAPPING
   - Source: `business.规模明细` (historical data)
   - Final fallback attempt

### Domain-Specific Notes

- **Plan Code Corrections**: Specific codes "1P0290" and "1P0807" have leading '1' removed
- **Default Values**:
  - Empty 机构代码 defaults to "G00" (headquarters)
  - Empty 计划代码 defaults to "AN001" (集合计划) or "AN002" (单一计划)
  - Empty 组合代码 defaults based on 计划类型 or "QTAN003" for 职年业务
- **Branch Overrides**: Manual branch code overrides in mappings.py (lines 128-137)

---

## 8. Validation Rules

> **Implementation:** Convert to Pydantic models and Pandera schemas. See [Mapping Guide - Section 8](../guides/domain-migration/code-mapping.md#section-8-validation-rules--models--schemas)

### Required Fields (Bronze)
- `月度` (date) - Required for Silver/Gold
- `计划代码` (string) - Required for Silver/Gold
- `客户名称` (string) - Used for company ID resolution
- `期末资产规模` (numeric) - Required for Silver/Gold

### Required Fields (Gold)
- `月度`: date (not null)
- `计划代码`: string (not null, min_length=1)
- `company_id`: string (not null)
- `期初资产规模`: float (>= 0)
- `期末资产规模`: float (>= 0)
- `投资收益`: float
- `当期收益率`: float (nullable)
- `流失(含待遇支付)`: float (nullable)

### Data Type Constraints
- Date fields: Valid YYYY-MM-DD format
- Numeric fields: Non-negative where specified
- String fields: Non-empty after cleaning
- Composite PK: (`月度`, `计划代码`, `company_id`) must be unique

### Business Rules
- 年化收益率 can be null if 期末资产规模 is 0
- 流失(含待遇支付) includes all outflows
- Negative values allowed only for specific metrics (e.g., 投资收益)

---

## 9. Special Processing Notes

> **Implementation:** Handle in `pipeline_builder.py` special steps or in `helpers.py`. See [Mapping Guide - Section 9](../guides/domain-migration/code-mapping.md#section-9-special-processing-notes--helperspy)

### Edge Cases and Known Issues

1. **Missing Plan Codes**
   - Default logic applies based on 计划类型
   - AN001 for 集合计划, AN002 for 单一计划

2. **Branch Code Manual Overrides**
   - "内蒙" → "G31"
   - "战略" → "G37"
   - "中国" → "G37"
   - "济南" → "G21"
   - "北京其他" → "G37"
   - "北分" → "G37"

3. **Portfolio Code Logic**
   - Remove leading 'F' from existing codes
   - Default based on 计划类型:
     - 集合计划 → QTAN001
     - 单一计划 → QTAN002
     - 职年受托/职年投资 → QTAN003

4. **Company ID Resolution Complexity**
   - 5-step resolution chain (see Section 7)
   - Company ID3 static mappings for special cases:
     - FP0001/FP0002 → 614810477
     - P0809 → 608349737
     - And 5 other specific plan codes

### Legacy System Quirks

1. **Column Renaming Pattern**
   - 机构 → 机构名称 (then mapped to 机构代码)
   - 计划号 → 计划代码
   - 特殊字符 handling in 流失（含待遇支付）

2. **Null Handling Pattern**
   - String "null" → actual null
   - Null values → defaults (G00, AN001, etc.)

3. **Date Processing**
   - Uses `parse_to_standard_date()` for Chinese date formats

### Performance Considerations

- Company ID resolution involves up to 5 mapping lookups
- Consider caching mapping tables in memory
- Bulk operations preferred over row-by-row

---

## 10. Parity Validation Checklist

> **Implementation:** Use parity validation script. See [Mapping Guide - Section 10](../guides/domain-migration/code-mapping.md#section-10-parity-validation-checklist--validation)

### Test Data Preparation
- [x] Real test data from production (33,615 rows)
- [x] Legacy mappings configured
- [x] Output directory created: `tests/fixtures/validation_results/annuity_performance/`

### Validation Execution
- [x] Legacy cleaner executed and output captured
- [x] New pipeline executed and output captured
- [x] Parity comparison script run
- [x] Comparison report generated

### Current Status (2025-12-04)
- **Row Count Match**: ✅ 33,615 rows
- **Column Match**: ✅ 24 columns (1 renamed: 流失(含待遇支付))
- **Data Differences**:
  - Small number of legacy-only records (0.3%)
  - Need to investigate specific differences

### Actions Required
- [ ] Investigate and resolve remaining data differences
- [ ] Achieve 100% parity match
- [ ] Document any intentional differences
- [ ] Update this section with final validation results

### Validation Scripts
```bash
# Run parity validation
PYTHONPATH=src uv run python scripts/tools/parity/validate_annuity_performance_parity.py

# Check latest results
ls -la tests/fixtures/validation_results/annuity_performance/
```

---

## Implementation Status

### Phase 1: Dependencies ⚠️ PARTIAL
- 7 dependency tables identified
- 3 tables migrated successfully to enrichment_index/static
- 2 tables NOT FOUND (eqc_search_result, annuity_account_mapping)
- 2 tables remain in place (年金计划, 规模明细)

### Phase 2: Documentation ✅ COMPLETE
- All 10 sections documented
- Legacy code analyzed
- Rules extracted and documented
- Migration status verified

### Phase 3: Implementation ✅ COMPLETE
- 6-file domain structure created
- Unit tests written and passing
- Integration tests written and passing
- Uses CompanyIdResolver with enrichment service

### Phase 4: Validation 🔄 IN PROGRESS
- Parity validation shows 99.7% match
- Small differences may be due to missing dependency tables
- Need to restore missing tables or implement fallback logic

---

## Next Steps

### Critical Actions Required

1. **Restore Missing Dependency Tables**
   - Create/restore `legacy.eqc_search_result` table (~11,820 rows)
   - Create/restore `enterprise.annuity_account_mapping` table (~5,000 rows)
   - Run migration script for missing tables

2. **Complete Parity Validation**
   - Investigate if 0.3% difference is due to missing tables
   - Fix any bugs in implementation
   - Achieve 100% parity match

3. **Update Code to Handle Missing Dependencies**
   - Add fallback logic in CompanyIdResolver
   - Ensure graceful degradation when tables are missing

### Documentation Updates

4. **Update Index File**
   - Mark annuity_performance as "PARTIAL" until dependencies restored

### Production Readiness

5. **Final Validation**
   - Full end-to-end testing with all dependencies
   - Performance testing
   - Deployment preparation

---

**Last Updated:** 2025-12-16
**Status:** 90% Complete (Story 6.2-P11: Added 年金账户号 derivation rule CR-011)

## Related Active Docs

- [Domain Contract](../domains/annuity_performance.md)
- [Runbook](../runbooks/annuity_performance.md)
- [Documentation Standards](../engineering/documentation-standards.md)
