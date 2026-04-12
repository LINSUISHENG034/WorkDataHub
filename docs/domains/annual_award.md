# annual_award

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/annual_award/service.py`, `src/work_data_hub/domain/annual_award/pipeline_builder.py`, `src/work_data_hub/cli/etl/main.py`
> Last verified: `2026-04-11`
> Scope: Active ETL domain contract

## Overview

`annual_award` merges the trustee and investee award sheets from the monthly business workbook and loads the result to the customer schema. The domain is registered in `src/work_data_hub/domain/registry.py` and uses the shared ETL CLI.

业务口径说明：
- `customer."中标客户明细"` 属于申报口径。
- 该表会在实际系统数据中展现，但它表达的是“申报中标事实”，不是客户状态快照本身。

## Inputs

- Base path: `data/real_data/{YYYYMM}/收集数据/业务收集`
- File patterns: `*台账登记*.xlsx`, `*当年中标*.xlsx`
- Primary sheet fallback: `企年受托中标(空白)`
- Multi-sheet inputs: `企年受托中标(空白)`, `企年投资中标(空白)`

## File Discovery And Sheet Selection

- `--period` resolves the monthly folder.
- Discovery supports the configured workbook patterns and merges both configured sheets when present.
- `sheet_name` is a fallback; `sheet_names` is the actual multi-sheet contract for this domain.

## Transformation And Validation

The award pipeline performs:

- column renaming and business-type normalization
- product-line and plan-type derivation
- date parsing for `上报月份` and `中标日期`
- branch-code mapping and customer-name cleanup
- domain cleansing and company ID resolution
  - runtime note: the standard adapter path always passes an `EqcLookupConfig`
    object into the pipeline; when no explicit EQC settings are provided, it
    uses a disabled config rather than omitting the step entirely
- plan-code enrichment from `客户年金计划`
- fallback plan-code defaulting plus legacy-column drop

## Output Tables

- Target schema: `customer`
- Target table: `中标客户明细`
- Delete/refresh key: `上报月份`, `业务类型`
- Backfill: required for this domain

## CLI And Operational Entry Points

- CLI entry: [src/work_data_hub/cli/etl/main.py](../../src/work_data_hub/cli/etl/main.py)
- Domain pipeline: [src/work_data_hub/domain/annual_award/pipeline_builder.py](../../src/work_data_hub/domain/annual_award/pipeline_builder.py)

Example:

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_award --period 202411 --plan-only
```

## Configuration

- Domain config: [config/data_sources.yml](../../config/data_sources.yml)
- Domain adapter: [src/work_data_hub/domain/annual_award/adapter.py](../../src/work_data_hub/domain/annual_award/adapter.py)
- Domain pipeline: [src/work_data_hub/domain/annual_award/pipeline_builder.py](../../src/work_data_hub/domain/annual_award/pipeline_builder.py)

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_award --period 202411 --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Related Runbooks And Rules

- [Runbook](../runbooks/annual_award.md)
- [Cleansing Rules Index](../cleansing-rules/index.md)
- [Capability And Mechanism Map](./annual_award-capability-map.md)
- [Documentation Standards](../engineering/documentation-standards.md)
