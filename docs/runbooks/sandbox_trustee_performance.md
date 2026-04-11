# sandbox_trustee_performance Runbook

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

Related domain contract: [sandbox_trustee_performance](../domains/sandbox_trustee_performance.md)

## Preconditions

- `.wdh_env` exists and includes `PYTHONPATH=src`
- the sandbox sample workbook exists under `data/real_data/202411/收集数据/业务收集`
- operators understand this domain writes to the non-production `sandbox` schema

## Manual Execution

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sandbox_trustee_performance --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sandbox_trustee_performance --execute
```

## Common Errors

| Error shape | Likely cause | Action |
|------------|--------------|--------|
| No files discovered | Sandbox sample path does not exist locally | Confirm the fixed sample directory has been restored. |
| High row failure ratio | Too many rows fail service validation | Inspect the input sheet and the required identifiers before rerunning. |
| Wrong worksheet loaded | Sheet override or workbook structure drift | Use the configured sheet `0` or pass an explicit `--sheet` override. |

## Verification

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains sandbox_trustee_performance --plan-only
uv run python scripts/quality/check_docs_alignment.py
```

## Rollback Or Safe Re-run

- Prefer `--plan-only` before re-executing the sandbox load.
- Because this is a sandbox-only table, rerun against the same sample workbook after correcting the input or sheet selection.
- Keep the run isolated to the sandbox domain; do not combine it with production domains when troubleshooting.
