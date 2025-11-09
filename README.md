# WorkDataHub

[![CI](https://github.com/LINSUISHENG034/WorkDataHub/actions/workflows/ci.yml/badge.svg)](https://github.com/LINSUISHENG034/WorkDataHub/actions/workflows/ci.yml)

A modernized data processing platform built with Clean Architecture principles, featuring type-safe Python 3.10+, advanced validation frameworks, and Dagster orchestration.

## Project Overview

WorkDataHub is a comprehensive data engineering platform designed to process, validate, and transform business data with enterprise-grade reliability. The platform follows Clean Architecture patterns to ensure maintainability, testability, and separation of concerns across all layers.

## Directory Structure

The project follows Clean Architecture with clear layer separation:

```
src/work_data_hub/
├── domain/              # Pure business logic (no external dependencies)
│   ├── pipelines/       # Core pipeline framework
│   └── ...              # Domain models and business rules
├── io/                  # Data access layer
│   ├── readers/         # Excel and file readers
│   ├── loader/          # PostgreSQL loading framework
│   └── connectors/      # File discovery and external connectors
├── orchestration/       # Dagster jobs and schedules
├── cleansing/           # Registry-driven data cleansing rules
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
- Pure business logic and transformations
- 100% testable without external services
- NO imports from `io/` or `orchestration/` layers
- Contains pipeline framework, domain models, and business rules

**I/O Layer** (`io/`)
- File reading, database writes, external API calls
- May import from `domain/` layer
- Handles all infrastructure concerns

**Orchestration Layer** (`orchestration/`)
- Dagster job definitions and schedule triggers
- Wires together `domain/` and `io/` components
- Top-level layer that can import from all other layers

**Cleansing Layer** (`cleansing/`)
- Reusable data cleansing rules using registry pattern
- Validation and normalization logic

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

4. **Verify installation:**
   ```bash
   # Run tests to verify setup
   pytest tests/unit -v
   ```

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

### Code Quality

```bash
# Run type checking
uv run mypy src/ --strict

# Run linting
uv run ruff check src/

# Auto-fix linting issues (only when needed)
uv run ruff check src/ --fix

# Format code
uv run ruff format src/

# Format check (CI equivalent)
uv run ruff format --check src/
```

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

## Project Status

This project is under active development. See `docs/sprint-status.yaml` for current progress across all epics and stories.

## License

[Your License Here]

## Contributing

[Contributing guidelines if applicable]
