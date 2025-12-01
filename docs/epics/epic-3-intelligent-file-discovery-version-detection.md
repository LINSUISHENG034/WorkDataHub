# Epic 3: Intelligent File Discovery & Version Detection

**Goal:** Eliminate manual file selection every month by automatically detecting the latest data version (V1, V2, V3) across all domains and intelligently matching files using configurable patterns. This epic transforms "which file should I process?" from a daily decision into an automated capability.

**Business Value:** Monthly data drops arrive in inconsistent folder structures with V1, V2 revisions. Manual file selection is error-prone and time-consuming. Automated version detection saves 15-30 minutes per monthly run and eliminates the risk of processing stale data.

**Dependencies:** Epic 1 (configuration framework, logging)

**Dependency Flow:** 3.0 (config validation) → 3.1 (version scan) → 3.2 (file match) → 3.3 (Excel read) → 3.4 (normalize) → 3.5 (integration)

---

### Story 3.0: Data Source Configuration Schema Validation

As a **data engineer**,
I want **Pydantic validation of the data_sources.yml configuration structure**,
So that **configuration errors are caught at startup before any pipeline runs, preventing cryptic runtime failures**.

**Acceptance Criteria:**

**Given** I have `config/data_sources.yml` with domain configurations
**When** application starts and loads configuration
**Then** System should:
- Validate entire YAML structure using Pydantic `DataSourceConfig` model
- Verify required fields per domain: `base_path`, `file_patterns`, `sheet_name`
- Validate field types: `file_patterns` is list of strings, `version_strategy` is enum
- Check enum values: `version_strategy` in ['highest_number', 'latest_modified', 'manual']
- Raise clear error on missing/invalid fields before any file operations

**And** When configuration has missing required field (e.g., `sheet_name`)
**Then** Raise `ValidationError` at startup: "Domain 'annuity_performance' missing required field 'sheet_name'"

**And** When configuration has invalid version strategy
**Then** Raise `ValidationError`: "Invalid version_strategy 'newest', must be one of: ['highest_number', 'latest_modified', 'manual']"

**And** When configuration is valid
**Then** Log success: "Configuration validated: 6 domains configured"

**And** When template variables in paths (e.g., `{YYYYMM}`)
**Then** Validation allows placeholders, validates structure not resolved values

**Prerequisites:** Epic 1 Story 1.4 (configuration framework)

**Technical Notes:**
- Implement in `config/schemas.py` as Pydantic models:
  ```python
  from pydantic import BaseModel, Field
  from typing import Literal, List

  class DomainConfig(BaseModel):
      base_path: str = Field(..., description="Path template with {YYYYMM} placeholders")
      file_patterns: List[str] = Field(..., min_items=1)
      exclude_patterns: List[str] = Field(default_factory=list)
      sheet_name: str | int
      version_strategy: Literal['highest_number', 'latest_modified', 'manual'] = 'highest_number'
      fallback: Literal['error', 'use_latest_modified'] = 'error'

  class DataSourceConfig(BaseModel):
      domains: Dict[str, DomainConfig]
  ```
- Load and validate in `config/settings.py` during `Settings` initialization
- Fail fast: validation errors prevent application startup
- Prevents runtime errors in Stories 3.1-3.5 from malformed config
- Add unit tests for valid/invalid config scenarios
- Document supported Excel formats: `.xlsx` (via openpyxl), `.xlsm` supported, `.xls` NOT supported
- Reference: Dependency mapping identified config schema as hidden dependency

---

### Story 3.1: Version-Aware Folder Scanner

As a **data engineer**,
I want **automatic detection of versioned folders (V1, V2, V3) with configurable precedence rules**,
So that **the system always processes the latest data version without manual selection**.

**Acceptance Criteria:**

**Given** I have monthly data in `reference/monthly/202501/收集数据/业务收集/`
**When** both V1 and V2 folders exist
**Then** Scanner should:
- Detect all version folders matching pattern `V\d+`
- Select highest version number (V2 > V1)
- Return selected version path with justification logged
- Log: "Version detection: Found [V1, V2], selected V2 (highest_number strategy)"

**And** When only non-versioned files exist (no V folders)
**Then** Scanner should fallback to base path and log: "No version folders found, using base path"

**And** When version strategy configured as `latest_modified`
**Then** Scanner compares modification timestamps and selects most recently modified folder

**And** When version detection is ambiguous (e.g., V1 and V2 modified same day)
**Then** Scanner raises error with actionable message: "Ambiguous versions: V1 and V2 both modified on 2025-01-05, configure precedence rule or specify --version manually"

**And** When CLI override `--version=V1` provided
**Then** Scanner uses V1 regardless of automatic detection, logs: "Manual override: using V1 as specified"

