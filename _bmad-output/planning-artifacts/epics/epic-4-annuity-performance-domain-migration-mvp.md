# Epic 4: Annuity Performance Domain Migration (MVP)

**Goal:** Complete the first domain migration using the Strangler Fig pattern, proving that the modern architecture can successfully replace legacy code with 100% output parity. This epic validates the entire platform on the highest-complexity domain, establishing patterns that all future domain migrations will follow.

**Business Value:** Annuity performance is the most complex domain with enrichment, multi-sheet processing, and intricate transformations. Successfully migrating it proves the architecture works and provides a reference implementation for the 5+ remaining domains. Establishes foundation for complete legacy system retirement.

**Dependencies:** Epic 1 (infrastructure), Epic 2 (validation), Epic 3 (file discovery)

**Strangler Fig Approach:** Build new pipeline → Run parallel with legacy → Validate 100% parity → Cutover → Delete legacy code

---

### Story 4.1: Annuity Domain Data Models (Pydantic)

As a **data engineer**,
I want **Pydantic models for annuity performance with Chinese field names matching Excel sources**,
So that **row-level validation enforces business rules and data flows through Bronze → Silver → Gold with type safety**.

**Acceptance Criteria:**

**Given** I have annuity Excel data with columns: `月度, 计划代码, 客户名称, 期初资产规模, 期末资产规模, 投资收益, 年化收益率`
**When** I create Pydantic models for Input and Output
**Then** I should have:
- `AnnuityPerformanceIn` (loose validation for messy Excel input):
  - `月度: Optional[Union[str, int, date]]` (handles various date formats)
  - `计划代码: Optional[str]` (can be missing initially)
  - `客户名称: Optional[str]` (enrichment source)
  - Numeric fields: `Optional[float]` (handles nulls)
- `AnnuityPerformanceOut` (strict validation for clean output):
  - `月度: date` (required, parsed)
  - `计划代码: str` (required, non-empty)
  - `company_id: str` (required, enriched - or temporary ID)
  - `期末资产规模: float = Field(ge=0)` (non-negative)
  - All business rules enforced

**And** When validating input row with `月度="202501"` and `期末资产规模="1,234,567.89"`
**Then** `AnnuityPerformanceIn` accepts the values (loose validation)

**And** When converting to output model
**Then** `AnnuityPerformanceOut` validates:
- Date parsed: `"202501"` → `date(2025, 1, 1)`
- Number cleaned: `"1,234,567.89"` → `1234567.89`
- All required fields present
- Business rules satisfied

**And** When output validation fails (e.g., missing `company_id`)
**Then** Raise `ValidationError` with field name and requirement

**Prerequisites:** Epic 2 Story 2.1 (Pydantic validation framework), Story 2.4 (Chinese date parsing)

**Technical Notes:**
- Implement in `domain/annuity_performance/models.py`
- Use Epic 2 Story 2.4 date parser in `@field_validator('月度')`
- Use Epic 2 Story 2.3 cleansing registry for company name normalization
- Field descriptions document Chinese field meanings:
  ```python
  class AnnuityPerformanceOut(BaseModel):
      月度: date = Field(..., description="Reporting month (月度)")
      计划代码: str = Field(..., min_length=1, description="Plan code (计划代码)")
      company_id: str = Field(..., description="Enterprise company ID or temporary IN_* ID")
      # ... more fields
  ```
- Separate models enable progressive validation (Epic 2 pattern)
- Reference: PRD §581-624 (FR-2.1: Pydantic Row-Level Validation)

---

### Story 4.2: Annuity Bronze Layer Validation Schema

As a **data engineer**,
I want **pandera DataFrame schema validating raw Excel data immediately after load**,
So that **corrupted source data is rejected before any processing with clear actionable errors**.

**Acceptance Criteria:**

**Given** I load raw annuity Excel DataFrame from Epic 3 file discovery
**When** I apply `BronzeAnnuitySchema` validation
**Then** Schema should verify:
- Expected columns present: `['月度', '计划代码', '客户名称', '期初资产规模', '期末资产规模', '投资收益', '年化收益率']`
- No completely null columns (indicates corrupted Excel)
- Numeric columns coercible to float: `期初资产规模, 期末资产规模, 投资收益, 年化收益率`
- Date column parseable (coerce with custom parser from Epic 2 Story 2.4)
- At least 1 data row (not just headers)

