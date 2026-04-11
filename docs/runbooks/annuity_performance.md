# annuity_performance Runbook

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

Related domain contract: [annuity_performance](../domains/annuity_performance.md)

## Preconditions

- `.wdh_env` exists and contains `PYTHONPATH=src` plus a valid `DATABASE_URL`
- source workbook for the target `YYYYMM` exists under `data/real_data/{YYYYMM}/收集数据/数据采集`
- operator understands whether post-hooks should run after load

## Manual Execution

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute --no-post-hooks
```

## Common Errors

| Error shape | Likely cause | Action |
|------------|--------------|--------|
| No files discovered | Wrong `YYYYMM` folder or workbook name | Verify the path and file naming against `config/data_sources.yml`. |
| Multiple files matched | Ambiguous workbook set | Re-run with `--file-selection newest` or clean up duplicates. |
| Enrichment/token failure | EQC lookup path unavailable | Retry with valid token state or use `--no-enrichment` if operationally acceptable. |
| Refresh/load conflict | Existing rows for the same refresh key | Run plan-only first, confirm the period, then re-run in execute mode. |

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
uv run pytest tests/integration/test_annuity_config.py -v
```

## Rollback Or Safe Re-run

- Prefer `--plan-only` before any production rerun.
- If the previous execution should not have triggered post-hooks, re-run with `--no-post-hooks`.
- If data for the same period must be replaced, use the configured delete/refresh scope for `月度`, `业务类型`, and `计划类型`, then execute the same command again.
