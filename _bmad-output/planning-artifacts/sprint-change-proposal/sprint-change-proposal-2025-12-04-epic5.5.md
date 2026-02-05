# Sprint Change Proposal: Epic 5.5 - Pipeline Architecture Validation

**Date:** 2025-12-04
**Proposed By:** Link (via Correct-Course Workflow)
**Status:** Pending Approval
**Change Scope:** Moderate (New Epic insertion, backlog reorganization)

---

## Section 1: Issue Summary

### Problem Statement

Epic 5 has successfully established the Infrastructure Layer and validated its feasibility through the `annuity_performance` domain. However, a single domain implementation is insufficient to prove the architecture's generality and reusability. Before committing to Epic 6 (Company Enrichment Service) and subsequent batch domain migrations, we need additional validation.

### Context

- **Discovery Point:** Post-Epic 5 completion review
- **Trigger:** Strategic decision to validate architecture before scaling
- **Evidence:**
  - `AnnuityIncomeCleaner` shares ~70% cleansing logic with `AnnuityPerformanceCleaner`
  - High code reuse potential identified but unverified
  - No established standard for documenting legacy cleansing rules

### Change Trigger Type

- [ ] Technical limitation discovered during implementation
- [x] New requirement emerged (architecture validation need)
- [ ] Misunderstanding of original requirements
- [ ] Strategic pivot or market change
- [ ] Failed approach requiring different solution

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| Epic 5 | None | Already completed, no changes needed |
| **Epic 5.5** | **New** | Insert new validation epic between Epic 5 and Epic 6 |
| Epic 6 | Delayed Start | Blocked until Epic 5.5 completes |
| Epic 7 | No Direct Impact | May benefit from multi-domain testing experience |

### Story Impact

**New Stories Required:**

| Story ID | Title | Description |
|----------|-------|-------------|
| 5.5.1 | Legacy Cleansing Rules Documentation | Document AnnuityIncomeCleaner rules using new template |
| 5.5.2 | AnnuityIncome Domain Implementation | Implement domain using Infrastructure Layer |
| 5.5.3 | Legacy Parity Validation | Validate 100% parity with legacy output |
| 5.5.4 | Multi-Domain Integration Test & Optimization | Integration test for both domains + optimization recommendations |

### Artifact Conflicts

| Artifact | Impact | Action Required |
|----------|--------|-----------------|
| `docs/epics/index.md` | Update | Add Epic 5.5 entry |
| `docs/sprint-artifacts/sprint-status.yaml` | Update | Add Epic 5.5 and stories |
| `docs/brownfield-architecture.md` | Update | Add annuity_income domain description |
| `config/data_sources.yml` | Update | Add annuity_income data source configuration |

### Technical Impact

| Area | Impact | Details |
|------|--------|---------|
| New Domain | Addition | `src/work_data_hub/domain/annuity_income/` (6-file standard) |
| Data Models | Addition | Pydantic models for AnnuityIncome |
| Integration Tests | Extension | Multi-domain parallel processing validation |
| Documentation | New Structure | `docs/templates/` and `docs/cleansing-rules/` directories |

---

## Section 3: Recommended Approach

### Selected Path: Direct Adjustment

**Rationale:**
1. Architecture is already established and proven with one domain
2. Low risk - using validated patterns from Epic 5
3. Aligns with "validate before batch migration" strategy
4. Outputs (cleansing documentation, optimization recommendations) directly benefit Epic 6

### Effort Estimate

| Item | Estimate |
|------|----------|
| Story 5.5.1 | 0.5 day |
| Story 5.5.2 | 1-2 days |
| Story 5.5.3 | 0.5 day |
| Story 5.5.4 | 1 day |
| **Total** | **3-5 days** |

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Architecture issues discovered | Low | Epic 5.5 scope allows for fixes before Epic 6 |
| Parity validation failures | Medium | Follow established `legacy-parity-validation.md` process |
| Integration test complexity | Low | Build on existing test infrastructure |

### Timeline Impact

- Epic 6 start delayed by ~1 week
- This delay is justified by reduced risk in subsequent batch migrations

---

## Section 4: Detailed Change Proposals

### 4.1 New Epic File

**File:** `docs/epics/epic-5.5-pipeline-architecture-validation.md`
**Action:** Create new file

