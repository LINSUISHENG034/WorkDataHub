# Story 4.10: Refactor Annuity Performance to Standard Domain Pattern

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | 4.10 |
| **Epic** | Epic 4: Annuity Performance Domain Migration (MVP) |
| **Status** | Drafted |
| **Created** | 2025-11-30 |
| **Origin** | Sprint Change Proposal: Annuity Performance Refactoring |
| **Priority** | Critical |
| **Estimate** | 1-2 days |

---

## User Story

**As a** data engineer,
**I want** the annuity_performance module refactored to use shared generic steps and configuration-driven transformations,
**So that** the module is maintainable (<1,000 lines), serves as the reference implementation for Epic 9, and demonstrates the "Standard Domain Pattern".

---

## Strategic Context

> **This is the FINAL refactoring Story for annuity_performance.**
>
> After Story 4.10, the annuity module MUST serve as the **Reference Implementation** for Epic 9 (Growth Domains). This Story transforms the module from 3,700 lines of custom boilerplate to a clean, configuration-driven implementation using the generic steps from Story 1.12.

### Why This Story Exists

**Problem:** Stories 4.7-4.9 reduced annuity_performance from 4,942 → 3,710 lines (25% reduction), but the module still contains significant boilerplate:
- Custom step classes wrapping simple DataFrame operations (column renaming, value mapping)
- Configuration data hardcoded in step logic instead of separate config files
- Verbose implementations that could use shared generic steps

**Root Cause:** Story 1.12 (generic steps) was not available when Epic 4 was implemented. Domain-specific steps were created for operations that should use framework-provided generic steps.

**Solution:** Refactor annuity_performance to use Story 1.12 generic steps:
- Move static mappings to `domain/annuity_performance/config.py`
- Replace custom mapping/replacement steps with `DataFrameMappingStep`, `DataFrameValueReplacementStep`
- Keep only domain-specific business logic in custom steps

### Impact on Epic 9

After this refactor, Epic 9 domain migrations will:
- Use annuity_performance as reference implementation
- Copy config-driven pattern (mappings in `config.py`, generic steps in pipeline)
- Achieve <1,000 lines per domain (vs. 3,700 lines without this refactor)

---

## Acceptance Criteria

### AC-4.10.1: Module Line Count Reduction (QUANTIFIED)

**Requirement:** Total Python code in `annuity_performance/` MUST be < 1,000 lines

**Baseline (Before Story 4.10):** 3,710 lines

**Target:** < 1,000 lines (73% reduction)

**Verification Command:**
```bash
find src/work_data_hub/domain/annuity_performance -name "*.py" -exec cat {} + | wc -l
```

**Pass Criteria:** Output < 1000

**Breakdown Estimate:**
- `config.py`: ~150 lines (all mappings and constants)
- `pipeline_steps.py`: ~200 lines (domain-specific steps only)
- `service.py`: ~300 lines (orchestration)
- `schemas.py`: ~250 lines (Pandera schemas)
- `models.py`: ~100 lines (Pydantic models)
- **Total:** ~1,000 lines

---

### AC-4.10.2: Configuration File Created (CONFIG.PY)

**Requirement:** All static mappings moved to `domain/annuity_performance/config.py`

**Must Include:**
```python
# Column name mappings (Chinese → English)
COLUMN_MAPPING = {
    '月度': 'report_date',
    '计划代码': 'plan_code',
    '客户名称': 'customer_name',
    '期初资产规模': 'beginning_assets',
    '期末资产规模': 'ending_assets',
    '投资收益': 'investment_income',
    '年化收益率': 'annualized_return'
}

# Value replacement mappings
PLAN_CODE_CORRECTIONS = {
    'OLD_CODE_A': 'NEW_CODE_A',
    'OLD_CODE_B': 'NEW_CODE_B'
}

BUSINESS_TYPE_MAPPING = {
    '旧值1': '新值1',
    '旧值2': '新值2'
}

INSTITUTION_CODE_MAPPING = {
    '机构A': 'INST_001',
    '机构B': 'INST_002'
}

# Expected columns for validation
BRONZE_EXPECTED_COLUMNS = [
    '月度', '计划代码', '客户名称', '期初资产规模',
    '期末资产规模', '投资收益', '年化收益率'
]

GOLD_OUTPUT_COLUMNS = [
    'report_date', 'plan_code', 'company_id', 'beginning_assets',
    'ending_assets', 'investment_income', 'annualized_return'
]
```

