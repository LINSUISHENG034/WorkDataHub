# Domain Development Guide

**Version:** 2.1
**Last Updated:** 2026-03-04
**Based On:** Orchestration Layer Refactor (Protocol + Registry + Factory)

---

## Quick Links

| Document | Purpose |
|----------|---------|
| [Domain Migration Workflow](./workflow.md) | **Start Here** - End-to-end migration process |
| [Cleansing Rules to Code Mapping](./code-mapping.md) | How to translate documentation to code |
| [Troubleshooting Guide](./troubleshooting.md) | Common issues and solutions |
| [Cleansing Rules Template](../../templates/cleansing-rules-template.md) | Template for creating cleansing rules documents |
| [Legacy Parity Validation Guide](../../runbooks/legacy-parity-validation.md) | Validation procedures |

---

## Overview

This guide provides comprehensive instructions for implementing new data domains in WorkDataHub. It is based on lessons learned from Epic 5.5, which validated the Infrastructure Layer architecture by implementing the `annuity_income` domain as a second reference implementation alongside `annuity_performance`.

> **Note:** For the complete end-to-end migration workflow, see [Domain Migration Workflow](./workflow.md).
>
> **Phase Mapping:** This guide's Phase 1-2 correspond to workflow.md's Phase 1-2. This guide's Phase 3-7 are detailed sub-phases of workflow.md's Phase 3 (Implementation).

### Purpose

- Enable developers to independently create new domains following established patterns
- Document the 8-file standard domain structure
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

## Domain Directory Structure (8-File Standard)

Each domain follows a standardized 8-file structure (updated with Protocol adapter):

```
src/work_data_hub/domain/{domain_name}/
├── __init__.py          # Module exports
├── adapter.py           # DomainServiceProtocol implementation
├── constants.py         # Domain-specific constants
├── models.py            # Pydantic data models (Bronze/Silver/Gold)
├── schemas.py           # Pandera DataFrame schemas
├── helpers.py           # Data transformation helpers
├── service.py           # Business service layer
└── pipeline_builder.py  # Pipeline step configuration
```

### File Responsibilities

| File | Purpose | Key Contents |
|------|---------|--------------|
| `__init__.py` | Public API exports | Export main service function, models, schemas |
| **`adapter.py`** | **Protocol implementation** | **`{Domain}Service` class implementing `DomainServiceProtocol`** |
| `models.py` | Data models | `{Domain}In` (Bronze), `{Domain}Out` (Silver/Gold) Pydantic models |
| `schemas.py` | DataFrame validation | `Bronze{Domain}Schema`, `Gold{Domain}Schema` Pandera schemas |
| `helpers.py` | Transformation utilities | `convert_dataframe_to_models()`, domain-specific helpers |
| `service.py` | Business logic | `process_{domain}()` / `process_with_enrichment()` |
| `pipeline_builder.py` | Pipeline composition | `build_bronze_to_silver_pipeline()` |
| `constants.py` | Static mappings | Column mappings, code translations, business rules |

---

## Development Checklist

### Phase 1: Dependency Analysis & Migration (PREREQUISITE)

- [ ] Identify all dependency tables from legacy code analysis
- [ ] Document dependencies in cleansing rules document (Section 2)
- [ ] **CRITICAL**: Complete Migration Strategy Decisions (Section 3)
  - [ ] Review each dependency table with team
  - [ ] Document chosen strategy and rationale
  - [ ] Team lead review and sign-off
- [ ] Execute migration based on decided strategy
  - [ ] For Enrichment Index: Use `scripts/migrations/migrate_legacy_to_enrichment_index.py`
  - [ ] For Direct Migration: Use appropriate migration scripts
  - [ ] For Static Embedding: Update constants files
- [ ] Complete Migration Validation Checklist (Section 4)
- [ ] Update migration status in documentation

### Phase 2: Analysis (Before Coding)

- [ ] Analyze legacy data source structure and column names
- [ ] Document column mappings (legacy name → new name)
- [ ] Identify validation rules and business constraints
- [ ] Document cleansing rules in `docs/cleansing-rules/{domain}.md`
- [ ] Identify upsert keys (unique record identifiers)
- [ ] Review existing domain implementations for patterns

