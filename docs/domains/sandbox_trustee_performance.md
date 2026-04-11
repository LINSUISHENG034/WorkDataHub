# sandbox_trustee_performance

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/sandbox_trustee_performance/service.py`, `src/work_data_hub/domain/sandbox_trustee_performance/models.py`, `src/work_data_hub/cli/etl/main.py`
> Last verified: `2026-04-11`
> Scope: Active ETL domain contract

## Overview

`sandbox_trustee_performance` is the non-production trustee-performance domain used by sample jobs, schedules, and sandbox validation flows. It is registered in `src/work_data_hub/domain/registry.py` and writes to the sandbox schema.

## Inputs

- Base path: `data/real_data/202411/收集数据/业务收集`
- File pattern: `**/*受托业绩*.xlsx`
- Sheet selection: sheet index `0`

## File Discovery And Sheet Selection

- The configured path is period-free and fixed to the sandbox sample dataset.
- Recursive discovery is enabled through the `**/*受托业绩*.xlsx` pattern.
- Operators can override the sheet via `--sheet`, but config defaults to sheet `0`.

## Transformation And Validation

This domain uses a simpler row-oriented service than the annuity and customer domains:

- input rows are validated into `TrusteePerformanceIn`
- report date, plan code, and company code are extracted per row
- performance metrics are normalized into `TrusteePerformanceOut`
- rows missing required identifiers are skipped
- the service raises when more than half of rows fail processing

## Output Tables

- Target schema: `sandbox`
- Target table: `sandbox_trustee_performance`
- Backfill: not required by the domain adapter

## CLI And Operational Entry Points

- CLI entry: [src/work_data_hub/cli/etl/main.py](../../src/work_data_hub/cli/etl/main.py)
- Domain service: [src/work_data_hub/domain/sandbox_trustee_performance/service.py](../../src/work_data_hub/domain/sandbox_trustee_performance/service.py)

Example:

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sandbox_trustee_performance --plan-only
```

## Configuration

- Domain config: [config/data_sources.yml](../../config/data_sources.yml)
- Domain adapter: [src/work_data_hub/domain/sandbox_trustee_performance/adapter.py](../../src/work_data_hub/domain/sandbox_trustee_performance/adapter.py)
- Models: [src/work_data_hub/domain/sandbox_trustee_performance/models.py](../../src/work_data_hub/domain/sandbox_trustee_performance/models.py)

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sandbox_trustee_performance --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Related Runbooks And Rules

- [Runbook](../runbooks/sandbox_trustee_performance.md)
- [Cleansing Rules Index](../cleansing-rules/index.md)
- [Documentation Standards](../engineering/documentation-standards.md)
