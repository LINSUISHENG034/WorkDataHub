# Sprint Change Proposal: EQC Data Persistence & Legacy Table Integration

**Date:** 2025-12-14
**Trigger:** Legacy system feature gap (Data retention for analytics)
**Author:** Sm (Scrum Master)
**Proposed Story:** 6.2-P5 (Patch Story for Epic 6: Company Enrichment Service)
**Status:** ✅ Approved with Revisions
**PM Review:** `docs/sprint-artifacts/reviews/pm-review-eqc-data-persistence-2025-12-14.md`

---

## 1. Issue Summary

### Current State
The legacy `annuity_hub` crawler persisted rich company data (`base_info`, `business_info`, `labels`) to MongoDB for every EQC query, enabling:
- Historical data analysis and trend tracking
- Offline company profile queries
- Audit trail for data enrichment operations

### Gap Identified
The new `EqcProvider` (Story 6.6) currently only caches the name-to-ID mapping in `enrichment_index`, discarding valuable business details from EQC API responses:
- `EQCClient.search_company()` and `get_company_detail()` parse responses but don't preserve raw data
- `EqcProvider._cache_result()` only writes to `enrichment_index` (lookup key → company_id)
- `enterprise.company_master` table exists but is underutilized (only stores basic fields)

### Key Discovery During PM Review
Legacy enterprise data has already been migrated to PostgreSQL:

| Table | Record Count | Description |
|-------|--------------|-------------|
| `enterprise.base_info` | 28,576 | Company basic information |
| `enterprise.business_info` | 11,542 | Company business details |
| `enterprise.biz_label` | 126,332 | Business labels |
| `enterprise.enrichment_index` | 42,527 | Lookup cache |

### Architecture Issue Identified
`company_master` and `base_info` tables have overlapping purposes:
- Both use `company_id` as primary key
- Both store company basic information
- Maintaining two tables increases complexity and risks data inconsistency

### Business Impact
- **Data Loss**: Rich attributes (Registration Capital, Address, Industry, Labels) are discarded after each API call
- **Redundant API Costs**: Future analytics or audits may require re-querying EQC API (budget-limited)
- **Legacy Parity Gap**: Cannot replicate historical data analysis workflows from legacy system

---

## 2. Approved Architecture Decision

### Decision: Consolidate to Legacy Table Structure

**Rationale:**
1. **Simplify data model**: Maintain one set of tables, reduce complexity
2. **Data consistency**: Unified data source, avoid inconsistency
3. **Legacy alignment**: Keep same data structure as Legacy system
4. **Data refresh capability**: Use existing `company_id` to refresh data

### Revised Data Storage Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Enterprise Data Storage Architecture               │
├─────────────────────────────────────────────────────────────────┤
│  base_info (Primary Table)                                      │
│  ├── company_id (PK)                                            │
│  ├── companyFullName, unite_code, province, reg_cap...          │
│  └── raw_data (JSONB) [NEW] - Complete API response             │
│                                                                 │
│  business_info (Detail Table)                                   │
│  ├── company_id (PK/FK)                                         │
│  └── address, legal_person_name, business_scope...              │
│                                                                 │
│  biz_label (Label Table)                                        │
│  ├── companyId (FK)                                             │
│  └── type, lv1Name, lv2Name, lv3Name, lv4Name                   │
│                                                                 │
│  enrichment_index (Lookup Cache)                                │
│  └── lookup_key → company_id mapping                            │
│                                                                 │
│  company_master → Deprecate or reposition as "normalized view"  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Story Definition

### Story: 6.2-P5 - EQC Data Persistence & Legacy Table Integration

**Objective:**
1. Write EQC query results to Legacy table structure (`base_info`, `business_info`, `biz_label`)
2. Support data refresh based on existing `company_id`
3. Add `raw_data` column to `base_info` table for complete API response storage

### Acceptance Criteria

