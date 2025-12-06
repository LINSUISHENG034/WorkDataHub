# Domain Development Guide

**Version:** 1.0
**Last Updated:** 2025-12-06
**Based On:** Epic 5.5 Pipeline Architecture Validation

---

## Overview

This guide provides comprehensive instructions for implementing new data domains in WorkDataHub. It is based on lessons learned from Epic 5.5, which validated the Infrastructure Layer architecture by implementing the `annuity_income` domain as a second reference implementation alongside `annuity_performance`.

### Purpose

- Enable developers to independently create new domains following established patterns
- Document the 6-file standard domain structure
- Capture best practices and common pitfalls discovered during Epic 5.5
- Provide reusable code templates and configuration examples

### Target Audience

- Developers implementing new data domains
- Technical leads reviewing domain implementations
- AI assistants working on domain-related tasks

---

## Prerequisites

Before implementing a new domain, ensure you have:

1. **Understanding of Bronze-Silver-Gold Architecture**
   - Bronze: Raw data ingestion with minimal validation
   - Silver: Cleansed and transformed data (Pydantic models)
   - Gold: Business-ready data with full validation (Pandera schemas)

2. **Familiarity with Core Libraries**
   - [Pydantic](https://docs.pydantic.dev/) - Row-level data validation
   - [Pandera](https://pandera.readthedocs.io/) - DataFrame schema validation
   - [Pandas](https://pandas.pydata.org/) - Data manipulation
   - [Structlog](https://www.structlog.org/) - Structured logging

3. **Access to Legacy System**
   - Source data files or database access
   - Legacy cleansing logic documentation
   - Business rules and validation requirements

4. **Project Setup**
   - Development environment configured (`uv sync`)
   - Database connection available
   - Test fixtures prepared

---

## Domain Directory Structure (6-File Standard)

Each domain follows a standardized 6-file structure:

```
src/work_data_hub/domain/{domain_name}/
├── __init__.py          # Module exports
├── models.py            # Pydantic data models (Bronze/Silver/Gold)
├── schemas.py           # Pandera DataFrame schemas
├── helpers.py           # Data transformation helpers
├── service.py           # Business service layer
├── pipeline_builder.py  # Pipeline step configuration
├── constants.py         # Domain-specific constants (optional)
└── assets/              # Dagster Assets (optional)
    └── __init__.py
```

### File Responsibilities

| File | Purpose | Key Contents |
|------|---------|--------------|
| `__init__.py` | Public API exports | Export main service function, models, schemas |
| `models.py` | Data models | `{Domain}In` (Bronze), `{Domain}Out` (Silver/Gold) Pydantic models |
| `schemas.py` | DataFrame validation | `Bronze{Domain}Schema`, `Gold{Domain}Schema` Pandera schemas |
| `helpers.py` | Transformation utilities | `convert_dataframe_to_models()`, domain-specific helpers |
| `service.py` | Business logic | `process_{domain}()` main entry point |
| `pipeline_builder.py` | Pipeline composition | `build_bronze_to_silver_pipeline()` |
| `constants.py` | Static mappings | Column mappings, code translations, business rules |

---

## Development Checklist

### Phase 1: Analysis (Before Coding)

- [ ] Analyze legacy data source structure and column names
- [ ] Document column mappings (legacy name → new name)
- [ ] Identify validation rules and business constraints
- [ ] Document cleansing rules in `docs/cleansing-rules/{domain}.md`
- [ ] Identify upsert keys (unique record identifiers)
- [ ] Review existing domain implementations for patterns

### Phase 2: Implementation

- [ ] Create domain directory: `src/work_data_hub/domain/{domain_name}/`
- [ ] Define Pydantic models (`models.py`)
  - [ ] `{Domain}In` - Bronze layer input model (lenient validation)
  - [ ] `{Domain}Out` - Silver/Gold layer output model (strict validation)
- [ ] Define Pandera schemas (`schemas.py`)
  - [ ] `Bronze{Domain}Schema` - DataFrame-level Bronze validation
  - [ ] `Gold{Domain}Schema` - DataFrame-level Gold validation
- [ ] Implement data transformation (`helpers.py`)
  - [ ] `convert_dataframe_to_models()` - DataFrame to Pydantic conversion
  - [ ] Domain-specific helper functions
- [ ] Implement service layer (`service.py`)
  - [ ] `process_{domain}()` - Main processing entry point
  - [ ] `DEFAULT_UPSERT_KEYS` - Module-level constant
- [ ] Configure pipeline steps (`pipeline_builder.py`)
  - [ ] `build_bronze_to_silver_pipeline()` - Pipeline composition

### Phase 3: Configuration

- [ ] Configure upsert keys (`DEFAULT_UPSERT_KEYS` in service.py)
- [ ] Add data source configuration (if using file discovery)
- [ ] Register domain cleansing rules in `CleansingRegistry`
- [ ] Create database migration (DDL + UNIQUE constraints)

### Phase 4: Testing & Validation

- [ ] Write unit tests for models (`tests/unit/domain/{domain}/`)
- [ ] Write unit tests for helpers and schemas
- [ ] Write integration tests for service layer
- [ ] Perform legacy parity validation (compare output with legacy system)
- [ ] Establish performance baseline

### Phase 5: Documentation

- [ ] Create domain documentation (`docs/domains/{domain}.md`)
- [ ] Create operational runbook (`docs/runbooks/{domain}.md`)
- [ ] Update `docs/bmm-index.md` with links to new documentation
- [ ] Document any domain-specific cleansing rules

### Phase 6: Deployment & Merge

- [ ] Create PR referencing story ID; include doc changes and checklists
- [ ] Run smoke tests (minimum: `uv run pytest -m unit`) and attach results
- [ ] Request reviewer from domain TL; capture review notes
- [ ] Resolve comments; re-run tests after changes
- [ ] Merge to `main` only after approvals; tag release notes if applicable
- [ ] Notify ops for Dagster/DB rollout if schema/config changed

---

## Key Configuration Patterns

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

# Enable/disable UPSERT mode (requires UNIQUE constraint on upsert_keys)
ENABLE_UPSERT_MODE = False  # Detail table - use refresh mode instead

# UPSERT keys (only used when ENABLE_UPSERT_MODE = True)
DEFAULT_UPSERT_KEYS: Optional[List[str]] = None

# REFRESH keys (used when ENABLE_UPSERT_MODE = False)
# Defines scope for DELETE before INSERT (Legacy: update_based_on_field)
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

**Usage in service function:**

```python
def process_{domain}(
    month: str,
    *,
    refresh_keys: Optional[List[str]] = None,
    # ... other parameters
) -> DomainPipelineResult:
    if ENABLE_UPSERT_MODE:
        # UPSERT mode
        load_result = warehouse_loader.load_dataframe(...)
    else:
        # REFRESH mode
        actual_refresh_keys = refresh_keys if refresh_keys is not None else DEFAULT_REFRESH_KEYS
        load_result = warehouse_loader.load_with_refresh(
            dataframe,
            table=table_name,
            schema=schema,
            refresh_keys=actual_refresh_keys,
        )
```

#### Mode 2: UPSERT Mode (ON CONFLICT DO UPDATE) - For Aggregate Tables

Use this mode when:
- Table contains **aggregate records** (汇总数据)
- Each key combination has **exactly one row**
- You want to **update existing records** or insert new ones

**Configuration:**

```python
# service.py

ENABLE_UPSERT_MODE = True  # Aggregate table - use upsert mode

# Keys for conflict detection (must be UNIQUE in database)
DEFAULT_UPSERT_KEYS = ["月度", "计划代码"]

# Not used in UPSERT mode
DEFAULT_REFRESH_KEYS: Optional[List[str]] = None
```

**Behavior:**
- INSERT new records
- UPDATE existing records when key conflict occurs

**Database Requirements:** UNIQUE constraint required on `upsert_keys`.

```sql
-- Add unique constraint for upsert support
ALTER TABLE {schema}.{table_name}
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

> **Reference:** [Sprint Change Proposal - Upsert Keys Redesign](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-06-upsert-keys-redesign.md)

### Cleansing Registry Configuration

Domain-specific cleansing rules are registered in the `CleansingRegistry`.

**Location:** `src/work_data_hub/infrastructure/cleansing/registry.py`

```python
# In domain's models.py
CLEANSING_DOMAIN = "annuity_performance"
CLEANSING_REGISTRY = get_cleansing_registry()

# Apply domain rules in field validators
cleaned = CLEANSING_REGISTRY.apply_rules(value, rules, field_name=field_name)
```

**Cleansing Rules Documentation:**

Create `docs/cleansing-rules/{domain}.md` documenting all cleansing rules applied to the domain.

### Schema Validation Rules

**Bronze Schema (Lenient):**
- `nullable=True` for most columns
- `coerce=True` for type conversion
- `strict=False` to allow extra columns

**Gold Schema (Strict):**
- `nullable=False` for required columns
- Business rule checks (e.g., `pa.Check.ge(0)` for non-negative values)
- `strict=True` to reject extra columns
- `unique=COMPOSITE_KEY` for uniqueness validation

---

## Common Issues & Solutions

### OPT-001: Failed Record Tracking

**Problem:** Records that fail validation are silently dropped, making debugging difficult.

**Solution:** Export failed records to CSV for analysis.

```python
# In service.py, after model conversion
if dropped_count > 0:
    success_codes = {r.计划代码 for r in records}
    failed_df = input_df[~input_df["计划代码"].isin(success_codes)]

    if not failed_df.empty:
        csv_path = export_error_csv(
            failed_df,
            filename_prefix=f"failed_records_{Path(data_source).stem}",
            output_dir=Path("logs"),
        )
        logger.info("Exported failed records", csv_path=str(csv_path), count=len(failed_df))
```

### OPT-002: Bracket Handling in Company Names

**Problem:** Company names with brackets at start/end (e.g., `"公司(集团)"`) were not being cleaned correctly.

**Business Rule:** Brackets at the start or end of company names are abnormal and should be removed. Brackets in the middle should be preserved.

**Solution:** Use regex to clean start/end brackets:

```python
# Clean brackets at start
result = re.sub(r'^[（\(][^）\)]*[）\)]', '', result)

# Clean brackets at end
result = re.sub(r'[（\(][^）\)]*[）\)]$', '', result)
```

**Test Cases:**

| Input | Expected Output | Reason |
|-------|-----------------|--------|
| `"(集团)中国机械公司"` | `"中国机械公司"` | Start bracket removed |
| `"中国机械公司(集团)"` | `"中国机械公司"` | End bracket removed |
| `"中国（北京）科技公司"` | `"中国（北京）科技公司"` | Middle bracket preserved |

### Column Name Normalization

**Problem:** Chinese column names may have inconsistent formatting (spaces, aliases).

**Solution:** Use `MappingStep` in pipeline to standardize column names:

```python
# In pipeline_builder.py
COLUMN_ALIAS_MAPPING = {
    "机构": "机构名称",
    "流失(含待遇支付)": "流失_含待遇支付",
    "年化收益率": "当期收益率",
}

steps = [
    MappingStep(COLUMN_ALIAS_MAPPING),
    # ... other steps
]
```

### Date Parsing

**Problem:** Dates come in various formats (YYYYMM, Chinese format, Excel serial numbers).

**Solution:** Use the centralized date parser:

```python
from work_data_hub.utils.date_parser import parse_chinese_date, parse_yyyymm_or_chinese

# In pipeline step
CalculationStep({
    "月度": lambda df: df["月度"].apply(parse_chinese_date),
})

# In Pydantic model validator
@field_validator("月度", mode="before")
@classmethod
def parse_date_field(cls, v: Any) -> Optional[date]:
    return parse_yyyymm_or_chinese(v)
```

---

## Testing Strategy

### Unit Tests

**Location:** `tests/unit/domain/{domain}/`

**What to Test:**
- Pydantic model validation (valid and invalid inputs)
- Field validators and transformations
- Helper functions
- Schema validation

**Example:**

```python
# tests/unit/domain/annuity_performance/test_models.py
import pytest
from work_data_hub.domain.annuity_performance.models import AnnuityPerformanceOut

class TestAnnuityPerformanceOut:
    def test_valid_record(self):
        record = AnnuityPerformanceOut(
            计划代码="AN001",
            月度="202401",
            company_id="C001",
            # ... other fields
        )
        assert record.计划代码 == "AN001"

    def test_invalid_plan_code_rejected(self):
        with pytest.raises(ValidationError):
            AnnuityPerformanceOut(计划代码="", ...)
```

### Integration Tests

**Location:** `tests/integration/domain/{domain}/`

**What to Test:**
- Full pipeline execution
- Database loading
- File discovery integration

### Legacy Parity Tests

**Purpose:** Ensure new implementation produces identical results to legacy system.

**Approach:**
1. Process same input data through both systems
2. Compare row counts
3. Compare aggregated values (sums, counts)
4. Identify and document any intentional differences

**Example:**

```python
def test_legacy_parity():
    # Process with new pipeline
    new_result = process_annuity_performance(month="202401", ...)

    # Load legacy output
    legacy_df = pd.read_csv("tests/fixtures/legacy_output_202401.csv")

    # Compare
    assert len(new_result.records) == len(legacy_df)
    assert new_result.total_assets == legacy_df["期末资产规模"].sum()
```

### Test Commands

```bash
# Run unit tests only
uv run pytest -m unit tests/unit/domain/{domain}/

# Run integration tests
uv run pytest -m integration tests/integration/domain/{domain}/

# Run all domain tests
uv run pytest tests/unit/domain/{domain}/ tests/integration/domain/{domain}/
```

---

## Code Templates

### models.py Template

```python
"""Pydantic data models for {domain} domain."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from work_data_hub.infrastructure.cleansing import get_cleansing_registry

CLEANSING_DOMAIN = "{domain}"
CLEANSING_REGISTRY = get_cleansing_registry()


class {Domain}In(BaseModel):
    """Bronze layer input model - lenient validation."""

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_default=True,
    )

    # Define fields with Optional types for lenient validation
    primary_key: Optional[str] = Field(None, description="Primary identifier")
    report_date: Optional[Union[date, str, int]] = Field(None, description="Report date")
    # ... add domain-specific fields

    @model_validator(mode="before")
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> dict:
        """Convert NaN values to None for proper handling."""
        import math
        if not isinstance(data, dict):
            return data
        return {
            k: None if isinstance(v, float) and math.isnan(v) else v
            for k, v in data.items()
        }


class {Domain}Out(BaseModel):
    """Silver/Gold layer output model - strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
    )

    # Define fields with strict types
    primary_key: str = Field(..., min_length=1, description="Primary identifier")
    report_date: date = Field(..., description="Report date")
    # ... add domain-specific fields

    @field_validator("report_date", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> Optional[date]:
        from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese
        return parse_yyyymm_or_chinese(v) if v else None
```

### schemas.py Template

```python
"""Pandera DataFrame schemas for {domain} domain."""
from __future__ import annotations

from typing import List, Sequence, Tuple

import pandas as pd
import pandera.pandas as pa

BRONZE_REQUIRED_COLUMNS: Sequence[str] = (
    "primary_key",
    "report_date",
    # ... add required columns
)

GOLD_REQUIRED_COLUMNS: Sequence[str] = (
    "primary_key",
    "report_date",
    # ... add required columns
)

GOLD_COMPOSITE_KEY: Sequence[str] = ("report_date", "primary_key")


Bronze{Domain}Schema = pa.DataFrameSchema(
    columns={
        "primary_key": pa.Column(pa.String, nullable=True, coerce=True),
        "report_date": pa.Column(pa.DateTime, nullable=True, coerce=True),
        # ... add columns
    },
    strict=False,
    coerce=True,
)


Gold{Domain}Schema = pa.DataFrameSchema(
    columns={
        "primary_key": pa.Column(pa.String, nullable=False, coerce=True),
        "report_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
        # ... add columns with business rule checks
    },
    strict=True,
    coerce=True,
    unique=GOLD_COMPOSITE_KEY,
)
```

### service.py Template

```python
"""Business service layer for {domain} domain."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import DomainPipelineResult, PipelineContext
from work_data_hub.infrastructure.validation import export_error_csv

from .helpers import convert_dataframe_to_models, normalize_month, run_discovery
from .models import {Domain}Out
from .pipeline_builder import build_bronze_to_silver_pipeline

logger = structlog.get_logger(__name__)

# Choose loading strategy based on table type
ENABLE_UPSERT_MODE = False  # Detail tables -> REFRESH; Aggregate -> True (UPSERT)

# UPSERT keys (used when ENABLE_UPSERT_MODE = True)
DEFAULT_UPSERT_KEYS = ["report_date", "primary_key"]

# REFRESH keys (used when ENABLE_UPSERT_MODE = False)
DEFAULT_REFRESH_KEYS = ["report_date", "business_type", "plan_type"]


def process_{domain}(
    month: str,
    *,
    file_discovery: Any,
    warehouse_loader: Any,
    domain: str = "{domain}",
    table_name: str = "{domain}_table",
    schema: str = "public",
    upsert_keys: Optional[List[str]] = None,
    refresh_keys: Optional[List[str]] = None,
) -> DomainPipelineResult:
    """Process {domain} data for a given month."""
    normalized_month = normalize_month(month)
    start_time = time.perf_counter()

    logger.bind(domain=domain).info("pipeline.start", month=normalized_month)

    # Step 1: Discover and load source data
    discovery_result = run_discovery(
        file_discovery=file_discovery,
        domain=domain,
        month=normalized_month,
    )

    # Step 2: Build and execute pipeline
    pipeline = build_bronze_to_silver_pipeline()
    context = PipelineContext(
        pipeline_name="bronze_to_silver",
        domain=domain,
        # ... other context fields
    )
    result_df = pipeline.execute(discovery_result.df.copy(), context)

    # Step 3: Convert to models
    records, _ = convert_dataframe_to_models(result_df)

    # Step 4: Export failed records for debugging
    dropped_count = len(discovery_result.df) - len(records)
    if dropped_count > 0:
        # ... export failed records logic
        pass

    # Step 5: Load to warehouse (UPSERT for aggregate, REFRESH for detail)
    dataframe = pd.DataFrame([r.model_dump() for r in records])
    if ENABLE_UPSERT_MODE:
        actual_upsert_keys = upsert_keys if upsert_keys is not None else DEFAULT_UPSERT_KEYS
        load_result = warehouse_loader.load_dataframe(
            dataframe,
            table=table_name,
            schema=schema,
            upsert_keys=actual_upsert_keys,
        )
    else:
        actual_refresh_keys = refresh_keys if refresh_keys is not None else DEFAULT_REFRESH_KEYS
        load_result = warehouse_loader.load_with_refresh(
            dataframe,
            table=table_name,
            schema=schema,
            refresh_keys=actual_refresh_keys,
        )

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.bind(domain=domain).info("pipeline.completed", duration_ms=duration_ms)

    return DomainPipelineResult(
        success=True,
        rows_loaded=load_result.rows_inserted + load_result.rows_updated,
        rows_failed=dropped_count,
        duration_ms=duration_ms,
        file_path=Path(discovery_result.file_path),
        version="N/A",
    )
```

### pipeline_builder.py Template

```python
"""Pipeline composition for {domain} domain."""
from __future__ import annotations

from typing import Dict, Optional

import structlog

from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    Pipeline,
    TransformStep,
)

from .constants import COLUMN_ALIAS_MAPPING, LEGACY_COLUMNS_TO_DELETE

logger = structlog.get_logger(__name__)


def build_bronze_to_silver_pipeline() -> Pipeline:
    """Compose the Bronze -> Silver pipeline using shared infrastructure steps."""
    steps: list[TransformStep] = [
        # Step 1: Column name standardization
        MappingStep(COLUMN_ALIAS_MAPPING),

        # Step 2: Data cleansing via CleansingRegistry
        CleansingStep(domain="{domain}"),

        # Step 3: Domain-specific transformations
        # CalculationStep({...}),

        # Step 4: Drop legacy columns
        DropStep(list(LEGACY_COLUMNS_TO_DELETE)),
    ]

    pipeline = Pipeline(steps)

    logger.bind(domain="{domain}").info(
        "Built bronze_to_silver pipeline",
        step_count=len(steps),
    )

    return pipeline
```

---

## Reference Implementations

### annuity_performance (Primary Reference)

- **Location:** `src/work_data_hub/domain/annuity_performance/`
- **Documentation:** `docs/domains/annuity_performance.md`
- **Runbook:** `docs/runbooks/annuity_performance.md`
- **Features:** Full 6-file structure, company ID enrichment, complex transformations

### annuity_income (Validation Reference)

- **Location:** `src/work_data_hub/domain/annuity_income/`
- **Documentation:** Not yet published; reference source code for patterns
- **Purpose:** Validates Infrastructure Layer architecture generality
- **Features:** Simpler structure, demonstrates pattern reusability

---

## References

- [System Architecture](../architecture/index.md)
- [Pipeline Integration Guide](../architecture-patterns/pipeline-integration-guide.md)
- [Cleansing Rules Documentation](../cleansing-rules/)
- [BMM Index](../bmm-index.md)
- [Sprint Change Proposal - Post-MVP Optimizations](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-06-post-mvp-optimizations.md)

---

**End of Guide**
