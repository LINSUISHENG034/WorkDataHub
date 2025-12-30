# Sprint Change Proposal: FK Backfill Configuration Completion

> **Date:** 2025-12-30
> **Author:** Claude (Correct-Course Workflow)
> **Status:** Implemented
> **Priority:** P1 (High)
> **Scope:** Minor (Direct Implementation)
> **Reference:** `docs/specific/multi-domain/fk-backfill-gap-analysis.md`

---

## 1. Issue Summary

### Problem Statement

During multi-domain architecture review after Epic 7.3 completion, FK (Foreign Key) backfill configuration gaps were identified:

1. **BF-001**: `annuity_performance` domain is missing `fk_customer` configuration for `company_id → mapping.年金客户`
2. **BF-002**: `annuity_income` domain has **no FK backfill configuration at all** (entire domain missing from `foreign_keys.yml`)

### Discovery Context

- **When:** Post Epic 7.3 multi-domain consistency analysis
- **How:** Analysis documented in `docs/specific/multi-domain/fk-backfill-gap-analysis.md`
- **Evidence:**
  - `foreign_keys.yml` only contains `annuity_performance` with 4 FKs (missing `fk_customer`)
  - `annuity_income` section completely absent
  - `annuity_income_job()` in `jobs.py` has comment: "No backfill needed for this domain" (incorrect)

### Risks If Not Addressed

| Risk                                              | Impact | Likelihood |
| ------------------------------------------------- | ------ | ---------- |
| Fact tables populated without Dimension records   | High   | High       |
| Cross-domain queries failing due to missing joins | High   | Medium     |
| Inconsistent data state between domains           | Medium | High       |
| Epic 8 validation tests failing on FK constraints | High   | High       |

---

## 2. Impact Analysis

### Epic Impact

| Epic     | Status  | Impact                           |
| -------- | ------- | -------------------------------- |
| Epic 7.3 | Done    | Extended with Story 7.3-7        |
| Epic 8   | Backlog | Benefits from complete FK config |

### Story Impact

| Story     | Type | Description                          |
| --------- | ---- | ------------------------------------ |
| **7.3-7** | New  | FK Backfill Configuration Completion |

### Artifact Conflicts

| Artifact                      | Change Type | Description                                                           |
| ----------------------------- | ----------- | --------------------------------------------------------------------- |
| `config/foreign_keys.yml`     | MODIFY      | Add `annuity_income` section + `fk_customer` to `annuity_performance` |
| `orchestration/jobs.py`       | MODIFY      | Update `annuity_income_job()` to include backfill ops                 |
| `cli/etl/config.py`           | MODIFY      | Add `annuity_income` to backfill domain list                          |
| `fk-backfill-gap-analysis.md` | UPDATE      | Mark issues as resolved                                               |

### Technical Impact

- **Code Changes:** ~50 lines (config) + ~10 lines (Python)
- **Infrastructure:** None
- **Deployment:** None (config-only for new installs)
- **Existing Data:** Requires manual backfill run for existing databases

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

**Rationale:**

- Configuration-driven changes (low risk)
- Follows existing patterns in codebase
- No architectural changes required
- Effort estimate: **2-4 hours**
- Risk level: **Low**

### Trade-offs Considered

| Approach          | Pros                      | Cons                | Decision          |
| ----------------- | ------------------------- | ------------------- | ----------------- |
| Direct Adjustment | Low effort, immediate fix | None                | ✅ Selected       |
| Rollback          | N/A                       | No code to rollback | ❌ Not applicable |
| MVP Review        | N/A                       | MVP scope unchanged | ❌ Not applicable |

---

## 4. Detailed Change Proposals

### 4.1 Configuration Changes

#### `config/foreign_keys.yml`

**Change 1:** Add `fk_customer` to `annuity_performance` (after line 140)

```yaml
# 年金客户 (Annuity Customer) reference table backfill
# Story 7.3-7: Add company_id → 年金客户 FK relationship (BF-001)
- name: "fk_customer"
  source_column: "company_id"
  target_table: "年金客户"
  target_key: "company_id"
  target_schema: "mapping"
  mode: "insert_missing"
  skip_blank_values: true # Skip temp IDs (IN*)
  backfill_columns:
    - source: "company_id"
      target: "company_id"
    - source: "客户名称"
      target: "客户名称"
      optional: true
    - source: "机构代码"
      target: "主拓机构代码"
      optional: true
      aggregation:
        type: "max_by"
        order_column: "期末资产规模"
    - source: "机构名称"
      target: "主拓机构"
      optional: true
      aggregation:
        type: "max_by"
        order_column: "期末资产规模"
    - source: "业务类型"
      target: "管理资格"
      optional: true
      aggregation:
        type: "concat_distinct"
        separator: "+"
        sort: true
```

**Change 2:** Add entire `annuity_income` domain section

