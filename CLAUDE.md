# CLAUDE.md v1.02

This file provides comprehensive guidance to Claude Code when working with Python code in this repository.

## Core Development Philosophy

### KISS (Keep It Simple, Stupid)

Simplicity should be a key goal in design. Choose straightforward solutions over complex ones whenever possible. Simple solutions are easier to understand, maintain, and debug.

### YAGNI (You Aren't Gonna Need It)

Avoid building functionality on speculation. Implement features only when they are needed, not when you anticipate they might be useful in the future.

### Design Principles

- **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Open/Closed Principle**: Software entities should be open for extension but closed for modification.
- **Single Responsibility**: Each function, class, and module should have one clear purpose.
- **Fail Fast**: Check for potential errors early and raise exceptions immediately when issues occur.

## 🧱 Code Structure & Modularity

### File and Function Limits

- **Never create a file longer than 500 lines of code**. If approaching this limit, refactor by splitting into modules.
- **Functions should be under 50 lines** with a single, clear responsibility.
- **Classes should be under 100 lines** and represent a single concept or entity.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
- **Line length should be max 100 characters** ruff rule in pyproject.toml
- Use the project virtual environment for all Python commands; prefer running tools via uv:
  - Setup: uv venv && uv sync
  - Run: uv run <command>

### Project Architecture

This project follows a configuration‑driven, vertically sliced ETL architecture with clear boundaries between orchestration, IO, domain, and configuration. Tests live under the top‑level `tests/` directory (unit, integration, and end‑to‑end).

```text
src/work_data_hub/
  config/
    settings.py            # pydantic‑settings; env vars prefixed WDH_*
    schema.py              # config schema validation
    data_sources.yml       # discovery patterns, selection, table/pk
  io/
    connectors/
      file_connector.py    # config‑driven file discovery
    readers/
      excel_reader.py      # resilient Excel ingestion
    loader/
      warehouse_loader.py  # PostgreSQL loader (plan‑only or execute)
  domain/
    trustee_performance/
      models.py            # Pydantic v2 models (in/out)
      service.py           # pure transformation functions
  orchestration/
    ops.py                 # discover/read/process/load ops
    jobs.py                # single/multi‑file jobs + CLI entry
    schedules.py           # production schedules
    sensors.py             # file/new‑data sensors
    repository.py          # Dagster Definitions registry
  utils/
    types.py               # shared types/helpers

tests/
  e2e/                     # end‑to‑end flows
  domain/
  io/
  config/
  fixtures/

legacy/annuity_hub/        # reference during migration (read‑only)
```

Dependencies Rule

- Orchestration may depend on IO, Domain, Config, and Utils.
- Domain must not import Orchestration.
- IO should not import Orchestration.
- Config and Utils provide shared, dependency‑free infrastructure.

## 🛠️ Development Environment

### UV Package Management

This project uses UV for blazing-fast Python package and environment management.

```bash
# Create virtual environment
uv venv

# Sync dependencies
uv sync

# Add a package ***NEVER UPDATE A DEPENDENCY DIRECTLY IN PYPROJECT.toml***
# ALWAYS USE UV ADD
uv add requests

# Add development dependency
uv add --dev pytest ruff mypy

# Remove a package
uv remove requests

# Run commands in the environment
uv run python script.py
uv run pytest
uv run ruff check src/
```

### Development Commands

```bash
# Run all tests
uv run pytest

# Focus tests by pattern
uv run pytest -k "<pattern>" -v

# Run specific tests with verbose output
uv run pytest tests/test_module.py -v

# Run tests with coverage (optional)
uv run pytest --cov=src --cov-report=term-missing

# Format code
uv run ruff format .

# Check linting (scoped to src/)
uv run ruff check src/

# Fix linting issues automatically
uv run ruff check src/ --fix

# Type checking
uv run mypy src/

# Optional: pre-commit hooks (only if configured)
# uv run pre-commit run --all-files
```

## 📋 Style & Conventions

### Python Style Guide

- **Follow PEP8** with these specific choices:
  - Line length: 100 characters (set by Ruff in pyproject.toml)
  - Use double quotes for strings
  - Use trailing commas in multi-line structures
- **Always use type hints** for function signatures and class attributes
- **Format with `ruff format`** (faster alternative to Black)
- **Use `pydantic` v2** for data validation and settings management

### Docstring Standards

