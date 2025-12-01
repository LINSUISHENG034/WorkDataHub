# Epic 2: Multi-Layer Data Quality Framework

**Goal:** Build the Bronze → Silver → Gold validation system that catches bad data before database corruption. This epic implements multi-layered data quality gates using Pydantic (row-level) and pandera (DataFrame-level) to ensure only valid data reaches the database.

**Business Value:** Data integrity is non-negotiable. This establishes the safety net that makes fearless refactoring possible - bad source data is rejected immediately with actionable errors, preventing the "garbage in, garbage out" problem.

---

### Story 2.1: Pydantic Models for Row-Level Validation (Silver Layer)

As a **data engineer**,
I want **Pydantic v2 models that validate individual rows during transformation**,
So that **business rules are enforced consistently and invalid data is caught with clear error messages**.

**Acceptance Criteria:**

**Given** I have the pipeline framework from Epic 1
**When** I create Pydantic models for the annuity performance domain
**Then** I should have:
- `AnnuityPerformanceIn` model with loose validation (handles messy Excel input)
- `AnnuityPerformanceOut` model with strict validation (enforces business rules)
- Chinese field names matching Excel sources (e.g., `月度: Optional[Union[str, int, date]]` → `月度: date`)
- Custom validators for business rules: `@field_validator('期末资产规模')` ensures >= 0
- Clear error messages: "Row 15, field '月度': Cannot parse 'INVALID' as date, expected format: YYYYMM or YYYY年MM月"
- Validation summary: total rows processed, successful, failed with reasons

**And** When I validate 100 rows where 5 have invalid dates
**Then** Pydantic raises `ValidationError` with details for all 5 failed rows

**And** When all rows pass validation
**Then** Returns list of `AnnuityPerformanceOut` objects ready for database loading

**Prerequisites:** Epic 1 Story 1.5 (pipeline framework to integrate validators)

**Technical Notes:**
- Use Pydantic v2 for performance and better error messages
- Separate Input/Output models enables progressive validation (loose → strict)
- Custom validator example:
  ```python
  from pydantic import BaseModel, field_validator, ValidationError

  class AnnuityPerformanceOut(BaseModel):
      月度: date  # Strict: must be valid date
      计划代码: str = Field(min_length=1)
      期末资产规模: float = Field(ge=0)  # >= 0

      @field_validator('月度', mode='before')
      def parse_chinese_date(cls, v):
          return parse_yyyymm_or_chinese(v)  # Story 2.4 utility
  ```
- Integration: Pipeline step validates each row, collects errors
- Reference: PRD §751-796 (FR-2: Multi-Layer Validation), §464-479 (Pydantic v2)

---

### Story 2.2: Pandera Schemas for DataFrame Validation (Bronze/Gold Layers)

As a **data engineer**,
I want **pandera DataFrameSchemas that validate entire DataFrames at layer boundaries**,
So that **schema violations are caught before data moves between Bronze/Silver/Gold layers**.

**Acceptance Criteria:**

**Given** I have Pydantic models from Story 2.1
**When** I create pandera schemas for Bronze and Gold layers
**Then** I should have:
- `BronzeAnnuitySchema`: validates raw Excel data (expected columns present, basic types)
- `GoldAnnuitySchema`: validates database-ready data (composite PK unique, no nulls in required fields)
- Schema checks: column presence, data types, uniqueness constraints, value ranges
- Decorator usage: `@pa.check_io(df1=BronzeSchema, out=SilverSchema)` on pipeline functions
- Failed validation exports to CSV: `failed_bronze_YYYYMMDD.csv` with violation details

**And** When Bronze schema validates raw Excel DataFrame
**Then** It should verify:
- Expected columns exist: `['月度', '计划代码', '客户名称', '期初资产规模', ...]`
- No completely null columns
- Date columns are parseable (coerce to datetime)

**And** When Gold schema validates database-ready DataFrame
**Then** It should verify:
- Composite PK `(月度, 计划代码, company_id)` has no duplicates
- Required fields are not null
- All columns match database schema (no extra columns)

**And** When validation fails
**Then** Raises `SchemaError` with details: which columns/rows failed, which checks violated

**Prerequisites:** Story 2.1 (Pydantic models for Silver layer)

**Technical Notes:**
- Use pandera 0.18+ for DataFrame-level contracts
- Bronze schema: permissive (data quality issues expected in raw Excel)
- Gold schema: strict (database integrity requirements)
- Decorator pattern integrates with pipeline framework (Story 1.5)
- Example:
  ```python
  import pandera as pa

  BronzeAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, coerce=True),
      "计划代码": pa.Column(pa.String, nullable=True),
      "期末资产规模": pa.Column(pa.Float, nullable=True)
  }, strict=False)  # Allow extra columns

  GoldAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, nullable=False),
      "计划代码": pa.Column(pa.String, nullable=False),
      "company_id": pa.Column(pa.String, nullable=False),
      "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0))
  }, strict=True, unique=['月度', '计划代码', 'company_id'])
  ```
- Reference: PRD §484-563 (Data Quality Requirements), docs/deep_research/4.md (Pandera)

---

### Story 2.3: Cleansing Registry Framework

As a **data engineer**,
I want **a centralized registry of reusable cleansing rules**,
So that **value-level transformations are standardized across all domains without code duplication**.

**Acceptance Criteria:**

**Given** I have validation schemas from Story 2.2
**When** I implement cleansing registry in `cleansing/registry.py`
**Then** I should have:
- `CleansingRegistry` class with rule registration: `registry.register('trim_whitespace', trim_func)`
- Built-in rules: trim whitespace, normalize company names, standardize dates, remove special characters
- Pydantic adapter: rules applied automatically during model validation via `@field_validator`
- Rule composition: multiple rules can apply to same field in sequence
- Per-domain configuration: enable/disable rules via YAML config

