# Epic 2 Performance Acceptance Criteria

**Epic**: Epic 2 - Multi-Layer Data Quality Framework
**Version**: 1.0
**Date**: 2025-11-16
**Status**: MANDATORY for all Epic 2 stories

---

## Overview

This document defines **mandatory** performance acceptance criteria for Epic 2's validation framework. All stories implementing Pydantic, Pandera, or custom validation steps must meet these thresholds before story completion.

**Rationale**: Epic 1 Retrospective identified "Validation Performance Death Spiral" as a potential Epic 2 failure scenario. These criteria prevent production performance issues.

---

## Performance Acceptance Criteria

### AC-PERF-1: Validation Throughput (MANDATORY)

**Requirement**: Pydantic/Pandera validation must process **≥1000 rows/second** on standard hardware.

**Test Hardware Baseline**:
- **Local Development**: Developer laptops (2020+ models, 16GB RAM minimum)
- **CI Environment**: GitHub Actions standard runners (2 CPU cores, 7GB RAM)
- **Production Estimate**: AWS EC2 t3.medium or equivalent (2 vCPU, 4GB RAM)

**Measurement Method**:
```python
import time
import pandas as pd

# Prepare test data
df = pd.DataFrame([...])  # 10,000 rows minimum
pipeline = Pipeline(steps=[validation_step], config=config)

# Measure execution time
start = time.time()
result = pipeline.execute(df)
duration = time.time() - start

# Calculate throughput
rows_per_second = len(df) / duration

# Acceptance criterion
assert rows_per_second >= 1000, \
    f"Validation throughput {rows_per_second:.0f} rows/s < 1000 rows/s threshold"
```

**Test File**: `tests/integration/test_validation_performance.py`

**Failure Handling**:
- If throughput < 1000 rows/s: Story **BLOCKED**, must optimize before review
- Acceptable optimizations:
  - Vectorize operations (prefer DataFrame ops over row-by-row)
  - Cache expensive lookups
  - Use Pydantic's batch validation mode
  - Profile and optimize hot paths

---

### AC-PERF-2: Validation Overhead Budget (MANDATORY)

**Requirement**: Validation overhead must be **<20%** of total pipeline execution time.

**Definition**:
```
Validation Overhead % = (Total Validation Time / Total Pipeline Time) × 100
```

**Measurement Method**:
```python
result = pipeline.execute(df)

# Extract timing from pipeline metrics
validation_time = sum(
    step.duration_seconds
    for step in result.metrics.step_metrics
    if "validation" in step.name.lower() or
       "pydantic" in step.name.lower() or
       "pandera" in step.name.lower()
)

total_time = result.metrics.duration_seconds
overhead_pct = (validation_time / total_time) * 100

# Acceptance criterion
assert overhead_pct < 20.0, \
    f"Validation overhead {overhead_pct:.1f}% exceeds 20% threshold"
```

**Test File**: `tests/integration/test_validation_overhead.py`

**Guidance**:
- **Acceptable overhead**: 10-15% for typical validation workloads
- **Warning zone**: 15-20% - consider optimization if data volume grows
- **Failure**: >20% - must refactor validation approach

**Optimization Strategies**:
1. **Schema validation first** (fast, fails early): Pandera DataFrameStep
2. **Business rules second** (slower): Pydantic RowTransformStep
3. **Expensive lookups last** (slowest): Enrichment, external APIs

---

### AC-PERF-3: Baseline Regression Tracking (RECOMMENDED)

**Requirement**: Track performance baselines using `.performance_baseline.json` pattern from Story 1.11.

**Baseline File Structure**:
```json
{
  "validation_throughput_rows_per_sec": {
    "pydantic_field_validation": 1500,
    "pandera_schema_validation": 5000,
    "business_rules_validation": 1200
  },
  "overhead_percentage": {
    "pydantic_field_validation": 12.5,
    "pandera_schema_validation": 5.0,
    "business_rules_validation": 15.0
  },
  "test_data_size": 10000,
  "last_updated": "2025-11-16T10:30:00Z"
}
```

**Warning Threshold**: Performance degrades >20% from baseline
- Example: If baseline throughput is 1500 rows/s, warn if drops below 1200 rows/s

**Test Implementation**:
```python
import json
from pathlib import Path

baseline_file = Path("tests/.performance_baseline.json")

if baseline_file.exists():
    baseline = json.loads(baseline_file.read_text())
    baseline_throughput = baseline["validation_throughput_rows_per_sec"]["pydantic_field_validation"]

    if rows_per_second < baseline_throughput * 0.8:
        pytest.warns(
            UserWarning,
            match=f"Performance degraded {((baseline_throughput - rows_per_second) / baseline_throughput * 100):.1f}%"
        )
```

---

## Story-Specific Requirements

### Epic 2 Story 2.1: Pydantic Field-Level Validation

**Acceptance Criteria**:
- [ ] AC-PERF-1: Pydantic validation ≥1000 rows/s
- [ ] AC-PERF-2: Validation overhead <20%
- [ ] Performance test with 10,000-row fixture
- [ ] Baseline recorded in `.performance_baseline.json`

**Target Throughput**: 1500+ rows/s (50% above minimum for safety margin)

---

### Epic 2 Story 2.2: Pandera DataFrame Schema Validation

**Acceptance Criteria**:
- [ ] AC-PERF-1: Pandera validation ≥1000 rows/s
- [ ] AC-PERF-2: Validation overhead <20%
- [ ] Performance test with 10,000-row fixture

**Expected Throughput**: 5000+ rows/s (Pandera operates on entire DataFrame, should be faster than row-by-row)

