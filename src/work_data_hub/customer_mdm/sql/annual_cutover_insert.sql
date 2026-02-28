-- Annual Cutover Step 2: Insert new records for all active customers
-- Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
-- AC-3: New Record Creation
--
-- Business Rule (Principle 1 - 年度切断):
-- Insert new records with status_year = year for all customers with prior year activity.
--
-- Parameters:
--   1. year (for prior_year_dec: year - 1)
--   2. whitelist_top_n
--   3. strategic_threshold
--   4. cutover_date (for closed_records)
--   5. status_year
--   6. cutover_date (for valid_from)

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
    -- Dynamic strategic evaluation based on latest available source month
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
        WHERE 月度 = (SELECT MAX(月度) FROM business.规模明细)
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
    FROM customer."客户年金计划"
    WHERE valid_to = %s::date
    ORDER BY company_id, plan_code, product_line_code, valid_from DESC
)
INSERT INTO customer."客户年金计划" (
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
LEFT JOIN customer."客户明细" cust ON pyd.company_id = cust.company_id
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
