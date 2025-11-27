# Epic Technical Specification: Multi-Layer Data Quality Framework

Date: 2025-11-16
Author: Link
Epic ID: 2
Status: Contexted

---

## Overview

Epic 2 establishes the **multi-layer data quality framework** that ensures only valid, clean data reaches the PostgreSQL warehouse. This epic implements a defensive validation strategy using:

- **Pydantic v2** for row-level business rule validation (Silver layer)
- **Pandera** for DataFrame-level schema validation (Bronze/Gold layers)
- **Registry-driven cleansing rules** for standardized value transformations
- **Comprehensive error reporting** with actionable feedback for data quality issues

The framework follows the **medallion architecture** (Bronze → Silver → Gold), where each layer applies progressively stricter validation:

- **Bronze Layer**: Validates raw Excel data has expected structure (columns present, basic types)
- **Silver Layer**: Enforces business rules on individual rows (date ranges, numeric constraints, required fields)
- **Gold Layer**: Ensures database integrity constraints (composite PK uniqueness, no nulls in required fields)

This epic builds on Epic 1's pipeline framework, logging, and database infrastructure to create a **safety net** that prevents "garbage in, garbage out" scenarios.

**Business Value**: Data integrity is non-negotiable. This framework catches bad source data immediately with clear error messages, preventing database corruption and enabling fearless refactoring. Invalid data is exported to CSV with specific failure reasons, empowering data providers to fix issues at the source.

**Epic 1 Retrospective Learnings Applied**:
- Mandatory performance acceptance criteria (≥1000 rows/s, <20% overhead)
- 10,000-row test fixtures (not 5-row samples)
- Performance baseline tracking to catch regressions early

---

## Objectives and Scope

### Primary Objectives

1. **Implement multi-layer validation framework** that catches data quality issues at appropriate layers:
   - Bronze: Structural/schema validation (fast, fails early)
   - Silver: Business rule validation (row-level, Pydantic)
   - Gold: Database integrity validation (composite PK uniqueness)

2. **Establish registry-driven cleansing** for standardized transformations:
   - Trim whitespace, normalize company names, parse Chinese dates
   - Reusable rules applicable across all domains
   - Per-domain configuration for enabling/disabling rules

3. **Build comprehensive error reporting** with actionable feedback:
   - Export failed rows to CSV with specific error messages
   - Error thresholds: fail fast if >10% of rows invalid (likely systemic issue)
   - Partial success handling: continue with valid rows when appropriate

4. **Meet mandatory performance requirements**:
   - ≥1000 rows/s validation throughput
   - <20% validation overhead
   - Performance baseline tracking for regression detection

### In Scope

- Pydantic v2 models with Chinese field names for annuity domain
- Pandera DataFrame schemas for Bronze and Gold layers
- Cleansing registry framework with built-in rules
- Chinese date parsing utilities (YYYYMM, YYYY年MM月, YYYY-MM)
- Validation error CSV export with row/field/reason details
- Performance test fixtures (10,000 rows minimum)
- Integration with Epic 1 pipeline framework

### Out of Scope (Deferred)

- **Domain-specific validators beyond annuity**: Future epics will add validators for other domains
- **Real-time validation UI**: MVP uses batch processing only
- **Advanced fuzzy matching**: Simple string normalization only, no Levenshtein distance
- **Async validation**: All validation is synchronous (blocking) for MVP
- **Custom validation DSL**: Use Pydantic/Pandera directly, no abstraction layer

### Success Criteria

1. **Annuity domain validates end-to-end**: Bronze → Silver → Gold with 100% parity to legacy validation logic
2. **Performance criteria met**: All stories pass AC-PERF-1 and AC-PERF-2 (epic-2-performance-acceptance-criteria.md)
3. **Error reporting functional**: Failed rows export to CSV with actionable error messages
4. **Cleansing rules reusable**: Registry enables sharing rules across domains

---

## System Architecture Alignment

### Clean Architecture Layer Mapping

Epic 2 components map to Clean Architecture layers:

| Component | Layer | Module Path | Dependencies |
|-----------|-------|-------------|--------------|
| Pydantic Models | Domain | `domain/annuity_performance/models.py` | Pydantic, cleansing registry |
| Pandera Schemas | Domain | `domain/annuity_performance/schemas.py` | Pandera, date parser |
| Cleansing Registry | Domain | `cleansing/registry.py` | None (pure functions) |
| Date Parser | Utils | `utils/date_parser.py` | stdlib only |
| Validation Steps | Domain | `domain/annuity_performance/pipeline_steps.py` | Epic 1 pipeline framework |

**Dependency Rules Enforced** (from architecture-boundaries.md):
- ✅ Domain layer has NO imports from `io/` or `orchestration/`
- ✅ All infrastructure injected via dependency injection (DI pattern)
- ✅ Validation logic is testable without database/files

### Medallion Stage Alignment

| Medallion Stage | Validation Type | Technology | Responsibility |
|-----------------|-----------------|------------|----------------|
| **Bronze** | Structural schema | Pandera `DataFrameSchema` | I/O layer validates raw Excel structure |
| **Silver** | Business rules | Pydantic `BaseModel` | Domain layer enforces row-level constraints |
| **Gold** | Database integrity | Pandera `DataFrameSchema` + uniqueness checks | Domain layer ensures composite PK uniqueness |

**Rationale**: Each layer validates what it "owns":
- Bronze validates Excel reader output (I/O concern)
- Silver validates business logic (domain concern)
- Gold validates database contracts (domain concern, enforced before I/O layer writes)

### Integration with Epic 1 Infrastructure

Epic 2 builds on Epic 1's foundation:

- **Pipeline Framework (Story 1.5)**: Validation steps implement `TransformStep` protocol
- **Logging (Story 1.3)**: Structured logs for validation metrics (rows processed, failed, duration)
- **Configuration (Story 1.4)**: Validation thresholds configurable via `settings.py`
- **Database Loader (Story 1.8)**: Gold validation ensures data matches database schema before loading

