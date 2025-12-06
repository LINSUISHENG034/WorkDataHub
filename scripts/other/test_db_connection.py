#!/usr/bin/env python3
"""
Test PostgreSQL database connection and setup reference tables.
"""

import sys

import psycopg2

# Database connection string
DSN = "postgres://postgres:Post.169828@localhost:5432/postgres"


def test_connection():
    """Test basic database connection."""
    try:
        conn = psycopg2.connect(DSN)
        print("✅ Database connection successful")

        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"✅ PostgreSQL version: {version}")

            cursor.execute("SELECT current_database(), current_schema();")
            db, schema = cursor.fetchone()
            print(f"✅ Current database: {db}, schema: {schema}")

        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def setup_reference_tables():
    """Create reference tables for testing."""
    try:
        conn = psycopg2.connect(DSN)
        print("✅ Creating reference tables...")

        with conn.cursor() as cursor:
            # Create 年金计划 table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "年金计划" (
                    "年金计划号" TEXT PRIMARY KEY,
                    "计划全称" TEXT,
                    "计划类型" TEXT,
                    "客户名称" TEXT,
                    "company_id" VARCHAR(50)
                );
            """)

            # Create 组合计划 table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "组合计划" (
                    "组合代码" TEXT PRIMARY KEY,
                    "年金计划号" TEXT,
                    "组合名称" TEXT,
                    "组合类型" TEXT,
                    "运作开始日" DATE
                );
            """)

            # Create unique indexes for ON CONFLICT
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_年金计划_年金计划号"
                ON "年金计划" ("年金计划号");
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_组合计划_组合代码"
                ON "组合计划" ("组合代码");
            """)

        conn.commit()
        print("✅ Reference tables created successfully")

        # Verify tables exist
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('年金计划', '组合计划');
            """)
            tables = cursor.fetchall()
            print(f"✅ Found tables: {[t[0] for t in tables]}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to setup reference tables: {e}")
        return False


def check_table_counts():
    """Check current row counts in reference tables."""
    try:
        conn = psycopg2.connect(DSN)

        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM "年金计划";')
            plan_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM "组合计划";')
            portfolio_count = cursor.fetchone()[0]

            print(
                f"✅ Current counts - 年金计划: {plan_count}, 组合计划: {portfolio_count}"
            )

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Failed to check table counts: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Testing PostgreSQL connection...")

    if not test_connection():
        sys.exit(1)

    if not setup_reference_tables():
        sys.exit(1)

    if not check_table_counts():
        sys.exit(1)

    print("✅ Database setup completed successfully!")
    print(f"📊 Use this connection string: WDH_DATABASE__URI={DSN}")