| AC | Description | Priority |
|----|-------------|----------|
| AC1 | Add `raw_data` JSONB column and `updated_at` column to `base_info` table | Required |
| AC2 | `EqcProvider` writes search results to `base_info` table on successful query | Required |
| AC3 | Call `findDepart` and write to `business_info` table | Optional (Phase 2) |
| AC4 | Call `findLabels` and write to `biz_label` table | Optional (Phase 2) |
| AC5 | Provide data refresh capability: re-query and update based on existing `company_id` | Required |
| AC6 | Deprecate or reposition `company_master` table | Required |
| AC7 | Add configuration for data freshness threshold (`eqc_data_freshness_threshold_days`) | Required |
| AC8 | Implement `EqcDataRefreshService` with staleness detection | Required |
| AC9 | Provide CLI entry point for data refresh (`work_data_hub.cli.eqc_refresh`) | Required |
| AC10 | Provide Dagster job entry point for data refresh | Optional |
| AC11 | Unit tests cover new functionality | Required |
| AC12 | Integration test verifies end-to-end flow | Required |
| AC13 | Create cleansing rules YAML configuration for `business_info` | Required |
| AC14 | Implement `CleansingRuleEngine` with configurable rules | Required |
| AC15 | Add `_cleansing_status` column to `business_info` table | Required |
| AC16 | Integrate cleansing into data refresh flow | Required |
| AC17 | Provide CLI for manual cleansing operations | Required |
| AC18 | Unit tests for cleansing rules | Required |
| AC19 | Implement `--initial-full-refresh` CLI command | Required |
| AC20 | Implement checkpoint/resume mechanism | Required |
| AC21 | Generate refresh report with success/failure statistics | Required |
| AC22 | Post-refresh verification queries | Required |

---

## 4. Technical Changes

### 4.1 Database Schema Enhancement
**File:** `io/schema/migrations/versions/YYYYMMDD_NNNNNN_add_raw_data_to_base_info.py`

```sql
-- Add raw_data column to base_info (NOT company_master)
ALTER TABLE enterprise.base_info
ADD COLUMN raw_data JSONB DEFAULT NULL;

-- Add updated_at column if not exists
ALTER TABLE enterprise.base_info
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
```

### 4.2 EqcProvider Enhancement
**File:** `src/work_data_hub/infrastructure/enrichment/eqc_provider.py`

Update `_cache_result` to write to `base_info` table:

```python
def _cache_result(self, company_name: str, result: CompanyInfo, raw_response: Dict) -> None:
    """
    Cache successful lookup result to both enrichment_index and base_info.
    """
    # 1. Write to enrichment_index (existing logic)
    # ...

    # 2. NEW: Write to base_info table
    self.mapping_repository.upsert_base_info(
        company_id=result.company_id,
        search_key_word=company_name,
        company_full_name=result.official_name,
        unite_code=result.unified_credit_code,
        raw_data=raw_response,
    )
```

### 4.3 Repository Enhancement
**File:** `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`

Add `upsert_base_info` method:

```python
def upsert_base_info(
    self,
    company_id: str,
    search_key_word: str,
    company_full_name: str,
    unite_code: Optional[str],
    raw_data: Dict[str, Any],
) -> bool:
    """
    Upsert company data to base_info table with raw API response.

    Conflict Resolution:
    - If company_id exists: Update raw_data and updated_at
    - Rationale: Preserve existing structured fields, update raw data
    """
    query = text("""
        INSERT INTO enterprise.base_info
            (company_id, search_key_word, "companyFullName", unite_code, raw_data, updated_at)
        VALUES
            (:company_id, :search_key_word, :company_full_name, :unite_code, :raw_data, NOW())
        ON CONFLICT (company_id) DO UPDATE SET
            raw_data = EXCLUDED.raw_data,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
    """)
    # ... implementation
```

---

## 5. Data Freshness Management

### 5.1 Requirement

EQC platform enterprise data may be updated over time. The system needs a mechanism to:
1. Detect stale data based on configurable threshold
2. Provide convenient entry points for users to trigger refresh
3. User decides whether to refresh (not automatic)

### 5.2 Configuration

**File:** `src/work_data_hub/config/settings.py`

