# INITIAL.md — C-024: Annuity Performance (规模明细) — Real-Sample E2E Skeleton & Marker

This INITIAL defines a minimal, opt-in test skeleton to enable local, real-sample validation for the “Annuity Performance (规模明细)” pilot without touching discovery/DDL/pipeline logic yet. It prepares a safe runway for following stages.

---

## FEATURE
Add an opt-in test scaffold and docs for running real-sample smoke tests for the “Annuity Performance (规模明细)” domain locally. No connector/DDL/pipeline changes in this stage.

## SCOPE
- In-scope:
  - Add pytest marker `legacy_data` (opt-in only)
  - Create smoke test skeleton under `tests/legacy/` with robust skip conditions
  - Update README with a “Real Sample Smoke (Annuity Performance)” quickstart (env vars + commands)
- Non-goals:
  - No changes to discovery/connector/DDL or pipeline integration
  - No CI changes (marker must be skipped by default)

## CONTEXT SNAPSHOT
```bash
reference/monthly/数据采集/
  V1/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx

src/work_data_hub/
  ...

tests/legacy/
  test_annuity_performance_smoke.py  # new, @pytest.mark.legacy_data
```

## EXAMPLES
- Path: `tests/smoke/test_monthly_data_smoke.py` — pattern for opt-in, local-only smoke tests
- Snippet:
```python
pytestmark = pytest.mark.legacy_data
def test_discovery_smoke():
    if not Path("reference/monthly").exists():
        pytest.skip("Local samples not present")
    # Will exercise in later stages when domain is wired
```

## DOCUMENTATION
- File: `PRPs/templates/INITIAL.template.md` — template followed by this DoR
- File: `README.md` — add a concise “Real Sample Smoke (Annuity Performance)” section (env vars + commands)

## INTEGRATION POINTS
- `pyproject.toml` — add pytest marker `legacy_data`
- `tests/legacy/test_annuity_performance_smoke.py` — skeleton with skip conditions
- `README.md` — add quickstart section

## DATA CONTRACTS
N/A in this stage (no DDL or schema integration yet).

## GOTCHAS & LIBRARY QUIRKS
- Tests must be opt-in; do not enable by default in CI
- Use robust skip conditions (no sample root / no DB / no psycopg2)
- Windows paths and Unicode filenames are common; avoid hard-coded separators

## IMPLEMENTATION NOTES
- Keep the test light: discovery placeholder and plan-only placeholder assertions guarded by skip
- Set `WDH_DATA_BASE_DIR=./reference/monthly` in examples; do not hardcode in tests

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
uv run pytest -m legacy_data -v  # locally, opt-in
```

## ACCEPTANCE CRITERIA
- [ ] `legacy_data` marker exists in `pyproject.toml`
- [ ] `tests/legacy/test_annuity_performance_smoke.py` present with robust skip conditions
- [ ] README contains a minimal “Real Sample Smoke (Annuity Performance)” section
- [ ] CI unaffected (marker skipped by default)

## ROLLOUT & RISK
- No production or CI impact; local-only opt-in smoke

## APPENDICES
```python
# tests/legacy/test_annuity_performance_smoke.py (skeleton)
import os, pytest
from pathlib import Path

pytestmark = pytest.mark.legacy_data

def _has_sample_root() -> bool:
    return Path("reference/monthly").exists()

def test_discovery_smoke():
    if not _has_sample_root():
        pytest.skip("Local samples not present")
    os.environ["WDH_DATA_BASE_DIR"] = "./reference/monthly"
    # Discovery/pipeline will be exercised in later stages
    assert True
```

