"""深入分析 客户年金计划 同步问题

分析:
1. 未同步的149条记录原因
2. 状态异常情况的合理性
"""

import os

from dotenv import load_dotenv

load_dotenv(".wdh_env", override=True)
import psycopg


def main():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    print("=" * 70)
    print("深入分析 客户年金计划 同步问题")
    print("=" * 70)

    # 分析1: 未同步记录的原因 - 检查外键约束
    print("\n1. 分析未同步的149条记录:")
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
            m.company_id,
            m.计划代码,
            m.产品线代码,
            CASE 
                WHEN cust.company_id IS NULL THEN 'FK: 客户不存在'
                WHEN pl.产品线代码 IS NULL THEN 'FK: 产品线不存在'
                ELSE '其他原因'
            END as missing_reason
        FROM missing m
        LEFT JOIN customer."客户明细" cust ON m.company_id = cust.company_id
        LEFT JOIN mapping."产品线" pl ON m.产品线代码 = pl.产品线代码
        LIMIT 20
    """)
    print("   前20条未同步记录及原因:")
    reasons_count = {}
    for row in cur.fetchall():
        reason = row[3]
        reasons_count[reason] = reasons_count.get(reason, 0) + 1
        print(
            f"   - company_id={row[0][:20]}..., plan={row[1]}, product_line={row[2]} -> {reason}"
        )

    # 统计原因分布
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
                WHEN cust.company_id IS NULL THEN 'FK: 客户不存在'
                WHEN pl.产品线代码 IS NULL THEN 'FK: 产品线不存在'
                ELSE '其他原因'
            END as missing_reason,
            COUNT(*) as cnt
        FROM missing m
        LEFT JOIN customer."客户明细" cust ON m.company_id = cust.company_id
        LEFT JOIN mapping."产品线" pl ON m.产品线代码 = pl.产品线代码
        GROUP BY 1
        ORDER BY 2 DESC
    """)
    print("\n   未同步原因统计:")
    for row in cur.fetchall():
        print(f"   - {row[0]}: {row[1]} 条")

    # 分析2: "无资产但正常" 的37条记录 - 应该是之前有资产的记录
    print("\n2. 分析 '无资产但正常' 的37条记录:")
    print("   (这些记录的10月期末资产=0，但contract_status='正常')")
    cur.execute("""
        WITH oct_latest AS (
            SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
                company_id, 
                计划代码, 
                产品线代码,
                期末资产规模,
                供款,
                月度
            FROM business."规模明细"
            WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
              AND company_id IS NOT NULL
              AND 产品线代码 IS NOT NULL
              AND 计划代码 IS NOT NULL
            ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
        )
        SELECT 
            c.company_id,
            c.plan_code,
            c.product_line_code,
            c.contract_status,
            o.期末资产规模,
            c.valid_from
        FROM customer."客户年金计划" c
        JOIN oct_latest o
            ON c.company_id = o.company_id
            AND c.plan_code = o.计划代码
            AND c.product_line_code = o.产品线代码
        WHERE c.valid_to = '9999-12-31'
          AND c.contract_status = '正常'
          AND o.期末资产规模 = 0
        LIMIT 10
    """)
    print("   前10条示例:")
    for row in cur.fetchall():
        print(f"   - company={row[0][:25]}..., valid_from={row[5]}, 期末资产={row[4]}")

    # 解释: 这些记录的状态是基于历史数据(12个月滚动供款)计算的
    print("\n   解释: contract_status 是基于 SCD Type 2 历史记录,")
    print("         不仅仅依赖当前月的期末资产规模,")
    print("         还考虑12个月滚动供款窗口")

    # 分析3: "有资产但停缴" 的5240条记录 - 12个月无供款
    print("\n3. 分析 '有资产但停缴' 的5240条记录:")
    print("   (期末资产规模>0 但 contract_status='停缴')")
    cur.execute("""
        WITH oct_latest AS (
            SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
                company_id, 
                计划代码, 
                产品线代码,
                期末资产规模,
                供款
            FROM business."规模明细"
            WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
              AND company_id IS NOT NULL
              AND 产品线代码 IS NOT NULL
              AND 计划代码 IS NOT NULL
            ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
        ),
        contribution_12m AS (
            SELECT
                company_id,
                计划代码,
                产品线代码,
                SUM(COALESCE(供款, 0)) as total_contribution
            FROM business."规模明细"
            WHERE 月度 >= (CURRENT_DATE - INTERVAL '12 months')
              AND company_id IS NOT NULL
            GROUP BY company_id, 计划代码, 产品线代码
        )
        SELECT 
            CASE 
                WHEN c12.total_contribution > 0 THEN '有供款'
                WHEN c12.total_contribution = 0 THEN '无供款'
                ELSE '无12个月数据'
            END as contribution_status,
            COUNT(*) as cnt
        FROM customer."客户年金计划" c
        JOIN oct_latest o
            ON c.company_id = o.company_id
            AND c.plan_code = o.计划代码
            AND c.product_line_code = o.产品线代码
        LEFT JOIN contribution_12m c12
            ON c.company_id = c12.company_id
            AND c.plan_code = c12.计划代码
            AND c.product_line_code = c12.产品线代码
        WHERE c.valid_to = '9999-12-31'
          AND c.contract_status = '停缴'
          AND o.期末资产规模 > 0
        GROUP BY 1
        ORDER BY 1
    """)
    print("   12个月供款分布:")
    for row in cur.fetchall():
        print(f"   - {row[0]}: {row[1]} 条")

    print("\n   解释: '停缴' 状态表示虽有资产，但12个月内无供款记录。")
    print("         这符合业务规则: 正常 = 期末资产>0 AND 12个月供款>0")

    # 分析4: 战客和已客为0的原因
    print("\n4. 分析战客(is_strategic)和已客(is_existing)均为0的原因:")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM 月度)::int as year,
            EXTRACT(MONTH FROM 月度)::int as month,
            COUNT(*)
        FROM business."规模明细"
        WHERE company_id IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2 DESC
        LIMIT 15
    """)
    print("   规模明细数据覆盖的月份:")
    for row in cur.fetchall():
        print(f"   - {row[0]}年{row[1]}月: {row[2]} 条")

    # 检查是否有上一年12月数据
    cur.execute("""
        SELECT COUNT(*), COUNT(DISTINCT company_id)
        FROM business."规模明细"
        WHERE EXTRACT(MONTH FROM 月度) = 12
          AND EXTRACT(YEAR FROM 月度) = EXTRACT(YEAR FROM CURRENT_DATE) - 1
          AND 期末资产规模 > 0
          AND company_id IS NOT NULL
    """)
    r = cur.fetchone()
    print(f"\n   上一年(2025年)12月有资产记录: {r[0]} 条, {r[1]} 个客户")

    if r[0] == 0:
        print("   注意: is_existing 基于上一年12月数据，当前可能无2025年12月数据")

    cur.close()
    conn.close()
    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
