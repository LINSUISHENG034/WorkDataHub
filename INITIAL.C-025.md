# INITIAL.md — C-025: Annuity Performance (规模明细) — Discovery Config & Versioned Selection

This INITIAL defines the discovery configuration and version-aware selection for the real “Annuity Performance (规模明细)” samples under `reference/monthly/数据采集/V*/...`, selecting the highest `V*` within the same month directory.

---

## FEATURE
Configure `annuity_performance` in `data_sources.yml` and implement `latest_by_year_month_and_version` selection in the connector to pick `V*` largest version under the `数据采集` directory for the same (year, month).

## SCOPE
- In-scope:
  - Add `annuity_performance` domain to `data_sources.yml` with pattern, select, sheet, and table
  - Implement selection strategy `latest_by_year_month_and_version` in `file_connector.py`
  - Normalize two-digit years (e.g., 24 → 2024) and keep month post-processing (10/11/12)
  - Unit tests verifying version selection and grouping by (year, month)
- Non-goals:
  - No DDL generation
  - No pipeline read/transform/load integration yet

## CONTEXT SNAPSHOT
```bash
reference/monthly/数据采集/
  V1/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx
  V2/...

src/work_data_hub/io/connectors/file_connector.py
src/work_data_hub/config/data_sources.yml
```

## EXAMPLES
- Path: `src/work_data_hub/io/connectors/file_connector.py` — follow style for pattern compilation and selection
- Snippet (pseudocode):
```python
def _scan_directory_for_domain(...):
    # existing logic + extract version from parent when parent.parent.name == "数据采集"
    parent = Path(file_path).parent
    version = None
    if parent.name.upper().startswith("V") and parent.parent.name == "数据采集":
        try:
            version = int(parent.name[1:])
        except ValueError:
            version = None
    # year/month capture + normalize two-digit year → 2000 + year

def _apply_selection_strategies(files):
    # group by (year, month)
    # within group, pick max by (version, mtime); if version is None, fallback mtime
```

## DOCUMENTATION
- File: `PRPs/templates/INITIAL.template.md` — template followed by this DoR
- File: `README.md` — ensure marker docs keep CI opt-in behavior (no changes beyond this stage)

## INTEGRATION POINTS
- `data_sources.yml` — add `annuity_performance` domain:
```yaml
domains:
  annuity_performance:
    description: "Annuity performance (规模明细) real sample"
    pattern: "(?P<year>\d{2}|20\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\\.(xlsx|xlsm)$"
    select: "latest_by_year_month_and_version"
    sheet: "规模明细"
    table: "规模明细"
```
- `file_connector.py` — implement new selection and normalization logic
- Tests: `tests/legacy/test_annuity_performance_discovery.py` (unit-like), `@pytest.mark.legacy_data` smoke

## DATA CONTRACTS
N/A (discovery only).

## GOTCHAS & LIBRARY QUIRKS
- Unicode paths and filenames; ensure regex compiles with `re.UNICODE`
- Two-digit years (24) must be normalized to 2024
- Selection must group by (year, month); only pick one file per group (highest V, then mtime)

## IMPLEMENTATION NOTES
- Keep logic additive; do not break existing strategies
- Ensure logs clearly show chosen version and reason
- Provide safe fallbacks when regex groups are missing (fallback mtime)

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k annuity_performance_discovery
uv run pytest -m legacy_data -v -k discovery  # opt-in local smoke
```

## ACCEPTANCE CRITERIA
- [ ] `annuity_performance` domain present in `data_sources.yml`
- [ ] Connector selects the highest `V*` version within (year, month); when no `V*`, falls back to latest mtime
- [ ] Two-digit year normalization is applied
- [ ] Unit tests for grouping and selection pass

## ROLLOUT & RISK
- No pipeline/DDL impact; safe to land incrementally

## APPENDICES
```python
# tests/legacy/test_annuity_performance_discovery.py (outline)
import os, pytest
from pathlib import Path
from src.work_data_hub.io.connectors.file_connector import DataSourceConnector

def test_latest_version_per_month(tmp_path, monkeypatch):
    # build 数据采集/V1 and V2 structure with fake files "24年11月年金终稿数据...xlsx"
    # set WDH_DATA_BASE_DIR to tmp_path and assert only V2 is returned
    assert True
```

