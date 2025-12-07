# Critical Issue Report: Resolver Pipeline Inconsistency

**Date:** 2025-12-07
**Status:** Confirmed via Code Analysis & Verification Script
**Component:** `CompanyIdResolver` (Infrastructure Layer)

## 1. Executive Summary
A critical gap exists between the **Backflow/Async population mechanism** and the **Resolver lookup mechanism**.
- **Population:** The Async Enrichment flow (Story 6.5 intent) uses aggressive normalization (`normalize_for_temp_id`) to generate keys for the database.
- **Backflow:** The current Backflow implementation (Story 6.4) only uses `.strip()`, creating "dirty" keys in the database.
- **Lookup:** The Resolver lookup (Story 6.4) uses **Raw/Stripped** names from the pipeline, failing to match the aggressively normalized keys that the system intends to learn.

**Impact:** The "Self-Learning" loop is broken. The system will write high-quality data to the cache (via Async) but will fail to read it back during subsequent runs, leading to permanent cache misses and wasted EQC budget.

## 2. Technical Evidence

### A. Lookup Logic (Current Implementation)
*File:* `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
*Method:* `_resolve_via_db_cache`

```python
# CURRENT CODE (Simplified)
# It takes values directly from the DataFrame column
values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
# It sends these RAW strings to the repository
results = self.mapping_repository.lookup_batch(list(alias_names))
```
*Result:* Queries DB for `"  Company A - Status  "`. Misses cache entry `"Company A"`.

### B. Backflow Logic (Current Implementation)
*File:* `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
*Method:* `_backflow_new_mappings`

```python
# CURRENT CODE
alias_value = row[column]
# Only simple stripping is applied
new_mappings.append({
    "alias_name": str(alias_value).strip(),
    ...
})
```
*Result:* Writes `"  Company A - Status  "` (stripped) to DB.
*Conflict:* If Async Worker writes `"Company A"`, we now have two fragmented entries or a miss.

### C. Async/Temp ID Logic (Story 6.2/6.5 Intent)
*File:* `src/work_data_hub/infrastructure/enrichment/normalizer.py`
*Method:* `normalize_for_temp_id`

This function performs aggressive cleaning (brackets, status markers, etc.). This is the **Target Standard**.

## 3. Required Fix (Story 6.4.1)

To restore the feedback loop, we must align all read/write paths to the **Target Standard**.

### Fix 1: Normalized Lookup
The Resolver must normalize candidates *before* querying the repository.
```python
# PROPOSED LOGIC
# 1. Get raw values
raw_values = df[col].unique()
# 2. Normalize them
lookup_map = {normalize_for_temp_id(v): v for v in raw_values}
# 3. Query DB with NORMALIZED keys
results = repo.lookup_batch(list(lookup_map.keys()))
```

### Fix 2: Normalized Backflow
The Backflow must normalize candidates *before* writing to the repository.
```python
# PROPOSED LOGIC
normalized_alias = normalize_for_temp_id(str(alias_value))
if normalized_alias:
    new_mappings.append({
        "alias_name": normalized_alias,
        ...
    })
```

## 4. Verification Plan
After applying Story 6.4.1, the validation script `scripts/validation/epic6/verify_resolver_flow.py` must pass, confirming:
1. Backflow writes Normalized Name (for P4 only).
2. Lookup queries with Normalized Name (for P4 only).

## 5. Correction (2025-12-07)

> **IMPORTANT:** The original analysis in Sections 1-3 was partially incorrect. This section provides the corrected understanding based on legacy system analysis.

### Original Analysis Issue

The original analysis suggested using `normalize_for_temp_id` for **ALL** lookup/backflow operations across all priority levels. This was **incorrect** based on legacy system analysis.

### Corrected Understanding

After reviewing the legacy implementation (`legacy/annuity_hub/data_handler/data_cleaner.py` and `mappings.py`):

