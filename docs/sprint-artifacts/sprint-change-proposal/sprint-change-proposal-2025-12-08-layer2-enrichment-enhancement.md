# Sprint Change Proposal: Layer 2 Enrichment Index Enhancement

**Date:** 2025-12-08
**Triggered By:** Epic 6 Retrospective
**Change Scope:** Minor
**Status:** Pending Approval

---

## 1. Issue Summary

### 1.1 Problem Statement

Epic 6 Retrospective identified architectural limitations in Layer 2 (Database Cache) of the Company Enrichment Service:

1. **Priority Gap**: Layer 2 currently supports only single `normalized_name → company_id` lookup, while Layer 1 (YAML Configuration) supports 5 priority levels (P1-P5)
2. **Insufficient Self-Learning**: Backflow only triggers on Layer 3 (Existing Column) hits, failing to leverage processed data effectively
3. **Data Silos**: Valid mappings from Domain processing are not fed back to the global cache

### 1.2 Discovery Context

| Item | Details |
|------|---------|
| **Source** | Epic 6 Retrospective (2025-12-08) |
| **Technical Debt** | TD-1 (Legacy migration), TD-2 (Golden Dataset testing) |
| **Requirements Doc** | `docs/specific/company-enrichment-service/layer2-enrichment-index-enhancement.md` |

### 1.3 Evidence

- Epic 6 completed successfully with 9 stories and 380+ tests
- Technical guide `company-enrichment-service.md` already has Layer 2 enhancement placeholders
- Detailed technical design documented in requirements specification

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Status | Impact | Action |
|------|--------|--------|--------|
| Epic 6 | Done | None | Preserve as-is |
| **Epic 6.1 (New)** | - | New supplementary epic | Create with 4 stories |
| Epic 7 | Backlog | Benefits from enhancement | No changes needed |

### 2.2 Story Impact

**New Stories Required:**

| Story ID | Title | Description |
|----------|-------|-------------|
| 6.1.1 | Enrichment Index Schema Enhancement | Create `enrichment_index` table with multi-type support |
| 6.1.2 | Layer 2 Multi-Priority Lookup | Implement DB-P1 to DB-P5 priority lookup |
| 6.1.3 | Domain Learning Mechanism | Implement self-learning from processed Domain data |
| 6.1.4 | Legacy Data Migration | Migrate existing data to new `enrichment_index` table |

### 2.3 Artifact Conflicts

| Artifact | Conflict | Required Update |
|----------|----------|-----------------|
| PRD | None | No changes |
| Architecture | Enhancement | Update Layer 2 flow diagram |
| UI/UX | N/A | No UI components |
| Database Schema | Addition | New `enrichment_index` table |
| Technical Guide | Enhancement | Complete Layer 2 sections |

### 2.4 Technical Impact

| Area | Impact |
|------|--------|
| `CompanyIdResolver` | Modify `_resolve_via_db_cache()` for multi-priority |
| `ResolutionStatistics` | Add `db_cache_hits` by priority tracking |
| `MappingRepository` | Add methods for new table operations |
| Alembic Migrations | New migration for `enrichment_index` table |
| Observability | New metrics for priority-based hits |

---

## 3. Recommended Approach

### 3.1 Selected Path

**Option 1: Direct Adjustment** - Create Epic 6.1 as supplementary epic

### 3.2 Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | Medium - 4 stories, estimated 1-2 weeks |
| Technical Risk | Low - Backward compatible design |
| Team Impact | Positive - Enhancement, not rework |
| Long-term Value | High - Self-learning reduces manual maintenance |
| Business Value | High - Improved cache hit rate, reduced API dependency |

### 3.3 Why This Approach

1. **Preserves Epic 6 Integrity**: Epic 6 successfully delivered 9 stories with 380+ tests
2. **Follows Project Convention**: Project already has Epic 5.5, Epic 5.6 as supplementary epics
3. **Clear Traceability**: Epic 6.1 clearly identifies as Epic 6 enhancement
4. **Low Risk**: Backward compatible - `CompanyIdResolver` external API unchanged

