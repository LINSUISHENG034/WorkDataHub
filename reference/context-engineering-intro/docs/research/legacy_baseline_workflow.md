# Legacy Baseline Workflow (Annuity Performance Example)

This note captures the core steps used to execute the real `AnnuityPerformanceCleaner`
without relying on the legacy MySQL deployment. Claude can mirror the same
sequence when migrating other legacy cleaners.

## 1. Curate Mapping Fixtures
- Collect the minimal dictionaries the legacy cleaner reads from MySQL
  (`COMPANY_ID[1-5]_MAPPING`, `COMPANY_BRANCH_MAPPING`,
  `BUSINESS_TYPE_CODE_MAPPING`, `DEFAULT_PORTFOLIO_CODE_MAPPING`, etc.).
- Store them inside `tests/fixtures/sample_legacy_mappings.json` with a
  `mappings.<name>.data` structure so they can be version-controlled and edited
  easily.

## 2. Inject Mapping Module Before Import
- The legacy file `legacy/annuity_hub/data_handler/mappings.py` opens MySQL
  connections at import time. To avoid that dependency we create an in-memory
  module with the same public attributes and register it in `sys.modules` before
  loading `legacy.annuity_hub.data_handler.data_cleaner`.
- The helper `build_mapping_module()` in
  `scripts/tools/run_legacy_annuity_cleaner.py` builds this replacement module
  directly from the JSON fixture (`tests/fixtures/sample_legacy_mappings.json`).

## 3. Execute the Real Cleaner
- After the module swap, import `AnnuityPerformanceCleaner` as usual and run it
  against the curated Excel subsets (`tests/fixtures/sample_data/annuity_subsets/`).
- Append `_source_file` so we can trace the origin of each row, then concatenate
  the per-file DataFrames.

## 4. Canonicalise & Persist
- Sort the combined DataFrame by `(月度, 计划代码, company_id)` to guarantee
  deterministic ordering.
- Save to Parquet (`tests/fixtures/annuity_performance/golden_legacy.parquet`) to
  preserve schema information for parity tests.

## 5. Reuse Pattern for Other Domains
- Repeat the same workflow (curated mappings → module injection → cleaner
  execution → canonical baseline) for other legacy cleaners. Only the mapping
  keys and sheet names change per domain.
- Keep steps + fixtures documented alongside each domain so the pipeline agents
  can regenerate baselines whenever business mappings change.

## Useful Commands
```bash
# Generate/refresh the golden baseline for annuity performance
python scripts/tools/run_legacy_annuity_cleaner.py \
  --inputs tests/fixtures/sample_data/annuity_subsets \
  --output tests/fixtures/annuity_performance/golden_legacy.parquet \
  --mappings tests/fixtures/sample_legacy_mappings.json
```
