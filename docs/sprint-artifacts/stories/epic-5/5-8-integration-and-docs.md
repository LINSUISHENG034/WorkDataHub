# Story 5.8: Integration Testing and Documentation

Status: done

## Story

As a **team member**,
I want **comprehensive integration testing and updated documentation**,
so that **refactoring quality is assured and Epic 9 has a reference implementation**.

## Acceptance Criteria

### 1. End-to-End Test Suite
- [ ] AC1: Complete annuity pipeline execution test (discover → process → load)
- [ ] AC2: Output data 100% consistency vs legacy baseline (`legacy/annuity_hub/data_handler` reference snapshot)
- [ ] AC3: Performance benchmarks met:
  - 1000 rows processed in <3 seconds
  - Memory usage <200MB
  - Database queries <10

### 2. Architecture Cleanliness Verification
- [ ] AC4: No legacy/deprecated code patterns remain in infrastructure layer
- [ ] AC5: Clean Architecture boundaries enforced (domain cannot import io/orchestration)
- [ ] AC6: No duplicate implementations or parallel code paths

### 3. Code Quality Checks
- [ ] AC7: Mypy strict mode passes (`uv run mypy src/work_data_hub`)
- [ ] AC8: Ruff linting no warnings (`uv run ruff check`)
- [ ] AC9: Test coverage targets:
  - `infrastructure/` >85%
  - `domain/annuity_performance/` >90%

### 4. Execution Contracts & Baselines
- [ ] AC10: Pipeline entrypoint contract documented and honored (service signature, inputs/outputs, dependency injection for discovery/loader/enrichment)
- [ ] AC11: `PipelineContext` fields propagated through all TransformSteps (domain, pipeline_name, run_id, logger, extra)
- [ ] AC12: Legacy baseline output pinned from `legacy/annuity_hub/data_handler` run (e.g., `tests/fixtures/annuity_performance/legacy_reference_output.csv`), and used for parity
- [ ] AC13: No legacy adapters/shims remain; only new architecture paths exist in code and tests

### 5. Documentation Updates
- [ ] AC14: `README.md` - Updated architecture diagram
- [ ] AC15: `docs/architecture/architectural-decisions.md` - AD-010 added
- [ ] AC16: `docs/architecture/implementation-patterns.md` - Infrastructure layer patterns
- [ ] AC17: `docs/architecture/infrastructure-layer.md` - NEW (infrastructure layer documentation)
- [ ] AC18: `docs/domains/annuity_performance.md` - Updated (post-refactor architecture)
- [ ] AC19: `docs/migration-guide.md` - NEW (Epic 9 reference guide)

### 6. Performance Report
- [ ] AC20: Generate comparison report (pre vs post refactor) using the new pipeline metrics
- [ ] AC21: Expected results documented:
  - Processing time improved 50%+
  - Memory usage reduced 30%+
  - Code lines reduced 65%+ (3446 → <500)

### 7. Cleanup
- [ ] AC22: Delete temporary files (including any `*_legacy.py` files)
- [ ] AC23: Remove feature flag code (if any)
- [ ] AC24: Remove excessive debug logging

### 8. Domain Structure Alignment
- [ ] AC25: `src/work_data_hub/domain/annuity_performance/` aligns to new architecture: no legacy modules (e.g., `pipeline_steps.py`, `transforms/`, old `config.py`), only orchestrator/service, pipeline builder, models/schemas/constants, and new-arch-compatible tests/imports

## Tasks / Subtasks

- [x] Task 1: Create E2E Integration Test Suite (AC: 1, 2, 3)
  - [x] 1.1: Create `tests/e2e/test_annuity_pipeline_e2e.py` with full pipeline test
  - [x] 1.2: Create baseline comparison test against legacy snapshot from `legacy/annuity_hub/data_handler` (store at `tests/fixtures/annuity_performance/legacy_reference_output.csv`)
  - [x] 1.3: Add performance benchmark test with timing assertions
  - [x] 1.4: Add memory profiling test using `psutil`

