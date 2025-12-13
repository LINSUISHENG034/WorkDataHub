# Breaking Change Review Checklist

**Purpose**: Ensure modifications to core framework code (Pipeline, WarehouseLoader, etc.) preserve backward compatibility and do not break existing functionality.

**When to Use**: BEFORE merging any pull request that modifies:
- `src/work_data_hub/domain/pipelines/` (Pipeline framework)
- `src/work_data_hub/io/loader/warehouse_loader.py` (WarehouseLoader)
- `src/work_data_hub/orchestration/ops.py` (Dagster ops)
- Any core framework class/function used by multiple stories

---

## Pre-Merge Requirements (BLOCKING)

### ✅ Backward Compatibility Verification

All items below MUST pass before merging framework changes.

#### 1. Story 1.5 Pipeline Core Tests

**Requirement**: Verify Story 1.5 unit tests still pass without modification.

```bash
# Run Story 1.5 pipeline core tests
uv run pytest tests/domain/pipelines/test_core.py -v

# Expected: All tests pass with 0 failures
```

**What This Verifies**:
- [x] Pipeline class constructor signature unchanged
- [x] Step execution order preserved
- [x] Error handling behavior unchanged
- [x] Metrics collection still functional

**If Tests Fail**:
- Review Pipeline.__init__() signature changes
- Check if new required parameters added (should be optional)
- Verify step execution loop not modified
- Examine PipelineResult structure changes

---

#### 2. Story 1.9 Dagster Integration Tests

**Requirement**: Verify Dagster sample_pipeline_job still executes successfully.

```bash
# Run Story 1.9 Dagster integration tests
uv run pytest tests/integration/test_dagster_sample_job.py -v

# Expected: All tests pass, especially:
# - test_sample_pipeline_job_executes_successfully
# - test_sample_pipeline_job_backward_compatibility
```

**What This Verifies**:
- [x] Dagster ops can still instantiate Pipeline
- [x] Op wiring still functional (read → validate → load)
- [x] No runtime errors in orchestration layer
- [x] Clean Architecture boundaries preserved

**If Tests Fail**:
- Check validate_op Pipeline instantiation (common issue)
- Verify read_csv_op output structure unchanged
- Examine load_to_db_op parameter passing
- Review Dagster OpExecutionContext usage

---

#### 3. Story 1.10 Advanced Features Tests

**Requirement**: Verify advanced pipeline features (retry logic, error collection mode) still work.

```bash
# Run Story 1.10 advanced features tests
uv run pytest tests/domain/pipelines/ -k "retry or error_collection" -v

# Expected: All retry and error collection tests pass
```

**What This Verifies**:
- [x] Retry logic still functional (tiered retry limits)
- [x] Error collection mode works (`stop_on_error=False`)
- [x] PipelineConfig optional parameters preserved
- [x] Exponential backoff behavior unchanged

**If Tests Fail**:
- Review PipelineConfig field changes
- Check is_retryable_error() function modifications
- Verify error_rows structure unchanged
- Examine retry_limits dictionary handling

---

#### 4. Integration Test Suite (Full)

**Requirement**: Run complete integration test suite to catch cross-story regressions.

```bash
# Run all integration tests
uv run pytest tests/integration/ -v

# Expected: All tests pass (may take 1-3 minutes)
```

**What This Verifies**:
- [x] End-to-end pipeline execution
- [x] Database loading (WarehouseLoader)
- [x] Performance baselines not regressed
- [x] No unexpected side effects

---

### ✅ API Signature Verification

#### Check 1: Pipeline Constructor Signature

**Current Signature** (Story 1.5 + Story 1.10):
```python
def __init__(self, steps: List[TransformStep], config: PipelineConfig):
    ...
```

**Verification**:
- [x] `steps` parameter remains required, same type
- [x] `config` parameter remains required, same type
- [x] No new required parameters added
- [x] No parameters removed

**How to Verify**:
```bash
# Search for all Pipeline instantiations in codebase
grep -r "Pipeline(" src/ tests/

# Manually verify each instantiation still works
# Common locations:
# - src/work_data_hub/orchestration/ops.py (validate_op)
# - tests/domain/pipelines/test_core.py
# - tests/integration/test_*.py
```

**If Signature Changed**:
- Add new parameters as optional with default values
- Preserve existing parameter order
- Add deprecation warning for old patterns (if intentional breaking change)
- Update ALL usages in:
  - `src/work_data_hub/orchestration/ops.py`
  - `tests/domain/pipelines/`
  - `tests/integration/`
  - `docs/pipeline-integration-guide.md`

---

#### Check 2: DataFrameStep and RowTransformStep Protocols

**Current Signatures**:
```python
class DataFrameStep(TransformStep, Protocol):
    def execute(self, dataframe: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        ...

class RowTransformStep(TransformStep, Protocol):
    def apply(self, row: Row, context: PipelineContext) -> StepResult:
        ...
```

