# Data Models Documentation

**Project:** WorkDataHub Data Platform
**Generated:** 2025-12-03
**Scan Level:** Exhaustive

---

## Overview

This document describes the data architecture of WorkDataHub, a data engineering platform built on Dagster for processing and managing financial performance data. The system follows a **Bronze-Silver-Gold** layered data architecture with strict validation at each layer.

---

## Database Schema (PostgreSQL)

### Core Framework Tables

#### `pipeline_executions`
**Purpose:** Tracks execution metadata for all data pipelines

| Column | Type | Description |
|--------|------|-------------|
| `execution_id` | UUID (PK) | Unique execution identifier |
| `pipeline_name` | String(150) | Name of the executed pipeline |
| `status` | String(30) | Execution status (success, failed, running) |
| `started_at` | Timestamp (TZ) | Execution start time |
| `completed_at` | Timestamp (TZ) | Execution completion time (nullable) |
| `input_file` | Text | Source file path |
| `row_counts` | JSONB | Row counts by layer (bronze/silver/gold) |
| `error_details` | Text | Error stack trace (if failed) |
| `created_at` | Timestamp (TZ) | Record creation timestamp |
| `updated_at` | Timestamp (TZ) | Last update timestamp |

**Indexes:**
- `ix_pipeline_executions_pipeline_name` - Query by pipeline
- `ix_pipeline_executions_started_at` - Time-based queries

---

#### `data_quality_metrics`
**Purpose:** Stores data quality metrics for pipeline runs

| Column | Type | Description |
|--------|------|-------------|
| `metric_id` | UUID (PK) | Unique metric identifier |
| `execution_id` | UUID (FK) | References `pipeline_executions` |
| `pipeline_name` | String(150) | Pipeline name for aggregation |
| `metric_type` | String(100) | Metric type (validation_errors, null_rate, etc.) |
| `metric_value` | Numeric(20,4) | Metric value |
| `recorded_at` | Timestamp (TZ) | Metric recording time |
| `metadata` | JSONB | Additional metric metadata |

**Relationships:**
- `execution_id` → `pipeline_executions.execution_id` (CASCADE DELETE)

**Indexes:**
- `ix_data_quality_metrics_pipeline_name` - Query by pipeline
- `ix_data_quality_metrics_metric_type` - Query by metric type

---

### Domain Tables

#### `annuity_performance_new`
**Purpose:** Stores annuity performance financial metrics (Epic 4 MVP)
**Note:** Shadow table for parallel execution validation (Epic 6)

**Primary Key:** Composite `(reporting_month, plan_code, company_id)`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| **Primary Key Columns** |
| `reporting_month` | Date | NOT NULL | Report date (月度) |
| `plan_code` | String(255) | NOT NULL | Plan code identifier (计划代码) |
| `company_id` | String(50) | NOT NULL | Company ID (enriched) |
| **Business Information** |
| `business_type` | String(255) | NULL | Business type (业务类型) |
| `plan_type` | String(255) | NULL | Plan type (计划类型) |
| `plan_name` | String(255) | NULL | Plan name (计划名称) |
| **Portfolio Information** |
| `portfolio_type` | String(255) | NULL | Portfolio type (组合类型) |
| `portfolio_code` | String(255) | NULL | Portfolio code (组合代码) |
| `portfolio_name` | String(255) | NULL | Portfolio name (组合名称) |
| **Customer Information** |
| `customer_name` | String(255) | NULL | Customer name (客户名称) |
| **Financial Metrics** |
| `starting_assets` | Numeric(18,4) | >= 0 | Initial assets (期初资产规模) |
| `ending_assets` | Numeric(18,4) | >= 0 | Final assets (期末资产规模) |
| `contribution` | Numeric(18,4) | NULL | Contribution amount (供款) |
| `loss_with_benefit` | Numeric(18,4) | NULL | Loss including benefits (流失_含待遇支付) |

**Indexes:**
- `idx_reporting_month` - Time-based queries
- `idx_company_id` - Company aggregations

**Constraints:**
- `CHECK (starting_assets >= 0)` - Non-negative assets
- `CHECK (ending_assets >= 0)` - Non-negative assets

---

## Pydantic Data Models

### Annuity Performance Domain

#### `AnnuityPerformanceIn` (Bronze Layer)
**Purpose:** Raw input validation after file reading

**Layer:** Bronze (post-read validation)
**Validation:** Basic type coercion, required fields

Key Fields:
- All raw columns from Excel source
- Customer name (raw, before cleansing)
- Date fields (flexible parsing with Chinese date support)
- Numeric fields (coerced from various formats)

