# INITIAL.md — C-024..C-027: Annuity Performance (规模明细) — Real Sample E2E Pilot

This INITIAL defines a focused, high‑signal DoR for implementing an end‑to‑end pilot of the real business domain “Annuity Performance (规模明细)”. It follows the PRP workflow and the repo’s existing patterns so Claude can deliver the feature in one pass with validation.

---

## FEATURE
Add a real‑sample E2E pipeline for “Annuity Performance (规模明细)” using files under `reference/monthly/数据采集/V*/...`, selecting the highest `V*` version per month, reading sheet `规模明细`, transforming to match the real Chinese table/column schema from `reference/db_migration/db_structure.json` (lines 1444–1715), and loading into Postgres (plan‑only & execute), with opt‑in tests and docs.

## SCOPE
- In‑scope:
  - Add `annuity_performance` domain to `data_sources.yml` (regex + selection + sheet)
  - Implement connector selection strategy: `latest_by_year_month_and_version`
- Generate Postgres DDL from JSON (Chinese table + columns + indexes + FKs): `scripts/dev/annuity_performance_real.sql` (see below)
  - Add opt‑in smoke/E2E tests with marker `legacy_data` (discovery, plan‑only, optional execute)
  - Update README with a “Real Sample Smoke (Annuity Performance)” section
- Non‑goals:
  - Full legacy parity or complex data cleansing rules (follow‑ups)
  - CI changes; tests must be opt‑in only
  - Migration of additional domains

## CONTEXT SNAPSHOT
```bash
reference/monthly/数据采集/
  V1/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx
  V2/...

src/work_data_hub/
  config/
    data_sources.yml             # add annuity_performance domain
  io/connectors/file_connector.py# extend selection strategy
  orchestration/                 # jobs/ops already in place
  io/loader/warehouse_loader.py  # stable transactional loader

scripts/dev/
  annuity_performance.sql        # new DDL

tests/legacy/
  test_annuity_performance_smoke.py  # new, @pytest.mark.legacy_data
```

## EXAMPLES
- Path: `scripts/create_table/trustee_performance.sql` — DDL style (English table + optional Chinese view, JSONB columns)
- Path: `tests/smoke/test_monthly_data_smoke.py` — pattern for opt‑in, local‑only tests
- Path: `src/work_data_hub/io/connectors/file_connector.py` — extend selection logic (month post‑processing exists); follow its style for new strategy

## DOCUMENTATION
- File: `PRPs/templates/INITIAL.template.md` — template followed by this DoR
- File: `README.md` — add “Real Sample Smoke (Annuity Performance)” steps
- File: `ROADMAP.md` — tasks C‑024..C‑027

## INTEGRATION POINTS
- Config: `data_sources.yml` add domain with regex + sheet + table + pk + selection
- Connector: `file_connector.py` add strategy `latest_by_year_month_and_version`
- Database: new DDL `scripts/dev/annuity_performance_real.sql` generated from `reference/db_migration/db_structure.json` (Chinese identifiers, with indexes and foreign keys)
- Jobs/CLI: reuse existing `jobs.py`/`ops.py` (plan‑only vs execute, `--max-files`)
- Tests: new opt‑in marker `legacy_data` in `pyproject.toml`; tests under `tests/legacy/`

## DATA CONTRACTS (schemas & payloads)
Target schema must be generated from the real JSON spec (Chinese identifiers). Do not hand‑code a reduced English schema for this pilot. Use a generator to convert MySQL‑style metadata to Postgres DDL with quoted identifiers.

DDL generation requirements:
- Input: `reference/db_migration/db_structure.json`, segment for 规模明细 (lines 1444–1715)
- Output: `scripts/dev/annuity_performance_real.sql`
- Behavior:
  - Preserve Chinese table and column names; quote identifiers: "表名"."列名"
  - Map types: VARCHAR/TEXT direct; DATE/TIMESTAMP; DOUBLE→`double precision` (or `numeric(p,s)` when precision is explicit); TINYINT→`boolean` (when semantic flag) else `smallint`
  - Drop MySQL COLLATE; ensure UTF‑8
  - Create PRIMARY KEY, UNIQUE/INDEXES, and FOREIGN KEYS as defined
  - Order DDL so referenced tables exist before FKs; if not feasible locally, emit FKs as a second phase (or guarded by a flag)

