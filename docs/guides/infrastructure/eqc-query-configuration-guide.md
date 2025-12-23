# EQC Query Configuration Guide

This guide documents how to properly configure EQC (Enterprise Query Center) queries in the New Pipeline for company ID resolution.

## Overview

EQC queries are used to resolve company names to canonical company IDs when:
1. The company is not found in YAML overrides
2. The company is not in the database cache (`enrichment_index`)
3. The source data doesn't have a valid existing company ID

## Configuration Parameters

### 1. Pipeline Level: `build_bronze_to_silver_pipeline()`

```python
from work_data_hub.domain.annuity_performance.pipeline_builder import (
    build_bronze_to_silver_pipeline,
)

pipeline = build_bronze_to_silver_pipeline(
    enrichment_service=None,           # Legacy, not required
    plan_override_mapping=mapping,      # YAML overrides
    sync_lookup_budget=1000,            # ← KEY: EQC API call budget
    mapping_repository=mapping_repo,    # ← KEY: Required for EQC
)
```

### 2. Strategy Level: `ResolutionStrategy`

```python
from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy

strategy = ResolutionStrategy(
    use_enrichment_service=True,   # ← Must be True to trigger EQC
    sync_lookup_budget=1000,       # ← Number of EQC API calls allowed
    generate_temp_ids=True,        # Generate temp IDs for unresolved
)
```

## Trigger Conditions

EQC queries are triggered **ONLY** when ALL conditions are met:

| Condition | Description |
|-----------|-------------|
| `strategy.use_enrichment_service = True` | EQC lookup enabled |
| `strategy.sync_lookup_budget > 0` | Budget available |
| `eqc_provider is not None` | EQC client initialized |
| `mask_missing.any()` | Unresolved records exist |

## Resolution Order

The resolver processes records in this priority order:

1. **YAML Overrides** - Plan code, account name, hardcode mappings
2. **Database Cache** - `enterprise.enrichment_index` table
3. **Existing Column** - Preserve valid numeric company IDs from source
4. **EQC Sync Lookup** - Real-time EQC API queries (budget-limited)
5. **Default Fallback** - `600866980` for empty customer names
6. **Temp ID Generation** - `INXXXX` for remaining unresolved

## EQC Provider Auto-Creation

When `mapping_repository` is provided, `CompanyIdResolver` automatically creates an `EqcProvider`:

```python
# In CompanyIdResolver.__init__:
if eqc_provider is None and mapping_repository is not None:
    self.eqc_provider = EqcProvider(
        token=settings.eqc_token,
        budget=settings.company_sync_lookup_limit,  # Default: 5
        mapping_repository=mapping_repository,
    )
```

## Cache Persistence

**CRITICAL:** Database writes must be committed explicitly!

```python
with engine.connect() as conn:
    mapping_repository = CompanyMappingRepository(conn)
    result = pipeline.execute(df, context)
    conn.commit()  # ← REQUIRED to persist EQC cache!
```

Without `conn.commit()`, all cached results are rolled back when the connection closes.

## CLI Usage

```bash
# Enable EQC enrichment with default budget (1000)
python guimo_iter_cleaner_compare.py --month 202412 --enrichment

# Custom budget
python guimo_iter_cleaner_compare.py --month 202412 --enrichment --sync-budget 5000
```

## Budget Recommendations

| Dataset Size | Recommended Budget |
|--------------|-------------------|
| < 1,000 rows | 100 |
| 1,000-10,000 | 1,000 |
| 10,000-50,000 | 5,000 |
| > 50,000 | 10,000+ |

> **Note:** Budget is consumed per **unique customer name**, not per row. Deduplication is automatic.

## Troubleshooting

### EQC Queries Not Triggering

1. **Check `use_enrichment_service`** - Must be `True`
2. **Check `sync_lookup_budget`** - Must be > 0
3. **Check `mapping_repository`** - Must be provided
4. **Check EQC token** - Must be valid (check `.wdh_env`)

### Cache Not Persisting

1. **Add `conn.commit()`** after pipeline execution
2. **Check for exceptions** in `_cache_result()`

### Token Expiration

EQC tokens expire periodically. Use auto-refresh:
```bash
uv run python -m work_data_hub.io.auth --capture --save
```

## Related Files

| File | Purpose |
|------|---------|
| `infrastructure/enrichment/company_id_resolver.py` | Resolution logic |
| `infrastructure/enrichment/eqc_provider.py` | EQC API client wrapper |
| `infrastructure/enrichment/mapping_repository.py` | Database cache operations |
| `io/connectors/eqc_client.py` | Low-level EQC API calls |