**Verification:**
```bash
test -f src/work_data_hub/domain/annuity_performance/config.py && echo "PASS" || echo "FAIL"
grep -q "COLUMN_MAPPING" src/work_data_hub/domain/annuity_performance/config.py && echo "PASS" || echo "FAIL"
```

**Pass Criteria:** File exists, contains all required configuration dictionaries

---

### AC-4.10.3: Generic Steps Used in Pipeline (IMPORT REQUIRED)

**Requirement:** `pipeline_steps.py` MUST import and use generic steps from Story 1.12

**Must Import:**
```python
from work_data_hub.domain.pipelines.steps import (
    DataFrameMappingStep,
    DataFrameValueReplacementStep,
    DataFrameCalculatedFieldStep,
    FieldCleanupStep
)
```

**Must Use in Pipeline Construction:**
```python
# Example pipeline using generic steps
from .config import COLUMN_MAPPING, PLAN_CODE_CORRECTIONS

annuity_pipeline = Pipeline("annuity_performance_standard_pattern")

# Use generic mapping step instead of custom RenameColumnsStep
annuity_pipeline.add_step(DataFrameMappingStep(COLUMN_MAPPING))

# Use generic replacement step instead of custom PlanCodeCleansingStep (if simple mapping)
annuity_pipeline.add_step(DataFrameValueReplacementStep({'plan_code': PLAN_CODE_CORRECTIONS}))

# Keep domain-specific steps for complex business logic
annuity_pipeline.add_step(CompanyIdResolutionStep(enrichment_service))

# Use generic calculated field step for simple math
annuity_pipeline.add_step(DataFrameCalculatedFieldStep({
    'asset_change': lambda df: df['ending_assets'] - df['beginning_assets']
}))
```

**Verification Command:**
```bash
grep -E "^from work_data_hub\.domain\.pipelines\.steps import|^from \.\.pipelines\.steps import" \
  src/work_data_hub/domain/annuity_performance/pipeline_steps.py
```

**Pass Criteria:** Import statement found, at least 2 generic steps used in pipeline

---

### AC-4.10.4: Custom Steps Reduced (ONLY DOMAIN-SPECIFIC LOGIC)

**Requirement:** `pipeline_steps.py` contains ONLY domain-specific steps (complex business logic that cannot use generic steps)

**Must Keep (Domain-Specific Business Logic):**
- `CompanyIdResolutionStep` - Enrichment integration with fallback logic
- `PlanCodeCleansingStep` - ONLY if it contains complex cleansing logic beyond simple mapping
- Any step with cross-field validation or complex conditional logic

**Must Delete (Replaced by Generic Steps):**
- Any step that only renames columns → Use `DataFrameMappingStep`
- Any step that only replaces values → Use `DataFrameValueReplacementStep`
- Any step that only calculates simple math → Use `DataFrameCalculatedFieldStep`

**Verification:**
```bash
# Count custom step classes (should be <=5)
grep -c "^class.*Step" src/work_data_hub/domain/annuity_performance/pipeline_steps.py
```

**Pass Criteria:** ≤5 custom step classes remaining (domain-specific only)

---

### AC-4.10.5: 100% Functional Parity (NO REGRESSIONS)

**Requirement:** Refactored pipeline produces IDENTICAL output to pre-refactor version

**Verification Strategy:**
1. Run pre-refactor pipeline on 202412 dataset, save output to CSV
2. Apply refactoring changes
3. Run post-refactor pipeline on same dataset
4. Compare outputs (row count, column names, values)

