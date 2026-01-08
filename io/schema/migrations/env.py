"""Alembic environment configuration anchored in the IO layer (Story 1.7).

Critical Issue 001 Fix: Layer 1 - Only use get_settings() as fallback when
no explicit URL is provided. See docs/specific/critical/001_downgrade_db.md
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure project root is importable (parents[3] -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from work_data_hub.config import get_settings  # noqa: E402  (import after path fix)
from work_data_hub.utils.logging import get_logger  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = get_logger("work_data_hub.io.schema.migrations.env")

# Layer 1+2: URL resolution with correct priority
# Priority: explicit_url > get_settings() > alembic.ini default
explicit_url = config.attributes.get("explicit_database_url")

if explicit_url:
    # Highest priority: Explicit URL from migration_runner
    config.set_main_option("sqlalchemy.url", explicit_url)
    logger.info("migrations.explicit_url", url=explicit_url[:50])
else:
    # Normal case: Use get_settings() to read from .wdh_env
    try:
        settings = get_settings()
        database_url = settings.get_database_connection_string()
        config.set_main_option("sqlalchemy.url", database_url)
        logger.info("migrations.settings_url", url=database_url[:50])
    except Exception as exc:  # pragma: no cover
        # Fallback: Keep alembic.ini default if settings unavailable
        fallback_url = config.get_main_option("sqlalchemy.url")
        logger.warning(
            "migrations.settings_unavailable",
            error=str(exc),
            fallback_url=fallback_url,
        )

target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

    logger.info("migrations.completed_offline", url=url)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a SQLAlchemy Engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

    logger.info(
        "migrations.completed_online", url=config.get_main_option("sqlalchemy.url")
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
