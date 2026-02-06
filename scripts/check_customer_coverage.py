"""检查2025年10月规模明细客户是否全部被customer_plan_contract覆盖"""
import os
from dotenv import load_dotenv
load_dotenv('.wdh_env', override=True)
import psycopg

conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print("=" * 70)
print("检查2025年10月规模明细客户是否全部被customer_plan_contract覆盖")
print("=" * 70)

# 1. 规模明细中的唯一客户数
cur.execute("""
    SELECT COUNT(DISTINCT company_id)
    FROM business."规模明细"
    WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
      AND company_id IS NOT NULL
""")
oct_customers = cur.fetchone()[0]
print(f"\n1. business.规模明细 2025年10月唯一客户数: {oct_customers}")

# 2. customer_plan_contract 中的唯一客户数 (当前有效记录)
cur.execute("""
    SELECT COUNT(DISTINCT company_id)
    FROM customer.customer_plan_contract
    WHERE valid_to = '9999-12-31'
""")
cpc_customers = cur.fetchone()[0]
print(f"2. customer_plan_contract 当前有效记录的唯一客户数: {cpc_customers}")

# 3. 检查在规模明细但不在contract表的客户
cur.execute("""
    WITH oct_customers AS (
        SELECT DISTINCT company_id
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
    )
    SELECT COUNT(*)
    FROM oct_customers oc
    LEFT JOIN customer.customer_plan_contract cpc
        ON oc.company_id = cpc.company_id
        AND cpc.valid_to = '9999-12-31'
    WHERE cpc.company_id IS NULL
""")
missing_customers = cur.fetchone()[0]
print(f"\n3. 在规模明细但不在contract表的客户数: {missing_customers}")

if missing_customers > 0:
    print(f"\n⚠️  有 {missing_customers} 个客户未被覆盖")
    
    # 4. 分析未覆盖客户的原因
    cur.execute("""
        WITH oct_customers AS (
            SELECT DISTINCT company_id
            FROM business."规模明细"
            WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
              AND company_id IS NOT NULL
        ),
        missing AS (
            SELECT oc.company_id
            FROM oct_customers oc
            LEFT JOIN customer.customer_plan_contract cpc
                ON oc.company_id = cpc.company_id
                AND cpc.valid_to = '9999-12-31'
            WHERE cpc.company_id IS NULL
        )
        SELECT 
            CASE 
                WHEN yj.company_id IS NULL THEN 'FK: 年金客户表无此客户'
                ELSE '其他原因'
            END as reason,
            COUNT(*) as cnt
        FROM missing m
        LEFT JOIN customer."年金客户" yj ON m.company_id = yj.company_id
        GROUP BY 1
        ORDER BY 2 DESC
    """)
    print("\n4. 未覆盖客户原因分析:")
    for row in cur.fetchall():
        print(f"   - {row[0]}: {row[1]} 个客户")
    
    # 5. 列出前10个未覆盖的客户
    cur.execute("""
        WITH oct_customers AS (
            SELECT DISTINCT company_id
            FROM business."规模明细"
            WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
              AND company_id IS NOT NULL
        ),
        missing AS (
            SELECT oc.company_id
            FROM oct_customers oc
            LEFT JOIN customer.customer_plan_contract cpc
                ON oc.company_id = cpc.company_id
                AND cpc.valid_to = '9999-12-31'
            WHERE cpc.company_id IS NULL
        )
        SELECT 
            m.company_id,
            yj.客户名称,
            CASE WHEN yj.company_id IS NULL THEN '不在年金客户表' ELSE '在年金客户表' END
        FROM missing m
        LEFT JOIN customer."年金客户" yj ON m.company_id = yj.company_id
        LIMIT 10
    """)
    print("\n5. 前10个未覆盖的客户:")
    for row in cur.fetchall():
        name = row[1] if row[1] else 'N/A'
        print(f"   - {row[0]}: {name} ({row[2]})")
else:
    print("\n✅ 所有2025年10月规模明细客户已被customer_plan_contract表覆盖!")

# 6. 额外检查：按业务键级别的覆盖情况
print("\n6. 按业务键(company_id + plan_code + product_line_code)级别检查:")
cur.execute("""
    WITH oct_biz_keys AS (
        SELECT DISTINCT 
            company_id, 
            计划代码, 
            产品线代码
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
          AND 产品线代码 IS NOT NULL
          AND 计划代码 IS NOT NULL
    )
    SELECT COUNT(*) FROM oct_biz_keys
""")
total_keys = cur.fetchone()[0]
print(f"   - 规模明细唯一业务键数: {total_keys}")

cur.execute("""
    WITH oct_biz_keys AS (
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
    covered AS (
        SELECT obk.*
        FROM oct_biz_keys obk
        JOIN customer.customer_plan_contract cpc
            ON obk.company_id = cpc.company_id
            AND obk.计划代码 = cpc.plan_code
            AND obk.产品线代码 = cpc.product_line_code
        WHERE cpc.valid_to = '9999-12-31'
           OR cpc.valid_from = CURRENT_DATE
    )
    SELECT COUNT(*) FROM covered
""")
covered_keys = cur.fetchone()[0]
print(f"   - 已覆盖的业务键数: {covered_keys}")
print(f"   - 未覆盖的业务键数: {total_keys - covered_keys}")
print(f"   - 覆盖率: {covered_keys/total_keys*100:.2f}%")

cur.close()
conn.close()
print("\n" + "=" * 70)