**Verification Command:**
```bash
# Pre-refactor
uv run python -c "
from work_data_hub.domain.annuity_performance.service import process_annuity_performance
result_before = process_annuity_performance('202412')
result_before.output_data.to_csv('baseline_202412.csv', index=False)
print(f'Before: {len(result_before.output_data)} rows')
"

# Post-refactor (after changes)
uv run python -c "
from work_data_hub.domain.annuity_performance.service import process_annuity_performance
result_after = process_annuity_performance('202412')
result_after.output_data.to_csv('refactored_202412.csv', index=False)
print(f'After: {len(result_after.output_data)} rows')
"

# Compare
diff baseline_202412.csv refactored_202412.csv && echo "IDENTICAL" || echo "DIVERGENCE"
```

**Pass Criteria:** Row count identical, CSV files identical (or explain acceptable differences)

---

### AC-4.10.6: All Tests Pass (REGRESSION GATE)

**Requirement:** All existing annuity_performance tests pass after refactoring

**Verification Command:**
```bash
uv run pytest tests/ -k "annuity_performance" -v --tb=short
```

**Pass Criteria:** Exit code 0, all tests pass

**Expected Test Update:**
- Update tests that mock custom steps (now using generic steps)
- Update imports if step classes renamed/deleted
- Verify test coverage maintained (>=58% baseline from Story 4.9)

---

### AC-4.10.7: Reference Implementation Documentation

**Requirement:** Documentation updated to position annuity_performance as Epic 9 reference

**Must Update:**

1. **README.md (or docs/domains/annuity_performance.md):**
   - Add section: "Standard Domain Pattern Reference Implementation"
   - Document config.py usage pattern
   - Show before/after comparison (3,700 lines → <1,000 lines)
   - Link to Architecture Decision #9

2. **docs/architecture.md:**
   - Update Architecture Decision #9 with annuity_performance as example
   - Include code snippets showing config-driven pattern
   - Reference this as template for Epic 9

**Verification:**
```bash
grep -q "Standard Domain Pattern" docs/domains/annuity_performance.md && echo "PASS" || echo "FAIL"
grep -q "Decision #9" docs/architecture.md && echo "PASS" || echo "FAIL"
```

**Pass Criteria:** Documentation updated, reference implementation clearly marked

---

## Technical Tasks

### Task 1: Create Configuration File (AC-4.10.2)

- [ ] Create `src/work_data_hub/domain/annuity_performance/config.py`
- [ ] Extract all hardcoded mappings from `pipeline_steps.py`, `service.py`
- [ ] Organize into logical sections (column mappings, value replacements, constants)
- [ ] Add docstrings explaining each configuration section
- [ ] Validate configuration structure (no typos, consistent formatting)

### Task 2: Refactor Pipeline Steps to Use Generic Steps (AC-4.10.3, AC-4.10.4)

- [ ] Audit existing `pipeline_steps.py`:
  - Identify steps that can be replaced by generic steps
  - Identify steps that must remain custom (domain-specific logic)
- [ ] Replace simple mapping/replacement steps:
  - Column renaming → `DataFrameMappingStep(COLUMN_MAPPING)`
  - Value replacements → `DataFrameValueReplacementStep(VALUE_MAPPING)`
  - Simple calculations → `DataFrameCalculatedFieldStep(CALC_FIELDS)`
- [ ] Update pipeline construction in `service.py` or `pipeline_steps.py`
- [ ] Delete obsolete custom step classes
- [ ] Update imports to use generic steps from `work_data_hub.domain.pipelines.steps`

### Task 3: Baseline Capture (BEFORE REFACTORING)

- [ ] Run pipeline on 202412 dataset
- [ ] Save output to `baseline_202412.csv`
- [ ] Record line count: `find ... | wc -l > baseline_lines.txt`
- [ ] Record test coverage baseline

### Task 4: Update Tests

