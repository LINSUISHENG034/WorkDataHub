# Functional Requirements

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
  - ✅ **Temporary ID generation:** Unresolved companies get stable `IN<16-char-Base32>` IDs generated via `HMAC_SHA1(WDH_ALIAS_SALT, business_key)` - ensures same company always maps to same temporary ID
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
