# Technology Stack

### Core Technologies (Locked In - Brownfield)

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| **Language** | Python | 3.10+ | Corporate standard, type system maturity |
| **Package Manager** | uv | Latest | 10-100x faster than pip, deterministic locks |
| **Orchestration** | Dagster | Latest | Definitions ready, CLI-first execution for MVP |
| **Data Validation** | Pydantic | 2.11.7+ | Row-level validation, type safety, performance |
| **DataFrame Library** | pandas | Latest (locked) | Team expertise, ecosystem maturity |
| **Database** | PostgreSQL | Corporate std | Transactional guarantees, JSON support |
| **Spreadsheet I/O** | openpyxl | Latest (locked) | Multi-sheet Excel reading |
| **Type Checking** | mypy | 1.17.1+ (strict) | 100% type coverage NFR |
| **Linting/Formatting** | Ruff | 0.12.12+ | Replaces black + flake8 + isort, 10-100x faster |
| **Testing** | pytest | Latest | Custom markers for postgres/legacy/monthly |
| **Structured Logging** | structlog | Latest | **Decision #8:** True structured logging |
| **Schema Validation** | pandera | Latest | DataFrame-level schemas (Bronze/Gold) |

### Architecture Patterns (Locked In - Brownfield)

| Pattern | Description | Epic Application |
|---------|-------------|------------------|
| **Medallion (Bronze→Silver→Gold)** | Layered data quality progression | Epic 2 (Validation), Epic 4 (Annuity) |
| **Strangler Fig** | Gradual legacy replacement with parity | Epic 4, 9 (Domain migrations) |
| **Configuration-Driven Discovery** | YAML-based file discovery | Epic 3 (File Discovery) |
| **Provider Protocol** | Abstraction for enrichment sources | Epic 5 (Enrichment - deferred to Growth) |

---
