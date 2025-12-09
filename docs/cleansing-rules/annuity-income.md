# AnnuityIncome Domain Cleansing Rules

## 1. Domain Overview

| Item | Value |
|------|-------|
| Legacy Cleaner Class | `AnnuityIncomeCleaner` |
| Source File | `legacy/annuity_hub/data_handler/data_cleaner.py` (lines 237-274) |
| Excel Sheet Name | `收入明细` |
| Target Database Table | `business.annuity_income` (TODO: confirm schema/table in Story 5.5.2) |

## 2. Dependency Table Inventory

### Critical Dependencies (Migrated)

| # | Table Name | Database | Purpose | Row Count | Migration Status |
|---|------------|----------|---------|-----------|-----------------|
| 1 | company_id_mapping | legacy | Company name to ID mapping | ~19,141 | [MIGRATED] |
| 2 | eqc_search_result | legacy | EQC company lookups | ~11,820 | [MIGRATED] |

### Optional Dependencies

| # | Table Name | Database | Purpose | Notes |
|---|------------|----------|---------|-------|
| 1 |年金计划 | legacy | Plan information lookup | Migrated as enrichment index mapping |

---

## 3. Migration Strategy Decisions

### Decision Summary
- **Decision Date**: 2025-12-08
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

### Dependency Table Strategies

| # | Table Name | Legacy Schema | Target Strategy | Target Location | Rationale |
|---|------------|---------------|-----------------|-----------------|-----------|
| 1 | company_id_mapping | legacy.company_id_mapping | Enrichment Index | enterprise.enrichment_index | Core company resolution system |
| 2 | eqc_search_result | legacy.eqc_search_result | Enrichment Index | enterprise.enrichment_index | EQC provider integration |
| 3 | 年金计划 | legacy.年金计划 | Static Embedding | domain constants | Small, stable mapping set |

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

| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | 机构 | 机构代码 | `df.rename(columns={'机构': '机构代码'})` | Initial rename, then overwritten by mapping |
| 2 | 机构名称 | 机构代码 | `df['机构名称'].map(COMPANY_BRANCH_MAPPING)` | Overwrites renamed column |
| 3 | 月度 | 月度 | `parse_to_standard_date()` | Chinese date format standardization |
| 4 | 业务类型 | 产品线代码 | `df['业务类型'].map(BUSINESS_TYPE_CODE_MAPPING)` | Creates new column |
| 5 | 客户名称 | 年金账户名 | `df['年金账户名'] = df['客户名称']` | Copy before normalization |
| 6 | 客户名称 | 客户名称 | `clean_company_name()` | Normalized in-place |
| 7 | 计划号 | company_id | `_update_company_id(plan_code_col='计划号')` | Standard resolution chain |
| 8 | 组合代码 | 组合代码 | Regex + conditional default | See CR-005, CR-006 |
| 9 | 固费 | 固费 | None | Fixed fee income (numeric) |
| 10 | 浮费 | 浮费 | None | Variable fee income (numeric) |
| 11 | 回补 | 回补 | None | Rebate income (numeric) |
| 12 | 税 | 税 | None | Tax amount (numeric) |
| 13 | 计划类型 | 计划类型 | None (used for conditional logic) | Input to DEFAULT_PORTFOLIO_CODE_MAPPING |
| 14 | N/A | company_id | **DEPRECATED** ID5 fallback | See Section 7 - Dropped in Migration |

---

## 6. Cleansing Rules

| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | 机构代码 | mapping | `df['机构名称'].map(COMPANY_BRANCH_MAPPING)` | 1 | Includes manual overrides (see below) |
| CR-002 | 月度 | date_parse | `df['月度'].apply(parse_to_standard_date)` | 2 | Handles Chinese date formats |
| CR-003 | 机构代码 | default_value | `replace('null', 'G00').fillna('G00')` | 3 | Headquarters fallback |
| CR-004 | 组合代码 | default_value | `df['组合代码'] = np.nan` if column missing | 4 | Safety check |
| CR-005 | 组合代码 | regex_replace | `str.replace('^F', '', regex=True)` | 5 | Remove 'F' prefix |
| CR-006 | 组合代码 | conditional | See conditional logic below | 6 | Based on 业务类型 and 计划类型 |
| CR-007 | 产品线代码 | mapping | `df['业务类型'].map(BUSINESS_TYPE_CODE_MAPPING)` | 7 | Creates new column |
| CR-008 | 年金账户名 | copy | `df['年金账户名'] = df['客户名称']` | 8 | Before normalization |
| CR-009 | 客户名称 | normalize | `clean_company_name()` | 9 | Company name normalization |
| CR-010 | company_id | resolution | `_update_company_id(plan_code_col='计划号', customer_name_col='客户名称')` | 10 | Standard 4-step chain |
| CR-011 | company_id | legacy_fallback (do not implement) | Legacy: `df['年金账户名'].map(COMPANY_ID5_MAPPING)` | — | **Legacy-only; dropped in migration. Do NOT implement in new pipeline.** |

