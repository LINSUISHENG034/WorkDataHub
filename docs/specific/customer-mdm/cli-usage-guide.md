# Customer MDM CLI Usage Guide

**Story 7.6-10: Integration Testing & Documentation**
**Version**: 1.0
**Last Updated**: 2026-01-30

## Overview

This document describes the command-line interface (CLI) for the Customer Master Data Management (MDM) system. The CLI provides manual triggers for data synchronization operations that normally run automatically as Post-ETL hooks.

## Prerequisites

- Database connection configured in `.wdh_env`
- Python environment with `work_data_hub` package installed
- Required tables created via Alembic migrations (009, 013)

## Commands

### 1. Contract Status Sync

Synchronizes contract status from `business.规模明细` to `customer.customer_plan_contract`.

```bash
# Production run (full sync)
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync

# Dry-run mode (no database changes)
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync --dry-run

# With period parameter (currently reserved for future use)
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync --period 202601
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Log actions without database changes | `False` |
| `--period` | Period to sync (YYYYMM format). Currently unused - syncs all data | `None` |

**Output Example:**
```
🔄 Starting contract status sync...
✓ Sync completed:
  Inserted: 1523
  Updated: 0
  Total processed: 1523
```

### 2. Monthly Snapshot Refresh

Refreshes dual monthly snapshots in:
`customer.fct_customer_product_line_monthly` and
`customer.fct_customer_plan_monthly`.

```bash
# Production run for January 2026
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202601

# Dry-run mode
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202601 --dry-run
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--period` | Period to refresh (YYYYMM format) **REQUIRED** | N/A |
| `--dry-run` | Log actions without database changes | `False` |

**Period Format:**
- Format: `YYYYMM` (6 digits)
- Example: `202601` for January 2026
- Internally converts to end-of-month date (e.g., `2026-01-31`)

**Output Example:**
```
🔄 Starting monthly snapshot refresh for period 202601...
✓ Snapshot refresh completed:
  ProductLine table: 847 records
  Plan table: 1203 records
```

## Post-ETL Hook Integration

Both commands are automatically triggered by the ETL pipeline's Post-ETL hook system:

```bash
# Full ETL with automatic post-hooks
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance --execute

# Skip post-hooks (sync only ETL data)
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domain annuity_performance --execute --no-post-hooks
```

### Hook Execution Order

When triggered automatically:
1. `contract_status_sync` runs first
2. `snapshot_refresh` runs second (depends on contract data)

## Execution Context

### When to Use Manual Commands

| Scenario | Command |
|----------|---------|
| Backfill historical data | `customer-mdm sync` |
| Re-generate specific month snapshot | `customer-mdm snapshot --period YYYYMM` |
| Debug/verify logic with dry-run | Add `--dry-run` flag |
| Re-run after ETL failure | `customer-mdm sync` then `snapshot` |

### Idempotency Guarantees

Both commands are idempotent:

- **Contract Sync**: Uses `ON CONFLICT DO NOTHING` - safe to re-run
- **Snapshot Refresh**: Uses `ON CONFLICT DO UPDATE` - re-running updates existing records

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `DATABASE_URL not found` | Missing `.wdh_env` | Ensure `.wdh_env` exists with valid `DATABASE_URL` |
| `Invalid period format` | Wrong period string | Use YYYYMM format (e.g., `202601`) |
| `ForeignKeyViolation` | Missing dimension data | Verify `年金客户` and `产品线` tables have required data |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check stderr for details) |

## Related Documentation

- [Contract Specification](customer-plan-contract-specification.md)
- [Snapshot Specification](customer-monthly-snapshot-specification.md)
- [Project Context](../../project-context.md)
