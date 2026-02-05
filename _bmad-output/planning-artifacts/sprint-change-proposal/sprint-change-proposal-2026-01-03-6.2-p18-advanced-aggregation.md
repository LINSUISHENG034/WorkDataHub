# Sprint Change Proposal: Advanced Aggregation for Backfill Mechanism

**Date**: 2026-01-03
**Author**: AI Agent
**Status**: Draft - Pending Review
**Change Scope**: Minor
**Story**: 6.2-P18

---

## Section 1: Issue Summary

### Problem Statement

The current backfill mechanism supports limited aggregation types (`first`, `max_by`, `concat_distinct`), which are insufficient for three key business requirements:

1.  **Composite Text Construction**: Combining static templates with dynamic field values (e.g., labels like `"新建客户_2510"`).
2.  **Distinct Counting**: Calculating the number of unique related items (e.g., counting associated plans for a customer).
3.  **Complex Transformations**: Arbitrary logic application that cannot be covered by standard aggregations (e.g., specific date formatting logic inside a label).

### Use Case Examples

1.  **Template Aggregation**:
    - Target: `年金客户.年金客户标签`
    - Requirement: Insert `"新建客户_{月度}"` where `{月度}` is dynamically derived from source data.
2.  **Count Distinct Aggregation**:
    - Target: `年金客户.关联计划数`
    - Requirement: Count unique `计划代码` associated with each `company_id`.
3.  **Lambda Aggregation**:
    - Target: `年金客户.复杂标签`
    - Requirement: `"新建客户_" + (月度前4位)`. Requires substring slicing logic.

### Context

These requirements are essential for enriching reference tables (like `年金客户`) with derived insights during the backfill process in the Multi-Domain ETL Framework (Epic 6).

---

## Section 2: Impact Analysis

### Epic Impact

- **Epic 6.2 (Generic Reference Data Management)**: Extension to existing backfill framework.
- No epic scope change required.

### Story Impact

- **Story 6.2-P15 (Complex Mapping Backfill Enhancement)**: Foundation - established `max_by` and `concat_distinct` patterns.
- **Story 6.2-P18**: New story for "Advanced Aggregation Capabilities" (this proposal).

### Artifact Conflicts

| Artifact                                                         | Impact                                                      |
| :--------------------------------------------------------------- | :---------------------------------------------------------- |
| `config/foreign_keys.yml`                                        | New aggregation types usage (optional)                      |
| `src/work_data_hub/domain/reference_backfill/models.py`          | Add `TEMPLATE`, `COUNT_DISTINCT`, `LAMBDA` enums and config |
| `src/work_data_hub/domain/reference_backfill/generic_service.py` | Add aggregation methods including `eval()` for lambda       |
| Architecture docs                                                | No change required                                          |
| UI/UX specs                                                      | N/A                                                         |

### Technical Impact

- **Backward Compatible**: Existing configurations continue to work unchanged.
- **Low Risk**: Isolated logic extensions within established patterns.
- **Security Note**: `LAMBDA` aggregation uses `eval()`. Since this is an internal developer tool configured via YAML (trusted source), this is acceptable but should be noted.

---

## Section 3: Recommended Approach

### Chosen Path: Direct Adjustment

Extend `AggregationType` with `template`, `count_distinct`, and `lambda`.

### Effort Estimate

| Task                              | Estimate       |
| :-------------------------------- | :------------- |
| Model changes (enums + config)    | 30 min         |
| Service implementation (Template) | 30 min         |
| Service implementation (Count)    | 30 min         |
| Service implementation (Lambda)   | 30 min         |
| Unit tests                        | 1.5 hours      |
| Documentation                     | 30 min         |
| **Total**                         | **~3.5 hours** |

---

## Section 4: Detailed Change Proposals

### 4.1 Model Changes

**File**: `src/work_data_hub/domain/reference_backfill/models.py`

#### 4.1.1 AggregationType Enum

```python
class AggregationType(str, Enum):
    FIRST = "first"
    MAX_BY = "max_by"
    CONCAT_DISTINCT = "concat_distinct"
    TEMPLATE = "template"
    COUNT_DISTINCT = "count_distinct"
    LAMBDA = "lambda"
```

#### 4.1.2 AggregationConfig Model

```python
class AggregationConfig(BaseModel):
    # ... existing fields ...
    template: Optional[str] = Field(
        default=None,
        description="Template string with {field} placeholders for template aggregation"
    )
    template_fields: List[str] = Field(
        default_factory=list,
        description="List of field names to extract values for template substitution"
    )
    code: Optional[str] = Field(
        default=None,
        description="Python lambda expression string (e.g., \"lambda g: g['col'].max()\")"
    )

    @model_validator(mode="after")
    def validate_config(self):
        # ... existing validation ...
        if self.type == AggregationType.TEMPLATE and not self.template:
            raise ValueError("template is required when type is 'template'")
        if self.type == AggregationType.LAMBDA and not self.code:
            raise ValueError("code is required when type is 'lambda'")
        return self
```

### 4.2 Service Changes

**File**: `src/work_data_hub/domain/reference_backfill/generic_service.py`

#### 4.2.1 Count Distinct Implementation

