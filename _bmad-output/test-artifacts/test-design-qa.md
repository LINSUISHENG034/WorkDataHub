---
stepsCompleted: ['step-01', 'step-02', 'step-03', 'step-04', 'step-05']
lastStep: 'step-05-generate-output'
lastSaved: '2026-02-27'
workflowType: 'testarch-test-design'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd/prd-summary.md'
  - '_bmad-output/planning-artifacts/brownfield-architecture.md'
---

# Test Design for QA: WorkDataHub

**Purpose:** Test execution recipe for QA team. Defines what to test, how to test it, and what QA needs from other teams.

**Date:** 2026-02-27
**Author:** TEA Master Test Architect
**Status:** Draft
**Project:** WorkDataHub

**Related:** See Architecture doc (`test-design-architecture.md`) for testability concerns and architectural blockers.

---

## Executive Summary

**Scope:** System-level QA test plan covering all 8 domains of WorkDataHub — data pipeline processing, file discovery, company enrichment, customer MDM, database migrations, legacy comparison, configuration, and performance.

**Risk Summary:**

- Total Risks: 10 (5 high-priority score ≥6, 4 medium, 1 low)
- Critical Categories: TECH (CI infrastructure), DATA (golden dataset), BUS (MDM logic)

**Coverage Summary:**

- P0 tests: ~11 (critical paths, data integrity, core pipeline)
- P1 tests: ~21 (important features, integration, MDM hooks)
- P2 tests: ~7 (edge cases, enrichment mock, security)
- P3 tests: ~3 (benchmarks, exploratory)
- **Total**: ~42 test scenarios (~68–105 hours with 1 engineer)

---

## Not in Scope

**Components or systems explicitly excluded from this test plan:**

| Item | Reasoning | Mitigation |
|---|---|---|
| **Dagster orchestration** | Dormant; CLI-driven execution is current mode | Periodic smoke test (P3) |
| **PowerBI dashboard rendering** | External BI tool; not testable in CI | Manual validation by analysts |
| **EQC real browser automation** | Requires headful browser + CAPTCHA; CI-incompatible | StubProvider for CI; manual on-demand |
| **Legacy MySQL write operations** | Read-only migration source; no writes | N/A |

**Note:** Items listed here have been reviewed and accepted as out-of-scope by QA, Dev, and PM.

---

## Dependencies & Test Blockers

**CRITICAL:** QA cannot proceed without these items from other teams.

### Backend/Architecture Dependencies (Pre-Implementation)

**Source:** See Architecture doc "Quick Guide" for detailed mitigation plans

1. **PostgreSQL CI Service Container** - Dev/Ops - Pre-implementation
   - QA needs: Ephemeral test databases in CI for all DB-interaction tests
   - Why it blocks: 100% of warehouse loader, migration, and MDM integration tests require PostgreSQL

2. **Golden Dataset Extraction** - Dev/QA - Pre-implementation
   - QA needs: Anonymized reference output from legacy system for comparison
   - Why it blocks: Legacy regression detection is impossible without baseline data

3. **StubProvider Completion** - Dev - Pre-implementation
   - QA needs: Mock coverage for all 5 enrichment resolution strategies
   - Why it blocks: Company enrichment integration tests cannot run in CI

### QA Infrastructure Setup (Pre-Implementation)

1. **Test Data Factories** - QA
   - Pydantic model factories with faker-based randomization for all 8 domains
   - Auto-cleanup fixtures for parallel safety

2. **Test Environments** - QA
   - Local: `uv run pytest` with `.wdh_env` config
   - CI/CD: GitHub Actions with PostgreSQL service container
   - Staging: N/A (batch processing, no persistent staging environment)

---

## Risk Assessment

**Note:** Full risk details in Architecture doc. This section summarizes risks relevant to QA test planning.

### High-Priority Risks (Score ≥6)

