# Pipeline Integration Guide

**Version**: 1.0
**Date**: 2025-11-16
**Target**: Epic 2 - Multi-Layer Data Quality Framework

## Overview

This guide demonstrates how to integrate validation frameworks (Pydantic, Pandera) into the WorkDataHub Pipeline framework established in Story 1.5 and enhanced in Story 1.10.

**Prerequisites**:
- Story 1.5: Pipeline Framework Core
- Story 1.10: Advanced Features (retry logic, error collection mode)

## Table of Contents

1. [Example 1: Pydantic Validator as RowTransformStep](#example-1-pydantic-validator-as-rowtransformstep)
2. [Example 2: Pandera Schema Check as DataFrameStep](#example-2-pandera-schema-check-as-dataframestep)
3. [Example 3: Chaining Validators with Error Collection Mode](#example-3-chaining-validators-with-error-collection-mode)
4. [API Reference](#api-reference)
5. [Best Practices](#best-practices)

---

## Example 1: Pydantic Validator as RowTransformStep

**Use Case**: Validate individual rows using Pydantic models (field-level validation, type coercion, business rules).

### Step 1: Define Your Pydantic Model

```python
from pydantic import BaseModel, Field, field_validator
from datetime import date
from decimal import Decimal


class AnnuityPerformanceRow(BaseModel):
    """Pydantic model for annuity performance data validation."""

    report_date: date = Field(description="Monthly report date (YYYYMM)")
    plan_code: str = Field(min_length=1, max_length=50)
    portfolio_code: str = Field(min_length=1, max_length=50)
    scale: Decimal = Field(ge=0, description="Must be non-negative")

    @field_validator("plan_code")
    @classmethod
    def validate_plan_code(cls, v: str) -> str:
        """Ensure plan code follows naming convention."""
        if not v.strip():
            raise ValueError("Plan code cannot be empty")
        return v.strip()
```

### Step 2: Create RowTransformStep Wrapper

```python
from work_data_hub.domain.pipelines.types import RowTransformStep, StepResult, Row, PipelineContext
from pydantic import ValidationError
from typing import Type


class PydanticValidationStep(RowTransformStep):
    """
    Validates individual rows using a Pydantic model.

    Returns StepResult with:
    - row: Original row (pass-through on success)
    - errors: Field-level validation errors with actionable messages
    - metadata: Validation details
    """

    def __init__(self, model: Type[BaseModel], name: str = "pydantic_validation"):
        self._name = name
        self.model = model

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        """Validate row against Pydantic model."""
        try:
            # Attempt validation
            validated_instance = self.model(**row)

            # On success, return original row (no modification)
            return StepResult(
                row=row,
                metadata={"validated": True, "model": self.model.__name__}
            )

        except ValidationError as e:
            # Convert Pydantic errors to actionable messages
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                input_value = error.get("input", "N/A")

                # Format: "Field 'scale': Must be non-negative. Got: -100.5"
                errors.append(
                    f"Field '{field}': {message}. Got: {input_value}"
                )

            return StepResult(
                row=row,
                errors=errors,
                metadata={
                    "validated": False,
                    "model": self.model.__name__,
                    "error_count": len(errors)
                }
            )
```

### Step 3: Integrate into Pipeline

```python
from work_data_hub.domain.pipelines.core import Pipeline
from work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig


# Create the validation step
pydantic_step = PydanticValidationStep(
    model=AnnuityPerformanceRow,
    name="annuity_validation"
)

# Define pipeline configuration
config = PipelineConfig(
    name="annuity_pydantic_pipeline",
    steps=[
        StepConfig(
            name="annuity_validation",
            import_path="your_module.PydanticValidationStep",
            options={"model_name": "AnnuityPerformanceRow"}
        )
    ],
    stop_on_error=True  # Fail fast on first validation error
)

# Build pipeline
pipeline = Pipeline(steps=[pydantic_step], config=config)

# Execute
import pandas as pd
df = pd.read_csv("data/annuity_performance_202501.csv")
result = pipeline.execute(df)

# Check results
print(f"Success: {result.success}")
print(f"Processed: {result.metrics.rows_processed}")
print(f"Errors: {len(result.error_rows)}")
```

### Output Example

**Success Case**:
```
Success: True
Processed: 1000
Errors: 0
```

**Validation Error Case**:
```
Success: False
Processed: 1000
Errors: 15

Error Row Example:
{
  "row_index": 42,
  "row_data": {"report_date": "INVALID", "plan_code": "P001", ...},
  "error_message": "Field 'report_date': Input should be a valid date. Got: INVALID",
  "step_name": "annuity_validation"
}
```

---

## Example 2: Pandera Schema Check as DataFrameStep

**Use Case**: Validate entire DataFrame schema and column constraints (data types, ranges, uniqueness).

### Step 1: Define Pandera Schema

```python
import pandera as pa
from pandera import Column, DataFrameSchema, Check


annuity_schema = DataFrameSchema(
    {
        "report_date": Column(
            pa.DateTime,
            checks=[
                Check.greater_than_or_equal_to(pd.Timestamp("2020-01-01")),
                Check.less_than_or_equal_to(pd.Timestamp("2030-12-31"))
            ],
            nullable=False,
            coerce=True,  # Attempt type coercion
            description="Monthly report date"
        ),
        "plan_code": Column(
            pa.String,
            checks=[
                Check.str_length(min_value=1, max_value=50),
                Check.str_matches(r"^[A-Z0-9]+$")
            ],
            nullable=False
        ),
        "scale": Column(
            pa.Float,
            checks=[Check.greater_than_or_equal_to(0)],
            nullable=False,
            description="Must be non-negative"
        )
    },
    strict=True,  # Reject extra columns
    coerce=True   # Enable DataFrame-level type coercion
)
```

### Step 2: Create DataFrameStep Wrapper

```python
from work_data_hub.domain.pipelines.types import DataFrameStep, PipelineContext
import pandas as pd
import pandera as pa


class PanderaSchemaStep(DataFrameStep):
    """
    Validates entire DataFrame against a Pandera schema.

    Raises exception on validation failure (fail-fast).
    For partial success scenarios, use error collection mode (Example 3).
    """

    def __init__(self, schema: pa.DataFrameSchema, name: str = "pandera_validation"):
        self._name = name
        self.schema = schema

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext
    ) -> pd.DataFrame:
        """Validate and optionally coerce DataFrame."""
        try:
            # Validate and apply coercion
            validated_df = self.schema.validate(dataframe, lazy=False)

            context.logger.info(
                "pandera.validation.success",
                rows=len(validated_df),
                columns=list(validated_df.columns)
            )

            return validated_df

        except pa.errors.SchemaError as e:
            # Pandera provides detailed error information
            context.logger.error(
                "pandera.validation.failed",
                error=str(e),
                failure_cases=e.failure_cases.to_dict() if hasattr(e, 'failure_cases') else None
            )
            raise  # Re-raise to fail pipeline
```

### Step 3: Integrate into Pipeline

```python
# Create the validation step
pandera_step = PanderaSchemaStep(
    schema=annuity_schema,
    name="schema_validation"
)

# Define pipeline configuration
config = PipelineConfig(
    name="annuity_pandera_pipeline",
    steps=[
        StepConfig(
            name="schema_validation",
            import_path="your_module.PanderaSchemaStep",
            options={"schema_name": "annuity_schema"}
        )
    ],
    stop_on_error=True
)

# Build and execute pipeline
pipeline = Pipeline(steps=[pandera_step], config=config)
result = pipeline.execute(df)
```

### Output Example

**Validation Error**:
```
pandera.validation.failed: SchemaError:
Column 'scale' failed validation:
  - Check 'greater_than_or_equal_to(0)' failed for 3 rows
  - Failure cases:
    index  scale
    42    -100.5
    156   -50.0
    789   -25.75
```

---

## Example 3: Chaining Validators with Error Collection Mode

**Use Case**: Run multiple validation steps and collect ALL errors (not just first failure) for CSV export and remediation.

### Complete Pipeline with Error Collection

```python
from work_data_hub.domain.pipelines.core import Pipeline
from work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig
import pandas as pd


# Step 1: Define validation steps
pydantic_step = PydanticValidationStep(
    model=AnnuityPerformanceRow,
    name="field_validation"
)

# Step 2: Define second validator (business rules)
class BusinessRuleValidationStep(RowTransformStep):
    """Example: Custom business rule validation."""

    def __init__(self, name: str = "business_rules"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        """Validate business rules."""
        errors = []

        # Rule 1: Scale must be >= 1000 for certain plan types
        if row.get("plan_type") == "企业年金" and row.get("scale", 0) < 1000:
            errors.append(
                f"Business rule violation: Plan type '企业年金' requires scale >= 1000. "
                f"Got: {row.get('scale')}"
            )

        # Rule 2: Portfolio code must match plan code prefix
        plan_code = row.get("plan_code", "")
        portfolio_code = row.get("portfolio_code", "")
        if not portfolio_code.startswith(plan_code[:3]):
            errors.append(
                f"Business rule violation: Portfolio code '{portfolio_code}' "
                f"must start with plan prefix '{plan_code[:3]}'"
            )

        return StepResult(row=row, errors=errors)


business_step = BusinessRuleValidationStep(name="business_rules")

# Step 3: Create pipeline with ERROR COLLECTION MODE
config = PipelineConfig(
    name="multi_layer_validation",
    steps=[
        StepConfig(
            name="field_validation",
            import_path="your_module.PydanticValidationStep",
            options={"model_name": "AnnuityPerformanceRow"}
        ),
        StepConfig(
            name="business_rules",
            import_path="your_module.BusinessRuleValidationStep",
            options={}
        )
    ],
    stop_on_error=False,  # KEY: Enable error collection mode
    max_retries=0  # No retry for validation errors
)

# Build pipeline
pipeline = Pipeline(
    steps=[pydantic_step, business_step],
    config=config
)

# Execute with error collection
df = pd.read_csv("data/annuity_performance_202501.csv")
result = pipeline.execute(df)

# Step 4: Export failed rows to CSV for remediation
if result.error_rows:
    error_df = pd.DataFrame(result.error_rows)

    # Enrich with actionable error messages
    error_df["error_details"] = error_df["error_message"].apply(
        lambda msg: msg.replace("Field '", "请修正字段 '").replace("Got:", "当前值:")
    )

    # Export for business users
    error_df.to_csv(
        "output/validation_errors_202501.csv",
        index=False,
        encoding="utf-8-sig",  # Excel-friendly BOM
        columns=["row_index", "step_name", "error_details", "row_data"]
    )

    print(f"✅ Exported {len(error_df)} validation errors to CSV")
    print(f"✅ Successfully processed {result.metrics.rows_processed - len(error_df)} rows")

# Step 5: Load valid rows to database
if result.success or (not config.stop_on_error and result.error_rows):
    # Get valid rows (rows without errors)
    valid_df = result.output

    # Load to database
    from work_data_hub.io.loader.warehouse_loader import load
    load_result = load(
        table="annuity_performance",
        rows=valid_df.to_dict(orient="records"),
        mode="append",
        pk=[],
        conn=conn  # Database connection
    )

    print(f"✅ Loaded {load_result['inserted']} valid rows to database")
```

### Output Example

```
Pipeline Execution Summary:
  Total rows: 10,000
  Valid rows: 9,950
  Failed rows: 50

Error Breakdown:
  field_validation: 30 errors (Pydantic validation failures)
  business_rules: 20 errors (Business rule violations)

✅ Exported 50 validation errors to CSV
✅ Successfully processed 9,950 rows
✅ Loaded 9,950 valid rows to database

CSV Export (validation_errors_202501.csv):
row_index | step_name         | error_details                                           | row_data
----------|-------------------|--------------------------------------------------------|----------
42        | field_validation  | 请修正字段 'scale': Must be non-negative. 当前值: -100.5 | {...}
156       | business_rules    | Business rule violation: Plan type '企业年金' requires... | {...}
```

---

## API Reference

### Pipeline Constructor

```python
Pipeline(
    steps: List[TransformStep],    # List of step instances
    config: PipelineConfig          # Configuration object
)
```

**Key Parameters**:
- `steps`: Instantiated step objects (DataFrameStep or RowTransformStep)
- `config`: PipelineConfig with name, step configs, and error handling settings

### PipelineConfig

```python
PipelineConfig(
    name: str,                      # Pipeline identifier
    steps: List[StepConfig],        # Step configurations
    stop_on_error: bool = True,     # Error handling mode
    max_retries: int = 3,           # Retry attempts for transient errors
    retry_backoff_base: float = 1.0 # Exponential backoff base (seconds)
)
```

**Error Handling Modes**:
- `stop_on_error=True`: Fail fast on first error (default)
- `stop_on_error=False`: Collect all errors, continue processing

### DataFrameStep Protocol

```python
class DataFrameStep(TransformStep, Protocol):
    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext
    ) -> pd.DataFrame:
        """Transform entire DataFrame."""
```

**When to Use**:
- Schema validation (Pandera)
- DataFrame-level operations (deduplication, sorting)
- Column-level transformations (type coercion, renaming)

### RowTransformStep Protocol

```python
class RowTransformStep(TransformStep, Protocol):
    def apply(
        self,
        row: Row,  # Dict[str, Any]
        context: PipelineContext
    ) -> StepResult:
        """Transform individual row."""
```

**When to Use**:
- Field-level validation (Pydantic)
- Row-by-row business rules
- Enrichment/lookup operations

### StepResult

```python
@dataclass
class StepResult:
    row: Row                        # Transformed row
    warnings: List[str] = []        # Non-fatal issues
    errors: List[str] = []          # Fatal errors
    metadata: Dict[str, Any] = {}   # Diagnostic data
```

**Error Message Guidelines**:
- ❌ Bad: `ValidationError: 1 validation error for AnnuityPerformanceRow`
- ✅ Good: `Field 'report_date': Input should be a valid date. Got: INVALID. Expected format: YYYYMM`

---

## Best Practices

### 1. Error Message Quality for Business Users

**Problem**: Technical errors like `ValidationError: 1 validation error` are unusable for data fixers.

**Solution**: Provide field-level, actionable errors with examples.

```python
# ❌ Bad error message
"ValidationError: 1 validation error for AnnuityPerformanceRow"

# ✅ Good error message
"Field 'report_date': Cannot parse 'INVALID' as date. Expected format: YYYYMM or YYYY年MM月. Example: 202501"
```

### 2. Performance Optimization

**Guideline**: Pydantic validation must process ≥1000 rows/second (Epic 2 AC).

**Optimization Strategies**:
- Use Pandera for DataFrame-level checks (faster than row-by-row)
- Place expensive validations after cheap filters
- Use Pydantic for field-level rules only

**Example**:
```python
# ✅ Optimized order
steps = [
    SchemaValidationStep(annuity_schema),         # Fast: DataFrame-level
    PydanticValidationStep(AnnuityPerformanceRow) # Slower: Row-by-row
]

# ❌ Suboptimal order
steps = [
    PydanticValidationStep(AnnuityPerformanceRow), # Slow first
    SchemaValidationStep(annuity_schema)           # Fast second
]
```

### 3. Validation Overhead Budget

**Guideline**: Validation overhead must be <20% of total pipeline execution time.

**Measurement**:
```python
result = pipeline.execute(df)

validation_time = sum(
    step.duration_seconds
    for step in result.metrics.step_metrics
    if "validation" in step.name
)

total_time = result.metrics.duration_seconds
overhead_pct = (validation_time / total_time) * 100

assert overhead_pct < 20, f"Validation overhead too high: {overhead_pct:.1f}%"
```

### 4. Backward Compatibility

**When modifying Pipeline framework**:
- Preserve Story 1.5 unit tests (core functionality)
- Verify Story 1.9 Dagster integration still works
- Run Story 1.10 advanced features tests

**Pre-modification checklist**:
```bash
# Run backward compatibility tests
uv run pytest tests/domain/pipelines/test_core.py -v
uv run pytest tests/integration/test_dagster_sample_job.py -v
```

### 5. Manual Testing for Business Users

**After implementing Epic 2 Story 2.5 (Error Reporting)**:
- Export sample validation errors to CSV
- Ask non-technical stakeholder: "Can you fix these errors using only the CSV?"
- Target: 90% of errors fixable without developer help

**Test Protocol**:
1. Generate CSV with 20 validation errors
2. Provide CSV to business user (no other context)
3. Track: How many errors fixed in 30 minutes?
4. Goal: ≥18/20 errors fixed (90%)

---

## Troubleshooting

### Issue: Pipeline raises TypeError on construction

**Symptom**:
```python
Pipeline(name="test", config={"key": "value"})
# TypeError: Pipeline.__init__() got an unexpected keyword argument 'name'
```

**Solution**: Pipeline does NOT accept `name` parameter. Use PipelineConfig:
```python
config = PipelineConfig(name="test", steps=[...])
pipeline = Pipeline(steps=[...], config=config)
```

### Issue: Error collection mode not working

**Symptom**: Pipeline stops on first error despite `stop_on_error=False`.

**Solution**: Ensure config is passed to Pipeline:
```python
# ❌ Missing config
pipeline = Pipeline(steps=[step1, step2])

# ✅ Config with error collection enabled
config = PipelineConfig(name="test", steps=[...], stop_on_error=False)
pipeline = Pipeline(steps=[step1, step2], config=config)
```

### Issue: Row indices in error_rows are incorrect

**Symptom**: `error_rows[0]["row_index"]` doesn't match original DataFrame index.

**Solution**: Reset index before pipeline execution:
```python
df = df.reset_index(drop=True)  # Reset to 0-based sequential index
result = pipeline.execute(df)
```

---

## Related Documentation

- [Story 1.5: Pipeline Framework Core](../sprint-artifacts/stories/1-5-shared-pipeline-framework-core-simple.md)
- [Story 1.10: Advanced Features](../sprint-artifacts/stories/1-10-pipeline-framework-advanced-features.md)
- [Architecture Patterns: Retry Classification](architecture-patterns/retry-classification.md)
- [Epic 1 Retrospective](../sprint-artifacts/epic-1-retrospective-2025-11-16.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16
**Authors**: Bob (Scrum Master) + Development Team
**Target Epic**: Epic 2 - Multi-Layer Data Quality Framework
