# WorkDataHub Brownfield Architecture Document

## Introduction

This document captures the CURRENT STATE of the WorkDataHub codebase, including technical debt, workarounds, and real-world patterns. It reflects the transition from a monolithic ETL toward a declarative, testable system composed of isolated domain services, configuration-driven discovery, and orchestrated pipelines. It serves as a reference for AI agents working on enhancements.

### Document Scope

- Covers active code under `src/work_data_hub/`, the Dagster-style orchestration surface, and the enrichment/auth subsystems.
- Calls out how configuration, tooling, and CI/CD interact with legacy parity requirements.
- Highlights dependencies on the legacy annuity hub snapshot and the roadmap/practice documents in `reference/context-engineering-intro/`(incomplete).

### Change Log

| Date | Version | Description | Author |
| :--- | :--- | :--- | :--- |
| 2025-10-06 | 1.2 | Updated dependencies, source tree, and recent changes | Winston (Architect) |
| 2025-10-05 | 1.1 | Initial brownfield analysis | Winston (Architect) |

-----

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

- **CLI entry point**: `PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli` is the unified entry point (Story 6.2-P6); `etl` handles domain execution with flags such as `--plan-only` (default) / `--execute`.
- **Orchestration glue**: `src/work_data_hub/orchestration/ops.py` and `jobs.py` (~40k lines combined) wire discovery → read → process → load flows and are the most interconnected modules.
- **Domain logic**: `src/work_data_hub/domain/` hosts pipelines for `annuity_performance`, `company_enrichment`, `reference_backfill`, and `sample_trustee_performance` plus the shared pipeline builder in `domain/pipelines/`.
- **Configuration surface**: `src/work_data_hub/config/settings.py`, `schema.py`, `mapping_loader.py`, and `config/data_sources.yml` govern environment-aware behavior, file discovery, and mapping seeds.
- **Connectors & IO**: `src/work_data_hub/io/` (e.g., `excel_reader.py`, `file_connector.py`, `loader/warehouse_loader.py`) implement resilient ingestion and transactional load semantics.
- **Cleansing utilities**: `src/work_data_hub/utils/` and `src/work_data_hub/cleansing/` split structural helpers from registry-driven value cleansers.
- **Auth & enrichment helpers**: `src/work_data_hub/auth/eqc_auth_opencv.py` and related files combine Playwright, OpenCV, and GMSSL for EQC login flows that feed the company enrichment service.
- **Legacy baseline**: `legacy/annuity_hub/` is the read-only reference implementation used for regression and parity checks.
- **Source-of-truth docs**: `reference/context-engineering-intro/README.md` (architecture notes), `ROADMAP.md` (milestones, debt), and `PRPs/` (ready execution slices). Important Note: The documents above are summaries of early development work and may have an unclear structure or disorganized descriptions.

### Supporting Assets

- **CI pipeline**: `.github/workflows/ci.yml` runs Ruff, mypy, and pytest (with coverage) on Python 3.10–3.12 plus gitleaks scanning.
- **Environment contract**: `.env` and `src/work_data_hub/config/settings.py` define the `WDH_*` configuration surface consumed by Pydantic Settings.
- **Schema generation**: `scripts/create_table/` scripts generate and verify DDL from JSON contracts; CI enforces the annuity DDL snapshot.

-----

## High Level Architecture

### Technical Summary

WorkDataHub retains Dagster definitions but executes them through an opinionated CLI wrapper. Pipelines follow a consistent topology:

1. Configuration-driven discovery (`data_sources.yml`, mapping seeds) selects files and metadata through `DataSourceConnector` implementations.
2. IO adapters normalize inputs via `excel_reader.py` and feed rows into domain services.
3. Domain services and pipeline steps (Pydantic v2 models + pure functions) perform validation, enrichment, and transformation.
4. Transactional loaders stage plan-only SQL or execute writes against the warehouse, respecting delete/insert scopes.

The orchestration layer no longer depends on Dagster’s daemon; it keeps definitions for future UI/daemon adoption once roadmap gates are met. Each domain migration is a vertically sliced pipeline verified against the legacy stack before new features are layered on top.

