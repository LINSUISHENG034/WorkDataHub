"""Pytest configuration for optional legacy/E2E suites and DB fixtures.

IMPORTANT: .wdh_env is loaded FIRST with override=True to ensure all environment
variables come from .wdh_env file only, NOT from system environment variables.
This is the SINGLE SOURCE OF TRUTH for all configuration.
"""

from __future__ import annotations

# ============================================================================
# CRITICAL: Load .wdh_env FIRST, before any other imports
# override=True ensures .wdh_env values take precedence over system env vars
# ============================================================================
from pathlib import Path
from dotenv import load_dotenv

_WDH_ENV_FILE = Path(__file__).parent.parent / ".wdh_env"
if _WDH_ENV_FILE.exists():
    load_dotenv(_WDH_ENV_FILE, override=True)
else:
    import warnings

    warnings.warn(
        f".wdh_env not found at {_WDH_ENV_FILE}. "
        "Tests may use system environment variables which could be dangerous!"
    )

import os
import platform
import sys
from types import SimpleNamespace

from typing import Generator

import uuid
from urllib.parse import urlparse, urlunparse

import pytest
import psycopg2
from psycopg2 import sql

from work_data_hub.config import get_settings

# Ensure Settings() can initialize in test environments without bespoke .env files.
os.environ.setdefault("DATABASE_URL", "sqlite:///workdatahub_dev.db")

# Some environments have a broken/hanging `wmic` implementation, which can cause
# `platform.uname()` (and downstream imports like SQLAlchemy/Pandera) to hang at
# import time. Patch platform helpers for tests to avoid blocking collection.
if sys.platform.startswith("win"):
    platform.win32_ver = lambda *args, **kwargs: ("", "", "", "")  # type: ignore[assignment]
    _fake_uname = SimpleNamespace(
        system="Windows",
        node="",
        release="",
        version="",
        machine=os.environ.get("PROCESSOR_ARCHITECTURE", ""),
        processor=os.environ.get("PROCESSOR_ARCHITECTURE", ""),
    )
    platform.uname = lambda: _fake_uname  # type: ignore[assignment]
    platform.system = lambda: "Windows"  # type: ignore[assignment]
    platform.machine = lambda: _fake_uname.machine  # type: ignore[assignment]
    platform.processor = lambda: _fake_uname.processor  # type: ignore[assignment]

LEGACY_OPTION = "run_legacy_tests"
E2E_OPTION = "run_e2e_tests"
LEGACY_MARK = "legacy_suite"
E2E_MARK = "e2e_suite"
LEGACY_ENV = "RUN_LEGACY_TESTS"
E2E_ENV = "RUN_E2E_TESTS"


def _validate_test_database(dsn: str) -> bool:
    """Ensure we're not connected to production database.

    This safety check prevents accidental data loss by verifying the database
    name matches test database naming conventions before destructive operations.

    Args:
        dsn: Database connection string (SQLAlchemy/PostgreSQL URL format)

    Returns:
        True if database name matches test pattern

    Raises:
        RuntimeError: If database name doesn't match test pattern

    Examples:
        >>> _validate_test_database("postgresql://localhost/work_data_hub_test")
        True
        >>> _validate_test_database("postgresql://localhost/work_data_hub")
        Traceback (most recent call last):
        ...
        RuntimeError: Refusing to run tests against non-test database...
    """
    import re
    from sqlalchemy.engine.url import make_url

    # Allow override for debugging (use with extreme caution)
    if os.getenv("WDH_SKIP_DB_VALIDATION") == "1":
        return True

    db_name = make_url(dsn).database

    # Handle edge case: None or empty database name
    if not db_name:
        raise RuntimeError(
            f"Refusing to run tests against empty/missing database name. "
            f"Test databases must contain one of: test, tmp, dev, local, sandbox. "
            f"Override with WDH_SKIP_DB_VALIDATION=1 (DANGEROUS)."
        )

    test_db_pattern = r"(test|tmp|dev|local|sandbox)"

    if not re.search(test_db_pattern, db_name, re.IGNORECASE):
        raise RuntimeError(
            f"Refusing to run tests against non-test database: {db_name}. "
            f"Test databases must contain one of: test, tmp, dev, local, sandbox. "
            f"Override with WDH_SKIP_DB_VALIDATION=1 (DANGEROUS)."
        )
    return True


