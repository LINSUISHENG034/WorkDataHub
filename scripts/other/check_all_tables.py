#!/usr/bin/env python3
"""
Check all table schemas and find where data is being inserted.
"""

import psycopg2

DSN = "postgres://postgres:Post.169828@localhost:5432/postgres"


def check_all_tables():
    """Check all tables for data and schema structure."""
    try:
        conn = psycopg2.connect(DSN)
        print("🔍 Checking all tables...")

        with conn.cursor() as cursor:
            # Get all tables with row counts
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY tablename;
            """)

            tables = cursor.fetchall()
            print("📊 Table statistics (schema, table, inserts, updates, deletes):")
            for schema, table, inserts, updates, deletes in tables:
                print(
                    f"   - {schema}.{table}: {inserts} inserts, {updates} updates, {deletes} deletes"
                )

            # Check actual row counts
            print("\n📋 Actual row counts:")
            for schema, table, _, _, _ in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                    count = cursor.fetchone()[0]
                    print(f"   - {table}: {count} rows")

                    # If table has data, show sample
                    if count > 0 and count < 20:
                        cursor.execute(f'SELECT * FROM "{table}" LIMIT 3;')
                        rows = cursor.fetchall()

                        # Get column names
                        cursor.execute(f"""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = '{table}' AND table_schema = 'public'
                            ORDER BY ordinal_position;
                        """)
                        columns = [row[0] for row in cursor.fetchall()]

                        print(f"     Columns: {columns}")
                        for row in rows[:2]:
                            print(f"     Sample: {dict(zip(columns, row))}")

                except Exception as e:
                    print(f"   ❌ Error checking {table}: {e}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False


if __name__ == "__main__":
    check_all_tables()
