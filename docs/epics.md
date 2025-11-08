# WorkDataHub - Epic Breakdown

**Author:** Link
**Date:** 2025-11-09
**Project Level:** Level 2-4 (Medium Complexity)
**Target Scale:** Internal Data Platform (6+ domains, 50K rows monthly)

---

## Overview

This document provides the complete epic and story breakdown for WorkDataHub, decomposing the requirements from the [PRD](./PRD.md) into implementable stories.

## Epic Structure Summary

**Phase 1: MVP (Prove the Pattern)**

1. **Epic 1: Foundation & Core Infrastructure** - Establish the foundational platform that all subsequent work depends on
2. **Epic 2: Multi-Layer Data Quality Framework** - Build the Bronze → Silver → Gold validation system
3. **Epic 3: Intelligent File Discovery & Version Detection** - Eliminate manual file selection every month
4. **Epic 4: Annuity Performance Domain Migration (MVP)** - Prove the Strangler Fig pattern on highest-complexity domain
5. **Epic 5: Company Enrichment Service** - Augment data with enterprise company IDs
6. **Epic 6: Testing & Validation Infrastructure** - Guarantee 100% parity with legacy system
7. **Epic 7: Orchestration & Automation** - "Set it and forget it" monthly processing
8. **Epic 8: Monitoring & Observability** - Understand what's happening and debug failures quickly

**Phase 2: Growth (Scale the Pattern)**

9. **Epic 9: Growth Domains Migration** - Complete legacy system retirement across all 6+ domains
10. **Epic 10: Configuration Management & Operational Tooling** - Declare behavior via config, empower business users

**Sequencing:** Foundation (1-3) → Enrichment (5, parallel) → Testing (6) → Annuity Migration (4) → Automation (7-8) → Scale (9-10)

---

## Epic 1: Foundation & Core Infrastructure

**Goal:** Establish the foundational platform that enables all subsequent domain migrations. This epic creates the "rails" that all pipelines will run on - shared frameworks, clean architecture boundaries, database infrastructure, and development tooling that ensures type safety and maintainability.

**Business Value:** Without this foundation, every domain would reinvent the wheel. This epic enables the "add a domain in <4 hours" promise by providing reusable, battle-tested infrastructure.

**Updated after Dependency Mapping:** Epic expanded from 6 to 11 stories with improved sequencing - CI/CD moved earlier, pipeline framework split into simple/advanced, database schema management added, logging and configuration management added for consistency.

---

### Story 1.1: Project Structure and Development Environment Setup

As a **data engineer**,
I want **a well-organized project structure with modern Python tooling configured**,
So that **I have a clean foundation for building the data platform with type safety and code quality guarantees**.

**Acceptance Criteria:**

**Given** I am starting the WorkDataHub project from scratch
**When** I set up the initial project structure
**Then** I should have:
- Python 3.10+ verified: `python --version` shows 3.10 or higher
- Directory structure following Clean Architecture (`src/work_data_hub/` with `domain/`, `io/`, `orchestration/`, `cleansing/`, `config/`, `utils/`)
- `pyproject.toml` configured with Python 3.10+ requirement
- Dependencies installed with specific versions: `pandas==2.1.3`, `dagster==1.5.9`, `pydantic==2.5.0`, `pandera==0.18.0`, `pytest==7.4.3`, `mypy==1.7.1`, `ruff==0.1.6`, `psycopg2-binary==2.9.9`
- Virtual environment configured (Poetry recommended, or venv)
- `.env.example` template with critical variables: `DATABASE_URL`, `DAGSTER_HOME`, `LOG_LEVEL`, `ENVIRONMENT` (dev/staging/prod)
- `.gitignore` configured to exclude `.env`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `*.pyc`

**And** When I run `mypy src/` it should complete without errors (empty codebase passes)
**And** When I run `ruff check src/` it should pass
**And** When I run `pytest` it should discover and run tests (0 tests initially)

**Prerequisites:** None (first story)

**Technical Notes:**
- Use `uv` for dependency+venv management (project standard) - faster than Poetry/pip
- Initialize with: `uv venv && uv pip install -r requirements.txt`
- Pin EXACT versions for reproducibility: `pandas==2.1.3` not `pandas>=2.1`
- Include development dependencies: mypy, ruff, pytest, pytest-cov, pytest-postgresql
- Set up pre-commit hooks (optional but recommended)
- Create `scripts/` directory for helper scripts (db setup, etc.)
- `uv` benefits: faster installs, better dependency resolution, compatible with pip
- Reference: PRD §397-439 (Code Organization), §1189-1248 (Maintainability NFRs)

---

### Story 1.2: Basic CI/CD Pipeline Setup

As a **data engineer**,
I want **automated quality checks configured from the start**,
So that **type errors and linting issues are caught immediately as I build the infrastructure**.

**Acceptance Criteria:**

