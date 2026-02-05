# Epic Technical Specification: Annuity Performance Domain Migration (MVP)

Date: 2025-11-28
Author: Link
Epic ID: 4
Status: Draft

---

## Overview

Epic 4 represents the first critical domain migration using the Strangler Fig pattern, proving that the modern WorkDataHub architecture can successfully replace legacy code with 100% output parity. This epic migrates the **annuity performance domain** - the most complex domain with enrichment, multi-sheet Excel processing, and intricate transformations.

**Why Annuity Performance First:**
The annuity domain was deliberately chosen as the MVP migration target because it represents the highest complexity in the system. Successfully migrating it validates that the Bronze→Silver→Gold architecture, multi-layer validation framework, and enrichment patterns can handle real-world complexity. This establishes the reference implementation pattern that all 5+ remaining domains will follow.

**Strategic Value:**
- Proves the Strangler Fig pattern works on production complexity
- Validates Epic 1-3 infrastructure under real workload
- Establishes repeatable migration patterns for Epic 9 (Growth Domains)
- Enables complete legacy system retirement by demonstrating parity enforcement

## Legacy Parity Requirements

> **Critical Requirement:** Epic 4 must achieve 100% functional parity with `legacy/annuity_hub/data_handler/data_cleaner.py::AnnuityPerformanceCleaner` to enable Strangler Fig migration.

### Current Production Implementation

**Legacy Class:** `AnnuityPerformanceCleaner` (lines 159-233)
**Purpose:** Processes "规模明细" sheet from annuity Excel files
**Production Status:** ACTIVE - currently used in production environment

### Functional Coverage Mapping

#### ✅ COVERED - Already in Tech Spec

| Legacy Functionality | Legacy Code | Epic 4 Implementation | Story | Status |
|---------------------|-------------|----------------------|-------|--------|
| **Sheet Reading** | Line 162, 165 | Epic 3 Story 3.3: Multi-sheet reader with sheet_name="规模明细" | 3.3 → 4.5 | ✅ Covered |
| **Date Parsing** | Line 174 | Story 4.1: `parse_yyyymm_or_chinese()` field validator | 4.1 | ✅ Covered |
| **Company Name Cleansing** | Line 200-201 | Epic 2 Story 2.3: Cleansing registry framework | 2.3 → 4.3 | ✅ Covered |
| **Company ID Enrichment (Partial)** | Line 203-227 | Story 4.3: EnrichmentGateway with stub provider (MVP) | 4.3 | ⚠️ **Stub only - full enrichment in Epic 5** |

#### ⚠️ MISSING - Must Add to Tech Spec

| Legacy Functionality | Legacy Code | Required in Epic 4 | Impact | Story |
|---------------------|-------------|-------------------|--------|-------|
| **Column Renaming** | Line 166-170 | Rename: 机构→机构名称, 计划号→计划代码, 流失（含待遇支付）→流失(含待遇支付) | HIGH | 4.3 |
| **Branch Code Mapping** | Line 172 | Map 机构名称 → 机构代码 using COMPANY_BRANCH_MAPPING | HIGH | 4.3 |
| **Plan Code Correction** | Line 176-182 | Fix typos (1P0290→P0290), set defaults (AN001 for 集合计划, AN002 for 单一计划) | HIGH | 4.3 |
| **Branch Code Default** | Line 184-185 | Replace null/'null' with 'G00' | MEDIUM | 4.3 |
| **Portfolio Code Normalization** | Line 187-196 | Remove 'F' prefix, set defaults (QTAN003 for 职年, map from 计划类型) | HIGH | 4.3 |
| **Product Line Code Mapping** | Line 198 | Map 业务类型 → 产品线代码 using BUSINESS_TYPE_CODE_MAPPING | HIGH | 4.3 |
| **Account Name Preservation** | Line 200 | Save original 客户名称 as 年金账户名 before cleansing | MEDIUM | 4.3 |
| **5-Step Enrichment Logic** | Line 203-227 | **Complex 5-step fallback strategy (see below)** | **CRITICAL** | 4.3 |
| **Column Deletion** | Line 230-232 | Drop: 备注, 子企业号, 子企业名称, 集团企业客户号, 集团企业客户名称 | LOW | 4.4 |

### Critical: 5-Step Company ID Enrichment Logic

**Legacy Implementation:** Lines 203-227 (5 sequential fallback steps)

```python
# Step 1: Map from 计划代码
df['company_id'] = df['计划代码'].map(COMPANY_ID1_MAPPING)

# Step 2: Clean 集团企业客户号 (remove 'C' prefix), then map
df['集团企业客户号'] = df['集团企业客户号'].str.lstrip('C')
mask = df['company_id'].isna() | (df['company_id'] == '')
df.loc[mask, 'company_id'] = df['集团企业客户号'].map(COMPANY_ID2_MAPPING)[mask]

# Step 3: Special case - if both company_id and 客户名称 empty, default to '600866980' or map from 计划代码
mask = (df['company_id'].isna() | (df['company_id'] == '')) & (df['客户名称'].isna() | (df['客户名称'] == ''))
company_id_from_plan = df['计划代码'].map(COMPANY_ID3_MAPPING).fillna('600866980')
df.loc[mask, 'company_id'] = company_id_from_plan[mask]

# Step 4: Map from cleaned 客户名称
mask = df['company_id'].isna() | (df['company_id'] == '')
df.loc[mask, 'company_id'] = df['客户名称'].map(COMPANY_ID4_MAPPING)[mask]

# Step 5: Map from original 年金账户名
mask = df['company_id'].isna() | (df['company_id'] == '')
df.loc[mask, 'company_id'] = df['年金账户名'].map(COMPANY_ID5_MAPPING)[mask]
```

**Epic 4 MVP Strategy:**
- **Story 4.3:** Implement steps 1-5 structure with stub provider
- **Stub Provider:** Returns temporary ID (`IN*`) for all unmapped cases
- **Epic 5 Growth:** Replace stub with real enrichment service (EQC API, async queue)

**Parity Requirement:**
- ✅ Step 1-5 **logic flow** must be preserved (fallback order)
- ✅ Mappings (COMPANY_ID1-5_MAPPING) must be loaded from config/database
- ⚠️ Step 2-5 **actual lookups** deferred to Epic 5 (use temporary IDs in MVP)

### Parity Validation Strategy (Epic 6)

**Pre-Condition for Epic 6:** Epic 4 must implement all legacy functionality (may use stubs for enrichment)

**Epic 6 Story 6.3: Golden Dataset Parity Tests**
1. Select 3 months of production data (e.g., 202411, 202412, 202501)
2. Run legacy `AnnuityPerformanceCleaner` → output A
3. Run Epic 4 pipeline → output B
4. Compare A vs B:
   - All columns present (including 机构代码, 组合代码, 产品线代码, etc.)
   - Row counts match (after filtering)
   - All non-enrichment fields identical
   - Enrichment fields: legacy company_id vs temporary ID mapping documented
5. Define parity threshold: 100% for non-enrichment fields, documented mapping for enrichment

**Epic 6 Story 6.4: Production Cutover**
- Cutover criteria: Parity tests pass with 100% non-enrichment accuracy
- Shadow table (`annuity_performance_NEW`) ready for production use
- Epic 5 enrichment service replaces temporary IDs

### Tech Spec Updates Required

**Story 4.3 (Transformation Pipeline) MUST include:**
1. ✅ Column renaming transformation step
2. ✅ Branch code mapping step
3. ✅ Plan code correction step (typo fixes + defaults)
4. ✅ Branch code default step
5. ✅ Portfolio code normalization step (remove F prefix + defaults)
6. ✅ Product line code mapping step
7. ✅ Account name preservation step
8. ✅ 5-step enrichment logic (with stub provider for MVP)

**Story 4.4 (Gold Layer) MUST include:**
- Column deletion: 备注, 子企业号, 子企业名称, 集团企业客户号, 集团企业客户名称

