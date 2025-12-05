# Epic Technical Specification: Intelligent File Discovery & Version Detection

Date: 2025-11-27
Author: Link
Epic ID: 3
Status: Validated with Real Data ✅
Version: 1.3
Last Validated: 2025-11-28 (Validation Report approved)

---

## Overview

Epic 3 implements an intelligent file discovery system that automatically detects the latest data version (V1, V2, V3) across all domains and matches files using configurable glob patterns. This epic eliminates the manual "which file should I process?" decision every month by providing:

- **Version-aware folder scanning** with configurable precedence rules (highest_number, latest_modified)
- **Pattern-based file matching** using glob patterns with include/exclude rules
- **Multi-sheet Excel reading** with Chinese character support
- **Column name normalization** handling whitespace and encoding inconsistencies
- **Unified discovery interface** orchestrating all components with structured error handling

The system transforms monthly data processing from a manual, error-prone task into a fully automated capability, saving 15-30 minutes per run and eliminating the risk of processing stale data.

**Key Innovation:** File-pattern-aware version detection scopes version selection to specific file patterns per domain, enabling partial corrections (e.g., only annuity data revised to V2) without forcing all domains to V2.

---

## PRD Alignment

This epic directly addresses the following Product Requirements Document objectives:

### Success Criteria Mapping

