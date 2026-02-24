# Shared Field Validators Analysis

> **Document Status:** Technical Debt Analysis
> **Created:** 2025-12-28
> **Related Epic:** Multi-Domain ETL Architecture

## Overview

This document analyzes the validation logic for four key fields (`计划代码`, `组合代码`, `客户名称`, `company_id`) across `annuity_performance` and `annuity_income` domains, identifying inconsistencies and code duplication that should be extracted to the infrastructure layer.

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Fields Analyzed | 4 (`计划代码`, `组合代码`, `客户名称`, `company_id`) |
| Domains Compared | 2 (annuity_performance, annuity_income) |
| Critical Issues | 3 (CN-001, CI-001, DR-001) |
| Total Issues | 12 (across Pydantic, Domain Registry, and Schema layers) |
| Code Duplication | ~120 LOC |
| Layers Affected | Pydantic Models, Domain Registry, Alembic Migrations |
| Recommended Action | Extract shared validators to `infrastructure/cleansing/validators.py` |

---

## Field-by-Field Comparison

### 1. `计划代码` (Plan Code)

#### Field Definition Comparison

| Aspect | annuity_performance | annuity_income | Difference |
|--------|---------------------|----------------|------------|
| **Bronze (In)** | `Optional[str]` | `Optional[str]` | ✅ Same |
| **Gold (Out)** | `str` (required) | `str` (required) | ✅ Same |
| **Bronze Validator** | `clean_code_field` | `clean_code_field` | ✅ Same logic |
| **Gold Validator** | `normalize_plan_code` | `normalize_plan_code` | ✅ Same (unified in Story 7.3-3) |

#### Bronze Layer Validators (Both Identical)

**Location:** `annuity_performance/models.py:208-222`, `annuity_income/models.py:142-154`

```python
# Both domains - AnnuityPerformanceIn / AnnuityIncomeIn
@field_validator(
    "组合代码",
    "计划代码",
    # ... other code fields
    "company_id",
    mode="before",
)
@classmethod
def clean_code_field(cls, v: Any) -> Optional[str]:  # Unified in Story 7.3-3
    if v is None:
        return None
    s_val = str(v).strip()
    return s_val if s_val else None
```

#### Gold Layer Validators (Unified in Story 7.3-3)

**annuity_performance/models.py:340-346:**
```python
@field_validator("计划代码", mode="after")
@classmethod
def normalize_plan_code(cls, v: Optional[str]) -> Optional[str]:  # Renamed in Story 7.3-3
    if v is None:
        return v
    normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
        raise ValueError(f"Code cannot be empty after normalization: {v}")
    return normalized
```

**annuity_income/models.py:240-246:**
```python
@field_validator("计划代码", mode="after")
@classmethod
def normalize_plan_code(cls, v: str) -> str:
    normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
        raise ValueError(f"Plan code cannot be empty after normalization: {v}")
    return normalized
```

**Issues Identified:**
| Issue ID | Severity | Description |
|----------|----------|-------------|
| PC-001 | ~~Low~~ | ~~Different validator function names~~ - **RESOLVED in Story 7.3-3** |
| PC-002 | Medium | `annuity_performance` has null check, `annuity_income` doesn't (different return types) |

---

### 2. `组合代码` (Portfolio Code)

#### Field Definition Comparison

| Aspect | annuity_performance | annuity_income | Difference |
|--------|---------------------|----------------|------------|
| **Bronze (In)** | `Optional[str]` | `Optional[str]` | ✅ Same |
| **Gold (Out)** | `Optional[str]` | `Optional[str]` | ✅ Same |
| **Bronze Validator** | `clean_code_field` | `clean_code_field` | ✅ Same |
| **Gold Validator** | None | None | ✅ Same (no gold validation) |

**Status:** ✅ Consistent across domains (no issues)

---

### 3. `客户名称` (Customer Name)

#### Field Definition Comparison

| Aspect | annuity_performance | annuity_income | Difference |
|--------|---------------------|----------------|------------|
| **Bronze (In)** | `Optional[str]` | `Optional[str]` | ✅ Same |
| **Gold (Out)** | `Optional[str]` | `str` (**required**) | ❌ **Critical** |
| **Gold Validator** | Has null check | No null check | ❌ **Critical** |

#### Gold Layer Validators

