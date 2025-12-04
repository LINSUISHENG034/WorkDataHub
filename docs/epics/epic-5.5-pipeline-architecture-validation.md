# Epic 5.5: Pipeline Architecture Validation (AnnuityIncome Domain)

## Overview

**Goal:** Validate the Infrastructure Layer established in Epic 5 by implementing a second domain (AnnuityIncome), ensuring architecture generality and establishing cleansing documentation standards.

**Status:** Backlog
**Blocking:** Epic 6 (Company Enrichment Service)
**Estimated Effort:** 3-5 days
**Added:** 2025-12-04 via Correct-Course Workflow

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

**Goal:** Document all cleansing rules from `AnnuityIncomeCleaner` using the new template

**Output:** `docs/cleansing-rules/annuity-income.md`

**Acceptance Criteria:**
- [ ] All column mappings documented
- [ ] All cleansing rules catalogued with rule type and logic
- [ ] Company ID resolution strategy documented
- [ ] Validation rules specified

---

### Story 5.5.2: AnnuityIncome Domain Implementation

**Goal:** Implement AnnuityIncome domain using Infrastructure Layer

**Output:** `src/work_data_hub/domain/annuity_income/` (6-file standard)

**Acceptance Criteria:**
- [ ] Domain follows 6-file standard (models, schemas, transforms, steps, config, service)
- [ ] Uses infrastructure components (CompanyIdResolver, CleansingRegistry)
- [ ] Configuration added to `data_sources.yml`
- [ ] Unit tests with >85% coverage

---

### Story 5.5.3: Legacy Parity Validation

**Goal:** Validate 100% parity with legacy `AnnuityIncomeCleaner` output

**Output:** Parity validation report

**Acceptance Criteria:**
- [ ] Follow `docs/runbooks/legacy-parity-validation.md` process
- [ ] 100% match rate achieved
- [ ] Any intentional differences documented
- [ ] Validation artifacts saved to `tests/fixtures/validation_results/`

---

### Story 5.5.4: Multi-Domain Integration Test & Optimization

**Goal:** Validate multi-domain parallel processing and document optimization opportunities

**Output:** Integration tests + `docs/sprint-artifacts/epic-5.5-optimization-recommendations.md`

**Acceptance Criteria:**
- [ ] Integration test scans and processes both `annuity_performance` and `annuity_income`
- [ ] Domain isolation verified (no data cross-contamination)
- [ ] Performance baseline recorded
- [ ] Code reuse opportunities identified and documented
- [ ] Optimization recommendations for Epic 6 produced

---

## Success Criteria

1. AnnuityIncome domain passes 100% parity validation
2. Integration test correctly scans and processes both domains in single run
3. Cleansing rules documentation standard established
4. Architecture optimization recommendations documented

## Dependencies

- Epic 5 completion (done)
- Legacy `AnnuityIncomeCleaner` code (available at `legacy/annuity_hub/data_handler/data_cleaner.py:237-274`)
- Real test data for parity validation

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Architecture issues discovered | Fix within Epic 5.5 scope before Epic 6 |
| Parity validation failures | Iterative debugging using established process |
| Scope creep | Strict focus on validation, defer optimizations to Epic 6 |

## References

- [Sprint Change Proposal](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-04-epic5.5.md)
- [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md)
- [Cleansing Rules Template](../templates/cleansing-rules-template.md)
- [Epic 5 Tech Spec](../sprint-artifacts/tech-spec-epic-5-infrastructure-layer.md)
