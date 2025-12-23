# Sprint Change Proposal: Epic 7.1 - Pre-Epic 8 Bug Fixes & Improvements

**Date:** 2025-12-23
**Author:** Link (via Claude)
**Type:** New Epic (Bug Fixes & Feature Enhancements)
**Status:** Draft - Pending Approval

---

## Executive Summary

This proposal introduces **Epic 7.1** as a focused cleanup and stabilization sprint between Epic 7 (Code Quality) and Epic 8 (Testing & Validation Infrastructure). The goal is to address discovered issues and reduce Epic 8 implementation complexity.

### Key Drivers

1. **Data Integrity Issues:** `enrichment_index` and `base_info` tables experiencing unexpected data loss
2. **Legacy Code Cleanup:** Deprecated `company_mapping` table still being created (Zero Legacy violation)
3. **Feature Gaps:** EQC API confidence scores not adjusted based on match quality
4. **Test Infrastructure:** Collection errors and failing tests blocking validation

---

## 1. Issue Summary

### 1.1 Trigger Context

**Epic 7 completed successfully** (all 6 stories done), but during retrospective validation and Epic 8 readiness assessment, multiple issues were identified that would complicate Epic 8 implementation if not addressed first.

### 1.2 Problem Categories

| Category | Count | Impact Level |
|----------|-------|--------------|
| Data Integrity Bugs | 2 | 🔴 Critical |
| Zero Legacy Violations | 1 | 🔴 Critical |
| Validation Blockers | 2 | 🟡 High |
| Feature Enhancements | 2 | 🟡 High |
| Tech Debt Cleanup | 3 | 🟢 Medium |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Notes |
|------|--------|-------|
| **Epic 7 (Code Quality)** | ✅ Complete | No changes needed |
| **Epic 7.1 (New)** | 🆕 Proposed | 11 action items across P0/P1/P2 |
| **Epic 8 (Validation)** | ⏸️ Blocked | Cannot start until P0 items resolved |
| **Future Epics** | ⚠️ At Risk | Data integrity issues could propagate |

### 2.2 Artifact Impact

| Artifact | Changes Required |
|----------|-----------------|
| **sprint-status.yaml** | Add Epic 7.1 and stories |
| **epic-8-readiness-assessment.md** | Update to reference Epic 7.1 |
| **Alembic Migrations** | Remove `company_mapping` creation |
| **manifest.yml** | Remove `company_mapping` from utility_tables |
| **Test Files** | Fix/remove 2 files with import errors |
| **cleaner_compare.py** | Add `--file-selection` parameter |
| **enrichment_index_ops.py** | Add confidence adjustment logic |

### 2.3 Technical Impact

```
┌─────────────────────────────────────────────────────────────────┐
│                    Data Integrity Chain                         │
├─────────────────────────────────────────────────────────────────┤
│  base_info (EQC raw data)                                       │
│       ↓ parsing                                                 │
│  enrichment_index (lookup cache)                                │
│       ↓ lookup                                                  │
│  Domain Tables (annuity_performance, etc.)                      │
│       ↓ validation                                              │
│  Epic 8 Classification-Based Validation                         │
└─────────────────────────────────────────────────────────────────┘

⚠️ If base_info/enrichment_index are cleared, entire chain breaks!
```

---

## 3. Recommended Approach

### 3.1 Selected Path: Direct Adjustment (New Epic)

**Rationale:**
- Issues are discrete and addressable within existing architecture
- No rollback or MVP scope change needed
- Clear scope boundaries prevent scope creep
- Estimated effort: 2-3 days for P0+P1

### 3.2 Epic 7.1 Scope Definition

#### P0 - BLOCKING (Must complete before Epic 8)

| Story | Title | Effort | Description |
|-------|-------|--------|-------------|
| **7.1-1** | Fix Data Clearing Root Cause | 4h | Investigate and fix `enrichment_index`/`base_info` clearing; add protection |
| **7.1-2** | ETL Execute Mode Validation | 2h | Verify `--execute` mode writes correctly to database |
| **7.1-3** | Fix Test Collection Errors | 1h | Fix/remove 2 files with `work_data_hub.scripts` import errors |
| **7.1-4** | Remove company_mapping Legacy | 3h | Delete deprecated table, DDL, loader, manifest entry, Alembic reference |

#### P1 - HIGH (Strongly Recommended)

