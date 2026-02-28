---
stepsCompleted: ['step-01', 'step-02', 'step-03', 'step-04', 'step-05']
lastStep: 'step-05-generate-output'
lastSaved: '2026-02-27'
workflowType: 'testarch-test-design'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd/prd-summary.md'
  - '_bmad-output/planning-artifacts/brownfield-architecture.md'
  - '_bmad-output/planning-artifacts/architecture-boundaries.md'
  - '_bmad-output/planning-artifacts/architecture/integration-architecture.md'
---

# Test Design for Architecture: WorkDataHub

**Purpose:** Architectural concerns, testability gaps, and NFR requirements for review by Architecture/Dev teams. Serves as a contract between QA and Engineering on what must be addressed before test development begins.

**Date:** 2026-02-27
**Author:** TEA Master Test Architect
**Status:** Architecture Review Pending
**Project:** WorkDataHub
**PRD Reference:** `_bmad-output/planning-artifacts/prd/prd-summary.md`
**ADR Reference:** `_bmad-output/planning-artifacts/brownfield-architecture.md`

---

## Executive Summary

**Scope:** System-level test design covering all 8 domains of the WorkDataHub data processing platform — a brownfield modernization of legacy Excel/MySQL workflows into a Clean Architecture Python pipeline system.

**Business Context** (from PRD):

- **Revenue/Impact:** Internal data platform serving annuity performance, trustee reporting, customer MDM, and company enrichment for the entire organization
- **Problem:** Legacy system relies on manual Excel processing, MySQL stored procedures, and undocumented business rules — fragile, error-prone, and unscalable
- **GA Launch:** Phased delivery; Epics 1–7.6 complete, Epic 8 (Testing & Validation) in backlog

**Architecture** (from Brownfield ADR):

- **Key Decision 1:** Clean Architecture with strict dependency direction (domain ← io ← orchestration)
- **Key Decision 2:** Medallion data pattern (Bronze → Silver → Gold) with Pydantic v2 + Pandera validation
- **Key Decision 3:** Stack: Python 3.10+, Dagster orchestration, SQLAlchemy+Alembic, PostgreSQL

**Expected Scale** (from ADR):

- 8 active domains, ~50K rows per monthly batch, <30 min total processing time
- Dual-DB: PostgreSQL (new) + Legacy MySQL (read-only migration source)

**Risk Summary:**

- **Total risks**: 10
- **High-priority (≥6)**: 5 risks requiring immediate mitigation
- **Test effort**: ~42 test scenarios (~68–105 hours for 1 engineer)

---

## Quick Guide

### 🚨 BLOCKERS - Team Must Decide (Can't Proceed Without)

**Pre-Implementation Critical Path** - These MUST be completed before QA can write integration tests:

1. **R-01: CI PostgreSQL Service Container** - CI pipeline has zero database test coverage; all `@pytest.mark.postgres` tests are skipped (recommended owner: Dev/Ops)
2. **R-03: Golden Dataset Extraction** - Legacy comparison tests require production data that doesn't exist in CI; regression detection is impossible without it (recommended owner: Dev/QA)
3. **R-04: Customer MDM SCD2 Test Coverage** - 19 stories of complex business logic (status evaluation, ratchet rules, annual cutover) with minimal integration tests (recommended owner: Dev)

**What we need from team:** Complete these 3 items pre-implementation or test development is blocked.

---

### ⚠️ HIGH PRIORITY - Team Should Validate (We Provide Recommendation, You Approve)

1. **R-02: EQC API Mock Layer** - StubProvider exists but incomplete; need full mock coverage for CI-safe enrichment testing (implementation phase, owner: Dev)
2. **R-05: Alembic Migration Rollback Tests** - 13 active migrations with no downgrade verification; production migration failure has no tested recovery path (implementation phase, owner: Dev/Ops)
3. **R-06: Multi-Domain Parallel Execution** - No tests verify resource contention when multiple domains run concurrently (implementation phase, owner: Dev)

**What we need from team:** Review recommendations and approve (or suggest changes).

---

### 📋 INFO ONLY - Solutions Provided (Review, No Decisions Needed)

1. **Test strategy**: 70% Unit / 20% Integration / 10% E2E (Python backend, no frontend UI)
2. **Tooling**: pytest + pytest-cov + pytest-postgresql, Ruff + MyPy for static analysis
3. **Tiered CI/CD**: PR (<10 min) / Nightly (<25 min) / Weekly (<45 min) / Release Gate (<60 min)
4. **Coverage**: ~42 test scenarios prioritized P0-P3 with risk-based classification
5. **Quality gates**: P0=100%, P1≥95%, coverage≥80%, zero CRITICAL risks at release

**What we need from team:** Just review and acknowledge (we already have the solution).

---

## For Architects and Devs - Open Topics 👷

### Risk Assessment

**Total risks identified**: 10 (5 high-priority score ≥6, 4 medium, 1 low)

