# Legacy Company ID Matching Logic Analysis

**Created:** 2025-12-07
**Context:** Epic 6 - Company Enrichment Service
**Purpose:** Reference documentation for company ID resolution implementation

## 1. Overview

This document captures the exact matching logic used in the legacy system (`legacy/annuity_hub/`) for company ID resolution. Understanding this logic is critical for maintaining backward compatibility and ensuring the new implementation produces identical results.

## 2. Priority Hierarchy

The legacy system implements a **5-level priority hierarchy** for company ID resolution:

| Priority | Name | Source Table | Lookup Column | Key Type |
|----------|------|--------------|---------------|----------|
| P1 | Plan Code | `mapping.年金计划` | 计划代码 | **RAW** |
| P2 | Account Number | `enterprise.annuity_account_mapping` | 年金账户号 / 集团企业客户号 | **RAW** |
| P3 | Hardcode | Hardcoded dict | 计划代码 | **RAW** |
| P4 | Customer Name | `enterprise.company_id_mapping` | 客户名称 | **CLEANED** |
| P5 | Account Name | `business.规模明细` | 年金账户名 | **RAW** |

## 3. Legacy Implementation Details

### 3.1 Mapping Generation (mappings.py)

```python
# P1: Plan Code → Company ID (单一计划 only)
def get_company_id1_mapping():
    query = """
        SELECT `年金计划号`, `company_id`
        FROM mapping.`年金计划`
        WHERE `计划类型`= '单一计划' AND `年金计划号` != 'AN002';
    """
    return {row[0]: row[1] for row in rows}  # RAW key

# P2: Account Number → Company ID
def get_company_id2_mapping():
    query = """
        SELECT DISTINCT `年金账户号`, `company_id`
        FROM `annuity_account_mapping`
        WHERE `年金账户号` NOT LIKE 'GM%';
    """
    return {row[0]: row[1] for row in rows}  # RAW key

# P3: Hardcode (explicit business rules)
COMPANY_ID3_MAPPING = {
    "FP0001": "614810477",
    "FP0002": "614810477",
    "FP0003": "610081428",
    "P0809": "608349737",
    "SC002": "604809109",
    "SC007": "602790403",
    "XNP466": "603968573",
    "XNP467": "603968573",
    "XNP596": "601038164",
}

# P4: Customer Name → Company ID
def get_company_id4_mapping():
    query = """
        SELECT DISTINCT `company_name`, `company_id`
        FROM `company_id_mapping`;
    """
    return {row[0]: row[1] for row in rows}  # CLEANED key (stored cleaned in DB)

# P5: Account Name → Company ID
def get_company_id5_mapping():
    query = """
        SELECT DISTINCT `年金账户名`, `company_id`
        FROM `规模明细`
        WHERE `company_id` IS NOT NULL;
    """
    return {row[0]: row[1] for row in rows}  # RAW key
```

### 3.2 Resolution Flow (data_cleaner.py - AnnuityPerformanceCleaner)

