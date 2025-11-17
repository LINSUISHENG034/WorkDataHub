# Error Message Quality Standards

**Epic**: Epic 2 - Multi-Layer Data Quality Framework
**Version**: 1.0
**Date**: 2025-11-16
**Audience**: Business users fixing data errors (non-technical)

---

## Overview

This document defines **mandatory** error message quality standards for Epic 2's validation framework. The goal: **90% of validation errors fixable by business users without developer assistance**.

**Problem Statement** (from Epic 1 Retrospective):
> Epic 2 Story 2.5 (Validation Error Reporting) exports failed rows to CSV. Business stakeholders receive files with cryptic error messages like "ValidationError: 1 validation error for AnnuityPerformanceOut". They can't fix source data. Manual error correction takes 4 hours per file. Business abandons framework.

**Solution**: Actionable, field-level errors with examples in business-friendly language.

---

## Quality Standards

### Standard 1: Field-Level Attribution (MANDATORY)

**Rule**: Every error must identify **which field** failed validation.

#### ❌ BAD Examples

```
ValidationError: 1 validation error for AnnuityPerformanceRow
```
→ **Problem**: User doesn't know which field to fix

```
Invalid data in row 42
```
→ **Problem**: No field specified

```
Validation failed
```
→ **Problem**: Generic, no context

#### ✅ GOOD Examples

```
Field 'report_date': Cannot parse 'INVALID' as date
```
→ **Why**: Clear field attribution

```
Field 'scale': Must be non-negative. Got: -100.5
```
→ **Why**: Field + violation + actual value

```
Field 'plan_code': Cannot be empty or whitespace
```
→ **Why**: Specific validation rule

---

### Standard 2: Actionable Guidance (MANDATORY)

**Rule**: Error message must explain **how to fix** the problem, not just what's wrong.

#### ❌ BAD Examples

```
Field 'report_date': Input should be a valid date
```
→ **Problem**: What format? No example provided

```
Field 'portfolio_code': Validation error
```
→ **Problem**: What rule was violated?

```
Field 'scale': Constraint failed
```
→ **Problem**: Which constraint? What value is acceptable?

#### ✅ GOOD Examples

```
Field 'report_date': Cannot parse 'INVALID' as date. Expected format: YYYYMM or YYYY年MM月. Example: 202501
```
→ **Why**: Shows expected format AND example

```
Field 'portfolio_code': Must start with plan prefix. Plan code: 'P001', Portfolio code: 'Z999'. Expected: Portfolio code starting with 'P00'
```
→ **Why**: Explains business rule with context

```
Field 'scale': Must be non-negative. Got: -100.5. Valid example: 1000.0
```
→ **Why**: Shows what's wrong + provides valid example

---

### Standard 3: Example Values (REQUIRED)

**Rule**: Include **valid example** in error message when format/constraint is ambiguous.

**When Required**:
- Date/time formats (YYYYMM vs YYYY-MM-DD vs YYYY年MM月)
- Numeric ranges (0-100 vs 0-1000000)
- String patterns (alphanumeric, specific prefixes, Chinese characters)
- Enum values (list all valid options)

#### Template

```
Field '{field_name}': {problem_description}. Expected: {constraint_description}. Example: {valid_example}
```

#### Examples by Data Type

**Dates**:
```python
# ❌ Bad
"Field 'report_date': Invalid date format"

# ✅ Good
"Field 'report_date': Cannot parse '20250115' as date. Expected format: YYYYMM (月度) or YYYY年MM月 (中文). Example: 202501 or 2025年01月"
```

**Decimals**:
```python
# ❌ Bad
"Field 'scale': Number out of range"

# ✅ Good
"Field 'scale': Value 1500000000.00 exceeds maximum 999999999.99 (9位整数+2位小数). Example: 123456789.12"
```

**Strings with Patterns**:
```python
# ❌ Bad
"Field 'plan_code': Invalid format"

# ✅ Good
"Field 'plan_code': Code 'p-001' contains lowercase. Expected: Uppercase alphanumeric only. Example: P001 or PLAN123"
```

**Enums**:
```python
# ❌ Bad
"Field 'plan_type': Invalid value"

# ✅ Good
"Field 'plan_type': Value '企业' not recognized. Valid options: 企业年金, 职业年金, 养老金产品"
```

---

### Standard 4: Business-Friendly Language (REQUIRED for Chinese users)

**Rule**: Use terminology familiar to business users, not technical jargon.

#### ❌ Technical Jargon (Avoid)

- "Validation error"
- "Constraint violation"
- "Type coercion failed"
- "Regex match failed"
- "Foreign key violation"

#### ✅ Business-Friendly Language (Use)

- "数据格式错误" (data format error)
- "超出允许范围" (exceeds allowed range)
- "必填字段为空" (required field is empty)
- "格式不匹配" (format mismatch)
- "关联数据不存在" (related data not found)

#### Example Translations

**English (Developer)**:
```
Field 'report_date': Validation error - input should be a valid date
```

**Chinese (Business User)**:
```
字段'月度'：日期格式错误，无法识别'INVALID'。请使用格式：YYYYMM 或 YYYY年MM月。示例：202501
```

