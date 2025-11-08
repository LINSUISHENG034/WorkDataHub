# WorkDataHub - Product Requirements Document

**Author:** Link
**Date:** 2025-11-08
**Version:** 1.0

---

## Executive Summary

**WorkDataHub** is a systematic refactoring of the legacy `annuity_hub` data processing system into a modern, maintainable, and highly automated data pipeline platform. The project transforms a bloated, tangled monolithic ETL system into an elegant, configuration-driven architecture that processes multiple enterprise data domains (annuity performance, business metrics, portfolio rankings, performance attribution, etc.) and delivers clean, analysis-ready data to downstream BI tools like PowerBI.

**Current State:** Internal data processing tool used by Link, with plans to transfer to team members after stabilization.

**Core Problem Solved:** Eliminates the maintenance nightmare of legacy code by replacing manual, error-prone data processing with automated, versioned pipelines that intelligently identify the latest data versions across multiple domains and systematically clean, transform, and load data into the corporate database.

**Primary Users:** Internal data analysts and business intelligence team members who need reliable, automated data processing to feed downstream analytics.

### What Makes This Special

**The Magic of WorkDataHub:**

WorkDataHub transforms data processing from a frustrating chore into an effortless, reliable system through three core innovations:

1. **Intelligent Automation** - Automatically detects and processes the latest version of data files across multiple domains (V1, V2, etc.) without manual intervention, eliminating the daily headache of "which file should I process today?"

2. **Fearless Extensibility** - Adding a new data domain takes minutes instead of weeks. The pipeline framework, Pydantic validation, and configuration-driven architecture mean new domains follow proven patterns without touching existing code.

3. **Team-Ready Maintainability** - Built for handoff. Clear separation of concerns (domain/io/orchestration), comprehensive data validation, and modern Python tooling (mypy, ruff, pytest) ensure team members can confidently modify and extend the system.

**The "Wow" Moment:** When a new monthly data drop arrives, WorkDataHub automatically identifies all new files across all domains, processes them through validated pipelines, and delivers clean data to PowerBI - all while you're focused on actual analysis instead of wrestling with Excel and SQL scripts.

---

## Project Classification

**Technical Type:** Internal Data Platform / ETL Pipeline System
**Domain:** Enterprise Business Intelligence / Data Engineering
**Complexity:** Medium (Complex data transformations, but not regulated domain)

**Classification Rationale:**

- **Project Type**: This is an internal developer/data engineering tool - a Python-based data pipeline platform similar to modern ETL tools (Airflow, Prefect), but purpose-built for your specific enterprise data domains
- **Domain**: Enterprise Business Intelligence / Data Engineering (annuity performance, business metrics, portfolio analytics) - not high-regulation fintech/healthcare, but business-critical internal data
- **Complexity**: Medium - Multiple data sources with versioning, complex transformations, and critical BI dependencies, but manageable scope with modern frameworks

**Reference Context:**
- **Research Documents:**
  - `docs/deep_research/1.md` - Modern Data Processing Architectures (Gemini Deep Research, 2025-11-08)
  - `docs/deep_research/2.md` - Refactoring Strategy Comparison Matrix
  - `docs/deep_research/3.md` - Strangler Fig Implementation Guide
  - `docs/deep_research/4.md` - Data Contracts with Pandera (DataFrame Validation)
  - `docs/research-deep-prompt-2025-11-08.md` - Research Prompt for AI Platforms
- **Archive Documents:**
  - `docs/archive/prd.md` - Previous Annuity Performance Pipeline Migration PRD
  - `docs/archive/architecture.md` - Brownfield Enhancement Architecture
- **Existing Codebase:** `src/work_data_hub/` - Partially refactored with Dagster + Pydantic + Pipeline framework
- **Legacy System:** `legacy/annuity_hub/` - Original monolithic implementation (to be replaced)

---

## Success Criteria

**WorkDataHub is successful when:**

### 1. Automation Excellence
**"Set it and forget it" data processing**

- ✅ **Zero Manual File Selection** - System automatically identifies and processes latest data versions (V1, V2, etc.) across all domains without user intervention
- ✅ **Monthly Data Drop Automation** - When new monthly data arrives (`reference/monthly/YYYYMM/收集数据`), all relevant domains are automatically detected, validated, and processed
- ✅ **Hands-Free PowerBI Refresh** - BI dashboards refresh with clean data without manual SQL scripts or Excel manipulation
- ✅ **Self-Healing Pipelines** - Data validation catches issues at source (Bronze layer), fails fast with clear error messages, preventing corrupt data from reaching the database

**Success Metric:** Process a complete monthly data drop (6+ domains) from arrival to PowerBI-ready state in <30 minutes with zero manual steps.

---

### 2. Fearless Extensibility
**"New domain in an afternoon, not a sprint"**

- ✅ **Pattern-Based Development** - Adding a new data domain follows the proven pipeline framework pattern (domain service + Pydantic models + Dagster job)
- ✅ **Configuration Over Code** - File discovery rules, cleansing mappings, and validation schemas are declared in YAML/JSON, not hardcoded in Python
- ✅ **Isolated Domains** - New domains don't touch existing code; failures in one domain don't cascade to others
- ✅ **Reusable Components** - Shared pipeline framework, cleansing registry, and IO abstractions mean 80% of boilerplate is already written

**Success Metric:** A developer with Python experience can add a new data domain (from sample Excel to database-loaded) in <4 hours following existing patterns.

---

### 3. Team-Ready Maintainability
**"Built for handoff, not hero-worship"**

- ✅ **100% Type Safety** - mypy passes with no type errors; all public functions have type hints
- ✅ **Clear Architecture Boundaries** - domain/ (business logic), io/ (data access), orchestration/ (Dagster) separation is enforced
- ✅ **Comprehensive Validation** - Pydantic models validate row-level data; pandera contracts validate DataFrame shape at layer boundaries
- ✅ **Self-Documenting Code** - Pipeline steps have descriptive names; data models use Chinese field names matching source Excel files
- ✅ **Test Coverage** - Critical transformation logic has unit tests; integration tests validate end-to-end pipeline execution

**Success Metric:** A team member unfamiliar with the codebase can:
- Understand what a domain pipeline does by reading its service file (<15 minutes)
- Fix a data transformation bug without breaking other domains (<2 hours)
- Confidently deploy changes after running tests and type checks

---

### 4. Legacy System Retirement
**"Strangler Fig success - legacy code decommissioned safely"**

- ✅ **100% Output Parity** - Refactored pipelines produce identical output to `legacy/annuity_hub` (validated with golden dataset regression tests)
- ✅ **Parallel Execution** - New and legacy pipelines run side-by-side during migration, with automated reconciliation detecting any discrepancies
- ✅ **Incremental Migration** - Domains are migrated one at a time using the Strangler Fig pattern, reducing risk
- ✅ **Legacy Deletion** - Once a domain is validated in production, the corresponding legacy code is deleted (not commented out or kept "just in case")

**Success Metric:** All 6+ core data domains migrated from legacy system with zero production data quality incidents during cutover.

---

### 5. Operational Reliability
**"Production-ready stability"**

- ✅ **Data Quality Gates** - Invalid source data is rejected at Bronze layer with actionable error messages before corruption spreads
- ✅ **Idempotent Pipelines** - Re-running the same pipeline with the same input produces identical output; no duplicate records or state corruption
- ✅ **Audit Trail** - Pipeline executions are logged in Dagster with timestamps, input files, record counts, and error details
- ✅ **Graceful Degradation** - Failures in optional enrichment services (e.g., company lookup) don't block the main pipeline

**Success Metric:** <2% pipeline failure rate across monthly production runs; all failures have clear root causes in logs.

---

**What Success Is NOT:**

- ❌ External user adoption (this is an internal tool)
- ❌ Real-time/streaming performance (monthly batch processing is sufficient)
- ❌ Cloud-native deployment (PostgreSQL + local execution is fine)
- ❌ ML/AI predictions (focus is data cleaning and transformation, not analytics)

---

## Product Scope

### MVP - Minimum Viable Product
**"Prove the pattern works on real complexity"**

**Goal:** Successfully migrate the **highest-complexity domain** (annuity performance) using the Strangler Fig pattern, proving the architecture can replace legacy code with zero regression.

**Core MVP Deliverables:**