### Phase 3: Implementation

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

### Phase 4: Protocol Adapter & Registration

- [ ] **Create `adapter.py`** implementing `DomainServiceProtocol`
  - [ ] `domain_name` property returning domain identifier
  - [ ] `requires_enrichment` property (True if needs CompanyEnrichmentService)
  - [ ] `requires_backfill` property (True if needs FK backfill)
  - [ ] `process()` method delegating to existing service
- [ ] **Register in `domain/registry.py`**
  - Add import and `register_domain()` call in `_register_all_domains()`
- [ ] Configure upsert keys (`DEFAULT_UPSERT_KEYS` in service.py)
- [ ] Add data source configuration (if using file discovery)
- [ ] Register domain cleansing rules in `CleansingRegistry`
- [ ] Create database migration (DDL + UNIQUE constraints)

### Phase 5: Testing & Validation

- [ ] Write unit tests for models (`tests/unit/domain/{domain}/`)
- [ ] Write unit tests for helpers and schemas
- [ ] Write integration tests for service layer
- [ ] Perform legacy parity validation (compare output with legacy system)
- [ ] Establish performance baseline

### Phase 6: Documentation

- [ ] Create domain documentation (`docs/domains/{domain}.md`)
- [ ] Create operational runbook (`docs/runbooks/{domain}.md`)
- [ ] Update `docs/bmm-index.md` with links to new documentation
- [ ] Document any domain-specific cleansing rules

### Phase 7: Deployment & Merge

- [ ] Create PR referencing story ID; include doc changes and checklists
- [ ] Run smoke tests (minimum: `uv run pytest -m unit`) and attach results
- [ ] Request reviewer from domain TL; capture review notes
- [ ] Resolve comments; re-run tests after changes
- [ ] Merge to `main` only after approvals; tag release notes if applicable
- [ ] Notify ops for Dagster/DB rollout if schema/config changed

---

## Key Configuration Patterns

### Foreign Key Backfill Configuration (config/foreign_keys.yml)

Use this when the domain 需要配置驱动的引用表回填（Epic 6.2）。`foreign_keys` 节是可选的，缺失时 loader 返回空列表（no-op）。

> **Note:** Story 6.2-P14 将 FK 配置从 `data_sources.yml` 拆分为独立的 `config/foreign_keys.yml` 文件，遵循单一职责原则。

**Steps**
1. 打开 `config/foreign_keys.yml`
2. 在目标域下添加 `foreign_keys`（依赖只能指向同一域内已声明的 FK，禁止跨域；不允许环/自引用）：

```yaml
# config/foreign_keys.yml
schema_version: "1.2"  # Story 6.2-P18 added advanced aggregations

domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        target_schema: "mapping"  # specify target schema
        mode: "insert_missing"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
          - source: "计划名称"
            target: "计划全称"
            optional: true
          # Story 6.2-P15: max_by aggregation
          - source: "机构代码"
            target: "主拓代码"
            optional: true
            aggregation:
              type: "max_by"
              order_column: "期末资产规模"
          # Story 6.2-P15: concat_distinct aggregation
          - source: "业务类型"
            target: "管理资格"
            optional: true
            aggregation:
              type: "concat_distinct"
              separator: "+"
              sort: true

      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        target_schema: "mapping"
        depends_on: ["fk_plan"]  # same-domain only
        backfill_columns:
          - source: "组合代码"
            target: "组合代码"
          - source: "计划代码"
            target: "年金计划号"
```

**Aggregation Types (Story 6.2-P15 / P18)**

| Type | Description | Required Fields |
|------|-------------|----------------|
| `first` | Default, takes first non-null value per group | None |
| `max_by` | Select value from row with maximum order column | `order_column` |
| `concat_distinct` | Concatenate distinct values with separator | `separator` (default `+`), `sort` (default true) |
| `count_distinct` | Count unique non-null values per group | None |
| `template` | Construct text from template with placeholders | `template` |
| `lambda` | Execute custom Python lambda expression | `code` |
| `jsonb_append` | Append list values to JSONB array column | `code` |