| Risk ID | Category | Description | Score | QA Test Coverage |
|---|---|---|---|---|
| **R-01** | TECH | CI has zero PostgreSQL test coverage | **9** | Enable postgres-marked tests in CI; add warehouse loader + migration tests |
| **R-03** | DATA | No golden dataset for legacy comparison | **9** | Automate golden dataset comparison in E2E suite |
| **R-04** | BUS | Customer MDM SCD2 logic undertested | **6** | Add SCD2 state transition + ratchet rule integration tests |
| **R-02** | TECH | EQC API untestable in CI | **6** | StubProvider-based enrichment integration tests |
| **R-05** | OPS | Alembic migration rollback unverified | **6** | Add upgrade/downgrade round-trip tests |

### Medium/Low-Priority Risks

| Risk ID | Category | Description | Score | QA Test Coverage |
|---|---|---|---|---|
| R-06 | PERF | Multi-domain parallel execution untested | 4 | Add concurrent domain integration tests |
| R-07 | SEC | Secrets managed manually via `.wdh_env` | 4 | Verify no secret leakage to logs |
| R-08 | DATA | PowerBI Gold layer no schema validation | 4 | Add Gold layer Pandera assertions |
| R-10 | DATA | Chinese column names in SQL generation | 4 | Expand SQL generation unit tests with CJK |
| R-09 | TECH | Dagster definitions dormant | 2 | Periodic smoke test |

---

## Entry Criteria

**QA testing cannot begin until ALL of the following are met:**

- [ ] PostgreSQL service container available in CI workflow
- [ ] Golden dataset extracted and stored as CI artifact
- [ ] StubProvider covers all 5 enrichment resolution strategies
- [ ] All Alembic migrations pass upgrade in CI
- [ ] Test data factories ready for all 8 domains
- [ ] `.wdh_env` template documented for local test setup

## Exit Criteria

**Testing phase is complete when ALL of the following are met:**

- [ ] All P0 tests passing (100% pass rate)
- [ ] All P1 tests passing (≥95% pass rate, failures triaged)
- [ ] No open high-priority / high-severity bugs
- [ ] Code coverage ≥80% on `src/work_data_hub/`
- [ ] All CRITICAL risks (Score=9) mitigated
- [ ] Legacy comparison passes against golden dataset

---

## Test Coverage Plan

**IMPORTANT:** P0/P1/P2/P3 = **priority and risk level** (what to focus on if time-constrained), NOT execution timing. See "Execution Strategy" for when tests run.

### P0 (Critical)

**Criteria:** Blocks core functionality + High risk (≥6) + No workaround + Affects majority of users

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| **P0-001** | Pydantic model validation (valid/invalid) | Unit | — | Existing; verify completeness |
| **P0-002** | Pandera DataFrame schema validation | Unit | — | Existing; verify completeness |
| **P0-003** | Bronze→Silver transformation correctness | Unit | — | Existing; verify all domains |
| **P0-004** | Pipeline end-to-end (plan-only mode) | Integration | — | Existing |
| **P0-005** | Pipeline end-to-end (execute + DB write) | Integration | R-01 | Needs postgres CI |
| **P0-006** | StubProvider offline lookup | Unit | — | Existing |
| **P0-007** | HMAC temp ID generation stability | Unit | — | Existing |
| **P0-008** | Customer status evaluation logic | Unit | R-04 | Existing; verify all paths |
| **P0-009** | SCD2 history record correctness | Integration | R-01, R-04 | Needs postgres CI |
| **P0-010** | Alembic migration upgrade | Integration | R-01, R-05 | Needs postgres CI |
| **P0-011** | Warehouse loader delete/insert semantics | Integration | R-01 | Needs postgres CI |

**Total P0:** ~11 tests

---

### P1 (High)