```yaml
# Annuity Income Domain
# Story 7.3-7: Add FK backfill configuration (parity with annuity_performance)
# Reference: docs/specific/multi-domain/fk-backfill-gap-analysis.md (BF-002)
annuity_income:
  foreign_keys:
    - name: "fk_plan"
      source_column: "计划代码"
      target_table: "年金计划"
      target_key: "年金计划号"
      target_schema: "mapping"
      mode: "insert_missing"
      backfill_columns:
        - source: "计划代码"
          target: "年金计划号"
        - source: "计划名称"
          target: "计划全称"
          optional: true
        - source: "客户名称"
          target: "客户名称"
          optional: true
        - source: "company_id"
          target: "company_id"
          optional: true

    - name: "fk_portfolio"
      source_column: "组合代码"
      target_table: "组合计划"
      target_key: "组合代码"
      target_schema: "mapping"
      mode: "insert_missing"
      depends_on: ["fk_plan"]
      backfill_columns:
        - source: "组合代码"
          target: "组合代码"
        - source: "计划代码"
          target: "年金计划号"
        - source: "组合名称"
          target: "组合名称"
          optional: true
        - source: "组合类型"
          target: "组合类型"
          optional: true

    - name: "fk_product_line"
      source_column: "产品线代码"
      target_table: "产品线"
      target_key: "产品线代码"
      target_schema: "mapping"
      mode: "insert_missing"
      backfill_columns:
        - source: "产品线代码"
          target: "产品线代码"
        - source: "业务类型"
          target: "产品线"
          optional: true

    - name: "fk_organization"
      source_column: "机构代码"
      target_table: "组织架构"
      target_key: "机构代码"
      target_schema: "mapping"
      mode: "insert_missing"
      skip_blank_values: true
      backfill_columns:
        - source: "机构代码"
          target: "机构代码"
        - source: "机构名称"
          target: "机构"
          optional: true

    - name: "fk_customer"
      source_column: "company_id"
      target_table: "年金客户"
      target_key: "company_id"
      target_schema: "mapping"
      mode: "insert_missing"
      skip_blank_values: true
      backfill_columns:
        - source: "company_id"
          target: "company_id"
        - source: "客户名称"
          target: "客户名称"
          optional: true
```

### 4.2 Code Changes

#### `src/work_data_hub/orchestration/jobs.py`

**Change:** Update `annuity_income_job()` to include backfill ops

```python
@job
def annuity_income_job() -> Any:
    """
    End-to-end annuity income processing job with optional reference backfill.

    Story 7.3-7: Added reference backfill support (parity with annuity_performance).
    """
    discovered_paths = discover_files_op()
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_annuity_income_op(excel_rows, discovered_paths)

    # Story 7.3-7: Generic reference backfill
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)
```

#### `src/work_data_hub/cli/etl/config.py` (L157)

**Change:** Add `annuity_income` to backfill domain list

```python
if domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
```

#### `src/work_data_hub/orchestration/jobs.py` (L389)

**Change:** Same update in duplicate `build_run_config`

```python
if args.domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
```

---

## 5. Implementation Handoff

### Scope Classification: Minor

This change can be implemented directly by development team.

### Deliverables

| Deliverable                | Description                          |
| -------------------------- | ------------------------------------ |
| Story 7.3-7                | FK Backfill Configuration Completion |
| Updated `foreign_keys.yml` | Complete FK config for both domains  |
| Updated `jobs.py`          | Backfill ops in `annuity_income_job` |
| Updated `config.py`        | Backfill domain list updated         |

### Implementation Tasks

1. [ ] Add `fk_customer` configuration to `annuity_performance` in `foreign_keys.yml`
2. [ ] Add complete `annuity_income` section to `foreign_keys.yml`
3. [ ] Update `annuity_income_job()` to include backfill ops
4. [ ] Update backfill domain list in `cli/etl/config.py`
5. [ ] Update backfill domain list in `jobs.py` (duplicate function)
6. [ ] Update `fk-backfill-gap-analysis.md` to mark issues resolved
7. [ ] Add Story 7.3-7 to `sprint-status.yaml`
8. [ ] Run tests: `pytest tests/ -k "backfill or annuity_income"`
9. [ ] Validate with real data: `uv run etl --domains annuity_income --period 202411`

### Success Criteria

- [ ] `foreign_keys.yml` contains complete FK config for both domains
- [ ] `annuity_income_job` includes `generic_backfill_refs_op` in pipeline
- [ ] CLI generates correct backfill config for `annuity_income` domain
- [ ] All existing tests pass
- [ ] Manual validation with real 202411 data succeeds

### Handoff Recipients

| Role             | Responsibility        |
| ---------------- | --------------------- |
| Development Team | Implement Story 7.3-7 |

---

## 6. Sprint Status Update

### Proposed Story 7.3-7 (Extension of Epic 7.3)

Since this issue was discovered during Epic 7.3 multi-domain testing and aligns with the "Multi-Domain Consistency Fixes" theme, we add this as Story 7.3-7 rather than creating a new Epic.

```yaml
# Story 7.3-7: FK Backfill Configuration Completion
# Added 2025-12-30 via Correct-Course workflow
# Discovered during Epic 7.3 multi-domain testing
# Fixes: BF-001 (annuity_performance missing fk_customer), BF-002 (annuity_income no FK config)
# Reference: docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-30-fk-backfill-completion.md
7.3-7-fk-backfill-configuration-completion: backlog # P1: Add missing FK configs (BF-001, BF-002)
```

---

## Appendix: Issue Reference

| Issue ID | Severity | Domain              | Description                    | Status |
| -------- | -------- | ------------------- | ------------------------------ | ------ |
| BF-001   | High     | annuity_performance | Missing `fk_customer` backfill | To Fix |
| BF-002   | High     | annuity_income      | No FK backfill configured      | To Fix |
| BF-003   | Medium   | Both                | `年金客户` table not populated | To Fix |

---

## Version History

| Date       | Author                  | Change                         |
| ---------- | ----------------------- | ------------------------------ |
| 2025-12-30 | Claude (Correct-Course) | Initial Sprint Change Proposal |