| Priority | Field | Lookup/Backflow Key | Rationale |
|----------|-------|---------------------|-----------|
| P1 (Plan) | 计划代码 | **RAW** | System-generated identifier |
| P2 (Account) | 年金账户号 | **RAW** | Structured identifier |
| P3 (Hardcode) | 硬编码 | **RAW** | Explicit business rules |
| P4 (Name) | 客户名称 | **NORMALIZED** | High variance, needs cleaning |
| P5 (Account Name) | 年金账户名 | **RAW** | Stored as-is in legacy DB |

### Key Finding from Legacy Code

```python
# legacy/annuity_hub/data_handler/data_cleaner.py (Line 246-279)

# P4: Customer name is CLEANED before lookup
df["客户名称"] = df["客户名称"].apply(
    lambda x: clean_company_name(x) if isinstance(x, str) else x
)
company_id_from_customer = df["客户名称"].map(COMPANY_ID4_MAPPING)

# P5: Account name uses RAW value
company_id_from_account = df["年金账户名"].map(COMPANY_ID5_MAPPING)
```

### Correct Fix (Revised)

**Only P4 (客户名称)** should use `normalize_company_name` for lookup and backflow. All other priorities should continue using RAW values.

Use `normalize_company_name` (from `infrastructure/cleansing/rules/string_rules.py`) instead of `normalize_for_temp_id` because:
1. `normalize_company_name` aligns with legacy `clean_company_name` behavior
2. `normalize_for_temp_id` includes lowercase conversion which is NOT in legacy

### References

- **Detailed Analysis:** `docs/specific/backflow/legacy-company-id-matching-logic.md`
- **Sprint Change Proposal:** `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-07-p4-normalization-fix.md`

## 6. Resolution (Story 6.4.1 Implementation)

**Date:** 2025-12-07
**Status:** ✅ RESOLVED

### Implementation Summary

Story 6.4.1 has been implemented to fix the P4 normalization inconsistency. The following changes were made:

#### A. `_resolve_via_db_cache` Method (Lines 415-509)

```python
# IMPLEMENTED CODE
# P4 (customer_name) needs normalization, others use RAW values
lookup_columns = [
    (strategy.plan_code_column, False),       # P1: RAW
    (strategy.account_number_column, False),  # P2: RAW
    (strategy.customer_name_column, True),    # P4: NORMALIZED
    (strategy.account_name_column, False),    # P5: RAW
]

# For P4 values, apply normalize_company_name before lookup
if needs_normalization:
    lookup_key = normalize_company_name(str_value)
    if not lookup_key:
        continue
else:
    lookup_key = str_value
```

#### B. `_backflow_new_mappings` Method (Lines 604-669)

```python
# IMPLEMENTED CODE
# P4 (customer_name) needs normalization, others use RAW values
backflow_fields = [
    (strategy.account_number_column, "account", 2, False),     # P2: RAW
    (strategy.customer_name_column, "name", 4, True),          # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
]

# For P4 values, apply normalize_company_name before backflow
if needs_normalization:
    alias_name = normalize_company_name(str(alias_value))
    if not alias_name:
        continue  # Skip if normalization returns empty
else:
    alias_name = str(alias_value).strip()
```

### Test Coverage

12 unit tests added covering:
- P4 lookup normalization (AC1)
- P4 backflow normalization (AC2)
- P1/P2/P3/P5 RAW value preservation (AC3)
- Edge cases: special characters, full-width conversion, empty results (AC4)
- Integration: round-trip backflow → lookup cache hit (AC5)

### Verification

All tests pass:
```
tests/unit/infrastructure/enrichment/test_company_id_resolver.py::TestP4NormalizationDbCacheLookup - 4 passed
tests/unit/infrastructure/enrichment/test_company_id_resolver.py::TestP4NormalizationBackflow - 4 passed
tests/unit/infrastructure/enrichment/test_company_id_resolver.py::TestP4NormalizationEdgeCases - 3 passed
tests/unit/infrastructure/enrichment/test_company_id_resolver.py::TestP4NormalizationIntegration - 1 passed
```

### Files Modified

| File | Action |
|------|--------|
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | MODIFIED - Added P4 normalization |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | MODIFIED - Added 12 tests |
| `docs/specific/backflow/critical-issue-resolver-inconsistency.md` | UPDATED - Added resolution section |
