# Source Tree Analysis

**Project:** WorkDataHub Data Platform
**Generated:** 2025-12-06
**Architecture:** Domain-Driven Design (DDD) with Layered Architecture
**Last Rescan:** Epic 5.5 - Added annuity_income domain

---

## Project Root Structure

```
WorkDataHub/
├── src/work_data_hub/          # Main application source code
│   ├── domain/                 # ✓ Domain layer (business logic)
│   ├── io/                     # ✓ I/O layer (data access)
│   ├── orchestration/          # ✓ Dagster orchestration layer
│   ├── cleansing/              # Data cleansing rules and integrations
│   ├── auth/                   # External system authentication
│   ├── config/                 # Configuration management
│   ├── utils/                  # Utility functions and helpers
│   └── scripts/                # CLI scripts and tools
│
├── io/schema/migrations/       # ✓ Alembic database migrations
├── tests/                      # ✓ Test suites (unit, integration, e2e)
├── docs/                       # ✓ Documentation (90+ files)
├── config/                     # External configuration files
├── legacy/                     # Legacy code (pre-refactor)
├── reference/                  # Reference materials and archives
├── logs/                       # Application logs (rotated daily)
│
├── .github/workflows/          # CI/CD pipeline definitions
├── .bmad/                      # BMad workflow management
├── .cache/                     # Runtime cache
├── pyproject.toml              # ✓ Python project configuration
├── alembic.ini                 # ✓ Database migration config
├── uv.lock                     # Dependency lock file
└── README.md                   # Project overview
```

---

## Critical Directory Details

### 1. `src/work_data_hub/domain/` - Domain Layer (Business Logic)

**Purpose:** Domain-Driven Design layer containing all business logic and domain models

```
domain/
├── annuity_performance/        # 📊 Annuity performance domain (Epic 4)
│   ├── models.py               # Pydantic models (In/Out)
│   ├── schemas.py              # Pandera validation schemas
│   ├── service.py              # Domain service (orchestration)
│   ├── pipeline_builder.py     # Pipeline builder configuration
│   ├── helpers.py              # Business logic helpers
│   └── constants.py            # Domain constants
│
├── annuity_income/             # 📊 Annuity income domain (Epic 5.5) ✨NEW
│   ├── models.py               # Pydantic models (In/Out)
│   ├── schemas.py              # Pandera validation schemas
│   ├── service.py              # Domain service (orchestration)
│   ├── pipeline_builder.py     # Pipeline builder configuration
│   ├── helpers.py              # Business logic helpers
│   └── constants.py            # Domain constants
│
├── sample_trustee_performance/ # 📊 Trustee performance domain (sample)
│   ├── models.py               # Sample domain models
│   └── service.py              # Sample domain service
│
├── company_enrichment/         # 🏢 Company ID enrichment service
│   ├── models.py               # Enrichment data models
│   ├── service.py              # Enrichment service logic
│   └── lookup_queue.py         # Async lookup queue
│
├── reference_backfill/         # 📋 Reference data backfill
│   ├── models.py               # Reference data models
│   └── service.py              # Backfill service
│
└── pipelines/                  # 🔧 Reusable pipeline framework
    ├── core.py                 # Pipeline interface and base
    ├── builder.py              # Pipeline builder pattern
    ├── config.py               # Pipeline configuration models
    ├── adapters.py             # Dagster adapters
    ├── exceptions.py           # Pipeline-specific exceptions
    ├── types.py                # Type aliases and protocols
    ├── examples.py             # Example pipeline implementations
    │
    ├── steps/                  # Generic pipeline steps
    │   ├── calculated_field_step.py    # Field calculation
    │   ├── column_normalization.py     # Column name normalization
    │   ├── customer_name_cleansing.py  # Customer name cleaning
    │   ├── date_parsing.py             # Date parsing (CN + ISO)
    │   ├── field_cleanup.py            # Field cleanup rules
    │   ├── filter_step.py              # Row filtering
    │   ├── mapping_step.py             # Value mapping
    │   └── replacement_step.py         # Value replacement
    │
    └── validation/             # Validation framework
        ├── helpers.py          # Validation helper functions
        └── summaries.py        # Validation summary generation
```

