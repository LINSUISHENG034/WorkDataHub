#!/usr/bin/env python3
"""
Schema diagnostics and detailed database inspection.
"""

import psycopg2

DSN = "postgres://postgres:Post.169828@localhost:5432/postgres"


def run_schema_diagnostics():
    """Run comprehensive schema diagnostics."""
    try:
        conn = psycopg2.connect(DSN)
        print("🔍 Running schema diagnostics...")

        with conn.cursor() as cursor:
            # Basic database info
            cursor.execute(
                "SELECT current_database(), current_schema(), current_setting('search_path');"
            )
            db, schema, search_path = cursor.fetchone()
            print(f"📊 Database: {db}, Schema: {schema}, Search path: {search_path}")

            # List all tables in public schema
            cursor.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            print("📋 Tables in public schema:")
            for table_name, table_type in tables:
                print(f"   - {table_name} ({table_type})")

            # Check reference tables specifically
            print("\n🔍 Reference table details:")

            # 年金计划 table
            try:
                cursor.execute('SELECT COUNT(*) FROM "年金计划";')
                plan_count = cursor.fetchone()[0]
                print(f"   - 年金计划: {plan_count} rows")

                cursor.execute("""
                    SELECT "年金计划号", "计划全称", "客户名称", "company_id"
                    FROM "年金计划"
                    LIMIT 5;
                """)
                rows = cursor.fetchall()
                if rows:
                    print("     Sample rows:")
                    for row in rows:
                        print(f"       {row}")

            except Exception as e:
                print(f"   ❌ Error checking 年金计划: {e}")

            # 组合计划 table
            try:
                cursor.execute('SELECT COUNT(*) FROM "组合计划";')
                portfolio_count = cursor.fetchone()[0]
                print(f"   - 组合计划: {portfolio_count} rows")

                cursor.execute("""
                    SELECT "组合代码", "年金计划号", "组合名称", "组合类型"
                    FROM "组合计划"
                    LIMIT 5;
                """)
                rows = cursor.fetchall()
                if rows:
                    print("     Sample rows:")
                    for row in rows:
                        print(f"       {row}")

            except Exception as e:
                print(f"   ❌ Error checking 组合计划: {e}")

            # Check indexes
            print("\n🔍 Indexes on reference tables:")
            cursor.execute("""
                SELECT indexname, tablename, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('年金计划', '组合计划')
                ORDER BY tablename, indexname;
            """)
            indexes = cursor.fetchall()
            for idx_name, tbl_name, idx_def in indexes:
                print(f"   - {tbl_name}.{idx_name}: {idx_def}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Schema diagnostics failed: {e}")
        return False


if __name__ == "__main__":
    run_schema_diagnostics()
