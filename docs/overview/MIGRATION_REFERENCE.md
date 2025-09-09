# Legacy → New Migration Reference (Curated)

See also: `README.md` (Developer Quickstart) for commands/entry points; `ROADMAP.md` for plan/status.

Purpose

- Provide a concise, up‑to‑date reference for migrating legacy `annuity_hub` functionality to the new WorkDataHub architecture.
- Aligns with ROADMAP Milestones M1–M2 and current implementation (config‑driven discovery, domain services, Dagster orchestration, transactional loader).

Scope & Alignment

- Discovery: config‑driven via `data_sources.yml` and `DataSourceConnector` (DONE for first slice).
- Domain: Pydantic models + pure services (trustee_performance is the reference implementation).
- Orchestration: Dagster ops/jobs/schedules/sensors (`repository.py` contains `Definitions`).
- Loader: PostgreSQL loader with plan‑only and execute modes.
- Mapping Service (M2 C‑014): DB‑driven rules engine planned; keep this decoupled from M1 slice.
- Parity/Regression (M2 C‑015): add test harness to compare legacy vs new outputs and report diffs.

Recommended Migration Approach

1) Vertical slice by domain
   - Repeat the trustee_performance pattern: discover → read → process → load
   - Keep domain logic pure and testable; validate with Pydantic models
2) Parity harness (C‑015)
   - Run legacy cleaner and new domain service on the same inputs
   - Normalize outputs and produce a diff report (row counts, PK sets, value tolerances)
3) Validation gates
   - ruff (format + lint), mypy (types), pytest (unit + E2E)
   - Optional coverage: `--cov=src --cov-report=term-missing`
4) Observability
   - Structured logs at op boundaries; sensors for new‑file and data‑quality probes
5) Mapping evolution (C‑014)
   - Defer intelligent MappingService until after initial domain migrations are stable
   - Use a DB‑driven rules engine per ROADMAP (not required for the first slice)

Domain Migration Order (from R‑015)

- P1 (Critical): AnnuityPerformance, AnnuityIncome, RevenueDetails, RevenueBudget
- P2 (Important): GroupRetirement, HealthCoverage×3, Award/Loss×4, Financial (RiskProvisionBalance)
- P3 (Standard): Remaining low‑complexity cleaners, Manual Adjustments, Portfolio Management

What to Keep from Legacy

- Business semantics and transformations encoded in cleaners
- Batch‑oriented processing concept (realized as chunked insert and multi‑file jobs)

What Changes in the New Architecture

- Config‑driven discovery replaces ad‑hoc scanning
- Pure domain services replace monolithic cleaners
- Typed contracts and quantization rules in Pydantic models
- Plan‑only SQL plans for safe previews; transactional execute mode

Validation & DoD (per slice)

- Lint: `uv run ruff check src/ --fix`
- Types: `uv run mypy src/`
- Tests: `uv run pytest -v` (domain + E2E)
- Docs: update README if commands/entry points change; keep ROADMAP status current

Primary References

- Legacy inventory: `docs/overview/R-015_LEGACY_INVENTORY.md`
- Legacy workflow analysis: `docs/overview/LEGACY_WORKFLOW_ANALYSIS.md`
- Mapping service concept (for M2 C‑014): to be defined later (defer design; follow KISS/YAGNI)
