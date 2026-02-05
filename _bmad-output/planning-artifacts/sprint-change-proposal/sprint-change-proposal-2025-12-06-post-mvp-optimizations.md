# Sprint Change Proposal: Post-MVP Optimizations

**Date:** 2025-12-06
**Triggered By:** Epic 5.5 MVP Validation Phase
**Status:** ✅ Approved (2025-12-06)
**Scope Classification:** Minor

---

## Section 1: Issue Summary

### Problem Statement

During the Epic 5.5 MVP validation phase (specifically Stories 5.5.3 and 5.5.4), four optimization opportunities were identified that would improve data quality observability, fix a data cleansing bug, enhance configuration capabilities, and document best practices for future domain development.

### Context

- **Discovery Time:** 2025-12-06
- **Discovery Phase:** Epic 5.5 Multi-Domain Integration Test & Optimization
- **Impact on MVP:** None - MVP validation completed successfully
- **Nature:** Post-MVP enhancements and bug fixes

### Evidence Summary

| ID | Issue | Evidence |
|----|-------|----------|
| OPT-001 | Failed records not exported in Dry Run mode | `annuity_performance`: 33,615 input → 33,613 output, 2 rows silently dropped |
| OPT-002 | Bracket handling bug in company name normalization | `"公司(集团)"` → `"公司（集团"` (missing closing bracket) |
| OPT-003 | Missing upsert_keys configuration support | Legacy uses `update_based_on_field`, new pipeline lacks config layer |
| OPT-004 | No domain development guide | Epic 5.5 experience not documented for future developers |

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 5.5 | Done | No impact - already completed |
| Epic 6 | Backlog | OPT-001/003 have synergy with Story 5.8 (Observability) |
| Epic 7 | Backlog | OPT-001 improves testing infrastructure |

**Recommendation:** Create 4 independent Stories, either as Epic 5.6 (Post-MVP Optimizations) or integrate into Epic 6 backlog.

### Artifact Conflicts

| Artifact | Conflict | Action Needed |
|----------|----------|---------------|
| PRD | None | Optional: Update FR-2.2 to mention failed record export |
| Architecture | None | Optional: Document failed record handling pattern |
| UI/UX | N/A | No UI components affected |
| Database DDL | OPT-003 | Add UNIQUE constraints for upsert keys |

### Code Impact (Simplified after KISS/YAGNI Review)

**Files requiring modification:**

| OPT | Files | Estimated LOC |
|-----|-------|---------------|
| OPT-001 | `domain/annuity_performance/service.py` | +10 |
| OPT-001 | `domain/annuity_income/service.py` | +10 |
| OPT-002 | `infrastructure/cleansing/rules/string_rules.py` | +2 |
| OPT-003 | `domain/*/service.py` (module constant) | +4 |
| OPT-004 | `docs/guides/domain-migration/development-guide.md` (new) | +200 |

> **Note:** After KISS/YAGNI review, OPT-001/002/003 were significantly simplified. See Section 4 for details.

---

## Section 3: Recommended Approach

### Selected Path: Option 1 - Direct Adjustment

**Rationale:**
1. All optimization requests are appropriately scoped as independent Stories
2. No impact on completed Epic 5.5 or MVP validation results
3. OPT-002 (bug fix) should be prioritized; others can be scheduled flexibly
4. Low effort, low risk implementation

### Effort and Risk Assessment (Updated after KISS/YAGNI Review)

| OPT | Priority | Effort | Risk | Timeline Impact |
|-----|----------|--------|------|-----------------|
| OPT-001 | Medium | 30 min | Low | None |
| OPT-002 | **High** | 15 min | Low | None |
| OPT-003 | Medium | 15 min | Low | None |
| OPT-004 | Medium | 2-3 hours | Low | None |

**Total Estimated Effort:** 3-4 hours (reduced from 8-12 hours after simplification)

### Alternatives Considered

| Option | Evaluation | Decision |
|--------|------------|----------|
| Option 2: Rollback | Not applicable - no completed work needs reverting | Rejected |
| Option 3: MVP Review | Not applicable - MVP already validated successfully | Rejected |

---

## Section 4: Detailed Change Proposals

> **KISS/YAGNI Review Applied:** The following proposals have been simplified to avoid over-engineering. Original complex proposals were replaced with minimal solutions that achieve the same goals.

### OPT-001: Dry Run Failed Records Export (Simplified)

**Story:** As a data engineer, I want failed validation records exported to CSV during Dry Run mode, so that I can quickly identify and fix data quality issues.

#### Simplified Approach

**Principle:** Reuse existing infrastructure. No new dataclasses, no function signature changes.

**File:** `src/work_data_hub/domain/annuity_performance/service.py`

