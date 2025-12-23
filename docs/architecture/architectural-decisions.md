# Architectural Decisions

> Epic 5 status: AD-010 (Infrastructure Layer & Pipeline Composition) implemented in code and documented in `docs/architecture/infrastructure-layer.md`.

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

    Format: IN<16-char-Base32> (no underscore separator)
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

    return f"IN{encoded}"
```

#### Decision Table

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Business Key** | Normalized company name only | Enable cross-domain joins |
| **Normalization** | Legacy-compatible + `.lower()` | Maintain parity with existing cleansing |
| **Hash Algorithm** | HMAC-SHA1 (not MD5) | More secure, cryptographically sound |
| **ID Format** | `IN<16-char-Base32>` | Distinguishable from legacy GM/GC codes |
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

#### Implementation

> **UPDATE (2025-12-02):** Implementation moved from Epic 6 to Epic 5 Story 5.4 for earlier availability.

- **Module:** `infrastructure/enrichment/normalizer.py` (Story 5.4)
- **Status Markers:** `CORE_REPLACE_STRING` defined inline in normalizer module
- **Integration Points:**
  - `infrastructure/enrichment/CompanyIdResolver._generate_temp_id()` (Story 5.4)
  - `EnrichmentGateway` calls when lookup fails (Epic 6 Story 6.5)
- **Testing:** Parity tests with legacy normalization using golden datasets

**CRITICAL:** Any code generating temporary company IDs MUST call `normalize_for_temp_id()` before hashing. Failure to do so will result in the same customer receiving different IDs due to whitespace, status markers, or character width variations.

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

#### Mandatory Shared Step Usage (Story 4.9)

> **REQUIREMENT:** All domain pipelines MUST use shared steps from `domain/pipelines/steps/` where applicable. Domain-specific steps should ONLY be created for business logic unique to that domain.

**Shared Step Usage Requirements:**

| Shared Step | When to Use | Domain-Specific Alternative |
|-------------|-------------|----------------------------|
| `ColumnNormalizationStep` | All domains with Excel input | ❌ Do NOT re-implement |
| `DateParsingStep` | All domains with date fields | ❌ Do NOT re-implement |
| `CustomerNameCleansingStep` | All domains with customer names | ❌ Do NOT re-implement |
| `FieldCleanupStep` | All domains before Gold projection | ❌ Do NOT re-implement |

**Domain-Specific Steps (Allowed):**
- Business logic unique to that domain (e.g., `PlanCodeCleansingStep` for annuity)
- Domain-specific mappings (e.g., `InstitutionCodeMappingStep`)
- Domain-specific enrichment logic (e.g., `CompanyIdResolutionStep`)

**Verification (Code Review Requirement):**
```bash
# Check that domain pipeline imports shared steps
grep -E "from work_data_hub\.domain\.pipelines\.steps import" \
  src/work_data_hub/domain/{domain_name}/pipeline_steps.py

