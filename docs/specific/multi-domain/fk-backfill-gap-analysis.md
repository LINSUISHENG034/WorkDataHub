# Foreign Key Backfill Gap Analysis

> **Document Status:** Technical Debt Analysis
> **Created:** 2025-12-28
> **Related Epic:** Multi-Domain ETL Architecture

## Overview

This document identifies missing foreign key (FK) backfill configurations for `annuity_performance` and `annuity_income` domains, ensuring referential integrity with parent tables in the `mapping` schema.

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Domains Analyzed | 2 (annuity_performance, annuity_income) |
| Parent Tables in mapping schema | 5 (年金计划, 组合计划, 产品线, 组织架构, 年金客户) |
| Missing FK Configurations | 5 (1 for annuity_performance, 4 for annuity_income) |
| Critical Gap | `年金客户` table not linked via `company_id` |

---

## Current FK Backfill Configuration

### `annuity_performance` (config/foreign_keys.yml)

| FK Name | Source Column | Target Table | Target Key | Status |
|---------|---------------|--------------|------------|--------|
| `fk_plan` | `计划代码` | `mapping.年金计划` | `年金计划号` | ✅ Configured |
| `fk_portfolio` | `组合代码` | `mapping.组合计划` | `组合代码` | ✅ Configured |
| `fk_product_line` | `产品线代码` | `mapping.产品线` | `产品线代码` | ✅ Configured |
| `fk_organization` | `机构代码` | `mapping.组织架构` | `机构代码` | ✅ Configured |
| `fk_customer` | `company_id` | `mapping.年金客户` | `company_id` | ❌ **MISSING** |

### `annuity_income` (config/foreign_keys.yml)

| FK Name | Source Column | Target Table | Target Key | Status |
|---------|---------------|--------------|------------|--------|
| `fk_plan` | `计划代码` | `mapping.年金计划` | `年金计划号` | ❌ **MISSING** |
| `fk_portfolio` | `组合代码` | `mapping.组合计划` | `组合代码` | ❌ **MISSING** |
| `fk_product_line` | `产品线代码` | `mapping.产品线` | `产品线代码` | ❌ **MISSING** |
| `fk_organization` | `机构代码` | `mapping.组织架构` | `机构代码` | ❌ **MISSING** |
| `fk_customer` | `company_id` | `mapping.年金客户` | `company_id` | ❌ **MISSING** |

---

## Parent Table Analysis

### `mapping.年金客户` (Annuity Customer)

**Primary Key:** `company_id` (VARCHAR, NOT NULL)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | NO | Auto-increment ID |
| `company_id` | VARCHAR | NO | **Primary Key** - Company identifier |
| `客户名称` | VARCHAR | YES | Customer name |
| `年金客户标签` | VARCHAR | YES | Customer label |
| `年金客户类型` | VARCHAR | YES | Customer type |
| `年金计划类型` | VARCHAR | YES | Plan type |
| `关键年金计划` | VARCHAR | YES | Key annuity plan |
| `主拓机构代码` | VARCHAR | YES | Primary branch code |
| `主拓机构` | VARCHAR | YES | Primary branch name |
| `客户简称` | VARCHAR | YES | Customer short name |
| `最新受托规模` | FLOAT | YES | Latest trustee scale |
| `最新投管规模` | FLOAT | YES | Latest investment scale |
| `管理资格` | VARCHAR | YES | Management qualification |
| `规模区间` | VARCHAR | YES | Scale range |
| ... | ... | ... | (additional columns) |

### Fact Table → Parent Table Relationships

```
business.规模明细 (annuity_performance)
    ├── 计划代码 ──────→ mapping.年金计划.年金计划号 ✅
    ├── 组合代码 ──────→ mapping.组合计划.组合代码 ✅
    ├── 产品线代码 ────→ mapping.产品线.产品线代码 ✅
    ├── 机构代码 ──────→ mapping.组织架构.机构代码 ✅
    └── company_id ────→ mapping.年金客户.company_id ❌ MISSING

business.收入明细 (annuity_income)
    ├── 计划代码 ──────→ mapping.年金计划.年金计划号 ❌ MISSING
    ├── 组合代码 ──────→ mapping.组合计划.组合代码 ❌ MISSING
    ├── 产品线代码 ────→ mapping.产品线.产品线代码 ❌ MISSING
    ├── 机构代码 ──────→ mapping.组织架构.机构代码 ❌ MISSING
    └── company_id ────→ mapping.年金客户.company_id ❌ MISSING
```

