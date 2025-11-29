# WorkDataHub Scale Adaptive Architecture

**Document Version:** 1.0
**Date:** 2025-11-09
**Project:** WorkDataHub - Internal Data Platform
**Architect:** Winston (BMAD Method)
**Status:** ✅ Approved for Implementation

---

## Executive Summary

This architecture defines the technical foundation for WorkDataHub, a brownfield migration project transforming a monolithic legacy ETL system into a modern, declarative, testable data platform. The architecture supports **10 epics with 100+ user stories** across MVP (Phase 1) and Growth (Phase 2) phases.

**Key Architectural Decisions:**
1. **File-Pattern-Aware Version Detection** - Intelligent version selection scoped per domain
2. **Legacy-Compatible Temporary Company IDs** - HMAC-based stable IDs with normalization parity
3. **Hybrid Pipeline Step Protocol** - Support both DataFrame and row-level transformations
4. **Hybrid Error Context Standards** - Structured exceptions with required context fields
5. **Explicit Chinese Date Format Priority** - Predictable parsing without fallback surprises
6. **Stub-Only Enrichment MVP** - Defer complex enrichment to Growth phase
7. **Comprehensive Naming Conventions** - Chinese Pydantic fields, English database columns
8. **structlog with Sanitization** - True structured logging with sensitive data protection

**Architecture Type:** Brownfield - Strangler Fig migration pattern with 100% legacy parity requirement

---

## Table of Contents

