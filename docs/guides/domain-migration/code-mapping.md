# Cleansing Rules to Code Mapping Guide

**Version:** 1.0
**Last Updated:** 2025-12-09
**Purpose:** Translate cleansing rules documentation into implementation code

---

## Overview

This guide explains how to convert each section of a cleansing rules document (e.g., `annuity-income.md`) into actual code. Use this as a reference during Phase 3 (Implementation) of the [Domain Migration Workflow](./workflow.md).

---

## Mapping Summary

| Document Section | Target Code File | Key Artifacts |
|------------------|------------------|---------------|
| Section 2: Dependency Table Inventory | Migration scripts | Executed migrations |
| Section 3: Migration Strategy Decisions | Migration scripts | Strategy implementation |
| Section 4: Migration Validation | Test fixtures | Validation results |
| Section 5: Column Mappings | `constants.py` | `COLUMN_MAPPING`, `COLUMN_ALIAS_MAPPING` |
| Section 6: Cleansing Rules | `cleansing_rules.yml` + `pipeline_builder.py` | Rule configurations, pipeline steps |
| Section 7: Company ID Resolution | `pipeline_builder.py` | `CompanyIdResolutionStep` config |
| Section 8: Validation Rules | `models.py` + `schemas.py` | Pydantic models, Pandera schemas |
| Section 9: Special Processing Notes | `constants.py` + `helpers.py` | Manual overrides, edge case handlers |
| Section 10: Parity Validation | `scripts/tools/parity/` | Validation scripts |

---

## Section-by-Section Implementation

### Section 2: Dependency Table Inventory → Migration Execution

**Document Example:**
```markdown
| # | Table Name | Database | Purpose | Row Count | Migration Status |
|---|------------|----------|---------|-----------|-----------------|
| 1 | company_id_mapping | legacy | Company name to ID | ~19,141 | [PENDING] |
| 2 | eqc_search_result | legacy | EQC lookups | ~11,820 | [PENDING] |
```

**Implementation:**

1. **For Enrichment Index strategy:**
   ```bash
   PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py
   ```

2. **For Static Embedding strategy:**
   ```python
   # constants.py
   STATIC_MAPPING = {
       "key1": "value1",
       "key2": "value2",
   }
   ```

3. **Update document status after migration:**
   ```markdown
   | 1 | company_id_mapping | legacy | Company name to ID | ~19,141 | [MIGRATED] |
   ```

---

### Section 5: Column Mappings → constants.py

**Document Example:**
```markdown
| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | 机构 | 机构代码 | rename | Initial rename |
| 2 | 机构名称 | 机构代码 | mapping | COMPANY_BRANCH_MAPPING |
| 3 | 月度 | 月度 | date_parse | Chinese date format |
```

**Implementation in `constants.py`:**

```python
"""Domain-specific constants for {domain}."""

# Column rename mapping (Legacy → Target)
# Source: Section 5, Column Mappings
COLUMN_MAPPING = {
    "机构": "机构代码",  # Row 1: Initial rename
}

# Column alias mapping for standardization
# Source: Section 5, Notes column
COLUMN_ALIAS_MAPPING = {
    "计划号": "计划代码",  # Alternate column names
    "流失(含待遇支付)": "流失_含待遇支付",  # Special character handling
}

# Columns to drop after processing
# Source: Section 5, columns not in target schema
LEGACY_COLUMNS_TO_DELETE = frozenset({
    "legacy_only_column",
    "temp_calculation_column",
})
```

**Mapping Rules:**

| Document Column | Code Artifact |
|-----------------|---------------|
| Legacy Column | Dict key in `COLUMN_MAPPING` |
| Target Column | Dict value in `COLUMN_MAPPING` |
| Transformation = "rename" | Simple key-value in `COLUMN_MAPPING` |
| Transformation = "mapping" | Separate mapping dict (e.g., `COMPANY_BRANCH_MAPPING`) |

---

### Section 6: Cleansing Rules → cleansing_rules.yml + pipeline_builder.py