```markdown
# Epic 5.5: Pipeline Architecture Validation (AnnuityIncome Domain)

## Overview

**Goal:** Validate the Infrastructure Layer established in Epic 5 by implementing a second domain (AnnuityIncome), ensuring architecture generality and establishing cleansing documentation standards.

**Blocking:** Epic 6 (Company Enrichment Service)

**Estimated Effort:** 3-5 days

## Background

Epic 5 successfully established the Infrastructure Layer with:
- 6-file domain standard
- Reusable infrastructure components (CompanyIdResolver, CleansingRegistry, etc.)
- Lightweight service orchestrator pattern

However, validation with a single domain is insufficient. AnnuityIncome shares ~70% cleansing logic with AnnuityPerformance, making it an ideal candidate for:
1. Validating architecture generality
2. Identifying code reuse opportunities
3. Establishing cleansing documentation standards

## Stories

### Story 5.5.1: Legacy Cleansing Rules Documentation
- **Goal:** Document all cleansing rules from `AnnuityIncomeCleaner` using the new template
- **Output:** `docs/cleansing-rules/annuity-income.md`
- **Acceptance Criteria:**
  - All column mappings documented
  - All cleansing rules catalogued with rule type and logic
  - Company ID resolution strategy documented
  - Validation rules specified

### Story 5.5.2: AnnuityIncome Domain Implementation
- **Goal:** Implement AnnuityIncome domain using Infrastructure Layer
- **Output:** `src/work_data_hub/domain/annuity_income/` (6-file standard)
- **Acceptance Criteria:**
  - Domain follows 6-file standard (models, schemas, transforms, steps, config, service)
  - Uses infrastructure components (CompanyIdResolver, CleansingRegistry)
  - Configuration added to `data_sources.yml`
  - Unit tests with >85% coverage

### Story 5.5.3: Legacy Parity Validation
- **Goal:** Validate 100% parity with legacy `AnnuityIncomeCleaner` output
- **Output:** Parity validation report
- **Acceptance Criteria:**
  - Follow `docs/runbooks/legacy-parity-validation.md` process
  - 100% match rate achieved
  - Any intentional differences documented
  - Validation artifacts saved to `tests/fixtures/validation_results/`

### Story 5.5.4: Multi-Domain Integration Test & Optimization
- **Goal:** Validate multi-domain parallel processing and document optimization opportunities
- **Output:** Integration tests + `docs/sprint-artifacts/epic-5.5-optimization-recommendations.md`
- **Acceptance Criteria:**
  - Integration test scans and processes both `annuity_performance` and `annuity_income`
  - Domain isolation verified (no data cross-contamination)
  - Performance baseline recorded
  - Code reuse opportunities identified and documented
  - Optimization recommendations for Epic 6 produced

## Success Criteria

1. ✅ AnnuityIncome domain passes 100% parity validation
2. ✅ Integration test correctly scans and processes both domains in single run
3. ✅ Cleansing rules documentation standard established
4. ✅ Architecture optimization recommendations documented

## Dependencies

- Epic 5 completion (done)
- Legacy `AnnuityIncomeCleaner` code (available)
- Real test data for parity validation

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Architecture issues discovered | Fix within Epic 5.5 scope before Epic 6 |
| Parity validation failures | Iterative debugging using established process |
| Scope creep | Strict focus on validation, defer optimizations to Epic 6 |
```

### 4.2 Sprint Status Update

**File:** `docs/sprint-artifacts/sprint-status.yaml`
**Action:** Edit - Insert after `epic-5-retrospective: completed`

```yaml
  # Epic 5.5: Pipeline Architecture Validation (AnnuityIncome Domain)
  # Added 2025-12-04 via Correct-Course workflow
  # BLOCKING: Must complete before Epic 6 to validate architecture generality
  # Validates Infrastructure Layer with second domain, establishes cleansing documentation standard
  epic-5.5: backlog
  5.5-1-legacy-cleansing-rules-documentation: backlog
  5.5-2-annuity-income-domain-implementation: backlog
  5.5-3-legacy-parity-validation: backlog
  5.5-4-multi-domain-integration-test-and-optimization: backlog
  epic-5.5-retrospective: optional
```

### 4.3 Epic Index Update

**File:** `docs/epics/index.md`
**Action:** Edit - Insert Epic 5.5 entry after Epic 5, before Epic 6

```markdown
| Epic 5.5 | Pipeline Architecture Validation | Validate Infrastructure Layer with AnnuityIncome domain, establish cleansing documentation standard, multi-domain integration testing | Blocks Epic 6 |
```

### 4.4 New Documentation Structure

**Action:** Create new directories and files

**Directory:** `docs/templates/`
**File:** `docs/templates/cleansing-rules-template.md`

