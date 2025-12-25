# WorkDataHub

[![CI](https://github.com/LINSUISHENG034/WorkDataHub/actions/workflows/ci.yml/badge.svg)](https://github.com/LINSUISHENG034/WorkDataHub/actions/workflows/ci.yml)

A modernized data processing platform built with Clean Architecture principles, featuring type-safe Python 3.10+, advanced validation frameworks, and Dagster orchestration.

## Project Overview

WorkDataHub is a comprehensive data engineering platform designed to process, validate, and transform business data with enterprise-grade reliability. The platform follows Clean Architecture patterns to ensure maintainability, testability, and separation of concerns across all layers.

## Directory Structure

The project follows Clean Architecture with clear layer separation:

```
src/work_data_hub/
├── domain/                   # Pure business logic (no external dependencies)
│   ├── pipelines/            # Core pipeline framework
│   │   └── steps/            # Generic transformation steps
│   ├── annuity_performance/  # Reference domain implementation
│   └── ...                   # Domain models and business rules
├── infrastructure/           # Reusable cross-domain services (Epic 5)
│   ├── transforms/           # Pipeline steps (MappingStep, CleansingStep, etc.)
│   ├── cleansing/            # Registry-driven data cleansing rules
│   ├── enrichment/           # Company ID resolution and normalization
│   ├── validation/           # Error handling and report generation
│   └── settings/             # Configuration schema and loaders
├── io/                  # Data access layer
│   ├── readers/         # Excel and file readers
│   ├── loader/          # PostgreSQL loading framework
│   └── connectors/      # File discovery and external connectors
├── orchestration/       # Dagster jobs and schedules
├── config/              # Configuration management (Pydantic settings)
└── utils/               # Shared utilities (logging, date parsing)

tests/
├── unit/                # Fast unit tests (<1s total)
├── integration/         # Integration tests with database (<10s)
├── e2e/                 # End-to-end pipeline tests
├── smoke/               # Quick validation tests
└── fixtures/            # Test data and golden datasets
```

### Layer Responsibilities

**Domain Layer** (`domain/`)
- Pure business logic and lightweight orchestration
- 100% testable without external services
- NO imports from `io/` or `orchestration/` layers
- Contains domain models, schemas, and service orchestrators
- Each domain ~500-900 lines (post-Epic 5 refactoring)

**Infrastructure Layer** (`infrastructure/`) - NEW in Epic 5
- Reusable cross-domain services and utilities
- Transform pipeline steps (MappingStep, CleansingStep, etc.)
- Data cleansing registry with YAML configuration
- Company ID resolution and normalization
- Validation error handling and report generation
- NO imports from `io/` or `orchestration/` layers
- Architecture diagram & narrative: see `docs/architecture/infrastructure-layer.md`

**I/O Layer** (`io/`)
- File reading, database writes, external API calls
- May import from `domain/` and `infrastructure/` layers
- Handles all external system interactions

**Orchestration Layer** (`orchestration/`)
- Dagster job definitions and schedule triggers
- Wires together `domain/`, `infrastructure/`, and `io/` components
- Top-level layer that can import from all other layers

**Config Layer** (`config/`)
- Pydantic settings for type-safe configuration
- YAML configuration loaders

**Utils Layer** (`utils/`)
- Pure utility functions (date parsing, column normalization)
- Shared helpers with no external dependencies

## Technology Stack

**Core Technologies:**
- **Python 3.10+**: Modern type system and language features
- **uv**: Ultra-fast package manager (10-100x faster than pip)
- **Dagster**: Orchestration and scheduling framework
- **PostgreSQL**: Primary data warehouse with Alembic migrations
- **Pydantic 2.11.7+**: Runtime type validation and settings management
- **Pandas**: Data transformation and manipulation

**Data Quality & Validation:**
- **Pydantic**: Row-level validation (Silver layer)
- **Pandera**: DataFrame schema validation (Bronze/Gold layers)
- **structlog**: True structured logging

**Developer Tools:**
- **mypy 1.17.1+**: Static type checking (100% type coverage required)
- **ruff 0.12.12+**: Fast linting and formatting (replaces black + flake8 + isort)
- **pytest**: Testing framework with pytest-cov for coverage

## Quick Start

### Prerequisites

- Python 3.10 or higher
- uv package manager ([installation guide](https://github.com/astral-sh/uv))
- PostgreSQL 12+ (for database features)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd WorkDataHub
   ```

2. **Install dependencies with uv:**
   ```bash
   # Install all dependencies including dev tools
   uv sync

   # Or install without dev dependencies
   uv sync --no-dev
   ```

3. **Configure environment:**
   ```bash
   # Copy environment template
   cp .env.example .env

   # Edit .env with your configuration
   # At minimum, set DATABASE_URL for PostgreSQL connection
   ```

### Excel Reader (Story 3.3) Quick Guide

- Supported formats: `.xlsx` and `.xlsm` via `pandas` + `openpyxl`; `.xls` is not supported.
- Usage:
  ```python
  from pathlib import Path
  from work_data_hub.io.readers.excel_reader import ExcelReader

  reader = ExcelReader()
  result = reader.read_sheet(
      Path("reference/monthly/202501/收集数据/数据采集/V1/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx"),
      sheet_name="规模明细",
      skip_empty_rows=True,
  )
  print(result.sheet_name, result.row_count, result.column_count)
  ```
- Behavior highlights:
  - Sheet selection by name or 0-based index; raises `DiscoveryError` with available sheets listed if not found.
  - Empty-row handling: blanks/whitespace → dropped when `skip_empty_rows=True` (default).
  - Merged cells: values forward-filled after empty-row cleanup to keep ranges consistent.
  - Returns `ExcelReadResult` with `df`, `sheet_name`, `row_count`, `column_count`, `file_path` (Path), `read_at` (datetime).
- Troubleshooting:
  - **File not found / corrupted**: You’ll see `DiscoveryError(failed_stage='excel_reading')`; check path/extension or re-save the Excel file.
  - **Missing sheet**: Ensure `sheet_name` matches exactly (case/locale); inspect `available sheets` in the error message.
  - **Unexpected row counts**: Set `skip_empty_rows=False` to inspect raw rows, then re-enable after confirming formatting-only rows are safe to drop.

4. **Verify installation:**
   ```bash
   # Run tests to verify setup
   pytest tests/unit -v
   ```

## Running Tests Locally

The GitHub Actions workflow now runs quality gates, unit tests, integration tests, and aggregated coverage. Reproduce those stages locally as follows.

### Unit Tests (fast / isolated)

```bash
PYTHONPATH=src uv run pytest -v -m "unit and not integration and not postgres" --maxfail=1
```

This covers Stories 1.1–1.6 with no external dependencies and completes in under 30 seconds. Add `--cov=src --cov-report=term-missing` to inspect coverage locally.

### Integration Tests (PostgreSQL required)

```bash
set DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db>   # Windows (use `export` on Linux/macOS)
PYTHONPATH=src uv run pytest -v -m "integration or postgres"
```

Integration tests exercise migrations, WarehouseLoader transactional behavior, and the sample pipeline → WarehouseLoader → PostgreSQL flow. They expect `DATABASE_URL` (or `WDH_TEST_DATABASE_URI`) to point to a disposable PostgreSQL database.

### Performance Regression Probe

```bash
PYTHONPATH=src uv run pytest tests/integration/test_performance_baseline.py::test_sample_pipeline_performance_regression -v
```

This writes/reads `tests/performance_baseline.json`. The first run seeds the baseline; subsequent runs warn (not fail) when execution time regresses by >20%.

### CI-equivalent Sweep

```bash
PYTHONPATH=src uv run pytest -v -m "unit and not integration and not postgres"
PYTHONPATH=src uv run pytest -v -m "integration or postgres"
PYTHONPATH=src uv run python scripts/validate_coverage_thresholds.py --coverage-file coverage.json --warn-only
```

The final command expects you to combine coverage files (via `coverage combine` + `coverage json`) before running the validator; it emits warnings when module-level targets (domain 90%, io 70%, orchestration 60%, overall 80%) are not met.

### Using uv Package Manager

**Why uv?**
- 10-100x faster than pip for dependency resolution and installation
- Deterministic lock files (uv.lock) for reproducible builds
- Compatible with standard Python packaging (pyproject.toml)

**Common Commands:**
```bash
# Install dependencies
uv sync

# Add a new package
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Update dependencies
uv lock --upgrade

# Activate virtual environment (if needed)
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## Development

### Running Tests

```bash
# Run all tests with verbosity
uv run pytest -v

# Run only unit tests (fast)
uv run pytest -m unit

# Run integration tests
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=src/work_data_hub --cov-report=html
```

**Test Markers:**
- `@pytest.mark.unit`: Fast unit tests (<1s total)
- `@pytest.mark.integration`: Integration tests with database (<10s)
- `@pytest.mark.postgres`: Requires PostgreSQL database
- `@pytest.mark.monthly_data`: Opt-in tests requiring reference data
- `@pytest.mark.legacy_data`: Opt-in tests for legacy compatibility
- `@pytest.mark.legacy_suite`: Opt-in legacy regression suites (`RUN_LEGACY_TESTS=1` or `--run-legacy-tests`)
- `@pytest.mark.e2e_suite`: Opt-in Dagster/warehouse E2E suites (`RUN_E2E_TESTS=1` or `--run-e2e-tests`)
- `@pytest.mark.e2e`: Legacy parity marker retained for backwards compatibility
- `@pytest.mark.performance`: Marks high-cost stress/performance scenarios
- `@pytest.mark.sample_domain`: Sample trustee pipeline scenarios

Legacy/E2E suites are skipped by default. Enable them with the matching CLI flags (`pytest --run-legacy-tests`, `pytest --run-e2e-tests`) or by exporting `RUN_LEGACY_TESTS=1` / `RUN_E2E_TESTS=1`.

### Code Quality

```bash
# Run type checking
uv run mypy src/ --strict

# Run linting
uv run ruff check src/work_data_hub docs

# Auto-fix linting issues (only when needed)
uv run ruff check src/work_data_hub docs --fix

# Format code
uv run ruff format src/work_data_hub docs

# Format check (CI equivalent)
uv run ruff format --check src/work_data_hub docs
```

> ℹ️ The `legacy/` tree has been removed as part of Epic 5 infrastructure refactoring. The broad `tests/` tree may still carry some lint debt from the historical codebase. The default Ruff command excludes problematic paths so guardrails stay green. Opt-in linting for them is still available with `uv run ruff check tests/` when you are ready to tackle the backlog.

### Dagster Orchestration

WorkDataHub uses Dagster for job orchestration and pipeline scheduling. The Dagster UI provides visibility into job execution, logs, and schedules.

**Starting the Dagster Development Server:**

```bash
# Launch Dagster UI (requires workspace.yaml in project root)
dagster dev

# Access the UI at: http://localhost:3000
# Press Ctrl+C to stop the server
```

**Available Jobs:**
- `sample_trustee_performance_job`: Sample multi-file processing pipeline
- `annuity_performance_job`: End-to-end annuity ETL with enrichment
- `process_company_lookup_queue_job`: Process pending EQC lookup requests

Note: `import_company_mappings_job` removed in Story 7.1-4 (Zero Legacy)

**Executing Jobs:**

```bash
# Execute job via CLI (without UI)
dagster job execute -f src/work_data_hub/orchestration/jobs.py -j annuity_performance_job

# List all available jobs
dagster job list
```

**Configuration:**
- **DAGSTER_HOME** (default: `~/.dagster`): SQLite metadata storage for local development
- **DAGSTER_POSTGRES_URL** (optional): PostgreSQL backend for production metadata storage

See `workspace.yaml` for Dagster code location configuration and `orchestration/` directory for job definitions.

## Configuration

WorkDataHub uses centralized configuration management powered by Pydantic Settings (Story 1.4). Configuration is loaded from environment variables with validation at startup to catch configuration errors early.

### Required Environment Variables

**DATABASE_URL** (required)
- Database connection string
- Format: `postgresql://username:password@host:port/database`
- Example: `postgresql://wdh_user:changeme@localhost:5432/wdh`
- **Production requirement**: Must be a PostgreSQL connection string (validated at startup)

**ENVIRONMENT** (default: `dev`)
- Deployment environment
- Valid values: `dev`, `staging`, `prod`
- Production environments enforce strict validation rules (e.g., PostgreSQL-only databases)

### Optional Environment Variables

**LOG_LEVEL** (default: `INFO`)
- Logging level for structured logging framework (Story 1.3)
- Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Used by the structlog-based logging system

**DAGSTER_HOME** (default: `~/.dagster`)
- Dagster home directory for orchestration metadata and run storage

**MAX_WORKERS** (default: `4`)
- Maximum number of concurrent worker threads for data processing operations

**DB_POOL_SIZE** (default: `10`)
- Database connection pool size for PostgreSQL connections

**DB_BATCH_SIZE** (default: `1000`)
- Batch size for bulk database operations

### Configuration Setup

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Set required variables in `.env`:**
   ```bash
   # Minimum required configuration
   DATABASE_URL=postgresql://user:password@localhost:5432/workdatahub
   ENVIRONMENT=dev
   ```

3. **Optional: Customize logging and performance:**
   ```bash
   LOG_LEVEL=DEBUG
   MAX_WORKERS=8
   DB_POOL_SIZE=20
   ```

### Data Sources Configuration (Epic 3)

WorkDataHub Epic 3 implements intelligent file discovery with version-aware configuration through `config/data_sources.yml`. This configuration defines how data files are discovered, matched, and loaded across different domains and data versions.

#### Configuration Structure

```yaml
# Epic 3: Intelligent File Discovery & Version Detection
# Schema Version: 1.0

schema_version: "1.0"

domains:
  # Annuity Performance Domain (validated with real 202411 data)
  annuity_performance:
    # Base path with template variables
    base_path: "reference/monthly/{YYYYMM}/收集数据/数据采集"
    # File patterns to match (glob syntax)
    file_patterns:
      - "*年金终稿*.xlsx"
    # Patterns to exclude (temp files, emails, etc.)
    exclude_patterns:
      - "~$*"         # Excel temp files
      - "*回复*"      # Email reply files
      - "*.eml"       # Email message files
    # Excel sheet name to load
    sheet_name: "规模明细"
    # Version selection strategy
    version_strategy: "highest_number"
    # Fallback behavior when version detection ambiguous
    fallback: "error"

  # Future domains can be added here:
  # universal_insurance:
  #   base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
  #   file_patterns: ["*万能险*.xlsx"]
  #   sheet_name: "明细数据"
```

#### Configuration Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `schema_version` | string | No | "1.0" | Configuration schema version for backward compatibility |
| `base_path` | string | Yes | - | Path template with `{YYYYMM}`, `{YYYY}`, `{MM}` placeholders |
| `file_patterns` | list[string] | Yes | - | Glob patterns to match files (at least 1 required) |
| `exclude_patterns` | list[string] | No | [] | Glob patterns to exclude (temp files, emails) |
| `sheet_name` | string|int | Yes | - | Excel sheet name (string) or 0-based index (int) |
| `version_strategy` | enum | No | "highest_number" | Strategy: "highest_number", "latest_modified", "manual" |
| `fallback` | enum | No | "error" | Fallback: "error", "use_latest_modified" |

#### Version Strategy Options

- **`highest_number`** (default): Select V3 > V2 > V1 (numeric version folders)
- **`latest_modified`**: Select most recently modified folder
- **`manual`**: Require explicit `--version=V1` CLI flag

#### Template Variables

Allowed template variables in `base_path`:
- `{YYYYMM}`: Full year and month (e.g., 202501)
- `{YYYY}`: Full year (e.g., 2025)
- `{MM}`: Month (e.g., 01)

**Security**: Only whitelisted variables allowed to prevent injection attacks.

#### Using Configuration in Code

```python
# Import the pre-instantiated singleton
from work_data_hub.config import settings

# Access configuration values
database_url = settings.DATABASE_URL
log_level = settings.LOG_LEVEL
environment = settings.ENVIRONMENT

# Configuration is loaded once and cached for performance
# Multiple imports return the same instance
```

### Configuration Validation

The configuration system validates settings at application startup:
- Missing required fields (e.g., `DATABASE_URL`) raise `ValidationError` with clear error messages
- Production environments (`ENVIRONMENT=prod`) enforce PostgreSQL URLs
- Invalid environment values are rejected (must be `dev`, `staging`, or `prod`)
- Type validation ensures integers for `MAX_WORKERS`, `DB_POOL_SIZE`, etc.

**See `.env.example` for complete configuration options including legacy WDH_-prefixed settings.**

## CI/CD Workflow

The GitHub Actions pipeline in `.github/workflows/ci.yml` enforces all Story 1.2 acceptance criteria:

1. **Quality Gate (`ruff-lint`, `ruff-format`, `mypy`)** – matrix job that runs the three quality gates in parallel on Python 3.10 using `uv run`. Dependency caching (`~/.cache/uv`) and restored `.mypy_cache` keep execution under the two-minute budget, and every step emits a `::notice::... completed in Ns` annotation for quick timing reviews.
2. **Pytest Suite** – executes `uv run pytest -v` so the smoke/unit tests created in Story 1.1 block merges on failure.
3. **Secret Scan** – runs `gitleaks/gitleaks-action@v2` with `--log-opts="--all"` so every commit in a pull request is scanned before merge.

### Interpreting CI failures

- `Quality Gate (ruff-lint)`: Fix lint errors with `uv run ruff check src/ --fix` (CI will show the failing files).
- `Quality Gate (ruff-format)`: Run `uv run ruff format src/` locally; push the formatted files and re-run CI.
- `Quality Gate (mypy)`: Execute `uv run mypy src/ --strict` to see the same strict-mode diagnostics CI enforces.
- `Pytest Suite`: Re-run `uv run pytest -v`; the job prints a runtime notice so you can spot slow suites quickly.
- `Secret Scan`: Review the gitleaks findings in the job log, rotate exposed credentials, and force-push a fixed commit.

### Local secret scanning

To mirror the CI gitleaks job locally, run:

```bash
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:latest detect --redact --source /repo --log-opts="--all"
```

If Docker is unavailable, download the latest gitleaks release and execute `gitleaks detect --redact --source .`.

### Optional pre-commit hooks

While not required, adding a pre-commit workflow keeps local changes aligned with CI. After installing [`pre-commit`](https://pre-commit.com/):

1. Create `.pre-commit-config.yaml` with hooks for Ruff (lint + format) and mypy, for example:

   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.7.0
       hooks:
         - id: ruff
         - id: ruff-format
     - repo: https://github.com/pre-commit/mirrors-mypy
       rev: v1.11.2
       hooks:
         - id: mypy
           args: [--strict, src/]
   ```

2. Install hooks with `pre-commit install`.
3. Run `pre-commit run --all-files` before opening a PR to catch the same issues the CI pipeline enforces.

### Coding Standards

**Naming Conventions (PEP 8):**
- Python files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Database tables: `lowercase_snake_case`

**Type Hints:**
- 100% type coverage required for all public functions
- Use mypy strict mode for enforcement

## Architecture Principles

### Clean Architecture Boundaries

The project enforces strict architectural boundaries:

1. **Domain layer** has NO dependencies on outer layers
2. **I/O layer** may depend on domain layer
3. **Orchestration layer** wires together domain + I/O
4. Dependencies flow inward: `orchestration/` → `io/` → `domain/`

For a detailed matrix of responsibilities, medallion mapping, and the
Story 1.6 `transform_annuity_data` dependency-injection example, see
`docs/architecture-boundaries.md`. That document also cites the Story 1.5
pipeline contracts (`domain/pipelines/{core,types}.py`), Story 1.4 settings
singleton, and Story 1.3 structlog helpers so future stories reference the same
infrastructure instead of recreating it.

🚧 **Boundary guardrail:** `uv run ruff check` now fails with `TID251` if any
`work_data_hub/domain` module imports `work_data_hub.io` or
`work_data_hub.orchestration`. The lint configuration automatically exempts the
outer layers, so a clean lint run is proof that Story 1.6 dependency rules hold.

### Non-Functional Requirements

**Maintainability:**
- 100% type safety enforced by mypy
- All public functions have type hints
- Comprehensive test coverage

**Performance:**
- Fast dependency management with uv
- Optimized data processing with Pandas
- Efficient validation with Pydantic

**Team Handoff Ready:**
- Clear separation of concerns
- Modern Python tooling
- Comprehensive documentation

## Database Migrations

- Alembic scripts live under `io/schema/migrations/` and are configured via the
  root `alembic.ini`, which loads the canonical connection string from
  `work_data_hub.config`.
- Use `python scripts/db_setup.py --seed` to run `alembic upgrade head` and
  optionally load `io/schema/fixtures/test_data.sql` for local smoke tests.
- Integration tests can depend on the `test_db_with_migrations` fixture defined
  in `tests/conftest.py`; it provisions a temporary SQLite database and applies
  the latest migrations automatically.
- Refer to `docs/database-migrations.md` for the complete workflow, naming
  conventions, and troubleshooting steps introduced in Story 1.7.

## Project Status

This project is under active development. See `docs/sprint-artifacts/sprint-status.yaml` for current progress across all epics and stories.

## License

[Your License Here]

## Contributing

[Contributing guidelines if applicable]
