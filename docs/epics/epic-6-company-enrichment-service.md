# Epic 5: Company Enrichment Service

**Goal:** Build a flexible company ID enrichment service using the Provider abstraction pattern, supporting multi-tier resolution (internal mappings → EQC API → async queue) with temporary ID generation for unresolved companies. This epic enables cross-domain joins with consistent enterprise company IDs.

**Business Value:** Company names in Excel files vary ("公司A", "A公司", "公司A有限公司"). Enrichment resolves these to canonical company IDs, enabling accurate customer attribution across domains. Temporary IDs ensure pipelines never block on enrichment failures.

**Dependencies:** Epic 1 (infrastructure, database), Epic 4 Story 4.3 (enrichment integration point)

**Note:** Can be developed in parallel with Epic 3-4 since Story 4.3 uses stub enrichment initially.

---

### Story 5.1: EnterpriseInfoProvider Protocol and Stub Implementation

As a **data engineer**,
I want **a Provider protocol defining the enrichment contract with a testable stub implementation**,
So that **pipelines can develop against stable interface without requiring external services**.

**Acceptance Criteria:**

**Given** I need company enrichment without external dependencies
**When** I define `EnterpriseInfoProvider` protocol
**Then** Protocol should specify:
```python
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class CompanyInfo:
    company_id: str
    official_name: str
    unified_credit_code: Optional[str]
    confidence: float  # 0.0-1.0
    match_type: str  # "exact", "fuzzy", "alias", "temporary"

class EnterpriseInfoProvider(Protocol):
    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        """Resolve company name to CompanyInfo or None if not found"""
        ...
```

**And** When I implement `StubProvider` for testing
**Then** Stub should:
- Return predefined fixtures for known test company names
- Return `None` for unknown names (simulates not found)
- Be configurable via constructor: `StubProvider(fixtures={"公司A": CompanyInfo(...)})`
- Always return confidence=1.0 (perfect match for fixtures)

**And** When pipeline uses stub provider in tests
**Then** Enrichment behaves predictably without external services

**And** When I inject stub into Story 4.3 annuity pipeline
**Then** Pipeline processes data successfully with fixture company IDs

**Prerequisites:** Epic 1 Story 1.6 (Clean Architecture boundaries for DI pattern)

**Technical Notes:**
- Implement protocol in `domain/enrichment/provider_protocol.py`
- Stub implementation in `domain/enrichment/stub_provider.py`
- Protocol ensures all providers have same interface (stub, EQC, legacy)
- Stub enables Epic 4 development without Epic 5 completion
- Reference: PRD §825-861 (FR-3.3: Company Enrichment Integration), reference/01_company_id_analysis.md

---

### Story 5.2: Temporary Company ID Generation (HMAC-based)

As a **data engineer**,
I want **stable temporary IDs for unresolved companies using HMAC**,
So that **same company always maps to same temporary ID across runs, enabling consistent joins**.

**Acceptance Criteria:**

**Given** I have unresolved company name `"新公司XYZ"`
**When** I generate temporary ID
**Then** System should:
- Generate stable ID: `HMAC_SHA1(WDH_ALIAS_SALT, "新公司XYZ")` → Base32 encode → `IN_<16-chars>`
- Example: `"新公司XYZ"` → `"IN_ABCD1234EFGH5678"`
- Same input always produces same ID (deterministic)
- Different inputs produce different IDs (collision-resistant)
- Prefix `IN_` distinguishes temporary from real company IDs

**And** When I generate ID for `"新公司XYZ"` twice
**Then** Both calls return identical ID: `"IN_ABCD1234EFGH5678"`

**And** When I generate IDs for 10,000 different company names
**Then** No collisions occur (all IDs unique)

**And** When temporary ID stored in database
**Then** Joins work correctly: same company name → same temporary ID → consistent attribution

**And** When company later resolved via async enrichment
**Then** Temporary ID replaced with real company_id in future runs

**Prerequisites:** None (pure cryptographic function)

**Technical Notes:**
- Implement in `domain/enrichment/temp_id_generator.py`
- Use Python `hmac` module with SHA1 algorithm
- Salt from environment variable: `WDH_ALIAS_SALT` (secret, unique per deployment)
- Base32 encoding for URL-safe, readable IDs
- Function signature:
  ```python
  def generate_temp_company_id(company_name: str, salt: str) -> str:
      """Generate stable temporary ID: IN_<16-char-Base32>"""
      normalized = company_name.strip().lower()  # Normalize before hashing
      digest = hmac.new(salt.encode(), normalized.encode(), hashlib.sha1).digest()
      encoded = base64.b32encode(digest)[:16].decode('ascii')
      return f"IN_{encoded}"
  ```