```python
# EQC Data Freshness Settings
eqc_data_freshness_threshold_days: int = 90  # Data older than this is considered stale
eqc_data_refresh_batch_size: int = 100       # Batch size for refresh operations
eqc_data_refresh_rate_limit: float = 1.0     # Requests per second during refresh
```

**Environment Variables:**
```bash
WDH_EQC_DATA_FRESHNESS_THRESHOLD_DAYS=90
WDH_EQC_DATA_REFRESH_BATCH_SIZE=100
WDH_EQC_DATA_REFRESH_RATE_LIMIT=1.0
```

### 5.3 Data Refresh Service
**File:** `src/work_data_hub/infrastructure/enrichment/data_refresh_service.py`

```python
class EqcDataRefreshService:
    """
    Service for refreshing enterprise data based on existing company_ids.
    """

    def get_stale_companies(self, threshold_days: Optional[int] = None) -> List[StaleCompanyInfo]:
        """
        Get list of companies with stale data.

        Returns companies where:
        - updated_at is NULL (never refreshed), OR
        - updated_at < NOW() - threshold_days
        """
        # ... implementation

    def refresh_by_company_ids(
        self,
        company_ids: List[str],
        include_business_info: bool = True,
        include_labels: bool = True,
    ) -> RefreshResult:
        """
        Refresh enterprise data for given company_ids.
        """
        # ... implementation
```

### 5.4 Refresh Entry Points

#### Entry Point 1: CLI Command (Primary)

```bash
# Check stale data status
uv run python -m work_data_hub.cli.eqc_refresh --status

# Refresh stale data (interactive confirmation)
uv run python -m work_data_hub.cli.eqc_refresh --refresh-stale

# Refresh specific companies
uv run python -m work_data_hub.cli.eqc_refresh --company-ids 1000065057,1000087994

# Refresh all data (with confirmation)
uv run python -m work_data_hub.cli.eqc_refresh --refresh-all

# Dry run (show what would be refreshed)
uv run python -m work_data_hub.cli.eqc_refresh --refresh-stale --dry-run
```

#### Entry Point 2: Dagster Job (For Orchestration)

```python
@job(
    name="eqc_data_refresh_job",
    description="Refresh stale EQC enterprise data",
)
def eqc_data_refresh_job():
    """
    Dagster job for refreshing EQC data.
    Can be triggered manually from Dagster UI.
    """
    # ... implementation
```

### 5.5 Data Refresh Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Data Refresh Flow                            │
├─────────────────────────────────────────────────────────────────┤
│  Step 1: Identify stale companies                               │
│      │   SELECT company_id FROM base_info                       │
│      │   WHERE updated_at IS NULL                               │
│      │      OR updated_at < NOW() - INTERVAL 'N days'           │
│      ↓                                                          │
│  Step 2: User confirmation (CLI/UI prompt)                      │
│      │   "Found 8,342 stale companies. Refresh? [y/N]"          │
│      ↓                                                          │
│  Step 3: For each company_id, call EQC API                      │
│      ├── get_base_info (search by company_id)                   │
│      ├── get_business_info (findDepart)                         │
│      └── get_label_info (findLabels)                            │
│      ↓                                                          │
│  Step 4: UPSERT to corresponding tables                         │
│      ├── base_info (with raw_data, updated_at = NOW())          │
│      ├── business_info                                          │
│      └── biz_label                                              │
│      ↓                                                          │
│  Step 5: Update enrichment_index cache                          │
│      ↓                                                          │
│  Step 6: Report results                                         │
│      │   "Refreshed: 8,300 | Failed: 42 | Skipped: 0"           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Cleansing Framework for business_info

### 6.1 Problem Statement

Current `enterprise.business_info` table stores raw text data directly parsed from EQC API JSON responses:

| Field | Current Value | Issue |
|-------|---------------|-------|
| `registerCaptial` | `'80000.00万元'` | Numeric + unit mixed, should split |
| `collegues_num` | `'企业选择不公示'` | Non-numeric text, should be NULL |
| `end_date` | `''` | Empty string, should be NULL |
| Date fields | `'1997-04-03'` | String format, should be DATE type |

