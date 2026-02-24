# Data Platform Specific Requirements

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

**Directory Structure (Actual):**
```
src/work_data_hub/
├── cli/                 # CLI ENTRY POINTS (argparse-based)
│   ├── __main__.py           # Subcommand router
│   ├── etl/                  # ETL job execution (--domains, --period, --execute)
│   ├── auth.py               # Authentication token management
│   ├── eqc_refresh.py        # EQC data refresh from API
│   ├── cleanse_data.py       # Data cleansing operations
│   └── customer_mdm/         # Customer MDM sub-commands (sync, snapshot, init-year, validate, cutover)
│
├── config/              # CONFIGURATION LOADING
│   ├── settings.py           # Application settings (pydantic-settings)
│   └── mapping_loader.py     # YAML mapping file loader
│
├── customer_mdm/        # CUSTOMER MASTER DATA MANAGEMENT
│   # Lifecycle management: sync, snapshot, init-year, validate, cutover
│
├── domain/              # BUSINESS LOGIC (core transformations)
│   ├── annuity_performance/  # MVP domain (adapter, constants, helpers, models, pipeline_builder, schemas, service)
│   ├── annuity_income/       # Annuity income domain (same pattern)
│   ├── annual_award/         # Annual award domain (same pattern)
│   ├── annual_loss/          # Annual loss domain (same pattern)
│   ├── company_enrichment/   # Company ID resolution (lookup_queue, models, observability, service)
│   ├── reference_backfill/   # Reference data backfill (config_loader, generic/hybrid/sync_service)
│   ├── sandbox_trustee_performance/  # Dev/test sandbox domain
│   └── pipelines/            # Shared pipeline framework (core, builder, adapters, steps, exceptions, config)
│
├── gui/                 # DESKTOP GUI
│   ├── eqc_query/            # Tkinter GUI for EQC lookups
│   └── eqc_query_fluent/     # PyQt6 Fluent-style GUI
│
├── infrastructure/      # SHARED INFRASTRUCTURE (replaces old cleansing/)
│   ├── cleansing/            # Rule engine, registry, normalizers, rules, validators, biz_label_parser
│   ├── enrichment/           # Company ID resolver, EQC provider, multi-strategy resolver, repository
│   ├── schema/               # Core DDL generator, domain registry, definitions per domain
│   ├── sql/                  # SQL core (identifier, parameters), dialects (postgresql), operations
│   ├── transforms/           # Base, cleansing_step, projection_step, standard_steps
│   ├── validation/           # Domain validators, error handler, failure exporter, report generator
│   ├── settings/             # Customer status schema, data source schema, loader
│   ├── helpers/              # Shared infrastructure helpers
│   ├── mappings/             # Infrastructure-level mappings
│   └── models/               # Infrastructure-level models
│
├── io/                  # I/O LAYER
│   ├── readers/              # Excel file reading
│   ├── loaders/              # PostgreSQL loading (warehouse_loader)
│   ├── connectors/           # File system operations
│   ├── auth/                 # Authentication (EQC token via Playwright)
│   └── schema/               # Alembic migrations (13 active versions)
│
├── orchestration/       # ORCHESTRATION (Dagster)
│   ├── jobs.py               # Dagster job definitions
│   ├── ops.py                # Dagster operation implementations
│   ├── schedules.py          # Scheduled triggers
│   └── sensors.py            # Event-driven triggers
│
└── utils/               # SHARED UTILITIES
    ├── date_parser.py        # Chinese date parsing
    ├── column_normalizer.py  # Column name normalization
    ├── logging.py            # Structured logging (structlog)
    └── types.py              # Shared type definitions
```

**Dependency Rule (Critical):**
- **`domain/` imports from:** NOTHING (pure business logic, zero dependencies)
- **`infrastructure/` imports from:** `domain/` only (shared infra: cleansing, enrichment, schema, sql, transforms, validation)
- **`io/` imports from:** `domain/` + `infrastructure/` (knows about models and infra, handles I/O)
- **`orchestration/` imports from:** `domain/` + `infrastructure/` + `io/` (wires everything together)
- **`cli/` imports from:** All layers (entry point, wires user commands to orchestration)
- **`customer_mdm/` imports from:** `domain/` + `infrastructure/` + `io/` (independent MDM module)

**Benefit:** Business logic in `domain/` is 100% testable without database, files, or external services.

---

### Technology Stack Decisions

**Core Framework:**
- **Dagster** - Orchestration (jobs, schedules, sensors, UI)
  - Rationale: Modern alternative to Airflow, better developer experience
  - Usage: Manages monthly triggers, cross-domain dependencies, monitoring

- **Pandas** - Data manipulation
  - Rationale: Mature, widely used, team familiarity
  - Usage: All DataFrame transformations

- **Pydantic v2** (>=2.11.7) - Data validation (row-level) + settings management
  - Rationale: Type-safe models, excellent error messages, Python 3.10+ native
  - Usage: Validate individual rows during transformation; `pydantic-settings` for config

- **pandera** (>=0.18.0) - Data validation (DataFrame-level)
  - Rationale: Complements Pydantic, enforces schema contracts at layer boundaries
  - Usage: Bronze/Silver/Gold layer validation

- **SQLAlchemy** (>=2.0) + **Alembic** - ORM and database migrations
  - Rationale: Industry standard ORM, Alembic provides versioned schema migrations
  - Usage: Schema definitions, DDL generation, 13 active migration versions

- **PostgreSQL** + **psycopg2** - Target database
  - Rationale: Corporate standard, mature, reliable
  - Usage: Final data storage for PowerBI consumption

- **structlog** - Structured logging
  - Rationale: JSON-structured logs for easy parsing and debugging
  - Usage: All application logging

**Integration & Automation:**
- **Playwright** + **playwright-stealth** - Browser automation
  - Usage: EQC platform token acquisition, intranet authentication
- **OpenCV** (`opencv-python-headless`) + **NumPy** - Image processing
  - Usage: Slider CAPTCHA solving for EQC authentication
- **gmssl** - Chinese national cryptography (SM2/SM3/SM4)
  - Usage: EQC API encryption requirements
- **dukpy** - JavaScript execution engine
  - Usage: EQC platform encryption logic execution
- **sqlglot** - SQL parsing and transpilation
  - Usage: SQL dialect handling and query generation

**GUI:**
- **PyQt6** + **pyqt6-fluent-widgets** - Desktop GUI (optional)
  - Usage: Fluent-style EQC query interface
- **Tkinter** - Lightweight GUI (built-in)
  - Usage: Simple EQC query tool

**Development Tools:**
- **mypy** (>=1.17.1) - Static type checking (100% coverage required)
- **ruff** (>=0.12.12) - Linting and formatting (replaces black + flake8 + isort)
- **pytest** + **pytest-cov** + **pytest-asyncio** - Testing framework
- **pre-commit** - Git hooks for code quality
- **pyarrow** (>=21.0.0) - Columnar data support
- **uv** - Ultra-fast package and virtual environment management (replaces pip/poetry)

**Package Management:**
- **uv** + `pyproject.toml` - All execution via `PYTHONPATH=src uv run`
- Python version: `>=3.10`

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