---

## Issue Summary

| Issue ID | Severity | Domain | Description |
|----------|----------|--------|-------------|
| **BF-001** | High | annuity_performance | Missing `fk_customer` backfill for `company_id` → `年金客户` |
| **BF-002** | High | annuity_income | No FK backfill configured (entire domain missing) |
| BF-003 | Medium | Both | `年金客户` table not populated from ETL data |

---

## Recommended Configuration

### New FK for `annuity_performance`

Add to `config/foreign_keys.yml` under `annuity_performance.foreign_keys`:

```yaml
      # 年金客户 (Annuity Customer) reference table backfill
      # Story X.X: Added company_id → 年金客户 FK relationship
      - name: "fk_customer"
        source_column: "company_id"
        target_table: "年金客户"
        target_key: "company_id"
        target_schema: "mapping"
        mode: "insert_missing"
        skip_blank_values: true  # Skip temp IDs (IN*) if needed
        backfill_columns:
          - source: "company_id"
            target: "company_id"
          - source: "客户名称"
            target: "客户名称"
            optional: true
          # Story 6.2-P15: max_by aggregation for 主拓机构代码
          # Selects 机构代码 from record with maximum 期末资产规模
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
          # Aggregation for 管理资格 (concat distinct 业务类型)
          - source: "业务类型"
            target: "管理资格"
            optional: true
            aggregation:
              type: "concat_distinct"
              separator: "+"
              sort: true
```

### New Domain Configuration for `annuity_income`

Add to `config/foreign_keys.yml`:

```yaml
  # Annuity Income Domain
  # Story X.X: Added FK backfill configuration (parity with annuity_performance)
  annuity_income:
    foreign_keys:
      # 年金计划 (Annuity Plan) reference table backfill
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        target_schema: "mapping"
        mode: "insert_missing"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
          - source: "计划类型"
            target: "计划类型"
            optional: true
          - source: "客户名称"
            target: "客户名称"
            optional: true
          - source: "company_id"
            target: "company_id"
            optional: true

      # 组合计划 (Portfolio Plan) reference table backfill
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

      # 产品线 (Product Line) reference table backfill
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

      # 组织架构 (Organization) reference table backfill
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

      # 年金客户 (Annuity Customer) reference table backfill
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

---

## Implementation Considerations

### 1. Dependency Order

For `annuity_income`, the FK backfill should follow this order:

```
1. fk_plan (年金计划)
2. fk_portfolio (组合计划) - depends_on: fk_plan
3. fk_product_line (产品线)
4. fk_organization (组织架构)
5. fk_customer (年金客户)
```

### 2. Aggregation for `年金客户`

The `年金客户` table contains aggregated customer information:
- `主拓机构代码` / `主拓机构`: Should use `max_by` aggregation on `期末资产规模`
- `管理资格`: Should use `concat_distinct` on `业务类型`

**Note:** `annuity_income` does not have `期末资产规模` column, so `max_by` aggregation is not applicable. Use `first` (default) instead.

### 3. Temp Company ID Handling

Both domains may contain temporary company IDs (format: `IN<16-char-Base32>`):
- These should be skipped during `年金客户` backfill
- Use `skip_blank_values: true` or add filter for `company_id NOT LIKE 'IN%'`

### 4. Job Configuration Update

The Dagster job wiring in `orchestration/jobs.py` already includes `generic_backfill_refs_op` for both domains. No job changes needed - configuration is read from `foreign_keys.yml`.

### 5. CLI Config Update

`cli/etl/config.py` already conditionally adds backfill config for `annuity_performance`. Need to add `annuity_income` to the list:

```python
# Current (L389):
if args.domain in ["annuity_performance", "sandbox_trustee_performance"]:

# Should be:
if args.domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
```

---

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `config/foreign_keys.yml` | **MODIFY** | Add `fk_customer` to annuity_performance, add entire `annuity_income` section |
| `cli/etl/config.py` | **MODIFY** | Add `annuity_income` to backfill domain list (L389) |
| `orchestration/jobs.py` | **NO CHANGE** | Already has `generic_backfill_refs_op` for annuity_income |

---

## Related Documentation

- [Shared Field Validators Analysis](./shared-field-validators-analysis.md) - Field consistency issues
- [New Domain Checklist](./new-domain-checklist.md) - Domain addition requirements
- [Project Context](../../project-context.md) - Architecture overview

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-28 | Barry (Quick Flow) | Initial FK backfill gap analysis |
