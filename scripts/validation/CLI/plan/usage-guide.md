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
3. **Legacy Dependencies**: `pypac` (install via `uv pip install pypac`)

## Usage

### Basic Comparison (10 rows)

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/guimo_iter_cleaner_compare.py `
    "tests\fixtures\real_data\202412\收集数据\数据采集\V2\【for年金分战区经营分析】24年12月年金规模收入数据0109采集-补充企年投资收入.xlsx" `
    --limit 10 --debug --export
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

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `excel_path` | (required) | Path to source Excel file |
| `--sheet` | `规模明细` | Sheet name to process |
| `--limit` | `100` | Row limit (0 = no limit) |
| `--enrichment` | `True` | Enable EQC/DB enrichment |
| `--debug` | `False` | Save debug snapshots |
| `--export` | `False` | Export CSV and Markdown reports |
| `--new-only` | `False` | Run only New Pipeline |

## Output Structure

All outputs are saved to a timestamped directory:

```
scripts/validation/CLI/_artifacts/<YYYYMMDD_HHMMSS>/
├── legacy_output.csv         # Legacy cleaner output
├── new_pipeline_output.csv   # New Pipeline output
├── diff_report.csv           # Detailed differences
└── summary.md                # Markdown summary
```

## Comparison Categories

### Numeric Fields (Zero Tolerance)

Fields compared with `Decimal` precision. `NULL` and `0` are treated as equivalent.

- `期初资产规模`, `期末资产规模`, `供款`, `流失(含待遇支付)`, `待遇支付`

### Derived Fields

Fields derived from mappings or transformations:

- `业务类型代码`, `机构代码`

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
| `0` | No critical issues (numeric fields match) |
| `1` | Critical issues found (numeric mismatch) |

## Resolution Priority (New Pipeline)

1. **YAML Overrides** (5 levels: plan → account → hardcode → name → account_name)
2. **Database Cache** (`enrichment_index` table)
3. **Existing Column Passthrough**
4. **EQC Sync Lookup** (budgeted)
5. **Temporary ID Generation** (HMAC-SHA1)
