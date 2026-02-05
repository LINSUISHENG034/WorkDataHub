# Sprint Change Proposal: Plan/Portfolio Code Consistency

**Date**: 2026-01-02
**Status**: Approved ✅
**Triggered By**: Epic 7.4 Validation (Code Consistency Analysis)
**Scope**: Epic 7.4 follow-up Story (Story 7.4-6)
**Priority**: P1 (Maintainability & DRY Compliance)

---

## Issue Summary

### Problem Statement

The `annuity_performance` and `annuity_income` domains contain **duplicate code** for plan code and portfolio code handling, violating the DRY (Don't Repeat Yourself) principle and SSOT (Single Source of Truth) design:

| Component                          | Issue                                          | Impact             |
| ---------------------------------- | ---------------------------------------------- | ------------------ |
| `PLAN_CODE_CORRECTIONS`            | Duplicate constant in both domains             | Maintenance risk   |
| `PLAN_CODE_DEFAULTS`               | Duplicate constant in both domains             | Maintenance risk   |
| `_apply_plan_code_defaults()`      | Identical function in both pipeline_builder.py | ~40 LOC duplicated |
| `_apply_portfolio_code_defaults()` | Similar function in both pipeline_builder.py   | ~72 LOC duplicated |

**Total duplicated code**: ~120-140 lines across 4 files

### Discovery Context

- **Discovered**: 2026-01-02 during multi-domain consistency analysis
- **Trigger**: Story 7.3-6 documented that `annuity_income` was copied from `annuity_performance`
- **Evidence**: `docs/specific/multi-domain/plan-portfolio-code-consistency-analysis.md`

---

## Impact Analysis

### Epic Impact

| Epic         | Status        | Impact                                                  |
| ------------ | ------------- | ------------------------------------------------------- |
| **Epic 7.4** | `done`        | Add Story 7.4-6 to complete architecture cleanup        |
| Epic 7.5     | `in-progress` | No change                                               |
| Epic 8       | `backlog`     | No blocking impact; cleaner codebase for future domains |

### Artifact Impact

| Artifact     | Impact   | Required Changes                         |
| ------------ | -------- | ---------------------------------------- |
| PRD          | None     | MVP unaffected                           |
| Architecture | Minor    | Extend infrastructure/mappings/shared.py |
| Code         | Moderate | Refactor 4 files, add 1 new module       |
| Tests        | Minor    | Update test imports                      |

---

## Recommended Approach

**Selected Option**: Direct Adjustment (Option 1)

### Rationale

1. **Low Risk**: Constants extraction is straightforward refactoring
2. **High Value**: Eliminates ~120 LOC duplication
3. **Minimal Timeline Impact**: 1 story (~2-4 hours implementation)
4. **No Rollback Needed**: Existing functionality preserved

---

## Proposed Changes

### Story 7.4-6: Plan/Portfolio Code Handling Consolidation

**Objective**: Eliminate code duplication by extracting shared constants and functions to infrastructure layer.

#### Task 1: Extract Plan Code Constants (P1)

**Target**: `infrastructure/mappings/shared.py`

```python
# Add to infrastructure/mappings/shared.py

# Plan code typo corrections (Story 7.5-4)
# Used by: annuity_performance, annuity_income
PLAN_CODE_CORRECTIONS: Dict[str, str] = {
    "1P0290": "P0290",
    "1P0807": "P0807",
}

# Plan code defaults based on plan type (Story 7.5-4)
# Used by: annuity_performance, annuity_income
PLAN_CODE_DEFAULTS: Dict[str, str] = {
    "集合计划": "AN001",
    "单一计划": "AN002",
}
```

**Files to Modify**:

- `infrastructure/mappings/shared.py` - Add constants
- `infrastructure/mappings/__init__.py` - Export constants
- `domain/annuity_performance/constants.py` - Change to import
- `domain/annuity_income/constants.py` - Change to import

#### Task 2: Create Shared Transform Helpers (P2)

**Target**: `infrastructure/transforms/plan_portfolio_helpers.py` (NEW FILE)

```python
"""Shared transform helpers for plan code and portfolio code normalization.

Story 7.5-4: Extracted from domain-specific pipeline_builder.py files
to establish single source of truth for cross-domain transformations.
"""

from typing import Optional
import pandas as pd

from work_data_hub.infrastructure.mappings import (
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PLAN_CODE_CORRECTIONS,
    PLAN_CODE_DEFAULTS,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)


def apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (legacy parity).

    Args:
        df: DataFrame with '计划代码' and optionally '计划类型' columns.

    Returns:
        Series with normalized plan codes.
    """
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, PLAN_CODE_DEFAULTS["集合计划"])
        result = result.mask(single_mask, PLAN_CODE_DEFAULTS["单一计划"])

    return result


def apply_portfolio_code_defaults(
    df: pd.DataFrame,
    portfolio_col: str = "组合代码",
    business_type_col: str = "业务类型",
    plan_type_col: str = "计划类型",
) -> pd.Series:
    """Apply default portfolio codes based on business type and plan type.

    Args:
        df: DataFrame with portfolio, business type, and plan type columns.
        portfolio_col: Name of portfolio code column.
        business_type_col: Name of business type column.
        plan_type_col: Name of plan type column.

    Returns:
        Series with normalized portfolio codes.
    """
    if portfolio_col not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df[portfolio_col].copy()

    # Clean portfolio codes (remove F prefix, normalize)
    result = result.astype(str).str.strip()
    result = result.str.replace(r"^[Ff]", "", regex=True)

    # Apply defaults based on business type and plan type
    empty_mask = result.isna() | (result == "") | (result == "nan")

    if business_type_col in df.columns:
        qtan003_mask = empty_mask & df[business_type_col].isin(PORTFOLIO_QTAN003_BUSINESS_TYPES)
        result = result.mask(qtan003_mask, "QTAN003")

    if plan_type_col in df.columns:
        for plan_type, default_code in DEFAULT_PORTFOLIO_CODE_MAPPING.items():
            type_mask = empty_mask & (df[plan_type_col] == plan_type)
            result = result.mask(type_mask, default_code)

    return result
```

**Files to Modify**:

- `infrastructure/transforms/plan_portfolio_helpers.py` - NEW FILE
- `infrastructure/transforms/__init__.py` - Export helpers
- `domain/annuity_performance/pipeline_builder.py` - Import and use shared function
- `domain/annuity_income/pipeline_builder.py` - Import and use shared function

#### Task 3: Update Domain Pipeline Builders

**annuity_performance/pipeline_builder.py** changes:

- Delete `_apply_plan_code_defaults()` (lines 41-58)
- Delete `_apply_portfolio_code_defaults()` (lines 61-96)
- Add import: `from work_data_hub.infrastructure.transforms import apply_plan_code_defaults, apply_portfolio_code_defaults`

**annuity_income/pipeline_builder.py** changes:

- Delete `_apply_plan_code_defaults()` (lines 108-127)
- Delete `_apply_portfolio_code_defaults()` (lines 130-165)
- Add import: `from work_data_hub.infrastructure.transforms import apply_plan_code_defaults, apply_portfolio_code_defaults`

#### Task 4: Add Unit Tests

**New File**: `tests/unit/infrastructure/transforms/test_plan_portfolio_helpers.py`

```python
"""Unit tests for plan/portfolio code helpers (Story 7.5-4)."""

import pandas as pd
import pytest

from work_data_hub.infrastructure.transforms import (
    apply_plan_code_defaults,
    apply_portfolio_code_defaults,
)


class TestApplyPlanCodeDefaults:
    """Tests for apply_plan_code_defaults function."""

    def test_returns_none_when_column_missing(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        result = apply_plan_code_defaults(df)
        assert all(v is None for v in result)

    def test_preserves_existing_values(self):
        df = pd.DataFrame({"计划代码": ["P001", "P002"], "计划类型": ["集合计划", "单一计划"]})
        result = apply_plan_code_defaults(df)
        assert list(result) == ["P001", "P002"]

    def test_fills_collective_default(self):
        df = pd.DataFrame({"计划代码": ["", None], "计划类型": ["集合计划", "集合计划"]})
        result = apply_plan_code_defaults(df)
        assert list(result) == ["AN001", "AN001"]

    def test_fills_single_default(self):
        df = pd.DataFrame({"计划代码": ["", None], "计划类型": ["单一计划", "单一计划"]})
        result = apply_plan_code_defaults(df)
        assert list(result) == ["AN002", "AN002"]


class TestApplyPortfolioCodeDefaults:
    """Tests for apply_portfolio_code_defaults function."""

    def test_returns_none_when_column_missing(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        result = apply_portfolio_code_defaults(df)
        assert all(v is None for v in result)

    def test_removes_f_prefix(self):
        df = pd.DataFrame({"组合代码": ["F12345", "f67890"]})
        result = apply_portfolio_code_defaults(df)
        assert list(result) == ["12345", "67890"]

    def test_fills_qtan003_for_zhinian(self):
        df = pd.DataFrame({
            "组合代码": ["", ""],
            "业务类型": ["职年受托", "职年投资"],
            "计划类型": ["", ""],
        })
        result = apply_portfolio_code_defaults(df)
        assert list(result) == ["QTAN003", "QTAN003"]
```

---

## Verification Plan

### Automated Tests

```bash
# Run new unit tests for shared helpers
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/unit/infrastructure/transforms/test_plan_portfolio_helpers.py -v

# Run existing domain pipeline tests (regression check)
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/unit/domain/annuity_performance/test_pipeline_builder.py -v
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/unit/domain/annuity_income/test_pipeline.py -v

# Run multi-domain integration test
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/integration/test_multi_domain_pipeline.py -v
```

### Manual Verification

1. **ETL Dry-Run** (both domains):
   ```bash
   PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
     --domains annuity_performance annuity_income --period 202510 --dry-run
   ```
   - Verify plan codes are normalized correctly
   - Verify portfolio codes are normalized correctly

---

## Implementation Handoff

| Scope         | Classification | Assignee                       |
| ------------- | -------------- | ------------------------------ |
| Code Changes  | Minor          | Dev Team (solo-dev)            |
| Story Update  | Minor          | SM (create-story workflow)     |
| Sprint Status | Minor          | SM (update sprint-status.yaml) |

### Success Criteria

1. ✅ `PLAN_CODE_CORRECTIONS` and `PLAN_CODE_DEFAULTS` exist ONLY in `infrastructure/mappings/shared.py`
2. ✅ `apply_plan_code_defaults()` and `apply_portfolio_code_defaults()` exist ONLY in `infrastructure/transforms/`
3. ✅ Both domain `constants.py` files import from infrastructure
4. ✅ Both domain `pipeline_builder.py` files use shared functions
5. ✅ All existing tests pass (no regression)
6. ✅ New unit tests verify shared helper behavior
7. ✅ Epic 7.4 marked 'done' again after Story 7.4-6 completion

---

## Approval

- [x] **PM Approval**: Scope confirmed as Epic 7.4 Story 7.4-6 ✅ 2026-01-02
- [x] **Dev Approval**: Technical approach validated ✅ 2026-01-02
- [x] **Ready for Implementation**: Story 7.4-6 drafted, sprint-status.yaml updated

---

## References

- [Analysis Document](file:///e:/Projects/WorkDataHub/docs/specific/multi-domain/plan-portfolio-code-consistency-analysis.md)
- [Story 5.5.4 - Portfolio Code Extraction](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/) (precedent for shared constants)
- [Story 7.3-6 - Annuity Income Pipeline Alignment](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/) (source of duplication)
