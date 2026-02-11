# Implementation Plan: Enhance FK Backfill for Annual Award/Loss

## Overview

**Goal:** Complete the FK backfill configuration for `annual_award` and `annual_loss` domains to populate all relevant fields in the `年金客户` table, not just `company_id`.

**Problem:** Current configuration only backfills `company_id` and `客户名称`, leaving other fields empty.

**Solution:** Extend the FK backfill configuration to map all available source columns to target fields using appropriate aggregation strategies.

---

## Schema Analysis

### Source Tables (当年中标/当年流失)

| Column | Type | Available |
|--------|------|-----------|
| `company_id` | varchar | ✅ |
| `客户名称` | varchar | ✅ |
| `机构代码` | varchar | ✅ |
| `机构名称` | varchar | ✅ |
| `业务类型` | varchar | ✅ |
| `计划类型` | varchar | ✅ |
| `年金计划号` | varchar | ✅ |
| `上报月份` | date | ✅ |
| `计划规模` | numeric | ✅ (for max_by ordering) |

### Target Table (年金客户)

| Target Column | Source Column | Aggregation |
|---------------|---------------|-------------|
| `company_id` | `company_id` | - (PK) |
| `客户名称` | `客户名称` | first |
| `主拓机构代码` | `机构代码` | max_by(计划规模) |
| `主拓机构` | `机构名称` | max_by(计划规模) |
| `管理资格` | `业务类型` | concat_distinct(+) |
| `年金计划类型` | `计划类型` | concat_distinct(/) |
| `关键年金计划` | `年金计划号` | max_by(计划规模) |
| `其他年金计划` | `年金计划号` | concat_distinct(,) |
| `关联计划数` | `年金计划号` | count_distinct |
| `关联机构数` | `机构名称` | count_distinct |
| `其他开拓机构` | `机构名称` | concat_distinct(,) |
| `年金客户标签` | `上报月份` | lambda (YYMM+新建) |
| `年金客户类型` | `上报月份` | template (中标客户/流失客户) |

---

## Tasks

### Task 1: Update annual_award FK Configuration
- **File:** `config/foreign_keys.yml`
- **Action:** Extend `annual_award.foreign_keys[0].backfill_columns` with all mappings
- **Customer Type:** `中标客户`
- **Acceptance:** Config loads without errors

### Task 2: Update annual_loss FK Configuration
- **File:** `config/foreign_keys.yml`
- **Action:** Extend `annual_loss.foreign_keys[0].backfill_columns` with all mappings
- **Customer Type:** `流失客户`
- **Acceptance:** Config loads without errors

### Task 3: Validate Configuration
- **Action:** Run config validation command
- **Command:** `uv run --env-file .wdh_env python -c "from work_data_hub.domain.reference_backfill.config_loader import load_fk_config; print(load_fk_config())"`
- **Acceptance:** No errors, both domains show complete backfill_columns

### Task 4: Run Integration Test
- **Action:** Execute ETL dry-run for both domains
- **Commands:**
  - `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_award --dry-run`
  - `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_loss --dry-run`
- **Acceptance:** No errors, backfill candidates show all columns populated

---

## Implementation Details

### annual_award Configuration (中标客户)

```yaml
annual_award:
  foreign_keys:
    - name: "fk_customer"
      source_column: "company_id"
      target_table: "年金客户"
      target_key: "company_id"
      target_schema: "customer"
      mode: "insert_missing"
      skip_blank_values: true
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
            order_column: "计划规模"
        - source: "机构名称"
          target: "主拓机构"
          optional: true
          aggregation:
            type: "max_by"
            order_column: "计划规模"
        - source: "业务类型"
          target: "管理资格"
          optional: true
          aggregation:
            type: "concat_distinct"
            separator: "+"
            sort: true
        - source: "计划类型"
          target: "年金计划类型"
          optional: true
          aggregation:
            type: "concat_distinct"
            separator: "/"
            sort: true
        - source: "年金计划号"
          target: "关键年金计划"
          optional: true
          aggregation:
            type: "max_by"
            order_column: "计划规模"
        - source: "年金计划号"
          target: "其他年金计划"
          optional: true
          aggregation:
            type: "concat_distinct"
            separator: ","
            sort: true
        - source: "年金计划号"
          target: "关联计划数"
          optional: true
          aggregation:
            type: "count_distinct"
        - source: "机构名称"
          target: "关联机构数"
          optional: true
          aggregation:
            type: "count_distinct"
        - source: "机构名称"
          target: "其他开拓机构"
          optional: true
          aggregation:
            type: "concat_distinct"
            separator: ","
            sort: true
        - source: "上报月份"
          target: "年金客户标签"
          optional: true
          aggregation:
            type: "lambda"
            code: 'lambda g: pd.to_datetime(g["上报月份"].dropna().iloc[0]).strftime("%y%m") + "中标" if len(g["上报月份"].dropna()) > 0 else ""'
        - source: "上报月份"
          target: "年金客户类型"
          optional: true
          aggregation:
            type: "template"
            template: "中标客户"
```

### annual_loss Configuration (流失客户)

Same structure as annual_award, with these differences:
- `年金客户标签` lambda: `"%y%m" + "流失"`
- `年金客户类型` template: `"流失客户"`

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Column name mismatch | Verified against actual DB schema |
| Aggregation errors | Using proven patterns from annuity_performance |
| NULL handling | All non-PK columns marked `optional: true` |

---

## Verification Checklist

- [ ] Config loads without errors
- [ ] ETL dry-run shows all columns in candidates
- [ ] No regression in existing FK backfill tests
- [ ] Records in 年金客户 have populated fields after ETL run
