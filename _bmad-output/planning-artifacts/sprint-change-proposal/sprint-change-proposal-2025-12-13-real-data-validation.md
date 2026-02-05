# Sprint Change Proposal: Real Data Multi-Domain Validation

**Date:** 2025-12-13
**Proposed By:** Link (Project Lead)
**Workflow:** Correct-Course
**Status:** Pending Approval

---

## Section 1: Issue Summary

### Problem Statement

Epic 6.2 (Generic Reference Data Management) completed with 268+ unit tests, but all tests used constructed mock data. The Epic 6.2 retrospective identified a critical gap: **the framework has not been validated with real production data**.

The project has implemented two domains (annuity_performance and annuity_income), but the complete end-to-end workflow (discovery → processing → writing) has not been tested with real 202510 data through the Orchestration Layer.

### Context

- **Discovery Date:** 2025-12-13 (Epic 6.2 Retrospective)
- **Trigger:** Need to validate complete multi-domain workflow before Epic 7 (Testing & Validation Infrastructure)
- **Real Data Location:** `tests/fixtures/real_data/202510/`
- **Target File:** `收集数据/数据采集/V2/【for年金机构经营分析】25年10月年金规模收入数据 1111.xlsx`

### Evidence

| Evidence Type | Details |
|---------------|---------|
| Real Data File | `【for年金机构经营分析】25年10月年金规模收入数据 1111.xlsx` |
| Expected Rows | 37,127 (validated in Epic 6.2 retro) |
| Domains to Test | annuity_performance (规模明细), annuity_income (收入明细) |
| Current Config Pattern | `*年金终稿*.xlsx` (does NOT match real file) |
| Real File Pattern | `*规模收入数据*.xlsx` |

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact Level | Description |
|------|--------------|-------------|
| Epic 6.2 | Patch Required | Configuration update needed for file discovery |
| Epic 7 | Blocked Until Fixed | Golden Dataset extraction depends on correct file discovery |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 6.2-P2 (New) | To Be Created | Real data validation story |
| 7-1 | Blocked | Depends on correct file discovery configuration |

### Artifact Conflicts

| Artifact | Conflict? | Required Change |
|----------|-----------|-----------------|
| config/data_sources.yml | Yes | Update file_patterns for both domains |
| sprint-status.yaml | Yes | Add new patch story 6.2-P2 |
| Architecture | No | No changes needed |
| PRD | No | No changes needed |

### Technical Impact

- **Code Changes:** None required - only configuration updates
- **Infrastructure:** No changes
- **Deployment:** No changes

---

## Section 3: Recommended Approach

### Selected Path: Direct Adjustment

Based on the analysis, the recommended approach is **Direct Adjustment** - modifying configuration within the existing Epic structure.

### Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | **Low** - Configuration changes only |
| Technical Risk | **Low** - File discovery framework already exists |
| Timeline Impact | **Minimal** - 1-2 days |
| Team Morale | **Positive** - Expected validation work |
| Long-term Sustainability | **Good** - Enables future real data processing |

### Alternatives Considered

| Option | Viable? | Reason |
|--------|---------|--------|
| Rollback | No | No code to rollback - configuration issue |
| MVP Scope Reduction | No | Not needed - simple fix |
| New Epic | No | Overkill for configuration change |

---

## Section 4: Detailed Change Proposals

### Change #1: Update File Discovery Patterns

**File:** `config/data_sources.yml`

**annuity_performance (lines 33-34):**
```yaml
# OLD:
file_patterns:
  - "*年金终稿*.xlsx"

# NEW:
file_patterns:
  - "*规模收入数据*.xlsx"
```

**annuity_income (lines 159-160):**
```yaml
# OLD:
file_patterns:
  - "*年金终稿*.xlsx"

# NEW:
file_patterns:
  - "*规模收入数据*.xlsx"
```

**Justification:**
- Real data file is named `【for年金机构经营分析】25年10月年金规模收入数据 1111.xlsx`
- Current pattern `*年金终稿*.xlsx` does not match
- Both domains read from same file (different sheets), so use same pattern

---