**Example Integration**:
```python
from domain.pipelines.core import Pipeline, PipelineContext
from domain.annuity_performance.pipeline_steps import (
    BronzeValidationStep,
    PydanticRowValidationStep,
    GoldValidationStep,
)

# Epic 1 pipeline framework orchestrates Epic 2 validation steps
pipeline = Pipeline("annuity_validation")
pipeline.add_step(BronzeValidationStep())  # Story 2.2: Pandera schema
pipeline.add_step(PydanticRowValidationStep())  # Story 2.1: Pydantic models
pipeline.add_step(GoldValidationStep())  # Story 2.2: Pandera schema with uniqueness

result = pipeline.run(raw_dataframe, context)
```

---

## Detailed Design

### Services and Modules

#### Module Structure

```
src/work_data_hub/
├── cleansing/
│   ├── __init__.py
│   ├── registry.py              # Story 2.3: CleansingRegistry class
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── string_rules.py      # trim_whitespace, normalize_company_name
│   │   ├── numeric_rules.py     # remove_currency_symbols, round_to_precision
│   │   └── date_rules.py        # standardize_date_format
│   └── config/
│       └── cleansing_rules.yml  # Per-domain rule configuration
├── domain/
│   └── annuity_performance/
│       ├── models.py             # Story 2.1: Pydantic models (In/Out)
│       ├── schemas.py            # Story 2.2: Pandera schemas (Bronze/Gold)
│       └── pipeline_steps.py    # Validation steps using Epic 1 framework
└── utils/
    ├── date_parser.py            # Story 2.4: parse_yyyymm_or_chinese()
    └── error_reporter.py         # Story 2.5: CSV export, error aggregation
```

#### Key Classes and Responsibilities

**1. CleansingRegistry** (`cleansing/registry.py`)
- **Purpose**: Centralized registry of reusable cleansing rules
- **Key Methods**:
  - `register(name: str, func: Callable) -> None`: Register a new rule
  - `apply_rule(value: Any, rule_name: str) -> Any`: Apply single rule
  - `apply_rules(value: Any, rule_names: List[str]) -> Any`: Apply multiple rules in sequence
- **Usage**: Integrated into Pydantic validators via `@field_validator`

**2. AnnuityPerformanceIn/Out** (`domain/annuity_performance/models.py`)
- **Purpose**: Pydantic models for row-level validation
- **Key Features**:
  - `AnnuityPerformanceIn`: Loose validation (accepts messy Excel input)
  - `AnnuityPerformanceOut`: Strict validation (enforces business rules)
  - Custom validators using cleansing registry and date parser
- **Example**:
  ```python
  class AnnuityPerformanceOut(BaseModel):
      月度: date  # Required, parsed from various formats
      计划代码: str = Field(min_length=1)
      company_id: str  # From Epic 5 enrichment
      期末资产规模: float = Field(ge=0)  # Non-negative

      @field_validator('月度', mode='before')
      def parse_date(cls, v):
          return parse_yyyymm_or_chinese(v)  # Story 2.4

      @field_validator('客户名称', mode='before')
      def clean_company_name(cls, v):
          registry = get_cleansing_registry()
          return registry.apply_rules(v, ['trim_whitespace', 'normalize_company'])
  ```

**3. BronzeAnnuitySchema / GoldAnnuitySchema** (`domain/annuity_performance/schemas.py`)
- **Purpose**: Pandera DataFrame schemas for structural validation
- **Key Features**:
  - BronzeAnnuitySchema: Validates raw Excel (expected columns, basic types)
  - GoldAnnuitySchema: Validates database-ready data (PK uniqueness, no nulls)
- **Example**:
  ```python
  import pandera as pa

  BronzeAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, coerce=True, nullable=True),
      "计划代码": pa.Column(pa.String, nullable=True),
      "期末资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
  }, strict=False, coerce=True)  # Allow extra columns

  GoldAnnuitySchema = pa.DataFrameSchema({
      "月度": pa.Column(pa.DateTime, nullable=False),
      "计划代码": pa.Column(pa.String, nullable=False),
      "company_id": pa.Column(pa.String, nullable=False),
      "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
  }, strict=True, unique=['月度', '计划代码', 'company_id'])  # Composite PK
  ```

**4. ValidationErrorReporter** (`utils/error_reporter.py`)
- **Purpose**: Aggregate validation errors and export to CSV
- **Key Methods**:
  - `collect_error(row_idx: int, field: str, error: str) -> None`
  - `export_to_csv(filepath: Path) -> None`
  - `get_summary() -> ValidationSummary`
- **Error CSV Format**:
  ```csv
  row_index,field_name,error_type,error_message,original_value
  15,月度,ValueError,"Cannot parse 'INVALID' as date",INVALID
  23,期末资产规模,ValueError,"Value must be >= 0",-1000.50
  ```

---

### Data Models and Contracts

#### Pydantic Models (Story 2.1)

**Input Model (Loose Validation)**:
```python
class AnnuityPerformanceIn(BaseModel):
    """Accepts messy Excel input with lenient validation"""
    月度: Optional[Union[str, int, date]]  # Various date formats
    计划代码: Optional[str]  # Can be missing initially
    客户名称: Optional[str]  # Enrichment source
    期初资产规模: Optional[float]  # Nullable
    期末资产规模: Optional[float]  # Nullable
    投资收益: Optional[float]  # Nullable
    年化收益率: Optional[float]  # Nullable

    class Config:
        str_strip_whitespace = True  # Auto-trim strings
        coerce_numbers_to_str = False
```