#### High-Priority Risks (Score ≥6) - IMMEDIATE ATTENTION

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner | Timeline |
|---|---|---|---|---|---|---|---|---|
| **R-01** | **TECH** | CI has zero PostgreSQL test coverage — all `@pytest.mark.postgres` tests skipped | 3 | 3 | **9** | Add PostgreSQL service container to CI workflow | Dev/Ops | Pre-implementation |
| **R-03** | **DATA** | Legacy comparison has no golden dataset — regression detection impossible in CI | 3 | 3 | **9** | Extract anonymized golden dataset; version control or CI artifact | Dev/QA | Pre-implementation |
| **R-04** | **BUS** | Customer MDM SCD2 logic (19 stories) has minimal integration test coverage | 2 | 3 | **6** | Add SCD2 state machine, ratchet rule, and annual cutover tests | Dev | Implementation |
| **R-02** | **TECH** | EQC API token expires in 30 min — enrichment flow untestable in CI | 3 | 2 | **6** | Complete StubProvider mock layer for all resolution strategies | Dev | Implementation |
| **R-05** | **OPS** | Alembic migration rollback (downgrade) never verified — no recovery path | 2 | 3 | **6** | Add upgrade/downgrade round-trip tests for all 13 migrations | Dev/Ops | Implementation |

#### Medium-Priority Risks (Score 3-5)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|---|
| R-06 | PERF | Multi-domain parallel execution untested — potential resource contention | 2 | 2 | 4 | Add concurrent domain execution integration tests | Dev |
| R-07 | SEC | `.wdh_env` secrets managed manually — no rotation or audit trail | 2 | 2 | 4 | Document secret rotation; verify no leakage to logs | Ops |
| R-08 | DATA | PowerBI Gold layer output has no automated schema validation | 2 | 2 | 4 | Add Gold layer Pandera schema assertions | QA |
| R-10 | DATA | Chinese column names in SQL generation may cause encoding issues | 2 | 2 | 4 | Expand SQL generation unit tests with CJK identifiers | Dev |

#### Low-Priority Risks (Score 1-2)

| Risk ID | Category | Description | Probability | Impact | Score | Action |
|---|---|---|---|---|---|---|
| R-09 | TECH | Dagster definitions dormant — future activation may break compatibility | 1 | 2 | 2 | Monitor; periodic smoke test |

#### Risk Category Legend

- **TECH**: Technical/Architecture (flaws, integration, scalability)
- **SEC**: Security (access controls, auth, data exposure)
- **PERF**: Performance (SLA violations, degradation, resource limits)
- **DATA**: Data Integrity (loss, corruption, inconsistency)
- **BUS**: Business Impact (UX harm, logic errors, revenue)
- **OPS**: Operations (deployment, config, monitoring)

---

### Testability Concerns and Architectural Gaps

**🚨 ACTIONABLE CONCERNS - Architecture Team Must Address**

#### 1. Blockers to Fast Feedback (WHAT WE NEED FROM ARCHITECTURE)

| Concern | Impact | What Architecture Must Provide | Owner | Timeline |
|---|---|---|---|---|
| **No PostgreSQL in CI** | All DB interaction tests skipped; warehouse loader, migrations, MDM untested | PostgreSQL service container in GitHub Actions workflow | Dev/Ops | Pre-implementation |
| **No golden dataset** | Legacy comparison impossible in clean environments; regression undetectable | Anonymized golden dataset extraction script + CI artifact storage | Dev/QA | Pre-implementation |
| **EQC API not mockable end-to-end** | Company enrichment integration tests cannot run in CI (browser + CAPTCHA) | Complete StubProvider covering all 5 resolution strategies | Dev | Pre-implementation |

#### 2. Architectural Improvements Needed (WHAT SHOULD BE CHANGED)

1. **Shared conftest.py consolidation**
   - **Current problem**: 204 fixtures scattered across 69 test files; only 6 conftest.py files
   - **Required change**: Extract common fixtures (DB sessions, test data factories, pipeline builders) into shared conftest hierarchy
   - **Impact if not fixed**: Duplicate setup logic, inconsistent test data, harder maintenance
   - **Owner**: Dev
   - **Timeline**: Implementation phase

2. **Customer MDM integration test infrastructure**
   - **Current problem**: Epic 7.6 has 19 stories with complex SCD2/ratchet/cutover logic but minimal integration tests
   - **Required change**: Add conftest.py with MDM-specific fixtures (customer lifecycle states, temporal test data)
   - **Impact if not fixed**: Business-critical status evaluation logic unverified at integration level
   - **Owner**: Dev
   - **Timeline**: Implementation phase

---

### Testability Assessment Summary

**📊 CURRENT STATE - FYI**

#### What Works Well

