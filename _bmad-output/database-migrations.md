# WorkDataHub Database Migration Guide

_Updated for Story 1.7 – Database Schema Management Framework_

## Directory Layout

| Path | Purpose |
| --- | --- |
| `alembic.ini` | Root configuration that points to the IO-layer migration scripts. |
| `io/schema/migrations/` | Alembic environment + migration versions (Clean Architecture IO ring). |
| `io/schema/migrations/versions/` | Timestamped migration scripts (e.g., `20251113_000001_create_core_tables.py`). |
| `io/schema/fixtures/test_data.sql` | Optional seed data for local testing. |
| `scripts/db_setup.py` | Cross-platform helper to run migrations and load seeds. |

## Naming & Versioning

- **File pattern:** `YYYYMMDD_HHMM_short_description.py` (prevents conflicts in multi-dev scenarios).
- **Revision IDs:** Match the filename for easy traceability (e.g., `20251113_000001`).
- **Tracking:** Alembic maintains schema state via the `alembic_version` table.

## Common Commands

```bash
# Upgrade to latest schema
alembic upgrade head

# Downgrade one revision (use with caution in shared environments)
alembic downgrade -1

# Generate a new migration (edit the resulting file before committing)
alembic revision -m "describe_change"
```

> ℹ️ `sqlalchemy.url` is dynamically resolved from `work_data_hub.config.get_settings()`.  
> Set `DATABASE_URL` / `WDH_DATABASE__URI` before running Alembic commands.

## Programmatic Runner & Script

- **Python API:** `work_data_hub.io.schema.migration_runner.upgrade(...)` (used by tests and tooling).
- **Helper Script:** `python scripts/db_setup.py --database-url <URL> [--seed]`
  - `--downgrade` runs `alembic downgrade`.
  - `--seed` loads `io/schema/fixtures/test_data.sql` (custom file via `--seed-file`).

## Test Database Integration

- `tests.conftest.test_db_with_migrations` fixture automatically provisions a temporary database and runs `alembic upgrade head`.
- Integration tests can depend on this fixture to ensure schema availability without a manual Postgres instance.
- Example usage:

```python
def test_pipeline_tables(test_db_with_migrations):
    engine = create_engine(test_db_with_migrations)
    assert "pipeline_executions" in inspect(engine).get_table_names()
```

## Workflow Expectations

1. **Before coding:** Run `alembic upgrade head` (or `scripts/db_setup.py`) to ensure your database matches the latest schema.
2. **Adding migrations:** Place new scripts under `io/schema/migrations/versions/` using the timestamp naming convention. Keep Postgres-specific types (`JSONB`, `UUID`) but provide SQLite fallbacks using SQLAlchemy variants.
3. **Testing:** Use `pytest -m integration tests/io/schema/test_migrations.py` to validate upgrades/downgrades locally.
4. **Documentation:** Update this guide whenever new tooling, commands, or conventions are introduced.

---

## Legacy Database Migration (2025-12-16)

> **重要变更**: Legacy MySQL 数据库已完全迁移至 PostgreSQL。

### 迁移概况

| 属性 | 旧值 | 新值 |
|------|------|------|
| 数据库类型 | MySQL | PostgreSQL |
| 连接地址 | `192.168.0.200:5432/annuity` | `localhost:5432/legacy` |
| 连接字符串 | _(已废弃)_ | `postgresql://postgres:Post.169828@localhost:5432/legacy` |

### 配置变更

在 `.wdh_env` 中添加了新的配置项：

```ini
# Target database (app code)
WDH_DATABASE__URI=postgres://postgres:Post.169828@localhost:5432/postgres

# Legacy database (migration scripts use this for reading source data)
LEGACY_DATABASE__URI=postgres://postgres:Post.169828@localhost:5432/legacy
```

### Schema 映射

Legacy 系统中的表现在位于 `legacy` 数据库的以下 schema：

| Schema | 主要表 |
|--------|--------|
| `enterprise` | `company_id_mapping`, `eqc_search_result`, `annuity_account_mapping` |
| `mapping` | `年金计划` |
| `business` | `规模明细` |
| `config` | 配置表 |
| `customer` | 客户数据 |
| `finance` | 财务数据 |

### 受影响的脚本

需要使用 `LEGACY_DATABASE__URI` 的脚本：

- `scripts/migrations/enrichment_index/migrate_full_legacy_db.py`
- `scripts/migrations/enrichment_index/migrate_plan_mapping.py`

### 注意事项

1. **双数据库模式**: 迁移脚本现在支持从 Legacy PostgreSQL 读取，写入到 Target PostgreSQL
2. **Schema 变更**: 源表从 `legacy.*` 变更为 `enterprise.*`
3. **环境变量**: 统一使用 `.wdh_env` 管理所有数据库配置，避免硬编码