Add ~10 lines after the existing dropped rows logging (around line 144):

```python
# After: event_logger.info("Dropped rows during conversion", ...)

# NEW: Export failed rows to CSV for debugging
if dropped_count > 0:
    # Get indices of successfully converted records
    success_indices = {r.计划代码 for r in records}
    # Filter to get failed rows from original DataFrame
    failed_df = result_df[~result_df["计划代码"].isin(success_indices)]

    if not failed_df.empty:
        csv_path = export_error_csv(
            failed_df,
            filename_prefix=f"failed_records_{data_source}",
            output_dir=Path("logs"),
        )
        event_logger.info("Exported failed records", csv_path=str(csv_path), count=len(failed_df))
```

**Rationale:**
- ❌ ~~New dataclass~~ → Not needed, use DataFrame directly
- ❌ ~~Change function signature~~ → Breaks callers, unnecessary
- ✅ Reuse existing `export_error_csv` function
- ✅ ~10 LOC vs original ~80 LOC

#### Acceptance Criteria

1. Dry Run mode exports failed records to `logs/failed_records_*.csv`
2. CSV contains original row data (all columns)
3. Logs record count and file path
4. No changes to `helpers.py` function signatures

---

### OPT-002: normalize_company_name Bracket Bug Fix (Revised)

**Story:** As a data engineer, I want company names with abnormal bracket patterns at start/end to be cleaned correctly, so that data quality is maintained.

#### Business Rule Clarification

> **业务规则：** 公司名称以 `(xx)` 或 `（xx）` 为**开头或结尾**都应归类为异常字符，正常企业名称不可能出现该情况，可以直接清除。
>
> **限制：** 只处理开头、结尾的情况，中间的括号内容不可直接清除。

#### Revised Approach

**File:** `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py`

**Fix:** 添加通用的开头/结尾括号清理规则，替代逐个后缀匹配：

```python
def normalize_company_name(name: str) -> str:
    """Normalize company name with bracket cleanup."""
    if not name:
        return name

    result = name.strip()

    # 半角转全角括号（保持现有逻辑）
    result = result.replace("(", "（").replace(")", "）")

    # NEW: 清理开头的括号内容 (xx) 或 （xx）
    result = re.sub(r'^[（\(][^）\)]*[）\)]', '', result)

    # NEW: 清理结尾的括号内容 (xx) 或 （xx）
    result = re.sub(r'[（\(][^）\)]*[）\)]$', '', result)

    # ... 其他现有清洗逻辑 ...

    return result.strip()
```

**Rationale:**
- ✅ 通用规则：处理所有开头/结尾括号，不需要维护后缀列表
- ✅ 安全：只处理开头/结尾，不影响中间的合法括号
- ✅ 简单：2 行正则替代复杂的后缀匹配逻辑
- ✅ 解决原 Bug：`"公司(集团)"` → `"公司"`（结尾括号被清除）

#### Test Cases

| 输入 | 期望输出 | 说明 |
|------|----------|------|
| `"(集团)中国机械公司"` | `"中国机械公司"` | 开头括号清除 |
| `"中国机械公司(集团)"` | `"中国机械公司"` | 结尾括号清除 |
| `"（测试）平安银行（集团）"` | `"平安银行"` | 开头+结尾都清除 |
| `"中国（北京）科技公司"` | `"中国（北京）科技公司"` | 中间括号保留 |
| `"华为技术有限公司"` | `"华为技术有限公司"` | 无括号不变 |

#### Acceptance Criteria

1. 开头的 `(xx)` 或 `（xx）` 被清除
2. 结尾的 `(xx)` 或 `（xx）` 被清除
3. 中间的括号内容保留不变
4. 所有现有单元测试通过
5. 新增上述 5 个测试用例

---

### OPT-003: Domain Upsert Keys Configuration (Simplified)

**Story:** As a data engineer, I want to configure upsert keys per domain, so that duplicate records are updated instead of inserted.

#### Key Finding: Infrastructure Already Exists!

After code review, discovered that:
- `service.py` already has `upsert_keys: Optional[List[str]] = None` parameter (line 44)
- `warehouse_loader.load_dataframe()` already accepts and uses `upsert_keys` (line 70)

**No new infrastructure needed!** Just need to pass the values at call site.

#### Simplified Approach

**Option A: Pass at call site (Recommended for flexibility)**

In Dagster asset or caller:
```python
result = process_annuity_performance(
    month="202401",
    upsert_keys=["月度", "计划代码"],  # Pass directly
)
```

**Option B: Module-level default constant (If you want a default)**

**File:** `src/work_data_hub/domain/annuity_performance/service.py`

