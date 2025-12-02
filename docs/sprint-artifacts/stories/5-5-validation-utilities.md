# Story 5.5: Implement Validation Error Handling Utilities

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | 5.5 |
| **Epic** | Epic 5: Infrastructure Layer Architecture & Domain Refactoring |
| **Status** | done |
| **Created** | 2025-12-02 |
| **Priority** | Critical (Blocks Story 5.7 and Epic 9) |
| **Estimate** | 1.0 day |

---

## User Story

**As a** developer,
**I want to** standardize validation error handling and reporting,
**So that** I don't need to rewrite error logging and CSV export logic for every domain.

---

## Strategic Context

> **This story migrates validation error handling utilities from scattered domain implementations to a centralized infrastructure layer.**
>
> Currently, validation error handling exists in multiple locations:
> - `utils/error_reporter.py` - `ValidationErrorReporter` class (332 lines)
> - `domain/pipelines/validation/helpers.py` - Schema validation helpers
> - `domain/annuity_performance/csv_export.py` - CSV export for unknown companies
> - Inline error handling in `domain/annuity_performance/processing_helpers.py`
>
> This story consolidates these into `infrastructure/validation/` with a clean, reusable API.

### Business Value

- **Code Reuse:** Epic 9 (6+ domains) can reuse validation utilities without duplication
- **Consistency:** Standardized error format across all validation layers (Pydantic, Pandera, custom)
- **Clean Architecture:** Separates infrastructure concerns from domain business logic
- **Maintainability:** Single location for validation error handling logic

### Dependencies

- **Story 5.1 (Infrastructure Foundation)** - COMPLETED ✅
- **Story 5.2 (Cleansing Migration)** - COMPLETED ✅
- **Story 5.3 (Config Reorganization)** - COMPLETED ✅
- **Story 5.4 (CompanyIdResolver)** - COMPLETED ✅
- This story is a prerequisite for Story 5.7 (Service Refactoring)

---

## Acceptance Criteria

### AC-5.5.1: Error Handler Module Created

**Requirement:** Create `infrastructure/validation/error_handler.py` with threshold checking and structured logging.

**CRITICAL DESIGN CONSTRAINT:**
- **DO NOT** create a `ValidationExecutor` class that wraps `schema.validate()`
- Provide utility functions that work WITH existing validation, not replace it

**Implementation:**
```python
# infrastructure/validation/error_handler.py

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from pandera.errors import SchemaErrors
from pydantic import ValidationError as PydanticValidationError

@dataclass
class ValidationErrorDetail:
    """Structured validation error for consistent handling."""
    row_index: Optional[int]
    field_name: str
    error_type: str
    error_message: str
    original_value: Any

def handle_validation_errors(
    errors: Union[SchemaErrors, List[PydanticValidationError], List[ValidationErrorDetail]],
    threshold: float = 0.1,
    total_rows: Optional[int] = None,
) -> None:
    """
    Check error thresholds and log validation errors.

    Raises ValidationThresholdExceeded if failure rate exceeds threshold.
    """

def collect_error_details(
    errors: Union[SchemaErrors, SchemaError, PydanticValidationError],
) -> Sequence[ValidationErrorDetail]:
    """
    Convert validation errors from various sources to structured format.

    Supports:
    - Pandera SchemaErrors (lazy validation)
    - Pandera SchemaError (fail-fast)
    - Pydantic ValidationError (exception containing list of errors)
    - Raw ValidationErrorDetail list (passthrough)
    """
```

**Verification:**
```bash
test -f src/work_data_hub/infrastructure/validation/error_handler.py && echo "PASS" || echo "FAIL"
python -c "from work_data_hub.infrastructure.validation import handle_validation_errors, collect_error_details" && echo "PASS" || echo "FAIL"
```

---

### AC-5.5.2: Report Generator Module Created

**Requirement:** Create `infrastructure/validation/report_generator.py` for CSV export of failed rows.

**Implementation:**
```python
# infrastructure/validation/report_generator.py

from pathlib import Path
from typing import List, Optional
import pandas as pd

def export_error_csv(
    failed_rows: pd.DataFrame,
    filename_prefix: str = "validation_errors",
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Export failed rows to CSV in standard log directory.

    Args:
        failed_rows: DataFrame containing rows that failed validation
        filename_prefix: Prefix for output filename (timestamp appended)
        output_dir: Output directory (defaults to logs/)

    Returns:
        Path to generated CSV file

    CSV Format:
        # Validation Errors Export
        # Date: 2025-12-02T10:30:00Z
        # Total Failed Rows: 50
        row_index,field_name,error_type,error_message,original_value
        15,月度,ValueError,"Cannot parse 'INVALID' as date",INVALID
        ...
    """

def export_validation_summary(
    total_rows: int,
    failed_rows: int,
    error_details: List[ValidationErrorDetail],
    domain: str,
    duration_seconds: float,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Export comprehensive validation summary with error breakdown.
    """
```