#### `AnnuityPerformanceOut` (Gold Layer)
**Purpose:** Final validated output ready for database loading

**Layer:** Gold (pre-database validation)
**Validation:** Pandera schema enforcement, business rules

Key Fields:
- Composite key: `(reporting_month, plan_code, company_id)`
- Enriched `company_id` (from enrichment service)
- Cleansed `customer_name`
- Validated financial metrics with CHECK constraints
- Calculated fields (if any)

---

### Trustee Performance Domain

#### `TrusteePerformanceIn` (Bronze Layer)
**Purpose:** Sample domain for testing standard pattern

#### `TrusteePerformanceOut` (Gold Layer)
**Purpose:** Gold layer output for trustee performance

**Note:** Sample domain used for validating standard domain pattern (Story 1.12)

---

### Enrichment Models

#### `EnrichmentStats`
**Purpose:** Tracks company ID enrichment statistics

Fields:
- `total_rows` - Total processed
- `enriched_count` - Successfully enriched
- `failed_count` - Enrichment failures
- `cache_hits` - Mapping cache hits
- `api_calls` - External API calls made

#### `ProcessingResultWithEnrichment`
**Purpose:** Pipeline processing result with enrichment metadata

Fields:
- `success` - Boolean success flag
- `dataframe` - Processed DataFrame
- `enrichment_stats` - EnrichmentStats instance
- `errors` - List of validation errors

---

## Data Flow Architecture

```
┌─────────────────┐
│  Excel Source   │
│  Files (.xlsx)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│             BRONZE LAYER (Raw Ingestion)            │
│  - Column normalization                             │
│  - Type coercion                                    │
│  - AnnuityPerformanceIn validation (Pydantic)       │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│           SILVER LAYER (Business Logic)             │
│  - Customer name cleansing                          │
│  - Company ID enrichment                            │
│  - Date parsing (Chinese + ISO formats)             │
│  - Field mapping and transformations                │
│  - Cleansing registry application                   │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│             GOLD LAYER (Analytics Ready)            │
│  - AnnuityPerformanceOut validation (Pandera)       │
│  - Business rule enforcement                        │
│  - Data quality metrics collection                  │
│  - CHECK constraint validation (pre-load)           │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│            DATABASE (PostgreSQL)                     │
│  - annuity_performance_new table                    │
│  - pipeline_executions tracking                     │
│  - data_quality_metrics recording                   │
└─────────────────────────────────────────────────────┘
```

---

## Data Quality Framework

### Validation Layers

**Bronze → Silver:**
- Pydantic models for type safety
- Flexible type coercion
- Required field validation

**Silver → Gold:**
- Pandera DataFrame schemas
- Business rule validation
- Cross-field consistency checks
- Domain-specific constraints

**Gold → Database:**
- SQL CHECK constraints
- Foreign key integrity
- Unique constraints on composite keys

### Error Handling

All validation errors are captured and stored in:
- `pipeline_executions.error_details` - Execution-level errors
- `data_quality_metrics` - Validation metric tracking
- Structured log files (if enabled)

---

## Key Design Patterns

### 1. Bronze-Silver-Gold Architecture
- **Bronze:** Raw data with minimal validation
- **Silver:** Business logic applied, cleansed data
- **Gold:** Analytics-ready, validated for consumption

### 2. Dual Validation Strategy
- **Pydantic:** Row-level validation (Bronze)
- **Pandera:** DataFrame-level validation (Gold)

### 3. Cleansing Registry
- Centralized rule definitions
- Domain-specific and global rules
- Extensible rule engine

### 4. Company Enrichment Service
- Mapping-first approach (fast path)
- External API fallback (EQC integration)
- Async queue for deferred lookups

### 5. Shadow Table Strategy
- Parallel execution validation (Epic 6)
- Zero-downtime cutover
- Parity validation before production

---

## Migration Strategy

Database migrations are managed via **Alembic** in `io/schema/migrations/versions/`.

Current migrations:
- `20251113_000001` - Core framework tables
- `20251129_000001` - Annuity performance shadow table

**Migration Pattern:**
1. Idempotent migrations (check table existence)
2. Down revision chain for rollback
3. Comments on all columns (Chinese + English)
4. Indexes for performance-critical queries

---

## Related Documentation

- [Architecture Documentation](./architecture.md) - System architecture
- [Developer Guide](./developer-guide.md) - Setup and workflows
- [Database Migrations Guide](./database-migrations.md) - Migration procedures
- [Domains: Annuity Performance](./domains/annuity_performance.md) - Domain details

---

**Document Status:** ✅ Complete
**Last Updated:** 2025-12-03
**Maintained By:** Development Team
