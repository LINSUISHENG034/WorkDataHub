# Domain Migration Workflow

**Version:** 2.1
**Last Updated:** 2026-03-04
**Purpose:** Single entry point for complete domain migration from legacy to new architecture

> [!TIP]
> **新架构**: 从 v2.0 开始，domain 实现需要包含 `adapter.py` 文件实现 `DomainServiceProtocol`，并在 `domain/registry.py` 中注册。参考 [development-guide.md](./development-guide.md) 获取详细模板。

---

## Overview

This document provides a complete end-to-end workflow for migrating a legacy domain to the WorkDataHub architecture. Follow the phases in order, using the linked guides for detailed instructions.

### Quick Navigation

| Phase | Goal | Input | Output | Duration | Guide |
|-------|------|-------|--------|----------|-------|
| **Phase 1** | Dependency Preparation | Legacy code analysis | Dependencies migrated | 1-2 days | [Section 1](#phase-1-dependency-preparation) |
| **Phase 2** | Documentation | Legacy code | `cleansing-rules/{domain}.md` | 1-2 days | [Section 2](#phase-2-documentation) |
| **Phase 3** | Implementation | Cleansing rules doc | 8-file domain structure | 2-3 days | [Section 3](#phase-3-implementation) |
| **Phase 4** | Validation | Legacy + New outputs | 100% parity match | 1-2 days | [Section 4](#phase-4-validation) |

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOMAIN MIGRATION WORKFLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  PHASE 1    │    │  PHASE 2    │    │  PHASE 3    │    │  PHASE 4    │  │
│  │  Dependency │───►│  Document   │───►│  Implement  │───►│  Validate   │  │
│  │  Preparation│    │  Analysis   │    │  Code       │    │  Parity     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│         ▼                  ▼                  ▼                  ▼         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ Dependencies│    │ cleansing-  │    │ 8-file      │    │ 100% match  │  │
│  │ migrated to │    │ rules/      │    │ domain      │    │ parity      │  │
│  │ enrichment  │    │ {domain}.md │    │ structure   │    │ report      │  │
│  │ index       │    │             │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Dependency Preparation

**Goal:** Identify and migrate all dependency tables before domain implementation

**Why First:** Dependencies are prerequisites - domain code cannot function correctly without migrated lookup tables.

### Checklist

- [ ] **1.1** Analyze legacy cleaner code for database dependencies
  - SQL queries (`SELECT ... FROM table_name`)
  - Mapping table references (`COMPANY_ID_MAPPING`, etc.)
  - External API calls

- [ ] **1.2** Document dependencies in cleansing rules document
  - Create `docs/cleansing-rules/{domain}.md` using [template](../templates/cleansing-rules-template.md)
  - Complete **Section 2: Dependency Table Inventory**
  - Complete **Section 3: Migration Strategy Decisions**

- [ ] **1.3** Execute dependency migrations
  - For Enrichment Index: `PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py`
  - For Static Embedding: Update `constants.py`
  - For Direct Migration: Use appropriate scripts

- [ ] **1.4** Validate migrations
  - Complete **Section 4: Migration Validation Checklist** in cleansing rules doc
  - Verify row counts match
  - Test lookup performance

### Key Documents

| Document | Purpose |
|----------|---------|
| [Cleansing Rules Template](../../templates/cleansing-rules-template.md) | Section 2-4 for dependency documentation |
| [Migration Script](../../scripts/migrations/migrate_legacy_to_enrichment_index.py) | Enrichment index migration |
| [Plan Code Migration Guide](./initial-preparation/plan-code-migration.md) | Specific guide for plan code mappings |

### Exit Criteria

- [ ] All critical dependencies identified and documented
- [ ] Migration strategy decided for each dependency
- [ ] Migrations executed and validated
- [ ] Section 2-4 of cleansing rules document completed

---

## Phase 2: Documentation

**Goal:** Create comprehensive cleansing rules documentation from legacy code analysis

**Why Important:** Documentation serves as the specification for implementation - accurate documentation leads to accurate code.

### Checklist

- [ ] **2.1** Analyze legacy cleaner class
  - Locate source file in `legacy/annuity_hub/data_handler/data_cleaner.py`
  - Identify the cleaner class and line numbers
  - Trace all transformation logic

- [ ] **2.2** Document column mappings
  - Complete **Section 5: Column Mappings**
  - Map every legacy column to target column
  - Document all transformations

- [ ] **2.3** Document cleansing rules
  - Complete **Section 6: Cleansing Rules**
  - Assign Rule IDs (CR-001, CR-002, etc.)
  - Document rule type, logic, and priority

- [ ] **2.4** Document Company ID resolution
  - Complete **Section 7: Company ID Resolution Strategy**
  - Document priority order and mapping tables
  - Note any domain-specific fallbacks

- [ ] **2.5** Document validation rules
  - Complete **Section 8: Validation Rules**
  - List required fields
  - Define data type constraints and business rules

- [ ] **2.6** Document special cases
  - Complete **Section 9: Special Processing Notes**
  - Edge cases, legacy quirks, known issues

- [ ] **2.7** Prepare parity checklist
  - Complete **Section 10: Parity Validation Checklist**

### Key Documents

| Document | Purpose |
|----------|---------|
| [Cleansing Rules Template](../../templates/cleansing-rules-template.md) | Section 5-10 for cleansing documentation |
| [annuity-income.md](../../cleansing-rules/annuity-income.md) | Reference example |

### Exit Criteria

- [ ] All 10 sections of cleansing rules document completed
- [ ] Document reviewed by team lead
- [ ] Document committed to repository

---

## Phase 3: Implementation

**Goal:** Implement domain code using cleansing rules document as specification

**Key Principle:** The cleansing rules document is your specification - every code decision should trace back to a documented rule.

### Checklist

- [ ] **3.1** Create domain directory structure
  ```
  src/work_data_hub/domain/{domain_name}/
  ├── __init__.py
  ├── adapter.py            # Protocol adapter
  ├── constants.py          # Domain-specific constants
  ├── models.py
  ├── schemas.py
  ├── helpers.py
  ├── service.py
  └── pipeline_builder.py
  ```

- [ ] **3.2** Implement constants.py
  - **Source:** Section 5 (Column Mappings) → `COLUMN_MAPPING`
  - **Source:** Section 6 (Cleansing Rules) → Static mappings
  - **Source:** Section 9 (Special Notes) → Manual overrides

- [ ] **3.3** Implement models.py
  - **Source:** Section 8 (Validation Rules) → Field definitions
  - Create `{Domain}In` (Bronze) and `{Domain}Out` (Gold) models

- [ ] **3.4** Implement schemas.py
  - **Source:** Section 8 (Validation Rules) → Pandera schemas
  - Create `Bronze{Domain}Schema` and `Gold{Domain}Schema`

- [ ] **3.5** Implement pipeline_builder.py
  - **Source:** Section 6 (Cleansing Rules) → Pipeline steps
  - **Source:** Section 7 (Company ID) → Resolution configuration

- [ ] **3.6** Implement service.py
  - Configure loading mode (UPSERT vs REFRESH)
  - Set upsert/refresh keys

- [ ] **3.7** Implement helpers.py
  - `convert_dataframe_to_models()`
  - Domain-specific helper functions

- [ ] **3.8** **Implement adapter.py** (Protocol)
  - Create `{Domain}Service` class implementing `DomainServiceProtocol`
  - Delegate `process()` to existing service function
  - Set `requires_enrichment` and `requires_backfill` properties

- [ ] **3.9** **Register in domain/registry.py**
  - Import adapter in `_register_all_domains()`
  - Call `register_domain("{domain_name}", {Domain}Service())`

- [ ] **3.10** Write tests
  - Unit tests for models and schemas
  - Integration tests for pipeline

### Key Documents

| Document | Purpose |
|----------|---------|
| [Domain Development Guide](./development-guide.md) | Detailed implementation patterns |
| [Cleansing Rules to Code Mapping](./code-mapping.md) | Document → Code translation |
| Your `cleansing-rules/{domain}.md` | Implementation specification |

### Exit Criteria

- [ ] All 8 files implemented
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Code reviewed

---

## Phase 4: Validation

**Goal:** Verify new implementation produces identical results to legacy system

**Success Criteria:** 100% parity match (excluding documented intentional differences)

### Checklist

- [ ] **4.1** Prepare validation environment
  - Real test data available
  - Legacy mappings configured
  - Output directory created

- [ ] **4.2** Run legacy cleaner
  - Execute legacy extraction script
  - Save output to `tests/fixtures/validation_results/`

- [ ] **4.3** Run new pipeline
  - Execute new domain pipeline
  - Save output to `tests/fixtures/validation_results/`

- [ ] **4.4** Compare outputs
  - Run parity validation script
  - Review comparison report

- [ ] **4.5** Analyze differences
  - If 100% match: Proceed to completion
  - If differences found:
    - Bug in implementation → Fix and re-validate
    - Intentional improvement → Document in cleansing rules doc

- [ ] **4.6** Complete parity checklist
  - Update **Section 10: Parity Validation Checklist** in cleansing rules doc
  - Document any intentional differences

### Key Documents

| Document | Purpose |
|----------|---------|
| [Legacy Parity Validation Guide](../../runbooks/legacy-parity-validation.md) | Validation procedures |
| Parity CLI: `scripts/validation/CLI/cleaner_compare.py` | Automated comparison |

### Exit Criteria

- [ ] 100% parity match achieved (or differences documented)
- [ ] Validation results saved
- [ ] Cleansing rules document updated with validation results

---

## Completion Checklist

### Documentation Complete

- [ ] `docs/cleansing-rules/{domain}.md` - All 10+ sections completed
- [ ] `docs/cleansing-rules/index.md` - Domain added to index

### Code Complete

- [ ] `src/work_data_hub/domain/{domain_name}/` - 8-file structure (incl. adapter.py)
- [ ] `domain/registry.py` - Domain registered
- [ ] `tests/unit/domain/{domain_name}/` - Unit tests
- [ ] `tests/integration/domain/{domain_name}/` - Integration tests

### Validation Complete

- [ ] Parity validation passed
- [ ] Results archived in `tests/fixtures/validation_results/`

### Review Complete

- [ ] Code review approved
- [ ] Documentation review approved
- [ ] Ready for merge

---

## Reference Examples

### Completed Migrations

| Domain | Cleansing Rules | Code | Status |
|--------|-----------------|------|--------|
| `annuity_performance` | (implicit) | `domain/annuity_performance/` | Migrated |
| `annuity_income` | [annuity-income.md](../../cleansing-rules/annuity-income.md) | `domain/annuity_income/` | Migrated |
| `annual_award` | — | `domain/annual_award/` | Migrated |
| `annual_loss` | — | `domain/annual_loss/` | Migrated |
| `sandbox_trustee_performance` | — | `domain/sandbox_trustee_performance/` | Migrated |

### Pending Migrations

See [Cleansing Rules Index](../../cleansing-rules/index.md) for full list of pending domains.

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [Domain Development Guide](./development-guide.md) | Detailed implementation patterns and code templates |
| [Cleansing Rules to Code Mapping](./code-mapping.md) | How to translate documentation to code |
| [Troubleshooting Guide](./troubleshooting.md) | Common issues and solutions |
| [Cleansing Rules Template](../../templates/cleansing-rules-template.md) | Template for creating cleansing rules documents |
| [Legacy Parity Validation Guide](../../runbooks/legacy-parity-validation.md) | Validation procedures and troubleshooting |

---

## FAQ

### Q: Can I skip Phase 1 if there are no dependencies?

A: You should still complete Phase 1 to verify there are no dependencies. Document "No dependencies identified" in Section 2 of the cleansing rules document.

### Q: What if I find new requirements during implementation?

A: Update the cleansing rules document first, then update the code. The document is the source of truth.

### Q: How do I handle intentional differences from legacy?

A: Document the difference in Section 9 (Special Processing Notes) with clear rationale. Exclude from parity comparison if appropriate.

### Q: Where can I find help with common errors?

A: See the [Troubleshooting Guide](./troubleshooting.md) for common issues and solutions organized by phase.

### Q: Can I work on multiple phases in parallel?

A: Phase 1 must complete before Phase 3. Phase 2 can overlap with Phase 1. Phase 4 requires Phase 3 completion.

---

## Complete Migration Checklist

Use this checklist to ensure all steps are completed before marking a domain migration as done.

### 🔍 Phase 1: Dependency Preparation
- [ ] All legacy code analyzed for database dependencies
- [ ] Dependencies documented in cleansing-rules/{domain}.md Section 2
- [ ] Migration strategy decided for each dependency (Section 3)
- [ ] All migrations executed (Enrichment Index, Static, Direct)
- [ ] Migration validation completed (Section 4)
- [ ] Migration status updated to [MIGRATED]

### 📝 Phase 2: Documentation
- [ ] All 10 sections of cleansing-rules/{domain}.md completed
  - [ ] Section 1: Domain Overview
  - [ ] Section 2-4: Dependencies (from Phase 1)
  - [ ] Section 5: Column Mappings
  - [ ] Section 6: Cleansing Rules (CR-001...)
  - [ ] Section 7: Company ID Resolution Strategy
  - [ ] Section 8: Validation Rules
  - [ ] Section 9: Special Processing Notes
  - [ ] Section 10: Parity Validation Checklist
- [ ] Document reviewed by technical lead
- [ ] Document committed to repository
- [ ] Domain added to cleansing-rules/index.md

### 💻 Phase 3: Implementation
- [ ] Domain directory created with all 8 files
  - [ ] `__init__.py` - Module exports
  - [ ] `adapter.py` - Protocol adapter
  - [ ] `constants.py` - Mappings and configurations
  - [ ] `models.py` - Pydantic models
  - [ ] `schemas.py` - Pandera schemas
  - [ ] `helpers.py` - Transformation functions
  - [ ] `service.py` - Business logic
  - [ ] `pipeline_builder.py` - Pipeline steps
- [ ] Code follows patterns from development-guide.md
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Code review completed and approved

### ✅ Phase 4: Validation
- [ ] Test data prepared from real source
- [ ] Legacy output captured
- [ ] New pipeline output captured
- [ ] Parity validation script executed
- [ ] 100% parity achieved (or differences documented)
- [ ] Validation results saved to `tests/fixtures/validation_results/`
- [ ] Section 10 of cleansing rules updated with results

### 📦 Final Deliverables
- [ ] Documentation complete
  - [ ] `docs/cleansing-rules/{domain}.md`
  - [ ] `docs/domains/{domain}.md` (optional)
  - [ ] `docs/runbooks/{domain}.md` (optional)
- [ ] Code complete
  - [ ] All 8 domain files
  - [ ] Unit tests
  - [ ] Integration tests
- [ ] Validation complete
  - [ ] Parity report
  - [ ] Performance baseline
- [ ] Ready for deployment
  - [ ] PR created and approved
  - [ ] Database migrations ready
  - [ ] Rollback plan documented

### 🎯 Success Criteria
- [ ] All dependencies migrated before domain implementation
- [ ] Documentation drives implementation (not vice versa)
- [ ] 100% parity with legacy (except intentional differences)
- [ ] All tests passing
- [ ] Code follows established patterns
- [ ] Team confident in deployment

---

## Quick Reference

### Common Commands
```bash
# Dependency migration
PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py

# Run tests
uv run pytest -m unit tests/unit/domain/{domain}/
uv run pytest -m integration tests/integration/domain/{domain}/

# Parity validation
PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py {domain} --month 202401 --export
```

### File Templates
- Cleansing Rules: `docs/templates/cleansing-rules-template.md`
- Domain Code: `docs/guides/domain-migration/development-guide.md`

### Key Contacts
- Technical Lead: Review documentation and code
- Database Team: Migration scripts and schema changes
- QA Team: Validation and parity testing

---

**End of Workflow Guide**
