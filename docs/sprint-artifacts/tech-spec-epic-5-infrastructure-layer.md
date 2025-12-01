# Tech-Spec: Epic 5 - Infrastructure Layer Architecture & Domain Refactoring

**Created:** 2025-12-01
**Status:** Ready for Development
**Epic:** Epic 5 - Infrastructure Layer Establishment

## Overview

### Problem Statement

The current `annuity_performance` domain architecture violates Clean Architecture principles with significant code bloat (3,446 lines vs target <1,000 lines). The domain layer contains infrastructure concerns that should be extracted into reusable components, blocking Epic 9 (Growth Domains Migration) and creating maintenance issues.

**Key Issues:**
- Domain layer mixes business logic with infrastructure (enrichment, validation, transforms)
- Cannot efficiently replicate pattern to 6+ domains in Epic 9
- Multiple conflicting `config` namespaces causing confusion
- Zero cross-domain code reuse potential

### Solution

Establish a proper `infrastructure/` layer following Clean Architecture boundaries with:
1. **Domain Layer Lightweighting** - Extract infrastructure logic, reduce to <500 lines
2. **Infrastructure Layer Creation** - Reusable services for enrichment, validation, transforms
3. **Config Namespace Cleanup** - Clear separation of concerns for configuration
4. **Python Code Composition** - Pipeline pattern instead of JSON configuration

### Scope (In/Out)

**In Scope:**
- Create `infrastructure/` layer with 4 core services
- Refactor `annuity_performance` domain to lightweight orchestrator
- Migrate `cleansing/` module to infrastructure
- Reorganize configuration namespaces
- Maintain data output compatibility (no schema changes)

**Out of Scope:**
- Database schema changes
- API endpoint modifications
- Other domain refactoring (Epic 9)
- JSON configuration engines
- External service integrations

## Context for Development

### Codebase Patterns

**Current Architecture Issues:**
```python
# BEFORE: Domain contains infrastructure logic (WRONG)
domain/annuity_performance/service.py  # 852 lines - bloated with infrastructure
    ├── company_id_resolution()         # Should be in infrastructure
    ├── validation_execution()          # Should be in infrastructure
    └── transform_operations()          # Should be in infrastructure
```

**Target Architecture:**
```python
# AFTER: Clean separation of concerns
infrastructure/
    ├── enrichment/company_id_resolver.py     # Reusable service
    ├── validation/error_handler.py           # Utilities, not wrappers
    └── transforms/standard_steps.py          # Pipeline composition

domain/annuity_performance/service.py         # <150 lines - pure orchestration
    └── process() → uses infrastructure services via dependency injection
```

### Files to Reference

**Key Files to Study:**
1. `docs/sprint-artifacts/sprint-change-proposal-infrastructure-refactoring-2025-12-01.md` - Complete proposal
2. `src/work_data_hub/domain/annuity_performance/` - Current implementation (3,446 lines)
3. `src/work_data_hub/cleansing/` - Module to migrate
4. `src/work_data_hub/config/` - Configuration to reorganize
5. `docs/sprint-artifacts/architecture-decision-making.md` - Design principles

### Technical Decisions

Based on architecture decision document:

1. **Batch Processing Strategy**
   - Use Pandas vectorized operations (no Python loops)
   - Default `BATCH_SIZE = 1000` for non-vectorizable operations
   - Define as infrastructure constant for global tuning

2. **No Backward Compatibility Adapters**
   - Breaking changes allowed - synchronous caller updates
   - Focus on data compatibility, not API compatibility
   - Update `orchestration/jobs.py` in same PR

3. **Configurable Error Handling**
   - Error threshold configurable (default 10%)
   - Export paths configurable via environment settings
   - Define defaults in `constants.py`

4. **Constructor Dependency Injection**
   - No DI frameworks - manual injection
   - Clear dependency declaration in `__init__`
   - Facilitates unit testing with mocks

5. **Performance Test Suite Required**
   - Create `tests/performance/` directory
   - Use `reference/archive/monthly/202412/` as gold standard
   - Benchmark time and memory before/after

## Implementation Plan

### Tasks

#### Phase 1: Infrastructure Foundation
- [ ] Task 1: Create infrastructure directory structure
  - Create `src/work_data_hub/infrastructure/` with subdirectories
  - Create `src/work_data_hub/data/mappings/` for business data
  - Add `__init__.py` with module documentation
  - Verify CI/CD passes with new structure

#### Phase 2: Module Migrations
- [ ] Task 2: Migrate cleansing module
  - Move `cleansing/` → `infrastructure/cleansing/`
  - Rename `cleansing/config/` → `cleansing/settings/`
  - Update ~15 import statements across codebase
  - Run full test suite to verify

- [ ] Task 3: Reorganize configuration namespaces
  - Keep `config/data_sources.yml` as runtime config
  - Move `config/schema.py` → `infrastructure/settings/data_source_schema.py`
  - Move `config/mappings/*.yml` → `data/mappings/`
  - Rename domain configs to avoid conflicts

#### Phase 3: Infrastructure Components
- [ ] Task 4: Implement CompanyIdResolver
  ```python
  class CompanyIdResolver:
      def __init__(self, enrichment_service: Optional[CompanyEnrichmentService] = None):
          """Constructor injection of optional enrichment"""

      def resolve_batch(self, df: pd.DataFrame, strategy: Dict[str, Any]) -> pd.DataFrame:
          """Vectorized batch resolution with 5-priority algorithm"""
  ```

