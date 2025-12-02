# Epic 5: Infrastructure Layer Architecture & Domain Refactoring

**Goal:** Establish proper Clean Architecture boundaries by creating a reusable `infrastructure/` layer and refactoring the domain layer to lightweight business orchestrators. This epic corrects architectural violations from Epic 4 implementation and establishes the foundation for Epic 9 (Growth Domains Migration).

**Business Value:** Reduces domain code from 3,446 to <500 lines (-85%), enabling rapid replication to 6+ domains in Epic 9. Eliminates technical debt, improves performance 5-10x through batch processing, and establishes clear architectural boundaries for sustainable long-term maintenance.

**Dependencies:** Epic 4 (Annuity Performance Domain Migration) must be completed, as this refactoring extracts infrastructure from the existing implementation.

**Architecture Decision:** AD-010 - Infrastructure Layer & Pipeline Composition

---

### Story 5.1: Infrastructure Layer Foundation Setup

As an **architect**,
I want to **establish the infrastructure layer directory structure**,
So that **subsequent stories can migrate functionality to proper architecture layers**.

**Acceptance Criteria:**

**Given** current codebase lacks infrastructure directory
**When** infrastructure foundation is created
**Then** the following structure exists:
```
src/work_data_hub/infrastructure/
├── __init__.py                      # Module docs + exports
├── settings/__init__.py
├── cleansing/__init__.py            # Placeholder for Story 5.2
├── enrichment/__init__.py
├── validation/__init__.py
└── transforms/__init__.py
```

**And** create `data/mappings/` directory for business data

**And** all `__init__.py` files contain:
- Module docstring explaining purpose
- `__all__` export declarations (initially empty)

**And** CI/CD pipeline passes (no import errors)

**And** git tracking confirmed for all new directories

**Prerequisites:** None
**Estimated Effort:** 0.5 day

---

### Story 5.2: Migrate Cleansing Module to Infrastructure

As a **data engineer**,
I want to **move the cleansing module into the infrastructure layer**,
So that **cleansing services are correctly categorized as cross-domain infrastructure**.

**Acceptance Criteria:**

**Given** `cleansing/` exists at top-level
**When** migration is performed
**Then**:
- Module relocated to `infrastructure/cleansing/`
- `cleansing/config/` renamed to `cleansing/settings/`
- All internal imports updated
- External references (~15 locations) updated:
  ```python
  # OLD
  from work_data_hub.cleansing import registry
  # NEW
  from work_data_hub.infrastructure.cleansing import registry
  ```

**And** all cleansing unit tests pass

**And** integration tests pass (annuity_performance using cleansing)

**And** cleansing rules configuration loads correctly:
```python
registry.get_domain_rules("annuity_performance", "客户名称")
# Returns: ["trim_whitespace", "normalize_company_name"]
```

**And** Pydantic adapter (`decimal_fields_cleaner`) works correctly

**Prerequisites:** Story 5.1
**Estimated Effort:** 0.5 day

---

### Story 5.3: Config Namespace Reorganization

As a **developer**,
I want to **eliminate config namespace conflicts and organize configuration by responsibility**,
So that **architecture layers are clear and configs are easy to locate**.

**Acceptance Criteria:**

**Given** multiple conflicting `config` namespaces exist
**When** reorganization is complete
**Then** migrations completed:

| Original Path | New Path | Type |
|---------------|----------|------|
| `config/data_sources.yml` | **Keep as is** | Runtime config |
| `config/schema.py` | `infrastructure/settings/data_source_schema.py` | Infrastructure code |
| `config/mapping_loader.py` | `infrastructure/settings/loader.py` | Infrastructure code |
| `config/mappings/*.yml` | `data/mappings/*.yml` | Business data |
| `domain/annuity_performance/config.py` | `domain/annuity_performance/constants.py` | Business constants |
| `domain/pipelines/config.py` | `domain/pipelines/pipeline_config.py` | Framework config |

**And** `config/` directory contains only:
- `settings.py` (environment variables)
- `__init__.py`
- `.env.example`

**And** all import paths updated (~25 locations)

**And** Dagster jobs successfully load data source configuration

**And** all tests pass (including config loading tests)

**Prerequisites:** Stories 5.1, 5.2
**Estimated Effort:** 1.0 day