**And** When Excel has all expected columns and valid data types
**Then** Validation passes, DataFrame returned for Silver layer processing

**And** When Excel missing required column `期末资产规模`
**Then** Raise `SchemaError`: "Bronze validation failed: Missing required column '期末资产规模', found columns: [列出实际列名]"

**And** When column `月度` has non-date values in multiple rows
**Then** Raise `SchemaError` with row numbers: "Bronze validation failed: Column '月度' rows [15, 23, 45] cannot be parsed as dates"

**And** When >10% of numeric column values are non-numeric
**Then** Raise `SchemaError`: "Bronze validation failed: Column '期末资产规模' has 15% invalid values (likely systemic data issue)"

**Prerequisites:** Epic 2 Story 2.2 (pandera schemas), Epic 3 Story 3.5 (file discovery provides DataFrame)

**Technical Notes:**
- Implement in `domain/annuity_performance/schemas.py`
- Use pandera `DataFrameSchema` with coercion:
  ```python
  import pandera as pa
  from utils.date_parser import parse_yyyymm_or_chinese

  BronzeAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, coerce=True, nullable=True),
      "计划代码": pa.Column(pa.String, nullable=True),
      "客户名称": pa.Column(pa.String, nullable=True),
      "期初资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
      "期末资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
      "投资收益": pa.Column(pa.Float, coerce=True, nullable=True),
      "年化收益率": pa.Column(pa.Float, coerce=True, nullable=True),
  }, strict=False, coerce=True)  # Allow extra columns, coerce types
  ```
- Custom coercion for Chinese dates using Epic 2 Story 2.4 parser
- Error threshold: fail if >10% of rows invalid (indicates systemic issue)
- Reference: PRD §756-765 (FR-2.1: Bronze Layer Validation)

---

### Story 4.3: Annuity Transformation Pipeline (Bronze → Silver)

As a **data engineer**,
I want **transformation pipeline steps converting raw Excel to validated business data**,
So that **annuity data flows through cleansing, enrichment, and validation to produce Silver layer output**.

**Acceptance Criteria:**

**Given** I have Bronze-validated DataFrame from Story 4.2
**When** I execute annuity transformation pipeline
**Then** Pipeline should apply steps in order:
1. **Parse dates:** Convert `月度` to `date` objects using Epic 2 Story 2.4 parser
2. **Cleanse company names:** Apply Epic 2 Story 2.3 registry rules (trim, normalize)
3. **Validate rows:** Convert each row to `AnnuityPerformanceIn` (Story 4.1)
4. **Enrich company IDs:** Resolve `客户名称` → `company_id` (Epic 5 integration point - mock for now)
5. **Calculate derived fields:** Add any computed metrics
6. **Validate output:** Convert to `AnnuityPerformanceOut` (strict validation)
7. **Filter invalid rows:** Export failures to CSV (Epic 2 Story 2.5)

**And** When pipeline processes 1000 rows with 950 valid
**Then** Returns DataFrame with 950 rows, exports 50 failed rows to CSV with error reasons

**And** When enrichment service unavailable (Epic 5 not implemented yet)
**Then** Pipeline uses fallback: `company_id = "UNKNOWN_" + normalize(客户名称)` (temporary)

**And** When row fails Pydantic output validation
**Then** Row excluded from output, logged to failed rows CSV with specific validation error

**And** When all rows pass validation
**Then** Returns Silver DataFrame ready for Gold layer projection

**Prerequisites:** Stories 4.1-4.2 (models and Bronze validation), Epic 1 Story 1.5 (pipeline framework), Epic 2 Stories 2.1-2.5 (validation and cleansing)

