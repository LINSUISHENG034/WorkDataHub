-- Annual Cutover Step 2: Insert new records for all active customers
-- Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
-- AC-3: New Record Creation
--
-- Business Rule (Principle 1 - 年度切断):
-- Insert new records with status_year = year for all customers with prior year activity.
--
-- Parameters:
--   1. year (for prior_year_dec: year - 1)
--   2. year (for strategic_whitelist: year - 1)
--   3. whitelist_top_n
--   4. strategic_threshold
--   5. cutover_date (for closed_records)
--   6. status_year
--   7. cutover_date (for valid_from)

WITH prior_year_dec AS (
    -- Get all active customers from prior year December
    SELECT DISTINCT
        company_id,
        计划代码 as plan_code,
        产品线代码 as product_line_code,
        业务类型
    FROM business.规模明细
    WHERE EXTRACT(YEAR FROM 月度) = %s - 1
      AND EXTRACT(MONTH FROM 月度) = 12
      AND company_id IS NOT NULL
      AND 期末资产规模 > 0
),
strategic_whitelist AS (
    -- Calculate strategic customers based on AUM threshold and top N
    SELECT
        company_id,
        计划代码 as plan_code,
        产品线代码 as product_line_code
    FROM (
        SELECT
            company_id,
            计划代码,
            产品线代码,
            机构代码,
            SUM(期末资产规模) as total_aum,
            ROW_NUMBER() OVER (
                PARTITION BY 机构代码, 产品线代码
                ORDER BY SUM(期末资产规模) DESC
            ) as rank_in_branch
        FROM business.规模明细
        WHERE EXTRACT(YEAR FROM 月度) = %s - 1
          AND EXTRACT(MONTH FROM 月度) = 12
          AND company_id IS NOT NULL
        GROUP BY company_id, 计划代码, 产品线代码, 机构代码
    ) ranked
    WHERE rank_in_branch <= %s
       OR total_aum >= %s
),
closed_records AS (
    -- Get the most recent closed record for each contract
    SELECT DISTINCT ON (company_id, plan_code, product_line_code)
        company_id,
        plan_code,
        product_line_code,
        customer_name,
        plan_name,
        product_line_name
    FROM customer.customer_plan_contract
    WHERE valid_to = %s::date
    ORDER BY company_id, plan_code, product_line_code, valid_from DESC
)
INSERT INTO customer.customer_plan_contract (
    company_id,
    plan_code,
    product_line_code,
    product_line_name,
    customer_name,
    plan_name,
    contract_status,
    is_strategic,
    is_existing,
    status_year,
    valid_from,
    valid_to,
    created_at,
    updated_at
)
SELECT
    pyd.company_id,
    pyd.plan_code,
    pyd.product_line_code,
    COALESCE(cr.product_line_name, p.产品线, pyd.业务类型) as product_line_name,
    COALESCE(cr.customer_name, cust.客户名称) as customer_name,
    COALESCE(cr.plan_name, plan.计划全称) as plan_name,
    '正常' as contract_status,
    CASE WHEN sw.company_id IS NOT NULL THEN TRUE ELSE FALSE END as is_strategic,
    TRUE as is_existing,
    %s as status_year,
    %s::date as valid_from,
    '9999-12-31'::date as valid_to,
    CURRENT_TIMESTAMP as created_at,
    CURRENT_TIMESTAMP as updated_at
FROM prior_year_dec pyd
LEFT JOIN mapping."产品线" p ON pyd.product_line_code = p.产品线代码
LEFT JOIN customer."年金关联公司" cust ON pyd.company_id = cust.company_id
LEFT JOIN mapping."年金计划" plan ON pyd.plan_code = plan.年金计划号
LEFT JOIN strategic_whitelist sw
    ON pyd.company_id = sw.company_id
    AND pyd.plan_code = sw.plan_code
    AND pyd.product_line_code = sw.product_line_code
LEFT JOIN closed_records cr
    ON pyd.company_id = cr.company_id
    AND pyd.plan_code = cr.plan_code
    AND pyd.product_line_code = cr.product_line_code
ON CONFLICT (company_id, plan_code, product_line_code, valid_from)
DO NOTHING;
