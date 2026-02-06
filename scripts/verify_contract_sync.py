"""Verify customer_plan_contract sync logic with October 2025 data.

验证脚本：检查从 business.规模明细 到 customer.customer_plan_contract 的同步逻辑
"""
import os
from dotenv import load_dotenv
load_dotenv('.wdh_env', override=True)
import psycopg

def main():
    conn = psycopg.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    print("=" * 60)
    print("验证 customer_plan_contract 更新逻辑 - 2025年10月数据")
    print("=" * 60)
    
    # 查询1: business.规模明细 2025年10月数据概况
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT company_id) as unique_companies,
            COUNT(DISTINCT 计划代码) as unique_plans,
            COUNT(DISTINCT 产品线代码) as unique_product_lines
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
          AND 产品线代码 IS NOT NULL
          AND 计划代码 IS NOT NULL
    """)
    r = cur.fetchone()
    print("\n1. business.规模明细 2025年10月数据概况:")
    print(f"   - 总记录数: {r[0]}")
    print(f"   - 唯一客户数: {r[1]}")
    print(f"   - 唯一计划数: {r[2]}")
    print(f"   - 唯一产品线数: {r[3]}")
    
    # 查询2: 按状态分类的规模明细 (根据期末资产规模判断)
    cur.execute("""
        SELECT 
            CASE WHEN 期末资产规模 > 0 THEN '有资产' ELSE '无资产' END as asset_status,
            COUNT(*) as cnt,
            COUNT(DISTINCT company_id) as companies
        FROM business."规模明细"
        WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
          AND company_id IS NOT NULL
        GROUP BY CASE WHEN 期末资产规模 > 0 THEN '有资产' ELSE '无资产' END
        ORDER BY asset_status
    """)
    print("\n2. 2025年10月按期末资产规模分类:")
    for row in cur.fetchall():
        print(f"   - {row[0]}: {row[1]} 条记录, {row[2]} 个客户")
    
    # 查询3: customer_plan_contract 当前有效记录
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT company_id) as companies,
            COUNT(*) FILTER (WHERE contract_status = '正常') as active,
            COUNT(*) FILTER (WHERE contract_status = '停缴') as suspended,
            COUNT(*) FILTER (WHERE is_strategic = TRUE) as strategic,
            COUNT(*) FILTER (WHERE is_existing = TRUE) as existing
        FROM customer.customer_plan_contract
        WHERE valid_to = '9999-12-31'
    """)
    r = cur.fetchone()
    print("\n3. customer.customer_plan_contract 当前有效记录:")
    print(f"   - 总记录数: {r[0]}")
    print(f"   - 唯一客户数: {r[1]}")
    print(f"   - 正常状态: {r[2]}")
    print(f"   - 停缴状态: {r[3]}")
    print(f"   - 战客数量: {r[4]}")
    print(f"   - 已客数量: {r[5]}")
    
    # 查询4: 验证同步完整性 - 2025年10月的唯一业务键是否都在 contract 表中
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
            LEFT JOIN customer.customer_plan_contract c
                ON b.company_id = c.company_id
                AND b.计划代码 = c.plan_code
                AND b.产品线代码 = c.product_line_code
                AND c.valid_to = '9999-12-31'
            WHERE c.contract_id IS NULL
        )
        SELECT COUNT(*) as missing_count FROM missing
    """)
    missing_count = cur.fetchone()[0]
    print(f"\n4. 同步完整性检查:")
    print(f"   - 2025年10月业务键中未同步到 contract 表的记录数: {missing_count}")
    if missing_count == 0:
        print("   ✅ 所有2025年10月的唯一业务组合已成功同步")
    else:
        print("   ⚠️  存在未同步的记录")
    
    # 查询5: 验证状态逻辑 - 期末资产规模>0 应该对应正常或停缴(根据供款情况)
    cur.execute("""
        WITH oct_latest AS (
            SELECT DISTINCT ON (company_id, 计划代码, 产品线代码)
                company_id, 
                计划代码, 
                产品线代码,
                期末资产规模
            FROM business."规模明细"
            WHERE 月度 BETWEEN '2025-10-01' AND '2025-10-31'
              AND company_id IS NOT NULL
              AND 产品线代码 IS NOT NULL
              AND 计划代码 IS NOT NULL
            ORDER BY company_id, 计划代码, 产品线代码, 月度 DESC
        )
        SELECT 
            c.contract_status,
            CASE WHEN o.期末资产规模 > 0 THEN '有资产' ELSE '无资产' END as asset_status,
            COUNT(*) as cnt
        FROM customer.customer_plan_contract c
        JOIN oct_latest o 
            ON c.company_id = o.company_id
            AND c.plan_code = o.计划代码
            AND c.product_line_code = o.产品线代码
        WHERE c.valid_to = '9999-12-31'
        GROUP BY c.contract_status, CASE WHEN o.期末资产规模 > 0 THEN '有资产' ELSE '无资产' END
        ORDER BY asset_status, c.contract_status
    """)
    print("\n5. 状态逻辑验证 (contract_status vs 期末资产规模):")
    for row in cur.fetchall():
        print(f"   - 合约状态={row[0]}, 资产状态={row[1]}: {row[2]} 条")
    
    # 查询6: 抽样检查 - 前5条记录详情
    cur.execute("""
        SELECT 
            c.company_id,
            c.plan_code,
            c.product_line_code,
            c.contract_status,
            c.is_strategic,
            c.is_existing,
            c.valid_from,
            c.customer_name
        FROM customer.customer_plan_contract c
        WHERE c.valid_to = '9999-12-31'
        LIMIT 5
    """)
    print("\n6. 抽样记录 (前5条):")
    for row in cur.fetchall():
        print(f"   - {row[7] or 'N/A'}: status={row[3]}, strategic={row[4]}, existing={row[5]}")
    
    cur.close()
    conn.close()
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
