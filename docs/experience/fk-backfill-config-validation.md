# FK Backfill Configuration Validation Experience

**Date:** 2026-02-11
**Story:** 7.6-17 (FK Backfill for Annual Award/Loss)
**Author:** Code Review Agent

## Issue Summary

During code review of Story 7.6-17, a configuration error was discovered where the FK backfill `source` column name did not match the actual database table column name.

| Config Value | Actual Column | Impact |
|--------------|---------------|--------|
| `客户全称` | `客户名称` | FK backfill silently skipped |

## Root Cause

The Sprint Change Proposal referenced source table schemas from business documents, but the actual ETL pipeline transforms column names during processing. The final table schema differs from the raw source data.

## Lesson Learned

### Before Adding FK Backfill Config

1. **Verify actual table schema** - Query `information_schema.columns` to confirm column names:
   ```sql
   SELECT column_name
   FROM information_schema.columns
   WHERE table_schema = 'customer' AND table_name = '当年中标'
   ORDER BY ordinal_position;
   ```

2. **Check pipeline transformations** - Review domain pipeline to understand column renaming/mapping.

3. **Test with real data** - Run ETL with `--execute` flag and verify:
   - `Reference Backfill Summary: Operations > 0` (if missing records exist)
   - Query database to confirm records were inserted

### Validation Query Template

```sql
-- Check for missing FK records
SELECT COUNT(DISTINCT a.company_id)
FROM customer."当年流失" a
LEFT JOIN customer."年金客户" c ON a.company_id = c.company_id
WHERE c.company_id IS NULL;
```

## Prevention Checklist

- [ ] Query actual table schema before writing FK config
- [ ] Cross-reference with domain pipeline column mappings
- [ ] Run ETL with real data to verify backfill operations
- [ ] Check database for expected record insertions

## Related Files

- `config/foreign_keys.yml` - FK backfill configuration
- `config/data_sources.yml` - Domain configuration with `requires_backfill` flag
