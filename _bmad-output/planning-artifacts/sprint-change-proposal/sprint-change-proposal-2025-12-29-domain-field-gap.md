# Sprint Change Proposal: Domain Field Gap Fix

> **Date:** 2025-12-29  
> **Author:** Link (via Correct-Course Workflow)  
> **Status:** DRAFT  
> **Scope:** Minor - Development Team

---

## 1. Issue Summary

### Problem Statement

The `annuity_income` domain is missing 4 fields that exist in the source Excel data but are not defined in the Domain Schema or Pydantic models. These fields are present and working correctly in `annuity_performance`.

### Discovery Context

- **Trigger Document:** `docs/specific/multi-domain/domain-field-gap-summary.md`
- **Related Epic:** 7.3 (Multi-Domain Consistency Fixes) - completed
- **Root Cause:** Original `annuity_income` implementation focused on financial fields, omitting descriptive "name" fields

### Evidence

**annuity_income - Missing Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `计划名称` | VARCHAR(255) | Plan name (human-readable) |
| `组合类型` | VARCHAR(255) | Portfolio type |
| `组合名称` | VARCHAR(255) | Portfolio name |
| `机构名称` | VARCHAR(255) | Institution name |

> [!NOTE]
> The gap summary document incorrectly listed `annuity_performance` as also missing fields. Analysis confirms `annuity_performance` **already has all 8 fields** correctly implemented.

---

## 2. Impact Analysis

### Epic Impact

- **Epic 7.3 (Completed):** Multi-domain consistency fixes - Story 7.3-1/2/3 addressed `客户名称`/`company_id` nullability and shared validators
- **Epic 7.4 (NEW):** Required to address this field gap
- **Epic 8 (Blocked):** Testing infrastructure - can proceed after 7.4 fix

### Story Impact

- **New Story Required:** 7.4-1 - Add missing fields to `annuity_income` domain

### Artifact Conflicts: None

- PRD unaffected (data completeness enhancement)
- Architecture aligned (follows Domain Registry pattern)
- Alembic migrations auto-generated from DDL generator

### Technical Impact

| Component                                             | Change Required                   |
| ----------------------------------------------------- | --------------------------------- |
| `infrastructure/schema/definitions/annuity_income.py` | Add 4 ColumnDef entries           |
| `domain/annuity_income/models.py`                     | Add fields to In/Out models       |
| Database                                              | Alembic migration for new columns |

---

## 3. Recommended Approach

### Selected Path: Option 1 - Direct Adjustment

**Rationale:**

1. **Low Effort:** Only 2 files to modify, standard field additions
2. **Low Risk:** All new fields are nullable, backward compatible
3. **No Timeline Impact:** Can complete in single story
4. **Proven Pattern:** Identical to existing `annuity_performance` implementation

### Effort Estimate: **Low** (1 story, ~2-3 hours)

### Risk Level: **Low** (nullable fields, no breaking changes)

### Alternatives Considered

- **Option 2 (Rollback):** Not applicable - no completed work to revert
- **Option 3 (MVP Review):** Not needed - field addition enhances, doesn't change MVP

---

## 4. Detailed Change Proposals

### 4.1 Story Definition (Under Existing Epic 7.3)

> [!NOTE]
> Per user feedback, adding as **Story 7.3-4** under existing Epic 7.3 (Multi-Domain Consistency Fixes) instead of creating new Epic 7.4.

```yaml
7.3-4-annuity-income-field-completeness:
  name: "Add Missing Fields to annuity_income"
  description: "Add 4 missing descriptive fields discovered during multi-domain testing"
  parent_epic: Epic 7.3 (Multi-Domain Consistency Fixes)
  priority: P1
  blocking: Epic 8 (for complete test data coverage)
```

### 4.2 Story 7.3-4: Add Missing Fields to annuity_income

**Acceptance Criteria:**

1. Schema definition includes 4 new ColumnDef entries
2. Pydantic models (In/Out) include 4 new Optional fields
3. Database migration adds columns to existing table
4. Unit tests verify field presence in schema
5. ETL pipeline correctly passes through fields from Excel

**Files to Modify:**

#### [MODIFY] annuity_income.py (Schema)

Path: `src/work_data_hub/infrastructure/schema/definitions/annuity_income.py`

```diff
 ColumnDef("机构代码", ColumnType.STRING, max_length=255),
+# Story 7.4-1: Add missing descriptive fields
+ColumnDef("计划名称", ColumnType.STRING, nullable=True, max_length=255),
+ColumnDef("组合类型", ColumnType.STRING, nullable=True, max_length=255),
+ColumnDef("组合名称", ColumnType.STRING, nullable=True, max_length=255),
+ColumnDef("机构名称", ColumnType.STRING, nullable=True, max_length=255),
 ColumnDef(
     "固费",
```

#### [MODIFY] models.py (Domain)

Path: `src/work_data_hub/domain/annuity_income/models.py`

**AnnuityIncomeIn:** Add 4 Optional fields after `机构代码`:

```python
计划名称: Optional[str] = Field(None, description="Plan name (计划名称)")
组合类型: Optional[str] = Field(None, description="Portfolio type (组合类型)")
组合名称: Optional[str] = Field(None, description="Portfolio name (组合名称)")
机构名称: Optional[str] = Field(None, description="Institution name (机构名称)")
```

**AnnuityIncomeOut:** Add 4 Optional fields after `机构代码`:

```python
计划名称: Optional[str] = Field(None, max_length=255, description="Plan name")
组合类型: Optional[str] = Field(None, max_length=255, description="Portfolio type")
组合名称: Optional[str] = Field(None, max_length=255, description="Portfolio name")
机构名称: Optional[str] = Field(None, max_length=255, description="Institution name")
```

---

## 5. Implementation Handoff

### Change Scope: **Minor**

Direct implementation by development team.

### Handoff Recipients

| Role             | Responsibility                          |
| ---------------- | --------------------------------------- |
| **Dev Team**     | Implement Story 7.4-1, create migration |
| **Scrum Master** | Update sprint-status.yaml with Epic 7.4 |

### Verification Plan

#### Automated Tests

```bash
# Run domain unit tests
PYTHONPATH=src uv run pytest tests/unit/domain/annuity_income/ -v

# Run schema validation tests
PYTHONPATH=src uv run pytest tests/unit/infrastructure/schema/ -v -k annuity_income

# Verify migration generates correct DDL
PYTHONPATH=src uv run python -c "from work_data_hub.infrastructure.sql import ddl_generator; print(ddl_generator.generate_create_table_ddl('annuity_income'))"
```

#### Manual Verification

1. After migration: Verify 4 new columns exist in `business.收入明细` table
2. Run ETL with sample Excel: Confirm new fields populated correctly

### Success Criteria

- [ ] All 4 fields present in schema definition
- [ ] All 4 fields present in Pydantic models
- [ ] Database table includes new columns
- [ ] Existing tests pass
- [ ] New field values correctly read from Excel

---

## 6. Document Corrections

The original `domain-field-gap-summary.md` contains inaccuracies that should be corrected:

1. **Status:** Change from `✅ 已修复` to `⏳ 待修复 (annuity_income only)`
2. **annuity_performance Section:** Mark as `✅ 已实现` (all 8 fields present)
3. **下一步行动:** Update to reflect only annuity_income work remaining

---

## Approval

- [ ] **User Approval:** Pending
- [ ] **Sprint Status Updated:** Pending
- [ ] **Story File Created:** Pending
