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
- PRP workflow and commands: `AGENTS.md`, `COMMANDS.md`
- Legacy analyses (superseded, for history):
  - `docs/project/01_architecture_analysis_report.md`
  - `docs/implement/01_implementation_plan.md`
  - `docs/project/02_production_data_sample_analysis.md`
  - `docs/project/03_specified_data_source_problems_analysis.md`
  - `docs/project/04_dependency_and_priority_analysis.md`
- PRPs (Product Requirements Prompts): `PRPs/`
- PRP workflow and commands: `AGENTS.md`, `COMMANDS.md`

## Source of Truth & Maintenance
- Plan and status live in `ROADMAP.md`.
- This quickstart stays minimal; update only when stable entry points or commands change.
- Changes that affect stable facts should include a README update in the DoD.
- Last reviewed: 2025‑09‑08.
