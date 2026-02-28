---
stepsCompleted: ['step-01-load-context', 'step-02-discover-tests', 'step-03f-aggregate-scores', 'step-04-generate-report']
lastStep: 'step-04-generate-report'
lastSaved: '2026-02-28'
workflowType: 'testarch-test-review'
inputDocuments:
  - '_bmad/tea/config.yaml'
  - '_bmad/tea/testarch/tea-index.csv'
  - '_bmad/tea/testarch/knowledge/test-quality.md'
  - '_bmad/tea/testarch/knowledge/data-factories.md'
  - '_bmad/tea/testarch/knowledge/test-levels-framework.md'
  - '_bmad/tea/testarch/knowledge/test-healing-patterns.md'
  - '_bmad/tea/testarch/knowledge/selective-testing.md'
---

# Test Quality Review: slice_tests/

**Quality Score**: 74/100 (C - Acceptable with improvements needed)
**Review Date**: 2026-02-28
**Review Scope**: directory
**Reviewer**: Link / TEA Agent

---

Note: This review audits existing tests; it does not generate tests.
Coverage mapping and coverage gates are out of scope here. Use `trace` for coverage decisions.

## Context Summary

- **Stack**: backend (Python/pytest)
- **Test Framework**: pytest
- **Directory**: `tests/slice_tests/`
- **Files Discovered**: 10 test files + conftest.py + generate_slices.py
- **Knowledge Fragments Loaded**: test-quality, data-factories, test-levels-framework, test-healing-patterns, selective-testing

## Step 2: Test Inventory

| File | Lines | Classes | Methods | Fixtures Used |
|------|-------|---------|---------|---------------|
| conftest.py | 399 | 0 | 9 helpers + 7 fixtures | — |
| generate_slices.py | 222 | 0 | 3 helpers | — |
| test_a_file_discovery.py | 278 | 6 (A-1→A-6) | 11 | annuity_performance_slice_df, annual_award_slice_df, annual_loss_slice_df, tmp_path |
| test_b_annuity_performance_pipeline.py | 337 | 13 (B-1→B-13) | 16 | annuity_performance_slice_df, disabled_eqc_config |
| test_c_annual_award_pipeline.py | 284 | 13 (C-1→C-13) | 16 | annual_award_slice_df, disabled_eqc_config |
| test_d_annual_loss_pipeline.py | 212 | 13 (D-1→D-13) | 14 | annual_loss_slice_df, disabled_eqc_config |
| test_e_backfill_engine.py | 359 | 12 (E-1→E-12) | 12 | — |
| test_e_backfill_per_domain.py | 246 | 7 (E-13→E-19) | 17 | — |
| test_f_load_upsert.py | 190 | 5 (F-1→F-5) | 8 | — |
| test_g_snapshot_status.py | 129 | 6 (G-1→G-6) | 8 | — |

**Totals**: 10 test files, ~2,656 lines, 75 test classes, ~102 test methods

## Step 3: Quality Evaluation (Parallel)

### Overall Score

| Dimension | Score | Grade | Weight |
|-----------|-------|-------|--------|
| Determinism | 74/100 | C | 30% |
| Isolation | 84/100 | B | 30% |
| Maintainability | 71/100 | C | 25% |
| Performance | 62/100 | D | 15% |
| **Weighted Overall** | **74/100** | **C** | — |

Coverage is excluded from `test-review` scoring. Use `trace` for coverage analysis.

### Violation Summary

| Severity | Count | Dimensions |
|----------|-------|------------|
| HIGH | 11 | Determinism(1), Maintainability(6), Performance(4) |
| MEDIUM | 15 | Determinism(2), Isolation(2), Maintainability(5), Performance(6) |
| LOW | 16 | Determinism(3), Isolation(3), Maintainability(5), Performance(5) |
| **TOTAL** | **42** | — |

---

## Executive Summary

**Overall Assessment**: Acceptable with improvements needed

**Recommendation**: Approve with Comments

### Key Strengths

- Excellent test organization: 75 classes across 7 phases (A→G) with clear numbered naming (TestB1ColumnMapping, TestE7AggregateMaxBy)
- Strong determinism foundations: all `_make_ctx()` helpers use fixed `datetime(2025, 10, 1)`, all fallback data is hardcoded, no `random` module, no `time.sleep()`, no unmocked external DB/API calls
- Good isolation: all DataFrame fixtures are function-scoped, tests use `.copy()` before mutation, mock fixtures create fresh instances per test
- Comprehensive domain coverage: all 3 pipeline domains (annuity_performance, annual_award, annual_loss) tested step-by-step with matching phase structure
- Clean mock strategy: `CompanyIdResolver` uses `disabled_eqc_config`, loader uses `conn=None` for plan-only mode — no real DB needed

### Key Weaknesses

