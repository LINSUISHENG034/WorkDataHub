# is_strategic Dynamic Evaluation Implementation Plan

- Source: `_bmad-output/planning-artifacts/specific/customer-mdm/is_strategic_dynamic_evaluation.md`
- Date: 2026-02-28

## Scope
1. Keep `is_existing` logic unchanged (prior-year December).
2. Change `is_strategic` to dynamic evaluation from current data.
3. Preserve Ratchet Rule (`FALSE -> TRUE` only, no downgrade).

## Implementation Steps
1. Update `src/work_data_hub/customer_mdm/sql/common_ctes.sql`
   - Refactor `strategic_whitelist` to use latest available month (`MAX(月度)`) instead of prior-year December.
   - Keep threshold/top-N logic unchanged.
2. Update `src/work_data_hub/customer_mdm/contract_sync.py`
   - Adjust SQL parameter contract/comments to match updated CTE placeholders.
3. Align annual/init logic
   - Update `_update_strategic` in `src/work_data_hub/customer_mdm/year_init.py` to use dynamic month source.
   - Update `src/work_data_hub/customer_mdm/sql/annual_cutover_insert.sql` strategic whitelist source to dynamic month.
4. Add/adjust integration tests
   - Extend fixture data in `tests/integration/customer_mdm/conftest.py` with a new customer that has no prior-year Dec row but current AUM >= threshold.
   - Add assertion in `tests/integration/customer_mdm/test_status_fields.py` that this customer is `is_strategic = TRUE` and `is_existing = FALSE`.
5. Validate
   - Run focused customer MDM unit/integration tests related to strategic logic and sync behavior.

## Acceptance Criteria
1. New high-AUM customers without prior-year December data can become strategic in sync runs.
2. Existing customer identification remains based on prior-year December.
3. Ratchet behavior remains enforced (no strategic downgrade-driven close/insert).
4. Updated tests pass.
