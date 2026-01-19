# Validation Report: Story 7.6-6

**Document:** `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md`  
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2026-01-18T09:30+08:00

---

## Summary

- **Overall:** 18/24 passed (75%)
- **Critical Issues:** 3
- **Partial Items:** 4

---

## Section Results

### 1. Structure & Metadata

**Pass Rate: 4/4 (100%)**

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Status field present | Line 3: `Status: ready-for-dev` |
| ✓ PASS | "At a Glance" table complete | Lines 5-14: Goal, Impact, Risk, Dependencies, Effort, Rollback all specified |
| ✓ PASS | User Story format | Lines 16-20: Clear As/I Want/So That structure |
| ✓ PASS | Acceptance Criteria numbered | Lines 22-66: AC-1 through AC-5 clearly defined |

---

### 2. Technical Accuracy

**Pass Rate: 5/8 (63%)**

| Mark | Item | Evidence |
|------|------|----------|
| ✗ FAIL | **Migration file path** | Line 245: `src/work_data_hub/io/schema/migrations/versions/008_...` |
| | **Impact:** Actual path is `io/schema/migrations/versions/008_...` (no `src/work_data_hub/` prefix) |
| ✗ FAIL | **Config file existence** | Line 334: `config/customer_mdm.yaml` — **[NEW FILE] Create this file** |
| | **Impact:** Story says "Create this file during Task 1" but this is buried in Dev Notes. Should be explicit Task. |
| ✗ FAIL | **`--no-post-hooks` CLI flag** | Line 91-93: Task 4 says "Add `--no-post-hooks` flag" to `main.py` |
| | **Impact:** `main.py` analyzed (491 lines) - flag does NOT exist. Implementation needed. |
| ✓ PASS | Table DDL matches spec | Lines 116-164 match `customer-plan-contract-specification.md` v0.6 §2.1 exactly |
| ✓ PASS | FK constraints correct | Lines 146-149: FK to `customer."年金客户"` (migrated schema), FK to `mapping."产品线"` |
| ✓ PASS | Post-ETL Hook pattern | Lines 192-224: Hook registry and execution patterns well-documented |
| ✓ PASS | Reference SQL provided | Lines 263-287: Initial population SQL with proper UPSERT pattern |
| ⚠ PARTIAL | Previous story learnings | Lines 248-259: Basic learnings captured but missing specific file path patterns |

---

### 3. Disaster Prevention

**Pass Rate: 4/6 (67%)**

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Wheel reinvention prevention | Lines 92-95: References existing CLI patterns and migration patterns |
| ⚠ PARTIAL | **Library/version specification** | Lines 196-198: `dataclass` used but no `typing` imports shown |
| | **Missing:** Python version constraint, specific sqlalchemy/dagster versions for hooks |
| ✓ PASS | Code reuse opportunities | Line 77: `sync_contract_status()` reused by both hook and manual CLI |
| ⚠ PARTIAL | **Existing code integration** | Line 220-224: Hook execution insertion point says "line 379 in executors.py" |
| | **Actual:** `executors.py` is 391 lines. Line 379 is inside error handling. Should be ~line 381 post-success |
| ✓ PASS | Rollback strategy | Line 14: `DROP TABLE customer.customer_plan_contract CASCADE;` |
| ✓ PASS | Idempotency design | Lines 52, 81: UPSERT pattern with ON CONFLICT DO NOTHING |

---

### 4. LLM Agent Optimization

**Pass Rate: 5/6 (83%)**

| Mark | Item | Evidence |
|------|------|----------|
| ✓ PASS | Task breakdown granular | Lines 68-104: 6 tasks with clear subtasks |
| ✓ PASS | File structure diagram | Lines 226-246: Complete file tree with [NEW]/[MODIFY] markers |
| ✓ PASS | CLI examples provided | Lines 289-302: All 3 CLI usage patterns shown |
| ✓ PASS | Validation queries | Lines 304-330: 5 SQL queries for post-implementation validation |
| ⚠ PARTIAL | **Config file content** | Lines 336-344: YAML shown but missing strategic_threshold/whitelist details |
| | **Missing:** Full config structure with all fields (see spec v0.6 §8.4) |
| ✓ PASS | References section | Lines 355-361: 5 source document links provided |

---

## Failed Items

### ✗ F1: Migration File Path Incorrect (CRITICAL)

**Story says:**
```
src/work_data_hub/io/schema/migrations/versions/008_create_customer_plan_contract.py
```

**Actual location:**
```
io/schema/migrations/versions/008_create_customer_plan_contract.py
```

**Recommendation:** Update File Structure diagram (line 244-245) and Task 1 to use correct path without `src/work_data_hub/` prefix.

---

### ✗ F2: Config File Not Explicit Task

**Current:** Config file creation mentioned only in Dev Notes (line 334-347) with `> [!TIP]` marker.

**Problem:** LLM developer may miss this requirement completely.