**Output Model (Strict Validation)**:
```python
class AnnuityPerformanceOut(BaseModel):
    """Enforces business rules for database-ready output"""
    月度: date  # Required, parsed
    计划代码: str = Field(min_length=1)  # Required, non-empty
    company_id: str  # Required (real or temporary ID)
    客户名称: str  # Original name (for reference)
    期初资产规模: float = Field(ge=0)  # Non-negative
    期末资产规模: float = Field(ge=0)  # Non-negative
    投资收益: float  # Can be negative
    年化收益率: Optional[float] = Field(ge=-1.0, le=10.0)  # Sanity check

    @field_validator('月度', mode='before')
    def parse_date(cls, v):
        """Parse YYYYMM, YYYY年MM月, or YYYY-MM formats"""
        return parse_yyyymm_or_chinese(v)

    @field_validator('客户名称', mode='before')
    def clean_company_name(cls, v):
        """Normalize company names for enrichment"""
        registry = get_cleansing_registry()
        return registry.apply_rules(v, ['trim_whitespace', 'normalize_company'])

    @model_validator(mode='after')
    def validate_business_rules(self):
        """Cross-field business rules"""
        # If 期末资产规模 is 0, 年化收益率 should be None
        if self.期末资产规模 == 0 and self.年化收益率 is not None:
            raise ValueError("年化收益率 should be None when 期末资产规模 is 0")
        return self
```

#### Pandera Schemas (Story 2.2)

**Bronze Schema (Structural Validation)**:
```python
BronzeAnnuitySchema = pa.DataFrameSchema(
    columns={
        "月度": pa.Column(pa.DateTime, coerce=True, nullable=True),
        "计划代码": pa.Column(pa.String, nullable=True),
        "客户名称": pa.Column(pa.String, nullable=True),
        "期初资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
        "期末资产规模": pa.Column(pa.Float, coerce=True, nullable=True),
        "投资收益": pa.Column(pa.Float, coerce=True, nullable=True),
        "年化收益率": pa.Column(pa.Float, coerce=True, nullable=True),
    },
    strict=False,  # Allow extra columns from Excel
    coerce=True,   # Auto-convert types where possible
    checks=[
        pa.Check(lambda df: len(df) > 0, error="DataFrame cannot be empty"),
        pa.Check(lambda df: df.notna().any().all(), error="All columns are null"),
    ]
)
```

**Gold Schema (Database Integrity)**:
```python
GoldAnnuitySchema = pa.DataFrameSchema(
    columns={
        "月度": pa.Column(pa.DateTime, nullable=False),
        "计划代码": pa.Column(pa.String, nullable=False),
        "company_id": pa.Column(pa.String, nullable=False),
        "期初资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
        "期末资产规模": pa.Column(pa.Float, nullable=False, checks=pa.Check.ge(0)),
        "投资收益": pa.Column(pa.Float, nullable=False),
        "年化收益率": pa.Column(pa.Float, nullable=True),
    },
    strict=True,  # No extra columns allowed
    unique=['月度', '计划代码', 'company_id'],  # Composite PK
    checks=[
        pa.Check(lambda df: len(df) > 0, error="DataFrame cannot be empty"),
    ]
)
```

#### Cleansing Rule Contracts (Story 2.3)

All cleansing rules follow this contract:
```python
from typing import Any, TypeAlias

CleansingRule: TypeAlias = Callable[[Any], Any]

def rule_example(value: Any) -> Any:
    """
    Pure function: no side effects, no external dependencies

    Args:
        value: Raw value from Excel (can be None, str, int, float, etc.)

    Returns:
        Cleansed value (same or different type)

    Raises:
        ValueError: If value cannot be cleansed (will be caught by error reporter)
    """
    pass
```

**Built-in Rules**:
```python
# String rules
def trim_whitespace(value: str) -> str:
    return value.strip() if isinstance(value, str) else value

def normalize_company_name(value: str) -> str:
    """Remove special chars, standardize spacing"""
    if not isinstance(value, str):
        return value
    # Replace full-width spaces with half-width
    value = value.replace('　', ' ')
    # Remove quotes and brackets
    value = value.strip('「」『』""')
    # Collapse multiple spaces
    return ' '.join(value.split())

# Numeric rules
def remove_currency_symbols(value: str) -> str:
    """Remove ¥, $, , (comma) from numeric strings"""
    if not isinstance(value, str):
        return value
    return value.replace('¥', '').replace('$', '').replace(',', '')

# Date rules (integrated with Story 2.4)
def standardize_date_format(value: Any) -> date:
    """Wrap parse_yyyymm_or_chinese for registry use"""
    return parse_yyyymm_or_chinese(value)
```

---

### APIs and Interfaces

#### Cleansing Registry API (Story 2.3)

**Public Interface**:
```python
class CleansingRegistry:
    """Singleton registry for reusable cleansing rules"""

    def register(self, name: str, func: CleansingRule) -> None:
        """Register a new cleansing rule"""

    def apply_rule(self, value: Any, rule_name: str) -> Any:
        """Apply single rule to value"""

    def apply_rules(self, value: Any, rule_names: List[str]) -> Any:
        """Apply multiple rules in sequence (composition)"""

    def get_domain_rules(self, domain: str, field: str) -> List[str]:
        """Retrieve configured rules for domain field"""

# Singleton instance
def get_cleansing_registry() -> CleansingRegistry:
    """Retrieve global registry instance"""
```

**Configuration API** (`cleansing/config/cleansing_rules.yml`):
```yaml
domains:
  annuity_performance:
    客户名称: [trim_whitespace, normalize_company_name]
    计划代码: [trim_whitespace, uppercase]
    期末资产规模: [remove_currency_symbols]

  # Future domains inherit default rules
  default:
    - trim_whitespace
```

#### Date Parser API (Story 2.4)

