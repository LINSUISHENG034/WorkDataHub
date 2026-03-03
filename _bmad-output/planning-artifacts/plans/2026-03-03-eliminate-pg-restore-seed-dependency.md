# Eliminate pg_restore Seed Dependency & Clean Up Seeds Directory

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the external `pg_restore` dependency from seed data loading so `alembic upgrade head` works on fresh environments without PostgreSQL client tools, and separate business backup data from seed data.

**Architecture:** Replace `.dump` format seed files (which require `pg_restore`) with `.csv` format (loaded by pure Python). Export `base_info` and `enrichment_index` from the dev database as CSV, place them in `config/seeds/003/`, then strip all dump-related code from the migration and library modules. Move misplaced business data backups out of `config/seeds/`.

**Tech Stack:** Python 3.12, psycopg (v3), SQLAlchemy, Alembic, pytest

---

## Pre-Requisites

- Access to the development PostgreSQL database (credentials in `.wdh_env`)
- `psycopg` (v3) installed (`uv sync` should cover this)
- The tables `enterprise.base_info` and `enterprise.enrichment_index` must contain current data in the dev DB

---

### Task 1: Create CSV export script for base_info and enrichment_index

**Files:**
- Create: `scripts/seed_data/export_seed_csv.py`

**Step 1: Write the export script**

This script uses psycopg v3's `COPY ... TO STDOUT` protocol to export tables as CSV — no external tools needed.

```python
"""Export seed tables as CSV using psycopg v3 (pure Python, no pg_dump needed).

Usage:
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py

    # Export to custom directory
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py \
        --output-dir config/seeds/003

    # Export specific table
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py \
        --tables enterprise.base_info
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from work_data_hub.config import get_settings


# Default tables to export as seed CSV
DEFAULT_TABLES: list[tuple[str, str]] = [
    ("enterprise", "base_info"),
    ("enterprise", "enrichment_index"),
]


def get_connection_string() -> str:
    """Get psycopg v3 connection string from project settings."""
    settings = get_settings()
    url = settings.get_database_connection_string()
    # Ensure we use plain postgresql:// for psycopg v3
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def export_table_to_csv(conn_string: str, schema: str, table: str, output_path: Path) -> int:
    """Export a single table to CSV using psycopg v3 COPY protocol.

    Args:
        conn_string: PostgreSQL connection string
        schema: Schema name
        table: Table name
        output_path: Output CSV file path

    Returns:
        Number of bytes written
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            # Get row count first
            cur.execute(f'SELECT COUNT(*) FROM {schema}."{table}"')
            row_count = cur.fetchone()[0]

            # Export using COPY protocol (binary streaming, no external tools)
            with open(output_path, "wb") as f:
                with cur.copy(
                    f'COPY {schema}."{table}" TO STDOUT WITH (FORMAT CSV, HEADER true, ENCODING \'UTF8\')'
                ) as copy:
                    for block in copy:
                        f.write(block)

    file_size = output_path.stat().st_size
    print(f"  {schema}.{table}: {row_count:,} rows, {file_size:,} bytes -> {output_path}")
    return file_size


def parse_table_identifier(table_id: str) -> tuple[str, str]:
    """Parse 'schema.table' identifier."""
    if "." not in table_id:
        raise ValueError(f"Invalid format: {table_id}. Use schema.table")
    schema, table = table_id.split(".", 1)
    return schema, table.strip('"')


def main() -> int:
    parser = argparse.ArgumentParser(description="Export seed tables as CSV")
    parser.add_argument(
        "--output-dir",
        default=Path("config/seeds/003"),
        type=Path,
        help="Output directory (default: config/seeds/003)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help='Tables in "schema.table" format (default: base_info + enrichment_index)',
    )
    args = parser.parse_args()

    tables = (
        [parse_table_identifier(t) for t in args.tables]
        if args.tables
        else DEFAULT_TABLES
    )

    conn_string = get_connection_string()
    print(f"Exporting {len(tables)} table(s) as CSV to {args.output_dir}/\n")

    for schema, table in tables:
        output_path = args.output_dir / f"{table}.csv"
        export_table_to_csv(conn_string, schema, table, output_path)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Commit**

```bash
git add scripts/seed_data/export_seed_csv.py
git commit -m "feat(seeds): add pure-Python CSV export script for seed tables"
```

---

### Task 2: Export base_info and enrichment_index as CSV

**Files:**
- Create: `config/seeds/003/base_info.csv` (from DB export)
- Create: `config/seeds/003/enrichment_index.csv` (from DB export)

> **Note:** `config/seeds/` is in `.gitignore` — these files are local deployment artifacts, not committed to git.

**Step 1: Run the export script**

```bash
PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py
```

Expected output:
```
Exporting 2 table(s) as CSV to config/seeds/003/

  enterprise.base_info: 27,535 rows, ~XXX bytes -> config/seeds/003/base_info.csv
  enterprise.enrichment_index: ~44,891 rows, ~XXX bytes -> config/seeds/003/enrichment_index.csv

