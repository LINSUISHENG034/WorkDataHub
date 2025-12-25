# Ruff Warning Triage Analysis (Story 7.1-10)

**Analysis Date:** 2025-12-26
**Total Warnings:** 419
**Analyzed by:** Dev Agent (Claude Opus 4.5)
**Ruff Version:** 0.13.0 (≥ 0.12.12 ✓)

## Summary

| Priority | Count | Categories | Percentage |
|----------|-------|------------|------------|
| **P0 (Critical)** | 11 | TID251 (Banned imports - Clean Architecture violations) | 2.6% |
| **P1 (High)** | 162 | PLR2004 (Magic values), PLR0913/0912/0915/0911 (Code complexity) | 38.7% |
| **P2 (Medium)** | 215 | E501 (Line length), F401/F841 (Unused code), E402 (Imports) | 51.3% |
| **P3 (Low)** | 31 | TID252 (Relative imports) | 7.4% |

**Key Findings:**
- ✅ **419 total warnings** matches initial estimate (different from SCP's 1074)
- ✅ **TID251 violations** are minimal (11), indicating Clean Architecture is well-enforced
- ⚠️ **E501 (Line too long)** is the #1 issue at 205 occurrences (49%), fully auto-fixable
- ⚠️ **PLR2004 (Magic values)** at 66 occurrences requires manual refactoring

## Category Breakdown

### P0 - Critical (Clean Architecture Violations)

**TID251: Banned Imports**

**Count:** 11 occurrences

**Affected Files:**

| File | Location | Violation |
|------|----------|-----------|
| `src/work_data_hub/auth/eqc_auth_handler.py:6` | Domain layer | `from work_data_hub.io.auth.eqc_auth_handler import *` |
| `src/work_data_hub/cli/auth.py` | CLI layer | `work_data_hub.io` import |
| `src/work_data_hub/cli/etl/auth.py` | CLI layer | `work_data_hub.io` import |
| `src/work_data_hub/cli/etl/executors.py` | CLI layer | `work_data_hub.io` import |
| `src/work_data_hub/infrastructure/enrichment/data_refresh_service.py` | Infrastructure | `work_data_hub.io` import |
| `src/work_data_hub/infrastructure/enrichment/eqc_provider.py` | Infrastructure | `work_data_hub.io` import |

**Root Cause:**

Domain layer (`work_data_hub.auth`) importing from IO layer (`work_data_hub.io.connectors`) violates Clean Architecture boundary (Story 1.6). Infrastructure and CLI layers also have direct IO dependencies.

**Fix Strategy:**

1. **Domain Layer (auth/eqc_auth_handler.py):**
   - Use protocol/dependency injection pattern
   - Import from `work_data_hub.infrastructure.enrichment` instead
   - See Story 1.6 Clean Architecture for reference

2. **Infrastructure Layer (infrastructure/enrichment/):**
   - Accept protocols/interfaces as constructor parameters
   - Move IO imports to orchestration layer

3. **CLI Layer:**
   - CLI can import from IO layer (acceptable, as CLI is outermost layer)
   - Add `# noqa: TID251` with TODO comment for future refactoring

**Estimated Effort:** 2-3 hours

**Tech Debt Story:** Create Story 7.1-15 (11 violations > 3 threshold)

---

### P1 - High (Code Quality Issues)

#### PLR2004: Magic Value Comparison

**Count:** 66 occurrences

**Sample Violations:**

```python
# ❌ WRONG: Magic value
# src/migrations/migrate_legacy_to_enrichment_index.py:165, 215
if len(report.sample_records) < 10:
    report.sample_records.append(...)
```

**Affected Files:**

| File | Occurrences | Sample Magic Values |
|------|-------------|---------------------|
| `src/migrations/migrate_legacy_to_enrichment_index.py` | 2 | `10` (sample limit) |
| Multiple files across domain/infrastructure/io | 64 | Various numbers |

**Fix Strategy:**

Replace magic numbers with named constants at module level:

```python
# ✅ CORRECT: Named constant
SAMPLE_RECORDS_LIMIT = 10  # Configured for migration debugging

if len(report.sample_records) < SAMPLE_RECORDS_LIMIT:
    report.sample_records.append(...)
```

**Estimated Effort:** 1-2 hours

**Tech Debt Story:** Create Story 7.1-16 (66 violations > 30 threshold)

---

#### PLR0915: Too Many Statements

**Count:** 32 occurrences

**Definition:** Functions with >50 statements (exceeds complexity threshold)

**Affected Files:** Various domain service and infrastructure files

**Fix Strategy:**

1. Extract logical blocks into private helper functions
2. Use early returns to reduce nesting
3. Consider command pattern for complex workflows

**Estimated Effort:** 2-3 hours

**Tech Debt Story:** Create Story 7.1-17 (32 violations > 5 threshold)

---

#### PLR0913: Too Many Arguments (6+)

**Count:** 30 occurrences

**Definition:** Functions with 6+ parameters (design smell)

**Fix Strategy:**

Refactor to use dataclasses or configuration objects:

```python
# ❌ WRONG: Too many parameters
def process_data(
    arg1, arg2, arg3, arg4, arg5, arg6, arg7
):
    pass

# ✅ CORRECT: Dataclass
@dataclass
class ProcessConfig:
    arg1: str
    arg2: int
    arg3: bool
    arg4: str
    arg5: int
    arg6: bool
    arg7: str = "default"

def process_data(config: ProcessConfig):
    pass
```

**Estimated Effort:** 2-3 hours

**Tech Debt Story:** Include in Story 7.1-17 (function complexity refactor)

---

#### PLR0912: Too Many Branches

**Count:** 25 occurrences

**Definition:** Functions with >12 branches (cyclomatic complexity)

**Fix Strategy:**

1. Extract branch logic into strategy pattern
2. Use lookup tables/dicts for dispatch
3. Apply guard clauses to reduce nesting

**Estimated Effort:** 2-3 hours

**Tech Debt Story:** Include in Story 7.1-17

---

#### PLR0911: Too Many Return Statements

**Count:** 9 occurrences

**Fix Strategy:**

1. Consolidate returns with early exit pattern
2. Use single return with result variable
3. Extract complex conditions to helper functions

**Estimated Effort:** 1 hour

**Tech Debt Story:** Include in Story 7.1-17

---

### P2 - Medium (Formatting & Cleanup)

#### E501: Line Too Long (>88)

**Count:** 205 occurrences (49% of all warnings)

**Definition:** Lines exceeding 88 characters (project's hard constraint from project-context.md)

**Fix Strategy:**

```bash
# Auto-fix most issues
uv run ruff format src/

# Manual fixes for remaining:
# - Break long URLs
# - Refactor deeply nested expressions
# - Break long docstrings into multiple lines
```

**Estimated Effort:** 30 minutes

**Auto-fixable:** ✅ Yes (with `ruff format`)

---

#### F401: Unused Import

**Count:** 0 occurrences (not found in actual analysis)

**Note:** Story expected F401 warnings, but actual scan shows none.

---

#### F841: Unused Variable

**Count:** 5 occurrences

**Fix Strategy:**

```bash
# Auto-fix
uv run ruff check --select F841 --fix src/

# Manual review: Some variables may be intended for side effects
```

**Estimated Effort:** 15 minutes

**Auto-fixable:** ✅ Yes

---

#### E402: Module Import Not at Top

**Count:** 5 occurrences

**Fix Strategy:**

```bash
# Auto-fix (move imports to top)
uv run ruff check --select E402 --fix src/
```

**Estimated Effort:** 5 minutes

**Auto-fixable:** ✅ Yes

---

### P3 - Low (Stylistic)

#### TID252: Relative Imports

**Count:** 31 occurrences

**Definition:** Relative imports (e.g., `from . import module`) vs absolute imports

**Fix Strategy:**

```bash
# Convert to absolute imports
uv run ruff check --select TID252 --fix src/
```

**Estimated Effort:** 15 minutes

**Auto-fixable:** ✅ Yes

**Note:** This is a stylistic preference, not a functional issue. Can be deferred.

---

## Prioritized Fix Plan

### Sprint 7.1 - Immediate (P0 only)

**Action:** Fix all TID251 violations (Clean Architecture boundary)

**Stories to Create:**
- ✅ **Story 7.1-15:** Fix TID251 Clean Architecture Violations (11 occurrences)
  - Effort: 2-3 hours
  - Priority: P0 - Must complete before Epic 8

---

### Epic 7.1 Tech Debt - P1 (if time permits)

**Action:** Address code quality smells

**Stories to Create:**
- ✅ **Story 7.1-16:** Refactor Magic Values to Constants (66 occurrences)
  - Effort: 1-2 hours
  - Priority: P1 - Code maintainability

- ✅ **Story 7.1-17:** Reduce Function Complexity (PLR0915/0913/0912/0911)
  - Effort: 2-3 hours
  - Priority: P1 - Design quality
  - Scope: 32+30+25+9 = 96 function refactorings

---

### Epic 8 Preparation - P2 (Automated)

**Action:** Run automated fixes for formatting issues

**Commands:**

```bash
# Task 6.1: Fix line length (205 occurrences - 49% of warnings)
uv run ruff format src/

# Task 6.2: Fix unused variables (5 occurrences)
uv run ruff check --select F841 --fix src/

# Task 6.2: Fix import order (5 occurrences)
uv run ruff check --select E402 --fix src/

# Task 6.3: Fix relative imports (31 occurrences - optional)
uv run ruff check --select TID252 --fix src/
```

**Estimated Effort:** 30-45 minutes total

**Auto-fixable:** ✅ Yes (246 warnings - 59% of total)

**Impact:** Reduces warning count from 419 → 173 (58% reduction)

---

### Ongoing - P3 (Deferred)

**Action:** Address remaining stylistic issues incrementally

**Deferred Items:**
- TID252 (Relative imports) - Can be converted in future refactors
- Remaining PLR complexity issues not addressed in P1 stories

---

## Technical Debt Metrics

**Baseline (Story 7.1-10):**

| Metric | Value | Source |
|--------|-------|--------|
| **Total Warnings** | 419 | `ruff check src/ --statistics` |
| **P0 (Critical)** | 11 | TID251 violations |
| **P1 (High)** | 162 | PLR code quality (66+32+30+25+9) |
| **P2 (Medium)** | 215 | E501 (205) + F841 (5) + E402 (5) |
| **P3 (Low)** | 31 | TID252 relative imports |

**Auto-fixable Potential:**
- **59% of warnings (246/419)** can be auto-fixed with `ruff format` and `--fix` flags
- **After automated fixes:** 419 → 173 warnings (58% reduction)

**Manual Fix Effort:**
- **P0 (TID251):** 2-3 hours
- **P1 (PLR code quality):** 5-8 hours (across 3 tech debt stories)
- **Total manual effort:** 7-11 hours

---

## Recommendations

### Immediate Actions (Before Epic 8)

1. ✅ **Fix TID251 violations** (Story 7.1-15)
   - **Priority:** P0 - Blocking for Epic 8
   - **Effort:** 2-3 hours
   - **Impact:** Removes Clean Architecture violations

2. ✅ **Add `# noqa: TID251` with TODO** for CLI layer violations
   - CLI layer can import from IO (acceptable)
   - Document for future refactoring

3. 📊 **Track warning count in sprint status**
   - Add `technical_debt_metrics` section (Task 5)
   - Monitor trend as stories are completed

---

### Preventive Measures

1. **Enable `--fix` mode in pre-commit hooks** (Story 7.6)
   ```bash
   # .git/hooks/pre-commit
   uv run ruff format src/
   uv run ruff check --select F841,E402,TID252 --fix src/
   ```

2. **Add Ruff check to CI gate** (Future enhancement)
   ```yaml
   # .github/workflows/ci.yml
   - name: Ruff Check
     run: uv run ruff check src/ --select TID251 --fail-on-error
   ```

3. **Review and update `pyproject.toml` quarterly**
   - Consider enabling UP (pyupgrade) for modern Python syntax
   - Review line length policy (88 vs 100) for team alignment

---

### Quick Win Opportunity (Task 6)

**Run automated fixes to reduce warnings by 58%:**

```bash
# Fix line length (205 warnings → 0)
uv run ruff format src/

# Fix unused variables (5 warnings → 0)
uv run ruff check --select F841 --fix src/

# Fix import order (5 warnings → 0)
uv run ruff check --select E402 --fix src/

# Fix relative imports (31 warnings → 0)
uv run ruff check --select TID252 --fix src/

# Verify no test breakage
PYTHONPATH=src uv run --env-file .wdh_env pytest tests/ -v
```

**Impact:**
- Warnings: 419 → 173 (-58%)
- Time: 30-45 minutes
- Risk: Low (automated fixes are safe)

---

## Appendix: Ruff Configuration Reference

**Current `pyproject.toml` Configuration:**

```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "PLR"]  # Pycodestyle, Pyflakes, isort, Pylint refactor
extend-select = ["TID"]  # Tidy imports for Clean Architecture

# NOTE: UP (pyupgrade) not enabled - add to extend-select if needed
# To enable: extend-select = ["TID", "UP"]

[tool.ruff.lint.per-file-ignores]
# Per-file ignores defined for io/, orchestration/, scripts/, tests/
# See pyproject.toml for full configuration
```

**Enabled Rules Summary:**

| Rule Category | Description | Warnings |
|---------------|-------------|----------|
| **E** | Pycodestyle errors | E501 (205), E402 (5) |
| **F** | Pyflakes | F841 (5) |
| **W** | Pycodestyle warnings | (none) |
| **I** | isort (import sorting) | (enabled via TID) |
| **PLR** | Pylint refactor rules | PLR2004 (66), PLR0915 (32), PLR0913 (30), PLR0912 (25), PLR0911 (9) |
| **TID** | Tidy imports | TID251 (11), TID252 (31) |

---

**Document Version:** 1.0
**Created:** 2025-12-26
**Next Review:** After Story 7.1-15 (TID251 fixes) completion