- [ ] Identify tests that mock deleted custom steps
- [ ] Update mocks to use generic steps
- [ ] Update imports in test files
- [ ] Add tests for `config.py` (validate configuration structure)
- [ ] Run all tests, fix failures

### Task 5: Functional Parity Verification (AC-4.10.5)

- [ ] Run refactored pipeline on 202412 dataset
- [ ] Save output to `refactored_202412.csv`
- [ ] Compare baseline vs. refactored outputs
- [ ] Investigate any differences (acceptable vs. regression)
- [ ] Document comparison results

### Task 6: Documentation Update (AC-4.10.7)

- [ ] Update `docs/domains/annuity_performance.md`:
  - Add "Standard Domain Pattern Reference Implementation" section
  - Document config.py pattern
  - Show before/after metrics (line count, complexity)
- [ ] Update `docs/architecture.md`:
  - Enhance Architecture Decision #9 with annuity example
  - Include code snippets
  - Mark as template for Epic 9
- [ ] Update main README.md (if applicable)

### Task 7: Final Verification (ALL ACs)

- [ ] Verify line count < 1,000: `find ... | wc -l`
- [ ] Verify config.py exists and complete
- [ ] Verify generic steps imported and used
- [ ] Verify ≤5 custom steps remaining
- [ ] Verify all tests pass
- [ ] Verify functional parity (CSV comparison)
- [ ] Verify documentation updated

---

## Code Review Checklist

**Reviewer MUST verify each item before approval:**

| # | Check | Verification Method | Pass? |
|---|-------|---------------------|-------|
| 1 | Line count < 1,000 | `find ... wc -l` | [ ] |
| 2 | `config.py` exists with all mappings | File review | [ ] |
| 3 | Generic steps imported from Story 1.12 | Import statement check | [ ] |
| 4 | ≤5 custom step classes (domain-specific only) | `grep -c "^class.*Step"` | [ ] |
| 5 | Functional parity (CSV comparison) | `diff baseline refactored` | [ ] |
| 6 | All tests pass | `pytest -k annuity_performance` | [ ] |
| 7 | Test coverage >= baseline (58%) | `pytest --cov` | [ ] |
| 8 | Documentation updated (reference implementation) | File review | [ ] |
| 9 | No hardcoded mappings in step classes | Code review | [ ] |
| 10 | Pipeline uses config-driven pattern | Code review | [ ] |

**PR cannot be merged unless ALL checks pass.**

---

## Anti-Pattern Warnings

> **The following patterns are PROHIBITED in this Story:**

| Anti-Pattern | Why It's Wrong | What To Do Instead |
|--------------|----------------|-------------------|
| ❌ Keep custom step "just in case" | Defeats purpose, maintains bloat | Delete if replaced by generic step |
| ❌ Hardcode mappings in step classes | Violates config-driven pattern | Move to `config.py` |
| ❌ Create new custom steps for simple operations | Ignores generic steps from Story 1.12 | Use `DataFrameMappingStep`, etc. |
| ❌ Skip functional parity check | Risk of silent regressions | Run CSV comparison, verify identical |
| ❌ "Refactor later" mindset | This IS the final refactoring | Complete to specification NOW |

---

## Dev Notes

### Dependency on Story 1.12

**CRITICAL:** This Story REQUIRES Story 1.12 (Generic Steps) to be completed first.

**Dependency Check:**
```bash
# Verify Story 1.12 generic steps exist
test -f src/work_data_hub/domain/pipelines/steps/mapping_step.py && echo "Story 1.12 DONE" || echo "Story 1.12 PENDING"
```

**If Story 1.12 not complete:**
- Block this Story until Story 1.12 merged
- Do NOT proceed with refactoring

### Code Size Reduction Breakdown

**Current (Before Story 4.10):** 3,710 lines

**Target (After Story 4.10):** <1,000 lines

