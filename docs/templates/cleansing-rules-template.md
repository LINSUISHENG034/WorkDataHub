# Legacy Cleansing Rules Documentation Template

## Purpose

Standard template for documenting legacy cleansing rules before domain migration. Use this template to create a comprehensive reference for Pipeline configuration.

**Related Guides:**

- [Domain Migration Workflow](../guides/domain-migration/workflow.md) - End-to-end migration process
- [Cleansing Rules to Code Mapping](../guides/domain-migration/code-mapping.md) - How to translate this document to code

---

## 1. Domain Overview

| Item | Value |
|------|-------|
| Legacy Cleaner Class | `{ClassName}` |
| Source File | `legacy/annuity_hub/data_handler/data_cleaner.py` |
| Excel Sheet Name | `{sheet_name}` |
| Target Database Table | `{schema}.{table}` |

## 2. Dependency Table Inventory

> **Implementation:** Execute migration scripts before Phase 3. See [Mapping Guide - Section 2](../guides/domain-migration/code-mapping.md#section-2-dependency-table-inventory--migration-execution)

### Critical Dependencies (Must Migrate Before Domain Implementation)

| # | Table Name | Database | Purpose | Row Count | Migration Status |
|---|------------|----------|---------|-----------|-----------------|
| 1 | | | | | [PENDING] |

### Optional Dependencies

| # | Table Name | Database | Purpose | Notes |
|---|------------|----------|---------|-------|
| 1 | | | | |

---

## 3. Migration Strategy Decisions

> **Implementation:** Choose strategy for each dependency, then execute appropriate migration. See [Mapping Guide - Section 2](../guides/domain-migration/code-mapping.md#section-2-dependency-table-inventory--migration-execution)

### Decision Summary

- **Decision Date**: YYYY-MM-DD
- **Decision Maker**: [Name]
- **Reviewed By**: [Name]

### Strategy Options Reference

| Strategy | Description | Typical Use Cases |
|----------|-------------|-------------------|
| Direct Migration | Move table as-is | Simple lookup tables |
| Enrichment Index | Migrate to enterprise.enrichment_index | Company/entity mappings |
| Transform & Load | Restructure data | Complex schema changes |
| Static Embedding | Hardcode in constants | Small, stable lookups |
| Decommission | Mark obsolete | Unused tables |
| Custom Strategy | Team-defined approach | Unique requirements |

### Dependency Table Strategies

| # | Table Name | Legacy Schema | Target Strategy | Target Location | Rationale |
|---|------------|---------------|-----------------|-----------------|-----------|
| 1 | | | | | |

---

## 4. Migration Validation Checklist

> **Implementation:** Complete after executing migrations in Section 2-3.

### Pre-Migration

- [ ] Source database accessible
- [ ] Target schema/index exists
- [ ] Migration script tested in dry-run mode

### Migration Execution

- [ ] Run migration script: `PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py`
- [ ] Verify batch completion without errors

### Post-Migration Validation

- [ ] Row count validation (source vs target)
- [ ] Data sampling validation (10 random keys)
- [ ] Performance validation (lookup latency < 10ms)

---

## 5. Column Mappings

> **Implementation:** Convert to `constants.py` → `COLUMN_MAPPING` and `COLUMN_ALIAS_MAPPING` dicts. See [Mapping Guide - Section 5](../guides/domain-migration/code-mapping.md#section-5-column-mappings--constantspy)

| # | Legacy Column | Target Column | Transformation | Notes |
|---|---------------|---------------|----------------|-------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

---

## 6. Cleansing Rules

> **Implementation:** Convert to `cleansing_rules.yml` (simple rules) or `pipeline_builder.py` (complex rules). See [Mapping Guide - Section 6](../guides/domain-migration/code-mapping.md#section-6-cleansing-rules--cleansing_rulesyml--pipeline_builderpy)

| Rule ID | Field | Rule Type | Logic | Priority | Notes |
|---------|-------|-----------|-------|----------|-------|
| CR-001 | | mapping | | | |
| CR-002 | | date_parse | | | |
| CR-003 | | default_value | | | |

### Rule Types Reference

| Type | Description | Example | Code Target |
|------|-------------|---------|-------------|
| `mapping` | Value mapping using lookup table | `COMPANY_BRANCH_MAPPING` | `MappingStep` or `ReplacementStep` |
| `date_parse` | Date format standardization | `parse_to_standard_date()` | `CleansingStep` or `CalculationStep` |
| `default_value` | Fill missing values with default | `fillna('G00')` | `ReplacementStep` or `CalculationStep` |
| `regex_replace` | Pattern-based string replacement | `str.replace('^F', '')` | `CalculationStep` |
| `conditional` | Conditional logic based on other fields | `mask(condition, value)` | `CalculationStep` |
| `strip_prefix` | Remove prefix from string | `str.lstrip('C')` | `CalculationStep` |
| `normalize` | Text normalization (trim, case, etc.) | `clean_company_name()` | `CleansingStep` |

---

## 7. Company ID Resolution Strategy

> **Implementation:** Configure `CompanyIdResolutionStep` in `pipeline_builder.py`. See [Mapping Guide - Section 7](../guides/domain-migration/code-mapping.md#section-7-company-id-resolution--pipeline_builderpy)

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

## 8. Validation Rules

> **Implementation:** Convert to `models.py` (Pydantic models) and `schemas.py` (Pandera schemas). See [Mapping Guide - Section 8](../guides/domain-migration/code-mapping.md#section-8-validation-rules--modelspy--schemaspy)

### Required Fields

- [ ] Field 1
- [ ] Field 2
- [ ] Field 3

### Data Type Constraints

| Field | Expected Type | Constraint | Notes | Pydantic Field |
|-------|---------------|------------|-------|----------------|
| | `string` | | | `str = Field(...)` |
| | `date` | Format: YYYY-MM-DD | | `date = Field(...)` |
| | `numeric` | | | `Decimal = Field(ge=0)` |

### Business Rules

| Rule ID | Description | Validation Logic | Implementation |
|---------|-------------|------------------|----------------|
| VR-001 | | | `@field_validator` or Pandera `Check` |
| VR-002 | | | `@field_validator` or Pandera `Check` |

---

## 9. Special Processing Notes

> **Implementation:** Add to `constants.py` (manual overrides) and `helpers.py` (edge case handlers). See [Mapping Guide - Section 9](../guides/domain-migration/code-mapping.md#section-9-special-processing-notes--constantspy--helperspy)

### Edge Cases

{Document any special cases that need attention}

### Legacy Quirks

{Document any legacy behavior that seems unusual but must be preserved for parity}

### Known Issues

{Document any known issues or limitations}

---

## 10. Parity Validation Checklist

> **Implementation:** Create validation script at `scripts/tools/parity/validate_{domain}_parity.py`. See [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md)

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
