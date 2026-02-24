# Epic 1: Foundation & Core Infrastructure

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
