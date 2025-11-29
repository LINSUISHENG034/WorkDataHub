# Annuity Performance Pipeline - Operational Runbook

> **Story 4.6** - Operational guide for executing and troubleshooting the annuity performance pipeline

## Quick Reference

| Item | Value |
|------|-------|
| **Pipeline Name** | `annuity_performance_job` |
| **Domain** | `annuity_performance` |
| **Output Table** | `annuity_performance_new` |
| **Config File** | `config/data_sources.yml` |
| **Dagster Port** | `3000` (default) |

## Manual Execution

### Via Dagster UI (Recommended)

1. **Start Dagster development server:**
   ```bash
   cd E:\Projects\WorkDataHub
   uv run dagster dev
   ```

2. **Open Dagster UI:**
   - Navigate to http://localhost:3000

3. **Execute the pipeline:**
   - Select **"annuity_performance_job"** from the jobs list
   - Click **"Launchpad"**
   - Configure run parameters:
     ```yaml
     ops:
       load_annuity_data:
         config:
           month: "202411"  # Target month in YYYYMM format
     ```
   - Click **"Launch Run"**

4. **Monitor execution:**
   - Watch the run progress in the Runs tab
   - Check logs for any warnings or errors

### Via CLI

```bash
# Navigate to project root
cd E:\Projects\WorkDataHub

# Execute with specific month
uv run dagster job execute -j annuity_performance_job \
  --config '{"ops": {"load_annuity_data": {"config": {"month": "202411"}}}}'

# Or using a config file
uv run dagster job execute -j annuity_performance_job \
  --config-yaml run_config.yaml
```

### Via Python Script

```python
from work_data_hub.pipelines.annuity import run_annuity_pipeline

# Execute for specific month
result = run_annuity_pipeline(month="202411")

# Check result
if result.success:
    print(f"Processed {result.records_loaded} records")
else:
    print(f"Pipeline failed: {result.error}")
```

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `DiscoveryError: No files found matching pattern` | File missing or wrong path | 1. Verify folder exists: `reference/monthly/{YYYYMM}/收集数据/数据采集/`<br>2. Check version folders (V1, V2, etc.) exist<br>3. Verify file matches pattern `*年金终稿*.xlsx` |
| `DiscoveryError: Multiple version folders found` | Ambiguous version selection | 1. Check `version_strategy` in config<br>2. Remove duplicate version folders<br>3. Set `fallback: "use_latest_modified"` if acceptable |
| `SchemaError: Missing required column '计划代码'` | Excel structure changed | 1. Open Excel file and verify column names<br>2. Check sheet name is `规模明细`<br>3. Update Bronze schema if columns renamed |
| `ValidationError: company_id cannot be empty` | Company enrichment failed | 1. Check `WDH_ALIAS_SALT` environment variable is set<br>2. Verify company name is not empty in source data<br>3. Check Epic 5 enrichment service status |
| `IntegrityError: duplicate key value violates unique constraint` | Duplicate composite PK | 1. Check for duplicate rows in source Excel<br>2. Run verification query (see below)<br>3. Clean source data or adjust deduplication logic |
| `ConnectionError: could not connect to server` | Database unavailable | 1. Verify `DATABASE_URL` environment variable<br>2. Check PostgreSQL service is running<br>3. Test connection: `psql $DATABASE_URL -c "SELECT 1"` |
| `ValidationError: starting_assets must be >= 0` | Negative asset value in source | 1. Check source Excel for negative values<br>2. Verify data entry is correct<br>3. If valid, update CHECK constraint |
| `DateParseError: Cannot parse date '202413'` | Invalid month value | 1. Check source data for invalid dates<br>2. Verify month is 01-12<br>3. Check for data entry errors |
| `FileNotFoundError: Sheet '规模明细' not found` | Wrong sheet name | 1. Open Excel and verify sheet name<br>2. Update `sheet_name` in config if changed<br>3. Check for hidden sheets |
| `PermissionError: Access denied to file` | File locked by Excel | 1. Close Excel if file is open<br>2. Check file permissions<br>3. Remove `~$` temp files |

## Verification Queries

### Check Row Count

```sql
-- Count records for specific month
SELECT COUNT(*) as record_count
FROM annuity_performance_new
WHERE reporting_month = '2024-11-01';

-- Expected: Should match row count in source Excel (minus header)
```

### Check for Temporary IDs (Enrichment Gaps)

```sql
-- Count records with temporary company IDs
SELECT COUNT(*) as temp_id_count
FROM annuity_performance_new
WHERE company_id LIKE 'IN_%';

-- If count > 0, these need Epic 5 enrichment resolution
```

### Verify Composite PK Uniqueness