### CR-006 Conditional Logic (组合代码 Default)

```python
df['组合代码'] = df['组合代码'].mask(
    (df['组合代码'].isna() | (df['组合代码'] == '')),
    df.apply(
        lambda x: 'QTAN003' if x['业务类型'] in ['职年受托', '职年投资']
                  else DEFAULT_PORTFOLIO_CODE_MAPPING.get(x['计划类型']),
        axis=1
    )
)
```

**Decision Tree:**
1. If 组合代码 is empty/null:
   - If 业务类型 in ['职年受托', '职年投资'] → 'QTAN003'
   - Else → `DEFAULT_PORTFOLIO_CODE_MAPPING.get(计划类型)`

### CR-009 clean_company_name() Logic

**Location:** `legacy/annuity_hub/common_utils/common_utils.py:309-343`

**Operations (in order):**

1. **Remove whitespace:** `re.sub(r'\s+', '', name)`
2. **Remove "及下属子企业":** `re.sub(r'及下属子企业', '', name)`
3. **Remove suffixes:** `re.sub(r'(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$', '', name)`
4. **Remove CORE_REPLACE_STRING patterns:**
   - Patterns: `{'已转出', '待转出', '终止', '转出', '转移终止', '已作废', '已终止', '保留', '保留账户', '存量', '已转移终止', '本部', '未使用', '集合', '原'}`
   - Remove from start: `^([\(\（]?){pattern}([\)\）]?)(?=[^\u4e00-\u9fff]|$)`
   - Remove from end: `(?<![\u4e00-\u9fff])([\-\(\（]?){pattern}([\)\）]?)[\-\(\（\)\）]*$`
5. **Clean trailing characters:** `re.sub(r'[\-\(\（\)\）]+$', '', name)`
6. **Character width conversion:** Full-width to half-width (default)

### Rule Types Reference

| Type | Description | Example |
|------|-------------|---------|
| `mapping` | Value mapping using lookup table | `COMPANY_BRANCH_MAPPING` |
| `date_parse` | Date format standardization | `parse_to_standard_date()` |
| `default_value` | Fill missing values with default | `fillna('G00')` |
| `regex_replace` | Pattern-based string replacement | `str.replace('^F', '')` |
| `conditional` | Conditional logic based on other fields | `mask(condition, value)` |
| `copy` | Copy column value | `df['年金账户名'] = df['客户名称']` |
| `normalize` | Text normalization | `clean_company_name()` |
| `resolution` | Multi-step ID resolution | `_update_company_id()` |
| `fallback` | Last-resort mapping | **DEPRECATED** |

---

## 7. Company ID Resolution Strategy

### Standard Resolution Chain (via `_update_company_id`)

| Priority | Source Field | Mapping Table | Logic | Notes |
|----------|--------------|---------------|-------|-------|
| 1 | 计划号 | `COMPANY_ID1_MAPPING` | `df['计划号'].map(COMPANY_ID1_MAPPING)` | Single plan lookup |
| 2 | 计划号 + 客户名称 | `COMPANY_ID3_MAPPING` | When company_id empty AND 客户名称 empty, use ID3 with default '600866980' | Special case handling |
| 3 | 客户名称 | `COMPANY_ID4_MAPPING` | `df['客户名称'].map(COMPANY_ID4_MAPPING)` | Customer name lookup |

### Mapping Table Sources

| Mapping | Database | Query | Notes |
|---------|----------|-------|-------|
| `COMPANY_ID1_MAPPING` | mapping | `SELECT 年金计划号, company_id FROM 年金计划 WHERE 计划类型='单一计划' AND 年金计划号 != 'AN002'` | Plan-based |
| `COMPANY_ID3_MAPPING` | Static | Hardcoded 9 entries (FP0001, FP0002, etc.) | Special plans |
| `COMPANY_ID4_MAPPING` | enterprise | `SELECT company_name, company_id FROM company_id_mapping` | Name-based |

### DEPRECATED: COMPANY_ID5_MAPPING (Legacy Fallback)

