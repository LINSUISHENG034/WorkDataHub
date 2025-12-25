# scripts/create_table/ - DDL Scripts Directory

## Scope

> **Important:** As of Story 6.2-P13, domain tables are NO LONGER managed in this directory.

This directory is now ONLY for:

1. **Utility Tables** - Standalone tables not part of domain schema (e.g., `lookup_requests`)
2. **Temporary Tables** - Staging tables for data processing
3. **One-time Scripts** - Data repair and migration scripts
4. **Historical Reference** - Legacy DDL files retained for reference (deprecated, not for new deployments)

## Migration Guide

### For Domain Tables

Domain tables (`规模明细`, `收入明细`, `年金计划`, `组合计划`) are now managed via:

1. **Schema Truth Source**: `src/work_data_hub/io/schema/domain_registry.py`
2. **Versioned Migrations**: `io/schema/migrations/versions/`

To add or modify a domain table:

```bash
# 1. Update domain_registry.py with schema changes
# 2. Generate migration
uv run alembic revision -m "your_change_description"

# 3. Edit the generated migration file
# 4. Apply migration
uv run alembic upgrade head
```

Note: `scripts/create_table/manifest.yml` may still contain a legacy `domains:` section for
backward compatibility with `generate_from_json.py`, but it is **deprecated** and not the
schema source of truth.

### For Utility Tables

Utility tables (non-domain) remain in this directory:

```bash
# Create/update DDL file
scripts/create_table/ddl/your_table.sql

# Register in manifest.yml under utility_tables
```

## Deprecated

The following DDL files are **deprecated** and should NOT be used for new deployments:

| File | Table | Replacement |
|------|-------|-------------|
| `ddl/annuity_performance.sql` | `business."规模明细"` | `io/schema/domain_registry.py` + Alembic |
| `ddl/annuity_plans.sql` | `mapping."年金计划"` | `io/schema/domain_registry.py` + Alembic |
| `ddl/portfolio_plans.sql` | `mapping."组合计划"` | `io/schema/domain_registry.py` + Alembic |

These files are retained for historical reference only.

## Directory Structure

```
scripts/create_table/
├── README.md           # This file
├── manifest.yml        # Table registry with scope sections
├── ddl/               # DDL files
│   ├── annuity_performance.sql  # DEPRECATED - use domain_registry
│   ├── annuity_plans.sql        # DEPRECATED - use domain_registry
│   ├── portfolio_plans.sql      # DEPRECATED - use domain_registry
│   └── lookup_requests.sql      # Active - utility table
└── generate_from_json.py        # DDL generation utility
```

> **Note:** `company_mapping.sql` was removed in Story 7.1-4 (Zero Legacy).
> The `enterprise.company_mapping` table was replaced by `enterprise.enrichment_index`.

## References

- **Domain Registry (Canonical)**: `src/work_data_hub/infrastructure/schema/domain_registry.py`
- **Domain Registry (IO Shim)**: `src/work_data_hub/io/schema/domain_registry.py` (backward compatibility)
- **Migration Runner**: `src/work_data_hub/io/schema/migration_runner.py`
- **Alembic Config**: `alembic.ini`
- **Story**: `docs/sprint-artifacts/stories/6.2-p13-unified-domain-schema-management.md`