**Acceptance Criteria Updates:**
- **AC-4.3.5:** All legacy transformation steps implemented (including 机构代码, 组合代码, 产品线代码)
- **AC-4.3.6:** 5-step enrichment logic preserved (fallback order correct)
- **AC-EPIC4.4:** Parity validation plan documented for Epic 6

### Risk Assessment

**RISK-4.5: Missing Legacy Functionality (Severity: CRITICAL)**
- **Description:** If Epic 4 doesn't implement all legacy features, Strangler Fig migration impossible
- **Impact:** Cannot retire legacy code, Epic 4 becomes isolated feature instead of migration
- **Mitigation:** Update Tech Spec NOW to include all missing features (this section documents them)
- **Validation:** Real Data Validation must verify all legacy features present

**RISK-4.6: Enrichment Logic Divergence (Severity: HIGH)**
- **Description:** 5-step enrichment logic complex - easy to miss edge cases
- **Impact:** Different company_id assignments than legacy (breaks cross-domain joins)
- **Mitigation:** Test with real production data (202412: 33,615 rows), compare step-by-step
- **Contingency:** Document temporary ID mapping for Epic 5 backfill

### Next Steps

1. **Update Story 4.3 AC** - Add all missing transformation steps
2. **Update Story 4.4 AC** - Add column deletion requirement
3. **Update Real Data Validation** - Verify all legacy features on 202412 data
4. **Resolve Configuration Architecture** - Answer Q-4.5 (see below)

### Open Question: Mapping Configuration Architecture (Q-4.5) - RESOLVED

**Context:** Legacy uses MySQL-driven mappings (~10,000+ entries), but new architecture has only YAML files (~20 entries labeled "示例与补丁"). This creates a critical parity gap.

**✅ RESOLUTION: Adopt Epic 5 Complete Architecture Design**

After reviewing PRD and epics.md, Epic 5 (Stories 5.1-5.8) provides a **complete enrichment architecture** that supersedes legacy mappings:

**Epic 5 Architecture (Recommended):**

```
┌─────────────────────────────────────────────────────┐
│ EnrichmentGateway (Story 5.5)                       │
├─────────────────────────────────────────────────────┤
│ Tier 1: Internal Mapping Resolver (Story 5.4)      │
│   → enterprise.company_name_index (unified table)   │
│   → Multi-tier: exact/fuzzy/alias matching          │
│   → 90%+ cache hit rate                             │
├─────────────────────────────────────────────────────┤
│ Tier 2: EQC API Provider (Story 5.6)               │
│   → Sync lookup with budget (5 calls/run)          │
│   → Cache results to company_name_index             │
├─────────────────────────────────────────────────────┤
│ Tier 3: Temporary ID Generation (Story 5.2)        │
│   → HMAC-based stable IDs: IN<16-char-Base32>     │
│   → Same company → same temp ID (deterministic)     │
├─────────────────────────────────────────────────────┤
│ Background: Async Queue (Story 5.7)                │
│   → Resolve temp IDs in background                 │
│   → enterprise.enrichment_requests table            │
└─────────────────────────────────────────────────────┘
```

**Database Schema (Story 5.3):**
```sql
enterprise.company_master (主表):
  - company_id (PK)
  - official_name
  - unified_credit_code
  - aliases (TEXT[])
  - source: "eqc_api", "manual", "legacy_import"

enterprise.company_name_index (统一mapping表):
  - normalized_name (PK)
  - company_id (FK → company_master)
  - match_type: "plan", "account", "hardcode", "name", "account_name"
  - confidence: 0.00-1.00
  - created_at

enterprise.enrichment_requests (async queue):
  - request_id (PK, UUID)
  - company_name, status, company_id, confidence
  - created_at, processed_at
```

**Legacy 5-Step Mapping → Epic 5 Migration:**

| Legacy Mapping | 迁移目标 | match_type | confidence |
|---------------|---------|------------|------------|
| COMPANY_ID1_MAPPING (~500) | company_name_index | "plan" | 1.0 |
| COMPANY_ID2_MAPPING (~1000) | company_name_index | "account" | 1.0 |
| COMPANY_ID3_MAPPING (8) | company_name_index | "hardcode" | 1.0 |
| COMPANY_ID4_MAPPING (~3000) | company_name_index | "name" | varies |
| COMPANY_ID5_MAPPING (~5000) | company_name_index | "account_name" | 0.8 |

**Epic 4 MVP Strategy (Before Epic 5):**
- Use `StubProvider` (Story 5.1): Returns temporary IDs for ALL companies
- Generate stable temporary IDs (Story 5.2): `IN<HMAC-SHA1-Base32>`
- No database lookup needed in MVP (all temp IDs)
- Epic 5 backfills real company_ids when complete

**Epic 4 Stories Configuration:**
- **Story 4.3:** Inject `StubProvider` (no database dependency)
- **Story 4.6:** Document temp ID format, prepare for Epic 5 migration
- **No YAML mappings needed** - Epic 5 uses database-driven approach

**Advantages over Legacy:**
1. ✅ Unified table (10,000 mappings → 1 table)
2. ✅ Multi-tier matching (exact/fuzzy/alias)
3. ✅ Async resolution (no pipeline blocking)
4. ✅ Confidence scoring (manual review for low confidence)
5. ✅ Graceful degradation (temp IDs when enrichment fails)
6. ✅ EQC API integration (external data source)

**Configuration Files Status:**
- `config/data_sources.yml` → ✅ **Keep** (Epic 3 file discovery, authoritative)
- `src/work_data_hub/config/data_sources.yml` → ❌ **Remove** (legacy duplicate)
- `src/work_data_hub/config/mappings/*.yml` → ⚠️ **Optional** (only for small static patches like COMPANY_BRANCH 6 hardcoded entries)

**Decision:** Adopt Epic 5 architecture. Epic 4 MVP uses stub + temporary IDs only.

---

## Objectives and Scope

### In Scope

**Core Deliverables:**
1. **Pydantic Data Models** (Story 4.1)
   - `AnnuityPerformanceIn` with loose validation for Excel input
   - `AnnuityPerformanceOut` with strict business rules
   - Chinese field names matching Excel sources (月度, 计划代码, 客户名称, etc.)

2. **Bronze Layer Validation** (Story 4.2)
   - Pandera schema validating raw Excel structure
   - Reject corrupted source data immediately
   - Clear error messages with row/column context

3. **Bronze→Silver Transformation** (Story 4.3)
   - Date parsing using Chinese date utilities (Epic 2)
   - Company name cleansing via registry framework
   - Company ID enrichment integration (Epic 5 stub for MVP)
   - Row-level Pydantic validation
   - Failed row CSV export

4. **Gold Layer Projection** (Story 4.4)
   - Composite PK validation: (月度, 计划代码, company_id)
   - Column projection to database schema
   - Final pandera schema validation

5. **End-to-End Integration** (Story 4.5)
   - Complete pipeline: file discovery → validation → transformation → database
   - Dagster job definition
   - Shadow table writes (`annuity_performance_NEW`)
   - Idempotent upsert operations

6. **Configuration & Documentation** (Story 4.6)
   - Domain config in `data_sources.yml`
   - Database migration for shadow table
   - Runbook and troubleshooting guide

### Out of Scope (Deferred)

**Other Domains (Epic 9 - Growth Domains):**
- ❌ 收入明细 (Revenue Details) - deferred to Epic 9
- ❌ 企康缴费 (Enterprise Health Insurance) - deferred to Epic 9
- ❌ 历史浮费 (Historical Float Fees) - deferred to Epic 9
- ❌ Other 5+ domains beyond annuity_performance
- **Rationale:** Epic 4 is MVP - proves pattern on single highest-complexity domain first
- **Epic 9 Strategy:** Use Epic 4 as reference implementation for remaining domains

**Epic 6 - Testing Infrastructure:**
- Golden dataset parity tests (Epic 6 Story 6.3)
- Legacy parallel execution (Epic 6 Story 6.1-6.2)
- Production cutover (Epic 6 Story 6.4)

