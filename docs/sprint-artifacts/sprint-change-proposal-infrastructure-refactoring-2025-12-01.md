# Sprint Change Proposal: Epic 5 - Infrastructure Layer Architecture & Domain Refactoring

**Date:** 2025-12-01
**Author:** Bob (Scrum Master)
**Status:** Ready for Review
**Epic:** Epic 5 (New Epic - Infrastructure Layer Establishment)
**Topic:** Domain Layer Lightweighting, Infrastructure Layer Establishment, and Config Namespace Reorganization
**Workflow:** Correct-Course (纠偏工作流)
**Decision:** Create Independent Epic (not Epic 4.X extension)

---

## 1. Issue Summary

### Trigger
Current `annuity_performance` domain architecture is bloated (3,446 lines vs target <1,000 lines), blocking Epic 9 (Growth Domains Migration) and violating Clean Architecture principles.

**Why Independent Epic 5?**
- **Architectural Magnitude:** Establishes entirely new `infrastructure/` layer - fundamental architecture change
- **Cross-Epic Impact:** Affects future Epic 9 and all domain implementations
- **Requires Tech Spec:** Architecture-level changes need detailed technical specification document
- **Clear Boundaries:** Epic 4 focuses on annuity domain; Epic 5 establishes infrastructure foundation

### Problem Statement
The domain layer mixes business logic with infrastructure concerns, resulting in:
- **Code Bloat:** 3,446 lines in annuity_performance domain (target: <1,000)
- **Low Reusability:** Cannot efficiently replicate to 6+ domains in Epic 9
- **Architecture Violation:** Domain layer contains infrastructure logic (enrichment, validation, transforms)
- **Config Chaos:** Multiple `config` namespaces causing confusion and conflicts

### Evidence
**Code Analysis:**
```
domain/annuity_performance/
├── service.py              852 lines (should be <150)
├── models.py               ~300 lines
├── pipeline_steps.py       ~800 lines (should be in infrastructure)
├── transforms/             ~1,494 lines (should be in infrastructure)
└── config.py               155 lines (naming conflict)

Total: 3,446 lines (vs target: <500 lines for domain layer)
```

**Additional Issues:**
- `cleansing/` module at top-level (should be in infrastructure)
- Config files scattered across 4+ locations
- No clear infrastructure layer for cross-domain services

### Root Cause
Misunderstanding of Clean Architecture boundaries during Epic 4 implementation. Infrastructure services (enrichment, validation, transforms) were embedded in domain layer instead of being extracted as reusable components.

---

## 2. Impact Analysis

| Area | Impact Description | Severity |
|------|--------------------|----------|
| **Architecture** | Violates Clean Architecture AD-001; domain layer contains infrastructure logic | High |
| **Epic 9 (Growth)** | **BLOCKED** - Cannot replicate pattern to 6+ domains (would create 20K+ lines technical debt) | Critical |
| **Maintainability** | 3,446 lines vs <500 target = 600%+ bloat; NFR-3 maintainability violated | High |
| **Code Reuse** | Zero cross-domain reuse; every domain would duplicate infrastructure logic | Critical |
| **Config Management** | 4+ `config` namespaces causing import confusion and maintenance issues | Medium |
| **Technical Debt** | Estimated 2-3 weeks to refactor if delayed; compounding with each new domain | High |

### Affected Components

**Direct Impact:**
- `domain/annuity_performance/` - Complete refactoring
- New: `infrastructure/` layer - Creation required
- `cleansing/` - Migration to infrastructure
- `config/` - Namespace reorganization

**Indirect Impact:**
- `orchestration/jobs.py` - Interface adaptation (backward compatible)
- Epic 1 Story 1.12 - Integration with Standard Domain Generic Steps
- Future Epic 9 domains - Positive impact (reusable infrastructure)

---

## 3. Recommended Approach

### Strategy: Comprehensive Architecture Refactoring (Correct-Course)

**Core Principle:** Establish proper Clean Architecture boundaries NOW before Epic 9.

**Three-Dimensional Refactoring:**

#### Dimension 1: Domain Layer Lightweighting
- Extract infrastructure logic from domain layer
- Domain service becomes lightweight business orchestrator (<150 lines)
- Pure business models and constants only

#### Dimension 2: Infrastructure Layer Establishment
- Create `infrastructure/` layer with 4 core services:
  - `enrichment/` - CompanyIdResolver (batch optimization)
  - `validation/` - ValidationExecutor (batch validation)
  - `transforms/` - TransformExecutor (vectorized transforms)
  - `cleansing/` - Moved from top-level