**Lambda Security Note:**
> [!CAUTION]
> The `lambda` aggregation type executes arbitrary Python code via `eval()`. This is considered safe because:
> 1. Config files (`config/foreign_keys.yml`) are developer-controlled (trusted source)
> 2. Not exposed to end-user input
> 3. Code review required for config changes
>
> **Never** allow user-provided input to flow into lambda code strings.

**Best Practices**
- **Unique per domain:** FK 名称在同一域内必须唯一。
- **Same-domain dependencies only:** `depends_on` 仅能引用同域 FK，跨域引用应拆分为独立域配置。
- **No cycles:** 环/自引用会在加载阶段被拒绝（错误信息包含 `circular dependency`）。
- **Optional columns:** 仅对非必需字段使用 `optional: true`，避免吞掉关键字段。
- **Backward compatibility:** `schema_version: "1.2"` + 缺失 `foreign_keys` 节均应无副作用（返回空列表）。

**Schema Version Evolution Strategy**

| Version | Features | Migration Path |
|---------|----------|----------------|
| 1.0 | Basic `foreign_keys`, `depends_on`, `optional` | N/A (initial) |
| 1.1 | `target_schema`, `skip_blank_values` | Additive, 1.0 compatible |
| 1.2 (current) | Advanced aggregations (`max_by`, `concat_distinct`, `count_distinct`, `template`, `lambda`, `jsonb_append`) | Additive, 1.x compatible |
| 2.0 (future) | Breaking changes (if any) | Migration script + deprecation warnings |

**Version Compatibility Rules:**
1. **Minor versions (1.x):** Always backward compatible; new fields are optional with sensible defaults
2. **Major versions (2.x):** May introduce breaking changes; migration scripts provided
3. **Missing `foreign_keys`:** Always treated as empty list (no-op) regardless of version
4. **Unknown fields:** Rejected by Pydantic `extra='forbid'` to catch typos early

### Data Loading Mode Configuration

WorkDataHub uses a CLI-driven data loading approach. The final loading step (`load_op`) performs an **idempotent delete-then-insert** operation on the target table, driven by the composite primary key (`pk`) defined in `config/data_sources.yml`.

#### Default Mode: `delete_insert`

The default (and most common) mode:
1. Delete existing rows matching the PK values found in the input data
2. Bulk insert all new records

This is **not** an `ON CONFLICT` upsert — it is a delete-then-insert pattern that ensures idempotent reloads.

#### Alternative Mode: `append`

For append-only use cases where existing data should never be deleted.

#### Configuration in `data_sources.yml`

```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    output:
      table_name: "规模明细"
      pk: ["月度", "业务类型", "计划类型"]  # Composite key for delete_insert
    # ...
```

The `pk` attribute defines which columns scope the DELETE before INSERT. All existing records matching the PK combinations present in the input data are deleted, then all new records are inserted.

#### CLI Behavior

- Without `--execute`, the CLI runs in **plan-only mode** (no database writes)
- `generic_backfill_refs_op` is always invoked but returns 0 operations if no FK config exists for the domain

#### Current Domain Configurations

| Domain | Output Table | Output Schema | PK (delete scope) |
|--------|-------------|---------------|-------------------|
| `annuity_performance` | `规模明细` | `business` | `["月度", "业务类型", "计划类型"]` |
| `annuity_income` | `收入明细` | `business` | `["月度", "业务类型", "计划类型"]` |
| `annual_award` | `中标客户明细` | `customer` | `["上报月份", "业务类型"]` |
| `annual_loss` | `流失客户明细` | `customer` | `["上报月份", "业务类型"]` |
| `sandbox_trustee_performance` | `sandbox_trustee_performance` | `sandbox` | (none — sandbox domain) |

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

# Composite primary key for delete_insert loading (must match data_sources.yml pk)
DEFAULT_PK_KEYS = ["report_date", "business_type", "plan_type"]


