# WorkDataHub — Developer Quickstart

A concise entry point for new contributors. This page orients you quickly and links to the single sources of truth for plan, design, and code.

## What & Why

WorkDataHub is a reliable, declarative, and testable data processing platform replacing a legacy monolithic ETL with isolated domain services, configuration‑driven discovery, and orchestrated end‑to‑end pipelines.

## Status

- Project plan and current status: see [ROADMAP.md](ROADMAP.md).

## Architecture at a Glance

- Config: environment settings and schemas; config‑driven discovery of inputs.
- IO: connectors (file), readers (Excel), and a transactional warehouse loader.
- Domain: Pydantic models + pure services (e.g., sample_trustee_performance).
- Orchestration: Dagster‑style ops and jobs (discover → read → transform → load).
- Utils: typed helpers and common types.

## Utils vs Cleansing

- `utils/`: Generic, structural utilities. Stateless, domain‑agnostic, broadly reusable, no registry/config required.
  - Examples: `utils/column_normalizer.py` (header normalization; structural), `utils/date_parser.py` (Chinese date parsing → standard `date`).
- `cleansing/`: Value‑level cleansing rules with a lightweight registry. Composable, replaceable, and measurable by category.
  - Examples: `cleansing/rules/numeric_rules.py` (null normalization, currency/thousand separators removal, percentage → decimal, ROUND_HALF_UP quantization).
- Dependencies: domain/ops/io can use both utils and cleansing; cleansing can call utils; utils must not depend on domain/cleansing (no cycles).
- Why `date_parser.py` lives in utils/: it’s a generic parser (not a switchable “rule”), needs no registry/toggles (KISS/YAGNI). If domain/scene‑specific date strategies are needed later, add rules under `cleansing/rules/` that reuse `utils.date_parser` internally.

## Workflow (High‑Level)

A structural view of the end‑to‑end pipeline from trigger to data load. This focuses on orchestration and dataflow, independent of domain‑specific rules.

```mermaid
flowchart TD
  A[Triggers\nCLI / Schedule / Sensor] --> B[Dagster Definitions\n(repository.py)]
  B --> C{Job}
  C --> D[discover_files_op\nConfig‑driven file discovery]
  D --> E{Single file?}
  E -- Yes --> F[read_excel_op\nRead rows from Excel]
  E -- No  --> G[read_and_process_files_op\nBatch read + accumulate]
  F --> H[process_op\nDomain service transformation]
  G --> H[process_op\nDomain service transformation]
  H --> I[load_op\nPlan‑only (SQL plan) or Execute]
  I --> J[Results\nPlans or transactional DB load]
  J --> K[Logging / Observability / Error handling]
```

Key characteristics

- Triggers: initiated via CLI, scheduled runs, or file‑driven sensors.
- Central registry: Dagster `Definitions` exposes jobs/schedules/sensors.
- Jobs: compose ops into a directed flow; support single or multi‑file paths.
- Discovery: configuration‑driven patterns and selection strategies determine inputs.
- Reading: resilient Excel ingestion producing normalized row records.
- Processing: domain services apply validation and transformations.
- Loading: plan-only returns SQL plans; execute mode performs transactional writes.

## Orchestration Modes (KISS/YAGNI)

- CLI‑first (current): trigger via `uv run python -m src.work_data_hub.orchestration.jobs`; use `--plan-only` for safe dry‑run and `--execute` for actual writes. No Dagster services required; jobs run in‑process.
- Simple scheduling (as needed): use system schedulers/cron to invoke the CLI for daily/hourly runs and retries (wrap in a small script).
- Dagster UI/Daemon (defer until needed): deploy only when gates are met (multi‑domain, backfill/event triggers, observability/auditing, non‑engineer UI needs). For local exploration: `uv run dagster dev -f src/work_data_hub/orchestration/repository.py`.

## Code Map (stable entry points)

- Config: `src/work_data_hub/config/settings.py`, `src/work_data_hub/config/schema.py`, `src/work_data_hub/config/data_sources.yml`
- IO — Readers/Connectors/Loader:
  - `src/work_data_hub/io/readers/excel_reader.py`
  - `src/work_data_hub/io/connectors/file_connector.py`
  - `src/work_data_hub/io/loader/warehouse_loader.py`