### Change #2: Add Patch Story to Sprint Status

**File:** `docs/sprint-artifacts/sprint-status.yaml`

**Addition after `epic-6.2-retrospective: completed`:**
```yaml
# Story 6.2-P2: Real Data Validation for Multi-Domain Workflow
# Added 2025-12-13 via Correct-Course workflow
# Validates complete workflow (discovery → processing → writing) with real 202510 data
# Reference: docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-13-real-data-validation.md
6.2-p2-real-data-multi-domain-validation: backlog
```

**Justification:**
- Formal tracking of real data validation work
- Patch story under Epic 6.2, to be completed before Epic 7
- Validates Orchestration Layer can correctly orchestrate multi-domain cleansing workflow

---

## Section 5: Implementation Handoff

### Change Scope Classification: Minor

This change can be implemented directly by the development team without requiring backlog reorganization or architectural review.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| Developer | Implement configuration changes and run validation |
| QA | Verify multi-domain workflow with real data |

### Implementation Tasks

1. **Update config/data_sources.yml**
   - Change `file_patterns` for annuity_performance domain
   - Change `file_patterns` for annuity_income domain

2. **Update sprint-status.yaml**
   - Add story `6.2-p2-real-data-multi-domain-validation`

3. **Execute Validation**
   - Run CLI with `--period 202510` for both domains
   - Verify file discovery finds correct file
   - Verify both sheets are processed correctly
   - Compare output with expected row counts

4. **Document Results**
   - Record validation results in story file
   - Update retrospective if new issues found

### Success Criteria

| Criteria | Measurement |
|----------|-------------|
| File Discovery | Both domains discover `*规模收入数据*.xlsx` file |
| Sheet Selection | annuity_performance reads 规模明细, annuity_income reads 收入明细 |
| Row Processing | Expected row counts match (37,127 for 规模明细) |
| Database Write | Data successfully written to business schema |
| No Errors | Pipeline completes without errors |

---

## Section 6: Critical Discovery During Validation

### Architecture Mismatch Identified

During validation execution, a significant architecture mismatch was discovered:

| Component | Expected Schema | Actual Schema |
|-----------|-----------------|---------------|
| `DataSourceConnector` (legacy) | `pattern`, `select`, `table`, `pk` | - |
| `config/data_sources.yml` | - | `base_path`, `file_patterns`, `version_strategy`, `output` |
| `FileDiscoveryService` (Epic 3) | - | `base_path`, `file_patterns`, `version_strategy`, `output` |

### Root Cause

The orchestration layer (`discover_files_op`) uses `DataSourceConnector` which expects the legacy schema format, but the configuration file has been migrated to Epic 3 schema. This is a symptom of **incremental migration** where new architecture was introduced but not all consumers were updated.

### Impact

- **Blocking**: Cannot run multi-domain validation until architecture is unified
- **Technical Debt**: Legacy and new components coexist, causing confusion and maintenance burden

---

## Section 7: Configuration Conflict Discovery Methodology

### How We Found These Issues

During the validation attempt, we systematically discovered configuration conflicts through the following process:

#### Step 1: Execute and Observe Errors

```bash
WDH_DATA_BASE_DIR="tests/fixtures/real_data/202510/收集数据/数据采集/V2" \
PYTHONPATH=src uv run python -m work_data_hub.orchestration.jobs \
--domain annuity_performance --plan-only
```

**Error Pattern**: `Domain 'annuity_performance' missing required key: pattern`

#### Step 2: Trace Error to Source

| Error Message | Source File | Line |
|---------------|-------------|------|
| `missing required key: pattern` | `file_connector.py` | 210 |
| `DataSourcesConfig validation failed` | `data_source_schema.py` | 116 |

#### Step 3: Identify Schema Mismatch

**Legacy Schema (DomainConfig)**:
```python
class DomainConfig(BaseModel):
    pattern: str  # Required
    select: Literal[...]  # Required
    table: str  # Required
    pk: List[str]  # Required
```

**Epic 3 Schema (DomainConfigV2)**:
```python
class DomainConfigV2(BaseModel):
    base_path: str  # Required
    file_patterns: List[str]  # Required
    version_strategy: str  # Required
    output: OutputConfig  # Required
```

