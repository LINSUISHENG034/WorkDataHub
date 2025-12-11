#!/usr/bin/env python3
"""
测试同步脚本

用于快速测试MySQL到PostgreSQL的schema同步功能。
"""

import os
import sys
from pathlib import Path

# 设置Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from sqlglot_parser import SQLGlotParser
from ddl_generator import PostgreSQLDDLGenerator


def test_sql_parsing():
    """测试SQL解析功能"""
    print("=== 测试SQL解析功能 ===")

    # 使用绝对路径
    sql_dir = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "legacy_db" / "schema"
    sql_file = sql_dir / "business" / "规模明细.sql"

    if not sql_file.exists():
        print(f"❌ SQL文件不存在: {sql_file}")
        return False

    parser = SQLGlotParser()
    table_def = parser.parse_sql_file(sql_file)

    if table_def:
        print(f"✅ 解析成功: {table_def}")
        print(f"   索引数量: {len(table_def.indexes)}")
        print(f"   外键数量: {len(table_def.foreign_keys)}")

        print("\n  索引列表:")
        for idx in table_def.indexes:
            print(f"    - {idx.name}: {idx.columns}")

        print("\n  外键列表:")
        for fk in table_def.foreign_keys:
            print(f"    - {fk.name}: {fk.columns} -> {fk.ref_table}.{fk.ref_columns}")

        return True
    else:
        print("❌ 解析失败")
        return False


def test_ddl_generation():
    """测试DDL生成功能"""
    print("\n=== 测试DDL生成功能 ===")

    from sqlglot_parser import MySQLIndex, MySQLForeignKey

    # 创建测试索引
    test_indexes = [
        MySQLIndex("KY_客户名称", ["客户名称"], "INDEX", False),
        MySQLIndex("FK_组织架构_规模明细", ["机构代码"], "INDEX", False),
        MySQLIndex("PRIMARY", ["id"], "PRIMARY", True)
    ]

    # 创建测试外键
    test_foreign_keys = [
        MySQLForeignKey(
            "规模明细_ibfk_1",
            ["产品线代码"],
            "产品线",
            ["产品线代码"],
            "RESTRICT",
            "CASCADE"
        )
    ]

    # 生成DDL
    generator = PostgreSQLDDLGenerator("business", "规模明细")

    print("\n  生成的索引DDL:")
    for idx in test_indexes:
        ddl = generator.generate_create_index_sql(idx)
        print(f"    {idx.name}:")
        print(f"      {ddl[:50]}...")

    print("\n  生成的外键DDL:")
    for fk in test_foreign_keys:
        ddl = generator.generate_alter_table_foreign_key_sql(fk)
        print(f"    {fk.name}:")
        print(f"      {ddl[:50]}...")

    print("✅ DDL生成测试完成")
    return True


def main():
    """主测试函数"""
    print("MySQL到PostgreSQL Schema同步工具 - 测试")
    print("=" * 60)

    # 测试环境变量
    db_connection = (
        os.getenv('WDH_DATABASE__URI') or
        os.getenv('DATABASE_URL')
    )

    if db_connection:
        print(f"✅ 数据库连接: {db_connection[:30]}...")
    else:
        print("⚠️ 未设置数据库连接环境变量")

    # 运行测试
    success = True
    success &= test_sql_parsing()
    success &= test_ddl_generation()

    print("\n" + "=" * 60)
    if success:
        print("✅ 所有测试通过")
    else:
        print("❌ 部分测试失败")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)