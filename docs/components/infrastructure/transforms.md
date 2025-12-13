# Pipeline Transformation Steps

Story 5.6: Implement Standard Pipeline Steps
Architecture Decision AD-010: Infrastructure Layer & Pipeline Composition

## Overview

The `infrastructure/transforms` module provides standard, reusable pipeline transformation steps that can be composed to build domain-specific data processing pipelines.

**Design Principles:**
- Python code composition over JSON configuration
- Immutability: steps return new DataFrames, never mutate input
- Vectorized Pandas operations for performance
- Structured logging with context

## Import Path

```python
from work_data_hub.infrastructure.transforms import (
    # Base classes
    TransformStep,
    Pipeline,
    # Standard steps
    MappingStep,
    ReplacementStep,
    CalculationStep,
    FilterStep,
    CleansingStep,
    DropStep,
    RenameStep,
)
```

## Components

### TransformStep (Base Class)

Abstract base class for all transformation steps.

```python
class TransformStep(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-friendly step name for logging."""
        pass

    @abstractmethod
    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Apply transformation, returning new DataFrame."""
        pass
```

### Pipeline

Compose multiple steps into a sequential pipeline.

```python
pipeline = Pipeline([
    MappingStep({'old_col': 'new_col'}),
    FilterStep(lambda df: df['value'] > 0),
])
result = pipeline.execute(df, context)
```

### MappingStep

Rename DataFrame columns.

```python
step = MappingStep({'月度': 'report_date', '计划代码': 'plan_code'})
```

### ReplacementStep

Replace values in columns.

```python
step = ReplacementStep({
    'status': {'draft': 'pending', 'old': 'archived'}
})
```

### CalculationStep

Add calculated fields using vectorized operations.

```python
step = CalculationStep({
    'total': lambda df: df['a'] + df['b'],
    'ratio': lambda df: df['x'] / df['y'],
})
```

### FilterStep

Filter rows based on boolean conditions.

```python
step = FilterStep(lambda df: df['value'] > 0, description="positive values only")
```

### CleansingStep

Apply cleansing rules from the cleansing registry.

```python
step = CleansingStep(domain="annuity_performance")
# Or with explicit rules
step = CleansingStep(
    domain="annuity_performance",
    rules_override={"客户名称": ["trim_whitespace", "normalize_company_name"]}
)
```

### DropStep

Remove specified columns.

```python
step = DropStep(['temp_col', 'debug_col'])
```

### RenameStep

Alias for MappingStep (semantic clarity).

```python
step = RenameStep({'old_name': 'new_name'})
```

## End-to-End Example

```python
from work_data_hub.infrastructure.transforms import (
    Pipeline, MappingStep, ReplacementStep, CalculationStep, FilterStep
)
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

# Create context
context = PipelineContext(
    pipeline_name="financial_processing",
    execution_id="run-001",
    timestamp=datetime.now(timezone.utc),
    config={},
)

# Build pipeline
pipeline = Pipeline([
    MappingStep({'月度': 'report_date', '计划代码': 'plan_code'}),
    ReplacementStep({'status': {'draft': 'pending'}}),
    CalculationStep({
        'return_rate': lambda df: df['income'] / df['assets'],
        'asset_change': lambda df: df['ending'] - df['beginning'],
    }),
    FilterStep(lambda df: df['assets'] > 10000),
])

# Execute
result = pipeline.execute(df_input, context)
```

## Error Handling

- **MappingStep**: Logs warning for missing columns, skips rename
- **ReplacementStep**: Logs warning for missing columns, continues
- **CalculationStep**: Raises exception on calculation error (fail fast)
- **FilterStep**: Raises ValueError if predicate returns None or wrong length
- **CleansingStep**: Logs warning for failed rules, continues processing

## Logging

All steps use structured logging via `structlog`:

```python
log.info("columns_renamed", count=5)
log.warning("column_not_found", column="missing_col")
log.error("calculation_failed", field="ratio", error="division by zero")
```

## Performance

All steps use vectorized Pandas operations:
- MappingStep: `df.rename(columns=mapping)`
- ReplacementStep: `df[column].replace(mapping)`
- CalculationStep: User-provided vectorized functions
- FilterStep: `df[boolean_mask]`

Target performance: <10ms per 1000 rows for standard operations.