- [x] Task 2: Verify Architecture Cleanliness (AC: 4, 5, 6)
  - [x] 2.1: Audit infrastructure layer for legacy patterns or deprecated code
  - [x] 2.2: Run `uv run ruff check` to verify TID251 rules (domain cannot import io/orchestration)
  - [x] 2.3: Search for duplicate implementations or parallel code paths
  - [x] 2.4: Remove any backward compatibility adapters or shims (new architecture only)

- [x] Task 3: Code Quality Verification (AC: 7, 8, 9)
  - [x] 3.1: Run `uv run mypy src/work_data_hub --strict` and fix any errors
  - [x] 3.2: Run `uv run ruff check` and fix any warnings
  - [x] 3.3: Run `uv run pytest --cov=src/work_data_hub/infrastructure --cov-report=term-missing`
  - [x] 3.4: Run `uv run pytest --cov=src/work_data_hub/domain/annuity_performance --cov-report=term-missing`
  - [x] 3.5: Add missing tests to reach coverage targets

- [x] Task 4: Execution Contracts & Baselines (AC: 10, 11, 12, 13)
  - [x] 4.1: Document service entrypoint contract (inputs/outputs, DI expectations for discovery/loader/enrichment)
  - [x] 4.2: Assert `PipelineContext` propagation in tests (domain, pipeline_name, run_id, logger, extra)
  - [x] 4.3: Pin legacy baseline snapshot produced by `legacy/annuity_hub/data_handler` to `tests/fixtures/annuity_performance/legacy_reference_output.csv`; use it for parity checks
  - [x] 4.4: Delete any legacy adapters/shims; ensure only new architecture paths are invoked in tests and code

- [x] Task 5: Documentation Updates (AC: 14, 15, 16, 17, 18, 19)
  - [x] 5.1: Update `README.md` with new architecture diagram showing infrastructure layer
  - [x] 5.2: Create/update `docs/architecture/architectural-decisions.md` with AD-010 (already exists)
  - [x] 5.3: Update `docs/architecture/implementation-patterns.md` with infrastructure patterns
  - [x] 5.4: Create `docs/architecture/infrastructure-layer.md` (NEW - infrastructure layer documentation)
  - [x] 5.5: Update `docs/domains/annuity_performance.md` (post-refactor architecture)
  - [x] 5.6: Create `docs/migration-guide.md` for Epic 9 domain migration reference

- [x] Task 6: Performance Report Generation (AC: 20, 21)
  - [x] 6.1: Create performance comparison script
  - [x] 6.2: Run benchmarks and collect metrics using the new pipeline
  - [x] 6.3: Generate `docs/sprint-artifacts/epic-5-performance-report.md`
  - [x] 6.4: Document code line count reduction

- [x] Task 7: Cleanup and Finalization (AC: 22, 23, 24)
  - [x] 7.1: Remove any temporary/debug files created during Epic 5 (none found)
  - [x] 7.2: Remove feature flags if any were added (none found)
  - [x] 7.3: Review and remove excessive debug logging (acceptable level)
  - [x] 7.4: Final code review pass

- [x] Task 8: Domain Structure Alignment (AC: 25)
  - [x] 8.1: Audit `src/work_data_hub/domain/annuity_performance/` for legacy files/directories (e.g., `pipeline_steps.py`, `transforms/`, old `config.py`)
  - [x] 8.2: Remove/rename legacy artifacts; ensure imports/tests point only to new-arch modules (no legacy artifacts found)
  - [x] 8.3: Re-run lint/tests relevant to domain module after cleanup (all checks passed)

## Dev Notes

### Architecture Context

**Epic 5 Goal:** Establish proper Clean Architecture boundaries by creating a reusable `infrastructure/` layer and refactoring the domain layer to lightweight business orchestrators.

