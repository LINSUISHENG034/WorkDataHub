# Validation Report: Story 7.1-12

**Document:** `docs/sprint-artifacts/stories/7.1-12-annuity-plans-schema-backfill-alignment.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2025-12-26T17:30:00+08:00
**Validator:** Claude Opus 4 (Fresh Context)

---

## Summary

- **Overall:** 9/14 passed (64%)
- **Critical Issues:** 4 (🔴 BLOCKING)
- **Enhancement Opportunities:** 3
- **LLM Optimizations:** 2

**⚠️ BLOCKING FINDING:** Production database verification reveals the story's problem statement is **partially incorrect**. Production already has `年金计划号` as PRIMARY KEY (inherently UNIQUE). The issue exists only in the schema definition file.

---

## Critical Discovery: Production vs Schema Definition Mismatch

### Database Verification Results

```sql
-- Verified via PostgreSQL information_schema
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'mapping' AND table_name = '年金计划';

-- RESULT:
-- 年金计划_pkey | PRIMARY KEY  ← ALREADY UNIQUE ON 年金计划号!
```

```sql
-- Duplicate check (AC-3 pre-validation):
SELECT "年金计划号", COUNT(*) FROM mapping."年金计划"
GROUP BY "年金计划号" HAVING COUNT(*) > 1;

-- RESULT: [] (No duplicates exist)
```

### Schema Discrepancy Analysis

| Aspect | Schema Definition (Code) | Production Database |
|--------|--------------------------|---------------------|
| Primary Key | `annuity_plans_id` (auto-increment) | `年金计划号` (VARCHAR) |
| `年金计划号` constraint | Regular INDEX (not unique) | **PRIMARY KEY** (unique) |
| Column `是否统括` | Present | Named `北京统括` |
| ID column name | `annuity_plans_id` | `id` |

**Root Cause:** The production table was created from legacy schema, not from the `generate_create_table_sql()` function. The schema definition file does not match production reality.

---

## Section Results

### 1. Story Structure & Format
Pass Rate: 4/4 (100%)

[✓] **Story Format (As a... I want... So that...)**
Evidence: Lines 7-9 - Complete user story format present.

[✓] **Context Section**
Evidence: Lines 12-17 - Comprehensive context with Priority, Effort, Epic, Source.

[✓] **Acceptance Criteria**
Evidence: Lines 74-99 - 5 ACs with GIVEN/WHEN/THEN format.

[✓] **Tasks / Subtasks**
Evidence: Lines 101-160 - 6 tasks with subtasks, checkboxes, and code snippets.

---

### 2. Technical Accuracy
Pass Rate: 2/6 (33%)

[✗] **FAIL: Root Cause Analysis - Database Reality Mismatch**
Evidence: Story claims (Lines 28-32):
```python
indexes=[
    IndexDef(["年金计划号"]),  # ← 只是普通索引，NOT UNIQUE!
]
```

**ACTUAL DATABASE STATE:**
```sql
PRIMARY KEY: 年金计划_pkey ON (年金计划号)  -- ALREADY UNIQUE!
```

**Impact: CRITICAL** - The problem statement is **correct for schema definition** but **incorrect for production database**. The ON CONFLICT issue only occurs when using `generate_create_table_sql()` for new environments, not in production.

[✗] **FAIL: Migration Approach Will Fail**
Evidence: Task 3 (Lines 125-147) proposes:
```python
op.create_unique_constraint('uq_年金计划_年金计划号', ...)
```

**Reality:** Production already has `年金计划号` as PRIMARY KEY. This migration will fail with "constraint already exists" error.

**Impact: CRITICAL** - Story tasks will fail on production.

[✗] **FAIL: Schema Definition vs Production Not Reconciled**
Evidence: Story assumes schema definition → production pipeline, but production uses different schema.

**Impact: HIGH** - Developer will be confused when:
1. Schema says PK = `annuity_plans_id`, but production PK = `年金计划号`
2. Generated DDL doesn't match production table structure

[⚠] **PARTIAL: AC-3 Data Validation Pre-Check**
Evidence: Task 1 requires duplicate check query.
**Database Result:** No duplicates exist (pre-verified).
**Impact: LOW** - Task is redundant but harmless.

[✓] **IndexDef Supports Unique Constraint**
Evidence: Lines 50-58 correctly reference `core.py` Lines 40-48.

[✓] **FK Backfill Config Verification**
Evidence: Lines 170-171 correctly reference `foreign_keys.yml` Lines 39-84.

---

### 3. Completeness of Dev Notes
Pass Rate: 3/4 (75%)

[✓] **Key Architecture References Table**
Evidence: Lines 166-172 - Comprehensive table with file paths and line numbers.

[✓] **Business Rule Clarification**
Evidence: Lines 174-178 - Explains composite_key vs unique constraint.

[✓] **Rollback Procedure**
Evidence: Lines 180-186 - Clear rollback steps for duplicate scenarios.

[✗] **FAIL: Missing Production Schema Awareness**
Evidence: Story does not acknowledge production differs from code definition.

**Impact: HIGH** - Developer may attempt migration on production that will fail.

---

### 4. LLM-Dev-Agent Optimization
Pass Rate: 2/3 (67%)

[✓] **Actionable Instructions**
Evidence: Tasks have specific code snippets and SQL queries.

[⚠] **PARTIAL: Decision Points Missing**
Evidence: No conditional logic for "if production already has constraint."

[✓] **Clear Structure**
Evidence: Standard story format with logical flow.

---

## Failed Items

### ✗ Critical Issue #1: Problem Statement Invalid for Production
**Location:** Lines 19-47
**Current:** States ON CONFLICT fails because `年金计划号` is not unique.
**Reality:** Production has `年金计划号` as PRIMARY KEY - it IS unique.
**Recommendation:** Reframe as "Schema Definition Alignment" story:
```markdown
**Problem:** Schema definition file does not match production database structure.
- Definition: IndexDef(["年金计划号"]) - regular index
- Production: PRIMARY KEY on 年金计划号 - already unique