**Document Example:**
```markdown
| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | 机构代码 | mapping | COMPANY_BRANCH_MAPPING | 1 | Manual overrides |
| CR-002 | 月度 | date_parse | parse_to_standard_date | 2 | Chinese formats |
| CR-003 | 机构代码 | default_value | fillna('G00') | 3 | Headquarters fallback |
| CR-005 | 组合代码 | regex_replace | str.replace('^F', '') | 5 | Remove F prefix |
```

**Implementation Option 1: cleansing_rules.yml**

```yaml
# src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml
domains:
  annuity_income:
    # CR-001: Branch code mapping
    - rule: mapping
      columns: ["机构代码"]
      mapping_name: "COMPANY_BRANCH_MAPPING"
      priority: 1

    # CR-002: Date parsing
    - rule: date_parse
      columns: ["月度"]
      format: "chinese"
      priority: 2

    # CR-003: Default value
    - rule: default_value
      columns: ["机构代码"]
      value: "G00"
      priority: 3

    # CR-005: Regex replacement
    - rule: regex_replace
      columns: ["组合代码"]
      pattern: "^F"
      replacement: ""
      priority: 5
```

**Implementation Option 2: pipeline_builder.py (for complex rules)**

```python
"""Pipeline composition for {domain}."""
from work_data_hub.infrastructure.transforms import (
    MappingStep,
    ReplacementStep,
    CleansingStep,
    CalculationStep,
    DropStep,
    Pipeline,
)

def build_bronze_to_silver_pipeline() -> Pipeline:
    """Build transformation pipeline.

    Rule mapping from cleansing-rules/{domain}.md Section 6:
    - CR-001 → MappingStep (COMPANY_BRANCH_MAPPING)
    - CR-002 → CleansingStep (date_parse via registry)
    - CR-003 → ReplacementStep (default value)
    - CR-005 → CalculationStep (regex)
    - CR-006 → CalculationStep (conditional logic)
    """
    steps = [
        # CR-001: Branch code mapping
        MappingStep(COLUMN_ALIAS_MAPPING),

        # CR-002, CR-003: Via cleansing registry
        CleansingStep(domain="annuity_income"),

        # CR-005: Regex replacement for 组合代码
        CalculationStep({
            "组合代码": lambda df: df["组合代码"].str.replace(r"^F", "", regex=True),
        }),

        # CR-006: Conditional default (complex logic)
        CalculationStep({
            "组合代码": lambda df: df["组合代码"].mask(
                df["组合代码"].isna() | (df["组合代码"] == ""),
                df.apply(
                    lambda x: "QTAN003" if x["业务类型"] in ["职年受托", "职年投资"]
                    else DEFAULT_PORTFOLIO_CODE_MAPPING.get(x["计划类型"]),
                    axis=1
                )
            ),
        }),

        # Drop legacy columns
        DropStep(list(LEGACY_COLUMNS_TO_DELETE)),
    ]

    return Pipeline(steps)
```

**Rule Type → Code Mapping:**

| Rule Type | Code Implementation |
|-----------|---------------------|
| `mapping` | `MappingStep` or `ReplacementStep` |
| `date_parse` | `CleansingStep` (via registry) or `CalculationStep` |
| `default_value` | `ReplacementStep` or `CalculationStep` with `fillna()` |
| `regex_replace` | `CalculationStep` with `str.replace()` |
| `conditional` | `CalculationStep` with `mask()` or `apply()` |
| `normalize` | `CleansingStep` (via registry) |
| `copy` | `CalculationStep` with column assignment |

---

### Section 7: Company ID Resolution → pipeline_builder.py

**Document Example:**
```markdown
### Priority Order

| Priority | Source Field | Mapping Table | Fallback |
|----------|--------------|---------------|----------|
| 1 | 计划号 | COMPANY_ID1_MAPPING | Next priority |
| 2 | 计划号 + 客户名称 | COMPANY_ID3_MAPPING | Default '600866980' |
| 3 | 客户名称 | COMPANY_ID4_MAPPING | None |
```

**Implementation in `pipeline_builder.py`:**