**Given** I have the project structure from Story 1.1
**When** I configure basic CI/CD pipeline (GitHub Actions, GitLab CI, or local pre-commit)
**Then** I should have:
- CI runs on: all pull requests, main branch, and release/* branches
- CI job that runs `mypy src/` with strict mode (blocks on errors, target: <30 seconds)
- CI job that runs `ruff check src/` and `ruff format --check src/` (blocks on violations, target: <20 seconds)
- CI job that runs `pytest` (will pass with 0 tests initially, target: <10 seconds)
- Total execution time: <90 seconds for basic checks
- Dependency caching enabled: pip packages (~/.cache/pip), mypy cache (.mypy_cache)
- Clear failure messages pointing to specific file and line number

**And** When I intentionally introduce a type error in any subsequent story
**Then** CI should fail immediately with error pointing to exact location

**And** When CI fails on main branch
**Then** Provides rollback instructions and alerts team

**And** When all checks pass
**Then** CI reports success and allows merge

**Prerequisites:** Story 1.1 (project structure)

**Technical Notes:**
- Set up basic checks NOW, expand with integration tests in Story 1.11
- Use GitHub Actions if using GitHub, or equivalent CI platform
- Cache strategy: `actions/cache@v3` for pip, restore from cache key based on requirements hash
- Run mypy and ruff in parallel for faster feedback (GitHub Actions: matrix strategy)
- Time budget per check helps identify slowdowns early
- This enables quality gates for Stories 1.3-1.10 development
- Reference: PRD §1224-1236 (NFR-3.4: Code Review & CI/CD)

---

### Story 1.3: Structured Logging Framework

As a **data engineer**,
I want **a centralized, structured logging system configured from the start**,
So that **all subsequent stories use consistent logging and I can debug issues with rich context**.

**Acceptance Criteria:**

**Given** I have CI/CD from Story 1.2
**When** I implement logging framework in `utils/logging.py`
**Then** I should have:
- Structured JSON logging using `structlog` or Python's `logging` with JSON formatter
- Log levels configured: DEBUG (development), INFO (production), WARNING, ERROR
- Logger factory function: `get_logger(name: str) -> Logger` for consistent logger creation
- Standard log fields: timestamp (ISO 8601), level, logger_name, message, context (dict)
- Log rotation: daily rotation with 30-day retention (`logging.handlers.TimedRotatingFileHandler`)
- Output targets: stdout (always) + file (`logs/workdatahub-YYYYMMDD.log`, production only)

**And** When I log a message with context
**Then** Output includes structured fields:
```json
{
  "timestamp": "2025-11-09T10:30:00Z",
  "level": "INFO",
  "logger": "domain.pipeline",
  "message": "Pipeline step completed",
  "context": {"step_name": "validate_data", "duration_ms": 1250, "row_count": 1000}
}
```

**And** When log level set to INFO
**Then** DEBUG messages are suppressed (not logged)

**And** When exception occurs
**Then** Logger captures stack trace automatically

**Prerequisites:** Story 1.2 (CI/CD validates logging code)

**Technical Notes:**
- Use `structlog` for true structured logging (recommended) or `python-json-logger`
- Configure via environment variable: `LOG_LEVEL` from `.env`
- Add helper methods: `logger.info_with_context(message, **kwargs)` for easy context injection
- All subsequent stories MUST use this logger (not print statements)
- Reference: PRD §1033-1045 (FR-8.1: Structured Logging), prevents inconsistent logging across stories

---

### Story 1.4: Configuration Management Framework

As a **data engineer**,
I want **centralized configuration loaded from environment variables with validation**,
So that **I avoid duplicating `os.getenv()` calls and catch missing config early**.

**Acceptance Criteria:**

**Given** I have logging from Story 1.3
**When** I implement configuration in `config/settings.py`
**Then** I should have:
- Pydantic `Settings` model with all required configuration fields
- Environment variable loading with type validation and defaults
- Required fields: `DATABASE_URL`, `ENVIRONMENT` (dev/staging/prod)
- Optional fields with defaults: `LOG_LEVEL` (INFO), `DAGSTER_HOME` (~/.dagster), `MAX_WORKERS` (4)
- Validation on startup: missing required vars raise clear error before any processing
- Singleton pattern: `get_settings()` returns cached instance (load once, reuse everywhere)

**And** When application starts with missing `DATABASE_URL`
**Then** Raises `ValidationError` with message: "DATABASE_URL is required but not set in environment"

**And** When `ENVIRONMENT=production` and `DATABASE_URL` is not PostgreSQL connection string
**Then** Raises validation error (prevents accidentally using SQLite in production)

**And** When I call `get_settings()` multiple times
**Then** Returns same cached instance (not re-parsing environment variables)

**Prerequisites:** Story 1.3 (logging for config load errors), Story 1.2 (CI validates config code)

**Technical Notes:**
- Use Pydantic `BaseSettings` for automatic `.env` file loading and validation
- Add custom validators: `@validator('DATABASE_URL')` to check PostgreSQL URL format in production
- Configuration loaded in `config/__init__.py`: `settings = get_settings()`
- All subsequent stories import: `from config import settings`
- Document all environment variables in README.md
- Example:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
```
- Reference: PRD §998-1030 (FR-7: Configuration Management), prevents config duplication

---

### Story 1.5: Shared Pipeline Framework Core (Simple)

As a **data engineer**,
I want **a simple, synchronous pipeline execution framework**,
So that **I can chain transformation steps without complexity, proving the pattern works before adding advanced features**.

**Acceptance Criteria:**

**Given** I have logging and config from Stories 1.3-1.4
**When** I implement basic pipeline framework in `domain/pipelines/core.py`
**Then** I should have:
- `TransformStep` protocol defining strict contract:
  ```python
  class TransformStep(Protocol):
      def execute(self, data: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
          """Transform data and return modified DataFrame"""
  ```
- `PipelineContext` dataclass with standard fields: `pipeline_name: str`, `execution_id: str`, `timestamp: datetime`, `config: dict`
- `Pipeline` class with `add_step(step)` and `run(initial_data)` methods
- Synchronous sequential execution: step N completes before step N+1 starts
- Simple error handling: stop on first error, raise with clear message showing which step failed
- Basic metrics: total execution time, step count
- Metrics logged to stdout (JSON format via Story 1.3 logger) and returned in `PipelineResult` object

**And** When I create a test pipeline with 3 steps (add field, filter rows, calculate sum)
**Then** Each step executes in order with correct input/output chaining

**And** When a step raises an exception
**Then** Pipeline halts with error showing step name, step index, and original exception

**And** When pipeline completes successfully
**Then** Returns `PipelineResult(success=True, output_data=df, metrics={...}, errors=[])`

**Prerequisites:** Story 1.4 (config for pipeline settings), Story 1.3 (logging for metrics), Story 1.2 (CI validates code)

**Technical Notes:**
- Keep this SIMPLE: no async, no parallel, no retries (that's Story 1.10)
- Focus on: sequential execution, clear errors, basic metrics
- Domain-agnostic: no business logic here
- Add unit tests for framework (pytest fixtures for test steps)
- Concrete example of a step:
  ```python
  class AddPipelineIdStep:
      def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
          df = df.copy()  # Don't mutate input
          df['pipeline_run_id'] = context.execution_id
          return df
  ```
- Prove pattern works before adding complexity in Story 1.10
- Reference: PRD §804-816 (FR-3.1: Pipeline Framework Execution)

---

### Story 1.6: Clean Architecture Boundaries Enforcement

As a **data engineer**,
I want **strict separation between domain logic, I/O operations, and orchestration**,
So that **business logic is testable without external dependencies and the codebase is maintainable**.

**Acceptance Criteria:**

**Given** I have the simple pipeline framework from Story 1.5
**When** I create placeholder modules for each layer
**Then** I should have:
- `domain/` package with `__init__.py` that imports NOTHING from `io/` or `orchestration/`
- `io/` package with modules: `readers/excel_reader.py`, `loader/warehouse_loader.py`, `connectors/file_connector.py`
- `orchestration/` package with modules: `jobs.py`, `ops.py`, `schedules.py`, `sensors.py`
- Domain layer defines Protocol interfaces (use `typing.Protocol`), I/O layer provides concrete implementations
- Placeholder files with docstrings explaining each layer's purpose

**And** When I run mypy with strict checking via Story 1.2 CI
**Then** It should enforce that `domain/` has no imports from `io/` or `orchestration/`

**And** When I create a sample domain service function
**Then** It should demonstrate dependency injection pattern:
```python
# domain/annuity_performance/service.py
from typing import Protocol, Optional, List, Dict

class EnrichmentProtocol(Protocol):
    def enrich(self, company_name: str) -> str: ...

def transform_annuity_data(
    rows: List[Dict],
    enrichment_service: Optional[EnrichmentProtocol] = None  # <- DI
) -> List[Dict]:
    # Pure transformation logic, testable without real service
    return [transform_row(r, enrichment_service) for r in rows]
```

**And** When README.md is updated
**Then** It includes architecture diagram showing layer dependencies and import rules

**Prerequisites:** Story 1.5 (pipeline framework exists to enforce boundaries around)

**Technical Notes:**
- Use dependency injection: pass I/O services as parameters to domain functions
- Domain layer should be pure Python (standard library + pandas/pydantic only)
- Add `.pylintrc` rule to block `io.*` imports in `domain/` (belt-and-suspenders with mypy)
- Document dependency rules clearly in README
- Reference: PRD §397-447 (Clean Architecture), §649-696 (Dependency Injection Pattern)

---

### Story 1.7: Database Schema Management Framework

As a **data engineer**,
I want **a systematic way to create and evolve database schemas**,
So that **pipeline tests don't fail due to missing tables and production schema changes are tracked**.

**Acceptance Criteria:**

**Given** I have architecture boundaries from Story 1.6
**When** I set up database schema management
**Then** I should have:
- Schema migration tool configured: Alembic (recommended) OR raw SQL scripts in `io/schema/migrations/` if Alembic too heavy
- Initial migration creating core tables: `pipeline_executions` (audit log), `data_quality_metrics`
- Schema follows PostgreSQL conventions: `lowercase_snake_case` for tables/columns (not CamelCase)
- Migration command: `alembic upgrade head` applies all pending migrations
- Rollback support: `alembic downgrade -1` reverts last migration
- Schema versioning tracked in database: `alembic_version` table
- Migration file naming: `YYYYMMDD_HHMM_description.py` (timestamp prevents multi-developer conflicts)

**And** When I run migrations on an empty PostgreSQL database
**Then** All core tables should be created with correct schema

**And** When test database is created
**Then** Migrations run automatically and database seeded with minimal fixture data for testing

**And** When Story 1.8 database tests run
**Then** Test database setup includes running migrations first

**And** When future stories add domain tables (e.g., `annuity_performance`)
**Then** Each table has corresponding migration file with timestamp

**Prerequisites:** Story 1.6 (know where schema files live: `io/schema/migrations/`)

**Technical Notes:**
- Use Alembic for migration management (industry standard with SQLAlchemy)
- Alternative: Flyway or raw SQL scripts if team prefers simpler approach
- Store migrations in `io/schema/migrations/` (I/O layer concern)
- Add `alembic.ini` configuration file
- Document migration workflow in README: how to create, apply, and rollback
- Create helper script: `scripts/db_setup.sh` for fresh database init
- Test migrations in CI (Story 1.2 CI runs migrations on temp database)
- Seed data: create `io/schema/fixtures/test_data.sql` for test database
- Reference: PRD §879-906 (FR-4: Database Loading), prevents implicit dependency

---

### Story 1.8: PostgreSQL Connection and Transactional Loading Framework

As a **data engineer**,
I want **a reliable database connection framework with transactional guarantees**,
So that **I can safely load DataFrames to PostgreSQL without risk of partial data corruption**.

**Acceptance Criteria:**

**Given** I have schema management from Story 1.7
**When** I implement `io/loader/warehouse_loader.py`
**Then** I should have:
- `WarehouseLoader` class with methods: `connect()`, `load_dataframe()`, `disconnect()`
- Connection pooling: min=2, max=10 connections (configurable via `DB_POOL_SIZE` env var)
- Transactional bulk loading: all-or-nothing writes with rollback on error
- Batch inserts in chunks of 1000 rows (balance transaction size vs. speed)
- Parameterized queries only (no SQL string concatenation)
- `get_allowed_columns(table_name)` method that queries database schema
- `project_columns(df, table_name)` method that filters DataFrame to allowed columns
- When >5 columns removed by projection, log WARNING (potential data loss indicator)
- Retry logic: on database connection failures, retry 3 times with exponential backoff

**And** When I load a test DataFrame to a PostgreSQL table
**Then** All rows should be inserted within a single transaction

**And** When loading fails mid-batch (simulated error)
**Then** The entire batch should rollback (no partial data in database)

**And** When DataFrame contains extra columns not in database table
**Then** Loader automatically projects to allowed columns and logs removed column names

**And** When database connection fails transiently
**Then** Loader retries 3 times (backoff: 1s, 2s, 4s) before raising exception

**Prerequisites:** Story 1.7 (tables exist from migrations), Story 1.6 (architecture boundaries)

**Technical Notes:**
- Use psycopg2 or SQLAlchemy for PostgreSQL connection
- Connection string from `settings.DATABASE_URL` (Story 1.4 config)
- Context manager pattern for transaction safety: `with loader.transaction():`
- Integration tests using temporary test database (created by Story 1.7 migrations)
- Support upsert: `ON CONFLICT (pk_cols) DO UPDATE`
- Batch size configurable via `DB_BATCH_SIZE` env var (default 1000)
- Connection pool prevents connection exhaustion on parallel loads
- Reference: PRD §879-906 (FR-4: Database Loading), §1252-1277 (Security NFRs)

---

### Story 1.9: Dagster Orchestration Setup

As a **data engineer**,
I want **Dagster configured as the orchestration layer**,
So that **I can define, schedule, and monitor data pipelines through a unified interface**.

**Acceptance Criteria:**

**Given** I have the database loader from Story 1.8
**When** I set up Dagster in `orchestration/`
**Then** I should have:
- Dagster 1.5+ installed and configured with workspace file (`workspace.yaml`)
- Required environment variables documented: `DAGSTER_HOME` (metadata storage path), `DAGSTER_POSTGRES_URL` (optional, for production)
- Sample job definition in `orchestration/jobs.py` using simple pipeline framework from Story 1.5
- Concrete sample job: read CSV → validate with Pydantic → write to database using Story 1.8 loader
- Sample op (operation) in `orchestration/ops.py` that calls domain service
- Dagster UI accessible at `http://localhost:3000`
- Repository definition that exposes jobs to Dagster
- Shutdown instructions: `dagster dev` process stopped via Ctrl+C

**And** When I launch the Dagster UI via `dagster dev`
**Then** I should see the sample job listed and be able to run it manually

**And** When the sample job executes
**Then** I should see execution logs, step-by-step progress, success/failure status, and duration

**And** When a job fails
**Then** Dagster should capture the exception and display full stack trace in UI

**And** When using PostgreSQL backend for Dagster metadata storage
**Then** Configure via `DAGSTER_POSTGRES_URL` environment variable

**Prerequisites:** Story 1.8 (database framework), Story 1.5 (pipeline framework to orchestrate)

**Technical Notes:**
- Use Dagster 1.5+ for latest features
- Organize: `orchestration/__init__.py` exposes `Definitions` object
- Keep ops thin (delegate to domain services from Story 1.6)
- Local development: SQLite storage (default)
- Production: PostgreSQL backend via `DAGSTER_POSTGRES_URL`
- Add schedule and sensor placeholders (activated in Epic 7)
- Sample job concrete example:
  ```python
  @job
  def sample_pipeline_job():
      raw_data = read_csv_op()
      validated = validate_op(raw_data)
      load_to_db_op(validated)
  ```
- Reference: PRD §909-949 (FR-5: Orchestration & Automation)

---

### Story 1.10: Pipeline Framework Advanced Features

As a **data engineer**,
I want **advanced pipeline capabilities for complex scenarios**,
So that **I can handle optional enrichment, error collection, and retries without rewriting the framework**.

**Acceptance Criteria:**

**Given** I have the simple pipeline from Story 1.5 working AND at least 2 domain pipelines tested (Epic 4 Stories 4.3 + 4.5)
**When** I enhance the pipeline framework with advanced features
**Then** I should have:
- **Error handling modes:** `stop_on_error=True` (fail fast) or `False` (collect errors, continue)
- **Step immutability:** Use shallow copy for DataFrames (faster), deep copy only for nested dicts (performance vs. safety trade-off)
- **Optional steps:** `TransformStep` can return `StepSkipped` to bypass without error
- **Per-step metrics:** Duration, input/output row counts, memory usage
- **Retry logic (whitelist approach):** Retry ONLY on network timeouts, database connection errors, rate limits
- **Retry observability:** Log each retry attempt with step name, attempt number, error type, backoff delay

**And** When a pipeline has optional enrichment step and external service is down
**Then** Pipeline should log warning, skip enrichment, and continue with remaining steps

**And** When I enable collect errors mode and 10 rows fail validation
**Then** Pipeline completes successfully, returns 90 valid rows + 10 error rows with reasons

**And** When a step fails with transient error (e.g., connection timeout)
**Then** Pipeline retries up to `max_retries=3` with exponential backoff before failing

**And** When retries succeed on 2nd attempt
**Then** Logs show: "Step 'enrich_data' succeeded on retry 2/3 after NetworkTimeout"

**Prerequisites:** Story 1.5 (simple framework) + Epic 4 Stories 4.3, 4.5 (proven with 2 domain pipelines)

**Technical Notes:**
- Build on Story 1.5 foundation, maintain backward compatibility
- Add `PipelineConfig` dataclass for advanced options
- Immutability strategy: `df.copy()` for DataFrames (cheap), `copy.deepcopy()` for nested structures
- Retry classification (transient errors only):
  - ✅ Retry: `psycopg2.OperationalError`, `requests.Timeout`, `HTTPError` with 429/503 status
  - ❌ Don't retry: `ValueError`, `KeyError`, `psycopg2.IntegrityError` (data errors, not transient)
- Log all retries to Story 1.3 structured logger
- Consider async execution for I/O-bound steps (future enhancement, not MVP)
- Reference: PRD §804-816 (FR-3.1: Pipeline Framework), §1149-1172 (NFR-2.2: Fault Tolerance)

---

### Story 1.11: Enhanced CI/CD with Integration Tests

As a **data engineer**,
I want **comprehensive CI/CD checks including integration tests**,
So that **database interactions, pipeline execution, and end-to-end flows are validated before merge**.

**Acceptance Criteria:**

**Given** I have all infrastructure from Stories 1.1-1.10
**When** I enhance the CI/CD pipeline from Story 1.2
**Then** I should have:
- **Unit tests:** Fast (<30 sec), no external dependencies, run on every commit
- **Integration tests:** Complete in <3 minutes, use temporary PostgreSQL database, run on PR
- **Database provisioning:** Use `pytest-postgresql` fixture (auto-provisions temp DB) OR Docker Compose for CI
- **Coverage reporting:** Track coverage trends with per-module targets:
  - `domain/` >90% (core business logic)
  - `io/` >70% (I/O operations)
  - `orchestration/` >60% (Dagster wiring)
- **Test database setup:** Story 1.7 migrations run automatically before integration tests
- **Parallel execution:** Unit and integration tests run in parallel stages (fail fast: units first)
- **Performance regression:** Track pipeline execution time in CI, alert if >20% regression vs. baseline

**And** When integration tests run
**Then** They should:
- Create temporary test database via pytest-postgresql
- Run Story 1.7 migrations (`alembic upgrade head`)
- Execute sample pipeline end-to-end (read → transform → load)
- Validate data in database matches expectations
- Clean up test database afterward (pytest fixture teardown)

**And** When coverage drops below threshold
**Then** CI should warn but not block initially (set enforcement date 30 days out)

**And** When all checks pass (mypy, ruff, unit tests, integration tests, coverage)
**Then** PR is ready for merge

**And** When pipeline execution time increases by >20% vs. baseline
**Then** CI logs performance regression warning

**Prerequisites:** All previous stories (1.1-1.10) complete

**Technical Notes:**
- Extend Story 1.2 basic CI with additional stages
- Database provisioning options:
  - Option A: `pytest-postgresql` (simpler, in-process PostgreSQL)
  - Option B: Docker Compose with postgres service (more realistic)
- Separate test markers: `@pytest.mark.unit` vs `@pytest.mark.integration`
- Run strategy: `pytest -m unit` (fast), then `pytest -m integration` (slower)
- Add coverage badge to README (shields.io or codecov)
- Configure branch protection: require all checks pass before merge
- Total CI time target: <10 minutes (parallel execution: unit + integration in parallel)
- Performance baseline stored in CI artifacts, compared on each run
- Reference: PRD §1189-1248 (NFR-3: Maintainability Requirements)

---

## Epic 2: Multi-Layer Data Quality Framework

**Goal:** Build the Bronze → Silver → Gold validation system that catches bad data before database corruption. This epic implements multi-layered data quality gates using Pydantic (row-level) and pandera (DataFrame-level) to ensure only valid data reaches the database.

**Business Value:** Data integrity is non-negotiable. This establishes the safety net that makes fearless refactoring possible - bad source data is rejected immediately with actionable errors, preventing the "garbage in, garbage out" problem.

---

### Story 2.1: Pydantic Models for Row-Level Validation (Silver Layer)

As a **data engineer**,
I want **Pydantic v2 models that validate individual rows during transformation**,
So that **business rules are enforced consistently and invalid data is caught with clear error messages**.

**Acceptance Criteria:**

**Given** I have the pipeline framework from Epic 1
**When** I create Pydantic models for the annuity performance domain
**Then** I should have:
- `AnnuityPerformanceIn` model with loose validation (handles messy Excel input)
- `AnnuityPerformanceOut` model with strict validation (enforces business rules)
- Chinese field names matching Excel sources (e.g., `月度: Optional[Union[str, int, date]]` → `月度: date`)
- Custom validators for business rules: `@field_validator('期末资产规模')` ensures >= 0
- Clear error messages: "Row 15, field '月度': Cannot parse 'INVALID' as date, expected format: YYYYMM or YYYY年MM月"
- Validation summary: total rows processed, successful, failed with reasons

**And** When I validate 100 rows where 5 have invalid dates
**Then** Pydantic raises `ValidationError` with details for all 5 failed rows

**And** When all rows pass validation
**Then** Returns list of `AnnuityPerformanceOut` objects ready for database loading

**Prerequisites:** Epic 1 Story 1.5 (pipeline framework to integrate validators)

**Technical Notes:**
- Use Pydantic v2 for performance and better error messages
- Separate Input/Output models enables progressive validation (loose → strict)
- Custom validator example:
  ```python
  from pydantic import BaseModel, field_validator, ValidationError

  class AnnuityPerformanceOut(BaseModel):
      月度: date  # Strict: must be valid date
      计划代码: str = Field(min_length=1)
      期末资产规模: float = Field(ge=0)  # >= 0

      @field_validator('月度', mode='before')
      def parse_chinese_date(cls, v):
          return parse_yyyymm_or_chinese(v)  # Story 2.4 utility
  ```
- Integration: Pipeline step validates each row, collects errors
- Reference: PRD §751-796 (FR-2: Multi-Layer Validation), §464-479 (Pydantic v2)

---

### Story 2.2: Pandera Schemas for DataFrame Validation (Bronze/Gold Layers)

As a **data engineer**,
I want **pandera DataFrameSchemas that validate entire DataFrames at layer boundaries**,
So that **schema violations are caught before data moves between Bronze/Silver/Gold layers**.

**Acceptance Criteria:**

**Given** I have Pydantic models from Story 2.1
**When** I create pandera schemas for Bronze and Gold layers
**Then** I should have:
- `BronzeAnnuitySchema`: validates raw Excel data (expected columns present, basic types)
- `GoldAnnuitySchema`: validates database-ready data (composite PK unique, no nulls in required fields)
- Schema checks: column presence, data types, uniqueness constraints, value ranges
- Decorator usage: `@pa.check_io(df1=BronzeSchema, out=SilverSchema)` on pipeline functions
- Failed validation exports to CSV: `failed_bronze_YYYYMMDD.csv` with violation details

**And** When Bronze schema validates raw Excel DataFrame
**Then** It should verify:
- Expected columns exist: `['月度', '计划代码', '客户名称', '期初资产规模', ...]`
- No completely null columns
- Date columns are parseable (coerce to datetime)

**And** When Gold schema validates database-ready DataFrame
**Then** It should verify:
- Composite PK `(月度, 计划代码, company_id)` has no duplicates
- Required fields are not null
- All columns match database schema (no extra columns)

**And** When validation fails
**Then** Raises `SchemaError` with details: which columns/rows failed, which checks violated

**Prerequisites:** Story 2.1 (Pydantic models for Silver layer)

**Technical Notes:**
- Use pandera 0.18+ for DataFrame-level contracts
- Bronze schema: permissive (data quality issues expected in raw Excel)
- Gold schema: strict (database integrity requirements)
- Decorator pattern integrates with pipeline framework (Story 1.5)
- Example:
  ```python
  import pandera as pa

  BronzeAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, coerce=True),
      "计划代码": pa.Column(pa.String, nullable=True),
      "期末资产规模": pa.Column(pa.Float, nullable=True)
  }, strict=False)  # Allow extra columns

  GoldAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, nullable=False),
      "计划代码": pa.Column(pa.String, nullable=False),
      "company_id": pa.Column(pa.String, nullable=False),
      "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0))
  }, strict=True, unique=['月度', '计划代码', 'company_id'])
  ```
- Reference: PRD §484-563 (Data Quality Requirements), docs/deep_research/4.md (Pandera)

---

### Story 2.3: Cleansing Registry Framework

As a **data engineer**,
I want **a centralized registry of reusable cleansing rules**,
So that **value-level transformations are standardized across all domains without code duplication**.

**Acceptance Criteria:**

**Given** I have validation schemas from Story 2.2
**When** I implement cleansing registry in `cleansing/registry.py`
**Then** I should have:
- `CleansingRegistry` class with rule registration: `registry.register('trim_whitespace', trim_func)`
- Built-in rules: trim whitespace, normalize company names, standardize dates, remove special characters
- Pydantic adapter: rules applied automatically during model validation via `@field_validator`
- Rule composition: multiple rules can apply to same field in sequence
- Per-domain configuration: enable/disable rules via YAML config

**And** When I register a cleansing rule for company names
**Then** It should normalize: "公司  有限" → "公司有限" (remove extra spaces)

**And** When Pydantic model uses cleansing adapter
**Then** Rules apply automatically during validation:
  ```python
  class AnnuityPerformanceOut(BaseModel):
      客户名称: str

      @field_validator('客户名称', mode='before')
      def clean_company_name(cls, v):
          return registry.apply_rules(v, ['trim_whitespace', 'normalize_company'])
  ```

**And** When rule is disabled in config for specific domain
**Then** That rule is skipped during validation

**Prerequisites:** Story 2.1 (Pydantic models to integrate with)

**Technical Notes:**
- Singleton pattern for registry: `registry = CleansingRegistry()`
- Rules are pure functions: `(value: Any) -> Any`
- Example built-in rules:
  ```python
  def trim_whitespace(value: str) -> str:
      return value.strip() if isinstance(value, str) else value

  def normalize_company_name(value: str) -> str:
      # Remove 「」, replace full-width spaces, etc.
      return value.replace('　', ' ').strip('「」')
  ```
- Configuration in `config/cleansing_rules.yml`:
  ```yaml
  domains:
    annuity_performance:
      客户名称: [trim_whitespace, normalize_company]
      计划代码: [trim_whitespace, uppercase]
  ```
- Reference: PRD §817-824 (FR-3.2: Registry-Driven Cleansing)

---

### Story 2.4: Chinese Date Parsing Utilities

As a **data engineer**,
I want **robust utilities for parsing various Chinese date formats**,
So that **inconsistent date formats from Excel sources are handled uniformly**.

**Acceptance Criteria:**

**Given** I have cleansing framework from Story 2.3
**When** I implement date parsing in `utils/date_parser.py`
**Then** I should have:
- `parse_yyyymm_or_chinese(value)` function supporting multiple formats:
  - Integer: `202501` → `date(2025, 1, 1)`
  - String: `"2025年1月"` → `date(2025, 1, 1)`
  - String: `"2025-01"` → `date(2025, 1, 1)`
  - Date object: `date(2025, 1, 1)` → `date(2025, 1, 1)` (passthrough)
  - 2-digit year: `"25年1月"` → `date(2025, 1, 1)` (assumes 20xx for <50, 19xx for >=50)
- Validation: rejects dates outside reasonable range (2000-2030)
- Clear errors: `ValueError("Cannot parse '不是日期' as date, supported formats: YYYYMM, YYYY年MM月, YYYY-MM")`

**And** When parsing `202501`
**Then** Returns `date(2025, 1, 1)`

**And** When parsing `"2025年1月"`
**Then** Returns `date(2025, 1, 1)`

**And** When parsing invalid date `"invalid"`
**Then** Raises `ValueError` with supported formats listed

**And** When parsing date outside range (1990)
**Then** Raises `ValueError("Date 1990-01 outside valid range 2000-2030")`

**Prerequisites:** Story 2.3 (cleansing framework)

**Technical Notes:**
- Use regex for Chinese format parsing: `re.match(r'(\d{4})年(\d{1,2})月', value)`
- Handle both full-width and half-width numbers
- Return first day of month for YYYYMM formats (business decision)
- Integration with Pydantic:
  ```python
  @field_validator('月度', mode='before')
  def parse_date(cls, v):
      return parse_yyyymm_or_chinese(v)
  ```
- Add comprehensive unit tests for all formats and edge cases
- Reference: PRD §863-871 (FR-3.4: Chinese Date Parsing)

---

### Story 2.5: Validation Error Handling and Reporting

As a **data engineer**,
I want **comprehensive error handling that exports failed rows with actionable feedback**,
So that **data quality issues can be fixed at the source without debugging pipeline code**.

**Acceptance Criteria:**

**Given** I have validation framework from Stories 2.1-2.4
**When** pipeline encounters validation failures
**Then** I should have:
- Failed rows exported to CSV: `logs/failed_rows_annuity_YYYYMMDD_HHMMSS.csv`
- CSV columns: original row data + `error_type`, `error_field`, `error_message`
- Error summary logged: "Validation failed: 15 rows failed Bronze schema, 23 rows failed Pydantic validation"
- Partial success handling: pipeline can continue with valid rows if configured (Epic 1 Story 1.10)
- Error threshold: if >10% of rows fail, stop pipeline (likely systemic data issue)

**And** When 15 rows fail Bronze schema validation (missing required columns)
**Then** CSV export shows:
  ```csv
  月度,计划代码,error_type,error_field,error_message
  202501,ABC123,SchemaError,期末资产规模,Column missing in source data
  ```

**And** When 5 out of 100 rows fail Pydantic validation
**Then** Pipeline continues with 95 valid rows and exports 5 failed rows to CSV

**And** When >10% of rows fail validation
**Then** Pipeline stops immediately with error: "Validation failure rate 15% exceeds threshold 10%, likely systemic issue"

**And** When all validations pass
**Then** No error CSV is created, logs show: "Validation success: 100 rows processed, 0 failures"

**Prerequisites:** Stories 2.1-2.4 (validation framework)

**Technical Notes:**
- Use Story 1.3 structured logging for error summaries
- CSV export location configurable: `settings.FAILED_ROWS_PATH` (default: `logs/`)
- Failure threshold configurable: `settings.VALIDATION_FAILURE_THRESHOLD` (default: 0.10)
- Integration with pipeline framework (Story 1.5): add validation step that collects errors
- Consider data sensitivity: failed row CSV might contain PII, ensure proper access control
- Reference: PRD §756-776 (FR-2.2: Silver Layer Validation)

---

## Epic 3: Intelligent File Discovery & Version Detection

**Goal:** Eliminate manual file selection every month by automatically detecting the latest data version (V1, V2, V3) across all domains and intelligently matching files using configurable patterns. This epic transforms "which file should I process?" from a daily decision into an automated capability.

**Business Value:** Monthly data drops arrive in inconsistent folder structures with V1, V2 revisions. Manual file selection is error-prone and time-consuming. Automated version detection saves 15-30 minutes per monthly run and eliminates the risk of processing stale data.

**Dependencies:** Epic 1 (configuration framework, logging)

**Dependency Flow:** 3.0 (config validation) → 3.1 (version scan) → 3.2 (file match) → 3.3 (Excel read) → 3.4 (normalize) → 3.5 (integration)

---

### Story 3.0: Data Source Configuration Schema Validation

As a **data engineer**,
I want **Pydantic validation of the data_sources.yml configuration structure**,
So that **configuration errors are caught at startup before any pipeline runs, preventing cryptic runtime failures**.

**Acceptance Criteria:**

**Given** I have `config/data_sources.yml` with domain configurations
**When** application starts and loads configuration
**Then** System should:
- Validate entire YAML structure using Pydantic `DataSourceConfig` model
- Verify required fields per domain: `base_path`, `file_patterns`, `sheet_name`
- Validate field types: `file_patterns` is list of strings, `version_strategy` is enum
- Check enum values: `version_strategy` in ['highest_number', 'latest_modified', 'manual']
- Raise clear error on missing/invalid fields before any file operations

**And** When configuration has missing required field (e.g., `sheet_name`)
**Then** Raise `ValidationError` at startup: "Domain 'annuity_performance' missing required field 'sheet_name'"

**And** When configuration has invalid version strategy
**Then** Raise `ValidationError`: "Invalid version_strategy 'newest', must be one of: ['highest_number', 'latest_modified', 'manual']"

**And** When configuration is valid
**Then** Log success: "Configuration validated: 6 domains configured"

**And** When template variables in paths (e.g., `{YYYYMM}`)
**Then** Validation allows placeholders, validates structure not resolved values

**Prerequisites:** Epic 1 Story 1.4 (configuration framework)

**Technical Notes:**
- Implement in `config/schemas.py` as Pydantic models:
  ```python
  from pydantic import BaseModel, Field
  from typing import Literal, List

  class DomainConfig(BaseModel):
      base_path: str = Field(..., description="Path template with {YYYYMM} placeholders")
      file_patterns: List[str] = Field(..., min_items=1)
      exclude_patterns: List[str] = Field(default_factory=list)
      sheet_name: str | int
      version_strategy: Literal['highest_number', 'latest_modified', 'manual'] = 'highest_number'
      fallback: Literal['error', 'use_latest_modified'] = 'error'

  class DataSourceConfig(BaseModel):
      domains: Dict[str, DomainConfig]
  ```
- Load and validate in `config/settings.py` during `Settings` initialization
- Fail fast: validation errors prevent application startup
- Prevents runtime errors in Stories 3.1-3.5 from malformed config
- Add unit tests for valid/invalid config scenarios
- Document supported Excel formats: `.xlsx` (via openpyxl), `.xlsm` supported, `.xls` NOT supported
- Reference: Dependency mapping identified config schema as hidden dependency

---

### Story 3.1: Version-Aware Folder Scanner

As a **data engineer**,
I want **automatic detection of versioned folders (V1, V2, V3) with configurable precedence rules**,
So that **the system always processes the latest data version without manual selection**.

**Acceptance Criteria:**

**Given** I have monthly data in `reference/monthly/202501/收集数据/业务收集/`
**When** both V1 and V2 folders exist
**Then** Scanner should:
- Detect all version folders matching pattern `V\d+`
- Select highest version number (V2 > V1)
- Return selected version path with justification logged
- Log: "Version detection: Found [V1, V2], selected V2 (highest_number strategy)"

**And** When only non-versioned files exist (no V folders)
**Then** Scanner should fallback to base path and log: "No version folders found, using base path"

**And** When version strategy configured as `latest_modified`
**Then** Scanner compares modification timestamps and selects most recently modified folder

**And** When version detection is ambiguous (e.g., V1 and V2 modified same day)
**Then** Scanner raises error with actionable message: "Ambiguous versions: V1 and V2 both modified on 2025-01-05, configure precedence rule or specify --version manually"

**And** When CLI override `--version=V1` provided
**Then** Scanner uses V1 regardless of automatic detection, logs: "Manual override: using V1 as specified"

**Prerequisites:** Story 3.0 (validated configuration), Epic 1 Story 1.4 (configuration framework), Story 1.3 (logging)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py`
- Version detection strategies: `highest_number` (default), `latest_modified`, `manual`
- Use `pathlib.Path.glob()` for folder scanning
- Configuration in `config/data_sources.yml`:
  ```yaml
  domains:
    annuity_performance:
      version_strategy: "highest_number"
      fallback: "error"  # or "use_latest_modified"
  ```
- Return `VersionedPath` dataclass: `path: Path, version: str, strategy_used: str`
- Unit tests for all strategies and edge cases
- Reference: PRD §565-605 (Version Detection System)

---

### Story 3.2: Pattern-Based File Matcher

As a **data engineer**,
I want **flexible file matching using glob patterns with include/exclude rules**,
So that **files are found despite naming variations and temp files are automatically filtered out**.

**Acceptance Criteria:**

**Given** I configure file patterns in `config/data_sources.yml`:
```yaml
annuity_performance:
  file_patterns:
    - "*年金*.xlsx"
    - "*规模明细*.xlsx"
  exclude_patterns:
    - "~$*"  # Excel temp files
    - "*回复*"  # Email reply files
```

**When** I scan folder with files: `年金数据2025.xlsx`, `~$年金数据2025.xlsx`, `规模明细回复.xlsx`
**Then** Matcher should:
- Find files matching include patterns: `["年金数据2025.xlsx"]`
- Exclude temp files and replies
- Return exactly 1 matching file
- Log: "File matching: 3 candidates, 1 match after filtering"

**And** When no files match patterns
**Then** Raise error: "No files found matching patterns ['*年金*.xlsx', '*规模明细*.xlsx'] in path /reference/monthly/202501/..."

**And** When multiple files match after filtering
**Then** Raise error with candidate list: "Ambiguous match: Found 2 files ['年金数据V1.xlsx', '年金数据V2.xlsx'], refine patterns or use version detection"

**And** When pattern uses Chinese characters
**Then** Matcher correctly handles UTF-8 encoding and finds matches

**Prerequisites:** Story 3.1 (version detection provides base path), Story 3.0 (validated config)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py` as `FilePatternMatcher` class
- Use `pathlib.Path.glob()` with Unicode support for Chinese characters
- Include/exclude logic: `(match any include) AND (match no exclude)`
- Validation: exactly 1 file must remain after filtering (fail if 0 or >1)
- Error messages include full file paths for troubleshooting
- Configuration loaded from Story 3.0 validated schema
- **Cross-platform testing:** Test Chinese characters in paths on Windows and Linux (encoding differences)
- Reference: PRD §608-643 (File Discovery and Processing)

---

### Story 3.3: Multi-Sheet Excel Reader

As a **data engineer**,
I want **targeted sheet extraction from multi-sheet Excel workbooks**,
So that **I can process specific data without manual sheet copying**.

**Acceptance Criteria:**

**Given** I have Excel file `年金数据2025.xlsx` with sheets: `['Summary', '规模明细', 'Notes']`
**When** configuration specifies `sheet_name: "规模明细"`
**Then** Reader should:
- Load only the specified sheet as DataFrame
- Preserve Chinese characters in column names
- Skip completely empty rows automatically
- Return DataFrame with proper column types inferred

**And** When sheet name is integer index `sheet_name: 1`
**Then** Reader loads second sheet (0-indexed)

**And** When specified sheet name doesn't exist
**Then** Raise error: "Sheet '规模明细' not found in file 年金数据2025.xlsx, available sheets: ['Summary', 'Notes']"

**And** When Excel has merged cells
**Then** Reader uses first cell's value for entire merged range (pandas default behavior)

**And** When Excel has formatting but no data in rows
**Then** Reader skips empty rows, logs: "Skipped 5 empty rows during load"

**Prerequisites:** Story 3.2 (file matcher provides Excel path)

**Technical Notes:**
- Implement in `io/readers/excel_reader.py` as `ExcelReader` class
- Use `pandas.read_excel()` with parameters:
  - `sheet_name`: from config
  - `engine='openpyxl'`: better Unicode support
  - `na_values`: ['', ' ', 'N/A', 'NA']
  - `skiprows`: none (handle in Bronze validation)
- Handle both sheet name (str) and index (int) from config
- Error handling: file not found, corrupted Excel, sheet missing
- Return `ExcelReadResult` dataclass: `df: pd.DataFrame, sheet_name: str, row_count: int`
- Reference: PRD §729-748 (FR-1.3: Multi-Sheet Excel Reading)

---

### Story 3.4: Column Name Normalization

As a **data engineer**,
I want **automatic normalization of column names from Excel sources**,
So that **inconsistent spacing, special characters, and encoding issues don't break pipelines**.

**Acceptance Criteria:**

**Given** I load Excel with column names: `['月度  ', '  计划代码', '客户名称\n', '期末资产规模']`
**When** I apply column normalization
**Then** Normalized names should be: `['月度', '计划代码', '客户名称', '期末资产规模']`

**And** When column names have full-width spaces `'客户　名称'` (full-width space)
**Then** Replace with half-width: `'客户 名称'` → `'客户名称'` (then trim)

**And** When column has newlines or tabs
**Then** Replace with single space: `'客户\n名称'` → `'客户 名称'`

**And** When column is completely empty or whitespace-only
**Then** Generate placeholder name: `'Unnamed_1'`, `'Unnamed_2'`, etc., and log warning

**And** When duplicate column names exist after normalization
**Then** Append suffix: `'月度'`, `'月度_1'`, `'月度_2'` and log warning

**Prerequisites:** Story 3.3 (Excel reader produces DataFrames with raw column names)

**Technical Notes:**
- Implement in `utils/column_normalizer.py` as pure function
- Normalization steps:
  1. Strip leading/trailing whitespace
  2. Replace full-width spaces (U+3000) with half-width
  3. Replace newlines/tabs with single space
  4. Replace multiple consecutive spaces with single space
  5. Handle empty/duplicate names
- Apply automatically in ExcelReader before returning DataFrame
- Configuration option to disable normalization if needed (default: enabled)
- Unit tests with edge cases: emoji in names, numeric names, etc.
- Reference: PRD §742-748 (FR-1.4: Resilient Data Loading)

---

### Story 3.5: File Discovery Integration

As a **data engineer**,
I want **a unified file discovery interface combining version detection, pattern matching, and Excel reading**,
So that **any domain can discover and load files with a single configuration entry**.

**Acceptance Criteria:**

**Given** I configure domain in `config/data_sources.yml`:
```yaml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns: ["*年金*.xlsx"]
    exclude_patterns: ["~$*"]
    sheet_name: "规模明细"
    version_strategy: "highest_number"
```

**When** I call `discover_and_load(domain='annuity_performance', month='202501')`
**Then** System should:
- Resolve `{YYYYMM}` placeholder to `202501`
- Scan for version folders (Story 3.1)
- Match files using patterns (Story 3.2)
- Load specified Excel sheet (Story 3.3)
- Normalize column names (Story 3.4)
- Return `DataDiscoveryResult`: `df: DataFrame, file_path: Path, version: str, sheet_name: str`

**And** When discovery completes successfully
**Then** Log structured summary:
```json
{
  "domain": "annuity_performance",
  "file_path": "reference/monthly/202501/收集数据/业务收集/V2/年金数据.xlsx",
  "version": "V2",
  "sheet_name": "规模明细",
  "row_count": 1250,
  "column_count": 15,
  "duration_ms": 850
}
```

**And** When any step fails (version detection, file matching, Excel reading)
**Then** Raise structured error with stage context:
```python
DiscoveryError(
    domain="annuity_performance",
    failed_stage="version_detection",  # or "file_matching", "excel_reading", "normalization"
    original_error=<original exception>,
    message="Version detection failed: Ambiguous versions V1 and V2 both modified on 2025-01-05"
)
```

**And** When multiple domains configured
**Then** Each domain discovery is independent (failure in one doesn't block others)

**And** When error raised from any sub-component
**Then** Error context includes: domain name, failed stage, input parameters, original exception

**Prerequisites:** Stories 3.0-3.4 (all discovery components including config validation)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py` as `FileDiscoveryService` class
- Facade pattern: orchestrates version scanner, pattern matcher, Excel reader, normalizer
- Template variable resolution: `{YYYYMM}`, `{YYYY}`, `{MM}` from config or parameters
- **Structured error context:** Wrap exceptions with stage markers for debugging
  ```python
  class DiscoveryError(Exception):
      def __init__(self, domain: str, failed_stage: str, original_error: Exception, message: str):
          self.domain = domain
          self.failed_stage = failed_stage  # One of: config_validation, version_detection, file_matching, excel_reading, normalization
          self.original_error = original_error
          super().__init__(message)
  ```
- Error aggregation: collect all errors from sub-components with stage context
- Integration with Epic 1 logging (Story 1.3): log structured error details
- Return rich result object: `DataDiscoveryResult(df, file_path, version, sheet_name, duration_ms)`
- **Caching opportunity:** Cache version detection results per month (optimization for Epic 9)
- Add integration test: end-to-end discovery with real file structure
- **Cross-platform validation:** Test on Windows and Linux for path encoding consistency
- Reference: PRD §699-748 (FR-1: Intelligent Data Ingestion complete), Dependency mapping enhanced error context

---

## Epic 4: Annuity Performance Domain Migration (MVP)

**Goal:** Complete the first domain migration using the Strangler Fig pattern, proving that the modern architecture can successfully replace legacy code with 100% output parity. This epic validates the entire platform on the highest-complexity domain, establishing patterns that all future domain migrations will follow.

**Business Value:** Annuity performance is the most complex domain with enrichment, multi-sheet processing, and intricate transformations. Successfully migrating it proves the architecture works and provides a reference implementation for the 5+ remaining domains. Establishes foundation for complete legacy system retirement.

**Dependencies:** Epic 1 (infrastructure), Epic 2 (validation), Epic 3 (file discovery)

**Strangler Fig Approach:** Build new pipeline → Run parallel with legacy → Validate 100% parity → Cutover → Delete legacy code

---

### Story 4.1: Annuity Domain Data Models (Pydantic)

As a **data engineer**,
I want **Pydantic models for annuity performance with Chinese field names matching Excel sources**,
So that **row-level validation enforces business rules and data flows through Bronze → Silver → Gold with type safety**.

**Acceptance Criteria:**

**Given** I have annuity Excel data with columns: `月度, 计划代码, 客户名称, 期初资产规模, 期末资产规模, 投资收益, 年化收益率`
**When** I create Pydantic models for Input and Output
**Then** I should have:
- `AnnuityPerformanceIn` (loose validation for messy Excel input):
  - `月度: Optional[Union[str, int, date]]` (handles various date formats)
  - `计划代码: Optional[str]` (can be missing initially)
  - `客户名称: Optional[str]` (enrichment source)
  - Numeric fields: `Optional[float]` (handles nulls)
- `AnnuityPerformanceOut` (strict validation for clean output):
  - `月度: date` (required, parsed)
  - `计划代码: str` (required, non-empty)
  - `company_id: str` (required, enriched - or temporary ID)
  - `期末资产规模: float = Field(ge=0)` (non-negative)
  - All business rules enforced

**And** When validating input row with `月度="202501"` and `期末资产规模="1,234,567.89"`
**Then** `AnnuityPerformanceIn` accepts the values (loose validation)

**And** When converting to output model
**Then** `AnnuityPerformanceOut` validates:
- Date parsed: `"202501"` → `date(2025, 1, 1)`
- Number cleaned: `"1,234,567.89"` → `1234567.89`
- All required fields present
- Business rules satisfied

**And** When output validation fails (e.g., missing `company_id`)
**Then** Raise `ValidationError` with field name and requirement

**Prerequisites:** Epic 2 Story 2.1 (Pydantic validation framework), Story 2.4 (Chinese date parsing)

**Technical Notes:**
- Implement in `domain/annuity_performance/models.py`
- Use Epic 2 Story 2.4 date parser in `@field_validator('月度')`
- Use Epic 2 Story 2.3 cleansing registry for company name normalization
- Field descriptions document Chinese field meanings:
  ```python
  class AnnuityPerformanceOut(BaseModel):
      月度: date = Field(..., description="Reporting month (月度)")
      计划代码: str = Field(..., min_length=1, description="Plan code (计划代码)")
      company_id: str = Field(..., description="Enterprise company ID or temporary IN_* ID")
      # ... more fields
  ```
- Separate models enable progressive validation (Epic 2 pattern)
- Reference: PRD §581-624 (FR-2.1: Pydantic Row-Level Validation)

---

### Story 4.2: Annuity Bronze Layer Validation Schema

As a **data engineer**,
I want **pandera DataFrame schema validating raw Excel data immediately after load**,
So that **corrupted source data is rejected before any processing with clear actionable errors**.

**Acceptance Criteria:**

**Given** I load raw annuity Excel DataFrame from Epic 3 file discovery
**When** I apply `BronzeAnnuitySchema` validation
**Then** Schema should verify:
- Expected columns present: `['月度', '计划代码', '客户名称', '期初资产规模', '期末资产规模', '投资收益', '年化收益率']`
- No completely null columns (indicates corrupted Excel)
- Numeric columns coercible to float: `期初资产规模, 期末资产规模, 投资收益, 年化收益率`
- Date column parseable (coerce with custom parser from Epic 2 Story 2.4)
- At least 1 data row (not just headers)

**And** When Excel has all expected columns and valid data types
**Then** Validation passes, DataFrame returned for Silver layer processing

**And** When Excel missing required column `期末资产规模`
**Then** Raise `SchemaError`: "Bronze validation failed: Missing required column '期末资产规模', found columns: [列出实际列名]"

**And** When column `月度` has non-date values in multiple rows
**Then** Raise `SchemaError` with row numbers: "Bronze validation failed: Column '月度' rows [15, 23, 45] cannot be parsed as dates"

**And** When >10% of numeric column values are non-numeric
**Then** Raise `SchemaError`: "Bronze validation failed: Column '期末资产规模' has 15% invalid values (likely systemic data issue)"

**Prerequisites:** Epic 2 Story 2.2 (pandera schemas), Epic 3 Story 3.5 (file discovery provides DataFrame)

**Technical Notes:**
- Implement in `domain/annuity_performance/schemas.py`
- Use pandera `DataFrameSchema` with coercion:
  ```python
  import pandera as pa
  from utils.date_parser import parse_yyyymm_or_chinese

  BronzeAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, coerce=True, nullable=True),
      "计划代码": pa.Column(pa.String, nullable=True),
      "客户名称": pa.Column(pa.String, nullable=True),
      "期初资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
      "期末资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
      "投资收益": pa.Column(pa.Float, coerce=True, nullable=True),
      "年化收益率": pa.Column(pa.Float, coerce=True, nullable=True),
  }, strict=False, coerce=True)  # Allow extra columns, coerce types
  ```
- Custom coercion for Chinese dates using Epic 2 Story 2.4 parser
- Error threshold: fail if >10% of rows invalid (indicates systemic issue)
- Reference: PRD §756-765 (FR-2.1: Bronze Layer Validation)

---

### Story 4.3: Annuity Transformation Pipeline (Bronze → Silver)

As a **data engineer**,
I want **transformation pipeline steps converting raw Excel to validated business data**,
So that **annuity data flows through cleansing, enrichment, and validation to produce Silver layer output**.

**Acceptance Criteria:**

**Given** I have Bronze-validated DataFrame from Story 4.2
**When** I execute annuity transformation pipeline
**Then** Pipeline should apply steps in order:
1. **Parse dates:** Convert `月度` to `date` objects using Epic 2 Story 2.4 parser
2. **Cleanse company names:** Apply Epic 2 Story 2.3 registry rules (trim, normalize)
3. **Validate rows:** Convert each row to `AnnuityPerformanceIn` (Story 4.1)
4. **Enrich company IDs:** Resolve `客户名称` → `company_id` (Epic 5 integration point - mock for now)
5. **Calculate derived fields:** Add any computed metrics
6. **Validate output:** Convert to `AnnuityPerformanceOut` (strict validation)
7. **Filter invalid rows:** Export failures to CSV (Epic 2 Story 2.5)

**And** When pipeline processes 1000 rows with 950 valid
**Then** Returns DataFrame with 950 rows, exports 50 failed rows to CSV with error reasons

**And** When enrichment service unavailable (Epic 5 not implemented yet)
**Then** Pipeline uses fallback: `company_id = "UNKNOWN_" + normalize(客户名称)` (temporary)

**And** When row fails Pydantic output validation
**Then** Row excluded from output, logged to failed rows CSV with specific validation error

**And** When all rows pass validation
**Then** Returns Silver DataFrame ready for Gold layer projection

**Prerequisites:** Stories 4.1-4.2 (models and Bronze validation), Epic 1 Story 1.5 (pipeline framework), Epic 2 Stories 2.1-2.5 (validation and cleansing)

**Technical Notes:**
- Implement in `domain/annuity_performance/pipeline_steps.py` using Epic 1 Story 1.5 pipeline framework
- Each transformation step implements `TransformStep` protocol
- Company enrichment integration point: inject `EnrichmentService` via dependency injection (Epic 1 Story 1.6 pattern)
- For MVP: use stub enrichment service that returns temporary IDs
- Error handling: collect validation errors per Epic 2 Story 2.5 pattern
- Pipeline config: `stop_on_error=False` (collect all errors), threshold=10% (Epic 2 Story 2.5)
- Example pipeline construction:
  ```python
  from domain.pipelines.core import Pipeline, PipelineContext

  annuity_pipeline = Pipeline("annuity_performance")
  annuity_pipeline.add_step(ParseDatesStep())
  annuity_pipeline.add_step(CleanseCompanyNamesStep(cleansing_registry))
  annuity_pipeline.add_step(ValidateInputRowsStep(AnnuityPerformanceIn))
  annuity_pipeline.add_step(EnrichCompanyIDsStep(enrichment_service))  # Stub for MVP
  annuity_pipeline.add_step(ValidateOutputRowsStep(AnnuityPerformanceOut))
  ```
- Reference: PRD §799-871 (FR-3: Configurable Data Transformation)

---

### Story 4.4: Annuity Gold Layer Projection and Schema

As a **data engineer**,
I want **Gold layer validation ensuring database-ready data meets all integrity constraints**,
So that **only clean, projection-filtered data with unique composite keys reaches PostgreSQL**.

**Acceptance Criteria:**

**Given** I have Silver DataFrame from Story 4.3 transformation pipeline
**When** I apply Gold layer projection and validation
**Then** System should:
- Project to database columns only (remove intermediate calculation fields)
- Validate composite PK uniqueness: `(月度, 计划代码, company_id)` has no duplicates
- Enforce not-null constraints on required fields
- Apply `GoldAnnuitySchema` pandera validation
- Prepare for Story 4.5 database loading

**And** When Silver DataFrame has 1000 rows with unique composite keys
**Then** Gold validation passes, returns 1000 rows ready for database

**And** When composite PK has duplicates (2 rows with same `月度, 计划代码, company_id`)
**Then** Raise `SchemaError`: "Gold validation failed: Composite PK (月度, 计划代码, company_id) has 2 duplicate combinations: [(2025-01-01, 'ABC123', 'COMP001'), ...]"

**And** When required field is null in Silver output
**Then** Raise `SchemaError`: "Gold validation failed: Required field 'company_id' is null in 5 rows"

**And** When DataFrame has extra columns not in database schema
**Then** Gold projection removes extra columns, logs: "Gold projection: removed columns ['intermediate_calc_1', 'temp_field_2']"

**Prerequisites:** Story 4.3 (Silver transformation), Epic 2 Story 2.2 (pandera schemas), Epic 1 Story 1.8 (database loader has schema projection)

**Technical Notes:**
- Implement in `domain/annuity_performance/schemas.py` as `GoldAnnuitySchema`
- Use pandera with strict validation:
  ```python
  GoldAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, nullable=False),
      "计划代码": pa.Column(pa.String, nullable=False),
      "company_id": pa.Column(pa.String, nullable=False),
      "期初资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
      "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
      "投资收益": pa.Column(pa.Float, nullable=False),
      "年化收益率": pa.Column(pa.Float, nullable=True),  # Can be null if 期末资产规模=0
  }, strict=True, unique=['月度', '计划代码', 'company_id'])
  ```
- Column projection: use Epic 1 Story 1.8 `WarehouseLoader.get_allowed_columns()` and `.project_columns()`
- Composite PK uniqueness critical for database integrity
- Reference: PRD §777-785 (FR-2.3: Gold Layer Validation)

---

### Story 4.5: Annuity End-to-End Pipeline Integration

As a **data engineer**,
I want **complete Bronze → Silver → Gold pipeline with database loading for annuity domain**,
So that **I can process monthly annuity data from Excel to PostgreSQL in a single execution**.

**Acceptance Criteria:**

**Given** I have all components from Stories 4.1-4.4 implemented
**When** I execute end-to-end annuity pipeline for month 202501
**Then** Pipeline should:
1. Discover file using Epic 3 Story 3.5 `FileDiscoveryService`
2. Validate Bronze using Story 4.2 `BronzeAnnuitySchema`
3. Transform using Story 4.3 pipeline (Bronze → Silver)
4. Validate Gold using Story 4.4 `GoldAnnuitySchema`
5. Load to database using Epic 1 Story 1.8 `WarehouseLoader`
6. Log execution metrics (duration, row counts, errors)

**And** When processing succeeds for 1000 input rows with 950 valid
**Then** Database should contain:
- 950 rows inserted into `annuity_performance_NEW` table (shadow mode)
- Composite PK constraint satisfied
- Audit log entry with: file_path, version, row counts, duration

**And** When any stage fails (file discovery, validation, transformation, database)
**Then** Pipeline fails fast with structured error showing failed stage (Epic 3 Story 3.5 error pattern)

**And** When I run pipeline twice with same input
**Then** Second run produces identical database state (idempotent upsert)

**And** When I execute via Dagster job
**Then** Dagster UI shows: execution graph, step-by-step logs, success/failure status

**Prerequisites:** Stories 4.1-4.4 (all annuity components), Epic 1 Story 1.9 (Dagster), Epic 1 Story 1.8 (database loader), Epic 3 Story 3.5 (file discovery)

**Technical Notes:**
- Implement in `domain/annuity_performance/service.py` as main orchestration function
- Create Dagster job in `orchestration/jobs.py`:
  ```python
  from domain.annuity_performance.service import process_annuity_performance

  @job
  def annuity_performance_job(context):
      month = context.op_config.get("month", "202501")
      result = process_annuity_performance(month)
      context.log.info(f"Processed {result.rows_loaded} rows in {result.duration_ms}ms")
  ```
- Write to `annuity_performance_NEW` table (shadow mode for Epic 6 parallel execution)
- Idempotent upsert: `ON CONFLICT (月度, 计划代码, company_id) DO UPDATE`
- Integration test: full pipeline with fixture Excel file
- Metrics logged via Epic 1 Story 1.3 structured logging
- Reference: PRD §879-906 (FR-4: Database Loading), §909-918 (FR-5.1: Dagster Jobs)

---

### Story 4.6: Annuity Domain Configuration and Documentation

As a **data engineer**,
I want **complete configuration and documentation for the annuity domain**,
So that **the domain is reproducible, maintainable, and serves as reference for future domain migrations**.

**Acceptance Criteria:**

**Given** I have working annuity pipeline from Story 4.5
**When** I finalize configuration and documentation
**Then** I should have:
- Domain config in `config/data_sources.yml`:
  ```yaml
  domains:
    annuity_performance:
      base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
      file_patterns: ["*年金*.xlsx", "*规模明细*.xlsx"]
      exclude_patterns: ["~$*", "*回复*"]
      sheet_name: "规模明细"
      version_strategy: "highest_number"
      fallback: "error"
  ```
- Database migration for `annuity_performance_NEW` table (Epic 1 Story 1.7 pattern)
- README section documenting annuity pipeline: input format, transformation steps, output schema
- Runbook: how to manually trigger annuity pipeline, troubleshoot common errors

**And** When team member reads annuity documentation
**Then** They should understand: data source location, expected Excel structure, transformation logic, database schema

**And** When I run `dagster job launch annuity_performance_job --config month=202501`
**Then** Pipeline executes successfully using configuration

**And** When database migration applied
**Then** `annuity_performance_NEW` table created with correct schema and composite PK

**Prerequisites:** Story 4.5 (working pipeline), Epic 1 Story 1.7 (database migrations), Epic 3 Story 3.0 (config schema)

**Technical Notes:**
- Configuration follows Epic 3 Story 3.0 validated schema structure
- Database migration file: `io/schema/migrations/YYYYMMDD_HHMM_create_annuity_performance_new.py`
- Table schema mirrors `GoldAnnuitySchema` from Story 4.4
- Documentation in `README.md` or `docs/domains/annuity_performance.md`
- Runbook includes: manual execution, common errors (missing file, validation failures), how to check results
- This becomes the **reference implementation** for Epic 9 domain migrations
- Reference: PRD §998-1030 (FR-7: Configuration Management)

---

## Epic 5: Company Enrichment Service

**Goal:** Build a flexible company ID enrichment service using the Provider abstraction pattern, supporting multi-tier resolution (internal mappings → EQC API → async queue) with temporary ID generation for unresolved companies. This epic enables cross-domain joins with consistent enterprise company IDs.

**Business Value:** Company names in Excel files vary ("公司A", "A公司", "公司A有限公司"). Enrichment resolves these to canonical company IDs, enabling accurate customer attribution across domains. Temporary IDs ensure pipelines never block on enrichment failures.

**Dependencies:** Epic 1 (infrastructure, database), Epic 4 Story 4.3 (enrichment integration point)

**Note:** Can be developed in parallel with Epic 3-4 since Story 4.3 uses stub enrichment initially.

---

### Story 5.1: EnterpriseInfoProvider Protocol and Stub Implementation

As a **data engineer**,
I want **a Provider protocol defining the enrichment contract with a testable stub implementation**,
So that **pipelines can develop against stable interface without requiring external services**.

**Acceptance Criteria:**

**Given** I need company enrichment without external dependencies
**When** I define `EnterpriseInfoProvider` protocol
**Then** Protocol should specify:
```python
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class CompanyInfo:
    company_id: str
    official_name: str
    unified_credit_code: Optional[str]
    confidence: float  # 0.0-1.0
    match_type: str  # "exact", "fuzzy", "alias", "temporary"

class EnterpriseInfoProvider(Protocol):
    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        """Resolve company name to CompanyInfo or None if not found"""
        ...
```

**And** When I implement `StubProvider` for testing
**Then** Stub should:
- Return predefined fixtures for known test company names
- Return `None` for unknown names (simulates not found)
- Be configurable via constructor: `StubProvider(fixtures={"公司A": CompanyInfo(...)})`
- Always return confidence=1.0 (perfect match for fixtures)

**And** When pipeline uses stub provider in tests
**Then** Enrichment behaves predictably without external services

**And** When I inject stub into Story 4.3 annuity pipeline
**Then** Pipeline processes data successfully with fixture company IDs

**Prerequisites:** Epic 1 Story 1.6 (Clean Architecture boundaries for DI pattern)

**Technical Notes:**
- Implement protocol in `domain/enrichment/provider_protocol.py`
- Stub implementation in `domain/enrichment/stub_provider.py`
- Protocol ensures all providers have same interface (stub, EQC, legacy)
- Stub enables Epic 4 development without Epic 5 completion
- Reference: PRD §825-861 (FR-3.3: Company Enrichment Integration), reference/01_company_id_analysis.md

---

### Story 5.2: Temporary Company ID Generation (HMAC-based)

As a **data engineer**,
I want **stable temporary IDs for unresolved companies using HMAC**,
So that **same company always maps to same temporary ID across runs, enabling consistent joins**.

**Acceptance Criteria:**

**Given** I have unresolved company name `"新公司XYZ"`
**When** I generate temporary ID
**Then** System should:
- Generate stable ID: `HMAC_SHA1(WDH_ALIAS_SALT, "新公司XYZ")` → Base32 encode → `IN_<16-chars>`
- Example: `"新公司XYZ"` → `"IN_ABCD1234EFGH5678"`
- Same input always produces same ID (deterministic)
- Different inputs produce different IDs (collision-resistant)
- Prefix `IN_` distinguishes temporary from real company IDs

**And** When I generate ID for `"新公司XYZ"` twice
**Then** Both calls return identical ID: `"IN_ABCD1234EFGH5678"`

**And** When I generate IDs for 10,000 different company names
**Then** No collisions occur (all IDs unique)

**And** When temporary ID stored in database
**Then** Joins work correctly: same company name → same temporary ID → consistent attribution

**And** When company later resolved via async enrichment
**Then** Temporary ID replaced with real company_id in future runs

**Prerequisites:** None (pure cryptographic function)

**Technical Notes:**
- Implement in `domain/enrichment/temp_id_generator.py`
- Use Python `hmac` module with SHA1 algorithm
- Salt from environment variable: `WDH_ALIAS_SALT` (secret, unique per deployment)
- Base32 encoding for URL-safe, readable IDs
- Function signature:
  ```python
  def generate_temp_company_id(company_name: str, salt: str) -> str:
      """Generate stable temporary ID: IN_<16-char-Base32>"""
      normalized = company_name.strip().lower()  # Normalize before hashing
      digest = hmac.new(salt.encode(), normalized.encode(), hashlib.sha1).digest()
      encoded = base64.b32encode(digest)[:16].decode('ascii')
      return f"IN_{encoded}"
  ```
- Security: Salt must be kept secret (not committed to git)
- Reference: PRD §834 (Temporary ID generation), reference/01_company_id_analysis.md §S-002

---

### Story 5.3: Internal Mapping Tables and Database Schema

As a **data engineer**,
I want **database tables for internal company mappings with migration**,
So that **high-confidence mappings are cached locally without API calls**.

**Acceptance Criteria:**

**Given** I need to store company enrichment data
**When** I create database migrations
**Then** I should have tables:

**`enterprise.company_master`:**
- `company_id` (PK, VARCHAR(50))
- `official_name` (VARCHAR(255), NOT NULL)
- `unified_credit_code` (VARCHAR(50), UNIQUE)
- `aliases` (TEXT[], alternative names)
- `source` (VARCHAR(50), e.g., "eqc_api", "manual", "legacy_import")
- `created_at`, `updated_at` (timestamps)

**`enterprise.company_name_index`:**
- `normalized_name` (VARCHAR(255), PK)
- `company_id` (FK → company_master, NOT NULL)
- `match_type` (VARCHAR(20), e.g., "exact", "fuzzy", "alias")
- `confidence` (DECIMAL(3,2), range 0.00-1.00)
- `created_at` (timestamp)
- Index on `(normalized_name, confidence DESC)` for fast lookup

**`enterprise.enrichment_requests`:**
- `request_id` (PK, UUID)
- `company_name` (VARCHAR(255), NOT NULL)
- `status` (VARCHAR(20), e.g., "pending", "processing", "done", "failed")
- `company_id` (FK → company_master, NULL until resolved)
- `confidence` (DECIMAL(3,2), NULL until resolved)
- `created_at`, `processed_at` (timestamps)
- Index on `(status, created_at)` for async processing queue

**And** When migration applied to fresh database
**Then** All tables created with correct schemas and constraints

**And** When I insert mapping: `("公司A有限公司", "COMP001", "exact", 1.00)`
**Then** Lookup of `"公司A有限公司"` returns `COMP001` with confidence 1.00

**And** When I insert enrichment request with status "pending"
**Then** Async processor can query pending requests ordered by created_at

**Prerequisites:** Epic 1 Story 1.7 (database migration framework)

**Technical Notes:**
- Migration file: `io/schema/migrations/YYYYMMDD_HHMM_create_enterprise_schema.py`
- Use schema `enterprise` to separate from domain tables
- Normalized name: lowercase, trimmed, special chars removed
- Confidence scoring: ≥0.90 auto-accept, 0.60-0.90 flag for review, <0.60 async queue
- Reference: PRD §836-849 (Company enrichment data persistence)

---

### Story 5.4: Internal Mapping Resolver (Multi-Tier Lookup)

As a **data engineer**,
I want **multi-tier lookup checking internal mappings before expensive API calls**,
So that **90%+ of lookups are resolved locally with zero API cost and sub-millisecond latency**.

**Acceptance Criteria:**

**Given** I have internal mappings populated in `enterprise.company_name_index`
**When** I lookup company name `"公司A有限公司"`
**Then** Resolver should:
1. Normalize input: trim, lowercase, remove special chars
2. Check exact match in `company_name_index` (fastest)
3. If not found, check fuzzy match (Levenshtein distance ≤2)
4. If not found, check aliases from `company_master`
5. Return `CompanyInfo` with highest confidence match or `None`

**And** When exact match exists with confidence 1.00
**Then** Return immediately without fuzzy/alias checks (optimization)

**And** When fuzzy match found with confidence 0.85
**Then** Return match with `match_type="fuzzy"`, `confidence=0.85`

**And** When no match found in any tier
**Then** Return `None` (caller handles fallback: EQC API or temporary ID)

**And** When multiple matches found
**Then** Return highest confidence match, log others as alternatives

**And** When lookup succeeds from cache
**Then** Response time <5ms (measured in integration tests)

**Prerequisites:** Story 5.3 (database tables), Story 5.1 (provider protocol)

**Technical Notes:**
- Implement in `domain/enrichment/internal_resolver.py` as `InternalMappingResolver`
- Implements `EnterpriseInfoProvider` protocol (Story 5.1)
- Normalization function shared with temporary ID generator (Story 5.2)
- Fuzzy matching: Use `fuzzywuzzy` or `RapidFuzz` library (Levenshtein distance)
- SQL query optimization:
  ```sql
  SELECT company_id, match_type, confidence
  FROM enterprise.company_name_index
  WHERE normalized_name = %s
  ORDER BY confidence DESC
  LIMIT 1
  ```
- Caching: Consider in-memory LRU cache for hot lookups (optional optimization)
- Reference: PRD §831 (Multi-tier resolution strategy)

---

### Story 5.5: EnrichmentGateway Integration and Fallback Logic

As a **data engineer**,
I want **unified gateway coordinating internal resolver, temporary ID generation, and async queueing**,
So that **enrichment never blocks pipelines and all companies get valid IDs (real or temporary)**.

**Acceptance Criteria:**

**Given** I have internal resolver (Story 5.4) and temp ID generator (Story 5.2)
**When** I implement `EnrichmentGateway` class
**Then** Gateway should:
1. Try internal resolver first (Story 5.4)
2. If not found AND budget available: try EQC API (Story 5.6, future)
3. If still not found: generate temporary ID (Story 5.2)
4. If confidence <0.60: queue for async enrichment (Story 5.7, future)
5. Return `CompanyInfo` with appropriate match_type and confidence

**And** When internal resolver finds exact match
**Then** Return immediately with confidence 1.00, no API call, no temp ID

**And** When internal resolver returns None
**Then** Generate temporary ID and return:
```python
CompanyInfo(
    company_id="IN_ABCD1234EFGH5678",
    official_name="新公司XYZ",  # Original name
    unified_credit_code=None,
    confidence=0.0,  # Temporary ID has no confidence
    match_type="temporary"
)
```

**And** When confidence between 0.60-0.90
**Then** Return company_id but set `needs_review=True` flag for human validation

**And** When gateway processes 1000 company names with 900 in cache
**Then** Only 100 generate temporary IDs (90% cache hit rate)

**And** When enrichment fails completely
**Then** Pipeline continues with temporary IDs (graceful degradation)

**Prerequisites:** Stories 5.1-5.4 (protocol, temp ID, internal resolver)

**Technical Notes:**
- Implement in `domain/enrichment/gateway.py` as `EnrichmentGateway`
- Implements `EnterpriseInfoProvider` protocol for pipeline compatibility
- Configuration: `WDH_ENRICH_ENABLED` (default: True), `WDH_ENRICH_SYNC_BUDGET` (default: 0 for MVP)
- Graceful degradation: enrichment is optional, pipeline never fails due to enrichment
- Metrics tracking:
  ```python
  EnrichmentStats:
      cache_hits: int
      temp_ids_generated: int
      api_calls: int  # For Story 5.6
      queue_depth: int  # For Story 5.7
  ```
- Integration with Story 4.3 annuity pipeline: inject gateway via DI
- Reference: PRD §836 (Gateway pattern), §855 (Graceful degradation)

---

### Story 5.6: EQC API Provider (Sync Lookup with Budget)

As a **data engineer**,
I want **synchronous EQC platform API lookup with budget limits**,
So that **high-value enrichment requests are resolved in real-time without runaway API costs**.

**Acceptance Criteria:**

**Given** I have EQC API credentials configured via `WDH_PROVIDER_EQC_TOKEN`
**When** I implement `EqcProvider` class
**Then** Provider should:
- Implement `EnterpriseInfoProvider` protocol (Story 5.1)
- Call EQC API endpoint: `POST /api/enterprise/search` with company name
- Parse response: extract `company_id`, `official_name`, `unified_credit_code`, confidence
- Respect budget: max `WDH_ENRICH_SYNC_BUDGET` calls per run (default: 0 for MVP, 5 for production)
- Timeout: 5 seconds per request (fail fast if API slow)
- Retry: 2 attempts on network timeout (not on 4xx errors)

**And** When API returns match with confidence 0.95
**Then** Return `CompanyInfo` with EQC data and cache to `enterprise.company_name_index`

**And** When API returns HTTP 404 (not found)
**Then** Return `None` (caller generates temporary ID)

**And** When API returns HTTP 401 (unauthorized)
**Then** Log error, disable provider for session, return `None` (fall back to temp IDs)

**And** When sync budget exhausted (5 calls made)
**Then** Return `None` immediately for remaining lookups (no more API calls this run)

**And** When API call succeeds
**Then** Cache result in `enterprise.company_name_index` for future runs

**Prerequisites:** Story 5.1 (provider protocol), Story 5.3 (database for caching)

**Technical Notes:**
- Implement in `domain/enrichment/eqc_provider.py`
- Use `requests` library with timeout and retry logic
- API token refresh: EQC tokens expire after 30 minutes (see reference doc §8)
- Budget tracking: instance variable `remaining_budget` decremented on each call
- Credential management:
  ```python
  class EqcProvider:
      def __init__(self, api_token: str, budget: int = 5):
          self.api_token = api_token
          self.remaining_budget = budget
  ```
- Cache writes are async (don't block on database write)
- Sanitize logs: NEVER log API token (security risk)
- Reference: PRD §833 (Sync lookup budget), §857-860 (Security & credentials), reference/01_company_id_analysis.md

---

### Story 5.7: Async Enrichment Queue (Deferred Resolution)

As a **data engineer**,
I want **async enrichment queue for low-confidence matches and unknowns**,
So that **temporary IDs are resolved to real IDs in background without blocking pipelines**.

**Acceptance Criteria:**

**Given** I have unresolved companies with temporary IDs
**When** enrichment gateway encounters low confidence match (<0.60)
**Then** System should:
- Insert into `enterprise.enrichment_requests` with status "pending"
- Include: company_name, temporary_id assigned, created_at
- Continue pipeline immediately (non-blocking)

**And** When async processor runs (separate Dagster job or cron)
**Then** Processor should:
- Query pending requests: `SELECT * FROM enrichment_requests WHERE status='pending' ORDER BY created_at LIMIT 100`
- Call EQC API for each (no budget limit for async)
- Update status: "pending" → "processing" → "done" or "failed"
- On success: update `company_name_index` with resolved mapping
- On failure after 3 retries: status="failed", log reason

**And** When company resolved via async queue
**Then** Next pipeline run uses cached mapping (no more temporary ID)

**And** When async processor fails mid-batch
**Then** Processing resumes from "pending" status on next run (idempotent)

**And** When queue depth exceeds 10,000
**Then** Log warning: "Enrichment queue backlog high, consider increasing async processing frequency"

**Prerequisites:** Story 5.3 (enrichment_requests table), Story 5.6 (EQC provider for API calls)

**Technical Notes:**
- Implement async processor in `orchestration/jobs.py` as `async_enrichment_job`
- Dagster schedule: run hourly or daily based on queue depth
- Status transitions: pending → processing (prevent duplicate processing) → done/failed
- Retry logic: exponential backoff for failed API calls (1min, 5min, 15min)
- Metrics: track queue depth, processing rate, success/failure ratio
- Future enhancement: priority queue (high-value companies processed first)
- Reference: PRD §833 (Async enrichment queue), §850 (Queue depth tracking)

---

### Story 5.8: Enrichment Observability and Export

As a **data engineer**,
I want **comprehensive metrics and CSV export of unknown companies**,
So that **I can monitor enrichment effectiveness and manually backfill critical unknowns**.

**Acceptance Criteria:**

**Given** I run annuity pipeline with enrichment enabled
**When** pipeline completes
**Then** System should log enrichment stats:
```json
{
  "enrichment_stats": {
    "total_lookups": 1000,
    "cache_hits": 850,
    "cache_hit_rate": 0.85,
    "temp_ids_generated": 100,
    "api_calls": 5,
    "sync_budget_used": 5,
    "async_queued": 45,
    "queue_depth_after": 120
  }
}
```

**And** When temporary IDs generated
**Then** Export CSV: `logs/unknown_companies_YYYYMMDD_HHMMSS.csv`
- Columns: `company_name, temporary_id, first_seen, occurrence_count`
- Sorted by occurrence_count DESC (most frequent unknowns first)

**And** When I review unknown companies CSV
**Then** I can manually add high-priority mappings to `enterprise.company_name_index`

**And** When enrichment stats tracked over time
**Then** I can monitor trends: cache hit rate improving, queue depth stable, temp ID rate decreasing

**And** When enrichment disabled via `WDH_ENRICH_ENABLED=False`
**Then** All companies get temporary IDs, stats show 100% temp ID rate

**Prerequisites:** Story 5.5 (gateway with metrics), Story 5.2 (temporary IDs)

**Technical Notes:**
- Implement metrics collection in `EnrichmentGateway` (Story 5.5)
- CSV export in `domain/enrichment/observability.py`
- Log stats via Epic 1 Story 1.3 structured logging
- CSV location: `logs/` directory (configurable via settings)
- Include occurrence count: track how many times each unknown company appears
- Dashboard integration (future): Expose metrics to Epic 8 monitoring
- Reference: PRD §849-855 (Enrichment observability)

---

