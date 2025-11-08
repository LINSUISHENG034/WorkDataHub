#!/usr/bin/env python3
"""
Simple table inspection without pg_stat.
"""
import psycopg2

DSN = "postgres://postgres:Post.169828@localhost:5432/postgres"

def simple_table_check():
    """Simple check of all tables."""
    try:
        conn = psycopg2.connect(DSN)
        print("🔍 Simple table check...")

        with conn.cursor() as cursor:
            # Get all tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)

            tables = [row[0] for row in cursor.fetchall()]
            print(f"📋 Found tables: {tables}")

            # Check row counts
            print("\n📊 Row counts:")
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                    count = cursor.fetchone()[0]
                    print(f"   - {table}: {count} rows")

                    # If table has data, show structure
                    if count > 0:
                        cursor.execute(f"""
                            SELECT column_name, data_type
                            FROM information_schema.columns
                            WHERE table_name = '{table}' AND table_schema = 'public'
                            ORDER BY ordinal_position;
                        """)
                        columns = cursor.fetchall()
                        print(f"     Columns: {[f'{col}({typ})' for col, typ in columns]}")

                        # Show sample data
                        cursor.execute(f'SELECT * FROM "{table}" LIMIT 2;')
                        rows = cursor.fetchall()
                        for i, row in enumerate(rows):
                            print(f"     Row {i+1}: {row}")

                except Exception as e:
                    print(f"   ❌ Error checking {table}: {e}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

if __name__ == "__main__":
    simple_table_check()