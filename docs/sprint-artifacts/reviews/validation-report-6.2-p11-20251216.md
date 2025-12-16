# Validation Report: Story 6.2-P11

**Document:** [6.2-p11-guimo-mingxi-field-derivation-fix.md](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/6.2-p11-guimo-mingxi-field-derivation-fix.md)
**Checklist:** [create-story/checklist.md](file:///e:/Projects/WorkDataHub/_bmad/bmm/workflows/4-implementation/create-story/checklist.md)
**Date:** 2025-12-16T21:22:48+08:00

---

## Summary

- **Overall:** 22/26 passed (85%)
- **Critical Issues:** 2
- **Enhancement Opportunities:** 3

---

## Section Results

### 1. Story Structure & INVEST Compliance

Pass Rate: 6/6 (100%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | **Independent** | Story is self-contained, focused on field derivation fix (L1-8) |
| ✓ PASS | **Negotiable** | Technical approach specified but implementation details flexible (L65-74) |
| ✓ PASS | **Valuable** | Directly enables P2-tier company_id lookup, matches Legacy behavior (L15-16) |
| ✓ PASS | **Estimable** | Clear effort estimate: ~2.5 hours (L6) |
| ✓ PASS | **Small** | 3 phases, well-scoped (L58-81) |
| ✓ PASS | **Testable** | Specific ACs with Given/When/Then format (L32-53) |

---

### 2. Acceptance Criteria Quality

Pass Rate: 4/5 (80%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | **AC1: Pipeline Field Derivation** | Clear input/output specification (L35-37) |
| ✓ PASS | **AC2: enrichment_index Restoration** | Data migration criteria defined (L39-42) |
| ⚠ PARTIAL | **AC3: company_id Resolution Rate** | ">50%" is vague; should specify exact expected percentage based on Legacy data |
| ✓ PASS | **AC4: CLI Token Auto-Refresh** | Behavior specified (L49-52) |
| ✓ PASS | **Testability** | All ACs have measurable outcomes |

**Impact:** Without baseline data, developers cannot objectively verify "50%" threshold.

---

### 3. Technical Specification Accuracy

Pass Rate: 5/7 (71%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | **Code location correct** | `pipeline_builder.py` confirmed (L89) |
| ✓ PASS | **Step ordering correct** | After Step 9, before Step 12 (L65-71) |
| ✗ FAIL | **Code snippet accuracy** | Proposed code has edge case: `df["集团企业客户号"].copy()` may fail if column doesn't exist after Step 9 transforms |
| ✓ PASS | **Legacy reference accurate** | [data_cleaner.py:251-279](file:///e:/Projects/WorkDataHub/legacy/annuity_hub/data_handler/data_cleaner.py#L251-L279) verified in issue analysis |
| ✓ PASS | **Files to modify list** | Correct files identified (L87-92) |
| ⚠ PARTIAL | **Constants update missing** | `年金账户号` is in `DEFAULT_ALLOWED_GOLD_COLUMNS` but story doesn't mention verifying column inclusion |
| ✗ FAIL | **Step numbering conflict** | Story says "Step 9b" but current code has Steps 1-12; should be Step 10 or insert between existing |

---

### 4. Command Reference Verification

Pass Rate: 4/4 (100%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | **alembic commands** | Correct syntax, verified (L97-100) |
| ✓ PASS | **Migration scripts exist** | [migrate_full_legacy_db.py](file:///e:/Projects/WorkDataHub/scripts/migrations/enrichment_index/migrate_full_legacy_db.py) verified |
| ✓ PASS | **CLI command** | `--dry-run --debug` flags correct (L103) |
| ✓ PASS | **Environment setup** | Uses `uv run --env-file .wdh_env` per project-context.md |

---

### 5. Anti-Pattern Prevention

Pass Rate: 3/4 (75%)

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | **No wheel reinvention** | Reuses existing `CalculationStep` infrastructure |
| ✓ PASS | **Correct library usage** | Uses pandas operations consistent with existing steps |
| ✓ PASS | **File location correct** | `pipeline_builder.py` is the right file |
| ⚠ PARTIAL | **Missing import check** | Story doesn't verify `run_get_token_auto_qr` import path exists |

---

## 🚨 Critical Issues (Must Fix)

### Issue 1: Code Snippet Has Defensive Check Bug

**Location:** Story L65-71

**Problem:** The proposed lambda:
```python
lambda df: df["集团企业客户号"].copy()
if "集团企业客户号" in df.columns else pd.Series([None] * len(df))
```

This is **identical** to Step 9's pattern, but critically:
- Step 9 **modifies** `集团企业客户号` in-place (lstrip "C")
- Step 9b runs **after** Step 9
- The column **will exist** at this point (Step 9 creates it if missing)

**Recommendation:** Simplify to:
```python
CalculationStep({
    "年金账户号": lambda df: df.get("集团企业客户号", pd.Series([None] * len(df))).copy(),
}),
```

### Issue 2: Step Numbering Causes Confusion

**Location:** Story L65

**Problem:** "Step 9b" naming is non-standard. Current pipeline has Steps 1-12 sequentially.

**Recommendation:** Either:
1. Renumber as "Step 9.5" (fractional)
2. Insert as new Step 10 and renumber subsequent steps
3. Use descriptive comment only: `# Derive 年金账户号 (after 集团企业客户号 cleaning)`

---

## ⚠ Partial Items (Should Improve)

### 1. AC3 Threshold Ambiguity

**What's Missing:** Baseline company_id resolution rate from Legacy 202510 data.

**Recommendation:** Add note:
> Query Legacy DB for actual resolution rate: `SELECT COUNT(CASE WHEN company_id NOT LIKE 'IN_%' THEN 1 END) * 100.0 / COUNT(*) FROM ...`

### 2. Token Auto-Refresh Import Path

**What's Missing:** Story doesn't verify `auto_eqc_auth.py` module path.

**Evidence:** Issue analysis L187 shows correct path:
```python
from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr
```

**Recommendation:** Add to Technical Notes section.

### 3. Unit Test Specifics

**What's Missing:** Exact test method names and assertions.

**Recommendation:** Add:
```python
def test_annuity_account_number_derived_correctly():
    """集团企业客户号 'C12345' → 年金账户号 '12345'"""
    
def test_annuity_account_number_handles_missing_column():
    """Missing 集团企业客户号 → 年金账户号 is None"""
```

---

## ✨ Optimization Suggestions

### 1. Token Efficiency

Current story is ~130 lines. Consider:
- Merge Phase 1 tasks into single "Data Layer Setup" task
- Remove redundant Legacy Reference section (already in issue analysis)

### 2. Developer Guardrails

Add explicit warning:
> [!CAUTION]
> Do NOT modify Step 12 (DropStep). The fix is to add a NEW step, not change existing deletion logic.

---

## Recommendations Summary

| Priority | Item | Action |
|----------|------|--------|
| 🔴 Must Fix | Code snippet defensive check | Simplify lambda, remove redundant column check |
| 🔴 Must Fix | Step numbering | Use consistent numbering (Step 10 or comment-only) |
| 🟡 Should Improve | AC3 threshold | Add baseline query or Legacy comparison |
| 🟡 Should Improve | Import path verification | Add `auto_eqc_auth.py` import to Technical Notes |
| 🟢 Consider | Token efficiency | Condense Phase 1 tasks |

---

**Generated By:** BMAD Scrum Master Validation Workflow
**Report Location:** `docs/sprint-artifacts/stories/validation-report-6.2-p11-20251216.md`