### Integration Highlights

- **Company enrichment**: `domain/company_enrichment/` exposes an async-ready lookup queue serviced by EQC automation (Playwright + OpenCV). Tokens and secrets are hydrated via `auth/eqc_settings.py` and stored in the Postgres cache defined in roadmap tasks.
- **Pipeline builder**: `domain/pipelines/` provides reusable `TransformStep` abstractions, adapters, and config parsing shared across annuity and forthcoming domains.
- **Cleansing registry**: `cleansing/registry.py` registers reusable value-level cleansing rules (e.g., numeric normalization) that complement structural helpers in `utils/`.
- **Legacy parity**: tests under `tests/e2e/test_pipeline_vs_legacy.py` enforce equivalence between new pipelines and the annuity legacy output before production promotion.

### Actual Tech Stack

| Category | Technology | Version / Notes |
| :--- | :--- | :--- |
| Language | Python | 3.10+ locally; CI validates 3.10, 3.11, 3.12 |
| Packaging & Env | uv | `uv.lock` checked in; `uv sync --dev` is the standard bootstrap |
| Orchestration | Dagster | Latest (definitions only; CLI-first execution) |
| Data validation | Pydantic | 2.11.7+ with `pydantic-settings>=2.10.1` |
| DataFrames | pandas | Locked via `uv.lock` (installed when syncing deps) |
| Spreadsheet IO | openpyxl | Latest (locked via uv) |
| Warehousing | psycopg2-binary | Latest (transactional loader) |
| Enrichment automation | Playwright ≥1.55.0, OpenCV Headless ≥4.11.0.86, GMSSL ≥3.2.2, playwright-stealth ≥2.0.0 |
| Columnar / interchange | pyarrow | ≥21.0.0 |
| Lint / Type / Test | Ruff ≥0.12.12, MyPy ≥1.17.1, Pytest with custom markers, pytest-cov ≥6.2.1, pytest-asyncio ≥1.2.0 |

### Repository Structure Reality Check

```
work-data-hub/
├── .bmad-core/                    # BMAD™ agent configuration and templates
├── legacy/
│   └── annuity_hub/               # Read-only legacy ETL snapshot.
├── reference/
│   ├── context-engineering-intro/
│   │   ├── README.md
│   │   ├── ROADMAP.md
│   │   └── PRPs/
│   └── monthly/                   # Production environment requires processing real-world data.
├── src/work_data_hub/
│   ├── auth/                      # EQC auth automation and settings.
│   ├── cleansing/                 # Registry-driven cleansing rules.
│   │   ├── config/                # Cleansing configuration
│   │   ├── integrations/          # Pydantic and other framework integrations
│   │   └── rules/                 # Value-level cleansing rules (numeric, etc.)
│   ├── config/                    # Settings, schemas, mapping loader, data_sources.yml.
│   ├── domain/
│   │   ├── annuity_performance/   # High-complexity pipeline under active refactor.
│   │   ├── company_enrichment/    # Lookup queue + models feeding multiple domains.
│   │   ├── pipelines/             # Shared pipeline builder, adapters, core types.
│   │   ├── reference_backfill/    # Backfill utilities for seed data.
│   │   └── sample_trustee_performance/ # First vertical slice reference implementation.
│   ├── io/                        # File connectors, Excel reader, warehouse loader.
│   │   ├── connectors/            # File connector, EQC client
│   │   ├── readers/               # Excel reader
│   │   └── loader/                # Warehouse, company enrichment, and mapping loaders
│   ├── orchestration/             # Ops, jobs, schedules, sensors, repository.
│   ├── scripts/                   # CLI helpers (EQC integration, mapping migration).
│   └── utils/                     # Structural helpers (column normalizer, date parser, PAToken client).
├── tests/                         # Unit, domain, IO, orchestration, e2e, fixtures, legacy parity.
└── pyproject.toml                 # uv-managed project definition + pytest markers.
```

-----

## Source Tree and Module Organization