**Epic 5 - Full Enrichment:**
- Real EQC API integration (Epic 5 Story 5.6)
- Async enrichment queue (Epic 5 Story 5.7)
- MVP uses stub provider + temporary IDs only

**Epic 7 - Orchestration:**
- Automated scheduling (Epic 7)
- Cross-domain dependencies (Epic 7)

### Success Criteria

**Technical Success:**
- ✅ Pipeline processes 10,000+ annuity rows without errors
- ✅ All validation layers (Bronze/Silver/Gold) pass
- ✅ Data loaded to `annuity_performance_NEW` table
- ✅ Idempotent re-runs produce identical results
- ✅ Execution time <10 minutes for typical monthly data (~10K rows)

**Architecture Validation:**
- ✅ Proves Bronze→Silver→Gold pattern works
- ✅ Validates multi-layer validation (pandera + Pydantic)
- ✅ Demonstrates Clean Architecture boundaries
- ✅ Establishes repeatable migration pattern for Epic 9

## System Architecture Alignment

### Architectural Decisions Applied

**Decision #3: Hybrid Pipeline Step Protocol**
- Annuity pipeline uses both DataFrame steps (bulk operations) and Row steps (validation/enrichment)
- Bronze validation: DataFrame-level pandera (fast structural checks)
- Silver validation: Row-level Pydantic (detailed business rules)
- Gold validation: DataFrame-level pandera (final constraints)

**Decision #5: Explicit Chinese Date Format Priority**
- `月度` field parsing uses `parse_yyyymm_or_chinese()` with explicit format priority
- Supports: YYYYMM, YYYY年MM月, YYYY-MM formats
- No dateutil fallback (predictable behavior)
- Range validation: 2000-2030

**Decision #7: Comprehensive Naming Conventions**
- Pydantic models use Chinese field names: `月度`, `计划代码`, `客户名称`
- Database columns use English snake_case: `reporting_month`, `plan_code`, `company_name`
- Explicit column mapping during Gold projection

**Decision #4: Hybrid Error Context Standards**
- All validation errors include structured context: domain, row_number, field, error_type
- Failed rows exported to CSV with actionable error messages
- Example: "Row 15, field '月度': Cannot parse 'INVALID' as date, expected: YYYYMM, YYYY年MM月"

### Clean Architecture Boundaries

**Domain Layer (`domain/annuity_performance/`):**
- `models.py`: Pydantic In/Out models (pure validation logic)
- `schemas.py`: Pandera Bronze/Gold schemas
- `pipeline_steps.py`: Transformation step implementations
- **Zero dependencies on `io/` or `orchestration/`**

**I/O Layer (`io/`):**
- File discovery via `FileDiscoveryService` (Epic 3)
- Database loading via `WarehouseLoader` (Epic 1)
- Excel reading via `ExcelReader` (Epic 3)

**Orchestration Layer (`orchestration/`):**
- Dagster job definition wires domain + I/O components
- Dependency injection: pass enrichment service to domain pipeline

### Integration Points

**Epic 1 - Foundation:**
- Uses `Pipeline` framework from Story 1.5 for step execution
- Uses `WarehouseLoader` from Story 1.8 for database writes
- Uses structured logging from Story 1.3 for metrics

**Epic 2 - Validation:**
- Bronze/Gold schemas from Story 2.2 (pandera)
- Pydantic validation pattern from Story 2.1
- Date parser from Story 2.4 (`parse_yyyymm_or_chinese`)
- Cleansing registry from Story 2.3 for company name normalization
- Error export from Story 2.5

**Epic 3 - File Discovery:**
- `FileDiscoveryService.discover_and_load()` provides raw DataFrame
- Version detection (Story 3.1) selects highest V folder
- Pattern matching (Story 3.2) finds `*年金*.xlsx`
- Multi-sheet reading (Story 3.3) loads `规模明细` sheet
- Column normalization (Story 3.4) cleans header names

**Epic 5 - Enrichment (MVP):**
- `EnrichmentGateway` with stub provider (Story 5.1)
- Temporary ID generation (Story 5.2) for unresolved companies
- Real enrichment deferred to Growth phase (Stories 5.6-5.8)

## Detailed Design

### Services and Modules

#### Module Structure

```
src/work_data_hub/
├── domain/
│   └── annuity_performance/
│       ├── __init__.py
│       ├── models.py              # Pydantic In/Out models (Story 4.1)
│       ├── schemas.py             # Pandera Bronze/Gold schemas (Story 4.2, 4.4)
│       ├── pipeline_steps.py     # Transformation steps (Story 4.3)
│       └── service.py            # Main orchestration (Story 4.5)
├── io/
│   ├── connectors/
│   │   └── file_connector.py     # FileDiscoveryService (Epic 3)
│   ├── readers/
│   │   └── excel_reader.py       # ExcelReader (Epic 3)
│   ├── loader/
│   │   └── warehouse_loader.py   # WarehouseLoader (Epic 1)
│   └── schema/
│       └── migrations/
│           └── YYYYMMDD_HHMM_create_annuity_performance_new.py
├── orchestration/
│   └── jobs.py                   # annuity_performance_job (Story 4.5)
└── config/
    └── data_sources.yml          # Domain configuration (Story 4.6)
```

#### Key Services

**AnnuityPerformanceService** (`domain/annuity_performance/service.py`)
```python
def process_annuity_performance(
    month: str,  # "202501"
    enrichment_service: EnterpriseInfoProvider,
    file_discovery: FileDiscoveryService,
    warehouse_loader: WarehouseLoader
) -> PipelineResult:
    """
    Main orchestration function for annuity pipeline

    Flow:
    1. Discover and load Excel file
    2. Validate Bronze layer
    3. Transform (Bronze → Silver)
    4. Validate Gold layer
    5. Load to database

    Returns:
        PipelineResult with metrics and status
    """
```

**FileDiscoveryService** (`io/connectors/file_connector.py`)
- Provides: `discover_and_load(domain, month)` → `DataDiscoveryResult`
- Epic 3 Story 3.5 integration point
- Returns DataFrame with normalized columns

**WarehouseLoader** (`io/loader/warehouse_loader.py`)
- Provides: `load_dataframe(df, table_name, mode='upsert')`
- Epic 1 Story 1.8 integration point
- Transactional writes with rollback on error

### Data Models and Contracts

#### Pydantic Models (Story 4.1)

**AnnuityPerformanceIn** (Loose validation for Excel input)
```python
from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import date

class AnnuityPerformanceIn(BaseModel):
    """Input model with permissive validation for messy Excel data"""

    月度: Optional[Union[str, int, date]] = None  # Various date formats
    计划代码: Optional[str] = None                 # Plan code, may be missing
    客户名称: Optional[str] = None                 # Company name for enrichment
    期初资产规模: Optional[Union[str, float]] = None  # Starting assets
    期末资产规模: Optional[Union[str, float]] = None  # Ending assets
    投资收益: Optional[Union[str, float]] = None     # Investment return
    年化收益率: Optional[Union[str, float]] = None   # Annualized return rate

    model_config = ConfigDict(
        str_strip_whitespace=True,
        arbitrary_types_allowed=True
    )
```

**AnnuityPerformanceOut** (Strict validation for database output)
```python
class AnnuityPerformanceOut(BaseModel):
    """Output model with strict business rules for database loading"""

    月度: date = Field(..., description="Reporting month, required")
    计划代码: str = Field(..., min_length=1, description="Plan code, non-empty")
    company_id: str = Field(..., description="Enriched company ID or temporary IN_* ID")
    期初资产规模: float = Field(..., ge=0, description="Starting assets, non-negative")
    期末资产规模: float = Field(..., ge=0, description="Ending assets, non-negative")
    投资收益: float = Field(..., description="Investment return")
    年化收益率: Optional[float] = Field(None, ge=-1.0, le=5.0, description="Rate, nullable if 期末=0")

    @field_validator('月度', mode='before')
    def parse_chinese_date(cls, v):
        """Parse various Chinese date formats"""
        from utils.date_parser import parse_yyyymm_or_chinese
        return parse_yyyymm_or_chinese(v)

    @field_validator('company_id')
    def validate_company_id(cls, v):
        """Ensure company_id is not empty"""
        if not v or v.strip() == "":
            raise ValueError("company_id cannot be empty")
        return v.strip()
```