Use Google-style docstrings for all public functions, classes, and modules:

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    min_amount: Decimal = Decimal("0.01")
) -> Decimal:
    """
    Calculate the discounted price for a product.

    Args:
        price: Original price of the product
        discount_percent: Discount percentage (0-100)
        min_amount: Minimum allowed final price

    Returns:
        Final price after applying discount

    Raises:
        ValueError: If discount_percent is not between 0 and 100
        ValueError: If final price would be below min_amount

    Example:
        >>> calculate_discount(Decimal("100"), 20)
        Decimal('80.00')
    """
```

### Naming Conventions

- **Variables and functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private attributes/methods**: `_leading_underscore`
- **Type aliases**: `PascalCase`
- **Enum values**: `UPPER_SNAKE_CASE`

## 🧪 Testing Strategy

### Test-Driven Development (TDD)

1. **Write the test first** - Define expected behavior before implementation
2. **Watch it fail** - Ensure the test actually tests something
3. **Write minimal code** - Just enough to make the test pass
4. **Refactor** - Improve code while keeping tests green
5. **Repeat** - One test at a time

### Testing Best Practices

```python
# Always use pytest fixtures for setup
import pytest
from datetime import datetime

@pytest.fixture
def sample_user():
    """Provide a sample user for testing."""
    return User(
        id=123,
        name="Test User",
        email="test@example.com",
        created_at=datetime.now()
    )

# Use descriptive test names
def test_user_can_update_email_when_valid(sample_user):
    """Test that users can update their email with valid input."""
    new_email = "newemail@example.com"
    sample_user.update_email(new_email)
    assert sample_user.email == new_email