### 6.2 Design Principles

1. **Configuration-Driven**: Cleansing rules defined in YAML, not hardcoded
2. **Dynamically Updatable**: Rules can be updated without code changes
3. **Graceful Degradation**: If cleansing fails, preserve original string value
4. **Audit Trail**: Track which fields were cleansed vs. preserved as-is
5. **Incremental**: Can re-cleanse existing data when rules are updated

### 6.3 Cleansing Rules Configuration

**File:** `src/work_data_hub/config/cleansing_rules/business_info.yaml`

```yaml
# Business Info Cleansing Rules
table: enterprise.business_info
source_column: raw_data  # From base_info.raw_data JSON

fields:
  # === Numeric Fields ===
  registerCaptial:
    target_type: numeric
    rules:
      - name: extract_chinese_currency
        pattern: '^([\d.]+)(万元|元|亿元)?$'
        extract_group: 1
        multiplier_map:
          万元: 10000
          亿元: 100000000
          元: 1
          null: 1
      - name: null_if_non_numeric
        condition: "not_matches_pattern"
        action: set_null
    fallback: preserve_original

  collegues_num:
    target_type: integer
    rules:
      - name: extract_integer
        pattern: '^(\d+)人?$'
        extract_group: 1
      - name: null_if_text
        condition: "contains_chinese"
        action: set_null
    fallback: set_null  # '企业选择不公示' → NULL

  # === Date Fields ===
  registered_date:
    target_type: date
    rules:
      - name: parse_date
        formats:
          - '%Y-%m-%d'
          - '%Y/%m/%d'
          - '%Y年%m月%d日'
      - name: null_if_empty
        condition: "is_empty_string"
        action: set_null
    fallback: preserve_original
```

### 6.4 Cleansing Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Data Cleansing Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  base_info.raw_data (JSONB)                                     │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────────────────────────────────┐                        │
│  │     CleansingRuleEngine             │                        │
│  │  ┌─────────────────────────────┐    │                        │
│  │  │  Load rules from YAML       │    │                        │
│  │  │  (business_info.yaml)       │    │                        │
│  │  └─────────────────────────────┘    │                        │
│  │              │                      │                        │
│  │              ▼                      │                        │
│  │  ┌─────────────────────────────┐    │                        │
│  │  │  Apply rules per field      │    │                        │
│  │  │  - Type conversion          │    │                        │
│  │  │  - Pattern extraction       │    │                        │
│  │  │  - Null handling            │    │                        │
│  │  └─────────────────────────────┘    │                        │
│  │              │                      │                        │
│  │              ▼                      │                        │
│  │  ┌─────────────────────────────┐    │                        │
│  │  │  Fallback on failure        │    │                        │
│  │  │  - preserve_original        │    │                        │
│  │  │  - set_null                 │    │                        │
│  │  └─────────────────────────────┘    │                        │
│  └─────────────────────────────────────┘                        │
│      │                                                          │
│      ▼                                                          │
│  business_info (Cleansed Data)                                  │
│  + _cleansing_status (JSONB) - Track cleansing results          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.5 Cleansing Entry Points

```bash
# Preview cleansing for specific company
uv run python -m work_data_hub.cli.cleanse_data --preview --company-id 1000065057

# Cleanse all business_info records
uv run python -m work_data_hub.cli.cleanse_data --table business_info

# Re-cleanse after rule update
uv run python -m work_data_hub.cli.cleanse_data --table business_info --force

# Dry run
uv run python -m work_data_hub.cli.cleanse_data --table business_info --dry-run
```

---

## 7. Initial Full Refresh Milestone

### 7.1 Objective

After completing the architecture refactoring (Phase 1-4), perform a **one-time full refresh** of all existing enterprise data to establish a clean baseline for future incremental updates.

### 7.2 Scope

