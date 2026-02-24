# Annuity Income Processing Gap Analysis

> **Date:** 2025-12-29
> **Author:** Link (via Quick Flow Solo Dev)
> **Status:** Issue Documented, Pending Fix
> **Related Epic:** Epic 7.3 (Multi-Domain Consistency Fixes)
> **Blocking:** Epic 8 (Testing & Validation Infrastructure)

---

## 1. Executive Summary

During post-ETL data verification for period `202510`, four processing inconsistencies were discovered between `annuity_performance` and `annuity_income` domains:

| Issue | Severity | Impact |
|-------|----------|--------|
| `company_id` lacks multi-priority matching | **Critical** | All `annuity_income` records have temporary IDs only |
| `客户名称` incorrectly filled from `计划名称` | **High** | Produces redundant/incorrect customer name data |
| `计划代码` missing corrections and defaults | **Medium** | Inconsistent plan code processing |
| `组合代码` processing logic differs | **Low** | Minor inconsistencies in portfolio code handling |

---

## 2. Discovery Context

### 2.1 Verification Command

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains --period 202510 --file-selection newest --execute --no-enrichment
```

### 2.2 ETL Results

| Domain | Status | Rows Inserted |
|--------|--------|---------------|
| `annuity_performance` | ✅ Success | 37,121 |
| `annuity_income` | ✅ Success | 13,639 |

### 2.3 Data Verification Queries

```sql
-- annuity_performance: 37,121 rows, 7 null customer names, 0 null company_ids
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN "客户名称" IS NULL THEN 1 ELSE 0 END) AS customer_name_nulls,
       SUM(CASE WHEN "company_id" IS NULL THEN 1 ELSE 0 END) AS company_id_nulls
FROM "business"."规模明细" WHERE "月度" = '2025-10-01';

-- annuity_income: 13,639 rows, 0 null customer names, 0 null company_ids
-- BUT: All company_ids are temporary IDs (HMAC-generated)
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN "客户名称" IS NULL THEN 1 ELSE 0 END) AS customer_name_nulls,
       SUM(CASE WHEN "company_id" IS NULL THEN 1 ELSE 0 END) AS company_id_nulls
FROM "business"."收入明细" WHERE "月度" = '2025-10-01';
```

---

## 3. Issue 1: `company_id` Lacks Multi-Priority Matching

### 3.1 Problem Description

`annuity_income` domain generates only **temporary IDs** for `company_id`, while `annuity_performance` uses a multi-priority resolution strategy that includes:

1. Plan code override mapping (YAML)
2. Account name mapping
3. Database cache lookup (`CompanyMappingRepository`)
4. EQC API lookup (when enabled)
5. Temporary ID generation (fallback)

The `annuity_income` domain is missing step 3 (database cache lookup) entirely.

### 3.2 Root Cause Analysis

#### 3.2.1 `annuity_performance/service.py` (Correct Implementation)

**File:** `src/work_data_hub/domain/annuity_performance/service.py`
**Lines:** 194-208, 231-236

```python
# Lines 194-208: Initialize CompanyMappingRepository
mapping_repository: Optional[CompanyMappingRepository] = None
repo_connection = None
try:
    from sqlalchemy import create_engine
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())
    repo_connection = engine.connect()
    mapping_repository = CompanyMappingRepository(repo_connection)
except Exception as e:
    logger.warning("Failed to initialize CompanyMappingRepository", error=str(e))
    mapping_repository = None
    repo_connection = None

# Lines 231-236: Pass to pipeline builder
pipeline = build_bronze_to_silver_pipeline(
    eqc_config=eqc_config,
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    mapping_repository=mapping_repository,  # ✅ Passed!
)
```

#### 3.2.2 `annuity_income/service.py` (Missing Implementation)

**File:** `src/work_data_hub/domain/annuity_income/service.py`
**Lines:** 253-258

```python
# Lines 253-258: NO CompanyMappingRepository initialization!
plan_overrides = load_plan_override_mapping()
pipeline = build_bronze_to_silver_pipeline(
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
    # ❌ Missing: mapping_repository parameter!
)
```

#### 3.2.3 `annuity_income/pipeline_builder.py` (Missing Parameter)

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`