```python
def parse_yyyymm_or_chinese(
    value: Union[str, int, date],
    default_day: int = 1
) -> date:
    """
    Parse various Chinese date formats to Python date object.

    Supported formats:
    - Integer: 202501 → date(2025, 1, 1)
    - String: "2025年1月" → date(2025, 1, 1)
    - String: "2025-01" → date(2025, 1, 1)
    - Date: date(2025, 1, 1) → date(2025, 1, 1) (passthrough)

    Args:
        value: Input date in various formats
        default_day: Day of month to use (default: 1)

    Returns:
        Parsed date object

    Raises:
        ValueError: If value cannot be parsed or is outside valid range (2000-2030)

    Examples:
        >>> parse_yyyymm_or_chinese(202501)
        date(2025, 1, 1)
        >>> parse_yyyymm_or_chinese("2025年1月")
        date(2025, 1, 1)
        >>> parse_yyyymm_or_chinese("invalid")
        ValueError: Cannot parse 'invalid' as date, supported formats: YYYYMM, YYYY年MM月, YYYY-MM
    """
```

#### Validation Error Reporter API (Story 2.5)

```python
@dataclass
class ValidationError:
    row_index: int
    field_name: str
    error_type: str  # "ValueError", "SchemaError", etc.
    error_message: str
    original_value: Any

@dataclass
class ValidationSummary:
    total_rows: int
    valid_rows: int
    failed_rows: int
    error_count: int
    error_rate: float  # failed_rows / total_rows

class ValidationErrorReporter:
    """Collect and export validation errors"""

    def collect_error(self, error: ValidationError) -> None:
        """Add error to collection"""

    def get_summary(self) -> ValidationSummary:
        """Return aggregated summary statistics"""

    def export_to_csv(self, filepath: Path) -> None:
        """Export errors to CSV with columns: row_index, field_name, error_type, error_message, original_value"""

    def check_threshold(self, threshold: float = 0.10) -> None:
        """Raise exception if error rate exceeds threshold (default 10%)"""
```

---

### Workflows and Sequencing

#### Story Sequencing and Dependencies

Epic 2 stories can be parallelized with careful dependency management:

```
Story 2.3 (Cleansing Registry)  ←─┐
Story 2.4 (Date Parser)         ←─┤
                                   ├─→ Story 2.1 (Pydantic Models) ─→ Story 2.5 (Error Reporting)
Story 2.2 (Pandera Schemas)     ←─┘                                      ↑
                                                                          │
                                                                    (Integration)
```

**Recommended Sequence**:
1. **Parallel Track A**: Stories 2.3 + 2.4 (utilities, no dependencies)
2. **Parallel Track B**: Story 2.2 (Pandera schemas, independent)
3. **Sequential**: Story 2.1 (depends on 2.3, 2.4)
4. **Sequential**: Story 2.5 (depends on 2.1, 2.2 - integration story)

#### Validation Pipeline Flow

**End-to-End Data Flow**:
```
┌─────────────────────────────────────────────────────────────┐
│ Epic 3: File Discovery (Excel → Raw DataFrame)              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ BRONZE VALIDATION (Story 2.2: Pandera Schema)               │
│ - Check expected columns present                            │
│ - Coerce types (str → float, str → datetime)                │
│ - Validate no completely null columns                       │
│ - Fast fail: 5-10ms for 10k rows                            │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ SILVER TRANSFORMATION (Story 2.1: Pydantic Models)          │
│ - Parse dates (Story 2.4)                                   │
│ - Cleanse values (Story 2.3)                                │
│ - Validate business rules (row-by-row)                      │
│ - Collect errors (Story 2.5)                                │
│ - Target: ≥1000 rows/s                                      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ GOLD VALIDATION (Story 2.2: Pandera Schema)                 │
│ - Verify composite PK uniqueness                            │
│ - Enforce not-null constraints                              │
│ - Project to database columns                               │
│ - Fast: 50-100ms for 10k rows                               │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Epic 1: Database Loader (PostgreSQL Write)                  │
└─────────────────────────────────────────────────────────────┘
```

#### Error Handling Flow (Story 2.5)

```
┌─────────────────────┐
│ Validation Step     │
└─────────────────────┘
           ↓
    ┌──────────┐
    │ Success? │
    └──────────┘
       ↙      ↘
     YES       NO
      ↓         ↓
   Continue   Collect Error
              (row_idx, field, message)
                    ↓
            ┌───────────────┐
            │ Threshold     │
            │ Check (10%)   │
            └───────────────┘
               ↙        ↘
          <10%         ≥10%
            ↓            ↓
      Continue      FAIL FAST
                   (Systemic Issue)

After Pipeline:
    ↓
┌─────────────────────────────────────┐
│ Export Failed Rows to CSV           │
│ logs/failed_rows_YYYYMMDD_HHMMSS.csv│
└─────────────────────────────────────┘
```

---

## Non-Functional Requirements

### Performance

Epic 2 has **mandatory** performance acceptance criteria documented in `docs/epic-2-performance-acceptance-criteria.md`. All stories must meet these thresholds:

#### AC-PERF-1: Validation Throughput (MANDATORY)

**Requirement**: ≥1000 rows/second on standard hardware

**Test Configuration**:
- Data volume: 10,000 rows minimum (not 5-row samples)
- Hardware baseline: Developer laptops (2020+, 16GB RAM) or GitHub Actions runners
- Test fixture: `tests/fixtures/performance/annuity_performance_10k.csv`

**Measurement**:
```python
import time
df = pd.read_csv("tests/fixtures/performance/annuity_performance_10k.csv")
start = time.time()
result = pipeline.execute(df)
duration = time.time() - start
rows_per_second = len(df) / duration

assert rows_per_second >= 1000, f"Throughput {rows_per_second:.0f} < 1000 rows/s"
```

**Story-Specific Targets**:
- Story 2.1 (Pydantic): ≥1500 rows/s (row-by-row validation is slower)
- Story 2.2 (Pandera): ≥5000 rows/s (DataFrame operations are faster)
- Story 2.3 (Cleansing): ≥1000 rows/s (vectorized string operations)

**Failure Handling**: If throughput <1000 rows/s, story is **BLOCKED** until optimized.

