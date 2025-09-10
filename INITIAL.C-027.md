# INITIAL.md — C-027: Annuity Performance (规模明细) — Plan-only & Execute Integration

This INITIAL defines the plan-only and execute integration for the “Annuity Performance (规模明细)” domain using the real Chinese table/columns produced in C‑026, with safe column projection and opt-in tests.

---

## FEATURE
Wire the domain into the existing pipeline (jobs/ops) to support plan-only and limited execute runs against the real Chinese table `"规模明细"` in Postgres. Include column projection to avoid column mismatches.

## SCOPE
- In-scope:
  - Add domain integration (discovery already available from C‑025)
  - Read Excel sheet `规模明细` by name
  - Minimal transformation: map/normalize only what is necessary (e.g., 年/月 → report_date if needed), otherwise keep Chinese columns intact
  - Column projection: ensure rows passed to loader only include columns defined in the Chinese table
  - Plan-only: generate DELETE + INSERT plans
  - Execute: small-scope run (`--max-files 1`) inserting into `"规模明细"`
  - Opt-in tests under `tests/legacy/`
- Non-goals:
  - Complex cleansing/validations (follow-up); keep MVP minimal and safe

## CONTEXT SNAPSHOT
```bash
scripts/dev/annuity_performance_real.sql      # real Chinese DDL from C‑026

src/work_data_hub/
  orchestration/jobs.py                       # reuse CLI
  orchestration/ops.py                        # plan-only/execute loading
  io/loader/warehouse_loader.py               # stable loader
  config/data_sources.yml                     # domain config present from C‑025

tests/legacy/
  test_annuity_performance_e2e.py             # new, opt-in
```

## EXAMPLES
- Path: `src/work_data_hub/orchestration/jobs.py` — CLI usage `--domain`, `--plan-only/--execute`, `--max-files`
- Path: `src/work_data_hub/orchestration/ops.py` — plan-only vs execute logic
- Snippet (projection):
```python
def project_columns(rows, allowed_cols):
    out = []
    for r in rows:
        out.append({k: r.get(k) for k in allowed_cols})
    return out
```

## DOCUMENTATION
- File: `PRPs/templates/INITIAL.template.md` — DoR template
- README — extend “Real Sample Smoke (Annuity Performance)” with execute steps

## INTEGRATION POINTS
- `data_sources.yml` — table: `"规模明细"`, sheet: `规模明细` (already set)
- `jobs.py/ops.py` — use the existing flow and return plans; re-use loader
- Column projection — whitelist derived from the Chinese DDL (hardcode for MVP or load from a small manifest under `scripts/dev/`)

## DATA CONTRACTS
- Chinese table/columns from C‑026 are the source of truth; loader should receive only these columns
- JSONB fields are allowed (e.g., `validation_warnings`, `metadata`) — adapter already present in loader

## GOTCHAS & LIBRARY QUIRKS
- Chinese identifiers must be quoted by loader/SQL builders (already handled)
- Excel numeric/percent cells require minimal normalization only when needed; prefer pass-through for MVP
- Keep execute scope small (`--max-files 1`)

## IMPLEMENTATION NOTES
- Begin with plan-only runs; once plans look correct, enable execute
- Implement a small `allowed_columns` list derived from the Chinese DDL
- Log summary: table/mode/deleted/inserted/batches

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/

# plan-only
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only --max-files 1

# execute (requires local DB and DDL applied)
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --execute --max-files 1

# opt-in tests
uv run pytest -m legacy_data -v -k annuity_performance
```

## ACCEPTANCE CRITERIA
- [ ] Plan-only produces DELETE + INSERT plans targeting `"规模明细"`
- [ ] Column projection prevents column-not-found errors in execute
- [ ] Execute inserts rows (small scope) and prints deleted/inserted/batches
- [ ] README updated with execute steps and cautions

## ROLLOUT & RISK
- Local-only; no CI changes
- Risk: column drift vs Chinese DDL → mitigated by projection whitelist

## APPENDICES
```python
# tests/legacy/test_annuity_performance_e2e.py (outline)
import os, pytest
from pathlib import Path

pytestmark = pytest.mark.legacy_data

def test_plan_only_then_execute_small():
    if not Path("reference/monthly").exists():
        pytest.skip("Local samples not present")
    os.environ["WDH_DATA_BASE_DIR"] = "./reference/monthly"
    # 1) plan-only CLI
    # 2) execute CLI with --max-files 1
    assert True
```