**`CompanyIdResolutionStep.__init__()` - Lines 95-126:**
```python
def __init__(
    self,
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
    # ❌ Missing: mapping_repository parameter!
) -> None:
    self._resolver = CompanyIdResolver(
        eqc_config=eqc_config,
        enrichment_service=enrichment_service,
        yaml_overrides=yaml_overrides,
        # ❌ Missing: mapping_repository=mapping_repository!
    )
```

**`build_bronze_to_silver_pipeline()` - Lines 161-167:**
```python
def build_bronze_to_silver_pipeline(
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
    # ❌ Missing: mapping_repository parameter!
) -> Pipeline:
```

### 3.3 Comparison Table

| Component | `annuity_performance` | `annuity_income` | Gap |
|-----------|----------------------|------------------|-----|
| `service.py` - `CompanyMappingRepository` init | ✅ Lines 194-208 | ❌ Missing | Critical |
| `service.py` - Pass `mapping_repository` | ✅ Line 235 | ❌ Missing | Critical |
| `pipeline_builder.py` - `build_bronze_to_silver_pipeline()` param | ✅ Line 218 | ❌ Missing | Critical |
| `pipeline_builder.py` - `CompanyIdResolutionStep.__init__()` param | ✅ Line 147 | ❌ Missing | Critical |
| `pipeline_builder.py` - Pass to `CompanyIdResolver` | ✅ Line 172 | ❌ Missing | Critical |

---

## 4. Issue 2: `客户名称` Incorrectly Filled from `计划名称`

### 4.1 Problem Description

When `客户名称` (customer name) is null/empty, `annuity_income` domain incorrectly fills it with `计划名称` (plan name), then falls back to literal string `"UNKNOWN"`. This produces redundant/incorrect data.

**Expected behavior (per `annuity_performance`):** Keep `客户名称` as null when source data is null.

### 4.2 Root Cause Analysis

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
**Lines:** 41-51

```python
def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Fallback customer name to 计划名称, then UNKNOWN."""
    if "客户名称" in df.columns:
        base = df["客户名称"]
    else:
        base = pd.Series([pd.NA] * len(df), index=df.index)

    plan_names = df.get("计划名称", pd.Series([pd.NA] * len(df), index=df.index))
    base = base.combine_first(plan_names)  # ❌ WRONG: Uses plan name as fallback!

    return base.fillna("UNKNOWN")  # ❌ WRONG: Then fills with "UNKNOWN"!
```

**Usage in pipeline (Line 228):**
```python
CalculationStep(
    {
        "客户名称": _fill_customer_name,  # ❌ Called here
        ...
    }
),
```

### 4.3 Comparison with `annuity_performance`

**File:** `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`

`annuity_performance` does **NOT** have a `_fill_customer_name` function. It preserves `客户名称` as-is (including null values).

The only customer name processing is in the output model validator:

**File:** `src/work_data_hub/domain/annuity_performance/models.py`
**Lines:** 334-339

```python
@field_validator("客户名称", mode="before")
@classmethod
def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
    # Story 7.3-2: Use shared clean_customer_name function
    field_name = info.field_name or "客户名称"
    return clean_customer_name(v, field_name, CLEANSING_DOMAIN)
    # ✅ Returns None if input is None - no fallback to plan name!
```

---

## 5. Issue 3: `计划代码` Missing Corrections and Defaults

### 5.1 Problem Description

`annuity_income` domain is missing two plan code processing steps that exist in `annuity_performance`:

1. **Plan Code Corrections** - Fixing known typos (e.g., `1P0290` → `P0290`)
2. **Plan Code Defaults** - Assigning default codes for empty values based on plan type

### 5.2 Root Cause Analysis

#### 5.2.1 `annuity_performance/constants.py` (Has Configurations)

**File:** `src/work_data_hub/domain/annuity_performance/constants.py`
**Lines:** 39-40

```python
PLAN_CODE_CORRECTIONS: Dict[str, str] = {"1P0290": "P0290", "1P0807": "P0807"}
PLAN_CODE_DEFAULTS: Dict[str, str] = {"集合计划": "AN001", "单一计划": "AN002"}
```