**Bilingual (Recommended)**:
```
Field '月度' (report_date): Cannot parse 'INVALID' as date. Expected format: YYYYMM or YYYY年MM月. Example: 202501
字段'月度'：日期格式错误。预期格式：YYYYMM 或 YYYY年MM月。示例：202501
```

---

### Standard 5: Row Context (REQUIRED for CSV exports)

**Rule**: Error export must include row identifier AND surrounding context to locate error in source file.

#### Required CSV Columns

| Column | Description | Example |
|--------|-------------|---------|
| `row_index` | 0-based row number in DataFrame | 42 |
| `row_number` | 1-based row number (Excel-friendly) | 43 |
| `field_name` | Field that failed validation | `report_date` |
| `field_value` | Actual value (for debugging) | `INVALID` |
| `error_message` | User-friendly error (Standard 1-4) | `Field 'report_date': Cannot parse...` |
| `context_*` | Key fields for row identification | `plan_code=P001`, `company_name=XX公司` |

#### Example CSV Export

```csv
row_number,field_name,field_value,error_message,plan_code,company_name
43,report_date,INVALID,"Field 'report_date': Cannot parse 'INVALID' as date. Expected format: YYYYMM. Example: 202501",P001,XX年金计划
156,scale,-100.5,"Field 'scale': Must be non-negative. Got: -100.5. Valid range: 0 to 999999999.99",P002,YY企业年金
```

**Why**: Business user can:
1. Find row 43 in original Excel file
2. See it's for plan P001, company XX年金计划
3. Fix `report_date` from `INVALID` to `202501`
4. Re-upload and validate

---

## Implementation Guidelines

### Pydantic Validators (Epic 2 Story 2.1)

```python
from pydantic import BaseModel, Field, field_validator

class AnnuityPerformanceRow(BaseModel):
    report_date: str = Field(description="月度 (YYYYMM)")

    @field_validator("report_date")
    @classmethod
    def validate_report_date(cls, v: str) -> str:
        """Validate report_date format with user-friendly error."""
        import re

        # ❌ Bad: Generic Pydantic error
        # Will produce: "Input should be a valid string"

        # ✅ Good: Custom error with example
        if not re.match(r'^\d{6}$', v):
            raise ValueError(
                f"Cannot parse '{v}' as date. "
                f"Expected format: YYYYMM (月度) or YYYY年MM月 (中文). "
                f"Example: 202501 or 2025年01月"
            )

        # Additional validation: Check if month is valid
        year = int(v[:4])
        month = int(v[4:6])
        if not (1 <= month <= 12):
            raise ValueError(
                f"Invalid month '{month}' in date '{v}'. "
                f"Month must be 01-12. Example: 202501 (January 2025)"
            )

        return v
```

### Pandera Schema Checks (Epic 2 Story 2.2)

```python
import pandera as pa
from pandera import Column, Check

schema = pa.DataFrameSchema({
    "scale": Column(
        pa.Float,
        checks=[
            Check.greater_than_or_equal_to(
                0,
                error="Field 'scale': Must be non-negative. Got: {failure_case}. Valid example: 1000.0"
            ),
            Check.less_than_or_equal_to(
                999999999.99,
                error="Field 'scale': Value {failure_case} exceeds maximum 999999999.99 (9位整数+2位小数)"
            )
        ],
        nullable=False,
        description="规模 (万元)"
    )
})
```

### Custom Cleansing Rules (Epic 2 Story 2.3)

```python
from work_data_hub.domain.pipelines.types import RowTransformStep, StepResult

class CurrencyCleansingStep(RowTransformStep):
    name = "currency_cleansing"

    def apply(self, row: dict, context: Any) -> StepResult:
        """Remove currency symbols with user-friendly errors."""
        field = "scale"
        value = row.get(field)

        if value is None:
            return StepResult(
                row=row,
                errors=[
                    f"Field '{field}' (规模): Required field is empty. "
                    f"Please provide a numeric value. Example: 1000.5"
                ]
            )

        # Attempt cleansing
        import re
        original_value = value
        cleaned = re.sub(r'[¥$,，]', '', str(value))

        try:
            numeric = float(cleaned)
            row[field] = numeric
            return StepResult(row=row)
        except ValueError:
            return StepResult(
                row=row,
                errors=[
                    f"Field '{field}' (规模): Cannot convert '{original_value}' to number. "
                    f"After removing currency symbols: '{cleaned}'. "
                    f"Please provide numeric value only. Valid example: 1000.5"
                ]
            )
```

---

## Testing Error Messages

### Manual Testing Protocol (Epic 2 Story 2.5)

**Acceptance Criterion**: Non-technical stakeholder can fix 90% of failed rows using only the error CSV.

**Test Procedure**:
1. Generate CSV with 20 validation errors (diverse error types)
2. Provide CSV to business stakeholder (no other context)
3. Ask them to fix errors using only the error CSV
4. Track: How many errors fixed in 30 minutes?
5. **Goal**: ≥18/20 errors fixed (90%)

