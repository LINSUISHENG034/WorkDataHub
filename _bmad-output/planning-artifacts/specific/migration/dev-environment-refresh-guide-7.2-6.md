# Development Environment Refresh Guide

**Story**: 7.2-6
**Date**: 2025-12-28
**Epic**: 7.2 - Alembic Migration Refactoring

## Overview

This guide explains how to refresh your development database using the new clean Alembic migration chain (001 → 002 → 003). This is required after Epic 7.2 migration refactoring.

## Prerequisites

- PostgreSQL running locally on port 5432
- `.wdh_env` file configured with correct database connection
- `uv` package manager installed
- Database user with CREATE SCHEMA privileges

## Migration Chain Summary

```
base (empty database)
  ↓
001_initial_infrastructure.py (17 tables)
  ↓
002_initial_domains.py (4 domain tables)
  ↓
003_seed_static_data.py (~45,603 rows seed data)
  ↓
HEAD (current state)
```

## Step-by-Step Refresh Process

### Phase 1: Backup Current Data (Optional but Recommended)

```bash
# Backup critical cache table (32K rows)
PGPASSWORD=Post.169828 pg_dump -h localhost -U postgres -d postgres \
  -t enterprise.enrichment_index -f backup_enrichment_index_$(date +%Y%m%d).sql
```

### Phase 2: Drop Existing Schemas

```bash
PGPASSWORD=Post.169828 psql -h localhost -U postgres -d postgres << 'EOF'
DROP SCHEMA IF EXISTS public CASCADE;
DROP SCHEMA IF EXISTS business CASCADE;
DROP SCHEMA IF EXISTS enterprise CASCADE;
DROP SCHEMA IF EXISTS mapping CASCADE;
DROP SCHEMA IF EXISTS system CASCADE;
CREATE SCHEMA public;
EOF
```

**Expected Output**: Should show CASCADE messages dropping all business tables.

### Phase 3: Run New Migration Chain

```bash
# Stamp initial version
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic stamp base

# Run full upgrade
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic upgrade head
```

**Expected Output**:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 20251228_000001, Initial infrastructure tables for clean migration chain.
INFO  [alembic.runtime.migration] Running upgrade 20251228_000001 -> 20251228_000002, Initial domain tables using Domain Registry definitions.
INFO  [alembic.runtime.migration] Running upgrade 20251228_000002 -> 20251228_000003, Seed static reference data from CSV files.
Seeded 1183 rows into enterprise.industrial_classification
Seeded 12 rows into mapping.产品线
... (more seed data messages)
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

### Phase 4: Verify Migration Success

#### 4.1 Check Alembic Version

```bash
PGPASSWORD=Post.169828 psql -h localhost -U postgres -d postgres -c "SELECT * FROM public.alembic_version;"
```

**Expected Output**:

```
   version_num
-----------------
 20251228_000003
```

#### 4.2 Verify Table Count

```sql
SELECT schemaname, COUNT(*) FROM pg_tables
WHERE schemaname IN ('public', 'business', 'enterprise', 'mapping', 'system')
GROUP BY schemaname
ORDER BY schemaname;
```

**Expected Output**:

```
 schemaname | count
------------+-------
 business   |     2
 enterprise |     7
 mapping    |     8
 public     |     4
 system     |     1
```

**Total: 22 tables**

#### 4.3 Verify Seed Data Row Counts

```sql
-- Enterprise schema
SELECT 'industrial_classification' as table_name, COUNT(*) FROM enterprise.industrial_classification
UNION ALL
SELECT 'enrichment_index', COUNT(*) FROM enterprise.enrichment_index;

-- Mapping schema (small)
SELECT '产品线', COUNT(*) FROM mapping.产品线
UNION ALL
SELECT '组织架构', COUNT(*) FROM mapping.组织架构
UNION ALL
SELECT '计划层规模', COUNT(*) FROM mapping.计划层规模;

-- Mapping schema (large)
SELECT '年金客户', COUNT(*) FROM mapping.年金客户
UNION ALL
SELECT '年金计划', COUNT(*) FROM mapping.年金计划
UNION ALL
SELECT '组合计划', COUNT(*) FROM mapping.组合计划;
```