#### 5.2.2 `annuity_income/constants.py` (Missing Configurations)

**File:** `src/work_data_hub/domain/annuity_income/constants.py`

```python
# ❌ No PLAN_CODE_CORRECTIONS defined
# ❌ No PLAN_CODE_DEFAULTS defined
```

#### 5.2.3 Pipeline Processing Comparison

**`annuity_performance/pipeline_builder.py`:**

```python
# Step 3: Plan code corrections
ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),

# Step 4: Plan code defaults (empty → AN001 for 集合计划, AN002 for 单一计划)
CalculationStep({
    "计划代码": lambda df: _apply_plan_code_defaults(df),
}),
```

**`annuity_income/pipeline_builder.py`:**

```python
# Step 2: Plan code normalization (uppercase ONLY - no corrections or defaults!)
CalculationStep({
    "计划代码": lambda df: (
        df.get("计划代码", pd.Series([pd.NA] * len(df), index=df.index))
    ).astype("string").str.upper(),
}),
# ❌ No ReplacementStep for corrections
# ❌ No _apply_plan_code_defaults function
```

### 5.3 Comparison Table

| Processing Step | `annuity_performance` | `annuity_income` | Gap |
|-----------------|----------------------|------------------|-----|
| Column rename (`计划号` → `计划代码`) | ✅ COLUMN_MAPPING | ✅ COLUMN_ALIAS_MAPPING | None |
| Plan code corrections | ✅ ReplacementStep | ❌ Missing | Medium |
| Empty value defaults (AN001/AN002) | ✅ _apply_plan_code_defaults | ❌ Missing | Medium |
| Uppercase normalization | ❌ (handled in model) | ✅ Pipeline Step 2 | Minor |

### 5.4 Data Impact

Current `202510` data shows no evidence of this gap (no `1P0290`, `1P0807`, `AN001`, or `AN002` codes), but the code paths are inconsistent and may cause issues with future data.

---

## 6. Issue 4: `组合代码` Processing Logic Differs

### 6.1 Problem Description

Both domains apply similar portfolio code processing, but the implementation details differ:

1. **annuity_performance** uses a dedicated `_clean_portfolio_code()` helper function
2. **annuity_income** uses inline pandas string methods with different behavior

### 6.2 Root Cause Analysis

#### 6.2.1 `annuity_performance/pipeline_builder.py` (Helper Function)

**File:** `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`
**Lines:** 98-136

```python
def _clean_portfolio_code(value) -> Optional[str]:
    """Clean and normalize portfolio code value."""
    # Handle None values
    if pd.isna(value):
        return None

    # Handle numeric values - preserve them as strings
    if isinstance(value, (int, float)):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)

    # Handle string values
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        # Remove 'F' or 'f' prefix if present
        if cleaned.upper().startswith("F"):
            cleaned = cleaned[1:]
        return cleaned if cleaned else None

    return None
```

**Usage in `_apply_portfolio_code_defaults()` (Line 76):**
```python
result = result.apply(lambda x: _clean_portfolio_code(x))
```

#### 6.2.2 `annuity_income/pipeline_builder.py` (Inline Processing)

**File:** `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
**Lines:** 54-72

```python
def _apply_portfolio_code_defaults(df: pd.DataFrame) -> pd.Series:
    if "组合代码" not in df.columns:
        result = pd.Series([None] * len(df), index=df.index)
    else:
        result = df["组合代码"].astype("string")
        # Step 1: Remove 'F' prefix (case-insensitive regex '^F')
        result = result.str.replace("^f", "", regex=True, flags=re.IGNORECASE)
        # Normalize empty placeholders to None
        result = result.replace({"nan": None, "None": None, "": None, pd.NA: None})
        # Standardize to uppercase strings
        result = result.str.upper()  # ❌ Different: forces uppercase
    # ... rest of defaults logic
