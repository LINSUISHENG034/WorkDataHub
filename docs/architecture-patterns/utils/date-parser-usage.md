# Date Parser Usage Guide

**Module:** `work_data_hub.utils.date_parser`
**Story:** 2.4 - Chinese Date Parsing Utilities
**Epic:** 2 - Multi-Layer Data Quality Framework

---

## Overview

The date parser provides robust utilities for parsing various Chinese date formats commonly found in Excel files and business data. It handles inconsistent date formats uniformly, converting them to Python `date` objects with validation.

### Key Features

- ✅ **Multiple format support**: Integer YYYYMM, Chinese format (YYYY年MM月), ISO (YYYY-MM), 2-digit years
- ✅ **Full-width digit normalization**: Automatically converts ０-９ to 0-9
- ✅ **Date range validation**: Enforces 2000-2030 valid range
- ✅ **Clear error messages**: Lists all supported formats when parsing fails
- ✅ **Type safety**: Full type hints for IDE support
- ✅ **High performance**: ≥2000 rows/s parsing throughput

---

## Quick Start

### Basic Usage

```python
from datetime import date
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

# Parse various formats
result1 = parse_yyyymm_or_chinese(202501)           # Integer YYYYMM
# → date(2025, 1, 1)

result2 = parse_yyyymm_or_chinese("2025年1月")      # Chinese format
# → date(2025, 1, 1)

result3 = parse_yyyymm_or_chinese("2025-01")        # ISO format
# → date(2025, 1, 1)

result4 = parse_yyyymm_or_chinese(date(2025, 1, 1)) # Date passthrough
# → date(2025, 1, 1)

result5 = parse_yyyymm_or_chinese("25年1月")        # 2-digit year
# → date(2025, 1, 1)  (assumes 20xx for <50)
```

### Error Handling

```python
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

try:
    result = parse_yyyymm_or_chinese("invalid_date")
except ValueError as e:
    print(e)
    # "Cannot parse 'invalid_date' as date. Supported formats:
    #  YYYYMM, YYYYMMDD, YYYY年MM月, YYYY年MM月DD日, YYYY-MM, YYYY-MM-DD, YY年MM月"

try:
    result = parse_yyyymm_or_chinese(199001)  # Out of range
except ValueError as e:
    print(e)
    # "Date 1990-01 outside valid range 2000-2030"
```

---

## Supported Date Formats

| Format | Example Input | Parsed Result | Notes |
|--------|--------------|---------------|-------|
| Integer YYYYMM | `202501` | `date(2025, 1, 1)` | First day of month |
| Integer YYYYMMDD | `20250115` | `date(2025, 1, 15)` | Specific day |
| Chinese YYYY年MM月 | `"2025年1月"` | `date(2025, 1, 1)` | First day of month |
| Chinese YYYY年MM月DD日 | `"2025年1月15日"` | `date(2025, 1, 15)` | Specific day |
| ISO YYYY-MM | `"2025-01"` | `date(2025, 1, 1)` | First day of month |
| ISO YYYY-MM-DD | `"2025-01-15"` | `date(2025, 1, 15)` | Specific day |
| 2-digit year YY年MM月 | `"25年1月"` | `date(2025, 1, 1)` | <50 → 20xx, ≥50 → 19xx |
| Date object | `date(2025, 1, 1)` | `date(2025, 1, 1)` | Validated passthrough |
| Full-width digits | `"２０２５年０１月"` | `date(2025, 1, 1)` | Auto-normalized to half-width |

---

## Integration with Pydantic Models

### Recommended Pattern: Field Validator

Use `@field_validator` with `mode='before'` to parse dates during Pydantic validation:

```python
from datetime import date
from pydantic import BaseModel, field_validator
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese


class AnnuityPerformanceOut(BaseModel):
    """Strict output model with date parsing."""

    月度: date  # Type hint as date (strict)
    计划代码: str
    期末资产规模: float

    @field_validator('月度', mode='before')
    @classmethod
    def parse_date_field(cls, v):
        """
        Parse various date formats into date object.

        Supports:
        - Integer: 202501 → date(2025, 1, 1)
        - Chinese: "2025年1月" → date(2025, 1, 1)
        - ISO: "2025-01" → date(2025, 1, 1)
        - 2-digit year: "25年1月" → date(2025, 1, 1)

        Raises:
            ValueError: If date cannot be parsed or is outside 2000-2030 range
        """
        if v is None:
            return v
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError as e:
            raise ValueError(f"Field '月度': {str(e)}") from e


# Usage
data = {
    "月度": 202501,  # Will be parsed to date(2025, 1, 1)
    "计划代码": "PLAN001",
    "期末资产规模": 1000000.0,
}

model = AnnuityPerformanceOut(**data)
assert model.月度 == date(2025, 1, 1)
```