**Reduction Strategy:**
| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| `pipeline_steps.py` | ~923 lines | ~200 lines | -723 lines (-78%) |
| `config.py` (new) | 0 lines | ~150 lines | +150 lines |
| `service.py` | ~388 lines | ~300 lines | -88 lines (-23%) |
| `schemas.py` | ~607 lines | ~250 lines | -357 lines (-59%) |
| `models.py` | ~100 lines | ~100 lines | 0 lines |
| **Total** | **3,710 lines** | **~1,000 lines** | **-2,710 lines (-73%)** |

**Key Reduction:**
- Most of `pipeline_steps.py` deleted (custom steps → generic steps)
- `schemas.py` simplified (remove wrapper functions, consolidated)

### Example: Before vs. After

**Before (Custom Step Class):**
```python
# pipeline_steps.py (80 lines for one step)
class RenameColumnsStep:
    def __init__(self):
        self.mapping = {
            '月度': 'report_date',
            '计划代码': 'plan_code',
            '客户名称': 'customer_name'
        }

    def execute(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        df = df.copy()
        df.rename(columns=self.mapping, inplace=True)
        return df
```

**After (Config-Driven):**
```python
# config.py
COLUMN_MAPPING = {
    '月度': 'report_date',
    '计划代码': 'plan_code',
    '客户名称': 'customer_name'
}

# pipeline_steps.py (3 lines)
from work_data_hub.domain.pipelines.steps import DataFrameMappingStep
from .config import COLUMN_MAPPING

pipeline.add_step(DataFrameMappingStep(COLUMN_MAPPING))
```

**Lines Saved:** 80 → 3 = -77 lines per mapping step (-96%)

### Legacy Parity Test Dataset

**Dataset:** 202412 (December 2024 data)

**Why 202412?**
- Most recent historical data
- Known baseline from Stories 4.1-4.9
- Comprehensive test (all edge cases encountered in past runs)

**Comparison Method:**
```bash
# Generate baseline
uv run python -m work_data_hub.domain.annuity_performance.service --month=202412 --output=baseline_202412.csv

# Generate refactored
uv run python -m work_data_hub.domain.annuity_performance.service --month=202412 --output=refactored_202412.csv

# Compare
diff -u baseline_202412.csv refactored_202412.csv
```

**Acceptable Differences:**
- Column order (if semantically equivalent)
- Floating point precision differences (e.g., 0.1234 vs 0.12340)

**Unacceptable Differences:**
- Row count mismatch
- Missing/extra columns
- Value differences (data loss/corruption)

---

## Definition of Done

- [ ] All 7 Technical Tasks completed
- [ ] All 7 Acceptance Criteria verified
- [ ] Code Review Checklist fully passed
- [ ] No anti-patterns present
- [ ] Line count < 1,000
- [ ] Functional parity verified (CSV comparison)
- [ ] All tests pass
- [ ] Documentation updated
- [ ] PR merged to main branch
- [ ] Sprint status updated to `done`

---

## References

- **Sprint Change Proposal:** `docs/sprint-change-proposal-2025-11-30_fix_bloat.md`
- **Story 1.12:** `docs/sprint-artifacts/stories/1-12-implement-standard-domain-generic-steps.md` (DEPENDENCY)
- **Epic Definition:** `docs/epics.md` (Epic 4: Annuity Performance Domain Migration)
- **Architecture Decision #9:** `docs/architecture.md` (Standard Domain Architecture Pattern)
- **Previous Story:** `docs/sprint-artifacts/stories/4-9-annuity-module-decomposition-for-reusability.md`
- **Generic Steps Location:** `src/work_data_hub/domain/pipelines/steps/` (Story 1.12)

---

## Dev Agent Record

### Context Reference

- To be created: `docs/sprint-artifacts/stories/4-10-refactor-annuity-performance-to-standard-domain-pattern.context.xml`

### Debug Log

(To be filled during implementation)

### Completion Notes

(To be filled after implementation)

---

*Story drafted by Bob (SM) based on Sprint Change Proposal 2025-11-30*
*🤖 Generated with [Claude Code](https://claude.com/claude-code)*
