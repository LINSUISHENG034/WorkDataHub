# Sprint Change Proposal: Dependency Table Migration Documentation Enhancement

**Document ID:** SCP-2025-12-09-001
**Date:** 2025-12-09
**Status:** Approved
**Change Type:** Preventive Process Improvement
**Scope Classification:** Minor

---

## 1. Issue Summary

### Problem Statement

The current `cleansing-rules-template.md` template (7 sections) and `domain-development-guide.md` workflow (6 phases) lack systematic guidance for dependency table migration. This gap may cause:

1. Missing dependency tables during domain migration
2. Inconsistent data between legacy and new systems
3. Debugging complexity when data discrepancies occur
4. Ad-hoc fixes discovered late in the migration process

### Discovery Context

- **Trigger:** Preventive improvement identified after completing Epic 6.1 Story 6.1.4 (Legacy Data Migration)
- **Evidence:**
  - Current template has only 7 sections, missing dependency-related content
  - `annuity-income.md` completed migration without documenting dependency tables
  - 20+ domains pending migration in `cleansing-rules/index.md`
  - Migration script exists (`migrate_legacy_to_enrichment_index.py`) but not referenced in documentation

### Key User Feedback

> "Dependency table inventory and migration strategy decisions should be placed at the **front** as **prerequisites** for domain migration. Only when these foundational conditions are ready can a domain be effectively migrated and fully aligned with legacy architecture."

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact |
|------|--------|
| Epic 6.1 (Current) | No impact - already completed |
| Epic 7+ (Future) | **Benefits** - improved templates and workflows will guide migrations |

**Conclusion:** No Epic-level changes required. This is a documentation/process improvement.

### Artifact Impact

| Artifact | Change Type | Priority | Description |
|----------|-------------|----------|-------------|
| `docs/templates/cleansing-rules-template.md` | Restructure + Add sections | **P0** | Reorder sections, add dependency-related sections at front |
| `docs/guides/domain-development-guide.md` | Add new phase | **P0** | Add Phase 1: Dependency Analysis & Migration |
| `docs/cleansing-rules/annuity-income.md` | Update example | P1 | Add dependency table sections as reference |
| `docs/cleansing-rules/index.md` | Add tracking column | P2 | Add migration status tracking |

### Technical Impact

- **Code Changes:** None
- **Database Changes:** None
- **Infrastructure Changes:** None
- **Testing Impact:** None

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

**Rationale:**

| Factor | Assessment |
|--------|------------|
| Implementation Effort | Low - only 3-4 document files to update |
| Timeline Impact | None - can be implemented immediately |
| Technical Risk | None - pure documentation changes |
| Team Impact | Positive - provides clear guidance for future migrations |
| Long-term Maintainability | High - standardized process reduces omissions |
| Business Value | High - ensures data migration consistency |

### Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| Rollback | Not applicable | No code to rollback |
| MVP Review | Not applicable | Does not affect MVP scope |

---

## 4. Detailed Change Proposals

### 4.1 Template Restructure: `cleansing-rules-template.md`

**Current Structure (7 sections):**
```
1. Domain Overview
2. Column Mappings
3. Cleansing Rules
4. Company ID Resolution Strategy
5. Validation Rules
6. Special Processing Notes
7. Parity Validation Checklist
```

**Proposed Structure (10 sections):**
```
1. Domain Overview
2. Dependency Table Inventory (NEW - PREREQUISITE)
3. Migration Strategy Decisions (NEW - PREREQUISITE)
4. Migration Validation Checklist (NEW - PREREQUISITE)
5. Column Mappings (was Section 2)
6. Cleansing Rules (was Section 3)
7. Company ID Resolution Strategy (was Section 4)
8. Validation Rules (was Section 5)
9. Special Processing Notes (was Section 6)
10. Parity Validation Checklist (was Section 7)
```

**New Section 2: Dependency Table Inventory**
```markdown
## 2. Dependency Table Inventory

### Critical Dependencies (Must Migrate Before Domain Implementation)

| # | Table Name | Database | Purpose | Row Count | Migration Status |
|---|------------|----------|---------|-----------|-----------------|
| 1 | | | | | [PENDING] |

### Optional Dependencies

| # | Table Name | Database | Purpose | Notes |
|---|------------|----------|---------|-------|
| 1 | | | | |
```

**New Section 3: Migration Strategy Decisions**
```markdown
## 3. Migration Strategy Decisions

### Decision Summary
- **Decision Date**: YYYY-MM-DD
- **Decision Maker**: [Name]
- **Reviewed By**: [Name]

### Strategy Options Reference

| Strategy | Description | Typical Use Cases |
|----------|-------------|-------------------|
| Direct Migration | Move table as-is | Simple lookup tables |
| Enrichment Index | Migrate to enterprise.enrichment_index | Company/entity mappings |
| Transform & Load | Restructure data | Complex schema changes |
| Static Embedding | Hardcode in constants | Small, stable lookups |
| Decommission | Mark obsolete | Unused tables |
| Custom Strategy | Team-defined approach | Unique requirements |

### Dependency Table Strategies

| # | Table Name | Legacy Schema | Target Strategy | Target Location | Rationale |
|---|------------|---------------|-----------------|-----------------|-----------|
| 1 | | | | | |
```