**Note**: If Pandera throughput <1000 rows/s, investigate:
- Schema complexity (too many check constraints)
- Type coercion overhead
- Index operations

---

### Epic 2 Story 2.3: Custom Cleansing Rules

**Acceptance Criteria**:
- [ ] AC-PERF-1: Cleansing throughput ≥1000 rows/s
- [ ] AC-PERF-2: Cleansing overhead <20%
- [ ] Regex patterns optimized (compiled, not re-created per row)

**Optimization Tip**: Use Pandas vectorized string operations instead of row-by-row regex:
```python
# ❌ Slow: Row-by-row regex
df.apply(lambda row: re.sub(pattern, repl, row['field']), axis=1)

# ✅ Fast: Vectorized string operation
df['field'].str.replace(pattern, repl, regex=True)
```

---

### Epic 2 Story 2.5: Validation Error Reporting

**Acceptance Criteria**:
- [ ] Error collection overhead <5% (on top of validation overhead)
- [ ] CSV export completes in <2 seconds for 10,000 rows
- [ ] Error message formatting throughput ≥5000 messages/s

**Note**: Error collection mode (`stop_on_error=False`) should NOT significantly slow down pipeline.

---

## Test Data Requirements

### Minimum Test Data Volume

All performance tests MUST use **10,000-row CSV fixtures** minimum to represent realistic production volumes.

**Fixture Location**: `tests/fixtures/performance/annuity_performance_10k.csv`

**Data Characteristics**:
- Realistic column count (15-25 columns)
- Realistic data types (strings, dates, decimals)
- Mix of valid and invalid rows (90% valid, 10% with validation errors)

**Rationale**: Story 1.11 integration tests used 5-row fixtures, which did not catch performance regressions. Epic 1 Retrospective identified this as a gap.

---

## Measurement Tools

### pytest-benchmark (Optional)

For detailed profiling, consider using `pytest-benchmark`:

```python
def test_pydantic_validation_benchmark(benchmark):
    df = pd.read_csv("tests/fixtures/performance/annuity_performance_10k.csv")

    result = benchmark(lambda: pipeline.execute(df))

    # pytest-benchmark automatically tracks min/max/mean/stddev
    assert result.metrics.rows_processed == 10000
```

### cProfile (For Hotspot Analysis)

If performance tests fail, profile to identify bottlenecks:

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

result = pipeline.execute(df)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Show top 20 slowest functions
```

---

## Failure Scenarios and Remediation

### Scenario 1: Throughput <1000 rows/s

**Symptoms**:
- AC-PERF-1 fails
- Test execution takes >10 seconds for 10k rows

**Common Causes**:
1. Row-by-row processing instead of vectorized operations
2. Expensive Pydantic validators (network calls, database lookups)
3. Unoptimized regex patterns (re-compiled each row)

**Remediation Steps**:
1. Profile with cProfile to identify hot spots
2. Vectorize operations where possible (use Pandera for schema checks)
3. Cache expensive lookups (use `@lru_cache` for pure functions)
4. Move slow validations to separate enrichment step (async processing)

---

### Scenario 2: Overhead >20%

**Symptoms**:
- AC-PERF-2 fails
- Validation time dominates total execution time

**Common Causes**:
1. Too many validation steps (redundant checks)
2. Validation placed before cheap filters (wastes CPU on rows that will be filtered)
3. Schema validation AND Pydantic validation (duplicated type checks)

**Remediation Steps**:
1. Reorder pipeline steps (cheap filters first, expensive validation last)
2. Combine validation logic (single Pydantic model instead of multiple steps)
3. Use Pandera for schema/type checks, Pydantic only for business rules

---

### Scenario 3: Regression from Baseline

**Symptoms**:
- AC-PERF-3 warns of >20% degradation
- Tests that previously passed now fail

**Common Causes**:
1. Added new validation rules without optimization
2. Changed data volume (fixture grew from 10k to 50k rows)
3. Dependency upgrade introduced performance regression

**Remediation Steps**:
1. Review recent changes with `git diff`
2. Bisect to identify regressing commit
3. Profile before/after comparison
4. Update baseline if intentional change (document reason)

---

## Reporting Performance Results

### In Story Completion Notes

Include performance metrics in Dev Agent Record:

```markdown
## Performance Validation

**Test Configuration**:
- Data volume: 10,000 rows
- Hardware: Local development (MacBook Pro M1, 16GB RAM)
- Test file: `tests/integration/test_story_2_1_performance.py`

**Results**:
- ✅ AC-PERF-1: Pydantic validation throughput: 1,542 rows/s (>1000 threshold)
- ✅ AC-PERF-2: Validation overhead: 14.3% (<20% threshold)
- ✅ AC-PERF-3: Baseline recorded: `tests/.performance_baseline.json`

**Optimization Notes**:
- Used Pydantic's `ValidationInfo` context to avoid redundant lookups
- Cached date parsing with `@lru_cache(maxsize=1000)`
- Vectorized currency symbol removal with Pandas `.str.replace()`
```

---

## References

- [Epic 1 Retrospective: Validation Performance Death Spiral](../docs/sprint-artifacts/epic-1-retrospective-2025-11-16.md#failure-scenario-2-the-validation-performance-death-spiral)
- [Story 1.11: Performance Baseline Pattern](../docs/sprint-artifacts/stories/1-11-enhanced-cicd-with-integration-tests.md)
- [Pipeline Integration Guide: Performance Optimization](../docs/pipeline-integration-guide.md#best-practices)

---

**Document Version**: 1.0
**Mandatory Compliance**: ALL Epic 2 stories
**Non-Compliance**: Story cannot be marked "Done" until performance criteria met
