# Deprecation Notice: `enterprise.company_master` Table

**Status:** REMOVED
**Deprecation Date:** 2025-12-14
**Removal Date:** 2025-12-15
**Story:** 6.2-P7 - Enterprise Schema Consolidation
**Replacement:** `enterprise.base_info` (Legacy table)

## Summary

The `enterprise.company_master` table has been **removed** from the migration files as of Story 6.2-P7. The table definition no longer exists in the codebase. All new development should use the `enterprise.base_info` table, which provides a complete schema aligned with the Legacy system's archive_base_info (37+ columns).

## Background

During Epic 6 (Company Enrichment Service), we created the `enterprise.company_master` table as part of Story 6.1 to store canonical company records. However, during Story 6.2-P5 implementation, we discovered that:

1. **Legacy table exists**: The `enterprise.base_info` table already exists in the legacy database with a well-established schema
2. **Overlapping purpose**: Both tables serve the same purpose (storing company master data)
3. **Minimal data**: `company_master` contains minimal test data only
4. **Integration priority**: Consolidating to `base_info` simplifies legacy system integration

## Migration Path

### Current State (2025-12-15)

- `company_master` table has been **removed** from migration files (Story 6.2-P7)
- The table may still exist in databases that applied the migration before removal
- No production code actively writes to `company_master`
- `base_info` table is the active persistence target for EQC data
- New databases (fresh installs) will not have `company_master` table

### Recommended Actions

**For New Development:**
- ✅ Use `enterprise.base_info` for all company master data
- ❌ Do NOT write to `enterprise.company_master`
- ✅ Use `enterprise.enrichment_index` for lookup caching (Story 6.1.1)

**For Existing Code:**
- Review any references to `company_master` in your code
- Update to use `base_info` or `enrichment_index` as appropriate
- **Important**: The table no longer exists in migration files - ensure your code doesn't depend on it
- For databases with existing `company_master` tables, consider a manual cleanup operation

### Table Comparison

| Feature | `company_master` (Removed) | `base_info` (Active) |
|---------|----------------------------|----------------------|
| Purpose | Was canonical company records | Legacy company master data |
| Schema | Was minimal (6 columns) | Rich (37+ columns from archive_base_info) |
| Data Source | EQC API (planned) | EQC API + Legacy system |
| Raw Data | Not supported | JSONB columns: raw_data, raw_business_info, raw_biz_label |
| Status | Removed from migrations | Active |
| Migration Status | Removed in 6.2-P7 | Created/Updated in 6.2-P7 |

## Technical Details

### Schema Differences

**`company_master` (Removed):**
```sql
-- This table has been removed from migration files
-- Previously existed with minimal schema (6 columns)
-- No longer created in new database installations
```

**`base_info` (Active - Expanded in 6.2-P7):**
```sql
CREATE TABLE enterprise.base_info (
    company_id VARCHAR(255) PRIMARY KEY,
    search_key_word VARCHAR(255),
    -- Legacy archive_base_info alignment (37 columns)
    name, name_display, symbol, rank_score, country,
    company_en_name, smdb_code, is_hk, coname, is_list,
    company_nature, _score, type, "registeredStatus",
    organization_code, le_rep, reg_cap, is_pa_relatedparty,
    province, "companyFullName", est_date, company_short_name,
    id, is_debt, unite_code, registered_status, cocode,
    default_score, company_former_name, is_rank_list,
    trade_register_code, "companyId", is_normal, company_full_name,
    -- Raw API response storage (Story 6.2-P5/6.2-P7)
    raw_data JSONB,                    -- search response
    raw_business_info JSONB,           -- findDepart response
    raw_biz_label JSONB,               -- findLabels response
    api_fetched_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Code References

The following code components reference `company_master`:

**Documentation:**
- `docs/epics/epic-6-company-enrichment-service.md` - Historical reference
- `docs/prd/functional-requirements.md` - Original design
- `docs/brownfield-architecture.md` - Architecture diagram

**Code:**
- `src/work_data_hub/infrastructure/enrichment/types.py` - Comment reference

**Migration Files:**
- `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` - Table REMOVED (6.2-P7)

## Timeline

- **2025-11-29**: `company_master` table created (Story 6.1)
- **2025-12-14**: Table deprecated in favor of `base_info` (Story 6.2-P5)
- **2025-12-15**: Table removed from migration files (Story 6.2-P7)
- **Note**: Existing databases may still have the table; new databases will not

## Questions?

For questions about this deprecation, refer to:
- Story 6.2-P5: `docs/sprint-artifacts/stories/6.2-p5-eqc-data-persistence-legacy-integration.md`
- PM Review: `docs/sprint-artifacts/reviews/pm-review-eqc-data-persistence-2025-12-14.md`
- Sprint Change Proposal: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-data-persistence.md`

## See Also

- [Enterprise Schema Overview](../architecture/architectural-decisions.md)
- [Epic 6: Company Enrichment Service](../epics/epic-6-company-enrichment-service.md)
- [Legacy Database Integration](../brownfield-architecture.md)
