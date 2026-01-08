"""Programmatic helpers for invoking Alembic migrations (Story 1.7).

Critical Issue 001 Fix: Added multi-layer defense against accidental
production database operations. See docs/specific/critical/001_downgrade_db.md
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config

from work_data_hub.config import get_settings
from work_data_hub.utils.logging import get_logger

LOGGER = get_logger("work_data_hub.io.schema.migration_runner")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
MIGRATIONS_DIR = PROJECT_ROOT / "io" / "schema" / "migrations"

# Layer 3: Production database protection patterns
# Databases matching TEST_SAFE_PATTERNS are considered safe for destructive ops
TEST_SAFE_PATTERNS: tuple[str, ...] = (
    r"test",
    r"tmp",
    r"dev",
    r"local",
    r"sandbox",
    r"wdh_test_",  # Ephemeral test database prefix from conftest.py
)

# Databases matching PRODUCTION_PATTERNS require explicit override
PRODUCTION_PATTERNS: tuple[str, ...] = (
    r"prod",
    r"production",
    r"live",
    r"master",
)

# Compile patterns once for performance
_TEST_SAFE_RE = re.compile("|".join(TEST_SAFE_PATTERNS), re.IGNORECASE)
_PRODUCTION_RE = re.compile("|".join(PRODUCTION_PATTERNS), re.IGNORECASE)


def _is_safe_database(url: str) -> bool:
    """Check if database URL matches safe test patterns.

    Args:
        url: Database connection string

    Returns:
        True if database name matches test-safe patterns
    """
    parsed = urlparse(url)
    db_name = (parsed.path or "").lstrip("/").lower()
    return bool(_TEST_SAFE_RE.search(db_name))


def _is_production_database(url: str) -> bool:
    """Check if database URL appears to be a production database.

    A database is considered "production" if:
    1. It matches production naming patterns, OR
    2. It does NOT match any test-safe patterns (fail-safe default)

    Args:
        url: Database connection string

    Returns:
        True if database appears to be production
    """
    parsed = urlparse(url)
    db_name = (parsed.path or "").lstrip("/").lower()
    host = (parsed.hostname or "").lower()

    # If matches test-safe pattern, definitely not production
    if _TEST_SAFE_RE.search(db_name):
        return False

    # If matches production pattern, definitely production
    if _PRODUCTION_RE.search(db_name) or _PRODUCTION_RE.search(host):
        return True

    # Fail-safe: if no test pattern matched, assume production
    return True


def _build_config(database_url: Optional[str]) -> Config:
    """Build Alembic config with explicit URL passing (Layer 2).

    Args:
        database_url: Explicit database URL. If provided, it will be passed
            to env.py via x-argument to prevent override.

    Returns:
        Configured Alembic Config object
    """
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if database_url:
        # Layer 2: Use x-argument for explicit URL passing
        # env.py must respect this and not override it
        cfg.set_main_option("sqlalchemy.url", database_url)
        cfg.attributes["explicit_database_url"] = database_url
    return cfg


def upgrade(database_url: Optional[str] = None, revision: str = "head") -> None:
    """Run ``alembic upgrade`` programmatically."""
    cfg = _build_config(database_url)
    command.upgrade(cfg, revision)
    LOGGER.info(
        "alembic.upgrade", revision=revision, url=cfg.get_main_option("sqlalchemy.url")
    )


def downgrade(database_url: Optional[str] = None, revision: str = "-1") -> None:
    """Run ``alembic downgrade`` with production protection (Layer 3).

    This function includes critical safety checks to prevent accidental
    downgrade operations on production databases.

    Args:
        database_url: Target database URL
        revision: Target revision (default: one step back)

    Raises:
        RuntimeError: If attempting to downgrade a production database
            without explicit override
    """
    cfg = _build_config(database_url)
    resolved_url = cfg.get_main_option("sqlalchemy.url") or ""

    # Layer 3: Production database protection
    if _is_production_database(resolved_url):
        override = os.getenv("WDH_ALLOW_PRODUCTION_DOWNGRADE")
        if override != "I_KNOW_WHAT_I_AM_DOING":
            # Mask password in error message
            safe_url = re.sub(r"://[^:]+:[^@]+@", "://***:***@", resolved_url)
            raise RuntimeError(
                f"BLOCKED: Refusing to downgrade potential production database.\n"
                f"Database: {safe_url}\n"
                f"To override, set WDH_ALLOW_PRODUCTION_DOWNGRADE="
                f"'I_KNOW_WHAT_I_AM_DOING'\n"
                f"WARNING: This will cause DATA LOSS. Ensure you have backups."
            )
        LOGGER.warning(
            "alembic.downgrade.production_override",
            url=resolved_url[:50],
            revision=revision,
        )

    command.downgrade(cfg, revision)
    LOGGER.info(
        "alembic.downgrade",
        revision=revision,
        url=cfg.get_main_option("sqlalchemy.url"),
    )


def stamp(database_url: Optional[str] = None, revision: str = "head") -> None:
    """Mark the database with a specific revision without running migrations."""
    cfg = _build_config(database_url)
    command.stamp(cfg, revision)
    LOGGER.info(
        "alembic.stamp", revision=revision, url=cfg.get_main_option("sqlalchemy.url")
    )


def get_default_database_url() -> str:
    """Return the connection string defined by application settings."""
    settings = get_settings()
    return settings.get_database_connection_string()