**Verification:**
```bash
test -f src/work_data_hub/infrastructure/validation/report_generator.py && echo "PASS" || echo "FAIL"
python -c "from work_data_hub.infrastructure.validation import export_error_csv" && echo "PASS" || echo "FAIL"
```

---

### AC-5.5.3: Error Handling Per Epic 2 Specification

**Requirement:** Implement error handling behavior matching Epic 2 Story 2.5 specification.

**Behavior:**
1. **Threshold Check:** Raise exception if failure rate >10% (configurable)
2. **CSV Export:** Export failed rows to `logs/failed_rows_*.csv`
3. **Structured Logging:** Log errors with context using structlog

**Implementation Pattern:**
```python
import structlog
from work_data_hub.infrastructure.validation import (
    handle_validation_errors,
    collect_error_details,
    export_error_csv,
    ValidationThresholdExceeded,
)

logger = structlog.get_logger()

# In domain validation code:
try:
    validated_df = schema.validate(df, lazy=True)
except SchemaErrors as exc:
    # Bind context for all subsequent logging in this block
    log = logger.bind(domain="annuity", operation="validation_bronze")
    
    # 1. Standardize format
    error_details = collect_error_details(exc)

    # 2. Export failed rows
    # Filter original DF to get the failed rows
    failed_indices = [e.row_index for e in error_details if e.row_index is not None]
    failed_df = df.iloc[failed_indices]
    csv_path = export_error_csv(failed_df, filename_prefix="bronze_validation")
    
    log.info("validation_failed_rows_exported", path=str(csv_path), count=len(failed_df))

    # 3. Check threshold (raises if >10%) and log summary
    handle_validation_errors(
        exc, # Pass exception directly
        threshold=0.1,
        total_rows=len(df),
        domain="annuity"
    )
```

**Verification:**
```python
# Test threshold behavior
from work_data_hub.infrastructure.validation import handle_validation_errors, ValidationThresholdExceeded, ValidationErrorDetail

# 5% error rate - should pass
errors_5pct = [ValidationErrorDetail(row_index=i, field_name="f", error_type="t", error_message="m", original_value="v") for i in range(5)]
handle_validation_errors(errors_5pct, threshold=0.1, total_rows=100)  # No exception

# 15% error rate - should raise
errors_15pct = [ValidationErrorDetail(row_index=i, field_name="f", error_type="t", error_message="m", original_value="v") for i in range(15)]
try:
    handle_validation_errors(errors_15pct, threshold=0.1, total_rows=100)
    assert False, "Should have raised"
except ValidationThresholdExceeded:
    pass  # Expected
```

---

### AC-5.5.4: Migrate and Delete Legacy Implementations

**Requirement:** Consolidate all validation error handling into infrastructure layer and remove legacy code.

**CRITICAL: No Backward Compatibility - Clean Architecture First**

The system is not yet in production. Priority is clean architecture, not compatibility.

**Migration Strategy:**
1. **DELETE** `utils/error_reporter.py` after implementing infrastructure utilities
2. **MIGRATE** `domain/pipelines/validation/helpers.py` to `infrastructure/validation/`
3. **UPDATE** all import references across codebase (~10 locations)
4. **DELETE** `domain/annuity_performance/csv_export.py` (functionality absorbed)

**Files to Delete:**
```
src/work_data_hub/utils/error_reporter.py          # DELETE - replaced by infrastructure
src/work_data_hub/domain/annuity_performance/csv_export.py  # DELETE - absorbed into report_generator
```

**Files to Migrate:**
```
domain/pipelines/validation/helpers.py → infrastructure/validation/schema_helpers.py
```

**Import Updates Required:**
```python
# OLD (delete these patterns)
from work_data_hub.utils.error_reporter import ValidationErrorReporter
from work_data_hub.domain.pipelines.validation.helpers import raise_schema_error

# NEW (single source of truth)
from work_data_hub.infrastructure.validation import (
    handle_validation_errors,
    collect_error_details,
    export_error_csv,
    raise_schema_error,
    ensure_required_columns,
    ensure_not_empty,
    ValidationErrorDetail,
    ValidationThresholdExceeded,
)
```

