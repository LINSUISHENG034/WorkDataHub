-- Common CTEs for contract status sync operations
-- Story 7.6-12: SCD Type 2 Implementation
-- BugFix: Use period-based year instead of CURRENT_DATE to avoid
--         looking up nonexistent future December data.
-- BugFix: Use period_end_date instead of CURRENT_DATE for 12-month
--         contribution window, ensuring correct results on historical re-runs.
--
-- These CTEs are shared between close_old_records.sql and sync_insert.sql
-- Parameters: prior_year, whitelist_top_n, strategic_threshold, period_end_date

-- CTE 1: Prior year December data for is_existing check
prior_year_dec AS (
    SELECT DISTINCT
        company_id,
        计划代码,
        产品线代码
    FROM business.规模明细
    WHERE EXTRACT(MONTH FROM 月度) = 12
      AND EXTRACT(YEAR FROM 月度) = %s
      AND 期末资产规模 > 0
      AND company_id IS NOT NULL
),

-- CTE 2: Strategic whitelist (top N per branch per product line)
-- Dynamic evaluation: use latest available source month (not prior-year December)
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
        WHERE 月度 = (SELECT MAX(月度) FROM business.规模明细)
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
    WHERE 月度 >= (%s - INTERVAL '12 months')
      AND company_id IS NOT NULL
    GROUP BY company_id, 计划代码, 产品线代码
)