```markdown
# Legacy Cleansing Rules Documentation Template

## Purpose

Standard template for documenting legacy cleansing rules before domain migration. Use this template to create a comprehensive reference for Pipeline configuration.

---

## 1. Domain Overview

| Item | Value |
|------|-------|
| Legacy Cleaner Class | `{ClassName}` |
| Source File | `legacy/annuity_hub/data_handler/data_cleaner.py` |
| Excel Sheet Name | `{sheet_name}` |
| Target Database Table | `{schema}.{table}` |

---

## 2. Column Mappings

| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | | | | |

---

## 3. Cleansing Rules

| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | | mapping | | | |
| CR-002 | | date_parse | | | |
| CR-003 | | default_value | | | |

### Rule Types Reference
- `mapping`: Value mapping using lookup table
- `date_parse`: Date format standardization
- `default_value`: Fill missing values with default
- `regex_replace`: Pattern-based string replacement
- `conditional`: Conditional logic based on other fields
- `strip_prefix`: Remove prefix from string
- `normalize`: Text normalization (trim, case, etc.)

---

## 4. Company ID Resolution Strategy

### Priority Order

| Priority | Source | Mapping Table | Fallback |
|----------|--------|---------------|----------|
| 1 | | | |
| 2 | | | |

### Default Value Handling
- Condition:
- Default Value:

---

## 5. Validation Rules

### Required Fields
- [ ] Field 1
- [ ] Field 2

### Data Type Constraints
| Field | Expected Type | Constraint |
|-------|---------------|------------|

### Business Rules
| Rule | Description | Validation Logic |
|------|-------------|------------------|

---

## 6. Special Processing Notes

{Document any special cases, edge cases, or legacy quirks that need attention}

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| | | Initial documentation |
```

**Directory:** `docs/cleansing-rules/`
**File:** `docs/cleansing-rules/index.md`

```markdown
# Cleansing Rules Documentation Index

This directory contains documented cleansing rules for each domain migrated from the legacy system.

## Purpose

- Provide reference for Pipeline configuration
- Enable parity validation against legacy behavior
- Capture tribal knowledge before it's lost

## Template

Use [cleansing-rules-template.md](../templates/cleansing-rules-template.md) when documenting a new domain.

## Documented Domains

| Domain | Status | Document | Legacy Class |
|--------|--------|----------|--------------|
| annuity_performance | ✅ Migrated (Epic 4-5) | (implicit in code) | `AnnuityPerformanceCleaner` |
| annuity_income | 📝 Pending (Epic 5.5) | [annuity-income.md](./annuity-income.md) | `AnnuityIncomeCleaner` |

## Pending Domains (Epic 6+)

- `GroupRetirementCleaner` - 团养缴费
- `HealthCoverageCleaner` - 企康缴费
- `IFECCleaner` - 提费扩面
- `APMACleaner` - 手工调整
- ... (see `legacy/annuity_hub/data_handler/data_cleaner.py` for full list)
```

---

## Section 5: Implementation Handoff

### Change Scope Classification

**Classification:** Moderate

**Rationale:**
- New Epic insertion requires backlog reorganization
- Multiple artifacts need updates
- No fundamental architecture changes needed

### Handoff Plan

| Role | Responsibility |
|------|----------------|
| **Scrum Master (SM)** | Create Epic 5.5 file, update sprint-status.yaml, create story files |
| **Developer (Dev)** | Implement stories 5.5.1 through 5.5.4 |
| **Tech Lead** | Review architecture optimization recommendations |

### Deliverables Checklist

- [ ] `docs/epics/epic-5.5-pipeline-architecture-validation.md` created
- [ ] `docs/sprint-artifacts/sprint-status.yaml` updated
- [ ] `docs/epics/index.md` updated
- [ ] `docs/templates/cleansing-rules-template.md` created
- [ ] `docs/cleansing-rules/index.md` created
- [ ] Story files created in `docs/sprint-artifacts/stories/`

### Success Criteria

1. Epic 5.5 formally registered in project tracking
2. All 4 stories completed with acceptance criteria met
3. Multi-domain integration test passing
4. Architecture optimization recommendations documented
5. Ready to proceed to Epic 6 with validated architecture

---

## Approval

- [x] **User Approval:** Approved 2025-12-04
- [x] **Implementation Started:** 2025-12-04

## Implementation Log

| Item | Status | Notes |
|------|--------|-------|
| Epic 5.5 file created | ✅ Done | `docs/epics/epic-5.5-pipeline-architecture-validation.md` |
| Sprint status updated | ✅ Done | Added Epic 5.5 and 4 stories |
| Epic index updated | ✅ Done | Added Epic 5.5 entry |
| Templates directory created | ✅ Done | `docs/templates/` |
| Cleansing rules directory created | ✅ Done | `docs/cleansing-rules/` |
| Cleansing rules template | ✅ Done | `docs/templates/cleansing-rules-template.md` |
| Cleansing rules index | ✅ Done | `docs/cleansing-rules/index.md` |

---

*Generated by Correct-Course Workflow on 2025-12-04*