```python
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolutionStep,
    ResolutionStrategy,
)

def build_bronze_to_silver_pipeline(
    enrichment_service=None,
    plan_override_mapping=None,
) -> Pipeline:
    """Build pipeline with Company ID resolution.

    Resolution strategy from cleansing-rules/{domain}.md Section 7:
    - Priority 1: Plan code lookup (COMPANY_ID1_MAPPING)
    - Priority 2: Plan + Customer special cases (COMPANY_ID3_MAPPING)
    - Priority 3: Customer name lookup (COMPANY_ID4_MAPPING)
    """

    # Configure resolution strategy based on Section 7
    resolution_strategy = ResolutionStrategy(
        plan_code_column="计划号",           # Source Field for Priority 1
        customer_name_column="客户名称",      # Source Field for Priority 3
        output_column="company_id",
        generate_temp_ids=True,              # Generate temp IDs for unresolved
    )

    steps = [
        # ... other steps ...

        # Company ID Resolution (Section 7)
        CompanyIdResolutionStep(
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping or COMPANY_ID3_MAPPING,
            strategy=resolution_strategy,
        ),

        # ... remaining steps ...
    ]

    return Pipeline(steps)
```

---

### Section 8: Validation Rules → models.py + schemas.py

**Document Example:**
```markdown
### Required Fields
- [x] 月度 (date)
- [x] 机构代码 (string, defaults to 'G00')
- [x] 计划号 (string)

### Data Type Constraints
| Field | Expected Type | Constraint | Notes |
|-------|---------------|------------|-------|
| 月度 | datetime | Format: YYYY-MM-DD | Standardized |
| 机构代码 | string | Pattern: G\d{2} | Branch code |
| 收入金额 | numeric | Decimal | Income amount |

### Business Rules
| Rule ID | Description | Validation Logic |
|---------|-------------|------------------|
| VR-001 | 机构代码 must have valid value | defaults to 'G00' |
| VR-002 | 月度 must be valid date | notna() |
```

**Implementation in `models.py`:**

```python
"""Pydantic models for {domain}."""
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainIn(BaseModel):
    """Bronze layer input model - lenient validation.

    Source: Section 8, Required Fields (lenient)
    """
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    # Required fields from Section 8
    月度: Optional[str] = None
    机构代码: Optional[str] = None
    计划号: Optional[str] = None
    收入金额: Optional[Decimal] = None


class DomainOut(BaseModel):
    """Gold layer output model - strict validation.

    Source: Section 8, Data Type Constraints + Business Rules
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # VR-002: 月度 must be valid date
    月度: date = Field(..., description="Report date")

    # VR-001: 机构代码 defaults to 'G00'
    机构代码: str = Field(default="G00", pattern=r"^G\d{2}$")

    # Required field
    计划号: str = Field(..., min_length=1)

    # Numeric field
    收入金额: Decimal = Field(..., ge=0)

    # Company ID (may be None if unresolved)
    company_id: Optional[str] = Field(None, pattern=r"^\d{9}$")

    @field_validator("月度", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> Optional[date]:
        """Parse date from various formats."""
        from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese
        return parse_yyyymm_or_chinese(v) if v else None
```

**Implementation in `schemas.py`:**

```python
"""Pandera schemas for {domain}.

Source: Section 8, Data Type Constraints
"""
import pandera as pa

# Required columns from Section 8
BRONZE_REQUIRED_COLUMNS = ("月度", "机构代码", "计划号", "收入金额")
GOLD_REQUIRED_COLUMNS = ("月度", "机构代码", "计划号", "收入金额", "company_id")

# Composite key for uniqueness
GOLD_COMPOSITE_KEY = ("月度", "计划号", "company_id")


BronzeDomainSchema = pa.DataFrameSchema(
    columns={
        # Lenient validation - nullable, coerce types
        "月度": pa.Column(pa.String, nullable=True, coerce=True),
        "机构代码": pa.Column(pa.String, nullable=True, coerce=True),
        "计划号": pa.Column(pa.String, nullable=True, coerce=True),
        "收入金额": pa.Column(pa.Float, nullable=True, coerce=True),
    },
    strict=False,  # Allow extra columns
    coerce=True,
)


GoldDomainSchema = pa.DataFrameSchema(
    columns={
        # Strict validation from Section 8 constraints
        "月度": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "机构代码": pa.Column(
            pa.String,
            nullable=False,
            checks=pa.Check.str_matches(r"^G\d{2}$"),
        ),
        "计划号": pa.Column(pa.String, nullable=False, coerce=True),
        "收入金额": pa.Column(
            pa.Float,
            nullable=False,
            checks=pa.Check.ge(0),  # Non-negative
        ),
        "company_id": pa.Column(pa.String, nullable=True, coerce=True),
    },
    strict=True,  # Reject extra columns
    unique=GOLD_COMPOSITE_KEY,
)
```