**Current State (Post Stories 5.1-5.7):**
- Infrastructure layer created at `src/work_data_hub/infrastructure/`
- Domain code reduced from 3,446 lines to ~2,626 lines (target: <500)
- Infrastructure code: ~3,960 lines (reusable across domains)

**Infrastructure Layer Structure:**
```
src/work_data_hub/infrastructure/
├── __init__.py
├── cleansing/
│   ├── __init__.py
│   ├── registry.py
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── numeric_rules.py
│   │   └── string_rules.py
│   └── integrations/
│       ├── __init__.py
│       └── pydantic_adapter.py
├── enrichment/
│   ├── __init__.py
│   ├── company_id_resolver.py
│   ├── normalizer.py
│   └── types.py
├── settings/
│   ├── __init__.py
│   ├── data_source_schema.py
│   └── loader.py
├── transforms/
│   ├── __init__.py
│   ├── base.py                    # TransformStep ABC, Pipeline class
│   ├── standard_steps.py          # MappingStep, CalculationStep, FilterStep, etc.
│   └── cleansing_step.py
└── validation/
    ├── __init__.py
    ├── error_handler.py           # handle_validation_errors, collect_error_details
    ├── report_generator.py
    ├── schema_helpers.py
    └── types.py
```

### Clean Architecture Boundaries

**CRITICAL - Dependency Direction:** `domain ← io ← orchestration`

| Layer | Allowed Imports | Forbidden Imports |
|-------|-----------------|-------------------|
| `domain/` | stdlib, pandas, pydantic, infrastructure/ | io/, orchestration/ |
| `infrastructure/` | stdlib, pandas, pydantic, domain/pipelines/types | io/, orchestration/ |
| `io/` | domain/, infrastructure/ | orchestration/ |
| `orchestration/` | domain/, infrastructure/, io/ | - |

**Ruff Enforcement:** TID251 rules in `pyproject.toml` prevent domain from importing io/orchestration.

**No Backward Compatibility:** Old architecture paths are out of scope; delete adapters/shims and avoid dual maintenance.

### Testing Standards

**Test Markers (from pyproject.toml):**
```python
@pytest.mark.unit          # Fast unit tests, no external deps
@pytest.mark.integration   # DB or filesystem required
@pytest.mark.postgres      # PostgreSQL required
@pytest.mark.e2e_suite     # Full Dagster/warehouse flows
@pytest.mark.performance   # Slow/resource-intensive
```

**Test Commands:**
```bash
# Unit tests only (fast)
uv run pytest -m unit

# Integration tests
uv run pytest -m integration

# Full test suite with coverage
uv run pytest --cov=src/work_data_hub --cov-report=term-missing

# Specific module coverage
uv run pytest --cov=src/work_data_hub/infrastructure -v
```

### Key Files to Reference

**Domain Service (refactored in 5.7):**
- `src/work_data_hub/domain/annuity_performance/service.py` (~152 lines)
- Uses `build_bronze_to_silver_pipeline()` from `pipeline_builder.py`
- Imports `handle_validation_errors` from infrastructure
- Service contract (from 5.7): inputs `month: str`, `file_discovery: FileDiscoveryService`, `warehouse_loader: WarehouseLoader`, optional `enrichment_service`, optional `plan_override_mapping`, and `PipelineContext` with `domain`, `pipeline_name`, `run_id`, `logger`, `extra`

**Infrastructure Transform Steps:**
- `infrastructure/transforms/base.py` - `TransformStep` ABC, `Pipeline` class
- `infrastructure/transforms/standard_steps.py` - `MappingStep`, `CalculationStep`, `FilterStep`, `DropStep`, `RenameStep`

**Validation Utilities:**
- `infrastructure/validation/error_handler.py` - `handle_validation_errors()`, `collect_error_details()`
- `infrastructure/validation/types.py` - `ValidationErrorDetail`, `ValidationSummary`, `ValidationThresholdExceeded`

