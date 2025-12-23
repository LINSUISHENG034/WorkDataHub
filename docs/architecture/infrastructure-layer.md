# Infrastructure Layer Documentation

## Overview

The infrastructure layer (`src/work_data_hub/infrastructure/`) provides reusable,
domain-agnostic services that support Clean Architecture boundaries. Created as
part of Epic 5 (Stories 5.1-5.8), this layer enables rapid domain migration for
Epic 9 by centralizing common transformation, validation, and enrichment logic.

> **Epic 7 Modularization (2025-12-22):** Large files have been decomposed into
> package structures following the 800-line limit. See Module Structure below.

## Architecture Position

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                                   │
│                 (CLI: cli/etl/, scheduling)                              │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         I/O Layer                                        │
│    io/loader/        io/connectors/eqc/        io/connectors/discovery/  │
│  (DB writing)        (EQC API client)          (File discovery)          │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                                   │
│  etl/ops/     enrichment/     schema/     transforms/     validation/    │
│ (Pipeline    (Company ID    (Domain     (Transform      (Schema         │
│  execution)   resolution)    Registry)   steps)          validation)     │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Domain Layer                                        │
│        (Business logic, Models, Schemas, Services)                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

> **Updated 2025-12-22 (Epic 7):** Reflects modularized package structure.

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
├── enrichment/                  # [Epic 7 Story 7.3: Modularized]
│   ├── __init__.py              # Public API exports
│   ├── company_id_resolver.py   # Batch company ID resolution
│   ├── gateway.py               # EnrichmentGateway (5-layer orchestration)
│   ├── normalizer.py            # Company name normalization
│   ├── providers/               # Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py              # EnterpriseInfoProvider protocol
│   │   ├── yaml_provider.py     # Layer 1: YAML config
│   │   ├── db_cache_provider.py # Layer 2: DB cache (enrichment_index)
│   │   └── eqc_provider.py      # Layer 4: EQC API
│   ├── temp_id.py               # Layer 5: Temp ID generation (HMAC-SHA1)
│   └── types.py                 # ResolutionStrategy, ResolutionResult
├── etl/
│   └── ops/                     # [Epic 7 Story 7.1: ops.py decomposition]
│       ├── __init__.py          # Public API: run_domain_pipeline, etc.
│       ├── core.py              # Main orchestration logic
│       ├── config.py            # ETL configuration loading
│       ├── discovery.py         # File discovery integration
│       ├── enrichment.py        # Enrichment step integration
│       ├── loading.py           # Database loading step
│       ├── backfill.py          # FK backfill operations
│       ├── reference_sync.py    # Reference data sync
│       └── models.py            # ETLResult, ETLConfig dataclasses
├── schema/                      # [Epic 7 Story 7.5: Domain Registry]
│   ├── __init__.py              # Public API: DomainRegistry, get_schema
│   ├── registry.py              # DomainRegistry class
│   ├── types.py                 # ColumnType, ColumnDef, IndexDef, DomainSchema
│   ├── domains/                 # Domain-specific schema definitions
│   │   ├── __init__.py
│   │   ├── annuity_performance.py
│   │   ├── annuity_income.py
│   │   ├── annuity_plans.py
│   │   └── portfolio_plans.py
│   └── sql_generator.py         # SQL DDL generation helpers
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
    ├── domain_validators.py     # [Epic 6.2-P13] Registry-driven validation
    ├── error_handler.py         # handle_validation_errors()
    ├── report_generator.py      # Validation report generation
    ├── schema_helpers.py        # Schema utility functions
    ├── schema_steps.py          # Reusable schema validation steps
    └── types.py                 # ValidationErrorDetail, etc.
```

### I/O Layer Packages (Epic 7 Story 7.2)

```
src/work_data_hub/io/
├── loader/                      # [Story 7.2: warehouse_loader.py decomposition]
│   ├── __init__.py              # WarehouseLoader, LoadResult exports
│   ├── core.py                  # WarehouseLoader class
│   ├── operations.py            # insert_missing, fill_null_only
│   ├── insert_builder.py        # SQL INSERT statement building
│   ├── sql_utils.py             # quote_ident, quote_qualified
│   └── models.py                # LoadResult, exceptions
├── connectors/
│   ├── eqc/                     # [Story 7.2: eqc_client.py decomposition]
│   │   ├── __init__.py          # EQCClient exports
│   │   ├── core.py              # EQCClient class
│   │   ├── transport.py         # HTTP transport layer
│   │   ├── parsers.py           # Response parsing
│   │   ├── models.py            # Data models
│   │   └── utils.py             # Rate limiting
│   └── discovery/               # [Story 7.2: file_connector.py decomposition]
│       ├── __init__.py          # FileDiscoveryService exports
│       ├── service.py           # FileDiscoveryService class
│       └── models.py            # Discovery result models
└── warehouse_loader.py          # Facade (backward-compatible re-exports)
```

### CLI Layer Package (Epic 7 Story 7.4)

```
src/work_data_hub/cli/
├── __init__.py
├── etl/                         # [Story 7.4: etl.py decomposition]
│   ├── __init__.py              # CLI entry point
│   ├── commands.py              # Click command definitions
│   ├── options.py               # CLI option definitions
│   ├── handlers.py              # Command handlers
│   └── formatters.py            # Output formatting
└── etl.py                       # Facade (backward-compatible entry point)
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

Batch resolution of company identifiers with 5-layer hierarchical strategy.

> **Updated Epic 6 (2025-12-08):** Full 5-layer enrichment architecture implemented.

**Resolution Priority (5 Layers):**
1. **Layer 1: YAML Config** - `config/company_mapping.yml` hardcoded mappings
2. **Layer 2: DB Cache** - `enterprise.enrichment_index` (5 lookup types by priority)
3. **Layer 3: Existing Column** - Check if source data already has `company_id`
4. **Layer 4: EQC API** - Synchronous lookup with budget control
5. **Layer 5: Temp ID** - HMAC-SHA1 based temporary ID (INxxx format)

**Layer 2 Lookup Types (by priority):**
- `plan_code` > `account_name` > `account_number` > `customer_name` > `plan_customer`

**Usage:**
```python
from work_data_hub.infrastructure.enrichment.gateway import EnrichmentGateway
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolver, ResolutionStrategy
)

# Full 5-layer resolution via gateway
gateway = EnrichmentGateway(db_connection=conn, eqc_client=client)
company_id = gateway.resolve(customer_name="某某公司")

# Batch resolution in pipeline context
resolver = CompanyIdResolver(
    enrichment_gateway=gateway,
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