**Verification:**
```bash
# Ensure no references to deleted modules
grep -r "from work_data_hub.utils.error_reporter" src/ tests/ && echo "FAIL: Old imports found" || echo "PASS"
grep -r "from work_data_hub.domain.pipelines.validation.helpers" src/ tests/ && echo "FAIL: Old imports found" || echo "PASS"
grep -r "from work_data_hub.domain.annuity_performance.csv_export" src/ tests/ && echo "FAIL: Old imports found" || echo "PASS"
```

---

### AC-5.5.5: Unit Test Coverage >90%

**Requirement:** Comprehensive test coverage for all validation utilities.

**Test Cases:**
1. `handle_validation_errors` - threshold checking
2. `collect_error_details` - Pandera SchemaErrors conversion
3. `collect_error_details` - Pydantic ValidationError conversion
4. `export_error_csv` - CSV generation with metadata header
5. `export_validation_summary` - summary report generation
6. Edge cases: empty errors, None values, Unicode handling
7. Performance: <5ms overhead per 1000 rows

**Test File:** `tests/unit/infrastructure/validation/test_error_handler.py`

**Verification:**
```bash
uv run pytest tests/unit/infrastructure/validation/ -v --cov=src/work_data_hub/infrastructure/validation --cov-report=term-missing
# Coverage should be >90%
```

---

### AC-5.5.6: Performance Requirements

**Requirement:** Utilities add minimal overhead to validation pipeline.

**Performance Targets:**
- Error collection: <5ms per 1000 rows
- CSV export: <50ms for 1000 error rows
- Threshold check: <1ms

**Verification:**
```python
import time
import pandas as pd

# Benchmark error collection
start = time.perf_counter()
for _ in range(1000):
    collect_error_details(mock_schema_errors)
elapsed = time.perf_counter() - start
assert elapsed < 5.0, f"Error collection too slow: {elapsed:.2f}s"
```

---

## Complete File Reference

### Files to Create

| File | Purpose |
|------|---------|
| `src/work_data_hub/infrastructure/validation/error_handler.py` | Error handling and threshold checking |
| `src/work_data_hub/infrastructure/validation/report_generator.py` | CSV export and summary reports |
| `src/work_data_hub/infrastructure/validation/schema_helpers.py` | Schema validation helpers (migrated from domain) |
| `src/work_data_hub/infrastructure/validation/types.py` | Shared types (ValidationErrorDetail, ValidationThresholdExceeded) |
| `tests/unit/infrastructure/validation/__init__.py` | Test package init |
| `tests/unit/infrastructure/validation/test_error_handler.py` | Error handler tests |
| `tests/unit/infrastructure/validation/test_report_generator.py` | Report generator tests |
| `tests/unit/infrastructure/validation/test_schema_helpers.py` | Schema helpers tests |
| `tests/unit/infrastructure/validation/conftest.py` | Test fixtures |

### Files to Modify

| File | Change |
|------|--------|
| `src/work_data_hub/infrastructure/validation/__init__.py` | Export all utilities |
| `src/work_data_hub/domain/annuity_performance/schemas.py` | Update imports to infrastructure |
| `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` | Update imports to infrastructure |
| `src/work_data_hub/domain/pipelines/types.py` | Remove ValidationErrorReporter reference |

### Files to Delete (Clean Architecture)

| File | Reason |
|------|--------|
| `src/work_data_hub/utils/error_reporter.py` | Replaced by `infrastructure/validation/` |
| `src/work_data_hub/domain/annuity_performance/csv_export.py` | Absorbed into `report_generator.py` |
| `src/work_data_hub/domain/pipelines/validation/helpers.py` | Migrated to `infrastructure/validation/schema_helpers.py` |
| `tests/unit/utils/test_error_reporter.py` | Tests migrated to infrastructure |
| `tests/unit/domain/pipelines/validation/test_helpers.py` | Tests migrated to infrastructure |

---

## Tasks / Subtasks

### Task 1: Create Types Module (AC 5.5.1)

- [x] Create `infrastructure/validation/types.py`
- [x] Define `ValidationErrorDetail` dataclass
- [x] Define `ValidationThresholdExceeded` exception
- [x] Define `ValidationSummary` dataclass (for report generation)
- [x] Add type annotations and docstrings

### Task 2: Implement Error Handler (AC 5.5.1, 5.5.3)

