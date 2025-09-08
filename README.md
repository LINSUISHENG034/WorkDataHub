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

# Lint, types, tests
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Focus a subset
uv run pytest -k trustee_performance -v
```

## Try It (End‑to‑End)
Run the existing end‑to‑end test for the first vertical slice (trustee performance):

```bash
uv run pytest tests/e2e/test_trustee_performance_e2e.py -v
```

## Docs Index
- System overview (current): `docs/overview/01_system_overview.md`
- PRPs (Product Requirements Prompts): `PRPs/`
- PRP workflow: `AGENTS.md`
- Legacy analyses (superseded, for history):
  - `docs/project/01_architecture_analysis_report.md`
  - `docs/implement/01_implementation_plan.md`
  - `docs/project/02_production_data_sample_analysis.md`
  - `docs/project/03_specified_data_source_problems_analysis.md`
  - `docs/project/04_dependency_and_priority_analysis.md`
- PRPs (Product Requirements Prompts): `PRPs/`
- PRP workflow: `AGENTS.md`

## Source of Truth & Maintenance
- Plan and status live in `ROADMAP.md`.
- This quickstart stays minimal; update only when stable entry points or commands change.
- Changes that affect stable facts should include a README update in the DoD.
- Last reviewed: 2025‑09‑08.
