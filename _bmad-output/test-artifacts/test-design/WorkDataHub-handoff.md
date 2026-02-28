---
title: 'TEA Test Design → BMAD Handoff Document'
version: '1.0'
workflowType: 'testarch-test-design-handoff'
sourceWorkflow: 'testarch-test-design'
generatedBy: 'TEA Master Test Architect'
generatedAt: '2026-02-27'
projectName: 'WorkDataHub'
---

# TEA → BMAD Integration Handoff

## Purpose

This document bridges TEA's test design outputs with BMAD's epic/story decomposition workflow (`create-epics-and-stories`). It provides structured integration guidance so that quality requirements, risk assessments, and test strategies flow into implementation planning.

## TEA Artifacts Inventory

| Artifact | Path | BMAD Integration Point |
|---|---|---|
| Architecture Test Design | `_bmad-output/test-artifacts/test-design-architecture.md` | Epic quality requirements, story acceptance criteria |
| QA Test Design | `_bmad-output/test-artifacts/test-design-qa.md` | Story test requirements, execution strategy |
| Risk Assessment | (embedded in architecture doc) | Epic risk classification, story priority |
| Coverage Strategy | (embedded in QA doc) | Story test requirements, P0-P3 mapping |

## Epic-Level Integration Guidance

### Risk References

The following P0/P1 risks should appear as epic-level quality gates:

| Risk ID | Score | Epic Impact | Quality Gate |
|---|---|---|---|
| R-01 | 9 (CRITICAL) | Epic 8 | CI PostgreSQL service must be operational before any DB test story |
| R-03 | 9 (CRITICAL) | Epic 8 | Golden dataset must be extracted before legacy comparison stories |
| R-04 | 6 (HIGH) | Epic 7.6 / Epic 8 | SCD2 integration tests must pass before MDM stories are "done" |
| R-02 | 6 (HIGH) | Epic 8 | StubProvider must cover all strategies before enrichment test stories |
| R-05 | 6 (HIGH) | Epic 8 | Migration rollback tests must pass before migration stories are "done" |

### Quality Gates

| Epic | Gate Criteria |
|---|---|
| Epic 8 (Testing & Validation) | R-01 + R-03 resolved before story development begins |
| Epic 7.6 (Customer MDM) | R-04 SCD2 tests pass before retrospective closes |
| All Epics | P0 pass rate = 100%, P1 ≥ 95%, coverage ≥ 80% |

## Story-Level Integration Guidance

### P0/P1 Test Scenarios → Story Acceptance Criteria

The following critical test scenarios MUST be embedded as acceptance criteria in their respective stories:

| Test ID | Scenario | Story Target | AC Text |
|---|---|---|---|
| P0-005 | Pipeline execute + DB write | Epic 8: CI Infrastructure | "Pipeline writes to PostgreSQL in CI and data matches expected output" |
| P0-009 | SCD2 history correctness | Epic 8: MDM Testing | "SCD2 state transitions produce correct history records in DB" |
| P0-010 | Alembic migration upgrade | Epic 8: Migration Testing | "All 13 migrations run successfully in CI PostgreSQL" |
| P1-016 | Migration rollback | Epic 8: Migration Testing | "Each migration can downgrade without data loss" |
| P1-019 | Legacy comparison | Epic 8: Regression Testing | "Pipeline output matches golden dataset within tolerance" |

## Risk-to-Story Mapping

| Risk ID | Category | P×I | Recommended Story/Epic | Test Level |
|---|---|---|---|---|
| R-01 | TECH | 9 | Epic 8: CI Infrastructure Setup | Integration |
| R-03 | DATA | 9 | Epic 8: Golden Dataset Extraction | E2E |
| R-04 | BUS | 6 | Epic 8: Customer MDM Test Suite | Integration |
| R-02 | TECH | 6 | Epic 8: Enrichment Mock Layer | Integration |
| R-05 | OPS | 6 | Epic 8: Migration Rollback Tests | Integration |
| R-06 | PERF | 4 | Epic 8: Multi-Domain Concurrency | Integration |
| R-10 | DATA | 4 | Epic 8: CJK SQL Generation Tests | Unit |

## Recommended BMAD → TEA Workflow Sequence

1. **TEA Test Design** (`TD`) → produces this handoff document
2. **BMAD Create Epics & Stories** → consumes this handoff, embeds quality requirements
3. **TEA ATDD** (`AT`) → generates acceptance tests per story
4. **BMAD Implementation** → developers implement with test-first guidance
5. **TEA Automate** (`TA`) → generates full test suite
6. **TEA Trace** (`TR`) → validates coverage completeness

## Phase Transition Quality Gates

| From Phase | To Phase | Gate Criteria |
|---|---|---|
| Test Design | Epic/Story Creation | All P0 risks have mitigation strategy |
| Epic/Story Creation | ATDD | Stories have acceptance criteria from test design |
| ATDD | Implementation | Failing acceptance tests exist for all P0/P1 scenarios |
| Implementation | Test Automation | All acceptance tests pass |
| Test Automation | Release | Trace matrix shows ≥80% coverage of P0/P1 requirements |
