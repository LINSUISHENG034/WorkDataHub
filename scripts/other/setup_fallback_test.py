#!/usr/bin/env python3
"""
Drop unique indexes to test fallback path.
"""

import psycopg2

DSN = "postgres://postgres:Post.169828@localhost:5432/postgres"


def drop_unique_indexes():
    """Drop unique indexes to force fallback path."""
    try:
        conn = psycopg2.connect(DSN)
        print("🗑️ Dropping unique indexes to test fallback...")

        with conn.cursor() as cursor:
            # First truncate the tables
            cursor.execute('TRUNCATE TABLE "年金计划";')
            cursor.execute('TRUNCATE TABLE "组合计划";')
            print("✅ Truncated reference tables")

            # Drop unique indexes to force fallback
            cursor.execute('DROP INDEX IF EXISTS "uq_年金计划_年金计划号";')
            cursor.execute('DROP INDEX IF EXISTS "uq_组合计划_组合代码";')
            print("✅ Dropped unique indexes")

            # Verify indexes are gone
            cursor.execute("""
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('年金计划', '组合计划')
                AND indexname LIKE 'uq_%'
                ORDER BY tablename, indexname;
            """)
            unique_indexes = cursor.fetchall()

            if unique_indexes:
                print(f"⚠️ Still found unique indexes: {unique_indexes}")
            else:
                print("✅ All unique indexes removed - fallback path will be used")

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to drop indexes: {e}")
        return False


def check_final_counts():
    """Check final row counts."""
    try:
        conn = psycopg2.connect(DSN)

        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM "年金计划";')
            plan_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM "组合计划";')
            portfolio_count = cursor.fetchone()[0]

            print(
                f"📊 Final counts - 年金计划: {plan_count}, 组合计划: {portfolio_count}"
            )

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to check counts: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Testing fallback path without unique indexes...")

    if not drop_unique_indexes():
        exit(1)

    if not check_final_counts():
        exit(1)

    print("✅ Ready for fallback path testing!")
