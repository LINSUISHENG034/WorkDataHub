# annuity_performance

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/annuity_performance/service.py`, `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/cli/etl/main.py`
> Last verified: `2026-04-11`
> Scope: Active ETL domain contract

## Overview

`annuity_performance` processes the `规模明细` worksheet from the monthly `规模收入数据` workbook and writes the normalized result to the business schema. The domain is registered in `src/work_data_hub/domain/registry.py` and is available through the shared ETL CLI.

## Inputs

- Base path: `data/real_data/{YYYYMM}/收集数据/数据采集`
- File patterns: `*规模收入数据*.xlsx`, `*规模*收入数据*.xlsx`
- Exclusions: default exclusions plus `*回复*`
- Sheet: `规模明细`

## File Discovery And Sheet Selection

- The domain requires `--period` because discovery resolves `{YYYYMM}` from the CLI period.
- `--file-selection` controls ambiguous matches and supports `error`, `newest`, `oldest`, and `first`.
- The workbook is single-sheet for this domain; `sheet_name` comes from `config/data_sources.yml`.

## Transformation And Validation

The Bronze-to-Silver pipeline in `pipeline_builder.py` performs:

- column mapping and plan-code correction/defaulting
- branch-code and product-line derivation
- month parsing and portfolio-code defaulting
- customer-account derivation and domain cleansing
- company ID resolution using the shared enrichment path
- legacy-column drop before load

Gold validation is enforced by the annuity performance models and schema helpers under `src/work_data_hub/domain/annuity_performance/`.

## Output Tables

- Target schema: `business`
- Target table: `规模明细`
- Delete/refresh key: `月度`, `业务类型`, `计划类型`
- Backfill: required for this domain

## CLI And Operational Entry Points

- CLI entry: [src/work_data_hub/cli/etl/main.py](../../src/work_data_hub/cli/etl/main.py)
- Unified CLI router: [src/work_data_hub/cli/__main__.py](../../src/work_data_hub/cli/__main__.py)

Example:

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
```

## Configuration

- Domain config: [config/data_sources.yml](../../config/data_sources.yml)
- Domain adapter: [src/work_data_hub/domain/annuity_performance/adapter.py](../../src/work_data_hub/domain/annuity_performance/adapter.py)
- Domain pipeline: [src/work_data_hub/domain/annuity_performance/pipeline_builder.py](../../src/work_data_hub/domain/annuity_performance/pipeline_builder.py)

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
uv run pytest tests/integration/test_annuity_config.py -v
```

## Related Runbooks And Rules

- [Runbook](../runbooks/annuity_performance.md)
- [Cleansing Rules](../cleansing-rules/annuity-performance.md)
- [Documentation Standards](../engineering/documentation-standards.md)
