-- SCD Type 2 Step 2: Insert new/changed records
-- Story 7.6-12: SCD Type 2 Implementation Fix
-- Story 7.6-15: Ratchet Rule - is_strategic only triggers on upgrade (FALSE → TRUE)
--
-- This INSERT creates new records only for:
-- - New contracts (no existing record)
-- - Changed status (old record was closed in Step 1)
--
-- IMPORTANT: Ratchet Rule Protection
-- The Ratchet Rule is enforced in Step 1 (close_old_records.sql).
-- If is_strategic would downgrade (TRUE → FALSE), Step 1 does NOT close the record,
-- so this INSERT's NOT EXISTS check will skip it (existing current record found).
-- This ensures strategic customers keep their status even if AUM drops.
--
-- Parameters: whitelist_top_n, strategic_threshold

WITH
-- Include common CTEs
{common_ctes}

INSERT INTO customer.customer_plan_contract (
    company_id,
    plan_code,
    product_line_code,
    product_line_name,
    customer_name,
    plan_name,
    is_strategic,
    is_existing,
    status_year,
    contract_status,
    valid_from,
    valid_to
)
SELECT DISTINCT ON (s.company_id, s.计划代码, s.产品线代码)
    s.company_id,
    s.计划代码 as plan_code,
    s.产品线代码 as product_line_code,
    COALESCE(p.产品线, s.业务类型) as product_line_name,
    cust.客户名称 as customer_name,
    plan.计划全称 as plan_name,
    CASE
        WHEN sw.company_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END as is_strategic,
    CASE
        WHEN pyd.company_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END as is_existing,
    EXTRACT(YEAR FROM s.月度) as status_year,
    CASE
        WHEN s.期末资产规模 > 0
             AND COALESCE(c12.has_contribution, FALSE) = TRUE
        THEN '正常'
        ELSE '停缴'
    END as contract_status,
    CURRENT_DATE as valid_from,
    '9999-12-31'::date as valid_to
FROM business.规模明细 s
LEFT JOIN mapping."产品线" p ON s.产品线代码 = p.产品线代码
LEFT JOIN customer."年金客户" cust ON s.company_id = cust.company_id
LEFT JOIN mapping."年金计划" plan ON s.计划代码 = plan.年金计划号
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
  AND NOT EXISTS (
      -- SCD Type 2: Skip if current record exists OR same-day record exists
      SELECT 1 FROM customer.customer_plan_contract existing
      WHERE existing.company_id = s.company_id
        AND existing.plan_code = s.计划代码
        AND existing.product_line_code = s.产品线代码
        AND (existing.valid_to = '9999-12-31' OR existing.valid_from = CURRENT_DATE)
  )
ORDER BY s.company_id, s.计划代码, s.产品线代码, s.月度 DESC
RETURNING company_id, plan_code, product_line_code;