```python
def _clean_method(self) -> pd.DataFrame:
    # CRITICAL: Clean customer name BEFORE P4 lookup
    # Line 246-249
    df["年金账户名"] = df["客户名称"]  # Preserve RAW value for P5
    df["客户名称"] = df["客户名称"].apply(
        lambda x: clean_company_name(x) if isinstance(x, str) else x
    )  # CLEANED value for P4

    # P1: Plan Code → RAW lookup
    # Line 252
    df["company_id"] = df["计划代码"].map(COMPANY_ID1_MAPPING)

    # P2: Account Number → RAW lookup (with prefix stripping)
    # Line 255-260
    df["集团企业客户号"] = df["集团企业客户号"].str.lstrip("C")
    mask = df["company_id"].isna() | (df["company_id"] == "")
    company_id_from_group = df["集团企业客户号"].map(COMPANY_ID2_MAPPING)
    df.loc[mask, "company_id"] = company_id_from_group[mask]

    # P3: Hardcode → RAW lookup (with fallback to 600866980)
    # Line 263-269
    mask = (df["company_id"].isna() | (df["company_id"] == "")) & (
        df["客户名称"].isna() | (df["客户名称"] == "")
    )
    company_id_from_plan = df["计划代码"].map(COMPANY_ID3_MAPPING).fillna("600866980")
    df.loc[mask, "company_id"] = company_id_from_plan[mask]

    # P4: Customer Name → CLEANED lookup
    # Line 272-274
    # NOTE: df["客户名称"] is already cleaned at this point!
    mask = df["company_id"].isna() | (df["company_id"] == "")
    company_id_from_customer = df["客户名称"].map(COMPANY_ID4_MAPPING)
    df.loc[mask, "company_id"] = company_id_from_customer[mask]

    # P5: Account Name → RAW lookup
    # Line 277-279
    # NOTE: df["年金账户名"] contains the ORIGINAL raw value!
    mask = df["company_id"].isna() | (df["company_id"] == "")
    company_id_from_account = df["年金账户名"].map(COMPANY_ID5_MAPPING)
    df.loc[mask, "company_id"] = company_id_from_account[mask]
```

## 4. clean_company_name() Function

**File:** `legacy/annuity_hub/common_utils/common_utils.py`

This function is used **only for P4 (Customer Name)** lookup. It performs the following transformations:

```python
def clean_company_name(name: str, to_fullwidth: bool = False) -> str:
    """
    清洗企业名称，包括去除多余空格、替换无效字符串，并可选地将字符从半角转换为全角或从全角转换为半角。
    """
    if not name:
        return ""

    # Step 1: Remove all whitespace
    name = re.sub(r"\s+", "", name)

    # Step 2: Remove business patterns
    name = re.sub(r"及下属子企业", "", name)
    name = re.sub(r"(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$", "", name)

    # Step 3: Remove status markers (29 patterns, sorted by length DESC)
    CORE_REPLACE_STRING = [
        "已转出", "待转出", "终止", "转出", "保留", "暂停", "注销", "清算", "解散",
        "吊销", "撤销", "停业", "歇业", "关闭", "迁出", "迁入", "变更", "合并",
        "分立", "破产", "重整", "托管", "接管", "整顿", "清盘", "退出", "终结",
        "结束", "完结", "已作废", "作废", "存量", "原"
    ]
    sorted_core_replace_string = sorted(CORE_REPLACE_STRING, key=lambda s: -len(s))

    for core_str in sorted_core_replace_string:
        # Remove at start (with optional brackets)
        pattern_start = rf"^([\(\（]?){re.escape(core_str)}([\)\）]?)(?=[^\u4e00-\u9fff]|$)"
        name = re.sub(pattern_start, "", name)

        # Remove at end (with optional separators and brackets)
        pattern_end = rf"(?<![\u4e00-\u9fff])([\-\(\（]?){re.escape(core_str)}([\)\）]?)[\-\(\（\)\）]*$"
        name = re.sub(pattern_end, "", name)

    # Step 4: Remove trailing punctuation
    name = re.sub(r"[\-\(\（\)\）]+$", "", name)

    # Step 5: Full-width ↔ Half-width conversion (default: to half-width)
    if to_fullwidth:
        name = "".join([
            chr(ord(char) + 0xFEE0) if 0x21 <= ord(char) <= 0x7E else char
            for char in name
        ])
    else:
        name = "".join([
            chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
            for char in name
        ])

    # Step 6: Normalize brackets to Chinese
    name = name.replace("(", "（").replace(")", "）")

    return name
```

### 4.1 Transformation Examples

| Input | Output |
|-------|--------|
| `"中国平安 "` | `"中国平安"` |
| `"中国平安-已转出"` | `"中国平安"` |
| `"中国平安（已转出）"` | `"中国平安"` |
| `"中国平安(集团)"` | `"中国平安（集团）"` |
| `"中国平安Ａ"` (full-width A) | `"中国平安A"` (half-width) |
| `"中国平安及下属子企业"` | `"中国平安"` |