#### Pandera Schemas (Stories 4.2, 4.4)

**BronzeAnnuitySchema** (Story 4.2)
```python
import pandera as pa

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

**GoldAnnuitySchema** (Story 4.4)
```python
GoldAnnuitySchema = pa.DataFrameSchema({
    "月度": pa.Column(pa.DateTime, nullable=False),
    "计划代码": pa.Column(pa.String, nullable=False),
    "company_id": pa.Column(pa.String, nullable=False),
    "期初资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
    "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
    "投资收益": pa.Column(pa.Float, nullable=False),
    "年化收益率": pa.Column(pa.Float, nullable=True),
}, strict=True, unique=['月度', '计划代码', 'company_id'])  # Composite PK uniqueness
```

#### Database Schema (Story 4.6)

**Table: `annuity_performance_NEW`** (Shadow table for MVP)
```sql
CREATE TABLE annuity_performance_NEW (
    reporting_month DATE NOT NULL,
    plan_code VARCHAR(50) NOT NULL,
    company_id VARCHAR(50) NOT NULL,
    company_name VARCHAR(255),
    starting_assets DECIMAL(18,2) NOT NULL CHECK (starting_assets >= 0),
    ending_assets DECIMAL(18,2) NOT NULL CHECK (ending_assets >= 0),
    investment_return DECIMAL(18,2) NOT NULL,
    annualized_return_rate DECIMAL(8,4),
    pipeline_run_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (reporting_month, plan_code, company_id),
    INDEX idx_reporting_month (reporting_month),
    INDEX idx_company_id (company_id)
);
```

### APIs and Interfaces

#### Public API

**Main Entry Point**
```python
def process_annuity_performance(month: str) -> PipelineResult:
    """
    Process annuity performance data for specified month

    Args:
        month: YYYYMM format (e.g., "202501")

    Returns:
        PipelineResult with execution metrics

    Raises:
        DiscoveryError: File discovery failed
        ValidationError: Bronze/Silver/Gold validation failed
        DatabaseError: Database loading failed
    """
```

**Result Contract**
```python
@dataclass
class PipelineResult:
    success: bool
    rows_loaded: int
    rows_failed: int
    duration_ms: float
    file_path: Path
    version: str
    errors: List[str]
    metrics: Dict[str, Any]
```

#### Internal Interfaces

**EnterpriseInfoProvider Protocol** (Epic 5)
```python
class EnterpriseInfoProvider(Protocol):
    def lookup(self, company_name: str) -> Optional[CompanyInfo]:
        """Resolve company name to CompanyInfo or None"""
        ...

@dataclass
class CompanyInfo:
    company_id: str
    official_name: str
    unified_credit_code: Optional[str]
    confidence: float  # 0.0-1.0
    match_type: str    # "exact", "fuzzy", "alias", "temporary"