| Status | Reason | Action |
|--------|--------|--------|
| **DROPPED IN MIGRATION** | Architecture alignment with AnnuityPerformance | Do NOT implement in new domain |

**Legacy Code (lines 269-272):**
```python
# 根据 '年金账户名' 补充 'company_id'
mask = df['company_id'].isna() | (df['company_id'] == '')
company_id_from_account = df['年金账户名'].map(COMPANY_ID5_MAPPING)
df.loc[mask, 'company_id'] = company_id_from_account[mask]
```

**Decision:** This fallback is NOT ported to the new implementation. The standard `CompanyIdResolutionStep` from Infrastructure Layer (Epic 5) provides consistent behavior across all domains.

### Default Value Handling

- **Condition:** When all mapping sources fail
- **Default Value:** None (company_id remains empty)
- **Note:** Unlike AnnuityPerformance which has ID5 fallback, AnnuityIncome in new architecture will have empty company_id for unresolved cases

---

## 8. Validation Rules

### Required Fields

- [x] 月度 (date)
- [x] 机构代码 (string, defaults to 'G00')
- [x] 计划号 or 计划代码 (string) - column name varies by data source version
- [x] 客户名称 (string)
- [x] 业务类型 (string)
- [x] 固费 (numeric) - Fixed fee income
- [x] 浮费 (numeric) - Variable fee income
- [x] 回补 (numeric) - Rebate income
- [x] 税 (numeric) - Tax amount

### Data Type Constraints

| Field | Expected Type | Constraint | Notes |
|-------|---------------|------------|-------|
| 月度 | `datetime` | Format: YYYY-MM-DD | Standardized from Chinese formats |
| 机构代码 | `string` | Pattern: G\d{2} | Branch code |
| 计划号/计划代码 | `string` | Non-empty | Used for company_id resolution; column name varies |
| 客户名称 | `string` | Normalized | After clean_company_name() |
| 年金账户名 | `string` | Original value | Before normalization |
| 组合代码 | `string` | Pattern: QTAN\d{3} or custom | After regex/conditional |
| 产品线代码 | `string` | From mapping | Derived from 业务类型 |
| 固费 | `numeric` | Decimal | Fixed fee income |
| 浮费 | `numeric` | Decimal | Variable fee income |
| 回补 | `numeric` | Decimal | Rebate income |
| 税 | `numeric` | Decimal | Tax amount |
| company_id | `string` | 9-digit or empty | Enterprise ID |

### Business Rules

| Rule ID | Description | Validation Logic |
|---------|-------------|------------------|
| VR-001 | 机构代码 must have valid value | `机构代码.notna() & (机构代码 != '')` - defaults to 'G00' |
| VR-002 | 月度 must be valid date | `月度.notna() & isinstance(月度, datetime)` |
| VR-003 | 组合代码 conditional default | If empty and 业务类型 in ['职年受托', '职年投资'] → 'QTAN003' |
| VR-004 | 产品线代码 must exist | `产品线代码.notna()` after mapping |
| VR-005 | company_id resolution follows standard chain | No ID5 fallback allowed |

---

## 9. Special Processing Notes

### Edge Cases

1. **Missing 组合代码 column:** Legacy code creates column with `np.nan` if not present
2. **'null' string in 机构代码:** Explicitly replaced with 'G00' (not just NaN)
3. **Empty 客户名称:** Skips clean_company_name() (lambda checks `isinstance(x, str)`)
4. **年金账户名 timing:** Must be copied BEFORE 客户名称 normalization

### Legacy Quirks

1. **Column rename then overwrite:** 机构 is renamed to 机构代码, then immediately overwritten by mapping from 机构名称
2. **Dual 组合代码 defaults:** Both regex replacement AND conditional default applied
3. **年金账户名 preserved but unused:** In legacy, used for ID5 fallback; in new architecture, preserved for audit trail only

### Known Issues

1. **COMPANY_BRANCH_MAPPING manual overrides:** Database query + hardcoded additions (see below)
2. **ID5 fallback inconsistency:** Legacy AnnuityIncome has ID5 fallback, AnnuityPerformance does not - new architecture standardizes to NO ID5

### COMPANY_BRANCH_MAPPING Complete Values

**Source:** `legacy/annuity_hub/data_handler/mappings.py:88-110`

```python
# Base mapping from DB: SELECT 机构, 机构代码 FROM 组织架构
# Plus manual overrides:
COMPANY_BRANCH_MAPPING.update({
    '内蒙': 'G31',
    '战略': 'G37',
    '中国': 'G37',
    '济南': 'G21',
    '北京其他': 'G37',
    '北分': 'G37',
})
```