# Check for duplicate step class names (should be empty or justified)
grep "^class.*Step" src/work_data_hub/domain/pipelines/steps/*.py | cut -d: -f2 | sort > /tmp/shared.txt
grep "^class.*Step" src/work_data_hub/domain/{domain_name}/pipeline_steps.py | cut -d: -f2 | sort > /tmp/domain.txt
comm -12 /tmp/shared.txt /tmp/domain.txt  # Should be empty
```

**Rationale:** Story 4.9 analysis revealed that incomplete Tech-Spec guidance ("use Pipeline framework" without "reuse shared steps") led to 4,942 lines of code in `annuity_performance/` when <2,000 was achievable. This mandatory requirement prevents future domains from repeating the same mistake.

#### Shared Domain Types and Validation (Story 4.8)

Story 4.8 extends the shared infrastructure with domain-level types and validation utilities:

**Directory Structure:**
```
src/work_data_hub/domain/pipelines/
├── types.py                        # Core types + shared domain types
│   ├── PipelineContext             # Pipeline execution context
│   ├── PipelineResult              # Pipeline framework result
│   ├── ErrorContext                # Shared error context (Story 4.8)
│   └── DomainPipelineResult        # Domain-level result (Story 4.8)
├── validation/                     # Shared validation utilities (Story 4.8)
│   ├── __init__.py                 # Public exports
│   ├── helpers.py                  # raise_schema_error, ensure_required_columns, ensure_not_empty
│   └── summaries.py                # ValidationSummaryBase
└── ...
```

**Shared Domain Types:**

| Type | Purpose | Location |
|------|---------|----------|
| `ErrorContext` | Structured error context for pipeline failures | `types.py` |
| `DomainPipelineResult` | Result for domain-level pipeline execution (e.g., `process_annuity_performance()`) | `types.py` |
| `ValidationSummaryBase` | Base class for validation summary dataclasses | `validation/summaries.py` |

**Shared Validation Helpers:**

| Helper | Purpose |
|--------|---------|
| `raise_schema_error()` | Raise SchemaError with consistent formatting |
| `ensure_required_columns()` | Validate required columns are present |
| `ensure_not_empty()` | Validate DataFrame is not empty |

**Usage in Domain Modules:**
```python
from work_data_hub.domain.pipelines.types import ErrorContext, DomainPipelineResult
from work_data_hub.domain.pipelines.validation import (
    ensure_required_columns,
    ensure_not_empty,
    ValidationSummaryBase,
)

# Use ErrorContext for consistent error reporting
error_ctx = ErrorContext(
    error_type="validation_error",
    operation="bronze_validation",
    domain="annuity_performance",
    stage="validation",
    error_message="Missing required columns",
)
logger.error("validation.failed", extra=error_ctx.to_log_dict())

# Use validation helpers in schema validation
ensure_not_empty(schema, dataframe, "Bronze")
ensure_required_columns(schema, dataframe, REQUIRED_COLUMNS, "Bronze")
```

**Domain Module Refactoring Pattern (Story 4.8):**

Large domain modules should be split into focused sub-modules:
- `service.py` → Core orchestration (<500 lines)
- `discovery_helpers.py` → File discovery utilities
- `processing_helpers.py` → Row processing and transformation
- Re-export all symbols from `service.py` for backward compatibility

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

**Problem:** Epic 6 (Company Enrichment Service) defines sophisticated company enrichment with 8 stories. Risk: blocks Epic 4 annuity migration, adds complexity.

**Decision:** Defer real enrichment to Growth phase. MVP uses StubProvider + temporary IDs only.

#### MVP Scope (Epic 6)

**Implemented Stories:**
- ✅ Story 6.1: `StubProvider` with test fixtures
- ✅ Story 6.2: Temporary ID generation (Decision #2)
- ✅ Story 6.5: `EnrichmentGateway` shell (stub + temp ID fallback only)

**Result:** All companies get temporary IDs in MVP

#### Growth Phase (Epic 9-10)

**Deferred Stories:**
- Story 6.3: Full database schema (3 tables)
- Story 6.4: Multi-tier internal mapping resolver
- Story 6.6: Sync EQC API provider (budget-limited, token management)
- Story 6.7: Async enrichment queue (deferred resolution)
- Story 6.8: Observability & metrics (CSV export, cache hit rates)

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

### Decision #10: Infrastructure Layer & Pipeline Composition ✅

**Problem:** Domain layer was becoming bloated with infrastructure concerns (Epic 4 implementation reached 3,446 lines vs target <1,000 lines). Infrastructure logic (enrichment, validation, transforms) was embedded in domain layer instead of being extracted as reusable components, blocking Epic 9 (Growth Domains Migration).

**Decision:** Establish `infrastructure/` layer with **Python Code Composition** (Pipeline Pattern) instead of JSON Configuration for data transformations.

#### Infrastructure Layer Structure

```
src/work_data_hub/infrastructure/
├── enrichment/                  # Data enrichment services
│   └── company_id_resolver.py   # CompanyIdResolver with batch optimization
├── validation/                  # Validation utilities and error handling
│   ├── error_handler.py         # Threshold checking, structured logging
│   └── report_generator.py      # CSV export for failed rows
├── transforms/                  # Reusable pipeline steps (Python classes)
│   ├── base.py                  # TransformStep base class, Pipeline composer
│   └── standard_steps.py        # MappingStep, CleansingStep, CalculationStep, etc.
├── cleansing/                   # Data cleansing registry (migrated from top-level)
│   ├── registry.py
│   ├── rules/
│   └── settings/
└── settings/                    # Infrastructure configuration
    ├── data_source_schema.py    # Schema validation for configs
    └── loader.py                # Config loading utilities
```

#### Python Code Composition Pattern

**Core Principle:** Domain services compose pipelines using Python code, not JSON config

```python
# Domain service builds pipeline through code composition
from work_data_hub.infrastructure.transforms import (
    Pipeline, RenameStep, CleansingStep, MappingStep, CalculationStep
)

class AnnuityPerformanceService:
    def _build_domain_pipeline(self) -> Pipeline:
        """Build domain-specific transformation pipeline using code composition"""
        return Pipeline([
            RenameStep(CHINESE_TO_ENGLISH_MAPPING),
            CleansingStep(self.cleansing, {
                "客户名称": ["trim_whitespace", "normalize_company_name"],
                "交易日期": ["standardize_date"]
            }),
            MappingStep(BUSINESS_TYPE_CODE_MAPPING, "业务类型", "product_line_code"),
            CalculationStep(
                lambda df: (df["期末资产规模"] - df["期初资产规模"]) / df["期初资产规模"],
                "当期收益率"
            )
        ])
```

#### Architecture Boundaries

| Layer | Responsibility | Code Location |
|-------|---------------|---------------|
| **Infrastructure** | Reusable utilities and pipeline building blocks | `infrastructure/` |
| **Domain** | Business orchestration using infrastructure components | `domain/{domain_name}/` |
| **Config** | Runtime configuration (environment variables, deployment-time settings) | `config/` |
| **Data** | Business data (mappings, reference data) | `data/mappings/` |

**Clean Architecture Enforcement:**
- Domain layer: <500 lines per domain (Pure business orchestration)
- Infrastructure provides utilities, NOT black-box engines
- Dependency injection for testability
- All infrastructure components have >85% test coverage

#### Rationale

1. **Python is the superior DSL** - No need for custom configuration languages/parsers
2. **Maintenance burden avoidance** - JSON config requires custom parser, validation, error handling
3. **Clean Architecture compliance** - Clear separation between infrastructure and business logic
4. **Cross-domain code reuse** - Epic 9 (6+ domains) can reuse infrastructure components
5. **Improved testability** - Code composition easier to test than config-driven engines
6. **Performance optimization** - Vectorized Pandas operations in infrastructure steps

#### Implications

**For Domain Development (Epic 4, Epic 9):**
- Domain service becomes lightweight orchestrator (<150 lines)
- Pipeline composition uses infrastructure building blocks
- Business logic stays in domain, infrastructure logic in infrastructure layer

**For Infrastructure Development (Epic 5):**
- Infrastructure provides reusable Steps (MappingStep, CleansingStep, etc.)
- Each Step uses vectorized Pandas operations for performance
- Steps are composable through Pipeline class
- No configuration engines - domain code composes steps directly

**For Configuration:**
- `config/` contains only runtime/deployment-time configuration
- `infrastructure/settings/` contains infrastructure configuration logic
- `data/mappings/` contains business data (not configuration)
- Domain `constants.py` contains business constants (avoid `config.py` naming conflicts)

#### Implementation (Epic 5)

- **Story 5.1-5.3:** Foundation and config reorganization
- **Story 5.4-5.6:** Infrastructure components (CompanyIdResolver, validation utilities, pipeline steps)
- **Story 5.7:** Refactor annuity_performance to lightweight orchestrator
- **Story 5.8:** Integration testing and documentation

**Expected Results:**
- Domain layer: 3,446 → <500 lines (-85% code)
- Infrastructure layer: 0 → ~1,200 lines (reusable)
- Net reduction: -1,246 lines
- Performance: 5-10x improvement (batch processing)

---

### Decision #9: Configuration-Driven Generic Steps ✅

**Problem:** Domain pipelines (Epic 4, 9) require common transformations like column renaming, value replacement, calculated fields, and row filtering. Without standardization, each domain re-implements these patterns, leading to code duplication and inconsistency.

**Decision:** Provide configuration-driven generic DataFrame steps that accept dictionaries/lambdas instead of hardcoded logic.

#### Generic Steps Architecture

**Available Steps:**

| Step | Purpose | Configuration Type |
|------|---------|-------------------|
| `DataFrameMappingStep` | Rename columns | `Dict[str, str]` (old → new) |
| `DataFrameValueReplacementStep` | Replace values in columns | `Dict[str, Dict[Any, Any]]` (column → {old: new}) |
| `DataFrameCalculatedFieldStep` | Add calculated columns | `Dict[str, Callable[[DataFrame], Series]]` |
| `DataFrameFilterStep` | Filter rows by condition | `Callable[[DataFrame], Series[bool]]` |

#### Implementation Pattern

```python
from work_data_hub.domain.pipelines.steps import (
    DataFrameMappingStep,
    DataFrameValueReplacementStep,
    DataFrameCalculatedFieldStep,
    DataFrameFilterStep,
)

# Configuration in domain config.py (not in step classes)
COLUMN_MAPPING = {'月度': 'report_date', '计划代码': 'plan_code'}
VALUE_REPLACEMENTS = {'status': {'draft': 'pending', 'old': 'new'}}
CALCULATED_FIELDS = {'total': lambda df: df['a'] + df['b']}
FILTER_CONDITION = lambda df: df['total'] > 0

# Pipeline assembly
pipeline.add_step(DataFrameMappingStep(COLUMN_MAPPING))
pipeline.add_step(DataFrameValueReplacementStep(VALUE_REPLACEMENTS))
pipeline.add_step(DataFrameCalculatedFieldStep(CALCULATED_FIELDS))
pipeline.add_step(DataFrameFilterStep(FILTER_CONDITION))
```

#### Design Principles

1. **Configuration Over Code**: Static mappings live in `config.py`, not step classes
2. **Pandas Vectorized Operations**: All steps use `df.rename()`, `df.replace()`, boolean indexing
3. **Immutability**: Input DataFrames are never mutated; new DataFrames are always returned
4. **Graceful Error Handling**: Missing columns logged as warnings, not errors

#### When to Use Generic Steps vs. Custom Steps

**Use Generic Steps:**
- ✅ Column renaming (`DataFrameMappingStep`)
- ✅ Value replacement/mapping (`DataFrameValueReplacementStep`)
- ✅ Simple calculations (addition, ratios) (`DataFrameCalculatedFieldStep`)
- ✅ Row filtering based on conditions (`DataFrameFilterStep`)

**Create Custom Steps:**
- ❌ Complex business logic with conditional branching
- ❌ External API calls or database lookups
- ❌ Stateful transformations depending on previous rows
- ❌ Domain-specific validation with custom error handling

#### Performance Targets

| Step | Target (10,000 rows) |
|------|---------------------|
| DataFrameMappingStep | <5ms |
| DataFrameValueReplacementStep | <10ms |
| DataFrameCalculatedFieldStep | <20ms |
| DataFrameFilterStep | <5ms |

#### Implementation (Story 1.12)

- **Module:** `domain/pipelines/steps/`
- **Files:** `mapping_step.py`, `replacement_step.py`, `calculated_field_step.py`, `filter_step.py`
- **Documentation:** `domain/pipelines/steps/README.md`
- **Tests:** `tests/unit/domain/pipelines/steps/test_*_step.py`

---

### Decision #11: Hybrid Reference Data Management Strategy ✅

**Problem:** FK constraint violations block pipeline execution when fact data (e.g., `规模明细` table) contains new FK values not present in reference tables. The current `reference_backfill` mechanism only covers 2 out of 4 foreign keys (50%), leaving `产品线` (Product Lines) and `组织架构` (Organization) gaps that cannot be automatically handled.

**Decision:** Implement hybrid strategy combining pre-load (authoritative data) with on-demand backfill (auto-derived data), with data quality tracking through source tracking fields.

#### Two-Layer Data Quality Model

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Authoritative Data (权威数据)                         │
│  Source: Legacy MySQL, MDM, Config files                        │
│  Characteristics: Complete fields, verified, audit trail        │
│  Marker: _source = 'authoritative'                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Auto-Derived Data (自动派生数据)                      │
│  Source: New FK values from fact data                           │
│  Characteristics: Minimal fields, needs review                  │
│  Marker: _source = 'auto_derived', _needs_review = true         │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

1. **Two-layer data quality model** - Distinguish authoritative data from auto-derived data
2. **Configuration-driven FK relationships** - Define FK relationships in `config/data_sources.yml`
3. **Dependency-aware processing order** - Topological sort for FK with dependencies
4. **Source tracking for data governance** - `_source`, `_needs_review`, `_derived_from_domain`, `_derived_at` columns
5. **Graceful degradation** - Backfill provides fallback when pre-load fails

#### FK Configuration Schema

```yaml
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "年金计划号"
        target_table: "年金计划"
        target_key: "年金计划号"
        derive_columns: ["年金计划号"]
      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        depends_on: ["fk_plan"]
        derive_columns: ["组合代码", "年金计划号"]
      - name: "fk_product_line"
        source_column: "产品线"
        target_table: "产品线"
        target_key: "产品线代码"
        derive_columns: ["产品线"]
      - name: "fk_organization"
        source_column: "组织代码"
        target_table: "组织架构"
        target_key: "组织代码"
        derive_columns: ["组织代码"]
```

#### Reference Table Schema Enhancement

All reference tables receive tracking columns:

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `_source` | VARCHAR(20) | 'authoritative' | Data origin: 'authoritative' or 'auto_derived' |
| `_needs_review` | BOOLEAN | false | Flag for records requiring manual review |
| `_derived_from_domain` | VARCHAR(50) | NULL | Domain that triggered auto-derivation |
| `_derived_at` | TIMESTAMP | NULL | When auto-derivation occurred |

#### Service Architecture

```python
class HybridReferenceService:
    """Coordinates pre-load and backfill for reference data management."""

    def __init__(self, sync_service: ReferenceSyncService,
                 backfill_service: GenericBackfillService):
        self.sync = sync_service      # Pre-load from authoritative sources
        self.backfill = backfill_service  # On-demand derivation

    def ensure_references(self, domain: str, df: pd.DataFrame) -> BackfillResult:
        """
        Ensure all FK references exist before fact data insertion.

        1. Check which FK values are missing
        2. For missing values, create auto-derived records
        3. Mark auto-derived records with tracking fields
        4. Return summary of actions taken
        """
        ...
```

#### Decision Table

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Strategy** | Hybrid (pre-load + backfill) | Balance data quality with automation |
| **Pre-load Sources** | Legacy MySQL, config files | Authoritative data from existing systems |
| **Backfill Trigger** | Missing FK values in fact data | On-demand, only when needed |
| **Data Quality Tracking** | `_source`, `_needs_review` columns | Enable data governance and review workflows |
| **FK Configuration** | YAML in `data_sources.yml` | Configuration-driven, no code changes for new FKs |
| **Dependency Handling** | Topological sort via `depends_on` | Correct insertion order for dependent FKs |

#### Success Criteria

1. All 4 FK relationships covered (100% coverage, up from 50%)
2. No FK constraint failures in pipeline execution
3. Auto-derived records properly tracked and reviewable
4. Pre-load covers >90% of FK values in normal operation
5. Backfill provides reliable fallback for new values

#### Implementation (Epic 6.2)

- **Story 6.2.1:** Generic Backfill Framework Core
- **Story 6.2.2:** Reference Table Schema Enhancement (tracking columns)
- **Story 6.2.3:** FK Configuration Schema Extension
- **Story 6.2.4:** Pre-load Reference Sync Service
- **Story 6.2.5:** Hybrid Reference Service Integration
- **Story 6.2.6:** Reference Data Observability

#### Related Documents

- Sprint Change Proposal: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-12-generic-reference-management.md`
- Problem Analysis: `docs/specific/backfill-method/problem-analysis.md`
- Mixed Strategy Solution: `docs/specific/backfill-method/mixed-strategy-solution.md`

---

## Technical Debt & Future Considerations

### TD-001: Cross-Domain Mapping Data Consolidation

**Identified:** Story 5.3 (2025-12-02)
**Priority:** Medium (address in Epic 9)
**Status:** Deferred

#### Problem

Some mappings in `domain/annuity_performance/constants.py` have strong cross-domain applicability but are currently locked in a single domain module:

| Mapping | Current Location | Cross-Domain Applicability |
|---------|------------------|---------------------------|
| `COMPANY_BRANCH_MAPPING` | `annuity_performance/constants.py` | High - all domains use institution codes |
| `BUSINESS_TYPE_CODE_MAPPING` | `annuity_performance/constants.py` | High - product line codes are company-wide |
| `PLAN_CODE_CORRECTIONS` | `annuity_performance/constants.py` | Low - annuity-specific |
| `DEFAULT_ALLOWED_GOLD_COLUMNS` | `annuity_performance/constants.py` | Low - domain-specific schema |

#### Current State

1. **`data/mappings/*.yml`** - Created but loader functions unused in production code
2. **`domain/xxx/constants.py`** - Contains both domain-specific and cross-domain mappings
3. **Data duplication** - `business_type_code.yml` duplicates `BUSINESS_TYPE_CODE_MAPPING`

#### Recommended Resolution (Epic 9)

When second domain requires same mappings:

```python
# 1. Move cross-domain mappings to data/mappings/
data/mappings/
├── company_branch.yml          # Complete institution code mapping
├── business_type_code.yml      # Complete business type mapping

# 2. Domain constants.py retains only domain-specific items
domain/annuity_performance/constants.py:
├── DEFAULT_ALLOWED_GOLD_COLUMNS  # Domain-specific
├── PLAN_CODE_CORRECTIONS         # Domain-specific
├── LEGACY_COLUMNS_TO_DELETE      # Domain-specific

# 3. Load cross-domain mappings via infrastructure
from work_data_hub.infrastructure.settings import (
    load_company_branch,
    load_business_type_code,
)
```

#### Decision Criteria

| Mapping Type | Location | Criteria |
|-------------|----------|----------|
| Cross-domain | `data/mappings/` | Used by 2+ domains, company-wide reference data |
| Domain-specific | `constants.py` | Used by single domain, domain-specific business rules |

#### Impact if Not Addressed

- Code duplication when Epic 9 domains need same mappings
- Inconsistent data if mappings updated in one location but not another
- Reduced maintainability as domain count grows

---