**Baseline Reference:**
- `tests/fixtures/annuity_performance/legacy_reference_output.csv` — produced by `legacy/annuity_hub/data_handler`; parity tests must match this legacy output (new infra must meet or beat performance while keeping data parity)

### Git Intelligence (Recent Commits)

```
8ecaf83 feat(domain): refactor AnnuityPerformanceService to lightweight orchestrator (Story 5.7)
1bf5440 Fix transforms tests and cleansing rule handling
af5fd1d feat(infra): implement validation utilities and migrate legacy code (Story 5.5)
745f6d1 feat(infra): complete story 5.4 company id resolver
651d6f6 feat: Complete Story 5.3 Config Namespace Reorganization
5c5de8a feat(infra): migrate cleansing module to infrastructure layer (Story 5.2)
cf386e8 Complete Story 5.1: Infrastructure Layer Foundation Setup
```

### Performance Baseline

**Pre-Refactor (Epic 4 end):**
- Domain code: 3,446 lines
- Processing time (1K rows): ~10s
- Memory usage (1K rows): ~300MB

**Target (Epic 5 end):**
- Domain code: <500 lines
- Processing time (1K rows): <3s
- Memory usage (1K rows): <200MB

### Documentation Templates

**AD-010 Template (for architectural-decisions.md):**
```markdown
## AD-010: Infrastructure Layer & Pipeline Composition

**Status:** Accepted
**Date:** 2025-12-01
**Context:** Domain layer contained 3,446 lines mixing business logic with infrastructure concerns.
**Decision:** Create `infrastructure/` layer for reusable cross-domain services.
**Consequences:**
- Domain reduced to <500 lines (business orchestration only)
- Infrastructure provides reusable transforms, validation, enrichment
- Epic 9 can replicate pattern to 6+ domains rapidly
```

**Migration Guide Structure:**
```markdown
# Domain Migration Guide (Epic 9 Reference)

## Overview
How to migrate a legacy domain to the new infrastructure-based architecture.

## Step-by-Step Process
1. Create domain directory structure
2. Define Pydantic models
3. Create Pandera schemas
4. Build pipeline using infrastructure steps
5. Create lightweight service orchestrator
6. Add tests

## Example: Annuity Performance Domain
[Reference implementation details]
```

### Project Structure Notes

- All new tests should go in `tests/e2e/` for E2E tests or `tests/integration/` for integration tests
- Performance tests should use `@pytest.mark.performance` marker
- Coverage reports should be generated to `htmlcov/` directory

### References

- [Source: docs/epics/epic-5-infrastructure-layer.md#story-58-integration-testing-and-documentation]
- [Source: docs/architecture-boundaries.md]
- [Source: docs/architecture/implementation-patterns.md]
- [Source: docs/bmm-index.md#epic-5-infrastructure-layer-architecture]
- [Source: pyproject.toml#tool.pytest.ini_options]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Story 5.8 is the final story in Epic 5 (Infrastructure Layer Architecture)
- Prerequisites: Stories 5.1-5.7 must be completed (5.6 and 5.7 are in review status)
- This story focuses on validation, documentation, and cleanup - no new feature code
- Critical for unblocking Epic 9 (Growth Domains Migration)

### File List

**Files to Create:**
- `tests/e2e/test_annuity_pipeline_e2e.py`
- `docs/architecture/infrastructure-layer.md` (NEW)
- `docs/migration-guide.md` (NEW)
- `docs/sprint-artifacts/epic-5-performance-report.md`

**Files to Update:**
- `README.md` - Architecture diagram
- `docs/architecture/architectural-decisions.md` - AD-010
- `docs/architecture/implementation-patterns.md` - Infrastructure patterns
- `docs/domains/annuity_performance.md` - Post-refactor architecture

**Files to Review/Cleanup:**
- All files in `src/work_data_hub/infrastructure/`
- All files in `src/work_data_hub/domain/annuity_performance/`
- Any `*_legacy.py` files that may exist
