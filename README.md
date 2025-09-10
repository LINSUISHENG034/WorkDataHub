# WorkDataHub — Developer Quickstart

A concise entry point for new contributors. This page orients you quickly and links to the single sources of truth for plan, design, and code.

## What & Why

WorkDataHub is a reliable, declarative, and testable data processing platform replacing a legacy monolithic ETL with isolated domain services, configuration‑driven discovery, and orchestrated end‑to‑end pipelines.

## Status

- Project plan and current status: see [ROADMAP.md](ROADMAP.md).

## Architecture at a Glance

- Config: environment settings and schemas; config‑driven discovery of inputs.
- IO: connectors (file), readers (Excel), and a transactional warehouse loader.
- Domain: Pydantic models + pure services (e.g., trustee_performance).
- Orchestration: Dagster‑style ops and jobs (discover → read → transform → load).
- Utils: typed helpers and common types.

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
- Loading: plan‑only returns SQL plans; execute mode performs transactional writes.

## Code Map (stable entry points)

- Config: `src/work_data_hub/config/settings.py`, `src/work_data_hub/config/schema.py`, `src/work_data_hub/config/data_sources.yml`
- IO — Readers/Connectors/Loader:
  - `src/work_data_hub/io/readers/excel_reader.py`
  - `src/work_data_hub/io/connectors/file_connector.py`
  - `src/work_data_hub/io/loader/warehouse_loader.py`
- Domain — Trustee Performance:
  - `src/work_data_hub/domain/trustee_performance/models.py`
  - `src/work_data_hub/domain/trustee_performance/service.py`
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
uv run pytest -k trustee_performance -v

# Optional: pre-commit hooks (only if configured)
# uv run pre-commit run --all-files
```

## Local Smoke Test

Test the complete trustee_performance pipeline using real `reference/monthly/` data and optional local PostgreSQL integration.

### Setup

1. **Ensure reference data exists** (or tests will be skipped):
   ```bash
   # Reference data should be at:
   ./reference/monthly/
   ```

2. **Configure environment variables** for local testing:
   ```bash
   # Required: Override data source directory
   export WDH_DATA_BASE_DIR=./reference/monthly
   
   # Optional: Local database for execute mode
   export WDH_DATABASE__URI=postgresql://wdh_user:changeme@localhost:5432/wdh_local
   ```

3. **Setup local database** (optional, for execute mode):
   ```bash
   # Apply test schema to your local PostgreSQL
   psql "$WDH_DATABASE__URI" -f scripts/dev/setup_test_schema.sql
   ```

### Usage

```bash
# Run plan-only mode (no database required)
uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --plan-only --max-files 2

# Run execute mode (requires database setup)
uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --execute --max-files 2

# Run smoke tests (opt-in via marker)
uv run pytest -m monthly_data -v

# Skip smoke tests by default (normal test runs)
uv run pytest tests/
```

### Expected Results

- **Plan-only**: Shows SQL execution plan with DELETE + INSERT operations, no database connection
- **Execute**: Shows loader summary with deleted/inserted counts from actual database operations
- **Smoke tests**: Validates discovery, plan generation, and optional database integration

## Try It (End‑to‑End)

Run the existing end‑to‑end test for the first vertical slice (trustee performance):

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

## Source of Truth & Maintenance

- Plan and status live in `ROADMAP.md`.
- This quickstart stays minimal; update only when stable entry points or commands change.
- Changes that affect stable facts should include a README update in the DoD.
- Last reviewed: 2025‑09‑08.