def _env_enabled(name: str) -> bool:
    """Return True when the opt-in environment flag is set to '1'."""
    return os.getenv(name) == "1"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI flags that mirror the RUN_* environment toggles."""
    parser.addoption(
        "--run-legacy-tests",
        action="store_true",
        dest=LEGACY_OPTION,
        default=_env_enabled(LEGACY_ENV),
        help="Run the legacy compatibility suite "
        "(set RUN_LEGACY_TESTS=1 or pass --run-legacy-tests).",
    )
    parser.addoption(
        "--run-e2e-tests",
        action="store_true",
        dest=E2E_OPTION,
        default=_env_enabled(E2E_ENV),
        help="Run the Dagster/warehouse end-to-end suite "
        "(set RUN_E2E_TESTS=1 or pass --run-e2e-tests).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip opt-in suites unless their corresponding flag is enabled."""
    run_legacy = config.getoption(LEGACY_OPTION)
    run_e2e = config.getoption(E2E_OPTION)

    skip_legacy = pytest.mark.skip(
        reason="Set RUN_LEGACY_TESTS=1 or pass --run-legacy-tests to run the legacy suite."
    )
    skip_e2e = pytest.mark.skip(
        reason="Set RUN_E2E_TESTS=1 or pass --run-e2e-tests to run the E2E suite."
    )

    for item in items:
        if LEGACY_MARK in item.keywords and not run_legacy:
            item.add_marker(skip_legacy)
            continue
        if E2E_MARK in item.keywords and not run_e2e:
            item.add_marker(skip_e2e)
            continue

        # Skip tests marked with needs_investigation due to complexity
        if "needs_investigation" in item.keywords:
            item.add_marker(
                pytest.mark.skip(
                    reason="Test needs investigation due to known complexity issues"
                )
            )
            continue


def _resolve_postgres_dsn() -> str:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get(
        "WDH_TEST_DATABASE_URI"
    )
    if not database_url or not database_url.startswith("postgres"):
        pytest.skip(
            "PostgreSQL DATABASE_URL/WDH_TEST_DATABASE_URI must be set for postgres-backed tests"
        )
    return database_url


def _create_ephemeral_database(base_dsn: str) -> tuple[str, str, str]:
    parsed = urlparse(base_dsn)
    base_db = parsed.path.lstrip("/") or "postgres"
    admin_db = "postgres" if base_db != "postgres" else base_db
    temp_db = f"{base_db}_test_{uuid.uuid4().hex[:8]}"

    admin_dsn = urlunparse(parsed._replace(path=f"/{admin_db}"))
    temp_dsn = urlunparse(parsed._replace(path=f"/{temp_db}"))

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(temp_db)
                )
            )
    finally:
        conn.close()

    return temp_dsn, temp_db, admin_dsn