**Goal:** Align schema definition with production reality.
```

### ✗ Critical Issue #2: Migration Task Will Fail
**Location:** Lines 125-147 (Task 3)
**Current:** Creates Alembic migration to add UNIQUE constraint.
**Reality:** Constraint already exists; migration will error.
**Recommendation:** Replace Task 3 with:
```markdown
- [ ] **Task 3: Verify Production State (No Migration Needed)**
  - [ ] 3.1 Confirm production has PRIMARY KEY on 年金计划号
  - [ ] 3.2 Document that no migration is required
  - [ ] 3.3 Mark this as "Production Already Correct"
```

### ✗ Critical Issue #3: Schema Definition Has Multiple Discrepancies
**Location:** `infrastructure/schema/definitions/annuity_plans.py`
**Issues Found:**
1. `primary_key="annuity_plans_id"` vs production `年金计划号`
2. Column `是否统括` vs production `北京统括`
3. `id` column naming inconsistency

**Recommendation:** Add Task 0:
```markdown
- [ ] **Task 0: Production Schema Audit (Pre-requisite)**
  - [ ] 0.1 Document actual production table structure
  - [ ] 0.2 Compare with schema definition file
  - [ ] 0.3 Create reconciliation plan (align definition or document legacy status)
```

### ✗ Critical Issue #4: AC-4 Will Fail
**Location:** Lines 92-94
**Current:** "Alembic migration adds constraint successfully"
**Reality:** Migration will fail - constraint exists.
**Recommendation:** Revise AC-4:
```markdown
### AC-4: Schema Definition Alignment
**GIVEN** production already has UNIQUE constraint on 年金计划号
**WHEN** schema definition is updated to match
**THEN** generate_create_table_sql() produces compatible DDL
```

---

## Partial Items

### ⚠ AC-5 Test Commands Incomplete
**Location:** Lines 153-156
**Current:** Tests FK backfill with domain annuity_performance.
**Missing:** Test that verifies `generate_create_table_sql("annuity_plans")` outputs UNIQUE INDEX.

**Add Subtask:**
```markdown
- [ ] 5.4 Verify DDL generation:
  ```python
  from work_data_hub.infrastructure.schema.ddl_generator import generate_create_table_sql
  ddl = generate_create_table_sql("annuity_plans")
  assert "CREATE UNIQUE INDEX" in ddl
  ```
