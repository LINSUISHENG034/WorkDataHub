# Technology Stack

### Core Technologies (Locked In - Brownfield)

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| **Language** | Python | 3.10+ | Corporate standard, type system maturity |
| **Package Manager** | uv | Latest | 10-100x faster than pip, deterministic locks |
| **Orchestration** | Dagster | Latest | Active — JOB_REGISTRY pattern, CLI + Dagster UI execution |
| **Data Validation** | Pydantic | 2.11.7+ | Row-level validation, type safety, performance |
| **DataFrame Library** | pandas | Latest (locked) | Team expertise, ecosystem maturity |
| **Database** | PostgreSQL | Corporate std | Transactional guarantees, JSON support |
| **Spreadsheet I/O** | openpyxl | Latest (locked) | Multi-sheet Excel reading |
| **Type Checking** | mypy | 1.17.1+ (strict) | 100% type coverage NFR |
| **Linting/Formatting** | Ruff | 0.12.12+ | Replaces black + flake8 + isort, 10-100x faster |
| **Testing** | pytest | Latest | Custom markers for postgres/legacy/monthly |
| **Structured Logging** | structlog | Latest | **Decision #8:** True structured logging |
| **Schema Validation** | pandera | >=0.18, <1.0 | DataFrame-level schemas (Bronze/Gold) |
| **ORM / DB Access** | SQLAlchemy | >=2.0 | Database abstraction, connection management |
| **Schema Migrations** | Alembic | Latest | All DDL changes via migration scripts |
| **CLI Output** | Rich | >=13.0 | Formatted console output |
| **Browser Automation** | Playwright | >=1.55 | EQC authentication flow |
| **Arrow Format** | pyarrow | >=21.0 | High-performance data interchange |
| **SM Crypto** | gmssl | >=3.2.1 | Chinese national standard encryption |
| **SQL Parsing** | sqlglot | >=28.1 | SQL dialect translation |
| **GUI (Optional)** | PyQt6 | >=6.6 | Desktop GUI with pyqt6-fluent-widgets |

### Architecture Patterns (Locked In - Brownfield)

| Pattern | Description | Epic Application |
|---------|-------------|------------------|
| **Medallion (Bronze→Silver→Gold)** | Layered data quality progression | Epic 2 (Validation), Epic 4 (Annuity) |
| **Strangler Fig** | Gradual legacy replacement with parity | Epic 4, 9 (Domain migrations) |
| **Configuration-Driven Discovery** | YAML-based file discovery | Epic 3 (File Discovery) |
| **Provider Protocol** | Abstraction for enrichment sources | Epic 6 (Enrichment — fully implemented, 5-layer architecture) |
| **Registry Pattern** | Configuration-driven domain management | Epic 7.4 (Domain Registry, JOB_REGISTRY + DOMAIN_SERVICE_REGISTRY) |
| **Post-ETL Hook Pattern** | Registry-based post-pipeline triggers | Epic 7.6 (Customer MDM — contract sync, snapshot refresh) |
| **Pipeline Composition** | Python code composition for transforms | Epic 5 (Infrastructure Layer — reusable TransformStep classes) |

---