**Key Patterns:**
- **Standard Domain Pattern** (Story 1.12): Each domain follows consistent structure
- **Service Layer:** Domain services orchestrate business workflows
- **Pipeline Steps:** Reusable, testable transformation units
- **Models:** Separate Input (Bronze) and Output (Gold) models

---

### 2. `src/work_data_hub/io/` - I/O Layer (Data Access)

**Purpose:** All external data access (files, databases, APIs) - isolated from domain logic

```
io/
├── readers/                    # Data readers
│   ├── excel_reader.py         # Excel file reader (openpyxl)
│   └── __init__.py
│
├── connectors/                 # External system connectors
│   ├── eqc_client.py           # EQC API client (company enrichment)
│   ├── file_connector.py       # File system connector
│   └── __init__.py
│
└── loader/                     # Database loaders
    ├── warehouse_loader.py     # PostgreSQL warehouse loader
    ├── company_mapping_loader.py   # Company mapping loader
    ├── company_enrichment_loader.py # Enrichment data loader
    └── __init__.py
```

**Architecture Rules:**
- ✅ Domain layer **cannot** import from `io` (enforced by Ruff TID251)
- ✅ I/O layer provides interfaces for domain layer
- ✅ All external dependencies isolated here

---

### 3. `src/work_data_hub/orchestration/` - Orchestration Layer

**Purpose:** Dagster-specific orchestration code (jobs, ops, schedules, sensors)

```
orchestration/
├── repository.py               # Dagster repository definition
├── jobs.py                     # Job definitions
├── ops.py                      # Dagster ops (operations)
├── schedules.py                # Scheduled jobs
├── sensors.py                  # File/event sensors
└── __init__.py
```

**Integration Pattern:**
- Orchestration → Domain services (calls domain logic)
- Orchestration → I/O adapters (for data access)
- **Never:** Orchestration → Direct database access

---

### 4. `src/work_data_hub/infrastructure/` - Infrastructure Layer (Epic 5)

**Purpose:** Reusable infrastructure components extracted from domain layer

```
infrastructure/
├── cleansing/                  # 🧹 Data cleansing framework
│   ├── registry.py             # Cleansing rule registry
│   ├── rules/                  # Rule implementations
│   │   ├── string_rules.py     # String cleansing rules
│   │   └── numeric_rules.py    # Numeric cleansing rules
│   ├── integrations/           # Framework integrations
│   │   └── pydantic_adapter.py # Pydantic integration
│   └── settings/               # Cleansing configuration
│       └── cleansing_rules.yml # Rule definitions
│
├── enrichment/                 # 🏢 Company enrichment utilities
│   ├── company_id_resolver.py  # Company ID resolution
│   ├── normalizer.py           # Name normalization
│   └── types.py                # Enrichment types
│
├── settings/                   # ⚙️ Configuration management
│   ├── data_source_schema.py   # Data source schema validation
│   └── loader.py               # Configuration loader
│
├── transforms/                 # 🔄 Data transformation utilities
│   ├── base.py                 # Base transform classes
│   └── standard_steps.py       # Standard pipeline steps
│
└── validation/                 # ✅ Validation utilities
    ├── error_handler.py        # Error handling
    ├── report_generator.py     # Validation reports
    ├── schema_helpers.py       # Schema utilities
    └── types.py                # Validation types
```

**Architecture Notes:**
- Extracted from domain layer (Epic 5 refactoring)
- Reduces domain layer from ~3,446 lines to <500 lines
- Provides reusable components for all domains

---

### 5. `src/work_data_hub/auth/` - Authentication

**Purpose:** External system authentication and session management