- Security: Salt must be kept secret (not committed to git)
- Reference: PRD §834 (Temporary ID generation), reference/01_company_id_analysis.md §S-002

---

### Story 5.3: Internal Mapping Tables and Database Schema

As a **data engineer**,
I want **database tables for internal company mappings with migration**,
So that **high-confidence mappings are cached locally without API calls**.

**Acceptance Criteria:**

**Given** I need to store company enrichment data
**When** I create database migrations
**Then** I should have tables:

**`enterprise.company_master`:**
- `company_id` (PK, VARCHAR(50))
- `official_name` (VARCHAR(255), NOT NULL)
- `unified_credit_code` (VARCHAR(50), UNIQUE)
- `aliases` (TEXT[], alternative names)
- `source` (VARCHAR(50), e.g., "eqc_api", "manual", "legacy_import")
- `created_at`, `updated_at` (timestamps)

**`enterprise.company_name_index`:**
- `normalized_name` (VARCHAR(255), PK)
- `company_id` (FK → company_master, NOT NULL)
- `match_type` (VARCHAR(20), e.g., "exact", "fuzzy", "alias")
- `confidence` (DECIMAL(3,2), range 0.00-1.00)
- `created_at` (timestamp)
- Index on `(normalized_name, confidence DESC)` for fast lookup

**`enterprise.enrichment_requests`:**
- `request_id` (PK, UUID)
- `company_name` (VARCHAR(255), NOT NULL)
- `status` (VARCHAR(20), e.g., "pending", "processing", "done", "failed")
- `company_id` (FK → company_master, NULL until resolved)
- `confidence` (DECIMAL(3,2), NULL until resolved)
- `created_at`, `processed_at` (timestamps)
- Index on `(status, created_at)` for async processing queue

**And** When migration applied to fresh database
**Then** All tables created with correct schemas and constraints

**And** When I insert mapping: `("公司A有限公司", "COMP001", "exact", 1.00)`
**Then** Lookup of `"公司A有限公司"` returns `COMP001` with confidence 1.00

**And** When I insert enrichment request with status "pending"
**Then** Async processor can query pending requests ordered by created_at

**Prerequisites:** Epic 1 Story 1.7 (database migration framework)

**Technical Notes:**
- Migration file: `io/schema/migrations/YYYYMMDD_HHMM_create_enterprise_schema.py`
- Use schema `enterprise` to separate from domain tables
- Normalized name: lowercase, trimmed, special chars removed
- Confidence scoring: ≥0.90 auto-accept, 0.60-0.90 flag for review, <0.60 async queue
- Reference: PRD §836-849 (Company enrichment data persistence)

---

### Story 5.4: Internal Mapping Resolver (Multi-Tier Lookup)

As a **data engineer**,
I want **multi-tier lookup checking internal mappings before expensive API calls**,
So that **90%+ of lookups are resolved locally with zero API cost and sub-millisecond latency**.

**Acceptance Criteria:**

**Given** I have internal mappings populated in `enterprise.company_name_index`
**When** I lookup company name `"公司A有限公司"`
**Then** Resolver should:
1. Normalize input: trim, lowercase, remove special chars
2. Check exact match in `company_name_index` (fastest)
3. If not found, check fuzzy match (Levenshtein distance ≤2)
4. If not found, check aliases from `company_master`
5. Return `CompanyInfo` with highest confidence match or `None`

**And** When exact match exists with confidence 1.00
**Then** Return immediately without fuzzy/alias checks (optimization)

**And** When fuzzy match found with confidence 0.85
**Then** Return match with `match_type="fuzzy"`, `confidence=0.85`

**And** When no match found in any tier
**Then** Return `None` (caller handles fallback: EQC API or temporary ID)

**And** When multiple matches found
**Then** Return highest confidence match, log others as alternatives

**And** When lookup succeeds from cache
**Then** Response time <5ms (measured in integration tests)

**Prerequisites:** Story 5.3 (database tables), Story 5.1 (provider protocol)

**Technical Notes:**
- Implement in `domain/enrichment/internal_resolver.py` as `InternalMappingResolver`
- Implements `EnterpriseInfoProvider` protocol (Story 5.1)
- Normalization function shared with temporary ID generator (Story 5.2)
- Fuzzy matching: Use `fuzzywuzzy` or `RapidFuzz` library (Levenshtein distance)
- SQL query optimization:
  ```sql
  SELECT company_id, match_type, confidence
  FROM enterprise.company_name_index
  WHERE normalized_name = %s
  ORDER BY confidence DESC
  LIMIT 1
  ```