**Technical Notes:**
- Implement in `domain/annuity_performance/pipeline_steps.py` using Epic 1 Story 1.5 pipeline framework
- Each transformation step implements `TransformStep` protocol
- Company enrichment integration point: inject `EnrichmentService` via dependency injection (Epic 1 Story 1.6 pattern)
- For MVP: use stub enrichment service that returns temporary IDs
- Error handling: collect validation errors per Epic 2 Story 2.5 pattern
- Pipeline config: `stop_on_error=False` (collect all errors), threshold=10% (Epic 2 Story 2.5)
- Example pipeline construction:
  ```python
  from domain.pipelines.core import Pipeline, PipelineContext

  annuity_pipeline = Pipeline("annuity_performance")
  annuity_pipeline.add_step(ParseDatesStep())
  annuity_pipeline.add_step(CleanseCompanyNamesStep(cleansing_registry))
  annuity_pipeline.add_step(ValidateInputRowsStep(AnnuityPerformanceIn))
  annuity_pipeline.add_step(EnrichCompanyIDsStep(enrichment_service))  # Stub for MVP
  annuity_pipeline.add_step(ValidateOutputRowsStep(AnnuityPerformanceOut))
  ```
- Reference: PRD §799-871 (FR-3: Configurable Data Transformation)

---

### Story 4.4: Annuity Gold Layer Projection and Schema

As a **data engineer**,
I want **Gold layer validation ensuring database-ready data meets all integrity constraints**,
So that **only clean, projection-filtered data with unique composite keys reaches PostgreSQL**.

**Acceptance Criteria:**

**Given** I have Silver DataFrame from Story 4.3 transformation pipeline
**When** I apply Gold layer projection and validation
**Then** System should:
- Project to database columns only (remove intermediate calculation fields)
- Validate composite PK uniqueness: `(月度, 计划代码, company_id)` has no duplicates
- Enforce not-null constraints on required fields
- Apply `GoldAnnuitySchema` pandera validation
- Prepare for Story 4.5 database loading

**And** When Silver DataFrame has 1000 rows with unique composite keys
**Then** Gold validation passes, returns 1000 rows ready for database

**And** When composite PK has duplicates (2 rows with same `月度, 计划代码, company_id`)
**Then** Raise `SchemaError`: "Gold validation failed: Composite PK (月度, 计划代码, company_id) has 2 duplicate combinations: [(2025-01-01, 'ABC123', 'COMP001'), ...]"

**And** When required field is null in Silver output
**Then** Raise `SchemaError`: "Gold validation failed: Required field 'company_id' is null in 5 rows"

**And** When DataFrame has extra columns not in database schema
**Then** Gold projection removes extra columns, logs: "Gold projection: removed columns ['intermediate_calc_1', 'temp_field_2']"

**Prerequisites:** Story 4.3 (Silver transformation), Epic 2 Story 2.2 (pandera schemas), Epic 1 Story 1.8 (database loader has schema projection)

**Technical Notes:**
- Implement in `domain/annuity_performance/schemas.py` as `GoldAnnuitySchema`
- Use pandera with strict validation:
  ```python
  GoldAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, nullable=False),
      "计划代码": pa.Column(pa.String, nullable=False),
      "company_id": pa.Column(pa.String, nullable=False),
      "期初资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
      "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
      "投资收益": pa.Column(pa.Float, nullable=False),
      "年化收益率": pa.Column(pa.Float, nullable=True),  # Can be null if 期末资产规模=0
  }, strict=True, unique=['月度', '计划代码', 'company_id'])
  ```
- Column projection: use Epic 1 Story 1.8 `WarehouseLoader.get_allowed_columns()` and `.project_columns()`
- Composite PK uniqueness critical for database integrity
- Reference: PRD §777-785 (FR-2.3: Gold Layer Validation)

---

### Story 4.5: Annuity End-to-End Pipeline Integration

As a **data engineer**,
I want **complete Bronze → Silver → Gold pipeline with database loading for annuity domain**,
So that **I can process monthly annuity data from Excel to PostgreSQL in a single execution**.

**Acceptance Criteria:**