- ✅ **Clean Architecture enforcement** — Ruff TID251 rule enforces dependency direction in CI; domain logic is pure and unit-testable
- ✅ **Multi-layer test structure** — Unit / Integration / E2E / Performance directories established with 204 pytest fixtures
- ✅ **Pydantic v2 strict typing** — All domain models use strict validation; model tests cover valid/invalid inputs
- ✅ **Configuration-driven design** — `data_sources.yml` + Pydantic Settings enable injectable, overridable config for tests
- ✅ **`--plan-only` mode** — Pipeline validation without side effects; ideal for fast CI feedback

#### Accepted Trade-offs (No Action Required)

For WorkDataHub Phase 1, the following trade-offs are acceptable:

- **Dagster orchestration dormant** — CLI-driven execution is sufficient for current scale; Dagster definitions maintained but not actively tested
- **No browser-based E2E for EQC** — StubProvider covers CI needs; real EQC testing is manual/on-demand only
- **Performance benchmarks are relative, not absolute** — No production baseline yet; benchmarks track regression between commits only

---

### Risk Mitigation Plans (High-Priority Risks ≥6)

**Purpose**: Detailed mitigation strategies for all 5 high-priority risks (score ≥6). These risks MUST be addressed before Epic 8 completion.

#### R-01: CI Has Zero PostgreSQL Test Coverage (Score: 9) - CRITICAL

**Mitigation Strategy:**

1. Add PostgreSQL 15 service container to GitHub Actions CI workflow
2. Enable `@pytest.mark.postgres` tests in CI (currently excluded via `-m "not postgres"`)
3. Add `pytest-postgresql` fixture for ephemeral test databases with auto-cleanup

**Owner:** Dev/Ops
**Timeline:** Pre-implementation (blocks all DB-related test development)
**Status:** Planned
**Verification:** CI pipeline runs postgres-marked tests and reports coverage

#### R-03: Legacy Comparison Has No Golden Dataset (Score: 9) - CRITICAL

**Mitigation Strategy:**

1. Extract anonymized golden dataset from current production Legacy MySQL output
2. Store as versioned CSV/Parquet fixtures in `tests/fixtures/golden/` or as CI artifact
3. Automate comparison: new pipeline output vs golden dataset with tolerance thresholds

**Owner:** Dev/QA
**Timeline:** Pre-implementation (blocks regression detection)
**Status:** Planned (aligned with Epic 8 Story 8-1)
**Verification:** `test_pipeline_vs_legacy.py` passes in clean CI environment

#### R-04: Customer MDM SCD2 Logic Undertested (Score: 6) - HIGH

**Mitigation Strategy:**

1. Add integration tests for SCD2 state transitions (active→churned→reactivated)
2. Test ratchet rule enforcement (status cannot downgrade without explicit override)
3. Test annual cutover logic with temporal boundary conditions

**Owner:** Dev
**Timeline:** Implementation phase
**Status:** Planned
**Verification:** All MDM status evaluation paths covered with DB-backed integration tests

#### R-02: EQC API Token Expires in 30 Min (Score: 6) - HIGH

**Mitigation Strategy:**

1. Complete StubProvider to cover all 5 resolution strategies (config → internal mapping → name index → API → temp ID)
2. Add mock response fixtures for EQC API endpoints
3. Ensure CI always uses StubProvider; real EQC testing is manual/on-demand only

**Owner:** Dev
**Timeline:** Implementation phase
**Status:** Partially implemented (StubProvider exists but incomplete)
**Verification:** All enrichment integration tests pass with StubProvider in CI

#### R-05: Alembic Migration Rollback Never Verified (Score: 6) - HIGH

**Mitigation Strategy:**

1. Add upgrade/downgrade round-trip test for each of the 13 active migrations
2. Verify data integrity after downgrade (no data loss on rollback)
3. Document manual rollback procedure for production emergencies

**Owner:** Dev/Ops
**Timeline:** Implementation phase
**Status:** Planned
**Verification:** `test_migration_roundtrip.py` passes upgrade→downgrade→upgrade for all revisions

---

### Assumptions and Dependencies

#### Assumptions

1. PostgreSQL 15+ will be available as CI service container (GitHub Actions supports this natively)
2. Legacy MySQL remains read-only; no new writes to legacy schema
3. Golden dataset can be extracted and anonymized without violating data policies

#### Dependencies

1. **CI PostgreSQL service** — Required before any DB integration test development
2. **Golden dataset extraction** — Required before legacy comparison automation
3. **StubProvider completion** — Required before enrichment integration tests

#### Risks to Plan

- **Risk**: Golden dataset may contain sensitive customer data that cannot be anonymized
  - **Impact**: Legacy comparison tests remain manual-only
  - **Contingency**: Use synthetic data generators that mimic production distributions

---

**End of Architecture Document**

**Next Steps for Architecture Team:**

1. Review Quick Guide (🚨/⚠️/📋) and prioritize blockers
2. Assign owners and timelines for high-priority risks (≥6)
3. Validate assumptions and dependencies
4. Provide feedback to QA on testability gaps