**Verification**:
- [x] `execute()` signature unchanged
- [x] `apply()` signature unchanged
- [x] Return types unchanged
- [x] No new required methods without default implementations

**How to Verify**:
```bash
# Find all implementations of DataFrameStep
grep -r "class.*DataFrameStep" src/

# Find all implementations of RowTransformStep
grep -r "class.*RowTransformStep" src/

# Verify each implementation still works
```

---

#### Check 3: PipelineConfig Fields

**Required Fields** (Story 1.5):
- `name: str`
- `steps: List[StepConfig]`

**Optional Fields** (Story 1.10):
- `stop_on_error: bool = True`
- `max_retries: int = 3`
- `retry_backoff_base: float = 1.0`
- `retryable_exceptions: tuple = (...)`
- `retryable_http_status_codes: tuple = (...)`
- `retry_limits: Dict[str, int] = {...}`

**Verification**:
- [x] All required fields remain required
- [x] New fields added as optional with defaults
- [x] No existing fields removed
- [x] Field types unchanged (no int → str coercion, etc.)

**How to Verify**:
```bash
# Review PipelineConfig definition
cat src/work_data_hub/domain/pipelines/config.py

# Check for field changes in git diff
git diff main src/work_data_hub/domain/pipelines/config.py
```

---

### ✅ Behavior Verification

#### Test 1: Error Propagation Behavior

**Requirement**: Errors still propagate correctly in both modes.

```python
# Test stop_on_error=True (default)
config = PipelineConfig(name="test", steps=[...], stop_on_error=True)
pipeline = Pipeline(steps=[failing_step], config=config)

result = pipeline.execute(df)
assert result.success is False
assert len(result.error_rows) > 0  # Errors captured

# Test stop_on_error=False (error collection mode)
config = PipelineConfig(name="test", steps=[...], stop_on_error=False)
pipeline = Pipeline(steps=[failing_step], config=config)

result = pipeline.execute(df)
# Should not raise exception, collect errors
assert len(result.error_rows) > 0
```

**Verification Checklist**:
- [x] `stop_on_error=True` still raises exception on error
- [x] `stop_on_error=False` collects errors without exception
- [x] error_rows structure unchanged: `{row_index, row_data, error_message, step_name}`

---

#### Test 2: Retry Behavior (Tiered Limits)

**Requirement**: Tiered retry logic still respects limits.

```python
# Database errors: 5 retries
# Network errors: 3 retries
# HTTP errors: 2-3 retries (status-dependent)

config = PipelineConfig(
    name="test",
    steps=[...],
    retry_limits={
        "database": 5,
        "network": 3,
        "http_429_503": 3,
        "http_500_502_504": 2,
    }
)
```

**Verification Checklist**:
- [x] Database errors (psycopg2.OperationalError) retry 5 times
- [x] Network errors (requests.Timeout) retry 3 times
- [x] HTTP 429/503 retry 3 times
- [x] HTTP 500/502/504 retry 2 times
- [x] Data errors (ValueError) do NOT retry

**How to Verify**:
```bash
# Run Story 1.10 retry tests
uv run pytest tests/domain/pipelines/ -k "retry" -v
```

---

#### Test 3: Metrics Collection

**Requirement**: Pipeline execution metrics still collected.

```python
result = pipeline.execute(df)

# Verify metrics structure unchanged
assert hasattr(result.metrics, 'rows_processed')
assert hasattr(result.metrics, 'duration_seconds')
assert hasattr(result.metrics, 'step_metrics')

# Verify step metrics structure
for step_metric in result.metrics.step_metrics:
    assert hasattr(step_metric, 'name')
    assert hasattr(step_metric, 'duration_seconds')
    assert hasattr(step_metric, 'rows_processed')
```

**Verification Checklist**:
- [x] PipelineResult.metrics exists
- [x] rows_processed count accurate
- [x] duration_seconds tracked
- [x] step_metrics list populated
- [x] StepMetrics structure unchanged

---

## Documentation Updates (REQUIRED)

### Update 1: Pipeline Integration Guide

**File**: `docs/pipeline-integration-guide.md`

**Required Updates** if API changed:
- [x] Update API Reference section with new signatures
- [x] Add examples showing new feature usage
- [x] Update "Troubleshooting" section with new error modes
- [x] Add migration guide if breaking change

**Example**:
```markdown
## Breaking Changes in v2.0

### Pipeline Constructor Change

**Old (v1.x)**:
```python
pipeline = Pipeline(name="test", steps=[...])
```

**New (v2.x)**:
```python
config = PipelineConfig(name="test", steps=[...])
pipeline = Pipeline(steps=[...], config=config)
```

**Migration Guide**:
1. Extract `name` into `PipelineConfig`
2. Pass `config` object to Pipeline constructor
3. Update all instantiations (use `grep -r "Pipeline(" src/`)
```