**And** When I register a cleansing rule for company names
**Then** It should normalize: "公司  有限" → "公司有限" (remove extra spaces)

**And** When Pydantic model uses cleansing adapter
**Then** Rules apply automatically during validation:
  ```python
  class AnnuityPerformanceOut(BaseModel):
      客户名称: str

      @field_validator('客户名称', mode='before')
      def clean_company_name(cls, v):
          return registry.apply_rules(v, ['trim_whitespace', 'normalize_company'])
  ```

**And** When rule is disabled in config for specific domain
**Then** That rule is skipped during validation

**Prerequisites:** Story 2.1 (Pydantic models to integrate with)

**Technical Notes:**
- Singleton pattern for registry: `registry = CleansingRegistry()`
- Rules are pure functions: `(value: Any) -> Any`
- Example built-in rules:
  ```python
  def trim_whitespace(value: str) -> str:
      return value.strip() if isinstance(value, str) else value

  def normalize_company_name(value: str) -> str:
      # Remove 「」, replace full-width spaces, etc.
      return value.replace('　', ' ').strip('「」')
  ```
- Configuration in `config/cleansing_rules.yml`:
  ```yaml
  domains:
    annuity_performance:
      客户名称: [trim_whitespace, normalize_company]
      计划代码: [trim_whitespace, uppercase]
  ```
- Reference: PRD §817-824 (FR-3.2: Registry-Driven Cleansing)

---

### Story 2.4: Chinese Date Parsing Utilities

As a **data engineer**,
I want **robust utilities for parsing various Chinese date formats**,
So that **inconsistent date formats from Excel sources are handled uniformly**.

**Acceptance Criteria:**

**Given** I have cleansing framework from Story 2.3
**When** I implement date parsing in `utils/date_parser.py`
**Then** I should have:
- `parse_yyyymm_or_chinese(value)` function supporting multiple formats:
  - Integer: `202501` → `date(2025, 1, 1)`
  - String: `"2025年1月"` → `date(2025, 1, 1)`
  - String: `"2025-01"` → `date(2025, 1, 1)`
  - Date object: `date(2025, 1, 1)` → `date(2025, 1, 1)` (passthrough)
  - 2-digit year: `"25年1月"` → `date(2025, 1, 1)` (assumes 20xx for <50, 19xx for >=50)
- Validation: rejects dates outside reasonable range (2000-2030)
- Clear errors: `ValueError("Cannot parse '不是日期' as date, supported formats: YYYYMM, YYYY年MM月, YYYY-MM")`

**And** When parsing `202501`
**Then** Returns `date(2025, 1, 1)`

**And** When parsing `"2025年1月"`
**Then** Returns `date(2025, 1, 1)`

**And** When parsing invalid date `"invalid"`
**Then** Raises `ValueError` with supported formats listed

**And** When parsing date outside range (1990)
**Then** Raises `ValueError("Date 1990-01 outside valid range 2000-2030")`

**Prerequisites:** Story 2.3 (cleansing framework)

**Technical Notes:**
- Use regex for Chinese format parsing: `re.match(r'(\d{4})年(\d{1,2})月', value)`
- Handle both full-width and half-width numbers
- Return first day of month for YYYYMM formats (business decision)
- Integration with Pydantic:
  ```python
  @field_validator('月度', mode='before')
  def parse_date(cls, v):
      return parse_yyyymm_or_chinese(v)
  ```
- Add comprehensive unit tests for all formats and edge cases
- Reference: PRD §863-871 (FR-3.4: Chinese Date Parsing)

---

### Story 2.5: Validation Error Handling and Reporting

As a **data engineer**,
I want **comprehensive error handling that exports failed rows with actionable feedback**,
So that **data quality issues can be fixed at the source without debugging pipeline code**.

**Acceptance Criteria:**

**Given** I have validation framework from Stories 2.1-2.4
**When** pipeline encounters validation failures
**Then** I should have:
- Failed rows exported to CSV: `logs/failed_rows_annuity_YYYYMMDD_HHMMSS.csv`
- CSV columns: original row data + `error_type`, `error_field`, `error_message`
- Error summary logged: "Validation failed: 15 rows failed Bronze schema, 23 rows failed Pydantic validation"
- Partial success handling: pipeline can continue with valid rows if configured (Epic 1 Story 1.10)
- Error threshold: if >10% of rows fail, stop pipeline (likely systemic data issue)

**And** When 15 rows fail Bronze schema validation (missing required columns)
**Then** CSV export shows:
  ```csv
  月度,计划代码,error_type,error_field,error_message
  202501,ABC123,SchemaError,期末资产规模,Column missing in source data
  ```

**And** When 5 out of 100 rows fail Pydantic validation
**Then** Pipeline continues with 95 valid rows and exports 5 failed rows to CSV

**And** When >10% of rows fail validation
**Then** Pipeline stops immediately with error: "Validation failure rate 15% exceeds threshold 10%, likely systemic issue"

**And** When all validations pass
**Then** No error CSV is created, logs show: "Validation success: 100 rows processed, 0 failures"

**Prerequisites:** Stories 2.1-2.4 (validation framework)

**Technical Notes:**
- Use Story 1.3 structured logging for error summaries
- CSV export location configurable: `settings.FAILED_ROWS_PATH` (default: `logs/`)
- Failure threshold configurable: `settings.VALIDATION_FAILURE_THRESHOLD` (default: 0.10)
- Integration with pipeline framework (Story 1.5): add validation step that collects errors
- Consider data sensitivity: failed row CSV might contain PII, ensure proper access control
- Reference: PRD §756-776 (FR-2.2: Silver Layer Validation)

---
