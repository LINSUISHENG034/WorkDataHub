# Infrastructure Layer Documentation

## Overview

The infrastructure layer (`src/work_data_hub/infrastructure/`) provides reusable,
domain-agnostic services that support Clean Architecture boundaries. Created as
part of Epic 5 (Stories 5.1-5.8), this layer enables rapid domain migration for
Epic 9 by centralizing common transformation, validation, and enrichment logic.

## Architecture Position

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                       │
│              (Dagster jobs, CLI, scheduling)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        I/O Layer                             │
│         (File connectors, DB loaders, API clients)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│    (Transforms, Validation, Cleansing, Enrichment)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                            │
│        (Business logic, Models, Schemas, Services)           │
└─────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/work_data_hub/infrastructure/
├── __init__.py
├── cleansing/
│   ├── __init__.py
│   ├── registry.py              # CleansingRegistry singleton
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── numeric_rules.py     # Numeric cleansing rules
│   │   └── string_rules.py      # String cleansing rules
│   ├── settings/
│   │   └── cleansing_rules.yml  # Domain-specific rule config
│   └── integrations/
│       └── pydantic_adapter.py  # Pydantic field validator
├── enrichment/
│   ├── __init__.py
│   ├── company_id_resolver.py   # Batch company ID resolution
│   ├── normalizer.py            # Company name normalization
│   └── types.py                 # ResolutionStrategy, ResolutionResult
├── settings/
│   ├── __init__.py
│   ├── data_source_schema.py    # Pydantic schemas for config
│   └── loader.py                # YAML config loader
├── transforms/
│   ├── __init__.py
│   ├── base.py                  # TransformStep ABC, Pipeline class
│   ├── projection_step.py       # Gold layer projection & validation
│   ├── standard_steps.py        # MappingStep, ReplacementStep, etc.
│   └── cleansing_step.py        # CleansingStep integration
└── validation/
    ├── __init__.py
    ├── error_handler.py         # handle_validation_errors()
    ├── report_generator.py      # Validation report generation
    ├── schema_helpers.py        # Schema utility functions
    ├── schema_steps.py          # Reusable schema validation steps
    └── types.py                 # ValidationErrorDetail, etc.
```

## Key Components

### 1. Transform Pipeline (`transforms/`)

The transform pipeline provides a composable framework for data transformations.

**Base Classes:**
- `TransformStep` - Abstract base class for all transformation steps
- `Pipeline` - Orchestrates step execution with metrics collection

**Standard Steps:**
- `MappingStep` - Column renaming/mapping
- `ReplacementStep` - Value replacement with mapping dict
- `CalculationStep` - Computed column generation
- `FilterStep` - Row filtering with predicates
- `DropStep` - Column removal
- `CleansingStep` - Registry-based data cleansing
- `GoldProjectionStep` - Column projection + Gold schema validation

**Validation Steps (`validation/schema_steps.py`):**
- `BronzeSchemaValidationStep` - DataFrame-level validation for Bronze schema
- `GoldSchemaValidationStep` - Gold-layer schema validation

**Usage Example:**
```python
from work_data_hub.infrastructure.transforms.base import Pipeline
from work_data_hub.infrastructure.transforms.standard_steps import (
    MappingStep, ReplacementStep, DropStep
)

pipeline = Pipeline(steps=[
    MappingStep(column_mapping={"old_name": "new_name"}),
    ReplacementStep(column="status", replacements={"A": "Active"}),
    DropStep(columns=["temp_col"]),
])

result_df = pipeline.execute(input_df, context)
```

### 2. Cleansing Registry (`cleansing/`)

Centralized cleansing rule management with YAML configuration.

**Key Features:**
- Singleton registry pattern
- Domain-specific rule configuration
- Hot-reload support for rule changes
- Pydantic integration via adapter

**Configuration Example (`cleansing_rules.yml`):**
```yaml
domains:
  annuity_performance:
    - rule: strip_whitespace
      columns: ["客户名称", "计划代码"]
    - rule: normalize_numeric
      columns: ["期初资产规模", "期末资产规模"]
```

### 3. Company ID Resolver (`enrichment/`)

Batch resolution of company identifiers with hierarchical strategy.

**Resolution Priority:**
1. Plan code override mapping
2. Existing company_id column
3. Enrichment service lookup (optional)
4. Temporary ID generation

**Usage:**
```python
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolver, ResolutionStrategy
)

resolver = CompanyIdResolver(
    enrichment_service=None,
    plan_override_mapping={"PLAN001": "COMP001"}
)

strategy = ResolutionStrategy(
    plan_code_column="计划代码",
    customer_name_column="客户名称",
    output_column="company_id"
)

result = resolver.resolve_batch(df, strategy)
```

### 4. Validation Utilities (`validation/`)

Standardized error handling and reporting for schema validation.

**Key Functions:**
- `handle_validation_errors()` - Process Pandera validation errors
- `collect_error_details()` - Extract structured error information
- `ValidationErrorDetail` - Typed error representation

## Clean Architecture Compliance

### Import Rules (TID251 Enforcement)

| Layer | Can Import | Cannot Import |
|-------|------------|---------------|
| `infrastructure/` | stdlib, pandas, pydantic | io/, orchestration/ |
| `domain/` | infrastructure/, stdlib | io/, orchestration/ |

### Dependency Injection Pattern

Infrastructure components are injected into domain services:

```python
# Domain service receives infrastructure components
def process_annuity_performance(
    month: str,
    file_discovery: FileDiscoveryProtocol,  # Injected
    warehouse_loader: WarehouseLoaderProtocol,  # Injected
    enrichment_service: Optional[EnrichmentProtocol] = None,
) -> DomainPipelineResult:
    ...
```

## Performance Characteristics

| Metric | Target | Achieved |
|--------|--------|----------|
| 1000 rows processing | <3s | ~1.5s |
| Memory usage (1K rows) | <200MB | ~150MB |
| Code lines (domain) | <1,100 | ~1,100 |

## Migration Guide for New Domains (6-File Standard)

Follow the standard 6-file domain structure:

1. **`__init__.py`** - Module exports
2. **`service.py`** - Lightweight orchestration (<200 lines)
3. **`models.py`** - Pydantic models for input/output (<400 lines)
4. **`schemas.py`** - Pandera schemas only (<250 lines)
5. **`constants.py`** - Business constants (~200 lines)
6. **`pipeline_builder.py`** - Pipeline assembly using infra steps (<150 lines)
7. **`helpers.py`** - Domain-specific helpers (<150 lines)

See `src/work_data_hub/domain/annuity_performance/` as the reference implementation.

## Related Documentation

- [Architectural Decisions](./architectural-decisions.md) - AD-010
- [Implementation Patterns](./implementation-patterns.md)
- [Domain: Annuity Performance](../domains/annuity_performance.md)