**Prerequisites:** Story 3.0 (validated configuration), Epic 1 Story 1.4 (configuration framework), Story 1.3 (logging)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py`
- Version detection strategies: `highest_number` (default), `latest_modified`, `manual`
- Use `pathlib.Path.glob()` for folder scanning
- Configuration in `config/data_sources.yml`:
  ```yaml
  domains:
    annuity_performance:
      version_strategy: "highest_number"
      fallback: "error"  # or "use_latest_modified"
  ```
- Return `VersionedPath` dataclass: `path: Path, version: str, strategy_used: str`
- Unit tests for all strategies and edge cases
- Reference: PRD §565-605 (Version Detection System)

---

### Story 3.2: Pattern-Based File Matcher

As a **data engineer**,
I want **flexible file matching using glob patterns with include/exclude rules**,
So that **files are found despite naming variations and temp files are automatically filtered out**.

**Acceptance Criteria:**

**Given** I configure file patterns in `config/data_sources.yml`:
```yaml
annuity_performance:
  file_patterns:
    - "*年金*.xlsx"
    - "*规模明细*.xlsx"
  exclude_patterns:
    - "~$*"  # Excel temp files
    - "*回复*"  # Email reply files
```

**When** I scan folder with files: `年金数据2025.xlsx`, `~$年金数据2025.xlsx`, `规模明细回复.xlsx`
**Then** Matcher should:
- Find files matching include patterns: `["年金数据2025.xlsx"]`
- Exclude temp files and replies
- Return exactly 1 matching file
- Log: "File matching: 3 candidates, 1 match after filtering"

**And** When no files match patterns
**Then** Raise error: "No files found matching patterns ['*年金*.xlsx', '*规模明细*.xlsx'] in path /reference/monthly/202501/..."

**And** When multiple files match after filtering
**Then** Raise error with candidate list: "Ambiguous match: Found 2 files ['年金数据V1.xlsx', '年金数据V2.xlsx'], refine patterns or use version detection"

**And** When pattern uses Chinese characters
**Then** Matcher correctly handles UTF-8 encoding and finds matches

**Prerequisites:** Story 3.1 (version detection provides base path), Story 3.0 (validated config)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py` as `FilePatternMatcher` class
- Use `pathlib.Path.glob()` with Unicode support for Chinese characters
- Include/exclude logic: `(match any include) AND (match no exclude)`
- Validation: exactly 1 file must remain after filtering (fail if 0 or >1)
- Error messages include full file paths for troubleshooting
- Configuration loaded from Story 3.0 validated schema
- **Cross-platform testing:** Test Chinese characters in paths on Windows and Linux (encoding differences)
- Reference: PRD §608-643 (File Discovery and Processing)

---

### Story 3.3: Multi-Sheet Excel Reader

As a **data engineer**,
I want **targeted sheet extraction from multi-sheet Excel workbooks**,
So that **I can process specific data without manual sheet copying**.

**Acceptance Criteria:**

**Given** I have Excel file `年金数据2025.xlsx` with sheets: `['Summary', '规模明细', 'Notes']`
**When** configuration specifies `sheet_name: "规模明细"`
**Then** Reader should:
- Load only the specified sheet as DataFrame
- Preserve Chinese characters in column names
- Skip completely empty rows automatically
- Return DataFrame with proper column types inferred

**And** When sheet name is integer index `sheet_name: 1`
**Then** Reader loads second sheet (0-indexed)

**And** When specified sheet name doesn't exist
**Then** Raise error: "Sheet '规模明细' not found in file 年金数据2025.xlsx, available sheets: ['Summary', 'Notes']"

**And** When Excel has merged cells
**Then** Reader uses first cell's value for entire merged range (pandas default behavior)

**And** When Excel has formatting but no data in rows
**Then** Reader skips empty rows, logs: "Skipped 5 empty rows during load"

**Prerequisites:** Story 3.2 (file matcher provides Excel path)

**Technical Notes:**
- Implement in `io/readers/excel_reader.py` as `ExcelReader` class
- Use `pandas.read_excel()` with parameters:
  - `sheet_name`: from config
  - `engine='openpyxl'`: better Unicode support
  - `na_values`: ['', ' ', 'N/A', 'NA']
  - `skiprows`: none (handle in Bronze validation)
- Handle both sheet name (str) and index (int) from config
- Error handling: file not found, corrupted Excel, sheet missing
- Return `ExcelReadResult` dataclass: `df: pd.DataFrame, sheet_name: str, row_count: int`
- Reference: PRD §729-748 (FR-1.3: Multi-Sheet Excel Reading)

---

### Story 3.4: Column Name Normalization

As a **data engineer**,
I want **automatic normalization of column names from Excel sources**,
So that **inconsistent spacing, special characters, and encoding issues don't break pipelines**.

