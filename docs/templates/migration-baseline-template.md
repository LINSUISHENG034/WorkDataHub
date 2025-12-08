# Migration Baseline Template (Shadow/Perf)

- Env: Postgres 14.x, DB=<shadow_db>, host=<shadow_host>
- Command: PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --dry-run --batch-size 500 --verbose
- Rows read: company_id_mapping=<n1>, eqc_search_result=<n2>, total=<n_total>
- Batch: <size>
- Runtime: <seconds> s; Throughput: <rows_per_sec> rows/s
- Logs: every 5000 rows timestamped
- Results: inserted=0, updated=0 (dry-run), skipped=<n_skipped>; Conflicts observed=<yes/no>; Errors=<none/desc>
- Notes: <anomalies/config tweaks>