## 5. Key Differences: clean_company_name vs normalize_for_temp_id

The new system has `normalize_for_temp_id()` which is similar but **adds lowercase conversion**:

| Step | clean_company_name | normalize_for_temp_id |
|------|-------------------|----------------------|
| Remove whitespace | ✅ | ✅ |
| Remove business patterns | ✅ | ✅ |
| Remove status markers | ✅ | ✅ |
| Remove trailing punctuation | ✅ | ✅ |
| Full-width → Half-width | ✅ | ✅ |
| Normalize brackets | ✅ | ✅ |
| **Lowercase** | ❌ | ✅ |

**Important:** For P4 lookup compatibility with legacy data, we should use `clean_company_name()` logic (without lowercase) rather than `normalize_for_temp_id()`.

## 6. Lookup Key Strategy Summary

| Priority | Field | Lookup Key | Backflow Key | Rationale |
|----------|-------|------------|--------------|-----------|
| **P1** | 计划代码 | RAW | RAW | System-generated identifier |
| **P2** | 年金账户号 | RAW | RAW | Structured identifier |
| **P3** | 硬编码 | RAW | N/A | Explicit business rules |
| **P4** | 客户名称 | **CLEANED** | **CLEANED** | High variance, needs normalization |
| **P5** | 年金账户名 | RAW | RAW | User-entered but stored as-is |

## 7. Implementation Implications

### 7.1 Current Implementation Issues

The current `CompanyIdResolver` implementation has the following issues:

1. **P4 Lookup:** Uses RAW customer name, but database stores CLEANED names → Cache miss
2. **P4 Backflow:** Writes RAW customer name, but should write CLEANED name → Data inconsistency

### 7.2 Required Fixes

Only **P4 (Customer Name)** needs modification:

```python
# In _resolve_via_db_cache():
# For P4 lookup, apply clean_company_name() before querying
if col == strategy.customer_name_column:
    lookup_key = clean_company_name(str(value))
else:
    lookup_key = str(value)

# In _backflow_new_mappings():
# For P4 backflow, apply clean_company_name() before writing
if column == strategy.customer_name_column:
    alias_name = clean_company_name(str(alias_value))
else:
    alias_name = str(alias_value).strip()
```

### 7.3 What NOT to Change

- P1, P2, P3, P5 should continue using RAW values
- Do NOT apply `normalize_for_temp_id()` to all fields (this was the incorrect suggestion in the original backflow document)

## 8. Database Schema Alignment

### 8.1 enterprise.company_mapping Table

The `match_type` field indicates which priority level the mapping belongs to:

| match_type | Priority | Key Format |
|------------|----------|------------|
| `plan` | P1 | RAW |
| `account` | P2 | RAW |
| `hardcode` | P3 | RAW |
| `name` | P4 | **CLEANED** |
| `account_name` | P5 | RAW |

### 8.2 Query Optimization

When querying the database cache, the lookup should:
1. Collect all potential lookup values from unresolved rows
2. Apply `clean_company_name()` only to customer name values (P4)
3. Query database with mixed RAW and CLEANED keys
4. Match results back to rows using the same key transformation

## 9. References

- **Legacy Source:** `legacy/annuity_hub/data_handler/mappings.py`
- **Legacy Cleaner:** `legacy/annuity_hub/data_handler/data_cleaner.py`
- **Legacy Utils:** `legacy/annuity_hub/common_utils/common_utils.py`
- **New Resolver:** `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
- **New Normalizer:** `src/work_data_hub/infrastructure/enrichment/normalizer.py`
- **Architecture Doc:** `docs/supplement/01_company_id_analysis.md`

## 10. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-07 | Initial documentation based on legacy code analysis | Claude Opus 4.5 |
