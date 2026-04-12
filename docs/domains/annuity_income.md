# annuity_income

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/annuity_income/service.py`, `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `src/work_data_hub/cli/etl/main.py`
> Last verified: `2026-04-11`
> Scope: Active ETL domain contract

## Overview

`annuity_income` processes the `收入明细` worksheet from the same monthly annuity workbook family used by `annuity_performance`. The domain is registered in `src/work_data_hub/domain/registry.py` and uses the shared ETL CLI plus a Bronze-to-Silver pipeline with enrichment support.

## Inputs

- Base path: `data/real_data/{YYYYMM}/收集数据/数据采集`
- File patterns: `*规模收入数据*.xlsx`, `*规模*收入数据*.xlsx`
- Exclusions: default exclusions plus `*回复*`
- Sheet: `收入明细`

## File Discovery And Sheet Selection

- Discovery resolves `{YYYYMM}` from `--period`.
- `--file-selection` handles multiple matching workbooks.
- The domain reads only the `收入明细` worksheet defined in `config/data_sources.yml`.

## Transformation And Validation

The income pipeline performs:

- column rename and plan-code normalization/correction
- branch-code mapping and month parsing
- defaulting for customer name and fee columns
- portfolio and product-line derivation
- preservation of account-name fields before cleansing
- domain cleansing plus company ID resolution
  - unresolved rows currently fall back to generated temporary `IN*` company IDs
- removal of legacy columns before load

Validation and output modeling live under `src/work_data_hub/domain/annuity_income/`.

## Output Tables

- Target schema: `business`
- Target table: `收入明细`
- Delete/refresh key: `月度`, `业务类型`, `计划类型`
- Backfill: required for this domain
- Additional operator artifact: when unresolved company names exist and export is
  enabled, the service may return an `unknown_names_csv` path for manual review

## CLI And Operational Entry Points

- CLI entry: [src/work_data_hub/cli/etl/main.py](../../src/work_data_hub/cli/etl/main.py)
- Unified CLI router: [src/work_data_hub/cli/__main__.py](../../src/work_data_hub/cli/__main__.py)

Example:

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_income --period 202411 --plan-only
```

## Configuration

- Domain config: [config/data_sources.yml](../../config/data_sources.yml)
- Domain adapter: [src/work_data_hub/domain/annuity_income/adapter.py](../../src/work_data_hub/domain/annuity_income/adapter.py)
- Domain pipeline: [src/work_data_hub/domain/annuity_income/pipeline_builder.py](../../src/work_data_hub/domain/annuity_income/pipeline_builder.py)

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_income --period 202411 --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Related Runbooks And Rules

- [Runbook](../runbooks/annuity_income.md)
- [Cleansing Rules](../cleansing-rules/annuity-income.md)
- [Capability And Mechanism Map](./annuity_income-capability-map.md)
- [Documentation Standards](../engineering/documentation-standards.md)
