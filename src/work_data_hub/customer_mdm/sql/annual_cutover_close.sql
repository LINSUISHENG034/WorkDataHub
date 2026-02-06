-- Annual Cutover Step 1: Close all current records
-- Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
-- AC-2: Record Closure
--
-- Business Rule (Principle 1 - 年度切断):
-- On January 1st, ALL current records must be closed (valid_to = 'YYYY-01-01')
-- regardless of status change.
--
-- Parameters: cutover_date (e.g., '2026-01-01')

UPDATE customer.customer_plan_contract
SET valid_to = %s::date,
    updated_at = CURRENT_TIMESTAMP
WHERE valid_to = '9999-12-31'
RETURNING contract_id;
