# WorkDataHub

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
# Run all tests
pytest

# Run only unit tests (fast)
pytest -m unit

# Run integration tests
pytest -m integration

# Run with coverage
pytest --cov=src/work_data_hub --cov-report=html
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
mypy src/

# Run linting
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .
```

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