```

### 6.3 Comparison Table

| Processing Step | `annuity_performance` | `annuity_income` | Gap |
|-----------------|----------------------|------------------|-----|
| Remove 'F' prefix | ✅ `cleaned[1:]` | ✅ `str.replace("^f", "")` | Same |
| Uppercase conversion | ❌ Preserves original case | ✅ Forces uppercase | Minor |
| Numeric value handling | ✅ Explicit int/float handling | ❌ Direct `astype("string")` | Minor |
| QTAN003 default (职年受托/职年投资) | ✅ | ✅ | None |
| Plan type defaults (QTAN001/QTAN002) | ✅ (excludes 职业年金) | ✅ (includes 职业年金) | Minor |

### 6.4 Data Impact

The differences are minor and unlikely to cause data quality issues:
- Uppercase conversion: Both tables show uppercase codes (QTAN001, QTAN002, etc.)
- Numeric handling: Existing data shows consistent string conversion

---

## 7. Data Impact Evidence

### 7.1 Sample Data Comparison

**`annuity_performance` (规模明细) - Null customer names preserved:**
```sql
SELECT "id", "计划代码", "客户名称", "company_id"
FROM "business"."规模明细"
WHERE "月度" = '2025-10-01' AND "客户名称" IS NULL
LIMIT 5;
```

| id | 计划代码 | 客户名称 | company_id |
|----|---------|---------|------------|
| 27261 | XNP717 | NULL | IN7KZNPWPCVQXJ6AY7 |
| 27262 | FP0001 | NULL | IN7KZNPWPCVQXJ6AY7 |
| 27263 | FP0002 | NULL | IN7KZNPWPCVQXJ6AY7 |

**`annuity_income` (收入明细) - No null customer names (all filled):**
```sql
SELECT "id", "计划代码", "客户名称", "company_id"
FROM "business"."收入明细"
WHERE "月度" = '2025-10-01'
LIMIT 5;
```

| id | 计划代码 | 客户名称 | company_id |
|----|---------|---------|------------|
| 1 | P0190 | 平安相伴今生企业年金集合计划 | INXELNISM3IAVLLWF5 |
| 2 | P0190 | 平安相伴今生企业年金集合计划 | INXELNISM3IAVLLWF5 |

Note: The `客户名称` values in `annuity_income` appear to be plan names, not actual customer names.

### 7.2 company_id Pattern Analysis

**`annuity_performance`:** Mixed IDs (some from database cache, some temporary)
**`annuity_income`:** All temporary IDs (HMAC pattern: `IN[A-Z0-9]{16}`)

---

## 8. Proposed Fix: Story 7.3-6

### 8.1 Scope

| Change | File | Lines | Effort | Priority |
|--------|------|-------|--------|----------|
| Add `CompanyMappingRepository` init | `annuity_income/service.py` | +15 | Low | **Critical** |
| Add `mapping_repository` param to `CompanyIdResolutionStep` | `annuity_income/pipeline_builder.py` | +3 | Low | **Critical** |
| Add `mapping_repository` param to `build_bronze_to_silver_pipeline` | `annuity_income/pipeline_builder.py` | +2 | Low | **Critical** |
| Pass `mapping_repository` to `CompanyIdResolver` | `annuity_income/pipeline_builder.py` | +1 | Low | **Critical** |
| Fix `_fill_customer_name` to NOT use plan name fallback | `annuity_income/pipeline_builder.py` | ~5 | Low | **High** |
| Add `PLAN_CODE_CORRECTIONS` to constants | `annuity_income/constants.py` | +1 | Low | Medium |
| Add `PLAN_CODE_DEFAULTS` to constants | `annuity_income/constants.py` | +1 | Low | Medium |
| Add `ReplacementStep` for plan code corrections | `annuity_income/pipeline_builder.py` | +1 | Low | Medium |
| Add `_apply_plan_code_defaults` function | `annuity_income/pipeline_builder.py` | +20 | Low | Medium |
| Unify `_clean_portfolio_code` helper | `annuity_income/pipeline_builder.py` | +40 | Low | Low |
| Update tests | `tests/domain/annuity_income/` | ~30 | Medium | - |

**Total Estimated Effort:** 3-4 hours

### 8.2 Detailed Changes

#### Change 1: `annuity_income/service.py` - Add `CompanyMappingRepository` (Critical)

```python
# Add imports at top:
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)