- Caching: Consider in-memory LRU cache for hot lookups (optional optimization)
- Reference: PRD §831 (Multi-tier resolution strategy)

---

### Story 5.5: EnrichmentGateway Integration and Fallback Logic

As a **data engineer**,
I want **unified gateway coordinating internal resolver, temporary ID generation, and async queueing**,
So that **enrichment never blocks pipelines and all companies get valid IDs (real or temporary)**.

**Acceptance Criteria:**

**Given** I have internal resolver (Story 5.4) and temp ID generator (Story 5.2)
**When** I implement `EnrichmentGateway` class
**Then** Gateway should:
1. Try internal resolver first (Story 5.4)
2. If not found AND budget available: try EQC API (Story 5.6, future)
3. If still not found: generate temporary ID (Story 5.2)
4. If confidence <0.60: queue for async enrichment (Story 5.7, future)
5. Return `CompanyInfo` with appropriate match_type and confidence

**And** When internal resolver finds exact match
**Then** Return immediately with confidence 1.00, no API call, no temp ID

**And** When internal resolver returns None
**Then** Generate temporary ID and return:
```python
CompanyInfo(
    company_id="IN_ABCD1234EFGH5678",
    official_name="新公司XYZ",  # Original name
    unified_credit_code=None,
    confidence=0.0,  # Temporary ID has no confidence
    match_type="temporary"
)
```

**And** When confidence between 0.60-0.90
**Then** Return company_id but set `needs_review=True` flag for human validation

**And** When gateway processes 1000 company names with 900 in cache
**Then** Only 100 generate temporary IDs (90% cache hit rate)

**And** When enrichment fails completely
**Then** Pipeline continues with temporary IDs (graceful degradation)

**Prerequisites:** Stories 5.1-5.4 (protocol, temp ID, internal resolver)

**Technical Notes:**
- Implement in `domain/enrichment/gateway.py` as `EnrichmentGateway`
- Implements `EnterpriseInfoProvider` protocol for pipeline compatibility
- Configuration: `WDH_ENRICH_ENABLED` (default: True), `WDH_ENRICH_SYNC_BUDGET` (default: 0 for MVP)
- Graceful degradation: enrichment is optional, pipeline never fails due to enrichment
- Metrics tracking:
  ```python
  EnrichmentStats:
      cache_hits: int
      temp_ids_generated: int
      api_calls: int  # For Story 5.6
      queue_depth: int  # For Story 5.7
  ```
- Integration with Story 4.3 annuity pipeline: inject gateway via DI
- Reference: PRD §836 (Gateway pattern), §855 (Graceful degradation)

---

### Story 5.6: EQC API Provider (Sync Lookup with Budget)

As a **data engineer**,
I want **synchronous EQC platform API lookup with budget limits**,
So that **high-value enrichment requests are resolved in real-time without runaway API costs**.

**Acceptance Criteria:**

**Given** I have EQC API credentials configured via `WDH_PROVIDER_EQC_TOKEN`
**When** I implement `EqcProvider` class
**Then** Provider should:
- Implement `EnterpriseInfoProvider` protocol (Story 5.1)
- Call EQC API endpoint: `POST /api/enterprise/search` with company name
- Parse response: extract `company_id`, `official_name`, `unified_credit_code`, confidence
- Respect budget: max `WDH_ENRICH_SYNC_BUDGET` calls per run (default: 0 for MVP, 5 for production)
- Timeout: 5 seconds per request (fail fast if API slow)
- Retry: 2 attempts on network timeout (not on 4xx errors)

**And** When API returns match with confidence 0.95
**Then** Return `CompanyInfo` with EQC data and cache to `enterprise.company_name_index`

**And** When API returns HTTP 404 (not found)
**Then** Return `None` (caller generates temporary ID)

**And** When API returns HTTP 401 (unauthorized)
**Then** Log error, disable provider for session, return `None` (fall back to temp IDs)

**And** When sync budget exhausted (5 calls made)
**Then** Return `None` immediately for remaining lookups (no more API calls this run)

**And** When API call succeeds
**Then** Cache result in `enterprise.company_name_index` for future runs

**Prerequisites:** Story 5.1 (provider protocol), Story 5.3 (database for caching)

