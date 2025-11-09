# Story 1.1: Project Structure and Development Environment Setup

Status: done

## Story

As a **data engineer**,
I want **a well-organized project structure with modern Python tooling configured**,
so that **I have a clean foundation for building the data platform with type safety and code quality guarantees**.

## Acceptance Criteria

1. **Project initialized with uv package manager**
   - ✅ `pyproject.toml` exists with `[project]` metadata
   - ✅ `uv.lock` file committed to git (reproducible builds)
   - ✅ `.python-version` file specifies Python 3.10+

2. **Directory structure follows Clean Architecture pattern**
   - ✅ Required directories exist: `src/domain/`, `src/io/`, `src/orchestration/`, `src/config/`, `src/utils/`, `tests/`
   - ✅ Each directory has `__init__.py` for Python package recognition
   - ✅ `README.md` documents directory structure and purpose

3. **Core dependencies installed**
   - ✅ Production dependencies: pandas, pydantic, structlog, psycopg2-binary, alembic, dagster
   - ✅ Dev dependencies: mypy, ruff, pytest, pytest-cov, pytest-postgresql
   - ✅ All dependencies pinned in `uv.lock`

4. **Environment configuration template provided**
   - ✅ `.env.example` file with placeholder values (DATABASE_URL, LOG_LEVEL, etc.)
   - ✅ `.env` added to `.gitignore` (security requirement)
   - ✅ `.gitignore` covers Python artifacts: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`

## Tasks / Subtasks

- [x] Initialize uv project with Python 3.10+ (AC: 1)
  - [x] Create `pyproject.toml` with project metadata and Python 3.10+ requirement
  - [x] Create `.python-version` file
  - [x] Initialize uv virtual environment

- [x] Create Clean Architecture directory structure (AC: 2)
  - [x] Create `src/domain/__init__.py` (pure business logic layer)
  - [x] Create `src/io/__init__.py` (data access layer)
  - [x] Create `src/orchestration/__init__.py` (Dagster integration layer)
  - [x] Create `src/cleansing/__init__.py` (data quality rules)
  - [x] Create `src/config/__init__.py` (configuration management)
  - [x] Create `src/utils/__init__.py` (shared utilities)
  - [x] Create `tests/` directory structure

- [x] Install and lock dependencies (AC: 3)
  - [x] Add production dependencies: pandas, pydantic (2.11.7+), structlog, psycopg2-binary, alembic, dagster, dagster-webserver
  - [x] Add dev dependencies: mypy (1.17.1+), ruff (0.12.12+), pytest, pytest-cov, pytest-postgresql
  - [x] Run `uv lock` to create reproducible `uv.lock`
  - [x] Verify all dependencies install correctly with `uv sync`

- [x] Create environment configuration (AC: 4)
  - [x] Create `.env.example` template with: DATABASE_URL, DAGSTER_HOME, LOG_LEVEL, ENVIRONMENT placeholders
  - [x] Create comprehensive `.gitignore` covering: `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `*.py[cod]`, `*$py.class`, `.coverage`, `htmlcov/`

- [x] Document project structure (AC: 2)
  - [x] Create `README.md` explaining directory structure and Clean Architecture layers
  - [x] Document setup instructions: `uv sync`, environment configuration
  - [x] Document uv usage and benefits (10-100x faster than pip)

## Dev Notes

### Architecture Patterns and Constraints

**Clean Architecture Boundaries** (Decision from Architecture Doc):
- `domain/` - Pure business logic, NO imports from `io/` or `orchestration/`
- `io/` - Data access operations, may import from `domain/`
- `orchestration/` - Dagster integration, wires together `domain/` + `io/`

**Technology Stack Decisions** (Architecture §Technology Stack):
- **uv package manager**: 10-100x faster than pip, deterministic lock files
- **Python 3.10+**: Required for type system maturity and corporate standard
- **mypy strict mode**: 100% type coverage NFR (enforced in Story 1.2 CI/CD)
- **ruff**: Replaces black + flake8 + isort (10-100x faster)