- [ ] Task 5: Implement validation utilities
  ```python
  # infrastructure/validation/error_handler.py
  def handle_validation_errors(errors, threshold: float = 0.1, total_rows: int = None):
      """Check thresholds and log errors - NOT a wrapper"""

  def collect_error_details(errors) -> List[Dict[str, Any]]:
      """Convert errors to structured format"""
  ```

- [ ] Task 6: Implement standard pipeline steps
  ```python
  # infrastructure/transforms/standard_steps.py
  class MappingStep(TransformStep):
      """Vectorized mapping transformation"""

  class CleansingStep(TransformStep):
      """Apply cleansing rules via registry"""
  ```

#### Phase 4: Domain Refactoring
- [ ] Task 7: Refactor AnnuityPerformanceService
  - Extract infrastructure logic (852 → <150 lines)
  - Implement pipeline composition pattern
  - Use constructor injection for dependencies
  - Create `constants.py` from `config.py`

- [ ] Task 8: Integration testing and documentation
  - End-to-end pipeline validation
  - Performance benchmarking
  - Update architecture documentation
  - Code review and cleanup

### Acceptance Criteria

#### Story 5.1: Infrastructure Foundation
- [ ] Given: No infrastructure directory exists
- [ ] When: Foundation created
- [ ] Then: Structure exists with proper module exports
- [ ] And: CI/CD pipeline passes

#### Story 5.2: Cleansing Migration
- [ ] Given: Cleansing at top-level
- [ ] When: Migration performed
- [ ] Then: Module in `infrastructure/cleansing/`
- [ ] And: All imports updated (~15 locations)
- [ ] And: Tests pass

#### Story 5.3: Config Reorganization
- [ ] Given: Multiple config namespaces
- [ ] When: Reorganization complete
- [ ] Then: Clear separation achieved
- [ ] And: No import conflicts
- [ ] And: Dagster jobs load correctly

#### Story 5.4: CompanyIdResolver
- [ ] Given: Logic embedded in service
- [ ] When: Extracted to infrastructure
- [ ] Then: Batch processing implemented
- [ ] And: 1000 rows processed <100ms
- [ ] And: Unit test coverage >90%

#### Story 5.5: Validation Utilities
- [ ] Given: Validation scattered in domain
- [ ] When: Utilities implemented
- [ ] Then: Reusable error handling available
- [ ] And: CSV export functional
- [ ] And: Threshold checking works

#### Story 5.6: Pipeline Steps
- [ ] Given: Transform logic in domain
- [ ] When: Standard steps created
- [ ] Then: Vectorized operations used
- [ ] And: Steps are composable
- [ ] And: Performance optimized

#### Story 5.7: Service Refactoring
- [ ] Given: 852-line service.py
- [ ] When: Refactored to orchestrator
- [ ] Then: <150 lines remaining
- [ ] And: Pipeline composition used
- [ ] And: Output data identical

#### Story 5.8: Integration & Docs
- [ ] Given: All refactoring complete
- [ ] When: Integration tested
- [ ] Then: E2E tests pass
- [ ] And: Performance improved 50%+
- [ ] And: Documentation updated

## Additional Context

### Dependencies

**External Dependencies:**
- `pandas` for vectorized operations
- `pydantic` for model validation
- `pandera` for schema validation
- Existing `CompanyEnrichmentService` interface

**Internal Dependencies:**
- Story 1.12 generic pipeline steps
- Epic 4 completed implementation
- Existing database schema (unchanged)

### Testing Strategy

**1. Unit Tests** (target >85% coverage)
```python
# tests/infrastructure/enrichment/test_company_id_resolver.py
def test_batch_resolution_performance():
    """1000 rows should process in <100ms"""

def test_hierarchical_resolution():
    """Test all 5 priority levels"""
```

**2. Integration Tests**
```python
# tests/integration/test_annuity_pipeline.py
def test_output_compatibility():
    """Output must match legacy exactly"""
```

**3. Performance Benchmarks**
```python
# tests/performance/benchmark_refactoring.py
def benchmark_before_after():
    """Compare metrics pre/post refactor"""
```

### Notes

**Critical Success Factors:**
1. **Data Compatibility** - Output must be bit-identical to current implementation
2. **No Adapters** - Direct breaking changes with caller updates
3. **Vectorization** - Eliminate Python loops for 5-10x performance
4. **Clear Boundaries** - Infrastructure provides utilities, not black boxes
5. **Python Composition** - Code is the DSL, no custom config languages

**Risk Mitigations:**
- Keep `_legacy.py` files temporarily for rollback
- Feature flags for gradual rollout
- Comprehensive regression testing
- Performance monitoring in production

**Migration Script Example:**
```python
# scripts/update_imports.py
IMPORT_MIGRATIONS = {
    "from work_data_hub.cleansing":
        "from work_data_hub.infrastructure.cleansing",
    "from work_data_hub.config.schema":
        "from work_data_hub.infrastructure.settings.data_source_schema",
}
```

## Next Steps

1. **Architecture Review** - Get approval on this tech spec
2. **Create Epic 5 File** - `docs/epics/epic-5-infrastructure-layer.md`
3. **Update Sprint Status** - Add Epic 5 with 8 stories to tracking
4. **Begin Story 5.1** - Start with infrastructure foundation

**Estimated Timeline:** 11 days (10 working + 1 buffer)
**Priority:** Critical (blocks Epic 9)
**Team:** Development team with architect review