**1. Automation Excellence - "Zero Manual File Selection"** (PRD Section: Success Criteria #1)
- **PRD Goal:** System automatically identifies and processes latest data versions (V1, V2, etc.) across all domains without user intervention
- **Epic 3 Delivers:**
  - Story 3.1: Version-aware folder scanner with configurable precedence (highest_number, latest_modified)
  - Story 3.2: Pattern-based file matching eliminates manual file selection
  - Story 3.5: Unified `discover_and_load()` API orchestrates automatic discovery

**2. Fearless Extensibility - "Configuration Over Code"** (PRD Section: Success Criteria #2)
- **PRD Goal:** File discovery rules declared in YAML/JSON, not hardcoded in Python
- **Epic 3 Delivers:**
  - Story 3.0: Pydantic-validated `data_sources.yml` schema
  - Generic discovery algorithm works for ANY domain via configuration
  - Vertical slice strategy: Extend via config, not code changes (Open-Closed Principle)

**3. Monthly Data Drop Automation** (PRD Section: Success Criteria #1)
- **PRD Goal:** When new monthly data arrives, all relevant domains are automatically detected, validated, and processed
- **Epic 3 Delivers:**
  - Template variable resolution: `{YYYYMM}` → `202501` (Story 3.5)
  - Multi-domain processing through shared discovery service
  - Saves 15-30 minutes per monthly run (quantified in Overview)

### Functional Requirements Mapping

Epic 3 implements **FR-1: Intelligent Data Ingestion** capabilities from PRD Section: Functional Requirements.

| PRD FR | Description | Epic 3 Story Mapping |
|--------|-------------|---------------------|
| **FR-1.1** | Version-Aware File Discovery | Story 3.1: VersionScanner with strategy selection |
| **FR-1.2** | Pattern-Based File Matching | Story 3.2: FilePatternMatcher with include/exclude rules |
| **FR-1.3** | Multi-Sheet Excel Reading | Story 3.3: ExcelReader with Chinese character support |
| **FR-1.4** | Resilient Data Loading | Story 3.4: Column normalization + Story 3.3: Empty row handling |

**Acceptance Criteria Alignment:**
- ✅ FR-1.1-AC1: Scans `reference/monthly/{YYYYMM}/收集数据/` → Story 3.5 (template resolution)
- ✅ FR-1.1-AC2: Detects V1, V2 and selects highest → Story 3.1 (highest_number strategy)
- ✅ FR-1.1-AC3: Falls back to non-versioned files → Story 3.1 (fallback logic)
- ✅ FR-1.1-AC5: Manual override via CLI `--version=V1` → Story 3.1 (version_override parameter)
- ✅ FR-1.2-AC1: Include/exclude patterns in config → Story 3.0 + 3.2
- ✅ FR-1.2-AC3: Exactly 1 file match validation → Story 3.2 (ambiguity detection)
- ✅ FR-1.3-AC1: Sheet name in configuration → Story 3.0 + 3.3
- ✅ FR-1.3-AC4: Chinese character preservation → Story 3.3 (openpyxl engine + UTF-8)
- ✅ FR-1.4-AC1: Skip empty rows → Story 3.3 (skip_empty_rows parameter)
- ✅ FR-1.4-AC4: Column name normalization → Story 3.4 (normalize_column_names)

### Epic-Level Reference

**PRD Epic Roadmap:** Epic 3 - Version Detection System (PRD Section: Epic Sequencing)

**Reference Document:** `docs/prd.md` (WorkDataHub Product Requirements Document, Version 1.0)

**Related PRD Sections:**
- **Section: What Makes This Special** - Lines 25-26 (Intelligent Automation innovation)
- **Section: Success Criteria #1** - Lines 66-74 (Automation Excellence)
- **Section: Success Criteria #2** - Lines 78-86 (Fearless Extensibility)
- **Section: Functional Requirements FR-1** - Lines 705-747 (Intelligent Data Ingestion)

---

## Epic 2 Retrospective Impact

> **DOCUMENT STATUS:** This tech-spec incorporates critical lessons from Epic 2 Retrospective (2025-11-27).

### Critical Improvements Applied

This Epic 3 tech-spec has been enhanced based on Epic 2 Retrospective findings:

**1. Data Source Validation (NEW SECTION)**
- 🚨 **BLOCKING:** Action Item #2 must complete before Epic 3 development
- Real data analysis required from `reference/archive/monthly/202411/收集数据/`
- Prevents 87.5% integration test failure rate seen in Epic 2 Story 2.5
- Validates assumptions about version folder structure, file patterns, edge cases

**2. Layer-Specific Field Requirements (NEW SECTION)**
- Clarifies what Epic 3 DOES validate (file discovery, Excel reading)
- Clarifies what Epic 3 does NOT validate (field presence, business rules)
- Distinguishes Source Fields, Enriched Fields, Calculated Fields
- Prevents model/data mismatches like `company_id`, `年化收益率` issues in Epic 2

**3. Test Data Realism Guidelines (NEW SECTION)**
- Anti-pattern: "Perfect" test data that masks real-world issues
- Requirement: Integration tests use fixtures based on Action Item #2 findings
- Edge cases replicate real 202411 data structure
- Prevents idealized test data causing production failures

**4. Vertical Slice Strategy (NEW SECTION)**
- Generic algorithm design (domain-agnostic)
- Annuity-only validation (vertical slice)
- Open-Closed Principle: extend via configuration, not code changes
- Prevents architecture defects requiring project-wide rework

**5. Two-Round Code Review Strategy (NEW SECTION)**
- Stories 2.4 and 2.5 required two rounds in Epic 2
- Cost: ~20% more time, Benefit: prevents production defects
- Explicit criteria for first and second review rounds
- Stories 3.3 and 3.5 likely requiring two rounds

### References

- **Epic 2 Retrospective:** `docs/sprint-artifacts/epic-2-retrospective-2025-11-27.md`
- **Action Item #1:** Enhance tech-spec template (4 new sections added)
- **Action Item #2:** Real data validation (BLOCKING Epic 3 development)
- **Version Detection Logic:** `docs/supplement/02_version_detection_logic.md`

### Document Changelog

**2025-11-28 (Validation Report Approval - PRD Alignment Added):**
- ✅ Epic 3 Tech-Spec validated by Scrum Master (91% score, approved for development)
- ✅ Added "PRD Alignment" section (lines 28-89)
  - Success Criteria mapping: Automation Excellence, Fearless Extensibility, Monthly Data Drop
  - Functional Requirements mapping: FR-1.1 through FR-1.4 (complete AC traceability)
  - Epic-level reference with PRD section citations
- ✅ Validation Report generated: `validation-report-2025-11-28-003528.md`
- ✅ Minor gap resolved: Overview now explicitly tied to PRD goals
- ✅ Version: 1.2 → 1.3
- ✅ Status: Validated → Approved for Development

**2025-11-27 (Action Item #2 Completed - Real Data Validation):**
- ✅ Completed Action Item #2: Real Data Validation & Analysis
- ✅ Created analysis report: `action-item-2-real-data-analysis.md`
- 🚨 **CRITICAL CORRECTIONS APPLIED:**
  - Base path: `业务收集` → `数据采集`
  - File patterns: `*年金*.xlsx` → `*年金终稿*.xlsx`
  - Exclude patterns: Added `*.eml`
- ✅ Updated "Data Source Validation" section with real 202411 data
- ✅ Added real data samples (5 rows, 23 columns documented)
- ✅ Added full column list with NaN indicators
- ✅ Validated version folder structure (V1 in 数据采集, V1-V3 in 战区收集)
- ✅ Confirmed Epic 2 field issues (`company_id`, `年化收益率` missing)
- ✅ Updated configuration examples throughout document
- ✅ Resolved Risk R0 (BLOCKING → RESOLVED)
- ✅ Changed status: Enhanced → Validated with Real Data
- ✅ Version: 1.1 → 1.2

**2025-11-27 (Post-Epic 2 Retrospective):**
- Added "Data Source Validation & Real Data Analysis" section
- Added "Layer-Specific Field Requirements" section
- Added "Test Data Realism Guidelines" section
- Added "Vertical Slice Strategy: Annuity-First Validation" section
- Added "Code Review Strategy" section with two-round requirements
- Added Risk R0: Real Data Validation Dependency (BLOCKING)
- Updated Risks section with Epic 2 precedent references

---

## Objectives and Scope

### Objectives

1. **Eliminate Manual File Selection**
   - Automatically identify latest data versions (V1, V2, V3) per domain
   - Process correct files without human intervention every monthly run

2. **Handle Inconsistent Naming**
   - Use configurable glob patterns to match files despite naming variations
   - Filter out temp files (`~$*`) and unwanted files (`*回复*`) automatically

3. **Support Multi-Sheet Excel**
   - Extract specific sheets from complex workbooks
   - Preserve Chinese characters in column names and data

4. **Robust Error Handling**
   - Provide structured errors showing which stage failed (version detection, file matching, Excel reading)
   - Include actionable guidance in error messages

### In-Scope

**Configuration (Story 3.0):**
- Pydantic validation of `data_sources.yml` structure
- Validate domain configs: `base_path`, `file_patterns`, `sheet_name`, `version_strategy`

**Version Detection (Story 3.1):**
- Scan for `V\d+` folders, select highest version or latest modified
- Support CLI override: `--version=V1` for manual selection
- Configurable fallback strategies

**File Matching (Story 3.2):**
- Glob pattern matching with include/exclude rules
- Handle Chinese characters in filenames (UTF-8)
- Validate exactly 1 file matches after filtering

**Excel Reading (Story 3.3):**
- Load specific sheets by name or index
- Handle merged cells, empty rows, Chinese columns
- Use openpyxl engine for better Unicode support

**Column Normalization (Story 3.4):**
- Strip whitespace, replace full-width spaces
- Handle newlines, tabs, duplicate names
- Generate placeholders for unnamed columns

**Integration (Story 3.5):**
- Unified `discover_and_load()` API
- Template variable resolution: `{YYYYMM}`, `{YYYY}`, `{MM}`
- Structured error context with stage markers

### Out-of-Scope

- CSV file reading (Excel only for MVP)
- Cloud storage integration (local filesystem only)
- Schema inference (handled by Epic 2 validation)
- Performance optimization beyond basic caching (deferred to Epic 9)

## Data Source Validation & Real Data Analysis

> **CRITICAL LESSON FROM EPIC 2:** Model/data mismatches caused 87.5% integration test failures in Epic 2. This section implements Action Item #2 from Epic 2 Retrospective to prevent similar issues.

### Data Source Schema Verification (Action Item #2)

✅ **COMPLETED: 2025-11-27**

**Analysis Report:** `docs/sprint-artifacts/auxiliary/action-item-2-real-data-analysis.md`

**Critical Findings:**

🚨 **PATH CORRECTIONS APPLIED:**
- ❌ **Previous Assumption:** `reference/monthly/{YYYYMM}/收集数据/业务收集`
- ✅ **Real Data Location:** `tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集`

🚨 **PATTERN CORRECTIONS APPLIED:**
- ❌ **Previous Pattern:** `["*年金*.xlsx"]` (too broad, would match multiple files)
- ✅ **Validated Pattern:** `["*年金终稿*.xlsx"]` (unambiguous, matches exactly 1 file)

**Completed Validations:**

1. ✅ **Version Folder Structure Verification**
   - ✅ Confirmed: `数据采集/V1/` contains annuity file
   - ✅ Confirmed: `战区收集/` has V1, V2, V3 (multi-version test case)
   - ✅ Validated: Structure matches `docs/supplement/02_version_detection_logic.md`

2. ✅ **Annuity Domain `file_patterns` Determination**
   - ✅ Found file: `【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx`
   - ✅ Optimal pattern: `["*年金终稿*.xlsx"]` (unambiguous, 1 match)
   - ✅ Tested: No ambiguous matching in V1 directory

3. ✅ **Edge Cases Generated**
   - ✅ Multi-version: `战区收集` has V1, V2, V3 (V3 most recent)
   - ✅ Single version: `数据采集` has only V1
   - ✅ Fallback: `组合排名` has no version folders
   - ✅ Exclusions: Found `*回复*.eml` file (validates exclude pattern)

4. ✅ **Consistency Check with Architecture Document**
   - ✅ Decision #1 (File-Pattern-Aware Version Detection) validated
   - ⚠️ **Deviation:** Base path corrected (`业务收集` → `数据采集`)

**Validated Configuration:**

```yaml
# ✅ VALIDATED with real 202411 data
annuity_performance:
  base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"  # ✅ CORRECTED from 业务收集
  file_patterns: ["*年金终稿*.xlsx"]                      # ✅ CORRECTED from *年金*.xlsx
  exclude_patterns: ["~$*", "*回复*", "*.eml"]            # ✅ Added .eml exclusion
  sheet_name: "规模明细"                                   # ✅ CONFIRMED exists
  version_strategy: "highest_number"
  fallback: "error"
```

**Real Data Samples (from 202411):**

```
# Source: reference/archive/monthly/202411/收集数据/数据采集/V1/
# File: 【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx
# Sheet: 规模明细 (33,269 rows, 23 columns)

月度       | 计划代码 | 客户名称                        | 期初资产规模    | 期末资产规模    | 当期收益率 | 机构代码 | 机构
---------- | ------- | ------------------------------ | ------------- | ------------- | --------- | ------- | ----
202411     | Z0005   | 新疆维吾尔自治区叁号职业年金计划 | 6.237423e+09  | 7.260821e+09  | 0.050861  | G23     | 新疆
202411     | Z0004   | 湖北省（肆号）职业年金计划        | 6.742567e+09  | 9.213629e+09  | 0.051508  | G09     | 湖北
202411     | Z0003   | 北京市（贰号）职业年金计划        | 1.093619e+10  | 1.342700e+10  | 0.053628  | G01     | 北京
202411     | Z0012   | 天津市贰号职业年金计划           | 5.613525e+09  | 6.635820e+09  | 0.043880  | G03     | 天津
202411     | Z0015   | 广西壮族自治区叁号职业年金计划    | 6.671706e+09  | 8.092648e+09  | 0.061108  | G14     | 广西

# Key Observations (✅ = Confirmed, ❌ = Missing):
- ✅ 月度 field: YYYYMM format (202411, not YYYY年MM月)
- ✅ 客户名称 has full legal names with Chinese characters
- ❌ company_id does NOT exist in source (will be enriched in Epic 5)
- ❌ 年化收益率 does NOT exist in source (calculated field, Gold layer only)
- ⚠️ NaN values present in 7 columns: 组合类型, 组合代码, 组合名称, 子企业号, 子企业名称, 集团企业客户号, 集团企业客户名称
- ✅ Numeric fields use scientific notation (e.g., 6.237423e+09)
- ✅ UTF-8 encoding for all Chinese characters
```

**Full Column List (23 columns):**

1. 月度 | 2. 业务类型 | 3. 计划类型 | 4. 计划代码 | 5. 计划名称 | 6. 组合类型* | 7. 组合代码* | 8. 组合名称*
9. 客户名称 | 10. 期初资产规模 | 11. 期末资产规模 | 12. 供款 | 13. 流失(含待遇支付) | 14. 流失 | 15. 待遇支付
16. 投资收益 | 17. 当期收益率 | 18. 机构代码 | 19. 机构 | 20. 子企业号* | 21. 子企业名称* | 22. 集团企业客户号* | 23. 集团企业客户名称*

(*) = Columns with frequent NaN values

### Layer-Specific Field Requirements

**Lesson from Epic 2:** Distinguish Source Fields, Enriched Fields, and Calculated Fields

**Field Classification for Epic 3:**

| Field Category | Bronze Layer | Silver Layer | Gold Layer | Notes |
|----------------|--------------|--------------|------------|-------|
| **Source Fields** | Validate presence | Validate business rules | Validate database constraints | Fields that exist in Excel source |
| **Enriched Fields** | Not validated | Optional (awaiting enrichment) | Required (after enrichment) | Added by Epic 5 (e.g., `company_id`) |
| **Calculated Fields** | Not validated | Not validated | Required (after calculation) | Computed in Gold layer (e.g., `年化收益率`) |

**Epic 3 Specifics:**

Epic 3 focuses on **file discovery and Excel reading** - NO field-level validation.

**Bronze Layer Output:**
- DataFrame with raw columns from Excel (as-is, column names normalized)
- No field-level validation (handled by Epic 2 Bronze schemas)

**What Epic 3 DOES validate:**
- ✅ File exists and matches patterns
- ✅ Excel sheet exists and is readable
- ✅ Column names are normalizable (no completely null columns)
- ✅ DataFrame has at least 1 data row

**What Epic 3 does NOT validate:**
- ❌ Field presence (e.g., whether `月度` or `客户名称` columns exist)
- ❌ Field types (e.g., whether `期末资产规模` is numeric)
- ❌ Business rules (handled by Epic 2 Silver layer)

**Handoff to Epic 2:**
- Epic 3 returns normalized DataFrame
- Epic 2 Bronze validation receives DataFrame and validates expected columns exist

### Test Data Realism Guidelines

**Anti-Pattern from Epic 2:** Creating "perfect" test data that masks real-world issues

**Epic 3 Test Data Requirements:**

1. **Version Folder Structures (Unit Tests)**
   - Include V1 only, V1+V2, V1+V2+V3 scenarios
   - Include scenarios with NO version folders (fallback to base path)
   - Include empty version folders (V2 exists but has no matching files)

2. **File Naming Patterns (Integration Tests)**
   - Include Chinese characters: `年金数据.xlsx`, `规模明细.xlsx`
   - Include temp files: `~$年金数据.xlsx` (must be excluded)
   - Include ambiguous patterns: `年金数据V1.xlsx`, `年金数据V2.xlsx` (should trigger error)
   - Include unwanted files: `年金数据回复.xlsx` (must be excluded)

3. **Excel Files (Integration Tests)**
   - Include multi-sheet workbooks with Chinese sheet names
   - Include merged cells (openpyxl default behavior)
   - Include empty rows with formatting (must be skipped)
   - Include columns with whitespace: `'月度  '`, `'  计划代码'`
   - Include full-width spaces: `'客户　名称'` (U+3000)
   - Include duplicate column names after normalization

4. **Edge Cases from Real Data**
   - Based on Action Item #2 findings from 202411 data
   - Replicate actual version folder structure
   - Use real file naming patterns
   - Include real Excel anomalies (merged cells, empty rows, encoding issues)

**Success Criteria:**
- Integration tests use fixtures based on Action Item #2 findings
- Test failures in Epic 3 reflect real-world issues, not idealized scenarios
- Test data includes all edge cases discovered in 202411 analysis

### Vertical Slice Strategy: Annuity-First Validation

**Strategic Decision from Epic 2 Retrospective:**

Epic 3 builds **generic** file discovery system (domain-agnostic), but validates with **annuity domain only** until proven end-to-end.

**Implementation Approach:**

**Generic Design:**
```python
# Domain-agnostic algorithm (works for ANY domain)
def discover_and_load(
    domain: str,  # "annuity_performance", "universal_insurance", etc.
    month: str,
    version_override: Optional[str] = None
) -> DataDiscoveryResult:
    # Load domain-specific configuration
    config = load_data_source_config(domain)

    # Generic discovery algorithm
    versioned_path = version_scanner.detect_version(
        base_path=config.base_path.format(YYYYMM=month),
        file_patterns=config.file_patterns,  # Only this differs per domain
        strategy=config.version_strategy
    )

    # Generic file matching, Excel reading, normalization
    ...
```

**Annuity-Only Validation:**
```yaml
# config/data_sources.yml - MVP focuses on annuity only
domains:
  annuity_performance:  # ✅ Validated with real 202411 data
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"  # ⚠️ CORRECTED
    file_patterns: ["*年金终稿*.xlsx"]                      # ⚠️ CORRECTED
    exclude_patterns: ["~$*", "*回复*", "*.eml"]
    sheet_name: "规模明细"
    version_strategy: "highest_number"

  # Future domains (Epic 9) extend via configuration only:
  # universal_insurance:
  #   base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
  #   file_patterns: ["*万能险*.xlsx"]  # No code changes needed
```

**Benefits:**
- ✅ Generic system ready for multi-domain expansion (Open-Closed Principle)
- ✅ Annuity validation prevents architecture defects before scaling
- ✅ Future domains add configuration, not code changes

**Open-Closed Principle:**
- **Open for extension:** New domains via configuration
- **Closed for modification:** Core algorithm unchanged

## System Architecture Alignment

### Architecture Decisions Applied

**Decision #1: File-Pattern-Aware Version Detection**
- Scopes version detection to domain-specific file patterns
- Enables partial corrections without forcing all domains to same version
- Example: Annuity V2, Business Collection V1 (different versions coexist)

**Decision #7: Comprehensive Naming Conventions**
- Pydantic fields use original Chinese from Excel sources
- Database columns use `lowercase_snake_case` English
- Configuration files use `snake_case.yml`

**Decision #4: Hybrid Error Context Standards**
- Structured exceptions with required context fields
- Error messages include: domain, stage, file path, original error
- Example: `DiscoveryError(domain="annuity_performance", failed_stage="file_matching", ...)`

### Clean Architecture Boundaries

**Configuration Layer (`config/`):**
- `data_sources.yml`: Domain configurations
- `schemas.py`: Pydantic validation models
- `mapping_loader.py`: YAML loading utilities

**I/O Layer (`io/connectors/`):**
- `file_connector.py`: `FileDiscoveryService` facade
- `version_scanner.py`: Version folder detection
- `pattern_matcher.py`: Glob pattern matching
- `excel_reader.py`: Excel reading (moved to `io/readers/`)

**Utils Layer (`utils/`):**
- `column_normalizer.py`: Column name normalization

**Domain Layer:**
- No direct dependencies - receives DataFrames from I/O layer

### Integration with Other Epics

**Epic 1 Dependencies:**
- Story 1.3: Structured logging for discovery metrics
- Story 1.4: Configuration framework for settings
- Story 1.2: CI/CD validates discovery code

**Epic 2 Integration:**
- Bronze validation receives DataFrames from Epic 3
- Column names normalized before validation

**Epic 4 Integration:**
- Annuity pipeline calls `discover_and_load(domain='annuity_performance', month='202501')`
- Returns ready-to-validate DataFrame

## Detailed Design

### Services and Modules

#### `FileDiscoveryService` (Story 3.5)

**Location:** `io/connectors/file_connector.py`

**Responsibilities:**
- Orchestrate version detection, file matching, Excel reading, normalization
- Resolve template variables: `{YYYYMM}` → `202501`
- Return `DataDiscoveryResult` with DataFrame and metadata

**Key Methods:**
```python
def discover_and_load(
    domain: str,
    month: str,  # YYYYMM format
    version_override: Optional[str] = None
) -> DataDiscoveryResult:
    """
    Discover and load Excel data for domain and month.

    Returns:
        DataDiscoveryResult containing:
        - df: pd.DataFrame (normalized columns)
        - file_path: Path (selected file)
        - version: str (V1, V2, etc.)
        - sheet_name: str (loaded sheet)
        - duration_ms: int (total discovery time)
    """
```

**Error Handling:**
- Wraps all exceptions in `DiscoveryError` with stage context
- Stages: `config_validation`, `version_detection`, `file_matching`, `excel_reading`, `normalization`

#### `VersionScanner` (Story 3.1)

**Location:** `io/connectors/file_connector.py`

**Responsibilities:**
- Scan for versioned folders (`V1`, `V2`, `V3`)
- Select version based on strategy: `highest_number`, `latest_modified`, `manual`
- Handle fallbacks when no versions found

**Key Methods:**
```python
def detect_version(
    base_path: Path,
    file_patterns: List[str],
    strategy: VersionStrategy = VersionStrategy.HIGHEST_NUMBER
) -> VersionedPath:
    """
    Returns:
        VersionedPath(
            path: Path,          # Selected versioned path
            version: str,        # "V2" or "base" if no versions
            strategy_used: str   # "highest_number", etc.
        )
    """
```

**Strategies:**
- `highest_number`: V3 > V2 > V1 (numeric sort)
- `latest_modified`: Most recently modified folder
- `manual`: CLI override `--version=V1`

#### `FilePatternMatcher` (Story 3.2)

**Location:** `io/connectors/file_connector.py`

**Responsibilities:**
- Match files using glob patterns
- Apply include/exclude filters
- Validate exactly 1 match

**Key Methods:**
```python
def match_files(
    search_path: Path,
    include_patterns: List[str],
    exclude_patterns: List[str]
) -> Path:
    """
    Returns:
        Path of single matched file

    Raises:
        DiscoveryError if 0 or multiple matches
    """
```

**Pattern Logic:**
```python
# Pseudo-code
candidates = []
for pattern in include_patterns:
    candidates.extend(search_path.glob(pattern))

# Apply exclusions
filtered = [
    f for f in candidates
    if not any(f.match(excl) for excl in exclude_patterns)
]

# Validate exactly 1
if len(filtered) == 0:
    raise DiscoveryError(failed_stage="file_matching", message="No files found")
elif len(filtered) > 1:
    raise DiscoveryError(failed_stage="file_matching", message=f"Ambiguous: {filtered}")
else:
    return filtered[0]
```

#### `ExcelReader` (Story 3.3)

**Location:** `io/readers/excel_reader.py`

**Responsibilities:**
- Load specific Excel sheet by name or index
- Handle Chinese characters, merged cells, empty rows
- Return DataFrame with raw column names

**Key Methods:**
```python
def read_sheet(
    file_path: Path,
    sheet_name: str | int,
    skip_empty_rows: bool = True
) -> ExcelReadResult:
    """
    Returns:
        ExcelReadResult(
            df: pd.DataFrame,
            sheet_name: str,
            row_count: int
        )

    Raises:
        DiscoveryError if sheet not found or file corrupted
    """
```

**Implementation:**
```python
df = pd.read_excel(
    file_path,
    sheet_name=sheet_name,
    engine='openpyxl',  # Better Unicode support
    na_values=['', ' ', 'N/A', 'NA']
)
```

#### `ColumnNormalizer` (Story 3.4)

**Location:** `utils/column_normalizer.py`

**Responsibilities:**
- Normalize column names: trim, replace full-width spaces, handle duplicates
- Pure function (no side effects)

**Key Functions:**
```python
def normalize_column_names(columns: List[str]) -> List[str]:
    """
    Normalization steps:
    1. Strip leading/trailing whitespace
    2. Replace full-width spaces (U+3000) with half-width
    3. Replace newlines/tabs with single space
    4. Replace multiple spaces with single space
    5. Handle empty names: generate 'Unnamed_1', 'Unnamed_2'
    6. Handle duplicates: append '_1', '_2' suffix
    """
```

### Data Models and Contracts

#### Configuration Models (Story 3.0)

**Location:** `config/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Literal, List

class DomainConfig(BaseModel):
    """Configuration for single domain file discovery."""
    base_path: str = Field(
        ...,
        description="Path template with {YYYYMM} placeholders"
    )
    file_patterns: List[str] = Field(
        ...,
        min_items=1,
        description="Glob patterns to match files"
    )
    exclude_patterns: List[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude"
    )
    sheet_name: str | int = Field(
        ...,
        description="Excel sheet name or 0-based index"
    )
    version_strategy: Literal['highest_number', 'latest_modified', 'manual'] = 'highest_number'
    fallback: Literal['error', 'use_latest_modified'] = 'error'

class DataSourceConfig(BaseModel):
    """Top-level configuration for all domains."""
    domains: Dict[str, DomainConfig]
```

**Validation:**
- Applied at startup in `config/settings.py`
- Fail fast on missing/invalid fields
- Prevents runtime errors

#### Result Models

**`VersionedPath` (Story 3.1):**
```python
@dataclass
class VersionedPath:
    path: Path              # Selected version path
    version: str            # "V2" or "base"
    strategy_used: str      # "highest_number", "latest_modified", "manual"
```

**`ExcelReadResult` (Story 3.3):**
```python
@dataclass
class ExcelReadResult:
    df: pd.DataFrame
    sheet_name: str
    row_count: int
```

**`DataDiscoveryResult` (Story 3.5):**
```python
@dataclass
class DataDiscoveryResult:
    df: pd.DataFrame        # Normalized DataFrame
    file_path: Path         # Selected file
    version: str            # Version used
    sheet_name: str         # Sheet loaded
    duration_ms: int        # Total discovery time
```

#### Error Models

**`DiscoveryError` (Story 3.5):**
```python
class DiscoveryError(Exception):
    """Structured error for file discovery failures."""

    def __init__(
        self,
        domain: str,
        failed_stage: Literal[
            'config_validation',
            'version_detection',
            'file_matching',
            'excel_reading',
            'normalization'
        ],
        original_error: Exception,
        message: str
    ):
        self.domain = domain
        self.failed_stage = failed_stage
        self.original_error = original_error
        super().__init__(message)
```

### APIs and Interfaces

#### Public API (Story 3.5)

**Entry Point:**
```python
from io.connectors.file_connector import FileDiscoveryService

# Initialize service
discovery = FileDiscoveryService(config_loader)

# Discover and load data
result = discovery.discover_and_load(
    domain='annuity_performance',
    month='202501',
    version_override=None  # Optional CLI override
)

# Use result
df = result.df  # Ready for Bronze validation (Epic 2)
logger.info(f"Loaded {result.file_path} version {result.version}")
```

**Configuration API:**
```python
from config.mapping_loader import load_data_source_config

# Load domain config (Story 3.0)
config = load_data_source_config('annuity_performance')
# Returns: DomainConfig with validated fields
```

#### Internal APIs (Components)

**Version Scanner:**
```python
scanner = VersionScanner()
versioned_path = scanner.detect_version(
    base_path=Path("reference/monthly/202501/收集数据/业务收集"),
    file_patterns=["*年金*.xlsx"],
    strategy=VersionStrategy.HIGHEST_NUMBER
)
```

**File Matcher:**
```python
matcher = FilePatternMatcher()
file_path = matcher.match_files(
    search_path=versioned_path.path,
    include_patterns=["*年金*.xlsx"],
    exclude_patterns=["~$*", "*回复*"]
)
```

**Excel Reader:**
```python
reader = ExcelReader()
result = reader.read_sheet(
    file_path=file_path,
    sheet_name="规模明细"
)
```

**Column Normalizer:**
```python
from utils.column_normalizer import normalize_column_names

normalized = normalize_column_names(df.columns.tolist())
df.columns = normalized
```

### Workflows and Sequencing

#### Discovery Flow (Story 3.5)

```
1. Load Configuration (Story 3.0)
   ├─> Validate YAML structure with Pydantic
   ├─> Resolve domain config for 'annuity_performance'
   └─> Fail fast if invalid

2. Resolve Template Variables
   ├─> Replace {YYYYMM} with '202501'
   └─> Construct base_path

3. Version Detection (Story 3.1)
   ├─> Scan for V1, V2, V3 folders
   ├─> Apply strategy: highest_number
   ├─> Return VersionedPath
   └─> Log: "Selected V2 (highest_number strategy)"

4. File Matching (Story 3.2)
   ├─> Apply include patterns: ["*年金*.xlsx"]
   ├─> Filter exclude patterns: ["~$*"]
   ├─> Validate exactly 1 match
   └─> Return file_path

5. Excel Reading (Story 3.3)
   ├─> Load sheet "规模明细"
   ├─> Handle merged cells, empty rows
   └─> Return DataFrame

6. Column Normalization (Story 3.4)
   ├─> Normalize column names
   ├─> Handle duplicates, empty names
   └─> Update DataFrame columns

7. Return Result
   └─> DataDiscoveryResult with all metadata
```

#### Error Handling Flow

```
At Each Stage:
try {
    execute_stage()
} catch (Exception e) {
    throw DiscoveryError(
        domain="annuity_performance",
        failed_stage="current_stage",  # version_detection, file_matching, etc.
        original_error=e,
        message="Actionable error description"
    )
}

Caller receives:
- Which domain failed
- Which stage failed
- Original exception for debugging
- Actionable message
```

## Non-Functional Requirements

### Performance

**File Discovery Speed:**
- **Target:** <10 seconds total discovery time
- **Breakdown:**
  - Version detection: <2 seconds (filesystem scan)
  - File matching: <1 second (glob pattern matching)
  - Excel reading: <5 seconds (10MB file with 10K rows)
  - Normalization: <100ms (column name processing)

**Measurement:**
- Track `duration_ms` in `DataDiscoveryResult`
- Log slow discoveries (>10s) as warnings

**Optimization:**
- Cache version detection results per month (Epic 9)
- Use `pathlib.Path.glob()` (faster than `os.walk()`)
- Read only target sheet (not entire workbook)

### Security

**Path Traversal Prevention:**
- Validate base_path doesn't contain `../`
- Restrict to `reference/` directory only
- Example:
  ```python
  if '..' in str(base_path) or not base_path.is_relative_to('reference/'):
      raise SecurityError("Invalid path: potential directory traversal")
  ```

**File Type Validation:**
- Only allow `.xlsx`, `.xlsm` extensions
- Reject `.xls` (legacy format, security concerns)

**Sanitization:**
- Log file paths but sanitize in structured logs
- Never log full file contents (may contain PII)

### Reliability

**Idempotency:**
- Same inputs → same outputs (deterministic)
- Example: `discover_and_load(domain='annuity', month='202501')` always returns same file

**Error Recovery:**
- Provide clear recovery steps in error messages
- Example: "No files found matching patterns ['*年金*.xlsx']. Check: 1) File exists in V2/, 2) Pattern includes Chinese characters"

**Validation:**
- Exactly 1 file match required (fail if 0 or >1)
- Sheet name must exist (fail if missing)
- Column normalization handles all edge cases (duplicates, empty names)

### Observability

**Structured Logging:**
```json
{
  "event": "discovery.completed",
  "domain": "annuity_performance",
  "file_path": "reference/monthly/202501/收集数据/业务收集/V2/年金数据.xlsx",
  "version": "V2",
  "sheet_name": "规模明细",
  "row_count": 1250,
  "column_count": 15,
  "duration_ms": 850
}
```

**Error Logging:**
```json
{
  "event": "discovery.failed",
  "domain": "annuity_performance",
  "failed_stage": "file_matching",
  "error_type": "DiscoveryError",
  "message": "Ambiguous match: found 2 files",
  "candidates": ["年金数据V1.xlsx", "年金数据V2.xlsx"]
}
```

## Dependencies and Integrations

### External Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| pandas | Latest (locked) | DataFrame operations |
| openpyxl | Latest (locked) | Excel file reading (`.xlsx`) |
| pydantic | 2.11.7+ | Configuration validation |
| pathlib | stdlib | Path operations |

### Internal Dependencies

**Epic 1 (Foundation):**
- Story 1.3: Structured logging
- Story 1.4: Configuration framework
- Story 1.2: CI/CD validation

**Epic 2 (Validation):**
- Bronze validation receives DataFrames from discovery

**Epic 4 (Annuity Domain):**
- Calls `discover_and_load()` in pipeline

### Integration Points

**Configuration File:**
```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns: ["*年金*.xlsx", "*规模明细*.xlsx"]
    exclude_patterns: ["~$*", "*回复*"]
    sheet_name: "规模明细"
    version_strategy: "highest_number"
    fallback: "error"
```

**Python Integration:**
```python
# domain/annuity_performance/service.py
from io.connectors.file_connector import FileDiscoveryService

def process_annuity_performance(month: str):
    # Discover and load data
    discovery = FileDiscoveryService(config_loader)
    result = discovery.discover_and_load(
        domain='annuity_performance',
        month=month
    )

    # Pass to Bronze validation (Epic 2)
    bronze_df = validate_bronze(result.df)

    # Continue pipeline...
```

## Acceptance Criteria (Authoritative)

### Story 3.0: Configuration Schema Validation

**AC1:** Given `data_sources.yml` with valid structure
**When** application starts
**Then** configuration validated with Pydantic, no errors

**AC2:** Given configuration missing required field `sheet_name`
**When** application starts
**Then** raise `ValidationError`: "Missing required field 'sheet_name'"

**AC3:** Given invalid `version_strategy` value
**When** application starts
**Then** raise `ValidationError`: "Invalid version_strategy, must be: ['highest_number', 'latest_modified', 'manual']"

### Story 3.1: Version-Aware Folder Scanner

**AC1:** Given folder with V1 and V2 subfolders
**When** scan with `highest_number` strategy
**Then** select V2, log: "Selected V2 (highest_number strategy)"

**AC2:** Given no version folders
**When** scan with fallback to base path
**Then** use base path, log: "No version folders found, using base path"

**AC3:** Given CLI override `--version=V1`
**When** scan with manual strategy
**Then** use V1 regardless of V2 existing, log: "Manual override: using V1"

### Story 3.2: Pattern-Based File Matcher

**AC1:** Given files `['年金数据.xlsx', '~$年金数据.xlsx']` with pattern `*年金*.xlsx` and exclude `~$*`
**When** match files
**Then** return `'年金数据.xlsx'` (temp file excluded)

**AC2:** Given no files matching pattern
**When** match files
**Then** raise `DiscoveryError`: "No files found matching patterns"

**AC3:** Given multiple files match
**When** match files
**Then** raise `DiscoveryError`: "Ambiguous match: Found 2 files ['file1.xlsx', 'file2.xlsx']"

### Story 3.3: Multi-Sheet Excel Reader

**AC1:** Given Excel with sheets `['Summary', '规模明细', 'Notes']` and config `sheet_name: "规模明细"`
**When** read Excel
**Then** load only '规模明细' sheet as DataFrame

**AC2:** Given sheet name doesn't exist
**When** read Excel
**Then** raise `DiscoveryError`: "Sheet '规模明细' not found, available: ['Summary', 'Notes']"

**AC3:** Given Excel has empty rows with formatting
**When** read Excel
**Then** skip empty rows, log: "Skipped 5 empty rows during load"

### Story 3.4: Column Name Normalization

**AC1:** Given columns `['月度  ', '  计划代码', '客户名称\n']`
**When** normalize
**Then** return `['月度', '计划代码', '客户名称']`

**AC2:** Given column with full-width space `'客户　名称'`
**When** normalize
**Then** return `'客户名称'` (full-width replaced, trimmed)

**AC3:** Given duplicate column names after normalization
**When** normalize
**Then** append suffix: `['月度', '月度_1', '月度_2']`, log warning

### Story 3.5: File Discovery Integration

**AC1:** Given valid domain config for annuity
**When** call `discover_and_load(domain='annuity_performance', month='202501')`
**Then** return `DataDiscoveryResult` with DataFrame, file_path, version, sheet_name, duration_ms

**AC2:** Given file matching fails
**When** discovery executes
**Then** raise `DiscoveryError` with `failed_stage='file_matching'`, actionable message

**AC3:** Given successful discovery
**When** discovery completes
**Then** log structured summary with domain, file_path, version, row_count, duration_ms

## Traceability Mapping

| AC ID | Spec Section | Component | Test Idea |
|-------|--------------|-----------|-----------|
| 3.0-AC1 | Configuration | `config/schemas.py` | Load valid `data_sources.yml`, assert no errors |
| 3.0-AC2 | Configuration | Pydantic validator | Remove `sheet_name`, expect `ValidationError` |
| 3.0-AC3 | Configuration | Pydantic validator | Set `version_strategy: 'invalid'`, expect error |
| 3.1-AC1 | Version Scanner | `VersionScanner.detect_version()` | Create V1, V2 folders, assert V2 selected |
| 3.1-AC2 | Version Scanner | Fallback logic | No version folders, assert base path used |
| 3.1-AC3 | Version Scanner | Manual override | Pass `version_override='V1'`, assert V1 used |
| 3.2-AC1 | File Matcher | `FilePatternMatcher.match_files()` | Create temp file, assert excluded |
| 3.2-AC2 | File Matcher | Error handling | Empty folder, expect `DiscoveryError` |
| 3.2-AC3 | File Matcher | Ambiguity detection | Create 2 matching files, expect error |
| 3.3-AC1 | Excel Reader | `ExcelReader.read_sheet()` | Load sheet by name, assert DataFrame |
| 3.3-AC2 | Excel Reader | Sheet not found | Request missing sheet, expect error |
| 3.3-AC3 | Excel Reader | Empty row handling | Excel with empty rows, assert skipped |
| 3.4-AC1 | Normalizer | `normalize_column_names()` | Columns with whitespace, assert trimmed |
| 3.4-AC2 | Normalizer | Full-width handling | Column with `'　'`, assert replaced |
| 3.4-AC3 | Normalizer | Duplicate handling | Duplicate names, assert suffix added |
| 3.5-AC1 | Integration | `FileDiscoveryService.discover_and_load()` | End-to-end, assert result object |
| 3.5-AC2 | Integration | Error propagation | Simulate file matching failure, assert `DiscoveryError` |
| 3.5-AC3 | Integration | Logging | Success case, assert structured log |

## Risks, Assumptions, Open Questions

### Risks

**R0: Real Data Validation Dependency (RESOLVED ✅)**
- **Impact:** CRITICAL (was blocking)
- **Status:** ✅ **RESOLVED** on 2025-11-27
- **Description:** Tech-spec required real data validation (Action Item #2) before finalization.
- **Epic 2 Precedent:** Model/data mismatches caused 87.5% integration test failures in Story 2.5.
- **Resolution:**
  - ✅ Action Item #2 completed and documented
  - ✅ Analysis report: `docs/sprint-artifacts/auxiliary/action-item-2-real-data-analysis.md`
  - ✅ Tech-spec updated with real data findings
  - ✅ **Path corrected:** `业务收集` → `数据采集`
  - ✅ **Pattern corrected:** `*年金*.xlsx` → `*年金终稿*.xlsx`
- **Result:** Epic 3 development READY TO PROCEED

**R1: Cross-Platform Path Encoding**
- **Impact:** High
- **Likelihood:** Medium
- **Description:** Chinese characters in paths may behave differently on Windows vs Linux
- **Mitigation:**
  - Test on both Windows and Linux in CI
  - Use `pathlib.Path` for cross-platform compatibility
  - Explicitly handle UTF-8 encoding

**R2: Excel File Corruption**
- **Impact:** High
- **Likelihood:** Low
- **Description:** Corrupted Excel files may crash reader or produce partial data
- **Mitigation:**
  - Wrap Excel reading in try-except
  - Validate row count against expected minimum
  - Export failed files to quarantine folder for manual inspection

**R3: Version Detection Ambiguity**
- **Impact:** Medium
- **Likelihood:** Medium
- **Description:** V1 and V2 modified on same day, unclear which to use
- **Mitigation:**
  - Raise clear error requiring manual resolution
  - Support CLI override: `--version=V1`
  - Document precedence rules in runbook

### Assumptions

**A1: File System Access**
- Assume local filesystem access to `reference/monthly/` directory
- No cloud storage (S3, Azure Blob) support in MVP

**A2: Excel Format**
- Assume `.xlsx` or `.xlsm` format (Office 2007+)
- No `.xls` (legacy Office 97-2003) support

**A3: Sheet Naming**
- Assume sheet names are stable (not changing month-to-month)
- If sheet name changes, configuration must be updated

**A4: Version Frequency**
- Assume max 5 versions per month (V1-V5)
- If more versions, update regex pattern `V\d+` → `V\d{1,2}`

### Open Questions

**Q1: Should version detection cache results?**
- **Context:** Same month scanned multiple times in testing/debugging
- **Decision:** Defer caching to Epic 9 (optimization phase)
- **Rationale:** Premature optimization, filesystem scan is fast enough (<2s)

**Q2: How to handle `.xlsm` (macro-enabled) files?**
- **Context:** Some domains may use macro-enabled workbooks
- **Decision:** Support `.xlsm` via openpyxl (macros ignored, data preserved)
- **Validation:** Test with sample `.xlsm` file in integration tests

**Q3: What if {YYYYMM} placeholder incorrect?**
- **Context:** User passes `month='invalid'` to `discover_and_load()`
- **Decision:** Validate month format: `^\d{6}$` (YYYYMM)
- **Error:** Raise `ValueError` with expected format

## Test Strategy Summary

### Unit Tests (Fast, Isolated)

**Story 3.0: Configuration Validation**
- Valid config → passes
- Missing fields → ValidationError
- Invalid enum values → ValidationError

**Story 3.1: Version Scanner**
- V1, V2 exist → V2 selected
- No versions → base path used
- Manual override → override respected

**Story 3.2: File Matcher**
- Single match → file returned
- No matches → DiscoveryError
- Multiple matches → DiscoveryError
- Exclusion patterns → temp files filtered

**Story 3.4: Column Normalizer**
- Whitespace → trimmed
- Full-width spaces → replaced
- Duplicates → suffixed
- Empty names → placeholder generated

### Integration Tests (Moderate Speed)

**Story 3.3: Excel Reader**
- Read sheet by name → DataFrame
- Read sheet by index → DataFrame
- Missing sheet → DiscoveryError
- Chinese characters preserved → verified

**Story 3.5: End-to-End Discovery**
- Valid config + files → DataDiscoveryResult
- Missing file → DiscoveryError with stage
- Corrupted Excel → DiscoveryError
- Full pipeline (version → match → read → normalize) → success

### Edge Case Tests

**Chinese Character Handling:**
- Filenames with Chinese characters
- Column names with Chinese characters
- Full-width vs half-width characters

**Error Cases:**
- File not found
- Sheet not found
- Ambiguous version detection
- Multiple file matches
- Corrupted Excel
- Invalid configuration

**Performance Tests:**
- 10MB Excel file (10K rows) → <5s read time
- Full discovery → <10s total time
- Measure and log all stages

### Test Data

**Fixtures Required:**
- Sample Excel files: valid, corrupted, macro-enabled
- Sample folder structures: V1 only, V1+V2, no versions
- Sample configurations: valid, invalid, edge cases
- Chinese character test data: filenames, column names, cell values

### Code Review Strategy

**Lesson from Epic 2:** Two-round code reviews caught critical issues in Stories 2.4 and 2.5.

**Epic 3 Code Review Requirements:**

**First Review Round:**
- ✅ All acceptance criteria (AC) met
- ✅ Unit tests pass with >80% coverage
- ✅ Integration tests use realistic fixtures (based on Action Item #2)
- ✅ Performance tests meet NFR targets (<10s discovery)
- ✅ Code follows architecture patterns (Clean Architecture boundaries)
- ✅ Structured error handling with stage markers (DiscoveryError)
- ✅ Documentation updated (docstrings, README)

**Common Issues to Catch (Epic 2 Lessons):**
- Missing performance tests
- Integration test failures due to unrealistic fixtures
- Documentation status inconsistencies
- Missing edge case coverage

**Second Review Round (if needed):**
- ✅ All first review issues resolved
- ✅ Integration test pass rate >75% (6/8 minimum)
- ✅ Performance regression check (no >20% slowdown)
- ✅ Final approval by senior developer

**Review Efficiency:**
- Cost: ~20% more time for second round
- Benefit: Prevents production defects, catches architectural issues early
- ROI: Proven valuable in Epic 2 (87.5% test failure rate caught and fixed)

---

## Post-Review Follow-ups

This section tracks action items identified during code reviews for Epic 3 stories.

### Story 3.1: Version-Aware Folder Scanner

**Review Date:** 2025-11-28
**Reviewer:** Link
**Outcome:** BLOCKED
**Status:** Awaiting fixes

**Critical Issues (8 items):**

1. **[HIGH]** Add missing import `from datetime import datetime` in test file
   - File: tests/unit/io/connectors/test_version_scanner.py:1
   - Impact: NameError in test_versionedpath_contains_all_required_fields
   - Story: 3.1

2. **[HIGH]** Fix invalid directory touch() operations in tests
   - Files: tests/unit/io/connectors/test_version_scanner.py lines 110, 273-292
   - Impact: TypeError - cannot call touch() on directory paths
   - Story: 3.1

3. **[HIGH]** Fix timestamp race conditions in latest_modified tests
   - Files: tests/unit:56-76, tests/integration:41-74
   - Impact: Ambiguity detection triggers unexpectedly, 2 tests fail
   - Fix: Touch files BEFORE creating version directories OR increase sleep >1s
   - Story: 3.1

4. **[HIGH]** Implement complete rejected_versions metadata
   - File: src/work_data_hub/io/connectors/version_scanner.py:149-152
   - Impact: AC #1 requirement not fully met - missing filtered versions with reasons
   - Fix: Include ALL scanned versions with filter reasons
   - Story: 3.1

5. **[MEDIUM]** Add platform detection for Windows-incompatible tests
   - Files: tests/unit:320-346, tests/integration:184-207
   - Impact: 2 tests fail on Windows (chmod, leading/trailing space paths)
   - Fix: Skip on Windows or use platform-specific handling
   - Story: 3.1

6. **[MEDIUM]** Remove or adjust test_invalid_strategy_raises_error
   - File: tests/unit/io/connectors/test_version_scanner.py:212-228
   - Impact: Type system already prevents invalid strategies at compile time
   - Fix: Remove test or adjust to test runtime validation path
   - Story: 3.1

7. **[HIGH]** Correct Change Log false statement
   - File: docs/sprint-artifacts/stories/3-1-version-aware-folder-scanner.md:702
   - Impact: States "All tests passing" but 9/26 tests failing (34.6% failure rate)
   - Fix: Update to reflect actual test status
   - Story: 3.1

8. **[CRITICAL]** Fix ALL 9 failing tests before story approval
   - Test Status: 17/26 PASSED, 9/26 FAILED (34.6% failure rate)
   - Breakdown: 6 unit tests failing, 3 integration tests failing
   - Blocker: Story cannot be approved until 100% tests passing
   - Story: 3.1

**Advisory Items:**

- Consider extracting timestamp tolerance (1 second) as configuration parameter for future flexibility
- VERSION_PATTERN could support V0 if needed (currently rejects per spec)
- Performance requirement (<2 seconds) verified passing with 50 versions

**Stories Likely Requiring Two Rounds (based on Epic 2 patterns):**
- Story 3.3: Excel Reader (integration complexity)
- Story 3.5: File Discovery Integration (end-to-end orchestration)