### Batch Processing with Error Collection

```python
from pydantic import ValidationError
from typing import List, Tuple

def process_excel_rows(rows: List[dict]) -> Tuple[List[AnnuityPerformanceOut], List[dict]]:
    """
    Process Excel rows with error collection.

    Returns:
        Tuple of (valid_models, failed_rows_with_errors)
    """
    valid_models = []
    failed_rows = []

    for i, row in enumerate(rows):
        try:
            model = AnnuityPerformanceOut(**row)
            valid_models.append(model)
        except ValidationError as e:
            failed_rows.append({
                "row_number": i + 1,
                "data": row,
                "errors": e.errors(),
            })

    return valid_models, failed_rows


# Usage
rows = [
    {"月度": 202501, "计划代码": "PLAN001", "期末资产规模": 1000000.0},
    {"月度": "2025年1月", "计划代码": "PLAN002", "期末资产规模": 2000000.0},
    {"月度": "invalid", "计划代码": "PLAN003", "期末资产规模": 3000000.0},  # Will fail
]

valid, failed = process_excel_rows(rows)
print(f"Valid: {len(valid)}, Failed: {len(failed)}")
# Valid: 2, Failed: 1
```

---

## Advanced Usage

### Backwards-Compatible Wrapper

For code that expects `None` on parse failure (legacy behavior), use `parse_chinese_date`:

```python
from work_data_hub.utils.date_parser import parse_chinese_date

# Returns None instead of raising ValueError
result1 = parse_chinese_date("invalid")  # → None
result2 = parse_chinese_date(None)       # → None
result3 = parse_chinese_date(202501)     # → date(2025, 1, 1)
```

### Additional Utility Functions

```python
from work_data_hub.utils.date_parser import (
    extract_year_month_from_date,
    format_date_as_chinese,
    normalize_date_for_database,
)

# Extract year and month
year, month = extract_year_month_from_date(202501)
# → (2025, 1)

# Format as Chinese
chinese_str = format_date_as_chinese(date(2025, 1, 1))
# → "2025年1月"

# Normalize to database format (ISO)
db_str = normalize_date_for_database(202501)
# → "2025-01-01"
```

---

## Performance

The date parser is designed for high-throughput batch processing:

- **Throughput:** ≥2000 rows/s on standard hardware
- **Validation overhead:** <5% in typical pipelines
- **Regex compilation:** Patterns compiled at module load (one-time cost)

### Performance Testing

```python
import time
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

# Generate test data
test_dates = [202501 + i for i in range(10000)]

# Measure throughput
start = time.time()
results = [parse_yyyymm_or_chinese(d) for d in test_dates]
duration = time.time() - start

rows_per_second = len(test_dates) / duration
print(f"Throughput: {rows_per_second:.0f} rows/s")
# Typical: 3000-5000 rows/s
```

---

## Error Messages

The parser provides clear, actionable error messages:

### Format Not Recognized

```
ValueError: Cannot parse 'xyz123' as date. Supported formats: YYYYMM, YYYYMMDD,
YYYY年MM月, YYYY年MM月DD日, YYYY-MM, YYYY-MM-DD, YY年MM月 (2-digit year)
```

### Date Out of Range

```
ValueError: Date 1990-01 outside valid range 2000-2030
```

### Invalid Date Values

```
ValueError: Invalid date value: month must be in 1..12
```

---

## Common Use Cases

### Use Case 1: Excel Data Import

```python
import pandas as pd
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

# Read Excel file
df = pd.read_excel("annuity_data.xlsx", sheet_name="规模明细")

# Parse date column
df['月度'] = df['月度'].apply(
    lambda x: parse_yyyymm_or_chinese(x) if pd.notna(x) else None
)
```

### Use Case 2: Cleansing Registry Integration

```python
from work_data_hub.infrastructure.cleansing.registry import rule, RuleCategory
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

@rule("parse_chinese_date", RuleCategory.DATE, "Parse Chinese date formats")
def parse_chinese_date_rule(value):
    """
    Cleansing rule for date parsing.

    Can be applied via registry.apply_rules(value, ['parse_chinese_date'])
    """
    return parse_yyyymm_or_chinese(value)
```

