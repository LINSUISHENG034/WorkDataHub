# WorkDataHub Architecture Session Checkpoint

**Session Date:** 2025-11-09
**Facilitator:** Winston (Architect Agent)
**User:** Link
**Session Type:** Scale Adaptive Architecture Design (Brownfield Project)
**Skill Level:** Intermediate

---

## Session Status

**Progress:** 6 of 8 critical architectural decisions completed (75%)

**Completed:**
- ✅ Technology Stack Assessment & Gap Identification
- ✅ Decision #1: Version Detection Logic
- ✅ Decision #2: Temporary Company ID Generation
- ✅ Decision #3: Pipeline Step Protocol (Hybrid: DataFrame + Row-level)
- ✅ Decision #4: Error Message Standards (Hybrid with Required Context)
- ✅ Decision #5: Chinese Date Format Support (Explicit Format Priority)
- ✅ Decision #6: Enrichment Service Architecture (Stub-Only MVP)

**In Progress:**
- 🔄 Ready to proceed to Decision #7: Naming Conventions

**Remaining:**
- Decision #8: Logging Requirements
- Design novel patterns and integration points
- Define implementation patterns for AI agent consistency
- Generate final architecture document
- Validate architecture completeness and update workflow status

---

## Project Context

**Project:** WorkDataHub - Internal Data Platform
**Scale:** Level 2-4 (Medium Complexity)
**Scope:** 10 epics, 100+ stories across MVP and Growth phases
**Type:** Brownfield - Partial implementation exists, completing migration from legacy `annuity_hub`

**Key Characteristics:**
- Strangler Fig migration pattern (gradual legacy replacement)
- Bronze → Silver → Gold data quality layers (Medallion architecture)
- Chinese date/text handling requirements
- Company ID enrichment with temporary ID fallback
- 100% legacy parity requirement during migration

**Technology Stack (Locked In):**
- Python 3.10+, uv package manager
- Dagster orchestration (CLI-first execution)
- Pydantic v2, pandas, PostgreSQL
- pytest, mypy (strict), ruff
- Existing partial implementation in `src/work_data_hub/`

---

## Decision #1: File-Pattern-Aware Version Detection ✅

### Decision Summary

**Problem:** Monthly data arrives in inconsistent versioned folders (V1, V2, V3). Different domains may have corrections at different version levels. Need automatic version selection without data loss.

**Solution:** File-pattern-aware version detection scoped per domain

### Algorithm

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

### Decision Rules

1. Scan for folders matching pattern `V\d+` (V1, V2, V3, etc.)
2. For each domain's file patterns, iterate versions from highest to lowest
3. Select **first version where a matching file exists** (per domain)
4. If no versioned folders contain matching files → fall back to base path
5. If multiple files match pattern in same version → ERROR (ambiguous, refine pattern)
6. Manual override: Support `--version=V1` CLI flag for debugging

### Key Benefits

✅ **No data loss:** Each domain independently selects its highest available version
✅ **Handles partial corrections:** Annuity uses V2, other domains use V1 automatically
✅ **Deterministic:** Same inputs always produce same version selection
✅ **Debuggable:** Clear structured logs show version selection reasoning

### Example Execution

**Scenario:**
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

### Logging Output

```json
{
  "domain": "annuity_performance",
  "base_path": "reference/monthly/202501/收集数据/业务收集",
  "file_patterns": ["*年金*.xlsx"],
  "versions_scanned": ["V2", "V1"],
  "selected_version": "V2",
  "selected_file": "V2/年金数据.xlsx",
  "strategy": "highest_version_with_matching_file"
}
```

### Implementation Notes (Epic 3 Story 3.1)

- Implement in `io/connectors/file_connector.py`
- Return `VersionedPath` dataclass: `path, version, strategy_used`
- Configuration in `config/data_sources.yml` per domain:
  ```yaml
  domains:
    annuity_performance:
      base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
      file_patterns: ["*年金*.xlsx"]
      version_strategy: "highest_number"  # Document for clarity
  ```
- Integration with Epic 3 Story 3.5 (File Discovery Integration)

---

## Decision #2: Legacy-Compatible Temporary Company ID Generation ✅

### Decision Summary

**Problem:** Company names vary across Excel sources. When enrichment service can't resolve to official company IDs, need stable temporary IDs that:
- Are deterministic (same company → same ID across runs)
- Enable cross-domain joins
- Are clearly distinguishable from real company IDs
- Don't block pipelines on enrichment failures