### 3.4 Alternatives Considered

| Alternative | Why Not Selected |
|-------------|------------------|
| Modify Epic 6 | Breaks completed epic integrity |
| Merge into Epic 7 | Theme mismatch (Testing vs Enrichment) |
| Create independent Epic 7 | Loses association with Epic 6 |

---

## 4. Detailed Change Proposals

### 4.1 New Epic Definition

```yaml
# Epic 6.1: Layer 2 Enrichment Index Enhancement
epic-6.1: backlog
6.1-1-enrichment-index-schema-enhancement: backlog
6.1-2-layer2-multi-priority-lookup: backlog
6.1-3-domain-learning-mechanism: backlog
6.1-4-legacy-data-migration: backlog
epic-6.1-retrospective: optional
```

### 4.2 Story Definitions

#### Story 6.1.1: Enrichment Index Schema Enhancement

**Objective:** Create new `enrichment_index` table supporting multi-type lookups

**Tasks:**
- [ ] Create Alembic migration script for `enterprise.enrichment_index`
- [ ] Implement `lookup_type` enum (plan_code, account_name, account_number, customer_name, plan_customer)
- [ ] Implement `source` enum (yaml, eqc_api, manual, backflow, domain_learning, legacy_migration)
- [ ] Add indexes for efficient lookup
- [ ] Update `CompanyMappingRepository` with new table operations

**Acceptance Criteria:**
- New table created with proper constraints
- Repository methods for CRUD operations
- Unit tests for repository

---

#### Story 6.1.2: Layer 2 Multi-Priority Lookup

**Objective:** Implement DB-P1 to DB-P5 priority decision flow in Layer 2

**Tasks:**
- [ ] Modify `CompanyIdResolver._resolve_via_db_cache()` for multi-priority
- [ ] Implement batch query optimization
- [ ] Update `ResolutionStatistics` to track hits by priority
- [ ] Add decision path logging (e.g., `DB-P1:MISS→DB-P2:HIT`)

**Acceptance Criteria:**
- Layer 2 checks all 5 priority levels in order
- Statistics track hits per priority level
- Performance maintained with batch queries

**Dependencies:** Story 6.1.1

---

#### Story 6.1.3: Domain Learning Mechanism

**Objective:** Implement self-learning from processed Domain data

**Tasks:**
- [ ] Create `DomainLearningService`
- [ ] Implement learning data extraction logic
- [ ] Integrate into Pipeline post-processing
- [ ] Add learning statistics and logging
- [ ] Configure confidence levels per lookup_type

**Acceptance Criteria:**
- Valid mappings extracted from Domain tables after processing
- Mappings written to `enrichment_index` with appropriate confidence
- Temporary IDs (IN_*) excluded from learning
- Statistics track learning metrics

**Dependencies:** Story 6.1.2

---

#### Story 6.1.4: Legacy Data Migration to Enrichment Index

**Objective:** Migrate existing data to new `enrichment_index` table

**Tasks:**
- [ ] Analyze legacy data structure (`company_name_index`, legacy tables)
- [ ] Create migration script with data transformation
- [ ] Execute migration with validation
- [ ] Verify data integrity post-migration

**Acceptance Criteria:**
- All existing `company_name_index` data migrated
- Legacy mappings preserved with appropriate source tag
- No data loss during migration

**Dependencies:** Story 6.1.1

---

### 4.3 Database Schema Change