**Critical:** These manual overrides MUST be included in the new implementation.

**Gap Analysis:** `annuity_performance/constants.py` is MISSING these legacy overrides:
- `'内蒙': 'G31'` - Missing
- `'战略': 'G37'` - Missing
- `'中国': 'G37'` - Missing
- `'济南': 'G21'` - Present as '山东': 'G21' (different key)
- `'北京其他': 'G37'` - Missing
- `'北分': 'G37'` - Missing

**Action for Story 5.5.2:** Ensure AnnuityIncome includes ALL legacy entries. Consider updating shared infrastructure mapping.

### DEFAULT_PORTFOLIO_CODE_MAPPING

```python
DEFAULT_PORTFOLIO_CODE_MAPPING = {
    '集合计划': 'QTAN001',
    '单一计划': 'QTAN002',
    '职业年金': 'QTAN003'
}
```

---

## 10. Parity Validation Checklist

### Row/Column Matching

- [ ] Row count matches legacy output (same input file)
- [ ] Column names match after all renames
- [ ] No extra columns introduced
- [ ] No columns missing (except intentionally dropped)

### Data Value Matching

- [ ] 机构代码 values 100% match (including 'G00' defaults)
- [ ] 月度 dates match (format: YYYY-MM-DD)
- [ ] 组合代码 values match (regex + conditional applied)
- [ ] 产品线代码 values match (from BUSINESS_TYPE_CODE_MAPPING)
- [ ] 客户名称 normalized values match
- [ ] 年金账户名 preserves original 客户名称

### Company ID Validation

- [ ] company_id from standard chain (ID1 → ID3 → ID4) matches legacy
- [ ] **ID5 fallback is DISABLED** - verify no ID5 lookups occur
- [ ] Empty company_id cases documented (previously filled by ID5)
- [ ] Compare with AnnuityPerformance behavior for consistency

### Rule Coverage

- [ ] All 11 cleansing operations mapped to Cleansing Rules table
- [ ] Manual mapping overrides (COMPANY_BRANCH_MAPPING) complete
- [ ] Regex patterns match exactly
- [ ] Conditional logic order preserved

### Execution Steps

1. **Prepare test data:** Extract sample from `tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集/*年金终稿*.xlsx` Sheet `收入明细`
2. **Run legacy cleaner:** Execute `AnnuityIncomeCleaner` on test data
3. **Run new pipeline:** Execute new AnnuityIncome domain pipeline on same data
4. **Compare outputs:**
   - Row count: `assert len(legacy_df) == len(new_df)`
   - Column names: `assert set(legacy_df.columns) == set(new_df.columns)`
   - Values: `pd.testing.assert_frame_equal(legacy_df, new_df, check_dtype=False)`
5. **Document differences:** Any intentional differences (e.g., ID5 removal) must be documented
6. **Archive results:** Save to `tests/fixtures/validation_results/annuity_income_parity_{date}.json`

---

## 11. Security / Database / Performance

### Target Database Schema

| Item | Value | Notes |
|------|-------|-------|
| Schema | `business` | Align with annuity domains |
| Table | `annuity_income` | Follow annuity naming |
| Primary Key | (`月度`, `计划号`, `company_id`) | Composite key mirrors annuity_performance |
| Indexes | (`月度`), (`company_id`), (`机构代码`) | Date filter, enrichment join, branch filter |

### Column Constraints

| Column | Nullable | Type | Constraint |
|--------|----------|------|------------|
| 月度 | NO | DATE | NOT NULL |
| 机构代码 | NO | VARCHAR(10) | DEFAULT 'G00' |
| 计划号 | NO | VARCHAR(50) | NOT NULL |
| 客户名称 | YES | VARCHAR(200) | Normalized |
| 年金账户名 | YES | VARCHAR(200) | Original |
| 组合代码 | YES | VARCHAR(20) | After defaults |
| 产品线代码 | YES | VARCHAR(20) | From mapping |
| 收入金额 | YES | DECIMAL(18,2) | Numeric |
| company_id | YES | VARCHAR(20) | 9-digit or NULL |

### Access Control & Audit

- **Sensitivity:** 客户名称, 计划号 may contain PII → apply platform RBAC; mask in logs for non-privileged contexts.
- **Audit:** Use infra-layer audit logging; capture user, timestamp, source file.
- **Masking:** No SSN/ID numbers expected; mask company_id in non-privileged logs if policy requires.

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Row volume | ~10,000-50,000 rows/month | Typical monthly file |
| Processing time | <3s per 1,000 rows | Align with infra baseline |
| Memory | <200MB baseline | Infra baseline |