#### Step 4: Map Component Dependencies

```
config/data_sources.yml (Epic 3 Schema)
    │
    ├── validate_data_sources_config() → DataSourcesConfig (Legacy) ❌ MISMATCH
    │   └── Fixed: Now uses DataSourceConfigV2 ✅
    │
    ├── DataSourceConnector._load_config() → Legacy Schema ❌ MISMATCH
    │   └── Needs: Update to support Epic 3 schema
    │
    └── FileDiscoveryService → DomainConfigV2 (Epic 3) ✅ CORRECT
```

### Configuration Conflict Detection Checklist

Based on this experience, here is a reusable checklist for detecting configuration conflicts:

```markdown
## Configuration Conflict Detection Checklist

### 1. Schema Version Audit
- [ ] List all Pydantic models that validate configuration files
- [ ] Identify which schema version each model expects
- [ ] Compare with actual configuration file structure
- [ ] Document mismatches

### 2. Consumer Dependency Mapping
- [ ] Identify all components that read the configuration file
- [ ] For each consumer, determine which schema it expects
- [ ] Create dependency graph showing config → consumer relationships
- [ ] Highlight consumers using outdated schema

### 3. Path Reference Audit
- [ ] Search codebase for hardcoded config paths
- [ ] Verify all paths point to current config location
- [ ] Check for duplicate config files in different locations
- [ ] Update or remove stale references

### 4. Runtime Validation
- [ ] Execute each major workflow with --plan-only
- [ ] Capture and categorize all validation errors
- [ ] Trace errors to source components
- [ ] Document required fixes

### 5. Integration Point Verification
- [ ] Test CLI entry points with real parameters
- [ ] Verify environment variable handling
- [ ] Check default value consistency across components
- [ ] Validate error messages are actionable
```

### Discovered Issues Summary

| Issue Type | Count | Examples |
|------------|-------|----------|
| Hardcoded Config Paths | 3 | `settings.py`, `data_source_schema.py` (2 locations) |
| Schema Mismatch | 2 | `validate_data_sources_config()`, `DataSourceConnector` |
| Missing CLI Parameters | 1 | `--period` for YYYYMM template |
| Stale Op Configuration | 1 | `backfill_refs_op` → `generic_backfill_refs_op` |

---

## Section 8: Revised Story Structure

Given the scope of changes discovered, the work is split into two independent stories:

### Story 6.2-P2: Real Data Validation Configuration

**Scope**: Configuration updates only (already completed)

| Task | Status |
|------|--------|
| Update file_patterns in data_sources.yml | ✅ Done |
| Update config path references | ✅ Done |
| Update schema validation to use V2 | ✅ Done |
| Update backfill op configuration | ✅ Done |

**Effort**: 0.5 days (Completed)

### Story 6.2-P3: Orchestration Layer Architecture Unification

**Scope**: Unify orchestration layer to use Epic 3 FileDiscoveryService

| Task | Effort |
|------|--------|
| Update `discover_files_op` to use `FileDiscoveryService` | 1 day |
| Add `--period` CLI parameter for YYYYMM template | 0.5 day |
| Update job definitions for multi-domain support | 0.5 day |
| Remove or deprecate `DataSourceConnector` | 0.5 day |
| Integration testing with real data | 0.5 day |

**Total Effort**: 3 days

**Dependencies**: Story 6.2-P2 (completed)

**Acceptance Criteria**:
1. CLI supports `--period 202510` parameter
2. Both domains discover files from same source
3. Multi-domain workflow executes successfully
4. Legacy `DataSourceConnector` marked as deprecated

---

## Approval

- [ ] **Project Lead (Link):** Approve this Sprint Change Proposal
- [ ] **Developer:** Acknowledge implementation tasks

---

**Document Generated:** 2025-12-13
**Updated:** 2025-12-13 (Added Section 6 - Critical Discovery)
**Workflow:** BMM Correct-Course
**Reference:** Epic 6.2 Retrospective (2025-12-13)