Add 2 lines at top of file:
```python
# Default upsert keys for this domain (equivalent to Legacy update_based_on_field)
DEFAULT_UPSERT_KEYS = ["月度", "计划代码"]
```

Then use in function:
```python
def process_annuity_performance(
    ...
    upsert_keys: Optional[List[str]] = None,
):
    actual_keys = upsert_keys or DEFAULT_UPSERT_KEYS
    # ... rest of function uses actual_keys
```

**Rationale:**
- ❌ ~~New config.py files~~ → YAGNI, no such files exist
- ❌ ~~Complex configuration mechanism~~ → Over-engineering
- ✅ Use existing parameter → Already implemented!
- ✅ ~2-4 LOC vs original ~40 LOC

#### Database DDL (Still Required)

```sql
-- Migration: Add unique constraint for upsert support
ALTER TABLE annuity.annuity_performance
ADD CONSTRAINT uq_annuity_performance_month_plan
UNIQUE (月度, 计划代码);

ALTER TABLE annuity.annuity_income
ADD CONSTRAINT uq_annuity_income_month_type
UNIQUE (月度, 业务类型);
```

#### Acceptance Criteria

1. `upsert_keys` passed when calling `process_annuity_performance()`
2. Re-running pipeline updates existing records instead of duplicating
3. Database tables have corresponding UNIQUE constraints

---

### OPT-004: Domain Development Guide

**Story:** As a developer, I want a comprehensive domain development guide, so that I can create new domains following established patterns.

#### Change: Create new documentation file

**File:** `docs/guides/domain-migration/development-guide.md` (NEW)

**Content Outline:**

```markdown
# Domain Development Guide

## Overview
Guide for implementing new data domains in WorkDataHub, based on Epic 5.5 learnings.

## Domain Directory Structure
```
src/work_data_hub/domain/{domain_name}/
├── __init__.py
├── config.py          # Domain configuration (UPSERT_KEYS, etc.)
├── models.py          # Pydantic data models
├── schemas.py         # Pandera DataFrame schemas
├── helpers.py         # Data transformation helpers
├── service.py         # Business service layer
└── assets/            # Dagster Assets
    └── __init__.py
```

## Development Checklist
- [ ] Analyze Legacy data source and cleansing logic
- [ ] Define Pydantic models (models.py)
- [ ] Define Pandera schemas (schemas.py)
- [ ] Implement data transformation (helpers.py)
- [ ] Implement service layer (service.py)
- [ ] Configure upsert keys (config.py)
- [ ] Define Dagster Assets (assets/)
- [ ] Write unit tests
- [ ] Legacy parity validation
- [ ] Database DDL (table + UNIQUE constraints)

## Key Configuration
### UPSERT_KEYS
[Documentation of upsert configuration...]

### Schema Validation Rules
[Best practices for Pandera schema design...]

## Common Issues & Solutions
### Bracket Handling (OPT-002)
[Document the bracket bug and fix...]

### Failed Record Tracking (OPT-001)
[Document failed record export pattern...]

## Testing Strategy
[Unit test, integration test, E2E validation guidance...]

## References
- [Cleansing Rules Template](../templates/cleansing-rules-template.md)
- [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md)
```

#### Acceptance Criteria

1. Document covers complete domain development lifecycle
2. Includes reusable code templates and configuration examples
3. Documents Epic 5.5 lessons learned and best practices
4. New developers can independently create domains using this guide
5. Document reviewed and merged to main branch

---

## Section 5: Implementation Handoff

### Scope Classification: Minor

These changes can be implemented directly by the development team without requiring backlog reorganization or architectural review.

### Handoff Recipients

| Role | Responsibility | Items |
|------|----------------|-------|
| **Development Team** | Code implementation | OPT-001, OPT-002, OPT-003 |
| **Technical Writer / Dev** | Documentation | OPT-004 |
| **DBA / Dev** | Database DDL | OPT-003 UNIQUE constraints |

### Recommended Execution Order

1. **OPT-002** (High priority bug fix) - Immediate
2. **OPT-001** (Failed records export) - Next sprint
3. **OPT-003** (Upsert keys config) - Next sprint
4. **OPT-004** (Documentation) - Parallel with above

### Success Criteria

1. All 4 OPT items implemented and tested
2. No regression in existing functionality
3. Unit test coverage maintained > 85%
4. Documentation reviewed and approved

---

## Approval

**Prepared By:** Claude (AI Assistant)
**Date:** 2025-12-06

**Approval Status:** [x] Approved / [ ] Rejected / [ ] Revise

**Approver:** Link
**Date:** 2025-12-06

**Notes:**
将 4 个优化需求作为独立 Stories 实施

---

*Generated by Correct Course Workflow*
