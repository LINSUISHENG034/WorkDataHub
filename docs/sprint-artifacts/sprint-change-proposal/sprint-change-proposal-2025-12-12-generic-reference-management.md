# Sprint Change Proposal: Generic Reference Data Management

**Date:** 2025-12-12
**Status:** Pending Approval
**Triggered By:** Story 6.1 Development - `annuity_performance` Domain
**Change Scope:** Moderate
**Proposed Epic:** Epic 6.2 - Generic Reference Data Management

---

## 1. Issue Summary

### 1.1 Problem Statement

When fact data (e.g., `规模明细` table) contains foreign key values that don't exist in parent tables, database INSERT operations fail due to FK constraint violations. The current `reference_backfill` mechanism only covers 2 out of 4 foreign keys (50%), leaving `产品线` (Product Lines) and `组织架构` (Organization) gaps that cannot be automatically handled.

### 1.2 Discovery Context

- **Discovered During:** Story 6.1 development for `annuity_performance` domain
- **Discovery Date:** 2025-12-11
- **Issue Type:** Technical limitation discovered during implementation

### 1.3 Evidence

**Current FK Coverage Gap:**

| FK Constraint | Reference Table | Current Backfill | Status |
|--------------|-----------------|------------------|--------|
| `fk_规模明细_年金计划` | 年金计划 | `derive_plan_candidates()` | ✅ Covered |
| `fk_规模明细_组合计划` | 组合计划 | `derive_portfolio_candidates()` | ✅ Covered |
| `fk_规模明细_产品线` | 产品线 | - | ❌ **Gap** |
| `fk_规模明细_组织架构` | 组织架构 | - | ❌ **Gap** |

**Coverage Rate:** 50% (2/4)

**Business Impact:**
- Significantly reduces data processing automation level
- Requires manual intervention to resolve FK violations
- Blocks pipeline execution until parent records are created

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 6: Company Enrichment | Done | No impact - different problem domain |
| Epic 6.1: Layer 2 Enrichment | Done | No impact - already completed |
| **Epic 6.2 (NEW)** | Proposed | New epic to address this issue |
| Epic 7: Testing & Validation | Backlog | Minor - Golden Dataset tests need to consider auto_derived records |
| Epic 9+: Growth Domains | Future | Positive - new framework simplifies FK handling |

### 2.2 Story Impact

**Current Stories:** No existing stories affected (Epic 6.1 completed successfully)

**New Stories Required:** 4-6 stories for Epic 6.2 implementation

### 2.3 Artifact Conflicts

| Artifact | Current State | Required Change |
|----------|---------------|-----------------|
| Database Schema | No source tracking | Add `_source`, `_needs_review`, `_derived_from_domain`, `_derived_at` columns |
| `config/data_sources.yml` | No FK configuration | Add `foreign_keys` configuration structure |
| Architecture Decisions | No FK management decision | Add AD-011: Hybrid Reference Data Management |
| Domain Development Guide | No FK handling guidance | Update with FK configuration instructions |
| `reference_backfill` domain | Hardcoded 2 FKs | Extend to generic framework |

### 2.4 Technical Impact

**Code Changes Required:**

| Component | Location | Change Type |
|-----------|----------|-------------|
| Generic Backfill Service | `domain/reference_backfill/service.py` | Major refactor |
| FK Configuration Model | `domain/reference_backfill/models.py` | New file |
| Pipeline Ops | `orchestration/ops.py` | Extend existing |
| Database Migrations | `io/schema/migrations/` | New migration |
| Configuration Schema | `config/data_sources.yml` | Schema extension |

---

## 3. Recommended Approach

### 3.1 Selected Path: Hybrid Strategy (Option B + D)

**Strategy:** Combine Generic Backfill Framework (Option B) with Pre-load Reference Tables (Option D) for optimal data quality and automation.

### 3.2 Phased Implementation

```
Phase 1: Generic Backfill Framework (Option B)
    ↓ Quickly solve current problem
Phase 2: Data Source Tracking Fields
    ↓ Prepare for hybrid strategy
Phase 3: Pre-load Service (Option D)
    ↓ Improve data quality
Phase 4: Hybrid Strategy Integration
    ↓ Final form
```

### 3.3 Hybrid Strategy Design

**Two-Layer Data Quality Model:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Authoritative Data (权威数据)                         │
│  Source: Legacy MySQL, MDM, Config files                        │
│  Characteristics: Complete fields, verified, audit trail        │
│  Marker: source = 'authoritative'                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Auto-Derived Data (自动派生数据)                      │
│  Source: New FK values from fact data                           │
│  Characteristics: Minimal fields, needs review                  │
│  Marker: source = 'auto_derived', needs_review = true           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Rationale

| Factor | Assessment |
|--------|------------|
| Business Reality | New FK values are common in complex business; pure pre-load cannot handle |
| Data Quality | Pure backfill degrades reference data quality; hybrid preserves pre-load advantages |
| Operations | Even if pre-load fails, system continues (degraded mode) |
| Evolution | As data governance matures, auto_derived ratio naturally decreases |

### 3.5 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema migration issues | Low | Medium | Test in staging first |
| Auto-derived data accumulation | Medium | Low | Set alert thresholds, regular review |
| Circular FK dependencies | Low | High | Configure `depends_on` in FK config |
| Pre-load job failures | Medium | Low | Backfill provides fallback |

### 3.6 Effort and Timeline

| Metric | Assessment |
|--------|------------|
| Effort Estimate | **Medium** - 4-6 Stories |
| Risk Level | **Medium** - Schema changes but controllable |
| Timeline Impact | **Low** - Does not block other work |

---

## 4. Detailed Change Proposals

### 4.1 Epic 6.2: Generic Reference Data Management

**Goal:** Build a generic reference data management framework using hybrid strategy (pre-load + on-demand backfill), supporting multi-FK, multi-domain, configuration-driven approach with data quality tracking.

**Business Value:** Eliminates FK constraint failures, improves pipeline automation, provides data quality visibility through source tracking.

**Dependencies:** Epic 5 (Infrastructure Layer), Epic 6.1 (Enrichment Index)

---

### 4.2 Proposed Stories

#### Story 6.2.1: Generic Backfill Framework Core

**As a** data engineer,
**I want** a configuration-driven generic backfill framework,
**So that** new FK relationships can be handled without code changes.

**Acceptance Criteria:**

*Functional:*
- FK relationships defined in `config/data_sources.yml`
- Generic `derive_candidates()` function based on configuration
- Supports multiple FKs per domain (all 4 FKs: 年金计划, 组合计划, 产品线, 组织架构)
- Dependency ordering using `graphlib.TopologicalSorter` based on `depends_on` field

*Risk Mitigation (验证脚本覆盖):*
- [ ] **Circular Dependency Detection:** System raises `ValueError` when circular dependencies detected
- [ ] **Topological Sort Correctness:** Processing order respects `depends_on` (parent before child)
- [ ] **Data Source Tracking:** Auto-derived records include `_source='auto_derived'`, `_needs_review=True`, `_derived_from_domain`, `_derived_at`
- [ ] **Performance Baseline:** ≥2,000 rows/sec for batch insert operations

*Verification:*
- All tests in `scripts/validation/verify_backfill_integrated.py` must pass (6/6)

**Technical Notes:**
- Implement `ForeignKeyConfig` Pydantic model with `depends_on: List[str]` field
- Implement `GenericBackfillService` class with `_topological_sort()` method
- Use `graphlib.TopologicalSorter` (Python 3.9+) for DAG sorting
- SQL generation using SQLAlchemy Core

---

#### Story 6.2.2: Reference Table Schema Enhancement

**As a** data engineer,
**I want** data source tracking fields on reference tables,
**So that** I can distinguish authoritative data from auto-derived data.

