#!/usr/bin/env python
"""Verify Legacy PostgreSQL database connection for Epic 8.

This script verifies the connection to the Legacy PostgreSQL database
(migrated from MySQL in Story 6.2-P1) required for Epic 8 Golden Dataset comparison.

Verification checks:
1. WDH_LEGACY_* environment variables are set (AC-1)
2. PostgresSourceAdapter can be instantiated (AC-2)
3. Database connection works (AC-3)
4. Reference tables are accessible (AC-4)

Usage:
    uv run --env-file .wdh_env python scripts/validation/verify_legacy_db_connection.py
"""

import os
import sys

from work_data_hub.io.connectors.postgres_source_adapter import PostgresSourceAdapter


def check_env_vars() -> bool:
    """Check WDH_LEGACY_* environment variables (AC-1)."""
    required_vars = [
        "WDH_LEGACY_HOST",
        "WDH_LEGACY_PORT",
        "WDH_LEGACY_DATABASE",
        "WDH_LEGACY_USER",
        "WDH_LEGACY_PASSWORD",
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value is None or value == "":
            missing.append(var)

    if missing:
        print("  ✗ Missing environment variables:")
        for var in missing:
            print(f"    - {var}")
        return False

    print("  ✓ All WDH_LEGACY_* environment variables are set")
    return True


def check_adapter_config(adapter: PostgresSourceAdapter) -> bool:
    """Check PostgresSourceAdapter configuration (AC-2)."""
    print("\n[AC-2] PostgresSourceAdapter Configuration:")
    print(f"  Host: {adapter.host}")
    print(f"  Port: {adapter.port}")
    print(f"  Database: {adapter.database}")
    print(f"  User: {adapter.user}")
    print("  ✓ PostgresSourceAdapter configured successfully")
    return True


def check_connection(adapter: PostgresSourceAdapter) -> bool:
    """Test database connection (AC-3)."""
    print("\n[AC-3] Testing Database Connection...")

    try:
        with adapter.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version()")
                row = cursor.fetchone()
                # RealDictCursor returns dict, not tuple
                version = row.get("version", "") if row else ""
                print("  ✓ Connected to PostgreSQL")
                print(f"  Version: {version[:80]}...")
                return True
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False


def check_reference_tables(adapter: PostgresSourceAdapter) -> bool:
    """Verify reference data tables (AC-4)."""
    print("\n[AC-4] Checking Reference Tables...")

    tables = [
        ("enterprise", "annuity_plan"),
        ("enterprise", "portfolio_plan"),
        ("enterprise", "organization"),
    ]

    all_passed = True

    with adapter.get_connection() as conn:
        with conn.cursor() as cursor:
            for schema, table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                    row = cursor.fetchone()
                    # RealDictCursor returns dict, not tuple
                    count = list(row.values())[0] if row else 0
                    print(f"  ✓ {schema}.{table}: {count} rows")
                except Exception as e:
                    print(f"  ✗ {schema}.{table}: Failed - {e}")
                    all_passed = False

    return all_passed


def main() -> int:
    """Run all verification checks."""
    print("=" * 60)
    print("Legacy PostgreSQL Connection Verification")
    print("=" * 60)

    # Check environment variables
    print("\n[AC-1] Checking Environment Variables...")
    if not check_env_vars():
        print("\n✗ FAILED: Missing required environment variables")
        print("\nPlease add the following to your .wdh_env file:")
        print("  WDH_LEGACY_HOST=localhost")
        print("  WDH_LEGACY_PORT=5432")
        print("  WDH_LEGACY_DATABASE=legacy")
        print("  WDH_LEGACY_USER=postgres")
        print("  WDH_LEGACY_PASSWORD=***")
        return 1

    # Instantiate adapter
    print("\nInstantiating PostgresSourceAdapter...")
    adapter = PostgresSourceAdapter(connection_env_prefix="WDH_LEGACY")

    # Check adapter configuration
    if not check_adapter_config(adapter):
        print("\n✗ FAILED: PostgresSourceAdapter configuration")
        return 1

    # Test connection
    if not check_connection(adapter):
        print("\n✗ FAILED: Database connection")
        return 1

    # Check reference tables
    if not check_reference_tables(adapter):
        print("\n✗ FAILED: Reference tables")
        return 1

    # All checks passed
    print("\n" + "=" * 60)
    print("✓ All checks passed!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