# In process_with_enrichment(), before building pipeline:
mapping_repository: Optional[CompanyMappingRepository] = None
repo_connection = None
try:
    from sqlalchemy import create_engine
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())
    repo_connection = engine.connect()
    mapping_repository = CompanyMappingRepository(repo_connection)
except Exception as e:
    logger.bind(domain="annuity_income", step="mapping_repository").warning(
        "Failed to initialize CompanyMappingRepository; proceeding without DB cache",
        error=str(e),
    )
    mapping_repository = None
    repo_connection = None

# Pass to build_bronze_to_silver_pipeline():
pipeline = build_bronze_to_silver_pipeline(
    enrichment_service=enrichment_service,
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
    mapping_repository=mapping_repository,  # NEW!
)
```

#### Change 2: `annuity_income/pipeline_builder.py` - Add `mapping_repository` Parameter (Critical)

```python
# CompanyIdResolutionStep.__init__():
def __init__(
    self,
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,  # NEW!
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
) -> None:
    self._resolver = CompanyIdResolver(
        eqc_config=eqc_config,
        enrichment_service=enrichment_service,
        yaml_overrides=yaml_overrides,
        mapping_repository=mapping_repository,  # NEW!
    )

# build_bronze_to_silver_pipeline():
def build_bronze_to_silver_pipeline(
    eqc_config: EqcLookupConfig = None,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    plan_override_mapping: Optional[Dict[str, str]] = None,
    mapping_repository=None,  # NEW!
    generate_temp_ids: bool = True,
    sync_lookup_budget: int = 0,
) -> Pipeline:
    # ...
    CompanyIdResolutionStep(
        eqc_config=eqc_config,
        enrichment_service=enrichment_service,
        plan_override_mapping=plan_override_mapping,
        mapping_repository=mapping_repository,  # NEW!
        generate_temp_ids=generate_temp_ids,
        sync_lookup_budget=sync_lookup_budget,
    ),
```

#### Change 3: `annuity_income/pipeline_builder.py` - Fix `_fill_customer_name` (High)

```python
def _fill_customer_name(df: pd.DataFrame) -> pd.Series:
    """Keep customer name as-is, allow null (consistent with annuity_performance).

    Story 7.3-6: Removed plan name fallback to match annuity_performance behavior.
    """
    if "客户名称" in df.columns:
        return df["客户名称"]  # Keep as-is, including nulls
    else:
        return pd.Series([pd.NA] * len(df), index=df.index)
```

#### Change 4: `annuity_income/constants.py` - Add Plan Code Configurations (Medium)

```python
# Add to constants.py:
PLAN_CODE_CORRECTIONS: Dict[str, str] = {"1P0290": "P0290", "1P0807": "P0807"}
PLAN_CODE_DEFAULTS: Dict[str, str] = {"集合计划": "AN001", "单一计划": "AN002"}
```

#### Change 5: `annuity_income/pipeline_builder.py` - Add Plan Code Processing (Medium)

```python
# Add import:
from work_data_hub.infrastructure.transforms import ReplacementStep

# Add after MappingStep:
ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS}),