---

### Story 5.4: Implement CompanyIdResolver in Infrastructure

As a **data engineer**,
I want to **extract company ID resolution logic into a reusable infrastructure service**,
So that **batch optimization is achieved and multiple domains can reuse this service**.

**Acceptance Criteria:**

**Given** company ID resolution logic embedded in annuity service
**When** CompanyIdResolver is implemented
**Then**:
- Create `infrastructure/enrichment/company_id_resolver.py`
- Implement `CompanyIdResolver` class:
  ```python
  class CompanyIdResolver:
      def __init__(
          self,
          enrichment_service: Optional[CompanyEnrichmentService] = None
      ):
          """Initialize with optional enrichment service"""

      def resolve_batch(
          self,
          df: pd.DataFrame,
          strategy: Dict[str, Any]
      ) -> pd.DataFrame:
          """Batch resolve company_id with hierarchical strategy"""
  ```
- Support hierarchical resolution:
  1. Plan override lookup (from mapping table)
  2. Internal mapping lookup
  3. Enrichment service call (optional)
  4. Default fallback
- Batch processing optimization (vectorized operations)

**And** unit test coverage >90%

**And** performance benchmarks met:
- 1000 rows processed in <100ms (without external API)
- Memory usage <100MB for 10K rows

**And** backward compatible with existing enrichment_service interface

**Prerequisites:** Story 5.1
**Estimated Effort:** 1.5 days

---

### Story 5.5: Implement Validation Error Handling Utilities

As a **developer**,
I want to **standardize validation error handling and reporting**,
So that **I don't need to rewrite error logging and CSV export logic for every domain**.

**Acceptance Criteria:**

**Given** validation logic scattered across annuity domain
**When** validation utilities are implemented
**Then**:
- **DO NOT** create a `ValidationExecutor` class that wraps `schema.validate()`
- Create `infrastructure/validation/error_handler.py`:
  ```python
  def handle_validation_errors(
      errors: Union[SchemaErrors, List[ValidationError]],
      threshold: float = 0.1,
      total_rows: int = None
  ) -> None:
      """Check error thresholds and log validation errors"""

  def collect_error_details(
      errors: Union[SchemaErrors, List[ValidationError]]
  ) -> List[Dict[str, Any]]:
      """Convert validation errors to structured format"""
  ```
- Create `infrastructure/validation/report_generator.py`:
  ```python
  def export_error_csv(
      failed_rows: pd.DataFrame,
      filename_prefix: str = "validation_errors"
  ) -> Path:
      """Export failed rows to CSV in standard log directory"""
  ```

**And** error handling per Epic 2 specification:
- Raise exception if failure rate >10%
- Export failed rows to CSV (`logs/failed_rows_*.csv`)
- Structured error logging with context

**And** unit test coverage >90%

**And** performance maintained (utilities add minimal overhead <5ms per 1000 rows)

**Prerequisites:** Story 5.2 (requires cleansing)
**Estimated Effort:** 1.0 day

---

### Story 5.6: Implement Standard Pipeline Steps

As a **data engineer**,
I want a **library of reusable Pipeline Steps**,
So that **I can compose domain pipelines using standard Python components instead of writing custom logic for every field**.

**Acceptance Criteria:**

**Given** transformation logic embedded in annuity domain
**When** standard pipeline steps are implemented
**Then**:
- **ABANDON** JSON configuration-driven `TransformExecutor`
- Create `infrastructure/transforms/base.py`:
  ```python
  class TransformStep(ABC):
      """Base class for all pipeline steps"""
      @abstractmethod
      def apply(self, df: pd.DataFrame) -> pd.DataFrame:
          """Apply transformation to DataFrame"""
          pass

  class Pipeline:
      """Compose multiple steps into a pipeline"""
      def __init__(self, steps: List[TransformStep]):
          self.steps = steps

      def execute(self, df: pd.DataFrame) -> pd.DataFrame:
          for step in self.steps:
              df = step.apply(df)
          return df
  ```
- Create `infrastructure/transforms/standard_steps.py` with reusable steps:
  - `MappingStep` - Apply mapping from source to target column
  - `CalculationStep` - Apply calculation function to create new column
  - `RenameStep` - Rename columns based on mapping
  - `DropStep` - Drop specified columns
  - `CleansingStep` - Apply cleansing rules to specified columns

