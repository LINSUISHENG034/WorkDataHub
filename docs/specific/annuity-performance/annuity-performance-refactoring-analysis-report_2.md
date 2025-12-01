# Annuity Performance Domain Architecture Analysis Report

**Date:** 2025-11-30
**Status:** Analysis Phase
**Context:** Post-implementation review of Stories 4.7-4.9

## 1. Executive Summary

Following the implementation of the annuity_performance domain migration (Stories 4.7-4.9), a critical review revealed significant architectural bloat and inefficiency. The current implementation, while functionally correct (achieving parity with legacy), suffers from over-engineering that compromises the project's core goals of maintainability and rapid extensibility.

This report documents the analysis of the current state, identifies root causes using First Principles thinking, and proposes a simplified **Standard Domain Architecture** pattern.

## 2. Problem Statement

**Observation:**
The refactored `annuity_performance` module is significantly larger and more complex than the legacy code it replaces, without delivering proportional value in flexibility or reliability.

- **Legacy Code:** ~70 lines of concise Pandas-based logic.
- **New Code:** 470+ lines across multiple files (`service.py`, `pipeline_steps.py`, `processing_helpers.py`), utilizing verbose class-based steps and row-by-row processing.

**Core Issues:**
1.  **Boilerplate Explosion:** Simple transformations (e.g., column mapping) are wrapped in verbose `TransformStep` classes.
2.  **Performance Regression:** The architecture enforces a row-by-row processing model (via `processing_helpers.py`) for validation and enrichment, abandoning Pandas' vectorized performance advantages.
3.  **Logic Duplication:** Validation logic is split between Pipeline steps and helper functions, creating potential for inconsistency.
4.  **High Friction for Extension:** Adding a new domain requires writing significant boilerplate code, violating the "new domain in <4 hours" PRD objective.

## 3. First Principles Analysis

We revisited the fundamental definition and responsibilities of a **Domain Module** within the Clean Architecture context to identify where the design deviated.

### 3.1 Domain Module Responsibilities (The "Ideal")

A Domain module should be a **pure business logic container**:
*   **Defines What:** Data schemas (Models), business rules, and transformation logic.
*   **Ignorant of How:** Should not care about file I/O, database connections, or execution orchestration details.

### 3.2 Deviation Analysis (The "Reality")

| Component | Current Implementation | First Principles Verdict |
| :--- | :--- | :--- |
| **Pipeline Steps** | Class-based wrappers for simple logic. | **Over-engineered.** Business logic is usually a function or configuration, not a stateful class. |
| **Processing Helpers** | Row-by-row iteration engine. | **Anti-Pattern.** Reinvents an execution engine inside the domain; performance killer; belongs in infrastructure or should be vectorized. |
| **Models (Pydantic)** | Dual models (In/Out) with per-row conversion. | **Valid but Misused.** Validation is necessary, but forcing row-by-row conversion for bulk data is inefficient. |

### 3.3 Root Cause

The root cause is **Schizophrenic Architecture**: The system attempts to be both a high-performance DataFrame pipeline AND a meticulous row-by-row object mapper.
- It uses Pandas for Step 1 (good).
- It then discards Pandas efficiency to iterate 50k+ rows in Python loops for Step 2 (bad).
- It wraps simple "What" (business rules) into complex "How" (class hierarchies), confusing configuration with implementation.

## 4. Proposed Solution: "Standard Domain" Architecture

We propose a simplified, standardized architecture that all domains must follow.

### 4.1 Core Principles
1.  **Pandas First:** Embrace vectorized operations for ALL transformations.
2.  **Configuration over Code:** Define mappings and rules in data structures (config.py), not classes.
3.  **Eliminate Row Loops:** No row-by-row iteration inside the domain.
4.  **Thin Domain:** Minimal boilerplate.

### 4.2 Standard Domain Structure

```
domain/<domain_name>/
├── __init__.py
├── config.py           # (NEW) Pure configuration (mappings, rules) - NO logic
├── service.py          # Entry point & orchestration - minimal logic
├── pipeline_steps.py   # Domain-specific vectorized steps (only if generic ones fail)
└── schemas.py          # Pandera/Pydantic schemas for validation
```

### 4.3 Module Responsibilities

| Module | Responsibility | Constraints |
| :--- | :--- | :--- |
| **config.py** | Define **WHAT** to do. Mappings (`{'A': 'B'}`), field lists, rules. | **Zero logic.** Pure data structures (Dict, List). |
| **schemas.py** | Define **Data Contracts**. Pandera Schemas for DataFrame validation. | **Zero transformation.** Validation only. |
| **service.py** | **Orchestration**. Load config, instantiate Pipeline, run Pipeline. | **Zero iteration.** No `for row in df`. Max 50 lines of code. |
| **pipeline_steps.py** | **Custom Logic**. Only for domain-specific vector operations. | **Vectorized only.** Must accept/return DataFrame. |

### 4.4 Migration Plan (Epic 4.5)

1.  **Generic Steps:** Create `DataFrameMappingStep`, `DataFrameReplacementStep`, `BulkEnrichmentStep` in shared framework.
2.  **Refactor Annuity:** Convert `annuity_performance` to the Standard Domain structure.
    *   Move mappings to `config.py`.
    *   Delete `processing_helpers.py`.
    *   Simplify `pipeline_steps.py` by using generic steps.
3.  **Verify:** Ensure parity with legacy output is maintained.

## 5. Conclusion

This refactoring is critical before proceeding to Epic 9 (Growth Domains). It will reduce code volume, improve performance, and dramatically lower the cost of adding new domains.