**annuity_performance/models.py:338-353:**
```python
客户名称: Optional[str] = Field(None, max_length=255, description="Customer name")

@field_validator("客户名称", mode="before")
@classmethod
def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
    if v is None:
        return v  # ✅ Allows null
    try:
        field_name = info.field_name or "客户名称"
        return apply_domain_rules(
            v,
            field_name,
            fallback_rules=DEFAULT_COMPANY_RULES,
        )
    except Exception as e:
        raise ValueError(...)
```

**annuity_income/models.py:193, 225-238:**
```python
客户名称: str = Field(..., max_length=255, description="Customer name (normalized)")
#        ^^^ Required - no Optional

@field_validator("客户名称", mode="before")
@classmethod
def clean_customer_name(cls, v: Any, info: ValidationInfo) -> str:
    # ❌ No null check - fails on None input
    try:
        field_name = info.field_name or "客户名称"
        return apply_domain_rules(
            v,
            field_name,
            fallback_rules=DEFAULT_COMPANY_RULES,
        )
    except Exception as e:
        raise ValueError(...)
```

**Issues Identified:**
| Issue ID | Severity | Description |
|----------|----------|-------------|
| CN-001 | **Critical** | `annuity_income` rejects null `客户名称`, causing validation failures |
| CN-002 | Medium | Duplicate `apply_domain_rules()` function (9 lines × 2) |
| CN-003 | Medium | Duplicate `DEFAULT_COMPANY_RULES` constant |
| CN-004 | Low | Same validator logic, but different null handling |

---

### 4. `company_id`

#### Field Definition Comparison

| Aspect | annuity_performance | annuity_income | Difference |
|--------|---------------------|----------------|------------|
| **Bronze (In)** | `Optional[str]` | `Optional[str]` | ✅ Same |
| **Gold (Out)** | `Optional[str]` | `str` (**required**) | ❌ **Critical** |
| **Gold Validator** | Has null check | No null check | ❌ **Critical** |

#### Gold Layer Validators

**annuity_performance/models.py:249-254, 365-381:**
```python
company_id: Optional[str] = Field(
    None,
    min_length=1,
    max_length=50,
    description="Company identifier - generated during data cleansing",
)

@field_validator("company_id", mode="after")
@classmethod
def normalize_company_id(cls, v: Optional[str]) -> Optional[str]:
    """Validate company_id format."""
    if v is None:
        return v  # ✅ Allows null
    normalized = v.upper()
    if not normalized.strip():
        raise ValueError(f"company_id cannot be empty: {v}")
    return normalized
```

**annuity_income/models.py:185-190, 248-262:**
```python
company_id: str = Field(
    ...,  # Required for gold output parity and composite PK
    min_length=1,
    max_length=50,
    description="Company identifier - generated during data cleansing",
)

@field_validator("company_id", mode="after")
@classmethod
def normalize_company_id(cls, v: str) -> str:
    """Validate company_id format."""
    # ❌ No null check - v is required str
    normalized = v.upper()
    if not normalized.strip():
        raise ValueError(f"company_id cannot be empty: {v}")
    return normalized
```

**Issues Identified:**
| Issue ID | Severity | Description |
|----------|----------|-------------|
| CI-001 | **Critical** | `annuity_income` requires `company_id`, `annuity_performance` allows null |
| CI-002 | Medium | Same validator logic duplicated with different null handling |

---

## Cross-Domain Comparison with `sandbox_trustee_performance`

The `sandbox_trustee_performance` domain uses different field naming conventions (English vs Chinese):

| Field | annuity_* | sandbox_trustee_performance |
|-------|-----------|----------------------------|
| Plan Code | `计划代码` | `plan_code` |
| Company ID | `company_id` | `company_code` |
| Customer Name | `客户名称` | N/A (not used) |
| Portfolio Code | `组合代码` | N/A (not used) |

**sandbox_trustee_performance/models.py:165-179:**
```python
@field_validator("plan_code", "company_code", mode="after")
@classmethod
def normalize_codes(cls, v: str) -> str:
    if v is None:
        return v
    normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized.replace(".", "").isalnum():
        raise ValueError(f"Code contains invalid characters: {v}")
    return normalized
```

**Issues:**
| Issue ID | Severity | Description |
|----------|----------|-------------|
| SP-001 | Low | Different validation rule (`.isalnum()` vs Chinese bracket check) |
| SP-002 | Info | Uses English field names (by design for sandbox) |

---

## Duplicate Code Analysis

### Helper Functions

Both `annuity_performance` and `annuity_income` define identical helper functions:

| Function | Lines | annuity_performance | annuity_income |
|----------|-------|---------------------|----------------|
| `apply_domain_rules()` | 9 | L45-53 | L40-49 |

