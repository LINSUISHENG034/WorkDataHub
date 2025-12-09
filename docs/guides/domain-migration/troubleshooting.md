# Domain Migration Troubleshooting Guide

**Version:** 1.0
**Last Updated:** 2025-12-09
**Purpose:** Common issues and solutions during domain migration

---

## Quick Navigation

| Phase | Common Issues | Solutions |
|-------|---------------|-----------|
| [Phase 1](#phase-1-dependency-issues) | Migration failures, missing tables | Migration logs, database checks |
| [Phase 2](#phase-2-documentation-issues) | Incomplete documentation | Template checklist, peer review |
| [Phase 3](#phase-3-implementation-issues) | Code errors, test failures | Debug techniques, common fixes |
| [Phase 4](#phase-4-validation-issues) | Parity mismatches | Comparison tools, diff analysis |

---

## Phase 1: Dependency Issues

### Issue: Migration Script Fails

**Symptoms:**
```
Error: relation "legacy.table_name" does not exist
Migration failed: table not found
```

**Solutions:**

1. **Check source database connection:**
   ```bash
   PGPASSWORD="password" psql -h localhost -U user -d legacy_db -c "\dt"
   ```

2. **Verify table names in legacy code:**
   ```bash
   grep -r "FROM\|JOIN\|INTO" legacy/annuity_hub/data_handler/ | grep -i "table_name"
   ```

3. **Check migration script configuration:**
   ```python
   # In scripts/migrations/migrate_legacy_to_enrichment_index.py
   # Verify SOURCE_DB_CONFIG is correct
   print(f"Connecting to: {SOURCE_DB_CONFIG['database']}")
   ```

### Issue: Row Count Mismatch After Migration

**Symptoms:**
- Source: 19,141 rows
- Target: 18,923 rows
- 218 rows missing

**Solutions:**

1. **Check for NULL values in key columns:**
   ```sql
   SELECT COUNT(*) FROM legacy.table_name WHERE key_column IS NULL;
   ```

2. **Check for duplicates:**
   ```sql
   SELECT key_column, COUNT(*)
   FROM legacy.table_name
   GROUP BY key_column
   HAVING COUNT(*) > 1;
   ```

3. **Review migration logs for errors:**
   ```bash
   tail -f logs/migration_*.log | grep -i "error\|warning\|skipped"
   ```

### Issue: Performance Issues During Migration

**Symptoms:**
- Migration taking > 1 hour
- Database connection timeouts
- Memory errors

**Solutions:**

1. **Use batch processing:**
   ```python
   # Add to migration script
   BATCH_SIZE = 1000
   for offset in range(0, total_rows, BATCH_SIZE):
       process_batch(offset, BATCH_SIZE)
   ```

2. **Add indexes before migration:**
   ```sql
   CREATE INDEX idx_migration_key ON legacy.table_name(key_column);
   ```

3. **Run during off-peak hours:**
   - Schedule migrations for nights/weekends
   - Notify stakeholders about downtime

---

## Phase 2: Documentation Issues

### Issue: Incomplete Cleansing Rules Documentation

**Symptoms:**
- Template sections left blank
- Missing rule priorities
- Unclear transformation logic

**Solutions:**

1. **Use the documentation checklist:**
   - [ ] Review every line of legacy cleaner code
   - [ ] Map each transformation to a rule ID
   - [ ] Verify rule types (mapping, regex, conditional)
   - [ ] Check execution order

2. **Trace example data through legacy code:**
   ```python
   # Create a debug version of legacy cleaner
   def debug_cleaner(sample_data):
       print(f"Input: {sample_data}")
       # Step through each transformation
       print(f"After mapping: {result1}")
       print(f"After cleansing: {result2}")
       return final_result
   ```

3. **Peer review checklist:**
   - [ ] Can another developer implement from this doc?
   - [ ] Are all edge cases covered?
   - [ ] Is the logic unambiguous?

### Issue: Column Mapping Conflicts

**Symptoms:**
- Multiple legacy columns mapping to same target
- Circular dependencies
- Lost data during transformation

**Solutions:**

1. **Create mapping matrix:**
   ```markdown
   | Legacy Column | Target Column | Transformation | Source |
   |---------------|---------------|----------------|--------|
   | 机构 | 机构代码 | rename | Line 45 |
   | 机构名称 | 机构代码 | mapping | Line 47 |
   ```

2. **Identify conflicts:**
   ```python
   # Check for duplicate target columns
   targets = [v['target'] for v in column_mappings]
   duplicates = [x for x in set(targets) if targets.count(x) > 1]
   ```

3. **Resolve with intermediate columns:**
   ```python
   # Use temporary column names
   df['机构_from_name'] = df['机构名称'].map(mapping)
   df['机构_from_code'] = df['机构']
   # Then decide final logic
   ```

---

## Phase 3: Implementation Issues

### Issue: Pydantic Validation Errors

**Common Errors:**
```python
pydantic.ValidationError: 1 validation error for DomainOut
月度: Input should be a valid date [type=date_type]
```

**Solutions:**

1. **Check date parsing in field validators:**
   ```python
   @field_validator("月度", mode="before")
   @classmethod
   def parse_date(cls, v):
       if v is None:
           return None
       if isinstance(v, str):
           return parse_yyyymm_or_chinese(v)
       if isinstance(v, (int, float)):
           # Handle Excel serial dates
           return datetime.from_excel(v)
       return v
   ```

2. **Debug with model_dump:**
   ```python
   try:
       record = DomainOut(**data)
   except ValidationError as e:
       print(f"Failed data: {data}")
       print(f"Errors: {e.errors()}")
       raise
   ```

3. **Use optional types for bronze layer:**
   ```python
   class DomainIn(BaseModel):
       月度: Optional[Union[str, date, int]] = None
   ```

### Issue: Pipeline Step Ordering

**Symptoms:**
- Data cleaned before column renamed
- Mappings applied to wrong columns
- Company resolution failing

**Solutions:**

1. **Document step dependencies:**
   ```python
   def build_bronze_to_silver_pipeline():
       steps = [
           # Step 1: Column renaming (must be first)
           MappingStep(COLUMN_RENAME_MAPPING),

           # Step 2: Basic cleansing
           CleansingStep(domain="my_domain"),

           # Step 3: Complex transformations (depends on clean data)
           CalculationStep(complex_logic),

           # Step 4: Company ID resolution (depends on final columns)
           CompanyIdResolutionStep(...),
       ]
   ```

2. **Add debug logging between steps:**
   ```python
   class DebugStep(TransformStep):
       def transform(self, df, context):
           logger.info("Debug: columns=%s, rows=%d", df.columns.tolist(), len(df))
           return df
   ```

3. **Test with sample data:**
   ```python
   test_df = pd.DataFrame({
       "旧列名": ["value1", "value2"],
       "月度": ["202401", "202402"],
   })
   result = pipeline.execute(test_df)
   ```

### Issue: Test Failures

**Common Test Errors:**
```bash
FAILED tests/unit/domain/my_domain/test_models.py::TestDomainOut::test_invalid_data
AssertionError: Expected ValidationError but passed
```

**Solutions:**

1. **Verify test data is actually invalid:**
   ```python
   def test_invalid_date():
       with pytest.raises(ValidationError):
           DomainOut(月度="invalid_date")  # Make sure this is really invalid
   ```

2. **Check model configuration:**
   ```python
   # Make sure validation is strict enough
   class DomainOut(BaseModel):
       model_config = ConfigDict(
           strict=True,  # Reject extra fields
           validate_default=True,  # Validate defaults
           str_strip_whitespace=True,
       )
   ```

3. **Debug with hypothesis testing:**
   ```python
   from hypothesis import given, strategies as st

   @given(st.datetimes(min_value=datetime(2020, 1, 1)))
   def test_date_range(self, dt):
       record = DomainOut(月度=dt)
       assert record.月度 == dt.date()
   ```

---

## Phase 4: Validation Issues

### Issue: Parity Mismatch

**Symptoms:**
```
Row count: Legacy=1234, New=1232 (difference: 2)
Column X sum: Legacy=45678.90, New=45678.91 (difference: 0.01)
```

**Solutions:**

1. **Identify mismatched records:**
   ```python
   # Find records in legacy but not in new
   merged = legacy_df.merge(new_df, on=['key1', 'key2'], how='outer', indicator=True)
   missing = merged[merged['_merge'] == 'left_only']
   print(f"Missing in new: {len(missing)}")
   missing.to_csv('missing_records.csv', index=False)
   ```

2. **Check for rounding differences:**
   ```python
   # Use numpy.isclose for floating point comparison
   np.isclose(legacy_df['amount'], new_df['amount'], rtol=1e-4)
   ```

3. **Analyze differences systematically:**
   ```python
   def compare_columns(col):
       if col.dtype in ['object', 'string']:
           return (legacy_df[col] != new_df[col]).sum()
       else:
           return np.not_equal(legacy_df[col], new_df[col]).sum()

   differences = {col: compare_columns(legacy_df[col])
                 for col in legacy_df.columns}
   ```

### Issue: Performance Regression

**Symptoms:**
- Legacy: 10 seconds for 10,000 rows
- New: 2 minutes for 10,000 rows

**Solutions:**

1. **Profile the pipeline:**
   ```python
   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()

   result = pipeline.execute(df)

   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(20)  # Top 20 slowest functions
   ```

2. **Optimize common bottlenecks:**
   ```python
   # Use vectorized operations instead of apply
   # Bad:
   df['new_col'] = df.apply(lambda x: expensive_func(x), axis=1)

   # Good:
   df['new_col'] = vectorized_func(df['col1'], df['col2'])
   ```

3. **Cache expensive lookups:**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=1000)
   def expensive_lookup(key):
       # Expensive database call or computation
       return result
   ```

---

## General Debugging Tips

### 1. Use Structured Logging
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "Processing domain",
    domain=domain,
    month=month,
    input_rows=len(df),
    step="column_mapping",
)
```

### 2. Create Debug Scripts
```python
# scripts/debug/domain_debug.py
def debug_domain(domain, month):
    # Load sample data
    # Run each pipeline step separately
    # Save intermediate results
    # Compare with legacy at each step
    pass
```

### 3. Use IDE Debuggers
- Set breakpoints in pipeline steps
- Inspect DataFrame state between transformations
- Watch variables during model validation

### 4. Document Intentional Differences
```markdown
## Intentional Differences from Legacy

| Difference | Reason | Impact |
|------------|--------|--------|
| ID5 fallback removed | Architecture alignment | Some records will have null company_id |
| Date format standardized | ISO 8601 compliance | Dates in YYYY-MM-DD format |
| Company name cleaning | Consistency across domains | Normalized company names |
```

---

## Getting Help

### When to Ask for Help
- Stuck on an issue for > 2 hours
- Architecture questions
- Database migration issues
- Performance problems

### Who to Ask
| Issue | Contact |
|-------|---------|
| Code implementation | Technical Lead or Senior Developer |
| Database issues | DBA Team |
| Infrastructure problems | DevOps Team |
| Validation failures | QA Team |

### How to Ask Effectively
1. **Describe the problem clearly**
   - What were you trying to do?
   - What happened instead?
   - What did you expect?

2. **Include relevant details**
   - Error messages (full stack trace)
   - Code snippet
   - Input/output examples
   - Environment details

3. **Show what you've tried**
   - List of attempted solutions
   - Results of debugging steps

4. **Provide minimal reproduction case**
   ```python
   # Smallest code that shows the issue
   def reproduce_issue():
       df = pd.DataFrame({...})
       result = problematic_function(df)
       return result
   ```

---

## Prevention Checklist

### Before Starting
- [ ] Read all migration guides
- [ ] Set up development environment
- [ ] Request access to legacy database
- [ ] Allocate adequate time (don't rush)

### During Migration
- [ ] Commit frequently with descriptive messages
- [ ] Document decisions and trade-offs
- [ ] Review progress daily
- [ ] Test with real data early

### Before Completion
- [ ] Peer review all code
- [ ] Run full test suite
- [ ] Validate with multiple data sets
- [ ] Document known limitations

---

## References

- [Domain Migration Workflow](./workflow.md)
- [Domain Development Guide](./development-guide.md)
- [Cleansing Rules Template](../../templates/cleansing-rules-template.md)
- [Legacy Parity Validation Guide](../../runbooks/legacy-parity-validation.md)

---

**End of Troubleshooting Guide**