### Use Case 3: API Response Validation

```python
from pydantic import BaseModel, field_validator
from datetime import date
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

class AnnuityReportRequest(BaseModel):
    """API request with flexible date input."""

    report_period: date
    plan_code: str

    @field_validator('report_period', mode='before')
    @classmethod
    def parse_period(cls, v):
        """Accept YYYYMM, YYYY年MM月, or YYYY-MM formats."""
        return parse_yyyymm_or_chinese(v)


# API handler
def generate_report(request: AnnuityReportRequest):
    # request.report_period is guaranteed to be a date object
    return f"Report for {request.report_period.isoformat()}"


# Client can send any supported format
response = generate_report(AnnuityReportRequest(
    report_period=202501,  # or "2025年1月" or "2025-01"
    plan_code="PLAN001"
))
```

---

## Testing

### Unit Testing with Pytest

```python
import pytest
from datetime import date
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese


def test_parse_various_formats():
    """Test all supported date formats."""
    assert parse_yyyymm_or_chinese(202501) == date(2025, 1, 1)
    assert parse_yyyymm_or_chinese("2025年1月") == date(2025, 1, 1)
    assert parse_yyyymm_or_chinese("2025-01") == date(2025, 1, 1)
    assert parse_yyyymm_or_chinese("25年1月") == date(2025, 1, 1)
    assert parse_yyyymm_or_chinese(date(2025, 1, 1)) == date(2025, 1, 1)


def test_full_width_digits():
    """Test full-width digit normalization."""
    assert parse_yyyymm_or_chinese("２０２５年０１月") == date(2025, 1, 1)


def test_invalid_format_raises():
    """Test error handling for invalid formats."""
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_yyyymm_or_chinese("invalid")


def test_out_of_range_raises():
    """Test date range validation."""
    with pytest.raises(ValueError, match="outside valid range"):
        parse_yyyymm_or_chinese(199001)  # Before 2000
```

---

## Architecture & Design

### Clean Architecture Compliance

- **Layer:** `utils/` (shared utilities)
- **Dependencies:** Python stdlib only (no I/O, no external services)
- **Usage:** Imported by domain layer (Pydantic models, pipeline steps)
- **Pattern:** Pure functions with no side effects

### Date Range Rationale

**Valid range: 2000-2030**

- **Why 2000 minimum?** Legacy data quality issues before Y2K
- **Why 2030 maximum?** Catch data entry errors (typos, transposed digits)
- **Configurable?** Currently hardcoded; can be made configurable if needed

### 2-Digit Year Handling

**Rule:** `YY < 50 → 20YY`, `YY ≥ 50 → 19YY`

- `"25年1月"` → `2025-01-01`
- `"49年12月"` → `2049-12-01`
- `"50年1月"` → `1950-01-01` (out of range, raises error)

This follows standard conventions and is enforced by range validation.

---

## References

- **PRD:** [FR-3.4 Chinese Date Parsing](../../PRD.md#fr-34-chinese-date-parsing)
- **Architecture:** [Decision #5: Explicit Chinese Date Format Priority](../architecture.md#decision-5-explicit-chinese-date-format-priority)
- **Epic Tech Spec:** [Epic 2 Story 2.4](../sprint-artifacts/tech-spec-epic-2.md)
- **Story:** [Story 2.4 Documentation](../sprint-artifacts/2-4-chinese-date-parsing-utilities.md)
- **Tests:** `tests/utils/test_date_parser.py`
- **Performance Tests:** `tests/performance/test_story_2_4_performance.py`

---

## Troubleshooting

### Common Issues

**Issue:** `ValueError: Date 2025-13 outside valid range 2000-2030`
- **Cause:** Invalid month value (13)
- **Fix:** Validate month is 1-12 before calling parser

**Issue:** Performance slower than expected
- **Cause:** Regex patterns not cached (shouldn't happen if imported normally)
- **Fix:** Ensure module-level import, not dynamic import in loop

**Issue:** Full-width digits not recognized
- **Cause:** Character encoding issues
- **Fix:** Ensure file/data is UTF-8 encoded

---

## Changelog

**2025-11-17** - Initial documentation
- Comprehensive usage guide with examples
- Pydantic integration patterns
- Performance guidance and troubleshooting

---

**Maintained by:** Data Engineering Team
**Contact:** See project README for team contact information
