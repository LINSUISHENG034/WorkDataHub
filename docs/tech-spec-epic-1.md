# Epic Technical Specification: Foundation & Core Infrastructure

Date: 2025-11-09
Author: Link
Epic ID: epic-1
Status: Draft

---

## Overview

Epic 1 establishes the foundational platform infrastructure that all subsequent domain migrations depend on. This epic creates the "rails" that all data pipelines will run on: shared transformation frameworks (Bronze → Silver → Gold), clean architecture boundaries enforcing testability, database loading capabilities with transactional guarantees, structured logging for observability, configuration management for declarative behavior, and CI/CD automation ensuring code quality from day one.

The epic delivers a battle-tested reference implementation through 11 stories, proving the architecture works with a complete sample pipeline (CSV → validate → transform → database) executed via Dagster. This foundation enables the PRD's core promise: adding new data domains in <4 hours by following proven patterns, with 100% type safety (mypy strict mode), comprehensive validation (Pydantic + pandera), and maintainability guarantees (>80% test coverage) that make team handoff viable.

## Objectives and Scope

**In Scope:**

- ✅ Project structure with Python 3.10+, uv package manager, modern tooling (mypy, ruff, pytest)
- ✅ Basic CI/CD pipeline with type checking, linting, and unit tests (expanded to integration tests in Story 1.11)
- ✅ Structured logging framework using **structlog** (Decision #8) with JSON output and sanitization
- ✅ Configuration management with Pydantic Settings, environment variable validation
- ✅ Shared pipeline framework supporting **both DataFrame and Row-level steps** (Decision #3: Hybrid Protocol)
- ✅ Clean Architecture boundaries: `domain/` (pure logic) ← `io/` (data access) ← `orchestration/` (Dagster)
- ✅ Database schema management with Alembic migrations
- ✅ PostgreSQL transactional loading with connection pooling, batch inserts, column projection
- ✅ Dagster orchestration setup with sample job proving end-to-end execution
- ✅ Advanced pipeline features: error handling modes, optional steps, retry logic (whitelist approach), per-step metrics
- ✅ Comprehensive CI/CD with integration tests using pytest-postgresql

**Out of Scope (Deferred to Later Epics):**

- ❌ Domain-specific pipelines (Epic 4: Annuity, Epic 9: Growth domains)
- ❌ Multi-layer validation schemas (Epic 2: Pydantic models, pandera schemas)
- ❌ File discovery and version detection (Epic 3)
- ❌ Company enrichment service (Epic 5: MVP uses stub only per Decision #6)
- ❌ Parity testing against legacy system (Epic 6)
- ❌ Production Dagster schedules and sensors (Epic 7: Orchestration, deferred post-MVP)
- ❌ Monitoring dashboards and alerting (Epic 8: Observability)

## System Architecture Alignment

Epic 1 implements the core architectural decisions and patterns defined in the Architecture document:

**Decision #3: Hybrid Pipeline Step Protocol** - The pipeline framework (`domain/pipelines/core.py`) supports both `DataFrameStep` (bulk operations) and `RowTransformStep` (per-row validation/enrichment) protocols, enabling optimal pattern selection per transformation type. Story 1.5 implements the basic framework, Story 1.10 adds advanced features (error handling modes, retries, metrics).

**Decision #7: Comprehensive Naming Conventions** - Project structure follows PEP 8 standards: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. Story 1.1 establishes the directory layout (`domain/`, `io/`, `orchestration/`, `cleansing/`, `config/`, `utils/`) that all future epics will follow.

**Decision #8: structlog with Sanitization** - Story 1.3 implements true structured logging with JSON rendering, context binding, and strict sanitization rules (never log tokens, passwords, API keys). All log entries include required fields: `timestamp`, `level`, `logger`, `event`, `context`.

**Medallion Architecture (Bronze → Silver → Gold)** - The pipeline framework is designed to support the three-tier data quality progression pattern. Epic 1 provides the execution engine; Epic 2 will add the validation schemas (pandera for Bronze/Gold, Pydantic for Silver).

**Technology Stack Alignment:**
- Python 3.10+ (Story 1.1)
- uv for dependency management (Story 1.1: 10-100x faster than pip)
- Dagster for orchestration (Story 1.9: definitions ready, CLI-first for MVP)
- PostgreSQL with Alembic migrations (Stories 1.7, 1.8)
- mypy strict mode + ruff (Stories 1.1, 1.2: 100% type coverage NFR)
- pytest with custom markers (Story 1.11: unit/integration/parity markers)

**Constraints:**
- Story 1.5 keeps pipeline framework SIMPLE (no async, no parallel, no retries initially)
- Story 1.10 adds complexity ONLY after 2+ domain pipelines tested (Epic 4 Stories 4.3, 4.5)
- Database writes are transactional (all-or-nothing, Story 1.8)
- CI must pass before merge (Story 1.2 basic checks, Story 1.11 comprehensive suite)

## Detailed Design

### Services and Modules

Epic 1 establishes the foundational module structure that all subsequent epics will build upon:

| Module Path | Responsibility | Key Components | Owner Story |
|-------------|----------------|----------------|-------------|
| **`config/`** | Configuration management | `settings.py` (Pydantic Settings), `data_sources.yml`, `.env` template | Story 1.4 |
| **`utils/`** | Shared utilities | `logging.py` (structlog factory), `column_normalizer.py`, `date_parser.py` (deferred to Epic 2) | Story 1.3 |
| **`domain/pipelines/`** | Transformation framework | `core.py` (Pipeline executor), `builder.py`, `types.py` (protocols) | Stories 1.5, 1.10 |
| **`io/readers/`** | Data ingestion | `excel_reader.py` (placeholder, Epic 3), `csv_reader.py` (sample for Story 1.9) | Story 1.6 |
| **`io/loader/`** | Data persistence | `warehouse_loader.py` (PostgreSQL transactional loading) | Story 1.8 |
| **`io/connectors/`** | External systems | `file_connector.py` (placeholder, Epic 3) | Story 1.6 |
| **`io/schema/`** | Database migrations | `migrations/` (Alembic), `fixtures/test_data.sql` | Story 1.7 |
| **`orchestration/`** | Dagster integration | `jobs.py`, `ops.py`, `schedules.py`, `sensors.py` | Story 1.9 |
| **`cleansing/`** | Data quality rules | `registry.py` (placeholder, Epic 2) | Story 1.6 |

**Input/Output Flow:**
```
CSV/Excel → io/readers → DataFrame
                ↓
         domain/pipelines (transform steps)
                ↓
    io/loader → PostgreSQL (transactional)
                ↓
         orchestration/jobs (Dagster monitoring)
```

**Dependency Rules (Clean Architecture):**
- ✅ `domain/` imports: ONLY standard library + pandas/pydantic (no `io/` or `orchestration/`)
- ✅ `io/` imports: `domain/` for model types
- ✅ `orchestration/` imports: `domain/` + `io/` (wires everything together)

### Data Models and Contracts

Epic 1 defines foundational type contracts and protocols, not domain-specific models (Epic 2, 4).

#### Pipeline Framework Types (`domain/pipelines/types.py`)

**PipelineContext:**
```python
@dataclass
class PipelineContext:
    """Execution context passed to all transformation steps."""
    pipeline_name: str
    execution_id: str
    timestamp: datetime
    config: Dict[str, Any]
```

**DataFrameStep Protocol (Decision #3):**
```python
class DataFrameStep(Protocol):
    """Bulk DataFrame transformation for performance."""
    def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Transform entire DataFrame (vectorized operations)."""
        ...
```

**RowTransformStep Protocol (Decision #3):**
```python
class RowTransformStep(Protocol):
    """Per-row transformation with detailed error tracking."""
    def apply(self, row: Row, context: Dict) -> StepResult:
        """Transform single row with validation/enrichment."""
        ...

@dataclass
class StepResult:
    """Result of row-level transformation."""
    row: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
```

**PipelineResult:**
```python
@dataclass
class PipelineResult:
    """Output of pipeline execution."""
    success: bool
    output_data: pd.DataFrame
    metrics: Dict[str, Any]  # duration_ms, rows_processed, errors_count
    errors: List[str]
```

#### Configuration Schema (`config/settings.py`)

**Settings Model (Pydantic BaseSettings):**
```python
class Settings(BaseSettings):
    """Application configuration with validation."""
    # Required fields
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"

    # Optional with defaults
    LOG_LEVEL: str = "INFO"
    DAGSTER_HOME: str = Field(default="~/.dagster")
    MAX_WORKERS: int = 4
    DB_POOL_SIZE: int = 10
    DB_BATCH_SIZE: int = 1000

    class Config:
        env_file = ".env"

    @validator('DATABASE_URL')
    def validate_postgres_url(cls, v, values):
        """Ensure production uses PostgreSQL, not SQLite."""
        if values.get('ENVIRONMENT') == 'prod' and 'postgresql' not in v:
            raise ValueError("Production must use PostgreSQL connection string")
        return v
```

#### Database Schema (Story 1.7 Alembic Migrations)

**Core Audit Tables:**

**`pipeline_executions` (audit log):**
```sql
CREATE TABLE pipeline_executions (
    execution_id VARCHAR(100) PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,  -- 'running', 'success', 'failed'
    input_file_path TEXT,
    rows_input INT,
    rows_output INT,
    rows_failed INT,
    duration_ms INT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**`data_quality_metrics` (tracking):**
```sql
CREATE TABLE data_quality_metrics (
    metric_id SERIAL PRIMARY KEY,
    execution_id VARCHAR(100) REFERENCES pipeline_executions(execution_id),
    domain VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    recorded_at TIMESTAMP DEFAULT NOW()
);
```

### APIs and Interfaces

#### Pipeline Framework API (`domain/pipelines/core.py`)

**Pipeline Class (Story 1.5):**
```python
class Pipeline:
    """Executes transformation steps in sequence."""

    def __init__(self, name: str, config: Optional[Dict] = None):
        """Initialize pipeline with name and optional configuration."""
        self.name = name
        self.steps: List[Union[DataFrameStep, RowTransformStep]] = []
        self.context = PipelineContext(
            pipeline_name=name,
            execution_id=f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            config=config or {}
        )

    def add_step(self, step: Union[DataFrameStep, RowTransformStep]) -> 'Pipeline':
        """Add transformation step (builder pattern)."""
        self.steps.append(step)
        return self

    def run(self, initial_data: pd.DataFrame) -> PipelineResult:
        """Execute all steps sequentially, return result."""
        # Implementation in Story 1.5
        ...
```

**Advanced Configuration (Story 1.10):**
```python
@dataclass
class PipelineConfig:
    """Advanced pipeline options."""
    stop_on_error: bool = True  # Fail fast vs. collect errors
    max_retries: int = 3  # Retry transient errors
    retry_backoff_ms: int = 1000  # Exponential backoff base
    error_threshold: float = 0.10  # Stop if >10% rows fail
```

#### Database Loader API (`io/loader/warehouse_loader.py`)

**WarehouseLoader Class (Story 1.8):**
```python
class WarehouseLoader:
    """Transactional PostgreSQL loading with connection pooling."""

    def __init__(self, connection_url: str, pool_size: int = 10, batch_size: int = 1000):
        """Initialize with connection pool."""
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2, maxconn=pool_size, dsn=connection_url
        )
        self.batch_size = batch_size

    def load_dataframe(
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        upsert_keys: Optional[List[str]] = None
    ) -> LoadResult:
        """
        Load DataFrame to PostgreSQL table with transaction.

        Args:
            df: DataFrame to load
            table: Target table name
            schema: Database schema (default: public)
            upsert_keys: Columns for ON CONFLICT DO UPDATE (upsert mode)

        Returns:
            LoadResult with rows_inserted, rows_updated, duration_ms

        Raises:
            DatabaseError: On connection/transaction failures (with retry)
        """
        ...

    def get_allowed_columns(self, table: str, schema: str = "public") -> List[str]:
        """Query database schema for allowed column names."""
        ...

    def project_columns(self, df: pd.DataFrame, table: str, schema: str = "public") -> pd.DataFrame:
        """Filter DataFrame to only allowed database columns."""
        allowed = self.get_allowed_columns(table, schema)
        removed = [c for c in df.columns if c not in allowed]
        if len(removed) > 5:
            logger.warning("column_projection.many_removed", removed_count=len(removed), removed=removed)
        return df[allowed]
```

#### Logging API (`utils/logging.py`)

**Logger Factory (Story 1.3):**
```python
def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get structured logger with standard configuration.

    Returns logger pre-configured with:
    - JSON rendering (Decision #8)
    - ISO timestamp
    - Log level filtering
    - Context binding support

    Usage:
        logger = get_logger(__name__)
        logger = logger.bind(domain="annuity", execution_id="exec_123")
        logger.info("pipeline.started", rows=1000)
    """
    return structlog.get_logger(name)
```

#### Configuration API (`config/settings.py`)

**Settings Singleton (Story 1.4):**
```python
@lru_cache()
def get_settings() -> Settings:
    """
    Get cached Settings instance (load once, reuse everywhere).

    Validates environment variables on first call.
    Raises ValidationError if required fields missing.
    """
    return Settings()

# Usage in all modules
from config import settings  # Pre-instantiated singleton
database_url = settings.DATABASE_URL
```

#### Dagster Integration API (`orchestration/jobs.py`)

**Job Definition Pattern (Story 1.9):**
```python
from dagster import job, op

@op
def read_csv_op(context) -> pd.DataFrame:
    """Dagster op: read CSV file."""
    # Thin wrapper delegating to domain logic
    ...

@op
def validate_op(context, df: pd.DataFrame) -> pd.DataFrame:
    """Dagster op: validate data."""
    # Delegates to domain/pipelines
    ...

@op
def load_to_db_op(context, df: pd.DataFrame):
    """Dagster op: load to PostgreSQL."""
    # Delegates to io/loader/warehouse_loader
    ...

@job
def sample_pipeline_job():
    """Sample end-to-end pipeline demonstrating framework."""
    raw_data = read_csv_op()
    validated = validate_op(raw_data)
    load_to_db_op(validated)
```

### Workflows and Sequencing

#### Story Implementation Sequence

Epic 1 follows a carefully orchestrated build sequence to minimize rework:

```
Story 1.1 (Project Structure)
    ↓
Story 1.2 (Basic CI/CD) ← Validates 1.1
    ↓
Story 1.3 (Logging) ← Tested by 1.2 CI
    ↓
Story 1.4 (Config) ← Uses 1.3 logging
    ↓
Story 1.5 (Simple Pipeline) ← Uses 1.3 logging, 1.4 config
    ↓
Story 1.6 (Architecture Boundaries) ← Enforces patterns from 1.5
    ↓
Story 1.7 (Database Schema Mgmt) ← Knows structure from 1.6
    ↓
Story 1.8 (Database Loader) ← Uses 1.7 migrations, 1.3 logging
    ↓
Story 1.9 (Dagster Setup) ← Uses 1.5 pipeline, 1.8 loader
    ↓
Story 1.10 (Advanced Pipeline) ← Enhances 1.5 after proving with 1.9
    ↓
Story 1.11 (Enhanced CI/CD) ← Tests all infrastructure 1.1-1.10
```

#### Pipeline Execution Flow (Story 1.5)

**Simple Sequential Execution:**
```
1. Pipeline.run(initial_data: DataFrame)
    ↓
2. For each step in pipeline.steps:
    ├─ If DataFrameStep:
    │   └─ df = step.execute(df, context)
    │
    └─ If RowTransformStep:
        └─ For each row in df:
            ├─ result = step.apply(row, context)
            ├─ Collect warnings/errors
            └─ Update row with result
    ↓
3. Return PipelineResult(success, output_df, metrics, errors)
```

#### Database Loading Flow (Story 1.8)

**Transactional Load Workflow:**
```
1. WarehouseLoader.load_dataframe(df, table, schema, upsert_keys)
    ↓
2. Get connection from pool (with retry on failure)
    ↓
3. BEGIN TRANSACTION
    ↓
4. Column projection: df = project_columns(df, table, schema)
    ↓
5. Batch processing (chunks of 1000 rows):
    ├─ For each batch:
    │   ├─ Generate parameterized INSERT/UPSERT query
    │   ├─ Execute batch
    │   └─ Check for errors
    ↓
6. If any error:
    ├─ ROLLBACK TRANSACTION
    └─ Raise DatabaseError with context
    ↓
7. COMMIT TRANSACTION
    ↓
8. Return LoadResult(rows_inserted, rows_updated, duration_ms)
    ↓
9. Release connection to pool
```

#### Sample End-to-End Pipeline (Story 1.9)

**Dagster Job Execution Sequence:**
```
dagster job launch sample_pipeline_job
    ↓
1. read_csv_op
    ├─ Read CSV file from configured path
    ├─ Load into pandas DataFrame
    └─ Return df (Dagster type-checked)
    ↓
2. validate_op(df)
    ├─ Create Pipeline("sample_validation")
    ├─ Add validation steps:
    │   ├─ CheckRequiredColumnsStep (DataFrame)
    │   └─ ValidateDataTypesStep (Row-level)
    ├─ pipeline.run(df)
    └─ Return validated_df
    ↓
3. load_to_db_op(validated_df)
    ├─ Get WarehouseLoader from config
    ├─ loader.load_dataframe(
    │       df=validated_df,
    │       table="sample_data",
    │       schema="public"
    │   )
    ├─ Log execution metrics (Story 1.3 logger)
    └─ Update pipeline_executions audit table (Story 1.7 schema)
    ↓
4. Dagster UI shows:
    ├─ Execution graph (3 ops connected)
    ├─ Step-by-step logs (from Story 1.3 structlog)
    ├─ Success/failure status
    └─ Duration per op
```

#### CI/CD Workflow (Stories 1.2 & 1.11)

**Comprehensive CI Pipeline:**
```
git push → GitHub/GitLab
    ↓
1. Restore dependency cache (uv, pip)
    ↓
2. Run in parallel:
    ├─ mypy src/ --strict (type check, <30s)
    ├─ ruff check src/ (lint, <20s)
    └─ ruff format --check src/ (format check, <10s)
    ↓
3. If any check fails → BLOCK merge, show errors
    ↓
4. Run unit tests (Story 1.11):
    └─ pytest -v -m unit --cov=src/domain --cov=src/utils (<30s)
    ↓
5. Run integration tests (Story 1.11):
    ├─ Provision temporary PostgreSQL (pytest-postgresql)
    ├─ Run Story 1.7 Alembic migrations
    ├─ pytest -v -m integration --cov=src/io --cov=src/orchestration (<3min)
    └─ Cleanup test database
    ↓
6. Aggregate coverage report:
    ├─ Check thresholds: domain/ >90%, io/ >70%, orchestration/ >60%
    └─ If below threshold: WARN (block enforcement after 30 days)
    ↓
7. All checks pass → ALLOW merge to main
```

## Non-Functional Requirements

### Performance

**Epic 1 Performance Targets:**

| Component | Target | Rationale | Verification Method |
|-----------|--------|-----------|---------------------|
| **Pipeline Framework** | <100ms overhead per step | Enable 100+ step pipelines | Story 1.5 unit tests with timing |
| **Database Connection Pool** | <50ms connection acquisition | Fast batch job startup | Story 1.8 integration tests |
| **Batch Insert (1000 rows)** | <500ms per batch | Support 50K row domain in <5 min | Story 1.8 load tests |
| **DataFrame Step Execution** | Vectorized (pandas speed) | 10-100x faster than row iteration | Story 1.5 DataFrame protocol |
| **Row Step Execution** | <1ms per row (simple validation) | 50K rows in <50s (acceptable for Silver layer) | Story 1.10 benchmarks |
| **CI Pipeline** | <5 min total (unit + integration) | Fast feedback loop | Story 1.11 GitHub Actions timing |

**Architecture Support:**
- **Decision #3:** DataFrame steps use vectorized pandas operations (avoid Python loops)
- **Story 1.8:** Connection pooling eliminates repeated connection overhead
- **Story 1.8:** Batch inserts (1000 rows/batch) vs. row-by-row (100x faster)

**Performance Testing (Story 1.11):**
```python
@pytest.mark.performance
def test_pipeline_overhead():
    """Verify pipeline framework adds <100ms overhead."""
    pipeline = Pipeline("perf_test")
    pipeline.add_step(NoOpDataFrameStep())  # Does nothing

    df = pd.DataFrame({'col': range(10000)})

    start = time.perf_counter()
    result = pipeline.run(df)
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 100, f"Pipeline overhead {duration_ms}ms exceeds 100ms target"
```

### Security

**Epic 1 Security Requirements:**

| Requirement | Implementation | Story | Verification |
|-------------|----------------|-------|--------------|
| **No secrets in git** | `.env` gitignored, `.env.example` with placeholders | Story 1.1 | CI gitleaks scan (Story 1.2) |
| **Environment variable validation** | Pydantic Settings raises ValidationError if missing | Story 1.4 | Unit tests with missing env vars |
| **Parameterized SQL queries** | `psycopg2` with placeholder `%s`, never f-strings | Story 1.8 | Code review checklist |
| **Connection string protection** | Never log full `DATABASE_URL` (sanitize in logs) | Story 1.3 | Log sanitization tests |
| **Least privilege database** | Application user has INSERT/SELECT only, not DDL | Story 1.7 | Alembic uses separate admin user |
| **Dependency vulnerability scanning** | `uv` with lock file, Dependabot alerts | Story 1.1 | GitHub Security tab monitoring |

**Decision #8 Sanitization Rules (Story 1.3):**

**NEVER log these patterns:**
```python
SENSITIVE_PATTERNS = [
    r'password',
    r'token',
    r'api[_-]?key',
    r'secret',
    r'DATABASE_URL',
    r'WDH_.*_SALT',  # Decision #2 salt
    r'WDH_PROVIDER_.*_TOKEN',  # Epic 5 API tokens
]
```

**Sanitization Implementation:**
```python
def sanitize_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields before logging."""
    sanitized = data.copy()
    for key in list(sanitized.keys()):
        if any(re.search(pattern, key, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS):
            sanitized[key] = "***REDACTED***"
    return sanitized

# Usage in structured logging
logger.info(
    "database.connection.established",
    **sanitize_for_logging({"DATABASE_URL": settings.DATABASE_URL, "pool_size": 10})
)
# Output: {"event": "database.connection.established", "DATABASE_URL": "***REDACTED***", "pool_size": 10}
```

**SQL Injection Prevention (Story 1.8):**
```python
# ❌ NEVER do this (SQL injection vulnerability)
query = f"INSERT INTO {table} VALUES ('{value}')"

# ✅ ALWAYS use parameterized queries
query = "INSERT INTO %s (col1, col2) VALUES (%s, %s)"
cursor.execute(query, (table_name, value1, value2))
```

### Reliability/Availability

**Epic 1 Reliability Guarantees:**

| Requirement | Implementation | Story | Target |
|-------------|----------------|-------|--------|
| **Transactional integrity** | PostgreSQL ACID transactions (all-or-nothing) | Story 1.8 | 100% (never partial writes) |
| **Connection resilience** | Connection pool with retry on transient failures | Story 1.8 | 3 retries, exponential backoff |
| **Database migration safety** | Alembic migrations with rollback support | Story 1.7 | Zero downtime on schema changes |
| **Type safety** | mypy strict mode, 100% coverage | Story 1.2 | CI blocks on type errors |
| **Test coverage** | Automated pytest suite | Story 1.11 | >80% coverage (CI enforced) |
| **Error context** | Structured error messages (Decision #4) | Story 1.10 | All exceptions include context |

**Transaction Handling (Story 1.8):**
```python
def load_dataframe(self, df: pd.DataFrame, table: str) -> LoadResult:
    """Transactional loading: all rows succeed or all rows rollback."""
    conn = self.pool.getconn()
    try:
        with conn:  # Auto-commit on exit, auto-rollback on exception
            cursor = conn.cursor()

            for batch in chunk_dataframe(df, self.batch_size):
                # All batches succeed or entire transaction rolls back
                cursor.executemany(insert_query, batch)

        return LoadResult(success=True, rows_inserted=len(df))

    except Exception as e:
        # Transaction automatically rolled back by context manager
        logger.error("database.load.failed", error=str(e), rows=len(df))
        raise DatabaseError(f"Load failed, transaction rolled back: {e}") from e

    finally:
        self.pool.putconn(conn)
```

**Retry Logic (Story 1.10):**
```python
@dataclass
class RetryConfig:
    """Retry configuration for transient errors."""
    max_attempts: int = 3
    backoff_ms: int = 1000  # Exponential: 1s, 2s, 4s
    retriable_errors: Set[Type[Exception]] = field(default_factory=lambda: {
        ConnectionError,
        TimeoutError,
        psycopg2.OperationalError  # Database connection lost
    })

def execute_with_retry(func: Callable, retry_config: RetryConfig) -> Any:
    """Execute function with exponential backoff retry."""
    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            return func()
        except Exception as e:
            if type(e) not in retry_config.retriable_errors:
                raise  # Non-retriable error, fail immediately

            if attempt == retry_config.max_attempts:
                raise  # Max retries exhausted

            sleep_ms = retry_config.backoff_ms * (2 ** (attempt - 1))
            logger.warning("retry.attempt", attempt=attempt, sleep_ms=sleep_ms, error=str(e))
            time.sleep(sleep_ms / 1000)
```

**Graceful Degradation:**
- Pipeline execution continues collecting errors (if `stop_on_error=False` in Story 1.10)
- Failed rows logged to separate CSV for manual review (deferred to Epic 2 Story 2.5)
- Database connection pool degrades gracefully (reduces pool size if connections timeout)

### Observability

**Epic 1 Observability Capabilities:**

| Capability | Implementation | Story | Output Format |
|------------|----------------|-------|---------------|
| **Structured logging** | structlog with JSON renderer (Decision #8) | Story 1.3 | JSON lines to stdout + file |
| **Pipeline execution tracking** | `pipeline_executions` audit table | Story 1.7 | PostgreSQL table with execution_id |
| **Step-level metrics** | Duration, row counts per step | Story 1.10 | Embedded in PipelineResult |
| **Dagster UI** | Visual execution graph with logs | Story 1.9 | Web UI at localhost:3000 |
| **CI/CD metrics** | Test duration, coverage percentages | Story 1.11 | GitHub Actions annotations |
| **Error attribution** | Row-level error context (Decision #4) | Story 1.10 | Structured error messages |

**Structured Log Output (Story 1.3):**

**Example Log Entry:**
```json
{
  "timestamp": "2025-11-09T10:30:15.234Z",
  "level": "info",
  "logger": "domain.pipelines.core",
  "event": "pipeline.step.completed",
  "pipeline_name": "sample_validation",
  "execution_id": "exec_20251109_103000",
  "step_name": "ValidateDataTypesStep",
  "step_type": "row_transform",
  "duration_ms": 1250,
  "rows_processed": 1000,
  "rows_failed": 5,
  "warnings_count": 12
}
```

**Key Event Types (Standardized across all pipelines):**
- `pipeline.started` - Pipeline execution begins
- `pipeline.step.started` - Individual step begins
- `pipeline.step.completed` - Step completes successfully
- `pipeline.step.failed` - Step fails with error
- `pipeline.completed` - Pipeline finishes (success or failure)
- `database.connection.acquired` - Connection pool operation
- `database.load.started` - Database loading begins
- `database.load.completed` - Database loading completes

**Pipeline Metrics (Story 1.10):**
```python
@dataclass
class PipelineMetrics:
    """Metrics collected during pipeline execution."""
    total_duration_ms: int
    rows_input: int
    rows_output: int
    rows_failed: int
    step_metrics: Dict[str, StepMetrics]  # Per-step breakdown

@dataclass
class StepMetrics:
    """Metrics for individual pipeline step."""
    step_name: str
    step_type: str  # "dataframe" or "row_transform"
    duration_ms: int
    rows_in: int
    rows_out: int
    errors_count: int
    warnings_count: int
```

**Database Audit Trail (Story 1.7):**

**Query pipeline execution history:**
```sql
-- Find all failed executions in last 7 days
SELECT execution_id, pipeline_name, started_at, error_message
FROM pipeline_executions
WHERE status = 'failed'
  AND started_at > NOW() - INTERVAL '7 days'
ORDER BY started_at DESC;

-- Calculate success rate per pipeline
SELECT
    pipeline_name,
    COUNT(*) as total_executions,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM pipeline_executions
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY pipeline_name;
```

**Dagster UI Integration (Story 1.9):**

**Capabilities:**
- Visual execution graph showing data flow between ops
- Real-time log streaming from structlog (stdout capture)
- Step-by-step execution timeline with durations
- Re-run failed jobs from UI
- Execution history with filtering/search

**Access:**
```bash
# Start Dagster UI (development)
dagster dev

# Open browser: http://localhost:3000
# Navigate to: Jobs → sample_pipeline_job → Launch Run
```

## Dependencies and Integrations

**External Dependencies (Story 1.1 - uv managed):**

| Dependency | Version | Purpose | Import Scope |
|------------|---------|---------|--------------|
| **python** | 3.10+ | Runtime | All modules |
| **uv** | latest | Package manager | Development only |
| **pandas** | latest | DataFrame operations | `domain/`, `io/` |
| **pydantic** | 2.11.7+ | Settings, validation (Silver layer in Epic 2) | `config/`, `domain/` (Epic 2+) |
| **structlog** | latest | Structured logging (Decision #8) | All modules via `utils/logging.py` |
| **psycopg2-binary** | latest | PostgreSQL driver | `io/loader/`, `io/schema/` |
| **alembic** | latest | Database migrations | `io/schema/migrations/` |
| **dagster** | latest | Orchestration framework | `orchestration/` |
| **dagster-webserver** | latest | Dagster UI (dev only) | Development |
| **mypy** | 1.17.1+ | Type checking (strict mode) | CI/CD only |
| **ruff** | 0.12.12+ | Linting + formatting | CI/CD only |
| **pytest** | latest | Testing framework | Tests only |
| **pytest-cov** | latest | Coverage reporting | Tests + CI |
| **pytest-postgresql** | latest | Temporary test databases | Integration tests (Story 1.11) |

**Dependency Installation (Story 1.1):**
```bash
# Create project with uv
uv init workdatahub
cd workdatahub

# Add dependencies
uv add pandas pydantic structlog psycopg2-binary alembic dagster dagster-webserver

# Add dev dependencies
uv add --dev mypy ruff pytest pytest-cov pytest-postgresql

# Lock dependencies (committed to git)
uv lock

# Install from lock file (reproducible across environments)
uv sync
```

**Internal Module Dependencies (Clean Architecture):**

**Allowed Import Patterns:**
```python
# ✅ domain/ can import:
import pandas as pd
from pydantic import BaseModel
# ❌ domain/ CANNOT import:
from io.loader import WarehouseLoader  # FORBIDDEN (breaks clean architecture)

# ✅ io/ can import:
from domain.pipelines.types import PipelineContext
from config.settings import get_settings
# ❌ io/ CANNOT import:
from orchestration.jobs import sample_pipeline_job  # FORBIDDEN (circular dependency)

# ✅ orchestration/ can import:
from domain.pipelines.core import Pipeline
from io.loader.warehouse_loader import WarehouseLoader
from io.readers.csv_reader import CSVReader
```

**Integration Points with Future Epics:**

| Future Epic | Integration Point | Epic 1 Provides | Future Epic Adds |
|-------------|-------------------|-----------------|------------------|
| **Epic 2 (Validation)** | `domain/pipelines/core.py` | Pipeline framework with step protocols | Pydantic validators, pandera schemas as steps |
| **Epic 3 (File Discovery)** | `io/connectors/file_connector.py` | Placeholder stub | Version detection algorithm (Decision #1) |
| **Epic 4 (Annuity)** | `domain/pipelines/core.py` | Reusable pipeline executor | Annuity-specific transformation steps |
| **Epic 5 (Enrichment)** | `domain/pipelines/types.py` | RowTransformStep protocol | `EnrichCompanyIDsStep` implementation |
| **Epic 6 (Testing)** | `tests/` structure | Basic unit/integration test framework (Story 1.11) | Parity tests comparing new vs legacy |
| **Epic 7 (Orchestration)** | `orchestration/jobs.py` | Sample job proving Dagster works | Production schedules, sensors, partitions |
| **Epic 8 (Monitoring)** | `utils/logging.py` | structlog foundation | Dashboards, alerting, metric aggregation |

**Database Schema Integration (Story 1.7):**

**Epic 1 Creates:**
- `public.pipeline_executions` (audit log)
- `public.data_quality_metrics` (metrics tracking)

**Future Epics Add:**
- Epic 4: `public.annuity_performance` (business data table)
- Epic 5: `enterprise.company_master`, `enterprise.company_aliases`, `enterprise.enrichment_cache` (enrichment tables)
- Epic 9: Additional domain tables (business collection, investment data, etc.)

## Acceptance Criteria (Authoritative)

These criteria define "DONE" for Epic 1. All must be met before marking the epic complete.

### Story 1.1: Project Structure & Tooling Setup

**AC-1.1.1:** Project initialized with `uv` package manager
- ✅ `pyproject.toml` exists with `[project]` metadata
- ✅ `uv.lock` file committed to git (reproducible builds)
- ✅ `.python-version` file specifies Python 3.10+

**AC-1.1.2:** Directory structure follows Clean Architecture pattern
- ✅ Required directories exist: `src/domain/`, `src/io/`, `src/orchestration/`, `src/config/`, `src/utils/`, `tests/`
- ✅ Each directory has `__init__.py` for Python package recognition
- ✅ `README.md` documents directory structure and purpose

**AC-1.1.3:** Core dependencies installed
- ✅ Production dependencies: pandas, pydantic, structlog, psycopg2-binary, alembic, dagster
- ✅ Dev dependencies: mypy, ruff, pytest, pytest-cov, pytest-postgresql
- ✅ All dependencies pinned in `uv.lock`

**AC-1.1.4:** Environment configuration template provided
- ✅ `.env.example` file with placeholder values (DATABASE_URL, LOG_LEVEL, etc.)
- ✅ `.env` added to `.gitignore` (security requirement)
- ✅ `.gitignore` covers Python artifacts: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`

---

### Story 1.2: Basic CI/CD Pipeline

**AC-1.2.1:** CI pipeline configuration file exists
- ✅ `.github/workflows/ci.yml` OR `.gitlab-ci.yml` (depending on platform)
- ✅ Triggers on: push to main, pull requests

**AC-1.2.2:** Type checking enforced
- ✅ CI runs `mypy src/ --strict` and blocks merge on errors
- ✅ `mypy.ini` or `pyproject.toml` configures strict mode
- ✅ All existing code (Stories 1.1-1.2) passes type checking

**AC-1.2.3:** Linting enforced
- ✅ CI runs `ruff check src/` and blocks merge on violations
- ✅ `ruff.toml` or `pyproject.toml` configures rules
- ✅ All existing code passes linting

**AC-1.2.4:** Code formatting checked
- ✅ CI runs `ruff format --check src/` and blocks merge if not formatted
- ✅ Local formatting command documented: `uv run ruff format src/`

**AC-1.2.5:** Secret scanning enabled
- ✅ CI runs gitleaks or equivalent tool to detect secrets
- ✅ Blocks merge if secrets detected in commits

**AC-1.2.6:** CI execution time acceptable
- ✅ Total CI pipeline (type check + lint + format) completes in <2 minutes

---

### Story 1.3: Structured Logging Framework

**AC-1.3.1:** Logging utility module implemented
- ✅ `src/utils/logging.py` exists with `get_logger(name: str)` function
- ✅ Returns `structlog.BoundLogger` instance

**AC-1.3.2:** structlog configured per Decision #8
- ✅ JSON rendering enabled (`structlog.processors.JSONRenderer`)
- ✅ ISO 8601 timestamps (`structlog.processors.TimeStamper(fmt="iso")`)
- ✅ Log level and logger name added to all entries
- ✅ Configuration applied at module import (singleton pattern)

**AC-1.3.3:** Sanitization implemented
- ✅ `sanitize_for_logging(data: Dict)` function exists
- ✅ Redacts sensitive patterns: password, token, api_key, secret, DATABASE_URL, WDH_.*_SALT
- ✅ Unit tests verify redaction works correctly

**AC-1.3.4:** Context binding demonstrated
- ✅ Example code shows: `logger = logger.bind(domain="test", execution_id="exec_123")`
- ✅ Bound context appears in all subsequent log entries

**AC-1.3.5:** Log output targets configured
- ✅ Logs written to stdout (always)
- ✅ File logging optional via `LOG_TO_FILE` environment variable
- ✅ File rotation configured (daily, 30-day retention) if enabled

**AC-1.3.6:** Unit tests pass
- ✅ Test log entry structure (required fields present)
- ✅ Test sanitization (sensitive data redacted)
- ✅ Test context binding (bound fields appear in logs)

---

### Story 1.4: Configuration Management

**AC-1.4.1:** Settings module implemented
- ✅ `src/config/settings.py` exists with `Settings(BaseSettings)` class
- ✅ Required fields: `DATABASE_URL: str`, `ENVIRONMENT: Literal["dev", "staging", "prod"]`
- ✅ Optional fields with defaults: `LOG_LEVEL`, `DB_POOL_SIZE`, `DB_BATCH_SIZE`

**AC-1.4.2:** Environment variable validation works
- ✅ `Settings()` raises `ValidationError` if required `DATABASE_URL` missing
- ✅ Custom validator ensures production uses PostgreSQL (not SQLite)

**AC-1.4.3:** Settings singleton pattern implemented
- ✅ `get_settings()` function uses `@lru_cache()` decorator
- ✅ Multiple calls return same instance (cached)

**AC-1.4.4:** Settings accessible project-wide
- ✅ `src/config/__init__.py` exports: `from .settings import get_settings, settings`
- ✅ Usage pattern documented: `from config import settings`

**AC-1.4.5:** Integration with logging
- ✅ `utils/logging.py` uses `settings.LOG_LEVEL` to configure log level
- ✅ Example code demonstrates using settings in other modules

**AC-1.4.6:** Unit tests pass
- ✅ Test missing required field raises ValidationError
- ✅ Test production environment validates PostgreSQL URL
- ✅ Test settings singleton (same instance returned)

---

### Story 1.5: Basic Pipeline Framework

**AC-1.5.1:** Type definitions implemented
- ✅ `src/domain/pipelines/types.py` exists
- ✅ `PipelineContext` dataclass defined
- ✅ `DataFrameStep` protocol defined (Decision #3)
- ✅ `RowTransformStep` protocol defined (Decision #3)
- ✅ `StepResult` dataclass defined
- ✅ `PipelineResult` dataclass defined

**AC-1.5.2:** Pipeline executor implemented
- ✅ `src/domain/pipelines/core.py` exists with `Pipeline` class
- ✅ `__init__(name, config)` constructor
- ✅ `add_step(step)` method returns self (builder pattern)
- ✅ `run(initial_data)` method executes steps sequentially

**AC-1.5.3:** DataFrame step execution works
- ✅ Pipeline recognizes `DataFrameStep` instances
- ✅ Calls `step.execute(df, context)` and updates DataFrame

**AC-1.5.4:** Row transform step execution works
- ✅ Pipeline recognizes `RowTransformStep` instances
- ✅ Iterates DataFrame rows, calls `step.apply(row, context)`
- ✅ Collects warnings and errors from `StepResult`
- ✅ Updates row with transformation result

**AC-1.5.5:** Pipeline result returned
- ✅ `PipelineResult` includes: success flag, output DataFrame, metrics (duration, row counts), errors list

**AC-1.5.6:** Logging integrated
- ✅ Pipeline logs: `pipeline.started`, `pipeline.step.started`, `pipeline.step.completed`, `pipeline.completed`
- ✅ Uses structlog from Story 1.3

**AC-1.5.7:** SIMPLE implementation (no advanced features)
- ✅ NO retry logic (added in Story 1.10)
- ✅ NO error handling modes (added in Story 1.10)
- ✅ NO optional steps (added in Story 1.10)
- ✅ Sequential execution only (no parallelism)

**AC-1.5.8:** Unit tests pass
- ✅ Test DataFrame step execution
- ✅ Test Row transform step execution
- ✅ Test mixed step types in single pipeline
- ✅ Test pipeline result structure
- ✅ Test logging output (verify events emitted)

---

### Story 1.6: Clean Architecture Boundary Enforcement

**AC-1.6.1:** Module organization documented
- ✅ `docs/architecture-boundaries.md` OR README section explains:
  - `domain/` responsibilities (pure business logic)
  - `io/` responsibilities (data access, external systems)
  - `orchestration/` responsibilities (Dagster integration)

**AC-1.6.2:** Placeholder modules created
- ✅ `src/io/readers/__init__.py` exists (Epic 3 will add implementations)
- ✅ `src/io/connectors/__init__.py` exists
- ✅ `src/cleansing/__init__.py` exists (Epic 2 will add implementations)

**AC-1.6.3:** Import rules enforced via linting
- ✅ `ruff` or custom script checks `domain/` does NOT import from `io/` or `orchestration/`
- ✅ CI fails if forbidden imports detected

**AC-1.6.4:** Example dependency injection pattern documented
- ✅ Shows `orchestration/` injecting `io/loader` into `domain/pipeline` via constructor
- ✅ Demonstrates testability (mock `io/` in `domain/` tests)

---

### Story 1.7: Database Schema Management with Alembic

**AC-1.7.1:** Alembic initialized
- ✅ `src/io/schema/alembic.ini` exists
- ✅ `src/io/schema/migrations/` directory exists
- ✅ `src/io/schema/migrations/env.py` configured to use `settings.DATABASE_URL`

**AC-1.7.2:** Initial migration created
- ✅ Migration file creates `pipeline_executions` table (schema in Data Models section)
- ✅ Migration file creates `data_quality_metrics` table
- ✅ Both migrations include rollback (downgrade) logic

**AC-1.7.3:** Migration execution documented
- ✅ README or docs explain: `alembic upgrade head` (apply migrations)
- ✅ README or docs explain: `alembic downgrade -1` (rollback last migration)

**AC-1.7.4:** Migrations tested
- ✅ Can apply migration to empty PostgreSQL database (no errors)
- ✅ Can rollback migration successfully
- ✅ Tables exist after upgrade with correct columns and types

**AC-1.7.5:** Separate migration user documented
- ✅ Docs explain: use database admin user for migrations
- ✅ Application user (for data loading) has INSERT/SELECT only, not DDL

---

### Story 1.8: PostgreSQL Transactional Loading

**AC-1.8.1:** Loader class implemented
- ✅ `src/io/loader/warehouse_loader.py` exists with `WarehouseLoader` class
- ✅ `__init__(connection_url, pool_size, batch_size)` constructor
- ✅ Creates `psycopg2.pool.ThreadedConnectionPool`

**AC-1.8.2:** DataFrame loading method implemented
- ✅ `load_dataframe(df, table, schema, upsert_keys)` method exists
- ✅ Returns `LoadResult` dataclass with rows_inserted, rows_updated, duration_ms

**AC-1.8.3:** Transactional guarantees enforced
- ✅ Uses PostgreSQL transaction: `BEGIN` → batches → `COMMIT` OR `ROLLBACK`
- ✅ If any batch fails, entire transaction rolled back (all-or-nothing)

**AC-1.8.4:** Batch processing implemented
- ✅ DataFrame chunked into batches (default 1000 rows from settings)
- ✅ Uses `cursor.executemany()` for batch inserts

**AC-1.8.5:** Parameterized queries used (security)
- ✅ INSERT queries use `%s` placeholders, never f-strings or string concatenation
- ✅ SQL injection impossible (verified by code review)

**AC-1.8.6:** Column projection implemented
- ✅ `get_allowed_columns(table, schema)` queries database schema
- ✅ `project_columns(df, table, schema)` filters DataFrame to allowed columns
- ✅ Logs warning if >5 columns removed

**AC-1.8.7:** Connection pool management
- ✅ Connections acquired from pool via `getconn()`
- ✅ Connections always released via `putconn()` (even on error, using try/finally)

**AC-1.8.8:** Logging integrated
- ✅ Logs: `database.load.started`, `database.load.completed`, `database.load.failed`
- ✅ Includes metrics: rows, duration_ms, table, schema

**AC-1.8.9:** Integration tests pass
- ✅ Test successful load (verify rows in database)
- ✅ Test transactional rollback (simulate batch error, verify no rows inserted)
- ✅ Test column projection (extra columns removed)
- ✅ Uses pytest-postgresql for temporary test database

---

### Story 1.9: Dagster Orchestration Setup

**AC-1.9.1:** Dagster project initialized
- ✅ `src/orchestration/jobs.py` exists
- ✅ `src/orchestration/ops.py` exists (op definitions)
- ✅ `pyproject.toml` or `workspace.yaml` configures Dagster code location

**AC-1.9.2:** Sample ops implemented
- ✅ `read_csv_op` reads CSV file, returns DataFrame
- ✅ `validate_op` runs simple Pipeline validation, returns DataFrame
- ✅ `load_to_db_op` uses WarehouseLoader to load DataFrame

**AC-1.9.3:** Sample job defined
- ✅ `sample_pipeline_job` wires together: read_csv_op → validate_op → load_to_db_op
- ✅ Job executes successfully (end-to-end test)

**AC-1.9.4:** Dagster UI accessible
- ✅ `dagster dev` command starts UI on localhost:3000
- ✅ Job appears in UI "Jobs" tab
- ✅ Can launch job from UI successfully

**AC-1.9.5:** Logging integration verified
- ✅ structlog output appears in Dagster UI logs tab
- ✅ JSON log entries readable (pretty-printed or raw JSON)

**AC-1.9.6:** Sample test data provided
- ✅ `tests/fixtures/sample_data.csv` exists with test rows
- ✅ Sample job reads this file successfully

**AC-1.9.7:** Demonstrates Clean Architecture
- ✅ Ops are thin wrappers (5-10 lines each)
- ✅ Ops delegate to `domain/` and `io/` modules (no business logic in ops)

---

### Story 1.10: Advanced Pipeline Features

**AC-1.10.1:** Error handling modes implemented
- ✅ `PipelineConfig` dataclass includes `stop_on_error: bool` field
- ✅ If `stop_on_error=True`, pipeline stops on first error
- ✅ If `stop_on_error=False`, pipeline collects errors and continues

**AC-1.10.2:** Retry logic implemented
- ✅ `RetryConfig` dataclass defines retry parameters (max_attempts, backoff_ms, retriable_errors)
- ✅ `execute_with_retry()` function implements exponential backoff
- ✅ Only retries errors in `retriable_errors` set (whitelist approach)

**AC-1.10.3:** Optional steps supported
- ✅ Pipeline supports marking steps as optional (continue on failure)
- ✅ Optional step failure logged as warning, not error

**AC-1.10.4:** Per-step metrics collected
- ✅ `PipelineResult.metrics` includes `step_metrics: Dict[str, StepMetrics]`
- ✅ Each `StepMetrics` includes: duration_ms, rows_in, rows_out, errors_count, warnings_count

**AC-1.10.5:** Error context implemented (Decision #4)
- ✅ Exceptions include structured context: error_type, operation, domain, row_number, field, input_data
- ✅ Error messages follow format: `[ERROR_TYPE] message | Domain: X | Row: N | Field: Y`

**AC-1.10.6:** Performance benchmarks run
- ✅ DataFrame step overhead <100ms (verified via pytest.mark.performance tests)
- ✅ Row step overhead <1ms per row for simple validation

**AC-1.10.7:** Unit tests pass
- ✅ Test stop_on_error modes (stop vs. collect)
- ✅ Test retry logic (successful retry, max retries exhausted)
- ✅ Test optional steps (failure doesn't stop pipeline)
- ✅ Test per-step metrics (correct values)
- ✅ Test error context (structured fields present)

---

### Story 1.11: Comprehensive CI/CD with Integration Tests

**AC-1.11.1:** Pytest markers configured
- ✅ `pytest.ini` or `pyproject.toml` defines markers: `unit`, `integration`, `performance`
- ✅ Tests tagged with appropriate markers

**AC-1.11.2:** Integration test database setup
- ✅ `pytest-postgresql` plugin configured
- ✅ Fixture `test_db` provisions temporary PostgreSQL
- ✅ Runs Alembic migrations before tests (Story 1.7 migrations applied)

**AC-1.11.3:** Integration tests implemented
- ✅ Test end-to-end pipeline: CSV → validate → database
- ✅ Test WarehouseLoader with real PostgreSQL
- ✅ Test Dagster job execution
- ✅ Minimum 3 integration tests covering critical paths

**AC-1.11.4:** CI pipeline enhanced
- ✅ CI runs unit tests: `pytest -v -m unit`
- ✅ CI runs integration tests: `pytest -v -m integration`
- ✅ CI collects coverage: `pytest --cov=src --cov-report=term-missing`

**AC-1.11.5:** Coverage thresholds defined
- ✅ `domain/` modules: >90% coverage target
- ✅ `io/` modules: >70% coverage target
- ✅ `orchestration/` modules: >60% coverage target
- ✅ CI warns (not blocks) if below threshold (enforcement after 30 days)

**AC-1.11.6:** CI execution time acceptable
- ✅ Unit tests: <30 seconds
- ✅ Integration tests: <3 minutes
- ✅ Total CI pipeline (type + lint + unit + integration): <5 minutes

**AC-1.11.7:** Coverage report generated
- ✅ CI uploads coverage report (Codecov, Coveralls, or artifact)
- ✅ Coverage visible in PR comments or CI logs

---

### Epic-Level Acceptance Criteria

**AC-EPIC-1.1:** All 11 stories completed with ACs met
- ✅ Each story's ACs verified (checklist above)

**AC-EPIC-1.2:** Sample end-to-end pipeline executes successfully
- ✅ Read CSV → Validate → Load to PostgreSQL works
- ✅ Dagster UI shows successful execution with logs

**AC-EPIC-1.3:** CI/CD pipeline passes
- ✅ All type checks, linting, unit tests, integration tests pass
- ✅ Coverage thresholds met or warnings documented

**AC-EPIC-1.4:** Documentation complete
- ✅ README explains project setup (`uv sync`, database migrations)
- ✅ Architecture boundaries documented
- ✅ Example usage of Pipeline, WarehouseLoader, Settings shown

**AC-EPIC-1.5:** Foundation ready for Epic 2
- ✅ Epic 2 can add Pydantic validators as RowTransformStep implementations
- ✅ Epic 2 can add pandera schemas as DataFrameStep implementations
- ✅ No rework required to Story 1.5 pipeline framework

## Traceability Mapping

This section maps Epic 1 stories back to PRD requirements and Architecture decisions, ensuring complete coverage.

### PRD Requirements → Epic 1 Stories

| PRD Requirement | Description | Epic 1 Story | Implementation Status |
|-----------------|-------------|--------------|----------------------|
| **REQ-001: Python 3.10+ Platform** | Modern Python with type system maturity | Story 1.1 | ✅ Core |
| **REQ-005: uv Package Manager** | 10-100x faster than pip, deterministic locks | Story 1.1 | ✅ Core |
| **REQ-010: Structured Logging** | JSON output, context binding, sanitization | Story 1.3 | ✅ Core |
| **REQ-015: Configuration Management** | Pydantic Settings, env var validation | Story 1.4 | ✅ Core |
| **REQ-020: Pipeline Framework** | Reusable transformation executor | Story 1.5, 1.10 | ✅ Core |
| **REQ-025: Database Transactional Loading** | All-or-nothing writes to PostgreSQL | Story 1.8 | ✅ Core |
| **REQ-030: Database Schema Migrations** | Alembic with rollback support | Story 1.7 | ✅ Core |
| **REQ-035: Dagster Orchestration** | CLI-first execution, UI for monitoring | Story 1.9 | ✅ MVP (schedules deferred to Epic 7) |
| **REQ-040: Type Safety (mypy strict)** | 100% type coverage NFR | Story 1.2, 1.11 | ✅ Core |
| **REQ-045: Test Coverage >80%** | Automated unit + integration tests | Story 1.11 | ✅ Core |
| **REQ-050: Clean Architecture** | domain/ ← io/ ← orchestration/ boundaries | Story 1.6 | ✅ Core |

### Architecture Decisions → Epic 1 Implementation

| Decision | Epic 1 Implementation | Stories | Notes |
|----------|----------------------|---------|-------|
| **Decision #3: Hybrid Pipeline Step Protocol** | `DataFrameStep` + `RowTransformStep` protocols | 1.5, 1.10 | Full implementation (DataFrame AND Row protocols) |
| **Decision #7: Naming Conventions** | PEP 8: snake_case modules, PascalCase classes | 1.1, 1.2 | Enforced via ruff linting in CI |
| **Decision #8: structlog with Sanitization** | JSON renderer, sensitive pattern redaction | 1.3 | Full implementation with test coverage |

**Deferred Decisions (Future Epics):**
- Decision #1: File-Pattern-Aware Version Detection → Epic 3 Story 3.1
- Decision #2: Legacy-Compatible Temporary Company IDs → Epic 5 Story 5.2
- Decision #4: Hybrid Error Context Standards → Partially implemented (Story 1.10), full usage in Epic 2+
- Decision #5: Explicit Chinese Date Format Priority → Epic 2 Story 2.4
- Decision #6: Stub-Only Enrichment MVP → Epic 5 Stories 5.1, 5.2, 5.5

### Non-Functional Requirements → Epic 1 Implementation

| NFR Category | Requirement | Epic 1 Implementation | Verification |
|--------------|-------------|----------------------|--------------|
| **Performance** | Pipeline overhead <100ms per step | Story 1.5 design, Story 1.10 benchmarks | pytest.mark.performance tests |
| **Performance** | Database batch insert <500ms/1000 rows | Story 1.8 batch processing | Integration tests measure timing |
| **Performance** | CI pipeline <5 min total | Stories 1.2, 1.11 optimizations | GitHub Actions timer |
| **Reliability** | Transactional integrity (100%) | Story 1.8 PostgreSQL transactions | Integration tests verify rollback |
| **Reliability** | Type safety (100% coverage) | Stories 1.2 mypy strict mode | CI blocks on type errors |
| **Maintainability** | Test coverage >80% | Story 1.11 pytest + coverage | CI enforces thresholds |
| **Security** | No secrets in git | Story 1.1 .gitignore, 1.2 gitleaks | CI secret scanning |
| **Security** | Parameterized SQL queries | Story 1.8 psycopg2 %s placeholders | Code review checklist |
| **Security** | Log sanitization | Story 1.3 SENSITIVE_PATTERNS | Unit tests verify redaction |
| **Observability** | Structured logs (JSON) | Story 1.3 structlog | All modules emit JSON logs |
| **Observability** | Execution audit trail | Story 1.7 pipeline_executions table | Database queries verify data |
| **Observability** | Dagster UI | Story 1.9 dagster dev | Manual UI testing |

### Story Dependencies (Implementation Order)

```
1.1 (Project Structure) → 1.2 (CI/CD) → 1.3 (Logging) → 1.4 (Config)
                                ↓
                          1.5 (Simple Pipeline)
                                ↓
                          1.6 (Architecture Boundaries)
                                ↓
                          1.7 (Database Schema)
                                ↓
                          1.8 (Database Loader)
                                ↓
                          1.9 (Dagster Setup) → 1.10 (Advanced Pipeline) → 1.11 (Enhanced CI/CD)
```

**Critical Path:** Stories 1.1 → 1.5 → 1.8 → 1.9 (end-to-end pipeline works)
**Parallel Work:** After 1.5, Stories 1.6, 1.7 can be developed in parallel

## Risks, Assumptions, Open Questions

### Risks

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner Story |
|---------|-------------|-------------|--------|---------------------|-------------|
| **R-1.1** | Story 1.5 pipeline framework too simple, requires rework when Epic 2 adds validation | MEDIUM | MEDIUM | Story 1.10 adds advanced features AFTER proving with 2+ domains (Epic 4). Protocols designed for extension without modification. | 1.5, 1.10 |
| **R-1.2** | pytest-postgresql setup complex, integration tests flaky or slow | LOW | MEDIUM | Use well-maintained pytest-postgresql plugin. Provision fresh database per test (isolated). CI retries flaky tests 1x. | 1.11 |
| **R-1.3** | Dagster UI learning curve for team unfamiliar with orchestration tools | LOW | LOW | Story 1.9 provides sample job with documentation. Dagster UI optional for MVP (CLI execution sufficient). | 1.9 |
| **R-1.4** | mypy strict mode too restrictive, blocks productivity | LOW | HIGH | Stories 1.1-1.4 prove mypy works before adding complexity. Incremental adoption: start with `domain/`, then `io/`. Use `# type: ignore` sparingly with justification comments. | 1.2 |
| **R-1.5** | Database connection pool exhaustion under load | LOW | MEDIUM | Story 1.8 uses conservative pool size (10). Load testing in Epic 7 will tune. Monitor connection metrics (logs). | 1.8 |
| **R-1.6** | structlog JSON logs too verbose, hard to read locally | LOW | LOW | Story 1.3 supports environment toggle: JSON for production, pretty-print for dev (via LOG_FORMAT env var). | 1.3 |
| **R-1.7** | Alembic migration conflicts if multiple developers work on schema | MEDIUM | LOW | Migration file naming uses timestamps (auto-sorted). Merge conflicts resolved manually. Docs warn: coordinate schema changes. | 1.7 |
| **R-1.8** | Clean Architecture boundaries too strict, hinder pragmatism | LOW | MEDIUM | Story 1.6 enforces via linting (not runtime). Allows pragmatic exceptions with `# noqa: IMPORT_BOUNDARY` and code review approval. | 1.6 |

### Assumptions

| Assumption ID | Description | Validation | Owner Story |
|---------------|-------------|------------|-------------|
| **A-1.1** | PostgreSQL database available for development and testing | Confirmed: team has local PostgreSQL or Docker available | 1.7, 1.8 |
| **A-1.2** | Python 3.10+ installed on all developer machines | Confirmed: corporate standard, enforced by .python-version file | 1.1 |
| **A-1.3** | uv package manager adoption acceptable to team | Assumption: team willing to learn uv (10x faster than pip justifies learning curve) | 1.1 |
| **A-1.4** | CI/CD platform supports GitHub Actions or GitLab CI | Confirmed: project repository type determines platform | 1.2, 1.11 |
| **A-1.5** | Batch size of 1000 rows suitable for all domains | Assumption: Epic 4 annuity testing will validate. Configurable via settings if needed. | 1.8 |
| **A-1.6** | Sample CSV data sufficient to prove end-to-end pipeline | Assumption: Real domain data comes in Epic 3 (file discovery) + Epic 4 (annuity) | 1.9 |
| **A-1.7** | Dagster CLI-first execution sufficient for MVP | Confirmed: PRD defers schedules/sensors to Epic 7 (post-MVP) | 1.9 |
| **A-1.8** | Structured logging overhead (<10ms per log call) acceptable | Assumption: structlog performance acceptable. Benchmarks in Story 1.10 will validate. | 1.3 |
| **A-1.9** | Test coverage thresholds (90%/70%/60%) achievable | Assumption: Thresholds based on industry standards. May adjust after Story 1.11 measurement. | 1.11 |
| **A-1.10** | No parallel pipeline execution needed in MVP | Confirmed: PRD defines sequential execution only. Parallelism deferred to Epic 7 if needed. | 1.5 |

### Open Questions

| Question ID | Description | Decision Needed By | Blocking Story | Current Status |
|-------------|-------------|---------------------|----------------|----------------|
| **Q-1.1** | Which CI/CD platform: GitHub Actions or GitLab CI? | Story 1.2 start | Story 1.2 | **OPEN** - Depends on repository hosting platform choice |
| **Q-1.2** | Should Dagster UI run in production or dev-only? | Story 1.9 start | Story 1.9 | **OPEN** - PRD suggests dev-only for MVP, but team preference may differ |
| **Q-1.3** | Pretty-print JSON logs for local dev or always JSON? | Story 1.3 start | Story 1.3 | **PROPOSED** - Environment toggle: LOG_FORMAT=json/pretty |
| **Q-1.4** | Database migration rollback strategy for production? | Story 1.7 start | Story 1.7 | **OPEN** - Need runbook for rollback procedures |
| **Q-1.5** | Coverage enforcement: warn or block on low coverage? | Story 1.11 start | Story 1.11 | **PROPOSED** - Warn for 30 days, then block (grace period for adoption) |
| **Q-1.6** | Retry logic: which errors are retriable? | Story 1.10 start | Story 1.10 | **PROPOSED** - Whitelist: ConnectionError, TimeoutError, psycopg2.OperationalError |
| **Q-1.7** | Database pool size tuning: 10 sufficient? | Story 1.8 start | Story 1.8 | **PROPOSED** - Start with 10, tune in Epic 7 performance testing |
| **Q-1.8** | Secret scanning: gitleaks or alternative tool? | Story 1.2 start | Story 1.2 | **PROPOSED** - gitleaks (open-source, GitHub Actions native support) |

### Decisions Required

**Immediate (Before Story 1.2 Start):**
1. **Q-1.1:** CI/CD platform choice (GitHub Actions vs. GitLab CI)
2. **Q-1.8:** Secret scanning tool (gitleaks recommended)

**Before Story 1.3 Start:**
3. **Q-1.3:** Log format toggle for local development

**Before Story 1.7 Start:**
4. **Q-1.4:** Production database migration rollback procedures

**Before Story 1.11 Start:**
5. **Q-1.5:** Coverage enforcement policy (warn vs. block)

## Test Strategy Summary

Epic 1 establishes the testing foundation that all subsequent epics will build upon. Story 1.11 delivers comprehensive test infrastructure covering unit, integration, and performance testing.

### Testing Pyramid

```
                    /\
                   /  \
                  / E2E \        ← Epic 6 (Parity Tests vs. Legacy)
                 /______\          Deferred to future epic
                /        \
               / Integration \     ← Story 1.11 (Database, Dagster, End-to-End)
              /______________\      ~10 tests, <3 min execution
             /                \
            /   Unit Tests     \   ← Stories 1.3-1.10 (Functions, Classes)
           /____________________\    ~50 tests, <30 sec execution
```

### Test Categories

#### 1. Unit Tests (Stories 1.3-1.10)

**Scope:** Pure functions, classes, business logic in `domain/` and `utils/`

**Characteristics:**
- ✅ No external dependencies (database, files, network)
- ✅ Mock all I/O operations
- ✅ Fast execution (<30 seconds total)
- ✅ High coverage target (>90% for `domain/`, `utils/`)

**Pytest Marker:** `@pytest.mark.unit`

**Example Test Files:**
```
tests/unit/
├── test_logging.py              # Story 1.3
│   ├── test_get_logger_returns_structlog
│   ├── test_sanitize_for_logging_redacts_passwords
│   └── test_context_binding
├── test_settings.py              # Story 1.4
│   ├── test_missing_database_url_raises_error
│   ├── test_production_requires_postgresql
│   └── test_settings_singleton
├── test_pipeline_core.py         # Story 1.5
│   ├── test_dataframe_step_execution
│   ├── test_row_transform_step_execution
│   ├── test_mixed_step_pipeline
│   └── test_pipeline_result_structure
└── test_pipeline_advanced.py    # Story 1.10
    ├── test_stop_on_error_modes
    ├── test_retry_logic_exponential_backoff
    ├── test_optional_steps
    └── test_error_context_structure
```

**Run Command:**
```bash
# Development (fast feedback)
uv run pytest -v -m unit

# With coverage
uv run pytest -v -m unit --cov=src/domain --cov=src/utils --cov-report=term-missing
```

---

#### 2. Integration Tests (Story 1.11)

**Scope:** Component integration with real external systems (PostgreSQL, filesystem)

**Characteristics:**
- ✅ Uses pytest-postgresql for temporary databases
- ✅ Runs Alembic migrations before tests
- ✅ Tests `io/` modules with real dependencies
- ✅ Medium execution time (<3 minutes total)
- ✅ Coverage target (>70% for `io/`, >60% for `orchestration/`)

**Pytest Marker:** `@pytest.mark.integration`

**Example Test Files:**
```
tests/integration/
├── conftest.py                   # Shared fixtures (test_db, alembic setup)
├── test_warehouse_loader.py      # Story 1.8
│   ├── test_successful_dataframe_load
│   ├── test_transactional_rollback_on_error
│   ├── test_column_projection_removes_extra_columns
│   └── test_batch_processing_1000_rows
├── test_dagster_jobs.py          # Story 1.9
│   ├── test_sample_pipeline_job_execution
│   ├── test_csv_read_op
│   └── test_load_to_db_op
└── test_end_to_end.py            # Story 1.11
    └── test_csv_to_database_pipeline  # Full E2E test
```

**Shared Fixtures (conftest.py):**
```python
import pytest
from pytest_postgresql import factories

# Provision temporary PostgreSQL database
postgresql = factories.postgresql_proc(port=None)  # Random port
test_db = factories.postgresql("postgresql")

@pytest.fixture
def migrated_db(test_db):
    """Apply Alembic migrations to test database."""
    # Run: alembic upgrade head
    # Yield connection
    # Teardown: alembic downgrade base
    ...
```

**Run Command:**
```bash
# Development (requires PostgreSQL running)
uv run pytest -v -m integration

# With coverage
uv run pytest -v -m integration --cov=src/io --cov=src/orchestration --cov-report=term-missing
```

---

#### 3. Performance Tests (Story 1.10)

**Scope:** Verify NFR performance targets are met

**Characteristics:**
- ✅ Benchmarks critical paths (pipeline overhead, database loading)
- ✅ Fails test if performance degrades below threshold
- ✅ Runs as part of CI (not skipped)

**Pytest Marker:** `@pytest.mark.performance`

**Example Tests:**
```python
import time
import pytest
import pandas as pd

@pytest.mark.performance
def test_pipeline_overhead_under_100ms():
    """Verify Decision #3: DataFrame step overhead <100ms."""
    pipeline = Pipeline("perf_test")
    pipeline.add_step(NoOpDataFrameStep())  # Does nothing

    df = pd.DataFrame({'col': range(10000)})

    start = time.perf_counter()
    result = pipeline.run(df)
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 100, f"Pipeline overhead {duration_ms:.2f}ms exceeds 100ms target"

@pytest.mark.performance
@pytest.mark.integration
def test_database_batch_insert_under_500ms(migrated_db):
    """Verify Story 1.8: Batch insert (1000 rows) <500ms."""
    loader = WarehouseLoader(connection_url=migrated_db)
    df = pd.DataFrame({'col1': range(1000), 'col2': ['test'] * 1000})

    start = time.perf_counter()
    result = loader.load_dataframe(df, table='test_table', schema='public')
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 500, f"Batch insert {duration_ms:.2f}ms exceeds 500ms target"
```

**Run Command:**
```bash
uv run pytest -v -m performance
```

---

#### 4. End-to-End Parity Tests (Epic 6 - Deferred)

**Scope:** Compare new pipeline outputs vs. legacy system (100% match required)

**Status:** Deferred to Epic 6 (after Epic 4 annuity migration)

**Pytest Marker:** `@pytest.mark.parity` (defined in Story 1.11, used in Epic 6)

---

### CI/CD Test Execution (Story 1.11)

**GitHub Actions / GitLab CI Workflow:**

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv sync

      - name: Run type checking
        run: uv run mypy src/ --strict

      - name: Run linting
        run: uv run ruff check src/

      - name: Run formatting check
        run: uv run ruff format --check src/

      - name: Run secret scanning
        uses: gitleaks/gitleaks-action@v2

      - name: Run unit tests
        run: uv run pytest -v -m unit --cov=src/domain --cov=src/utils --cov-report=xml

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/test
        run: uv run pytest -v -m integration --cov=src/io --cov=src/orchestration --cov-report=xml --cov-append

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

**Execution Time Targets:**
- Type check + Lint + Format: <1 min
- Unit tests: <30 sec
- Integration tests: <3 min
- **Total CI pipeline: <5 min**

---

### Coverage Thresholds (Story 1.11)

| Module Category | Minimum Coverage | Enforcement |
|-----------------|------------------|-------------|
| `src/domain/` | **90%** | CI warns if below (blocks after 30 days) |
| `src/utils/` | **90%** | CI warns if below |
| `src/io/` | **70%** | CI warns if below |
| `src/orchestration/` | **60%** | CI warns if below |

**Coverage Report Format:**
```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
src/domain/pipelines/core.py          120      5    96%   45-47, 89
src/domain/pipelines/types.py          30      0   100%
src/utils/logging.py                   45      2    96%   67-68
src/io/loader/warehouse_loader.py     150     30    80%   120-145, 200
-----------------------------------------------------------------
TOTAL                                 500     50    90%
```

---

### Test Data Management

**Fixtures Location:**
```
tests/fixtures/
├── sample_data.csv               # Story 1.9 (Dagster sample job)
├── test_config.yml               # Configuration for tests
└── expected_outputs/             # Golden datasets for parity tests (Epic 6)
```

**Test Database Strategy:**
- **Unit tests:** SQLite in-memory (no setup required)
- **Integration tests:** pytest-postgresql temporary PostgreSQL (isolated, fresh per test)
- **Local development:** Docker Compose PostgreSQL (persistent for debugging)

---

### Test Utilities (Story 1.11)

**Shared Test Helpers:**
```python
# tests/utils/factories.py
def create_sample_dataframe(rows: int = 100) -> pd.DataFrame:
    """Generate test DataFrame with realistic data."""
    return pd.DataFrame({
        'id': range(rows),
        'name': [f'Company_{i}' for i in range(rows)],
        'value': [100.0 * i for i in range(rows)]
    })

# tests/utils/assertions.py
def assert_dataframe_equal_ignore_order(df1: pd.DataFrame, df2: pd.DataFrame):
    """Assert DataFrames equal, ignoring row order."""
    pd.testing.assert_frame_equal(
        df1.sort_values(by=list(df1.columns)).reset_index(drop=True),
        df2.sort_values(by=list(df2.columns)).reset_index(drop=True),
        check_dtype=False
    )
```

---

### Quality Gates (CI Enforcement)

**CI blocks merge if:**
1. ❌ Type checking fails (mypy errors)
2. ❌ Linting fails (ruff violations)
3. ❌ Code not formatted (ruff format --check)
4. ❌ Secrets detected (gitleaks)
5. ❌ Unit tests fail
6. ❌ Integration tests fail

**CI warns (but allows merge) if:**
7. ⚠️ Coverage below threshold (grace period: 30 days, then blocks)

---

**End of Epic Technical Specification**

_This specification provides the complete technical blueprint for Epic 1: Foundation & Core Infrastructure. All 11 stories, acceptance criteria, dependencies, risks, and testing strategies are defined for implementation._

**Next Steps:**
1. Obtain stakeholder approval on this tech spec
2. Update sprint-status.yaml to mark epic-1 as "ready for implementation"
3. Begin Story 1.1 implementation following AC-1.1.X criteria

## Post-Review Follow-ups

- **2025-11-10 – Story 1.3:** Dev Notes still need a concrete `.bind(domain="annuity", execution_id="exec_123")` example plus the resulting JSON payload so downstream teams can reuse the context binding guidance.
- **2025-11-10 – Story 1.3:** Document the `LOG_LEVEL`, `LOG_TO_FILE`, and `LOG_FILE_DIR` settings (matching `work_data_hub.utils.logging`) in `.env.example` / developer docs so operational teams can enable file logging without reverse-engineering the module.