| Story | Title | Effort | Description |
|-------|-------|--------|-------------|
| **7.1-5** | Add File Selection to cleaner_compare | 2h | Add `--file-selection` parameter for consistency with ETL CLI |
| **7.1-6** | Fix Classification Logic | 1h | Change `regression_company_id_mismatch` → `data_source_difference` |
| **7.1-7** | Verify Legacy DB Connection | 1h | Confirm MySQL connection for Epic 8 Golden Dataset comparison |
| **7.1-8** | EQC Confidence Dynamic Adjustment | 4h | Adjust confidence based on match type (全称精确匹配/模糊匹配/拼音) |

#### P2 - MEDIUM (Recommended)

| Story | Title | Effort | Description |
|-------|-------|--------|-------------|
| **7.1-9** | Clean Up Failing Tests | 4h | Address 33 failing tests (mostly DB integration) |
| **7.1-10** | Categorize Ruff Warnings | 2h | Triage 1074 Ruff warnings from Story 7.6 |
| **7.1-11** | Update project-context.md | 1h | Reflect Epic 7 architecture changes |

### 3.3 Effort & Risk Summary

| Scope | Stories | Effort | Risk |
|-------|---------|--------|------|
| P0 Only | 4 | ~10h | Low |
| P0 + P1 | 8 | ~18h | Low |
| Full (P0+P1+P2) | 11 | ~25h | Low |

**Recommendation:** Complete P0 + P1 (8 stories, ~18h) before Epic 8 kickoff.

---

## 4. Detailed Change Proposals

### 4.1 Story 7.1-1: Fix Data Clearing Root Cause

**Problem:** `enrichment_index` and `base_info` tables being unexpectedly cleared

**Investigation Findings:**
- `tests/conftest.py:184` runs `migration_runner.downgrade(temp_dsn, "base")`
- If `DATABASE_URL` misconfigured, production DB could be wiped
- No explicit DELETE statements without WHERE conditions found
- Tests may fail or connect to wrong DB if `.wdh_env` not loaded

**Proposed Fixes:**

**Fix 1: Safety check for test database**
```python
# Add safety check in conftest.py
def _validate_test_database(dsn: str) -> bool:
    """Ensure we're not connected to production database."""
    parsed = urlparse(dsn)
    db_name = parsed.path.lstrip('/')
    if 'test' not in db_name.lower() and 'tmp' not in db_name.lower():
        raise RuntimeError(f"Refusing to run tests against non-test database: {db_name}")
    return True
```

**Fix 2: Default to .wdh_env for test database configuration**
```python
# conftest.py - Auto-load .wdh_env if exists
from pathlib import Path
from dotenv import load_dotenv

# Load .wdh_env from project root by default
_env_file = Path(__file__).parent.parent / ".wdh_env"
if _env_file.exists():
    load_dotenv(_env_file)
```

**Acceptance Criteria:**
- [ ] Root cause identified and documented
- [ ] Protection mechanism added to prevent production data loss
- [ ] Tests automatically load `.wdh_env` from project root if available
- [ ] Data restoration procedure documented

---

### 4.2 Story 7.1-4: Remove company_mapping Legacy

**Problem:** Deprecated `company_mapping` table and code still exist (Zero Legacy violation)

**Files to Modify/Delete:**

| Action | File |
|--------|------|
| DELETE | `scripts/create_table/ddl/company_mapping.sql` |
| DELETE | `src/work_data_hub/io/loader/company_mapping_loader.py` |
| MODIFY | `scripts/create_table/manifest.yml` - Remove `company_mapping` from `utility_tables` |
| MODIFY | `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` - Remove Step 5 |
| MODIFY | `src/work_data_hub/orchestration/jobs.py` - Remove `import_company_mappings_job` |
| DELETE | `tests/io/test_company_mapping_loader.py` |
| DELETE | `tests/io/loader/test_company_mapping_loader.py` |
| DELETE | `tests/e2e/test_company_mapping_migration.py` |
| DELETE | `tests/integration/migrations/test_enterprise_schema_migration.py` (company_mapping tests) |

**Acceptance Criteria:**
- [ ] All `company_mapping` references removed from codebase
- [ ] Alembic migration no longer creates the table
- [ ] Tests pass without company_mapping
- [ ] Documentation updated to remove references

---