### Core Modules

- **Orchestration (`src/work_data_hub/orchestration/`)**
  - `ops.py`: Defines discover/read/process/load ops with configuration selectors and toggles for `--plan-only` vs `--execute`.
  - `jobs.py`: Composes ops into jobs, wires CLI flags, and controls multi-file accumulation vs single-file paths.
  - `schedules.py` & `sensors.py`: Ready but dormant; used when roadmap gate C-050 is met.

- **Domain Services (`src/work_data_hub/domain/`)**
  - `annuity_performance/`: Large refactor in progress (pipeline steps, CSV export, parity enforcement).
  - `company_enrichment/`: Queue-backed enrichment service using Postgres and EQC token automation.
  - `pipelines/`: Abstractions for defining step-based pipelines, config parsing, and adapter interfaces.
  - `sample_trustee_performance/`: Stable vertical slice used as reference implementation.
  - `reference_backfill/`: Backfill utilities for seed datasets and parity comparisons.

- **Configuration (`src/work_data_hub/config/`)**
  - `settings.py`: Pydantic Settings binding to `WDH_*` environment variables (`.env` documents required keys).
  - `schema.py`: Data source schema definitions powering validation of `data_sources.yml`.
  - `mapping_loader.py` & `mappings/`: YAML-based mapping seeds used across domains; migration chores ensure portability.

- **IO (`src/work_data_hub/io/`)**
  - `connectors/file_connector.py`: Custom file discovery supporting environment overrides and globbing.
  - `connectors/eqc_client.py`: HTTP client for EQC integration and company data enrichment.
  - `readers/excel_reader.py`: Resilient Excel ingestion with normalization and error handling.
  - `loader/warehouse_loader.py`: Delete/insert aware loader that skips auto-generated keys.
  - `loader/company_enrichment_loader.py`: Specialized loader for company enrichment data.
  - `loader/company_mapping_loader.py`: Loader for company mapping seed data.

- **Auth & Utilities**
  - `auth/eqc_auth_opencv.py` & `auth/eqc_auth_handler.py`: Automates EQC slider captcha resolution (OpenCV) and token acquisition (Playwright, GMSSL).
  - `utils/column_normalizer.py` & `utils/date_parser.py`: Structural helpers consumed across domains, cleansing, and pipelines.
  - `utils/patoken_client.py`: PAToken client for authentication flows.
  - `cleansing/rules/numeric_rules.py`: Category-driven transformations (null normalization, currency stripping, rounding).
  - `cleansing/integrations/pydantic_adapter.py`: Integration layer for Pydantic models with cleansing rules.

### Tests and Fixtures

- `tests/domain/`: Unit coverage for domain services and cleansing rules.
- `tests/e2e/`: Verifies plan-only and execute flows plus parity with legacy outputs.
- `tests/io/` & `tests/config/`: Exercise connectors, readers, mappings, and settings contracts.
- `tests/legacy/`: Harness for comparing new outputs against `legacy/annuity_hub` datasets.
- `tests/fixtures/`: Provides sample Excel files, mapping data, and eqc tokens for deterministic tests.

-----

## Data Models and APIs

### Data Models

- **Pydantic v2 models** (e.g., `domain/annuity_performance/models.py`, `domain/company_enrichment/models.py`) enforce strict typing, custom validators, and deterministic serialization for downstream loaders.
- **Pipeline steps** (`domain/annuity_performance/pipeline_steps.py`, `domain/pipelines/core.py`) define staged transforms with explicit contracts for inputs/outputs, enabling targeted parity checks and logging.
- **Settings models** (`config/settings.py`) derive environment-bound configuration, including toggles for pipeline mode, enrichment providers, and IO directories.

### APIs & Integration Points