### Constants

| Constant | annuity_performance | annuity_income |
|----------|---------------------|----------------|
| `DEFAULT_COMPANY_RULES` | L27 | L26 |
| `DEFAULT_NUMERIC_RULES` | L37-42 | L33-37 |
| `MIN_YYYYMM_VALUE` | L35 | L29 |
| `MAX_YYYYMM_VALUE` | L36 | L30 |
| `MAX_DATE_RANGE_DAYS` | L32 | L31 |
| `CLEANSING_DOMAIN` | L25 | L24 |
| `CLEANSING_REGISTRY` | L26 | L25 |

**Total Duplicated LOC:** ~30 lines of constants + 9 lines of helper = **~40 LOC per domain**

### Validator Logic Duplication

| Validator | Purpose | Duplication |
|-----------|---------|-------------|
| `clean_code_field` | Bronze code field cleanup | ~6 lines × 2 |
| `clean_customer_name` | Customer name cleansing | ~12 lines × 2 |
| `normalize_company_id` | Company ID validation | ~8 lines × 2 |
| `normalize_plan_code` | Plan code normalization | ~6 lines × 2 |
| `clean_numeric_fields` | Numeric field cleansing | ~20 lines × 2 |
| `clean_decimal_fields_output` | Gold decimal cleansing | ~12 lines × 2 |

**Total Validator Duplication:** ~64 lines × 2 = **~128 LOC**

---

## Issue Summary Matrix

| Issue ID | Severity | Field | Layer | Description |
|----------|----------|-------|-------|-------------|
| **CN-001** | Critical | 客户名称 | Pydantic | `annuity_income` rejects null values, should allow null |
| **CI-001** | Critical | company_id | Pydantic | `annuity_income` requires field, should be Optional |
| **DR-001** | Critical | 客户名称 | Domain Registry | `annuity_income` has `nullable=False`, should be `True` |
| DR-002 | Medium | 客户名称 | Domain Registry | `gold_required` includes `客户名称`, should be removed |
| PC-002 | Medium | 计划代码 | Pydantic | Null handling differs in gold validators |
| CN-002 | Medium | 客户名称 | Pydantic | Duplicate `apply_domain_rules()` function |
| CN-003 | Medium | 客户名称 | Pydantic | Duplicate `DEFAULT_COMPANY_RULES` constant |
| CI-002 | Medium | company_id | Pydantic | Duplicate validator logic |
| DR-003 | Info | company_id | Schema Mismatch | Pydantic `Optional` vs DB `NOT NULL` |
| PC-001 | ~~Low~~ | ~~计划代码~~ | ~~Pydantic~~ | ~~Different validator names for same logic~~ - **RESOLVED in Story 7.3-3** |
| CN-004 | Low | 客户名称 | Pydantic | Same logic, different null handling |
| SP-001 | Low | plan_code | Pydantic | Different validation rule (design choice) |

---

## Schema Layer Inconsistencies (Domain Registry)

### Overview

The Domain Registry (`infrastructure/schema/definitions/`) is the **Single Source of Truth (SSOT)** for database schema definitions. The Alembic migrations use `ddl_generator.generate_create_table_ddl()` to generate DDL from these definitions.

**CRITICAL:** Any changes to field nullability in Pydantic models **MUST** be synchronized with Domain Registry definitions.

### Current Schema Definitions

#### `annuity_income` (infrastructure/schema/definitions/annuity_income.py)

```python
columns=[
    ColumnDef("月度", ColumnType.DATE, nullable=False),
    ColumnDef("计划代码", ColumnType.STRING, nullable=False, max_length=255),
    ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),  # ❌ NOT NULL
    ColumnDef("客户名称", ColumnType.STRING, nullable=False, max_length=255),   # ❌ NOT NULL
    ColumnDef("组合代码", ColumnType.STRING, max_length=255),  # ✅ nullable (default)
    # ...
],
bronze_required=["月度", "计划代码", "客户名称", ...],
gold_required=["月度", "计划代码", "company_id", "客户名称", ...],
```

#### `annuity_performance` (infrastructure/schema/definitions/annuity_performance.py)

```python
columns=[
    ColumnDef("月度", ColumnType.DATE, nullable=False),
    ColumnDef("计划代码", ColumnType.STRING, nullable=False, max_length=255),
    ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),  # ⚠️ NOT NULL in DB
    ColumnDef("客户名称", ColumnType.STRING, max_length=255),  # ✅ nullable (default)
    ColumnDef("组合代码", ColumnType.STRING, max_length=255),  # ✅ nullable (default)
    # ...
],
```

