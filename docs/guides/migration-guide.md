# Domain Migration Guide (Epic 9 Reference)

## Overview

This guide documents how to migrate a legacy domain to the new infrastructure-based
architecture established in Epic 5. The `annuity_performance` domain serves as the
reference implementation.

## Prerequisites

- Familiarity with the infrastructure layer (`src/work_data_hub/infrastructure/`)
- Understanding of Clean Architecture boundaries
- Access to legacy domain code for analysis

## Migration Steps

### Step 1: Analyze Legacy Domain

1. **Identify data sources** - Excel files, APIs, databases
2. **Map transformation logic** - Column mappings, calculations, validations
3. **Document business rules** - Cleansing rules, enrichment logic
4. **Catalog output schema** - Database table structure, required columns

### Step 2: Create Domain Directory Structure (6-File Standard)

```
src/work_data_hub/domain/{domain_name}/
├── __init__.py
├── constants.py      # Static mappings, configuration
├── models.py         # Pydantic models (input/output)
├── schemas.py        # Pandera validation schemas
├── pipeline_builder.py  # Pipeline construction using infra steps
├── service.py        # Lightweight orchestrator
└── helpers.py        # Domain-specific helper functions
```

### Step 3: Define Pydantic Models

Create input and output models in `models.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal

class DomainRecordIn(BaseModel):
    """Input model for raw data."""
    field1: str
    field2: Optional[Decimal] = None

class DomainRecordOut(BaseModel):
    """Output model for warehouse."""
    field1: str
    field2: Decimal = Field(ge=0)
    company_id: str
```

### Step 4: Create Pandera Schemas

Define validation schemas in `schemas.py`. Use `infrastructure.validation.schema_steps` validation classes in the pipeline.

```python
import pandera as pa
from pandera.typing import Series

class BronzeSchema(pa.DataFrameModel):
    """Raw data validation."""
    field1: Series[str] = pa.Field(nullable=False)
    field2: Series[float] = pa.Field(nullable=True, coerce=True)

class GoldSchema(pa.DataFrameModel):
    """Warehouse-ready validation."""
    field1: Series[str] = pa.Field(nullable=False)
    field2: Series[float] = pa.Field(ge=0, coerce=True)
    company_id: Series[str] = pa.Field(nullable=False)
```

### Step 5: Build Pipeline Using Infrastructure Steps

Create `pipeline_builder.py` utilizing standard steps and validation steps:

```python
from work_data_hub.infrastructure.transforms.base import Pipeline
from work_data_hub.infrastructure.transforms.standard_steps import (
    MappingStep, ReplacementStep, CleansingStep, DropStep
)
from work_data_hub.infrastructure.transforms.projection_step import GoldProjectionStep
from work_data_hub.infrastructure.validation.schema_steps import (
    BronzeSchemaValidationStep
)
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolver, ResolutionStrategy
)

def build_bronze_to_silver_pipeline(
    enrichment_service=None,
    plan_override_mapping=None,
) -> Pipeline:
    """Build the transformation pipeline."""

    steps = [
        BronzeSchemaValidationStep(),
        MappingStep(column_mapping=COLUMN_MAPPING),
        ReplacementStep(column="status", replacements=STATUS_MAPPING),
        CleansingStep(domain="your_domain"),
        CompanyIdResolutionStep(
            enrichment_service=enrichment_service,
            plan_override_mapping=plan_override_mapping or {},
        ),
        GoldProjectionStep(), # Projects to Gold schema columns
    ]

    return Pipeline(steps=steps)
```

### Step 6: Create Service Orchestrator

Create lightweight `service.py` (<200 lines):

```python
from work_data_hub.domain.pipelines.types import (
    DomainPipelineResult, PipelineContext
)
from .helpers import convert_dataframe_to_models

def process_domain(
    month: str,
    file_discovery,
    warehouse_loader,
    enrichment_service=None,
) -> DomainPipelineResult:
    """
    Main entry point for domain processing.

    Args:
        month: Target month (YYYYMM format)
        file_discovery: Injected file discovery service
        warehouse_loader: Injected warehouse loader
        enrichment_service: Optional enrichment service

    Returns:
        DomainPipelineResult with processing metrics
    """
    # 1. Discover and load data
    discovery_result = file_discovery.discover_and_load(
        domain="your_domain", month=month
    )

    # 2. Build and execute pipeline
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=enrichment_service
    )
    context = PipelineContext(
        pipeline_name="bronze_to_silver",
        execution_id=f"your_domain_{month}",
        domain="your_domain",
    )
    result_df = pipeline.execute(discovery_result.dataframe, context)
    
    # Convert to models if needed
    records, unknown_names = convert_dataframe_to_models(result_df)
    dataframe = _records_to_dataframe(records)

    # 3. Load to warehouse
    load_result = warehouse_loader.load_dataframe(
        dataframe,
        table="your_domain_table",
        upsert_keys=["month", "plan_code", "company_id"],
    )

    return DomainPipelineResult(
        success=True,
        rows_loaded=load_result.rows_inserted,
        rows_failed=len(discovery_result.dataframe) - len(result_df),
        duration_ms=...,
        file_path=discovery_result.file_path,
        version=discovery_result.version,
    )
```

### Step 7: Add Tests

Create test files following existing patterns:

```
tests/
├── unit/domain/{domain_name}/
│   ├── test_models.py
│   ├── test_schemas.py
│   └── test_pipeline_builder.py
├── integration/domain/{domain_name}/
│   └── test_end_to_end.py
└── e2e/
    └── test_{domain_name}_e2e.py
```

## Reference Implementation

The `annuity_performance` domain demonstrates all patterns:

| Component | File | Lines |
|-----------|------|-------|
| Constants | `constants.py` | ~95 |
| Models | `models.py` | ~340 |
| Schemas | `schemas.py` | ~210 |
| Pipeline Builder | `pipeline_builder.py` | ~135 |
| Service | `service.py` | ~160 |
| Helpers | `helpers.py` | ~130 |
| **Total** | | **~1,100** |

## Common Patterns

### 1. Column Mapping

```python
COLUMN_MAPPING = {
    "原始列名": "标准列名",
    "Old Name": "new_name",
}
```

### 2. Value Replacement

```python
STATUS_MAPPING = {
    "A": "Active",
    "I": "Inactive",
}
```

### 3. Cleansing Rules

Configure in `infrastructure/cleansing/settings/cleansing_rules.yml`:

```yaml
domains:
  your_domain:
    - rule: strip_whitespace
      columns: ["field1", "field2"]
    - rule: normalize_numeric
      columns: ["amount"]
```

### 4. Company ID Resolution

```python
strategy = ResolutionStrategy(
    plan_code_column="计划代码",
    customer_name_column="客户名称",
    output_column="company_id",
    generate_temp_ids=True,
)
```

## Checklist

- [ ] Domain directory created with 6 standard files (including `helpers.py`)
- [ ] Pydantic models defined for input/output
- [ ] Pandera schemas created for Bronze/Gold validation
- [ ] Pipeline builder using infrastructure steps (schema_steps, projection_step)
- [ ] Service orchestrator (<200 lines)
- [ ] Unit tests for models and schemas
- [ ] Integration tests for pipeline
- [ ] E2E tests for full flow
- [ ] Cleansing rules configured in YAML
- [ ] Documentation updated

## Related Documentation

- [Infrastructure Layer](./architecture/infrastructure-layer.md)
- [Architectural Decisions](./architecture/architectural-decisions.md)
- [Implementation Patterns](./architecture/implementation-patterns.md)