**Given** I have all components from Stories 4.1-4.4 implemented
**When** I execute end-to-end annuity pipeline for month 202501
**Then** Pipeline should:
1. Discover file using Epic 3 Story 3.5 `FileDiscoveryService`
2. Validate Bronze using Story 4.2 `BronzeAnnuitySchema`
3. Transform using Story 4.3 pipeline (Bronze → Silver)
4. Validate Gold using Story 4.4 `GoldAnnuitySchema`
5. Load to database using Epic 1 Story 1.8 `WarehouseLoader`
6. Log execution metrics (duration, row counts, errors)

**And** When processing succeeds for 1000 input rows with 950 valid
**Then** Database should contain:
- 950 rows inserted into `annuity_performance_NEW` table (shadow mode)
- Composite PK constraint satisfied
- Audit log entry with: file_path, version, row counts, duration

**And** When any stage fails (file discovery, validation, transformation, database)
**Then** Pipeline fails fast with structured error showing failed stage (Epic 3 Story 3.5 error pattern)

**And** When I run pipeline twice with same input
**Then** Second run produces identical database state (idempotent upsert)

**And** When I execute via Dagster job
**Then** Dagster UI shows: execution graph, step-by-step logs, success/failure status

**Prerequisites:** Stories 4.1-4.4 (all annuity components), Epic 1 Story 1.9 (Dagster), Epic 1 Story 1.8 (database loader), Epic 3 Story 3.5 (file discovery)

**Technical Notes:**
- Implement in `domain/annuity_performance/service.py` as main orchestration function
- Create Dagster job in `orchestration/jobs.py`:
  ```python
  from domain.annuity_performance.service import process_annuity_performance

  @job
  def annuity_performance_job(context):
      month = context.op_config.get("month", "202501")
      result = process_annuity_performance(month)
      context.log.info(f"Processed {result.rows_loaded} rows in {result.duration_ms}ms")
  ```
- Write to `annuity_performance_NEW` table (shadow mode for Epic 6 parallel execution)
- Idempotent upsert: `ON CONFLICT (月度, 计划代码, company_id) DO UPDATE`
- Integration test: full pipeline with fixture Excel file
- Metrics logged via Epic 1 Story 1.3 structured logging
- Reference: PRD §879-906 (FR-4: Database Loading), §909-918 (FR-5.1: Dagster Jobs)

---

### Story 4.6: Annuity Domain Configuration and Documentation

As a **data engineer**,
I want **complete configuration and documentation for the annuity domain**,
So that **the domain is reproducible, maintainable, and serves as reference for future domain migrations**.

**Acceptance Criteria:**

**Given** I have working annuity pipeline from Story 4.5
**When** I finalize configuration and documentation
**Then** I should have:
- Domain config in `config/data_sources.yml`:
  ```yaml
  domains:
    annuity_performance:
      base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
      file_patterns: ["*年金*.xlsx", "*规模明细*.xlsx"]
      exclude_patterns: ["~$*", "*回复*"]
      sheet_name: "规模明细"
      version_strategy: "highest_number"
      fallback: "error"
  ```
- Database migration for `annuity_performance_NEW` table (Epic 1 Story 1.7 pattern)
- README section documenting annuity pipeline: input format, transformation steps, output schema
- Runbook: how to manually trigger annuity pipeline, troubleshoot common errors

**And** When team member reads annuity documentation
**Then** They should understand: data source location, expected Excel structure, transformation logic, database schema

**And** When I run `dagster job launch annuity_performance_job --config month=202501`
**Then** Pipeline executes successfully using configuration

**And** When database migration applied
**Then** `annuity_performance_NEW` table created with correct schema and composite PK

**Prerequisites:** Story 4.5 (working pipeline), Epic 1 Story 1.7 (database migrations), Epic 3 Story 3.0 (config schema)

**Technical Notes:**
- Configuration follows Epic 3 Story 3.0 validated schema structure
- Database migration file: `io/schema/migrations/YYYYMMDD_HHMM_create_annuity_performance_new.py`
- Table schema mirrors `GoldAnnuitySchema` from Story 4.4
- Documentation in `README.md` or `docs/domains/annuity_performance.md`
- Runbook includes: manual execution, common errors (missing file, validation failures), how to check results
- This becomes the **reference implementation** for Epic 9 domain migrations
- Reference: PRD §998-1030 (FR-7: Configuration Management)

---