**Optimization Strategies**:
1. **Vectorize operations**: Use Pandas `.str.replace()` instead of row-by-row regex
2. **Cache expensive lookups**: Use `@lru_cache` for date parsing, cleansing rules
3. **Batch Pydantic validation**: Use `TypeAdapter.validate_python()` with list input
4. **Profile hot paths**: Use `cProfile` to identify bottlenecks

#### AC-PERF-2: Validation Overhead Budget (MANDATORY)

**Requirement**: <20% of total pipeline execution time

**Definition**:
```
Validation Overhead % = (Total Validation Time / Total Pipeline Time) × 100
```

**Measurement**:
```python
result = pipeline.execute(df)
validation_time = sum(
    step.duration_seconds
    for step in result.metrics.step_metrics
    if "validation" in step.name.lower()
)
total_time = result.metrics.duration_seconds
overhead_pct = (validation_time / total_time) * 100

assert overhead_pct < 20.0, f"Validation overhead {overhead_pct:.1f}% > 20%"
```

**Guidance**:
- **Acceptable**: 10-15% for typical workloads
- **Warning**: 15-20% (consider optimization if data volume grows)
- **Failure**: >20% (must refactor validation approach)

**Step Ordering Optimization**:
1. Bronze schema validation (fast, fails early)
2. Business rules validation (slower, row-by-row)
3. Expensive lookups last (enrichment, external APIs)

#### AC-PERF-3: Baseline Regression Tracking (RECOMMENDED)

**Requirement**: Track performance baselines, warn if >20% regression

**Baseline File**: `tests/.performance_baseline.json`
```json
{
  "validation_throughput_rows_per_sec": {
    "pydantic_field_validation": 1500,
    "pandera_schema_validation": 5000,
    "business_rules_validation": 1200
  },
  "overhead_percentage": {
    "bronze_validation": 5.0,
    "silver_validation": 12.5,
    "gold_validation": 3.0
  },
  "test_data_size": 10000,
  "last_updated": "2025-11-16T10:30:00Z"
}
```

**CI Integration**: GitHub Actions compares current run to baseline, warns if degraded >20%

### Security

#### Data Sensitivity

- **PII Handling**: Failed row CSV exports may contain customer names (客户名称)
  - Store in `logs/` directory with restrictive permissions (600)
  - Add `logs/` to `.gitignore` to prevent accidental commits
  - Document data retention policy (delete after 30 days)

- **SQL Injection Prevention**: Validation errors include user input values
  - Sanitize error messages before logging/export
  - Never execute error messages as SQL (use parameterized queries)

#### Dependency Security

- **Pydantic v2**: Pin to `pydantic>=2.5.0,<3.0` (avoid breaking changes)
- **Pandera**: Pin to `pandera>=0.18.0,<1.0` (actively maintained)
- **No external API calls**: All validation is offline (no network dependencies)

### Reliability/Availability

#### Graceful Degradation

- **Partial Success Handling**: Pipeline continues with valid rows if error rate <10%
  - Example: 950 valid rows + 50 failed rows → pipeline succeeds, exports 950 to database
  - Failed rows exported to CSV for manual review

- **Fail Fast on Systemic Issues**: If error rate ≥10%, stop pipeline immediately
  - Rationale: Likely configuration error or corrupted source file
  - Error message includes: error rate, sample failed rows, suggested fixes

#### Error Recovery

- **Idempotent Validation**: Re-running validation on same input produces identical results
  - No side effects (no database writes, no state mutations)
  - Deterministic error messages (same error for same input)

- **Retry Logic**: Validation failures are NOT retried (not transient errors)
  - Transient errors (network timeouts) are handled by Epic 5 enrichment
  - Validation errors are permanent (bad data quality, fix at source)

### Observability

#### Validation Metrics (Logged via Epic 1 Story 1.3)

```json
{
  "validation_metrics": {
    "bronze_validation": {
      "duration_ms": 150,
      "input_rows": 10000,
      "output_rows": 10000,
      "failed_rows": 0
    },
    "silver_validation": {
      "duration_ms": 8500,
      "input_rows": 10000,
      "output_rows": 9950,
      "failed_rows": 50,
      "error_rate": 0.005,
      "throughput_rows_per_sec": 1176
    },
    "gold_validation": {
      "duration_ms": 200,
      "input_rows": 9950,
      "output_rows": 9950,
      "failed_rows": 0
    },
    "total_validation_time_ms": 8850,
    "total_pipeline_time_ms": 12000,
    "validation_overhead_pct": 73.75  # WARNING: Exceeds 20% threshold!
  }
}
```

#### Error Reporting Observability

- **CSV Export Metadata**: Include summary header in exported CSV
  ```csv
  # Validation Errors Export
  # Date: 2025-11-16T10:30:00Z
  # Total Rows: 10000
  # Failed Rows: 50
  # Error Rate: 0.5%
  # Validation Duration: 8.5s
  row_index,field_name,error_type,error_message,original_value
  15,月度,ValueError,"Cannot parse 'INVALID' as date",INVALID
  ```

- **Performance Warnings**: Log warnings if overhead approaches threshold
  ```python
  if overhead_pct > 15.0:
      logger.warning(
          "Validation overhead approaching threshold",
          overhead_pct=overhead_pct,
          threshold=20.0,
          suggestion="Consider vectorizing validation logic"
      )
  ```

---

## Dependencies and Integrations

### Internal Dependencies (Epic 1)

| Epic 1 Story | Dependency | Usage in Epic 2 |
|--------------|------------|-----------------|
| Story 1.2 | CI/CD Pipeline | Performance tests run in CI with 10k row fixtures |
| Story 1.3 | Structured Logging | Log validation metrics (duration, row counts, error rates) |
| Story 1.4 | Configuration | Validation thresholds, cleansing rules loaded from config |
| Story 1.5 | Pipeline Framework | Validation steps implement `TransformStep` protocol |
| Story 1.6 | Clean Architecture | Validation logic in domain layer, no I/O dependencies |
| Story 1.8 | Database Loader | Gold validation ensures data matches loader's schema expectations |