- **CLI**: `python -m work_data_hub.cli etl` exposes flags for domain selection (`--domains` / `--all-domains`), max files, plan-only vs execute, and pipeline overrides.
- **Dagster Definitions**: `orchestration/repository.py` exposes `Definitions` for potential Dagster UI/daemon usage, though currently executed in-process.
- **EQC Integration**: `scripts/demos/test_slider_fix.py` and `src/work_data_hub/scripts/eqc_integration_example.py` demonstrate programmatic token retrieval that feeds the enrichment queue.
- **DDL Generation**: `scripts/create_table/generate_from_json` produces SQL from JSON contracts, with CI ensuring no drift for annuity tables.

-----

## Technical Debt and Known Issues

### Priority Debt (see `reference/context-engineering-intro/ROADMAP.md`)

1. **C-014 Mapping Service**: Centralize mapping/default rules to unblock multi-domain migrations (`ROADMAP.md:54`).
2. **F-065 Annuity Pipeline Refactor**: Complete the pipeline-based architecture with enrichment adapters and parity harness (`ROADMAP.md:58`).
3. **C-066 Golden Dataset Regression**: Build the dataset-backed regression suite to protect future parity (`ROADMAP.md:59`).
4. **Pending Domain Migrations**: High-complexity domains (annuity income, revenue/budget, health coverage) remain PENDING and will surface legacy quirks (`ROADMAP.md:60-69`).
5. **C-064 Lint/Format Policy**: Consolidate repo-wide lint/format configuration once roadmap gate is reached (`ROADMAP.md:164`).

### Workarounds & Tribal Knowledge

- `.bmad-core/`: AI agent configuration framework (BMAD™ Core) for architect, developer, and product owner personas; used with Claude Code slash commands.
- `legacy/annuity_hub/` stays read-only; capture deviations in PRPs or docs instead of patching legacy code.
- Always run `--plan-only` before `--execute` to inspect generated SQL plans and satisfy CI expectations.
- EQC automation relies on headful Playwright with slider captcha solving; developers must refresh tokens within 30 minutes of inactivity (see `src/work_data_hub/auth/EQC_AUTH_OPENCV_ISSUE_REPORT.md`).
- Mapping seeds may reference localized column names; use `utils/column_normalizer` and cleansing rules to align naming before loading.
- CI enforces DDL stability for annuity tables—regenerate via `scripts/create_table/generate_from_json` whenever pipeline contracts change.
- **Recent work** (Oct 2025): Cleansing pipeline framework introduced with registry-driven rules and Pydantic integration; company enrichment service hardened with EQC automation.

### Company Enrichment Service Architecture

**Overview:** Company ID resolution is a critical enrichment service supporting cross-domain analytics. Implementation follows Provider abstraction pattern with fallback to stable temporary IDs for unresolved companies. See `reference/01_company_id_analysis.md` for comprehensive solution documentation.

**Core Components:**

1. **Provider Layer (`domain/company_enrichment/providers.py`)**
   - `EnterpriseInfoProvider` protocol: Defines `search_by_name(name)` and `get_by_id(id)` interfaces
   - `StubProvider`: Offline fixtures for testing/CI (no external dependencies)
   - `EqcProvider`: Real EQC platform API client with rate limiting, retry logic, token management
   - `LegacyProvider` (optional): Adapter for existing Mongo/MySQL crawler

2. **Gateway (`domain/company_enrichment/gateway.py`)**
   - `EnterpriseInfoGateway`: Orchestrates normalization, provider calls, scoring, caching
   - Handles sync budget limiting (prevent blocking main pipeline)
   - Implements fallback chain: cache → provider → temporary ID generation
   - Evaluates confidence scores and applies human review thresholds

3. **Data Models (`domain/company_enrichment/models.py`)**
   - `CompanyCandidate`: Search result with match score and metadata
   - `CompanyDetail`: Canonical company record with official_name, unified_credit_code, aliases
   - `LookupRequest`: Queue entry for async enrichment
   - `CompanyIdResult`: Resolution result with source tracking and confidence

