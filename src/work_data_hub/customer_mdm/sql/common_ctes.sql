-- Common CTEs for contract status sync operations
-- Story 7.6-12: SCD Type 2 Implementation
--
-- These CTEs are shared between close_old_records.sql and sync_insert.sql
-- Parameters: %s (whitelist_top_n), %s (strategic_threshold)

-- CTE 1: Prior year December data for is_existing check
prior_year_dec AS (
    SELECT DISTINCT
        company_id,
        计划代码,
        产品线代码
    FROM business.规模明细
    WHERE EXTRACT(MONTH FROM 月度) = 12
      AND EXTRACT(YEAR FROM 月度) = EXTRACT(YEAR FROM CURRENT_DATE) - 1
      AND 期末资产规模 > 0
      AND company_id IS NOT NULL
),

-- CTE 2: Strategic whitelist (top N per branch per product line)
strategic_whitelist AS (
    SELECT
        company_id,
        计划代码,
        产品线代码
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
        WHERE EXTRACT(MONTH FROM 月度) = 12
          AND EXTRACT(YEAR FROM 月度) = EXTRACT(YEAR FROM CURRENT_DATE) - 1
          AND company_id IS NOT NULL
        GROUP BY company_id, 计划代码, 产品线代码, 机构代码
    ) ranked
    WHERE rank_in_branch <= %s
       OR total_aum >= %s
),

-- CTE 3: 12-month rolling contribution check
contribution_12m AS (
    SELECT
        company_id,
        计划代码,
        产品线代码,
        CASE WHEN SUM(COALESCE(供款, 0)) > 0 THEN TRUE ELSE FALSE END
            as has_contribution
    FROM business.规模明细
    WHERE 月度 >= (CURRENT_DATE - INTERVAL '12 months')
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码
)