def _drop_database(admin_dsn: str, db_name: str) -> None:
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            # Terminate any remaining connections to allow DROP DATABASE
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid();
                """,
                (db_name,),
            )
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
            )
    finally:
        conn.close()


@pytest.fixture
def postgres_db_with_migrations() -> Generator[str, None, None]:
    """Use a temporary PostgreSQL database, apply migrations, and yield DSN."""
    from work_data_hub.io.schema import migration_runner

    base_dsn = _resolve_postgres_dsn()
    temp_dsn, temp_db, admin_dsn = _create_ephemeral_database(base_dsn)

    original_database_url = os.environ.get("DATABASE_URL")
    original_wdh_database_uri = os.environ.get("WDH_DATABASE__URI")
    original_wdh_test_uri = os.environ.get("WDH_TEST_DATABASE_URI")

    os.environ["DATABASE_URL"] = temp_dsn
    os.environ["WDH_DATABASE__URI"] = temp_dsn
    os.environ["WDH_TEST_DATABASE_URI"] = temp_dsn
    get_settings.cache_clear()

    migration_runner.upgrade(temp_dsn)
    try:
        yield temp_dsn
    finally:
        _validate_test_database(
            temp_dsn
        )  # Safety check: prevent production DB clearing
        migration_runner.downgrade(temp_dsn, "base")
        _drop_database(admin_dsn, temp_db)
        get_settings.cache_clear()

        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url

        if original_wdh_database_uri is None:
            os.environ.pop("WDH_DATABASE__URI", None)
        else:
            os.environ["WDH_DATABASE__URI"] = original_wdh_database_uri

        if original_wdh_test_uri is None:
            os.environ.pop("WDH_TEST_DATABASE_URI", None)
        else:
            os.environ["WDH_TEST_DATABASE_URI"] = original_wdh_test_uri


@pytest.fixture
def test_db_with_migrations(postgres_db_with_migrations: str) -> str:
    """Backward-compatible alias for existing tests."""
    return postgres_db_with_migrations


@pytest.fixture
def postgres_connection(postgres_db_with_migrations: str):
    """Provide a live psycopg2 connection to the test database with migrations applied."""
    conn = psycopg2.connect(postgres_db_with_migrations, connect_timeout=5)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


# ============================================================================
# E2E Test Infrastructure: Domain and Mapping Tables (Story 7.1-13)
# ============================================================================


def _create_domain_tables(dsn: str, domains: list[str]) -> None:
    """Create domain tables for E2E testing.

    Uses generate_create_table_sql() from domain registry to create tables
    with correct schema including UNIQUE constraints needed for FK backfill.

    Must be called AFTER postgres_db_with_migrations fixture has applied
    Alembic migrations.

    Args:
        dsn: PostgreSQL connection string
        domains: List of domain names (e.g., ["annuity_performance", "annuity_income"])

    Raises:
        RuntimeError: If DDL generation or table creation fails for any domain
    """
    from work_data_hub.infrastructure.schema.ddl_generator import (
        generate_create_table_sql,
    )
    from work_data_hub.infrastructure.schema.registry import list_domains

    conn = psycopg2.connect(dsn)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            # Create business schema if not exists
            cur.execute("CREATE SCHEMA IF NOT EXISTS business")

            # Validate domains are registered
            registered_domains = list_domains()
            for domain in domains:
                if domain not in registered_domains:
                    raise RuntimeError(
                        f"Domain '{domain}' is not registered. "
                        f"Available domains: {sorted(registered_domains)}"
                    )

            # Create domain tables
            for domain in domains:
                try:
                    create_sql = generate_create_table_sql(domain)
                    cur.execute(create_sql)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to create table for domain '{domain}': {e}"
                    )
    finally:
        conn.close()


def _create_mapping_tables(dsn: str) -> None:
    """Create mapping tables with required UNIQUE constraints.

    Mapping tables are required for FK backfill ON CONFLICT operations.
    - annuity_plans: UNIQUE constraint on 年金计划号 (Story 7.1-12)
    - portfolio_plans: Composite index on (年金计划号, 组合代码)

    Args:
        dsn: PostgreSQL connection string

    Raises:
        RuntimeError: If table creation fails
    """
    from work_data_hub.infrastructure.schema.ddl_generator import (
        generate_create_table_sql,
    )

    conn = psycopg2.connect(dsn)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            # Create mapping schema if not exists
            cur.execute("CREATE SCHEMA IF NOT EXISTS mapping")

            # Create annuity_plans (has UNIQUE on 年金计划号 per Story 7.1-12)
            cur.execute(generate_create_table_sql("annuity_plans"))

            # Create portfolio_plans (has composite index for ON CONFLICT)
            cur.execute(generate_create_table_sql("portfolio_plans"))
    finally:
        conn.close()


@pytest.fixture
def postgres_db_with_domain_tables(
    postgres_db_with_migrations: str,
) -> Generator[str, None, None]:
    """Extend base fixture with domain and mapping tables for E2E testing.

    Creates:
    - Domain tables: business.规模明细, business.收入明细
    - Mapping tables: mapping.年金计划, mapping.组合计划

    Scope: function (matches base fixture scope to avoid ScopeMismatch errors).

    Cleanup: Handled by base fixture's ephemeral database drop (no explicit
    cleanup needed - tables are dropped when the temp DB is dropped).

    Args:
        postgres_db_with_migrations: DSN for test DB with migrations applied

    Yields:
        str: DSN for test database with domain and mapping tables created
    """
    _create_domain_tables(
        postgres_db_with_migrations, ["annuity_performance", "annuity_income"]
    )
    _create_mapping_tables(postgres_db_with_migrations)
    yield postgres_db_with_migrations
    # No explicit cleanup needed - base fixture drops entire ephemeral DB
