# Test Quality Review: Cleanup & Standardization

**Review Date**: 2025-12-07
**Review Scope**: Suite (Cleanup Focus)
**Reviewer**: TEA Agent (Test Architect)

---

## Executive Summary

**Overall Assessment**: **Needs Improvement** (Architecture & Hygiene)

A comprehensive scan of the `tests/` directory (104 files) reveals a robust test suite with good coverage of acceptance criteria and domain logic. However, the suite shows signs of "sprint accumulation" — temporary test files created for specific stories or bug fixes that have not been refactored into the permanent test architecture.

**Key Strengths:**
✅ **Strong Acceptance Testing**: Files like `test_story_2_1_ac.py` map directly to PRD requirements with rigorous checks.
✅ **Architecture Enforcement**: `test_project_structure.py` is an excellent practice for enforcing clean architecture boundaries.
✅ **Domain Separation**: Tests are generally well-segregated by domain.

**Key Weaknesses:**
❌ **Legacy Artifacts**: Several files (`test_integration.py`, `test_cleansing_framework.py`) are deprecated, skipped, or redundant.
❌ **Vague Naming**: Files named `test_service_bug.py` or `test_integration_fixes.py` obscure their purpose and purpose.
❌ **Script-Style Tests**: Some tests (`test_cleansing_framework.py`) use `__main__` blocks and script-like patterns instead of standard pytest fixtures.

**Recommendation**: **Approve with Cleanup Tasks**. The suite is functional but requires a hygiene pass to prevent long-term rot.

---

## Critical Cleanup Actions (Immediate)

These actions should be taken to improve test hygiene and reduce noise.

### 1. Delete Deprecated/Skipped Tests

| File | Issue | Recommendation |
|------|-------|----------------|
| `tests/unit/test_integration.py` | Marked `@pytest.mark.skip`, depends on deprecated `sample_trustee_performance`, tests integration in `unit/` folder. | **DELETE** |
| `tests/unit/test_cleansing_framework.py` | Script-style test with `__main__` block, redundant with `cleansing/test_registry.py`, mixed language comments. | **DELETE** (Verify `test_registry.py` covers all cases first) |

### 2. Rename Vague Files

| Current Name | Issue | New Name (Recommended) |
|--------------|-------|------------------------|
| `tests/domain/trustee_performance/test_service_bug.py` | "Bug" is temporal. Doesn't describe *what* is tested. | `test_service_validation_error_handling.py` |
| `tests/domain/pipelines/test_integration_fixes.py` | "Fixes" is temporal. Tests factory methods and config. | `test_pipeline_config_factory.py` |

### 3. Consolidate Story Tests

| Pattern | Issue | Recommendation |
|---------|-------|----------------|
| `test_story_X_ac.py` | Files bound to sprint stories rot. Features persist, stories end. | Move to `tests/domain/{domain}/test_acceptance.py` or `test_models.py` |
| `test_story_X_performance.py` | same as above | Move to `tests/performance/domain/{domain}_benchmarks.py` |

---

## Quality Criteria Assessment (Sampled)

| Criterion | Status | Notes |
|-----------|--------|-------|
| **BDD Format** | ✅ PASS | `test_story_2_1_ac.py` uses clear AC mapping and Given-When-Then logic. |
| **Test IDs** | ⚠️ WARN | Many tests lack explicit IDs (e.g., `1.1-E2E-001`). Hard to trace back to requirements without file naming conventions. |
| **Naming** | ❌ FAIL | `test_service_bug.py` and `test_integration_fixes.py` violate naming best practices. |
| **Isolation** | ✅ PASS | Most tests use fixtures. `test_project_structure.py` is purely static analysis (good). |
| **Clean Code** | ⚠️ WARN | `test_cleansing_framework.py` contains `try-except ImportError` logic inside test file, which is an anti-pattern for pytest. |

---

## Detailed Findings

### 1. `tests/unit/test_project_structure.py`
**Rating**: ⭐⭐⭐⭐⭐ (Excellent)
This is a model test. It validates:
- Directory structure (Clean Architecture).
- Dependency versions (`pyproject.toml` vs `uv.lock`).
- Environment template existence.
**Action**: Keep as a reference standard.

### 2. `tests/domain/annuity_performance/test_story_2_1_ac.py`
**Rating**: ⭐⭐⭐⭐ (Good content, bad location)
Excellent validation of data models using Pydantic. It effectively tests the "Bronze Layer" validation logic.
**Action**: Rename to `tests/domain/annuity_performance/test_model_validation.py`. Remove "Story" reference from filename (keep in docstring if needed).

### 3. `tests/domain/trustee_performance/test_service_bug.py`
**Rating**: ⭐⭐ (Bad naming)
The test content is valid (reproducing a specific error), but the filename is technical debt.
**Action**: Rename to reflect the behavior being tested (e.g., `test_invalid_date_error_handling.py`).

### 4. `tests/unit/test_cleansing_framework.py`
**Rating**: ⭐ (Delete)
This file appears to be a "demo" script rather than a rigorous unit test. It duplicates logic found in `tests/unit/cleansing/test_registry.py`.
**Action**: Delete. Ensure `test_registry.py` has full coverage of `RuleCategory` and registry lookups.

---

## Next Steps

1.  **Execute Deletions**: Remove the two identified files.
2.  **Rename Files**: Fix the naming of the "bug" and "fixes" files.
3.  **Refactor Plan**: Create a task to consolidate `test_story_*` files into domain regression suites over the next sprint.

**Signed,**
*Murat (TEA)*
*Master Test Architect*