```

**TransformStep Protocol** (Epic 1)
```python
class TransformStep(Protocol):
    def execute(self, data: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Transform data and return modified DataFrame"""
        ...
```

### Workflows and Sequencing

#### End-to-End Pipeline Flow (Story 4.5)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FILE DISCOVERY (Epic 3)                                      │
├─────────────────────────────────────────────────────────────────┤
│ Input:  domain="annuity_performance", month="202501"            │
│ Output: Raw DataFrame, file_path, version                       │
│                                                                  │
│ Steps:                                                           │
│ • Resolve {YYYYMM} placeholder → "202501"                       │
│ • Scan for version folders (V1, V2, V3...)                      │
│ • Select highest version                                         │
│ • Match file patterns: *年金*.xlsx                              │
│ • Load sheet: "规模明细"                                          │
│ • Normalize column names                                         │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. BRONZE VALIDATION (Story 4.2)                                │
├─────────────────────────────────────────────────────────────────┤
│ Input:  Raw DataFrame                                            │
│ Output: Bronze-validated DataFrame                               │
│                                                                  │
│ Checks:                                                          │
│ • Expected columns present                                       │
│ • No completely null columns                                     │
│ • Numeric columns coercible to float                             │
│ • Date column parseable                                          │
│ • At least 1 data row                                            │
│                                                                  │
│ Failure: SchemaError with row/column details                     │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. BRONZE→SILVER TRANSFORMATION (Story 4.3)                     │
├─────────────────────────────────────────────────────────────────┤
│ Input:  Bronze DataFrame                                         │
│ Output: Silver DataFrame (validated rows) + failed_rows.csv     │
│                                                                  │
│ Steps:                                                           │
│ a) Parse dates: 月度 → date objects                             │
│ b) Cleanse company names: registry rules                        │
│ c) Validate rows: AnnuityPerformanceIn                          │
│ d) Enrich company IDs: EnrichmentGateway lookup                 │
│    • Cache hit → real company_id                                │
│    • Cache miss → temporary IN_* ID                             │
│ e) Calculate derived fields                                      │
│ f) Validate output: AnnuityPerformanceOut                       │
│ g) Export failed rows to CSV                                     │
│                                                                  │
│ Error handling: Collect all errors, continue if <10% failure    │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GOLD VALIDATION & PROJECTION (Story 4.4)                     │
├─────────────────────────────────────────────────────────────────┤
│ Input:  Silver DataFrame                                         │
│ Output: Gold DataFrame (database-ready)                          │
│                                                                  │
│ Steps:                                                           │
│ • Project to database columns only                               │
│ • Validate composite PK uniqueness                               │
│ • Enforce not-null constraints                                   │
│ • Apply GoldAnnuitySchema                                        │
│                                                                  │
│ Failure: SchemaError with composite key violations               │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. DATABASE LOADING (Story 4.5)                                 │
├─────────────────────────────────────────────────────────────────┤
│ Input:  Gold DataFrame                                           │
│ Output: Database rows inserted/updated                           │
│                                                                  │
│ Steps:                                                           │
│ • Open transaction                                               │
│ • Upsert in batches of 1000 rows                                │
│ • ON CONFLICT (月度, 计划代码, company_id) DO UPDATE            │
│ • Commit transaction                                             │
│ • Log audit entry                                                │
│                                                                  │
│ Target table: annuity_performance_NEW (shadow mode)              │
│ Failure: Rollback entire transaction                             │
└─────────────────────────────────────────────────────────────────┘
```

#### Dagster Job Definition (Story 4.5)

```python
@job
def annuity_performance_job():
    """Dagster job for annuity performance processing"""

    @op
    def load_config():
        return {
            "month": "202501",
            "domain": "annuity_performance"
        }

    @op
    def discover_file(config):
        file_discovery = FileDiscoveryService()
        return file_discovery.discover_and_load(
            domain=config["domain"],
            month=config["month"]
        )

    @op
    def process_pipeline(discovery_result):
        enrichment = StubProvider()  # MVP: stub only
        result = process_annuity_performance(
            month=discovery_result.month,
            enrichment_service=enrichment
        )
        return result

    @op
    def log_metrics(result):
        logger.info("Pipeline complete", extra={
            "rows_loaded": result.rows_loaded,
            "duration_ms": result.duration_ms
        })

    config = load_config()
    discovery = discover_file(config)
    result = process_pipeline(discovery)
    log_metrics(result)
```

## Non-Functional Requirements

### Performance

**Throughput Requirements:**
- Process 10,000 rows in <10 minutes (target: 1,000 rows/minute)
- Bronze validation: <5ms per 1000 rows (DataFrame-level)
- Silver validation: <50ms per 100 rows (row-level Pydantic)
- Gold validation: <5ms per 1000 rows (DataFrame-level)
- Database loading: <30 seconds for 10,000 rows (batch inserts)

**Memory Constraints:**
- Peak memory usage: <2GB for 50,000 rows
- DataFrame operations use chunking for files >100MB
- No full DataFrame copies (use views where possible)

**Optimization Strategies:**
- Batch database inserts (1000 rows per transaction)
- Minimize DataFrame copying (use inplace operations carefully)
- Lazy evaluation for validation (fail fast on critical errors)
- Connection pooling for database (Epic 1 Story 1.8)

**Performance Monitoring:**
- Log execution time per pipeline step
- Track memory usage via structlog metrics
- Alert if execution time >15 minutes (150% of target)

### Security

**Data Sensitivity:**
- Annuity data contains customer PII (客户名称, 资产规模)
- Failed row CSV exports may contain sensitive data
- Must enforce access control on logs/ directory

**Access Controls:**
- Database credentials via environment variables (never committed)
- `WDH_ALIAS_SALT` for temporary ID generation (secret, unique per deployment)
- Failed row CSVs written to restricted `logs/` directory

**SQL Injection Prevention:**
- Parameterized queries only (Epic 1 Story 1.8 `WarehouseLoader`)
- No string concatenation for SQL generation
- Use SQLAlchemy ORM or psycopg2 with parameter binding

**Logging Security:**
- NEVER log company_id mappings (reveals enrichment logic)
- NEVER log database credentials or API tokens
- Sanitize error messages to exclude sensitive field values

**Credential Management:**
- Use `.env` files for local development (gitignored)
- Use secret management service for production (e.g., AWS Secrets Manager)
- Rotate `WDH_ALIAS_SALT` if compromised

### Reliability/Availability

**Fault Tolerance:**
- Database transactions: all-or-nothing (rollback on error)
- Enrichment failures: graceful degradation (use temporary IDs)
- File discovery failures: clear error with actionable message

**Idempotency:**
- Re-running pipeline with same input produces identical database state
- Upsert strategy: `ON CONFLICT DO UPDATE`
- No duplicate rows due to composite PK constraint

**Error Recovery:**
- Bronze validation failure: stop immediately (corrupted source data)
- Silver validation failure: collect errors, continue if <10% failed
- Gold validation failure: stop immediately (data integrity issue)
- Database failure: retry 3 times with exponential backoff (Epic 1 Story 1.8)

**Partial Success Handling:**
- Export failed rows to CSV for manual review
- Continue with valid rows if failure rate <10%
- Log partial success metrics: "Processed 950/1000 rows, 50 failed"

**Availability Target:**
- Pipeline should execute successfully 99% of the time
- Enrichment service downtime does not block pipeline (temporary IDs)
- Database connection issues: retry with backoff

### Observability

**Structured Logging (Epic 1 Story 1.3):**
```json
{
  "timestamp": "2025-11-28T10:30:00Z",
  "level": "INFO",
  "logger": "domain.annuity_performance",
  "message": "Pipeline completed",
  "context": {
    "domain": "annuity_performance",
    "month": "202501",
    "file_path": "reference/monthly/202501/.../V2/年金数据.xlsx",
    "version": "V2",
    "rows_loaded": 9500,
    "rows_failed": 500,
    "duration_ms": 585000,
    "enrichment_cache_hit_rate": 0.85
  }
}
```

**Metrics Tracked:**
- **Discovery:** file_path, version, row_count, column_count, duration_ms
- **Validation:** bronze_pass_rate, silver_pass_rate, gold_pass_rate, failure_threshold
- **Transformation:** rows_in, rows_out, rows_failed, enrichment_cache_hits, temp_ids_generated
- **Database:** rows_inserted, rows_updated, transaction_duration_ms

**Error Tracking:**
- Failed row CSV export with structured errors
- Error summary logged: "15 rows failed Bronze schema, 23 rows failed Pydantic validation"
- Aggregate error types: missing_column, invalid_date, negative_value, composite_pk_duplicate

**Alerting Triggers:**
- Execution time >15 minutes (performance degradation)
- Failure rate >10% (data quality issue)
- Database connection failures (infrastructure issue)
- Zero rows loaded (file discovery or validation issue)

## Dependencies and Integrations

### Epic Dependencies (Must Complete First)

**Epic 1: Foundation & Core Infrastructure** ✅
- Story 1.3: Structured logging for metrics
- Story 1.4: Configuration management for data_sources.yml
- Story 1.5: Pipeline framework for step execution
- Story 1.6: Clean Architecture boundaries (DI pattern)
- Story 1.7: Database migrations for annuity_performance_NEW table
- Story 1.8: WarehouseLoader for database writes
- Story 1.9: Dagster orchestration setup

**Epic 2: Multi-Layer Data Quality Framework** ✅
- Story 2.1: Pydantic validation pattern (In/Out models)
- Story 2.2: Pandera DataFrame schemas (Bronze/Gold)
- Story 2.3: Cleansing registry for company name normalization
- Story 2.4: Chinese date parsing utilities
- Story 2.5: Validation error export to CSV

**Epic 3: Intelligent File Discovery & Version Detection** ✅
- Story 3.0: Config schema validation (Epic 1 dependency)
- Story 3.1: Version-aware folder scanner
- Story 3.2: Pattern-based file matcher
- Story 3.3: Multi-sheet Excel reader
- Story 3.4: Column name normalization
- Story 3.5: Integrated file discovery service

### Partial Dependencies (MVP Subset)

**Epic 5: Company Enrichment Service** (Partial)
- Story 5.1: EnterpriseInfoProvider protocol + stub ✅
- Story 5.2: Temporary ID generation (HMAC) ✅
- Stories 5.3-5.8: Full enrichment (deferred to Growth phase) ❌

### Integration Points

| Component | Integration Method | Epic 4 Usage |
|-----------|-------------------|--------------|
| FileDiscoveryService | Direct function call | Story 4.5 |
| WarehouseLoader | DI via constructor | Story 4.5 |
| Pipeline framework | TransformStep protocol | Story 4.3 |
| EnrichmentGateway | DI via parameter | Story 4.3 (stub) |
| Cleansing registry | Direct function call | Story 4.3 |
| Date parser | Direct function call | Story 4.1 |

### Configuration Dependencies

**data_sources.yml** (Story 4.6)
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

**Environment Variables**
- `DATABASE_URL`: PostgreSQL connection string (Epic 1)
- `WDH_ALIAS_SALT`: Temporary ID generation salt (Epic 5)
- `LOG_LEVEL`: Logging verbosity (Epic 1)
- `WDH_ENRICH_ENABLED`: Enable enrichment (default: True)

## Acceptance Criteria (Authoritative)

### Story 4.1: Annuity Domain Data Models

**AC-4.1.1:** Pydantic models exist with Chinese field names
- `AnnuityPerformanceIn` with `Optional` fields for loose validation
- `AnnuityPerformanceOut` with strict business rules (`ge=0` for assets)

**AC-4.1.2:** Date validator parses Chinese formats
- Handles: YYYYMM, YYYY年MM月, YYYY-MM
- Raises clear `ValueError` for invalid formats

**AC-4.1.3:** Validation enforces business rules
- `期末资产规模 >= 0` (non-negative assets)
- `company_id` non-empty string
- All required fields present in Out model

### Story 4.2: Annuity Bronze Layer Validation

**AC-4.2.1:** Bronze schema validates raw Excel structure
- Expected columns: ['月度', '计划代码', '客户名称', '期初资产规模', '期末资产规模', '投资收益', '年化收益率']
- No completely null columns
- Numeric columns coercible to float

**AC-4.2.2:** Missing column raises SchemaError
- Error message lists expected vs. actual columns

**AC-4.2.3:** Systemic data issue detection
- If >10% of rows invalid, raise SchemaError with percentage

### Story 4.3: Annuity Transformation Pipeline

**AC-4.3.1:** Pipeline executes 7 transformation steps in order
- Parse dates → Cleanse names → Validate input → Enrich → Calculate → Validate output → Export failures

**AC-4.3.2:** Failed rows exported to CSV
- CSV includes: original row data + error_type + error_field + error_message

**AC-4.3.3:** Enrichment stub integration
- Stub provider returns temporary IDs for unknowns
- Format: `IN<16-char-Base32>`

**AC-4.3.4:** Partial success handling
- Continue with valid rows if <10% fail
- Export 50 failed rows, load 950 valid rows

### Story 4.4: Annuity Gold Layer Projection

**AC-4.4.1:** Composite PK uniqueness validated
- (月度, 计划代码, company_id) has no duplicates
- SchemaError lists duplicate combinations

**AC-4.4.2:** Column projection removes extra fields
- Only database columns retained
- Log removed column names

**AC-4.4.3:** Not-null constraints enforced
- Required fields: 月度, 计划代码, company_id, 期初/期末资产规模, 投资收益

### Story 4.5: Annuity End-to-End Pipeline Integration

**AC-4.5.1:** Complete pipeline execution
- File discovery → Bronze → Silver → Gold → Database
- All steps complete without errors for valid input

**AC-4.5.2:** Database loading with upsert
- 950 rows inserted/updated to `annuity_performance_NEW`
- `ON CONFLICT (月度, 计划代码, company_id) DO UPDATE`

**AC-4.5.3:** Idempotent re-runs
- Running twice with same input produces identical database state

**AC-4.5.4:** Dagster job execution
- Job visible in Dagster UI
- Step-by-step logs displayed
- Success/failure status shown

**AC-4.5.5:** Execution time target
- 10,000 rows processed in <10 minutes

### Story 4.6: Annuity Domain Configuration

**AC-4.6.1:** Configuration in data_sources.yml
- Domain config with: base_path, file_patterns, exclude_patterns, sheet_name, version_strategy

**AC-4.6.2:** Database migration applied
- `annuity_performance_NEW` table created with composite PK

**AC-4.6.3:** Documentation complete
- README section: input format, transformation steps, output schema
- Runbook: manual execution, troubleshooting guide

### Epic-Level Acceptance Criteria

**AC-EPIC4.1:** Architecture validation
- ✅ Bronze→Silver→Gold pattern proven
- ✅ Multi-layer validation (pandera + Pydantic) works
- ✅ Clean Architecture boundaries maintained

**AC-EPIC4.2:** Performance targets met
- ✅ 10,000 rows in <10 minutes
- ✅ Memory usage <2GB for 50,000 rows

**AC-EPIC4.3:** Reference implementation
- ✅ Establishes repeatable pattern for Epic 9 migrations
- ✅ All 6 stories complete and documented

## Traceability Mapping

### PRD Requirements → Epic 4 Stories

| PRD Requirement | Epic 4 Implementation | Story |
|-----------------|----------------------|-------|
| FR-1.3: Multi-Sheet Excel Reading | ExcelReader loads "规模明细" sheet | Epic 3.3 → 4.5 |
| FR-2.1: Pydantic Row Validation | AnnuityPerformanceIn/Out models | 4.1 |
| FR-2.1: Bronze Layer Validation | BronzeAnnuitySchema | 4.2 |
| FR-2.3: Gold Layer Validation | GoldAnnuitySchema | 4.4 |
| FR-3.1: Pipeline Framework | Pipeline with TransformSteps | 4.3 |
| FR-3.2: Cleansing Registry | Company name normalization | 4.3 |
| FR-3.3: Company Enrichment | StubProvider + temporary IDs | 4.3 |
| FR-3.4: Chinese Date Parsing | parse_yyyymm_or_chinese | 4.1 |
| FR-4: Database Loading | WarehouseLoader upsert | 4.5 |
| FR-5.1: Dagster Jobs | annuity_performance_job | 4.5 |
| FR-7: Configuration Management | data_sources.yml | 4.6 |
| NFR-1.1: Processing Time | <10 min for 10K rows | 4.5 |
| NFR-2.2: Fault Tolerance | Transaction rollback, retries | 4.5 |
| NFR-2.5: Data Integrity | Composite PK constraint | 4.4, 4.6 |
| NFR-3.1: Type Safety | Pydantic + mypy validation | 4.1 |

### Architecture Decisions → Epic 4 Implementation

| Decision | Epic 4 Application | Location |
|----------|-------------------|----------|
| AD-3: Hybrid Pipeline Protocol | DataFrame + Row validation | 4.2, 4.3, 4.4 |
| AD-4: Error Context Standards | Structured validation errors | 4.2, 4.3, 4.4 |
| AD-5: Chinese Date Priority | parse_yyyymm_or_chinese | 4.1 |
| AD-7: Naming Conventions | Chinese Pydantic, English DB | 4.1, 4.6 |

### Epic 1-3 Infrastructure → Epic 4 Usage

| Infrastructure Component | Epic 4 Dependency | Impact |
|-------------------------|-------------------|---------|
| Pipeline framework (1.5) | Transform steps execution | Critical |
| WarehouseLoader (1.8) | Database writes | Critical |
| Structured logging (1.3) | Metrics tracking | High |
| Dagster setup (1.9) | Job orchestration | High |
| Config framework (1.4) | data_sources.yml | High |
| File discovery (3.5) | Excel file loading | Critical |
| Date parser (2.4) | 月度 field parsing | Critical |
| Cleansing registry (2.3) | Company name normalization | Medium |
| Pandera schemas (2.2) | Bronze/Gold validation | Critical |
| Pydantic patterns (2.1) | In/Out models | Critical |

## Risks, Assumptions, Open Questions

### Risks

**RISK-4.1: Excel File Format Variations** (Severity: HIGH)
- **Description:** Real annuity Excel files may have unexpected format variations not captured in samples
- **Mitigation:** Bronze schema validation fails fast with clear errors, enabling quick config adjustment
- **Contingency:** Add additional file patterns to data_sources.yml if needed

**RISK-4.2: Enrichment Cache Miss Rate** (Severity: MEDIUM)
- **Description:** If cache hit rate <50%, many temporary IDs generated, complicating cross-domain joins
- **Mitigation:** Use stub provider for MVP; Epic 5 Stories 5.6-5.8 address full enrichment
- **Contingency:** Manual backfill of high-frequency company names to `enterprise.company_name_index`

**RISK-4.3: Performance Degradation with Large Files** (Severity: MEDIUM)
- **Description:** Files >50,000 rows may exceed 10-minute target or 2GB memory limit
- **Mitigation:** Chunking strategy for large files (defer to Epic 9 if not needed for MVP)
- **Contingency:** Process files in batches of 10,000 rows

**RISK-4.4: Composite PK Duplicates in Source Data** (Severity: LOW)
- **Description:** Excel may contain duplicate (月度, 计划代码) combinations for same company
- **Mitigation:** Gold schema validation detects duplicates, exports to failed_rows.csv
- **Contingency:** Define deduplication rule (e.g., keep row with latest timestamp)

### Assumptions

**ASSUME-4.1:** Epic 1-3 infrastructure complete before Epic 4 start
- **Validation:** Check sprint status before beginning Epic 4 stories

**ASSUME-4.2:** Excel files follow consistent structure
- **Validation:** Bronze schema validation on first production run

**ASSUME-4.3:** Company enrichment stub sufficient for MVP
- **Validation:** Temporary IDs enable pipeline execution without blocking

**ASSUME-4.4:** Shadow table approach acceptable for MVP
- **Validation:** Writes to `annuity_performance_NEW`, parity testing in Epic 6

**ASSUME-4.5:** Typical monthly data volume ~10,000 rows
- **Validation:** Confirm with historical data analysis

### Open Questions

**Q-4.1:** What deduplication rule for composite PK duplicates?
- **Context:** Gold validation may find duplicate (月度, 计划代码, company_id) in source
- **Options:** (a) Keep first row, (b) Keep last row, (c) Sum numeric fields
- **Decision Needed:** Before Story 4.4 implementation
- **Owner:** Product Owner

**Q-4.2:** Should enrichment cache misses queue for async resolution in MVP?
- **Context:** Story 5.7 (async queue) deferred to Growth phase
- **Options:** (a) MVP uses only temporary IDs, (b) Implement minimal async queue now
- **Decision Needed:** Before Story 4.3 implementation
- **Recommendation:** Option (a) - defer async queue, use temporary IDs only
- **Owner:** Tech Lead

**Q-4.3:** What access controls for failed_rows.csv exports?
- **Context:** CSV may contain PII (客户名称, 资产规模)
- **Options:** (a) Encrypt CSV, (b) Restrict logs/ directory, (c) Anonymize sensitive fields
- **Decision Needed:** Before Story 4.3 implementation
- **Recommendation:** Option (b) - restrict directory, document in security policy
- **Owner:** Security Lead

## Real Data Validation Strategy

> **Epic 3 Lesson Learned:** "应该及时用第一性原理思考我们正在构建的方案是否符合真实生产环境的需要，确保我们的规划以及实施都是有效且不过工程化的，从而让整体方案都保持在一个相对优雅的状态。" - Link

### Core Principle

Real data validation must happen **during story development**, not after epic completion. Each story validates against production archive data immediately after implementation to:
- Verify solution effectiveness on real-world data
- Discover edge cases early
- Prevent over-engineering through simplicity checks
- Ensure performance meets NFRs at real scale

### Test Data Source

**Primary Dataset:** `reference/archive/monthly/202412/`
- **Path:** `reference\archive\monthly\202412\收集数据\数据采集`
- **Version:** V2 (highest version with corrections)
- **File:** `【for年金分战区经营分析】24年12月年金终稿数据1227采集.xlsx`
- **Characteristics:** 33,615 rows, 23 columns
- **Why 202412:** Contains V1 and V2 versions - proves version detection works

**Backup Dataset:** `reference/archive/monthly/202411/`
- **Path:** `reference\archive\monthly\202411\收集数据\数据采集`
- **Version:** V1 (standard structure)
- **File:** `【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx`
- **Characteristics:** 33,269 rows, 23 columns
- **Why 202411:** Clean baseline with no version conflicts

### Per-Story Validation Plans

#### Story 4.1: Pydantic Models - Real Data Validation

**Validation Objective:** Verify models handle all field variations in real Excel data

**Real Data Source:** 202412 Excel file, first 100 rows
**Validation Criteria:**
1. `AnnuityPerformanceIn` accepts all 33,615 rows without parse errors
2. Date parsing handles actual `月度` format (202412 → date(2024, 12, 1))
3. Numeric fields handle commas and Chinese characters in Excel
4. Company names with special characters parse correctly

**Expected Results:**
- 100% rows parseable by `AnnuityPerformanceIn`
- Date validator handles production date formats
- Numeric coercion successful for all asset/return fields

**Edge Cases to Test:**
- Empty/null company names → validation error
- Negative asset values → caught by `ge=0` constraint
- Invalid date formats → clear error message

**Simplicity Check:**
- ✅ Two models (In/Out) sufficient? No intermediate models needed?
- ✅ Field validators minimal? Only essential business rules?

**Performance Target:** <1ms per row validation

---

#### Story 4.2: Bronze Schema - Real Data Validation

**Validation Objective:** Verify Bronze schema accepts raw Excel structure from Epic 3

**Real Data Source:** 202412 DataFrame from Epic 3 file discovery
**Validation Criteria:**
1. Schema validates 33,615 row DataFrame
2. All 23 expected columns present (no missing/extra)
3. Numeric column coercion successful (资产规模, 投资收益, etc.)
4. No completely null columns detected

**Expected Results:**
- Bronze validation passes for 202412 data
- Coercion converts numeric strings to floats
- Date column recognized and coercible

**Edge Cases to Test:**
- 202311 structure (different folder layout) → config adjustment only, no code change
- 202510 (ambiguous files) → Epic 3 already handles, Bronze receives valid DataFrame
- Missing columns → clear SchemaError with expected vs actual

**Simplicity Check:**
- ✅ Schema as permissive as needed for Bronze layer?
- ✅ Not duplicating Epic 3 column normalization?

**Performance Target:** <5ms for 33K rows (DataFrame-level validation)

---

#### Story 4.3: Transformation Pipeline - Real Data Validation

**Validation Objective:** Verify end-to-end transformation on production data scale

**Real Data Source:** 202412 full dataset (33,615 rows)
**Validation Criteria:**
1. All 7 pipeline steps execute without errors
2. Date parsing: 33,615 rows with valid dates
3. Company name cleansing: removes special chars, trims whitespace
4. Enrichment: stub provider generates temporary IDs for all unknowns
5. Failed row CSV export: 0 rows if data clean, or <10% threshold
6. Silver validation: 95%+ rows pass `AnnuityPerformanceOut`

**Expected Results:**
- Pipeline completes in <6 minutes (33K rows, 1K rows/min target)
- 32K+ rows pass validation (>95% success rate)
- Failed rows CSV: <1,680 rows (5% acceptable threshold)
- Enrichment: All companies get temporary IDs (stub mode)

**Edge Cases to Test:**
- Duplicate company names → same temporary ID generated
- Missing `期末资产规模` → failed row with clear error
- Invalid `年化收益率` (>100%) → range validation catches

**Simplicity Check:**
- ✅ 7 steps justified? Each step necessary?
- ✅ No redundant transformations (e.g., date parsing twice)?
- ✅ Error collection minimal overhead?

**Performance Target:** <6 minutes for 33K rows

---

#### Story 4.4: Gold Schema - Real Data Validation

**Validation Objective:** Verify composite PK uniqueness on real data

**Real Data Source:** Silver DataFrame from Story 4.3 (32K+ rows)
**Validation Criteria:**
1. Composite PK (月度, 计划代码, company_id) has no duplicates
2. Column projection removes intermediate fields
3. All required fields non-null
4. Asset values non-negative

**Expected Results:**
- Gold validation passes for 32K+ rows
- 0 composite PK duplicates (or detect and handle)
- Projection removes 2-3 intermediate calculation columns
- Final DataFrame ready for database loading

**Edge Cases to Test:**
- Duplicate PKs in source → Gold validation catches, exports to failed_rows.csv
- Extra columns in Silver → removed by projection, logged

**Simplicity Check:**
- ✅ Gold schema as strict as needed for database integrity?
- ✅ Not over-validating (Bronze/Silver already validated)?

**Performance Target:** <5ms for 32K rows (DataFrame-level validation)

---

#### Story 4.5: End-to-End Integration - Real Data Validation

**Validation Objective:** Verify complete pipeline on production data with database loading

**Real Data Source:** 202412 full dataset (33,615 rows from Epic 3 → 32K+ rows to database)
**Validation Criteria:**
1. File discovery (Epic 3) → V2 folder selected automatically
2. Bronze → Silver → Gold → Database flow completes
3. Database: 32K+ rows inserted to `annuity_performance_NEW`
4. Idempotent re-run: identical database state
5. Execution time: <10 minutes total

**Expected Results:**
- ✅ File discovered: V2 folder (highest version)
- ✅ Rows loaded: 32,000+ (>95% of 33,615 input)
- ✅ Database state: Composite PK constraint enforced
- ✅ Duration: <10 minutes (target: 6-8 minutes)
- ✅ Audit log: execution metrics logged

**Edge Cases to Test:**
- Re-run same month → upsert updates existing rows
- Database connection failure → retry 3 times, then fail with clear error
- Failed rows CSV: exported with error details

**Simplicity Check:**
- ✅ End-to-end flow as simple as needed?
- ✅ No unnecessary intermediate files or caching?
- ✅ Error handling graceful without complexity?

**Performance Target:** <10 minutes for 33K rows (Epic NFR requirement)

---

#### Story 4.6: Configuration & Documentation - Real Data Validation

**Validation Objective:** Verify configuration supports production folder structure

**Real Data Source:** 202412 and 202411 paths (different structures)
**Validation Criteria:**
1. `data_sources.yml` config for annuity domain loads successfully
2. Database migration creates `annuity_performance_NEW` table
3. Documentation accurate (runbook matches actual behavior)

**Expected Results:**
- Config schema validation passes
- Database migration applied without errors
- Composite PK constraint created
- Documentation includes: file paths, expected formats, troubleshooting

**Edge Cases to Test:**
- Invalid config (missing required field) → validation error on startup
- Migration applied twice → idempotent (no errors)

**Simplicity Check:**
- ✅ Configuration as simple as needed?
- ✅ Documentation clear without over-explaining?

**Performance Target:** N/A (configuration/documentation story)

---

### Cross-Story Validation

**Real Data End-to-End Test (After Story 4.5):**
1. Start with fresh database
2. Run complete pipeline: `process_annuity_performance(month="202412")`
3. Verify:
   - File discovery: V2 selected
   - Bronze validation: passes
   - Silver transformation: >95% success
   - Gold validation: passes
   - Database: 32K+ rows loaded
   - Duration: <10 minutes
   - Idempotent re-run: identical state

**Real Data Regression Test (After Story 4.6):**
- Run against 202411, 202412, 202501 (3 months)
- Verify consistent behavior across different data volumes
- No performance degradation

### Simplicity Governance

Each story's Real Data Validation includes explicit **Simplicity Check** section:
- Question assumptions: "Is this complexity necessary?"
- Compare against real data: "Does real data require this feature?"
- Team can challenge: "Can we solve this more simply?"

**Link's Principle:** Keep solution "在一个相对优雅的状态" (in a relatively elegant state)

---

## Test Strategy Summary

### Unit Tests

**Story 4.1: Pydantic Models**
- Test valid inputs: various date formats (YYYYMM, YYYY年MM月, YYYY-MM)
- Test invalid inputs: unparseable dates, negative assets, empty company_id
- Test field validators: ge=0 constraint, string trimming
- Coverage target: >95%

**Story 4.2: Bronze Schema**
- Test valid DataFrame: all expected columns present
- Test missing columns: SchemaError with column list
- Test invalid types: non-numeric in numeric columns
- Test completely null columns: SchemaError
- Coverage target: >90%

**Story 4.3: Transformation Steps**
- Test each step in isolation: date parsing, cleansing, enrichment, validation
- Test error collection: 50 failed rows, 950 pass
- Test enrichment stub: returns temporary IDs
- Test CSV export: failed_rows.csv structure
- Coverage target: >90%

**Story 4.4: Gold Schema**
- Test composite PK uniqueness: detect duplicates
- Test column projection: remove extra columns
- Test not-null constraints: required fields validated
- Coverage target: >90%

### Integration Tests

**Story 4.5: End-to-End Pipeline**
- Test complete flow: file discovery → validation → transformation → database
- Test with fixture Excel file (100 rows): all stages pass
- Test idempotent re-run: identical database state
- Test error scenarios: missing file, invalid Excel, validation failures
- Test database state: verify row counts, composite PK constraint
- Coverage target: >80%

**Story 4.6: Configuration**
- Test data_sources.yml loading: valid config parsed
- Test invalid config: validation error on startup
- Test database migration: annuity_performance_NEW table created
- Coverage target: >70%

### Performance Tests

**Throughput Validation:**
- Test 10,000 row file: completes in <10 minutes
- Test 50,000 row file: memory usage <2GB
- Test database loading: 10,000 rows in <30 seconds

**Benchmark Baseline:**
- Measure execution time per stage: discovery, Bronze, Silver, Gold, database
- Store baseline metrics for regression detection

### Test Data

**Fixture Excel File:** `tests/fixtures/annuity_sample.xlsx`
- 100 rows with realistic data
- Includes edge cases: missing values, invalid dates, duplicate PKs (5%)
- Chinese field names matching production

**Database Fixtures:**
- Temporary PostgreSQL database (pytest-postgresql)
- Migrations applied before each integration test
- Cleaned up after test completion

**Stub Enrichment Fixtures:**
```python
stub_provider = StubProvider(fixtures={
    "公司A有限公司": CompanyInfo(company_id="COMP001", ...),
    "公司B": CompanyInfo(company_id="COMP002", ...),
})
```

### CI/CD Integration

**Automated Checks (Epic 1 Story 1.11):**
- Run all unit tests on every commit (<30 seconds)
- Run integration tests on PR (<3 minutes)
- Track coverage trends: warn if <target
- Performance regression alert: >20% slower than baseline

### AC → Test Coverage Matrix

| AC | Test Type | Test Case | Status |
|----|-----------|-----------|--------|
| **Story 4.1** | | | |
| AC-4.1.1 | Unit | `test_pydantic_models_chinese_fields` | ✅ |
| AC-4.1.2 | Unit | `test_date_validator_chinese_formats` | ✅ |
| AC-4.1.3 | Unit | `test_validation_business_rules_assets_nonnegative` | ✅ |
| **Story 4.2** | | | |
| AC-4.2.1 | Unit | `test_bronze_schema_validates_excel_structure` | ✅ |
| AC-4.2.2 | Unit | `test_bronze_missing_column_raises_schema_error` | ✅ |
| AC-4.2.3 | Unit | `test_bronze_systemic_issue_detection_10pct_threshold` | ✅ |
| **Story 4.3** | | | |
| AC-4.3.1 | Unit | `test_pipeline_7_steps_execution_order` | ✅ |
| AC-4.3.2 | Unit | `test_failed_rows_csv_export_structure` | ✅ |
| AC-4.3.3 | Unit | `test_enrichment_stub_returns_temp_ids` | ✅ |
| AC-4.3.4 | Unit | `test_partial_success_handling_under_10pct_failure` | ✅ |
| AC-4.3.5 | Unit | `test_legacy_transformation_steps_column_rename_branch_code` | ✅ |
| AC-4.3.6 | Unit | `test_5step_enrichment_fallback_order` | ✅ |
| **Story 4.4** | | | |
| AC-4.4.1 | Unit | `test_gold_composite_pk_uniqueness_validation` | ✅ |
| AC-4.4.2 | Unit | `test_gold_column_projection_removes_extra_fields` | ✅ |
| AC-4.4.3 | Unit | `test_gold_notnull_constraints_enforced` | ✅ |
| **Story 4.5** | | | |
| AC-4.5.1 | Integration | `test_e2e_pipeline_complete_execution` | ✅ |
| AC-4.5.2 | Integration | `test_database_upsert_on_conflict` | ✅ |
| AC-4.5.3 | Integration | `test_idempotent_rerun_identical_state` | ✅ |
| AC-4.5.4 | Integration | `test_dagster_job_visible_in_ui` | ✅ |
| AC-4.5.5 | Performance | `test_10k_rows_under_10_minutes` | ✅ |
| **Story 4.6** | | | |
| AC-4.6.1 | Integration | `test_data_sources_yml_config_loading` | ✅ |
| AC-4.6.2 | Integration | `test_database_migration_creates_table` | ✅ |
| AC-4.6.3 | Manual | Documentation review checklist | ✅ |
| **Epic-Level** | | | |
| AC-EPIC4.1 | Integration | `test_architecture_validation_bronze_silver_gold` | ✅ |
| AC-EPIC4.2 | Performance | `test_performance_targets_met` | ✅ |
| AC-EPIC4.3 | Manual | Reference implementation review | ✅ |
| AC-EPIC4.4 | Integration | `test_parity_validation_plan_documented` (Epic 6 prep) | ✅ |

**Legend:**
- ✅ = Test case defined and mapped
- Unit = pytest unit test
- Integration = pytest integration test with fixtures
- Performance = pytest-benchmark or manual timing
- Manual = Documentation/review checklist