**Recommendation:** Add explicit subtask under Task 1:
```markdown
- [ ] Create `config/customer_mdm.yaml` with placeholder values (see Dev Notes)
```

---

### ✗ F3: `--no-post-hooks` Flag Implementation Gap

**Story claims:** Task 4 adds `--no-post-hooks` flag to `main.py`.

**Reality check:** `main.py` (491 lines) was analyzed - this flag does NOT exist in current codebase.

**Recommendation:** No change needed in story - this correctly identifies new work. But add explicit arg parsing code sample:

```python
# Add to main.py around line 175 (after --skip-facts)
parser.add_argument(
    "--no-post-hooks",
    action="store_true",
    default=False,
    help="Disable Post-ETL hooks (e.g., customer MDM sync)",
)
```

---

## Partial Items

### ⚠ P1: Previous Story Learnings Incomplete

**Current (lines 248-259):** Basic learnings about sheet names and CLI patterns.

**Missing:**
- Migration numbering pattern: `00X_xxx.py` where X is sequential (next is 008)
- Customer schema already exists from Story 7.6-0
- `customer.年金客户` FK target moved from `mapping` to `customer` schema (see `foreign_keys.yml` lines 160-164)

**Recommendation:** Add to Previous Story Intelligence:
```markdown
**Schema context:**
- Customer schema created in Story 7.6-0 (no need to CREATE SCHEMA)
- `customer.年金客户` table already exists (FK target)
- Next migration number: 008 (after 007_add_customer_tags_jsonb.py)
```

---

### ⚠ P2: Hook Integration Line Number Inaccurate

**Story says (line 220):** Insert after line 379 in `_execute_single_domain()`.

**Actual `executors.py`:**
- Line 379 is: `console.print(f"   {clean_message}")`
- Line 381 is: `return 0 if result.success else 1`

**Correct insertion point:** After line 381 (inside the `if result.success:` block, before the final return).

**Recommendation:** Update Dev Notes:
```python
# Insert BEFORE line 381 in _execute_single_domain(), inside the `if result.success:` block:
if not getattr(args, 'no_post_hooks', False):
    from .hooks import run_post_etl_hooks
    run_post_etl_hooks(domain=domain, period=getattr(args, 'period', None))
```

---

### ⚠ P3: Config File Structure Incomplete

**Current (lines 336-344):** Shows basic YAML with 3 fields.

**Spec v0.6 §8.4 shows:** Same 3 fields, but Story Note says "Full strategic customer logic implemented in Story 7.6-9".

**Gap:** No explanation of which fields are placeholders vs. active for Story 7.6-6.

**Recommendation:** Add clarification:
```markdown
> [!NOTE]
> For Story 7.6-6, only `status_year` is actively used. `strategic_threshold` and 
> `whitelist_top_n` are reserved for Story 7.6-9 (Index & Trigger Optimization).
```

---

### ⚠ P4: Missing `typing` Import in Code Samples

**Code samples (lines 196-214):** Use `List`, `Callable`, `Optional` without showing imports.

**Recommendation:** Add import line:
```python
from dataclasses import dataclass
from typing import Callable, List, Optional
```

---

## Recommendations

### 1. Must Fix (Critical Failures)

| # | Issue | Action |
|---|-------|--------|
| F1 | Migration path wrong | Change `src/work_data_hub/io/...` → `io/schema/migrations/...` |
| F2 | Config file buried | Add explicit subtask to Task 1 |
| F3 | N/A - correctly identifies new work | Add arg parser code sample for clarity |

### 2. Should Improve (Important Gaps)

| # | Issue | Action |
|---|-------|--------|
| P1 | Previous story intel incomplete | Add schema context and migration numbering |
| P2 | Line number inaccurate | Update to line 381 with correct block context |
| P3 | Config fields unclear | Add NOTE explaining active vs. placeholder fields |
| P4 | Missing imports | Add typing imports to code samples |

### 3. Consider (Minor Improvements)

| # | Suggestion |
|---|------------|
| 1 | Add `contract_sync.py` function signature sample in Dev Notes |
| 2 | Add explicit SQL for verifying FK constraint integrity post-migration |
| 3 | Add note about running `alembic upgrade head` after migration creation |

---

## Validation Methodology

This validation was performed by:

1. Loading Story 7.6-6 and systematically comparing against create-story checklist
2. Cross-referencing with:
   - Sprint Change Proposal 2026-01-10 (especially §4.1.2, §4.2)
   - customer-plan-contract-specification.md v0.6
   - Previous Story 7.6-5
   - project-context.md
   - Actual codebase files:
     - `executors.py` (391 lines)
     - `main.py` (491 lines)
     - `io/schema/migrations/versions/` (7 existing migrations)
     - `config/foreign_keys.yml` (FK config for customer schema)
3. Identifying discrepancies between story claims and actual project state
4. Prioritizing issues by impact on LLM developer agent success