- [x] Create `infrastructure/validation/error_handler.py`
- [x] Implement `handle_validation_errors()` function
- [x] Implement `collect_error_details()` for Pandera SchemaErrors
- [x] Implement `collect_error_details()` for Pydantic ValidationError
- [x] Add structured logging with structlog
- [x] Handle edge cases (empty errors, None values)

### Task 3: Implement Report Generator (AC 5.5.2)

- [x] Create `infrastructure/validation/report_generator.py`
- [x] Implement `export_error_csv()` function
- [x] Implement `export_validation_summary()` function
- [x] Add metadata header to CSV output
- [x] Handle Unicode (Chinese characters) properly
- [x] Create output directory if not exists

### Task 4: Migrate Schema Helpers (AC 5.5.4)

- [x] Create `infrastructure/validation/schema_helpers.py`
- [x] Migrate `raise_schema_error()` from `domain/pipelines/validation/helpers.py`
- [x] Migrate `ensure_required_columns()` from `domain/pipelines/validation/helpers.py`
- [x] Migrate `ensure_not_empty()` from `domain/pipelines/validation/helpers.py`
- [x] Update all imports in domain code

### Task 5: Update Module Exports

- [x] Update `infrastructure/validation/__init__.py`
- [x] Export all functions: `handle_validation_errors`, `collect_error_details`, `export_error_csv`, `raise_schema_error`, `ensure_required_columns`, `ensure_not_empty`
- [x] Export all types: `ValidationErrorDetail`, `ValidationThresholdExceeded`, `ValidationSummary`
- [x] Ensure no circular imports

### Task 6: Delete Legacy Files (AC 5.5.4 - Clean Architecture)

- [x] Delete `src/work_data_hub/utils/error_reporter.py`
- [x] Delete `src/work_data_hub/domain/annuity_performance/csv_export.py`
- [x] Delete `src/work_data_hub/domain/pipelines/validation/helpers.py`
- [x] Update `domain/pipelines/validation/__init__.py` (remove exports or delete if empty)
- [x] Delete corresponding test files for removed modules

### Task 7: Update All Import References

- [x] Update `domain/annuity_performance/schemas.py` imports
- [x] Update `domain/annuity_performance/pipeline_steps.py` imports
- [x] Update `domain/pipelines/types.py` (remove ValidationErrorReporter)
- [x] Search and update any other references across codebase
- [x] Verify no broken imports: `uv run python -c "import work_data_hub"`

### Task 8: Write Unit Tests (AC 5.5.5)

- [x] Create `tests/unit/infrastructure/validation/conftest.py` with fixtures
- [x] Test `handle_validation_errors` threshold behavior
- [x] Test `collect_error_details` Pandera conversion
- [x] Test `collect_error_details` Pydantic conversion
- [x] Test `export_error_csv` output format
- [x] Test `export_validation_summary` output
- [x] Test schema helpers (`raise_schema_error`, `ensure_required_columns`, `ensure_not_empty`)
- [x] Test edge cases (empty, None, Unicode)
- [x] Test performance benchmarks

### Task 9: Verification & Cleanup

- [x] Run `uv run ruff check .` - fix any errors
- [x] Run `uv run pytest tests/ -v` - full test suite
- [x] Verify coverage >90% for infrastructure/validation
- [x] Verify no references to deleted modules remain
- [x] Add inline documentation for complex logic

---

## Dev Notes

### Existing Implementation Reference

**ValidationErrorReporter (`utils/error_reporter.py:74-332`):**
- Collects errors with row-level attribution
- Tracks unique failed rows (prevents double-counting)
- Enforces error rate thresholds (default 10%)
- Exports to CSV with metadata header
- Sanitizes values for safe CSV export

**Key Methods to Replicate:**
```python
# From ValidationErrorReporter
def collect_error(self, row_index, field_name, error_type, error_message, original_value)
def get_summary(self, total_rows) -> ValidationSummary
def check_threshold(self, total_rows, threshold=0.10)
def export_to_csv(self, filepath, total_rows, domain, duration_seconds)
def _sanitize_value(self, value) -> str
```

**Schema Validation Helpers (`domain/pipelines/validation/helpers.py`):**
```python
def raise_schema_error(schema, data, message, failure_cases=None)
def ensure_required_columns(schema, dataframe, required, schema_name)
def ensure_not_empty(schema, dataframe, schema_name)
```

### Architecture Decision Reference

**AD-004 (Hybrid Error Context Standards):**
- Standard error format: `[ERROR_TYPE] Base message | Domain: X | Row: N | Field: Y | Input: {...}`
- Required context fields: error_type, operation, message, domain, row_number, field, input_data