```
auth/
├── models.py                   # Auth data models
├── eqc_auth_handler.py         # EQC authentication handler
├── eqc_auth_opencv.py          # EQC OpenCV-based auth
├── enhanced_eqc_handler.py     # Enhanced EQC handler
├── eqc_settings.py             # EQC configuration
└── EQC_AUTH_OPENCV_ISSUE_REPORT.md  # Auth troubleshooting guide
```

**Features:**
- Playwright-based browser automation
- Session persistence and reuse
- Automatic captcha handling (slider + OTP)
- Token extraction and refresh

---

### 6. `src/work_data_hub/config/` - Configuration Management

**Purpose:** Configuration loading, validation, and mapping management

```
config/
├── settings.py                 # Pydantic Settings (Story 1.4)
├── schema.py                   # Configuration schemas
├── mapping_loader.py           # YAML mapping loader
├── data_sources.yml            # Data source configurations
│
└── mappings/                   # Company mapping files
    ├── company_branch.yml      # Company branch mappings
    ├── default_portfolio_code.yml  # Default portfolio codes
    └── company_id_overrides_plan.yml  # Company ID overrides
```

---

### 7. `src/work_data_hub/utils/` - Utilities

**Purpose:** Shared utility functions and helpers

```
utils/
├── types.py                    # Type aliases and protocols
├── column_normalizer.py        # Column name normalization
├── patoken_client.py           # PA Token client
└── __init__.py
```

---

### 8. `src/work_data_hub/scripts/` - Scripts

**Purpose:** CLI tools and migration scripts

```
scripts/
├── migrate_company_mappings.py     # Company mapping migration
├── eqc_integration_example.py      # EQC integration example
└── __init__.py
```

---

### 9. `io/schema/migrations/` - Database Migrations

**Purpose:** Alembic database migration scripts

```
io/schema/migrations/
├── env.py                      # Alembic environment configuration
├── script.py.mako              # Migration script template
│
└── versions/                   # Migration versions
    ├── 20251113_000001_create_core_tables.py
    └── 20251129_000001_create_annuity_performance_new.py
```

**Migration Strategy:**
- Idempotent migrations
- Down revision chain for rollback
- Inline comments (English + Chinese)
- Performance-critical indexes

---

### 10. `tests/` - Test Suites

**Purpose:** Comprehensive test coverage (unit, integration, e2e)

```
tests/
├── unit/                       # Unit tests (fast, no external deps)
│   ├── domain/                 # Domain logic tests
│   ├── pipelines/              # Pipeline framework tests
│   └── utils/                  # Utility tests
│
├── integration/                # Integration tests (DB, filesystem)
│   ├── io/                     # I/O layer tests
│   └── orchestration/          # Orchestration tests
│
├── e2e/                        # End-to-end tests
│   └── pipelines/              # Full pipeline tests
│
├── fixtures/                   # Test fixtures and sample data
│   ├── sample_data.csv         # Sample input data
│   └── performance/            # Performance test data
│
└── conftest.py                 # Pytest configuration and fixtures
```

**Test Markers:**
- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.postgres` - Requires PostgreSQL
- `@pytest.mark.e2e_suite` - End-to-end workflows
- `@pytest.mark.performance` - Performance tests

---

### 11. `docs/` - Documentation

**Purpose:** Comprehensive project documentation (90+ files)

```
docs/
├── PRD.md                      # ✓ Product Requirements Document
├── architecture.md             # ✓ System architecture
├── brownfield-architecture.md  # ✓ Brownfield analysis
├── architecture-boundaries.md  # ✓ Clean architecture boundaries
├── developer-guide.md          # ✓ Developer onboarding
├── database-migrations.md      # ✓ Migration procedures
├── epics.md                    # ✓ Epic planning
├── backlog.md                  # ✓ Product backlog
│
├── initial/                    # Initial research and validation
├── sprint-artifacts/           # Sprint stories, specs, retros
│   ├── stories/                # User stories (detailed)
│   ├── tech-spec-epic-*.md     # Technical specifications
│   └── epic-*-retro-*.md       # Sprint retrospectives
│
├── architecture-patterns/      # Architecture patterns and standards
├── domains/                    # Domain-specific documentation
├── runbooks/                   # Operational runbooks
├── supplement/                 # Supplementary analysis
├── specific/                   # Deep-dive analysis
├── crystallization/            # Crystallized knowledge
└── archive/                    # Archived documents
```

---

## Entry Points

### Application Entry Points

1. **Dagster Web Server**
   - Command: `dagster dev`
   - Entry: `orchestration/repository.py`
   - Port: 3000 (default)

2. **Pipeline Execution (CLI)**
   - Command: `dagster job execute -j <job_name>`
   - Entry: `orchestration/jobs.py`

3. **Scripts**
   - Entry: `scripts/<script_name>.py`
   - Execution: `uv run python scripts/<script>.py`

### Database Entry Point

- **Migrations:** `alembic upgrade head`
- **Configuration:** `alembic.ini`
- **Entry:** `io/schema/migrations/env.py`

---

## Integration Points

### Internal Integration

```
┌─────────────────┐
│  Orchestration  │ (Dagster jobs/ops)
└────────┬────────┘
         │
         ├──────────────────────────┐
         │                          │
         ▼                          ▼