### External Dependencies

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `pydantic` | ≥2.5.0,<3.0 | Row-level validation with custom validators | MIT |
| `pandera` | ≥0.18.0,<1.0 | DataFrame schema validation and coercion | MIT |
| `pandas` | ≥2.1.0 | DataFrame operations (from Epic 1) | BSD-3-Clause |

**Rationale for Version Pins**:
- Pydantic v2: Major rewrite from v1, incompatible APIs (pin to v2.x)
- Pandera 0.18+: Stable API, Python 3.10+ support
- Pandas 2.1+: Performance improvements for string operations

### Integration Points

#### With Epic 3 (File Discovery)

- **Input**: Epic 3 Story 3.5 provides `DataFrame` with normalized column names
- **Contract**: Epic 2 Story 2.2 Bronze validation expects specific columns (defined in schema)
- **Failure Mode**: If Epic 3 returns unexpected columns, Bronze validation fails with actionable error

#### With Epic 4 (Annuity Domain)

- **Integration**: Epic 4 uses Epic 2's validation framework
  - Story 4.1: Defines Pydantic models using Epic 2 patterns
  - Story 4.2: Defines Pandera schemas using Epic 2 patterns
  - Story 4.3: Integrates validation steps into annuity pipeline

#### With Epic 5 (Company Enrichment)

- **Deferred Integration**: Epic 2 models include `company_id` field, but enrichment logic comes from Epic 5
- **Temporary Behavior**: For Epic 2 testing, use stub company IDs (e.g., `"UNKNOWN_" + 客户名称`)

---

## Acceptance Criteria (Authoritative)

### Epic-Level Acceptance Criteria

**Epic 2 is complete when**:

1. ✅ **All 5 stories delivered** (2.1-2.5) with DoD satisfied
2. ✅ **Performance criteria met**: AC-PERF-1 and AC-PERF-2 passed for all stories
3. ✅ **Annuity domain validated end-to-end**: Bronze → Silver → Gold with 100% parity to legacy
4. ✅ **Error reporting functional**: Failed rows exported to CSV with actionable error messages
5. ✅ **Integration tests passing**: 10,000-row fixture validates without performance regressions
6. ✅ **Documentation complete**: Validation framework usage guide, performance tuning guide
7. ✅ **Retrospective held**: Lessons learned documented for Epic 3-6 improvements

### Story-Level Acceptance Criteria

#### Story 2.1: Pydantic Models for Row-Level Validation

**Given** I have raw annuity DataFrame from Epic 3
**When** I validate rows using `AnnuityPerformanceIn` → `AnnuityPerformanceOut`
**Then**:
- ✅ Input model accepts messy data (optional fields, various date formats)
- ✅ Output model enforces business rules (required fields, non-negative amounts, valid dates)
- ✅ Custom validators use Story 2.3 cleansing registry and Story 2.4 date parser
- ✅ Validation errors include field name, row index, and specific failure reason
- ✅ Performance: ≥1000 rows/s throughput (AC-PERF-1)
- ✅ Performance: <20% overhead (AC-PERF-2)

#### Story 2.2: Pandera Schemas for DataFrame Validation

**Given** I have raw DataFrame (Bronze) and transformed DataFrame (Gold)
**When** I apply `BronzeAnnuitySchema` and `GoldAnnuitySchema`
**Then**:
- ✅ Bronze schema validates expected columns present, basic types coercible
- ✅ Gold schema validates composite PK uniqueness, not-null constraints
- ✅ Schema errors include which columns/rows failed, which checks violated
- ✅ Performance: ≥1000 rows/s (5000+ rows/s expected for DataFrame ops)
- ✅ Performance: <20% overhead

#### Story 2.3: Cleansing Registry Framework

**Given** I need to normalize company names and dates across domains
**When** I use `CleansingRegistry` to apply rules
**Then**:
- ✅ Registry supports rule registration: `register('trim_whitespace', func)`
- ✅ Built-in rules: `trim_whitespace`, `normalize_company_name`, `remove_currency_symbols`
- ✅ Rule composition: multiple rules apply in sequence
- ✅ Per-domain configuration via `cleansing_rules.yml`
- ✅ Integration: Pydantic validators call registry via `@field_validator`
- ✅ Performance: ≥1000 rows/s

#### Story 2.4: Chinese Date Parsing Utilities

**Given** I have dates in various formats (YYYYMM, YYYY年MM月, YYYY-MM)
**When** I call `parse_yyyymm_or_chinese(value)`
**Then**:
- ✅ Parses integer: `202501` → `date(2025, 1, 1)`
- ✅ Parses Chinese format: `"2025年1月"` → `date(2025, 1, 1)`
- ✅ Parses ISO format: `"2025-01"` → `date(2025, 1, 1)`
- ✅ Validates range: rejects dates outside 2000-2030
- ✅ Clear errors: `ValueError("Cannot parse 'INVALID' as date, supported formats: ...")`
- ✅ Integration: Used in Pydantic `@field_validator` and cleansing registry

#### Story 2.5: Validation Error Handling and Reporting

**Given** I have validation failures from Stories 2.1-2.2
**When** I use `ValidationErrorReporter` to collect and export errors
**Then**:
- ✅ Errors exported to CSV: `logs/failed_rows_YYYYMMDD_HHMMSS.csv`
- ✅ CSV includes: row_index, field_name, error_type, error_message, original_value
- ✅ Error summary logged: total rows, failed rows, error rate
- ✅ Threshold enforcement: fail fast if >10% of rows invalid
- ✅ Partial success: pipeline continues with valid rows if error rate <10%
- ✅ Performance: Error collection overhead <5% (on top of validation time)

---

## Traceability Mapping

### PRD Requirements → Epic 2 Stories