**New Section 4: Migration Validation Checklist**
```markdown
## 4. Migration Validation Checklist

### Pre-Migration
- [ ] Source database accessible
- [ ] Target schema/index exists
- [ ] Migration script tested in dry-run mode

### Migration Execution
- [ ] Run migration script: `PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py`
- [ ] Verify batch completion without errors

### Post-Migration Validation
- [ ] Row count validation (source vs target)
- [ ] Data sampling validation (10 random keys)
- [ ] Performance validation (lookup latency < 10ms)
```

---

### 4.2 Workflow Update: `domain-development-guide.md`

**Current Phases:**
```
Phase 1: Analysis (Before Coding)
Phase 2: Implementation
Phase 3: Configuration
Phase 4: Testing & Validation
Phase 5: Documentation
Phase 6: Deployment & Merge
```

**Proposed Phases:**
```
Phase 1: Dependency Analysis & Migration (NEW - PREREQUISITE)
Phase 2: Analysis (was Phase 1)
Phase 3: Implementation (was Phase 2)
Phase 4: Configuration (was Phase 3)
Phase 5: Testing & Validation (was Phase 4)
Phase 6: Documentation (was Phase 5)
Phase 7: Deployment & Merge (was Phase 6)
```

**New Phase 1 Content:**
```markdown
### Phase 1: Dependency Analysis & Migration (PREREQUISITE)

- [ ] Identify all dependency tables from legacy code analysis
- [ ] Document dependencies in cleansing rules document (Section 2)
- [ ] **CRITICAL**: Complete Migration Strategy Decisions (Section 3)
  - [ ] Review each dependency table with team
  - [ ] Document chosen strategy and rationale
  - [ ] Team lead review and sign-off
- [ ] Execute migration based on decided strategy
  - [ ] For Enrichment Index: Use `scripts/migrations/migrate_legacy_to_enrichment_index.py`
  - [ ] For Direct Migration: Use appropriate migration scripts
  - [ ] For Static Embedding: Update constants files
- [ ] Complete Migration Validation Checklist (Section 4)
- [ ] Update migration status in documentation
```

---

### 4.3 Example Update: `annuity-income.md`

Add the three new sections (2, 3, 4) with actual data from the completed migration:

**Section 2 Example:**
```markdown
## 2. Dependency Table Inventory

### Critical Dependencies (Migrated)

| # | Table Name | Database | Purpose | Row Count | Migration Status |
|---|------------|----------|---------|-----------|-----------------|
| 1 | company_id_mapping | legacy | Company name to ID mapping | ~19,141 | [MIGRATED] |
| 2 | eqc_search_result | legacy | EQC company lookups | ~11,820 | [MIGRATED] |
```

---

### 4.4 Index Update: `cleansing-rules/index.md`

**Current Table:**
```markdown
| Domain | Status | Document | Legacy Class |
```

**Proposed Table:**
```markdown
| Domain | Status | Document | Legacy Class | Dependencies Migrated |
```

---

## 5. Implementation Handoff

### Scope Classification: Minor

This change can be implemented directly by the development team without backlog reorganization or strategic review.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Execute document updates |
| **Technical Lead** | Review changes for consistency |

### Implementation Tasks

| Task | Priority | Estimated Effort |
|------|----------|------------------|
| Update `cleansing-rules-template.md` | P0 | 30 min |
| Update `domain-development-guide.md` | P0 | 30 min |
| Update `annuity-income.md` (example) | P1 | 20 min |
| Update `cleansing-rules/index.md` | P2 | 10 min |

### Success Criteria

1. Template contains dependency-related sections at front (Sections 2-4)
2. Workflow contains Phase 1: Dependency Analysis & Migration
3. `annuity-income.md` updated as reference example
4. All changes pass Technical Lead review

---

## 6. Approval and Sign-off

### Approval Status

- **User Approval:** Approved (2025-12-09)
- **Approval Conditions:** Dependency table sections must be placed at front as prerequisites

### Next Steps

1. Implement document updates per Section 4 specifications
2. Technical Lead review
3. Merge changes to main branch
4. Notify team of updated templates and workflow

---

## References

1. [Original Requirements Document](../../specific/optimized-requirements/dependency-table-migration-for-cleansing-rules.md)
2. [Current Cleansing Rules Template](../../templates/cleansing-rules-template.md)
3. [Current Domain Development Guide](../../guides/domain-development-guide.md)
4. [Migration Script](../../../scripts/migrations/migrate_legacy_to_enrichment_index.py)
5. [Cleansing Rules Index](../../cleansing-rules/index.md)

---

## Change History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-09 | Claude (AI) | Initial proposal created via Correct Course workflow |

---

**End of Sprint Change Proposal**
