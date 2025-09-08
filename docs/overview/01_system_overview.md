# WorkDataHub — System Overview (M1)

Purpose: a concise, up-to-date overview that reflects the current architecture and code, aligned to ROADMAP. It replaces early exploratory documents while keeping them for historical context.

## Scope & Audience
- Audience: new contributors and reviewers.
- Scope: stable concepts, responsibilities, and entry points. For live plan/status, see `ROADMAP.md`. For step-by-step onboarding, see `README.md`.

## Architecture Summary
- Declarative, domain-oriented pipelines with explicit contracts and orchestration.
- Vertical slices: implement and validate end-to-end per domain.
- Safety-first: plan-only execution by default; CI gates enforce quality.

## Component Model (responsibilities)
- Config: environment settings, schema validation, and discovery rules
  - `src/work_data_hub/config/settings.py`
  - `src/work_data_hub/config/schema.py`
  - `src/work_data_hub/config/data_sources.yml`
- IO: resilient connectors/readers + transactional loader
  - `src/work_data_hub/io/connectors/file_connector.py`
  - `src/work_data_hub/io/readers/excel_reader.py`
  - `src/work_data_hub/io/loader/warehouse_loader.py`
- Domain: Pydantic v2 models + pure services per domain
  - `src/work_data_hub/domain/trustee_performance/{models.py, service.py}`
- Orchestration: Dagster ops/jobs wiring the slice end-to-end
  - `src/work_data_hub/orchestration/{ops.py, jobs.py}`
- Utils: shared types/utilities
  - `src/work_data_hub/utils/types.py`

## Data Flow (E2E)
1) Discover: config-driven discovery of domain files (patterns, versioning hints).
2) Read: Excel rows → list[dict] with robust parsing.
3) Process: domain service validates/transforms into typed models (Pydantic v2).
4) Load: transactional delete-insert or append with plan-only preview by default.

## Configuration & Contracts
- Settings via env (see `.env.example`) and `settings.py`.
- Data source registry in `data_sources.yml` (domains → patterns/table/pk).
- Schema validation via `config/schema.py` to fail fast on misconfigurations.
- Domain contracts: Pydantic models define required/optional fields and types; validation at boundaries ensures correctness.

## Domain Slice (M1): Trustee Performance
- Models: `domain/trustee_performance/models.py` capture the record shape with precise types (e.g., Decimal for money-like fields).
- Service: `domain/trustee_performance/service.py` converts raw Excel rows into validated models; tolerant to Excel numeric cell quirks; propagates `data_source` lineage.
- Tests: `tests/domain/trustee_performance/` + `tests/e2e/test_trustee_performance_e2e.py` validate both unit behavior and end-to-end correctness.

## Orchestration & CLI
- Ops: see `orchestration/ops.py` for discover → read → process → load. JSON-serializable boundaries simplify Dagster run configs and testability.
- Jobs: see `orchestration/jobs.py` for single-file and multi-file jobs and a local CLI (plan-only by default; `--execute` to run against DB).
- Loader: `io/loader/warehouse_loader.py` supports plan-only SQL generation and executed transactions; delete-insert requires PK.

## Quality Gates & Local Workflow
- Lint: `uv run ruff check src/ --fix`
- Types: `uv run mypy src/`
- Tests: `uv run pytest -v` (focus with `-k <pattern>`)
- E2E example: `uv run pytest tests/e2e/test_trustee_performance_e2e.py -v`

## Roadmap Alignment (excerpt)
- M0 completed: security & CI baseline, E2E test baseline.
- M1 completed: connector, reader, domain models/service, loader, ops/jobs, config seeds; bug fixes and input type relaxations.
- See `ROADMAP.md` for current status and upcoming slices (Domain B, observability, parity, deployment).

## Docs Lineage (superseded)
The following early analyses are preserved for history but superseded by this overview:
- `docs/superseded/01_architecture_analysis_report.md`
- `docs/superseded/02_production_data_sample_analysis.md`
- `docs/superseded/03_specified_data_source_problems_analysis.md`
- `docs/superseded/04_dependency_and_priority_analysis.md`
- `docs/superseded/05_implementation_plan.md`

## Maintenance
- Source of truth: plan/status in `ROADMAP.md`; quickstart in `README.md`.
- Keep this overview minimal; update only when component responsibilities or stable entry points change.
- Last reviewed: 2025-09-08.

