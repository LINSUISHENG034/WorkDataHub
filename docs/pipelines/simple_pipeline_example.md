# Simple Pipeline Reference (Story 1.5)

This reference implementation demonstrates how to compose the new pipeline executor
introduced in Story 1.5. The example lives in
`src/work_data_hub/domain/pipelines/examples.py` and chains three steps:

1. **AddColumnStep** – derives a `total` column (`revenue + expenses`) while keeping the input DataFrame immutable.
2. **FilterRowsStep** – filters the DataFrame using a configurable threshold to prove row filtering semantics.
3. **AggregateStep** – groups the filtered rows by `region` to showcase downstream aggregation.

```python
from work_data_hub.domain.pipelines.examples import build_reference_pipeline
import pandas as pd

input_df = pd.DataFrame(
    [
        {"region": "APAC", "revenue": 15, "expenses": 2},
        {"region": "APAC", "revenue": 3, "expenses": 1},
        {"region": "EMEA", "revenue": 20, "expenses": 5},
    ]
)

pipeline = build_reference_pipeline(min_total=10)
result = pipeline.run(input_df)

assert result.success
print(result.output_data)
# =>
#   region  region_total
# 0   APAC            17
# 1   EMEA            25
```

The sample pipeline emits the standard structlog events (`pipeline.started`,
`pipeline.step.started`, `pipeline.step.completed`, and `pipeline.completed`)
through the centralized logger (`work_data_hub.utils.logging`). Use this example
as the canonical template when building additional domain-specific pipelines.