# Add function:
def _apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (consistent with annuity_performance)."""
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, "AN001")
        result = result.mask(single_mask, "AN002")

    return result
```

#### Change 6: `annuity_income/pipeline_builder.py` - Unify Portfolio Code Helper (Low, Optional)

```python
# Extract shared _clean_portfolio_code function to infrastructure layer
# or copy from annuity_performance for consistency.
# This is optional as the current inline implementation produces correct results.
```

### 8.3 Acceptance Criteria

**Critical (Must Fix):**
- [ ] AC1: `annuity_income` `company_id` resolution uses database cache lookup
- [ ] AC2: `annuity_income` `客户名称` preserves null values (no plan name fallback)
- [ ] AC3: After re-running ETL, `annuity_income` has mix of cached IDs and temp IDs (same pattern as `annuity_performance`)

**High (Should Fix):**
- [ ] AC4: `annuity_income` applies `PLAN_CODE_CORRECTIONS` mapping
- [ ] AC5: `annuity_income` applies `PLAN_CODE_DEFAULTS` for empty plan codes

**Medium (Nice to Have):**
- [ ] AC6: `组合代码` processing uses shared `_clean_portfolio_code` helper

**General:**
- [ ] AC7: All existing tests pass
- [ ] AC8: New unit tests verify consistent behavior between domains

---

## 9. Comprehensive Shared Field Analysis

This section provides a systematic comparison of all shared fields between `annuity_performance` and `annuity_income` domains, identifying inconsistencies and opportunities for infrastructure layer extraction.

### 9.1 Field-by-Field Comparison Matrix

#### 9.1.1 Model Validators (models.py)

| Field | annuity_performance | annuity_income | Status | Notes |
|-------|---------------------|----------------|--------|-------|
| **月度** | `date` (Out), `parse_yyyymm_or_chinese` | `date` (Out), `parse_yyyymm_or_chinese` | ✅ Consistent | Both use shared `parse_yyyymm_or_chinese` |
| **计划代码** | `normalize_plan_code(allow_null=True)` | `normalize_plan_code(allow_null=False)` | ⚠️ Intentional | Business requirement: annuity_income requires plan code (composite PK) |
| **company_id** | `normalize_company_id()` | `normalize_company_id()` | ✅ Consistent | Both use shared validator from infrastructure |
| **客户名称** | `clean_customer_name()` | `clean_customer_name()` | ✅ Consistent | Model validators consistent; pipeline filling differs (Issue 2) |
| **业务类型** | `Optional[str]` | `Optional[str]` | ✅ Consistent | No special validator |
| **计划类型** | `Optional[str]` | `Optional[str]` | ✅ Consistent | No special validator |
| **组合代码** | `Optional[str]` | `Optional[str]` | ⚠️ Gap | Processing logic differs (Issue 4) |
| **机构代码** | `Optional[str]` | `str` (required) | ⚠️ Intentional | Business requirement: annuity_income requires institution code |
| **机构名称** | `Optional[str]` | `Optional[str]` | ✅ Consistent | No special validator |
| **产品线代码** | `Optional[str]` | `str` (required) | ⚠️ Intentional | Business requirement: annuity_income requires product line |
| **年金账户名** | `Optional[str]` | `Optional[str]` | ✅ Consistent | No special validator |
| **计划名称** | `Optional[str]` | `Optional[str]` (7.3-4) | ✅ Consistent | Added to annuity_income in Story 7.3-4 |
| **组合类型** | `Optional[str]` | `Optional[str]` (7.3-4) | ✅ Consistent | Added to annuity_income in Story 7.3-4 |
| **组合名称** | `Optional[str]` | `Optional[str]` (7.3-4) | ✅ Consistent | Added to annuity_income in Story 7.3-4 |

#### 9.1.2 Pipeline Processing (pipeline_builder.py)

| Processing Step | annuity_performance | annuity_income | Status | Priority |
|-----------------|---------------------|----------------|--------|----------|
| **Column Mapping** | `COLUMN_MAPPING` | `COLUMN_ALIAS_MAPPING` | ⚠️ Gap | Low |
| **Plan Code Corrections** | `ReplacementStep(PLAN_CODE_CORRECTIONS)` | ❌ Missing | ⚠️ Gap | Medium |
| **Plan Code Defaults** | `_apply_plan_code_defaults()` | ❌ Missing | ⚠️ Gap | Medium |
| **Customer Name Fallback** | None (preserves null) | `_fill_customer_name()` (uses 计划名称) | ⚠️ Gap | **High** |
| **Portfolio Code Processing** | `_clean_portfolio_code()` helper | Inline pandas str methods | ⚠️ Gap | Low |
| **CompanyIdResolver mapping_repository** | ✅ Passed | ❌ Missing | ⚠️ Gap | **Critical** |
| **Institution Code Mapping** | `机构名称` → lookup → `机构代码` | `机构` → direct → `机构代码` | ⚠️ Gap | Low |
| **年金账户号 Derivation** | `集团企业客户号.str.lstrip("C")` | ❌ Missing | ⚠️ Gap | Low |

#### 9.1.3 Constants (constants.py)

| Constant | annuity_performance | annuity_income | Status |
|----------|---------------------|----------------|--------|
| `PLAN_CODE_CORRECTIONS` | ✅ Defined | ❌ Missing | **Gap** |
| `PLAN_CODE_DEFAULTS` | ✅ Defined | ❌ Missing | **Gap** |
| `COLUMN_MAPPING` | `{"机构": "机构名称", "计划号": "计划代码", ...}` | `{"机构": "机构代码", "计划号": "计划代码"}` | Different |
| `LEGACY_COLUMNS_TO_DELETE` | Includes `集团企业客户号`, `集团企业客户名称` | Includes `机构名称` | Different (expected) |
| `DEFAULT_INSTITUTION_CODE` | ✅ `"G00"` | ✅ `"G00"` | ✅ Consistent |
| Shared mappings from `infrastructure.mappings` | ✅ All imported | ✅ All imported | ✅ Consistent |

### 9.2 Issue 5: Column Mapping Strategy Differences

#### 9.2.1 Problem Description

The two domains use different strategies for mapping the `机构` (institution) column:

**annuity_performance (`constants.py` Line 60-65):**
```python
COLUMN_MAPPING: Dict[str, str] = {
    "机构": "机构名称",  # → Then lookup COMPANY_BRANCH_MAPPING → 机构代码
    "计划号": "计划代码",
    ...
}
```

**annuity_income (`constants.py` Line 15-18):**
```python
COLUMN_ALIAS_MAPPING: Dict[str, str] = {
    "机构": "机构代码",  # → Direct mapping, then lookup
    "计划号": "计划代码",
}
```

#### 9.2.2 Impact Analysis

- **Data Flow Difference:**
  - `annuity_performance`: `机构` → `机构名称` → `COMPANY_BRANCH_MAPPING[机构名称]` → `机构代码`
  - `annuity_income`: `机构` → `机构代码` → `机构名称.map(COMPANY_BRANCH_MAPPING)` → overwrite `机构代码`

- **End Result:** Both produce correct `机构代码`, but through different paths

- **Recommendation:** Document as intentional difference (source data structure varies)

### 9.3 Issue 6: Required Field Differences

#### 9.3.1 Problem Description

Some fields that are optional in `annuity_performance` are required in `annuity_income`:

| Field | annuity_performance | annuity_income | Reason |
|-------|---------------------|----------------|--------|
| `计划代码` | Optional (model level) | **Required** (composite PK) | Business requirement |
| `机构代码` | Optional | **Required** | Business requirement |
| `产品线代码` | Optional | **Required** | Business requirement |
| `固费`, `浮费`, `回补`, `税` | N/A | **Required** (income fields) | Domain-specific |

#### 9.3.2 Recommendation

These differences are **intentional business requirements**, not gaps:
- `annuity_income` has stricter data quality requirements because it's used for financial reporting
- Document as "intentional domain differences" in domain documentation

### 9.4 Issue 7: Missing `年金账户号` Derivation

#### 9.4.1 Problem Description

`annuity_performance` derives `年金账户号` from `集团企业客户号` (with "C" prefix stripped), but `annuity_income` doesn't have this field.

**annuity_performance (`pipeline_builder.py` Lines 277-292):**
```python
# Step 9: Clean Group Enterprise Customer Number (lstrip "C")
CalculationStep({
    "集团企业客户号": lambda df: df["集团企业客户号"].str.lstrip("C")
    if "集团企业客户号" in df.columns
    else pd.Series([None] * len(df)),
}),
# Step 10: Derive 年金账户号 from cleaned 集团企业客户号
CalculationStep({
    "年金账户号": lambda df: df.get("集团企业客户号", pd.Series([None] * len(df))).copy(),
}),
```

#### 9.4.2 Recommendation

- **Priority:** Low
- **Action:** If `annuity_income` source data contains `集团企业客户号`, add similar derivation
- **Current Status:** `annuity_income` doesn't have `年金账户号` in gold output, so no gap

---

## 10. Infrastructure Extraction Recommendations

Based on the comprehensive analysis, the following items should be considered for extraction to the `infrastructure` layer:

### 10.1 High Priority (Story 7.3-6 Scope)

| Item | Current Location | Extraction Target | Rationale |
|------|------------------|-------------------|-----------|
| `CompanyMappingRepository` initialization | `annuity_performance/service.py` | Pass to `annuity_income/service.py` | Critical for company_id resolution |
| `mapping_repository` parameter | `annuity_performance/pipeline_builder.py` | Add to `annuity_income/pipeline_builder.py` | Required for database cache lookup |

### 10.2 Medium Priority (Future Story)

| Item | Current Location | Extraction Target | Rationale |
|------|------------------|-------------------|-----------|
| `_clean_portfolio_code()` | `annuity_performance/pipeline_builder.py` | `infrastructure/transforms/helpers.py` | Reusable helper function |
| `PLAN_CODE_CORRECTIONS` | `annuity_performance/constants.py` | `infrastructure/mappings/plan_codes.py` | Shared correction mapping |
| `PLAN_CODE_DEFAULTS` | `annuity_performance/constants.py` | `infrastructure/mappings/plan_codes.py` | Shared default mapping |
| `_apply_plan_code_defaults()` | `annuity_performance/pipeline_builder.py` | `infrastructure/transforms/helpers.py` | Reusable helper function |

### 10.3 Low Priority (Optional)

| Item | Current Location | Extraction Target | Rationale |
|------|------------------|-------------------|-----------|
| `年金账户号` derivation logic | `annuity_performance/pipeline_builder.py` | Document only | Domain-specific, not needed in annuity_income |
| Column mapping unification | Both `constants.py` | Document only | Different source data structures |

### 10.4 Already Extracted (Story 7.3-2/7.3-3)

The following validators have already been extracted to `infrastructure/cleansing/validators.py`:

- ✅ `apply_domain_rules()` - Generic domain rule applicator
- ✅ `clean_code_field()` - Bronze layer code field cleaner
- ✅ `normalize_plan_code()` - Gold layer plan code normalizer
- ✅ `normalize_company_id()` - Gold layer company_id normalizer
- ✅ `clean_customer_name()` - Gold layer customer name cleaner with domain rules
- ✅ `DEFAULT_COMPANY_RULES` - Common company name cleansing rules
- ✅ `DEFAULT_NUMERIC_RULES` - Common numeric field cleansing rules
- ✅ `MIN_YYYYMM_VALUE`, `MAX_YYYYMM_VALUE`, `MAX_DATE_RANGE_DAYS` - Date validation constants

---

## 11. Summary of Gaps by Severity

### 11.1 Critical (Must Fix for Data Integrity)

| Issue | ID | Story | Status |
|-------|-----|-------|--------|
| `company_id` lacks multi-priority matching | Issue 1 | 7.3-6 | Proposed |
| `mapping_repository` not passed to `CompanyIdResolver` | Issue 1 | 7.3-6 | Proposed |

### 11.2 High (Should Fix for Consistency)

| Issue | ID | Story | Status |
|-------|-----|-------|--------|
| `客户名称` incorrectly filled from `计划名称` | Issue 2 | 7.3-6 | Proposed |

### 11.3 Medium (Nice to Have)

| Issue | ID | Story | Status |
|-------|-----|-------|--------|
| `计划代码` missing corrections (`1P0290` → `P0290`) | Issue 3 | 7.3-6 | Proposed |
| `计划代码` missing defaults (`AN001`/`AN002`) | Issue 3 | 7.3-6 | Proposed |

### 11.4 Low (Document Only)

| Issue | ID | Story | Status |
|-------|-----|-------|--------|
| `组合代码` processing logic differs | Issue 4 | N/A | Documented |
| Column mapping strategy differs | Issue 5 | N/A | Documented (intentional) |
| Required field differences | Issue 6 | N/A | Documented (business requirement) |
| Missing `年金账户号` derivation | Issue 7 | N/A | Documented (not needed) |

---

## 12. References

- [Sprint Change Proposal: Multi-Domain Field Validation Consistency](../../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-29-multi-domain-consistency.md)
- [Shared Field Validators Analysis](./shared-field-validators-analysis.md)
- [Infrastructure Layer Documentation](../../architecture/infrastructure-layer.md)
- [Shared Validators Source](../../../src/work_data_hub/infrastructure/cleansing/validators.py)

---

_Generated by Quick Flow Solo Dev on 2025-12-29_
_Last Updated: 2025-12-29 (Added comprehensive field analysis)_