---

### Update 2: CHANGELOG.md

**File**: `CHANGELOG.md`

**Required Entry Format**:
```markdown
## [Unreleased]

### Changed
- **BREAKING**: Pipeline constructor now requires PipelineConfig object instead of name parameter
  - Migration: See docs/pipeline-integration-guide.md#breaking-changes
  - Affects: All code instantiating Pipeline directly

### Added
- PipelineConfig now supports custom retry limits via `retry_limits` parameter

### Deprecated
- Pipeline(name=...) constructor pattern deprecated, use PipelineConfig instead
  - Deprecation warnings will be removed in v3.0

### Fixed
- Retry logic now respects tiered retry limits correctly
```

---

### Update 3: Story Files

**Files**: `docs/sprint-artifacts/stories/*.md`

**Required Updates**:
- [x] Update Dev Agent Record with backward compatibility notes
- [x] Document which tests were run to verify compatibility
- [x] List all files modified and potential impact

**Example** (in story completion notes):
```markdown
## Backward Compatibility Verification

**Tests Run**:
- ✅ Story 1.5 pipeline core tests: `pytest tests/domain/pipelines/test_core.py` (PASSED)
- ✅ Story 1.9 Dagster integration: `pytest tests/integration/test_dagster_sample_job.py` (PASSED)
- ✅ Story 1.10 advanced features: `pytest tests/domain/pipelines/ -k retry` (PASSED)

**API Changes**:
- Added optional `custom_validators` parameter to PipelineConfig
- Preserved all existing parameters and defaults
- No breaking changes to public API

**Migration Required**: None (fully backward compatible)
```

---

## Common Breaking Change Scenarios

### Scenario 1: Adding Required Parameter

**❌ BAD** (Breaking Change):
```python
# Before
def __init__(self, steps: List[TransformStep], config: PipelineConfig):
    ...

# After (BREAKING!)
def __init__(self, steps: List[TransformStep], config: PipelineConfig, validators: List[Validator]):
    ...
```

**✅ GOOD** (Backward Compatible):
```python
# After (compatible)
def __init__(
    self,
    steps: List[TransformStep],
    config: PipelineConfig,
    validators: Optional[List[Validator]] = None  # Optional with default
):
    ...
```

---

### Scenario 2: Changing Return Type

**❌ BAD** (Breaking Change):
```python
# Before
def execute(self, df: pd.DataFrame) -> pd.DataFrame:
    ...

# After (BREAKING!)
def execute(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Error]]:
    ...
```

**✅ GOOD** (Backward Compatible):
```python
# Keep old method, add new one
def execute(self, df: pd.DataFrame) -> pd.DataFrame:
    ...

def execute_with_errors(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Error]]:
    ...
```

---

### Scenario 3: Removing/Renaming Field

**❌ BAD** (Breaking Change):
```python
# Before
class PipelineConfig(BaseModel):
    name: str
    steps: List[StepConfig]

# After (BREAKING!)
class PipelineConfig(BaseModel):
    pipeline_name: str  # Renamed!
    steps: List[StepConfig]
```

**✅ GOOD** (Backward Compatible):
```python
# After (compatible with deprecation)
class PipelineConfig(BaseModel):
    name: str = Field(deprecated=True)  # Keep old field
    pipeline_name: str  # New field

    @model_validator(mode='before')
    def handle_deprecated_name(cls, values):
        # Auto-migrate old field to new
        if 'name' in values and 'pipeline_name' not in values:
            values['pipeline_name'] = values['name']
            warnings.warn("'name' is deprecated, use 'pipeline_name'", DeprecationWarning)
        return values
```

---

## Rollback Plan

**If Breaking Change Detected After Merge**:

1. **Immediate Actions**:
   - [ ] Revert commit: `git revert <commit-hash>`
   - [ ] Notify team in Slack/email
   - [ ] Document breaking change in incident log

2. **Fix Forward** (If revert not possible):
   - [ ] Add backward compatibility shim
   - [ ] Update all affected code locations
   - [ ] Add regression tests to prevent recurrence
   - [ ] Document migration path

3. **Post-Incident**:
   - [ ] Add missing test coverage
   - [ ] Update Breaking Change checklist with new scenario
   - [ ] Review why pre-merge checks didn't catch issue

---

## References

- [Epic 1 Retrospective: Backward Compatibility](../docs/sprint-artifacts/epic-1-retrospective-2025-11-16.md#3-backward-compatibility-must-be-verified-before-review)
- [Story 1.10: Backward Compatibility Preservation](../docs/sprint-artifacts/stories/1-10-pipeline-framework-advanced-features.md)
- [Pipeline Integration Guide](../docs/pipeline-integration-guide.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16 (Epic 2 Prep Work)
**Mandatory Use**: ALL framework modification pull requests
