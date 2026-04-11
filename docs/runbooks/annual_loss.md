# annual_loss Runbook

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

Related domain contract: [annual_loss](../domains/annual_loss.md)

## Preconditions

- `.wdh_env` exists and includes `PYTHONPATH=src` and `DATABASE_URL`
- the target workbook exists under `data/real_data/{YYYYMM}/收集数据/业务收集`
- the workbook contains the configured trustee and investee loss sheets

## Manual Execution

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_loss --period 202411 --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_loss --period 202411 --execute
```

## Common Errors

| Error shape | Likely cause | Action |
|------------|--------------|--------|
| Missing sheet | Workbook does not contain one of the configured loss tabs | Confirm both configured sheet names are present. |
| Plan enrichment gap | Customer-plan lookup returned no match | Verify the customer-plan reference set for the period. |
| Ambiguous workbook | Multiple candidate files matched | Re-run with `--file-selection newest` or clean up duplicate files. |

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annual_loss --period 202411 --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Rollback Or Safe Re-run

- Re-run in `--plan-only` mode first if the previous execution is suspect.
- Replace data only within the configured refresh key scope: `上报月份`, `业务类型`.
- Use the same period and file-selection strategy during rerun to keep the load deterministic.