**And** all steps use vectorized Pandas operations for performance

**And** steps are composable and reusable

**And** integration with Story 1.12 (Standard Domain Generic Steps)

**And** unit test coverage >85%

**And** developer documentation with examples

**Prerequisites:** Story 5.2 (requires cleansing)
**Estimated Effort:** 1.5 days

---

### Story 5.7: Refactor AnnuityPerformanceService to Lightweight Orchestrator

As a **developer**,
I want to **refactor annuity service into a lightweight business orchestrator using code composition**,
So that **domain layer contains only business logic and adheres to Clean Architecture**.

**Acceptance Criteria:**

**Given** current service.py is 852 lines
**When** refactoring is complete
**Then**:
- `service.py` reduced to <150 lines
- All infrastructure logic removed (migrated to infrastructure layer)
- Pure business orchestration using Python code composition
- Domain service uses dependency injection for infrastructure services
- Pipeline composition pattern implemented

**And** backward compatibility maintained:
- Dagster jobs run without modification
- Existing calling code works
- Configuration file format compatible

**And** `models.py` simplified to <200 lines

**And** `constants.py` created with all business constants (renamed from config.py)

**And** end-to-end tests pass:
- Dagster job executes successfully
- Output data 100% identical to pre-refactor (comparison test)
- Performance within 10% of baseline

**And** all existing tests pass (updated as needed)

**Prerequisites:** Stories 5.4, 5.5, 5.6 (all infrastructure components ready)
**Estimated Effort:** 2.0 days

---

### Story 5.8: Integration Testing and Documentation

As a **team member**,
I want **comprehensive integration testing and updated documentation**,
So that **refactoring quality is assured and Epic 9 has a reference implementation**.

**Acceptance Criteria:**

**Given** all refactoring stories (5.1-5.7) complete
**When** integration validation executed
**Then**:

**1. End-to-End Test Suite:**
- Complete annuity pipeline execution (discover → process → load)
- Output data 100% consistency verification (vs pre-refactor baseline)
- Performance benchmarks:
  - 1000 rows processed in <3 seconds
  - Memory usage <200MB
  - Database queries <10

**2. Backward Compatibility Verification:**
- Dagster jobs run without modification
- Existing calling code works
- Configuration file format compatible

**3. Code Quality Checks:**
- Mypy strict mode passes
- Ruff linting no warnings
- Test coverage:
  - `infrastructure/` >85%
  - `domain/annuity_performance/` >90%

**4. Documentation Updates:**
- `README.md` - Updated architecture diagram
- `docs/architecture/architectural-decisions.md` - AD-010 added
- `docs/architecture/implementation-patterns.md` - Infrastructure layer patterns
- `docs/migration-guide.md` - NEW (Epic 9 reference guide)

**5. Performance Report:**
- Generate comparison report (pre vs post refactor)
- Expected results:
  - Processing time improved 50%+
  - Memory usage reduced 30%+
  - Code lines reduced 65%+ (3446 → <500)

**And** code review passed (minimum 1 team member)

**And** cleanup completed:
- Delete temporary files
- Remove feature flag code
- Remove debug logging

**Prerequisites:** Story 5.7
**Estimated Effort:** 1.5 days

---

## Epic Summary

**Total Stories:** 8 (5.1 - 5.8)
**Estimated Effort:** 10 working days + 1 buffer = 11 days (2.2 weeks)
**Priority:** Critical (blocks Epic 9)

**Success Metrics:**

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Domain code lines | 3,446 | <500 | Line count |
| Infrastructure code | 0 | ~1,200 | Line count |
| Net code reduction | - | -1,246 | Δ lines |
| Processing time (1K rows) | ~10s | <3s | Benchmark |
| Memory usage (1K rows) | ~300MB | <200MB | Profiler |
| Test coverage (domain) | ~75% | >90% | pytest-cov |
| Test coverage (infra) | N/A | >85% | pytest-cov |

**Qualitative Targets:**
- ✅ Clean Architecture compliance
- ✅ Epic 9 unblocked
- ✅ Config namespace clarity
- ✅ Zero technical debt increase
- ✅ Backward compatibility maintained
