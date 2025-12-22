"""
Diagnostic utilities for ETL CLI.

Story 7.4: CLI Layer Modularization - Database connection diagnostics.
"""

from work_data_hub.config.settings import get_settings


def _check_database_connection() -> int:
    """
    Test database connection and display diagnostic info.

    Story 6.2-P16 AC-2: Database connection diagnostics.
    Validates settings and attempts connection without running ETL.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("🔍 Database Connection Diagnostics")
    print("=" * 50)

    try:
        settings = get_settings()

        from pathlib import Path

        # Display DSN components (never show password)
        print(f"   Host: {settings.database_host}")
        print(f"   Port: {settings.database_port}")
        print(f"   Database: {settings.database_db}")
        print(f"   User: {settings.database_user}")
        print(f"   Password: {'***' if settings.database_password else '(not set)'}")
        env_file = Path(".wdh_env")
        print(
            f"   .wdh_env: {env_file.resolve()} "
            f"({('found' if env_file.exists() else 'missing')})"
        )

        # Validate required settings
        missing = []
        if not settings.database_host:
            missing.append("WDH_DATABASE__HOST")
        if not settings.database_port:
            missing.append("WDH_DATABASE__PORT")
        if not settings.database_db:
            missing.append("WDH_DATABASE__DB")
        if not settings.database_user:
            missing.append("WDH_DATABASE__USER")
        if not settings.database_password:
            missing.append("WDH_DATABASE__PASSWORD")

        if missing:
            print(f"\n❌ Missing required settings: {', '.join(missing)}")
            print("   Add these to your .wdh_env file")
            return 1

        # Attempt connection
        print("\n🔌 Attempting connection...", end=" ", flush=True)

        import psycopg2

        dsn = settings.get_database_connection_string()
        conn = None
        try:
            conn = psycopg2.connect(dsn)
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
        finally:
            if conn is not None:
                conn.close()

        print("✅ Connected!")
        print(
            f"\n📋 PostgreSQL: {version.split(',')[0] if ',' in version else version}"
        )
        print("=" * 50)
        print("✅ Database connection successful")
        return 0

    except Exception as e:
        print("❌ Failed")
        print(f"\n❌ Connection error: {e}")
        print("\n💡 Troubleshooting hints:")
        print("   - Verify WDH_DATABASE__* settings in .wdh_env")
        print("   - Check if PostgreSQL server is running")
        print("   - Verify network connectivity to database host")
        print("   - Confirm database user has login permissions")
        return 1