4. **Persistence Schema (Postgres `enterprise` schema)**
   ```sql
   -- Canonical company master data
   enterprise.company_master (
     company_id TEXT PRIMARY KEY,
     official_name TEXT NOT NULL,
     unified_credit_code TEXT,
     aliases TEXT[],
     source TEXT,  -- 'internal' | 'external'
     updated_at TIMESTAMP
   )

   -- Normalized name index for fast lookup
   enterprise.company_name_index (
     norm_name TEXT PRIMARY KEY,
     company_id TEXT REFERENCES company_master,
     match_type TEXT,  -- 'exact' | 'alias' | 'fuzzy'
     updated_at TIMESTAMP
   )

   -- Async enrichment queue
   enterprise.enrichment_requests (
     id SERIAL PRIMARY KEY,
     raw_name TEXT NOT NULL,
     norm_name TEXT NOT NULL,
     business_key TEXT,
     status TEXT,  -- 'pending' | 'processing' | 'done' | 'failed'
     attempts INT DEFAULT 0,
     last_error TEXT,
     requested_at TIMESTAMP,
     updated_at TIMESTAMP
   )
   ```

5. **Temporary ID Generation**
   - Unresolved companies get stable `IN_<16-char-Base32>` IDs
   - Generated via `HMAC_SHA1(WDH_ALIAS_SALT, business_key)` truncated to 128 bits
   - Business key: normalized company name + optional plan code/account signals
   - Ensures same company always maps to same temporary ID across runs

6. **Resolution Strategy (Multi-tier fallback)**
   ```
   1. Configuration overrides (manual mappings)
   2. Internal mappings: plan_company_map, account_company_map
   3. Name index: company_name_index (exact/alias/fuzzy match)
   4. Sync online lookup (budget-limited): Call EqcProvider within sync_budget
   5. Async queue: Enqueue for deferred resolution, return temporary ID
   6. Fallback: Generate stable temporary ID
   ```

7. **Confidence Scoring & Human Review**
   - **≥0.90**: Auto-accept, use company_id directly
   - **0.60-0.90**: Accept but flag `needs_review=True` for human verification
   - **<0.60**: Keep temporary ID, queue for async resolution

**Configuration Surface:**

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `WDH_ALIAS_SALT` | HMAC salt for temporary ID generation | **Required** |
| `WDH_ENRICH_COMPANY_ID` | Enable enrichment service | `0` (disabled) |
| `WDH_ENRICH_SYNC_BUDGET` | Max sync API calls per run | `0` (no sync) |
| `WDH_ENTERPRISE_PROVIDER` | Provider selection | `stub` |
| `WDH_PROVIDER_EQC_TOKEN` | EQC API token (30-min validity) | None |
| `WDH_COMPANY_ENRICHMENT_ENABLED` | Simplified approach toggle | `0` |
| `WDH_COMPANY_SYNC_LOOKUP_LIMIT` | Sync lookup limit (S-003) | `5` |

**Implementation Approaches:**

**Complex Approach (CI-002):** Full-featured with 8 sub-tasks
- CI-002A: Provider & Gateway minimal loop
- CI-002B: Cache, name index, request queue
- CI-002C: Sync budget enrichment (optional)
- CI-002D: Async backfill job
- CI-002E: Observability & operational metrics
- CI-002F: Real EQC Provider with credentials
- CI-002G: Legacy crawler adapter
- CI-002H: Existing data import/migration

**Simplified Approach (S-001~S-004):** Streamlined for MVP
- S-001: Legacy mapping migration to unified table
- S-002: Direct EQC client (no Gateway/Provider abstraction)
- S-003: Basic cache + lookup queue with temp ID sequence
- S-004: MVP end-to-end validation with legacy parity

**Current Implementation Status:**
- ✅ Basic `domain/company_enrichment/` structure exists
- ✅ EQC authentication automation (`auth/eqc_auth_opencv.py`)
- ✅ Specialized loader (`loader/company_enrichment_loader.py`)
- ⚠️ **Decision pending:** Complex vs. Simplified approach for MVP
- ⚠️ **Incomplete:** Full Provider/Gateway pattern, async queue, observability

**MVP Scope Recommendation:**
- **Use StubProvider** for MVP (offline fixtures)
- Defer EQC integration, async queue, legacy migration to Growth phase
- Focus MVP on proving core pipeline patterns (Bronze→Silver→Gold, validation, orchestration)