**Solution:** HMAC-based temporary IDs with legacy-compatible normalization

### Architecture

#### Business Key Composition

**Decision:** Company name only (no domain context)

**Rationale:**
- Enables cross-domain joins (primary purpose of temporary IDs)
- Same company across multiple domains → same temporary ID
- Edge case (truly different companies with identical names) handled by async enrichment

#### Normalization Strategy

**Decision:** Legacy-compatible normalization + lowercase for hash stability

**Key Operations (from `legacy/annuity_hub/common_utils/common_utils.py::clean_company_name`):**

1. **Complete whitespace removal:** `re.sub(r'\s+', '', name)`
2. **Business-specific pattern removal:**
   - `"及下属子企业"` (and subsidiaries)
   - Trailing: `(团托)`, `-A`, `-123`, `-养老`, `-福利`
3. **Status marker cleansing:** Remove from start/end
   - 29 markers: `已转出`, `待转出`, `终止`, `转出`, `转移终止`, `已作废`, `已终止`, `保留`, `保留账户`, `存量`, etc.
4. **Character width normalization:** Full-width → Half-width
   - Example: `"公司Ａ"` → `"公司A"`
5. **Bracket normalization:** English → Chinese brackets
   - `'(' → '（'`, `')' → '）'`
6. **Additional: Lowercase** (NEW - not in legacy)
   - Ensures `"公司A"` and `"公司a"` get same temporary ID

### Implementation

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

    # 1. Remove all whitespace (legacy behavior)
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

    # 5. Full-width → Half-width conversion (legacy default)
    name = ''.join([
        chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
        for char in name
    ])

    # 6. Normalize brackets to Chinese (legacy behavior)
    name = name.replace('(', '（').replace(')', '）')

    # 7. Additional: Lowercase for hash stability (NEW - not in legacy)
    name = name.lower()

    return name


def generate_temp_company_id(company_name: str, salt: str) -> str:
    """
    Generate stable temporary company ID.

    Format: IN_<16-char-Base32>
    Algorithm: HMAC-SHA1 (more secure than legacy MD5)

    Note: Legacy uses MD5 with GM/GC prefixes for different purpose.
          This is NEW temporary ID system with IN_ prefix.
    """
    normalized = normalize_for_temp_id(company_name)

    # HMAC-SHA1 with secret salt (more secure than legacy MD5)
    digest = hmac.new(
        salt.encode('utf-8'),
        normalized.encode('utf-8'),
        hashlib.sha1
    ).digest()

    # Take first 80 bits (10 bytes), Base32 encode → 16 chars
    encoded = base64.b32encode(digest[:10]).decode('ascii')

    return f"IN_{encoded}"