### Deployment / Integration

- **Story 5.5.1:** Documentation only - no deployment
- **Story 5.5.2:** Implement pipeline + Dagster orchestration using this spec
- **Story 5.5.3:** Parity validation outputs to `tests/fixtures/validation_results/`
- **Runbook:** Reference `docs/runbooks/legacy-parity-validation.md`

---

## 12. Debugging & Exception Cases

### Common Exceptions

| Exception | Cause | Expected | Actual | Resolution |
|-----------|-------|----------|--------|------------|
| 计划号 missing | Empty/null in source | company_id resolution fails | company_id = NULL | Verify ID3/ID4 fallback triggered |
| 机构名称 not in mapping | New branch or typo | 机构代码 = NaN | 机构代码 = 'G00' | Check COMPANY_BRANCH_MAPPING completeness |
| 组合代码 starts with 'F' | Legacy format | 'F001' | '001' | Regex replacement applied |
| 月度 parse failure | Unexpected format | datetime | Original string | Check parse_to_standard_date() patterns |
| company_id empty after resolution | No mapping match | NULL | NULL | **Expected** - ID5 fallback disabled |

### Troubleshooting Steps

1. **company_id is NULL:**
   - Check 计划号 exists in COMPANY_ID1_MAPPING
   - Check 客户名称 (normalized) exists in COMPANY_ID4_MAPPING
   - Verify ID5 fallback is NOT being used (intentional)

2. **机构代码 is 'G00' unexpectedly:**
   - Check 机构名称 value in source data
   - Verify COMPANY_BRANCH_MAPPING includes all manual overrides
   - Check for 'null' string (not NaN) in source

3. **组合代码 incorrect:**
   - Verify regex '^F' removal applied first
   - Check 业务类型 value for conditional logic
   - Verify 计划类型 exists in DEFAULT_PORTFOLIO_CODE_MAPPING

4. **Date parsing failed:**
   - Check input format against supported patterns
   - Verify no extra whitespace or characters
   - Check for mixed formats in same column

### ID5 Fallback Verification

**Critical Check:** Ensure ID5 fallback is NOT implemented:

```python
# This code should NOT exist in new implementation:
# mask = df['company_id'].isna() | (df['company_id'] == '')
# company_id_from_account = df['年金账户名'].map(COMPANY_ID5_MAPPING)
# df.loc[mask, 'company_id'] = company_id_from_account[mask]
```

**Validation:** Compare company_id values between legacy (with ID5) and new (without ID5) - document all differences.

---

## 13. Compatibility Notes

### Technology Stack Alignment

Per `docs/architecture/technology-stack.md`:

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | Required |
| pandas | Locked version | No known breaking changes |
| Pydantic | 2.11.7+ | Schema validation |
| pandera | Latest | DataFrame validation |
| Dagster | Latest | Orchestration |
| uv | Latest | Package management |
| Ruff | 0.12.12+ | Linting |
| mypy | 1.17.1+ | Type checking (strict) |

### Breaking Changes

**No known breaking changes** for this domain migration.

### Migration Considerations

1. **Clean Architecture:** Infrastructure/domain layers must not depend on io/orchestration
2. **6-file standard:** Follow Epic 5 domain structure
3. **CleansingRegistry:** Use infrastructure layer utilities where available
4. **CompanyIdResolver:** Use standard infrastructure component (no custom ID5 logic)

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-05 | Claude (AI) | Initial documentation from legacy code analysis |

---

## References

- [Legacy Source: data_cleaner.py:237-274](../../legacy/annuity_hub/data_handler/data_cleaner.py)
- [Legacy Source: mappings.py](../../legacy/annuity_hub/data_handler/mappings.py)
- [Legacy Source: common_utils.py:264-343](../../legacy/annuity_hub/common_utils/common_utils.py)
- [Template: cleansing-rules-template.md](../templates/cleansing-rules-template.md)
- [Tech Spec: Epic 5.5](../sprint-artifacts/tech-spec-epic-5.5-pipeline-architecture-validation.md)
- [Infrastructure Layer](../architecture/infrastructure-layer.md)
- [Technology Stack](../architecture/technology-stack.md)
- [Parity Validation Runbook](../runbooks/legacy-parity-validation.md)

---

**Reviewer Sign-off:** _________________ Date: _________
