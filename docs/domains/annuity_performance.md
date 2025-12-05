# Annuity Performance Domain

> **Epic 5 Refactored** - Reference implementation for Epic 9 domain migrations

## Overview

The Annuity Performance domain processes monthly annuity performance data from Excel files into a validated PostgreSQL table. This is the first domain migrated under the WorkDataHub platform and serves as the **reference implementation** for all future domain migrations (Epic 9).

**Post-Epic 5 Architecture:** The domain has been refactored to use the new infrastructure layer, reducing domain code from ~3,446 lines to ~900 lines while improving performance and maintainability.

| Attribute | Value |
|-----------|-------|
| **Domain Name** | `annuity_performance` |
| **Data Source** | Excel files from `收集数据/数据采集` folder |
| **Sheet Name** | `规模明细` |
| **Output Table** | `annuity_performance_NEW` |
| **Primary Key** | `(月度, 计划代码, company_id)` |

## Architecture (Post-Epic 5)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Orchestration Layer                                  │
│                    (Dagster jobs, CLI, scheduling)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              I/O Layer                                       │
│              (FileDiscoveryService, WarehouseLoader)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Infrastructure Layer                                  │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│    │ transforms/ │  │ cleansing/  │  │ enrichment/ │  │ validation/ │      │
│    │  Pipeline   │  │  Registry   │  │ CompanyId   │  │   Error     │      │
│    │   Steps     │  │   Rules     │  │  Resolver   │  │  Handler    │      │
│    └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Domain Layer                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    annuity_performance/                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ service.py  │  │ pipeline_   │  │  models.py  │  │ schemas.py  │  │   │
│  │  │ (~160 lines)│  │ builder.py  │  │  (Pydantic) │  │ (Pandera)   │  │   │
│  │  │ Orchestrator│  │ (~135 lines)│  │  (~340 lines│  │ (~210 lines)│  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │   │
│  │  │constants.py │  │ helpers.py  │  │ __init__.py │                   │   │
│  │  │ (~95 lines) │  │ (~130 lines)│  │ (~35 lines) │                   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Excel File → FileDiscoveryService → Bronze Validation → Pipeline Execution → Gold Validation → WarehouseLoader
     │              │                      │                    │                   │              │
     │              ▼                      ▼                    ▼                   ▼              ▼
     │        discover_and_load()    BronzeSchema         MappingStep          GoldSchema    load_dataframe()
     │                                (Pandera)          CleansingStep         (Pandera)
     │                                                   CompanyIdStep
     └─────────────────────────────────────────────────────────────────────────────────────────────┘
                                    process_annuity_performance()
```

## Input Format

### File Location

Files are discovered using the Epic 3 file discovery system with version-aware folder scanning:

```
tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集/V{n}/*年金终稿*.xlsx
```

**Example paths:**
- `reference/monthly/202411/收集数据/数据采集/V1/24年11月年金终稿数据.xlsx`
- `reference/monthly/202501/收集数据/数据采集/V2/25年1月年金终稿数据.xlsx`

### Excel Structure

| Column (Chinese) | Column (English) | Type | Description |
|------------------|------------------|------|-------------|
| 月度 | reporting_month | Date | Report period (YYYYMM format) |
| 计划代码 | plan_code | String | Plan identifier (part of PK) |
| 业务类型 | business_type | String | Business type classification |
| 计划类型 | plan_type | String | Plan type classification |
| 计划名称 | plan_name | String | Plan name |
| 组合类型 | portfolio_type | String | Portfolio type |
| 组合代码 | portfolio_code | String | Portfolio code |
| 组合名称 | portfolio_name | String | Portfolio name |
| 客户名称 | customer_name | String | Customer/company name |
| 期初资产规模 | starting_assets | Decimal | Initial asset scale |
| 期末资产规模 | ending_assets | Decimal | Final asset scale |
| 供款 | contribution | Decimal | Contribution amount |
| 流失(含待遇支付) | loss_with_benefit | Decimal | Loss including benefit payment |
| 流失 | loss | Decimal | Loss amount |
| 待遇支付 | benefit_payment | Decimal | Benefit payment |
| 投资收益 | investment_return | Decimal | Investment return |
| 当期收益率 | annualized_return_rate | Decimal | Annualized return rate |
| 机构代码 | institution_code | String | Institution code |
| 机构名称 | institution_name | String | Institution name |
| 产品线代码 | product_line_code | String | Product line code |
| 年金账户号 | pension_account_number | String | Pension account number |
| 年金账户名 | pension_account_name | String | Pension account name |
| 子企业号 | sub_enterprise_number | String | Sub-enterprise number |
| 子企业名称 | sub_enterprise_name | String | Sub-enterprise name |
| 集团企业客户号 | group_customer_number | String | Group customer number |
| 集团企业客户名称 | group_customer_name | String | Group customer name |

### Sheet Name

The data is located in the **`规模明细`** sheet within the Excel file.

## Transformation Steps

### Step 1: Bronze Layer Validation (Story 4.2)

**Model:** `AnnuityPerformanceIn`

- Loose validation with `Optional[Union[...]]` types
- Accepts messy Excel data formats
- Handles Chinese column names
- Cleans numeric fields (removes commas, currency symbols)
- Preprocesses date fields (converts integer YYYYMM to string)

**Key validations:**
- Column name mapping (Chinese → internal)
- Basic type coercion
- Null value standardization
- **Infrastructure Component:** `BronzeSchemaValidationStep` (in `infrastructure/validation/schema_steps.py`)

### Step 2: Silver Layer Transformation (Story 4.3)

**Cleansing operations:**

1. **Date Parsing** (Story 2.4)
   - Converts `202411` → `date(2024, 11, 1)`
   - Handles Chinese dates: `"2024年11月"` → `date(2024, 11, 1)`
   - Validates date range: 2000-2030

2. **Company Name Cleansing** (Story 2.3)
   - Trims whitespace
   - Normalizes company names
   - Applies domain-specific rules from CleansingRegistry

3. **Numeric Cleaning**
   - Removes currency symbols (¥, $)
   - Handles comma-separated numbers (1,234.56)
   - Converts percentages (5.5% → 0.055)
   - Standardizes null values

4. **Company ID Enrichment** (Epic 5 - stub for MVP)
   - Generates temporary company IDs using HMAC
   - Full enrichment via EQC API in Epic 5

### Step 3: Gold Layer Projection (Story 4.4)

**Model:** `AnnuityPerformanceOut`

- Strict validation with required fields
- Non-negative constraints on asset values
- Business rule validation:
  - Report date cannot be in the future
  - Warns if date is older than 10 years
- Field normalization (uppercase codes, trimmed strings)
- **Infrastructure Component:** `GoldProjectionStep` (in `infrastructure/transforms/projection_step.py`)

**Output fields match database schema exactly.**

## Output Schema

### Database Table: `annuity_performance_new`

```sql
CREATE TABLE annuity_performance_new (
    -- Primary Key (Composite)
    reporting_month DATE NOT NULL,
    plan_code VARCHAR(255) NOT NULL,
    company_id VARCHAR(50) NOT NULL,

    -- Business Information
    business_type VARCHAR(255),
    plan_type VARCHAR(255),
    plan_name VARCHAR(255),
    portfolio_type VARCHAR(255),
    portfolio_code VARCHAR(255),
    portfolio_name VARCHAR(255),
    customer_name VARCHAR(255),

    -- Financial Metrics
    starting_assets NUMERIC(18,4) CHECK (starting_assets >= 0),
    ending_assets NUMERIC(18,4) CHECK (ending_assets >= 0),
    contribution NUMERIC(18,4),
    loss_with_benefit NUMERIC(18,4),
    loss NUMERIC(18,4),
    benefit_payment NUMERIC(18,4),
    investment_return NUMERIC(18,4),
    annualized_return_rate NUMERIC(10,6),

    -- Organizational Information
    institution_code VARCHAR(255),
    institution_name VARCHAR(255),
    product_line_code VARCHAR(255),
    pension_account_number VARCHAR(50),
    pension_account_name VARCHAR(255),

    -- Enterprise Group Information
    sub_enterprise_number VARCHAR(50),
    sub_enterprise_name VARCHAR(255),
    group_customer_number VARCHAR(50),
    group_customer_name VARCHAR(255),

    -- Audit Columns
    pipeline_run_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    PRIMARY KEY (reporting_month, plan_code, company_id)
);

-- Indexes
CREATE INDEX idx_annuity_perf_new_reporting_month ON annuity_performance_new(reporting_month);
CREATE INDEX idx_annuity_perf_new_company_id ON annuity_performance_new(company_id);
CREATE INDEX idx_annuity_perf_new_pipeline_run ON annuity_performance_new(pipeline_run_id);
```

### Shadow Table Strategy

The `annuity_performance_new` table is a **shadow table** for Epic 6 parallel execution:

1. New pipeline writes to `annuity_performance_new`
2. Legacy system writes to `annuity_performance` (existing)
3. Epic 6 compares outputs for 100% parity validation
4. After parity proven, cutover: rename `_new` to production table

## Configuration

### Data Source Configuration

**File:** `config/data_sources.yml`

```yaml
domains:
  annuity_performance:
    # Base path with template variable {YYYYMM}
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"

    # File patterns to match (glob syntax)
    file_patterns:
      - "*年金终稿*.xlsx"

    # Patterns to exclude
    exclude_patterns:
      - "~$*"         # Excel temp files
      - "*回复*"      # Email reply files
      - "*.eml"       # Email message files

    # Excel sheet name
    sheet_name: "规模明细"

    # Version selection: V3 > V2 > V1
    version_strategy: "highest_number"

    # Fail on ambiguous version detection
    fallback: "error"
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `WDH_ALIAS_SALT` | HMAC salt for temporary company ID generation | Yes |

### Configuration Validation

Configuration is validated at startup using Epic 3 Story 3.0 schema:

```python
from src.work_data_hub.config.schema import validate_data_sources_config_v2

# Validates structure, types, and security constraints
validate_data_sources_config_v2('config/data_sources.yml')
```

## Related Stories

| Story | Description | Status |
|-------|-------------|--------|
| 4.1 | Annuity Domain Data Models (Pydantic) | Done |
| 4.2 | Annuity Bronze Layer Validation Schema | Done |
| 4.3 | Annuity Transformation Pipeline (Bronze → Silver) | Done |
| 4.4 | Annuity Gold Layer Projection and Schema | Done |
| 4.5 | Annuity End-to-End Pipeline Integration | Done |
| 4.6 | Annuity Domain Configuration and Documentation | Current |

## Code References (Post-Epic 5 Cleanup)

| Component | Path | Lines |
|-----------|------|-------|
| **Service Orchestrator** | `domain/annuity_performance/service.py` | 160 |
| **Pipeline Builder** | `domain/annuity_performance/pipeline_builder.py` | 135 |
| **Pydantic Models** | `domain/annuity_performance/models.py` | 338 |
| **Pandera Schemas** | `domain/annuity_performance/schemas.py` | 209 |
| **Constants** | `domain/annuity_performance/constants.py` | 95 |
| **Helpers** | `domain/annuity_performance/helpers.py` | 133 |
| **Init** | `domain/annuity_performance/__init__.py` | 35 |
| **Infrastructure Steps** | `infrastructure/transforms/standard_steps.py` | (shared) |
| **Company ID Resolver** | `infrastructure/enrichment/company_id_resolver.py` | (shared) |
| **Validation Utilities** | `infrastructure/validation/error_handler.py` | (shared) |
| Data Source Config | `config/data_sources.yml` | - |

**Total Domain Lines:** ~1,105 (Target: <1,100)

### Key Infrastructure Dependencies

```python
# Service imports from infrastructure layer
from work_data_hub.infrastructure.transforms.base import Pipeline
from work_data_hub.infrastructure.transforms.standard_steps import (
    MappingStep, ReplacementStep, CleansingStep, DropStep
)
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolver, ResolutionStrategy
)
from work_data_hub.infrastructure.validation.error_handler import (
    handle_validation_errors
)
```

## Standard Domain Pattern Reference Implementation

> **6-File Standard** - Finalized structure for Epic 9

### Overview

The annuity_performance module serves as the **reference implementation** for the Standard Domain Pattern. This pattern uses:

1. **Constants over Config:** Static mappings moved to `constants.py`.
2. **Generic Steps:** `standard_steps.py` for common ops (Mapping, Replacement).
3. **Infrastructure Validation:** Reusable `schema_steps.py` and `projection_step.py`.
4. **Lean Domain Layer:** Focus on orchestration and business models.

### Code Metrics Improvement

| Metric | Pre-Cleanup (Epic 4) | Post-Cleanup (Epic 5) | Change |
|--------|----------------------|-----------------------|--------|
| Total Lines | ~3,446 | ~1,105 | -68% |
| File Count | 9 | 7 | -22% |
| Custom Steps | 8+ | 1 (PipelineBuilder) | -87% |
| Test Coverage | ~58% | >90% | +32% |

### Epic 9 Migration Guide

When migrating additional domains, follow this pattern:

1. **Create `constants.py`** with all static mappings
2. **Use generic steps** for column renaming, value replacement, calculated fields
3. **Create custom steps only** for domain-specific business logic (rare)
4. **Import from `work_data_hub.infrastructure`**:
   - `MappingStep`, `ReplacementStep`, `DropStep`, `CleansingStep`
   - `BronzeSchemaValidationStep`, `GoldSchemaValidationStep`, `GoldProjectionStep`

## Future Enhancements (Epic 9)

When migrating additional domains, use this implementation as a template:

1. Copy `config/data_sources.yml` entry structure
2. Follow database migration pattern (composite PK, indexes, constraints)
3. Create domain models following `AnnuityPerformanceIn/Out` pattern
4. **NEW:** Create `constants.py` following the Standard Domain Pattern
5. **NEW:** Use generic steps from `infrastructure/transforms/` for standard operations
6. Use documentation template from this file
7. Adapt runbook template for domain-specific errors

**Expected time savings:** Each new domain's configuration and documentation should take <2 hours instead of starting from scratch.