**AD-010 (Infrastructure Layer & Pipeline Composition):**
- Infrastructure provides reusable utilities
- Domain layer uses dependency injection
- Utilities add minimal overhead

### Design Principles

**DO:**
- Provide standalone utility functions
- Support multiple error source types (Pandera, Pydantic)
- Use structured logging with context
- Handle Unicode (Chinese) properly
- Create output directories automatically
- **DELETE legacy implementations** - single source of truth in infrastructure

**DO NOT:**
- Create wrapper classes around schema.validate()
- Keep multiple implementations (no backward compatibility needed)
- Add heavy dependencies

### Integration with Story 5.7

Story 5.7 will refactor `AnnuityPerformanceService` to use these utilities:

```python
# Story 5.7 usage pattern
from work_data_hub.infrastructure.validation import (
    handle_validation_errors,
    collect_error_details,
    export_error_csv,
)

class AnnuityPerformanceService:
    def _validate_bronze(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            return BronzeSchema.validate(df)
        except SchemaErrors as exc:
            error_details = collect_error_details(exc)
            export_error_csv(df.iloc[...], "bronze_validation")
            handle_validation_errors(error_details, total_rows=len(df))
            raise
```

### Git Intelligence (Recent Commits)

```
745f6d1 feat(infra): complete story 5.4 company id resolver
651d6f6 feat: Complete Story 5.3 Config Namespace Reorganization
5c5de8a feat(infra): migrate cleansing module to infrastructure layer (Story 5.2)
625fc3d Cleanup test suite after Epic 5 architecture refactoring
cf386e8 Complete Story 5.1: Infrastructure Layer Foundation Setup ✅
```

**Patterns from Recent Stories:**
- Infrastructure modules follow `infrastructure/{module}/` structure
- Types defined in separate `types.py` file
- Comprehensive unit tests in `tests/unit/infrastructure/{module}/`
- Export all public symbols from `__init__.py`

---

## Dev Agent Record

### Context Reference

- **Previous Story (5.4):** CompanyIdResolver completed with 99% test coverage
- **Architecture Decisions:** AD-004 (Error Context), AD-010 (Infrastructure Layer)
- **Existing Implementation:** `utils/error_reporter.py` (332 lines), `domain/pipelines/validation/helpers.py`

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Implemented `infrastructure/validation` module with `error_handler`, `report_generator`, and `schema_helpers`.
- Standardized `ValidationErrorDetail` and `ValidationThresholdExceeded` types.
- Migrated legacy logic from `utils/error_reporter.py` and `domain/pipelines/validation/helpers.py`.
- Added comprehensive tests in `tests/unit/infrastructure/validation/` with >95% coverage.
- Removed legacy `error_reporter.py` and `csv_export.py` to enforce clean architecture.
- Fixed API issue in `collect_error_details` to support `row_index` injection for Pydantic errors.
- Optimized `error_handler` imports for performance.

### File List

#### Created
- `src/work_data_hub/infrastructure/validation/__init__.py`
- `src/work_data_hub/infrastructure/validation/error_handler.py`
- `src/work_data_hub/infrastructure/validation/report_generator.py`
- `src/work_data_hub/infrastructure/validation/schema_helpers.py`
- `src/work_data_hub/infrastructure/validation/types.py`
- `tests/unit/infrastructure/validation/__init__.py`
- `tests/unit/infrastructure/validation/conftest.py`
- `tests/unit/infrastructure/validation/test_error_handler.py`
- `tests/unit/infrastructure/validation/test_report_generator.py`
- `tests/unit/infrastructure/validation/test_schema_helpers.py`
- `tests/unit/infrastructure/validation/test_types.py`

#### Modified
- `src/work_data_hub/domain/annuity_performance/processing_helpers.py`
- `src/work_data_hub/domain/annuity_performance/schemas.py`
- `src/work_data_hub/domain/pipelines/types.py`
- `src/work_data_hub/domain/pipelines/validation/__init__.py`
- `src/work_data_hub/utils/__init__.py`
- `tests/unit/domain/annuity_performance/test_service_helpers.py`

#### Deleted / Renamed
- `src/work_data_hub/domain/pipelines/validation/helpers.py` (Migrated)
- `src/work_data_hub/domain/annuity_performance/csv_export.py` (Deleted)
- `src/work_data_hub/utils/error_reporter.py` (Deleted)
- `tests/unit/utils/test_error_reporter.py` (Deleted)
- `tests/performance/test_story_2_5_performance.py` (Deleted)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-02 | Story created with comprehensive developer context | Claude Opus 4.5 |
