# Database Connection Usage (Project Components)

This guide shows how to use the built-in settings helper to create database connections and run lightweight checks.

## 1) Load settings and get the connection string

```python
from work_data_hub.config import get_settings

settings = get_settings()
database_url = settings.get_database_connection_string()
print(database_url)  # e.g., postgresql://user:pass@host:5432/db
```

Settings automatically read `.env` (or `WDH_ENV_FILE` override). It supports both full URI (`WDH_DATABASE__URI`) and component variables (`WDH_DATABASE_HOST`, `WDH_DATABASE_PORT`, `WDH_DATABASE_USER`, `WDH_DATABASE_PASSWORD`, `WDH_DATABASE_DB`).

## 2) Create an engine/connection with SQLAlchemy

```python
from sqlalchemy import create_engine

engine = create_engine(database_url)
with engine.connect() as conn:
    result = conn.execute(text("select version()")).scalar()
    print(result)
```

## 3) Check required tables for legacy migration

```python
from sqlalchemy import text

with engine.connect() as conn:
    tables = conn.execute(text("""
        select table_schema, table_name
        from information_schema.tables
        where table_name in ('enrichment_index','company_id_mapping','eqc_search_result')
    """)).fetchall()
    print(tables)
```

Expected: `enterprise.enrichment_index`, `legacy.company_id_mapping`, `legacy.eqc_search_result` all present.

## 4) Running the migration script (dry-run)

```bash
PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py \
  --dry-run --batch-size 500 --verbose \
  --report-path docs/sprint-artifacts/stories/validation-report-<timestamp>.md
```

This uses the same settings loader under the hood; ensure `.env` or environment variables provide the database connection.