---

### Section 9: Special Processing Notes → constants.py + helpers.py

**Document Example:**
```markdown
### COMPANY_BRANCH_MAPPING Complete Values
```python
# Base mapping from DB plus manual overrides:
COMPANY_BRANCH_MAPPING.update({
    '内蒙': 'G31',
    '战略': 'G37',
    '北京其他': 'G37',
})
```

### Edge Cases
1. Missing 组合代码 column: Create with np.nan
2. 'null' string in 机构代码: Replace with 'G00'
```

**Implementation in `constants.py`:**

```python
"""Constants including manual overrides from Section 9."""

# Base mapping (from database or config)
COMPANY_BRANCH_MAPPING = {
    # ... base mappings ...
}

# Manual overrides from Section 9: Special Processing Notes
# CRITICAL: These must be included for parity
COMPANY_BRANCH_MAPPING.update({
    "内蒙": "G31",
    "战略": "G37",
    "中国": "G37",
    "济南": "G21",
    "北京其他": "G37",
    "北分": "G37",
})

# Default portfolio code mapping from Section 9
DEFAULT_PORTFOLIO_CODE_MAPPING = {
    "集合计划": "QTAN001",
    "单一计划": "QTAN002",
    "职业年金": "QTAN003",
}
```

**Implementation in `helpers.py`:**

```python
"""Helper functions for edge cases from Section 9."""
import numpy as np
import pandas as pd


def ensure_column_exists(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Edge Case 1: Create missing column with NaN.

    Source: Section 9, Edge Cases, item 1
    """
    if column not in df.columns:
        df[column] = np.nan
    return df


def replace_null_string(df: pd.DataFrame, column: str, default: str) -> pd.DataFrame:
    """Edge Case 2: Replace 'null' string with default.

    Source: Section 9, Edge Cases, item 2
    """
    df[column] = df[column].replace("null", default).fillna(default)
    return df
```

---

### Section 10: Parity Validation → Validation Scripts

**Document Example:**
```markdown
### Execution Steps
1. Prepare test data from `tests/fixtures/real_data/`
2. Run legacy cleaner
3. Run new pipeline
4. Compare outputs
5. Document differences
```

**Implementation:**

Create `scripts/tools/parity/validate_{domain}_parity.py` following the pattern in [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md).

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│           CLEANSING RULES → CODE QUICK REFERENCE                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Section 2-4 (Dependencies)                                     │
│  └─► Execute migration scripts                                  │
│                                                                 │
│  Section 5 (Column Mappings)                                    │
│  └─► constants.py: COLUMN_MAPPING, COLUMN_ALIAS_MAPPING         │
│                                                                 │
│  Section 6 (Cleansing Rules)                                    │
│  ├─► cleansing_rules.yml (simple rules)                         │
│  └─► pipeline_builder.py (complex rules)                        │
│                                                                 │
│  Section 7 (Company ID)                                         │
│  └─► pipeline_builder.py: CompanyIdResolutionStep               │
│                                                                 │
│  Section 8 (Validation Rules)                                   │
│  ├─► models.py: Pydantic models                                 │
│  └─► schemas.py: Pandera schemas                                │
│                                                                 │
│  Section 9 (Special Notes)                                      │
│  ├─► constants.py: Manual overrides                             │
│  └─► helpers.py: Edge case handlers                             │
│                                                                 │
│  Section 10 (Parity Validation)                                 │
│  └─► scripts/tools/parity/validate_{domain}_parity.py           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [Domain Migration Workflow](./workflow.md) | End-to-end migration process |
| [Domain Development Guide](./development-guide.md) | Code templates and patterns |
| [Troubleshooting Guide](./troubleshooting.md) | Common issues and solutions |
| [Cleansing Rules Template](../templates/cleansing-rules-template.md) | Documentation template |
| [annuity-income.md](../cleansing-rules/annuity-income.md) | Reference example |

---

**End of Mapping Guide**