1. **Annuity Performance Domain - Complete Migration**
   - ✅ Refactor existing `domain/annuity_performance/` to use shared pipeline framework
   - ✅ Integrate company enrichment service adapter for data augmentation
   - ✅ Implement Bronze → Silver → Gold layered architecture
   - ✅ Add pandera data contracts at layer boundaries (DataFrame validation)
   - ✅ Create golden dataset regression suite (100% parity with legacy output)
   - ✅ Parallel execution with legacy system + automated reconciliation
   - ✅ Production validation and legacy code deletion

2. **Core Infrastructure - Battle-Tested**
   - ✅ Shared pipeline framework (`domain/pipelines/core.py`) - proven with annuity domain
   - ✅ Cleansing framework with registry-driven rules (`cleansing/registry.py`)
   - ✅ Configuration-driven file discovery (auto-detect V1, V2 versions)
   - ✅ Dagster orchestration layer with jobs, schedules, sensors
   - ✅ PostgreSQL transactional loading with error handling
   - ✅ Pydantic v2 models for row-level validation

3. **Version Detection System**
   - ✅ Automatically identify latest data version across domains (V1, V2, etc.)
   - ✅ Smart file pattern matching for monthly data drops (`reference/monthly/YYYYMM/收集数据/`)
   - ✅ Configurable version precedence rules per domain

4. **Data Quality Foundation**
   - ✅ Bronze layer validation (reject bad source data immediately)
   - ✅ Pydantic models with Chinese field names matching Excel sources
   - ✅ Pandera DataFrame contracts enforcing schema at layer boundaries
   - ✅ Clear error messages with actionable guidance

**MVP Success Criteria:**
- ✅ Annuity performance domain processes monthly data with 100% parity to legacy
- ✅ Version detection works across V1/V2 variations automatically
- ✅ Golden dataset regression tests pass (no output differences)
- ✅ Team member can understand and modify annuity pipeline in <2 hours

**Out of Scope for MVP:**
- ❌ Migrating all 6+ domains (only annuity domain)
- ❌ Performance optimization beyond "good enough" (<30 min per domain)
- ❌ Advanced scheduling (basic monthly triggers sufficient)
- ❌ UI/dashboard for pipeline monitoring (Dagster UI is sufficient)

---

### Growth Features (Post-MVP)
**"Complete the migration - all domains on modern platform"**

**Goal:** Migrate remaining 5+ data domains following the proven annuity pattern, achieving complete legacy system retirement.

**Additional Domains to Migrate:**

Based on `reference/monthly/202501/收集数据/`:

1. **业务收集 (Business Collection)**
   - Multiple sub-domains with V1/V2 versioning
   - KPI tracking, fee collection, investment metrics
   - Pattern: Similar to annuity (multi-sheet Excel, enrichment needed)

2. **数据采集 (Data Collection)**
   - Investment portfolio aggregations
   - Regional performance analytics
   - Pattern: Simpler than annuity (fewer transformations)

3. **战区收集 (Regional Collection)**
   - Geographic/regional performance breakdowns
   - Pattern: Medium complexity (aggregations + mapping)

4. **组合排名 (Portfolio Rankings)**
   - Portfolio performance rankings and comparisons
   - Pattern: Calculation-heavy (less data quality issues)

5. **绩效归因 (Performance Attribution)**
   - Performance analysis and attribution reporting
   - Pattern: Complex calculations (similar to annuity)

6. **其他数据 (Other Data)**
   - Miscellaneous supplementary datasets
   - Pattern: Case-by-case assessment

**Growth Features:**

1. **Domain Migration Pipeline**
   - Create reusable migration checklist/template
   - Standardize golden dataset test creation
   - Document domain-specific patterns (enrichment, multi-sheet, calculations)

2. **Enhanced Orchestration**
   - Cross-domain dependency management (if domain B needs domain A output)
   - Smart scheduling (trigger dependent domains automatically)
   - Parallel execution of independent domains

3. **Improved Version Detection**
   - Machine learning-based "latest file" detection (if naming patterns vary)
   - Version conflict resolution (what if V1 and V2 both exist?)
   - Historical version tracking

4. **Operational Tooling**
   - CLI tools for common operations (re-run domain, validate parity, etc.)
   - Data quality dashboard (track validation failures across domains)
   - Reconciliation reports (new vs legacy output comparison)

**Growth Success Criteria:**
- ✅ All 6+ core domains migrated and validated
- ✅ Legacy `legacy/annuity_hub/` completely deleted
- ✅ Monthly data processing runs unattended across all domains
- ✅ <2% failure rate in production

---

### Vision (Future)
**"Beyond parity - intelligent automation"**

**Goal:** Transform WorkDataHub from a legacy replacement into an intelligent data platform that prevents issues before they occur and adapts to changing data sources.

**Vision Features:**

1. **Predictive Data Quality**
   - ML models that learn "normal" data patterns per domain
   - Anomaly detection: "This month's portfolio values are 30% higher than usual - likely data error"
   - Proactive alerts before bad data reaches database