**Criteria:** Important features + Medium risk (3-4) + Common workflows + Workaround exists but difficult

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| **P1-001** | Silver→Gold projection logic | Unit | — | Existing |
| **P1-002** | Multi-domain parallel execution | Integration | R-06 | New; resource contention |
| **P1-003** | Failed records export & reporting | Unit | — | Existing |
| **P1-004** | Version-aware folder scanning | Unit | — | Existing |
| **P1-005** | Pattern-matching file selection | Unit | — | Existing |
| **P1-006** | Multi-sheet Excel reading | Unit | — | Existing |
| **P1-007** | Column name normalization (CJK) | Unit | R-10 | Existing |
| **P1-008** | File discovery integration | Integration | — | Existing |
| **P1-009** | Multi-layer resolution strategy | Unit | R-02 | Partial; expand |
| **P1-010** | Confidence score & review threshold | Unit | R-02 | Partial; expand |
| **P1-011** | Post-ETL hook: contract_status_sync | Integration | R-04 | New; needs postgres |
| **P1-012** | Post-ETL hook: snapshot_refresh | Integration | R-04 | New; needs postgres |
| **P1-013** | Annual cutover logic | Unit | R-04 | New; verify boundary |
| **P1-014** | Ratchet rule enforcement | Unit | R-04 | New; verify constraints |
| **P1-015** | Fact table monthly snapshot refresh | Integration | R-04 | New; needs postgres |
| **P1-016** | Alembic migration rollback (downgrade) | Integration | R-05 | New; needs postgres |
| **P1-017** | Schema consistency validation | Integration | R-01 | Existing |
| **P1-018** | SQL generation (CJK identifiers) | Unit | R-10 | Existing |
| **P1-019** | Legacy comparison (annuity performance) | E2E | R-03 | Needs golden dataset |
| **P1-020** | Pydantic Settings env binding | Unit | — | Existing |
| **P1-021** | data_sources.yml schema validation | Unit | — | Existing |

**Total P1:** ~21 tests

---

### P2 (Medium)

**Criteria:** Secondary features + Low risk (1-2) + Edge cases + Regression prevention

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| **P2-001** | EQC API integration (mock) | Integration | R-02 | New; StubProvider |
| **P2-002** | Async enrichment queue processing | Integration | R-02 | New |
| **P2-003** | Secrets not leaked to logs | Unit | R-07 | New; structlog filter |
| **P2-004** | Gitleaks CI scan effectiveness | Integration | R-07 | Existing |
| **P2-005** | Pipeline processing <30min (8 domains) | Performance | — | Partial baseline |
| **P2-006** | Pandera validation benchmarks | Performance | — | Existing |
| **P2-007** | Golden dataset automated comparison | E2E | R-03 | New; needs dataset |

**Total P2:** ~7 tests

---

### P3 (Low)

**Criteria:** Nice-to-have + Exploratory + Performance benchmarks + Documentation validation

| Test ID | Requirement | Test Level | Notes |
|---|---|---|---|
| **P3-001** | Date parsing performance benchmarks | Performance | Existing |
| **P3-002** | structlog structured output validation | Unit | Existing |
| **P3-003** | Dagster definitions smoke test | Integration | Periodic only |

**Total P3:** ~3 tests

---

## Execution Strategy

**Philosophy:** Run everything fast in PRs; defer expensive suites to nightly/weekly.

**Organized by execution tier:**

### Every PR: pytest Unit + Integration (~10 min)

**All fast tests** (from any priority level):

- All unit tests (`tests/unit/`)
- Integration tests without postgres marker (`tests/integration/` minus `@pytest.mark.postgres`)
- Ruff linting + MyPy type checking
- Total: ~30+ existing tests + new unit tests

**Command:** `PYTHONPATH=src uv run pytest -m "not postgres and not legacy_data and not monthly_data" --cov=src/work_data_hub`

**Why run in PRs:** Fast feedback, no external infrastructure needed

### Nightly: PostgreSQL Integration Tests (~25 min)

**All database-dependent tests:**

- Postgres-marked integration tests (warehouse loader, migrations, MDM)
- Customer MDM SCD2 + post-ETL hook tests
- Schema consistency validation

**Command:** `PYTHONPATH=src uv run pytest -m "postgres" --cov=src/work_data_hub`

**Why defer to nightly:** Requires PostgreSQL service container; slower setup

### Weekly: E2E + Performance (~45 min)

**Full regression and performance suites:**

- Legacy comparison E2E tests (golden dataset)
- Multi-domain parallel execution tests
- Performance benchmarks (Pandera, date parsing, model validation)

**Command:** `PYTHONPATH=src uv run pytest tests/e2e/ tests/performance/ -m "not monthly_data"`

