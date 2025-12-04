# Legacy Cleansing Rules Documentation Template

## Purpose

Standard template for documenting legacy cleansing rules before domain migration. Use this template to create a comprehensive reference for Pipeline configuration.

---

## 1. Domain Overview

| Item | Value |
|------|-------|
| Legacy Cleaner Class | `{ClassName}` |
| Source File | `legacy/annuity_hub/data_handler/data_cleaner.py` |
| Excel Sheet Name | `{sheet_name}` |
| Target Database Table | `{schema}.{table}` |

---

## 2. Column Mappings

| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

---

## 3. Cleansing Rules

| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | | mapping | | | |
| CR-002 | | date_parse | | | |
| CR-003 | | default_value | | | |

### Rule Types Reference

| Type | Description | Example |
|------|-------------|---------|
| `mapping` | Value mapping using lookup table | `COMPANY_BRANCH_MAPPING` |
| `date_parse` | Date format standardization | `parse_to_standard_date()` |
| `default_value` | Fill missing values with default | `fillna('G00')` |
| `regex_replace` | Pattern-based string replacement | `str.replace('^F', '')` |
| `conditional` | Conditional logic based on other fields | `mask(condition, value)` |
| `strip_prefix` | Remove prefix from string | `str.lstrip('C')` |
| `normalize` | Text normalization (trim, case, etc.) | `clean_company_name()` |

---

## 4. Company ID Resolution Strategy

### Priority Order

| Priority | Source Field | Mapping Table | Fallback |
|----------|--------------|---------------|----------|
| 1 | | `COMPANY_ID1_MAPPING` | Next priority |
| 2 | | `COMPANY_ID2_MAPPING` | Next priority |
| 3 | | `COMPANY_ID3_MAPPING` | Default value |
| 4 | | `COMPANY_ID4_MAPPING` | Next priority |
| 5 | | `COMPANY_ID5_MAPPING` | None |

### Default Value Handling

- **Condition:** When all mapping sources fail
- **Default Value:** `{default_company_id}`
- **Logic:** `{describe the fallback logic}`

---

## 5. Validation Rules

### Required Fields

- [ ] Field 1
- [ ] Field 2
- [ ] Field 3

### Data Type Constraints

| Field | Expected Type | Constraint | Notes |
|-------|---------------|------------|-------|
| | `string` | | |
| | `date` | Format: YYYY-MM-DD | |
| | `numeric` | | |

### Business Rules

| Rule ID | Description | Validation Logic |
|---------|-------------|------------------|
| VR-001 | | |
| VR-002 | | |

---

## 6. Special Processing Notes

### Edge Cases

{Document any special cases that need attention}

### Legacy Quirks

{Document any legacy behavior that seems unusual but must be preserved for parity}

### Known Issues

{Document any known issues or limitations}

---

## 7. Parity Validation Checklist

- [ ] Row count matches legacy output
- [ ] Column names match (considering renames)
- [ ] Data values match (100% match rate)
- [ ] Date formats consistent
- [ ] Null handling consistent
- [ ] Company ID resolution consistent

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| YYYY-MM-DD | | Initial documentation |