**Technical Notes:**
- Implement in `domain/enrichment/eqc_provider.py`
- Use `requests` library with timeout and retry logic
- API token refresh: EQC tokens expire after 30 minutes (see reference doc §8)
- Budget tracking: instance variable `remaining_budget` decremented on each call
- Credential management:
  ```python
  class EqcProvider:
      def __init__(self, api_token: str, budget: int = 5):
          self.api_token = api_token
          self.remaining_budget = budget
  ```
- Cache writes are async (don't block on database write)
- Sanitize logs: NEVER log API token (security risk)
- Reference: PRD §833 (Sync lookup budget), §857-860 (Security & credentials), reference/01_company_id_analysis.md

---

### Story 5.7: Async Enrichment Queue (Deferred Resolution)

As a **data engineer**,
I want **async enrichment queue for low-confidence matches and unknowns**,
So that **temporary IDs are resolved to real IDs in background without blocking pipelines**.

**Acceptance Criteria:**

**Given** I have unresolved companies with temporary IDs
**When** enrichment gateway encounters low confidence match (<0.60)
**Then** System should:
- Insert into `enterprise.enrichment_requests` with status "pending"
- Include: company_name, temporary_id assigned, created_at
- Continue pipeline immediately (non-blocking)

**And** When async processor runs (separate Dagster job or cron)
**Then** Processor should:
- Query pending requests: `SELECT * FROM enrichment_requests WHERE status='pending' ORDER BY created_at LIMIT 100`
- Call EQC API for each (no budget limit for async)
- Update status: "pending" → "processing" → "done" or "failed"
- On success: update `company_name_index` with resolved mapping
- On failure after 3 retries: status="failed", log reason

**And** When company resolved via async queue
**Then** Next pipeline run uses cached mapping (no more temporary ID)

**And** When async processor fails mid-batch
**Then** Processing resumes from "pending" status on next run (idempotent)

**And** When queue depth exceeds 10,000
**Then** Log warning: "Enrichment queue backlog high, consider increasing async processing frequency"

**Prerequisites:** Story 5.3 (enrichment_requests table), Story 5.6 (EQC provider for API calls)

**Technical Notes:**
- Implement async processor in `orchestration/jobs.py` as `async_enrichment_job`
- Dagster schedule: run hourly or daily based on queue depth
- Status transitions: pending → processing (prevent duplicate processing) → done/failed
- Retry logic: exponential backoff for failed API calls (1min, 5min, 15min)
- Metrics: track queue depth, processing rate, success/failure ratio
- Future enhancement: priority queue (high-value companies processed first)
- Reference: PRD §833 (Async enrichment queue), §850 (Queue depth tracking)

---

### Story 5.8: Enrichment Observability and Export

As a **data engineer**,
I want **comprehensive metrics and CSV export of unknown companies**,
So that **I can monitor enrichment effectiveness and manually backfill critical unknowns**.

**Acceptance Criteria:**

**Given** I run annuity pipeline with enrichment enabled
**When** pipeline completes
**Then** System should log enrichment stats:
```json
{
  "enrichment_stats": {
    "total_lookups": 1000,
    "cache_hits": 850,
    "cache_hit_rate": 0.85,
    "temp_ids_generated": 100,
    "api_calls": 5,
    "sync_budget_used": 5,
    "async_queued": 45,
    "queue_depth_after": 120
  }
}
```

**And** When temporary IDs generated
**Then** Export CSV: `logs/unknown_companies_YYYYMMDD_HHMMSS.csv`
- Columns: `company_name, temporary_id, first_seen, occurrence_count`
- Sorted by occurrence_count DESC (most frequent unknowns first)

**And** When I review unknown companies CSV
**Then** I can manually add high-priority mappings to `enterprise.company_name_index`

**And** When enrichment stats tracked over time
**Then** I can monitor trends: cache hit rate improving, queue depth stable, temp ID rate decreasing

**And** When enrichment disabled via `WDH_ENRICH_ENABLED=False`
**Then** All companies get temporary IDs, stats show 100% temp ID rate

**Prerequisites:** Story 5.5 (gateway with metrics), Story 5.2 (temporary IDs)

**Technical Notes:**
- Implement metrics collection in `EnrichmentGateway` (Story 5.5)
- CSV export in `domain/enrichment/observability.py`
- Log stats via Epic 1 Story 1.3 structured logging
- CSV location: `logs/` directory (configurable via settings)
- Include occurrence count: track how many times each unknown company appears
- Dashboard integration (future): Expose metrics to Epic 8 monitoring
- Reference: PRD §849-855 (Enrichment observability)

---