2. **Self-Healing Pipelines**
   - Automatic retry with exponential backoff for transient failures
   - Smart fallback strategies (use previous month's mapping if new one is missing)
   - Auto-generate cleansing rules from repeated manual corrections

3. **Natural Language Configuration**
   - "Add validation: account numbers must be 10 digits"
   - AI-assisted cleansing rule creation from examples
   - Plain English domain documentation generation

4. **Intelligent Schema Evolution**
   - Detect when Excel source schema changes (new columns, renamed fields)
   - Suggest Pydantic model updates automatically
   - Migration scripts for historical data when schema evolves

5. **Advanced Analytics Integration**
   - Real-time data quality metrics exposed to PowerBI
   - Pipeline performance dashboards (processing time trends, bottlenecks)
   - Predictive load times ("Next month's data will take 45 minutes based on growth trends")

6. **Multi-Source Fusion**
   - Automatically join/enrich data from multiple sources (Excel + database + API)
   - Conflict resolution when same data appears in multiple sources
   - Master data management patterns

**Vision Success Criteria:**
- ✅ Data quality issues caught before human review 90% of the time
- ✅ Schema changes automatically detected and suggested (human approval still required)
- ✅ Zero manual intervention for 95% of monthly data drops

---

**Scope Philosophy - Strangler Fig Migration:**

This scope follows the **Strangler Fig pattern** (from Gemini research):

1. **MVP** = Strangle the hardest piece (annuity domain) to prove the pattern
2. **Growth** = Systematically strangle remaining domains one-by-one
3. **Vision** = New capabilities only possible with modern architecture

Each phase delivers value independently. No "big bang" rewrite risk.

---

## Data Platform Specific Requirements

### Architecture Pattern: Layered Data Pipeline (Bronze → Silver → Gold)

**Adopted from Gemini Research (docs/deep_research/1.md - Medallion Architecture)**

WorkDataHub implements a **three-tier data quality progression** that transforms raw Excel files into analysis-ready database tables:

**1. Bronze Layer (Raw/Immutable)**
- **Purpose:** Exact copy of source data as it arrived
- **Storage:** Original Excel files preserved in `reference/monthly/YYYYMM/收集数据/`
- **Benefit:** Can always re-run pipelines from raw data without re-querying sources
- **Example:** `业务收集/V2/年金数据.xlsx` → stored as-is, never modified

**2. Silver Layer (Cleansed/Validated)**
- **Purpose:** Data cleaned, validated, standardized, and enriched
- **Transformations Applied:**
  - Column name normalization (Chinese field names preserved)
  - Data type coercion (strings → dates, numbers)
  - Pydantic validation (row-level schema enforcement)
  - Pandera contracts (DataFrame-level schema enforcement)
  - Cleansing rules applied (registry-driven value standardization)
  - Enrichment (company ID resolution via lookup service)
- **Storage:** In-memory DataFrames (not persisted to disk)
- **Benefit:** Application-ready data with guaranteed quality

**3. Gold Layer (Business-Ready)**
- **Purpose:** Data aggregated/joined for specific business use cases
- **Outputs:** PostgreSQL database tables consumed by PowerBI
- **Transformations:**
  - Final column projection (only fields needed by BI tools)
  - Business calculations (KPIs, ratios, derived metrics)
  - Composite primary keys (月度 + 计划代码 + company_id)
- **Benefit:** PowerBI dashboards query optimized, pre-aggregated data

**Traceability:** Each layer builds on the previous, creating a clear lineage from Excel → Database.

---

### Migration Strategy: Strangler Fig Pattern

**Adopted from Gemini Research (docs/deep_research/2.md, 3.md - Strangler Fig Implementation)**

WorkDataHub follows the **Strangler Fig pattern** to safely replace legacy code without a risky "big bang" rewrite:

**Pattern Application:**

1. **Identify a "Seam"** (Target Domain)
   - Start with annuity_performance (highest complexity = litmus test)
   - Each domain is an independent "seam" that can be strangled

2. **Build New Pipeline** (Modern Implementation)
   - Create new pipeline using shared framework
   - Writes output to temporary location initially

3. **Run in Parallel** (Shadow Mode)
   - Legacy pipeline writes to: `db.annuity_performance` (production)
   - New pipeline writes to: `db.annuity_performance_NEW` (validation)
   - Both run on same input data

4. **Reconcile Outputs** (Validation)
   - Automated comparison: `pd.testing.assert_frame_equal(legacy_df, new_df)`
   - Golden dataset regression tests ensure 100% parity
   - Must pass for 3-5 consecutive monthly runs

5. **Cutover** (The "Strangling")
   - New pipeline now writes to production table
   - Legacy code no longer called

6. **Decommission** (Delete Legacy)
   - Delete old code from `legacy/annuity_hub/`
   - NOT commented out - fully removed

7. **Repeat** (Next Domain)
   - Pick next seam (e.g., 业务收集)
   - Apply same pattern

**Safety Benefits:**
- ✅ No "big bang" risk - each domain migrates independently
- ✅ Always have working rollback (switch back to legacy if issues found)
- ✅ Incremental value delivery (each domain completion is a win)
- ✅ Learn from each migration (patterns improve domain-by-domain)

---

### Code Organization: Clean Architecture

**Adopted from Gemini Research (docs/deep_research/1.md - Separation of Concerns)**

**Directory Structure:**
```
src/work_data_hub/
├── domain/              # BUSINESS LOGIC (core transformations)
│   ├── annuity_performance/
│   │   ├── models.py         # Pydantic In/Out models
│   │   ├── service.py        # Pure transformation functions
│   │   └── pipeline_steps.py # Pipeline step implementations
│   ├── pipelines/            # Shared pipeline framework
│   │   ├── core.py           # Pipeline execution engine
│   │   ├── builder.py        # Pipeline construction
│   │   └── types.py          # Common types
│
├── io/                  # INFRASTRUCTURE (I/O operations)
│   ├── readers/
│   │   └── excel_reader.py   # Excel file reading
│   ├── loader/
│   │   └── warehouse_loader.py # PostgreSQL loading
│   └── connectors/
│       └── file_connector.py # File system operations
│
├── orchestration/       # ORCHESTRATION (Dagster jobs)
│   ├── jobs.py          # Dagster job definitions
│   ├── ops.py           # Dagster operation implementations
│   ├── schedules.py     # Scheduled triggers
│   └── sensors.py       # Event-driven triggers
│
├── cleansing/           # CLEANSING (data quality rules)
│   ├── registry.py      # Central rule registry
│   └── rules/           # Specific cleansing rules
│
├── config/              # CONFIGURATION
│   ├── settings.py      # Application settings
│   ├── data_sources.yml # File discovery patterns
│   └── mappings/        # Domain-specific mappings
│
└── utils/               # SHARED UTILITIES
    ├── date_parser.py   # Chinese date parsing
    └── column_normalizer.py
```

**Dependency Rule (Critical):**
- **`domain/` imports from:** NOTHING (pure business logic, zero dependencies)
- **`io/` imports from:** `domain/` only (knows about models, not how to transform them)
- **`orchestration/` imports from:** `domain/` + `io/` (wires everything together)

**Benefit:** Business logic in `domain/` is 100% testable without database, files, or external services.

---

### Technology Stack Decisions

**Core Framework:**
- **Dagster** - Orchestration (jobs, schedules, sensors, UI)
  - Rationale: Modern alternative to Airflow, better developer experience
  - Usage: Manages monthly triggers, cross-domain dependencies, monitoring

- **Pandas** - Data manipulation
  - Rationale: Mature, widely used, team familiarity
  - Alternative considered: Polars (faster) - deferred to optimization phase
  - Usage: All DataFrame transformations

- **Pydantic v2** - Data validation (row-level)
  - Rationale: Type-safe models, excellent error messages, Python 3.10+ native
  - Usage: Validate individual rows during transformation

- **pandera** - Data validation (DataFrame-level)
  - Rationale: Complements Pydantic, enforces schema contracts at layer boundaries
  - Usage: Bronze/Silver/Gold layer validation (see Gemini research file 4)

- **PostgreSQL** - Target database
  - Rationale: Corporate standard, mature, reliable
  - Usage: Final data storage for PowerBI consumption

**Development Tools:**
- **mypy** - Static type checking (100% coverage required)
- **ruff** - Linting and formatting (replaces black + flake8 + isort)
- **pytest** - Unit and integration testing
- **pyarrow** - Parquet file support (for intermediate data storage if needed)

---

### Data Quality Requirements

**Validation Strategy: Multi-Layered Defense**

**1. Source Data Validation (Bronze Layer Entry)**
```python
# Using pandera contracts at Bronze boundary
@pa.check_schema(BronzeAnnuitySchema)
def load_raw_excel(file_path: str) -> pd.DataFrame:
    """Reject bad source data immediately"""
    df = pd.read_excel(file_path)
    return df  # If this returns, data passed schema contract
```

**Required Bronze Validations:**
- ✅ Expected columns present (月度, 计划代码, 客户名称, etc.)
- ✅ No completely null columns
- ✅ Date fields parseable (月度, 年, 月)
- ✅ Numeric fields are numeric (期初资产规模, 期末资产规模, etc.)
- ✅ Required fields not null (plan codes, dates)

**2. Transformation Validation (Silver Layer Processing)**
```python
# Using Pydantic models for row-level validation
class AnnuityPerformanceIn(BaseModel):
    """Input model with loose validation"""
    月度: Optional[Union[str, int, date]]
    计划代码: Optional[str]
    # ... more fields

class AnnuityPerformanceOut(BaseModel):
    """Output model with strict validation"""
    月度: date  # Must be valid date
    计划代码: str = Field(min_length=1)  # Must be non-empty
    company_id: str  # Must be resolved
    # ... more fields with strict constraints
```

**Required Silver Validations:**
- ✅ All rows pass Pydantic `AnnuityPerformanceOut` validation
- ✅ Business rules enforced (e.g., 期末资产规模 >= 0)
- ✅ Enrichment completed (company_id resolved or marked as unknown)
- ✅ No data loss (input row count = output row count, or explicit filtering logged)

**3. Output Validation (Gold Layer Database)**
```python
# Using pandera contracts before database write
@pa.check_schema(GoldAnnuitySchema)
def prepare_for_database(df: pd.DataFrame) -> pd.DataFrame:
    """Final validation before PostgreSQL"""
    # Ensure composite PK is unique
    assert not df.duplicated(subset=['月度', '计划代码', 'company_id']).any()
    return df
```

**Required Gold Validations:**
- ✅ Composite primary key uniqueness (月度 + 计划代码 + company_id)
- ✅ Column projection (only allowed DB columns present)
- ✅ No SQL injection risk (parameterized queries only)

**4. Regression Validation (Parity with Legacy)**
```python
# Golden dataset tests
def test_annuity_parity_golden_dataset():
    """Ensure new pipeline output = legacy output"""
    legacy_output = load_legacy_output("golden/annuity_202501.csv")
    new_output = run_new_pipeline("golden/annuity_202501_input.xlsx")

    pd.testing.assert_frame_equal(
        legacy_output.sort_values(['月度', '计划代码']),
        new_output.sort_values(['月度', '计划代码']),
        check_dtype=False  # Allow type differences if values match
    )
```

**Failure Handling:**
- **Bronze failure:** Stop immediately, log error with file path and row numbers
- **Silver failure:** Log validation errors, optionally export failed rows to CSV for review
- **Gold failure:** Rollback database transaction, preserve partial results for debugging
- **Regression failure:** Block production deployment until parity restored

---

### Version Detection System

**Challenge:** Monthly data arrives in folders with inconsistent naming:
```
reference/monthly/202501/收集数据/
├── 业务收集/
│   ├── V1/  # First submission
│   └── V2/  # Corrected submission (use this one!)
├── 数据采集/
│   └── V1/  # Only one version
```

**Requirements:**

1. **Automatic Latest Detection**
   - Scan for V1, V2, V3, ... folders
   - Select highest version number automatically
   - Fallback to non-versioned if no V folders exist

2. **Configurable Precedence Rules**
```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    version_strategy: "highest_number"  # V2 > V1
    fallback: "error"  # Fail if ambiguous

  business_collection:
    version_strategy: "highest_number"
    fallback: "use_latest_modified"  # Use newest file by timestamp
```

3. **Version Validation**
   - Warn if V1 and V2 both modified on same day (possible error)
   - Log which version was selected for audit trail
   - Support manual override via CLI flag: `--version=V1`

4. **Historical Tracking**
   - Record in database: which version was processed for each month
   - Enable reprocessing specific version if needed

---

### File Discovery and Processing

**Pattern Matching:**

WorkDataHub must intelligently discover Excel files across varying folder structures:

**Configuration-Driven Discovery:**
```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns:
      - "*年金*.xlsx"
      - "*规模明细*.xlsx"
    exclude_patterns:
      - "~$*"  # Ignore Excel temp files
      - "*回复*"  # Ignore email files
    sheet_name: "规模明细"
    version_aware: true
```

**Processing Logic:**
1. Resolve `{YYYYMM}` from current processing month
2. Check for V1, V2, ... subfolders (version detection)
3. Match files using glob patterns
4. Exclude unwanted files
5. Validate exactly 1 file found (error if 0 or multiple)
6. Load specified sheet name

**Error Cases:**
- ❌ No files match patterns → Error: "No annuity data found for 202501"
- ❌ Multiple files match → Error: "Ambiguous: found 2 files matching pattern"
- ❌ Sheet name missing → Error: "Sheet '规模明细' not found in file"

---

### Dependency Injection Pattern

**Adopted from Gemini Research (docs/deep_research/1.md - DI and Repository Pattern)**

**Goal:** Make `domain/` services testable without real files or databases.

**Current Pattern (Functional DI):**
```python
# domain/annuity_performance/service.py
def process_with_enrichment(
    rows: List[Dict[str, Any]],
    enrichment_service: Optional[CompanyEnrichmentService] = None,
    # ↑ Dependency injected as parameter
) -> ProcessingResultWithEnrichment:
    """Pure function - testable without real enrichment service"""
    # Transformation logic here
    if enrichment_service:
        result = enrichment_service.resolve_company_id(...)
```

**Testing:**
```python
# tests/domain/test_annuity_service.py
def test_process_without_enrichment():
    """Test with no dependencies - pure transformation"""
    result = process_with_enrichment(sample_rows)
    assert len(result.records) == 10

def test_process_with_mock_enrichment():
    """Test with fake enrichment service"""
    mock_service = FakeEnrichmentService(company_id="FAKE123")
    result = process_with_enrichment(sample_rows, mock_service)
    assert result.records[0].company_id == "FAKE123"
```

**Future Enhancement (Class-Based DI):**
```python
# For more complex domains, consider:
class AnnuityPipelineService:
    def __init__(
        self,
        reader: ExcelReader,  # Injected
        enrichment: CompanyEnrichmentService,  # Injected
        loader: WarehouseLoader  # Injected
    ):
        self.reader = reader
        self.enrichment = enrichment
        self.loader = loader
```

**Benefit:** Complete isolation of business logic from I/O, enabling fast unit tests.

---

## Functional Requirements

Organized by **capability** (not technology), with acceptance criteria that connect to user value.

---

### FR-1: Intelligent Data Ingestion
**"Automatically find and load the right data"**

**Capabilities:**

**FR-1.1: Version-Aware File Discovery**
- **Description:** System automatically detects latest data version (V1, V2, V3) across all domains without manual selection
- **User Value:** Eliminates "which file should I process?" decision every month
- **Acceptance Criteria:**
  - ✅ Scans `reference/monthly/{YYYYMM}/收集数据/` for all configured domains
  - ✅ Detects versioned folders (V1, V2, ...) and selects highest number automatically
  - ✅ Falls back to non-versioned files when no V folders exist
  - ✅ Logs selected version to audit trail with timestamp
  - ✅ Supports manual override via CLI: `--version=V1` for debugging
  - ✅ Errors clearly if multiple candidates found without precedence rule

**FR-1.2: Pattern-Based File Matching**
- **Description:** Uses configurable glob patterns to find Excel files despite naming variations
- **User Value:** Works with inconsistent file naming from different data sources
- **Acceptance Criteria:**
  - ✅ Configuration defines include patterns: `["*年金*.xlsx", "*规模明细*.xlsx"]`
  - ✅ Configuration defines exclude patterns: `["~$*", "*回复*"]` (temp files, emails)
  - ✅ Validates exactly 1 file matches after filtering (errors if 0 or multiple)
  - ✅ Errors include file paths of candidates for troubleshooting

**FR-1.3: Multi-Sheet Excel Reading**
- **Description:** Extracts specific sheets from multi-sheet Excel workbooks
- **User Value:** Handles complex source files without manual sheet extraction
- **Acceptance Criteria:**
  - ✅ Configuration specifies target sheet: `sheet_name: "规模明细"`
  - ✅ Handles both sheet name (string) and sheet index (integer) references
  - ✅ Errors clearly if sheet not found: "Sheet '规模明细' not found in file X"
  - ✅ Preserves Chinese characters in sheet names and column headers

**FR-1.4: Resilient Data Loading**
- **Description:** Gracefully handles common Excel data issues during load
- **User Value:** Prevents pipeline crashes from minor data format variations
- **Acceptance Criteria:**
  - ✅ Skips completely empty rows automatically
  - ✅ Coerces numeric strings to numbers where appropriate
  - ✅ Handles merged cells (uses first cell's value for entire range)
  - ✅ Normalizes column names (spaces, special characters) using `column_normalizer`
  - ✅ Logs warnings for data coercion (e.g., "Column '月度' coerced from string to date")

---

### FR-2: Multi-Layer Data Validation
**"Catch bad data before it contaminates the database"**

**Capabilities:**

**FR-2.1: Bronze Layer Validation (Source Data Quality)**
- **Description:** Validates raw Excel data immediately upon loading
- **User Value:** Fails fast when source data is corrupt, preventing wasted processing time
- **Acceptance Criteria:**
  - ✅ Pandera schema enforces expected columns present: `月度, 计划代码, 客户名称, ...`
  - ✅ Rejects completely null columns
  - ✅ Validates date fields are parseable (handles integer YYYYMM, Chinese dates, ISO dates)
  - ✅ Validates numeric fields contain numbers (期初资产规模, 期末资产规模, etc.)
  - ✅ Errors show: file path, row numbers, column names, and validation rule violated
  - ✅ Error messages are actionable: "Fix Excel file at path X, rows 15-20, column '月度' contains non-date values"

**FR-2.2: Silver Layer Validation (Transformation Quality)**
- **Description:** Validates each transformed row using Pydantic models
- **User Value:** Ensures business rules are enforced consistently
- **Acceptance Criteria:**
  - ✅ All rows pass `AnnuityPerformanceOut` (or equivalent domain model) validation
  - ✅ Business rules enforced: `期末资产规模 >= 0`, `计划代码` non-empty, dates in valid range
  - ✅ Enrichment status tracked: company_id resolved vs. marked unknown
  - ✅ Data loss is explicit: if rows filtered, log count + reason ("15 rows filtered: missing 计划代码")
  - ✅ Validation errors exported to CSV for review if >10 errors: `failed_rows_YYYYMMDD.csv`

**FR-2.3: Gold Layer Validation (Database Integrity)**
- **Description:** Final validation before PostgreSQL write
- **User Value:** Guarantees database integrity constraints never violated
- **Acceptance Criteria:**
  - ✅ Composite primary key uniqueness: `(月度, 计划代码, company_id)` no duplicates
  - ✅ Column projection: only allowed database columns present (prevent SQL errors)
  - ✅ SQL injection prevention: all queries use parameterized statements
  - ✅ Transactional writes: all-or-nothing (rollback on any error)
  - ✅ Pre-write validation using pandera `GoldAnnuitySchema` (or equivalent per domain)

**FR-2.4: Regression Validation (Legacy Parity)**
- **Description:** Automated comparison of new pipeline output vs. legacy output
- **User Value:** Proves new system is a safe replacement for legacy code
- **Acceptance Criteria:**
  - ✅ Golden dataset tests compare outputs row-by-row using `pd.testing.assert_frame_equal`
  - ✅ Tests pass for 3-5 consecutive monthly runs before production promotion
  - ✅ Differences reported with: row count, column names, specific values mismatched
  - ✅ Reconciliation mode: parallel execution writes to separate tables for comparison
  - ✅ Blocks deployment if parity breaks (CI/CD integration)

---

### FR-3: Configurable Data Transformation
**"Transform data using reusable, testable pipelines"**

**Capabilities:**

**FR-3.1: Pipeline Framework Execution**
- **Description:** Execute transformation steps in sequence using shared pipeline framework
- **User Value:** Consistent transformation pattern across all domains
- **Acceptance Criteria:**
  - ✅ Pipelines defined as list of `TransformStep` objects
  - ✅ Each step receives input row + context, returns transformed row + metadata
  - ✅ Steps execute in order, output of step N becomes input of step N+1
  - ✅ Immutability enforced: `current_row = {**row}` prevents accidental mutations
  - ✅ Error handling configured per pipeline: `stop_on_error=True` (fail fast) or `False` (collect errors)
  - ✅ Execution metrics collected: duration per step, total pipeline time, error counts

**FR-3.2: Registry-Driven Cleansing**
- **Description:** Apply value-level cleansing rules from central registry
- **User Value:** Standardize data transformations without duplicating code
- **Acceptance Criteria:**
  - ✅ Rules registered once in `cleansing/registry.py`, applied across domains
  - ✅ Example rules: trim whitespace, normalize company names, standardize dates
  - ✅ Pydantic adapter integration: rules applied automatically during model validation
  - ✅ Rules are composable: multiple rules can apply to same field
  - ✅ Configurable rule application: enable/disable rules per domain via config

**FR-3.3: Company Enrichment Integration**
- **Description:** Resolve company IDs using internal mappings and external lookup service (EQC platform API), with fallback to stable temporary IDs for unresolved companies. Uses Provider abstraction pattern for testability and legacy migration support.
- **User Value:** Augment data with enterprise identifiers for cross-domain joins, enabling consistent customer attribution across multiple data domains
- **Reference Documentation:** `reference/01_company_id_analysis.md` - comprehensive solution architecture with two implementation approaches (Complex CI-002 vs. Simplified S-001~S-004)
- **Acceptance Criteria:**
  - ✅ **Multi-tier resolution strategy:**
    - (1) Internal mapping tables: `plan_company_map`, `account_company_map`, `name_company_index`
    - (2) Synchronous EQC API lookup (budget-limited to prevent blocking)
    - (3) Async enrichment queue for deferred resolution
  - ✅ **Temporary ID generation:** Unresolved companies get stable `IN_<16-char-Base32>` IDs generated via `HMAC_SHA1(WDH_ALIAS_SALT, business_key)` - ensures same company always maps to same temporary ID
  - ✅ **Confidence scoring with human review thresholds:**
    - ≥0.90: Auto-accept and use company_id
    - 0.60-0.90: Accept but flag `needs_review=True`
    - <0.60: Keep temporary ID and queue for async resolution
  - ✅ **Provider abstraction:** `EnterpriseInfoProvider` protocol with multiple implementations:
    - `StubProvider`: Offline fixtures for testing/CI
    - `EqcProvider`: Real EQC platform API integration
    - `LegacyProvider`: Adapter for existing Mongo/MySQL crawler (optional)
  - ✅ **Gateway pattern:** `EnterpriseInfoGateway` handles normalization, evaluation, caching, and fallback logic
  - ✅ **Data persistence schema:**
    - `enterprise.company_master`: Canonical company records with official_name, unified_credit_code, aliases
    - `enterprise.company_name_index`: Normalized name → company_id mapping with match_type tracking
    - `enterprise.enrichment_requests`: Queue for async resolution with status tracking (pending/processing/done/failed)
  - ✅ **Sync lookup budget:** `WDH_ENRICH_SYNC_BUDGET` prevents runaway API calls (default: 0-5 per run)
  - ✅ **Unknown companies exported:** CSV with unresolved company names for manual review/backfill
  - ✅ **Enrichment observability:** Stats tracked per run:
    - Hit distribution: internal exact/fuzzy, external API, async queued, unknown
    - Sync budget consumption
    - Queue depth and processing success rate
    - Temporary ID generation count
  - ✅ **Graceful degradation:** Enrichment failures don't block main pipeline (optional service with feature flag `WDH_ENRICH_COMPANY_ID`)
  - ✅ **Security & credential management:**
    - EQC API token via `WDH_PROVIDER_EQC_TOKEN` (30-min validity)
    - Logs sanitized (no token leakage)
    - Optional Playwright automation for token capture (see `reference/01_company_id_analysis.md` §8)
  - ✅ **Legacy migration support:** Import existing mappings from Mongo/MySQL via `--job import_company_mappings` CLI command

**FR-3.4: Chinese Date Parsing**
- **Description:** Parse various Chinese date formats uniformly
- **User Value:** Handles inconsistent date formats from different Excel sources
- **Acceptance Criteria:**
  - ✅ Supports formats: `2025年1月`, `202501`, `2025-01`, `25年1月`, `date(2025, 1, 1)` objects
  - ✅ Uses `utils/date_parser.py` unified parsing logic
  - ✅ Handles 2-digit years: `25` → `2025` (assumes 20xx for <50, 19xx for >=50)
  - ✅ Validation: rejects dates outside reasonable range (2000-2030)
  - ✅ Clear errors: "Cannot parse '不是日期' as date in row 15, column '月度'"

---

### FR-4: Database Loading & Management
**"Reliably persist clean data to PostgreSQL"**

**Capabilities:**

**FR-4.1: Transactional Bulk Loading**
- **Description:** Load validated DataFrames to PostgreSQL with ACID guarantees
- **User Value:** No partial data corruption if pipeline fails mid-load
- **Acceptance Criteria:**
  - ✅ Uses `warehouse_loader.py` transactional interface
  - ✅ All-or-nothing writes: rollback entire batch if any row fails
  - ✅ Upsert support: `ON CONFLICT (月度, 计划代码, company_id) DO UPDATE`
  - ✅ Connection pooling: reuse connections across multiple loads
  - ✅ Parameterized queries only (no SQL injection risk)

**FR-4.2: Schema Projection**
- **Description:** Only write columns that exist in target database table
- **User Value:** Prevents "column not found" SQL errors when Excel has extra fields
- **Acceptance Criteria:**
  - ✅ `get_allowed_columns()` queries actual database schema
  - ✅ `project_columns()` filters DataFrame to allowed columns before write
  - ✅ Logs removed columns for troubleshooting: "Removed columns during projection: [extra_field_1, extra_field_2]"
  - ✅ Warnings if expected column missing: "Expected column '投资收益' not found in DataFrame"

**FR-4.3: Audit Logging**
- **Description:** Record every pipeline execution in database for traceability
- **User Value:** Answer questions like "which file was processed for January 2025?"
- **Acceptance Criteria:**
  - ✅ Logged per execution: timestamp, domain, input file path, version used, row counts (input/output/failed), duration
  - ✅ Error details captured: exception message, stack trace, failed row IDs
  - ✅ Queryable via SQL: "show me all annuity runs in last 6 months"
  - ✅ Retention policy: keep logs for 2 years

---

### FR-5: Orchestration & Automation
**"Schedule and coordinate pipeline execution"**

**Capabilities:**

**FR-5.1: Dagster Job Definitions**
- **Description:** Define pipelines as Dagster jobs for execution and monitoring
- **User Value:** Centralized control over all data processing
- **Acceptance Criteria:**
  - ✅ Each domain has corresponding Dagster job: `annuity_performance_job`, `business_collection_job`, etc.
  - ✅ Jobs composed of ops (operations): read → transform → validate → load
  - ✅ Op outputs are typed and validated (Dagster type system)
  - ✅ Dagster UI shows execution history, logs, and metrics

**FR-5.2: Monthly Schedule Triggers**
- **Description:** Automatically trigger pipelines on monthly cadence
- **User Value:** "Set and forget" automation - no manual monthly execution
- **Acceptance Criteria:**
  - ✅ Schedules defined in `orchestration/schedules.py`: `trustee_daily_schedule`, etc.
  - ✅ Cron expressions configurable: `0 2 5 * *` (5th of month, 2 AM)
  - ✅ Time zone aware (corporate timezone setting)
  - ✅ Manual trigger override available via Dagster UI

**FR-5.3: File Arrival Sensors**
- **Description:** Trigger pipelines when new data files detected
- **User Value:** Process data as soon as it arrives, not waiting for schedule
- **Acceptance Criteria:**
  - ✅ Sensors watch `reference/monthly/{YYYYMM}/收集数据/` for new files
  - ✅ Configurable polling interval: default 5 minutes
  - ✅ Debouncing: wait for file size to stabilize before triggering (prevent partial file processing)
  - ✅ Sensor state persisted: don't re-trigger for already-processed files

**FR-5.4: Cross-Domain Dependencies**
- **Description:** Coordinate execution order when domains depend on each other
- **User Value:** Domain B automatically waits for Domain A if needed
- **Acceptance Criteria:**
  - ✅ Dependency graph declared in job definitions: `job_B.depends_on(job_A)`
  - ✅ Dagster enforces execution order
  - ✅ Failed upstream job blocks downstream (prevent cascading failures)
  - ✅ Parallel execution of independent domains for speed

---

### FR-6: Migration Support (Strangler Fig)
**"Safely replace legacy code domain-by-domain"**

**Capabilities:**

**FR-6.1: Parallel Execution Mode**
- **Description:** Run new and legacy pipelines side-by-side on same input
- **User Value:** Validate new pipeline without risking production
- **Acceptance Criteria:**
  - ✅ Configuration flag: `parallel_mode=True` enables shadow execution
  - ✅ Legacy writes to: `db.annuity_performance` (production table)
  - ✅ New writes to: `db.annuity_performance_NEW` (validation table)
  - ✅ Both pipelines process identical input data
  - ✅ Execution times compared (performance regression detection)

**FR-6.2: Automated Reconciliation**
- **Description:** Compare new vs. legacy outputs and report differences
- **User Value:** Automated parity validation - no manual comparison needed
- **Acceptance Criteria:**
  - ✅ Reconciliation script compares tables row-by-row
  - ✅ Differences reported: row count mismatches, column value differences
  - ✅ Report includes: percentage match, specific mismatched rows, discrepancy details
  - ✅ Acceptable tolerance configurable: `tolerance=0.01` for float comparisons
  - ✅ Dashboard visualizes parity trends over time

**FR-6.3: Golden Dataset Test Suite**
- **Description:** Regression tests using frozen historical data
- **User Value:** Proves new pipeline produces identical output to legacy
- **Acceptance Criteria:**
  - ✅ Golden datasets stored: `tests/golden/annuity_202501_input.xlsx`, `tests/golden/annuity_202501_expected.csv`
  - ✅ Tests run in CI/CD: block merges if parity breaks
  - ✅ One golden dataset per domain (representative complexity)
  - ✅ Tests cover edge cases: missing data, special characters, date variations
  - ✅ Golden datasets updated only with explicit approval (manual review required)

**FR-6.4: Legacy Code Deletion**
- **Description:** Remove legacy code once new pipeline validated
- **User Value:** Simplified codebase - no maintaining two systems
- **Acceptance Criteria:**
  - ✅ Checklist before deletion: (1) 3-5 months parity passed, (2) production traffic cutover, (3) team sign-off
  - ✅ Legacy code fully deleted from `legacy/annuity_hub/` (not commented out)
  - ✅ Git tag created before deletion for emergency rollback: `legacy-annuity-final`
  - ✅ Documentation updated to remove legacy references

---

### FR-7: Configuration Management
**"Declare behavior via config, not code changes"**

**Capabilities:**

**FR-7.1: YAML-Based Domain Configuration**
- **Description:** All domain-specific settings in declarative YAML files
- **User Value:** Add/modify domains without code changes
- **Acceptance Criteria:**
  - ✅ File: `config/data_sources.yml` defines all domains
  - ✅ Per-domain config includes: file paths, patterns, sheet names, version strategy
  - ✅ Configuration validated on load: errors if required fields missing
  - ✅ Hot reload: config changes apply without restart (dev mode)

**FR-7.2: Mapping Files (JSON/YAML)**
- **Description:** Value mappings externalized from code
- **User Value:** Business users can update mappings without developer
- **Acceptance Criteria:**
  - ✅ Mappings stored in `config/mappings/`: `company_id_overrides.yml`, `business_type_codes.yml`, etc.
  - ✅ Format: `key: value` pairs or nested structures
  - ✅ Loaded once at startup, cached in memory
  - ✅ Validation: warn if mapping key not found during lookup

**FR-7.3: Environment-Specific Settings**
- **Description:** Different config for dev vs. production
- **User Value:** Test against sample data without touching production database
- **Acceptance Criteria:**
  - ✅ Settings loaded from: `.env` file, environment variables, or `config/settings.py`
  - ✅ Environment profiles: `development`, `staging`, `production`
  - ✅ Database connections, file paths, log levels configurable per environment
  - ✅ Secrets not committed to git (use environment variables or secret manager)

---

### FR-8: Monitoring & Observability
**"Understand what's happening and why"**

**Capabilities:**

**FR-8.1: Structured Logging**
- **Description:** Comprehensive, queryable logs for all pipeline operations
- **User Value:** Debug failures quickly - no guessing what went wrong
- **Acceptance Criteria:**
  - ✅ Logs include: timestamp, log level, domain, step, row count, duration, error details
  - ✅ JSON structured format for easy parsing: `{"timestamp": "...", "level": "ERROR", "domain": "annuity", ...}`
  - ✅ Log levels: DEBUG (development), INFO (production), WARNING (issues), ERROR (failures)
  - ✅ Logs persisted to files: `logs/worddatahub-YYYYMMDD.log` with daily rotation

**FR-8.2: Dagster UI Monitoring**
- **Description:** Visual dashboard for pipeline execution status
- **User Value:** At-a-glance view of what's running, what failed, what succeeded
- **Acceptance Criteria:**
  - ✅ Dagster UI accessible at `http://localhost:3000`
  - ✅ Shows: all jobs, run history, execution graphs, logs
  - ✅ Real-time updates during execution
  - ✅ Historical runs queryable by date, domain, status

**FR-8.3: Execution Metrics Collection**
- **Description:** Track performance and data quality metrics
- **User Value:** Identify bottlenecks and trends over time
- **Acceptance Criteria:**
  - ✅ Metrics tracked: execution duration, row counts (input/output/failed), validation error counts
  - ✅ Per-step timing: identify slowest transformation steps
  - ✅ Metrics stored in database: queryable for trend analysis
  - ✅ PowerBI dashboard: visualize metrics (optional growth feature)

**FR-8.4: Error Alerting**
- **Description:** Notify team when pipelines fail
- **User Value:** Know about failures immediately, not next day
- **Acceptance Criteria:**
  - ✅ Alert channels: email, Slack, or webhook (configurable)
  - ✅ Alert thresholds: fail after N retries, or critical domains only
  - ✅ Alert content: domain, error message, failure time, log link
  - ✅ Mute alerts during maintenance windows

---

**Requirements Summary:**
- **8 functional capability areas** covering entire data pipeline lifecycle
- **28 specific requirements** (FR-1.1 through FR-8.4)
- All requirements **connect to user value** (automation, reliability, maintainability)
- All requirements include **measurable acceptance criteria**

---

## Non-Functional Requirements

Focused on **performance, reliability, maintainability, and security** - the attributes critical for an internal data platform.

---

### NFR-1: Performance Requirements
**"Fast enough to complete within business hours"**

**NFR-1.1: Batch Processing Speed**
- **Requirement:** Process a complete monthly data drop (6+ domains, ~50,000 total rows) in <30 minutes
- **Rationale:** Allows processing to complete within work hours if issues require manual intervention
- **Measurement:**
  - Track end-to-end execution time per domain
  - Measure total time from first file read to last database commit
  - 95th percentile must be <30 minutes for full monthly run
- **Acceptance:**
  - ✅ Annuity domain (highest complexity, ~10K rows): <10 minutes
  - ✅ Simple domains (~2K rows): <3 minutes
  - ✅ All 6 domains in parallel: <30 minutes total

**NFR-1.2: Database Write Performance**
- **Requirement:** Bulk insert/upsert of 10,000 rows completes in <60 seconds
- **Rationale:** Database write shouldn't be bottleneck
- **Measurement:**
  - Time database operations separately from transformation
  - Use connection pooling and batch inserts (not row-by-row)
- **Acceptance:**
  - ✅ 10,000 row upsert: <60 seconds
  - ✅ Connection pooling enabled (max 5 connections)
  - ✅ Batch size optimized (test 500, 1000, 5000 row batches)

**NFR-1.3: Memory Efficiency**
- **Requirement:** Process any single domain within 4GB RAM
- **Rationale:** Runs on standard developer workstation or small server
- **Measurement:**
  - Monitor peak memory usage during execution
  - Use memory profiling tools (memory_profiler)
- **Acceptance:**
  - ✅ Peak memory <4GB for largest domain (annuity)
  - ✅ Memory released after each domain (no leaks)
  - ✅ Streaming processing for files >100MB (chunked reading)

**Performance Anti-Goals:**
- ❌ Real-time/streaming performance (monthly batch is sufficient)
- ❌ Horizontal scaling (single-machine execution is fine)
- ❌ Sub-second response times (batch processing acceptable)

---

### NFR-2: Reliability Requirements
**"Data integrity above all else"**

**NFR-2.1: Data Integrity Guarantees**
- **Requirement:** Zero data corruption - incorrect data never written to database
- **Rationale:** PowerBI dashboards drive business decisions; bad data = bad decisions
- **Measurement:**
  - Golden dataset regression tests must pass 100%
  - Validation failures must prevent database writes
  - Transactional rollback on any error
- **Acceptance:**
  - ✅ Multi-layer validation (Bronze/Silver/Gold) catches all schema violations
  - ✅ Database transactions ensure atomicity (all-or-nothing)
  - ✅ Parity tests detect any output changes vs. legacy within 0.01% tolerance
  - ✅ Zero production incidents with data corruption (measured quarterly)

**NFR-2.2: Fault Tolerance**
- **Requirement:** Pipeline failures are recoverable; system resumes from failure point
- **Rationale:** Monthly processing shouldn't restart from scratch if one domain fails
- **Measurement:**
  - Track partial completion states
  - Test recovery scenarios (database down, file missing, network error)
- **Acceptance:**
  - ✅ Domain isolation: failure in domain A doesn't affect domain B
  - ✅ Idempotent operations: re-running same input produces identical output
  - ✅ Clear error messages identify exact failure point (file, row, column)
  - ✅ Manual re-run possible for specific domain without re-processing all domains

**NFR-2.3: Operational Reliability**
- **Requirement:** <2% pipeline failure rate in production (measured monthly)
- **Rationale:** Automation value lost if pipelines frequently require manual fixes
- **Measurement:**
  - Track success/failure ratio per month
  - Classify failures: data quality issues vs. code bugs vs. infrastructure
- **Acceptance:**
  - ✅ >98% success rate for monthly production runs
  - ✅ All failures have root cause identified in logs
  - ✅ Retry logic for transient failures (database connection timeout, etc.)
  - ✅ Graceful degradation: optional services (enrichment) don't block core pipeline

**NFR-2.4: Data Loss Prevention**
- **Requirement:** Bronze layer data preserved indefinitely for re-processing
- **Rationale:** Source Excel files are immutable audit trail
- **Measurement:**
  - Verify Bronze files never modified or deleted
  - Test re-processing from historical Bronze data
- **Acceptance:**
  - ✅ Original Excel files retained in `reference/monthly/YYYYMM/收集数据/`
  - ✅ Re-running pipeline on month-old data produces identical results
  - ✅ Backup strategy: Bronze files backed up to separate location (weekly)

---

### NFR-3: Maintainability Requirements
**"Built for team handoff"**

**NFR-3.1: Code Quality Standards**
- **Requirement:** 100% type coverage with mypy; zero type errors
- **Rationale:** Type safety prevents bugs and improves IDE autocomplete for team
- **Measurement:**
  - Run `mypy src/` in CI/CD
  - Block merges if type errors exist
- **Acceptance:**
  - ✅ All public functions have type hints
  - ✅ `mypy --strict` passes with zero errors
  - ✅ Pydantic models enforce runtime type validation
  - ✅ CI/CD enforces type checking on every commit

**NFR-3.2: Test Coverage**
- **Requirement:** >80% test coverage for domain/ logic; 100% for critical paths
- **Rationale:** Refactoring confidence and regression prevention
- **Measurement:**
  - `pytest --cov=src/work_data_hub/domain`
  - Track coverage trends over time
- **Acceptance:**
  - ✅ Domain services (transformation logic): >90% coverage
  - ✅ Critical paths (validation, database writes): 100% coverage
  - ✅ Integration tests for each domain: end-to-end pipeline execution
  - ✅ Golden dataset regression tests for legacy parity

**NFR-3.3: Documentation Standards**
- **Requirement:** All domain services have docstrings; architecture documented
- **Rationale:** Team member onboarding and knowledge transfer
- **Measurement:**
  - Manual review of docstring presence
  - Architecture diagrams exist and are current
- **Acceptance:**
  - ✅ Every domain service function has docstring (Google style)
  - ✅ Pydantic models document field meanings (especially Chinese fields)
  - ✅ README.md explains: project structure, how to add domain, how to run pipelines
  - ✅ Architecture diagram shows: Bronze/Silver/Gold flow, dependency boundaries

**NFR-3.4: Code Review & CI/CD**
- **Requirement:** All changes require passing CI/CD checks before merge
- **Rationale:** Prevent regressions and maintain code quality
- **Measurement:**
  - CI/CD pipeline results
  - Time to merge (shouldn't block development)
- **Acceptance:**
  - ✅ CI runs: mypy (type check), ruff (lint/format), pytest (tests), parity tests
  - ✅ All checks must pass green before merge allowed
  - ✅ CI execution time: <5 minutes for fast feedback
  - ✅ Code review required for domain changes (single reviewer sufficient)

**NFR-3.5: Dependency Management**
- **Requirement:** Pin all dependency versions; reproducible builds
- **Rationale:** Avoid "works on my machine" issues during team handoff
- **Measurement:**
  - Check `pyproject.toml` for pinned versions
  - Test fresh install in clean environment
- **Acceptance:**
  - ✅ All dependencies pinned: `pandas==2.1.0` (not `pandas>=2.0`)
  - ✅ `requirements.txt` (or Poetry lock file) version-locked
  - ✅ Python version specified: `requires-python = ">=3.10"`
  - ✅ Fresh install + test passes on clean machine

---

### NFR-4: Security Requirements
**"Protect credentials and database access"**

**NFR-4.1: Credential Management**
- **Requirement:** No secrets committed to git; environment variables or secret manager
- **Rationale:** Prevent credential leaks if repository shared
- **Measurement:**
  - Manual code review for hardcoded secrets
  - Use tools like `git-secrets` or `trufflehog`
- **Acceptance:**
  - ✅ Database passwords in environment variables or `.env` (gitignored)
  - ✅ EQC API credentials in environment variables
  - ✅ `.env.example` template provided (without actual secrets)
  - ✅ Pre-commit hook prevents committing `.env` or credential files

**NFR-4.2: Database Access Control**
- **Requirement:** Database credentials grant minimum required privileges
- **Rationale:** Limit blast radius if credentials compromised
- **Measurement:**
  - Review database user permissions
  - Test with read-only user (should fail on writes)
- **Acceptance:**
  - ✅ Production database user: INSERT, UPDATE, SELECT on specific tables only (no DROP, CREATE)
  - ✅ Development database user: full permissions on dev database
  - ✅ Connection strings environment-specific (dev vs. prod databases different)
  - ✅ SSL/TLS enforced for database connections

**NFR-4.3: Input Validation (Security)**
- **Requirement:** All external inputs validated against injection attacks
- **Rationale:** Prevent SQL injection or malicious file paths
- **Measurement:**
  - Code review for SQL concatenation (should use parameterized queries)
  - Test with malicious inputs
- **Acceptance:**
  - ✅ All SQL queries use parameterized statements (no string concatenation)
  - ✅ File paths validated: no `../` traversal, must be within `reference/` directory
  - ✅ Excel data treated as untrusted: validated before processing
  - ✅ No `eval()` or `exec()` on user-provided data

**NFR-4.4: Audit Trail Security**
- **Requirement:** Pipeline execution logs are tamper-evident
- **Rationale:** Investigate issues or suspicious activity
- **Measurement:**
  - Log integrity checks (append-only, no modification)
  - Retention policy enforced
- **Acceptance:**
  - ✅ Logs written append-only (cannot be edited after creation)
  - ✅ Execution history in database includes: user, timestamp, input files
  - ✅ Log retention: 2 years minimum
  - ✅ Access controls: only authorized users can read production logs

**Security Anti-Goals:**
- ❌ Encryption at rest (database/filesystem already secured by IT)
- ❌ OAuth/SSO (internal tool, Windows authentication sufficient)
- ❌ Penetration testing (not external-facing)
- ❌ GDPR compliance (internal enterprise data, not personal consumer data)

---

### NFR-5: Usability Requirements (Developer/Operator)
**"Easy to operate and debug"**

**NFR-5.1: Clear Error Messages**
- **Requirement:** Every error includes actionable guidance
- **Rationale:** Reduce mean time to resolution (MTTR)
- **Measurement:**
  - Manual review of error message quality
  - Track time to resolve incidents
- **Acceptance:**
  - ✅ Errors specify: what failed, where (file/row/column), why, how to fix
  - ✅ Example: "Bronze validation failed: file 'annuity_202501.xlsx', row 15, column '月度' contains 'INVALID' - expected date format"
  - ✅ Validation errors link to docs/examples
  - ✅ No cryptic stack traces shown to end users (log full trace, show summary)

**NFR-5.2: Debuggability**
- **Requirement:** Failed pipeline state is inspectable for troubleshooting
- **Rationale:** Fix issues quickly without guessing
- **Measurement:**
  - Test debugging scenarios (inspect failed rows, replay specific step)
  - Developer feedback on debug experience
- **Acceptance:**
  - ✅ Failed rows exported to CSV with original values + error reasons
  - ✅ Dagster UI shows: execution graph, step-by-step logs, duration per step
  - ✅ Replay capability: re-run specific domain without re-processing all
  - ✅ Dry-run mode: validate without database writes

**NFR-5.3: Operational Simplicity**
- **Requirement:** Common operations require single command
- **Rationale:** Reduce operator burden and training time
- **Measurement:**
  - Task analysis: how many steps for common operations?
  - Operator feedback on ease of use
- **Acceptance:**
  - ✅ Process monthly data: `dagster job launch annuity_performance_job --config month=202501`
  - ✅ View pipeline status: Dagster UI dashboard
  - ✅ Re-run failed domain: Single button click in Dagster UI
  - ✅ No manual SQL scripts required for normal operations

---

**Non-Functional Requirements Summary:**

| Category | Key Metrics | Critical Requirements |
|----------|-------------|----------------------|
| **Performance** | <30 min full monthly run, <10 min per domain, <4GB RAM | Batch processing speed sufficient for business hours |
| **Reliability** | >98% success rate, 0% data corruption, 100% parity | Data integrity guaranteed through multi-layer validation |
| **Maintainability** | 100% type coverage, >80% test coverage, docs complete | Team-ready for handoff with clear architecture |
| **Security** | No secrets in git, parameterized queries, audit logs | Credentials protected, SQL injection prevented |
| **Usability** | Actionable errors, single-command ops, inspectable failures | Easy to debug and operate |

**Total NFRs:** 17 specific requirements across 5 categories

---

## Implementation Planning

### Epic Breakdown Required

Requirements must be decomposed into epics and bite-sized stories (200k context limit).

**Next Step:** Run `/bmad:bmm:workflows:create-epics-and-stories` to create the implementation breakdown.

---

## References

**Research Documents:**
- `docs/deep_research/1.md` - Modern Data Processing Architectures (Gemini Deep Research, 37 pages)
- `docs/deep_research/2.md` - Refactoring Strategy Comparison Matrix (Strangler Fig vs Branch by Abstraction vs Big Bang)
- `docs/deep_research/3.md` - Strangler Fig Implementation Guide with Python Examples
- `docs/deep_research/4.md` - Data Contracts with Pandera (DataFrame Validation Best Practices)
- `docs/research-deep-prompt-2025-11-08.md` - Original Research Prompt for AI Platforms

**Archive Documents:**
- `docs/archive/prd.md` - Previous Annuity Performance Pipeline Migration PRD
- `docs/archive/architecture.md` - Brownfield Enhancement Architecture

**Existing Codebase:**
- `src/work_data_hub/` - Partially refactored with Dagster + Pydantic + Pipeline framework
- `legacy/annuity_hub/` - Original monolithic implementation (to be replaced)

**Data Domains:**
- `reference/monthly/202501/收集数据/` - Example monthly data structure with 6+ domains

---

## Next Steps

### Immediate Next Steps

1. **✅ PRD Complete** - This document captures comprehensive requirements for WorkDataHub refactoring

2. **Epic & Story Breakdown** (Required)
   - Run: `/bmad:bmm:workflows:create-epics-and-stories`
   - Purpose: Decompose requirements into implementable bite-sized stories
   - Output: Epic files in `docs/epics/` with detailed user stories

3. **Architecture Document** (Recommended)
   - Run: `/bmad:bmm:workflows:architecture`
   - Purpose: Define technical architecture decisions and patterns
   - Output: Architecture document with technology choices, patterns, ADRs

4. **Solutioning Gate Check** (Required before implementation)
   - Run: `/bmad:bmm:workflows:solutioning-gate-check`
   - Purpose: Validate all planning complete before coding begins
   - Ensures: PRD ↔ Architecture ↔ Stories are aligned

### Recommended Implementation Sequence

Following the **Strangler Fig pattern** from Gemini research:

**Phase 1: MVP (Prove the Pattern)**
- Epic 1: Complete annuity_performance domain migration
- Epic 2: Golden dataset regression test suite
- Epic 3: Version detection system
- Epic 4: Pandera data contracts (Bronze/Silver/Gold)

**Phase 2: Growth (Complete Migration)**
- Epic 5-10: Migrate remaining 5+ domains (业务收集, 数据采集, etc.)
- Epic 11: Enhanced orchestration (cross-domain dependencies)
- Epic 12: Operational tooling (CLI, monitoring dashboards)

**Phase 3: Vision (Intelligent Platform)**
- Epic 13: Predictive data quality (ML anomaly detection)
- Epic 14: Self-healing pipelines
- Epic 15: Schema evolution automation

---

## PRD Summary

**WorkDataHub** systematically refactors a legacy monolithic ETL system into a modern, maintainable data platform using:

**Core Innovation:**
1. **Intelligent Automation** - Auto-detect file versions, hands-free monthly processing
2. **Fearless Extensibility** - Add domains in <4 hours using proven patterns
3. **Team-Ready Maintainability** - 100% type-safe, comprehensive validation, clear architecture

**Technical Foundation:**
- **Bronze → Silver → Gold** layered architecture (Medallion pattern)
- **Strangler Fig** migration (domain-by-domain replacement)
- **Pydantic + pandera** multi-layer validation (row + DataFrame contracts)
- **Dagster** orchestration with jobs, schedules, sensors
- **Clean Architecture** with strict dependency boundaries

**Success Metrics:**
- <30 min full monthly processing (6+ domains, 50K rows)
- >98% pipeline success rate
- 100% legacy parity validated
- <4 hours to add new domain

**Scope:**
- **MVP:** Annuity domain migration with golden dataset tests
- **Growth:** All 6+ domains migrated, legacy deleted
- **Vision:** Predictive quality, self-healing, schema evolution

**Requirements:**
- **28 Functional Requirements** across 8 capability areas
- **17 Non-Functional Requirements** (performance, reliability, maintainability, security, usability)

**The Magic:**
When monthly data arrives, WorkDataHub automatically finds the latest versions across all domains, validates them through Bronze/Silver/Gold layers, and delivers clean data to PowerBI - while you focus on analysis instead of wrestling with Excel and SQL scripts.

---

_This PRD captures the essence of WorkDataHub: transforming manual, error-prone data processing into an effortless, reliable, automated system that the team can confidently maintain and extend._

_Created through collaborative discovery between Link and AI Product Manager (Mary), 2025-11-08._