| PRD Requirement | PRD Section | Epic 2 Story | Implementation |
|-----------------|-------------|--------------|----------------|
| FR-2: Multi-Layer Validation | §751-796 | Stories 2.1, 2.2 | Pydantic (Silver), Pandera (Bronze/Gold) |
| FR-2.1: Pydantic Row Validation | §581-624 | Story 2.1 | `AnnuityPerformanceIn/Out` models |
| FR-2.2: Silver Layer Validation | §756-776 | Story 2.1 | Pydantic business rules |
| FR-2.3: Gold Layer Validation | §777-785 | Story 2.2 | Pandera composite PK uniqueness |
| FR-3.2: Registry-Driven Cleansing | §817-824 | Story 2.3 | `CleansingRegistry` class |
| FR-3.4: Chinese Date Parsing | §863-871 | Story 2.4 | `parse_yyyymm_or_chinese()` |
| NFR-2.1: Performance Requirements | §1133-1148 | All stories | AC-PERF-1, AC-PERF-2 |
| NFR-3.1: Code Quality Standards | §1189-1205 | All stories | Type hints, docstrings, CI checks |

### Architecture Decisions → Epic 2 Components

| Architecture Decision | Source Document | Epic 2 Implementation |
|-----------------------|-----------------|----------------------|
| Clean Architecture Layers | architecture-boundaries.md | Validation in domain layer, no I/O imports |
| Medallion Architecture | architecture.md | Bronze/Silver/Gold validation stages |
| Dependency Injection | architecture-boundaries.md | Cleansing registry injected into Pydantic validators |
| Performance Baselines | Epic 1 Retrospective | `.performance_baseline.json` tracking |

---

## Risks, Assumptions, Open Questions

### Risks

| Risk | Impact | Mitigation | Owner |
|------|--------|------------|-------|
| **Validation performance <1000 rows/s** | HIGH: Blocks production deployment | Mandatory AC-PERF-1 testing, early profiling | Dev Team |
| **Pydantic v2 breaking changes** | MEDIUM: Models fail after dependency upgrade | Pin to `pydantic>=2.5,<3.0`, test with multiple versions | Dev Team |
| **Chinese date parsing edge cases** | MEDIUM: Validation fails on uncommon formats | Comprehensive unit tests, document supported formats | Dev Team |
| **Error CSV contains PII** | MEDIUM: Data privacy violation | Restrict file permissions (600), auto-delete after 30 days | Security Team |

### Assumptions

1. **Excel data quality**: Assume ≤10% invalid rows per file (if >10%, likely systemic issue)
2. **Date formats**: Assume only 3 formats supported (YYYYMM, YYYY年MM月, YYYY-MM), no dd/mm/yyyy
3. **Performance baselines**: Assume GitHub Actions runners representative of production (2 CPU, 7GB RAM)
4. **Cleansing rules**: Assume domain-specific rules configured via YAML (not hardcoded)

### Open Questions

| Question | Status | Decision Needed By | Notes |
|----------|--------|---------------------|-------|
| Should error CSV include ALL original row data or just failed fields? | OPEN | Story 2.5 start | Privacy vs. debuggability trade-off |
| How to handle partial date formats (e.g., "2025" without month)? | OPEN | Story 2.4 start | Default to January or reject as invalid? |
| Should Pandera coercion warnings be logged or silently ignored? | OPEN | Story 2.2 start | Balance observability vs. log noise |
| Can we reuse Story 2.4 date parser for other domains with different ranges? | OPEN | Epic 9 planning | Make date range configurable? |

---

## Test Strategy Summary

### Test Pyramid

```
        ┌──────────────┐
        │  Integration │  10,000-row fixtures (AC-PERF-1, AC-PERF-2)
        │    Tests     │  End-to-end validation pipelines
        └──────────────┘
             ▲
       ┌─────────────┐
       │  Unit Tests  │  Individual validators, cleansing rules
       │   (Fast)     │  Pydantic models, Pandera schemas
       └──────────────┘
            ▲
    ┌────────────────┐
    │ Type Checking  │  mypy --strict (CI)
    │   (Fastest)    │  Ruff linting
    └────────────────┘
```

### Test Coverage Targets

- **Domain Layer** (Pydantic models, Pandera schemas): ≥90% coverage
- **Cleansing Registry**: ≥80% coverage
- **Utils** (date parser, error reporter): ≥85% coverage

### Performance Test Fixtures

**Location**: `tests/fixtures/performance/`

**Required Fixtures**:
1. `annuity_performance_10k.csv`: 10,000 rows with realistic data distribution
   - 90% valid rows (pass all validation)
   - 10% invalid rows (fail business rules)
   - 25 columns (match annuity domain schema)

2. `annuity_performance_edge_cases.csv`: 100 rows with edge cases
   - Various date formats
   - Null values, special characters
   - Boundary values (0, negative numbers, very large numbers)

**Fixture Generation Script**: `tests/fixtures/performance/generate_fixtures.py`

### Story-Specific Test Plans

#### Story 2.1: Pydantic Models

**Unit Tests**:
- Valid row validation (all fields pass)
- Invalid row validation (each field fails independently)
- Custom validators (date parsing, company name normalization)
- Cross-field validators (business rule interactions)

**Performance Tests**:
- 10,000 rows in <10 seconds (AC-PERF-1: 1000 rows/s)
- Overhead <20% of total pipeline time (AC-PERF-2)

#### Story 2.2: Pandera Schemas

**Unit Tests**:
- Bronze schema: missing columns, wrong types, null columns
- Gold schema: composite PK duplicates, null values in required fields
- Schema coercion: string to float, string to datetime

**Performance Tests**:
- 10,000 rows in <2 seconds (5000 rows/s expected)

#### Story 2.3: Cleansing Registry

**Unit Tests**:
- Rule registration and retrieval
- Single rule application
- Multiple rule composition (order matters)
- Per-domain configuration loading

**Integration Tests**:
- Pydantic validators call registry
- YAML configuration changes reflected in behavior

