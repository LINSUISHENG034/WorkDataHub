# Deprecation Notice: `enterprise.company_master` Table

**Status:** DEPRECATED
**Deprecation Date:** 2025-12-14
**Story:** 6.2-P5 - EQC Data Persistence & Legacy Table Integration
**Replacement:** `enterprise.base_info` (Legacy table)

## Summary

The `enterprise.company_master` table is **deprecated** and should not be used for new development. All EQC API data persistence now uses the `enterprise.base_info` table, which is the established legacy table structure.

## Background

During Epic 6 (Company Enrichment Service), we created the `enterprise.company_master` table as part of Story 6.1 to store canonical company records. However, during Story 6.2-P5 implementation, we discovered that:

1. **Legacy table exists**: The `enterprise.base_info` table already exists in the legacy database with a well-established schema
2. **Overlapping purpose**: Both tables serve the same purpose (storing company master data)
3. **Minimal data**: `company_master` contains minimal test data only
4. **Integration priority**: Consolidating to `base_info` simplifies legacy system integration

## Migration Path

### Current State (2025-12-14)

- `company_master` table exists but contains minimal data (test records only)
- No production code actively writes to `company_master`
- `base_info` table is the active persistence target for EQC data

### Recommended Actions

**For New Development:**
- ✅ Use `enterprise.base_info` for all company master data
- ❌ Do NOT write to `enterprise.company_master`
- ✅ Use `enterprise.enrichment_index` for lookup caching (Story 6.1.1)

**For Existing Code:**
- Review any references to `company_master` in your code
- Update to use `base_info` or `enrichment_index` as appropriate
- No immediate action required - table will remain for backward compatibility

### Table Comparison

| Feature | `company_master` (Deprecated) | `base_info` (Active) |
|---------|------------------------------|----------------------|
| Purpose | Canonical company records | Legacy company master data |
| Schema | Minimal (company_id, official_name, unified_credit_code, aliases) | Rich (40+ fields from legacy system) |
| Data Source | EQC API (planned) | EQC API + Legacy system |
| Raw Data | Not supported | JSONB column (Story 6.2-P5) |
| Status | Deprecated | Active |

## Technical Details

### Schema Differences

**`company_master` (Deprecated):**
```sql
CREATE TABLE enterprise.company_master (
    company_id VARCHAR(100) PRIMARY KEY,
    official_name VARCHAR(255) NOT NULL,
    unified_credit_code VARCHAR(50) UNIQUE,
    aliases TEXT[],
    source VARCHAR(50) DEFAULT 'internal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**`base_info` (Active):**
```sql
CREATE TABLE enterprise.base_info (
    company_id VARCHAR(255) PRIMARY KEY,
    search_key_word VARCHAR(255),
    companyFullName VARCHAR(255),
    unite_code VARCHAR(255),
    -- ... 40+ additional fields from legacy system
    raw_data JSONB,  -- Added in Story 6.2-P5
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
- `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` - Table creation

## Timeline

- **2025-11-29**: `company_master` table created (Story 6.1)
- **2025-12-14**: Table deprecated in favor of `base_info` (Story 6.2-P5)
- **Future**: Table may be dropped in a future cleanup story (no timeline set)

## Questions?

For questions about this deprecation, refer to:
- Story 6.2-P5: `docs/sprint-artifacts/stories/6.2-p5-eqc-data-persistence-legacy-integration.md`
- PM Review: `docs/sprint-artifacts/reviews/pm-review-eqc-data-persistence-2025-12-14.md`
- Sprint Change Proposal: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-data-persistence.md`

## See Also

- [Enterprise Schema Overview](../architecture/architectural-decisions.md)
- [Epic 6: Company Enrichment Service](../epics/epic-6-company-enrichment-service.md)
- [Legacy Database Integration](../brownfield-architecture.md)
