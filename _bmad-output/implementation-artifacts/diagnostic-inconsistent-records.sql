-- Diagnostic SQL for 141 inconsistent records
-- Story 7.6-15: AC-6 - Investigate remaining inconsistencies
--
-- Purpose: Identify why 141 records still have inconsistent contract_status
-- after applying the Ratchet Rule fix.

-- ============================================================================
-- STEP 1: Get the 141 inconsistent records with detailed analysis
-- ============================================================================

WITH contribution_12m AS (
    SELECT
        company_id,
        计划代码,
        产品线代码,
        SUM(COALESCE(供款, 0)) as total_contribution,
        CASE WHEN SUM(COALESCE(供款, 0)) > 0 THEN TRUE ELSE FALSE END as has_contribution,
        COUNT(*) as record_count
    FROM business."规模明细"
    WHERE 月度 >= (CURRENT_DATE - INTERVAL '12 months')
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码
),
latest_source AS (
    SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
        company_id,
        计划代码,
        产品线代码,
        期末资产规模,
        月度 as latest_month
    FROM business."规模明细"
    WHERE company_id IS NOT NULL
    ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
),
status_check AS (
    SELECT
        cpc.company_id,
        cpc.plan_code,
        cpc.product_line_code,
        cpc.contract_status as current_status,
        ls.期末资产规模,
        ls.latest_month,
        COALESCE(c12.has_contribution, FALSE) as has_contribution_12m,
        COALESCE(c12.total_contribution, 0) as total_contribution_12m,
        COALESCE(c12.record_count, 0) as contribution_record_count,
        -- Expected status based on business rule
        CASE
            WHEN ls.期末资产规模 > 0 AND COALESCE(c12.has_contribution, FALSE) = TRUE
            THEN '正常'
            ELSE '停缴'
        END as expected_status,
        -- Discrepancy flag
        CASE
            WHEN cpc.contract_status IS DISTINCT FROM
                 CASE
                     WHEN ls.期末资产规模 > 0 AND COALESCE(c12.has_contribution, FALSE) = TRUE
                     THEN '正常'
                     ELSE '停缴'
                 END
            THEN TRUE
            ELSE FALSE
        END as is_inconsistent
    FROM customer.customer_plan_contract cpc
    JOIN latest_source ls
        ON cpc.company_id = ls.company_id
        AND cpc.plan_code = ls.计划代码
        AND cpc.product_line_code = ls.产品线代码
    LEFT JOIN contribution_12m c12
        ON ls.company_id = c12.company_id
        AND ls.计划代码 = c12.计划代码
        AND ls.产品线代码 = c12.产品线代码
    WHERE cpc.valid_to = '9999-12-31'
)
-- ============================================================================
-- OUTPUT: Detailed analysis of inconsistent records
-- ============================================================================
SELECT
    company_id,
    plan_code,
    product_line_code,
    current_status,
    expected_status,
    期末资产规模,
    has_contribution_12m,
    total_contribution_12m,
    contribution_record_count,
    latest_month,
    -- Categorize the inconsistency type
    CASE
        -- Type 1: Should be 正常 but is 停缴 (data shows activity)
        WHEN current_status = '停缴' AND expected_status = '正常'
        THEN 'Type-1: False-停缴 (has contribution)'
        -- Type 2: Should be 停缴 but is 正常 (no contribution but positive AUM)
        WHEN current_status = '正常' AND expected_status = '停缴'
        THEN 'Type-2: False-正常 (no contribution)'
        ELSE 'Unknown'
    END as inconsistency_type
FROM status_check
WHERE is_inconsistent = TRUE
ORDER BY inconsistency_type, 期末资产规模 DESC;

-- Expected output: 141 rows with detailed diagnostics
