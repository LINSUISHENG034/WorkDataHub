# Generic Pipeline Steps

This module provides reusable, configuration-driven DataFrame transformation steps for the WorkDataHub pipeline framework.

> NOTE: DataFrame steps were migrated to `work_data_hub.infrastructure.transforms` in Story 5.6. Import `MappingStep`, `ReplacementStep`, `CalculationStep`, and `FilterStep` from the infrastructure module (examples below are updated).

## Overview

Story 1.12 introduces generic steps that implement the **Standard Domain Architecture Pattern** (Architecture Decision #9). These steps eliminate boilerplate code by accepting configuration dictionaries instead of hardcoded logic.

### Key Benefits

- **Configuration Over Code**: Static mappings live in `config.py`, not step classes
- **Pandas Vectorized Operations**: All steps use vectorized operations for optimal performance
- **Immutability**: Input DataFrames are never mutated; new DataFrames are always returned
- **Reusability**: Same steps work across all domains (annuity_performance, Epic 9 domains, etc.)

## Available Steps

### MappingStep

Renames DataFrame columns based on a configuration dictionary.

```python
from work_data_hub.infrastructure.transforms import MappingStep

column_mapping = {
    '月度': 'report_date',
    '计划代码': 'plan_code',
    '客户名称': 'customer_name'
}

step = MappingStep(column_mapping)
df_out = step.execute(df_in, context)
```

**Features:**
- Uses `df.rename(columns=mapping)` (Pandas vectorized operation)
- Missing columns are logged as warnings and skipped
- Returns new DataFrame (does not mutate input)

### ReplacementStep

Replaces values in specified columns based on configuration.

```python
from work_data_hub.infrastructure.transforms import ReplacementStep

value_replacements = {
    'plan_code': {
        'OLD_CODE_A': 'NEW_CODE_A',
        'OLD_CODE_B': 'NEW_CODE_B'
    },
    'business_type': {
        '旧值1': '新值1',
        '旧值2': '新值2'
    }
}

step = ReplacementStep(value_replacements)
df_out = step.execute(df_in, context)
```

**Features:**
- Uses `df.replace(replacement_dict)` (Pandas vectorized operation)
- Supports multiple columns with different mappings
- Values not in mapping remain unchanged

### CalculationStep

Adds calculated fields using lambda functions or callable objects.

```python
from work_data_hub.infrastructure.transforms import CalculationStep

calculated_fields = {
    'annualized_return': lambda df: df['investment_income'] / df['ending_assets'],
    'asset_change': lambda df: df['ending_assets'] - df['beginning_assets']
}

step = CalculationStep(calculated_fields)
df_out = step.execute(df_in, context)
```

**Features:**
- Calculation functions receive entire DataFrame (enabling vectorized operations)
- Handles errors gracefully (missing columns, division by zero)
- Failed calculations are logged and skipped; successful ones are kept

### FilterStep

Filters rows based on boolean conditions.

```python
from work_data_hub.infrastructure.transforms import FilterStep

filter_condition = lambda df: (df['ending_assets'] > 0) & (df['report_date'] >= '2025-01-01')

step = FilterStep(filter_condition, description="positive assets after 2025")
df_out = step.execute(df_in, context)
```

**Features:**
- Uses `df[condition]` (Pandas boolean indexing)
- Logs number of rows filtered out
- Returns empty DataFrame (not error) when all rows filtered

## Usage Patterns

### Domain Configuration Pattern

Store mappings in domain config files:

```python
# src/work_data_hub/domain/annuity_performance/config.py
COLUMN_MAPPING = {
    '月度': 'report_date',
    '计划代码': 'plan_code',
    '客户名称': 'customer_name'
}

VALUE_REPLACEMENTS = {
    'business_type': {'旧值1': '新值1', '旧值2': '新值2'}
}

CALCULATED_FIELDS = {
    'annualized_return': lambda df: df['investment_income'] / df['ending_assets']
}
```

```python
# src/work_data_hub/domain/annuity_performance/pipeline.py
from work_data_hub.infrastructure.transforms import (
    MappingStep,
    ReplacementStep,
    CalculationStep,
)
from .config import COLUMN_MAPPING, VALUE_REPLACEMENTS, CALCULATED_FIELDS

pipeline.add_step(MappingStep(COLUMN_MAPPING))
pipeline.add_step(ReplacementStep(VALUE_REPLACEMENTS))
pipeline.add_step(CalculationStep(CALCULATED_FIELDS))
```

### Complete Pipeline Example

```python
from work_data_hub.domain.pipelines.core import Pipeline, PipelineContext
from work_data_hub.infrastructure.transforms import (
    MappingStep,
    ReplacementStep,
    CalculationStep,
    FilterStep,
)

# Build pipeline using generic steps
pipeline = Pipeline("generic_steps_demo")
pipeline.add_step(MappingStep({'旧列名': '新列名'}))
pipeline.add_step(ReplacementStep({'status': {'draft': 'pending'}}))
pipeline.add_step(CalculationStep({'total': lambda df: df['a'] + df['b']}))
pipeline.add_step(FilterStep(lambda df: df['total'] > 0))

result = pipeline.run(input_df)
```

## When to Use Generic Steps vs. Custom Steps

### Use Generic Steps When:

- ✅ Column renaming (use `MappingStep`)
- ✅ Value replacement/mapping (use `ReplacementStep`)
- ✅ Simple calculations (addition, subtraction, ratios) (use `CalculationStep`)
- ✅ Row filtering based on conditions (use `FilterStep`)

### Create Custom Steps When:

- ❌ Complex business logic that spans multiple columns with conditional branching
- ❌ External API calls or database lookups during transformation
- ❌ Stateful transformations that depend on previous rows
- ❌ Domain-specific validation with custom error handling

## Performance Targets

All generic steps are designed for high performance using Pandas vectorized operations:

| Step | Target (10,000 rows) |
|------|---------------------|
| MappingStep | <5ms |
| ReplacementStep | <10ms |
| CalculationStep | <20ms |
| FilterStep | <5ms |

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Wrong | What To Do Instead |
|--------------|----------------|-------------------|
| ❌ `df.iterrows()` | Defeats vectorization, kills performance | Use vectorized Pandas operations |
| ❌ `df.apply(axis=1)` | Row-by-row iteration | Use vectorized operations or `CalculationStep` |
| ❌ Hardcoded logic in step classes | Creates domain-specific coupling | Accept configuration as constructor parameter |
| ❌ Mutating input DataFrame | Breaks immutability contract | Always return new DataFrame |

## References

- **Architecture Decision #3**: Hybrid Pipeline Step Protocol (`docs/architecture.md`)
- **Architecture Decision #9**: Standard Domain Architecture Pattern (`docs/architecture.md`)
- **Story 1.12**: Implement Standard Domain Generic Steps
- **Pipeline Framework**: `src/work_data_hub/domain/pipelines/core.py`
