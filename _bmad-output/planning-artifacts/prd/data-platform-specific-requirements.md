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