**Why defer to weekly:** Long-running; requires golden dataset artifacts

---

## QA Effort Estimate

**QA test development effort only** (excludes DevOps infrastructure work):

| Priority | Count | Effort Range | Notes |
|---|---|---|---|
| P0 | ~11 | ~30–45 hours | CI postgres setup + SCD2 integration |
| P1 | ~21 | ~25–40 hours | MDM hooks + migration rollback + parallel |
| P2 | ~7 | ~10–15 hours | EQC mock + secret validation |
| P3 | ~3 | ~3–5 hours | Benchmarks, smoke tests |
| **Total** | **~42** | **~68–105 hours** | **1 engineer, full-time** |

**Assumptions:**

- Includes test design, implementation, debugging, CI integration
- Excludes ongoing maintenance (~10% effort)
- Assumes test infrastructure (factories, fixtures) ready

---

## Tooling & Access

| Tool or Service | Purpose | Access Required | Status |
|---|---|---|---|
| pytest + pytest-cov | Test runner + coverage | pip install (dev deps) | Ready |
| pytest-postgresql | Ephemeral test DB | pip install (dev deps) | Ready |
| Ruff + MyPy | Linting + type checking | pip install (dev deps) | Ready |
| GitHub Actions | CI/CD pipeline | Repo write access | Ready |
| PostgreSQL 15 | CI service container | GitHub Actions config | Pending |

---

## Interworking & Regression

**Services and components impacted by test infrastructure changes:**

| Service/Component | Impact | Regression Scope | Validation Steps |
|---|---|---|---|
| **Warehouse Loader** | DB write tests enabled | All existing loader tests must pass | Run full postgres suite |
| **Alembic Migrations** | Rollback tests added | Existing upgrade tests unaffected | Run migration round-trip |
| **Customer MDM** | New integration tests | Existing unit tests unaffected | Run MDM test suite |
| **Company Enrichment** | StubProvider expanded | Existing stub tests unaffected | Run enrichment suite |

**Regression test strategy:**

- All existing tests must continue to pass after infrastructure changes
- New tests are additive; no modification to existing test logic
- CI pipeline runs full suite on merge to main

---

## Appendix A: Code Examples & Tagging

**pytest Markers for Selective Execution:**

```python
import pytest

# P0 critical test — DB integration
@pytest.mark.postgres
@pytest.mark.p0
def test_pipeline_execute_db_write(pg_session, sample_bronze_df):
    """Pipeline writes to PostgreSQL and data matches expected output."""
    result = run_pipeline(session=pg_session, data=sample_bronze_df, mode="execute")
    assert result.success is True
    rows = pg_session.execute(text("SELECT count(*) FROM target_table")).scalar()
    assert rows == len(sample_bronze_df)


# P1 unit test — no DB needed
@pytest.mark.p1
def test_ratchet_rule_enforcement():
    """Status cannot downgrade without explicit override."""
    customer = make_customer(status="active")
    with pytest.raises(RatchetViolationError):
        customer.update_status("prospect")
```

**Run specific markers:**

```bash
# Run only P0 tests
PYTHONPATH=src uv run pytest -m "p0"

# Run P0 + P1 tests (no postgres)
PYTHONPATH=src uv run pytest -m "(p0 or p1) and not postgres"

# Run only postgres-dependent tests
PYTHONPATH=src uv run pytest -m "postgres"
```

---

## Appendix B: Knowledge Base References

- **Risk Governance**: `_bmad/tea/testarch/knowledge/risk-governance.md` — Risk scoring methodology (P×I matrix)
- **Test Priorities Matrix**: `_bmad/tea/testarch/knowledge/test-priorities-matrix.md` — P0-P3 classification criteria
- **Test Levels Framework**: `_bmad/tea/testarch/knowledge/test-levels-framework.md` — Unit/Integration/E2E selection guide
- **Test Quality**: `_bmad/tea/testarch/knowledge/test-quality.md` — Definition of Done (deterministic, isolated, <300 lines, <1.5 min)

---

**Generated by:** BMad TEA Agent
**Workflow:** `_bmad/tea/testarch/test-design`
