-- SCD Type 2 Step 1: Close old records when status changes
-- Story 7.6-12: SCD Type 2 Implementation Fix
-- Story 7.6-15: Ratchet Rule - is_strategic only triggers on upgrade (FALSE → TRUE)
--
-- This UPDATE closes current records (valid_to = '9999-12-31') when any
-- tracked status field has changed:
-- - contract_status
-- - is_strategic (UPGRADE ONLY - Ratchet Rule)
-- - is_existing
--
-- Parameters: whitelist_top_n, strategic_threshold

WITH
-- Include common CTEs
{common_ctes}
,
-- CTE 4: Latest source data (most recent month per contract)
latest_source AS (
    SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
        company_id,
        计划代码,
        产品线代码,
        期末资产规模
    FROM business.规模明细
    WHERE company_id IS NOT NULL
      AND 产品线代码 IS NOT NULL
      AND 计划代码 IS NOT NULL
    ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
),
-- CTE 5: New status calculation (using latest source data)
new_status AS (
    SELECT
        ls.company_id,
        ls.计划代码 as plan_code,
        ls.产品线代码 as product_line_code,
        CASE WHEN sw.company_id IS NOT NULL THEN TRUE ELSE FALSE END
            as is_strategic,
        CASE WHEN pyd.company_id IS NOT NULL THEN TRUE ELSE FALSE END
            as is_existing,
        CASE
            WHEN ls.期末资产规模 > 0
                 AND COALESCE(c12.has_contribution, FALSE) = TRUE
            THEN '正常'
            ELSE '停缴'
        END as contract_status
    FROM latest_source ls
    LEFT JOIN strategic_whitelist sw
        ON ls.company_id = sw.company_id
        AND ls.计划代码 = sw.计划代码
        AND ls.产品线代码 = sw.产品线代码
    LEFT JOIN prior_year_dec pyd
        ON ls.company_id = pyd.company_id
        AND ls.计划代码 = pyd.计划代码
        AND ls.产品线代码 = pyd.产品线代码
    LEFT JOIN contribution_12m c12
        ON ls.company_id = c12.company_id
        AND ls.计划代码 = c12.计划代码
        AND ls.产品线代码 = c12.产品线代码
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
      OR (old.is_strategic = FALSE AND new.is_strategic = TRUE)
      OR old.is_existing IS DISTINCT FROM new.is_existing
  );