Done.
```

**Step 2: Verify the CSV files are valid**

```bash
# Check file existence and header row
head -1 config/seeds/003/base_info.csv
head -1 config/seeds/003/enrichment_index.csv

# Check row counts (subtract 1 for header)
wc -l config/seeds/003/base_info.csv
wc -l config/seeds/003/enrichment_index.csv
```

Expected: Both files have headers and the expected row counts.

**Step 3: Spot-check JSONB field in base_info CSV**

`base_info` has JSONB columns (`raw_data`, `raw_business_info`, `raw_biz_label`). Verify they are properly quoted in CSV:

```bash
# Show a sample row (second line) — JSON values should be double-quote escaped
PYTHONPATH=src uv run python -c "
import csv
with open('config/seeds/003/base_info.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    row = next(reader)
    for col in ['raw_data', 'raw_business_info', 'raw_biz_label']:
        if col in row:
            val = row[col]
            print(f'{col}: type={type(val).__name__}, len={len(val) if val else 0}, preview={val[:80] if val else \"NULL\"}...')
"
```

Expected: JSON values are plain strings, parseable by Python's json module.

---

### Task 3: Simplify migration 003 — remove all dump-related code

**Files:**
- Modify: `io/schema/migrations/versions/003_seed_static_data.py`

**Step 1: Remove unused imports and dump-related code**

Remove these elements from `003_seed_static_data.py`:

1. **Imports to remove** (lines 26-28):
   - `import enum`
   - `import os`
   - `import subprocess`

2. **Classes/constants to remove**:
   - `class _SeedFormat` (lines 35-43)
   - `_SEED_FORMAT_PRIORITY` (line 47)

3. **Functions to remove**:
   - `_resolve_seed_file()` (lines 113-155) — format-aware resolver, no longer needed
   - `_load_dump_seed_data()` (lines 234-281) — pg_restore caller
   - `_load_seed_data()` (lines 284-313) — format dispatcher

4. **Change upgrade() calls for base_info and enrichment_index** (lines 438-445):

   Replace:
   ```python
   # === 11. base_info (27,535 rows - uses pg_dump format for JSON fields) ===
   if _table_exists(conn, "base_info", "enterprise"):
       count = _load_seed_data(conn, "base_info", "enterprise")
       print(f"Seeded {count} rows into enterprise.base_info")

   # === 12. enrichment_index (32,052 rows - format auto-detected) ===
   if _table_exists(conn, "enrichment_index", "enterprise"):
       count = _load_seed_data(conn, "enrichment_index", "enterprise")
       print(f"Seeded {count} rows into enterprise.enrichment_index")
   ```

   With:
   ```python
   # === 11. base_info (27,535 rows - CSV, JSONB fields auto-cast) ===
   if _table_exists(conn, "base_info", "enterprise"):
       count = _load_csv_seed_data(
           conn, "base_info.csv", "base_info", "enterprise"
       )
       print(f"Seeded {count} rows into enterprise.base_info")

   # === 12. enrichment_index (44,891 rows - CSV) ===
   if _table_exists(conn, "enrichment_index", "enterprise"):
       count = _load_csv_seed_data(
           conn, "enrichment_index.csv", "enrichment_index", "enterprise"
       )
       print(f"Seeded {count} rows into enterprise.enrichment_index")
   ```

5. **Update module docstring** to remove mention of pg_dump format.

**After this step, the file should only import:** `csv`, `Path`, `sa`, `op`.

**Step 2: Verify the file has no dump references**

```bash
# Must return zero matches
grep -c "dump\|pg_restore\|subprocess\|_SeedFormat\|_resolve_seed_file\|_load_dump\|_load_seed_data" io/schema/migrations/versions/003_seed_static_data.py
```

Expected: `0`

**Step 3: Verify Python syntax**

```bash
PYTHONPATH=src uv run python -c "import ast; ast.parse(open('io/schema/migrations/versions/003_seed_static_data.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

**Step 4: Commit**

```bash
git add io/schema/migrations/versions/003_seed_static_data.py
git commit -m "refactor(migration): remove pg_restore dependency from seed loading

base_info and enrichment_index now load from CSV like all other seed
tables. Removes _SeedFormat, _resolve_seed_file, _load_dump_seed_data,
and related imports (enum, os, subprocess)."
```

---

### Task 4: Verify migration works end-to-end

> **Note:** This task requires a fresh (or downgradeable) database. If testing on a dev DB with existing data, run downgrade first.

**Step 1: Run downgrade to clear seed data**

```bash
PYTHONPATH=src uv run alembic -c io/schema/alembic.ini downgrade 20251228_000002
```

Expected: Seed data tables truncated.

**Step 2: Run upgrade to re-seed from CSV**

```bash
PYTHONPATH=src uv run alembic -c io/schema/alembic.ini upgrade head
```

Expected output should include:
```
Loading seed data from: .../config/seeds
Seeded 104 rows into enterprise.company_types_classification
...
Seeded XXXXX rows into enterprise.base_info
Seeded XXXXX rows into enterprise.enrichment_index
```

No `pg_restore not found` warnings.

**Step 3: Verify row counts**

```bash
PYTHONPATH=src uv run python -c "
from work_data_hub.config import get_settings
from sqlalchemy import create_engine, text
settings = get_settings()
engine = create_engine(settings.get_database_connection_string())
with engine.connect() as conn:
    for schema, table in [('enterprise', 'base_info'), ('enterprise', 'enrichment_index')]:
        result = conn.execute(text(f'SELECT COUNT(*) FROM {schema}.\"{table}\"'))
        print(f'{schema}.{table}: {result.scalar():,} rows')
"
```

Expected: Both tables have data (base_info ~27,535 rows, enrichment_index ~44,891 rows).

**Step 4: Spot-check JSONB data integrity in base_info**

```bash
PYTHONPATH=src uv run python -c "
from work_data_hub.config import get_settings
from sqlalchemy import create_engine, text
settings = get_settings()
engine = create_engine(settings.get_database_connection_string())
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT COUNT(*) FROM enterprise.base_info
        WHERE raw_data IS NOT NULL AND jsonb_typeof(raw_data) = \'object\'
    '''))
    print(f'base_info rows with valid JSONB raw_data: {result.scalar():,}')
"
```

Expected: Non-zero count — JSONB fields survived the CSV round-trip.

---

### Task 5: Move business data backups out of seeds directory

**Files:**
- Move: `config/seeds/002/customer_plan_contract.dump` -> `data/backups/customer_plan_contract.dump`
- Move: `config/seeds/002/收入明细.dump` -> `data/backups/收入明细.dump`
- Move: `config/seeds/002/规模明细.dump` -> `data/backups/规模明细.dump`

> **Note:** `data/*` is already in `.gitignore` (except `data/mappings/`), so `data/backups/` is auto-ignored. No `.gitignore` changes needed.

**Step 1: Create backups directory and move files**

```bash
mkdir -p data/backups
mv config/seeds/002/customer_plan_contract.dump data/backups/
mv "config/seeds/002/收入明细.dump" "data/backups/收入明细.dump"
mv "config/seeds/002/规模明细.dump" "data/backups/规模明细.dump"
```

**Step 2: Verify moves**

```bash
ls -la data/backups/
ls -la config/seeds/002/
```

Expected:
- `data/backups/` contains the 3 `.dump` files
- `config/seeds/002/` only contains `base_info.dump`, `enrichment_index.dump`, `客户明细.csv`

> **Note:** The old `.dump` files for base_info and enrichment_index in `config/seeds/002/` can stay — they won't be loaded because `config/seeds/003/` has higher-priority CSV files. Removing them is optional cleanup.

---

### Task 6: Update config/seeds/README.md

**Files:**
- Modify: `config/seeds/README.md`

**Step 1: Update README to reflect CSV-only approach**

Key changes:
1. Remove all references to `.dump` format and `pg_dump`/`pg_restore`
2. Remove format priority table (only CSV now)
3. Update the version status table to show v003 CSV files
4. Replace `export_seed_dump.py` reference with `export_seed_csv.py`
5. Note that business data backups have been moved to `data/backups/`

Update the directory structure section to:

```markdown
### 1.1 版本管理机制

种子数据采用版本化管理，CSV 格式，每个文件独立解析到最高版本：

config/seeds/
├── 001/                              # 版本 1 (初始数据)
│   ├── enrichment_index.csv
│   ├── 客户明细.csv
│   └── ...
├── 002/                              # 版本 2 (客户明细更新)
│   └── 客户明细.csv
├── 003/                              # 版本 3 (base_info/enrichment_index CSV化)
│   ├── base_info.csv
│   └── enrichment_index.csv
└── README.md
```

Update the version status table:

```markdown
| 文件 | v001 | v002 | v003 | 使用版本 | 格式 |
|------|------|------|------|----------|------|
| base_info | - | - | 27,535 行 | v003 | csv |
| enrichment_index | 32,052 行 | - | ~44,891 行 | v003 | csv |
| 客户明细 | 9,822 行 | 10,306 行 | - | v002 | csv |
```

Remove the "格式优先级" section entirely.

Update section 3.2 to reference the new export script:

```markdown
### 3.2 版本 003 数据导出 (2026-03-03)

**v003 使用纯 Python CSV 导出**，消除 pg_dump/pg_restore 外部工具依赖：

**导出脚本**: `scripts/seed_data/export_seed_csv.py`

    PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py
```

**Step 2: Commit**

```bash
git add config/seeds/README.md
git commit -m "docs(seeds): update README for CSV-only approach (no more pg_dump)"
```

---

### Task 7: Simplify seed_resolver.py — remove DUMP format support

**Files:**
- Modify: `src/work_data_hub/io/schema/seed_resolver.py`
- Test: `tests/unit/io/schema/test_seed_resolver.py`

**Step 1: Write a failing test that asserts SeedFormat.DUMP no longer exists**

Add to `tests/unit/io/schema/test_seed_resolver.py`:

```python
class TestCsvOnlyFormat:
    """Tests verifying dump format support has been removed."""

    def test_seed_format_has_no_dump(self) -> None:
        """SeedFormat should only have CSV after dump removal."""
        from work_data_hub.io.schema.seed_resolver import SeedFormat

        assert list(SeedFormat) == [SeedFormat.CSV]
        assert not hasattr(SeedFormat, "DUMP")
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=src uv run pytest tests/unit/io/schema/test_seed_resolver.py::TestCsvOnlyFormat -v
```

Expected: FAIL (SeedFormat.DUMP still exists)

**Step 3: Simplify seed_resolver.py**

1. Remove `SeedFormat.DUMP` from the enum (keep only `CSV`)
2. Remove `SEED_FORMAT_PRIORITY` list (only one format, no priority needed)
3. Simplify `_find_table_files_in_version()` — only check for `.csv`
4. Simplify `resolve_seed_file()` — no format priority logic needed
5. Remove `import enum` if no longer needed (but SeedFormat still uses enum, so keep it)

After simplification, `SeedFormat` should be:

```python
class SeedFormat(enum.Enum):
    """Supported seed data formats."""

    CSV = "csv"

    @property
    def extension(self) -> str:
        """Get file extension for this format."""
        return f".{self.value}"
```

And `_find_table_files_in_version` simplifies to:

```python
def _find_table_files_in_version(
    seeds_base_dir: Path, version: str, table_name: str
) -> Optional[tuple[Path, SeedFormat]]:
    """Find CSV file for a table in a specific version directory."""
    version_dir = seeds_base_dir / version
    if not version_dir.exists():
        return None

    file_path = version_dir / f"{table_name}.csv"
    if file_path.exists():
        return (file_path, SeedFormat.CSV)

    return None
```

> **Note:** The return type changes from `List[tuple]` to `Optional[tuple]`. Update `resolve_seed_file()` accordingly.

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=src uv run pytest tests/unit/io/schema/test_seed_resolver.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/io/schema/seed_resolver.py tests/unit/io/schema/test_seed_resolver.py
git commit -m "refactor(seed-resolver): remove DUMP format, CSV-only"
```

---

### Task 8: Simplify seed_loader.py — remove dump loading code

**Files:**
- Modify: `src/work_data_hub/io/schema/seed_loader.py`

**Step 1: Remove dump-related code from seed_loader.py**

1. Remove `import subprocess` (line 16)
2. Remove `_load_dump_seed_data()` function (lines 88-148)
3. Simplify `load_seed_data()` — remove the `SeedFormat.DUMP` branch (lines 187-188)
4. Remove `SeedFormat` import if no longer used by `load_seed_data()` — actually it's still used to check `seed_info.format == SeedFormat.CSV`, but after removing DUMP, the format check can be simplified or removed.

After simplification, `load_seed_data()` becomes:

```python
def load_seed_data(
    conn: Connection,
    table_name: str,
    schema: str,
    seeds_base_dir: Path,
    exclude_columns: Optional[list[str]] = None,
    version: Optional[str] = None,
) -> int:
    """Load seed data for a table from CSV.

    Args:
        conn: SQLAlchemy connection
        table_name: Target table name
        schema: Target schema name
        seeds_base_dir: Path to seeds base directory
        exclude_columns: Columns to exclude
        version: Optional explicit version override

    Returns:
        Number of rows loaded

    Raises:
        FileNotFoundError: If no seed CSV found
    """
    seed_info = resolve_seed_file(table_name, seeds_base_dir, version)

    if seed_info is None or not seed_info.exists:
        raise FileNotFoundError(f"No seed CSV found for {table_name}")

    return _load_csv_seed_data(
        conn, seed_info.path, table_name, schema, exclude_columns
    )
```

**Step 2: Verify no dump references remain**

```bash
grep -c "dump\|pg_restore\|subprocess" src/work_data_hub/io/schema/seed_loader.py
```

Expected: `0`

**Step 3: Run existing tests**

```bash
PYTHONPATH=src uv run pytest tests/unit/io/schema/ -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add src/work_data_hub/io/schema/seed_loader.py
git commit -m "refactor(seed-loader): remove pg_restore/dump loading code"
```

---

### Task 9: Clean up export_seed_dump.py

**Files:**
- Delete: `scripts/seed_data/export_seed_dump.py`

**Step 1: Verify no code imports or references this script**

```bash
grep -r "export_seed_dump" --include="*.py" src/ tests/ scripts/ io/
```

Expected: No hits in executable code (may appear in docs/README only).

**Step 2: Delete the script**

```bash
rm scripts/seed_data/export_seed_dump.py
```

**Step 3: Commit**

```bash
git add -u scripts/seed_data/export_seed_dump.py
git commit -m "chore: remove export_seed_dump.py (replaced by export_seed_csv.py)"
```

---

### Task 10: Run full test suite to verify no regressions

**Step 1: Run unit tests**

```bash
PYTHONPATH=src uv run pytest tests/unit/ -v --tb=short
```

Expected: ALL PASS

**Step 2: Run linter**

```bash
uv run ruff check src/work_data_hub/io/schema/seed_resolver.py src/work_data_hub/io/schema/seed_loader.py io/schema/migrations/versions/003_seed_static_data.py
```

Expected: No errors

**Step 3: Final commit (if any lint fixes needed)**

```bash
git add -A
git commit -m "chore: lint fixes after seed refactor"
```

---

## Summary of Changes

| File | Action | Task |
|------|--------|------|
| `scripts/seed_data/export_seed_csv.py` | **CREATE** | 1 |
| `config/seeds/003/base_info.csv` | **CREATE** (local only, gitignored) | 2 |
| `config/seeds/003/enrichment_index.csv` | **CREATE** (local only, gitignored) | 2 |
| `io/schema/migrations/versions/003_seed_static_data.py` | **MODIFY** (remove dump code) | 3 |
| `config/seeds/002/{3 business dumps}` | **MOVE** to `data/backups/` | 5 |
| `config/seeds/README.md` | **MODIFY** | 6 |
| `src/work_data_hub/io/schema/seed_resolver.py` | **MODIFY** (remove DUMP format) | 7 |
| `tests/unit/io/schema/test_seed_resolver.py` | **MODIFY** (add CSV-only test) | 7 |
| `src/work_data_hub/io/schema/seed_loader.py` | **MODIFY** (remove dump loader) | 8 |
| `scripts/seed_data/export_seed_dump.py` | **DELETE** | 9 |

## Out of Scope

- **Global psycopg v3 migration** (Problem 1 in the code smell doc): The current fix in `env.py` covers Alembic. A full project migration from psycopg2 to psycopg v3 is a separate, larger effort.
- **COPY FROM optimization**: For future bulk loading needs (e.g., 625K row `规模明细`), use psycopg3's `cursor.copy()` with `COPY FROM STDIN`. Not needed for current seed sizes.
