-- SCD Type 2 Step 1: Close old records when status changes
-- Story 7.6-12: SCD Type 2 Implementation Fix
--
-- This UPDATE closes current records (valid_to = '9999-12-31') when any
-- tracked status field has changed:
-- - contract_status
-- - is_strategic
-- - is_existing
--
-- Parameters: %s (whitelist_top_n), %s (strategic_threshold)

WITH
-- Include common CTEs
{common_ctes}
,
-- CTE 4: New status calculation
new_status AS (
    SELECT DISTINCT
        s.company_id,
        s.计划代码 as plan_code,
        s.产品线代码 as product_line_code,
        CASE WHEN sw.company_id IS NOT NULL THEN TRUE ELSE FALSE END
            as is_strategic,
        CASE WHEN pyd.company_id IS NOT NULL THEN TRUE ELSE FALSE END
            as is_existing,
        CASE
            WHEN s.期末资产规模 > 0
                 AND COALESCE(c12.has_contribution, FALSE) = TRUE
            THEN '正常'
            ELSE '停缴'
        END as contract_status
    FROM business.规模明细 s
    LEFT JOIN strategic_whitelist sw
        ON s.company_id = sw.company_id
        AND s.计划代码 = sw.计划代码
        AND s.产品线代码 = sw.产品线代码
    LEFT JOIN prior_year_dec pyd
        ON s.company_id = pyd.company_id
        AND s.计划代码 = pyd.计划代码
        AND s.产品线代码 = pyd.产品线代码
    LEFT JOIN contribution_12m c12
        ON s.company_id = c12.company_id
        AND s.计划代码 = c12.计划代码
        AND s.产品线代码 = c12.产品线代码
    WHERE s.company_id IS NOT NULL
      AND s.产品线代码 IS NOT NULL
      AND s.计划代码 IS NOT NULL
)
UPDATE customer.customer_plan_contract AS old
SET valid_to = (CURRENT_DATE - INTERVAL '1 day')::date,
    updated_at = CURRENT_TIMESTAMP
FROM new_status AS new
WHERE old.company_id = new.company_id
  AND old.plan_code = new.plan_code
  AND old.product_line_code = new.product_line_code
  AND old.valid_to = '9999-12-31'
  AND (
      old.contract_status IS DISTINCT FROM new.contract_status
      OR old.is_strategic IS DISTINCT FROM new.is_strategic
      OR old.is_existing IS DISTINCT FROM new.is_existing
  );
