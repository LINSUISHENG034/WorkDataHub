# Archived Alembic Migrations

This directory contains **archived Alembic migration files** from the pre-Epic 7.2 migration chain.

## Archive Date

2025-12-28 (Story 7.2-1: Migration Backup and Archive)

## Purpose

These migrations were archived as part of **Epic 7.2: Alembic Migration Refactoring** to establish a clean migration baseline for Epic 8 (Testing & Validation Infrastructure).

**Important:** These archived migrations are **NOT used** by Alembic. They are preserved for historical reference only.

## Archived Files (10 migrations)

| Filename | Date | Description |
|----------|------|-------------|
| `20251113_000001_create_core_tables.py` | 2025-11-13 | Initial core tables (pipeline_executions, data_quality_metrics) |
| `20251206_000001_create_enterprise_schema.py` | 2025-12-06 | Enterprise schema (base_info, business_info, biz_label) |
| `20251207_000001_add_next_retry_at_column.py` | 2025-12-07 | Add next_retry_at to enrichment_requests |
| `20251208_000001_create_enrichment_index.py` | 2025-12-08 | Create enrichment_index table |
| `20251212_120000_add_reference_tracking_fields.py` | 2025-12-12 | Add _source, _needs_review fields |
| `20251214_000001_create_sync_state_table.py` | 2025-12-14 | Create system.sync_state table |
| `20251214_000002_add_raw_data_to_base_info.py` | 2025-12-14 | Add JSONB columns to base_info |
| `20251214_000003_add_cleansing_status_to_business_info.py` | 2025-12-14 | Add cleansing status to business_info |
| `20251219_000001_create_domain_tables.py` | 2025-12-19 | Create domain tables (规模明细, 收入明细, etc.) |
| `20251129_000001_create_annuity_performance_new.py` | 2025-11-29 | Shadow table (deprecated) |

## Original Migration Branching Structure

The archived migration chain had a **branching structure** with 2 heads:

```
20251206_000001_create_enterprise_schema (head)
├── 20251212_120000_add_reference_tracking_fields
│   └── 20251219_000001_create_domain_tables (head 1)
└── 20251214_000001_create_sync_state_table
    ├── 20251214_000002_add_raw_data_to_base_info
    │   └── 20251214_000003_add_cleansing_status_to_business_info (head 2)
    └── 20251129_000001_create_annuity_performance_new (orphan)
```

## New Migration Structure (Post-Archive)

After archiving, the migration structure is:

```
io/schema/migrations/versions/
├── _archived/          # Historical migrations (ignored by Alembic)
│   ├── .gitkeep
│   ├── README.md
│   └── [10 migration files]
└── (empty - ready for new clean migrations)
```

## New Migrations (Epic 7.2 Phase 2+)

New linear migrations will be created in Story 7.2-2:
- `001_infrastructure.py` - Core infrastructure tables
- `002_domains.py` - Domain tables (规模明细, 收入明细, etc.)
- `003_seed_data.py` - Reference data seeding

## References

- **Story:** [Story 7.2-1: Migration Backup and Archive](../../../../docs/sprint-artifacts/stories/7.2-1-migration-backup-and-archive.md)
- **Sprint Change Proposal:** [Epic 7.2: Alembic Migration Refactoring](../../../../docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-27-migration-refactoring.md)
- **Migration Checklist:** [docs/specific/migration/migration-checklist.md](../../../../docs/specific/migration/migration-checklist.md)

---

**Note:** Do NOT restore these files to the parent `versions/` directory. The new migration chain will be created from scratch in Story 7.2-2.