```sql
-- New table: enterprise.enrichment_index
CREATE TABLE enterprise.enrichment_index (
    id SERIAL PRIMARY KEY,

    -- Lookup keys
    lookup_key VARCHAR(255) NOT NULL,
    lookup_type VARCHAR(20) NOT NULL,  -- plan_code, account_name, account_number, customer_name, plan_customer

    -- Mapping result
    company_id VARCHAR(50) NOT NULL,

    -- Metadata
    confidence DECIMAL(3,2) DEFAULT 1.00,
    source VARCHAR(50) NOT NULL,       -- yaml, eqc_api, manual, backflow, domain_learning, legacy_migration
    source_domain VARCHAR(50),         -- Learning source domain
    source_table VARCHAR(100),         -- Learning source table

    -- Statistics
    hit_count INT DEFAULT 0,
    last_hit_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (lookup_key, lookup_type)
);

-- Indexes
CREATE INDEX ix_enrichment_index_type_key ON enterprise.enrichment_index(lookup_type, lookup_key);
CREATE INDEX ix_enrichment_index_source ON enterprise.enrichment_index(source);
CREATE INDEX ix_enrichment_index_source_domain ON enterprise.enrichment_index(source_domain);
```

### 4.4 Dependency Graph

```
Story 6.1.1 (Schema)
    ↓
Story 6.1.2 (Multi-Priority) ←── Story 6.1.4 (Legacy Migration)
    ↓
Story 6.1.3 (Domain Learning)
```

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

**Scope:** **Minor** - Can be implemented directly by development team

### 5.2 Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Scrum Master** | Create Epic 6.1 file, update sprint-status.yaml |
| **Developer** | Implement 4 stories |
| **Tech Lead** | Review architecture changes and database migrations |

### 5.3 Deliverables

| Deliverable | Owner | Status |
|-------------|-------|--------|
| Epic 6.1 definition file | SM | Pending |
| Story files (4) | SM | Pending |
| Updated sprint-status.yaml | SM | Pending |
| Implementation | Dev | Pending |
| Code review | Tech Lead | Pending |

### 5.4 Success Criteria

1. **Schema**: `enrichment_index` table created with all required columns and indexes
2. **Multi-Priority**: Layer 2 checks DB-P1 through DB-P5 in order
3. **Domain Learning**: Valid mappings automatically learned from processed data
4. **Migration**: All legacy data migrated without loss
5. **Backward Compatibility**: `CompanyIdResolver` external API unchanged
6. **Test Coverage**: All new functionality covered by unit tests

### 5.5 Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration data loss | Low | High | Backup before migration, validate counts |
| Performance regression | Low | Medium | Batch queries, proper indexing |
| Confidence conflicts | Medium | Low | Use GREATEST() on conflict |

---

## 6. Approval

### 6.1 Approval Status

| Role | Name | Status | Date |
|------|------|--------|------|
| Product Owner | - | Pending | - |
| Tech Lead | - | Pending | - |
| Developer | Link | Pending | - |

### 6.2 Next Steps After Approval

1. SM creates Epic 6.1 file in `docs/epics/` or appropriate location
2. SM updates `sprint-status.yaml` with Epic 6.1 and stories
3. SM drafts Story 6.1.1 first (schema is prerequisite)
4. Dev begins implementation following dependency order

---

## Appendix

### A. Related Documents

| Document | Path |
|----------|------|
| Requirements Spec | `docs/specific/company-enrichment-service/layer2-enrichment-index-enhancement.md` |
| Technical Guide | `docs/guides/company-enrichment-service.md` |
| Epic 6 Retrospective | `docs/sprint-artifacts/retrospective/epic-6-retro-2025-12-08.md` |
| Golden Dataset Plan | `docs/specific/company-enrichment-service/golden-dataset-testing-plan.md` |

### B. Sprint Status Update Preview

```yaml
# Add to sprint-status.yaml after approval:

# Epic 6.1: Layer 2 Enrichment Index Enhancement
# Supplementary epic from Epic 6 Retrospective
# Enhances DB Cache with multi-priority lookup and domain learning
epic-6.1: backlog
6.1-1-enrichment-index-schema-enhancement: backlog
6.1-2-layer2-multi-priority-lookup: backlog
6.1-3-domain-learning-mechanism: backlog
6.1-4-legacy-data-migration: backlog
epic-6.1-retrospective: optional
```

---

**Document Version:** 1.0
**Created:** 2025-12-08
**Author:** Correct Course Workflow
**Workflow:** `/bmad:bmm:workflows:correct-course`