┌─────────────────┐         ┌─────────────────┐
│  Domain Layer   │         │    I/O Layer    │
│  (Business)     │         │  (Data Access)  │
└─────────────────┘         └─────────────────┘
         │                          │
         │                          │
         └──────────┬───────────────┘
                    │
                    ▼
           ┌─────────────────┐
           │   PostgreSQL    │
           └─────────────────┘
```

### External Integration

- **EQC API** → `auth/eqc_auth_handler.py` → `io/connectors/eqc_client.py`
- **Excel Files** → `io/readers/excel_reader.py`
- **PostgreSQL** → `io/loader/warehouse_loader.py`

---

## Code Organization Principles

### 1. Clean Architecture (Story 1.6)
- **Domain** is independent of I/O and Orchestration
- **I/O** provides interfaces for domain
- **Orchestration** coordinates workflows

### 2. Standard Domain Pattern (Story 1.12)
Each domain follows consistent 6-file structure:
- `models.py` - Pydantic data models (In/Out)
- `schemas.py` - Pandera validation schemas
- `service.py` - Domain service orchestration
- `pipeline_builder.py` - Pipeline builder configuration
- `helpers.py` - Business logic helpers
- `constants.py` - Domain constants

### 3. Pipeline Framework (Epic 1)
- Reusable steps in `domain/pipelines/steps/`
- Pipeline builder pattern
- Dagster adapter for orchestration

### 4. Testing Strategy
- **Unit tests** - Domain logic (fast)
- **Integration tests** - I/O and DB (medium)
- **E2E tests** - Full workflows (slow)
- **Performance tests** - Baseline validation

---

## Development Workflow

### Local Development
```bash
# Setup environment
uv sync

# Run tests
uv run pytest -m unit  # Fast unit tests
uv run pytest -m integration  # Integration tests

# Run Dagster
dagster dev

# Run migrations
alembic upgrade head
```

### CI/CD Entry Points
- `.github/workflows/` - GitHub Actions pipelines
- Tests run on: `main` branch push, PR creation
- Stages: lint (ruff), type-check (mypy), test (pytest)

---

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool config |
| `alembic.ini` | Database migration configuration |
| `uv.lock` | Locked dependency versions |
| `.python-version` | Python version (3.12.10) |
| `.env.example` | Environment variable template |
| `CLAUDE.md` | Claude Code AI assistant instructions |

---

## Dependencies Management

**Tool:** `uv` (ultra-fast Python package manager)

```bash
uv add <package>        # Add dependency
uv sync                 # Sync environment
uv run <command>        # Run in environment
```

---

## Related Documentation

- [Architecture Documentation](./architecture.md) - System architecture
- [Data Models](./bmm-data-models.md) - Database and models
- [Developer Guide](./developer-guide.md) - Development workflows

---

**Document Status:** ✅ Complete
**Last Updated:** 2025-12-06
**Maintained By:** Development Team