# Test edge cases and error conditions
def test_user_update_email_fails_with_invalid_format(sample_user):
    """Test that invalid email formats are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        sample_user.update_email("not-an-email")
    assert "Invalid email format" in str(exc_info.value)
```

### Test Organization

- Unit tests: Test individual functions/methods in isolation
- Integration tests: Test component interactions
- End-to-end tests: Test complete user workflows
- Keep test files next to the code they test
- Use `conftest.py` for shared fixtures
- Aim for 80%+ code coverage, but focus on critical paths

## 🚨 Error Handling

Use domain‑specific exceptions at clear boundaries (connector → reader → domain service → loader → orchestration). Fail fast on invalid configuration or mode; provide actionable messages.

Custom exceptions (examples in this repo)

```python
# IO / Readers
class ExcelReadError(Exception):
    """Raised when Excel file reading fails."""

# IO / Connectors
class DataSourceConnectorError(Exception):
    """Raised when data source discovery or config handling fails."""

# IO / Loader
class DataWarehouseLoaderError(Exception):
    """Raised for validation or execution errors in warehouse loading."""
```

Error boundaries and patterns

- Connectors (discovery): Validate YAML structure and domain keys. Raise DataSourceConnectorError on missing sections, invalid regex, or unknown domain.
- Readers (Excel): Raise ExcelReadError for missing/invalid sheet, empty files, parse/engine errors; return [] only for legitimate "no data" cases.
- Domain services: Keep pure and deterministic. Validate inputs; aggregate per‑row issues as warnings, and raise a single transformation error only when error rate crosses a threshold.
- Loader (DB plan/execute): Validate mode, PK, and input shape; raise DataWarehouseLoaderError for invalid configuration or database execution failures.
- Orchestration (ops/jobs): Catch at op boundary, log with context, then re‑raise. Do not silently swallow exceptions.

Example: op‑level handling

```python
@op
def read_excel_op(context, config, file_paths):
    if not file_paths:
        context.log.warning("No file paths provided to read_excel_op")
        return []
    try:
        rows = read_excel_rows(file_paths[0], sheet=config.sheet)
        context.log.info(
            "Excel reading completed",
            extra={"file": file_paths[0], "sheet": config.sheet, "rows": len(rows)}
        )
        return rows
    except Exception as e:
        context.log.error(f"Excel reading failed: {e}")
        raise
```

Sensors: prefer SkipReason over hard failures

```python
@sensor(job=trustee_performance_multi_file_job)
def trustee_new_files_sensor(context):
    try:
        files = DataSourceConnector().discover("trustee_performance")
        if not files:
            return SkipReason("No trustee performance files found")
        # ...
    except Exception as e:
        context.log.error(f"File discovery sensor error: {e}")
        return SkipReason(f"Sensor error: {e}")
```

Guidelines

- Raise specific exceptions; avoid generic bare exceptions in library code.
- Validate early at the edges; keep core transformations pure.
- Log once at the boundary and re‑raise; avoid duplicate noisy logs.
- Do not expose secrets or full payloads in error messages.

## 📓 Logging Strategy

Use standard logging for libraries and Dagster’s `context.log` inside ops/sensors. Prefer structured, concise summaries with key context.

Levels and usage

- DEBUG: verbose details for diagnosis (e.g., compiled patterns, selected files).
- INFO: pipeline summaries (counts, domains, table names).
- WARNING: recoverable anomalies (missing optional files, empty results).
- ERROR: failures with actionable context (which step, which file/config).

Patterns (consistent with repository)

```python
# Library modules
import logging
logger = logging.getLogger(__name__)

logger.debug("Compiled pattern", extra={"domain": domain, "pattern": pattern})
logger.info("Selected files", extra={"domain": domain, "count": len(selected)})

# Orchestration
context.log.info(
    "Load completed",
    extra={"table": cfg.table, "mode": cfg.mode, "deleted": res["deleted"], "inserted": res["inserted"]}
)
context.log.error(f"Load operation failed: {e}")
```

Best practices

- In ops/sensors, prefer `context.log` to include run metadata automatically.
- Include domain, file path (or basename), counts, and config path; avoid logging large payloads.
- Do not log full SQL statements with sensitive values; summarize and/or log parameter counts instead.
- Keep messages consistent and searchable; prefer key=value or structured extras.

## 🔧 Configuration Management

### Environment Variables and Settings

This project uses Pydantic v2 Settings with an `WDH_` environment prefix and nested keys via double underscore. See `.env.example` for available variables.

```python
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Core
    app_name: str = Field(default="WorkDataHub")
    debug: bool = False
    log_level: str = "INFO"

    # Data processing
    data_base_dir: str = "./data"
    data_sources_config: str = "./src/work_data_hub/config/data_sources.yml"

    # Performance
    max_file_size_mb: int = 100
    max_workers: int = 4
    dev_sample_size: Optional[int] = None

    # Database (nested via WDH_DATABASE__*)
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "wdh_user"
    database_password: str = "changeme"
    database_db: str = "wdh"
    database_uri: Optional[str] = None

    def get_database_connection_string(self) -> str:
        if self.database_uri:
            return self.database_uri
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_db}"
        )

    model_config = SettingsConfigDict(
        env_prefix="WDH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

Usage

```python
from src.work_data_hub.config.settings import get_settings

settings = get_settings()
dsn = settings.get_database_connection_string()
```

Common env vars

- `WDH_DATA_BASE_DIR`, `WDH_DATA_SOURCES_CONFIG`
- `WDH_DATABASE__HOST`, `WDH_DATABASE__PORT`, `WDH_DATABASE__USER`, `WDH_DATABASE__PASSWORD`, `WDH_DATABASE__DB`
- Optional override: `WDH_DATABASE__URI`

## 🏗️ Data Models and Validation

### Example Pydantic Models strict with pydantic v2

```python
from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

class ProductBase(BaseModel):
    """Base product model with common fields."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    category: str
    tags: List[str] = []

    @validator('price')
    def validate_price(cls, v):
        if v > Decimal('1000000'):
            raise ValueError('Price cannot exceed 1,000,000')
        return v

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class ProductCreate(ProductBase):
    """Model for creating new products."""
    pass

