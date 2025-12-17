# Known Issues and Investigation Notes

## Issue: New Pipeline Returns Temporary IDs While Legacy Has Numeric IDs

**Date:** 2025-12-17  
**Status:** Under Investigation

### Symptoms

When running the comparison script, the New Pipeline returns temporary IDs (e.g., `IN_GC4EC354W4N7FQHG`) while the Legacy cleaner successfully resolves numeric company IDs (e.g., `718967745`).

```
Legacy company_id: [718967745, 1856124762, 696130391, 695835707, ...]
New company_id:    [IN_2CMLXGCTFVPUVYRD, IN_GC4EC354W4N7FQHG, ...]
```

### Classification

All differences are classified as `regression_missing_resolution`:
- Legacy: Valid numeric company_id
- New Pipeline: Temporary ID (IN_xxx)

### Root Cause Analysis

#### Hypothesis 1: enrichment_index Table Missing Data

The New Pipeline uses the `enrichment_index` table for database cache lookup. If this table is empty or missing the required mappings, the resolution falls through to temporary ID generation.

**Verification Query:**
```sql
SELECT lookup_type, lookup_key, company_id 
FROM enrichment_index 
WHERE lookup_key IN ('Z0006', 'Z0014', 'Z0002', 'Z0135', 'Z0215', 'Z0001')
ORDER BY lookup_type, lookup_key;
```

#### Hypothesis 2: Legacy Uses Different Lookup Strategy

The Legacy `AnnuityPerformanceCleaner` may use a different database or lookup mechanism that is not replicated in the New Pipeline.

**Investigation Steps:**
1. Review `legacy/annuity_hub/data_handler/data_cleaner.py` for `_update_company_id()` logic
2. Identify the database/table used by Legacy
3. Compare with New Pipeline's `CompanyIdResolver`

#### Hypothesis 3: Database Connection Issues

The `.wdh_env` environment file may not be properly loaded, or the database credentials may be incorrect.

**Verification:**
```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python -c "
from work_data_hub.infrastructure.database.connection import get_engine
from work_data_hub.infrastructure.enrichment.mapping_repository import CompanyMappingRepository
engine = get_engine()
repo = CompanyMappingRepository(engine)
print('Connection successful')
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM enrichment_index'))
    print(f'enrichment_index rows: {result.scalar()}')
"
```

### Recommended Actions

1. **Populate enrichment_index**: Migrate mappings from Legacy database
2. **Review Legacy Logic**: Document the exact lookup strategy used by Legacy
3. **Add YAML Overrides**: For critical plan codes, add to `company_id_overrides_plan.yml`

### Technical Details

#### New Pipeline Resolution Path

```
CompanyIdResolver.resolve_batch()
  └─> Step 1: YAML overrides (yaml_hits=0)
  └─> Step 2: Database cache (db_cache_hits=0)
  └─> Step 3: Existing column passthrough (hits=0)
  └─> Step 4: EQC sync lookup (budget=50, hits=0)
  └─> Step 5: Temp ID generation (all rows)
```

#### Files Involved

- `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
- `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`
- `legacy/annuity_hub/data_handler/data_cleaner.py`

### Related Documents

- Implementation Plan: `scripts/validation/CLI/annuity-performance-cleaner-comparison-plan.md`
- Usage Guide: `scripts/validation/CLI/plan/usage-guide.md`
