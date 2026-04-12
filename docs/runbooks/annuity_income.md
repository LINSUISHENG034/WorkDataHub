# annuity_income Runbook

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

Related domain contract: [annuity_income](../domains/annuity_income.md)

## Preconditions

- `.wdh_env` exists and includes `PYTHONPATH=src` and `DATABASE_URL`
- source workbook for the target `YYYYMM` exists under `data/real_data/{YYYYMM}/收集数据/数据采集`
- downstream operators know whether enrichment is required for the run

## Manual Execution

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_income --period 202411 --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_income --period 202411 --execute
```

## Common Errors

| Error shape | Likely cause | Action |
|------------|--------------|--------|
| No files discovered | Wrong period folder or workbook name | Verify the discovery path and workbook patterns. |
| Customer or fee defaults look wrong | Workbook structure changed | Compare the incoming sheet against the expected `收入明细` columns. |
| Enrichment failure | EQC path unavailable | Retry with a healthy environment or use `--no-enrichment` if approved. |
| Temporary `IN*` company IDs appear | Resolver could not match a company in the standard path | Review the unresolved names export and decide whether mappings or source data need correction. |

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_income --period 202411 --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Rollback Or Safe Re-run

- Re-run in `--plan-only` mode first if the prior load is in doubt.
- Replace data only within the configured refresh key scope: `月度`, `业务类型`, `计划类型`.
- Use the same period and command shape for a clean re-run.
- If `unknown_names_csv` is emitted, inspect it before treating the run as fully reconciled.