- Configuration-driven, domain-agnostic components

#### Dimension 3: Config Namespace Cleanup
- `config/` → Application-level only (environment variables)
- `infrastructure/settings/` → Infrastructure configuration
- `data/mappings/` → Business data (not configuration)
- Rename domain `config.py` → `constants.py` (avoid conflicts)

### Expected Outcomes

**Quantitative:**
- Domain layer: 3,446 → <500 lines (-85% code)
- Infrastructure layer: 0 → ~1,200 lines (reusable)
- Net reduction: -1,246 lines
- Performance: 5-10x improvement (batch processing)

**Qualitative:**
- ✅ Clean Architecture compliance
- ✅ Epic 9 unblocked
- ✅ Config clarity restored
- ✅ Technical debt eliminated

---

## 4. Detailed Change Proposals

### 4.1 Architecture Documentation Update

**Action:** Update `docs/architecture.md`

**New Architectural Decision:**

```markdown
## AD-010: Infrastructure Layer & Pipeline Composition

**Context:** Domain layer was becoming bloated with infrastructure concerns.

**Decision:** Establish `infrastructure/` layer with **Python Code Composition** (Pipeline Pattern) instead of JSON Configuration for data transformations:
- `enrichment/` - Data enrichment services
- `validation/` - Validation utilities and error handling
- `transforms/` - Reusable pipeline steps (Python classes)
- `cleansing/` - Data cleansing registry
- `settings/` - Infrastructure configuration

**Rationale:**
- Python is the superior DSL for logic - no need for custom configuration languages
- Avoids the maintenance burden of a custom configuration parser
- Enforce Clean Architecture boundaries
- Enable cross-domain code reuse (Epic 9)
- Improve testability and maintainability through code composition

**Implications:**
- Infrastructure provides the building blocks (Steps/Utils), not black box engines
- Domain layer becomes lightweight orchestrators using Python composition
- Each new domain reuses infrastructure components through clear Python APIs
```

### 4.2 File Migration Map

#### Phase 1: Infrastructure Foundation
```bash
# Create infrastructure layer
mkdir -p src/work_data_hub/infrastructure/{settings,enrichment,validation,transforms}

# Migrate cleansing
mv src/work_data_hub/cleansing/ \
   src/work_data_hub/infrastructure/cleansing/
mv infrastructure/cleansing/config/ \
   infrastructure/cleansing/settings/
```

#### Phase 2: Config Reorganization
```bash
# Create data directory for business data
mkdir -p src/work_data_hub/data/mappings/

# Infrastructure settings (keep data_sources.yml as runtime config)
mv config/schema.py infrastructure/settings/data_source_schema.py
mv config/mapping_loader.py infrastructure/settings/loader.py

# Migrate business data
mv config/mappings/*.yml data/mappings/

# Rename domain configs to avoid conflicts
mv domain/annuity_performance/config.py \
   domain/annuity_performance/constants.py
mv domain/pipelines/config.py \
   domain/pipelines/pipeline_config.py
```

#### Phase 3: Infrastructure Components
```python
# Create new infrastructure services
infrastructure/
├── enrichment/
│   └── company_id_resolver.py      # From domain/annuity_performance/service.py (~200 lines)
├── validation/
│   └── validation_executor.py      # From domain/annuity_performance/service.py (~150 lines)
└── transforms/
    └── transform_executor.py       # From domain/annuity_performance/service.py (~350 lines)
```

#### Phase 4: Domain Layer Refactoring
```python
# Refactor domain service to lightweight orchestrator
domain/annuity_performance/
├── service.py              # 852 → <150 lines (dependency injection + orchestration)
├── models.py               # ~300 → <200 lines (simplified)
├── schemas.py              # Keep (Pandera schemas)
└── constants.py            # Renamed from config.py (business constants)

# DELETE (migrated to infrastructure)
├── pipeline_steps.py       # → infrastructure/transforms/
└── transforms/             # → infrastructure/transforms/
```

### 4.3 Import Path Updates