`data_sources.yml` — new domain (annuity_performance):
```yaml
domains:
  annuity_performance:
    description: "Annuity performance (规模明细) real sample"
    # Examples under 数据采集/V*/: "24年11月年金终稿数据*.xlsx"
    pattern: "(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\\.(xlsx|xlsm)$"
    select: "latest_by_year_month_and_version"
    sheet: "规模明细"
    # Use the real Chinese physical table name exactly as in DDL/JSON
    table: "规模明细"
    # PK will come from the generated DDL; do not override unless needed for loader planning
```

Connector selection semantics:
- Group by (year, month). Within a group, prefer file whose parent directory (under `数据采集`) is `V<max>`; if no `V*`, fallback to latest mtime.
- Post‑process 2‑digit `year` → 2000 + year (e.g., 24 -> 2024).
- Keep month post‑processing for 10/11/12 disambiguation.

Pseudocode in `file_connector.py`:
```python
version = None
parent = Path(file_path).parent
if parent.name and parent.name.upper().startswith("V") and parent.parent.name == "数据采集":
    try:
        version = int(parent.name[1:])
    except ValueError:
        version = None
# After discovery, group by (year, month) and select max by (version, mtime)
if len(str(year)) == 2:  # normalize 2-digit year
    year = 2000 + int(year)
```

## GOTCHAS & LIBRARY QUIRKS
- Filenames use Chinese and two‑digit years; capture groups must be Unicode‑aware; normalize years
- Version directory `V*` only when higher parent is exactly `数据采集`
- Sheet name is Chinese (`规模明细`); read by name
- Loader expects JSONB adaptation (already in place)
- Tests must be opt‑in; do not enable in CI by default

## IMPLEMENTATION NOTES
- Follow connector style (pattern compilation, logging, fallbacks) in `file_connector.py`
- Keep changes minimal; do not refactor unrelated code
- Generate DDL to `scripts/dev/annuity_performance_real.sql` from JSON (see generator notes)
- Tests: `tests/legacy/test_annuity_performance_smoke.py` with `@pytest.mark.legacy_data` and skip when sample/DB missing
- Marker in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
    "legacy_data: tests requiring real local samples under reference/monthly (opt-in)",
  ]
  ```

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Local, opt-in smoke (requires local sample & DB)
uv run pytest -m legacy_data -v

# Plan-only first to validate mapping; enable execute after column projection aligns with the real table
```

## ACCEPTANCE CRITERIA
- [ ] Discovery selects only the highest `V*` version file within the same `数据采集` directory and month
- [ ] Plan‑only run generates DELETE + INSERT plans targeting `annuity_performance`
- [ ] Execute run (local Postgres) inserts rows and prints deleted/inserted/batches (after ensuring transformation output projects only columns defined in the Chinese table)
- [ ] DDL script `scripts/dev/annuity_performance_real.sql` applies successfully locally (with indexes & FKs or staged FK application)
- [ ] README updated with “Real Sample Smoke (Annuity Performance)” steps
- [ ] Tests are opt‑in and skipped by default in CI

## ROLLOUT & RISK
- Rollout: local‑only pilot; no CI changes; no production migrations
- Risk: filename variants; mitigate with tolerant regex and fallbacks
- Risk: schema drift; contain via minimal DDL and iterative refinement

## APPENDICES
Test skeleton (tests/legacy/test_annuity_performance_smoke.py):
```python
import os
import pytest
from pathlib import Path
from src.work_data_hub.io.connectors.file_connector import DataSourceConnector

pytestmark = pytest.mark.legacy_data

def _has_sample_root() -> bool:
    return Path("reference/monthly").exists()

def test_discovery_latest_version_selected():
    if not _has_sample_root():
        pytest.skip("Local samples not present")
    os.environ["WDH_DATA_BASE_DIR"] = "./reference/monthly"
    connector = DataSourceConnector()
    files = connector.discover("annuity_performance")
    assert isinstance(files, list)
    assert len(files) >= 1  # at least one selected

def test_plan_only_smoke():
    if not _has_sample_root():
        pytest.skip("Local samples not present")
    os.environ["WDH_DATA_BASE_DIR"] = "./reference/monthly"
    # Optional: import CLI job and run plan-only with --max-files 1
```