**Sample Test Errors** (Cover all types):
- Date format errors (3 errors)
- Negative numbers (2 errors)
- Empty required fields (3 errors)
- Out-of-range values (2 errors)
- String pattern violations (3 errors)
- Enum/lookup failures (3 errors)
- Business rule violations (4 errors)

### Automated Testing

```python
def test_error_message_quality():
    """Verify error messages meet quality standards."""
    # Trigger validation error
    row = {"report_date": "INVALID", "scale": -100.5}
    result = validation_step.apply(row, context)

    assert len(result.errors) == 2

    # Check report_date error
    date_error = [e for e in result.errors if "report_date" in e][0]

    # Standard 1: Field-level attribution
    assert "Field 'report_date'" in date_error

    # Standard 2: Actionable guidance
    assert "Expected format" in date_error or "请使用格式" in date_error

    # Standard 3: Example value
    assert "Example:" in date_error or "示例" in date_error
    assert "202501" in date_error  # Actual example present

    # Standard 4: Business-friendly (no jargon)
    assert "ValidationError" not in date_error
    assert "Constraint" not in date_error

    # Check scale error
    scale_error = [e for e in result.errors if "scale" in e][0]
    assert "Got: -100.5" in scale_error  # Shows actual value
    assert "non-negative" in scale_error or "非负" in scale_error
```

---

## Error Message Templates

### Template Library

Use these templates for consistency:

#### Date Format Errors

```
Field '{field_name}': Cannot parse '{value}' as date. Expected format: YYYYMM or YYYY年MM月. Example: 202501
字段'{field_name_chinese}'：日期格式错误。预期格式：YYYYMM 或 YYYY年MM月。示例：202501
```

#### Numeric Range Errors

```
Field '{field_name}': Value {value} {violation}. Valid range: {min} to {max}. Example: {example}
字段'{field_name_chinese}'：数值{value}{violation_chinese}。有效范围：{min} 至 {max}。示例：{example}
```

Where `{violation}` = "exceeds maximum" | "below minimum" | "out of range"
Where `{violation_chinese}` = "超出最大值" | "低于最小值" | "超出范围"

#### Required Field Errors

```
Field '{field_name}': Required field is empty. Please provide a value. Example: {example}
字段'{field_name_chinese}'：必填字段为空。请提供值。示例：{example}
```

#### Enum/Lookup Errors

```
Field '{field_name}': Value '{value}' not recognized. Valid options: {option1}, {option2}, {option3}
字段'{field_name_chinese}'：值'{value}'无效。有效选项：{option1}, {option2}, {option3}
```

#### Business Rule Errors

```
Field '{field_name}': Business rule violation. {rule_description}. {context}. Expected: {expected}
字段'{field_name_chinese}'：业务规则违规。{rule_description_chinese}。{context}。预期：{expected_chinese}
```

---

## CSV Export Best Practices

### Filename Convention

```
validation_errors_{domain}_{date}_{run_id}.csv
```

Example: `validation_errors_annuity_performance_20250116_a3f9b2.csv`

### Excel Compatibility

```python
import pandas as pd

# Export with UTF-8 BOM for Excel compatibility
error_df.to_csv(
    filename,
    index=False,
    encoding="utf-8-sig",  # UTF-8 with BOM (Excel-friendly)
    columns=["row_number", "field_name", "error_message", "plan_code", "company_name"]
)
```

### Column Ordering

**Priority order** (most important first):
1. `row_number` - User needs this to find row in source file
2. `field_name` - Which field to fix
3. `error_message` - How to fix it
4. Context columns (`plan_code`, `company_name`) - Locate row
5. `field_value` - For debugging (least important for business user)

---

## Localization Strategy

### Bilingual Errors (Recommended)

```
Field '月度' (report_date): Cannot parse 'INVALID' as date. Expected format: YYYYMM. Example: 202501
字段'月度'：日期格式错误。预期格式：YYYYMM。示例：202501
```

**Advantages**:
- Business users (Chinese speakers) get native language
- Developers (debugging) get English technical terms
- Field mapping clear: `月度` = `report_date`

### Configuration-Based Language

```python
from work_data_hub.config.settings import get_settings

settings = get_settings()

if settings.error_message_language == "zh":
    error_msg = f"字段'{field_chinese}'：日期格式错误..."
elif settings.error_message_language == "en":
    error_msg = f"Field '{field_name}': Cannot parse date..."
else:  # "bilingual"
    error_msg = (
        f"Field '{field_chinese}' ({field_name}): Cannot parse date...\n"
        f"字段'{field_chinese}'：日期格式错误..."
    )
```

---

## References

- [Epic 1 Retrospective: Error Export Usability Disaster](../docs/sprint-artifacts/epic-1-retrospective-2025-11-16.md#failure-scenario-3-the-error-export-usability-disaster)
- [Pipeline Integration Guide: Error Message Best Practices](../docs/pipeline-integration-guide.md#best-practices)
- [Epic 2 Story 2.5: Validation Error Reporting](../docs/sprint-artifacts/stories/)

---

**Document Version**: 1.0
**Mandatory Compliance**: ALL Epic 2 validation stories
**Quality Target**: 90% of errors fixable by business users without developer help