**Automated Migration Script:**
```python
# update_imports.py
IMPORT_MIGRATIONS = {
    # Cleansing
    "from work_data_hub.cleansing":
        "from work_data_hub.infrastructure.cleansing",

    # Infrastructure settings
    "from work_data_hub.config.schema":
        "from work_data_hub.infrastructure.settings.data_source_schema",
    "from work_data_hub.config.mapping_loader":
        "from work_data_hub.infrastructure.settings.loader",

    # Domain constants
    "from domain.annuity_performance.config":
        "from domain.annuity_performance.constants",
    "from domain.pipelines.config":
        "from domain.pipelines.pipeline_config",
}
```

**Affected Files:** ~30 import statements across 15 files

### 4.4 New Architecture Overview

**Final Structure:**
```
src/work_data_hub/
├── config/                          # Application & runtime configuration
│   ├── settings.py                  # Environment variables (Pydantic BaseSettings)
│   ├── data_sources.yml             # Runtime config (user-facing, deployment-time)
│   └── .env.example
│
├── infrastructure/                  # NEW: Cross-domain services
│   ├── settings/                    # Infrastructure configuration logic
│   │   ├── data_source_schema.py    # Schema validation for configs
│   │   └── loader.py                # Config loading utilities
│   ├── cleansing/                   # Migrated from top-level
│   │   ├── registry.py
│   │   ├── rules/
│   │   └── settings/cleansing_rules.yml
│   ├── enrichment/                  # NEW
│   │   └── company_id_resolver.py
│   ├── validation/                  # NEW
│   │   ├── error_handler.py        # Validation error utilities
│   │   └── report_generator.py     # Error report generation
│   └── transforms/                  # NEW
│       ├── base.py                  # Pipeline base classes
│       └── standard_steps.py       # Reusable pipeline steps
│
├── domain/                          # Lightweight business layer
│   ├── annuity_performance/
│   │   ├── service.py              # <150 lines (orchestration only)
│   │   ├── models.py               # <200 lines
│   │   ├── schemas.py              # <100 lines
│   │   └── constants.py            # Business constants (renamed from config.py)
│   └── pipelines/
│       ├── core.py
│       └── pipeline_config.py      # Renamed from config.py
│
├── data/                            # NEW: Business data
│   └── mappings/                    # Migrated from config/mappings
│       ├── business_type_code.yml
│       └── ...
│
├── io/                              # I/O layer (no changes)
└── orchestration/                   # Orchestration layer (adapter updates)
```

---

## 5. Story Breakdown

### Epic 5: Infrastructure Layer Architecture & Domain Refactoring

**Total Stories:** 8 (5.1 - 5.8)
**Estimated Effort:** 10 working days + 1 buffer = 11 days (2.2 weeks)
**Priority:** Critical (blocks Epic 9)
**Prerequisites:** Technical Specification document must be created first

---

### Story 5.1: Infrastructure Layer Foundation Setup

**User Story:**
As an **architect**, I want to **establish the infrastructure layer directory structure**, so that **subsequent stories can migrate functionality to proper architecture layers**.

**Acceptance Criteria:**

**Given** current codebase lacks infrastructure directory
**When** infrastructure foundation is created
**Then** the following structure exists:
```
src/work_data_hub/infrastructure/
├── __init__.py                      # Module docs + exports
├── settings/__init__.py
├── cleansing/__init__.py           # Placeholder for Story 5.2
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

**Technical Tasks:**
- Create directory structure
- Write module documentation
- Update `.gitignore` if needed
- Verify imports in CI

**Effort:** 0.5 day
**Priority:** P0 (Foundation)
**Dependencies:** None

---

### Story 5.2: Migrate Cleansing Module to Infrastructure

**User Story:**
As a **data engineer**, I want to **move the cleansing module into the infrastructure layer**, so that **cleansing services are correctly categorized as cross-domain infrastructure**.

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

**Rollback Plan:**
- Temporary symlink from old to new location
- Feature flag for emergency rollback

**Technical Tasks:**
- Execute file migration
- Batch update imports (script-assisted)
- Update test files
- Verify configuration loading
- Full test suite execution

**Effort:** 0.5 day
**Priority:** P0 (Foundation)
**Dependencies:** Story 5.1

---

### Story 5.3: Config Namespace Reorganization

**User Story:**
As a **developer**, I want to **eliminate config namespace conflicts and organize configuration by responsibility**, so that **architecture layers are clear and configs are easy to locate**.

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

**And** all import paths updated (~25 locations):
```python
# Examples
- from work_data_hub.config.schema import DataSourceConfig
+ from work_data_hub.infrastructure.settings.data_source_schema import DataSourceConfig

