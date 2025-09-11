# Baseline Validation Commands (P-023/P-024)

This guide lists the baseline validation commands you can run locally to verify the latest changes (alias serialization, DB auto-identity PKs, F-prefix refinement, and annuity service fixes).

> Always run commands via uv inside an activated virtualenv.

## 1) Lint, Type Check

```bash
uv run ruff format .
uv run ruff check src/ --fix
uv run mypy src/
```

## 2) Unit & Integration Tests (incremental)

- Annuity domain service:

```bash
uv run pytest -v tests/domain/annuity_performance/test_service.py
```

- Annuity models:

```bash
uv run pytest -v tests/domain/annuity_performance/test_models.py
```

- Cleansing framework (percent/currency):

```bash
uv run pytest -v tests/unit/test_cleansing_framework.py -k "percent or percentage or currency"
```

- Excel header/column normalization:

```bash
uv run pytest -v tests/io/test_excel_reader.py -k "header or column"
```

- Full test suite (optional):

```bash
uv run pytest -v
```

## 3) Plan-only E2E (no database required)

```bash
# For Windows PowerShell:
$env:WDH_DATA_BASE_DIR = "./reference/monthly"
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1

# For Linux/macOS:
WDH_DATA_BASE_DIR="./reference/monthly" uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1
```

Expected:

- JSON/SQL column names include `"流失_含待遇支付"` (normalized per column_normalizer)
- Delete scope key uses `["月度", "计划代码", "company_id"]` (non-unique in DB)
- No column-mismatch or null-only column errors

## 4) Execute E2E (requires local DB)

- Apply DDL:

```bash
# 设置数据库 URI（示例值为你当前使用的测试库）
# Windows PowerShell:
$env:WDH_DATABASE__URI = "postgres://postgres:Post.169828@localhost:5432/postgres"
# Linux/macOS:
# export WDH_DATABASE__URI="postgres://postgres:Post.169828@localhost:5432/postgres"

psql "$WDH_DATABASE__URI" -f scripts/create_table/ddl/annuity_performance.sql
```

- Run execute mode:

```bash
# For Windows PowerShell:
$env:WDH_DATA_BASE_DIR = "./reference/monthly"
uv run python -m src.work_data_hub.orchestration.jobs `
  --domain annuity_performance `
  --execute `
  --max-files 1 `
  --mode delete_insert

# For Linux/macOS:
WDH_DATA_BASE_DIR="./reference/monthly" uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --max-files 1 \
  --mode delete_insert
```

  - Run output
  
```bash

```

Expected:

- Inserts succeed without providing `id` (DB auto-identity)
- F-prefix stripping applies only to `组合代码` when matching `^F[0-9A-Z]+$`

## 5) Troubleshooting

- uv tries to resolve packages online and fails:
  - Set `$env: UV_NO_SYNC=1` to skip syncing in restricted networks

## Notes
- Annuity service no longer projects columns before transformation (prevents loss of raw fields needed for parsing). Batch validation projects per-row after validation.
- Alias serialization is enabled in ops with `by_alias=True, exclude_none=True`.
- Annuity DDL uses `GENERATED ALWAYS AS IDENTITY` for `id`.
- Tests use `company_id`; removed assertions on deprecated fields.
