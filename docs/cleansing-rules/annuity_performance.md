# Cleansing Rules: Annuity Performance

**Domain:** `annuity_performance`
**Source:** `legacy/annuity_hub/data_handler/data_cleaner.py` (Class: `AnnuityPerformanceCleaner`)
**Status:** DRAFT

---

## 1. Domain Overview

**Purpose:** Process annuity performance data (asset scale, yield, etc.) for business analysis.
**Source Type:** Excel/CSV (Sheet: "规模明细")
**Frequency:** Monthly

---

## 2. Dependency Table Inventory

| # | Table Name | Database | Purpose | Legacy Object | Migration Status |
|---|------------|----------|---------|---------------|------------------|
| 1 | 组织架构 | mapping | Branch code mapping | `COMPANY_BRANCH_MAPPING` | [MIGRATED] (Infra) |
| 2 | 年金计划 | mapping | Plan code to Company ID | `COMPANY_ID1_MAPPING` | [PENDING] |
| 3 | annuity_account_mapping | enterprise | Group Customer to Company ID | `COMPANY_ID2_MAPPING` | [PENDING] |
| 4 | company_id_mapping | enterprise | Name to Company ID | `COMPANY_ID4_MAPPING` | [MIGRATED] (Enrichment) |
| 5 | 规模明细 | business | Account Name to Company ID | `COMPANY_ID5_MAPPING` | [PENDING] |
| 6 | 产品线 | mapping | Business Type Code | `BUSINESS_TYPE_CODE_MAPPING` | [MIGRATED] (Infra) |
| 7 | 组合计划 | mapping | Default Plan Codes | `DEFAULT_PLAN_CODE_MAPPING` | [PENDING] |

---

## 3. Migration Strategy Decisions

| Dependency | Strategy | Rationale | Action |
|------------|----------|-----------|--------|
| `COMPANY_ID1_MAPPING` | Enrichment Index | Plan Code lookup is core enrichment feature. | Ensure Enrichment Service indexes Plan Codes. |
| `COMPANY_ID2_MAPPING` | Enrichment Index | Group Customer ID is a valid identifier. | Ensure Enrichment Service indexes Group IDs. |
| `COMPANY_ID3_MAPPING` | Static Config | Small, static list of special cases. | Add to `company_id_overrides_plan.yml`. |
| `COMPANY_ID5_MAPPING` | Enrichment Index | Account Name lookup is core enrichment feature. | Ensure Enrichment Service indexes Account Names. |
| `DEFAULT_PLAN_CODE_MAPPING` | Static/Service | Used for `组合代码` -> `计划代码`. | Map in code or load from DB. |

---

## 4. Migration Validation Checklist

- [ ] `COMPANY_ID3_MAPPING` values exist in `company_id_overrides_plan.yml`.
- [ ] Enrichment Service can resolve by `计划代码`.
- [ ] Enrichment Service can resolve by `客户名称`.

---

## 5. Column Mappings

| Legacy Column | Target Column | Transformation | Notes |
|---------------|---------------|----------------|-------|
| 机构 | 机构名称 | Rename | |
| 计划号 | 计划代码 | Rename | |
| 流失（含待遇支付） | 流失_含待遇支付 | Rename | |
| 机构名称 | 机构代码 | Mapping | Use `COMPANY_BRANCH_MAPPING` |
| 业务类型 | 产品线代码 | Mapping | Use `BUSINESS_TYPE_CODE_MAPPING` |
| 客户名称 | 年金账户名 | Copy | Copy before cleaning customer name |
| 集团企业客户号 | company_id | Mapping | Step 2 resolution (legacy) |

---

## 6. Cleansing Rules

| Rule ID | Field | Rule Type | Logic | Priority |
|---------|-------|-----------|-------|----------|
| CR-001 | 机构代码 | mapping | `COMPANY_BRANCH_MAPPING` | 1 |
| CR-002 | 月度 | date_parse | `parse_to_standard_date` | 1 |
| CR-003 | 计划代码 | replacement | `1P0290`->`P0290`, `1P0807`->`P0807` | 1 |
| CR-004 | 计划代码 | conditional_default | If empty & 集合计划 -> `AN001`; If empty & 单一计划 -> `AN002` | 2 |
| CR-005 | 机构代码 | default | Replace "null"/NaN with "G00" | 3 |
| CR-006 | 组合代码 | regex_replace | Remove start "F" | 1 |
| CR-007 | 组合代码 | conditional_default | `QTAN003` for 职年; else map `DEFAULT_PORTFOLIO_CODE_MAPPING` | 2 |
| CR-008 | 客户名称 | clean | `clean_company_name` | 2 |
| CR-009 | 集团企业客户号 | string | `lstrip("C")` | 1 |

---

## 7. Company ID Resolution Strategy

**Priority Order:**

1.  **Plan Code Lookup:** Map `计划代码` using `COMPANY_ID1_MAPPING`.
2.  **Group Customer Lookup:** Map `集团企业客户号` (stripped) using `COMPANY_ID2_MAPPING`.
3.  **Special Fallback:** If `plan + customer` match special criteria (legacy logic), use `COMPANY_ID3_MAPPING` or default `600866980`.
4.  **Customer Name Lookup:** Map `客户名称` using `COMPANY_ID4_MAPPING`.
5.  **Account Name Lookup:** Map `年金账户名` using `COMPANY_ID5_MAPPING`.

---

## 8. Validation Rules

### Required Fields
- [x] 计划代码
- [x] 月度

### Business Rules
- `月度` must be valid date.
- `当期收益率` should be between -100% and 100% (sanity check).
- `company_id` should be populated where possible.

---

## 9. Special Processing Notes

- **Manual Overrides in Branch Mapping:**
    - 内蒙 -> G31
    - 战略 -> G37
    - 北京其他 -> G37
    - (See `constants.py` for full list)

---

## 10. Parity Validation Checklist

- [ ] Row count match.
- [ ] `company_id` resolution match rate > 99%.
- [ ] Asset scale sums match.