| Table | Current Records | Action |
|-------|-----------------|--------|
| `base_info` | 28,576 | Re-query EQC API by company_id, update all fields + raw_data |
| `business_info` | 11,542 | Re-query EQC API (findDepart), apply cleansing rules |
| `biz_label` | 126,332 | Re-query EQC API (findLabels), replace existing labels |
| `enrichment_index` | 42,527 | Update mappings based on refreshed data |

### 7.3 Resource Estimation

**API Calls per Company:**
- `search` (get_base_info): 1 call
- `findDepart` (get_business_info): 1 call
- `findLabels` (get_label_info): 1 call
- **Total: 3 calls per company**

**Total API Calls:**
- 28,576 companies × 3 calls = **85,728 API calls**

**Time Estimation (at 1 req/sec rate limit):**
- 85,728 seconds ≈ **23.8 hours**
- With parallelization (3 concurrent): ~8 hours

### 7.4 CLI Command

```bash
# Full refresh with default settings
uv run python -m work_data_hub.cli.eqc_refresh --initial-full-refresh

# Full refresh with custom batch size and rate limit
uv run python -m work_data_hub.cli.eqc_refresh \
    --initial-full-refresh \
    --batch-size 500 \
    --rate-limit 2.0 \
    --resume-from-checkpoint

# Dry run (estimate only)
uv run python -m work_data_hub.cli.eqc_refresh \
    --initial-full-refresh \
    --dry-run
```

### 7.5 Checkpoint & Resume

```python
class RefreshCheckpoint:
    """
    Tracks refresh progress for resume capability.
    """
    refresh_id: str           # Unique refresh session ID
    started_at: datetime
    total_companies: int
    processed_companies: int
    last_company_id: str      # For resume
    status: str               # 'running', 'paused', 'completed', 'failed'
    errors: List[Dict]        # Failed company_ids with error messages
```

---

## 8. company_master Table Disposition

### Decision: Deprecate

**Rationale:**
1. `base_info` already serves as the primary company data table
2. Maintaining two tables with overlapping purposes increases complexity
3. `company_master` has minimal data (only from Story 6.3 testing)

**Migration Plan:**
1. Mark `company_master` as deprecated in documentation
2. Remove references to `company_master` in new code
3. Keep table for backward compatibility (no data migration needed)
4. Future: Drop table in a cleanup migration

---

## 9. Open Questions - Final Decisions

| Question | Decision |
|----------|----------|
| Q1: Labels Endpoint (Phase 2) | ✅ Defer to Phase 2 |
| Q2: GIN Index | ✅ No index initially |
| Q3: Data Retention Policy | ✅ No automatic cleanup |
| Q4: Epic/Story Number | ✅ **Patch Story 6.2-P5** |
| Q5: raw_data column location | ✅ **base_info table** (not company_master) |
| Q6: company_master disposition | ✅ **Deprecate** |

---

## 10. Implementation Phases Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              Story 6.2-P5 Implementation Phases                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Core Data Persistence                                 │
│  ├── Migration: raw_data + updated_at columns                   │
│  ├── EQCClient: return raw response                             │
│  ├── EqcProvider: write to base_info                            │
│  └── Repository: upsert_base_info method                        │
│                                                                 │
│  Phase 2: Data Freshness Management                             │
│  ├── Configuration: freshness threshold                         │
│  ├── EqcDataRefreshService: staleness detection                 │
│  ├── CLI: eqc_refresh commands                                  │
│  └── (Optional) Dagster job                                     │
│                                                                 │
│  Phase 3: Cleanup & Testing                                     │
│  ├── Deprecate company_master                                   │
│  ├── Unit tests                                                 │
│  └── Integration tests                                          │
│                                                                 │
│  Phase 4: Data Cleansing Framework                              │
│  ├── Cleansing rules YAML                                       │
│  ├── CleansingRuleEngine                                        │
│  ├── Migration: _cleansing_status column                        │
│  └── CLI: cleanse_data commands                                 │
│                                                                 │
│  Phase 5: Initial Full Refresh [MILESTONE]                      │
│  ├── Checkpoint/resume mechanism                                │
│  ├── Batch processing                                           │
│  ├── Execute full refresh (~28,576 companies)                   │
│  └── Verify data integrity                                      │
│                                                                 │
│  ════════════════════════════════════════════════════════════   │
│  BASELINE ESTABLISHED - Ready for incremental updates           │
│  ════════════════════════════════════════════════════════════   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Implementation Checklist

