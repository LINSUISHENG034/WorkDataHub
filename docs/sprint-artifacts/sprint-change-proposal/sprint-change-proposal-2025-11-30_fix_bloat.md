# Sprint Change Proposal: Annuity Performance Refactoring

**Date:** 2025-11-30
**Author:** Bob (Scrum Master)
**Status:** Draft
**Topic:** Addressing Code Bloat and Architectural Regression in Annuity Domain

---

## 1. Issue Summary

**Trigger:** Post-implementation review of `annuity_performance` (Stories 4.7-4.9) revealed severe code bloat and complexity compared to the legacy system.

**Problem Statement:**
The refactored `annuity_performance` module has grown to ~3,647 lines (vs ~75 core lines in legacy), a **48x increase**. This violates the PRD goal of "Fearless Extensibility" (<4 hours to add a domain).

**Evidence:**
- **Boilerplate:** Simple column mappings are wrapped in verbose `TransformStep` classes (80+ lines each).
- **Performance:** Architecture enforces row-by-row processing (`processing_helpers.py`) instead of vectorized Pandas operations.
- **Redundancy:** Dual validation logic in Pydantic models and Pandera schemas.

**Root Cause:**
Misinterpretation of Architectural Decision #3 ("Hybrid Pipeline"). The "Row-level" capability was overused as the default pattern, ignoring the "Pandas First" optimization necessary for ETL tasks.

---

## 2. Impact Analysis

| Area | Impact Description | Severity |
|------|--------------------|----------|
| **Architecture** | "Hybrid Pipeline" pattern needs strict guardrails to prevent misuse. | High |
| **Epic 4 (Annuity)** | Completed code is "correct" but unmaintainable. Needs immediate refactoring. | High |
| **Epic 9 (Growth)** | Replicating current pattern to 5 new domains would result in ~15k lines of technical debt. | Critical |
| **Legacy Parity** | Refactoring must maintain 100% output parity (verified by Golden Dataset). | Critical |

---

## 3. Recommended Approach

**Strategy:** **Refactor Immediately (Course Correction)**

We cannot proceed to Epic 9 (Growth Domains) with the current pattern. We must establish a "Standard Domain Architecture" now and refactor `annuity_performance` to prove it works.

**Core Changes:**
1.  **Pandas First:** Enforce vectorized operations. Ban row-loops for standard transformations.
2.  **Config over Code:** Move static mappings to `config.py`.
3.  **Shared Generic Steps:** Implement `DataFrameMappingStep`, `DataFrameReplacementStep` in the shared framework to avoid boilerplate.

**Estimated Effort:**
- 1-2 days to implement generic steps and refactor `annuity_performance`.
- **ROI:** Saves ~2 weeks of dev time during Epic 9 and drastically reduces long-term maintenance.

---

## 4. Detailed Change Proposals

### 4.1 Architecture Documentation Update

**Action:** Update `docs/architecture.md`
**Change:** Add **Decision #9: Standard Domain Architecture Pattern**.
**Details:**
- Explicitly define the "Standard Domain" folder structure.
- Mandate "Pandas First" for transformations.
- Restrict Pydantic usage to complex, cross-field validation that cannot be vectorized.

### 4.2 Codebase Refactoring (Annuity Domain)

**Action:** Massive simplification of `src/work_data_hub/domain/annuity_performance/`.

**Specific Changes:**
- **Delete:** `processing_helpers.py` (The row-iteration engine).
- **Simplify:** `service.py` (Remove row-processing orchestration).
- **Refactor:** `pipeline_steps.py` -> Replace custom classes with configuration-driven generic steps where possible.
- **New File:** `config.py` to hold all dictionary mappings and column lists.

### 4.3 Shared Framework Enhancement

**Action:** Create generic, configurable steps in `src/work_data_hub/domain/pipelines/steps/`.

**New Components:**
- `DataFrameMappingStep`: Takes a config dict `{'old_col': 'new_col'}` and applies it.
- `DataFrameValueReplacementStep`: Takes a config dict `{'col': {'old_val': 'new_val'}}` and applies it.
- `DataFrameCalculatedFieldStep`: Generic interface for simple column math.

---

## 5. Implementation Handoff

**Scope Classification:** **Moderate** (Requires specific refactoring stories but fits within current architectural vision).

**Route To:** Implementation Team (Developer)

**Plan:**
1.  **Create Story:** "Implement Standard Domain generic steps" (Shared Framework).
2.  **Create Story:** "Refactor Annuity Performance to Standard Domain pattern" (Cleanup).
3.  **Update Epic 9:** Add acceptance criteria to ensure new domains use the Standard pattern.

**Success Criteria:**
- `annuity_performance` line count reduced by >50%.
- `legacy_parity_test` passes with 100% match.
- No row-level iteration loops in `annuity_performance/service.py`.