### Schema Inconsistency Matrix

| Field | annuity_performance (DB) | annuity_income (DB) | Pydantic annuity_performance | Pydantic annuity_income | Issue |
|-------|--------------------------|---------------------|------------------------------|-------------------------|-------|
| `客户名称` | `NULL` allowed | `NOT NULL` | `Optional[str]` | `str` (required) | ❌ Inconsistent |
| `company_id` | `NOT NULL` | `NOT NULL` | `Optional[str]` | `str` (required) | ⚠️ Pydantic mismatch |
| `组合代码` | `NULL` allowed | `NULL` allowed | `Optional[str]` | `Optional[str]` | ✅ Consistent |
| `计划代码` | `NOT NULL` | `NOT NULL` | `str` (required) | `str` (required) | ✅ Consistent |

### Issues Identified

| Issue ID | Severity | Layer | Description |
|----------|----------|-------|-------------|
| **DR-001** | Critical | Domain Registry | `annuity_income.客户名称` is `nullable=False`, should be `nullable=True` |
| **DR-002** | Medium | Domain Registry | `annuity_income.gold_required` includes `客户名称`, should be removed |
| DR-003 | Info | Pydantic | `annuity_performance.company_id` is `Optional` in Pydantic but `NOT NULL` in DB |

---

## Alembic Migration Considerations

### Migration Architecture

The project uses **DDL Generator pattern** for migrations:

```
Domain Registry (SSOT)
    └── ddl_generator.generate_create_table_ddl()
            └── Alembic Migration (002_initial_domains.py)
                    └── PostgreSQL Tables
```

**Key File:** `io/schema/migrations/versions/002_initial_domains.py`

```python
def _execute_domain_ddl(conn, domain_name: str) -> None:
    from work_data_hub.infrastructure.schema import ddl_generator

    # Uses Domain Registry as SSOT
    create_table_sql = ddl_generator.generate_create_table_ddl(
        domain_name, if_not_exists=True
    )
    conn.execute(sa.text(create_table_sql))
```

### Migration Strategy for Fixing Null Constraints

Since migrations are designed for **from-scratch** scenarios, the recommended approach is:

1. **Modify Domain Registry** (SSOT):
   - Update `infrastructure/schema/definitions/annuity_income.py`
   - Change `ColumnDef("客户名称", ..., nullable=False)` to `nullable=True`
   - Remove `客户名称` from `gold_required` list

2. **No new migration needed** for fresh installs:
   - The existing `002_initial_domains.py` uses `ddl_generator` which reads from Domain Registry
   - Fresh installs will automatically get the corrected schema

3. **For existing databases** (production):
   - Option A: Create a separate hotfix migration with `ALTER TABLE` (not recommended for SSOT pattern)
   - Option B: Drop and recreate table (acceptable for dev/test, data loss)
   - Option C: Manual `ALTER TABLE` outside of Alembic (for production hotfix)

### Files Requiring Modification

| File | Change Type | Description |
|------|-------------|-------------|
| `infrastructure/schema/definitions/annuity_income.py` | **MODIFY** | Change `客户名称` to `nullable=True`, update `gold_required` |
| `domain/annuity_income/models.py` | **MODIFY** | Change `客户名称: str` to `Optional[str]`, add null check |
| `io/schema/migrations/versions/002_initial_domains.py` | **NO CHANGE** | Uses ddl_generator (auto-updated) |

### Production Database Hotfix (If Needed)

If the production database already has `NOT NULL` constraint on `客户名称`:

```sql
-- Manual hotfix for production (outside Alembic)
ALTER TABLE business.收入明细 ALTER COLUMN 客户名称 DROP NOT NULL;
```

**Warning:** This should be tracked in a separate migration or documented in release notes.

---

## Recommended Refactoring

### Option A: Shared Validators Module (Recommended)

Create `infrastructure/cleansing/validators.py`:

```python
"""
Shared Pydantic validators for domain models.

This module extracts common validation patterns to eliminate duplication
across annuity_performance, annuity_income, and future domains.
"""
from typing import Any, Callable, List, Optional
from pydantic import ValidationInfo

from work_data_hub.infrastructure.cleansing import get_cleansing_registry

# Shared Constants
DEFAULT_COMPANY_RULES = ["trim_whitespace", "normalize_company_name"]
DEFAULT_NUMERIC_RULES = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
]
MIN_YYYYMM_VALUE = 200000
MAX_YYYYMM_VALUE = 999999
MAX_DATE_RANGE_DAYS = 3650


def apply_domain_rules(
    domain: str,
    value: Any,
    field_name: str,
    fallback_rules: Optional[List[Any]] = None,
) -> Any:
    """Apply cleansing rules for a domain field."""
    registry = get_cleansing_registry()
    rules = registry.get_domain_rules(domain, field_name)
    if not rules:
        rules = fallback_rules or []
    if not rules:
        return value
    return registry.apply_rules(value, rules, field_name=field_name)


def create_code_field_cleaner() -> Callable:
    """Factory for bronze layer code field cleaners."""
    def clean_code_field(v: Any) -> Optional[str]:  # Singular form (Story 7.3-3)
        if v is None:
            return None
        s_val = str(v).strip()
        return s_val if s_val else None
    return clean_code_field


def create_customer_name_validator(
    domain: str,
    allow_null: bool = True,
) -> Callable:
    """Factory for customer name validators with consistent null handling."""
    def clean_customer_name(v: Any, info: ValidationInfo) -> Optional[str]:
        if v is None:
            return v if allow_null else None
        field_name = info.field_name or "客户名称"
        return apply_domain_rules(
            domain,
            v,
            field_name,
            fallback_rules=DEFAULT_COMPANY_RULES,
        )
    return clean_customer_name


def create_company_id_validator(allow_null: bool = True) -> Callable:
    """Factory for company_id validators."""
    def normalize_company_id(v: Optional[str]) -> Optional[str]:
        if v is None:
            return v if allow_null else None
        normalized = v.upper()
        if not normalized.strip():
            raise ValueError(f"company_id cannot be empty: {v}")
        return normalized
    return normalize_company_id


def create_plan_code_validator(allow_null: bool = True) -> Callable:
    """Factory for plan code validators."""
    def normalize_plan_code(v: Optional[str]) -> Optional[str]:
        if v is None:
            return v if allow_null else None
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"Plan code cannot be empty after normalization: {v}")
        return normalized
    return normalize_plan_code
```

### Option B: Configuration-Driven Validation

Extend `cleansing_rules.yml` with field-level null handling configuration.

### Option C: Base Model Class

Create abstract base models with shared validators.

---

## Implementation Priority

| Priority | Issue IDs | Description | Effort |
|----------|-----------|-------------|--------|
| P0 | CN-001, CI-001, DR-001 | Fix critical null handling in annuity_income + Domain Registry | 2 hours |
| P1 | CN-002, CN-003, CI-002 | Extract shared validators to infrastructure | 4 hours |
| P2 | ~~PC-001~~, PC-002, DR-003 | ~~Unify validator names~~ (RESOLVED in Story 7.3-3) and null handling | 2 hours |

---

## Affected Files (Complete List)

### P0: Critical Fixes (annuity_income null handling)

| File | Change Type | Description |
|------|-------------|-------------|
| `infrastructure/schema/definitions/annuity_income.py` | **MODIFY** | Change `客户名称` to `nullable=True`, update `gold_required` |
| `domain/annuity_income/models.py` | **MODIFY** | Change `客户名称: str` to `Optional[str]`, add null check in validator |
| `io/schema/migrations/versions/002_initial_domains.py` | **NO CHANGE** | Uses ddl_generator (auto-updated from Domain Registry) |

### P1: Shared Validators Extraction

| File | Change Type | Description |
|------|-------------|-------------|
| `infrastructure/cleansing/validators.py` | **CREATE** | New shared validators module |
| `infrastructure/cleansing/__init__.py` | **MODIFY** | Export new validators |
| `domain/annuity_income/models.py` | **MODIFY** | Import and use shared validators |
| `domain/annuity_performance/models.py` | **MODIFY** | Import and use shared validators |

### P2: Consistency Improvements

| File | Change Type | Description |
|------|-------------|-------------|
| Future domains | **TEMPLATE** | Import from infrastructure layer |

---

## Related Documentation

- [New Domain Checklist](./new-domain-checklist.md) - Domain addition requirements
- [Infrastructure Layer](../../architecture/infrastructure-layer.md) - Cleansing framework
- [Project Context](../../project-context.md) - Architecture overview

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-28 | Barry (Quick Flow) | Initial comprehensive analysis of four key fields |
| 2025-12-28 | Barry (Quick Flow) | Added Domain Registry and Alembic migration analysis |
| 2025-12-29 | Claude (Story 7.3-3) | Updated validator naming to reflect unified conventions |