### Phase 1: Core Data Persistence
- [ ] Create migration: `add_raw_data_to_base_info.py` (add `raw_data` JSONB and `updated_at` columns)
- [ ] Update `EQCClient` to return raw response alongside parsed results
- [ ] Update `EqcProvider._cache_result` to write to `base_info`
- [ ] Add `upsert_base_info` method to `CompanyMappingRepository`

### Phase 2: Data Freshness Management
- [ ] Add configuration settings to `settings.py`:
  - [ ] `eqc_data_freshness_threshold_days` (default: 90)
  - [ ] `eqc_data_refresh_batch_size` (default: 100)
  - [ ] `eqc_data_refresh_rate_limit` (default: 1.0)
- [ ] Create `EqcDataRefreshService` class:
  - [ ] `get_freshness_status()` - Get overall freshness statistics
  - [ ] `get_stale_companies()` - List companies with stale data
  - [ ] `refresh_stale_companies()` - Refresh stale data with rate limiting
  - [ ] `refresh_by_company_ids()` - Refresh specific companies
- [ ] Create CLI module `work_data_hub/cli/eqc_refresh.py`:
  - [ ] `--status` - Show freshness report
  - [ ] `--refresh-stale` - Refresh stale data
  - [ ] `--refresh-all` - Refresh all data
  - [ ] `--company-ids` - Refresh specific companies
  - [ ] `--dry-run` - Preview mode
- [ ] (Optional) Create Dagster job `eqc_data_refresh_job`

### Phase 3: Cleanup & Testing
- [ ] Update documentation to mark `company_master` as deprecated
- [ ] Add unit tests for new functionality
- [ ] Add integration test for end-to-end flow
- [ ] Update sprint-status.yaml with Story 6.2-P5

### Phase 4: Data Cleansing Framework
- [ ] Create cleansing rules YAML: `config/cleansing_rules/business_info.yaml`
- [ ] Implement `CleansingRuleEngine` class
- [ ] Create migration: `add_cleansing_status_to_business_info.py`
- [ ] Integrate cleansing into `EqcDataRefreshService`
- [ ] Create CLI module `work_data_hub/cli/cleanse_data.py`
- [ ] Add unit tests for cleansing rules
- [ ] Document cleansing rule syntax

### Phase 5: Initial Full Refresh
- [ ] Implement `--initial-full-refresh` CLI option
- [ ] Create `RefreshCheckpoint` model and persistence
- [ ] Implement batch processing with progress tracking
- [ ] Implement resume-from-checkpoint logic
- [ ] Create post-refresh verification script
- [ ] Generate refresh report
- [ ] **Execute initial full refresh** (milestone)
- [ ] Verify data integrity after refresh

---

## 12. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| `base_info` schema changes break existing queries | Medium | Low | Add column only, no schema changes to existing columns |
| Data refresh consumes API budget | High | Medium | Implement budget controls, batch processing with rate limiting |
| `company_master` deprecation breaks existing code | Medium | Low | Search codebase for references before deprecation |

---

## 13. Approval

**Status:** ✅ **Approved with Revisions**

**Approved By:** PM (Product Manager)

**Approval Date:** 2025-12-14

**Next Steps:**
1. ~~SM updates original proposal based on PM review~~ ✅ Done
2. Create Story 6.2-P5 in sprint-status.yaml
3. Dev agent implements changes per checklist
4. Code review by senior developer

---

**Document Version:** 2.0
**Last Updated:** 2025-12-14
**Revision History:**
- v1.0: Initial proposal (company_master approach)
- v2.0: Revised based on PM review (base_info consolidation, data freshness, cleansing framework, full refresh milestone)