- Domain — Sample Trustee Performance:
  - `src/work_data_hub/domain/sample_trustee_performance/models.py`
  - `src/work_data_hub/domain/sample_trustee_performance/service.py`
- Domain — Annuity Performance:
  - `src/work_data_hub/domain/annuity_performance/models.py`
  - `src/work_data_hub/domain/annuity_performance/service.py`
- Orchestration:
  - `src/work_data_hub/orchestration/ops.py`
  - `src/work_data_hub/orchestration/jobs.py`
- Utils: `src/work_data_hub/utils/types.py`

## How to Run

Prerequisite: Install `uv` (https://docs.astral.sh/uv/).

```bash
# Setup environment
uv venv && uv sync

# Format, lint, types, tests
uv run ruff format .
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Optional coverage
uv run pytest --cov=src --cov-report=term-missing

# Focus a subset
uv run pytest -k sample_trustee_performance -v

# Optional: pre-commit hooks (only if configured)
# uv run pre-commit run --all-files
```

## Sample Domain (Trustee Performance)

The `sample_trustee_performance` domain is a normative sample used for unit/integration tests and plan-only runs. It is not a production model and does not ship a DDL. For end‑to‑end database writes, use the `annuity_performance` domain instead.

### Quick usage (plan‑only)

```bash
# Use legacy reference data if available
export WDH_DATA_BASE_DIR=./reference/monthly

# Plan-only mode (no database required)
uv run python -m src.work_data_hub.orchestration.jobs --domain sample_trustee_performance --plan-only --max-files 2

# Run tests (default excludes postgres‑backed tests)
uv run pytest tests/
```

## Real Sample Smoke (Annuity Performance)

Test the Annuity Performance (规模明细) domain using legacy sample data with both plan-only and execute modes.

⚠️ **IMPORTANT**: Execute mode modifies database state. Only use with test databases.

### Prerequisites

1. **Ensure reference data exists** (or tests will be skipped):

  ```bash
  # Reference data should be at:
  ./reference/monthly/数据采集/V1/
  ```

2. **Configure environment variables**:

  ```bash
  # Required: Override data source directory
  export WDH_DATA_BASE_DIR=./reference/monthly
  
  # Optional: Local database for execute mode
  export WDH_DATABASE__URI=postgresql://wdh_user:changeme@localhost:5432/wdh_local
  ```

3. **Setup local database** (required for execute mode):

  ```bash
  # Apply updated DDL to your local PostgreSQL database
  psql "$WDH_DATABASE__URI" -f scripts/create_table/ddl/annuity_performance.sql
  ```

### CLI Usage

```bash
# Plan-only mode (safe - no database required)
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1

# Execute mode (MODIFIES DATABASE - requires DDL applied)
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --max-files 1 \
  --mode delete_insert

# Reference Backfill (insert missing plans/portfolios before loading facts)
# Plan-only preview (no DB changes):
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1 \
  --backfill-refs all \
  --backfill-mode insert_missing

# Execute backfill then load facts (requires DB):
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --max-files 1 \
  --backfill-refs plans \
  --backfill-mode insert_missing \
  --mode delete_insert

# Note: insert_missing currently uses "ON CONFLICT DO NOTHING" per key columns. A unique
# index/constraint on the target key(s) is required to avoid errors at runtime.
# If your environment lacks such constraints, prefer plan-only to preview and consider
# adding a unique index or implementing a SELECT-filter fallback.

### Reference Backfill DB Indexes (recommended)

For the fast‑path `ON CONFLICT DO NOTHING` to work efficiently and safely, create unique
indexes on the natural keys of the reference tables. If you cannot add indexes in your
environment, the loader will automatically fall back to a SELECT‑filter strategy, but
unique indexes are still recommended for performance and concurrency safety.

```sql
-- Annuity Plan (align with production FK)
CREATE UNIQUE INDEX IF NOT EXISTS "uq_年金计划_计划代码"
  ON "年金计划" ("计划代码");

-- Portfolio Plan
CREATE UNIQUE INDEX IF NOT EXISTS "uq_组合计划_组合代码"
  ON "组合计划" ("组合代码");
```

Guidelines
- Align `refs.plans.key` with your production FK target column (often `计划代码`).
- Prefer dual‑fill identifiers in candidates (e.g., set both `年金计划号` and `计划代码` to the same value) to support heterogeneous environments.
- Always run a plan‑only backfill first to preview SQL and candidate counts.
- Apply the indexes on test/staging first; verify backfill executes without constraint errors.
- If unique indexes cannot be added, rely on the built‑in fallback (SELECT‑filter) and monitor logs.

### Reference Configuration (Schema, Table, Key Management)

The reference backfill system uses configuration‑driven schema and table management via `data_sources.yml`. Each domain can specify schema qualification, table names, primary keys, and updatable columns for plans and portfolios.

#### Configuration Structure

```yaml
annuity_performance:
  # Fact table configuration
  table: "规模明细"
  pk: ["月度", "计划代码", "company_id"]

  # Reference table configuration
  refs:
    plans:
      schema: public                    # Optional: schema qualification
      table: "年金计划"                # Required: target table name
      key: ["年金计划号"]           # Required: primary key columns
      updatable: [                      # Required: columns that can be updated
        "计划全称",
        "计划类型",
        "客户名称",
        "company_id",
        "主拓代码",
        "主拓机构",
        "备注",
        "资格"
      ]
    portfolios:
      schema: public
      table: "组合计划"
      key: ["组合代码"]
      updatable: ["组合名称", "组合类型", "运作开始日"]
```

#### Schema Qualification Benefits

- **Qualified SQL Generation**: When schema is specified, the warehouse loader generates qualified SQL: `INSERT INTO "public"."年金计划" (...)`
- **Multi‑Schema Support**: Different reference tables can live in different schemas
- **Environment Isolation**: Development/staging can use different schemas than production

#### Usage Examples

```bash
# Schema‑qualified backfill (uses configuration schema)
uv run python ‑m src.work_data_hub.orchestration.jobs \
  ‑‑domain annuity_performance \
  ‑‑execute \
  ‑‑backfill‑refs all \
  ‑‑backfill‑mode insert_missing

# Plan‑only preview shows qualified table names
uv run python ‑m src.work_data_hub.orchestration.jobs \
  ‑‑domain annuity_performance \
  ‑‑plan‑only \
  ‑‑backfill‑refs plans
```

### Enhanced Plan Derivation Logic

The reference backfill system includes sophisticated business logic for deriving annuity plan references from fact data. This enhanced derivation handles tie‑breaking, aggregation, and formatting according to specific business requirements.

#### Business Rules Applied

1. **客户名称 (Client Name)**:
   - Most frequent value across all rows for the plan
   - Tie‑breaking: Select value from row with maximum 期末资产规模 (End Asset Scale)
   - Deterministic and reproducible results

2. **主拓代码, 主拓机构 (Primary Extension Code/Organization)**:
   - Values taken from the single row with maximum 期末资产规模
   - Ensures consistency between related fields

3. **备注 (Remarks)**:
   - Formatted as `YYMM_新建` from the 月度 (Monthly) field
   - Handles various date input formats: YYYYMM integers, date strings, datetime objects
   - Graceful degradation for invalid dates

4. **资格 (Qualifications)**:
   - Filtered business types in specific predefined order
   - Allowed types: `企年受托`, `年`, `企年投资`, `职年受托`, `职年投资`
   - Joined with '+' separator: `企年受托+年+职年投资`
   - Invalid business types are filtered out

#### Implementation Features

- **Deterministic Tie‑Breaking**: Uses stable sorting and first‑occurrence selection
- **Robust Date Parsing**: Handles multiple date formats with comprehensive error handling
- **Edge Case Handling**: Gracefully processes null values, empty inputs, and invalid data
- **Numeric Safety**: Safe conversion of asset scale values with fallback handling

#### Example Enhanced Derivation

```python
# Input: Multiple rows for plan PLAN001 with different client names and asset scales
input_rows = [
    {"계획코드": "PLAN001", "고객명": "Client A", "기말자산규모": 2000000, "业务类型": "기업연수탁"},
    {"계획코드": "PLAN001", "고객명": "Client A", "기말자산규모": 1000000, "업무유형": "연"},
    {"계획코드": "PLAN001", "고객명": "Client B", "기말자산규모": 1500000, "업무유형": "직업연투자"},
]

# Output: Single plan candidate with enhanced derivation
candidate = {
    "연금계획번호": "PLAN001",
    "고객명": "Client A",           # Most frequent, won tie‑break with max asset scale
    "주획코드": "AGENT001",        # From row with max asset scale (2M)
    "주획기관": "BRANCH001",       # From row with max asset scale (2M)
    "비고": "2411_신규",             # Formatted from 월도 202411
    "자격": "기업연수탁+연+직업연투자",  # Ordered business types
}
```

### Skip‑Facts Mode (Backfill‑Only Execution)

The skip‑facts mode enables running reference backfill operations without loading fact data. This is useful for:

- Populating reference tables before fact loading
- Testing reference derivation logic independently
- Incremental reference updates without fact processing
- Development and validation workflows

#### Usage Examples

```bash
# Skip facts: Only run reference backfill, no fact loading
uv run python ‑m src.work_data_hub.orchestration.jobs \
  ‑‑domain annuity_performance \
  ‑‑execute \
  ‑‑backfill‑refs all \
  ‑‑skip‑facts \
  ‑‑max‑files 1

# Plan‑only skip‑facts: Preview backfill operations only
uv run python ‑m src.work_data_hub.orchestration.jobs \
  ‑‑domain annuity_performance \
  ‑‑plan‑only \
  ‑‑backfill‑refs plans \
  ‑‑skip‑facts

# Skip facts with specific sheet and debug logging
uv run python ‑m src.work_data_hub.orchestration.jobs \
  ‑‑domain annuity_performance \
  ‑‑execute \
  ‑‑backfill‑refs all \
  ‑‑backfill‑mode insert_missing \
  ‑‑skip‑facts \
  ‑‑sheet "规模明细" \
  ‑‑debug
```

#### Expected Output

When using skip‑facts mode, you'll see:

1. **Job Summary**: `Skip facts: True` in the initial job parameters
2. **Reference Backfill Summary**: Shows plan and portfolio operations executed
3. **Fact Loading Summary**: Shows 0 deleted, 0 inserted, 0 batches (skipped)
4. **Debug Logs**: "Fact loading skipped due to ‑‑skip‑facts flag" message

```bash
🚀 Starting annuity_performance job...
   Skip facts: True
   Backfill refs: all
==================================================
📥 Reference Backfill Summary:
   Plan‑only: False
   연금계획: inserted=5
   조합계획: inserted=12

📊 Execution Summary:
   Table: 스케일디테일
   Mode: delete_insert
   Deleted: 0 rows      # Facts were skipped
   Inserted: 0 rows     # Facts were skipped
   Batches: 0
```

#### Integration with Other Features

- **Compatible with all backfill modes**: `insert_missing`, `fill_null_only`
- **Works with schema qualification**: Qualified SQL generated for reference tables
- **Supports enhanced derivations**: All sophisticated business rules applied
- **Plan‑only compatible**: Can preview skip‑facts execution without database changes

# Override composite key (runtime) for delete_insert mode
# Use comma/semicolon separated list (e.g., 月度,计划代码,company_id — Chinese column names)
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --mode delete_insert \
  --pk "月度,计划代码,company_id" \
  --max-files 1

# Temporarily disable overwrite behavior (append mode)
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --mode append \
  --max-files 1

# With specific sheet name (optional - configured in data_sources.yml)
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --sheet "规模明细" \  # sheet name in Chinese: "Scale Details"
  --max-files 1
```

### Test Usage

```bash
# Run legacy data smoke tests (opt-in via marker)
uv run pytest -m legacy_data -v -k annuity_performance

# Run E2E integration tests
uv run pytest -m legacy_data -v -k annuity_performance_e2e

# Skip legacy data tests by default (normal test runs)  
uv run pytest tests/

# Run with environment override
WDH_DATA_BASE_DIR=./reference/monthly uv run pytest -m legacy_data -v
```

### Generate Small Test Datasets (from real sample)

To speed up overwrite/append tests with realistic data, generate small subsets from the large sample Excel:

```bash
uv run python -m scripts.testdata.make_annuity_subsets \
  --src tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx \
  --sheet 规模明细  # sheet name in Chinese: "Scale Details"

# Output files (sheet name: "规模明细") under tests/fixtures/sample_data/annuity_subsets/:
#   - 2024年11月年金终稿数据_subset_distinct_5.xlsx
#   - 2024年11月年金终稿数据_subset_overlap_pk_6.xlsx
#   - 2024年11月年金终稿数据_subset_append_3.xlsx
```

### DDL Management (Single Source of Truth)

- Source: `reference/db_migration/db_structure.json` — describes physical columns from legacy; generator applies our conventions.
- Manifest: `scripts/create_table/manifest.yml` — maps domain → table/entity/delete_scope_key/ddl path.
- Generator: `scripts/create_table/generate_from_json.py` — produces normalized, idempotent PostgreSQL DDL.
- Apply: `scripts/create_table/apply_sql.py` — applies DDL using `.env` (or `--dsn`).

#### Database Conventions Applied

- **Primary Key**: Uses `{entity}_id` as auto-increment identity column (e.g., `annuity_plans_id`, `portfolio_plans_id`)
- **Legacy ID Field**: Original `id` fields from source JSON are excluded to follow project naming conventions
- **Audit Fields**: `created_at`, `updated_at` timestamps with auto-update triggers
- **Delete Scope Keys**: Non-unique composite indexes for efficient deletion operations
- **Data Types**: MySQL types mapped to PostgreSQL equivalents (TINYINT → SMALLINT, etc.)

Commands

```bash
# Generate DDL for annuity_performance from JSON + manifest
uv run python -m scripts.create_table.generate_from_json --domain annuity_performance

# Apply by domain (recommended)
uv run python -m scripts.create_table.apply_sql --domain annuity_performance

# Or apply a specific file
uv run python -m scripts.create_table.apply_sql --sql scripts/create_table/ddl/annuity_performance.sql

# List supported domains
uv run python -m scripts.create_table.apply_sql --list
```

### Expected Results

- **Plan-only**: Shows SQL execution plans with DELETE + INSERT operations targeting `"规模明细"` table
- **Execute**: Shows loader summary with deleted/inserted/batches counts from actual database operations  
- **Primary Key**: Uses `annuity_performance_id` as auto-increment primary key; delete scope key uses (`月度`, `计划代码`, `company_id`) and is non-unique
- **Column projection**: Prevents SQL column-not-found errors by filtering Excel data to valid database columns
- **Unicode handling**: Properly processes Chinese column names, table names, and file names

### Safety Guidelines

- Always use `--plan-only` first to validate SQL plans before executing
- Use `--max-files 1` for initial testing to limit scope
- Apply updated DDL (`scripts/create_table/ddl/annuity_performance.sql`) before execute mode
- Verify database configuration with test data, not production
- Monitor logs for column projection warnings and transformation errors

## Try It (End‑to‑End)

Run the existing tests for the first vertical slice (sample trustee performance):

```bash
uv run pytest tests/e2e/test_trustee_performance_e2e.py -v
```

## Docs Index

- Migration reference: `docs/plan/MIGRATION_REFERENCE.md`
- Legacy inventory: `docs/plan/R-015_LEGACY_INVENTORY.md`
- PRPs (Product Requirements Prompts): `PRPs/`
- PRP workflow: `AGENTS.md`
- Dagster docs: https://docs.dagster.io/
- Legacy analyses (superseded, for history):
  - `docs/project/01_architecture_analysis_report.md`
  - `docs/implement/01_implementation_plan.md`
  - `docs/project/02_production_data_sample_analysis.md`
  - `docs/project/03_specified_data_source_problems_analysis.md`
  - `docs/project/04_dependency_and_priority_analysis.md`

## Python Imports & Packaging

Follow these conventions to keep imports clean and tools happy:

- Use absolute imports that start from the `work_data_hub` package.
- Do not add `src` to import paths (keep `src/` as the project root for code, not a package prefix).
- When a tool requires the package to be installed (e.g., IDE/type-checking scenarios), use an editable install:
  - `pip install -e .` (or `uv pip install -e .`) so Python can resolve `work_data_hub`.

## Database Design Standards

### Entity-Specific Primary Keys

Following CLAUDE.md guidelines, all database tables use entity-specific primary keys for consistency and clarity:

```sql
-- ✅ STANDARDIZED: Entity-specific primary keys
"annuity_performance_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
"trustee_performance_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

### ETL-Specific Design Pattern

For ETL pipelines using `delete_insert` mode, we employ a hybrid approach:

1. **Technical Primary Key**: Auto-increment surrogate key (`{entity}_id`) for database performance
2. **Delete Scope Key (non-unique)**: Composite key on business fields used to determine deletion scope prior to insert; DB does not enforce uniqueness because production data may contain multiple rows per scope.

```sql
CREATE TABLE "规模明细" (
  "annuity_performance_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  
  -- Business fields
  "月度"                      DATE NOT NULL,
  "计划代码"                    VARCHAR(255) NOT NULL,
  "company_id"              VARCHAR(50) NOT NULL,
  
  -- Other fields...
);

-- Indexes to support delete scope filtering and common queries
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_计划代码_company_id"
  ON "规模明细" ("月度", "计划代码", "company_id");
```

### Column Naming Conventions

- **Primary keys**: `{entity}_id` (e.g., `annuity_performance_id`)
- **Foreign keys**: `{referenced_entity}_id`
- **Timestamps**: `{action}_at` (e.g., `created_at`, `updated_at`)
- **Chinese business columns**: Standardized via `column_normalizer.py`
- **Special characters**: Parentheses are normalized to underscores (e.g., `流失(含待遇支付)` → `流失_含待遇支付`)

## Test Markers

Markers configured in `pyproject.toml` to selectively run tests:

- `postgres`: Requires a PostgreSQL database; excluded by default in CI. Run with `-m postgres`.
- `monthly_data`: Requires `reference/monthly` sample data; opt-in. Run with `-m monthly_data`.
- `legacy_data`: Legacy E2E validations on sample data; opt-in. Run with `-m legacy_data`.
- `sample_domain`: Tests for the non‑production sample domain (`sample_trustee_performance`). Run with `-m sample_domain`.

Examples

```bash
# Default (CI-equivalent): exclude postgres-backed tests
uv run pytest -v -m "not postgres"

# Only sample domain tests
uv run pytest -v -m sample_domain

# Legacy annuity E2E validations (opt-in)
uv run pytest -v -m legacy_data -k annuity_performance_e2e

# Monthly smoke validations (opt-in)
uv run pytest -v -m monthly_data
```

### ETL Configuration

In `data_sources.yml`, specify the business composite key for delete_insert operations:

```yaml
annuity_performance:
  table: "规模明细"
  pk: ["月度", "计划代码", "company_id"]  # Business composite key for delete_insert
```

### Warehouse Loader Integration

The `warehouse_loader.py` automatically excludes auto-generated columns during INSERT operations:

```python
# Auto-generated columns are automatically excluded from INSERT statements
auto_generated_columns = {"id", "annuity_performance_id", "trustee_performance_id"}
```

This design provides:
- ✅ Database performance with surrogate keys
- ✅ ETL compatibility with business keys
- ✅ Data integrity through unique constraints
- ✅ Consistent naming following CLAUDE.md standards

## Source of Truth & Maintenance

- Plan and status live in `ROADMAP.md`.
- This quickstart stays minimal; update only when stable entry points or commands change.
- Changes that affect stable facts should include a README update in the DoD.
- Last reviewed: 2025‑09‑08.