**Expected Output**:

```
        table_name         | count
----------------------------+-------
 industrial_classification   |  1183
 enrichment_index            | 32052
 产品线                      |    12
 组织架构                    |    38
 计划层规模                  |     7
 年金客户                    |  9813
 年金计划                    |  1142
 组合计划                    |  1324
```

#### 4.4 Verify Primary Keys

```sql
SELECT table_schema, table_name, column_name
FROM information_schema.key_column_usage
WHERE table_schema IN ('business', 'mapping')
  AND column_name LIKE '%id%'
ORDER BY table_schema, table_name;
```

**Expected**: All domain tables should show `id` as primary key.

## Troubleshooting

### Issue 1: Database Connection Failed

**Symptoms**: `connection refused` or `password authentication failed`

**Solution**:

1. Verify PostgreSQL is running: `psql -h localhost -U postgres -d postgres -c "SELECT 1;"`
2. Check password in `.wdh_env`: `WDH_DATABASE__URI=postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres`
3. Verify database exists: `psql -h localhost -U postgres -d postgres -c "\l"`

### Issue 2: Permission Denied on CREATE SCHEMA

**Symptoms**: `permission denied to create schema`

**Solution**: Grant CREATE privileges to your user:

```sql
GRANT CREATE ON DATABASE postgres TO your_user;
GRANT ALL ON SCHEMA public TO your_user;
```

### Issue 3: Alembic "Table Already Exists"

**Symptoms**: `relation "xxx" already exists`

**Solution**: Drop all schemas and start fresh (see Phase 2).

### Issue 4: Seed Data Fails to Load

**Symptoms**: `relation "company_types_classification" does not exist`

**Status**: ✅ FIXED in Code Review 2025-12-28

The `company_types_classification` table schema bug (missing `schema="enterprise"` parameter) has been fixed in migration 001. If you previously ran migrations before this fix, apply it with:

```bash
# Re-run migration to apply fix
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic downgrade 20251228_000002
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic upgrade 20251228_000003
```

## What Other Developers Need to Do

If you're joining the project after Epic 7.2 migration refactoring:

1. **Pull latest code**:

   ```bash
   git pull origin main
   ```

2. **Refresh your development database** following this guide.

3. **Update your `.wdh_env`** (if needed):

   ```bash
   # Database Setup
   # 1. Create database
   # 2. Run: alembic upgrade head
   # 3. Verify: \dt *.* shows 22 tables
   ```

4. **Run tests to verify**:
   ```bash
   PYTHONPATH=src uv run --env-file .wdh_env pytest tests/io/schema/test_migrations.py -v
   ```

## Migration Rollback (Not Recommended)

⚠️ **WARNING**: Downgrade operations are DESTRUCTIVE.

```bash
# Downgrade one step (deletes seed data)
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic downgrade -1

# Downgrade to base (deletes all tables)
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic downgrade base
```

**Expected Behavior**:

- `003 → 002`: TRUNCATE all seed data (~45K rows)
- `002 → 001`: DROP CASCADE domain tables (business schema)
- `001 → base`: DROP CASCADE all infrastructure tables

## References

- **Story File**: `docs/sprint-artifacts/stories/7.2-6-dev-environment-refresh.md`
- **Sprint Change Proposal**: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-27-migration-refactoring.md`
- **Migration Files**: `io/schema/migrations/versions/`
  - `001_initial_infrastructure.py`
  - `002_initial_domains.py`
  - `003_seed_static_data.py`
- **Cross-Validation Report**: `docs/specific/migration/cross-validation-report-7.2-5-2025-12-28.md`

## Next Steps After Refresh

After completing the database refresh:

1. ✅ Verify all 22 tables are created
2. ✅ Verify seed data is loaded (~45K rows)
3. ✅ Run migration tests: `pytest tests/io/schema/test_migrations.py -v`
4. ✅ Run domain registry tests: `pytest tests/io/schema/test_domain_registry.py -v`
5. 📝 Report any issues discovered during verification

Your development environment is now ready for Epic 8 development!