#### Story 2.4: Date Parser

**Unit Tests**:
- Each supported format (YYYYMM, YYYY年MM月, YYYY-MM)
- Edge cases: 2-digit years, full-width characters
- Invalid inputs: raise ValueError with clear message
- Range validation: 2000-2030 only

#### Story 2.5: Error Reporter

**Unit Tests**:
- Error collection (multiple errors per row)
- CSV export format validation
- Threshold enforcement (10% error rate)
- Partial success handling

**Integration Tests**:
- End-to-end error flow: validation → collection → export
- CSV includes correct row indices and error messages

### CI/CD Integration

**GitHub Actions Workflow** (extends Story 1.2 CI):
```yaml
jobs:
  epic-2-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.10
        uses: actions/setup-python@v4
      - name: Install dependencies
        run: |
          uv sync --dev
      - name: Run unit tests
        run: uv run pytest tests/domain/ tests/cleansing/ tests/utils/ -v -m "not integration"
      - name: Run integration tests
        run: uv run pytest tests/integration/test_epic_2_*.py -v
      - name: Run performance tests
        run: |
          uv run pytest tests/performance/test_validation_*.py -v
          # Compare against baseline
          python scripts/check_performance_baseline.py
      - name: Check coverage
        run: |
          uv run pytest --cov=src/work_data_hub/domain --cov=src/work_data_hub/cleansing --cov-report=term-missing
          uv run coverage report --fail-under=85
```

---

## Post-Review Follow-ups

This section captures action items identified during code reviews of Epic 2 stories.

### Story 2.4: Chinese Date Parsing Utilities (Review: 2025-11-17)

**Review Outcome:** Changes Requested → ✅ All Action Items Completed (2025-11-17)

**Follow-up Actions:**

1. **✅ [Medium Priority] COMPLETED** Add performance test for date parsing (AC-PERF-1)
   - **File:** `tests/performance/test_story_2_4_performance.py` (created)
   - **Result:** 153,673 rows/s throughput (153x above 1000 rows/s minimum)
   - **Coverage:** All date formats, edge cases, format distribution analysis

2. **✅ [Medium Priority] COMPLETED** Fix Task 5 documentation inconsistency
   - **File:** `docs/sprint-artifacts/2-4-chinese-date-parsing-utilities.md` (updated)
   - **Fixed:** Task 5, Subtasks 5.1, 5.3 marked [x] complete
   - **Evidence:** Code verified at `models.py:379-399` and `test_service.py:180-188`

3. **✅ [Low Priority] COMPLETED** Create standalone usage documentation
   - **File:** `docs/utils/date-parser-usage.md` (created)
   - **Content:** Comprehensive guide with Pydantic patterns, performance guidance, troubleshooting

**Review Notes:** Core implementation is excellent - all 7 ACs verified complete, strong test coverage, clean architecture compliance. All action items addressed, ready for final review/approval.

### Story 2.5: Validation Error Handling and Reporting (Review: 2025-11-27)

**Review Outcome:** ⚠️ **CHANGES REQUESTED** (Awaiting Fix)

**Review Summary:**
Core implementation is **excellent** and production-ready - ValidationErrorReporter class has outstanding performance (125-333x above AC-PERF requirements), perfect code quality, and comprehensive documentation. However, integration tests (7/8) are failing due to incomplete test fixtures that don't match Pydantic model schema.

**Test Results:**
- ✅ Unit Tests: 20/20 PASSED (100%)
- ✅ Performance Tests: 7/7 PASSED (100%)
- ⚠️ Integration Tests: 1/8 PASSED (12.5%)

**Follow-up Actions:**

1. **🔴 [HIGH - BLOCKING]** Fix integration test fixtures
   - **File:** `tests/integration/test_epic_2_error_handling.py`
   - **Issue:** Missing required Pydantic fields (company_id, 业务类型, 计划类型, 组合类型, 组合代码, 组合名称, 机构代码, 机构名称, 产品线代码, 年金账户号, 年金账户名, 流失, 待遇支付)
   - **Fix:** Add complete test data matching Story 2.1 Pydantic model schema
   - **Verification:** All 8 integration tests should pass

2. **🟡 [MEDIUM - BLOCKING]** Adjust Bronze validation test data
   - **File:** `tests/integration/test_epic_2_error_handling.py`
   - **Issue:** Test data has 66% invalid dates, exceeds Bronze validator 50% threshold
   - **Fix:** Use ≤50% invalid data in test fixtures OR test Bronze threshold separately
   - **Verification:** Bronze validation tests pass without threshold error

3. **🟢 [LOW - RECOMMENDED]** Create test data factory helper
   - **File:** `tests/fixtures/test_data_factory.py` (new)
   - **Purpose:** Generate complete, valid AnnuityPerformance test records
   - **Benefit:** Reduces test fixture duplication and maintenance burden
   - **Usage:** `factory.create_valid_annuity_row()`, `factory.create_invalid_annuity_row(field='月度')`

**Review Notes:** Core implementation quality is exemplary - this is production-ready code with excellent architecture, type safety, documentation, and security. The only blocker is test refactoring (estimated 1-2 hours). Once integration tests pass, this story should be immediately approved.

**Strengths Identified:**
- ValidationErrorReporter performance: 625,083 errors/s (125x above requirement)
- CSV export performance: <0.5s for 1000 errors (333x faster than requirement)
- Memory efficiency: <10MB for 10K errors
- Security: Proper sanitization, CSV injection prevention, no PII leakage
- Architecture: Clean dependency injection, correct layer placement
- Documentation: Comprehensive docstrings with usage examples

---

**Document Status**: Draft - Ready for Technical Review
**Next Steps**:
1. Technical review by Architect
2. Story refinement sessions (break down detailed designs into tasks)
3. Create performance test fixtures (`generate_fixtures.py`)
4. Update sprint status: Epic 2 → "ready-for-dev"
