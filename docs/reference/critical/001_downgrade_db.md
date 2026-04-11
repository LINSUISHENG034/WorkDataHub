# Critical Database Downgrade Notes

> Source of truth: `alembic.ini`, `src/work_data_hub/io/schema/migration_runner.py`
> Last verified: `2026-04-11`
> Scope: Database migration safety

Downgrades are high-risk operations. Use them only when a migration rollback has been explicitly approved and the target environment has a verified backup.

## Minimum Safety Checklist

- confirm the current Alembic revision before any downgrade
- capture or verify a restorable database backup
- stop application writers before changing schema state
- run the downgrade in a controlled environment first when possible

## Reference Commands

```bash
uv run --env-file .wdh_env alembic current
uv run --env-file .wdh_env alembic downgrade -1
```
