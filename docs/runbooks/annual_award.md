# annual_award Runbook

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

Related domain contract: [annual_award](../domains/annual_award.md)

## Preconditions

- `.wdh_env` exists and includes `PYTHONPATH=src` and `DATABASE_URL`
- the target workbook exists under `data/real_data/{YYYYMM}/收集数据/业务收集`
- the workbook contains the configured trustee and investee award sheets

## Manual Execution

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_award --period 202411 --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_award --period 202411 --execute
```

## Common Errors

| Error shape | Likely cause | Action |
|------------|--------------|--------|
| Missing sheet | Workbook does not contain one of the configured award tabs | Check both configured sheet names before rerunning. |
| Plan code remains empty | Plan enrichment lookup did not resolve | Confirm customer-plan reference data is available for the period. |
| Company resolution failure | Enrichment path unavailable | Retry with enrichment restored or use `--no-enrichment` if approved. |

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_award --period 202411 --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Rollback Or Safe Re-run

- Validate both input sheets in `--plan-only` mode before rerunning.
- Replace data only within the configured refresh key scope: `上报月份`, `业务类型`.
- If the issue is enrichment-specific, retry with the same period after the enrichment path is restored.