```

### Decision Table

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Business Key** | Normalized company name only | Enable cross-domain joins |
| **Normalization** | Legacy-compatible (reuse `clean_company_name` core logic) | Maintain parity with existing data cleansing |
| **Additional Step** | Add `.lower()` for hash input | Ensure case-insensitive matching |
| **Hash Algorithm** | HMAC-SHA1 (not MD5) | More secure, cryptographically sound |
| **ID Format** | `IN_<16-char-Base32>` | Distinguishable from legacy GM/GC codes |
| **Salt Management** | `WDH_ALIAS_SALT` environment variable | Must be secret, consistent across environments |

### Security & Configuration

**Environment Variable:**
```bash
# .env (gitignored)
WDH_ALIAS_SALT="<32+ character random string>"  # Required, must be secret
```

**Security Notes:**
- Salt must be 32+ characters random string
- Same salt must be used across all environments for ID consistency
- If salt is lost/changed, all temporary IDs become different (document in runbook)
- Never commit salt to git (validate with gitleaks in CI)

### Implementation Notes (Epic 5 Story 5.2)

1. **Extract legacy normalization patterns into shared module:**
   - `CORE_REPLACE_STRING` set → `src/work_data_hub/cleansing/config/status_markers.py`
   - Core normalization logic → `src/work_data_hub/utils/company_normalizer.py`

2. **Reuse legacy patterns but document differences:**
   ```python
   # src/work_data_hub/utils/company_normalizer.py

   def normalize_company_name_legacy_compat(name: str) -> str:
       """
       Legacy-compatible normalization for company names.

       Based on: legacy/annuity_hub/common_utils/common_utils.py::clean_company_name

       Differences from legacy:
       - Adds .lower() at end for temp ID stability (legacy preserves case)
       - Uses imported CORE_REPLACE_STRING (same content as legacy)
       """
       # ... implementation following legacy pattern ...
   ```

3. **Test parity with legacy using golden datasets:**
   ```python
   def test_normalization_parity():
       """Ensure new normalization matches legacy for known companies."""
       legacy_results = load_legacy_normalized_names()
       for company in test_companies:
           new_result = normalize_company_name_legacy_compat(company).lower()
           legacy_result = legacy_clean_company_name(company).lower()
           assert new_result == legacy_result
   ```

### Integration Points

- **Epic 5 Story 5.5:** `EnrichmentGateway` calls `generate_temp_company_id()` when lookup fails
- **Epic 4 Story 4.3:** Annuity pipeline uses temporary IDs for unresolved companies
- **Epic 6:** Parity tests validate temporary ID stability across runs

---

## Remaining Decisions (Priority Order)

### Decision #3: Pipeline Step Protocol (High Priority)

**Blocks:** Epic 1 (Foundation), Epic 4 (Annuity Migration)

**Questions to Address:**
- What is the formal contract for pipeline transformation steps?
- How do steps communicate errors (fail fast vs collect)?
- What metadata must steps expose (duration, row counts, memory)?
- How do steps handle optional/conditional execution (enrichment service down)?
- Retry logic: which errors are transient vs permanent?

**Existing Context:**
- `domain/pipelines/core.py` has basic framework
- Epic 1 Story 1.5 (simple) and 1.10 (advanced) need formal protocol

---

### Decision #4: Error Message Standards (High Priority)

**Blocks:** Epic 2 (Validation), Epic 8 (Monitoring)

**Questions to Address:**
- What fields are required in all error messages?
- How should actionable guidance be structured?
- What error types/categories exist (validation, IO, enrichment, database)?
- How do error messages integrate with structured logging?
- CSV export format for failed rows (Epic 2 Story 2.5)?

---

### Decision #5: Chinese Date Format Support (Medium Priority)

**Blocks:** Epic 2 (Validation), Epic 4 (Annuity)

**Questions to Address:**
- Comprehensive list of supported formats (YYYYMM, YYYY年MM月, etc.)?
- Parsing priority order when multiple formats could match?
- Validation range (2000-2030 per PRD)?
- How to handle 2-digit years (25年 → 2025 or 1925)?
- Error messages for unparseable dates?

**Existing Context:**
- `legacy/annuity_hub/common_utils/common_utils.py::parse_to_standard_date` (lines 264-305)
- `utils/date_parser.py` exists but needs formalization

---

### Decision #6: Enrichment Service Architecture (Medium Priority)

**Blocks:** Epic 5 (Company Enrichment)

**Questions to Address:**
- Complex approach (CI-002: Provider/Gateway abstraction) vs Simplified (S-001~S-004)?
- For MVP: Use StubProvider or implement EQC integration?
- Async queue implementation (defer to Growth phase)?
- Confidence scoring thresholds (≥0.90 auto-accept, 0.60-0.90 review, <0.60 async)?

**Existing Context:**
- Brownfield doc §"Company Enrichment Service Architecture" (lines 200-333)
- Partial implementation exists in `domain/company_enrichment/`
- Decision pending: MVP scope vs full implementation

---

## Decision #3: Hybrid Pipeline Step Protocol ✅

### Decision Summary

**Problem:** Need formal contract for 100+ transformation steps across all domains. Brownfield code uses row-level processing, but PRD examples show DataFrame-level operations. Conflict between performance (DataFrame) and validation (row-level).

**Solution:** Support both DataFrame-level and Row-level steps with clear protocols.

### Dual Protocol Architecture

**DataFrame Steps (Bulk Operations):**
```python
class DataFrameStep(Protocol):
    def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Bulk DataFrame transformation (vectorized operations)"""
        ...
```

**Row Transform Steps (Validation & Enrichment):**
```python
class RowTransformStep(Protocol):
    def apply(self, row: Row, context: Dict) -> StepResult:
        """Per-row transformation with detailed error tracking"""
        ...
```

**Pipeline Integration:**
```python
class Pipeline:
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        for step in self.steps:
            if isinstance(step, DataFrameStep):
                df = step.execute(df, context)  # Bulk
            elif isinstance(step, RowTransformStep):
                df = self._apply_row_step(step, df, context)  # Iterate
        return df
```

### Usage Guidelines

**Use DataFrame Steps For:**
- Structural operations: add columns, filter rows, join DataFrames
- Pandera validation (Bronze/Gold schemas)
- Bulk calculations: sums, aggregations, rolling windows
- Database loading

**Use Row Steps For:**
- Pydantic validation (Silver layer, per-row business rules)
- Company enrichment (external API calls per company)
- Complex per-row logic (date parsing with fallbacks)
- Error collection with per-row attribution

**Recommended Pipeline Order:**
1. DataFrame steps first (fast bulk operations)
2. Row steps in middle (validation, enrichment)
3. DataFrame steps last (final projection, database load)

### Example: Annuity Pipeline (Epic 4 Story 4.3)

```python
pipeline.add_step(BronzeValidationStep())        # DataFrame - pandera
pipeline.add_step(ParseDatesStep())              # DataFrame - bulk date parsing
pipeline.add_step(CleanseCompanyNamesStep())     # DataFrame - bulk regex
pipeline.add_step(ValidateInputRowsStep())       # Row - Pydantic validation
pipeline.add_step(EnrichCompanyIDsStep())        # Row - external API lookup
pipeline.add_step(ValidateOutputRowsStep())      # Row - Pydantic validation
pipeline.add_step(GoldProjectionStep())          # DataFrame - column selection
pipeline.add_step(GoldValidationStep())          # DataFrame - pandera
```

### Implementation Notes (Epic 1 Stories 1.5 & 1.10)

- Story 1.5: Implement basic Pipeline with both step types
- Story 1.10: Add advanced features (retries, optional steps, metrics)
- Preserve existing brownfield `RowTransformStep` code
- All domain pipelines (Epic 4, 9) follow this pattern

---

## Decision #4: Hybrid Error Context Standards ✅

### Decision Summary

**Problem:** 100+ stories need consistent error messages with sufficient context for debugging. Without standards, errors lack actionable information (which row? which field? what input?).

**Solution:** Use exceptions with required structured context fields. Standard error format.

### Standard Error Format

```
[ERROR_TYPE] Base message | Domain: X | Row: N | Field: Y | Input: {...}
```

### Required Context Fields

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

### Implementation

```python
@dataclass
class ErrorContext:
    """Standard error context for all WorkDataHub operations."""
    error_type: str
    operation: str
    domain: Optional[str] = None
    row_number: Optional[int] = None
    field: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
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
```

### Example Error Messages

```
[ValidationError] Cannot parse '不是日期' as date, expected format: YYYYMM, YYYY年MM月, YYYY-MM | Domain: annuity_performance | Row: 15 | Field: 月度 | Input: {"value": "不是日期"}

[DiscoveryError] No files found matching patterns ['*年金*.xlsx'] in path reference/monthly/202501/收集数据/业务收集/V2 | Domain: annuity_performance | Stage: file_matching

[EnrichmentError] Company lookup failed: API timeout after 5000ms | Domain: annuity_performance | Row: 42 | Field: 客户名称 | Input: {"company_name": "公司A有限公司"}
```

### Integration Points

- Epic 2 Story 2.5: Failed row CSV export uses `ErrorContext` fields
- Epic 3 Story 3.5: Discovery errors include `failed_stage` context
- Epic 8: Structured logging consumes `ErrorContext` for monitoring

---

## Decision #5: Explicit Chinese Date Format Priority ✅

### Decision Summary

**Problem:** Excel files contain dates in wildly inconsistent formats (integers, Chinese strings, ISO strings, 2-digit years). Need predictable parsing without dateutil fallback surprises.

**Solution:** Explicit format priority list with full-width normalization and range validation (2000-2030). No fallback.

### Supported Formats (Priority Order)

1. `date`/`datetime` objects → Passthrough
2. `YYYYMMDD` (8 digits) → `date(YYYY, MM, DD)`
3. `YYYYMM` (6 digits) → `date(YYYY, MM, 1)` (first day of month)
4. `YYYY-MM-DD` → ISO full date
5. `YYYY-MM` → `date(YYYY, MM, 1)`
6. `YYYY年MM月DD日` → Chinese full date
7. `YYYY年MM月` → `date(YYYY, MM, 1)`
8. `YY年MM月` → `date(20YY, MM, 1)` if YY < 50, else `date(19YY, MM, 1)`

### Implementation

```python
def parse_yyyymm_or_chinese(value: Any) -> date:
    """Parse date with explicit format priority."""

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

### Integration Points

- Epic 2 Story 2.4: Implement as `utils/date_parser.py`
- Epic 4 Story 4.1: Annuity Pydantic models use `@field_validator('月度')`
- Test parity with legacy `parse_to_standard_date` for known edge cases

---

## Decision #6: Stub-Only Enrichment MVP ✅

### Decision Summary

**Problem:** Epic 5 defines sophisticated company enrichment with 8 stories (Provider abstraction, EQC API, async queue, observability). Risk: blocks Epic 4 annuity migration, adds complexity.

**Solution:** Defer real enrichment to Growth phase. MVP uses StubProvider + temporary IDs only.

### MVP Scope (Epic 5)

**Implemented Stories:**
- ✅ Story 5.1: `StubProvider` with test fixtures
- ✅ Story 5.2: Temporary ID generation (Decision #2)
- ✅ Story 5.5: `EnrichmentGateway` shell (stub + temp ID fallback only)

**Result:** All companies get temporary IDs in MVP

### Growth Phase (Epic 9-10)

**Deferred Stories:**
- Story 5.3: Full database schema (3 tables: company_master, company_name_index, enrichment_requests)
- Story 5.4: Multi-tier internal mapping resolver
- Story 5.6: Sync EQC API provider (budget-limited, token management)
- Story 5.7: Async enrichment queue (deferred resolution)
- Story 5.8: Observability & metrics (CSV export, cache hit rates)

**Result:** Backfill job resolves MVP temporary IDs to real company IDs

### MVP Implementation

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

### Configuration

```bash
# MVP .env
WDH_ENRICH_COMPANY_ID=0  # Disabled
WDH_COMPANY_ENRICHMENT_ENABLED=0  # Stub only

# Growth .env (Epic 9-10)
WDH_ENRICH_COMPANY_ID=1  # Enabled
WDH_PROVIDER_EQC_TOKEN=<token>
WDH_ENRICH_SYNC_BUDGET=5
```

### Rationale

1. **MVP Goal:** Prove core patterns (Bronze→Silver→Gold, validation, Strangler Fig)
2. **Enrichment is orthogonal:** Temporary IDs enable cross-domain joins (requirement met)
3. **Risk reduction:** Defer EQC complexity (30-min token expiry, captcha, rate limits)
4. **Faster to market:** Epic 4 annuity migration unblocked immediately
5. **Growth value:** Full enrichment becomes competitive advantage, not MVP blocker

---

### Decision #7: Naming Conventions (Medium Priority)

**Blocks:** All epics (consistency across 100+ stories)

**Questions to Address:**
- File naming: `snake_case` for all Python files?
- Class naming: `PascalCase` for classes, protocols?
- Function/variable naming: `snake_case`?
- Chinese field names in Pydantic models: Keep as-is or transliterate?
- Database objects: `lowercase_snake_case` (PostgreSQL convention)?
- Configuration files: `kebab-case.yml` or `snake_case.yml`?

---

### Decision #8: Logging Requirements (Medium Priority)

**Blocks:** Epic 1 (Foundation), Epic 8 (Monitoring)

**Questions to Address:**
- Required fields in all log entries (timestamp, level, logger_name, context)?
- Log levels per context (DEBUG for dev, INFO for prod)?
- Sensitive data sanitization rules (never log tokens, company IDs OK?)?
- Structured logging format (JSON)?
- Log rotation and retention (30 days per PRD)?

**Existing Context:**
- Epic 1 Story 1.3 specifies structured logging framework
- `structlog` or Python `logging` with JSON formatter

---

## Next Steps

1. **Resume at Decision #7:** Naming Conventions
2. **Complete Decision #8:** Logging Requirements
3. **Design novel patterns** (integration points, specialized algorithms)
4. **Define implementation patterns** (ensure AI agent consistency)
5. **Generate architecture document** (final deliverable)
6. **Update workflow status** (`docs/bmm-workflow-status.yaml`)

---

## Session Notes

**User Skill Level:** Intermediate
- Provided detailed technical explanations
- Presented options with trade-offs
- User actively contributed edge cases (version detection partial corrections scenario)
- User identified brownfield constraints (legacy `clean_company_name` logic)

**Facilitation Style:**
- Present 2-4 options per decision with clear pros/cons
- Explain rationale at intermediate depth (not basic, not expert)
- Incorporate user feedback and edge cases
- Validate decisions before proceeding

**Key Insights:**
- Version detection more complex than standard "highest number wins" due to partial domain corrections
- Company normalization must maintain legacy parity (extensive pattern list)
- Brownfield constraints require careful integration with existing code
- 100% legacy parity is non-negotiable during migration

---

**End of Checkpoint**

_To resume: Review this checkpoint, confirm understanding of completed decisions, proceed to Decision #3: Pipeline Step Protocol._