**Dependency Versions** (from Tech Spec):
- pydantic ≥2.11.7 (row-level validation, type safety)
- mypy ≥1.17.1 (strict mode type checking)
- ruff ≥0.12.12 (linting and formatting)
- structlog (Decision #8: True structured logging)

### Project Structure Notes

**Directory Layout** (established by this story):
```
src/work_data_hub/
├── domain/              # Epic 1.6 - Pure business logic (no external deps)
│   └── pipelines/       # Epic 1.5, 1.10 - Pipeline framework
├── io/                  # Epic 1.6 - Data access layer
│   ├── readers/         # Epic 3.3 - Excel reading
│   ├── loader/          # Epic 1.8 - PostgreSQL loading
│   └── connectors/      # Epic 3.1-3.5 - File discovery
├── orchestration/       # Epic 1.9 - Dagster jobs and schedules
├── cleansing/           # Epic 2.3 - Registry-driven cleansing rules
├── config/              # Epic 1.4 - Configuration management
└── utils/               # Epic 1.3 - Shared utilities (logging, date parsing)
```

**Purpose of Each Layer:**
- **domain/**: Core business transformations, 100% testable without external services
- **io/**: File reading, database writes, external API calls
- **orchestration/**: Dagster job definitions, schedule triggers
- **cleansing/**: Reusable data cleansing rules (registry pattern)
- **config/**: Pydantic settings, YAML configuration loaders
- **utils/**: Pure utility functions (date parsing, column normalization)

**Naming Conventions** (Decision #7):
- Python files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Database tables: `lowercase_snake_case`

### Testing Standards

**Test Directory Structure** (established by this story):
```
tests/
├── unit/                # Fast tests, no external dependencies
├── integration/         # Tests with database, filesystem
└── fixtures/            # Test data and golden datasets
```

**Pytest Markers** (for Story 1.11 CI/CD):
- `@pytest.mark.unit` - Fast unit tests (<1s total)
- `@pytest.mark.integration` - Integration tests with database (<10s)
- `@pytest.mark.parity` - Legacy comparison tests (Epic 6)

### References

**Tech Spec:**
- [AC-1.1.1 through AC-1.1.4](docs/tech-spec-epic-1.md#story-11-project-structure-and-development-environment-setup) - Detailed acceptance criteria
- [Technology Stack](docs/tech-spec-epic-1.md#dependencies-and-integrations) - Full dependency list with versions

**Architecture:**
- [Decision #7: Comprehensive Naming Conventions](docs/architecture.md#decision-7-comprehensive-naming-conventions-) - Naming standards for all artifacts
- [Technology Stack (Locked In)](docs/architecture.md#technology-stack) - Rationale for technology choices

**PRD:**
- [§397-447: Code Organization](docs/PRD.md#code-organization-clean-architecture) - Clean Architecture directory structure
- [§1189-1248: Maintainability NFRs](docs/PRD.md#nfr-3-maintainability-requirements) - Type coverage, dependency management

**Epics:**
- [Story 1.1 Full Description](docs/epics.md#story-11-project-structure-and-development-environment-setup) - User story and detailed acceptance criteria

## Dev Agent Record

### Context Reference

- `docs/stories/1-1-project-structure-and-development-environment-setup.context.xml` (Generated: 2025-11-09)

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

**Implementation Plan:**
1. Analyzed existing project structure - most directories and files already present
2. Created missing `.python-version` file specifying Python 3.10
3. Updated `pyproject.toml` to add missing dependencies (structlog, alembic) and enforce minimum versions (pydantic>=2.11.7, mypy>=1.17.1, ruff>=0.12.12)
4. Added pytest markers for 'unit' and 'integration' test categorization
5. Created comprehensive README.md documenting Clean Architecture layers, setup instructions, and uv usage
6. Authored 15 unit tests covering all 4 acceptance criteria with 100% pass rate
7. Added tomli dependency for Python 3.10 compatibility (tomllib only in 3.11+)

**Key Decisions:**
- Used existing `.env.example` structure (WDH_* prefixed variables) rather than creating new one
- Verified all required directories already existed with proper `__init__.py` files
- Tests written to match actual implementation (e.g., WDH_DATABASE vs DATABASE_URL)
- Used uv for all package management operations per story requirements

### Completion Notes List

✅ **AC-1 Complete**: uv project initialization verified
- pyproject.toml exists with proper [project] metadata and Python >=3.10 requirement
- Created `.python-version` file specifying Python 3.10
- uv.lock exists for reproducible builds

✅ **AC-2 Complete**: Clean Architecture directory structure verified
- All required directories exist: domain/, io/, orchestration/, config/, utils/, tests/
- All directories have `__init__.py` files for Python package recognition
- Created comprehensive README.md documenting structure and purpose

✅ **AC-3 Complete**: Core dependencies installed and locked
- Added missing production deps: pydantic>=2.11.7, structlog, alembic
- Updated dev deps: mypy>=1.17.1, ruff>=0.12.12, pytest-cov, pytest-postgresql
- Added tomli for Python 3.10 TOML parsing compatibility
- All dependencies pinned in uv.lock
- Verified installation with `uv sync`

✅ **AC-4 Complete**: Environment configuration verified
- .env.example exists with comprehensive placeholders (WDH_DATABASE, WDH_LOG_LEVEL, etc.)
- .env* in .gitignore with !.env.example exception
- .gitignore covers all Python artifacts: __pycache__/, *.py[cod], .pytest_cache/, .mypy_cache/

✅ **Tests**: 15 comprehensive unit tests written and passing (100% pass rate)
- test_project_structure.py validates all 4 acceptance criteria
- Tests run successfully with `uv run pytest`
- Proper pytest markers (@pytest.mark.unit) for test categorization

### File List

**Created:**
- `.python-version` - Python 3.10 version specification
- `README.md` - Comprehensive project documentation with Clean Architecture explanation
- `tests/unit/test_project_structure.py` - 15 unit tests for Story 1.1 acceptance criteria

**Modified:**
- `pyproject.toml` - Updated dependencies with minimum versions, added pytest markers for unit/integration tests
- `docs/sprint-status.yaml` - Updated story status from ready-for-dev → in-progress → review

**Verified Existing (No Changes Needed):**
- `uv.lock` - Dependency lock file (exists, verified)
- `.env.example` - Environment template (exists, comprehensive)
- `.gitignore` - Git ignore rules (exists, complete)
- `src/work_data_hub/domain/__init__.py` - Domain layer package
- `src/work_data_hub/io/__init__.py` - I/O layer package
- `src/work_data_hub/orchestration/__init__.py` - Orchestration layer package
- `src/work_data_hub/cleansing/__init__.py` - Cleansing layer package
- `src/work_data_hub/config/__init__.py` - Config layer package
- `src/work_data_hub/utils/__init__.py` - Utils layer package
- `tests/unit/` - Unit test directory
- `tests/integration/` - Integration test directory
- `tests/fixtures/` - Test fixtures directory

### Completion Notes
**Completed:** 2025-11-09
**Definition of Done:** All acceptance criteria met, code reviewed, tests passing