### 4.3 Story 7.1-8: EQC Confidence Dynamic Adjustment

**Problem:** EQC API results stored with static confidence regardless of match quality

**Current Data Distribution:**
| Match Type | Count | Current Confidence | Proposed Confidence |
|------------|-------|-------------------|---------------------|
| 全称精确匹配 | 13 | 1.00 (static) | 1.00 |
| 模糊匹配 | 107 | 1.00 (static) | 0.80 |
| 拼音 | 5 | 1.00 (static) | 0.60 |

**Proposed Implementation:**

```python
# config/eqc_confidence.yml (NEW - configurable mapping)
eqc_match_confidence:
  全称精确匹配: 1.00
  模糊匹配: 0.80
  拼音: 0.60
  default: 0.70

# infrastructure/enrichment/repository/enrichment_index_ops.py
def _get_eqc_confidence(match_type: str) -> float:
    """Get confidence score based on EQC match type."""
    config = load_eqc_confidence_config()
    return config.get(match_type, config.get('default', 0.70))
```

**Acceptance Criteria:**
- [ ] Confidence mapping is configurable via YAML
- [ ] EQC lookups use dynamic confidence based on match type
- [ ] Existing enrichment_index records can be backfilled with correct confidence
- [ ] Tests cover all match type scenarios

---

## 5. Implementation Handoff

### 5.1 Scope Classification: **Minor**

Direct implementation by development team. No backlog reorganization or strategic replan required.

### 5.2 Handoff Details

| Role | Responsibility |
|------|---------------|
| **Developer (Link)** | Implement all Epic 7.1 stories |
| **QA** | Verify data integrity and test coverage |
| **PM** | Approve this proposal, track Epic 7.1 completion |

### 5.3 Success Criteria

**Epic 7.1 Definition of Done:**
- [ ] All P0 stories completed (4 items)
- [ ] All P1 stories completed (4 items)
- [ ] `enrichment_index` and `base_info` data protected
- [ ] `company_mapping` fully removed from codebase
- [ ] Test suite passing without collection errors
- [ ] Epic 8 Readiness Assessment updated to reflect fixes

### 5.4 Timeline

```
Day 1: Stories 7.1-1, 7.1-2, 7.1-3 (Data integrity + validation)
Day 2: Stories 7.1-4, 7.1-5, 7.1-6 (Legacy cleanup + CLI alignment)
Day 3: Stories 7.1-7, 7.1-8 (Legacy DB + EQC confidence)
Day 4: P2 stories if time permits, Epic 8 kickoff
```

---

## 6. Appendix

### A. Related Documents

| Document | Purpose |
|----------|---------|
| [Epic 8 Strategy Change Proposal](sprint-change-proposal-2025-12-23-epic8-validation-strategy.md) | Classification-Based Validation approach |
| [Epic 8 Readiness Assessment](../reviews/epic-8-readiness-assessment.md) | Pre-flight checklist (source of P0-P2 items) |
| [Epic 7 Retrospective](../retrospective/epic-7-retro-2025-12-23.md) | Post-mortem findings |

### B. Files Containing company_mapping References (To Clean)

```
scripts/create_table/ddl/company_mapping.sql
scripts/create_table/manifest.yml
src/work_data_hub/io/loader/company_mapping_loader.py
src/work_data_hub/orchestration/jobs.py
src/work_data_hub/infrastructure/enrichment/repository/company_mapping_ops.py
io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py
tests/io/test_company_mapping_loader.py
tests/io/loader/test_company_mapping_loader.py
tests/e2e/test_company_mapping_migration.py
tests/domain/test_company_enrichment.py
tests/integration/migrations/test_enterprise_schema_migration.py
docs/brownfield-architecture.md
docs/guides/cli/cli-migration-guide.md
docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md
```

### C. EQC Match Type Distribution

```sql
SELECT elem->>'type' as match_type, COUNT(*) as cnt
FROM enterprise.base_info,
     jsonb_array_elements(raw_data->'list') as elem
WHERE raw_data IS NOT NULL
GROUP BY elem->>'type'
ORDER BY cnt DESC;

-- Results:
-- 模糊匹配: 107
-- 全称精确匹配: 13
-- 拼音: 5
```

---

**Document Version:** 1.0
**Created:** 2025-12-23
**Next Action:** PM Approval → Epic 7.1 Stories Creation → Implementation