```python
def _aggregate_count_distinct(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """
    Count distinct non-null values per group.

    Args:
        df: Source DataFrame
        group_col: Column to group by
        mapping: Column mapping configuration

    Returns:
        Series with count of distinct values per group
    """
    source_col = mapping.source
    if source_col not in df.columns:
        self.logger.warning(f"Source column '{source_col}' not found for count_distinct")
        return pd.Series(dtype="Int64")

    # Filter out null/blank values before counting
    valid_mask = self._non_blank_mask(df[source_col])
    filtered_df = df[valid_mask]

    return filtered_df.groupby(group_col, sort=False)[source_col].nunique()
```

#### 4.2.2 Lambda Implementation (with Security Measures)

```python
# Security: Allowed builtins whitelist for lambda evaluation
_LAMBDA_ALLOWED_BUILTINS = {
    "len", "str", "int", "float", "bool", "list", "dict", "set",
    "min", "max", "sum", "sorted", "enumerate", "zip", "range",
}

def _aggregate_lambda(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """
    Execute user-defined lambda expression on each group.

    SECURITY NOTE:
    - Config files are developer-controlled (trusted source)
    - Restricted builtins whitelist prevents dangerous operations
    - No access to __import__, open, exec, eval within lambda

    Args:
        df: Source DataFrame
        group_col: Column to group by
        mapping: Column mapping with lambda code

    Returns:
        Series with aggregated values per group

    Raises:
        ValueError: If lambda compilation fails
        RuntimeError: If lambda execution fails
    """
    code = mapping.aggregation.code

    # Security: Create restricted globals
    safe_builtins = {k: __builtins__[k] for k in _LAMBDA_ALLOWED_BUILTINS
                     if k in __builtins__}
    restricted_globals = {"__builtins__": safe_builtins}

    try:
        func = eval(code, restricted_globals, {})
    except SyntaxError as e:
        raise ValueError(f"Invalid lambda syntax: {code}") from e
    except Exception as e:
        self.logger.error(f"Failed to compile lambda: {code}. Error: {e}")
        raise ValueError(f"Lambda compilation failed: {e}") from e

    try:
        return df.groupby(group_col, sort=False).apply(func, include_groups=False)
    except Exception as e:
        self.logger.error(f"Lambda execution failed: {e}")
        raise RuntimeError(f"Lambda execution failed for column {mapping.target}: {e}") from e
```

#### 4.2.3 Template Implementation

```python
def _aggregate_template(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """
    Apply template string with field placeholders.

    Template format: "prefix_{field1}_suffix_{field2}"
    Placeholders are replaced with first non-null value from each group.

    Args:
        df: Source DataFrame
        group_col: Column to group by
        mapping: Column mapping with template config

    Returns:
        Series with formatted template strings per group

    Raises:
        ValueError: If template references non-existent field
    """
    template = mapping.aggregation.template
    template_fields = mapping.aggregation.template_fields or []

    # Extract field names from template if not explicitly provided
    if not template_fields:
        import re
        template_fields = re.findall(r'\{(\w+)\}', template)

    # Validate all template fields exist
    missing_fields = [f for f in template_fields if f not in df.columns]
    if missing_fields:
        raise ValueError(f"Template references missing fields: {missing_fields}")

    def apply_template(group: pd.DataFrame) -> str:
        values = {}
        for field in template_fields:
            # Get first non-null value
            non_null = group[field].dropna()
            values[field] = str(non_null.iloc[0]) if len(non_null) > 0 else ""
        return template.format(**values)

    return df.groupby(group_col, sort=False).apply(apply_template, include_groups=False)
```

### 4.3 Configuration Usage Example

**File**: `config/foreign_keys.yml`

```yaml
# Template Example
- source: "月度"
  target: "年金客户标签"
  aggregation:
    type: "template"
    template: "新建客户_{月度}"

# Count Distinct Example
- source: "计划代码"
  target: "关联计划数"
  optional: true
  aggregation:
    type: "count_distinct"

# Lambda Example
- source: "月度"
  target: "复杂标签"
  aggregation:
    type: "lambda"
    code: 'lambda g: f''PREFIX_{g["月度"].iloc[0]}'''
```

### 4.4 Error Handling Strategy

| Scenario | Behavior | Log Level |
|:---------|:---------|:----------|
| Template references non-existent field | Raise `ValueError`, abort backfill for this FK | ERROR |
| Lambda syntax error | Raise `ValueError`, abort backfill for this FK | ERROR |
| Lambda execution error | Raise `RuntimeError`, abort backfill for this FK | ERROR |
| Count distinct on missing column | Return empty Series, continue processing | WARNING |
| Template field has all NULL values | Use empty string `""` in template | DEBUG |

**Rationale**: Fail-fast for configuration errors (template/lambda), graceful degradation for data issues.

---

## Section 5: Implementation Handoff

### Change Scope Classification

**Minor** - Can be implemented directly by development team.

### Success Criteria

1.  `template` works for formatting.
2.  `count_distinct` works for counting.
3.  `lambda` correctly executes dynamic python code.
4.  All tests pass.

### Verification Plan

#### Automated Tests

**Command**:

```bash
pytest tests/unit/domain/reference_backfill/test_generic_backfill_service.py -v
```

**New Tests**:

- `test_template_aggregation`
- `test_count_distinct_aggregation`
- `test_lambda_aggregation`
- `test_validation_rules`

#### Manual Verification

1.  Run ETL with updated YAML config using lambda.
2.  Verify DB results.

---

## Approval

- [ ] User review and approval
- [ ] Implementation can proceed after approval