**Acceptance Criteria:**

**Given** I load Excel with column names: `['月度  ', '  计划代码', '客户名称\n', '期末资产规模']`
**When** I apply column normalization
**Then** Normalized names should be: `['月度', '计划代码', '客户名称', '期末资产规模']`

**And** When column names have full-width spaces `'客户　名称'` (full-width space)
**Then** Replace with half-width: `'客户 名称'` → `'客户名称'` (then trim)

**And** When column has newlines or tabs
**Then** Replace with single space: `'客户\n名称'` → `'客户 名称'`

**And** When column is completely empty or whitespace-only
**Then** Generate placeholder name: `'Unnamed_1'`, `'Unnamed_2'`, etc., and log warning

**And** When duplicate column names exist after normalization
**Then** Append suffix: `'月度'`, `'月度_1'`, `'月度_2'` and log warning

**Prerequisites:** Story 3.3 (Excel reader produces DataFrames with raw column names)

**Technical Notes:**
- Implement in `utils/column_normalizer.py` as pure function
- Normalization steps:
  1. Strip leading/trailing whitespace
  2. Replace full-width spaces (U+3000) with half-width
  3. Replace newlines/tabs with single space
  4. Replace multiple consecutive spaces with single space
  5. Handle empty/duplicate names
- Apply automatically in ExcelReader before returning DataFrame
- Configuration option to disable normalization if needed (default: enabled)
- Unit tests with edge cases: emoji in names, numeric names, etc.
- Reference: PRD §742-748 (FR-1.4: Resilient Data Loading)

---

### Story 3.5: File Discovery Integration

As a **data engineer**,
I want **a unified file discovery interface combining version detection, pattern matching, and Excel reading**,
So that **any domain can discover and load files with a single configuration entry**.

**Acceptance Criteria:**

**Given** I configure domain in `config/data_sources.yml`:
```yaml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns: ["*年金*.xlsx"]
    exclude_patterns: ["~$*"]
    sheet_name: "规模明细"
    version_strategy: "highest_number"
```

**When** I call `discover_and_load(domain='annuity_performance', month='202501')`
**Then** System should:
- Resolve `{YYYYMM}` placeholder to `202501`
- Scan for version folders (Story 3.1)
- Match files using patterns (Story 3.2)
- Load specified Excel sheet (Story 3.3)
- Normalize column names (Story 3.4)
- Return `DataDiscoveryResult`: `df: DataFrame, file_path: Path, version: str, sheet_name: str`

**And** When discovery completes successfully
**Then** Log structured summary:
```json
{
  "domain": "annuity_performance",
  "file_path": "reference/monthly/202501/收集数据/业务收集/V2/年金数据.xlsx",
  "version": "V2",
  "sheet_name": "规模明细",
  "row_count": 1250,
  "column_count": 15,
  "duration_ms": 850
}
```

**And** When any step fails (version detection, file matching, Excel reading)
**Then** Raise structured error with stage context:
```python
DiscoveryError(
    domain="annuity_performance",
    failed_stage="version_detection",  # or "file_matching", "excel_reading", "normalization"
    original_error=<original exception>,
    message="Version detection failed: Ambiguous versions V1 and V2 both modified on 2025-01-05"
)
```

**And** When multiple domains configured
**Then** Each domain discovery is independent (failure in one doesn't block others)

**And** When error raised from any sub-component
**Then** Error context includes: domain name, failed stage, input parameters, original exception

**Prerequisites:** Stories 3.0-3.4 (all discovery components including config validation)

**Technical Notes:**
- Implement in `io/connectors/file_connector.py` as `FileDiscoveryService` class
- Facade pattern: orchestrates version scanner, pattern matcher, Excel reader, normalizer
- Template variable resolution: `{YYYYMM}`, `{YYYY}`, `{MM}` from config or parameters
- **Structured error context:** Wrap exceptions with stage markers for debugging
  ```python
  class DiscoveryError(Exception):
      def __init__(self, domain: str, failed_stage: str, original_error: Exception, message: str):
          self.domain = domain
          self.failed_stage = failed_stage  # One of: config_validation, version_detection, file_matching, excel_reading, normalization
          self.original_error = original_error
          super().__init__(message)
  ```
- Error aggregation: collect all errors from sub-components with stage context
- Integration with Epic 1 logging (Story 1.3): log structured error details
- Return rich result object: `DataDiscoveryResult(df, file_path, version, sheet_name, duration_ms)`
- **Caching opportunity:** Cache version detection results per month (optimization for Epic 9)
- Add integration test: end-to-end discovery with real file structure
- **Cross-platform validation:** Test on Windows and Linux for path encoding consistency
- Reference: PRD §699-748 (FR-1: Intelligent Data Ingestion complete), Dependency mapping enhanced error context

---
