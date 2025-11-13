"""Pytest configuration for optional legacy and E2E suites."""

from __future__ import annotations

import os
import pytest

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
