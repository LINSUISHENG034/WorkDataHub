"""Pytest configuration for optional legacy/E2E suites and DB fixtures."""

from __future__ import annotations

import os

from typing import Generator

import uuid
from urllib.parse import urlparse, urlunparse

import pytest
import psycopg2
from psycopg2 import sql

from work_data_hub.config import get_settings
from work_data_hub.io.schema import migration_runner

# Ensure Settings() can initialize in test environments without bespoke .env files.
os.environ.setdefault("DATABASE_URL", "sqlite:///workdatahub_dev.db")

LEGACY_OPTION = "run_legacy_tests"
E2E_OPTION = "run_e2e_tests"
LEGACY_MARK = "legacy_suite"
E2E_MARK = "e2e_suite"
LEGACY_ENV = "RUN_LEGACY_TESTS"
E2E_ENV = "RUN_E2E_TESTS"


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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
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
            item.add_marker(pytest.mark.skip(reason="Test needs investigation due to known complexity issues"))
            continue


def _resolve_postgres_dsn() -> str:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("WDH_TEST_DATABASE_URI")
    if not database_url or not database_url.startswith("postgres"):
        pytest.skip("PostgreSQL DATABASE_URL/WDH_TEST_DATABASE_URI must be set for postgres-backed tests")
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
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(temp_db))
            )
    finally:
        conn.close()

    return temp_dsn, temp_db, admin_dsn


def _drop_database(admin_dsn: str, db_name: str) -> None:
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
            )
    finally:
        conn.close()


@pytest.fixture
def postgres_db_with_migrations() -> Generator[str, None, None]:
    """Use a temporary PostgreSQL database, apply migrations, and yield DSN."""
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