**Acceptance Criteria:**
- Add columns: `_source`, `_needs_review`, `_derived_from_domain`, `_derived_at`
- Migration script for all 4 reference tables
- Default values: `_source='authoritative'`, `_needs_review=false`

**Technical Notes:**
- Migration file: `YYYYMMDD_HHMM_add_reference_tracking_fields.py`
- Backward compatible (existing data marked as authoritative)

---

#### Story 6.2.3: FK Configuration Schema Extension

**As a** data engineer,
**I want** FK relationships defined in `data_sources.yml`,
**So that** adding new FKs only requires configuration updates.

**Acceptance Criteria:**
- New `foreign_keys` section in domain configuration
- Pydantic validation for FK configuration
- Support for `depends_on` to declare FK dependencies

**Configuration Example:**
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

---

#### Story 6.2.4: Pre-load Reference Sync Service

**As a** data engineer,
**I want** a pre-load service that syncs reference data from authoritative sources,
**So that** most FK values are covered before fact processing.

**Acceptance Criteria:**
- Sync from Legacy MySQL for 年金计划, 组合计划, 组织架构
- Load from config file for 产品线
- Mark all pre-loaded data as `source='authoritative'`
- Scheduled execution (daily at 1:00 AM)

**Technical Notes:**
- Implement `ReferenceSyncService` class
- Support multiple source types: `legacy_mysql`, `config_file`
- Dagster job: `reference_sync_job`

---

#### Story 6.2.5: Hybrid Reference Service Integration

**As a** data engineer,
**I want** a unified service combining pre-load and backfill,
**So that** pipelines never fail due to missing FK references.

**Acceptance Criteria:**
- `HybridReferenceService` coordinates pre-load and backfill
- Backfill only triggers for values not covered by pre-load
- Auto-derived records marked with tracking fields
- Notification on new auto-derived records (optional)

**Technical Notes:**
- Implement `HybridReferenceService` class
- Integration with existing pipeline ops
- Metrics: pre-load coverage, backfill count, auto-derived ratio

---

#### Story 6.2.6: Reference Data Observability

**As a** data engineer,
**I want** visibility into reference data quality,
**So that** I can monitor auto-derived ratio and prioritize data governance.

**Acceptance Criteria:**
- Dashboard query for data quality metrics
- Alert when auto_derived ratio exceeds threshold (e.g., >10%)
- Export pending review records to CSV
- Audit log for reference data changes

**Dashboard Query Example:**
```sql
SELECT
    _source,
    COUNT(*) as record_count,
    SUM(CASE WHEN _needs_review THEN 1 ELSE 0 END) as pending_review
FROM "business"."年金计划"
GROUP BY _source;
```

---

### 4.3 Architecture Decision Proposal

**AD-011: Hybrid Reference Data Management Strategy**

**Problem:** FK constraint violations block pipeline execution when fact data contains new FK values not present in reference tables.

**Decision:** Implement hybrid strategy combining pre-load (authoritative data) with on-demand backfill (auto-derived data), with data quality tracking.

**Key Design Points:**
1. Two-layer data quality model (authoritative vs. auto-derived)
2. Configuration-driven FK relationships
3. Dependency-aware processing order
4. Source tracking for data governance
5. Graceful degradation (backfill as fallback)

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

**Scope:** **Moderate** - Requires backlog reorganization and PO/SM coordination

### 5.2 Handoff Recipients

| Role | Responsibility |
|------|----------------|
| Product Owner | Approve Epic 6.2 creation, priority ranking |
| Scrum Master | Create story files, manage sprint status |
| Architect | Review architecture decision, ensure pattern consistency |
| Developer | Implement stories, write tests |

### 5.3 Success Criteria

1. All 4 FK relationships covered (100% coverage)
2. No FK constraint failures in pipeline execution
3. Auto-derived records properly tracked and reviewable
4. Pre-load covers >90% of FK values in normal operation
5. Backfill provides reliable fallback for new values

