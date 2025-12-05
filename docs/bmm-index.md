# WorkDataHub Documentation Index

**Project:** WorkDataHub Data Engineering Platform
**Type:** Data Engineering / ETL Platform (Monolith)
**Architecture:** Domain-Driven Design with Bronze-Silver-Gold Layered Architecture
**Generated:** 2025-12-06
**Last Rescan:** Epic 5.5 - Added annuity_income domain

---

## 🎯 Quick Reference

| Aspect | Details |
|--------|---------|
| **Primary Language** | Python 3.12.10 |
| **Core Framework** | Dagster (Data Orchestration) |
| **Data Processing** | Pandas + Pandera (DataFrame Validation) |
| **Database** | PostgreSQL with SQLAlchemy 2.0 + Alembic |
| **Architecture Pattern** | Domain-Driven Design (DDD) + Clean Architecture |
| **Data Architecture** | Bronze-Silver-Gold Medallion Architecture |
| **Entry Point** | `orchestration/repository.py` (Dagster) |
| **Test Command** | `uv run pytest -m unit` |

---

## 📚 Core Documentation (Start Here)

### Essential Reading

1. **[Product Requirements Document (PRD)](./prd/index.md)** - Product vision and requirements
2. **[System Architecture](./architecture/index.md)** - Complete system architecture
3. **[Brownfield Architecture Analysis](./brownfield-architecture.md)** - Legacy system analysis
4. **[Developer Guide](./developer-guide.md)** - Setup, workflows, and conventions
5. **[Architecture Boundaries](./architecture-boundaries.md)** - Clean architecture enforcement

### BMM Generated Documentation (This Scan)

- **[Data Models & Database Schema](./bmm-data-models.md)** ✨ **NEW** - Complete data architecture
- **[Source Tree Analysis](./bmm-source-tree-analysis.md)** ✨ **NEW** - Annotated codebase structure

---

## 🏗️ Architecture & Design

### System Architecture

- [System Architecture](./architecture/index.md) - Complete architecture overview
- [Architecture Boundaries](./architecture-boundaries.md) - Clean architecture rules
- [Brownfield Architecture](./brownfield-architecture.md) - Legacy analysis
- [Database Migrations Guide](./database-migrations.md) - Migration procedures

### Architecture Patterns

- [Pipeline Integration Guide](./architecture-patterns/pipeline-integration-guide.md)
- [Mandatory Conditions Addendum](./architecture-patterns/mandatory-conditions-addendum.md)
- [Tiered Retry Classification](./architecture-patterns/tiered-retry-classification.md)
- [Error Message Quality Standards](./architecture-patterns/error-message-quality-standards.md)
- [Epic 2 Performance Acceptance Criteria](./architecture-patterns/epic-2-performance-acceptance-criteria.md)

### Pipeline Patterns

- [Simple Pipeline Example](./architecture-patterns/pipelines/simple_pipeline_example.md)
- [Pipeline Steps README](../src/work_data_hub/domain/pipelines/steps/README.md)

### Utilities Documentation

- [Date Parser Usage Guide](./architecture-patterns/utils/date-parser-usage.md)

---

## 📊 Data Architecture

### Data Models & Schema

- **[BMM Data Models Documentation](./bmm-data-models.md)** ✨ **NEW** - Complete data architecture
  - Database schema (PostgreSQL)
  - Pydantic models (Bronze/Silver/Gold)
  - Data flow diagrams
  - Migration strategy
  - Validation layers

### Database Management

- [Database Migrations Guide](./database-migrations.md) - Alembic migration procedures
- **Migration Files:**
  - `io/schema/migrations/versions/20251113_000001_create_core_tables.py`
  - `io/schema/migrations/versions/20251129_000001_create_annuity_performance_new.py`

---

## 🏢 Domain Documentation

### Domain-Specific Guides

- [Annuity Performance Domain](./domains/annuity_performance.md) - Annuity domain documentation
- [Annuity Module Bloat Analysis](./specific/annuity-performance/annuity-module-bloat-analysis.md)
- [Annuity Refactoring Analysis Report 1](./specific/annuity-performance/annuity-performance-refactoring-analysis-report_1.md)
- [Annuity Refactoring Analysis Report 2](./specific/annuity-performance/annuity-performance-refactoring-analysis-report_2.md)

### Domain Design

- [Domain Refactoring Design](./specific/domain-design/domain-refactoring-design.md)
- [Domain Refactoring Validation Report](./specific/domain-design/domain-refactoring-validation-report.md)
- [Domain Integration Validation Report](./specific/domain-design/domain-integration-validation-report.md)
- [Domain Refactoring Enhanced Plan](./specific/domain-design/domain-refactoring-enhanced-plan.md)

---

## 🔧 Source Code Structure