- Significant code duplication: `test_d` is a near-complete clone of `test_c` (7 of 13 classes identical), `_make_ctx()` duplicated across 3 files despite existing `make_pipeline_context` fixture
- Performance bottleneck: function-scoped Excel fixtures re-read files on every test invocation; YAML configs re-parsed per test method in test_e and test_g
- 3 files exceed 300-line threshold: conftest.py (399), test_b (337), test_e_backfill_engine (359)
- One live `datetime.now()` call in `test_g_snapshot_status.py` without mocking
- Silent exception swallowing (`except Exception: pass`) in conftest fixtures and test_a

### Summary

The slice test suite demonstrates strong architectural foundations — phased organization, deterministic data, clean mocking patterns, and good isolation. The primary drag on the score comes from maintainability (extensive copy-paste between test_c/test_d and duplicated helpers) and performance (function-scoped fixtures that re-read Excel/YAML on every test invocation). Fixing the top 5 issues would raise the score from 74 to ~88 (grade B+).

---

## Critical Issues (Must Fix)

### 1. Massive code duplication between test_c and test_d

**Severity**: HIGH (Maintainability)
**Location**: `test_d_annual_loss_pipeline.py:1-212`

7 of 13 test classes in test_d are functionally identical to test_c counterparts (D-2/C-2, D-3/C-3, D-4/C-4, D-5/C-5, D-7/C-7, D-10/C-10, D-12/C-12), differing only in the import path (`annual_loss.constants` vs `annual_award.constants`).

**Recommended Fix**: Parametrize shared tests over domain:

```python
@pytest.mark.parametrize("domain", ["annual_award", "annual_loss"])
class TestBusinessTypeNormalization:
    def test_normalization(self, domain):
        mod = importlib.import_module(f"work_data_hub.domain.{domain}.constants")
        assert mod.BUSINESS_TYPE_NORMALIZATION["受托"] == "企年受托"
```

Keep only D-6 (流失日期), D-9 (cleansing domain), D-13 (考核标签 drop) as standalone.

### 2. Function-scoped Excel fixtures re-read on every test

**Severity**: HIGH (Performance)
**Location**: `conftest.py:296-335`

`annuity_performance_slice_df`, `annual_award_slice_df`, `annual_loss_slice_df` are function-scoped but read Excel via `pd.read_excel` on every invocation. The data is read-only — tests already call `.copy()` before mutation.

**Recommended Fix**:

```python
@pytest.fixture(scope="session")
def annuity_performance_slice_df() -> pd.DataFrame:
    path = FIXTURE_ROOT / "annuity_performance" / "slice_规模收入数据.xlsx"
    _ensure_slice_fixtures()
    return pd.read_excel(path, sheet_name="规模明细", engine="openpyxl")
```

### 3. Repeated YAML parsing in test_e and test_g

**Severity**: HIGH (Performance)
**Location**: `test_e_backfill_per_domain.py:16`, `test_g_snapshot_status.py:17`

`_load_configs()` re-parses YAML+Pydantic on every test method (~16 calls in test_e_backfill_per_domain). `_get_evaluator()` re-creates StatusEvaluator 8 times in test_g.

**Recommended Fix**:

```python
@pytest.fixture(scope="module")
def annuity_perf_fk_configs():
    return load_foreign_keys_config(domain="annuity_performance")
```

### 4. Duplicated `_make_ctx()` helper across 3 files

**Severity**: HIGH (Maintainability)
**Location**: `test_b:16`, `test_c:16`, `test_d:19`

Identical helper copy-pasted despite `make_pipeline_context` fixture already existing in conftest.py (line 381).

**Recommended Fix**: Delete `_make_ctx()` from all 3 files, use the existing fixture:

```python
def test_mapping_step(self, annuity_performance_slice_df, make_pipeline_context):
    ctx = make_pipeline_context("annuity_performance")
    # ...
```

### 5. Unmocked `datetime.now()` in test_g

**Severity**: HIGH (Determinism)
**Location**: `test_g_snapshot_status.py:102-107`

`test_get_current_period_format()` calls `get_current_period()` which uses the live system clock. The assertion only checks format (`len==6`, `isdigit`), not the actual value.

**Recommended Fix**:

```python
from unittest.mock import patch
from datetime import datetime

def test_get_current_period_format(self):
    with patch("work_data_hub.customer_mdm.snapshot_refresh.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 10, 15)
        period = get_current_period()
        assert period == "202510"
```

---

## Recommendations (Should Fix)

### 6. Module-level side effect in conftest.py

**Severity**: MEDIUM (Isolation)
**Location**: `conftest.py:283`

`_ensure_slice_fixtures()` runs at import time, creating Excel files as a side effect of importing conftest. This couples test collection to filesystem writes.

**Recommended Fix**: Move into a session-scoped autouse fixture:

```python
@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures():
    _ensure_slice_fixtures()
```

### 7. Silent exception swallowing in fixture loaders