- from domain.annuity_performance.config import PLAN_CODE_CORRECTIONS
+ from domain.annuity_performance.constants import PLAN_CODE_CORRECTIONS
```

**And** Dagster jobs successfully load data source configuration

**And** all tests pass (including config loading tests)

**And** documentation updated (README config section)

**Technical Tasks:**
- Create `data/mappings/` directory
- Migrate files to new locations
- Batch update imports
- Update configuration loading logic
- Update tests
- Update documentation

**Effort:** 1.0 day
**Priority:** P1 (Important)
**Dependencies:** Stories 5.1, 5.2

---

### Story 5.4: Implement CompanyIdResolver in Infrastructure

**User Story:**
As a **data engineer**, I want to **extract company ID resolution logic into a reusable infrastructure service**, so that **batch optimization is achieved and multiple domains can reuse this service**.

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

**And** unit test coverage >90%:
- Test each resolution tier
- Test batch processing performance
- Test error handling
- Test enrichment service integration (mocked)

**And** performance benchmarks met:
- 1000 rows processed in <100ms (without external API)
- Memory usage <100MB for 10K rows

**And** backward compatible:
- Existing enrichment_service interface unchanged
- Dependency injection support

**Technical Tasks:**
- Extract logic from service.py (~200 lines)
- Refactor to batch processing mode
- Implement hierarchical resolution strategy
- Write unit tests
- Performance benchmarking
- Integration testing with annuity_performance

**Effort:** 1.5 days
**Priority:** P0 (Core)
**Dependencies:** Story 5.1

---

### Story 5.5: Implement Validation Error Handling Utilities

**User Story:**
As a **developer**, I want to **standardize validation error handling and reporting**, so that **I don't need to rewrite error logging and CSV export logic for every domain**.

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
- Domain service will use utilities directly:
  ```python
  # Bronze validation
  try:
      BronzeSchema.validate(df, lazy=True)
  except SchemaErrors as e:
      error_handler.handle_validation_errors(e.failure_cases, total_rows=len(df))
      report_generator.export_error_csv(e.data[e.failure_cases.index])

  # Pydantic model validation (chunked for performance)
  valid_models = []
  errors = []
  for chunk in np.array_split(df, max(1, len(df) // 1000)):
      for _, row in chunk.iterrows():
          try:
              model = AnnuityPerformanceModel(**row.to_dict())
              valid_models.append(model)
          except ValidationError as e:
              errors.append({"row": row, "error": e})

  if errors:
      error_handler.handle_validation_errors(errors, total_rows=len(df))
  ```

**And** error handling per Epic 2 specification:
- Raise exception if failure rate >10%
- Export failed rows to CSV (`logs/failed_rows_*.csv`)
- Structured error logging with context

**And** unit test coverage >90%:
- Test error threshold calculation
- Test CSV export functionality
- Test error detail collection
- Test integration with Pandera and Pydantic errors

**And** performance maintained:
- Utilities add minimal overhead (<5ms per 1000 rows)
- CSV export is asynchronous for large datasets

**Technical Tasks:**
- Create lightweight utility functions (~100 lines total)
- Implement error threshold checking
- Implement CSV export with proper formatting
- Write comprehensive unit tests
- Document usage patterns

**Effort:** 1.0 day
**Priority:** P0 (Core)
**Dependencies:** Story 5.2 (requires cleansing)

---

### Story 5.6: Implement Standard Pipeline Steps

**User Story:**
As a **data engineer**, I want a **library of reusable Pipeline Steps**, so that **I can compose domain pipelines using standard Python components instead of writing custom logic for every field**.

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
  ```python
  class MappingStep(TransformStep):
      def __init__(self, mapping_dict: Dict, source_col: str, target_col: str):
          """Apply mapping from source to target column"""

  class CalculationStep(TransformStep):
      def __init__(self, func: Callable, target_col: str, **kwargs):
          """Apply calculation function to create new column"""

  class RenameStep(TransformStep):
      def __init__(self, rename_map: Dict[str, str]):
          """Rename columns based on mapping"""

  class DropStep(TransformStep):
      def __init__(self, columns: List[str]):
          """Drop specified columns"""

  class CleansingStep(TransformStep):
      def __init__(self, cleansing_registry: CleansingRegistry, rules_map: Dict[str, List[str]]):
          """Apply cleansing rules to specified columns"""
  ```

**And** all steps use vectorized Pandas operations for performance

**And** steps are composable and reusable:
```python
# Example usage in domain service
pipeline = Pipeline([
    RenameStep(CHINESE_TO_ENGLISH_MAPPING),
    CleansingStep(cleansing_registry, {"客户名称": ["trim_whitespace", "normalize_company_name"]}),
    MappingStep(BUSINESS_TYPE_CODE_MAPPING, "业务类型", "product_line_code"),
    CalculationStep(lambda df: df["期末资产规模"] - df["期初资产规模"], "asset_change"),
    DropStep(["临时字段1", "临时字段2"])
])
```

**And** integration with Story 1.12 (Standard Domain Generic Steps)

**And** unit test coverage >85%:
- Test each step type independently
- Test pipeline composition
- Test error handling
- Performance benchmarks

**And** developer documentation with examples

**Technical Tasks:**
- Create base classes and Pipeline (~100 lines)
- Implement standard step classes (~200 lines)
- Vectorization optimization
- Unit tests for each step type
- Integration tests with pipelines
- Documentation and examples

**Effort:** 1.5 days
**Priority:** P0 (Core)
**Dependencies:** Story 5.2 (requires cleansing)

---

### Story 5.7: Refactor AnnuityPerformanceService to Lightweight Orchestrator

**User Story:**
As a **developer**, I want to **refactor annuity service into a lightweight business orchestrator using code composition**, so that **domain layer contains only business logic and adheres to Clean Architecture**.

**Acceptance Criteria:**

**Given** current service.py is 852 lines
**When** refactoring is complete
**Then**:
- `service.py` reduced to <150 lines
- All infrastructure logic removed (migrated to infrastructure layer)
- Pure business orchestration using Python code composition:
  ```python
  class AnnuityPerformanceService:
      def __init__(
          self,
          cleansing_registry: CleansingRegistry,
          enrichment_resolver: CompanyIdResolver,
      ):
          """Dependency injection of infrastructure services"""
          self.cleansing = cleansing_registry
          self.enrichment = enrichment_resolver
          self.pipeline = self._build_domain_pipeline()

      def _build_domain_pipeline(self) -> Pipeline:
          """Build domain-specific transformation pipeline using code composition"""
          return Pipeline([
              RenameStep(CHINESE_TO_ENGLISH_MAPPING),
              CleansingStep(self.cleansing, {
                  "客户名称": ["trim_whitespace", "normalize_company_name"],
                  "交易日期": ["standardize_date"]
              }),
              MappingStep(BUSINESS_TYPE_CODE_MAPPING, "业务类型", "product_line_code"),
              MappingStep(PLAN_CODE_CORRECTIONS, "计划代码", "corrected_plan_code"),
              CalculationStep(
                  lambda df: (df["期末资产规模"] - df["期初资产规模"]) / df["期初资产规模"],
                  "当期收益率"
              ),
              DropStep(["临时字段1", "临时字段2", "原始业务类型"])
          ])

      def process(
          self, rows: List[Dict], data_source: str = "unknown"
      ) -> ProcessingResult:
          """Business flow orchestration (<100 lines)"""
          # Convert to DataFrame
          df = pd.DataFrame(rows)

          # Bronze validation
          try:
              BronzeSchema.validate(df, lazy=True)
          except SchemaErrors as e:
              error_handler.handle_validation_errors(e.failure_cases, len(df))
              report_generator.export_error_csv(e.data[e.failure_cases.index])
              raise

          # Apply transformation pipeline
          df_transformed = self.pipeline.execute(df)

          # Company ID enrichment
          df_enriched = self.enrichment.resolve_batch(
              df_transformed,
              strategy={
                  "plan_override_field": "corrected_plan_code",
                  "mapping_table": COMPANY_ID_MAPPINGS,
                  "default_company_id": "UNKNOWN"
              }
          )

          # Silver validation with Pydantic models
          valid_models = []
          for chunk in np.array_split(df_enriched, max(1, len(df_enriched) // 1000)):
              for _, row in chunk.iterrows():
                  try:
                      model = AnnuityPerformanceModel(**row.to_dict())
                      valid_models.append(model)
                  except ValidationError as e:
                      # Handle individual validation errors
                      pass

          # Gold layer preparation
          df_gold = pd.DataFrame([m.dict() for m in valid_models])
          GoldSchema.validate(df_gold)

          return ProcessingResult(
              success_count=len(valid_models),
              error_count=len(df) - len(valid_models),
              data=df_gold
          )
  ```

**And** backward compatibility adapter created:
```python
# domain/annuity_performance/adapters.py
def process_with_enrichment(...) -> ProcessingResultWithEnrichment:
    """Backward compatibility wrapper"""
    service = AnnuityPerformanceService(cleansing, enrichment)
    result = service.process(rows, data_source)
    return _convert_to_legacy_format(result)
```

**And** `models.py` simplified to <200 lines (complex transformation logic removed)

**And** `constants.py` created with all business constants:
```python
# domain/annuity_performance/constants.py
CHINESE_TO_ENGLISH_MAPPING = {...}
BUSINESS_TYPE_CODE_MAPPING = {...}
PLAN_CODE_CORRECTIONS = {...}
COMPANY_ID_MAPPINGS = {...}
```

**And** end-to-end tests pass:
- Dagster job executes successfully
- Output data 100% identical to pre-refactor (comparison test)
- Performance within 10% of baseline

**And** all existing tests pass (updated as needed)

**Technical Tasks:**
- Refactor service.py using pipeline composition
- Extract constants to constants.py
- Create backward compatibility adapter
- Simplify models.py
- Update tests for new structure
- Comparison testing
- Performance testing

**Effort:** 2.0 days
**Priority:** P0 (Core)
**Dependencies:** Stories 5.4, 5.5, 5.6 (all infrastructure components ready)

---

### Story 5.8: Integration Testing and Documentation

**User Story:**
As a **team member**, I want **comprehensive integration testing and updated documentation**, so that **refactoring quality is assured and Epic 9 has a reference implementation**.

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
- Existing calling code works (via adapters)
- Configuration file format compatible

**3. Code Quality Checks:**
- Mypy strict mode passes
- Ruff linting no warnings
- Test coverage:
  - `infrastructure/` >85%
  - `domain/annuity_performance/` >90%

**4. Documentation Updates:**
- `README.md` - Updated architecture diagram
- `docs/architecture/infrastructure-layer.md` - NEW (infrastructure layer documentation)
- `docs/domains/annuity_performance.md` - Updated (post-refactor architecture)
- `docs/migration-guide.md` - NEW (Epic 9 reference guide)

**5. Performance Report:**
- Generate comparison report (pre vs post refactor)
- Expected results:
  - Processing time improved 50%+
  - Memory usage reduced 30%+
  - Code lines reduced 65%+ (3446 → <500)

**And** code review passed (minimum 1 team member)

**And** cleanup completed:
- Delete `service_legacy.py`
- Remove feature flag code
- Remove debug logging

**Technical Tasks:**
- Write end-to-end tests
- Comparison testing (output consistency)
- Performance benchmarking
- Code quality checks
- Documentation writing
- Code review
- Cleanup tasks

**Effort:** 1.5 days
**Priority:** P0 (Quality Assurance)
**Dependencies:** Story 5.7

---

## 6. Implementation Schedule

### Sprint Timeline (12 Days Total)

**Week 1: Foundation & Config (Days 1-5)**
```
Day 1:   Story 5.1 - Infrastructure Foundation         ✓ 0.5d
Day 1-2: Story 5.2 - Cleansing Migration              ✓ 0.5d
Day 2-3: Story 5.3 - Config Reorganization            ✓ 1.0d
Day 3-5: Story 5.4 - CompanyIdResolver                ✓ 1.5d
```

**Week 2: Core Infrastructure (Days 6-10)**
```
Day 6:   Story 5.5 - Validation Utilities             ✓ 1.0d
Day 7-8: Story 5.6 - Standard Pipeline Steps          ✓ 1.5d
Day 9-10: Story 5.7 - Service Refactoring             ✓ 2.0d
```

**Week 3: Integration & Finalization (Days 11-12)**
```
Day 11-12: Story 5.8 - Testing & Documentation        ✓ 1.5d
           + 1 day buffer for unforeseen issues
```

### Milestones

- 🎯 **Milestone 1** (Day 3): Infrastructure foundation and config reorganization complete
- 🎯 **Milestone 2** (Day 9): All infrastructure components implemented
- 🎯 **Milestone 3** (Day 11): Domain layer refactored to lightweight orchestrator
- 🎯 **Milestone 4** (Day 13): Epic complete, all acceptance criteria met

---

## 7. Testing Strategy

### Test Pyramid
```
              🔺 E2E Tests (5%)
             ─────────────────
            🔺 Integration (15%)
           ───────────────────────
          🔺 Unit Tests (80%)
         ─────────────────────────
```

### Test Types

**1. Unit Tests** (Every Story)
- Infrastructure components tested independently
- Mock external dependencies
- Coverage target: >85%

**2. Integration Tests** (Stories 4.17, 4.18)
- Infrastructure + Domain integration
- Real test database
- Coverage target: >70%

**3. Comparison Tests** (Story 4.18)
- New vs old implementation output consistency
- 1000 rows of real data
- 100% data match required

**4. Performance Tests** (Stories 4.14, 4.15, 4.16, 4.18)
- Baseline vs refactored benchmarks
- Target: <3 seconds per 1000 rows
- Memory: <200MB

**5. Regression Tests** (Story 4.18)
- All Epic 4 existing tests pass
- CI/CD pipeline green

---

## 8. Risk Management

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| Output data inconsistency | Medium | High | Comparison testing + parallel validation | Dev |
| Performance degradation | Low | Medium | Performance benchmarking + optimization | Dev |
| Breaking existing functionality | Low | High | Backward compatibility adapters + feature flags | Dev |
| Effort overrun | Medium | Medium | 2-day buffer + scope adjustment options | SM |
| Insufficient test coverage | Low | Medium | Mandatory coverage gates in CI | Dev |

### Rollback Plan
- ✅ Preserve old implementations as `_legacy` files (temporary)
- ✅ Feature flags for new/old implementation switching
- ✅ Git branching: Each story on separate branch
- ✅ No destructive database changes (code refactor only)

---

## 9. Success Metrics

### Quantitative Targets

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Domain code lines | 3,446 | <500 | Line count |
| Infrastructure code | 0 | ~1,200 | Line count |
| Net code reduction | - | -1,246 | Δ lines |
| Processing time (1K rows) | ~10s | <3s | Benchmark |
| Memory usage (1K rows) | ~300MB | <200MB | Profiler |
| Test coverage (domain) | ~75% | >90% | pytest-cov |
| Test coverage (infra) | N/A | >85% | pytest-cov |

### Qualitative Targets
- ✅ Clean Architecture compliance
- ✅ Epic 9 unblocked
- ✅ Config namespace clarity
- ✅ Zero technical debt increase
- ✅ Backward compatibility maintained

---

## 10. Implementation Handoff

### Scope Classification
**Moderate** - Significant refactoring with clear architectural vision and detailed implementation plan.

### Route To
- **Primary:** Development Team (Implementation)
- **Support:** SM (Story drafting, progress tracking)
- **Review:** Architect (Architecture review, acceptance)

### Developer Handoff Package

**1. Specifications:**
- ✅ 8 detailed stories (4.11-4.18) with acceptance criteria
- ✅ Refactoring design documents (`docs/specific/domain-design/`)
- ✅ Code migration mapping table
- ✅ Test strategy and coverage requirements
- ✅ Performance benchmarking methodology

**2. Reference Materials:**
- Architecture decision document (AD-010)
- Clean Architecture boundaries diagram
- Infrastructure component interface definitions
- Epic 2/1.12 integration points

**3. Development Environment:**
- Feature branch naming: `epic-4x-story-{number}-{description}`
- CI/CD pipeline configuration
- Test database setup instructions
- Performance profiling tools

### Next Steps (Action Items)

**Phase 0: Technical Specification (Before Implementation)**
1. ✅ **Create Tech Spec** - Use `/bmad:bmm:workflows:create-tech-spec` workflow
   - Document infrastructure layer architecture design
   - Define component interfaces and contracts
   - Specify migration strategy and rollback plans
   - Include performance benchmarks and acceptance criteria
2. ✅ **Architecture Review** - Architect approval of tech spec
3. ✅ **Create Epic 5 file** - `docs/epics/epic-5-infrastructure-layer.md`

**Phase 1: Epic & Story Planning (After Tech Spec Approved)**
1. ✅ **Update sprint-status.yaml** - Add Epic 5 with 8 stories
2. ✅ **Draft Story 5.1** - Use `/create-story` workflow
3. ✅ **Draft remaining stories** - Stories 5.2-5.8

**Phase 2: Implementation (After Stories Approved)**
- Week 1: Stories 5.1-5.4 (Foundation & Config)
- Week 2: Stories 5.5-5.7 (Core Infrastructure & Refactoring)
- Week 3: Story 5.8 (Integration & Documentation)

**Success Criteria for Handoff:**
- [ ] **Tech Spec created and approved** (CRITICAL PREREQUISITE)
- [ ] Epic 5 file created with proper dependencies on Epic 4
- [ ] All 8 stories created in tracking system
- [ ] Dev team confirms understanding of architecture changes
- [ ] Test environments prepared
- [ ] Story 5.1 ready to start

---

## 11. Appendices

### A. File Migration Checklist

```bash
# Phase 1: Infrastructure Foundation
✓ Create infrastructure/ directory structure
✓ Create data/mappings/ directory

# Phase 2: Cleansing Migration
✓ Move cleansing/ → infrastructure/cleansing/
✓ Rename cleansing/config/ → cleansing/settings/
✓ Update ~15 import statements

# Phase 3: Config Reorganization
✓ data_sources.yml stays in config/ (runtime config)
✓ Move config/schema.py → infrastructure/settings/data_source_schema.py
✓ Move config/mapping_loader.py → infrastructure/settings/loader.py
✓ Move config/mappings/*.yml → data/mappings/
✓ Rename domain configs (avoid conflicts)
✓ Update ~25 import statements

# Phase 4: Infrastructure Implementation
✓ Create infrastructure/enrichment/company_id_resolver.py
✓ Create infrastructure/validation/error_handler.py
✓ Create infrastructure/validation/report_generator.py
✓ Create infrastructure/transforms/base.py
✓ Create infrastructure/transforms/standard_steps.py

# Phase 5: Domain Refactoring
✓ Refactor domain/annuity_performance/service.py (852 → <150 lines)
✓ Simplify domain/annuity_performance/models.py
✓ Rename domain/annuity_performance/config.py → constants.py
```

### B. Import Update Script Template

```python
#!/usr/bin/env python3
"""Automated import path migration script"""

import re
from pathlib import Path

MIGRATIONS = {
    # Cleansing
    r"from\s+work_data_hub\.cleansing":
        "from work_data_hub.infrastructure.cleansing",

    # Infrastructure settings (schema and loader only)
    r"from\s+work_data_hub\.config\.schema":
        "from work_data_hub.infrastructure.settings.data_source_schema",
    r"from\s+work_data_hub\.config\.mapping_loader":
        "from work_data_hub.infrastructure.settings.loader",

    # Domain constants
    r"from\s+domain\.annuity_performance\.config":
        "from domain.annuity_performance.constants",
    r"from\s+domain\.pipelines\.config":
        "from domain.pipelines.pipeline_config",
}

def migrate_file(file_path: Path):
    """Apply all import migrations to a single file"""
    content = file_path.read_text(encoding="utf-8")
    modified = False

    for old_pattern, new_import in MIGRATIONS.items():
        new_content = re.sub(old_pattern, new_import, content)
        if new_content != content:
            content = new_content
            modified = True

    if modified:
        file_path.write_text(content, encoding="utf-8")
        print(f"✓ Updated: {file_path}")

def main():
    """Migrate all Python files in src/ and tests/"""
    for pattern in ["src/**/*.py", "tests/**/*.py"]:
        for file_path in Path(".").glob(pattern):
            migrate_file(file_path)

if __name__ == "__main__":
    main()
```

### C. Performance Benchmarking Template

```python
"""Performance comparison: Pre vs Post refactor"""

import time
import tracemalloc
from typing import Dict, Any

def benchmark_processing(processor, data: List[Dict], runs: int = 3) -> Dict[str, Any]:
    """Benchmark data processing performance"""
    times = []
    memory_peaks = []

    for _ in range(runs):
        tracemalloc.start()
        start = time.perf_counter()

        result = processor.process(data)

        elapsed = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        times.append(elapsed)
        memory_peaks.append(peak / 1024 / 1024)  # MB

    return {
        "avg_time_ms": sum(times) / len(times) * 1000,
        "avg_memory_mb": sum(memory_peaks) / len(memory_peaks),
        "row_count": len(data),
        "rows_per_second": len(data) / (sum(times) / len(times))
    }

# Usage
legacy_results = benchmark_processing(legacy_processor, test_data)
new_results = benchmark_processing(new_processor, test_data)

print(f"Processing Time: {legacy_results['avg_time_ms']:.1f}ms → {new_results['avg_time_ms']:.1f}ms")
print(f"Improvement: {(1 - new_results['avg_time_ms']/legacy_results['avg_time_ms'])*100:.1f}%")
```

---

**End of Proposal**

**Status:** Ready for implementation
**Next Action:** Draft Story 4.11 using `/create-story` workflow
