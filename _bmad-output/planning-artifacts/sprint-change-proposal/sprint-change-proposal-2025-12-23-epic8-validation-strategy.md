# Sprint Change Proposal: Epic 8 Validation Strategy Revision

**Date:** 2025-12-23
**Author:** Link (via Claude)
**Type:** Epic Scope Revision
**Status:** Draft - Pending Approval

---

## Executive Summary

This proposal recommends **replacing the "Golden Dataset" approach** with an **enhanced Classification-Based Validation** strategy that:

1. Builds on existing `cleaner_compare.py` infrastructure
2. Accommodates intentional improvements over Legacy System
3. Provides more maintainable and accurate validation

---

## Problem Statement

### Original Epic 8 Assumption
> "Legacy System output = Correct output (Golden Dataset)"

### Reality
1. **Legacy System has known issues** that New Pipeline intentionally fixes
2. **company_id enrichment** may return different values (both potentially valid)
3. **Data quality improvements** would be flagged as "failures" under Golden Dataset comparison

### Evidence from Retrospective Validation
```
联想集团 (S2001) - 17 rows
├── Legacy company_id:      712180666
└── New Pipeline company_id: 633167472
└── Numeric fields: ✅ ALL MATCH EXACTLY
```

This demonstrates the New Pipeline is calculating correctly, but enrichment differs.

---

## Proposed Solution

### Replace Epic 8 Stories

| Original | Proposed Replacement |
|----------|---------------------|
| 8-1: Golden Dataset Extraction | 8-1: **Validation Rule Engine** |
| 8-2: Automated Reconciliation | 8-2: **Field Classification Framework** |
| 8-3: Parity Test in CI | 8-3: **Regression Detection in CI** |
| 8-4: Divergence Reporting | 8-4: **Divergence Classification & Reporting** |

### New Story Details

#### Story 8-1: Validation Rule Engine
**Goal:** Formalize validation rules that define "correct" behavior

```yaml
validation_rules:
  numeric_fields:
    strategy: zero_tolerance
    fields: [供款, 流失, 投资收益, 期初资产规模, 期末资产规模]

  derived_fields:
    strategy: calculation_match
    fields: [流失_含待遇支付]  # = 流失 + 待遇支付

  enrichment_fields:
    strategy: valid_if_resolved
    fields: [company_id]
    rules:
      - must_not_be_null
      - must_exist_in_公司信息
      # Legacy match is NOT required

  upgrade_fields:
    strategy: allow_difference
    fields: [年金账户号]
    documentation_required: true
```

**Acceptance Criteria:**
- YAML-based rule configuration
- Rules define business logic, not "match Legacy"
- Each field has explicit validation strategy

#### Story 8-2: Field Classification Framework
**Goal:** Extend `cleaner_compare.py` with configurable field classification

```python
class FieldClassification(Enum):
    NUMERIC = "zero_tolerance"      # Must match exactly
    DERIVED = "calculation_match"   # Verify formula correctness
    ENRICHMENT = "valid_resolution" # Valid if resolved correctly
    UPGRADE = "allow_difference"    # Expected to differ
    DEPRECATED = "ignore"           # Legacy-only fields
```

**Acceptance Criteria:**
- Configuration-driven field classification
- Per-domain classification overrides
- Classification rationale documentation

#### Story 8-3: Regression Detection in CI
**Goal:** Detect **unintentional** changes, not Legacy deviations

```yaml
ci_validation:
  trigger: pull_request

  regression_detection:
    # Compare PR branch vs main branch (not vs Legacy)
    baseline: main

    checks:
      - numeric_field_changes: FAIL
      - new_null_values: WARN
      - enrichment_rate_drop: WARN (if > 5%)

  legacy_comparison:
    # Optional, for documentation only
    enabled: true
    report_only: true  # Never fails CI
```

**Acceptance Criteria:**
- CI compares against main branch, not Legacy
- Legacy comparison is reporting-only
- Clear distinction between regression and improvement

#### Story 8-4: Divergence Classification & Reporting
**Goal:** Generate actionable divergence reports

```markdown
## Divergence Report: 2025-10

### Summary
| Category | Count | Action |
|----------|-------|--------|
| ✅ Numeric Match | 37,127 | None |
| ✅ Expected Upgrade | 17 | Document |
| ⚠️ Review Required | 3 | Manual review |
| ❌ Regression | 0 | Block release |

### Expected Upgrades (17 rows)
- 联想集团 company_id: New Pipeline uses EQC latest data
- Rationale: Legacy used stale company mapping

### Review Required (3 rows)
- [Details with investigation prompts]
```

**Acceptance Criteria:**
- Automated classification of divergences
- "Expected Upgrade" category for intentional improvements
- "Review Required" for investigation queue

---

## Comparison: Original vs Proposed

| Aspect | Original (Golden Dataset) | Proposed (Classification-Based) |
|--------|---------------------------|--------------------------------|
| Source of Truth | Legacy System | Business Rules |
| Handles Improvements | ❌ Flags as failure | ✅ Documents as upgrade |
| Maintenance | High (refresh Golden Dataset) | Low (update rules) |
| CI Integration | Brittle | Robust |
| False Positives | High | Low |

---

## Migration Path

### Phase 1: Enhance Existing Tools
1. Add `--classification-config` to `cleaner_compare.py`
2. Define field classifications for `annuity_performance`
3. Update Epic 8 Readiness Assessment

### Phase 2: Formalize Validation Rules
1. Create `validation_rules.yml` schema
2. Implement rule engine in `infrastructure/validation/`
3. Integrate with existing domain validators

### Phase 3: CI Integration
1. Add regression detection workflow
2. Legacy comparison as optional reporting
3. Divergence classification in PR comments

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Over-permissive rules hide real bugs | Strict classification review, numeric always zero-tolerance |
| Rule maintenance burden | Start minimal, expand as needed |
| Team unfamiliarity | Clear documentation, incremental rollout |

---

## Recommendation

**Approve this Sprint Change Proposal** to revise Epic 8 from "Golden Dataset Extraction" to "Classification-Based Validation".

### Benefits
1. ✅ Accommodates intentional improvements
2. ✅ Builds on existing infrastructure (`cleaner_compare.py`)
3. ✅ Lower maintenance burden
4. ✅ More accurate regression detection
5. ✅ Better alignment with actual business requirements

---

## Appendix: Fields Classification Matrix (Draft)

| Field | Classification | Rationale |
|-------|---------------|-----------|
| 月度 | EXACT | Must match period |
| 业务类型 | EXACT | Core dimension |
| 计划代码 | EXACT | Primary key component |
| 期初资产规模 | NUMERIC | Financial data |
| 期末资产规模 | NUMERIC | Financial data |
| 供款 | NUMERIC | Financial data |
| 流失 | NUMERIC | Financial data |
| 待遇支付 | NUMERIC | Financial data |
| 投资收益 | NUMERIC | Financial data |
| 流失_含待遇支付 | DERIVED | = 流失 + 待遇支付 |
| company_id | ENRICHMENT | EQC resolution |
| 年金账户号 | UPGRADE | May use new format |
| 年金账户名 | UPGRADE | Normalized names |

---

**Document Version:** 1.0
**Next Action:** PM Review and Approval