### 5.4 Technical Verification Results

**Verification Date:** 2025-12-12 (Enhanced)
**Script:** `scripts/validation/verify_backfill_integrated.py`

| Verification Item | Result | Notes |
|-------------------|--------|-------|
| Configuration Schema Validation | ✅ PASSED | All 4 FK configs parsed successfully |
| Topological Sort (depends_on) | ✅ PASSED | Correct order: grandparent → parent → child |
| Circular Dependency Detection | ✅ PASSED | Correctly detected and raised error |
| All 4 FK Coverage | ✅ PASSED | 9 records inserted into 4 tables |
| Data Source Tracking Fields | ✅ PASSED | `_source`, `_needs_review`, `_derived_from_domain`, `_derived_at` all correct |
| Large Dataset Performance (10K) | ✅ PASSED | **148,266 rows/sec** (threshold: 2,000 rows/sec) |

**Conclusion:** Technical feasibility confirmed with comprehensive risk coverage (6/6 tests passed).

### 5.5 Migration Strategy

**Context:** New Pipeline (Dagster-based) is NOT yet in production. Legacy system continues to operate independently.

**Strategy:** Clean One-Time Switch (无需向后兼容)

**Rationale:**
- No production traffic depends on current `reference_backfill` implementation
- Clean architecture is more valuable than backward compatibility shims
- Reduces long-term maintenance burden
- Avoids technical debt from compatibility layers

**Migration Approach:**

| Component | Current State | Target State | Action |
|-----------|---------------|--------------|--------|
| `derive_plan_candidates()` | Hardcoded function | Configuration-driven | **Replace** |
| `derive_portfolio_candidates()` | Hardcoded function | Configuration-driven | **Replace** |
| `BackfillService` class | Domain-specific | `GenericBackfillService` | **Replace** |
| Pipeline ops | Calls specific functions | Calls generic service | **Refactor** |
| `data_sources.yml` | No FK config | Add `foreign_keys` section | **Extend** |

**Implementation Steps:**

1. **Story 6.2.1:** Implement `GenericBackfillService` with full FK configuration support
2. **Story 6.2.3:** Add `foreign_keys` configuration to `data_sources.yml`
3. **Cutover:** Replace existing `BackfillService` calls with `GenericBackfillService`
4. **Cleanup:** Remove deprecated `derive_*_candidates()` functions after validation

**Rollback Plan:** If issues arise, revert to previous commit (Git-based rollback). No data migration required since reference tables schema changes are additive (new columns only).

### 5.6 Next Steps

1. **[PO]** Review and approve this Sprint Change Proposal
2. **[SM]** Create Epic 6.2 entry in sprint-status.yaml
3. **[SM]** Draft Story 6.2.1 using create-story workflow
4. **[Architect]** ~~Add AD-011 to architectural-decisions.md~~ ✅ Done
5. **[Dev]** Begin implementation after story approval

---

## 6. Appendix

### 6.1 Reference Documents

- Problem Analysis: `docs/specific/backfill-method/problem-analysis.md`
- Mixed Strategy Solution: `docs/specific/backfill-method/mixed-strategy-solution.md`
- Verification Plan: `docs/specific/backfill-method/verification-plan-v2.md`
- Existing Backfill Service: `src/work_data_hub/domain/reference_backfill/service.py`

### 6.2 Related PRD Requirements

- FR-4.1: Transactional Bulk Loading
- FR-7.1: YAML-Based Domain Configuration

### 6.3 Approval History

| Date | Reviewer | Decision | Notes |
|------|----------|----------|-------|
| 2025-12-12 | Pending | - | Initial proposal |
| 2025-12-12 | PM (Link) | ✅ **Approved** | Technical verification passed (6/6), migration strategy confirmed, acceptance criteria enhanced |

---

**Document Generated:** 2025-12-12
**Workflow:** Correct Course - Sprint Change Management
**Author:** BMad Method Assistant