```

---

## Recommendations

### 1. Must Fix: Reframe Story Scope (Critical)

**Current Scope:** Add UNIQUE constraint to production database
**Corrected Scope:** Align schema definition file with production database

**Revised Problem Statement:**
```markdown
### Problem Statement

The schema definition file `annuity_plans.py` does not match production reality:

1. **Definition:** `IndexDef(["年金计划号"])` creates regular index
2. **Production:** `年金计划号` is PRIMARY KEY (already unique)

When developers use `generate_create_table_sql()` to create new test/dev environments,
the generated DDL lacks the UNIQUE constraint that production has, causing ON CONFLICT
operations to fail in non-production environments.

### Solution

Update schema definition to match production:
```diff
-IndexDef(["年金计划号"]),
+IndexDef(["年金计划号"], unique=True),
```

This ensures all environments have consistent schema.
```

### 2. Should Improve: Add Production Verification Steps

Add to Dev Notes:
```sql
-- Production schema verification (run before any changes)
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'mapping' AND table_name = '年金计划'
ORDER BY ordinal_position;

-- Constraint verification
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'mapping' AND table_name = '年金计划';
```

### 3. Consider: Remove Migration Task Entirely

Since production already has the constraint, Task 3 (Alembic Migration) is unnecessary and will fail. Replace with:

```markdown
- [ ] **Task 3: Document Production State**
  - [ ] 3.1 Confirm production schema has correct constraint (verified)
  - [ ] 3.2 Add comment to annuity_plans.py explaining legacy table structure
  - [ ] 3.3 Mark migration as "Not Required - Production Correct"
```

---

## 🤖 LLM Optimization Improvements

### 1. Add Decision Tree

Before Task 1, add:
```markdown
**DECISION POINT:** Before starting, verify production constraint status:
- IF `年金计划号` is already PRIMARY KEY → Skip Task 3, only update schema definition
- IF `年金计划号` has no constraint → Execute full task list including migration
```

### 2. Reduce Redundant SQL Examples

Lines 103-145 repeat similar SQL patterns. Consolidate to single reference section.

### 3. Add Quick Start Summary

At top of story, add:
```markdown
## Quick Start (TL;DR)
1. Verify: Production already has UNIQUE constraint on 年金计划号 ✅
2. Fix: Update `annuity_plans.py` Line 39: `IndexDef(["年金计划号"], unique=True)`
3. Skip: No Alembic migration needed
4. Verify: Run FK backfill test
```

---

## Validation Conclusion

| Category | Count |
|----------|-------|
| ✓ PASS | 9 |
| ⚠ PARTIAL | 1 |
| ✗ FAIL | 4 |
| ➖ N/A | 0 |
| **Total** | 14 |

**Overall Assessment:** Story correctly identifies schema definition gap but **incorrectly assumes production needs modification**. Database verification confirms production already has the required constraint.

**Blocking Status:** 🔴 **BLOCKING** - Story requires revision before implementation.

**Key Fix Required:** Reframe from "Add UNIQUE constraint to database" to "Align schema definition with production."

---

## Interactive Improvement Options

🎯 **STORY CONTEXT QUALITY REVIEW COMPLETE**

**Story:** 7.1-12 - Fix Annuity Plans Schema and Backfill Config Alignment

I found **4 critical issues**, **1 partial issue**, and **2 optimization opportunities**.

### 🚨 CRITICAL ISSUES (Must Fix)

1. **Problem Statement Mismatch** - Production already has UNIQUE constraint
2. **Migration Task Will Fail** - Task 3 Alembic migration unnecessary
3. **Schema Definition Discrepancies** - Multiple differences vs production
4. **AC-4 Invalid** - Migration success criterion won't work

### ⚡ ENHANCEMENT OPPORTUNITIES (Should Add)

1. Add production verification SQL queries
2. Add decision tree for conditional execution
3. Add schema reconciliation documentation

### ✨ OPTIMIZATIONS (Nice to Have)

1. Add Quick Start TL;DR section
2. Reduce redundant SQL examples

---

**IMPROVEMENT OPTIONS:**

Which improvements would you like me to apply to the story?

**Select from the options:**
- **all** - Apply all suggested improvements
- **critical** - Apply only critical issues (reframe story + fix tasks)
- **select** - I'll choose specific numbers
- **none** - Keep story as-is
- **details** - Show me more details about any suggestion

Your choice:
