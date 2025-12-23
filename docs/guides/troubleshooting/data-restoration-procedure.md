# Data Restoration Procedure

**Document Version:** 1.0  
**Last Updated:** 2025-12-23  
**Author:** Story 7.1-1 Implementation  
**Security Level:** ⚠️ CRITICAL - Production Data Protection  

---

## Purpose

This document provides step-by-step procedures to detect and restore data loss in the `enrichment_index` and `base_info` tables. These tables are critical to the WorkDataHub ETL pipeline and must be protected at all times.

---

## Detection

### Check `enrichment_index` Table

```sql
-- Check row count
SELECT COUNT(*) AS total_rows FROM enterprise.enrichment_index;

-- Check data distribution by lookup_type
SELECT lookup_type, COUNT(*) AS count  
FROM enterprise.enrichment_index  
GROUP BY lookup_type  
ORDER BY count DESC;

-- Check recent activity
SELECT MAX(created_at) AS last_created, MAX(updated_at) AS last_updated  
FROM enterprise.enrichment_index;
```

**Expected Values:**
- `total_rows`: Typically \u003e 1000 entries (depends on your usage)
- `lookup_type` distribution should show multiple types: `plan_code`, `customer_name`, `account_name`, etc.
- `last_created`/`last_updated`: Should be recent timestamps

**Warning Signs:**
- Row count = 0 or significantly lower than expected
- Only a few lookup_types present
- Very old timestamps (no recent updates)

### Check `base_info` Table

```sql
-- Check row count
SELECT COUNT(*) AS total_rows FROM enterprise.base_info;

-- Check data freshness
SELECT MAX(api_fetched_at) AS last_fetch, MAX(updated_at) AS last_update  
FROM enterprise.base_info;

-- Sample company_id distribution
SELECT company_id, companyFullName  
FROM enterprise.base_info  
LIMIT 10;
```

**Expected Values:**
- `total_rows`: Typically \u003e 500 companies (depends on your portfolio)
- `last_fetch`: Should align with recent EQC API calls
- `company_id`: Should contain real company IDs (not just `IN_*` temp IDs)

**Warning Signs:**
- Row count = 0 or significantly reduced
- No recent `api_fetched_at` timestamps
- All `company_id` values are temp IDs (`IN_*`)

---

## Prevention

**Story 7.1-1** (this story) implemented the following protections:

### 1. Database Name Validation (`_validate_test_database()`)

All test fixtures and migration operations now validate the database name before performing destructive operations like `downgrade()`.

**Protected Operations:**
- `tests/conftest.py`: `postgres_db_with_migrations()` fixture
- All migration test files (enrichment_index, enterprise_schema, reference_tracking_fields)
- `scripts/temp/db_setup.py`: Database setup script

**Validation Rules:**
- Database name MUST contain one of: `test`, `tmp`, `dev`, `local`, `sandbox`
- Validation is case-insensitive
- Production database names (e.g., `work_data_hub`) will raise `RuntimeError`

**Override Mechanism (USE WITH EXTREME CAUTION):**
```bash
export WDH_SKIP_DB_VALIDATION=1  # DANGEROUS - Only use in controlled dev environments
```

### 2. Auto-load `.wdh_env` Configuration

`tests/conftest.py` now automatically loads `.wdh_env` at the top of the file, ensuring:
- `DATABASE_URL` points to the test database
- All environment variables are correctly loaded before test execution

---

## Restoration

### Option 1: Restore from Existing Scripts (**RECOMMENDED**)

The project already has restoration scripts in `scripts/migrations/enrichment_index/`.

#### Step 1: Restore Data from Legacy Source

```bash
uv run --env-file .wdh_env python scripts/migrations/enrichment_index/restore_enrichment_index.py
```

**What this does:**
- Reads legacy MySQL database (`legacy` schema)
- Extracts existing company enrichment mappings
- Repopulates `enrichment_index` table

**Reference:** `scripts/migrations/enrichment_index/README.md`

#### Step 2: Clean Up Invalid Data

```bash
uv run --env-file .wdh_env python scripts/migrations/enrichment_index/cleanup_enrichment_index.py
```

**What this does:**
- Removes invalid entries (e.g., `company_id='N'` or `company_id='IN%'`)
- Removes duplicate/low-confidence mappings
- Ensures data quality

### Option 2: Re-run EQC API Calls (If Option 1 Unavailable)

If legacy database is not available, rebuild enrichment_index by re-processing domain data:

```bash
# Re-run enrichment for annuity_performance domain
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domain annuity_performance \
  --execute \
  --period 2025-12

# Re-run for annuity_income domain  
uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
  --domain annuity_income \
  --execute \
  --period 2025-12
```

**Notes:**
- This will trigger EQC API calls for unresolved companies
- May consume EQC API budget
- Use `--dry-run` first to preview impact

### Option 3: Restore from Database Backup (If Available)

If you have database backups:

```bash
# PostgreSQL backup restoration (example)
pg_restore -d work_data_hub -t enterprise.enrichment_index backup_file.dump
pg_restore -d work_data_hub -t enterprise.base_info backup_file.dump
```

---

## Verification Checklist

After restoration, verify data integrity:

- [ ] **Row Counts Match Expected Values**
  - `enrichment_index`: Row count \u003e baseline (check historical trends)
  - `base_info`: Row count \u003e baseline

- [ ] **Lookup Type Distribution is Correct**
  ```sql
  SELECT lookup_type, COUNT(*) FROM enterprise.enrichment_index GROUP BY lookup_type;
  ```
  - Should show `plan_code`, `customer_name`, `account_name`, `account_number`

- [ ] **Data Freshness is Recent**
  ```sql
  SELECT MAX(created_at) FROM enterprise.enrichment_index;
  SELECT MAX(api_fetched_at) FROM enterprise.base_info;
  ```
  - Timestamps should reflect recent activity

- [ ] **No Invalid company_id Values**
  ```sql
  SELECT company_id, COUNT(*) FROM enterprise.enrichment_index  
  WHERE company_id IN ('N', 'IN') OR company_id IS NULL  
  GROUP BY company_id;
  ```
  - Should return 0 rows

- [ ] **ETL Pipeline Runs Successfully**
  ```bash
  uv run --env-file .wdh_env python -m work_data_hub.cli.etl \
    --domain annuity_performance --dry-run --period 2025-12
  ```
  - Should complete without errors

- [ ] **Cross-Reference with Source Data**
  - Compare enrichment_index entries with `config/company_mapping.yml`
  - Verify key companies are present in `base_info`

---

## Root Cause Analysis

**Reference:** `docs/sprint-artifacts/reviews/7.1-1-data-clearing-investigation.md`

**Primary Risk Area:** Local development environment where `.wdh_env` may not be loaded correctly, causing tests to connect to production database.

**CI/CD Safety:** GitHub Actions CI/CD is confirmed **SAFE** - uses isolated `testdb` Docker container.

**Prevention Measures (Story 7.1-1):**
1. Database name validation before destructive operations
2. Auto-load `.wdh_env` configuration in test fixtures
3. Comprehensive unit tests for validation logic

---

## Emergency Contacts

If you encounter data loss that cannot be resolved using this procedure:

1. **Do NOT re-run tests** - this may cause further data loss
2. **Check database backups** - restore from the most recent backup
3. **Review test execution logs** - identify which test triggered the issue
4. **Verify `.wdh_env` configuration** - ensure `DATABASE_URL` points to test database
5. **Contact the development team** for assistance

---

## Related Documentation

- [Investigation Report](../sprint-artifacts/reviews/7.1-1-data-clearing-investigation.md)
- [Database Schema Panorama](../database-schema-panorama.md)
- [Restoration Scripts README](../../scripts/migrations/enrichment_index/README.md)
- [Project Context](../project-context.md)

---

**⚠️ CRITICAL REMINDER:** Always verify `DATABASE_URL` in `.wdh_env` points to a test database before running any tests or migrations!