### Code Organization

- **[BMM Source Tree Analysis](./bmm-source-tree-analysis.md)** ✨ **NEW** - Complete codebase structure
  - Annotated directory tree
  - Critical directory purposes
  - Entry points and integration points
  - Code organization principles

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/work_data_hub/domain/` | Business logic (DDD) |
| `src/work_data_hub/io/` | Data access layer |
| `src/work_data_hub/orchestration/` | Dagster workflows |
| `src/work_data_hub/cleansing/` | Data cleansing rules |
| `src/work_data_hub/auth/` | External auth |
| `src/work_data_hub/config/` | Configuration |
| `io/schema/migrations/` | Database migrations |
| `tests/` | Test suites |

---

## 🚀 Development & Operations

### Getting Started

- [Developer Guide](./developer-guide.md) - Complete developer onboarding
- [README](../README.md) - Project overview and quick start

### Operational Guides

- [Annuity Performance Runbook](./runbooks/annuity_performance.md)

### Testing

**Test Markers:**
- `@pytest.mark.unit` - Fast unit tests (no external deps)
- `@pytest.mark.integration` - Integration tests (DB, filesystem)
- `@pytest.mark.postgres` - Requires PostgreSQL
- `@pytest.mark.e2e_suite` - End-to-end workflows
- `@pytest.mark.performance` - Performance tests

**Commands:**
```bash
uv run pytest -m unit              # Fast unit tests
uv run pytest -m integration       # Integration tests
uv run pytest -m "not postgres"    # Skip PostgreSQL tests
uv run pytest -m e2e_suite         # E2E workflows
```

---

## 📋 Sprint Planning & Execution

### Epic Planning

- [Epic Overview](./epics/index.md) - All epics and progress
  - [Epic 1: Foundation & Core Infrastructure](./epics/epic-1-foundation-core-infrastructure.md) ✅
  - [Epic 2: Multi-Layer Data Quality Framework](./epics/epic-2-multi-layer-data-quality-framework.md) ✅
  - [Epic 3: Intelligent File Discovery & Version Detection](./epics/epic-3-intelligent-file-discovery-version-detection.md) ✅
  - [Epic 4: Annuity Performance Domain Migration (MVP)](./epics/epic-4-annuity-performance-domain-migration-mvp.md) ✅
  - [Epic 5: Infrastructure Layer Architecture](./epics/epic-5-infrastructure-layer.md) ✅
  - [Epic 5.5: Pipeline Architecture Validation](./epics/epic-5.5-pipeline-architecture-validation.md) 🔄 IN PROGRESS
  - [Epic 6: Company Enrichment Service](./epics/epic-6-company-enrichment-service.md)
- [Product Backlog](./backlog.md) - Prioritized backlog

### Sprint Artifacts

#### Epic 1: Foundation & Infrastructure
- [Tech Spec - Epic 1](./sprint-artifacts/tech-spec-epic-1.md)
- [Epic 1 Retrospective](./sprint-artifacts/epic-1-retro-2025-11-16.md)
- **Stories:** 1.1-1.12 (Setup, CI/CD, Logging, Config, Pipeline Framework, etc.)
  - [Story 1.3: Structured Logging](./sprint-artifacts/stories/1-3-structured-logging-framework.md)
  - [Story 1.6: Clean Architecture Boundaries](./sprint-artifacts/stories/1-6-clean-architecture-boundaries-enforcement.md)
  - [Story 1.12: Standard Domain Generic Steps](./sprint-artifacts/stories/1-12-implement-standard-domain-generic-steps.md)

#### Epic 2: Validation & Data Quality
- [Tech Spec - Epic 2](./sprint-artifacts/tech-spec-epic-2.md)
- [Epic 2 Retrospective](./sprint-artifacts/epic-2-retro-2025-11-27.md)
- **Stories:** 2.1-2.5 (Pydantic, Pandera, Cleansing Registry, Date Parsing, Error Handling)
  - [Story 2.1: Pydantic Models (Silver Layer)](./sprint-artifacts/stories/2-1-pydantic-models-for-row-level-validation-silver-layer.md)
  - [Story 2.2: Pandera Schemas (Bronze/Gold)](./sprint-artifacts/stories/2-2-pandera-schemas-for-dataframe-validation-bronze-gold-layers.md)
  - [Story 2.3: Cleansing Registry Framework](./sprint-artifacts/stories/2-3-cleansing-registry-framework.md)
  - [Story 2.4: Chinese Date Parsing](./sprint-artifacts/stories/2-4-chinese-date-parsing-utilities.md)
  - [Story 2.5: Validation Error Handling](./sprint-artifacts/stories/2-5-validation-error-handling-and-reporting.md)

#### Epic 3: File Discovery & Reading
- [Tech Spec - Epic 3](./sprint-artifacts/tech-spec-epic-3.md)
- [Epic 3 Retrospective](./sprint-artifacts/epic-3-retro-2025-11-28.md)
- **Stories:** 3.0-3.5 (Version-aware scanning, Pattern matching, Excel reader, etc.)
  - [Story 3.0: Data Source Config Schema](./sprint-artifacts/stories/3-0-data-source-configuration-schema-validation.md)
  - [Story 3.1: Version-Aware Folder Scanner](./sprint-artifacts/stories/3-1-version-aware-folder-scanner.md)
  - [Story 3.3: Multi-Sheet Excel Reader](./sprint-artifacts/stories/3-3-multi-sheet-excel-reader.md)
  - [Story 3.4: Column Name Normalization](./sprint-artifacts/stories/3-4-column-name-normalization.md)

#### Epic 4: Annuity Performance Domain
- [Tech Spec - Epic 4](./sprint-artifacts/tech-spec-epic-4.md)
- **Stories:** 4.1-4.10 (Annuity domain models, pipelines, refactoring)
  - [Story 4.1: Annuity Data Models (Pydantic)](./sprint-artifacts/stories/4-1-annuity-domain-data-models-pydantic.md)
  - [Story 4.2: Bronze Layer Validation](./sprint-artifacts/stories/4-2-annuity-bronze-layer-validation-schema.md)
  - [Story 4.7: Pipeline Framework Refactoring](./sprint-artifacts/stories/4-7-pipeline-framework-refactoring.md)
  - [Story 4.8: Annuity Module Deep Refactoring](./sprint-artifacts/stories/4-8-annuity-module-deep-refactoring.md)
  - [Story 4.9: Module Decomposition for Reusability](./sprint-artifacts/stories/4-9-annuity-module-decomposition-for-reusability.md)
  - [Story 4.10: Refactor to Standard Domain Pattern](./sprint-artifacts/stories/4-10-refactor-annuity-performance-to-standard-domain-pattern.md)

---

## 📖 Supplementary Documentation

### Technical Analysis

- [Company ID Analysis](./supplement/01_company_id_analysis.md) - Company enrichment deep dive
- [Version Detection Logic](./supplement/02_version_detection_logic.md)
- [Clean Company Name Logic](./supplement/03_clean_company_name_logic.md)
- [Technical Architecture & Implementation Guide (中文)](./supplement/04_技术架构与实施指南.md)

### Deep Analysis & Crystallization

- [Schemas Architecture Deep Dive](./crystallization/schemas-architecture-deep-dive.md)
- [Key Points Summary](./initial/key-points.md)

### Initial Research

- [Research Deep Prompt](./initial/research-deep-prompt-2025-11-08.md)
- [Architecture Validation Report](./initial/validation-report-architecture-2025-11-09.md)
- [Implementation Readiness Report](./initial/implementation-readiness-report-2025-11-09.md)

---

## 🗂️ Change Management

### Sprint Change Proposals

- [Sprint Change Proposal - 2025-11-08](./archive/sprint-change-proposal-2025-11-08.md)
- [Sprint Change Proposal - 2025-11-09](./archive/sprint-change-proposal-2025-11-09.md)
- [Sprint Change Proposal - 2025-11-29 (Story 4.8)](./archive/sprint-change-proposal-2025-11-29-story-4-8.md)
- [Sprint Change Proposal - 2025-11-30](./archive/sprint-change-proposal-2025-11-30.md)
- [Sprint Change Proposal - 2025-11-30 (Fix Bloat)](./archive/sprint-change-proposal-2025-11-30_fix_bloat.md)
- [Infrastructure Refactoring Proposal - 2025-12-01](./sprint-artifacts/sprint-change-proposal-infrastructure-refactoring-2025-12-01.md)

### Feasibility & Reviews

- [Feasibility Analysis - 2025-12-01](./archive/sprint-change-proposal-feasibility-analysis-2025-12-01.md)
- [Proposal Review - First Principles - 2025-12-01](./archive/proposal-review-2025-12-01-first-principles.md)
- [Proposal Modifications Summary - 2025-12-01](./archive/proposal-modifications-summary-2025-12-01.md)
- [Breaking Change Review Checklist](./archive/breaking-change-review-checklist.md)

---

## 🔍 Validation & Code Reviews

### Validation Reports

- [Story 1.3 Context Validation](./sprint-artifacts/stories/1-3-structured-logging-framework.context-validation-report-2025-11-10.md)
- [Story 1.3 Validation Report](./sprint-artifacts/stories/1-3-structured-logging-framework.validation-report-2025-11-10.md)
- [Story 1.12 Validation Report](./sprint-artifacts/stories/1-12-validation-report-2025-11-30.md)
- [Story 4.10 Validation Report](./sprint-artifacts/stories/4-10-validation-report-2025-11-30.md)
- [Validation Report - 3-5 (2025-11-28)](./archive/validation-report-3-5-20251128.md)

### Code Reviews

- [Code Review - 3-5 (2025-11-28)](./archive/code-review-3-5-20251128.md)

---

## 📦 Auxiliary Documentation

### Auxiliary Files

- [Architecture Session Checkpoint](./sprint-artifacts/auxiliary/architecture-session-checkpoint.md)
- [Epic 6 Testing & Validation](./sprint-artifacts/auxiliary/epic-6-testing-validation.md)
- [Action Item 2: Real Data Analysis](./sprint-artifacts/auxiliary/action-item-2-real-data-analysis.md)

---

## 📜 Legacy & Reference

### Legacy Code

- [Legacy README](../legacy/README.md) - Legacy codebase overview
- [Legacy Design Strategies](../legacy/docs/design/strategies/README.md)

---

## 🎓 Getting Started Workflows

### For New Developers

1. **Read:** [Developer Guide](./developer-guide.md)
2. **Setup:** Follow setup instructions in Developer Guide
3. **Architecture:** Read [System Architecture](./architecture/index.md)
4. **Code Structure:** Review [Source Tree Analysis](./bmm-source-tree-analysis.md)
5. **Data Models:** Understand [Data Models](./bmm-data-models.md)
6. **Run Tests:** `uv run pytest -m unit`
7. **Start Dagster:** `dagster dev`

### For AI-Assisted Development (PRDs)

When creating a **brownfield PRD** for new features:

1. **Reference this index:** `docs/bmm-index.md` (this file)
2. **For data-related features:** Point to [Data Models](./bmm-data-models.md)
3. **For UI-only features:** N/A (no UI in this project)
4. **For backend features:** Reference [Architecture](./architecture/index.md) + [Source Tree](./bmm-source-tree-analysis.md)
5. **For full-stack features:** Reference all architecture docs

### For Understanding Existing Domains

- **Annuity Performance:** Start with [Domain Doc](./domains/annuity_performance.md), then [Runbook](./runbooks/annuity_performance.md)
- **Sample Trustee Performance:** Reference source code (`domain/sample_trustee_performance/`)
- **Pipeline Framework:** Read [Pipeline Integration Guide](./architecture-patterns/pipeline-integration-guide.md)

---

## 🔗 External Resources

### Technology Stack Links

- [Dagster Documentation](https://docs.dagster.io/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Pandera Documentation](https://pandera.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

---

## 📊 Project Statistics

- **Total Documentation Files:** 90+ markdown files
- **Epics Completed:** 5 (Epic 1-5)
- **Stories Completed:** 30+ stories
- **Code Domains:** 6 (annuity_performance, annuity_income ✨NEW, sample_trustee_performance, company_enrichment, reference_backfill, pipelines)
- **Database Tables:** 3 (pipeline_executions, data_quality_metrics, annuity_performance_new)
- **Test Markers:** 7 (unit, integration, postgres, e2e_suite, performance, legacy_suite, sample_domain)

---

## 🎯 Current Project Status

**Latest Completed Work:**
- ✅ Epic 1-4: Foundation, Data Quality, File Discovery, Annuity Domain (COMPLETED)
- ✅ Epic 5: Infrastructure Layer Architecture (COMPLETED)
- ✅ Story 5.5.1-5.5.4: Legacy Cleansing Rules, Annuity Income Domain, Legacy Parity, Multi-Domain Integration

**Current Focus (Epic 5.5 - Pipeline Architecture Validation):**
- 🔄 Story 5.5.5: Annuity Income Schema Correction (review)
- ⏳ Epic 5.5 Retrospective (optional)

**New Domain Added:**
- ✨ `annuity_income` - Second domain validating Infrastructure Layer architecture

**Upcoming:**
- Epic 6: Company Enrichment Service
- Epic 7: Testing & Validation Infrastructure

---

**Index Status:** ✅ Complete
**Last Updated:** 2025-12-06
**Generated By:** BMM Document Project Workflow
**Scan Level:** Exhaustive Scan

---

## 💡 Tips for AI Assistants

When working with this codebase:

1. **Always reference this index first** for comprehensive context
2. **Respect Clean Architecture boundaries** - Domain layer cannot import from `io` or `orchestration`
3. **Follow Standard Domain Pattern** - Each domain should have models, service, config
4. **Use Bronze-Silver-Gold layering** - Validate at each layer
5. **Write tests** - Unit tests are mandatory, integration tests for I/O
6. **Document decisions** - Update relevant docs when making changes
7. **Check existing patterns** - Look at `annuity_performance` or `sample_trustee_performance` for examples

---

**End of Index**
