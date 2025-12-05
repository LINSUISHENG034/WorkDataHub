# Proposal Review: Infrastructure Refactoring (First Principles Analysis)

**Date:** 2025-12-01
**Reviewer:** Link (AI Agent)
**Status:** Review Feedback

---

## 1. Core Critique: First Principles Analysis

We reviewed the original proposal (`sprint-change-proposal-infrastructure-refactoring-2025-12-01.md`) using **First Principles**. While the architectural goal (decoupling) is correct, the proposed implementation strategy suffers from **Over-Engineering** and **Inner-Platform Effect**.

### Key Findings

1.  **Red Alert: `TransformExecutor` (Story 4.16)**
    *   **Problem:** The proposal suggests building a JSON-configuration-driven engine to perform data transformations (mappings, calculations).
    *   **First Principle:** Python (with Pandas) is already the best language for expressing logic. Building a custom configuration DSL on top of it creates a "platform within a platform" that is harder to debug, test, and maintain than native code.
    *   **Recommendation:** Abandon the JSON engine. Use **Python Code Composition** (the Pipeline Pattern). Infrastructure should provide reusable Python components (`StandardSteps`), not a configuration execution engine.

2.  **Yellow Alert: `ValidationExecutor` (Story 4.15)**
    *   **Problem:** The proposal suggests a heavy Class wrapper around validation libraries.
    *   **First Principle:** `Pandera` and `Pydantic` are already "executors". Wrapping them in a stateful class adds unnecessary abstraction.
    *   **Recommendation:** Simplify to **Validation Utilities** (pure functions for error handling and reporting). Let the domain logic call `schema.validate()` directly.

3.  **Green Light: `CompanyIdResolver` (Story 4.14)**
    *   **Verdict:** This captures complex, highly specific business logic that needs to be reused. This is a valid candidate for an infrastructure service.

---

## 2. Recommended Modifications

We recommend modifying the Sprint Proposal to reflect a "Python-First" approach. Below are the specific revisions for the affected Stories.

### Modified Story 4.15: Implement Validation Error Handling Utilities

**Change:** From "Heavy Executor Class" to "Lightweight Utility Functions".

**User Story:**
As a **developer**, I want to **standardize validation error handling and reporting**, so that **I don't need to rewrite error logging and CSV export logic for every domain**.

**Acceptance Criteria:**
- **Do NOT** create a `ValidationExecutor` class that wraps `schema.validate()`.
- Create `infrastructure/validation/error_handler.py`:
  - `handle_validation_errors(errors, threshold, total_rows)`: Logic to check thresholds and log errors.
- Create `infrastructure/validation/report_generator.py`:
  - `export_error_csv(failed_rows, filename_prefix)`: Logic to save failed rows to the standard log directory.
- The domain service calling code will look like:
  ```python
  try:
      BronzeSchema.validate(df, lazy=True)
  except SchemaError as e:
      error_handler.handle_validation_errors(e.failure_cases)
      report_generator.export_error_csv(e.data)
  ```

### Modified Story 4.16: Implement Standard Pipeline Steps

**Change:** From "JSON Config Engine" to "Reusable Python Steps".

**User Story:**
As a **data engineer**, I want a **library of reusable Pipeline Steps**, so that **I can compose domain pipelines using standard Python components instead of writing custom logic for every field**.

**Acceptance Criteria:**
- **Abandon** `TransformExecutor` and JSON configuration parsing.
- Create `infrastructure/transforms/standard_steps.py` containing reusable classes inheriting from the base `TransformStep`:
  - `MappingStep(mapping_dict, target_col, source_col)`
  - `CalculationStep(func, target_col)`
  - `RenameStep(rename_map)`
  - `DropStep(columns)`
- These steps must use vectorized Pandas operations internally for performance.

### Modified Story 4.17: Refactor AnnuityPerformanceService

**Change:** Refactor to use **Code Composition** rather than Config Injection.

**Acceptance Criteria:**
- The `service.py` should construct a Pipeline using Python code:
  ```python
  def build_domain_pipeline():
      return Pipeline([
          StandardSteps.RenameStep(ALIAS_MAPPING),
          StandardSteps.MappingStep(PLAN_CODE_MAP, ...),
          CustomSteps.CompanyIdResolutionStep(resolver),
          StandardSteps.CalculationStep(calc_yield, ...),
      ])
  ```

---

## 3. Architecture Decision Record (ADR) Update Recommendation

**AD-010: Infrastructure Layer & Pipeline Composition**

*   **Decision:** Use **Python Code Composition** (Pipeline Pattern) instead of JSON Configuration for data transformations.
*   **Rationale:** Python is the superior DSL for logic. Avoids the maintenance burden of a custom configuration parser.
*   **Implication:** Infrastructure provides the *building blocks* (Steps/Utils), not the *black box engine*.

---

## 4. Configuration Structure Refinement (Restructuring Plan)

We recommend clarifying the "Configuration" architecture by strictly separating Runtime Config, Application Config, and Business Data.

### Categorization
1.  **Runtime Config:** User-facing files modified at deployment time (e.g., file scanning paths).
2.  **Application Config:** Environment variables for system behavior (e.g., DB connection, Logging).
3.  **Business Data:** Static mapping tables defining domain rules (e.g., Institution Code Mapping).

### Restructuring Map

| Current Location | New Location | Category | Reasoning |
|------------------|--------------|----------|-----------|
| `config/data_sources.yml` | **Keep as is** | Runtime Config | External interface for users/ops. |
| `src/.../config/settings.py` | `src/work_data_hub/config/settings.py` | App Config | Loads environment variables. |
| `src/.../config/schema.py` | `infrastructure/settings/data_source_schema.py` | Infra Code | Config validation logic belongs in infrastructure. |
| `src/.../config/mapping_loader.py` | `infrastructure/settings/loader.py` | Infra Code | Loading logic belongs in infrastructure. |
| `src/.../config/mappings/` | `src/work_data_hub/data/mappings/` | Business Data | Business rules should be separated from system config. |

### Final Structure Preview
```text
Project Root
├── config/                          # [Runtime Config] Deployment-time adjustments
│   └── data_sources.yml
│
└── src/work_data_hub/
    ├── config/                      # [App Config] Environment variables
    │   └── settings.py
    │
    ├── infrastructure/settings/     # [Infra Code] Config loading & validation logic
    │   ├── loader.py                (was mapping_loader.py)
    │   └── data_source_schema.py    (was schema.py)
    │
    └── data/mappings/               # [Business Data] Static business rules
        ├── plan_codes.yml
        └── ...
```

---

## 5. Full Revised Proposal Content

*(For reference, here is the complete text of the proposal as it should look after applying these changes)*

```markdown
# Sprint Change Proposal: Domain Architecture Refactoring

... [Sections 1-3 Modified to emphasize Python Composition over Config Engines] ...

### Story 4.15: Implement Validation Error Handling Utilities (REVISED)
... [See above] ...

### Story 4.16: Implement Standard Pipeline Steps (REVISED)
... [See above] ...

...
```
