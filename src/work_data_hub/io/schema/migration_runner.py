"""Programmatic helpers for invoking Alembic migrations (Story 1.7)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config

from work_data_hub.config import get_settings
from work_data_hub.utils.logging import get_logger

LOGGER = get_logger("work_data_hub.io.schema.migration_runner")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
MIGRATIONS_DIR = PROJECT_ROOT / "io" / "schema" / "migrations"


def _build_config(database_url: Optional[str]) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if database_url:
        cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade(database_url: Optional[str] = None, revision: str = "head") -> None:
    """Run ``alembic upgrade`` programmatically."""
    cfg = _build_config(database_url)
    command.upgrade(cfg, revision)
    LOGGER.info("alembic.upgrade", revision=revision, url=cfg.get_main_option("sqlalchemy.url"))


def downgrade(database_url: Optional[str] = None, revision: str = "-1") -> None:
    """Run ``alembic downgrade`` programmatically."""
    cfg = _build_config(database_url)
    command.downgrade(cfg, revision)
    LOGGER.info("alembic.downgrade", revision=revision, url=cfg.get_main_option("sqlalchemy.url"))


def stamp(database_url: Optional[str] = None, revision: str = "head") -> None:
    """Mark the database with a specific revision without running migrations."""
    cfg = _build_config(database_url)
    command.stamp(cfg, revision)
    LOGGER.info("alembic.stamp", revision=revision, url=cfg.get_main_option("sqlalchemy.url"))


def get_default_database_url() -> str:
    """Return the connection string defined by application settings."""
    settings = get_settings()
    return settings.get_database_connection_string()