def process_{domain}(
    month: str,
    *,
    file_discovery: Any,
    warehouse_loader: Any,
    domain: str = "{domain}",
    table_name: str = "{domain}_table",
    schema: str = "public",
    pk_keys: Optional[List[str]] = None,
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
    )
    result_df = pipeline.execute(discovery_result.df.copy(), context)

    # Step 3: Convert to models
    records, _ = convert_dataframe_to_models(result_df)

    # Step 4: Export failed records for debugging
    dropped_count = len(discovery_result.df) - len(records)
    if dropped_count > 0:
        # ... export failed records logic
        pass

    # Step 5: Load to warehouse (delete_insert mode driven by CLI/data_sources.yml)
    dataframe = pd.DataFrame([r.model_dump() for r in records])
    actual_pk = pk_keys if pk_keys is not None else DEFAULT_PK_KEYS
    load_result = warehouse_loader.load_dataframe(
        dataframe,
        table=table_name,
        schema=schema,
        pk_keys=actual_pk,
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
---

### adapter.py Template — Pattern A: Service Delegation

Use this pattern when the adapter delegates to an existing `service.py` function (e.g., `annuity_performance`, `annuity_income`).

```python
"""Domain Service Adapter implementing DomainServiceProtocol.

This adapter wraps existing domain service logic and provides a unified
interface for the generic orchestration layer.
"""
import time
from typing import Any, Dict, List

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    ProcessingContext,
)


class {Domain}Service:
    """{Domain} 领域服务适配器.

    Implements DomainServiceProtocol for unified orchestration.
    """

    @property
    def domain_name(self) -> str:
        return "{domain}"

    @property
    def requires_enrichment(self) -> bool:
        """Set True if domain needs CompanyEnrichmentService injection."""
        return True  # or False based on domain needs

    @property
    def requires_backfill(self) -> bool:
        """Set True if domain needs FK backfill after processing."""
        return True  # or False based on domain needs

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """委托给现有的 service 处理逻辑."""
        from .service import process_with_enrichment  # or process_{domain}

        start = time.perf_counter()

        result = process_with_enrichment(
            rows,
            data_source=context.data_source,
            enrichment_service=context.enrichment_service,
            export_unknown_names=context.export_unknown_names,
            session_id=context.session_id,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        return DomainProcessingResult(
            records=result.records,
            total_input=len(rows),
            total_output=len(result.records),
            failed_count=len(rows) - len(result.records),
            processing_time_ms=elapsed_ms,
            enrichment_stats=(
                result.enrichment_stats.model_dump()
                if hasattr(result, "enrichment_stats") and result.enrichment_stats
                else None
            ),
            unknown_names_csv=getattr(result, "unknown_names_csv", None),
        )
```

**Registration in `domain/registry.py`:**

```python
# Add in _register_all_domains() function:
from work_data_hub.domain.{domain_name}.adapter import {Domain}Service

register_domain("{domain_name}", {Domain}Service())
```

### adapter.py Template — Pattern B: Direct Pipeline Execution

Use this pattern when the adapter builds and executes the pipeline directly in `process()`, bypassing `service.py` (e.g., `annual_award`, `annual_loss`). This is appropriate when the domain has no standalone service function and the adapter *is* the orchestration layer.

```python
"""Domain Service Adapter — Direct Pipeline Execution.

The adapter builds the pipeline in process(), managing DB connections
and pipeline lifecycle directly.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    ProcessingContext,
)


class {Domain}Service:
    """{Domain} 领域服务适配器 (Direct Pipeline pattern)."""

    @property
    def domain_name(self) -> str:
        return "{domain}"

    @property
    def requires_enrichment(self) -> bool:
        return True

    @property
    def requires_backfill(self) -> bool:
        return False  # FK backfill handled at orchestration level via config

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """Build and execute pipeline directly."""
        from .helpers import convert_dataframe_to_models
        from .pipeline_builder import build_bronze_to_silver_pipeline
        from work_data_hub.domain.pipelines.types import PipelineContext
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            CompanyMappingRepository,
        )

        start = time.perf_counter()

        # Create mapping repository if enrichment is enabled
        mapping_repository = None
        repo_connection = None

        if context.enrichment_service is not None:
            try:
                from sqlalchemy import create_engine
                from work_data_hub.config.settings import get_settings

                settings = get_settings()
                engine = create_engine(settings.get_database_connection_string())
                repo_connection = engine.connect()
                mapping_repository = CompanyMappingRepository(repo_connection)
            except Exception:
                pass  # Continue without mapping repository

        try:
            df = pd.DataFrame(rows)

            eqc_config = (
                context.eqc_config
                if context.eqc_config
                else EqcLookupConfig.disabled()
            )

            pipeline = build_bronze_to_silver_pipeline(
                eqc_config=eqc_config,
                mapping_repository=mapping_repository,
                db_connection=repo_connection,
            )

            pipeline_context = PipelineContext(
                pipeline_name="bronze_to_silver",
                execution_id=f"{domain}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={"domain": "{domain}"},
                domain="{domain}",
                run_id=f"{domain}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                extra={"data_source": context.data_source},
            )

            result_df = pipeline.execute(df, pipeline_context)
            records, failed_count = convert_dataframe_to_models(result_df)

            elapsed_ms = (time.perf_counter() - start) * 1000

            return DomainProcessingResult(
                records=records,
                total_input=len(rows),
                total_output=len(records),
                failed_count=failed_count,
                processing_time_ms=elapsed_ms,
            )

        finally:
            if repo_connection is not None:
                try:
                    repo_connection.commit()  # Persist backflow data
                except Exception:
                    repo_connection.rollback()
                repo_connection.close()
```

**When to use which pattern:**

| Pattern | When to Use | Reference Implementations |
|---------|------------|--------------------------|
| **A: Service Delegation** | Domain has an existing `process_*()` or `process_with_enrichment()` function in `service.py` | `annuity_performance`, `annuity_income` |
| **B: Direct Pipeline** | Adapter *is* the orchestration layer; no standalone service function | `annual_award`, `annual_loss` |

---

## Reference Implementations

### annuity_performance (Primary Reference — Service Delegation Pattern)

- **Location:** `src/work_data_hub/domain/annuity_performance/`
- **Documentation:** `docs/domains/annuity_performance.md`
- **Runbook:** `docs/runbooks/annuity_performance.md`
- **Features:** Full 8-file structure, Protocol adapter (Pattern A), company ID enrichment, complex transformations, FK backfill

### annuity_income (Validation Reference — Service Delegation Pattern)

- **Location:** `src/work_data_hub/domain/annuity_income/`
- **Documentation:** Not yet published; reference source code for patterns
- **Purpose:** Validates Infrastructure Layer architecture generality
- **Features:** Protocol adapter (Pattern A), simpler structure, demonstrates pattern reusability

### annual_award (Direct Pipeline Pattern Reference)

- **Location:** `src/work_data_hub/domain/annual_award/`
- **Purpose:** Reference for Direct Pipeline Execution adapter pattern (Pattern B)
- **Features:** Multi-sheet support (`sheet_names` config), plan code enrichment (`PlanCodeEnrichmentStep`), company ID resolution, `customer` schema output

### annual_loss (Direct Pipeline Pattern Reference)

- **Location:** `src/work_data_hub/domain/annual_loss/`
- **Purpose:** Structurally identical to `annual_award`; validates Pattern B reusability
- **Features:** Multi-sheet support, plan code enrichment, company ID resolution, `customer` schema output

---

## Code Review Checklist (Lessons from annual_award)

Based on the annual_award domain code review, the following checklist ensures new domains properly integrate with existing infrastructure:

### 1. Company ID Resolution

**Required Components:**
- [ ] `mapping_repository` passed to `CompanyIdResolutionStep`
- [ ] `company_id_column` set in `ResolutionStrategy` to use source data
- [ ] `repo_connection.commit()` in finally block for backflow persistence

**Common Mistakes:**
```python
# ❌ WRONG - Missing mapping_repository (DB cache lookup skipped)
pipeline = build_bronze_to_silver_pipeline(eqc_config=eqc_config)

# ✅ CORRECT - Pass mapping_repository for enrichment_index lookup
pipeline = build_bronze_to_silver_pipeline(
    eqc_config=eqc_config,
    mapping_repository=mapping_repository,
    db_connection=repo_connection,
)
```

**ResolutionStrategy Configuration:**
```python
# ❌ WRONG - company_id_column=None ignores source data
strategy = ResolutionStrategy(
    company_id_column=None,  # Source company_id not used!
    ...
)

# ✅ CORRECT - Use existing company_id from source
strategy = ResolutionStrategy(
    company_id_column="company_id",  # Preserves source data
    ...
)
```

### 2. Plan Code Defaults

**Required:** Apply `PLAN_CODE_DEFAULTS` for empty plan codes after enrichment.

```python
from work_data_hub.infrastructure.mappings import PLAN_CODE_DEFAULTS

# For domains using '计划代码' column:
from work_data_hub.infrastructure.transforms import apply_plan_code_defaults
steps.append(CalculationStep({"计划代码": lambda df: apply_plan_code_defaults(df)}))

# For domains using different column names (e.g., '年金计划号'):
# Create adapter function that maps to PLAN_CODE_DEFAULTS
```

### 3. Database Connection Management

**Pattern from annuity_performance:**
```python
mapping_repository = None
repo_connection = None
try:
    from sqlalchemy import create_engine
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())
    repo_connection = engine.connect()
    mapping_repository = CompanyMappingRepository(repo_connection)
except Exception as e:
    logger.warning("Failed to initialize CompanyMappingRepository", error=str(e))

try:
    # ... pipeline execution ...
finally:
    if repo_connection is not None:
        try:
            repo_connection.commit()  # CRITICAL: Persist backflow data
        except Exception:
            repo_connection.rollback()
        repo_connection.close()
```

### 4. Data Priority Rules

**Principle:** Always preserve existing source data; only fill empty values.

```python
# ✅ CORRECT - Only process empty values
mask_empty = df["column"].isna() | (df["column"] == "")
# Apply enrichment only to mask_empty rows
```

### 5. EQC Query Configuration (Critical for Company ID Resolution)

**Problem:** Domains with `sync_budget=0` will only use cache, never query EQC API.

**Required Changes for New Domains:**

1. **CLI config.py** - Add EQC configuration block:
```python
# In src/work_data_hub/cli/etl/config.py
if domain == "your_domain":
    from work_data_hub.infrastructure.enrichment import EqcLookupConfig

    eqc_config = EqcLookupConfig.from_cli_args(args)
    run_config["ops"]["process_your_domain_op"] = {
        "config": {
            "enrichment_enabled": eqc_config.enabled,
            "enrichment_sync_budget": eqc_config.sync_budget,
            "export_unknown_names": eqc_config.export_unknown_names,
            "eqc_lookup_config": eqc_config.to_dict(),
            "plan_only": effective_plan_only,
            "session_id": session_id,
        }
    }
```

2. **CLI main.py** - Add domain to enrichment_domains:
```python
# In src/work_data_hub/cli/etl/main.py
enrichment_domains = {"annuity_performance", "your_domain"}  # Add your domain
```

3. **Op function** - Use ProcessingConfig instead of hardcoded values:
```python
# ❌ WRONG - Hardcoded sync_budget=0 (no EQC queries)
eqc_config = EqcLookupConfig(
    enabled=True,
    sync_budget=0,  # Never queries EQC!
)

# ✅ CORRECT - Use ProcessingConfig from CLI
if config.eqc_lookup_config is not None:
    eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config)
else:
    eqc_config = EqcLookupConfig(
        enabled=config.enrichment_enabled,
        sync_budget=max(config.enrichment_sync_budget, 0),
        auto_create_provider=config.enrichment_enabled,
        export_unknown_names=config.export_unknown_names,
        auto_refresh_token=True,
    )
```

### 6. Plan Code Defaults

**Required:** Apply `PLAN_CODE_DEFAULTS` for empty plan codes.

```python
from work_data_hub.infrastructure.mappings import PLAN_CODE_DEFAULTS
# PLAN_CODE_DEFAULTS = {"集合计划": "AN001", "单一计划": "AN002"}

# For standard '计划代码' column:
from work_data_hub.infrastructure.transforms import apply_plan_code_defaults

# For custom column names, create adapter function
```

---

## Plan Code Enrichment (PlanCodeEnrichmentStep)

Domains that need to fill empty `年金计划号` values can use the `PlanCodeEnrichmentStep` pipeline step. This step performs a DB lookup against the `客户年金计划` table.

**Domains using this step:** `annual_award`, `annual_loss`

### How It Works

1. Identifies rows where `年金计划号` is empty
2. Queries the `客户年金计划` table using `company_id` + `产品线代码` as join keys
3. Selects the best plan code based on `计划类型` prefix rules:
   - **集合计划** → Prefer plan codes starting with `P` (e.g., P0001, P0002)
   - **单一计划** → Prefer plan codes starting with `S` (e.g., S0001, S0002)
4. If no matching prefix is found, uses any available plan code for the company
5. Only updates rows where `年金计划号` is empty (preserves existing values)

### Usage in pipeline_builder.py

```python
from .pipeline_builder import PlanCodeEnrichmentStep

# Requires a DB connection (passed via build_bronze_to_silver_pipeline)
steps.append(PlanCodeEnrichmentStep(db_connection=db_connection))
```

> **Note:** This step is distinct from `PLAN_CODE_DEFAULTS` (which provides static fallback codes). `PlanCodeEnrichmentStep` performs actual DB lookups for dynamic plan code resolution.

---

## Multi-Sheet Configuration

Some domains read from multiple Excel sheets within the same file. Configure this via `sheet_names` in `config/data_sources.yml`.

### Configuration Example (from `annual_award`)

```yaml
# config/data_sources.yml
domains:
  annual_award:
    sheet_name: "企年受托中标(空白)"        # Fallback for single-sheet mode
    sheet_names:                            # Multi-sheet support
      - "企年受托中标(空白)"
      - "企年投资中标(空白)"
    # ...
```

**Behavior:**
- When `sheet_names` is present, the loader reads all listed sheets and concatenates them into a single DataFrame
- `sheet_name` serves as a fallback for single-sheet mode (backwards compatible)
- Each sheet typically represents a different `业务类型` (e.g., trustee vs. investee)

**Domains using multi-sheet:** `annual_award` (2 sheets), `annual_loss` (2 sheets)

---

## `requires_backfill` Property Semantics

The `requires_backfill` adapter property and the FK backfill configuration in `config/foreign_keys.yml` serve different purposes:

| Mechanism | Purpose | Who Uses It |
|-----------|---------|-------------|
| `adapter.requires_backfill` property | Protocol-level flag for orchestration checks | Orchestrator queries this to decide whether to *attempt* backfill |
| `config/foreign_keys.yml` domain entry | Actual FK backfill rules | CLI config builder always configures `generic_backfill_refs_op`; it returns 0 ops if no FK config exists |

**In practice:** Even if `requires_backfill = False` on the adapter, the CLI config builder always wires up `generic_backfill_refs_op`. The op itself is a no-op when no FK rules exist for the domain. Setting `requires_backfill = True` signals to the orchestration layer that the domain *expects* FK backfill to run as part of its processing contract.

**Current domain settings:**

| Domain | `requires_backfill` | Has FK config? |
|--------|-------------------|---------------|
| `annuity_performance` | `True` | Yes (5 FK rules) |
| `annuity_income` | `True` | Yes (5 FK rules) |
| `annual_award` | `False` | Yes (1 FK rule: `fk_customer`) |
| `annual_loss` | `False` | Yes (1 FK rule: `fk_customer`) |
| `sandbox_trustee_performance` | `False` | No |

---

## References

- [System Architecture](../architecture/index.md)
- [Pipeline Integration Guide](../architecture-patterns/pipeline-integration-guide.md)
- [Cleansing Rules Documentation](../cleansing-rules/)
- [BMM Index](../bmm-index.md)
- [Sprint Change Proposal - Post-MVP Optimizations](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-06-post-mvp-optimizations.md)

---

**End of Guide**