**Security Considerations:**
- EQC tokens expire after 30 minutes, require refresh
- Logs sanitized: no token leakage
- Playwright automation for token capture (optional, see `reference/01_company_id_analysis.md` §8)
- All credentials via environment variables (`WDH_PROVIDER_EQC_TOKEN`)

**Testing Strategy:**
- Unit tests with `StubProvider` (no external dependencies)
- Integration tests with mock EQC API
- E2E tests validate enrichment stats and unknown CSV export
- Parity tests ensure enrichment doesn't break legacy output equivalence

-----

## Development and Deployment

### Local Development Workflow

1. **Bootstrap**
   ```bash
   uv venv
   uv sync --dev
   ```
2. **Quality gates**
   ```bash
   uv run ruff format .
   uv run ruff check src/ --fix
   uv run mypy src/
   uv run pytest -v -m "not postgres"
   ```
3. **Pipeline execution**
   ```bash
   PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sample_trustee_performance --plan-only
   PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sample_trustee_performance --execute
   ```
4. **Legacy parity validation**
   ```bash
   uv run pytest tests/e2e/test_pipeline_vs_legacy.py::test_pipeline_vs_legacy_parity -v
   ```

### CI/CD Process

- GitHub Actions workflow (`ci.yml`) runs lint → type-check → tests on every push/PR.
- Test job runs across Python 3.10–3.12, enforces DDL snapshot consistency, and publishes coverage to Codecov (Python 3.12 matrix entry).
- Gitleaks scanning is non-blocking today but reports potential secret leaks.
- `ci-complete` job fails the workflow if any critical job fails, even if the security scan is non-blocking.

### Deployment Strategy

- Current deployments remain CLI-driven; Dagster UI/daemon deployment (C-050) will be triggered only when multi-domain orchestration and observability gates are met.
- Environment configuration uses `WDH_*` variables with profiles defined in `.env.example`; secrets must be injected via environment or secret managers before execution.

-----

## Testing Reality

### Test Coverage Snapshot

- **Unit & domain tests**: Validate transformation logic, cleansing rules, and enrichment services.
- **E2E tests**: Run plan-only and execute paths against sample datasets, asserting database load behavior where possible.
- **Legacy parity tests**: Compare outputs with `legacy/annuity_hub` artifacts to ensure migrations do not regress.
- **Auth/IO tests**: Cover EQC automation edge cases and IO failure handling.

### Pytest Markers (from `pyproject.toml`)

- `postgres`: Requires a live Postgres instance; excluded by default (`-m "not postgres"`).
- `monthly_data`: Opt-in tests needing `reference/monthly` sample data.
- `legacy_data`: Legacy E2E validations; opt-in to avoid heavy runs by default.
- `sample_domain`: Focused coverage for the sample trustee performance domain.

### Helpful Commands

```bash
uv run pytest -v -m sample_domain
uv run pytest -v -m legacy_data -k annuity_performance_e2e
uv run pytest --cov=src --cov-report=term-missing
```

-----

## If Enhancement PRD Provided - Impact Analysis

No PRD was supplied for this analysis; update this section when evaluating specific enhancements.

-----

## Appendix - Useful Commands and Scripts

```bash
# Regenerate annuity DDL from JSON contract
uv run python -m scripts.create_table.generate_from_json --domain annuity_performance --out scripts/create_table/ddl/annuity_performance.sql

# Apply generated SQL to a target database
uv run python -m scripts.create_table.apply_sql --sql scripts/create_table/ddl/annuity_performance.sql

# Seed enrichment cache or run EQC integration demos
uv run python src/work_data_hub/scripts/eqc_integration_example.py
uv run python scripts/demos/test_slider_fix.py

# Migrate mapping seeds from legacy sources
uv run python src/work_data_hub/scripts/migrate_company_mappings.py

# Launch Dagster definitions locally (manual exploration only)
uv run dagster dev -f src/work_data_hub/orchestration/repository.py
```
