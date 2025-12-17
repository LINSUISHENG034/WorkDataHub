# Annuity Performance Cleaner Comparison - Usage Guide

## Overview

This CLI tool compares the data cleansing output between the **Legacy AnnuityPerformanceCleaner** and the **New Pipeline** for the `annuity_performance` domain. It enables row-by-row validation to ensure data integrity during migration.

## Scripts

| Script | Purpose |
|--------|---------|
| `guimo_iter_cleaner_compare.py` | Core comparison script with CLI interface |
| `guimo_iter_config.py` | Configuration constants (fields, classifications) |
| `guimo_iter_report_generator.py` | Report generation (CSV, Markdown, console) |

## Prerequisites

1. **Python Environment**: Use `uv` for package management
2. **Environment File**: `.wdh_env` with database credentials
3. **Legacy Dependencies**: Ensure the legacy cleaner can import (if not, use `--new-only`)

## Usage

### Basic Comparison (100 rows)

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    "tests\fixtures\real_data\202311\收集数据\数据采集\V1\【for年金分战区经营分析】24年11月年金规模收入数据1209采集.xlsx" `
    --limit 100 --debug --export
```

### Auto-Discovery Mode (Recommended)

```powershell
# Automatically discover the correct file by month
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    --month 202311 --limit 100 --debug --export
```

### Full Dataset Comparison

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    <excel_path> --limit 0 --debug --export
```

### New Pipeline Only (No Legacy Dependencies)

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    <excel_path> --new-only --debug --limit 100
```

### EQC Enrichment Mode (Full Company ID Resolution)

Use `--enrichment` to enable real-time EQC API lookups for unresolved company names. This is **required** to minimize `needs_review` records.

```powershell
# Full dataset with EQC enrichment enabled
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    --month 202501 --limit 0 --debug --export --enrichment
```

```powershell
# With custom EQC budget (default: 1000)
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    --month 202501 --limit 0 --enrichment --sync-budget 5000
```

> [!IMPORTANT]
> **Without `--enrichment`**, records that cannot be resolved via YAML overrides or DB cache will be classified as `needs_review` and receive Temp IDs. **With `--enrichment`**, these records will first attempt EQC API lookup before generating Temp IDs.

**When to use `--enrichment`:**

| Scenario | Recommendation |
|----------|----------------|
| Quick validation / CI pipeline | ❌ Skip (faster, uses cached data) |
| Final validation before release | ✅ Enable (ensures full resolution) |
| First run on new month's data | ✅ Enable (populates cache for future runs) |
| Investigating `needs_review` records | ✅ Enable (confirms if EQC can resolve them) |

**Resolution with `--enrichment` enabled:**

1. YAML Overrides → 2. DB Cache → 3. Existing Column → **4. EQC API (NEW)** → 5. Default Fallback → 6. Temp ID

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `excel_path` | (required) | Path to source Excel file |
| `--sheet` | `规模明细` | Sheet name to process |
| `--limit` | `100` | Row limit (0 = no limit) |
| `--enrichment` | `False` | Enable EQC sync lookups (DB cache is enabled automatically when available) |
| `--month YYYYMM` | (None) | Auto-discover source file by month (e.g., `--month 202411`). Uses `FileDiscoveryService` from New Pipeline for intelligent version detection. Alternative to specifying `excel_path` manually. Note: Folder structure must match `config/data_sources.yml` pattern. |
| `--debug` | `False` | Save debug snapshots |
| `--export` | `False` | Export CSV and Markdown reports |
| `--new-only` | `False` | Run only New Pipeline |
| `--no-auto-refresh-token` | `False` | Disable automatic token refresh when `--enrichment` is enabled |
| `--sync-budget` | `1000` | EQC sync lookup budget (number of API calls allowed, 0 = disabled) |

> [!NOTE]
> When `--enrichment` is enabled and the EQC token is invalid/expired, a QR code popup will automatically appear for token refresh (Story 6.2-P11). Use `--no-auto-refresh-token` to disable this behavior.

## Output Structure

All outputs are saved to a timestamped directory:

```
scripts/validation/CLI/_artifacts/<YYYYMMDD_HHMMSS>/
├── diff_report_<YYYYMMDD_HHMMSS>.csv     # Detailed differences
├── diff_summary_<YYYYMMDD_HHMMSS>.md     # Markdown summary
└── debug_snapshots/                     # Optional (--debug)
    ├── legacy_output.csv
    └── new_pipeline_output.csv
```

## Comparison Categories

### Numeric Fields (Zero Tolerance)

Fields compared with `Decimal` precision. `NULL` and `0` are treated as equivalent.
If a value is non-numeric (e.g., `"abc"`), it is treated as a **critical issue** (do not silently coerce to 0).

- `期初资产规模`, `期末资产规模`, `供款`, `流失(含待遇支付)` / `流失_含待遇支付`, `流失`, `待遇支付`

### Derived Fields

Fields derived from mappings or transformations:

- `月度`, `机构代码`, `计划代码`, `组合代码`, `产品线代码`

### Upgrade Fields (company_id)

Classifications for `company_id` differences:

| Classification | Meaning |
|----------------|---------|
| `upgrade_eqc_resolved` | ✅ New resolved, Legacy was empty/invalid |
| `regression_missing_resolution` | ❌ Legacy had ID, New returns temp ID |
| `regression_company_id_mismatch` | ❌ Both numeric but different |
| `needs_review` | ❓ Manual review required |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No critical issues |
| `1` | Critical issues found (e.g., numeric mismatch, missing numeric columns, invalid numeric values, row count mismatch) |

## Resolution Priority (New Pipeline)

1. **YAML Overrides** (5 levels: plan → account → hardcode → name → account_name)
2. **Database Cache** (`enterprise.enrichment_index` preferred; legacy fallback when present)
3. **Existing Column Passthrough** (numeric values only)
4. **EQC Sync Lookup** (budgeted)
5. **Default Fallback** (`600866980` for empty customer_name - Legacy compatibility)
6. **Temporary ID Generation** (HMAC-SHA1)

## Recent Fixes (2025-12-18)

| Fix | Description |
|-----|-------------|
| **Alphanumeric Company ID** | DB cache now accepts alphanumeric IDs like `602671512X` (special customer codes) |
| **Empty Customer Name Fallback** | When `customer_name` is empty, returns `600866980` instead of temp ID (Legacy parity) |
| **Excel Row Numbers** | Diff reports now show Excel-compatible row numbers (1-indexed + header offset) |

## Notes

- **DB cache is always attempted** when the database is reachable; `--enrichment` only enables EQC sync lookups.
- The comparison script’s EQC sync budget is currently fixed (see `guimo_iter_cleaner_compare.py`); for tunable budgets use the ETL CLI (`work_data_hub.cli etl`).
