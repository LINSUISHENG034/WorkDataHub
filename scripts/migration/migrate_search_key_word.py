"""
Migration script for search_key_word table from legacy to postgres
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".wdh_env")

# Connection strings
LEGACY_DB_URI = os.getenv(
    "LEGACY_DATABASE__URI", "postgres://postgres:Post.169828@localhost:5432/legacy"
)
POSTGRES_DB_URI = os.getenv(
    "WDH_DATABASE__URI", "postgres://postgres:Post.169828@localhost:5432/postgres"
)


def migrate_data():
    """Migrate search_key_word table from legacy to postgres"""

    print("Starting migration...")

    # Connect to both databases
    legacy_conn = psycopg2.connect(LEGACY_DB_URI)
    postgres_conn = psycopg2.connect(POSTGRES_DB_URI)

    legacy_cur = legacy_conn.cursor()
    postgres_cur = postgres_conn.cursor()

    try:
        # Get total count
        legacy_cur.execute("SELECT COUNT(*) FROM enterprise.search_key_word")
        total_count = legacy_cur.fetchone()[0]
        print(f"Total records to migrate: {total_count}")

        # Fetch all data from legacy
        print("Fetching data from legacy database...")
        legacy_cur.execute(
            "SELECT key_word, type FROM enterprise.search_key_word ORDER BY type, key_word"
        )
        data = legacy_cur.fetchall()

        # Prepare batch insert
        print(f"Inserting {len(data)} records into postgres...")
        batch_size = 1000
        inserted = 0

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            postgres_cur.executemany(
                "INSERT INTO enterprise.search_key_word (key_word, type) VALUES (%s, %s) "
                "ON CONFLICT (key_word, type) DO NOTHING",
                batch,
            )
            postgres_conn.commit()
            inserted += len(batch)
            print(
                f"Progress: {inserted}/{len(data)} ({inserted / len(data) * 100:.1f}%)"
            )

        # Verify
        postgres_cur.execute("SELECT COUNT(*) FROM enterprise.search_key_word")
        final_count = postgres_cur.fetchone()[0]
        print("\nMigration complete!")
        print(f"  Legacy records: {total_count}")
        print(f"  Postgres records: {final_count}")

        if final_count == total_count:
            print("  ✓ All records migrated successfully!")
        else:
            print(
                f"  ⚠ Warning: Record count mismatch ({total_count - final_count} records missing)"
            )

        # Show breakdown by type
        print("\nRecords by type:")
        postgres_cur.execute(
            "SELECT type, COUNT(*) FROM enterprise.search_key_word GROUP BY type ORDER BY type"
        )
        for type_name, count in postgres_cur.fetchall():
            print(f"  {type_name}: {count:,}")

    except Exception as e:
        print(f"Error during migration: {e}")
        postgres_conn.rollback()
        raise
    finally:
        legacy_cur.close()
        postgres_cur.close()
        legacy_conn.close()
        postgres_conn.close()


if __name__ == "__main__":
    migrate_data()
