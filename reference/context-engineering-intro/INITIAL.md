# INITIAL.md — Legacy Mapping Extraction (规模明细)

## Feature
Extract and formalize all mapping dictionaries consumed by the legacy `AnnuityPerformanceCleaner` into version-controlled JSON fixtures so the new pipeline can reuse the exact lookup data without hitting MySQL.

## Scope
- In scope
  - Enumerate every mapping dependency referenced by `legacy/annuity_hub/data_handler/mappings.py`.
  - For each mapping, read the migrated PostgreSQL tables (produced by `reference/db_migration/V2/mysql_to_postgresql_migrator.py`) and export the mapping to a dedicated JSON file under `tests/fixtures/mappings/`.
  - Validate row counts / key sets against their source tables and document any gaps due to incomplete MySQL→Postgres migration.
  - Produce a consolidated report (markdown or JSON) listing missing keys or lookup values so maintainers can backfill them manually.
- Out of scope
  - Modifying the migrator script itself.
  - Updating pipeline code or service integration (handled in later tasks).
  - Rehydrating mappings for domains other than annuity performance.

## Mapping Inventory (must extract)
| Mapping Name | Legacy Source | Target JSON | Notes |
| --- | --- | --- | --- |
| `COMPANY_ID1_MAPPING` | `mapping.年金计划` (plan → company_id) | `tests/fixtures/mappings/company_id1_mapping.json` | Primary plan-code lookup |
| `COMPANY_ID2_MAPPING` | `enterprise.annuity_account_mapping` (account → company_id) | `tests/fixtures/mappings/company_id2_mapping.json` | Removes `GM%` accounts per legacy logic |
| `COMPANY_ID3_MAPPING` | Hard-coded dict in legacy module | `tests/fixtures/mappings/company_id3_mapping.json` | Includes default `600866980` fallback handling |
| `COMPANY_ID4_MAPPING` | `enterprise.company_id_mapping` (customer_name → company_id) | `tests/fixtures/mappings/company_id4_mapping.json` | Ensure UTF-8 characters preserved |
| `COMPANY_ID5_MAPPING` | `business.规模明细` (account_name → company_id) | `tests/fixtures/mappings/company_id5_mapping.json` | Use curated subset relevant to annuity |
| `COMPANY_BRANCH_MAPPING` | `mapping.组织架构` | `tests/fixtures/mappings/company_branch_mapping.json` | Include override entries (e.g., 内蒙→G31) present in legacy code |
| `BUSINESS_TYPE_CODE_MAPPING` | `mapping.产品线` | `tests/fixtures/mappings/business_type_code_mapping.json` | Map business type → 产品线代码 |
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | Legacy default dict | `tests/fixtures/mappings/default_portfolio_code_mapping.json` | Fallback: 集合计划→QTAN001, etc. |
| `PRODUCT_ID_MAPPING` | `mapping.产品明细` | `tests/fixtures/mappings/product_id_mapping.json` | Only if referenced by annuity cleaner |
| `PROFIT_METRICS_MAPPING` | `mapping.利润指标` | `tests/fixtures/mappings/profit_metrics_mapping.json` | Extract if the cleaner uses it (double-check code) |

> During execution, cross-check the legacy file to confirm whether each mapping above is actually accessed by `AnnuityPerformanceCleaner`. If additional dictionaries are referenced (e.g., `DEFAULT_PLAN_CODE_MAPPING`), add them to the list following the same conventions.

## Implementation Notes
1. **Prepare queries**: For each mapping table, write SQL against the migrated PostgreSQL database to retrieve required columns. Store reusable queries in a scratch script or `docs/VALIDATION.md`.
2. **Export workflow**:
   - Use Python (preferred via `uv run`) to read from Postgres and emit JSON with the shape `{ "description": ..., "source": ..., "data": { key: value, ... } }`.
   - Save each JSON under `tests/fixtures/mappings/<mapping_name>.json` (one file per mapping).
   - Ensure files are UTF-8 encoded and sorted by key for stable diffs.
3. **Missing data handling**:
   - If a query returns zero rows or obvious key gaps (e.g., plan codes present in Excel but missing in DB), record the missing identifiers in `tests/fixtures/mappings/_missing_entries.md` (or similar) with context about which mapping is affected.
   - Continue generating the JSON with available data; do not fail the entire run.
4. **Verification checks**:
   - Compare row counts from SQL vs JSON entry counts.
   - Spot-check a few critical keys (e.g., plan codes used in `tests/fixtures/sample_data/annuity_subsets/`) to confirm the mapping exists.
   - Optionally load the JSON back into Python and assert schema consistency.

## Validation Commands
```bash
# Example: export COMPANY_ID1_MAPPING via Python
uv run python scripts/tools/export_mapping.py \
  --mapping company_id1_mapping \
  --output tests/fixtures/mappings/company_id1_mapping.json

# Inspect JSON keys (sorted)
python - <<'PY'
import json
from pathlib import Path
path = Path('tests/fixtures/mappings/company_id1_mapping.json')
with path.open(encoding='utf-8') as fh:
    data = json.load(fh)
print(f"Keys: {len(data['data'])}")
print('\n'.join(sorted(list(data['data'])[:5])))
PY

# Record missing entries (if any)
cat tests/fixtures/mappings/_missing_entries.md
```

*(Feel free to implement your own export helper script; the command above is illustrative. Ensure any utilities you create live under `scripts/tools/`.)*

## Acceptance Criteria
- [ ] JSON files exist for every mapping listed in the inventory table, each with correct key/value structure.
- [ ] Each JSON includes metadata (`description` / `source`) documenting origin and extraction details.
- [ ] `tests/fixtures/mappings/_missing_entries.md` (or equivalent) catalogues any ids/names absent from the migrated DB.
- [ ] Validation evidence (row counts, sample keys) captured in the PR review comment or `docs/VALIDATION.md`.
- [ ] No changes beyond mapping extraction and documentation.

## Risks & Mitigations
- **Migrated DB incomplete**: Document missing entries; do not synthesize values. Coordination needed to backfill.
- **Encoding issues**: Ensure PostgreSQL client and JSON writer both use UTF-8; double-check Chinese characters in output.
- **Schema drift**: If table names/columns differ from legacy expectations, note discrepancies explicitly so upstream migration can be corrected.

## Deliverables
- Mapping JSON files in `tests/fixtures/mappings/` (one per mapping).
- Missing-entry report (`tests/fixtures/mappings/_missing_entries.md`).
- Updated `docs/VALIDATION.md` (optional but recommended) summarizing commands executed and checks performed.