```sql
-- Find any duplicate primary keys (should return 0 rows)
SELECT reporting_month, plan_code, company_id, COUNT(*) as duplicate_count
FROM annuity_performance_new
GROUP BY reporting_month, plan_code, company_id
HAVING COUNT(*) > 1;
```

### Check Data Quality

```sql
-- Summary statistics for financial metrics
SELECT
    reporting_month,
    COUNT(*) as record_count,
    SUM(starting_assets) as total_starting_assets,
    SUM(ending_assets) as total_ending_assets,
    AVG(annualized_return_rate) as avg_return_rate
FROM annuity_performance_new
WHERE reporting_month = '2024-11-01'
GROUP BY reporting_month;
```

### Check Pipeline Run History

```sql
-- Recent pipeline runs
SELECT
    pipeline_run_id,
    COUNT(*) as records_loaded,
    MIN(created_at) as run_start,
    MAX(created_at) as run_end
FROM annuity_performance_new
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY pipeline_run_id
ORDER BY run_start DESC;
```

### Compare with Previous Month

```sql
-- Month-over-month comparison
SELECT
    reporting_month,
    COUNT(*) as record_count,
    SUM(ending_assets) as total_assets
FROM annuity_performance_new
WHERE reporting_month IN ('2024-10-01', '2024-11-01')
GROUP BY reporting_month
ORDER BY reporting_month;
```

## Rollback Procedure

### Scenario 1: Bad Data Loaded

If incorrect data was loaded for a specific month:

```sql
-- 1. Identify the pipeline run
SELECT DISTINCT pipeline_run_id, created_at
FROM annuity_performance_new
WHERE reporting_month = '2024-11-01'
ORDER BY created_at DESC;

-- 2. Delete records from the bad run
DELETE FROM annuity_performance_new
WHERE pipeline_run_id = '<bad_run_id>';

-- 3. Verify deletion
SELECT COUNT(*) FROM annuity_performance_new
WHERE reporting_month = '2024-11-01';
```

### Scenario 2: Revert Database Migration

If the migration needs to be reverted:

```bash
# Navigate to project root
cd E:\Projects\WorkDataHub

# Downgrade one revision
uv run alembic downgrade -1

# Verify current revision
uv run alembic current
```

### Scenario 3: Re-run Pipeline for Specific Month

```bash
# 1. Delete existing data for the month
psql $DATABASE_URL -c "DELETE FROM annuity_performance_new WHERE reporting_month = '2024-11-01';"

# 2. Re-run pipeline
uv run dagster job execute -j annuity_performance_job \
  --config '{"ops": {"load_annuity_data": {"config": {"month": "202411"}}}}'
```

## Health Checks

### Pre-Execution Checklist

- [ ] Source file exists in expected location
- [ ] Database connection is working
- [ ] Environment variables are set (`DATABASE_URL`, `WDH_ALIAS_SALT`)
- [ ] No Excel temp files (`~$*`) in source folder
- [ ] Dagster service is running (if using UI)

### Post-Execution Checklist

- [ ] Pipeline completed without errors
- [ ] Record count matches source Excel
- [ ] No duplicate primary keys
- [ ] Financial totals are reasonable
- [ ] Temporary ID count is acceptable

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Pipeline Success Rate:** Should be 100% for production runs
2. **Record Count:** Should be consistent month-over-month (±10%)
3. **Temporary ID Ratio:** Should decrease as Epic 5 enrichment improves
4. **Processing Time:** Should be <5 minutes for typical monthly data

### Log Locations

| Log Type | Location |
|----------|----------|
| Dagster Logs | Dagster UI → Runs → Select Run → Logs |
| Application Logs | `logs/work_data_hub.log` |
| Database Logs | PostgreSQL server logs |

## Contact and Escalation

| Issue Type | Contact |
|------------|---------|
| Pipeline Failures | Data Engineering Team |
| Data Quality Issues | Data Steward |
| Database Issues | DBA Team |
| Configuration Changes | Platform Team |

## Appendix: Configuration Reference

### Full Configuration Example

```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/数据采集"
    file_patterns:
      - "*年金终稿*.xlsx"
    exclude_patterns:
      - "~$*"         # Excel temp files
      - "*回复*"      # Email reply files
      - "*.eml"       # Email message files
    sheet_name: "规模明细"
    version_strategy: "highest_number"
    fallback: "error"
```

### Environment Variables

```bash
# Required
export DATABASE_URL="postgresql://user:pass@localhost:5432/workdatahub"
export WDH_ALIAS_SALT="your-secret-salt-for-hmac"

# Optional
export WDH_LOG_LEVEL="INFO"
export WDH_ENV="production"
```