class ProductUpdate(BaseModel):
    """Model for updating products - all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class Product(ProductBase):
    """Complete product model with database fields."""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True  # Enable ORM mode
```

## 🔄 Git Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring
- `test/*` - Test additions or fixes

### Commit Message Format

Never include claude code, or written by claude code in commit messages

```commit
<type>(<scope>): <subject>

<body>

<footer>
```

Types: feat, fix, docs, style, refactor, test, chore

Example:

```commit
feat(auth): add two-factor authentication

- Implement TOTP generation and validation
- Add QR code generation for authenticator apps
- Update user model with 2FA fields

Closes #123
```

## 🗄️ Database Naming Standards

### Entity-Specific Primary Keys

All database tables use entity-specific primary keys for clarity and consistency:

```sql
-- ✅ STANDARDIZED: Entity-specific primary keys
sessions.session_id UUID PRIMARY KEY
leads.lead_id UUID PRIMARY KEY
messages.message_id UUID PRIMARY KEY
daily_metrics.daily_metric_id UUID PRIMARY KEY
agencies.agency_id UUID PRIMARY KEY
```

### Field Naming Conventions

```sql
-- Primary keys: {entity}_id
session_id, lead_id, message_id

-- Foreign keys: {referenced_entity}_id
session_id REFERENCES sessions(session_id)
agency_id REFERENCES agencies(agency_id)

-- Timestamps: {action}_at
created_at, updated_at, started_at, expires_at

-- Booleans: is_{state}
is_connected, is_active, is_qualified

-- Counts: {entity}_count
message_count, lead_count, notification_count

-- Durations: {property}_{unit}
duration_seconds, timeout_minutes
```

### Repository Pattern Auto-Derivation

The enhanced BaseRepository automatically derives table names and primary keys:

```python
# ✅ STANDARDIZED: Convention-based repositories
class LeadRepository(BaseRepository[Lead]):
    def __init__(self):
        super().__init__()  # Auto-derives "leads" and "lead_id"

class SessionRepository(BaseRepository[AvatarSession]):
    def __init__(self):
        super().__init__()  # Auto-derives "sessions" and "session_id"
```

**Benefits**:

- ✅ Self-documenting schema
- ✅ Clear foreign key relationships
- ✅ Eliminates repository method overrides
- ✅ Consistent with entity naming patterns

### Model-Database Alignment

Models mirror database fields exactly to eliminate field mapping complexity:

```python
# ✅ STANDARDIZED: Models mirror database exactly
class Lead(BaseModel):
    lead_id: UUID = Field(default_factory=uuid4)  # Matches database field
    session_id: UUID                               # Matches database field
    agency_id: str                                 # Matches database field
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        alias_generator=None  # Use exact field names
    )
```

### Orchestration Standards

Use Dagster jobs/ops for all pipeline orchestration. Keep ops thin and side‑effect aware; delegate transformation to pure domain services and IO to dedicated modules.

Guidelines

- Jobs compose ops: discover → read → process → load.
- Ops take validated Config objects; return JSON‑serializable results.
- Use `Definitions` (repository.py) to register jobs/schedules/sensors.
- Keep ops idempotent where practical; log concise summaries with context.

Example (composition pattern)

```python
@job
def trustee_performance_job():
    discovered_paths = discover_files_op()
    excel_rows = read_excel_op(discovered_paths)
    processed = process_trustee_performance_op(excel_rows, discovered_paths)
    load_op(processed)
```

Configuration (run_config pattern)

```yaml
ops:
  discover_files_op:
    config:
      domain: trustee_performance
  read_excel_op:
    config:
      sheet: 0
  load_op:
    config:
      table: trustee_performance
      mode: delete_insert
      pk: [report_date, plan_code, company_code]
      plan_only: true
```

Do

- Keep orchestration free of domain specifics beyond wiring.
- Use `context.log` at boundaries; re‑raise on failures.

Don’t

- Add HTTP routes or web handlers in this repository.
- Embed business rules inside ops when they belong to domain services.

## 📝 Documentation Standards

### Code Documentation

- Every module should have a docstring explaining its purpose
- Public functions must have complete docstrings
- Complex logic should have inline comments with `# Reason:` prefix
- Keep README.md updated with setup instructions and examples
- Maintain CHANGELOG.md for version history

### Pipeline Documentation

Document pipelines, not HTTP APIs. Provide:

- A short purpose statement for each job/op.
- Inputs/outputs, including config schema and example run_config.
- Error boundaries and failure modes (what raises where).
- Observability notes (key logs/metrics) and validation gates.

Example op docstring

```python
def load_op(context, config, processed_rows):
    """
    Load processed data to the warehouse or return a plan (plan_only).

    Args:
        context: Dagster execution context
        config: LoadConfig (table, mode, pk, plan_only)
        processed_rows: JSON-serializable records

    Returns:
        Dict with execution metadata (and 'sql_plans' when plan_only)

    Raises:
        DataWarehouseLoaderError: invalid config or DB execution failure
    """
```

Notes

- Summarize SQL plans (counts) rather than logging full SQL with parameters.
- Reference `data_sources.yml` for table/pk binding where applicable.
- Keep examples minimal and copy‑pastable (YAML or CLI).

## 🚀 Performance Considerations

Optimize for end-to-end pipeline throughput and safety. Profile only when needed; prefer simple, bounded changes (sampling, chunking).

I/O and discovery

- Pre‑compile regex patterns and use directory exclusions and max_depth to reduce traversal cost.
- Prefer selection strategies (e.g., latest_by_year_month or latest_by_mtime) to avoid processing historical files unnecessarily.
- Log counts and selected files; avoid listing the entire tree at INFO level.

Excel reading

- Use explicit sheet indices (or names) to avoid workbook scanning overhead.
- For development and diagnostics, sample with ExcelReader(max_rows=N) to bound memory and CPU.
- Keep column typing simple; defer heavy conversions to domain models when possible.

Transformation

- Keep services pure and deterministic; avoid global state and side effects.
- Fail fast on structurally invalid rows but continue processing the batch when safe.
- Quantize decimals in models (Pydantic validators) to avoid downstream precision churn.

Loading (PostgreSQL)

- Tune chunk_size for INSERT batching (typical range: 500–2000). Larger chunks reduce round‑trips but increase memory footprint.
- Ensure PKs and indexes exist for delete_insert mode to keep DELETE selective.
- Use plan‑only mode to validate SQL shape and row counts before executing against DB.
- Avoid logging full SQL with payloads; prefer summarizing operation counts and parameter lengths.

Example (plan‑only vs execute)

```python
# Plan-only
plan = load(
    table="trustee_performance",
    rows=processed_dicts,
    mode="delete_insert",
    pk=["report_date", "plan_code", "company_code"],
    conn=None,                  # Plan-only
)
# Execute with tuned chunk size (inside ops, connection managed safely)
result = load(
    table="trustee_performance",
    rows=processed_dicts,
    mode="delete_insert",
    pk=["report_date", "plan_code", "company_code"],
    conn=conn,                  # psycopg2 connection
)
```

Memory hygiene

- Limit read volume during development (max_rows or file subsets).
- Avoid constructing massive intermediate structures; prefer chunked operations for load.
- Summarize payloads in logs (counts, sizes), not raw rows.

## 🛡️ Security Best Practices

Secrets and configuration

- Use environment variables with the WDH_ prefix; do not commit .env files.
- Reference `.env.example` for required/optional variables; use double underscore for nested keys (e.g., `WDH_DATABASE__HOST`).
- Never log secrets or full DSNs; keep DSN handling inside configuration helpers.

Database safety

- Use parameterized operations (psycopg2) and JSONB adapters for dict/list values.
- Apply least‑privilege DB credentials suitable for the target schema.
- Keep transactional integrity: wrap DELETE + INSERT in a single transaction and rollback on failure.

Logging and error messages

- No secrets, passwords, or full SQL with parameters in logs.
- Prefer concise summaries: table, mode, counts (deleted/inserted/batches).
- On failures, log which step and context (domain, file name, config path) without leaking data.

Secret scanning and CI

- Keep optional secret scanning (e.g., pre‑commit/gitleaks) enabled where available.
- Validation gates must pass before merging (ruff, mypy, pytest).

Usage example

```python
from src.work_data_hub.config.settings import get_settings
settings = get_settings()

# Safe DSN retrieval
dsn = settings.get_database_connection_string()

# In ops, prefer plan-only first; switch to execute via config
context.log.info(
    "Connecting to database for execution",
    extra={"table": cfg.table, "mode": cfg.mode}
)
```

## 🔍 Debugging Tools

### Debugging Commands

```bash
# Interactive debugging with ipdb
uv add --dev ipdb
# Add breakpoint: import ipdb; ipdb.set_trace()

# Memory profiling
uv add --dev memory-profiler
uv run python -m memory_profiler script.py

# Line profiling
uv add --dev line-profiler
# Add @profile decorator to functions

# Debug with rich traceback
uv add --dev rich
# In code: from rich.traceback import install; install()
```

## 📊 Monitoring and Observability

Monitor pipelines through Dagster schedules, sensors, and structured logs. Aim for early, actionable signals with minimal noise.

### Dagster Components

- Schedules
  - Use a fixed daily schedule (e.g., 02:00 Asia/Shanghai) that builds run_config from `data_sources.yml`.
  - Run in execute mode with multi‑file processing and consistent load settings.

- Sensors
  - New files sensor: discovers files for a domain, filters by modification time using a cursor, and triggers a job with a unique run_key. Return `SkipReason` when there is nothing to do.
  - Data quality sensor: performs lightweight health checks (discovery counts, file accessibility, plan‑only SQL probe) and logs the outcome; prefer `SkipReason` over raising failures.

Example patterns

```python
# Cursor-based new-file detection (pseudo)
files = DataSourceConnector().discover("trustee_performance")
last_mtime = float(context.cursor) if context.cursor else 0.0
new_files = [f for f in files if f.metadata.get("modified_time", 0) > last_mtime]
if not new_files:
    return SkipReason("No new files detected")
max_mtime = max(f.metadata.get("modified_time", 0) for f in new_files)
context.update_cursor(str(max_mtime))
return RunRequest(run_key=f"new_files_{max_mtime}", run_config=...)
```

### Logging Fields (canonical)

Use consistent fields to make logs searchable and comparable across runs:

- Domain discovery: `domain`, `config_path`, `discovered_count`, `selected_count`
- Reading: `file`, `sheet`, `rows`
- Processing: `source_file`, `input_rows`, `output_records`, `domain`
- Loading: `table`, `mode`, `plan_only`, `deleted`, `inserted`, `batches`
- Sensor state: `cursor_last_mtime`, `new_files_count`, `run_key`

Recommended pattern

```python
context.log.info(
    "Load completed",
    extra={
        "table": cfg.table,
        "mode": cfg.mode,
        "plan_only": cfg.plan_only,
        "deleted": res.get("deleted", 0),
        "inserted": res.get("inserted", 0),
        "batches": res.get("batches", 0),
    },
)
```

### Data-Quality Signals

- No files discovered or accessible for an expected domain/path.
- Zero records produced after read/process (unexpected emptiness).
- Plan‑only SQL probe yields `None` SQL or mismatched column sets.
- Excessive validation warnings or error rates in transformations.

Treat these as warnings unless they indicate a hard failure; escalate to ERROR when the pipeline cannot proceed safely.

### Alerting (placeholder)

- Route alerts via environment‑based channels (e.g., Slack/email) when available.
- Use thresholds to avoid noisy alerts (e.g., repeated “no new files” within a window).
- Prefer summaries (counts, domains, time windows) over raw payloads.

### Operational Recipes

- Reproduce locally with plan‑only mode first (CLI), then switch to execute.
- Verify configuration sources: `WDH_DATA_BASE_DIR`, `WDH_DATA_SOURCES_CONFIG`.
- Inspect sensor cursor values and run_key continuity to confirm detection logic.
- Use focused tests (`-k <pattern>`) and domain unit tests before E2E.

## 📚 Useful Resources

### Essential Tools

- UV Documentation: https://github.com/astral-sh/uv
- Ruff: https://github.com/astral-sh/ruff
- Pytest: https://docs.pytest.org/
- Pydantic: https://docs.pydantic.dev/
- Dagster: https://docs.dagster.io/

### Python Best Practices

- PEP 8: https://pep8.org/
- PEP 484 (Type Hints): https://www.python.org/dev/peps/pep-0484/
- The Hitchhiker's Guide to Python: https://docs.python-guide.org/

## ⚠️ Important Notes

- **NEVER ASSUME OR GUESS** - When in doubt, ask for clarification
- **Always verify file paths and module names** before use
- **Keep CLAUDE.md updated** when adding new patterns or dependencies
- **Test your code** - No feature is complete without tests
- **Document your decisions** - Future developers (including yourself) will thank you

## 🔍 Search Command Requirements

**CRITICAL**: Always use MCP Serena or `rg` (ripgrep) instead of traditional `grep` and `find` commands:

```bash
# ❌ Don't use grep
grep -r "pattern" .

# ✅ Use rg instead
rg "pattern"

# ❌ Don't use find with name
find . -name "*.py"

# ✅ Use rg with file filtering
rg --files | rg "\.py$"
# or
rg --files -g "*.py"
```

**Enforcement Rules:**

```bash
(
    r"^grep\b(?!.*\|)",
    "Use 'rg' (ripgrep) instead of 'grep' for better performance and features",
),
(
    r"^find\s+\S+\s+-name\b",
    "Use 'rg --files | rg pattern' or 'rg --files -g pattern' instead of 'find -name' for better performance",
),
```

## 🚀 GitHub Flow Workflow Summary

main (protected) ←── PR ←── feature/your-feature
↓ ↑
deploy development

### Daily Workflow

1. git checkout main && git pull origin main
2. git checkout -b feature/new-feature
3. Make changes + tests
4. git push origin feature/new-feature
5. Create PR → Review → Merge to main

---

_This document is a living guide. Update it as the project evolves and new patterns emerge._
