"""进一步分析149条未同步记录"""

import os

from dotenv import load_dotenv

load_dotenv(".wdh_env", override=True)
import psycopg

conn = psycopg.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

print("分析149条未同步记录的详细原因:")

cur.execute("""
    WITH oct_biz AS (
        SELECT DISTINCT 
            company_id, 
            计划代码, 
            产品线代码
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
          AND 产品线代码 IS NOT NULL
          AND 计划代码 IS NOT NULL
    ),
    missing AS (
        SELECT b.*
        FROM oct_biz b
        LEFT JOIN customer."客户年金计划" c
            ON b.company_id = c.company_id
            AND b.计划代码 = c.plan_code
            AND b.产品线代码 = c.product_line_code
            AND c.valid_to = '9999-12-31'
        WHERE c.contract_id IS NULL
    )
    SELECT
        CASE
            WHEN hist.contract_id IS NOT NULL THEN '有历史记录(已关闭)'
            ELSE '从未同步过'
        END as sync_history,
        COUNT(DISTINCT m.company_id || m.计划代码 || m.产品线代码) as cnt
    FROM missing m
    LEFT JOIN customer."客户年金计划" hist
        ON m.company_id = hist.company_id
        AND m.计划代码 = hist.plan_code
        AND m.产品线代码 = hist.product_line_code
        AND hist.valid_to != '9999-12-31'
    GROUP BY 1
    ORDER BY 1
""")

for row in cur.fetchall():
    print(f"  - {row[0]}: {row[1]} 条")

# 检查是否是因为same day record问题
print("\n检查同日记录情况:")
cur.execute("""
    WITH oct_biz AS (
        SELECT DISTINCT 
            company_id, 
            计划代码, 
            产品线代码
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
          AND 产品线代码 IS NOT NULL
          AND 计划代码 IS NOT NULL
    ),
    missing AS (
        SELECT b.*
        FROM oct_biz b
        LEFT JOIN customer."客户年金计划" c
            ON b.company_id = c.company_id
            AND b.计划代码 = c.plan_code
            AND b.产品线代码 = c.product_line_code
            AND c.valid_to = '9999-12-31'
        WHERE c.contract_id IS NULL
    )
    SELECT
        COUNT(*) FILTER (WHERE same_day.contract_id IS NOT NULL) as has_same_day,
        COUNT(*) FILTER (WHERE same_day.contract_id IS NULL) as no_same_day
    FROM missing m
    LEFT JOIN customer."客户年金计划" same_day
        ON m.company_id = same_day.company_id
        AND m.计划代码 = same_day.plan_code
        AND m.产品线代码 = same_day.product_line_code
        AND same_day.valid_from = CURRENT_DATE
""")

r = cur.fetchone()
print(f"  - 有当日关闭记录: {r[0]} 条")
print(f"  - 无当日记录: {r[1]} 条")

cur.close()
conn.close()