1. [Technology Stack](#technology-stack)
2. [Architectural Decisions](#architectural-decisions)
3. [Novel Patterns](#novel-patterns)
4. [Implementation Patterns](#implementation-patterns)
5. [Integration Architecture](#integration-architecture)
6. [Non-Functional Requirements](#non-functional-requirements)
7. [Migration Strategy](#migration-strategy)
8. [Appendices](#appendices)

---

## Technology Stack

### Core Technologies (Locked In - Brownfield)

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| **Language** | Python | 3.10+ | Corporate standard, type system maturity |
| **Package Manager** | uv | Latest | 10-100x faster than pip, deterministic locks |
| **Orchestration** | Dagster | Latest | Definitions ready, CLI-first execution for MVP |
| **Data Validation** | Pydantic | 2.11.7+ | Row-level validation, type safety, performance |
| **DataFrame Library** | pandas | Latest (locked) | Team expertise, ecosystem maturity |
| **Database** | PostgreSQL | Corporate std | Transactional guarantees, JSON support |
| **Spreadsheet I/O** | openpyxl | Latest (locked) | Multi-sheet Excel reading |
| **Type Checking** | mypy | 1.17.1+ (strict) | 100% type coverage NFR |
| **Linting/Formatting** | Ruff | 0.12.12+ | Replaces black + flake8 + isort, 10-100x faster |
| **Testing** | pytest | Latest | Custom markers for postgres/legacy/monthly |
| **Structured Logging** | structlog | Latest | **Decision #8:** True structured logging |
| **Schema Validation** | pandera | Latest | DataFrame-level schemas (Bronze/Gold) |

### Architecture Patterns (Locked In - Brownfield)

| Pattern | Description | Epic Application |
|---------|-------------|------------------|
| **Medallion (Bronze→Silver→Gold)** | Layered data quality progression | Epic 2 (Validation), Epic 4 (Annuity) |
| **Strangler Fig** | Gradual legacy replacement with parity | Epic 4, 9 (Domain migrations) |
| **Configuration-Driven Discovery** | YAML-based file discovery | Epic 3 (File Discovery) |
| **Provider Protocol** | Abstraction for enrichment sources | Epic 5 (Enrichment - deferred to Growth) |

---

## Architectural Decisions

### Decision #1: File-Pattern-Aware Version Detection ✅

**Problem:** Monthly data arrives in versioned folders (V1, V2, V3). Different domains may have corrections at different version levels. Need automatic selection without data loss.

**Decision:** Version detection scoped to each domain's file patterns, not folder-level.

#### Algorithm

```python
def detect_version(base_path: Path, file_patterns: List[str]) -> Path:
    """
    Returns the versioned path where files matching patterns exist.
    Scopes version detection to specific file patterns, not entire folder.
    """
    # 1. Discover all version folders
    version_folders = sorted([v for v in base_path.glob("V*") if v.is_dir()],
                            reverse=True)  # V3, V2, V1

    # 2. For each version (highest first), check if ANY file pattern matches
    for version_folder in version_folders:
        for pattern in file_patterns:
            matches = list(version_folder.glob(pattern))
            if matches:
                return version_folder  # First version with matching file wins

    # 3. Fallback: no versioned folders have matching files → use base path
    return base_path
```

#### Decision Rules

1. Scan for folders matching pattern `V\d+` (V1, V2, V3, etc.)
2. For each domain's file patterns, iterate versions from highest to lowest
3. Select **first version where a matching file exists** (per domain)
4. If no versioned folders contain matching files → fall back to base path
5. If multiple files match pattern in same version → ERROR (ambiguous, refine pattern)
6. Manual override: Support `--version=V1` CLI flag for debugging

#### Example Scenario

**File Structure:**
```
reference/monthly/202501/收集数据/业务收集/
├── V1/
│   ├── 年金数据.xlsx        ← Annuity (original)
│   ├── 业务收集.xlsx        ← Business collection
│   └── 投资数据.xlsx        ← Investment
└── V2/
    └── 年金数据.xlsx        ← ONLY annuity corrected
```

**Results:**

| Domain | File Pattern | Selected Version | File Found |
|--------|--------------|------------------|------------|
| annuity_performance | `*年金*.xlsx` | V2 | `V2/年金数据.xlsx` |
| business_collection | `*业务*.xlsx` | V1 | `V1/业务收集.xlsx` |
| investment_data | `*投资*.xlsx` | V1 | `V1/投资数据.xlsx` |

#### Logging

```json
{
  "event": "version_detection.completed",
  "domain": "annuity_performance",
  "base_path": "reference/monthly/202501/收集数据/业务收集",
  "file_patterns": ["*年金*.xlsx"],
  "versions_scanned": ["V2", "V1"],
  "selected_version": "V2",
  "selected_file": "V2/年金数据.xlsx",
  "strategy": "highest_version_with_matching_file"
}
```

#### Implementation (Epic 3 Story 3.1)

- **Module:** `io/connectors/file_connector.py`
- **Return Type:** `VersionedPath` dataclass: `path`, `version`, `strategy_used`
- **Configuration:** `config/data_sources.yml` per domain
- **Integration:** Epic 3 Story 3.5 (File Discovery Integration)

---

### Decision #2: Legacy-Compatible Temporary Company ID Generation ✅

**Problem:** Company names vary across Excel sources. When enrichment service can't resolve to official IDs, need stable temporary IDs for cross-domain joins.

**Decision:** HMAC-SHA1 based temporary IDs with legacy-compatible normalization.

#### Business Key Composition

**Decision:** Company name only (no domain context)
**Rationale:** Enables cross-domain joins (same company → same temp ID across domains)

#### Normalization Strategy

**Based on:** `legacy/annuity_hub/common_utils/common_utils.py::clean_company_name`

**Operations (in order):**
1. **Remove all whitespace:** `re.sub(r'\s+', '', name)`
2. **Remove business patterns:** `"及下属子企业"`, trailing `(团托)`, `-A`, `-123`, `-养老`, `-福利`
3. **Remove status markers:** 29 patterns (`已转出`, `待转出`, `终止`, `转出`, `保留`, etc.)
4. **Full-width → Half-width:** `"公司Ａ"` → `"公司A"`
5. **Normalize brackets:** `'(' → '（'`, `')' → '）'`
6. **Lowercase** (NEW - not in legacy): Ensures case-insensitive matching

#### Implementation

```python
def normalize_for_temp_id(company_name: str) -> str:
    """
    Normalize company name for temporary ID generation.
    Uses legacy-compatible normalization to ensure consistency.

    Based on: legacy/annuity_hub/common_utils/common_utils.py::clean_company_name
    """
    if not company_name:
        return ''

    name = company_name

    # 1. Remove all whitespace
    name = re.sub(r'\s+', '', name)

    # 2. Remove business-specific patterns
    name = re.sub(r'及下属子企业', '', name)
    name = re.sub(r'(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$', '', name)

    # 3. Remove status markers (from CORE_REPLACE_STRING)
    for core_str in CORE_REPLACE_STRING_SORTED:
        pattern_start = rf'^([\(\（]?){re.escape(core_str)}([\)\）]?)(?=[^\u4e00-\u9fff]|$)'
        name = re.sub(pattern_start, '', name)

        pattern_end = rf'(?<![\u4e00-\u9fff])([\-\(\（]?){re.escape(core_str)}([\)\）]?)[\-\(\（\)\）]*$'
        name = re.sub(pattern_end, '', name)

    # 4. Remove trailing punctuation
    name = re.sub(r'[\-\(\（\)\）]+$', '', name)

    # 5. Full-width → Half-width conversion
    name = ''.join([
        chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
        for char in name
    ])

    # 6. Normalize brackets to Chinese
    name = name.replace('(', '（').replace(')', '）')

    # 7. Lowercase for hash stability (NEW)
    name = name.lower()

    return name


def generate_temp_company_id(company_name: str, salt: str) -> str:
    """
    Generate stable temporary company ID.

    Format: IN_<16-char-Base32>
    Algorithm: HMAC-SHA1 (more secure than legacy MD5)
    """
    normalized = normalize_for_temp_id(company_name)

    # HMAC-SHA1 with secret salt
    digest = hmac.new(
        salt.encode('utf-8'),
        normalized.encode('utf-8'),
        hashlib.sha1
    ).digest()

    # Take first 80 bits (10 bytes), Base32 encode → 16 chars
    encoded = base64.b32encode(digest[:10]).decode('ascii')

    return f"IN_{encoded}"
```

#### Decision Table

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Business Key** | Normalized company name only | Enable cross-domain joins |
| **Normalization** | Legacy-compatible + `.lower()` | Maintain parity with existing cleansing |
| **Hash Algorithm** | HMAC-SHA1 (not MD5) | More secure, cryptographically sound |
| **ID Format** | `IN_<16-char-Base32>` | Distinguishable from legacy GM/GC codes |
| **Salt Management** | `WDH_ALIAS_SALT` env var | Must be secret, consistent across environments |

#### Security & Configuration

```bash
# .env (gitignored)
WDH_ALIAS_SALT="<32+ character random string>"  # Required, must be secret
```

**Security Notes:**
- Salt must be 32+ characters random string
- Same salt across all environments for ID consistency
- If salt lost/changed, all temporary IDs become different (document in runbook)
- Never commit salt to git (validate with gitleaks in CI)

#### Implementation (Epic 5 Story 5.2)

- **Module:** `utils/company_normalizer.py`
- **Extract:** `CORE_REPLACE_STRING` → `cleansing/config/status_markers.py`
- **Integration:** `EnrichmentGateway` calls when lookup fails (Epic 5 Story 5.5)
- **Testing:** Parity tests with legacy normalization using golden datasets

---

### Decision #3: Hybrid Pipeline Step Protocol ✅

**Problem:** Need formal contract for 100+ transformation steps. Brownfield uses row-level processing, but PRD shows DataFrame-level operations. Conflict between performance (DataFrame) and validation (row-level).

**Decision:** Support both DataFrame-level and Row-level steps with clear protocols.

#### Dual Protocol Architecture

**DataFrame Steps (Bulk Operations):**
```python
class DataFrameStep(Protocol):
    """Bulk DataFrame transformation for performance."""

    def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """
        Transform entire DataFrame (vectorized operations).

        Args:
            df: Input DataFrame
            context: Execution context with domain, execution_id, shared state

        Returns:
            Transformed DataFrame
        """
        ...
```

**Row Transform Steps (Validation & Enrichment):**
```python
class RowTransformStep(Protocol):
    """Per-row transformation with detailed error tracking."""

    def apply(self, row: Row, context: Dict) -> StepResult:
        """
        Transform single row with validation and enrichment.

        Args:
            row: Input data row (dict-like)
            context: Execution context and shared state

        Returns:
            StepResult containing transformed row, warnings, errors, metadata
        """
        ...
```

**Pipeline Integration:**
```python
class Pipeline:
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute mixed DataFrame and row-level steps."""
        for step in self.steps:
            if isinstance(step, DataFrameStep):
                df = step.execute(df, self.context)  # Bulk
            elif isinstance(step, RowTransformStep):
                df = self._apply_row_step(step, df, self.context)  # Iterate
        return df
```

#### Usage Guidelines

**Use DataFrame Steps For:**
- Structural operations: add columns, filter rows, join DataFrames
- Pandera validation (Bronze/Gold schemas)
- Bulk calculations: sums, aggregations, rolling windows
- Database loading (Epic 1 Story 1.8)

**Use Row Steps For:**
- Pydantic validation (Silver layer, per-row business rules)
- Company enrichment (external API calls per company)
- Complex per-row logic (date parsing with fallbacks)
- Error collection with per-row attribution

**Recommended Pipeline Order:**
1. DataFrame steps first (fast bulk operations)
2. Row steps in middle (validation, enrichment)
3. DataFrame steps last (final projection, database load)

#### Example: Annuity Pipeline (Epic 4 Story 4.3)

```python
pipeline = Pipeline("annuity_performance")

# Bronze Layer - DataFrame (fast bulk operations)
pipeline.add_step(BronzeValidationStep())        # pandera schema
pipeline.add_step(ParseDatesStep())              # bulk date parsing
pipeline.add_step(CleanseCompanyNamesStep())     # bulk regex normalization

# Silver Layer - Row (validation & enrichment)
pipeline.add_step(ValidateInputRowsStep())       # Pydantic per-row validation
pipeline.add_step(EnrichCompanyIDsStep())        # External API lookup

# Gold Layer - DataFrame (projection & validation)
pipeline.add_step(ValidateOutputRowsStep())      # Pydantic business rules
pipeline.add_step(GoldProjectionStep())          # Column selection
pipeline.add_step(GoldValidationStep())          # pandera Gold schema
pipeline.add_step(LoadToWarehouseStep())         # Database insert

result_df = pipeline.run(bronze_df)
```

#### Implementation (Epic 1 Stories 1.5 & 1.10)

- **Story 1.5:** Basic Pipeline with both step types
- **Story 1.10:** Advanced features (retries, optional steps, metrics)
- **Preserve:** Existing brownfield `RowTransformStep` code
- **Apply:** All domain pipelines (Epic 4, 9) follow this pattern

#### Shared Steps Directory (Story 4.7)

Generic transformation steps are extracted to `domain/pipelines/steps/` for reuse across domains:

**Directory Structure:**
```
src/work_data_hub/domain/pipelines/
├── steps/                          # Shared transformation steps
│   ├── __init__.py                 # Public exports
│   ├── column_normalization.py     # ColumnNormalizationStep
│   ├── date_parsing.py             # DateParsingStep
│   ├── customer_name_cleansing.py  # CustomerNameCleansingStep
│   └── field_cleanup.py            # FieldCleanupStep
├── core.py                         # Pipeline class
├── types.py                        # Step protocols
└── config.py                       # Pipeline configuration
```

**Available Shared Steps:**

| Step | Purpose | Protocol |
|------|---------|----------|
| `ColumnNormalizationStep` | Normalize legacy column names to standard format | `RowTransformStep` |
| `DateParsingStep` | Parse and standardize date fields (YYYYMM, Chinese formats) | `RowTransformStep` |
| `CustomerNameCleansingStep` | Clean customer names using cleansing registry | `RowTransformStep` |
| `FieldCleanupStep` | Remove invalid columns and finalize record structure | `RowTransformStep` |

**Usage in Domain Pipelines:**
```python
from work_data_hub.domain.pipelines.steps import (
    ColumnNormalizationStep,
    DateParsingStep,
    CustomerNameCleansingStep,
    FieldCleanupStep,
)

def build_domain_pipeline(mappings: Dict[str, Any]) -> Pipeline:
    """Build pipeline using shared steps + domain-specific steps."""
    steps = [
        # Shared steps (from domain/pipelines/steps/)
        ColumnNormalizationStep(),
        DateParsingStep(),
        CustomerNameCleansingStep(),
        FieldCleanupStep(),
        # Domain-specific steps (in domain/{domain_name}/)
        DomainSpecificValidationStep(),
        DomainSpecificEnrichmentStep(mappings),
    ]
    return Pipeline(steps=steps)
```

**Adding New Shared Steps:**
1. Create step file in `domain/pipelines/steps/`
2. Implement `RowTransformStep` or `DataFrameStep` protocol
3. Export from `__init__.py`
4. Add unit tests in `tests/unit/domain/pipelines/steps/`

---

### Decision #4: Hybrid Error Context Standards ✅

**Problem:** 100+ stories need consistent error messages with sufficient context for debugging. Without standards, errors lack actionable information.

**Decision:** Use exceptions with required structured context fields.

#### Standard Error Format

```
[ERROR_TYPE] Base message | Domain: X | Row: N | Field: Y | Input: {...}
```

#### Required Context Fields

| Field | Required? | Purpose |
|-------|-----------|---------|
| `error_type` | ✅ Always | Category for aggregation/monitoring |
| `operation` | ✅ Always | Which function/step failed |
| `message` | ✅ Always | Human-readable description |
| `domain` | When applicable | Which domain pipeline |
| `row_number` | For row-level errors | CSV line number (1-indexed) |
| `field` | For validation errors | Which column/field failed |
| `input_data` | When helpful | Sanitized input (no secrets/PII) |
| `original_error` | When wrapping | Underlying exception message |

#### Implementation

```python
@dataclass
class ErrorContext:
    """Standard error context for all WorkDataHub operations."""
    error_type: str  # "ValidationError", "DiscoveryError", "EnrichmentError"
    operation: str   # "validate_row", "discover_file", "enrich_company"
    domain: Optional[str] = None
    row_number: Optional[int] = None
    field: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None  # Sanitized (no PII/secrets)
    original_error: Optional[str] = None

def create_error_message(base_message: str, context: ErrorContext) -> str:
    """Generate actionable error message with context."""
    parts = [f"[{context.error_type}] {base_message}"]

    if context.domain:
        parts.append(f"Domain: {context.domain}")
    if context.row_number:
        parts.append(f"Row: {context.row_number}")
    if context.field:
        parts.append(f"Field: {context.field}")
    if context.input_data:
        parts.append(f"Input: {context.input_data}")

    return " | ".join(parts)

# Usage
try:
    validate_date(value)
except ValueError as e:
    context = ErrorContext(
        error_type="ValidationError",
        operation="validate_date",
        domain="annuity_performance",
        row_number=15,
        field="月度",
        input_data={"value": value},
        original_error=str(e)
    )
    raise ValidationError(
        create_error_message("Cannot parse date", context),
        context=context
    ) from e
```

#### Example Error Messages

```
[ValidationError] Cannot parse '不是日期' as date, expected format: YYYYMM, YYYY年MM月, YYYY-MM | Domain: annuity_performance | Row: 15 | Field: 月度 | Input: {"value": "不是日期"}

[DiscoveryError] No files found matching patterns ['*年金*.xlsx'] in path reference/monthly/202501/收集数据/业务收集/V2 | Domain: annuity_performance | Stage: file_matching

[EnrichmentError] Company lookup failed: API timeout after 5000ms | Domain: annuity_performance | Row: 42 | Field: 客户名称 | Input: {"company_name": "公司A有限公司"}
```

#### Integration Points

- **Epic 2 Story 2.5:** Failed row CSV export uses `ErrorContext` fields
- **Epic 3 Story 3.5:** Discovery errors include `failed_stage` context
- **Epic 8:** Structured logging consumes `ErrorContext` for monitoring

---

### Decision #5: Explicit Chinese Date Format Priority ✅

**Problem:** Excel files contain dates in wildly inconsistent formats. Need predictable parsing without dateutil fallback surprises.

**Decision:** Explicit format priority list with full-width normalization and range validation (2000-2030). No fallback.

#### Supported Formats (Priority Order)

1. `date`/`datetime` objects → Passthrough
2. `YYYYMMDD` (8 digits) → `date(YYYY, MM, DD)`
3. `YYYYMM` (6 digits) → `date(YYYY, MM, 1)` (first day of month)
4. `YYYY-MM-DD` → ISO full date
5. `YYYY-MM` → `date(YYYY, MM, 1)`
6. `YYYY年MM月DD日` → Chinese full date
7. `YYYY年MM月` → `date(YYYY, MM, 1)`
8. `YY年MM月` → `date(20YY, MM, 1)` if YY < 50, else `date(19YY, MM, 1)`

#### Implementation

```python
def parse_yyyymm_or_chinese(value: Any) -> date:
    """
    Parse date with explicit format priority.

    Supports: YYYYMM, YYYYMMDD, YYYY年MM月, YYYY年MM月DD日, YYYY-MM, YYYY-MM-DD, YY年MM月
    Validates: 2000 <= year <= 2030

    Args:
        value: Date input (int, str, date, datetime)

    Returns:
        Parsed date object

    Raises:
        ValueError: If format unsupported or date out of range
    """
    # 0. Passthrough for date objects
    if isinstance(value, (date, datetime)):
        result = value.date() if isinstance(value, datetime) else value
        return _validate_date_range(result, 2000, 2030)

    # 1. Normalize full-width digits (０-９ → 0-9)
    s = _normalize_fullwidth_digits(str(value))

    # 2. Try formats in priority order (explicit, no fallback)
    parsers = [
        (r'^\d{8}$', '%Y%m%d'),           # 20250115
        (r'^\d{6}$', '%Y%m01'),           # 202501 → 20250101
        (r'^\d{4}-\d{2}-\d{2}$', '%Y-%m-%d'),
        (r'^\d{4}-\d{2}$', '%Y-%m-01'),
        (r'^\d{4}年\d{1,2}月\d{1,2}日$', '%Y年%m月%d日'),
        (r'^\d{4}年\d{1,2}月$', '%Y年%m月1日'),
        (r'^\d{2}年\d{1,2}月$', '%y年%m月1日'),  # 25年1月 → 2025年1月1日
    ]

    for pattern, fmt in parsers:
        if re.match(pattern, s):
            result = datetime.strptime(s, fmt).date()
            return _validate_date_range(result, 2000, 2030)

    # No fallback - explicit error
    raise ValueError(
        f"Cannot parse '{value}' as date. "
        f"Supported formats: YYYYMM, YYYYMMDD, YYYY年MM月, YYYY年MM月DD日, "
        f"YYYY-MM, YYYY-MM-DD, YY年MM月 (2-digit year)"
    )

def _normalize_fullwidth_digits(s: str) -> str:
    """Convert full-width digits (０-９) to half-width (0-9)."""
    trans = str.maketrans('０１２３４５６７８９', '0123456789')
    return s.translate(trans)

def _validate_date_range(d: date, min_year: int = 2000, max_year: int = 2030) -> date:
    """Validate date is within acceptable range."""
    if not (min_year <= d.year <= max_year):
        raise ValueError(
            f"Date {d.year}-{d.month:02d} outside valid range {min_year}-{max_year}"
        )
    return d
```

#### Integration Points

- **Epic 2 Story 2.4:** Implement as `utils/date_parser.py`
- **Epic 4 Story 4.1:** Annuity Pydantic models use `@field_validator('月度')`
- **Testing:** Parity tests with legacy `parse_to_standard_date` for known edge cases

---

### Decision #6: Stub-Only Enrichment MVP ✅

**Problem:** Epic 5 defines sophisticated company enrichment with 8 stories. Risk: blocks Epic 4 annuity migration, adds complexity.

**Decision:** Defer real enrichment to Growth phase. MVP uses StubProvider + temporary IDs only.

#### MVP Scope (Epic 5)

**Implemented Stories:**
- ✅ Story 5.1: `StubProvider` with test fixtures
- ✅ Story 5.2: Temporary ID generation (Decision #2)
- ✅ Story 5.5: `EnrichmentGateway` shell (stub + temp ID fallback only)

**Result:** All companies get temporary IDs in MVP

#### Growth Phase (Epic 9-10)

**Deferred Stories:**
- Story 5.3: Full database schema (3 tables)
- Story 5.4: Multi-tier internal mapping resolver
- Story 5.6: Sync EQC API provider (budget-limited, token management)
- Story 5.7: Async enrichment queue (deferred resolution)
- Story 5.8: Observability & metrics (CSV export, cache hit rates)

**Result:** Backfill job resolves MVP temporary IDs to real company IDs

#### MVP Implementation

```python
class StubProvider(EnterpriseInfoProvider):
    """MVP: Offline fixtures for testing (no external dependencies)."""
    def __init__(self, fixtures: Dict[str, CompanyInfo]):
        self.fixtures = fixtures

    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        normalized = normalize_company_name(company_name)
        return self.fixtures.get(normalized)

class EnrichmentGateway:
    """MVP: Stub fixtures + temporary ID fallback (no EQC API)."""
    def __init__(self, stub_provider: StubProvider, salt: str):
        self.stub = stub_provider
        self.salt = salt

    def enrich(self, company_name: str) -> CompanyInfo:
        # 1. Try stub fixtures
        result = self.stub.lookup(company_name)
        if result:
            return result

        # 2. Generate temporary ID (Decision #2)
        temp_id = generate_temp_company_id(company_name, self.salt)
        return CompanyInfo(
            company_id=temp_id,
            official_name=company_name,
            confidence=0.0,
            match_type="temporary"
        )
```

#### Configuration

```bash
# MVP .env
WDH_ENRICH_COMPANY_ID=0  # Disabled
WDH_COMPANY_ENRICHMENT_ENABLED=0  # Stub only

# Growth .env (Epic 9-10)
WDH_ENRICH_COMPANY_ID=1  # Enabled
WDH_PROVIDER_EQC_TOKEN=<token>
WDH_ENRICH_SYNC_BUDGET=5
```

#### Rationale

1. **MVP Goal:** Prove core patterns (Bronze→Silver→Gold, validation, Strangler Fig)
2. **Enrichment is orthogonal:** Temporary IDs enable cross-domain joins (requirement met)
3. **Risk reduction:** Defer EQC complexity (30-min token expiry, captcha, rate limits)
4. **Faster to market:** Epic 4 annuity migration unblocked immediately
5. **Growth value:** Full enrichment becomes competitive advantage, not MVP blocker

---

### Decision #7: Comprehensive Naming Conventions ✅

**Problem:** 100+ stories will create thousands of code artifacts. Without naming standards, AI agents will create inconsistent code.

**Decision:** Follow PEP 8 conventions with special handling for Chinese field names.

#### Naming Standards Table

| Category | Standard | Example | Rationale |
|----------|----------|---------|-----------|
| **Python Files** | `snake_case.py` | `file_connector.py` | PEP 8, brownfield compatibility |
| **Python Modules** | `snake_case/` | `domain/pipelines/` | PEP 8, brownfield compatibility |
| **Classes** | `PascalCase` | `EnrichmentGateway` | PEP 8, brownfield compatibility |
| **Functions/Methods** | `snake_case` | `generate_temp_company_id` | PEP 8, brownfield compatibility |
| **Variables** | `snake_case` | `company_name`, `temp_id` | PEP 8, brownfield compatibility |
| **Constants** | `UPPER_SNAKE_CASE` | `CORE_REPLACE_STRING` | PEP 8, brownfield compatibility |
| **Type Aliases** | `PascalCase` | `Row`, `PipelineContext` | PEP 8 convention |
| **Pydantic Fields** | **Original Chinese** | `月度`, `计划代码` | **Match Excel sources exactly** |
| **Database Tables** | `lowercase_snake_case` | `annuity_performance`, `company_master` | PostgreSQL convention |
| **Database Columns** | `lowercase_snake_case` | `company_id`, `reporting_month` | PostgreSQL convention |
| **Database Schema** | `lowercase` | `enterprise`, `public` | PostgreSQL convention |
| **Config Files** | `snake_case.yml` | `data_sources.yml` | Existing pattern, readable |
| **Environment Variables** | `UPPER_SNAKE_CASE` | `WDH_ALIAS_SALT` | Shell convention, existing pattern |

#### Special Rules

**Chinese Field Names (Pydantic Models):**

**Decision:** Use original Chinese from Excel sources (no transliteration)

```python
class AnnuityPerformanceOut(BaseModel):
    """Annuity performance output model (Gold layer)."""

    月度: date = Field(..., description="Reporting month")
    计划代码: str = Field(..., min_length=1, description="Plan code")
    客户名称: str = Field(..., description="Company name")
    期末资产规模: float = Field(ge=0, description="Ending assets")
```

**Rationale:**
- ✅ Perfect match with Excel source columns (no mapping errors)
- ✅ Maintains business terminology (domain experts recognize fields)
- ✅ Python 3.10+ supports Unicode identifiers
- ✅ Column normalizer (Epic 3 Story 3.4) preserves Chinese names

**Database Mapping:**

When loading Pydantic models → PostgreSQL, use explicit column projection:

```python
# Pydantic model uses Chinese
class AnnuityPerformanceOut(BaseModel):
    月度: date
    计划代码: str

# Database loading (Epic 1 Story 1.8)
df_for_db = df.rename(columns={
    '月度': 'reporting_month',
    '计划代码': 'plan_code',
    '客户名称': 'company_name',
    '期末资产规模': 'ending_assets',
    # ... explicit mapping
})

# Load to PostgreSQL
loader.load(df_for_db, table='annuity_performance', schema='public')
```

**File Organization:**
```
domain/<domain_name>/
├── models.py           # Pydantic models (Chinese fields)
├── pipeline_steps.py   # DataFrame and Row transform steps
├── schemas.py          # pandera schemas (Bronze/Gold)
└── config.yml          # Domain-specific configuration
```

---

### Decision #8: structlog with Sanitization ✅

**Problem:** Epic 1 Story 1.3 requires structured logging. Without formal standards, logs will be inconsistent and may leak sensitive data.

**Decision:** Use `structlog` with JSON rendering, context binding, and strict sanitization rules.

#### Required Log Fields (Every Log Entry)

```json
{
  "timestamp": "2025-11-09T10:30:00Z",  // ISO 8601 UTC
  "level": "INFO",                       // DEBUG, INFO, WARNING, ERROR, CRITICAL
  "logger": "domain.annuity_performance", // Logger name
  "event": "pipeline.completed",         // Event identifier (dot notation)
  "context": {                           // Domain-specific context
    "domain": "annuity_performance",
    "execution_id": "exec_20250109_103000",
    "duration_ms": 1250,
    "rows_processed": 1000,
    "rows_failed": 0
  }
}
```

#### Configuration

```python
import structlog

# Configure once at startup (Epic 1 Story 1.3)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(ensure_ascii=False)
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Usage - automatic context binding
logger = structlog.get_logger()
logger = logger.bind(domain="annuity_performance", execution_id="exec_123")

logger.info("pipeline.started", rows=1000)
# Output: {"event": "pipeline.started", "domain": "annuity_performance",
#          "execution_id": "exec_123", "rows": 1000, "level": "info",
#          "timestamp": "2025-11-09T10:30:00Z"}
```

#### Log Levels by Environment

| Environment | Level | Usage |
|-------------|-------|-------|
| Development | `DEBUG` | All logs including detailed step execution |
| Staging | `INFO` | Pipeline execution, warnings, errors |
| Production | `INFO` | Same as staging (performance acceptable) |

#### Sensitive Data Sanitization Rules

- ❌ **NEVER log:** Tokens (`WDH_PROVIDER_EQC_TOKEN`), passwords, API keys, salt (`WDH_ALIAS_SALT`)
- ⚠️ **Sanitize before logging:** Company names (OK), but not individual PII (names, SSNs)
- ✅ **Safe to log:** Company IDs (including temporary IDs), domain names, file paths, row counts, durations

#### Log Rotation & Retention

```python
from logging.handlers import TimedRotatingFileHandler

handler = TimedRotatingFileHandler(
    filename='logs/workdatahub.log',
    when='midnight',      # Rotate daily
    interval=1,
    backupCount=30,       # Keep 30 days (PRD requirement)
    encoding='utf-8'
)
```

#### Output Targets

- **stdout:** Always (for Docker/K8s log collection)
- **File:** Production only (`logs/workdatahub-YYYYMMDD.log`)

#### Environment Configuration

```bash
# .env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE=1   # 0 (disabled), 1 (enabled)
LOG_FILE_PATH=logs/workdatahub.log
```

---

## Novel Patterns

This section documents unique technical patterns specific to WorkDataHub.

### Pattern 1: File-Pattern-Aware Version Detection

**Problem Domain:** Monthly data governance with version control

**Novel Aspect:** Unlike traditional "highest version wins," this scopes version detection to specific file patterns per domain, enabling partial corrections without data loss.

**When to Use:**
- Multi-domain data ingestion from shared folder structures
- Version corrections that don't cover all domains
- Regulatory environments requiring version audit trails

**Implementation:** See Decision #1

---

### Pattern 2: Legacy-Compatible Temporary ID Generation

**Problem Domain:** Gradual enrichment with stable cross-domain joins

**Novel Aspect:** Combines cryptographic stability (HMAC) with legacy normalization parity (29 status marker patterns) to ensure consistent temporary IDs across brownfield/greenfield systems.

**When to Use:**
- Brownfield migrations requiring backward compatibility
- Enrichment services with async resolution
- Chinese company name normalization

**Implementation:** See Decision #2

---

### Pattern 3: Hybrid Pipeline Step Protocol

**Problem Domain:** Performance vs. validation trade-offs

**Novel Aspect:** Single pipeline supports both DataFrame-level (vectorized performance) and row-level (detailed validation) steps, allowing optimal pattern selection per transformation type.

**When to Use:**
- Data pipelines requiring both bulk operations and per-row validation
- Integration with multiple validation libraries (pandera + Pydantic)
- External API enrichment mixed with bulk transformations

**Implementation:** See Decision #3

---

### Pattern 4: Strangler Fig with Parity Enforcement

**Problem Domain:** Risk-free legacy system replacement

**Novel Aspect:** CI-enforced parity tests block deployment if new implementation deviates from legacy, ensuring zero business logic regression during migration.

**When to Use:**
- Mission-critical system migrations
- Regulatory environments requiring output consistency
- Brownfield refactoring with zero tolerance for deviations

**Implementation:**
```python
# tests/e2e/test_pipeline_vs_legacy.py
def test_annuity_pipeline_parity():
    """Enforce 100% output parity between new and legacy annuity pipeline."""
    # Run new pipeline
    new_output = run_annuity_pipeline(test_month="202501")

    # Run legacy pipeline
    legacy_output = run_legacy_annuity_hub(test_month="202501")

    # Assert exact match (CI blocks on failure)
    pd.testing.assert_frame_equal(
        new_output.sort_values(by=['计划代码', '月度']),
        legacy_output.sort_values(by=['计划代码', '月度']),
        check_dtype=False,  # Allow type improvements
        check_exact=False,  # Allow float precision improvements
        rtol=1e-5
    )
```

---

## Implementation Patterns

These patterns ensure AI agent consistency across 100+ stories.

### Pattern 1: Epic Story Implementation Flow

**For All Domain Migration Epics (Epic 4, 9):**

```
Story X.1: Pydantic Models (Chinese fields, validators)
  ↓
Story X.2: Bronze Schema (pandera, structural validation)
  ↓
Story X.3: Transformation Pipeline (DataFrame + Row steps)
  ↓
Story X.4: Gold Schema (pandera, business rules)
  ↓
Story X.5: Database Loading (warehouse_loader.py)
  ↓
Story X.6: Parity Tests (vs legacy, CI-enforced)
```

**Apply to:** Epic 4 (Annuity), Epic 9 (Growth Domains)

---

### Pattern 2: Error Handling Standard

**For All Transformation Steps:**

```python
def transform_step(row: Row, context: Dict) -> StepResult:
    """Standard error handling pattern."""
    warnings = []
    errors = []

    try:
        # 1. Validate inputs
        if not row.get('required_field'):
            raise ValueError("Missing required field")

        # 2. Perform transformation
        result = complex_transformation(row)

        # 3. Validate outputs
        if result < 0:
            warnings.append("Negative value detected, clamping to 0")
            result = 0

        return StepResult(
            row={**row, 'new_field': result},
            warnings=warnings,
            errors=errors
        )

    except Exception as e:
        # 4. Create structured error context
        context = ErrorContext(
            error_type="TransformationError",
            operation="transform_step",
            domain=context.get('domain'),
            row_number=context.get('row_number'),
            field='new_field',
            input_data={'row': sanitize(row)},
            original_error=str(e)
        )

        errors.append(create_error_message(str(e), context))

        return StepResult(
            row=row,  # Return original on error
            warnings=warnings,
            errors=errors
        )
```

---

### Pattern 3: Configuration-Driven Discovery

**For All Domains (Epic 3 Integration):**

```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns:
      - "*年金*.xlsx"
    version_strategy: "highest_number"  # Decision #1
    sheet_selection: "auto"  # First sheet with data

  business_collection:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns:
      - "*业务*.xlsx"
    version_strategy: "highest_number"
```

**Python Integration:**
```python
from config.mapping_loader import load_data_source_config

# Epic 3 Story 3.5
config = load_data_source_config("annuity_performance")
file_path = discover_file(
    base_path=config.base_path.format(YYYYMM="202501"),
    patterns=config.file_patterns,
    version_strategy=config.version_strategy  # Uses Decision #1
)
```

---

### Pattern 4: Testing Strategy

**Test Pyramid (Epic 6):**

```
                    /\
                   /  \
                  / E2E \    ← test_pipeline_vs_legacy.py (parity)
                 /______\
                /        \
               / Integration \   ← test_domain_pipeline.py
              /______________\
             /                \
            /   Unit Tests     \  ← test_date_parser.py, test_normalizer.py
           /____________________\
```

**Unit Tests (Epic 6 Story 6.1):**
- Test pure functions: date parser, company normalizer, validators
- Mock external dependencies: database, EQC API
- Fast (<1s total execution)

**Integration Tests (Epic 6 Story 6.2):**
- Test pipeline orchestration: step execution order, error propagation
- Use test fixtures: sample Excel files, stub providers
- Medium speed (<10s)

**E2E/Parity Tests (Epic 6 Story 6.3):**
- Compare new vs legacy outputs (100% match requirement)
- Use real data: `reference/monthly/` samples
- Slow (<60s), run on CI only

**Pytest Markers:**
```python
@pytest.mark.unit
def test_date_parser():
    """Fast unit test."""
    ...

@pytest.mark.integration
def test_annuity_pipeline():
    """Integration test with fixtures."""
    ...

@pytest.mark.parity
@pytest.mark.legacy_data
def test_annuity_vs_legacy():
    """E2E parity test (slow, CI only)."""
    ...
```

**Run Strategies:**
```bash
# Development (fast feedback)
uv run pytest -v -m "unit"

# Pre-commit (medium)
uv run pytest -v -m "unit or integration"

# CI (comprehensive)
uv run pytest -v --cov=src --cov-report=term-missing
```

---

## Integration Architecture

### Epic Dependency Graph

```
Epic 1 (Foundation)
  ├─> Epic 2 (Validation)
  ├─> Epic 3 (File Discovery)
  ├─> Epic 5 (Enrichment - MVP stub only)
  ├─> Epic 6 (Testing)
  ├─> Epic 7 (Orchestration)
  └─> Epic 8 (Monitoring)

Epic 4 (Annuity Migration)
  ├─ depends on: Epic 1, 2, 3, 5 (stub), 6
  └─> Epic 9 (Growth Domains)

Epic 9 (Growth Domains)
  ├─ depends on: Epic 4 (pattern reference)
  └─> Epic 5 (full enrichment), Epic 10 (config/tooling)
```

### Key Integration Points

**Epic 1 → Epic 2:**
- Foundation provides `Pipeline` class
- Validation provides `BronzeSchema`, `GoldSchema` (pandera)
- Validation provides `PydanticValidator` (row-level)

**Epic 2 → Epic 4:**
- Annuity pipeline uses Bronze/Silver/Gold validation layers
- `utils/date_parser.py` (Decision #5) used in Pydantic validators

**Epic 3 → Epic 4:**
- File Discovery provides `VersionedPath` (Decision #1)
- `DataSourceConnector` configures annuity file patterns

**Epic 5 → Epic 4:**
- `EnrichmentGateway.enrich()` called in annuity pipeline (Story 4.3)
- MVP: Returns temporary IDs (Decision #2, Decision #6)
- Growth: Returns real company IDs (Epic 9)

**Epic 6 → All:**
- Parity tests enforce legacy compatibility (Strangler Fig pattern)
- CI blocks deployment if parity fails

**Epic 7 → All:**
- Dagster definitions wrap pipelines for UI monitoring (deferred to post-MVP)
- CLI remains primary execution method for MVP

**Epic 8 → All:**
- `structlog` (Decision #8) used by all modules
- `ErrorContext` (Decision #4) feeds structured logs

---

## Non-Functional Requirements

### Performance (NFR §1001-1015)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Full monthly processing | <30 min | Epic 7 Story 7.4 (performance testing) |
| Single domain (50K rows) | <5 min | Epic 4 Story 4.7 (annuity perf test) |
| File discovery | <10 sec | Epic 3 Story 3.6 (discovery perf) |
| Company enrichment (MVP stub) | <1 ms/company | Epic 5 Story 5.1 (stub implementation) |

**Architecture Support:**
- **Decision #3:** DataFrame steps for vectorized operations (10-100x faster than row iteration)
- **Decision #1:** Fast version detection (no filesystem stat calls for performance)

### Reliability (NFR §1016-1026)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Success rate | >98% | Epic 8 Story 8.3 (reliability monitoring) |
| Data corruption | 0% | Epic 6 Story 6.3 (parity tests, CI-enforced) |
| Legacy parity | 100% | Epic 4 Story 4.6, Epic 9 parity tests |

**Architecture Support:**
- **Decision #4:** Structured error context enables root cause analysis
- **Strangler Fig pattern:** Parity tests prevent regressions

### Maintainability (NFR §1027-1032)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Type coverage (mypy) | 100% | CI enforces strict mode |
| Test coverage | >80% | CI blocks <80% coverage |
| Documentation | All public APIs | Epic 1 Story 1.2 (API docs) |

**Architecture Support:**
- **Decision #7:** Naming conventions ensure consistency
- **Decision #3:** Clear protocols for DataFrame vs Row steps

### Security (NFR §1033-1045)

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| No secrets in git | `.env` gitignored, gitleaks CI scan | Epic 1 Story 1.1 |
| Parameterized queries | `warehouse_loader.py` uses psycopg2 params | Epic 1 Story 1.8 |
| Sensitive data sanitization | **Decision #8:** structlog sanitization rules | Epic 8 Story 8.1 |
| Audit logging | All mutations logged with user context | Epic 8 Story 8.2 |

---

## Migration Strategy

### Strangler Fig Execution Plan

**Phase 1: MVP (Epics 1-8)**

| Month | Deliverable | Parity Status |
|-------|-------------|---------------|
| M1 | Foundation + Validation + Discovery | N/A (infrastructure) |
| M2 | Annuity domain migration | ✅ 100% parity with legacy |
| M3 | Enrichment (stub), Testing, Orchestration | ✅ Stub validates parity |
| M4 | Monitoring, production readiness | ✅ Ongoing parity monitoring |

**Phase 2: Growth (Epics 9-10)**

| Month | Deliverable | Parity Status |
|-------|-------------|---------------|
| M5-M6 | 5 additional domains | ✅ Per-domain parity tests |
| M7 | Full enrichment service (Stories 5.3-5.8) | ⚠️ Backfill temporary IDs |
| M8 | Configuration & tooling | ✅ Maintain parity |

### Parallel Running Strategy

**M2-M4 (MVP Phase):**
- **New system:** Annuity pipeline runs in parallel with legacy
- **Outputs:** Both new and legacy write to separate database schemas
- **Validation:** CI parity tests compare outputs
- **Cutover:** After 3 months of 100% parity, switch traffic to new system

**M5-M8 (Growth Phase):**
- **Repeat:** Apply same parallel running to each new domain
- **Enrichment backfill:** Async job resolves MVP temporary IDs → real company IDs
- **Legacy decommission:** After 6 months of stable production, retire legacy system

---

## Appendices

### Appendix A: Decision Summary Table

| # | Decision | Impact | MVP/Growth |
|---|----------|--------|------------|
| 1 | File-Pattern-Aware Version Detection | Epic 3 (Discovery) | MVP |
| 2 | Legacy-Compatible Temporary Company IDs | Epic 5 (Enrichment) | MVP |
| 3 | Hybrid Pipeline Step Protocol | Epic 1, 4, 9 (All pipelines) | MVP |
| 4 | Hybrid Error Context Standards | Epic 2, 8 (Validation, Monitoring) | MVP |
| 5 | Explicit Chinese Date Format Priority | Epic 2, 4 (Validation, Annuity) | MVP |
| 6 | Stub-Only Enrichment MVP | Epic 5 (Enrichment) | MVP (defer to Growth) |
| 7 | Comprehensive Naming Conventions | All epics | MVP |
| 8 | structlog with Sanitization | Epic 1, 8 (Foundation, Monitoring) | MVP |

### Appendix B: Technology Dependency Matrix

| Technology | Used By | Justification |
|------------|---------|---------------|
| Python 3.10+ | All modules | Corporate standard, type system maturity |
| uv | All dependencies | 10-100x faster than pip, reproducible builds |
| Dagster | Orchestration (deferred) | UI/monitoring ready for Growth phase |
| Pydantic v2 | Row-level validation | 5-50x faster than v1, better error messages |
| pandas | DataFrame operations | Team expertise, ecosystem maturity |
| pandera | Bronze/Gold schemas | DataFrame validation, complements Pydantic |
| structlog | All logging | True structured logging, context binding |
| pytest | All testing | Industry standard, rich plugin ecosystem |
| mypy (strict) | All type checking | NFR requirement: 100% type coverage |
| ruff | All linting/formatting | 10-100x faster than black + flake8 + isort |

### Appendix C: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WDH_ALIAS_SALT` | ✅ MVP | N/A | HMAC salt for temporary company IDs (Decision #2) |
| `WDH_ENRICH_COMPANY_ID` | ❌ | `0` | Enable enrichment service (Decision #6: disabled for MVP) |
| `WDH_COMPANY_ENRICHMENT_ENABLED` | ❌ | `0` | Simplified enrichment toggle (Decision #6: stub only for MVP) |
| `WDH_PROVIDER_EQC_TOKEN` | ❌ Growth | N/A | EQC API token (30-min validity, deferred to Growth) |
| `WDH_ENRICH_SYNC_BUDGET` | ❌ Growth | `0` | Max sync API calls per run (deferred to Growth) |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level (Decision #8: DEBUG/INFO/WARNING/ERROR) |
| `LOG_TO_FILE` | ❌ | `1` | Enable file logging (Decision #8) |
| `LOG_FILE_PATH` | ❌ | `logs/workdatahub.log` | Log file path (Decision #8) |

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Bronze Layer** | Raw data with structural validation only (pandera) |
| **Silver Layer** | Cleansed data with per-row business validation (Pydantic) |
| **Gold Layer** | Business-ready data with final projections and schemas (pandera) |
| **Strangler Fig** | Migration pattern: gradually replace legacy with parallel running |
| **Parity Test** | CI-enforced test comparing new vs legacy outputs (100% match required) |
| **Temporary Company ID** | Stable ID (`IN_<16-char-Base32>`) for unresolved companies (Decision #2) |
| **Version Detection** | Algorithm selecting correct V1/V2/V3 folder per domain (Decision #1) |
| **DataFrame Step** | Bulk transformation operating on entire DataFrame (Decision #3) |
| **Row Step** | Per-row transformation with detailed validation/enrichment (Decision #3) |
| **ErrorContext** | Structured error metadata for debugging (Decision #4) |

---

**End of Architecture Document**

_This architecture has been approved for implementation. All 100+ user stories across Epics 1-10 must adhere to the decisions, patterns, and standards defined in this document._

_For questions or clarification, refer to the architecture session checkpoint: `docs/architecture-session-checkpoint.md`_