**Severity**: MEDIUM (Determinism)
**Location**: `conftest.py:312-315`, `conftest.py:328-332`, `test_a_file_discovery.py`

`except Exception: pass` hides real failures (corrupt Excel, missing sheets, permission errors). Tests silently degrade instead of failing fast.

**Recommended Fix**: Catch only the expected exception:

```python
try:
    frames.append(pd.read_excel(path, sheet_name=s, engine="openpyxl"))
except ValueError:  # sheet not found
    pass
```

### 8. E-18/E-19 structural duplication in test_e_backfill_per_domain

**Severity**: MEDIUM (Maintainability)
**Location**: `test_e_backfill_per_domain.py:180-246`

E-18 (annual_award) and E-19 (annual_loss) are structurally identical, differing only in domain string.

**Recommended Fix**: Parametrize over domain:

```python
@pytest.mark.parametrize("domain", ["annual_award", "annual_loss"])
class TestBackfillPerDomain:
    def test_config_loads(self, domain):
        configs = load_foreign_keys_config(domain=domain)
        assert len(configs) > 0
```

### 9. Lazy imports inside test methods

**Severity**: MEDIUM (Performance)
**Location**: All test files (test_b through test_g)

Every test method re-executes `from work_data_hub.domain...` imports. While Python caches modules, the import machinery overhead accumulates across 102 methods.

**Recommended Fix**: Move imports to module top-level. Lazy imports are only justified when the import itself has heavy side effects.

### 10. TOCTOU race in `_ensure_excel_file()`

**Severity**: LOW (Isolation)
**Location**: `conftest.py:257-264`

`path.exists()` check followed by `ExcelWriter` is a time-of-check-to-time-of-use race under parallel pytest-xdist. Unlikely in current single-process usage but fragile.

**Recommended Fix**: Use atomic write-to-temp + rename, or accept the race with a comment.

---

## Best Practices Found

1. **Fixed timestamps everywhere**: All `_make_ctx()` helpers use `datetime(2025, 10, 1)` — no flaky clock dependencies (except test_g issue #5)
2. **Phased test organization (A→G)**: Clear numbered naming convention maps directly to pipeline steps, making failures immediately traceable
3. **Deterministic fallback data**: `_fallback_annuity_df()`, `_fallback_award_sheets()`, `_fallback_loss_sheets()` provide hardcoded DataFrames — no random data, no external dependencies
4. **Clean mock boundaries**: `disabled_eqc_config` + `conn=None` pattern cleanly isolates tests from DB/EQC without complex mock setup
5. **Copy-before-mutate discipline**: Tests consistently call `.copy()` before modifying fixture DataFrames
6. **Marker registration**: `pytest_configure` registers `slice_test` marker, enabling selective test execution via `-m slice_test`

---

## Knowledge Base References

| Fragment | Applied To |
|----------|-----------|
| test-quality.md | Scoring dimensions, severity thresholds, grade boundaries |
| data-factories.md | Evaluated fallback DataFrame builders against factory patterns |
| test-levels-framework.md | Classified slice tests as integration-level (real data, mocked I/O) |
| test-healing-patterns.md | Assessed self-healing potential of fixture generation strategy |
| selective-testing.md | Validated marker-based selective execution (`-m slice_test`) |

---

## Next Steps

### Immediate (before next merge)

1. **Fix #5**: Mock `datetime.now()` in test_g — eliminates the only non-deterministic test
2. **Fix #4**: Replace `_make_ctx()` with `make_pipeline_context` fixture in test_b/c/d
3. **Fix #7**: Replace `except Exception: pass` with `except ValueError: pass` in conftest

### Short-term (next sprint)

4. **Fix #2**: Promote Excel fixtures to session scope — biggest performance win
5. **Fix #3**: Cache YAML configs in module-scoped fixtures for test_e/test_g
6. **Fix #1**: Parametrize shared test_c/test_d classes over domain

### Follow-up

7. **Fix #6**: Move `_ensure_slice_fixtures()` into session-scoped autouse fixture
8. **Fix #8**: Parametrize E-18/E-19 over domain
9. **Fix #9**: Hoist lazy imports to module level across all test files

### Projected Score After Fixes

| Scenario | Score | Grade |
|----------|-------|-------|
| Current | 74/100 | C |
| After Immediate fixes (#4, #5, #7) | ~79/100 | C+ |
| After Short-term fixes (#1, #2, #3) | ~88/100 | B+ |
| After all fixes | ~93/100 | A |

---

## Decision

**Approve with Comments**

**Rationale**: The slice test suite provides meaningful verification of all 3 pipeline domains with strong determinism and isolation foundations. No blocking defects exist — all 5 critical issues are maintainability/performance improvements, not correctness bugs. The single determinism issue (#5) is low-risk (format-only assertion). The suite is safe to rely on for regression detection today, with the recommended fixes tracked as tech debt.
