#!/usr/bin/env python3
"""
手动测试验证脚本 - 检查数据库结构与项目要求的对比
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=os.getenv("WDH_DATABASE_HOST"),
        port=os.getenv("WDH_DATABASE_PORT"),
        user=os.getenv("WDH_DATABASE_USER"),
        password=os.getenv("WDH_DATABASE_PASSWORD"),
        database=os.getenv("WDH_DATABASE_DB")
    )

def check_table_structure():
    """检查规模明细表的结构"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = '规模明细'
                );
            """)
            table_exists = cur.fetchone()['exists']
            print(f"表'规模明细'是否存在: {table_exists}")
            
            if not table_exists:
                print("❌ 表不存在！需要创建表。")
                return
            
            # 获取列信息
            cur.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = '规模明细'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            
            print(f"\n📋 当前表结构 ({len(columns)} 列):")
            print("-" * 80)
            for col in columns:
                default = col['column_default'] or 'NULL'
                max_len = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
                print(f"  {col['column_name']:<25} {col['data_type']}{max_len:<15} "
                     f"nullable:{col['is_nullable']:<5} default:{default}")
            
            # 检查id列是否为自增
            cur.execute("""
                SELECT 
                    column_name,
                    column_default,
                    is_identity,
                    identity_generation
                FROM information_schema.columns 
                WHERE table_name = '规模明细' AND column_name = 'id';
            """)
            id_info = cur.fetchone()
            if id_info:
                print(f"\n🔍 ID列详细信息:")
                print(f"  列名: {id_info['column_name']}")
                print(f"  默认值: {id_info['column_default']}")
                print(f"  是否为标识列: {id_info.get('is_identity', 'N/A')}")
                print(f"  标识生成方式: {id_info.get('identity_generation', 'N/A')}")
            
            # 检查关键列是否存在
            required_columns = [
                "流失(含待遇支付)",
                "月度", 
                "计划代码", 
                "company_id"
            ]
            
            existing_column_names = [col['column_name'] for col in columns]
            
            print(f"\n✅ 关键列检查:")
            for req_col in required_columns:
                exists = req_col in existing_column_names
                status = "✅" if exists else "❌"
                print(f"  {status} {req_col}")
            
            # 检查主键
            cur.execute("""
                SELECT 
                    tc.constraint_name, 
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = '规模明细' AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position;
            """)
            pk_columns = cur.fetchall()
            
            print(f"\n🔑 主键信息:")
            if pk_columns:
                pk_cols = [col['column_name'] for col in pk_columns]
                print(f"  当前主键: {pk_cols}")
            else:
                print("  ❌ 未找到主键定义")
                
            # 期望的主键应该是 ["月度", "计划代码", "company_id"] 
            expected_pk = ["月度", "计划代码", "company_id"]
            if pk_columns:
                actual_pk = [col['column_name'] for col in pk_columns]
                if actual_pk == expected_pk:
                    print(f"  ✅ 主键符合期望: {expected_pk}")
                else:
                    print(f"  ❌ 主键不符合期望")
                    print(f"      期望: {expected_pk}")
                    print(f"      实际: {actual_pk}")
                    
    except Exception as e:
        print(f"❌ 数据库查询错误: {e}")
    finally:
        conn.close()

def compare_with_ddl():
    """与DDL文件对比"""
    print(f"\n📄 DDL文件期望的结构:")
    expected_structure = [
        ("id", "INTEGER", "GENERATED ALWAYS AS IDENTITY"),
        ("月度", "DATE", ""),
        ("业务类型", "VARCHAR(255)", ""),
        ("计划类型", "VARCHAR(255)", ""),
        ("计划代码", "VARCHAR(255)", ""),
        ("计划名称", "VARCHAR(255)", ""),
        ("组合类型", "VARCHAR(255)", ""),
        ("组合代码", "VARCHAR(255)", ""),
        ("组合名称", "VARCHAR(255)", ""),
        ("客户名称", "VARCHAR(255)", ""),
        ("期初资产规模", "double precision", ""),
        ("期末资产规模", "double precision", ""),
        ("供款", "double precision", ""),
        ("流失(含待遇支付)", "double precision", ""),  # 关键列！
        ("流失", "double precision", ""),
        ("待遇支付", "double precision", ""),
        ("投资收益", "double precision", ""),
        ("当期收益率", "double precision", ""),
        ("机构代码", "VARCHAR(255)", ""),
        ("机构名称", "VARCHAR(255)", ""),
        ("产品线代码", "VARCHAR(255)", ""),
        ("年金账户号", "VARCHAR(50)", ""),
        ("年金账户名", "VARCHAR(255)", ""),
        ("company_id", "VARCHAR(50)", ""),
    ]
    
    print("期望的列结构:")
    for col_name, col_type, extra in expected_structure:
        extra_info = f" {extra}" if extra else ""
        print(f"  {col_name:<25} {col_type}{extra_info}")

if __name__ == "__main__":
    print("🔍 数据库结构验证开始...")
    print("=" * 80)
    
    try:
        check_table_structure()
        compare_with_ddl()
        
        print(f"\n📝 建议:")
        print("1. 如果表结构不符合最新DDL，建议删除现有表并重新创建")
        print("2. 确保'流失(含待遇支付)'列存在（这是别名序列化的关键测试点）")
        print("3. 确保id列是GENERATED ALWAYS AS IDENTITY")
        print("4. 确保主键是复合主键: [月度, 计划代码, company_id]")
        
    except Exception as e:
        print(f"❌ 脚本执行错误: {e}")
    
    print("=" * 80)
    print("🔍 数据库结构验证完成")